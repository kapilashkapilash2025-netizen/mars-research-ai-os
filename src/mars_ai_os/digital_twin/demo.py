"""Verified end-to-end demonstration used by the public CLI."""

from __future__ import annotations

from dataclasses import replace

from mars_ai_os.digital_twin.engine import DigitalTwinEngine, event_names
from mars_ai_os.digital_twin.events import (
    BatteryChanged,
    Event,
    EventBus,
    MissionStarted,
    PredictionFinished,
    SnapshotCreated,
)
from mars_ai_os.digital_twin.models import NamedValue, reference_rover_state
from mars_ai_os.digital_twin.prediction import PredictionRequest
from mars_ai_os.digital_twin.provenance import create_provenance


def run_twin_demo() -> dict[str, object]:
    state = reference_rover_state()
    provenance = create_provenance(
        configuration={"environment": "mars-reference-v1", "hardware": "eight-wheel-reference"},
        seed=13,
        assumptions=(
            "Battery capacity and power values are reference assumptions.",
            "Thermal prediction is a first-order estimate, not calibrated physics.",
        ),
        author="twin-demo",
        recorded_at_s=0.0,
    )
    bus = EventBus()
    recorded_events: list[Event] = []
    for event_type in (SnapshotCreated, BatteryChanged, MissionStarted, PredictionFinished):
        bus.subscribe(event_type, recorded_events.append)
    engine = DigitalTwinEngine(
        initial_state=state,
        mission_id="demo-mission",
        seed=13,
        environment_id="mars-reference-v1",
        timestamp_s=0.0,
        provenance=provenance,
        event_bus=bus,
    )
    initial_id = engine.live_snapshot.snapshot_id
    changed_state = replace(
        state,
        power=replace(state.power, battery_energy_wh=3_950.0, battery_soc_percent=79.0),
        thermal=replace(
            state.thermal,
            components_c=(
                NamedValue("battery", 21.0, "C"),
                NamedValue("compute", 38.0, "C"),
            ),
        ),
        mission=replace(
            state.mission,
            phase="executing",
            active_task="inspect_ridge",
            estimated_remaining_s=600.0,
        ),
    )
    current, differences = engine.update_state(
        changed_state,
        timestamp_s=60.0,
        source="twin-demo",
        reason="demonstrate canonical state update",
    )
    prediction = engine.predict(PredictionRequest(horizon_s=180.0, step_s=60.0))
    cursor = engine.history.cursor()
    stepped_backward = cursor.step_backward().snapshot_id
    stepped_forward = cursor.step_forward().snapshot_id
    branch = engine.history.branch(initial_id, "what-if-demo")

    return {
        "initial_snapshot": initial_id,
        "current_snapshot": current.snapshot_id,
        "snapshot_count": len(engine.history.snapshots),
        "differences": [item.description for item in differences],
        "prediction_id": prediction.prediction_id,
        "prediction_snapshots": len(prediction.snapshots),
        "prediction_unknowns": list(prediction.unknowns),
        "replay": {"backward": stepped_backward, "forward": stepped_forward},
        "branch": {
            "name": branch.branch_name,
            "parent_snapshot": branch.parent_snapshot_id,
            "snapshots": len(branch.snapshots),
        },
        "events": list(event_names(recorded_events)),
        "safety": "information-only; no hardware commands",
    }

