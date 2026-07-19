from __future__ import annotations

from mars_ai_os.control import (
    MotionAuthorization,
    MotionIntent,
    OperatingMode,
    SafetyMotionController,
)
from mars_ai_os.control.demo import run_control_demo
from mars_ai_os.control.models import SourceType
from mars_ai_os.digital_twin import DigitalTwinEngine, create_provenance, reference_rover_state
from mars_ai_os.hal import HalConfiguration, InMemorySimulationBackend, ManualClock
from mars_ai_os.mars_physics import PhysicsEngine, VehicleParameters, reference_scenarios


def setup():
    clock = ManualClock()
    hal = InMemorySimulationBackend(HalConfiguration(), clock)
    hal.initialize()
    prov = create_provenance(
        configuration={"t": 1}, seed=13, assumptions=(), author="test", recorded_at_s=0
    )
    twin = DigitalTwinEngine(
        initial_state=reference_rover_state(),
        mission_id="m",
        seed=13,
        environment_id="e",
        timestamp_s=0,
        provenance=prov,
    )
    auth = MotionAuthorization(
        "a",
        "test",
        "test",
        (OperatingMode.TEST, OperatingMode.MANUAL_REVIEWED),
        1,
        1,
        2,
        0,
        10,
        "m",
    )
    controller = SafetyMotionController(hal)
    controller.enter_mode(OperatingMode.TEST, auth, 0)
    return clock, hal, twin, auth, controller


def intent(auth, ident="i", linear=0.5, angular=0, expiry=2):
    return MotionIntent(
        ident,
        "m",
        "test",
        SourceType.TEST_HARNESS,
        linear,
        angular,
        0,
        expiry,
        1,
        auth,
        OperatingMode.TEST,
        duration_s=1,
    )


def test_all_eight_commands_and_skid_steer_allocation():
    _, _, twin, auth, c = setup()
    r = c.process(intent(auth, angular=0.4), twin.live_snapshot)
    assert r.accepted and len(r.wheel_rpm) == 8 and r.wheel_rpm[0][1] != r.wheel_rpm[-1][1]


def test_startup_safe_expiry_duplicate_authorization_and_estop():
    clock, hal, twin, auth, c = setup()
    assert not SafetyMotionController(hal).process(intent(auth), twin.live_snapshot).accepted
    clock.advance(3)
    assert not c.process(intent(auth, "expired", expiry=1), twin.live_snapshot).accepted
    clock._now = 0
    assert (
        c.process(intent(auth, "once"), twin.live_snapshot).accepted
        and not c.process(intent(auth, "once"), twin.live_snapshot).accepted
    )
    hal.estop.activate(0)
    assert not c.process(intent(auth, "estop"), twin.live_snapshot).accepted


def test_limit_acceleration_battery_thermal_physics_and_safe_stop():
    _, hal, twin, auth, c = setup()
    limited = c.process(intent(auth, linear=99), twin.live_snapshot)
    assert limited.accepted and limited.approved_linear_mps <= 0.4
    low = replace_power(twin, 5)
    assert not c.process(intent(auth, "battery"), low.live_snapshot).accepted
    hal.registry.drive_motors()[0].temperature_c = 90
    assert not c.process(intent(auth, "hot"), twin.live_snapshot).accepted
    stop = c.safe_stop(twin.live_snapshot)
    assert stop.accepted and all(m.rpm == 0 for m in hal.registry.drive_motors())


def replace_power(twin, soc):
    from dataclasses import replace

    state = replace(
        twin.live_snapshot.state,
        power=replace(twin.live_snapshot.state.power, battery_soc_percent=soc),
    )
    twin.update_state(state, timestamp_s=0, source="test", reason="battery")
    return twin


def test_physics_derating_and_deterministic_demo():
    _, _, twin, auth, c = setup()
    scenario = reference_scenarios()[1]
    physics = PhysicsEngine().step(
        scenario.state,
        scenario.intent,
        scenario.environment,
        scenario.terrain,
        VehicleParameters(),
        timestep_s=1,
        seed=13,
    )
    r = c.process(intent(auth), twin.live_snapshot, physics)
    assert r.accepted and dict(r.derating)["terrain"] <= 1
    assert run_control_demo() == run_control_demo()
