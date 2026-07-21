from mars_ai_os.runtime import BootRuntime, BootState, reference_manifest
from mars_ai_os.runtime.demo import run_boot_demo


def test_ready_and_safe_mode_boot_are_deterministic():
    r = BootRuntime(reference_manifest())
    assert r.boot(tuple(s.name for s in reference_manifest()), 0) == BootState.READY
    assert BootRuntime(reference_manifest()).boot(("audit-service",), 0) == BootState.SAFE_MODE
    assert run_boot_demo() == run_boot_demo()
