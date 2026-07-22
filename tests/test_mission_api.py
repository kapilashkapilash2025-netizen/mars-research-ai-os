from mars_ai_os.mission.api import MissionApi
from mars_ai_os.mission.orchestrator import MissionOrchestrator


def test_api_validation_and_happy_path():
    api = MissionApi(MissionOrchestrator())
    status, health = api.dispatch("GET", "/api/v1/mission/health")
    assert status == 200 and health["status"] == "ready"
    status, plan = api.dispatch(
        "POST", "/api/v1/mission/plans", {"target": {"id": "delta", "distance_m": 420}}
    )
    assert status == 201
    status, denied = api.dispatch(
        "POST", "/api/v1/mission/runs", {"plan_id": plan["plan_id"], "selected_route_id": "safe"}
    )
    assert status == 403 and denied["error"]["code"] == "authorization_required"
    status, run = api.dispatch(
        "POST",
        "/api/v1/mission/runs",
        {
            "plan_id": plan["plan_id"],
            "selected_route_id": "safe",
            "human_authorized": True,
            "authorized_by": "operator",
        },
    )
    assert status == 201
    status, _ = api.dispatch(
        "POST", f"/api/v1/mission/runs/{run['run_id']}/commands", {"command": "start"}
    )
    assert status == 200
    status, _ = api.dispatch("POST", f"/api/v1/mission/runs/{run['run_id']}/step")
    assert status == 200
    status, report = api.dispatch("GET", f"/api/v1/mission/runs/{run['run_id']}/report")
    assert status == 200 and report["report_content_hash"]


def test_api_returns_structured_errors():
    api = MissionApi(MissionOrchestrator())
    status, body = api.dispatch(
        "POST", "/api/v1/mission/plans", {"target": {"id": "", "distance_m": -1}}
    )
    assert status == 422 and body["error"]["code"] == "validation_error"
    status, body = api.dispatch("GET", "/api/v1/mission/runs/missing")
    assert status == 404 and body["error"]["code"] == "mission_not_found"
