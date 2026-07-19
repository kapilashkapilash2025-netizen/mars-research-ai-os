"""Immutable, SI-unit HAL contracts; intentionally independent of device drivers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from mars_ai_os.digital_twin.provenance import canonical_json, configuration_hash


class LifecycleState(StrEnum):
    CREATED = "created"
    INITIALIZED = "initialized"
    READY = "ready"
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAULTED = "faulted"
    SAFE = "safe"
    STOPPED = "stopped"
    SHUTDOWN = "shutdown"


class CommandStatus(StrEnum):
    ACCEPTED = "accepted"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"
    DUPLICATE = "duplicate"
    UNSUPPORTED = "unsupported"
    LIMITED = "limited"
    FAULT_BLOCKED = "fault_blocked"
    ESTOP_BLOCKED = "estop_blocked"
    WATCHDOG_BLOCKED = "watchdog_blocked"


class TelemetryQuality(StrEnum):
    VALID = "valid"
    ESTIMATED = "estimated"
    DEGRADED = "degraded"
    STALE = "stale"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


class FaultSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


DRIVE_MOTOR_IDS = (
    "drive.left.front_outer",
    "drive.left.front_inner",
    "drive.left.rear_inner",
    "drive.left.rear_outer",
    "drive.right.front_outer",
    "drive.right.front_inner",
    "drive.right.rear_inner",
    "drive.right.rear_outer",
)


def _finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    device_id: str
    device_type: str
    logical_name: str
    backend_type: str
    model: str
    version: str
    interface_type: str
    capabilities: tuple[str, ...]
    units: tuple[str, ...]
    configuration_hash: str

    def __post_init__(self) -> None:
        if (
            not self.device_id.strip()
            or not self.logical_name.strip()
            or len(self.configuration_hash) != 64
        ):
            raise ValueError("Device identity requires non-empty IDs and configuration SHA-256")
        if tuple(sorted(set(self.capabilities))) != self.capabilities:
            raise ValueError("Capabilities must be sorted and unique")


@dataclass(frozen=True, slots=True)
class HalConfiguration:
    rover_id: str = "mars-reference-eight-wheel"
    backend: str = "in-memory-simulation"
    max_rpm: float = 120.0
    max_torque_nm: float = 35.0
    max_command_duration_s: float = 5.0
    watchdog_timeout_s: float = 2.0
    telemetry_max_age_s: float = 2.0
    temperature_warning_c: float = 70.0
    temperature_shutdown_c: float = 85.0
    minimum_supply_voltage_v: float = 36.0
    seed: int = 13
    model_version: str = "hal-in-memory/1.0"

    def __post_init__(self) -> None:
        if self.backend != "in-memory-simulation":
            raise ValueError(f"Unsupported backend: {self.backend}")
        for name in (
            "max_rpm",
            "max_torque_nm",
            "max_command_duration_s",
            "watchdog_timeout_s",
            "telemetry_max_age_s",
            "minimum_supply_voltage_v",
        ):
            _finite(name, getattr(self, name))
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.temperature_shutdown_c <= self.temperature_warning_c:
            raise ValueError("shutdown temperature must exceed warning temperature")

    @property
    def fingerprint(self) -> str:
        return configuration_hash(self)


@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    command_id: str
    target_device_id: str
    command_type: str
    issued_monotonic_s: float
    expires_monotonic_s: float
    sequence: int
    source: str
    payload: float
    unit: str
    correlation_id: str = ""
    mission_intent_id: str = ""
    authorized: bool = True
    configuration_hash: str = ""

    def __post_init__(self) -> None:
        _finite("payload", self.payload)
        _finite("issued_monotonic_s", self.issued_monotonic_s)
        _finite("expires_monotonic_s", self.expires_monotonic_s)
        if (
            not self.command_id
            or not self.target_device_id
            or not self.command_type
            or not self.unit
        ):
            raise ValueError("Command identity, type, and unit are required")
        if self.expires_monotonic_s <= self.issued_monotonic_s or self.sequence < 0:
            raise ValueError(
                "Command expiry must follow issue time and sequence must be non-negative"
            )


@dataclass(frozen=True, slots=True)
class CommandResult:
    command_id: str
    target_device_id: str
    status: CommandStatus
    timestamp_s: float
    lifecycle: LifecycleState
    reason: str | None = None
    applied_value: float | None = None
    applied_unit: str | None = None
    warnings: tuple[str, ...] = ()
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class TelemetryEnvelope:
    device_id: str
    sequence: int
    monotonic_s: float
    measurement: str
    value: float | None
    unit: str
    quality: TelemetryQuality
    valid: bool
    warnings: tuple[str, ...]
    configuration_hash: str
    fingerprint: str

    def fresh(self, now_s: float, max_age_s: float) -> bool:
        return self.valid and now_s - self.monotonic_s <= max_age_s


@dataclass(frozen=True, slots=True)
class HalFault:
    fault_id: str
    device_id: str
    code: str
    severity: FaultSeverity
    first_seen_s: float
    last_seen_s: float
    active: bool
    latched: bool
    recoverable: bool
    effect: str
    recommendation: str
    confidence: float


@dataclass(frozen=True, slots=True)
class AuditRecord:
    sequence: int
    timestamp_s: float
    action: str
    device_id: str | None
    detail: str
    fingerprint: str


def fingerprint(value: object) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(value).encode()).hexdigest()
