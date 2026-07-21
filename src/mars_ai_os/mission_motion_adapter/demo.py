from dataclasses import replace

from mars_ai_os.mission_motion_adapter import AdaptationContext, MissionMotionControllerAdapter
from mars_ai_os.navigation_execution import MissionMotionIntentRequest


def run_mission_motion_adapter_demo():
    r = MissionMotionIntentRequest("r", "s", "seg", 0.2, 0, 2, "review", "")
    r = replace(r, fingerprint="request")
    c = AdaptationContext(0, True, True, True, True, "t", "health", "auth", "review", "cfg")
    a = MissionMotionControllerAdapter()
    d = a.adapt(r, c)
    return {
        "state": d.state.value,
        "controller_intent": d.controller_intent.intent_id if d.controller_intent else None,
        "events": a.events,
        "safety": "adapter only; no HAL commands",
    }
