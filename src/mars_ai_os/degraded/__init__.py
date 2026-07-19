"""Default-deny, reviewed degraded mobility assessment."""

from dataclasses import dataclass, replace
from enum import StrEnum

from mars_ai_os.digital_twin.provenance import canonical_json
from mars_ai_os.hal.models import DRIVE_MOTOR_IDS, LifecycleState


def _fingerprint(value: object) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class MotorHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    UNKNOWN = "unknown"


class MechanicalState(StrEnum):
    FREE_ROLLING = "free_rolling"
    BRAKED = "braked"
    LOCKED = "locked"
    UNKNOWN = "unknown"


class DegradationClass(StrEnum):
    NOMINAL = "nominal"
    SINGLE_MOTOR_UNAVAILABLE = "single_motor_unavailable"
    MULTIPLE_MOTOR_FAILURE = "multiple_motor_failure"
    UNKNOWN_DRIVE_STATE = "unknown_drive_state"


class StopConfirmation(StrEnum):
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    UNCONFIRMED = "unconfirmed"


@dataclass(frozen=True, slots=True)
class MotorAssessment:
    device_id: str
    health: MotorHealth
    mechanical: MechanicalState
    lifecycle: LifecycleState
    telemetry_fresh: bool
    rpm: float | None
    timestamp_s: float
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class DriveAssessment:
    motors: tuple[MotorAssessment, ...]
    classification: DegradationClass
    left_capability: float
    right_capability: float
    confidence: float
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class ControlEvent:
    event_id: str
    event_type: str
    timestamp_s: float
    health_fingerprint: str
    fingerprint: str = ""


class EventBus:
    def __init__(self) -> None:
        self._events: list[ControlEvent] = []

    @property
    def events(self) -> tuple[ControlEvent, ...]:
        return tuple(self._events)

    def publish(self, event_type: str, now_s: float, health_fingerprint: str) -> ControlEvent:
        event = ControlEvent(
            f"{event_type}:{len(self._events)}", event_type, now_s, health_fingerprint
        )
        event = replace(event, fingerprint=_fingerprint(event))
        self._events.append(event)
        return event

    def replay(self) -> tuple[ControlEvent, ...]:
        """Read-only event replay; it never executes HAL commands."""
        return self.events


class DegradedMobilityService:
    def __init__(self, backend: object, bus: EventBus | None = None) -> None:
        self.backend = backend
        self.bus = bus or EventBus()

    def assess(self) -> DriveAssessment:
        now_s = self.backend.clock.now()
        rows: list[MotorAssessment] = []
        for device_id in DRIVE_MOTOR_IDS:
            motor = self.backend.registry.get(device_id)
            if motor is None:
                row = MotorAssessment(
                    device_id,
                    MotorHealth.UNKNOWN,
                    MechanicalState.UNKNOWN,
                    LifecycleState.CREATED,
                    False,
                    None,
                    now_s,
                )
            else:
                stale = (
                    motor.last_command_s is not None
                    and now_s - motor.last_command_s > self.backend.config.telemetry_max_age_s
                )
                mechanical = getattr(motor, "mechanical_state", MechanicalState.FREE_ROLLING)
                health = MotorHealth.STALE if stale else MotorHealth.HEALTHY
                if motor.lifecycle in {LifecycleState.FAULTED, LifecycleState.SHUTDOWN}:
                    health = MotorHealth.UNAVAILABLE
                row = MotorAssessment(
                    device_id, health, mechanical, motor.lifecycle, not stale, motor.rpm, now_s
                )
            rows.append(replace(row, fingerprint=_fingerprint(row)))
        failures = [row for row in rows if row.health != MotorHealth.HEALTHY]
        unsafe = any(
            row.mechanical
            in {MechanicalState.BRAKED, MechanicalState.LOCKED, MechanicalState.UNKNOWN}
            for row in rows
        )
        kind = (
            DegradationClass.UNKNOWN_DRIVE_STATE
            if unsafe or any(row.health in {MotorHealth.STALE, MotorHealth.UNKNOWN} for row in rows)
            else DegradationClass.NOMINAL
            if not failures
            else DegradationClass.SINGLE_MOTOR_UNAVAILABLE
            if len(failures) == 1
            else DegradationClass.MULTIPLE_MOTOR_FAILURE
        )
        left = sum(row.health == MotorHealth.HEALTHY for row in rows[:4]) / 4
        right = sum(row.health == MotorHealth.HEALTHY for row in rows[4:]) / 4
        assessment = DriveAssessment(tuple(rows), kind, left, right, min(left, right))
        assessment = replace(assessment, fingerprint=_fingerprint(assessment))
        self.bus.publish("DriveHealthAssessed", now_s, assessment.fingerprint)
        if kind != DegradationClass.NOMINAL:
            self.bus.publish("DriveDegradationDetected", now_s, assessment.fingerprint)
        return assessment

    def confirm_safe_stop(self, assessment: DriveAssessment) -> StopConfirmation:
        if any(not row.telemetry_fresh or row.rpm is None for row in assessment.motors):
            return StopConfirmation.UNCONFIRMED
        return (
            StopConfirmation.CONFIRMED
            if all(row.rpm == 0 or row.health != MotorHealth.HEALTHY for row in assessment.motors)
            else StopConfirmation.PARTIAL
        )
