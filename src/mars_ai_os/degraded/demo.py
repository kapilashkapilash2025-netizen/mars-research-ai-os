from mars_ai_os.degraded import DegradedMobilityService, MechanicalState
from mars_ai_os.hal import HalConfiguration, InMemorySimulationBackend, ManualClock


def run_degraded_demo() -> dict[str, object]:
    clock = ManualClock()
    backend = InMemorySimulationBackend(HalConfiguration(), clock)
    backend.initialize()
    service = DegradedMobilityService(backend)
    nominal = service.assess()
    motor = backend.registry.get("drive.left.front_outer")
    motor.lifecycle = motor.lifecycle.FAULTED
    motor.mechanical_state = MechanicalState.FREE_ROLLING
    degraded = service.assess()
    return {
        "nominal": nominal.classification.value,
        "degraded": degraded.classification.value,
        "events": [event.event_type for event in service.bus.replay()],
        "safe_stop": service.confirm_safe_stop(degraded).value,
        "safety": "default-deny reviewed simulation only",
    }
