from mars_ai_os.runtime import BootRuntime, reference_manifest


def run_boot_demo():
    runtime = BootRuntime(reference_manifest())
    state = runtime.boot(tuple(s.name for s in reference_manifest()), 0)
    return {
        "state": state.value,
        "records": len(runtime.audit),
        "audit": [r.state.value for r in runtime.audit],
        "safety": "runtime contract only; no bootloader or hardware control",
    }
