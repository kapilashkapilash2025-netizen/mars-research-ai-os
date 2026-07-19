"""Immutable reviewed-motion authority contracts in SI units."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from mars_ai_os.digital_twin.provenance import canonical_json, configuration_hash


class OperatingMode(StrEnum):
    DISABLED = "disabled"
    SAFE = "safe"
    MANUAL_REVIEWED = "manual_reviewed"
    AUTONOMOUS_SUPERVISED = "autonomous_supervised"
    RECOVERY = "recovery"
    TEST = "test"


class SourceType(StrEnum):
    MISSION_PLANNER = "mission_planner"
    AUTONOMOUS_NAVIGATION = "autonomous_navigation"
    LOCAL_SAFETY_CONTROLLER = "local_safety_controller"
    HUMAN_REVIEWED_COMMAND = "human_reviewed_command"
    TEST_HARNESS = "test_harness"
    EARTH_DELAYED_INTENT = "earth_delayed_intent"


class RuleOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


def _finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")


def fp(value: object) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class MotionAuthorization:
    authority_id: str
    subject: str
    role: str
    modes: tuple[OperatingMode, ...]
    maximum_linear_mps: float
    maximum_angular_rad_s: float
    maximum_duration_s: float
    issued_s: float
    expires_s: float
    mission_id: str
    reviewer: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "maximum_linear_mps",
            "maximum_angular_rad_s",
            "maximum_duration_s",
            "issued_s",
            "expires_s",
        ):
            _finite(name, getattr(self, name))
        if self.expires_s <= self.issued_s or not self.authority_id:
            raise ValueError("authorization must be identified and unexpired at issue")

    @property
    def fingerprint(self) -> str:
        return fp(self)


@dataclass(frozen=True, slots=True)
class HumanReview:
    intent_id: str
    reviewer: str
    approved: bool
    issued_s: float
    expires_s: float
    notes: str = ""

    @property
    def fingerprint(self) -> str:
        return fp(self)


@dataclass(frozen=True, slots=True)
class MotionIntent:
    intent_id: str
    mission_id: str
    source: str
    source_type: SourceType
    linear_mps: float
    angular_rad_s: float
    issued_s: float
    expires_s: float
    sequence: int
    authorization: MotionAuthorization | None
    mode: OperatingMode
    correlation_id: str = ""
    duration_s: float = 1.0
    human_reviewed: bool = False
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("linear_mps", "angular_rad_s", "issued_s", "expires_s", "duration_s"):
            _finite(name, getattr(self, name))
        if (
            not self.intent_id
            or self.expires_s <= self.issued_s
            or self.duration_s <= 0
            or self.sequence < 0
        ):
            raise ValueError("invalid motion intent timing or identity")

    @property
    def fingerprint(self) -> str:
        return fp(self)


@dataclass(frozen=True, slots=True)
class RoverGeometry:
    wheel_radius_m: float = 0.25
    track_width_m: float = 1.5
    maximum_linear_mps: float = 1.0
    maximum_angular_rad_s: float = 1.2
    maximum_acceleration_mps2: float = 0.4
    geometry_version: str = "skid-steer/1"

    def __post_init__(self) -> None:
        for name in (
            "wheel_radius_m",
            "track_width_m",
            "maximum_linear_mps",
            "maximum_angular_rad_s",
            "maximum_acceleration_mps2",
        ):
            _finite(name, getattr(self, name))
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")

    @property
    def fingerprint(self) -> str:
        return configuration_hash(self)


@dataclass(frozen=True, slots=True)
class RuleResult:
    rule_id: str
    outcome: RuleOutcome
    observed: float | str | None
    threshold: float | str | None
    action: str
    explanation: str


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    timestamp_s: float
    intent_fingerprint: str
    snapshot_id: str
    authorization_fingerprint: str | None
    physics_fingerprint: str | None
    rules: tuple[RuleResult, ...]
    commands: tuple[str, ...]
    warnings: tuple[str, ...]
    result: str
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class ControlResult:
    accepted: bool
    approved_linear_mps: float
    approved_angular_rad_s: float
    wheel_rpm: tuple[tuple[str, float], ...]
    command_statuses: tuple[str, ...]
    derating: tuple[tuple[str, float], ...]
    warnings: tuple[str, ...]
    safe_stop_required: bool
    trace: DecisionTrace
