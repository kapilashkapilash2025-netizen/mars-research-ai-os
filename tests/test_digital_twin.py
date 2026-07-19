from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from mars_ai_os.digital_twin import (
    DigitalTwinEngine,
    EventBus,
    HistoricalTwin,
    PredictionAssumptions,
    PredictionRequest,
    TwinSnapshot,
    compare_snapshots,
    create_provenance,
    reference_rover_state,
)
from mars_ai_os.digital_twin.demo import run_twin_demo
from mars_ai_os.digital_twin.events import (
    BatteryChanged,
    FaultDetected,
    MissionStarted,
    PredictionFinished,
    SnapshotCreated,
    TemperatureWarning,
)
from mars_ai_os.digital_twin.models import HealthStatus, NamedValue
from mars_ai_os.digital_twin.provenance import ProvenanceRecord


def provenance(timestamp_s: float = 0.0) -> ProvenanceRecord:
    return create_provenance(
        configuration={"environment": "test", "model": "reference"},
        seed=42,
        assumptions=("Test values are deterministic fixtures.",),
        author="pytest",
        recorded_at_s=timestamp_s,
    )


def snapshot(timestamp_s: float = 0.0) -> TwinSnapshot:
    return TwinSnapshot.create(
        timestamp_s=timestamp_s,
        mission_id="test-mission",
        seed=42,
        environment_id="test-environment",
        state=reference_rover_state(),
        provenance=provenance(timestamp_s),
    )


def engine(event_bus: EventBus | None = None) -> DigitalTwinEngine:
    return DigitalTwinEngine(
        initial_state=reference_rover_state(),
        mission_id="test-mission",
        seed=42,
        environment_id="test-environment",
        timestamp_s=0.0,
        provenance=provenance(),
        event_bus=event_bus,
    )


def test_snapshot_is_immutable_and_deterministic() -> None:
    first = snapshot()
    second = snapshot()

    assert first == second
    assert first.snapshot_id == second.snapshot_id
    with pytest.raises(FrozenInstanceError):
        first.timestamp_s = 1.0  # type: ignore[misc]


def test_snapshot_id_changes_with_state_or_provenance() -> None:
    original = snapshot()
    state = reference_rover_state()
    changed = replace(state, power=replace(state.power, battery_soc_percent=79.0))
    changed_snapshot = TwinSnapshot.create(
        timestamp_s=0.0,
        mission_id="test-mission",
        seed=42,
        environment_id="test-environment",
        state=changed,
        provenance=provenance(),
    )

    assert original.snapshot_id != changed_snapshot.snapshot_id


def test_state_diff_is_deterministic_and_descriptive() -> None:
    before = snapshot()
    state = before.state
    changed = replace(
        state,
        power=replace(state.power, battery_soc_percent=75.0),
        hardware=replace(
            state.hardware,
            motors=(
                replace(state.hardware.motors[0], temperature_c=25.0),
                *state.hardware.motors[1:],
            ),
        ),
    )
    after = TwinSnapshot.create(
        timestamp_s=60.0,
        mission_id=before.mission_id,
        seed=before.seed,
        environment_id=before.environment_id,
        state=changed,
        provenance=provenance(60.0),
    )

    differences = compare_snapshots(before, after)

    assert differences == compare_snapshots(before, after)
    assert tuple(item.path for item in differences) == tuple(
        sorted(item.path for item in differences)
    )
    assert any("temperature_c increased" in item.description for item in differences)
    assert any("battery_soc_percent decreased" in item.description for item in differences)


def test_history_supports_load_replay_steps_and_branching() -> None:
    first = snapshot()
    history = HistoricalTwin(first)
    second = TwinSnapshot.create(
        timestamp_s=10.0,
        mission_id=first.mission_id,
        seed=first.seed,
        environment_id=first.environment_id,
        state=replace(
            first.state,
            mission=replace(first.state.mission, phase="executing", elapsed_s=10.0),
        ),
        provenance=provenance(10.0),
    )
    history.append(second)

    assert history.load(first.snapshot_id) == first
    assert history.replay() == (first, second)
    cursor = history.cursor(second.snapshot_id)
    assert cursor.step_backward() == first
    assert cursor.step_forward() == second
    branch = history.branch(first.snapshot_id, "what-if")
    assert branch.parent_snapshot_id == first.snapshot_id
    assert branch.snapshots == (first,)


