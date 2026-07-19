from __future__ import annotations

import pytest

from mars_ai_os.digital_twin import DigitalTwinEngine, create_provenance, reference_rover_state
from mars_ai_os.hal.adapters import twin_candidate
from mars_ai_os.hal.demo import run_hal_demo
from mars_ai_os.hal.models import (
    DRIVE_MOTOR_IDS,
    CommandEnvelope,
    CommandStatus,
    HalConfiguration,
    LifecycleState,
)
from mars_ai_os.hal.runtime import ManualClock
from mars_ai_os.hal.simulation import InMemorySimulationBackend
from mars_ai_os.mars_physics import PhysicsEngine, VehicleParameters, reference_scenarios


def backend() -> tuple[ManualClock, InMemorySimulationBackend]:
    clock = ManualClock()
    result = InMemorySimulationBackend(HalConfiguration(), clock)
    result.initialize()
    return clock, result


def command(
    command_id: str = "c",
    target: str = DRIVE_MOTOR_IDS[0],
    payload: float = 20,
    expiry: float = 1,
    kind: str = "set_rpm",
    unit: str = "rpm",
) -> CommandEnvelope:
    return CommandEnvelope(command_id, target, kind, 0, expiry, 1, "test", payload, unit)


def test_eight_stable_motor_identities_and_registry() -> None:
    _, hal = backend()
    assert tuple(m.identity.device_id for m in hal.registry.drive_motors()) == DRIVE_MOTOR_IDS


def test_lifecycle_rejects_invalid_transition() -> None:
    _, hal = backend()
    with pytest.raises(ValueError):
        hal.registry.drive_motors()[0].transition(LifecycleState.CREATED)


def test_limits_expiry_duplicate_unknown_and_watchdog() -> None:
    clock, hal = backend()
    assert hal.command(command(payload=999)).status == CommandStatus.LIMITED
    assert hal.command(command("c", payload=1)).status == CommandStatus.DUPLICATE
    assert hal.command(command("expired", expiry=0.1)).status == CommandStatus.APPLIED
    clock.advance(3)
    assert len(hal.tick()) == 1
    assert hal.registry.drive_motors()[0].rpm == 0
    assert hal.command(command("unknown", "missing")).status == CommandStatus.REJECTED


def test_hard_torque_and_bad_unit_blocked() -> None:
    _, hal = backend()
    assert (
        hal.command(command(kind="set_torque", unit="N*m", payload=99)).status
        == CommandStatus.REJECTED
    )
    assert hal.command(command("unit", unit="m/s")).status == CommandStatus.REJECTED


def test_global_estop_latches_all_and_clear_does_not_resume() -> None:
    clock, hal = backend()
    for index, motor in enumerate(DRIVE_MOTOR_IDS):
        assert hal.command(command(str(index), motor)).status == CommandStatus.APPLIED
    hal.estop.activate(clock.now())
    assert hal.estop.latched and all(m.rpm == 0 for m in hal.registry.drive_motors())
    assert hal.command(command("blocked")).status == CommandStatus.ESTOP_BLOCKED
    assert hal.estop.clear(clock.now(), True) and not hal.estop.latched
    assert all(
        m.rpm == 0 and m.lifecycle == LifecycleState.STOPPED for m in hal.registry.drive_motors()
    )


def test_temperature_voltage_and_telemetry_freshness() -> None:
    clock, hal = backend()
    motor = hal.registry.get(DRIVE_MOTOR_IDS[0])
    motor.temperature_c = 86
    assert hal.command(command()).status == CommandStatus.FAULT_BLOCKED
    telemetry = hal.telemetry()[0]
    assert telemetry.fresh(clock.now(), 1)
    clock.advance(3)
    assert not telemetry.fresh(clock.now(), 1)


def test_twin_candidate_does_not_mutate_live_history() -> None:
    _, hal = backend()
    provenance = create_provenance(
        configuration={"x": 1}, seed=13, assumptions=(), author="test", recorded_at_s=0
    )
    twin = DigitalTwinEngine(
        initial_state=reference_rover_state(),
        mission_id="m",
        seed=13,
        environment_id="e",
        timestamp_s=0,
        provenance=provenance,
    )
    source = twin.live_snapshot
    candidate = twin_candidate(source, hal)
    assert twin.live_snapshot.snapshot_id == source.snapshot_id and len(twin.history.snapshots) == 1
    assert (
        candidate.snapshot_id != source.snapshot_id
        and candidate.state.sensors.readings[-1].name == "lidar_nearest_range"
    )


def test_configuration_invalid_and_demo_deterministic() -> None:
    with pytest.raises(ValueError, match="Unsupported backend"):
        HalConfiguration(backend="gazebo")
    assert run_hal_demo() == run_hal_demo()


def test_physics_assisted_telemetry_is_information_only() -> None:
    from mars_ai_os.hal.adapters import physics_assisted_measurements

    scenario = reference_scenarios()[0]
    result = PhysicsEngine().step(
        scenario.state,
        scenario.intent,
        scenario.environment,
        scenario.terrain,
        VehicleParameters(),
        timestep_s=1,
        seed=13,
    )
    assert tuple(item.name for item in physics_assisted_measurements(result)) == (
        "physics_battery_energy",
        "physics_motor_temperature",
        "physics_slip_ratio",
        "physics_wheel_speed",
    )
