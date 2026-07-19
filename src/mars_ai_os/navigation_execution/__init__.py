"""Reviewed NavigationIntent-to-motion-request bridge; never an actuator authority."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from math import atan2, hypot

from mars_ai_os.digital_twin.provenance import canonical_json
from mars_ai_os.navigation import NavigationIntent, RiskLevel, Waypoint


def _fp(value: object) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class ExecutionState(StrEnum):
    CREATED = "created"
    WAITING_REVIEW = "waiting_review"
    APPROVED = "approved"
    READY = "ready"
    SEGMENT_READY = "segment_ready"
    SEGMENT_SUBMITTED = "segment_submitted"
    SEGMENT_ACCEPTED = "segment_accepted"
    SEGMENT_COMPLETED = "segment_completed"
    GOAL_REACHED = "goal_reached"
    COMPLETED = "completed"
    FAILED = "failed"
    SAFE_STOP = "safe_stop"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class NavigationExecutionReview:
    review_id: str
    reviewer: str
    intent_fingerprint: str
    expires_s: float
    max_speed_mps: float
    max_turn_rate_rad_s: float
    max_segments: int
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class MotionSegment:
    segment_id: str
    sequence: int
    start: Waypoint
    end: Waypoint
    distance_m: float
    heading_rad: float
    speed_limit_mps: float
    duration_s: float
    risk: RiskLevel
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class MissionMotionIntentRequest:
    request_id: str
    session_id: str
    segment_id: str
    linear_mps: float
    angular_rad_s: float
    expiry_s: float
    review_fingerprint: str
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class NavigationExecutionSession:
    session_id: str
    intent_id: str
    state: ExecutionState
    created_s: float
    expires_s: float
    fingerprint: str = ""


class NavigationExecutionBridge:
    def __init__(self):
        self.events: list[str] = []
        self.audit: list[str] = []

    def segment(self, intent: NavigationIntent):
        if intent.risk in {RiskLevel.UNKNOWN, RiskLevel.CRITICAL}:
            raise ValueError("navigation risk blocks execution")
        segments = []
        for i, (a, b) in enumerate(zip(intent.waypoints, intent.waypoints[1:], strict=False)):
            d = hypot(b.x_m - a.x_m, b.y_m - a.y_m)
            if d <= 0:
                raise ValueError("zero-distance segment")
            s = MotionSegment(
                f"{intent.intent_id}:{i}",
                i,
                a,
                b,
                d,
                atan2(b.y_m - a.y_m, b.x_m - a.x_m),
                intent.max_speed_mps,
                d / intent.max_speed_mps,
                intent.risk,
                "",
            )
            segments.append(replace(s, fingerprint=_fp(s)))
        return tuple(segments)

    def start(self, intent: NavigationIntent, review: NavigationExecutionReview, now: float):
        if review.expires_s <= now or review.intent_fingerprint != intent.fingerprint:
            raise ValueError("review invalid")
        session = NavigationExecutionSession(
            f"session:{intent.intent_id}",
            intent.intent_id,
            ExecutionState.APPROVED,
            now,
            review.expires_s,
            "",
        )
        session = replace(session, fingerprint=_fp(session))
        self.events.extend(
            (
                "NavigationExecutionRequested",
                "NavigationExecutionApproved",
                "NavigationExecutionStarted",
            )
        )
        self.audit.append(session.fingerprint)
        return session

    def request(self, session, segment, review, now):
        if now >= session.expires_s:
            raise ValueError("session expired")
        r = MissionMotionIntentRequest(
            f"request:{segment.segment_id}",
            session.session_id,
            segment.segment_id,
            min(segment.speed_limit_mps, review.max_speed_mps),
            0,
            now + min(segment.duration_s, 1),
            review.fingerprint,
            "",
        )
        r = replace(r, fingerprint=_fp(r))
        self.events.append("NavigationSegmentSubmitted")
        return r
