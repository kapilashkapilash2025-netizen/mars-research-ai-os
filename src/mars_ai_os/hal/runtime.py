"""Injected time, explicit registry, lifecycle rules, and append-only audit."""

from __future__ import annotations

from dataclasses import replace
from time import monotonic

from mars_ai_os.hal.models import DRIVE_MOTOR_IDS, AuditRecord, LifecycleState, fingerprint


class ManualClock:
    def __init__(self, initial_s: float = 0.0) -> None:
        self._now = initial_s

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("Manual clock cannot move backward")
        self._now += seconds


class MonotonicClock:
    def now(self) -> float:
        return monotonic()


VALID_TRANSITIONS = {
    LifecycleState.CREATED: {LifecycleState.INITIALIZED, LifecycleState.SHUTDOWN},
    LifecycleState.INITIALIZED: {
        LifecycleState.READY,
        LifecycleState.SAFE,
        LifecycleState.SHUTDOWN,
    },
    LifecycleState.READY: {
        LifecycleState.ACTIVE,
        LifecycleState.SAFE,
        LifecycleState.FAULTED,
        LifecycleState.STOPPED,
    },
    LifecycleState.ACTIVE: {
        LifecycleState.SAFE,
        LifecycleState.DEGRADED,
        LifecycleState.FAULTED,
        LifecycleState.STOPPED,
    },
    LifecycleState.DEGRADED: {LifecycleState.SAFE, LifecycleState.FAULTED, LifecycleState.STOPPED},
    LifecycleState.FAULTED: {LifecycleState.SAFE, LifecycleState.SHUTDOWN},
    LifecycleState.SAFE: {LifecycleState.READY, LifecycleState.STOPPED, LifecycleState.SHUTDOWN},
    LifecycleState.STOPPED: {LifecycleState.READY, LifecycleState.SAFE, LifecycleState.SHUTDOWN},
    LifecycleState.SHUTDOWN: set(),
}


class DeviceRegistry:
    def __init__(self) -> None:
        self._devices: dict[str, object] = {}

    def register(self, device: object) -> None:
        identity = device.identity
        if identity.device_id in self._devices:
            raise ValueError(f"Duplicate device ID: {identity.device_id}")
        self._devices[identity.device_id] = device

    def get(self, device_id: str) -> object | None:
        return self._devices.get(device_id)

    def all(self) -> tuple[object, ...]:
        return tuple(self._devices[key] for key in sorted(self._devices))

    def by_capability(self, capability: str) -> tuple[object, ...]:
        return tuple(d for d in self.all() if capability in d.identity.capabilities)

    def drive_motors(self) -> tuple[object, ...]:
        return tuple(
            self._devices[device_id] for device_id in DRIVE_MOTOR_IDS if device_id in self._devices
        )


class AuditStream:
    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    @property
    def records(self) -> tuple[AuditRecord, ...]:
        return tuple(self._records)

    def append(
        self, timestamp_s: float, action: str, device_id: str | None, detail: str
    ) -> AuditRecord:
        record = AuditRecord(len(self._records) + 1, timestamp_s, action, device_id, detail, "")
        record = replace(record, fingerprint=fingerprint(record))
        self._records.append(record)
        return record
