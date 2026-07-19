from mars_ai_os.degraded import (
    DegradationClass,
    DegradedMobilityService,
    MechanicalState,
    StopConfirmation,
)
from mars_ai_os.degraded.demo import run_degraded_demo
from mars_ai_os.hal import HalConfiguration, InMemorySimulationBackend, ManualClock


def service():
    clock = ManualClock()
    backend = InMemorySimulationBackend(HalConfiguration(), clock)
    backend.initialize()
    return backend, DegradedMobilityService(backend)


def test_nominal_and_single_free_rolling_unavailable_are_deterministic():
    backend, assessed = service()
    assert assessed.assess().classification == DegradationClass.NOMINAL
    motor = backend.registry.get("drive.left.front_outer")
    motor.lifecycle = motor.lifecycle.FAULTED
    motor.mechanical_state = MechanicalState.FREE_ROLLING
    result = assessed.assess()
    assert result.classification == DegradationClass.SINGLE_MOTOR_UNAVAILABLE
    assert len(assessed.bus.replay()) == 3


def test_unknown_mechanical_and_stale_are_default_deny():
    backend, assessed = service()
    motor = backend.registry.get("drive.left.front_outer")
    motor.mechanical_state = MechanicalState.UNKNOWN
    assert assessed.assess().classification == DegradationClass.UNKNOWN_DRIVE_STATE
    motor.mechanical_state = MechanicalState.FREE_ROLLING
    motor.last_command_s = 0
    backend.clock.advance(3)
    assert assessed.assess().classification == DegradationClass.UNKNOWN_DRIVE_STATE


def test_safe_stop_requires_fresh_zero_telemetry_and_replay_is_read_only():
    _, assessed = service()
    result = assessed.assess()
    assert assessed.confirm_safe_stop(result) == StopConfirmation.CONFIRMED
    replay = assessed.bus.replay()
    assert replay == assessed.bus.replay()
    assert run_degraded_demo() == run_degraded_demo()
