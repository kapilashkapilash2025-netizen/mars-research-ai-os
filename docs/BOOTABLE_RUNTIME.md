# Bootable AI OS Runtime Foundation

This PR defines deterministic boot orchestration, critical-service self-test, safe mode, append-only boot
audit and systemd deployment templates. It does not build a kernel, bootloader, boot image or real driver.

Boot order is `BOOTING → SELF_TEST → READY` only when audit, Twin, safety and HAL services are present.
Otherwise it enters `SAFE_MODE`, where motion authority must remain unavailable.
