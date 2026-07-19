# ADR 0004: Safe backend-neutral Rover HAL

High-level services cannot access drivers directly: capability-specific contracts preserve validation,
expiry, telemetry, lifecycle, watchdog, and e-stop boundaries. Time is injected so simulation is
deterministic. E-stop is rover-level and latched; clearing never resumes motion. Simulated and physical
backends must share public contracts, while the first backend is in-memory for reproducible testing.
This decision is explicitly not a hardware-readiness claim.
