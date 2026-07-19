"""Default-deny MissionMotionIntentRequest adapter; never a HAL authority."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from mars_ai_os.digital_twin.provenance import canonical_json
from mars_ai_os.navigation_execution import MissionMotionIntentRequest


def _fp(value: object) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class AdapterState(StrEnum):
    CREATED = "created"
    VALIDATING = "validating"
    MAPPED = "mapped"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SAFE_STOP_REQUIRED = "safe_stop_required"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class AdaptationContext:
    now_s: float
    telemetry_fresh: bool
    watchdog_healthy: bool
    estop_clear: bool
    controller_available: bool
    twin_id: str
    health_fingerprint: str
    authorization_fingerprint: str
    review_fingerprint: str
    configuration_hash: str


@dataclass(frozen=True, slots=True)
class ControllerMotionIntent:
    intent_id: str
    mission_id: str
    linear_mps: float
    angular_rad_s: float
    expiry_s: float
    authorization_fingerprint: str
    review_fingerprint: str
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class AdaptationDecision:
    request_id: str
    state: AdapterState
    reason: str | None
    controller_intent: ControllerMotionIntent | None
    fingerprint: str = ""


class MissionMotionControllerAdapter:
    def __init__(self):
        self._consumed: set[str] = set()
        self.events: list[str] = []
        self.audit: list[str] = []

    def adapt(
        self, request: MissionMotionIntentRequest, context: AdaptationContext
    ) -> AdaptationDecision:
        def deny(state, reason):
            d = AdaptationDecision(request.request_id, state, reason, None)
            d = replace(d, fingerprint=_fp(d))
            self.events.append("MissionMotionPolicyRejected")
            self.audit.append(d.fingerprint)
            return d

        self.events.extend(("MissionMotionAdaptationRequested", "MissionMotionContextLoaded"))
        if request.request_id in self._consumed:
            return deny(AdapterState.REJECTED, "duplicate request")
        if context.now_s >= request.expiry_s:
            return deny(AdapterState.EXPIRED, "request expired")
        if not all(
            (
                context.telemetry_fresh,
                context.watchdog_healthy,
                context.estop_clear,
                context.controller_available,
            )
        ):
            return deny(AdapterState.SAFE_STOP_REQUIRED, "critical context unavailable")
        if request.review_fingerprint != context.review_fingerprint:
            return deny(AdapterState.REJECTED, "review binding mismatch")
        if request.expiry_s <= context.now_s or request.linear_mps == 0:
            return deny(AdapterState.REJECTED, "non-useful motion")
        intent = ControllerMotionIntent(
            f"controller:{request.request_id}",
            "mission",
            request.linear_mps,
            request.angular_rad_s,
            request.expiry_s,
            context.authorization_fingerprint,
            context.review_fingerprint,
            "",
        )
        intent = replace(intent, fingerprint=_fp(intent))
        self._consumed.add(request.request_id)
        d = AdaptationDecision(request.request_id, AdapterState.MAPPED, None, intent)
        d = replace(d, fingerprint=_fp(d))
        self.events.extend(
            (
                "MissionMotionReviewValidated",
                "MissionMotionPolicyApproved",
                "MissionMotionLimitsComposed",
                "ControllerMotionIntentCreated",
            )
        )
        self.audit.append(d.fingerprint)
        return d
