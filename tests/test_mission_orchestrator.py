from mars_ai_os.mission.contracts import content_hash, jsonable
from mars_ai_os.mission.orchestrator import MissionOrchestrator

REQUEST = {
    "mission_name": "Jezero verification traverse",
    "target": {"id": "delta", "name": "Delta Scarp", "distance_m": 420},
    "scenario_ids": ["nominal", "dust-storm", "wheel-degradation"],
}


def test_identical_inputs_have_stable_plan_and_predictions():
    first = MissionOrchestrator().create_plan(REQUEST)
    second = MissionOrchestrator().create_plan(REQUEST)
    assert first.plan_id == second.plan_id
    assert first.input_hash == second.input_hash
    assert [item.prediction_id for item in first.predictions] == [
        item.prediction_id for item in second.predictions
    ]
    assert content_hash(jsonable(first)) == content_hash(jsonable(second))


def test_three_routes_cross_three_scenarios_with_explainable_scores():
    plan = MissionOrchestrator().create_plan(REQUEST)
    assert len(plan.routes) == 3
    assert len(plan.predictions) == 9
    assert {item.scenario_id for item in plan.predictions} == {
        "nominal",
        "dust-storm",
        "wheel-degradation",
    }
    assert all(len(item.score_components) == 6 for item in plan.predictions)
    assert all(item.source_classification == "simulated" for item in plan.predictions)


def test_authorization_boundary_and_state_transitions():
    service = MissionOrchestrator()
    plan = service.create_plan(REQUEST)
    try:
        service.create_run({"plan_id": plan.plan_id, "selected_route_id": "safe"})
    except PermissionError:
        pass
    else:
        raise AssertionError("run must require explicit authorization")
    run = service.create_run(
        {
            "plan_id": plan.plan_id,
            "selected_route_id": "safe",
            "scenario_id": "wheel-degradation",
            "human_authorized": True,
            "authorized_by": "research-operator",
        }
    )
    assert run.current_snapshot.status == "authorized"
    service.command(run.run_id, "start")
    service.step(run.run_id)
    service.command(run.run_id, "pause")
    service.command(run.run_id, "resume")
    service.command(run.run_id, "safe_hold")
    service.command(run.run_id, "abort")
    assert service.replay(run.run_id) == service.repository.load_run(run.run_id).current_snapshot
    report = service.report(run.run_id)
    assert report["report_content_hash"]
    assert [event["sequence"] for event in report["events"]] == list(
        range(1, len(report["events"]) + 1)
    )


def test_snapshots_are_immutable_and_emergency_stop_is_safe():
    service = MissionOrchestrator()
    plan = service.create_plan(REQUEST)
    run = service.create_run(
        {
            "plan_id": plan.plan_id,
            "selected_route_id": "balanced",
            "human_authorized": True,
            "authorized_by": "reviewer",
        }
    )
    initial = run.current_snapshot
    service.command(run.run_id, "start")
    service.command(run.run_id, "emergency_stop")
    assert initial.status == "authorized"
    assert run.current_snapshot.status == "aborted"
    assert run.events[-1].safety_decision.human_authorized is True
