"""Immutable state models shared by historical, live, and predictive twins."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from hashlib import sha256
from typing import TypeAlias

from mars_ai_os.digital_twin.provenance import ProvenanceRecord, canonical_json, canonicalize

Scalar: TypeAlias = str | int | float | bool | None
Vector3: TypeAlias = tuple[float, float, float]


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class NamedValue:
    name: str
    value: Scalar
    unit: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Named value requires a name")


@dataclass(frozen=True, slots=True)
class MotorState:
    motor_id: str
    rpm: float
    temperature_c: float
    current_a: float | None = None
    fault: str | None = None


@dataclass(frozen=True, slots=True)
class HardwareState:
    motors: tuple[MotorState, ...]
    cpu_load_percent: float | None
    memory_used_mb: float | None
    memory_total_mb: float | None

    def __post_init__(self) -> None:
        ids = tuple(motor.motor_id for motor in self.motors)
        if len(set(ids)) != len(ids) or tuple(sorted(ids)) != ids:
            raise ValueError("Motors must have unique IDs in sorted order")


@dataclass(frozen=True, slots=True)
class SensorState:
    readings: tuple[NamedValue, ...]

    def __post_init__(self) -> None:
        _require_sorted_names(self.readings, "sensor readings")


@dataclass(frozen=True, slots=True)
class NavigationState:
    position_m: Vector3
    velocity_mps: Vector3
    orientation_rpy_rad: Vector3
    wheel_slip_ratio: tuple[NamedValue, ...]
    mode: str

    def __post_init__(self) -> None:
        _require_sorted_names(self.wheel_slip_ratio, "wheel slip values")


@dataclass(frozen=True, slots=True)
class CommunicationState:
    link_available: bool | None
    link_quality: float | None
    queued_bundles: int
    one_way_delay_s: float | None


@dataclass(frozen=True, slots=True)
class PowerState:
    battery_energy_wh: float | None
    battery_capacity_wh: float | None
    battery_soc_percent: float | None
    solar_input_w: float | None
    load_w: float | None


@dataclass(frozen=True, slots=True)
class ThermalState:
    components_c: tuple[NamedValue, ...]
    ambient_c: float | None

    def __post_init__(self) -> None:
        _require_sorted_names(self.components_c, "thermal components")


@dataclass(frozen=True, slots=True)
class FaultState:
    faults: tuple[str, ...]
    warnings: tuple[str, ...]
    health: HealthStatus

    def __post_init__(self) -> None:
        if tuple(sorted(set(self.faults))) != self.faults:
            raise ValueError("Faults must be unique and sorted")
        if tuple(sorted(set(self.warnings))) != self.warnings:
            raise ValueError("Warnings must be unique and sorted")


@dataclass(frozen=True, slots=True)
class MissionState:
    phase: str
    active_task: str | None
    elapsed_s: float
    estimated_remaining_s: float | None


@dataclass(frozen=True, slots=True)
class RoverState:
    hardware: HardwareState
    sensors: SensorState
    navigation: NavigationState
    communication: CommunicationState
    power: PowerState
    thermal: ThermalState
    faults: FaultState
    mission: MissionState


@dataclass(frozen=True, slots=True)
class TwinSnapshot:
    timestamp_s: float
    mission_id: str
    seed: int
    environment_id: str
    state: RoverState
    provenance: ProvenanceRecord
    metadata: tuple[NamedValue, ...]
    snapshot_id: str = ""

    def __post_init__(self) -> None:
        if not self.mission_id.strip() or not self.environment_id.strip():
            raise ValueError("Snapshot mission and environment IDs cannot be empty")
        if self.seed != self.provenance.seed:
            raise ValueError("Snapshot and provenance seeds must match")
        if self.timestamp_s != self.provenance.recorded_at_s:
            raise ValueError("Snapshot and provenance timestamps must match")
        _require_sorted_names(self.metadata, "snapshot metadata")
        if self.snapshot_id and len(self.snapshot_id) != 64:
            raise ValueError("snapshot_id must be a SHA-256 hex digest")

    @classmethod
    def create(
        cls,
        *,
        timestamp_s: float,
        mission_id: str,
        seed: int,
        environment_id: str,
        state: RoverState,
        provenance: ProvenanceRecord,
        metadata: tuple[NamedValue, ...] = (),
    ) -> TwinSnapshot:
        snapshot = cls(
            timestamp_s=timestamp_s,
            mission_id=mission_id,
            seed=seed,
            environment_id=environment_id,
            state=state,
            provenance=provenance,
            metadata=tuple(sorted(metadata, key=lambda item: item.name)),
        )
        digest = sha256(snapshot.canonical_payload().encode("utf-8")).hexdigest()
        return replace(snapshot, snapshot_id=digest)

    def canonical_payload(self) -> str:
        payload = canonicalize(self)
        payload["snapshot_id"] = ""
        return canonical_json(payload)

    def to_dict(self) -> dict[str, object]:
        return canonicalize(self)


def reference_rover_state() -> RoverState:
    motors = tuple(
        MotorState(f"motor_{index}", rpm=0.0, temperature_c=20.0)
        for index in range(1, 9)
    )
    slips = tuple(NamedValue(f"wheel_{index}", 0.0, "ratio") for index in range(1, 9))
    return RoverState(
        hardware=HardwareState(motors, 5.0, 512.0, 8_192.0),
        sensors=SensorState(
            (
                NamedValue("imu_acceleration_x", 0.0, "m/s2"),
                NamedValue("lidar_nearest_range", None, "m"),
            )
        ),
        navigation=NavigationState(
            position_m=(0.0, 0.0, 0.0),
            velocity_mps=(0.0, 0.0, 0.0),
            orientation_rpy_rad=(0.0, 0.0, 0.0),
            wheel_slip_ratio=slips,
            mode="idle",
        ),
        communication=CommunicationState(None, None, 0, None),
        power=PowerState(4_000.0, 5_000.0, 80.0, 120.0, 90.0),
        thermal=ThermalState(
            (
                NamedValue("battery", 20.0, "C"),
                NamedValue("compute", 35.0, "C"),
            ),
            ambient_c=-20.0,
        ),
        faults=FaultState((), (), HealthStatus.HEALTHY),
        mission=MissionState("idle", None, 0.0, None),
    )


def _require_sorted_names(values: tuple[NamedValue, ...], label: str) -> None:
    names = tuple(item.name for item in values)
    if len(set(names)) != len(names) or tuple(sorted(names)) != names:
        raise ValueError(f"{label} must have unique names in sorted order")
