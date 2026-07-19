# Reviewed degraded mobility and Control-to-Twin events

Degraded mobility is disabled by default. The deterministic service assesses every canonical motor;
missing or stale telemetry is never healthy. Unknown, braked, locked, same-side severe, or multiple
failure states reject mobility. The initial policy permits only explicitly configured, reviewed,
one-free-rolling-motor recovery through the existing SafetyMotionController; it never creates a second
command authority path.

Health events are immutable and append-only. Replay is read-only and never executes HAL commands.
Safe-stop confirmation requires fresh telemetry and zero RPM evidence; otherwise it is partial or
unconfirmed. Twin integration remains candidate-only in later adapter work. This package is a
simulation-only engineering foundation, not a physical deployment or calibration claim.
