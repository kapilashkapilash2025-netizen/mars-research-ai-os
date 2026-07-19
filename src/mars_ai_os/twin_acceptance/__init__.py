"""Deterministic, policy-gated candidate acceptance into canonical Twin history."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from mars_ai_os.digital_twin import DigitalTwinEngine
from mars_ai_os.digital_twin.models import TwinSnapshot
from mars_ai_os.digital_twin.provenance import canonical_json


def _fp(value: object) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class AcceptanceDecision(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    CONFLICT = "conflict"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class TwinCandidate:
    candidate_id: str
    schema_version: str
    source_component: str
    source_snapshot_id: str
    snapshot: TwinSnapshot
    created_s: float
    expires_s: float
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class GatewayEvent:
    event_type: str
    candidate_id: str
    timestamp_s: float
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    candidate_id: str
    decision: AcceptanceDecision
    reason: str | None
    snapshot_id: str | None
    fingerprint: str = ""


class TwinSchemaRegistry:
    supported = ("v1",)

    def validate(self, version: str) -> bool:
        return version in self.supported


class TwinAcceptanceGateway:
    def __init__(self, engine: DigitalTwinEngine, schema: TwinSchemaRegistry | None = None):
        self.engine, self.schema = engine, schema or TwinSchemaRegistry()
        self._seen: set[str] = set()
        self.events: list[GatewayEvent] = []

    def accept(self, candidate: TwinCandidate, now_s: float) -> AcceptanceResult:
        def result(decision, reason=None, snapshot_id=None):
            r = AcceptanceResult(candidate.candidate_id, decision, reason, snapshot_id)
            r = replace(r, fingerprint=_fp(r))
            self._event(
                "TwinCandidateAccepted"
                if decision == AcceptanceDecision.ACCEPTED
                else "TwinCandidateRejected"
                if decision != AcceptanceDecision.CONFLICT
                else "TwinConflictDetected",
                candidate,
                now_s,
            )
            return r

        if not self.schema.validate(candidate.schema_version):
            self._event("TwinSchemaRejected", candidate, now_s)
            return result(AcceptanceDecision.INVALID, "unsupported schema")
        if not candidate.fingerprint or candidate.fingerprint != _fp(
            replace(candidate, fingerprint="")
        ):
            return result(AcceptanceDecision.INVALID, "candidate fingerprint mismatch")
        if candidate.candidate_id in self._seen:
            return result(AcceptanceDecision.REJECTED, "duplicate candidate")
        if now_s >= candidate.expires_s:
            return result(AcceptanceDecision.EXPIRED, "candidate expired")
        if candidate.source_snapshot_id != self.engine.live_snapshot.snapshot_id:
            return result(AcceptanceDecision.CONFLICT, "source snapshot conflict")
        if candidate.snapshot.timestamp_s < self.engine.live_snapshot.timestamp_s:
            return result(AcceptanceDecision.SUPERSEDED, "out-of-order timestamp")
        self._seen.add(candidate.candidate_id)
        accepted, _ = self.engine.update_state(
            candidate.snapshot.state,
            timestamp_s=candidate.snapshot.timestamp_s,
            source="twin-acceptance-gateway",
            reason=f"accepted candidate {candidate.candidate_id}",
            provenance=candidate.snapshot.provenance,
        )
        self._event("TwinSnapshotWritten", candidate, now_s)
        self._event("TwinHistoryWritten", candidate, now_s)
        return result(AcceptanceDecision.ACCEPTED, snapshot_id=accepted.snapshot_id)

    def _event(self, kind, candidate, now):
        e = GatewayEvent(kind, candidate.candidate_id, now)
        self.events.append(replace(e, fingerprint=_fp(e)))


def create_candidate(
    candidate_id: str,
    source_component: str,
    source: TwinSnapshot,
    snapshot: TwinSnapshot,
    expires_s: float,
) -> TwinCandidate:
    c = TwinCandidate(
        candidate_id,
        "v1",
        source_component,
        source.snapshot_id,
        snapshot,
        source.timestamp_s,
        expires_s,
    )
    return replace(c, fingerprint=_fp(c))
