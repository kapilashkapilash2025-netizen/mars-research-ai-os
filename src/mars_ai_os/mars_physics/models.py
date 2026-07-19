"""Immutable SI-unit records for deterministic Mars physics predictions."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")


def _range(name: str, value: float, low: float, high: float) -> None:
    _finite(name, value)
    if not low <= value <= high:
        raise ValueError(f"{name} must be in [{low}, {high}]")


@dataclass(frozen=True, slots=True)
class MarsEnvironment:
    gravity_mps2: float = 3.721
    ambient_temperature_c: float = -30.0
    solar_irradiance_w_m2: float = 500.0
    dust_opacity: float = 0.1

    def __post_init__(self) -> None:
        _range("gravity_mps2", self.gravity_mps2, 0.1, 10.0)
        _range("ambient_temperature_c", self.ambient_temperature_c, -150.0, 40.0)
        _range("solar_irradiance_w_m2", self.solar_irradiance_w_m2, 0.0, 800.0)
        _range("dust_opacity", self.dust_opacity, 0.0, 1.0)


@dataclass(frozen=True, slots=True)
class Terrain:
    slope_deg: float = 0.0
    rolling_resistance_coefficient: float = 0.08
    traction_coefficient: float = 0.65
    cohesion_kpa: float = 2.0
    sinkage_factor_m_kpa: float = 0.003
    roughness: float = 0.1
    rock_density: float = 0.05

    def __post_init__(self) -> None:
        _range("slope_deg", self.slope_deg, -45.0, 45.0)
        _range("rolling_resistance_coefficient", self.rolling_resistance_coefficient, 0, 1)
        _range("traction_coefficient", self.traction_coefficient, 0.01, 2)
        _range("cohesion_kpa", self.cohesion_kpa, 0.01, 100)
        _range("sinkage_factor_m_kpa", self.sinkage_factor_m_kpa, 0, 1)
        _range("roughness", self.roughness, 0, 1)
        _range("rock_density", self.rock_density, 0, 1)


@dataclass(frozen=True, slots=True)
class VehicleParameters:
    mass_kg: float = 320.0
    wheel_radius_m: float = 0.25
    wheel_count: int = 8
    center_of_mass_height_m: float = 0.55
    support_half_width_m: float = 0.75
    drivetrain_efficiency: float = 0.72
    auxiliary_power_w: float = 85.0
    battery_capacity_wh: float = 5000.0
    solar_area_m2: float = 2.0
    solar_efficiency: float = 0.25

    def __post_init__(self) -> None:
        for name in (
            "mass_kg",
            "wheel_radius_m",
            "center_of_mass_height_m",
            "support_half_width_m",
            "battery_capacity_wh",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.wheel_count != 8:
            raise ValueError("This reference configuration requires exactly eight wheels")
        _range("drivetrain_efficiency", self.drivetrain_efficiency, 0.01, 1)
        _range("solar_efficiency", self.solar_efficiency, 0, 1)


@dataclass(frozen=True, slots=True)
class PhysicsConfiguration:
    model_version: str = "mars-physics/1.0"
    safe_slope_deg: float = 25.0
    maximum_sinkage_m: float = 0.25
    maximum_step_s: float = 60.0
    motor_thermal_capacity_j_c: float = 12000.0
    controller_thermal_capacity_j_c: float = 9000.0
    battery_thermal_capacity_j_c: float = 80000.0
    compute_thermal_capacity_j_c: float = 18000.0
    thermal_resistance_c_w: float = 0.6

    def __post_init__(self) -> None:
        if not self.model_version.strip():
            raise ValueError("model_version cannot be empty")
        _range("safe_slope_deg", self.safe_slope_deg, 1, 45)
        _range("maximum_sinkage_m", self.maximum_sinkage_m, 0.001, 2)
        _range("maximum_step_s", self.maximum_step_s, 0.001, 3600)


@dataclass(frozen=True, slots=True)
class PhysicsState:
    timestamp_s: float
    position_m: tuple[float, float, float]
    velocity_mps: float
    wheel_angular_speed_rad_s: float
    battery_energy_wh: float
    motor_temperature_c: float
    controller_temperature_c: float
    battery_temperature_c: float
    compute_temperature_c: float
    communication_available: bool | None

    def __post_init__(self) -> None:
        for name in (
            "timestamp_s",
            "velocity_mps",
            "wheel_angular_speed_rad_s",
            "battery_energy_wh",
            "motor_temperature_c",
            "controller_temperature_c",
            "battery_temperature_c",
            "compute_temperature_c",
        ):
            _finite(name, getattr(self, name))
        if self.timestamp_s < 0 or self.battery_energy_wh < 0:
            raise ValueError("time and battery energy cannot be negative")
        if len(self.position_m) != 3 or not all(isfinite(item) for item in self.position_m):
            raise ValueError("position_m must contain three finite SI values")


@dataclass(frozen=True, slots=True)
class SimulationIntent:
    target_speed_mps: float
    acceleration_mps2: float = 0.0
    safe_motion_state: bool = False

    def __post_init__(self) -> None:
        _finite("target_speed_mps", self.target_speed_mps)
        _finite("acceleration_mps2", self.acceleration_mps2)
        if self.target_speed_mps < 0:
            raise ValueError("Reverse motion is unsupported by reference model")


@dataclass(frozen=True, slots=True)
class ForceEstimate:
    slope_force_n: float
    normal_force_n: float
    rolling_force_n: float
    traction_limit_n: float
    demanded_force_n: float


@dataclass(frozen=True, slots=True)
class EnergyEstimate:
    drivetrain_energy_wh: float
    auxiliary_energy_wh: float
    solar_input_wh: float
    net_battery_change_wh: float
    curtailed_energy_wh: float
    unmet_energy_wh: float


@dataclass(frozen=True, slots=True)
class ThermalEstimate:
    motor_c: float
    controller_c: float
    battery_c: float
    compute_c: float


@dataclass(frozen=True, slots=True)
class SensorObservation:
    imu_acceleration_mps2: float
    encoder_speed_mps: float
    lidar_range_m: float
    camera_quality: float
    lidar_quality: float
    temperature_c: float
    battery_voltage_v: float


@dataclass(frozen=True, slots=True)
class OptimizationCostVector:
    energy: float
    traversal_risk: float
    thermal_risk: float
    slip_risk: float
    duration: float


@dataclass(frozen=True, slots=True)
class PhysicsResult:
    predicted_state: PhysicsState
    forces: ForceEstimate
    energy: EnergyEstimate
    thermal: ThermalEstimate
    slip_ratio: float
    sinkage_m: float
    observations: SensorObservation
    solar_quality: float
    communication_quality: float
    cost_vector: OptimizationCostVector
    warnings: tuple[str, ...]
    unsupported: tuple[str, ...]
    assumptions: tuple[str, ...]
    model_versions: tuple[str, ...]
    confidence: float
    configuration_hash: str
    fingerprint: str
    source_snapshot_id: str | None = None
    predicted_snapshot_id: str | None = None
