from mars_ai_os.navigation import NavigationPlanner, Waypoint, WorldModel
from mars_ai_os.navigation.demo import run_navigation_demo


def test_plan_and_intent_only():
    p = NavigationPlanner(WorldModel("v1", (Waypoint("start", 0, 0), Waypoint("goal", 3, 4))))
    i = p.plan("m", Waypoint("start", 0, 0), "goal", 0)
    assert i and i.estimated_distance_m == 5 and "motor" not in str(i).lower()


def test_blocked_unknown_and_demo():
    assert (
        NavigationPlanner(WorldModel("v1", (Waypoint("goal", 1, 1),), restricted=("goal",))).plan(
            "m", Waypoint("s", 0, 0), "goal", 0
        )
        is None
    )
    assert (
        NavigationPlanner(WorldModel("v1", (), confidence=0)).plan("m", Waypoint("s", 0, 0), "x", 0)
        is None
    )
    assert run_navigation_demo() == run_navigation_demo()
