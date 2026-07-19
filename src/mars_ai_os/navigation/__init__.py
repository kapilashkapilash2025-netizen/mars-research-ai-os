"""Intent-only deterministic navigation planning; no actuator authority."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from math import hypot

from mars_ai_os.digital_twin.provenance import canonical_json


def _fp(value: object) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Waypoint:
    name: str
    x_m: float
    y_m: float


@dataclass(frozen=True, slots=True)
class WorldModel:
    version: str
    waypoints: tuple[Waypoint, ...]
    restricted: tuple[str, ...] = ()
    hazards: tuple[str, ...] = ()
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class NavigationIntent:
    intent_id: str
    mission_id: str
    goal: str
    priority: int
    waypoints: tuple[Waypoint, ...]
    max_speed_mps: float
    max_turn_rate_rad_s: float
    risk: RiskLevel
    estimated_distance_m: float
    estimated_duration_s: float
    constraints: tuple[str, ...]
    planner_version: str
    timestamp_s: float
    confidence: float
    warnings: tuple[str, ...]
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class NavigationEvent:
    event_type: str
    goal: str
    fingerprint: str = ""


class NavigationPlanner:
    def __init__(self, world: WorldModel):
        self.world = world
        self.events: list[NavigationEvent] = []

    def plan(self, mission_id, start: Waypoint, goal, timestamp_s):
        self.events.append(
            NavigationEvent("NavigationRequested", goal, _fp((mission_id, goal, timestamp_s)))
        )
        targets = {w.name: w for w in self.world.waypoints}
        if self.world.confidence <= 0 or goal not in targets:
            self.events.append(NavigationEvent("GoalUnreachable", goal, _fp(goal)))
            return None
        if goal in self.world.restricted or goal in self.world.hazards:
            self.events.append(NavigationEvent("NavigationRejected", goal, _fp(goal)))
            return None
        target = targets[goal]
        distance = hypot(target.x_m - start.x_m, target.y_m - start.y_m)
        if self.world.confidence < 0.4:
            self.events.append(NavigationEvent("NavigationRejected", goal, _fp(goal)))
            return None
        intent = NavigationIntent(
            f"nav:{mission_id}:{goal}",
            mission_id,
            goal,
            1,
            (start, target),
            0.4,
            0.3,
            RiskLevel.LOW,
            distance,
            distance / 0.4,
            (),
            "route-planner/1",
            timestamp_s,
            self.world.confidence,
            (),
            "",
        )
        intent = replace(intent, fingerprint=_fp(intent))
        self.events.extend(
            (
                NavigationEvent("NavigationPlanned", goal, _fp(intent)),
                NavigationEvent("NavigationIntentCreated", goal, intent.fingerprint),
            )
        )
        return intent
