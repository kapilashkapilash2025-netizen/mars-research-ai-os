# ADR 0006: Reviewed degraded mobility

Degraded mobility defaults to deny. Any recovery review must bind to the exact deterministic health
fingerprint, and unknown mechanical state rejects movement. Event replay never re-executes commands;
safe stop requires telemetry evidence. A degraded operation expires and this is simulation-only.
