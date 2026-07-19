from mars_ai_os.recovery import (
    CandidateAcceptanceRequest,
    CandidateStatus,
    RecoveryCoordinator,
    RecoveryReview,
)


def run_recovery_demo():
    c = RecoveryCoordinator()
    r = RecoveryReview("r", "test", "health", "snapshot", 10)
    r = __import__("dataclasses").replace(r, fingerprint="review-test")
    s = c.create("s", "m", "i", "health", "auth", r, 0)
    s = c.execute(s, 1)
    candidate = c.candidate(s, "snapshot")
    candidate = c.accept(
        candidate, CandidateAcceptanceRequest(candidate.candidate_id, CandidateStatus.ACCEPTED, 1)
    )
    return {
        "session": s.status.value,
        "candidate": candidate.status.value,
        "events": [e.event_type for e in c.events],
        "audit": len(c.audit),
        "safety": "orchestration only; no hardware commands",
    }
