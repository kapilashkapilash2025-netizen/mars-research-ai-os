# ADR 0011: Reviewed Mission Motion Adapter

The adapter has no actuator authority. SafetyMotionController is the sole HAL-command authority;
adaptation is default-deny, replay-protected, context-fresh and simulation-only.
