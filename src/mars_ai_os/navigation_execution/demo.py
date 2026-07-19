from dataclasses import replace

from mars_ai_os.navigation import NavigationPlanner, Waypoint, WorldModel
from mars_ai_os.navigation_execution import NavigationExecutionBridge, NavigationExecutionReview


def run_navigation_execution_demo():
    i = NavigationPlanner(WorldModel("v", (Waypoint("start", 0, 0), Waypoint("goal", 2, 0)))).plan(
        "m", Waypoint("start", 0, 0), "goal", 0
    )
    b = NavigationExecutionBridge()
    r = NavigationExecutionReview("r", "test", i.fingerprint, 5, 0.2, 0.1, 1)
    r = replace(r, fingerprint="review")
    s = b.start(i, r, 0)
    segment = b.segment(i)[0]
    request = b.request(s, segment, r, 0)
    return {
        "session": s.state.value,
        "segment": segment.segment_id,
        "request": request.request_id,
        "events": b.events,
        "safety": "motion requests only; no HAL commands",
    }
