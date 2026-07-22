"""Canonical Digital Twin integration without implicit state acceptance."""

from __future__ import annotations

from dataclasses import replace
from math import pi

from mars_ai_os.digital_twin.events import EventBus, PhysicsPredictionCompleted
from mars_ai_os.digital_twin.models import (
    FaultState,
    HealthStatus,
    NamedValue,
    TwinSnapshot,
)
from mars_ai_os.digital_twin.provenance import create_provenance
from mars_ai_os.mars_physics.engine import PhysicsEngine
from mars_ai_os.mars_physics.models import (
    MarsEnvironment,
    PhysicsResult,
    PhysicsState,
    SimulationIntent,
    Terrain,
    VehicleParameters,
)


def state_from_snapshot(snapshot: TwinSnapshot, vehicle: VehicleParameters) -> PhysicsState:
    state = snapshot.state
    temperatures = {item.name: item.value for item in state.thermal.components_c}
    motor_temps = tuple(motor.temperature_c for motor in state.hardware.motors)
    rpm = sum(motor.rpm for motor in state.hardware.motors) / max(1, len(state.hardware.motors))
    energy = state.power.battery_energy_wh
    if energy is None:
        raise ValueError("Canonical twin battery energy is unknown")
    return PhysicsState(
        timestamp_s=snapshot.timestamp_s,
        position_m=state.navigation.position_m,
        velocity_mps=state.navigation.velocity_mps[0],
        wheel_angular_speed_rad_s=rpm * 2 * pi / 60,
        battery_energy_wh=energy,
        motor_temperature_c=sum(motor_temps) / max(1, len(motor_temps)),
        controller_temperature_c=float(
            temperatures.get("controller", temperatures.get("compute", 35.0))
        ),
        battery_temperature_c=float(temperatures.get("battery", 20.0)),
        compute_temperature_c=float(temperatures.get("compute", 35.0)),
        communication_available=state.communication.link_available,
    )


class PhysicsTwinAdapter:
    def __init__(
        self, engine: PhysicsEngine | None = None, event_bus: EventBus | None = None
    ) -> None:
        self.engine = engine or PhysicsEngine()
        self.events = event_bus or EventBus()

    def predict(
        self,
        source: TwinSnapshot,
        intent: SimulationIntent,
        environment: MarsEnvironment,
        terrain: Terrain,
        vehicle: VehicleParameters,
        *,
        timestep_s: float,
        seed: int,
    ) -> tuple[PhysicsResult, TwinSnapshot]:
        result = self.engine.step(
            state_from_snapshot(source, vehicle),
            intent,
            environment,
            terrain,
            vehicle,
            timestep_s=timestep_s,
            seed=seed,
        )
        candidate = self._candidate_snapshot(source, result, vehicle, seed)
        result = replace(
            result,
            source_snapshot_id=source.snapshot_id,
            predicted_snapshot_id=candidate.snapshot_id,
        )
        self.events.publish(
            PhysicsPredictionCompleted(
                source.timestamp_s,
                source.snapshot_id,
                candidate.snapshot_id,
                result.fingerprint,
                timestep_s,
                timestep_s,
                result.configuration_hash,
                result.warnings,
                result.assumptions,
                self.engine.configuration.model_version,
            )
        )
        return result, candidate

    def _candidate_snapshot(
        self, source: TwinSnapshot, result: PhysicsResult, vehicle: VehicleParameters, seed: int
    ) -> TwinSnapshot:
        old = source.state
        p = result.predicted_state
        slips = tuple(
            NamedValue(f"wheel_{i}", result.slip_ratio, "ratio")
            for i in range(1, vehicle.wheel_count + 1)
        )
        sensors = tuple(
            sorted(
                (
                    *old.sensors.readings,
                    NamedValue(
                        "physics_camera_quality", result.observations.camera_quality, "ratio"
                    ),
                ),
                key=lambda item: item.name,
            )
        )
        warnings = tuple(sorted(set(old.faults.warnings) | set(result.warnings)))
        health = HealthStatus.DEGRADED if warnings else old.faults.health
        candidate_state = replace(
            old,
            sensors=replace(old.sensors, readings=sensors),
            navigation=replace(
                old.navigation,
                position_m=p.position_m,
                velocity_mps=(p.velocity_mps, 0.0, 0.0),
                wheel_slip_ratio=slips,
                mode="physics-candidate",
            ),
            power=replace(
                old.power,
                battery_energy_wh=p.battery_energy_wh,
                battery_soc_percent=p.battery_energy_wh / vehicle.battery_capacity_wh * 100,
                solar_input_w=result.energy.solar_input_wh * 3600 / result.cost_vector.duration,
            ),
            thermal=replace(
                old.thermal,
                components_c=(
                    NamedValue("battery", p.battery_temperature_c, "C"),
                    NamedValue("compute", p.compute_temperature_c, "C"),
                    NamedValue("controller", p.controller_temperature_c, "C"),
                    NamedValue("motor_mean", p.motor_temperature_c, "C"),
                ),
                ambient_c=old.thermal.ambient_c,
            ),
            faults=FaultState(old.faults.faults, warnings, health),
        )
        provenance = create_provenance(
            configuration={
                "physics_configuration_hash": result.configuration_hash,
                "models": result.model_versions,
            },
            seed=seed,
            assumptions=result.assumptions,
            author="mars-physics-engine",
            recorded_at_s=p.timestamp_s,
        )
        return TwinSnapshot.create(
            timestamp_s=p.timestamp_s,
            mission_id=source.mission_id,
            seed=seed,
            environment_id=source.environment_id,
            state=candidate_state,
            provenance=provenance,
            metadata=(
                NamedValue("source_snapshot_id", source.snapshot_id),
                NamedValue("twin_kind", "physics-candidate"),
            ),
        )
