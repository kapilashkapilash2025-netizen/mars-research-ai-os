# Reviewed Mission Motion Request to Safety Controller Adapter

This default-deny adapter validates fresh reviewed context and maps immutable MissionMotionIntentRequest
to controller-compatible intent. It never creates wheel/motor/HAL commands or mutates Twin state.
