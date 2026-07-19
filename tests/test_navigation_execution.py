from dataclasses import replace

import pytest

from mars_ai_os.navigation import NavigationPlanner, Waypoint, WorldModel
from mars_ai_os.navigation_execution import NavigationExecutionBridge, NavigationExecutionReview
from mars_ai_os.navigation_execution.demo import run_navigation_execution_demo


def intent():
    return NavigationPlanner(WorldModel("v", (Waypoint("a", 0, 0), Waypoint("b", 3, 4)))).plan(
        "m", Waypoint("a", 0, 0), "b", 0
    )


def review(i):
    return replace(
        NavigationExecutionReview("r", "t", i.fingerprint, 5, 0.2, 0.1, 1), fingerprint="r"
    )


def test_segmentation_request_and_review():
    i = intent()
    b = NavigationExecutionBridge()
    s = b.start(i, review(i), 0)
    seg = b.segment(i)[0]
    assert seg.distance_m == 5 and b.request(s, seg, review(i), 0).linear_mps == 0.2


def test_invalid_review_and_demo():
    i = intent()
    b = NavigationExecutionBridge()
    with pytest.raises(ValueError):
        b.start(i, replace(review(i), expires_s=0), 0)
    assert run_navigation_execution_demo() == run_navigation_execution_demo()
