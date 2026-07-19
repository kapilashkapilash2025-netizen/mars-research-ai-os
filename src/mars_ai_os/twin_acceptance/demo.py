from dataclasses import replace

from mars_ai_os.digital_twin import DigitalTwinEngine, create_provenance, reference_rover_state
from mars_ai_os.twin_acceptance import TwinAcceptanceGateway, create_candidate


def run_twin_acceptance_demo():
    p = create_provenance(
        configuration={"d": 1}, seed=13, assumptions=(), author="demo", recorded_at_s=0
    )
    e = DigitalTwinEngine(
        initial_state=reference_rover_state(),
        mission_id="m",
        seed=13,
        environment_id="e",
        timestamp_s=0,
        provenance=p,
    )
    source = e.live_snapshot
    candidate_snapshot = replace(
        source, timestamp_s=1, provenance=replace(p, recorded_at_s=1), snapshot_id=""
    )
    from mars_ai_os.digital_twin.models import TwinSnapshot

    candidate_snapshot = TwinSnapshot.create(
        timestamp_s=1,
        mission_id="m",
        seed=13,
        environment_id="e",
        state=source.state,
        provenance=replace(p, recorded_at_s=1),
    )
    c = create_candidate("demo", "recovery", source, candidate_snapshot, 5)
    g = TwinAcceptanceGateway(e)
    r = g.accept(c, 1)
    return {
        "decision": r.decision.value,
        "history": len(e.history.snapshots),
        "events": [x.event_type for x in g.events],
        "safety": "explicit gateway acceptance only",
    }
