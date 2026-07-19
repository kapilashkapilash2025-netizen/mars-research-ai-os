"""Candidate-only HAL to canonical Digital Twin mapping."""

from __future__ import annotations

from dataclasses import replace

from mars_ai_os.digital_twin.models import NamedValue, TwinSnapshot
from mars_ai_os.hal.simulation import InMemorySimulationBackend
from mars_ai_os.mars_physics.models import PhysicsResult


def twin_candidate(source: TwinSnapshot, backend: InMemorySimulationBackend) -> TwinSnapshot:
    simulated = backend.registry.drive_motors()
    motors = tuple(
        replace(m, rpm=simulated[index].rpm, temperature_c=simulated[index].temperature_c)
        for index, m in enumerate(source.state.hardware.motors)
    )
    warnings = tuple(
        sorted(
            set(source.state.faults.warnings)
            | ({"emergency stop latched"} if backend.estop.latched else set())
        )
    )
    readings = tuple(item for item in source.state.sensors.readings if item.name != "hal_estop")
    state = replace(
        source.state,
        hardware=replace(source.state.hardware, motors=motors),
        sensors=replace(
            source.state.sensors,
            readings=tuple(
                sorted(
                    (*readings, NamedValue("hal_estop", backend.estop.latched, "bool")),
                    key=lambda x: x.name,
                )
            ),
        ),
        faults=replace(source.state.faults, warnings=warnings),
    )
    metadata = tuple(item for item in source.metadata if item.name != "hal_candidate")
    return TwinSnapshot.create(
        timestamp_s=source.timestamp_s,
        mission_id=source.mission_id,
        seed=source.seed,
        environment_id=source.environment_id,
        state=state,
        provenance=source.provenance,
        metadata=(*metadata, NamedValue("hal_candidate", True, "bool")),
    )


def physics_assisted_measurements(result: PhysicsResult) -> tuple[NamedValue, ...]:
    """Expose physics estimates as clearly labelled telemetry inputs, never commands."""
    return (
        NamedValue("physics_battery_energy", result.predicted_state.battery_energy_wh, "Wh"),
        NamedValue("physics_motor_temperature", result.thermal.motor_c, "C"),
        NamedValue("physics_slip_ratio", result.slip_ratio, "ratio"),
        NamedValue("physics_wheel_speed", result.predicted_state.velocity_mps, "m/s"),
    )
