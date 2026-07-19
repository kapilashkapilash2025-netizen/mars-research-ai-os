"""Deterministic reviewed recovery orchestration; never a motor-command authority."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from mars_ai_os.digital_twin.provenance import canonical_json


def _fp(value: object) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class RecoveryStatus(StrEnum):
    NEW = "new"
    WAITING_REVIEW = "waiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    SAFE_STOP = "safe_stop"
    FAILED = "failed"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    CANCELLED = "cancelled"


class CandidateStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class RecoveryReview:
    review_id: str
    reviewer: str
    health_fingerprint: str
    snapshot_id: str
    expires_s: float
    maximum_executions: int = 1
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class RecoverySession:
    session_id: str
    mission_id: str
    intent_id: str
    health_fingerprint: str
    authorization_fingerprint: str
    review_fingerprint: str
    created_s: float
    expires_s: float
    status: RecoveryStatus
    warnings: tuple[str, ...] = ()
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class RecoveryEvent:
    event_id: str
    event_type: str
    timestamp_s: float
    session_id: str
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class TwinCandidate:
    candidate_id: str
    source_snapshot_id: str
    session_id: str
    status: CandidateStatus
    decision_fingerprint: str
    warnings: tuple[str, ...]
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class CandidateAcceptanceRequest:
    candidate_id: str
    decision: CandidateStatus
    timestamp_s: float
    reason: str = ""


class RecoveryCoordinator:
    def __init__(self):
        self.events: list[RecoveryEvent] = []
        self.audit: list[str] = []

    def create(
        self, session_id, mission_id, intent_id, health, authorization, review: RecoveryReview, now
    ):
        status = RecoveryStatus.APPROVED if review.expires_s > now else RecoveryStatus.EXPIRED
        s = RecoverySession(
            session_id,
            mission_id,
            intent_id,
            health,
            authorization,
            review.fingerprint,
            now,
            review.expires_s,
            status,
        )
        s = replace(s, fingerprint=_fp(s))
        self._event("RecoverySessionCreated", s, now)
        self._event(
            "RecoveryReviewValidated" if status == RecoveryStatus.APPROVED else "RecoveryExpired",
            s,
            now,
        )
        self.audit.append(s.fingerprint)
        return s

    def execute(self, session: RecoverySession, now):
        if session.status != RecoveryStatus.APPROVED or now >= session.expires_s:
            return replace(
                session,
                status=RecoveryStatus.EXPIRED
                if now >= session.expires_s
                else RecoveryStatus.REJECTED,
            )
        r = replace(session, status=RecoveryStatus.COMPLETED)
        self._event("RecoveryExecutionStarted", session, now)
        self._event("RecoveryExecutionCompleted", r, now)
        self.audit.append(r.fingerprint)
        return r

    def candidate(self, session: RecoverySession, snapshot_id):
        c = TwinCandidate(
            f"candidate:{session.session_id}",
            snapshot_id,
            session.session_id,
            CandidateStatus.PENDING,
            session.fingerprint,
            session.warnings,
        )
        c = replace(c, fingerprint=_fp(c))
        self._event("TwinCandidateCreated", session, session.created_s)
        return c

    def accept(self, candidate: TwinCandidate, request: CandidateAcceptanceRequest):
        if candidate.status != CandidateStatus.PENDING:
            return candidate
        c = replace(candidate, status=request.decision)
        self.events.append(
            RecoveryEvent(
                f"candidate:{len(self.events)}",
                "TwinCandidateAccepted"
                if request.decision == CandidateStatus.ACCEPTED
                else "TwinCandidateRejected",
                request.timestamp_s,
                candidate.session_id,
                "",
            )
        )
        return replace(c, fingerprint=_fp(c))

    def _event(self, kind, session, now):
        e = RecoveryEvent(f"{kind}:{len(self.events)}", kind, now, session.session_id, "")
        self.events.append(replace(e, fingerprint=_fp(e)))
