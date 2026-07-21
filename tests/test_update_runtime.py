from mars_ai_os.update_runtime import (
    SecureUpdateManager,
    Slot,
    UpdatePackage,
    UpdateState,
    build_manifest,
)
from mars_ai_os.update_runtime.demo import run_update_demo


def test_ab_update_confirm_and_rollback():
    m = build_manifest()
    p = UpdatePackage("p", m, m.digest)
    u = SecureUpdateManager()
    assert u.validate(p)
    u.stage(p)
    u.request_boot()
    u.confirm_boot(True)
    assert u.record.state == UpdateState.CONFIRMED and u.record.active_slot == Slot.B
    u = SecureUpdateManager()
    u.validate(p)
    u.stage(p)
    u.request_boot()
    u.confirm_boot(False)
    assert u.record.state == UpdateState.ROLLED_BACK and u.record.active_slot == Slot.A


def test_digest_rejection_and_demo():
    m = build_manifest()
    assert not SecureUpdateManager().validate(UpdatePackage("bad", m, "bad"))
    assert run_update_demo() == run_update_demo()