def test_history_rejects_backward_time_and_duplicate_snapshots() -> None:
    first = snapshot(10.0)
    history = HistoricalTwin(first)

    with pytest.raises(ValueError, match="time ordered"):
        history.append(snapshot(5.0))
    with pytest.raises(ValueError, match="duplicated"):
        history.append(first)


def test_prediction_models_only_supported_future_state() -> None:
    twin = engine()
    state = twin.live_snapshot.state
    updated = replace(
        state,
        mission=replace(state.mission, phase="executing", estimated_remaining_s=180.0),
        communication=replace(state.communication, link_quality=0.8),
    )
    twin.update_state(updated, timestamp_s=60.0, source="test", reason="start mission")

    result = twin.predict(PredictionRequest(horizon_s=180.0, step_s=60.0))

    assert len(result.snapshots) == 3
    assert result.unknowns == ()
    assert result.snapshots[-1].state.power.battery_energy_wh == pytest.approx(4_000.9)
    assert result.snapshots[-1].state.mission.estimated_remaining_s == 0.0
    assert result.snapshots[-1].state.navigation == updated.navigation
    assert result.snapshots[-1].state.sensors == updated.sensors


def test_prediction_preserves_unknown_models_and_reports_them() -> None:
    twin = engine()
    assumptions = PredictionAssumptions(
        battery_efficiency=None,
        thermal_response_per_s=None,
        compute_heat_gain_c=None,
        mission_progress_rate=None,
        communication_period_s=None,
        communication_duration_s=None,
    )

    result = twin.predict(
        PredictionRequest(horizon_s=60.0, step_s=60.0, assumptions=assumptions)
    )

    assert result.snapshots[0].state == twin.live_snapshot.state
    assert result.unknowns == (
        "battery model inputs",
        "communication contact schedule",
        "mission progress rate",
        "thermal model inputs",
    )


def test_prediction_is_deterministic_for_same_snapshot_and_request() -> None:
    twin = engine()
    request = PredictionRequest(horizon_s=180.0, step_s=60.0)

    first = twin.predict(request)
    second = twin.predict(request)

    assert first == second
    assert tuple(item.snapshot_id for item in first.snapshots) == tuple(
        item.snapshot_id for item in second.snapshots
    )


def test_engine_publishes_typed_events_from_canonical_changes() -> None:
    bus = EventBus()
    events = []
    for event_type in (
        SnapshotCreated,
        BatteryChanged,
        MissionStarted,
        FaultDetected,
        TemperatureWarning,
        PredictionFinished,
    ):
        bus.subscribe(event_type, events.append)
    twin = engine(bus)
    state = twin.live_snapshot.state
    changed = replace(
        state,
        power=replace(state.power, battery_soc_percent=70.0),
        mission=replace(state.mission, phase="executing"),
        faults=replace(
            state.faults,
            faults=("motor_8_overcurrent",),
            warnings=("compute temperature warning",),
            health=HealthStatus.DEGRADED,
        ),
    )

    twin.update_state(changed, timestamp_s=10.0, source="test", reason="event test")
    twin.predict(PredictionRequest(horizon_s=60.0, step_s=60.0))

    assert [type(item) for item in events] == [
        SnapshotCreated,
        BatteryChanged,
        MissionStarted,
        FaultDetected,
        TemperatureWarning,
        PredictionFinished,
    ]


def test_engine_has_no_hardware_command_surface() -> None:
    twin = engine()
    forbidden = ("command", "actuate", "set_motor", "write_hardware", "drive")

    assert all(not hasattr(twin, name) for name in forbidden)


def test_demo_covers_update_diff_prediction_and_replay() -> None:
    result = run_twin_demo()

    assert result["snapshot_count"] == 2
    assert result["prediction_snapshots"] == 3
    assert result["branch"]["snapshots"] == 1  # type: ignore[index]
    assert result["safety"] == "information-only; no hardware commands"
    assert "BatteryChanged" in result["events"]  # type: ignore[operator]


def test_metadata_and_unknown_sensor_values_remain_explicit() -> None:
    state = reference_rover_state()

    lidar = next(item for item in state.sensors.readings if item.name == "lidar_nearest_range")
    assert lidar == NamedValue("lidar_nearest_range", None, "m")
