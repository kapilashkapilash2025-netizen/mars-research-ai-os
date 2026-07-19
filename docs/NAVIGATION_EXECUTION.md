# Reviewed Navigation Execution Bridge

The bridge converts a reviewed immutable NavigationIntent into deterministic MotionSegments and
MissionMotionIntentRequest records. It is default-deny and requires matching unexpired review. It has no
HAL/motor/wheel-command API; SafetyMotionController remains the sole motion command authority.
