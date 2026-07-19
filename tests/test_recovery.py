from dataclasses import replace

from mars_ai_os.recovery import (
    CandidateAcceptanceRequest,
    CandidateStatus,
    RecoveryCoordinator,
    RecoveryReview,
    RecoveryStatus,
)
from mars_ai_os.recovery.demo import run_recovery_demo


def review(expiry=10):
    return replace(RecoveryReview("r", "t", "h", "s", expiry), fingerprint="r")


def test_session_lifecycle_candidate_and_events():
    c = RecoveryCoordinator()
    s = c.create("s", "m", "i", "h", "a", review(), 0)
    assert s.status == RecoveryStatus.APPROVED
    s = c.execute(s, 1)
    assert s.status == RecoveryStatus.COMPLETED
    candidate = c.candidate(s, "snapshot")
    accepted = c.accept(
        candidate, CandidateAcceptanceRequest(candidate.candidate_id, CandidateStatus.ACCEPTED, 1)
    )
    assert accepted.status == CandidateStatus.ACCEPTED and len(c.events) == 6


def test_expiry_and_deterministic_demo():
    c = RecoveryCoordinator()
    s = c.create("s", "m", "i", "h", "a", review(0), 0)
    assert s.status == RecoveryStatus.EXPIRED
    assert run_recovery_demo() == run_recovery_demo()
