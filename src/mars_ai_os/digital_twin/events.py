"""Synchronous typed events emitted by information-model state changes."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar


@dataclass(frozen=True, slots=True)
class SnapshotCreated:
    timestamp_s: float
    snapshot_id: str


@dataclass(frozen=True, slots=True)
class BatteryChanged:
    timestamp_s: float
    before_percent: float | None
    after_percent: float | None


@dataclass(frozen=True, slots=True)
class MissionStarted:
    timestamp_s: float
    mission_id: str


@dataclass(frozen=True, slots=True)
class MissionCompleted:
    timestamp_s: float
    mission_id: str


@dataclass(frozen=True, slots=True)
class FaultDetected:
    timestamp_s: float
    fault: str


@dataclass(frozen=True, slots=True)
class TemperatureWarning:
    timestamp_s: float
    warning: str


@dataclass(frozen=True, slots=True)
class PredictionFinished:
    timestamp_s: float
    prediction_id: str
    snapshots: int


@dataclass(frozen=True, slots=True)
class PhysicsPredictionCompleted:
    timestamp_s: float
    source_snapshot_id: str
    predicted_snapshot_id: str
    fingerprint: str
    horizon_s: float
    timestep_s: float
    configuration_hash: str
    warnings: tuple[str, ...]
    assumptions: tuple[str, ...]
    model_version: str


Event = (
    SnapshotCreated
    | BatteryChanged
    | MissionStarted
    | MissionCompleted
    | FaultDetected
    | TemperatureWarning
    | PredictionFinished
    | PhysicsPredictionCompleted
)
E = TypeVar("E", bound=Event)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[type[Event], list[Callable[[Event], None]]] = defaultdict(list)

    def subscribe(self, event_type: type[E], callback: Callable[[E], None]) -> None:
        self._subscribers[event_type].append(callback)  # type: ignore[arg-type]

    def publish(self, event: Event) -> None:
        for callback in tuple(self._subscribers[type(event)]):
            callback(event)
