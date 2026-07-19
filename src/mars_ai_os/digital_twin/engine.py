"""Canonical information-only state gateway for every OS subsystem."""

from __future__ import annotations

from dataclasses import replace

from mars_ai_os.digital_twin.diff import StateDifference, compare_snapshots
from mars_ai_os.digital_twin.events import (
    BatteryChanged,
    Event,
    EventBus,
    FaultDetected,
    MissionCompleted,
    MissionStarted,
    PredictionFinished,
    SnapshotCreated,
    TemperatureWarning,
)
from mars_ai_os.digital_twin.history import HistoricalTwin
from mars_ai_os.digital_twin.models import NamedValue, RoverState, TwinSnapshot
from mars_ai_os.digital_twin.prediction import PredictionRequest, PredictionResult, PredictiveTwin
from mars_ai_os.digital_twin.provenance import ProvenanceRecord


class DigitalTwinEngine:
    """Own live state, immutable history, predictions, diffs, and events.

    This API intentionally exposes no actuator command or hardware write method.
    """

    def __init__(
        self,
        *,
        initial_state: RoverState,
        mission_id: str,
        seed: int,
        environment_id: str,
        timestamp_s: float,
        provenance: ProvenanceRecord,
        event_bus: EventBus | None = None,
    ) -> None:
        self.events = event_bus or EventBus()
        self._mission_id = mission_id
        self._seed = seed
        self._environment_id = environment_id
        self._provenance = provenance
        self._live = TwinSnapshot.create(
            timestamp_s=timestamp_s,
            mission_id=mission_id,
            seed=seed,
            environment_id=environment_id,
            state=initial_state,
            provenance=provenance,
            metadata=(NamedValue("twin_kind", "live"),),
        )
        self.history = HistoricalTwin(self._live)
        self.predictive = PredictiveTwin()

    @property
    def live_snapshot(self) -> TwinSnapshot:
        return self._live

    def update_state(
        self,
        state: RoverState,
        *,
        timestamp_s: float,
        source: str,
        reason: str,
        provenance: ProvenanceRecord | None = None,
    ) -> tuple[TwinSnapshot, tuple[StateDifference, ...]]:
        if timestamp_s < self._live.timestamp_s:
            raise ValueError("Live state cannot move backward in time")
        before = self._live
        update_provenance = provenance or replace(
            self._provenance,
            author=source,
            recorded_at_s=timestamp_s,
        )
        after = TwinSnapshot.create(
            timestamp_s=timestamp_s,
            mission_id=self._mission_id,
            seed=self._seed,
            environment_id=self._environment_id,
            state=state,
            provenance=update_provenance,
            metadata=(
                NamedValue("reason", reason),
                NamedValue("source", source),
                NamedValue("twin_kind", "live"),
            ),
        )
        differences = compare_snapshots(before, after)
        self._live = after
        self.history.append(after)
        self.events.publish(SnapshotCreated(timestamp_s, after.snapshot_id))
        self._publish_change_events(before, after)
        return after, differences

    def predict(self, request: PredictionRequest) -> PredictionResult:
        result = self.predictive.predict(self._live, request)
        self.events.publish(
            PredictionFinished(self._live.timestamp_s, result.prediction_id, len(result.snapshots))
        )
        return result

    def _publish_change_events(self, before: TwinSnapshot, after: TwinSnapshot) -> None:
        old = before.state
        new = after.state
        if old.power.battery_soc_percent != new.power.battery_soc_percent:
            self.events.publish(
                BatteryChanged(
                    after.timestamp_s,
                    old.power.battery_soc_percent,
                    new.power.battery_soc_percent,
                )
            )
        if old.mission.phase == "idle" and new.mission.phase not in {"idle", "completed"}:
            self.events.publish(MissionStarted(after.timestamp_s, after.mission_id))
        if old.mission.phase != "completed" and new.mission.phase == "completed":
            self.events.publish(MissionCompleted(after.timestamp_s, after.mission_id))
        for fault in sorted(set(new.faults.faults) - set(old.faults.faults)):
            self.events.publish(FaultDetected(after.timestamp_s, fault))
        for warning in sorted(set(new.faults.warnings) - set(old.faults.warnings)):
            if "temperature" in warning.lower() or "thermal" in warning.lower():
                self.events.publish(TemperatureWarning(after.timestamp_s, warning))


def event_names(events: list[Event]) -> tuple[str, ...]:
    return tuple(type(event).__name__ for event in events)
