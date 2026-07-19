from dataclasses import replace

from mars_ai_os.mission_motion_adapter import (
    AdaptationContext,
    AdapterState,
    MissionMotionControllerAdapter,
)
from mars_ai_os.mission_motion_adapter.demo import run_mission_motion_adapter_demo
from mars_ai_os.navigation_execution import MissionMotionIntentRequest


def request():
    return replace(
        MissionMotionIntentRequest("r", "s", "x", 0.2, 0, 2, "review", ""), fingerprint="r"
    )


def context():
    return AdaptationContext(0, True, True, True, True, "t", "h", "a", "review", "c")


def test_default_deny_duplicate_and_mapping():
    a = MissionMotionControllerAdapter()
    assert a.adapt(request(), context()).state == AdapterState.MAPPED
    assert a.adapt(request(), context()).state == AdapterState.REJECTED


def test_stale_context_and_demo():
    assert (
        MissionMotionControllerAdapter()
        .adapt(request(), replace(context(), telemetry_fresh=False))
        .state
        == AdapterState.SAFE_STOP_REQUIRED
    )
    assert run_mission_motion_adapter_demo() == run_mission_motion_adapter_demo()
