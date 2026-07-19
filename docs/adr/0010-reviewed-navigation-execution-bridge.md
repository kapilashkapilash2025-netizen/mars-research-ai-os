# ADR 0010: Reviewed Navigation Execution Bridge

Navigation planning produces intent only. This bridge produces reviewed motion requests only, preserving SafetyMotionController as the unique HAL command authority.
