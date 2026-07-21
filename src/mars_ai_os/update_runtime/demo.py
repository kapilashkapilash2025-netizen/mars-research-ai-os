from mars_ai_os.update_runtime import SecureUpdateManager, UpdatePackage, build_manifest


def run_update_demo():
    m = build_manifest()
    p = UpdatePackage("update-1", m, m.digest)
    u = SecureUpdateManager()
    valid = u.validate(p)
    u.stage(p)
    u.request_boot()
    u.confirm_boot(True)
    return {
        "valid": valid,
        "state": u.record.state.value,
        "active_slot": u.record.active_slot.value,
        "safety": "contract simulation only; no update flashed",
    }
