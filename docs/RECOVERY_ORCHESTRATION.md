# Reviewed Recovery Orchestration

Recovery sessions are immutable, default-deny, reviewed records between controller decisions and Twin
candidates. The coordinator never creates HAL commands; SafetyMotionController remains the sole motor
authority. Session lifecycle is `NEW → WAITING_REVIEW → APPROVED → EXECUTING → COMPLETED`, with safe,
rejected, expired, invalidated, failed and cancelled terminal paths. Invalid/expired sessions cannot resume.

Candidates are immutable and pending until a separate explicit acceptance request marks them accepted,
rejected, superseded, expired or cancelled. No canonical Twin state is mutated. Events and audit records
are append-only, deterministic, and replay is informational only. `mars-ai-os recovery-demo` is a
headless smoke path. This is simulation-only, not physical rover deployment.
