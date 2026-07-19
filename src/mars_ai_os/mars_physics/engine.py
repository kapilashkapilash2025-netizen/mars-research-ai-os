"""Deterministic, information-only Mars physics orchestration."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from math import atan, cos, exp, radians, sin, sqrt
from random import Random

from mars_ai_os.digital_twin.provenance import canonical_json, configuration_hash
from mars_ai_os.mars_physics.models import (
    EnergyEstimate,
    ForceEstimate,
    MarsEnvironment,
    OptimizationCostVector,
    PhysicsConfiguration,
    PhysicsResult,
    PhysicsState,
    SensorObservation,
    SimulationIntent,
    Terrain,
    ThermalEstimate,
    VehicleParameters,
)

ASSUMPTIONS = (
    "Dust attenuation is a bounded engineering approximation.",
    "Regolith sinkage is not calibrated terramechanics.",
    "Thermal behavior uses a first-order lumped model.",
    "Wheel loads are distributed equally across eight wheels.",
)


class PhysicsEngine:
    """Predict candidate physical state; never actuate or mutate canonical state."""

    def __init__(self, configuration: PhysicsConfiguration | None = None) -> None:
        self.configuration = configuration or PhysicsConfiguration()

    def step(
        self,
        state: PhysicsState,
        intent: SimulationIntent,
        environment: MarsEnvironment,
        terrain: Terrain,
        vehicle: VehicleParameters,
        *,
        timestep_s: float,
        seed: int,
    ) -> PhysicsResult:
        if not 0 < timestep_s <= self.configuration.maximum_step_s:
            raise ValueError("timestep_s must be positive and within configured maximum")
        if state.battery_energy_wh > vehicle.battery_capacity_wh:
            raise ValueError("battery energy exceeds configured capacity")
        if (
            state.communication_available is False
            and (intent.target_speed_mps > 0 or intent.acceleration_mps2 > 0)
            and not intent.safe_motion_state
        ):
            raise ValueError("Communication loss requires an explicit safe motion state")

        cfg = self.configuration
        theta = radians(terrain.slope_deg)
        normal = max(0.0, vehicle.mass_kg * environment.gravity_mps2 * cos(theta))
        slope_force = vehicle.mass_kg * environment.gravity_mps2 * sin(theta)
        rolling = (
            normal
            * terrain.rolling_resistance_coefficient
            * (1 + 0.7 * terrain.roughness + 0.5 * terrain.rock_density)
        )
        demanded = vehicle.mass_kg * intent.acceleration_mps2 + rolling + slope_force
        traction_limit = normal * terrain.traction_coefficient
        traction_excess = max(0.0, demanded - traction_limit) / max(abs(demanded), 1.0)
        wheel_speed = state.wheel_angular_speed_rad_s * vehicle.wheel_radius_m
        kinematic_slip = abs(wheel_speed - state.velocity_mps) / max(
            abs(wheel_speed), abs(state.velocity_mps), 0.05
        )
        slip = min(1.0, max(0.0, 0.45 * kinematic_slip + 0.55 * traction_excess))

        load_kpa = normal / vehicle.wheel_count / 1000.0
        sinkage = min(
            cfg.maximum_sinkage_m,
            terrain.sinkage_factor_m_kpa * load_kpa / terrain.cohesion_kpa * (1 + slip),
        )
        distance = intent.target_speed_mps * timestep_s
        positive_mechanical_j = max(0.0, demanded) * distance
        drivetrain_wh = positive_mechanical_j / vehicle.drivetrain_efficiency / 3600.0
        auxiliary_wh = vehicle.auxiliary_power_w * timestep_s / 3600.0
        dust_factor = max(0.0, 1.0 - 0.85 * environment.dust_opacity)
        solar_wh = (
            environment.solar_irradiance_w_m2
            * vehicle.solar_area_m2
            * vehicle.solar_efficiency
            * dust_factor
            * timestep_s
            / 3600.0
        )
        requested_change = solar_wh - drivetrain_wh - auxiliary_wh
        battery = min(
            vehicle.battery_capacity_wh,
            max(0.0, state.battery_energy_wh + requested_change),
        )
        actual_change = battery - state.battery_energy_wh
        curtailed_energy = max(0.0, requested_change - actual_change)
        unmet_energy = max(0.0, actual_change - requested_change)

        loss_w = (
            positive_mechanical_j / max(timestep_s, 1e-9) * (1 / vehicle.drivetrain_efficiency - 1)
        )
        motor = self._thermal_step(
            state.motor_temperature_c,
            environment.ambient_temperature_c,
            loss_w * 0.65,
            cfg.motor_thermal_capacity_j_c,
            timestep_s,
        )
        controller = self._thermal_step(
            state.controller_temperature_c,
            environment.ambient_temperature_c,
            loss_w * 0.25,
            cfg.controller_thermal_capacity_j_c,
            timestep_s,
        )
        battery_temp = self._thermal_step(
            state.battery_temperature_c,
            environment.ambient_temperature_c,
            abs(actual_change) * 2.0,
            cfg.battery_thermal_capacity_j_c,
            timestep_s,
        )
        compute = self._thermal_step(
            state.compute_temperature_c,
            environment.ambient_temperature_c,
            vehicle.auxiliary_power_w * 0.35,
            cfg.compute_thermal_capacity_j_c,
            timestep_s,
        )

        achieved_speed = (
            intent.target_speed_mps
            * (1 - slip)
            * max(0.2, 1 - sinkage / cfg.maximum_sinkage_m * 0.5)
        )
        x, y, z = state.position_m
        predicted = PhysicsState(
            timestamp_s=state.timestamp_s + timestep_s,
            position_m=(
                x + achieved_speed * timestep_s * cos(theta),
                y,
                z + achieved_speed * timestep_s * sin(theta),
            ),
            velocity_mps=achieved_speed,
            wheel_angular_speed_rad_s=intent.target_speed_mps / vehicle.wheel_radius_m,
            battery_energy_wh=battery,
            motor_temperature_c=motor,
            controller_temperature_c=controller,
            battery_temperature_c=battery_temp,
            compute_temperature_c=compute,
            communication_available=state.communication_available,
        )
        rng = Random(seed)
        visibility = max(0.0, 1 - environment.dust_opacity)
        observations = SensorObservation(
            imu_acceleration_mps2=intent.acceleration_mps2
            + rng.gauss(0, 0.015)
            + seed % 7 * 0.0001,
            encoder_speed_mps=achieved_speed + rng.gauss(0, 0.005),
            lidar_range_m=max(0.0, 30 * visibility + rng.gauss(0, 0.03)),
            camera_quality=max(0.0, min(1.0, visibility**1.5)),
            lidar_quality=max(0.0, min(1.0, visibility * 0.9)),
            temperature_c=motor + rng.gauss(0, 0.1),
            battery_voltage_v=max(
                0.0, 48 * sqrt(battery / vehicle.battery_capacity_wh) + rng.gauss(0, 0.02)
            ),
        )
        stability_limit = (
            90.0
            - atan(vehicle.center_of_mass_height_m / vehicle.support_half_width_m)
            * 180
            / 3.141592653589793
        )
        warnings: list[str] = []
        if abs(terrain.slope_deg) > cfg.safe_slope_deg:
            warnings.append("safe slope threshold exceeded")
        if abs(terrain.slope_deg) >= stability_limit:
            warnings.append("static stability margin exceeded")
        if terrain.slope_deg < -cfg.safe_slope_deg * 0.7:
            warnings.append("downhill regenerative/braking capacity requires safety review")
        if slip >= 0.6 or sinkage >= cfg.maximum_sinkage_m * 0.8:
            warnings.append("immobilization risk; derating or safe state advised")
        if max(motor, controller) >= 80:
            warnings.append("thermal derating advised")
        if battery <= 0:
            warnings.append("battery depleted; safe state required")
        if environment.dust_opacity >= 0.7:
            warnings.append("dust significantly degrades sensing, solar input, and communications")
        communication_quality = visibility if state.communication_available is not False else 0.0
        traversal_risk = min(
            1.0,
            0.4 * slip
            + 0.3 * abs(terrain.slope_deg) / 45
            + 0.2 * terrain.roughness
            + 0.1 * terrain.rock_density,
        )
        thermal_risk = min(1.0, max(0.0, max(motor, controller, battery_temp, compute) - 45) / 55)
        confidence = max(
            0.0,
            min(
                1.0,
                0.85
                - 0.25 * terrain.roughness
                - 0.2 * environment.dust_opacity
                - 0.2 * sinkage / cfg.maximum_sinkage_m,
            ),
        )
        config_hash = configuration_hash((cfg, environment, terrain, vehicle))
        base = PhysicsResult(
            predicted_state=predicted,
            forces=ForceEstimate(slope_force, normal, rolling, traction_limit, demanded),
            energy=EnergyEstimate(
                drivetrain_wh,
                auxiliary_wh,
                solar_wh,
                actual_change,
                curtailed_energy,
                unmet_energy,
            ),
            thermal=ThermalEstimate(motor, controller, battery_temp, compute),
            slip_ratio=slip,
            sinkage_m=sinkage,
            observations=observations,
            solar_quality=dust_factor,
            communication_quality=communication_quality,
            cost_vector=OptimizationCostVector(
                drivetrain_wh + auxiliary_wh, traversal_risk, thermal_risk, slip, timestep_s
            ),
            warnings=tuple(sorted(set(warnings))),
            unsupported=(),
            assumptions=ASSUMPTIONS,
            model_versions=(cfg.model_version, "sensor-noise/1.0", "thermal-lumped/1.0"),
            confidence=confidence,
            configuration_hash=config_hash,
            fingerprint="",
        )
        fingerprint = sha256(canonical_json(base).encode()).hexdigest()
        return replace(base, fingerprint=fingerprint)

    def _thermal_step(
        self, current: float, ambient: float, heat_w: float, capacity: float, dt: float
    ) -> float:
        equilibrium = ambient + heat_w * self.configuration.thermal_resistance_c_w
        tau = capacity * self.configuration.thermal_resistance_c_w
        return equilibrium + (current - equilibrium) * exp(-dt / tau)
