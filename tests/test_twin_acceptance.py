from dataclasses import replace

from mars_ai_os.digital_twin import DigitalTwinEngine, create_provenance, reference_rover_state
from mars_ai_os.digital_twin.models import TwinSnapshot
from mars_ai_os.twin_acceptance import (
    AcceptanceDecision,
    TwinAcceptanceGateway,
    _fp,
    create_candidate,
)
from mars_ai_os.twin_acceptance.demo import run_twin_acceptance_demo


def setup():
    p = create_provenance(
        configuration={"x": 1}, seed=13, assumptions=(), author="test", recorded_at_s=0
    )
    e = DigitalTwinEngine(
        initial_state=reference_rover_state(),
        mission_id="m",
        seed=13,
        environment_id="e",
        timestamp_s=0,
        provenance=p,
    )
    s = e.live_snapshot
    candidate = TwinSnapshot.create(
        timestamp_s=1,
        mission_id="m",
        seed=13,
        environment_id="e",
        state=s.state,
        provenance=replace(p, recorded_at_s=1),
    )
    return e, create_candidate("c", "recovery", s, candidate, 5)


def test_accepts_once_and_writes_immutable_history():
    e, c = setup()
    g = TwinAcceptanceGateway(e)
    r = g.accept(c, 1)
    assert r.decision == AcceptanceDecision.ACCEPTED and len(e.history.snapshots) == 2
    assert g.accept(c, 1).decision == AcceptanceDecision.REJECTED


def test_schema_fingerprint_expiry_and_conflict_reject():
    e, c = setup()
    g = TwinAcceptanceGateway(e)
    assert g.accept(replace(c, schema_version="v2"), 1).decision == AcceptanceDecision.INVALID
    assert g.accept(replace(c, fingerprint="bad"), 1).decision == AcceptanceDecision.INVALID
    expired = replace(c, candidate_id="expired", expires_s=1, fingerprint="")
    expired = replace(expired, fingerprint=_fp(expired))
    assert g.accept(expired, 1).decision == AcceptanceDecision.EXPIRED
    g.accept(c, 1)
    conflict = replace(c, candidate_id="conflict", fingerprint="")
    conflict = replace(conflict, fingerprint=_fp(conflict))
    assert g.accept(conflict, 1).decision == AcceptanceDecision.CONFLICT


def test_demo_deterministic():
    assert run_twin_acceptance_demo() == run_twin_acceptance_demo()
