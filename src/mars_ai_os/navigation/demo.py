from mars_ai_os.navigation import NavigationPlanner, Waypoint, WorldModel


def run_navigation_demo():
    p = NavigationPlanner(WorldModel("world/1", (Waypoint("start", 0, 0), Waypoint("goal", 4, 0))))
    i = p.plan("demo", Waypoint("start", 0, 0), "goal", 0)
    return {
        "intent": i.intent_id if i else None,
        "distance_m": i.estimated_distance_m if i else None,
        "events": [e.event_type for e in p.events],
        "safety": "navigation intent only; no motor commands",
    }
