"""Safe, backend-neutral rover HAL foundation."""

from mars_ai_os.hal.models import CommandEnvelope, HalConfiguration, LifecycleState
from mars_ai_os.hal.runtime import ManualClock, MonotonicClock
from mars_ai_os.hal.simulation import InMemorySimulationBackend

__all__ = [
    "CommandEnvelope",
    "HalConfiguration",
    "InMemorySimulationBackend",
    "LifecycleState",
    "ManualClock",
    "MonotonicClock",
]
