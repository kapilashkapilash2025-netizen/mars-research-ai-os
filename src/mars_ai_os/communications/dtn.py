"""Deterministic store-and-forward network for rover communication testing."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import IntEnum, StrEnum
from random import Random
from uuid import uuid4


class BundlePriority(IntEnum):
    EMERGENCY = 0
    HEALTH = 1
    NAVIGATION = 2
    SCIENCE = 3
    LOG = 4


class BundleState(StrEnum):
    ROVER_QUEUE = "rover_queue"
    ROVER_TO_RELAY = "rover_to_relay"
    RELAY_QUEUE = "relay_queue"
    RELAY_TO_EARTH = "relay_to_earth"
    PROPAGATING = "propagating"
    DELIVERED = "delivered"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CommunicationConfig:
    one_way_light_time_s: float = 12 * 60
    rover_relay_rate_bps: float = 2_000_000
    relay_earth_rate_bps: float = 1_000_000
    relay_contact_period_s: float = 10 * 60
    relay_contact_duration_s: float = 2 * 60
    dsn_contact_period_s: float = 15 * 60
    dsn_contact_duration_s: float = 10 * 60
    packet_loss_probability: float = 0.0
    max_retries: int = 3
    random_seed: int = 13

    def __post_init__(self) -> None:
        positive = (
            "one_way_light_time_s",
            "rover_relay_rate_bps",
            "relay_earth_rate_bps",
            "relay_contact_period_s",
            "relay_contact_duration_s",
            "dsn_contact_period_s",
            "dsn_contact_duration_s",
        )
        for name in positive:
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if self.relay_contact_duration_s > self.relay_contact_period_s:
            raise ValueError("relay contact duration cannot exceed its period")
        if self.dsn_contact_duration_s > self.dsn_contact_period_s:
            raise ValueError("DSN contact duration cannot exceed its period")
        if not 0 <= self.packet_loss_probability <= 1:
            raise ValueError("packet_loss_probability must be between zero and one")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")


@dataclass(slots=True)
class Bundle:
    topic: str
    size_bytes: int
    priority: BundlePriority
    created_at_s: float
    lifetime_s: float = 24 * 60 * 60
    bundle_id: str = field(default_factory=lambda: uuid4().hex[:12])
    state: BundleState = BundleState.ROVER_QUEUE
    attempts: int = 0
    delivered_at_s: float | None = None

    @property
    def expires_at_s(self) -> float:
        return self.created_at_s + self.lifetime_s

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["priority"] = self.priority.name.lower()
        data["state"] = self.state.value
        return data


@dataclass(slots=True)
class _Transfer:
    bundle: Bundle
    completes_at_s: float
    destination_state: BundleState


class MarsEarthNetwork:
    """Simulate scheduled DTN delivery through a Mars relay and Earth DSN."""

    def __init__(self, config: CommunicationConfig | None = None) -> None:
        self.config = config or CommunicationConfig()
        self.now_s = 0.0
        self.bundles: list[Bundle] = []
        self._rover_transfer: _Transfer | None = None
        self._relay_transfer: _Transfer | None = None
        self._propagating: list[tuple[float, Bundle]] = []
        self._random = Random(self.config.random_seed)

    def submit(
        self,
        topic: str,
        size_bytes: int,
        priority: BundlePriority,
        lifetime_s: float = 24 * 60 * 60,
    ) -> Bundle:
        if size_bytes <= 0:
            raise ValueError("Bundle size must be greater than zero")
        if lifetime_s <= 0:
            raise ValueError("Bundle lifetime must be greater than zero")
        bundle = Bundle(topic, size_bytes, priority, self.now_s, lifetime_s)
        self.bundles.append(bundle)
        return bundle

    def step(self, elapsed_s: float) -> None:
        if elapsed_s <= 0:
            raise ValueError("elapsed_s must be greater than zero")
        self.now_s += elapsed_s
        self._expire_bundles()
        self._complete_transfers()
        self._deliver_propagated_bundles()
        self._start_rover_transfer()
        self._start_relay_transfer()

    @property
    def relay_contact_active(self) -> bool:
        return _contact_active(
            self.now_s,
            self.config.relay_contact_period_s,
            self.config.relay_contact_duration_s,
        )

    @property
    def dsn_contact_active(self) -> bool:
        return _contact_active(
            self.now_s,
            self.config.dsn_contact_period_s,
            self.config.dsn_contact_duration_s,
        )

    def summary(self) -> dict[str, object]:
        counts = {state.value: 0 for state in BundleState}
        for bundle in self.bundles:
            counts[bundle.state.value] += 1
        return {
            "mission_time_s": self.now_s,
            "relay_contact": self.relay_contact_active,
            "dsn_contact": self.dsn_contact_active,
            "one_way_light_time_s": self.config.one_way_light_time_s,
            "bundles": counts,
        }

    def _expire_bundles(self) -> None:
        terminal = {BundleState.DELIVERED, BundleState.FAILED, BundleState.EXPIRED}
        for bundle in self.bundles:
            if bundle.state not in terminal and self.now_s >= bundle.expires_at_s:
                bundle.state = BundleState.EXPIRED
                if self._rover_transfer and self._rover_transfer.bundle is bundle:
                    self._rover_transfer = None
                if self._relay_transfer and self._relay_transfer.bundle is bundle:
                    self._relay_transfer = None

    def _complete_transfers(self) -> None:
        if self._rover_transfer and self.now_s >= self._rover_transfer.completes_at_s:
            transfer = self._rover_transfer
            self._rover_transfer = None
            self._finish_link(transfer)
        if self._relay_transfer and self.now_s >= self._relay_transfer.completes_at_s:
            transfer = self._relay_transfer
            self._relay_transfer = None
            if self._link_lost(transfer.bundle):
                return
            transfer.bundle.state = BundleState.PROPAGATING
            arrival = self.now_s + self.config.one_way_light_time_s
            self._propagating.append((arrival, transfer.bundle))

    def _finish_link(self, transfer: _Transfer) -> None:
        if self._link_lost(transfer.bundle):
            return
        transfer.bundle.state = transfer.destination_state

    def _link_lost(self, bundle: Bundle) -> bool:
        if self._random.random() >= self.config.packet_loss_probability:
            return False
        bundle.attempts += 1
        if bundle.attempts > self.config.max_retries:
            bundle.state = BundleState.FAILED
        elif bundle.state is BundleState.ROVER_TO_RELAY:
            bundle.state = BundleState.ROVER_QUEUE
        else:
            bundle.state = BundleState.RELAY_QUEUE
        return True

    def _deliver_propagated_bundles(self) -> None:
        pending = []
        for arrival_s, bundle in self._propagating:
            if bundle.state is BundleState.EXPIRED:
                continue
            if self.now_s >= arrival_s:
                bundle.state = BundleState.DELIVERED
                bundle.delivered_at_s = self.now_s
            else:
                pending.append((arrival_s, bundle))
        self._propagating = pending

    def _start_rover_transfer(self) -> None:
        if self._rover_transfer or not self.relay_contact_active:
            return
        bundle = self._next_bundle(BundleState.ROVER_QUEUE)
        if bundle is None:
            return
        bundle.state = BundleState.ROVER_TO_RELAY
        duration = bundle.size_bytes * 8 / self.config.rover_relay_rate_bps
        self._rover_transfer = _Transfer(bundle, self.now_s + duration, BundleState.RELAY_QUEUE)

    def _start_relay_transfer(self) -> None:
        if self._relay_transfer or not self.dsn_contact_active:
            return
        bundle = self._next_bundle(BundleState.RELAY_QUEUE)
        if bundle is None:
            return
        bundle.state = BundleState.RELAY_TO_EARTH
        duration = bundle.size_bytes * 8 / self.config.relay_earth_rate_bps
        self._relay_transfer = _Transfer(bundle, self.now_s + duration, BundleState.PROPAGATING)

    def _next_bundle(self, state: BundleState) -> Bundle | None:
        candidates = [bundle for bundle in self.bundles if bundle.state is state]
        if not candidates:
            return None
        return min(candidates, key=lambda item: (item.priority, item.created_at_s, item.bundle_id))


def _contact_active(now_s: float, period_s: float, duration_s: float) -> bool:
    return now_s % period_s < duration_s

