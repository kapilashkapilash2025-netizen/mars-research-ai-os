"""Safety-oriented skid-steer control for an eight-wheel Mars rover."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import pi
from time import monotonic

from mars_ai_os.navigation.motor import BLDCMotor, WheelPosition


class NavigationState(StrEnum):
    CREATED = "created"
    READY = "ready"
    STOPPED = "stopped"
    EMERGENCY_STOP = "emergency_stop"


@dataclass(frozen=True, slots=True)
class DriveLimits:
    wheel_radius_m: float = 0.25
    track_width_m: float = 1.6
    max_wheel_rpm: float = 120.0
    max_linear_speed_mps: float = 1.0
    max_angular_speed_radps: float = 0.8
    command_timeout_s: float = 0.5
    max_motor_temperature_c: float = 85.0

    def __post_init__(self) -> None:
        for name, value in (
            ("wheel_radius_m", self.wheel_radius_m),
            ("track_width_m", self.track_width_m),
            ("max_wheel_rpm", self.max_wheel_rpm),
            ("max_linear_speed_mps", self.max_linear_speed_mps),
            ("max_angular_speed_radps", self.max_angular_speed_radps),
            ("command_timeout_s", self.command_timeout_s),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")


@dataclass(slots=True)
class EightWheelDrive:
    """Coordinate four left and four right BLDC wheels as a skid-steer drive."""

    motors: Mapping[WheelPosition, BLDCMotor]
    limits: DriveLimits = field(default_factory=DriveLimits)
    clock: Callable[[], float] = monotonic
    _state: NavigationState = field(default=NavigationState.CREATED, init=False)
    _last_command_at: float | None = field(default=None, init=False)
    _stop_reason: str | None = field(default=None, init=False)

    @property
    def name(self) -> str:
        return "eight-wheel-navigation"

    @property
    def state(self) -> NavigationState:
        return self._state

    def start(self) -> None:
        if self._state is not NavigationState.CREATED:
            raise RuntimeError(f"Cannot start navigation from state {self._state}")
        self._validate_motor_layout()
        self._assert_motors_healthy()
        enabled: list[BLDCMotor] = []
        try:
            for position in WheelPosition:
                motor = self.motors[position]
                motor.enable()
                enabled.append(motor)
        except Exception:
            for motor in reversed(enabled):
                motor.disable()
            raise
        self._state = NavigationState.READY

    def command_velocity(self, linear_mps: float, angular_radps: float) -> dict[str, float]:
        if self._state is not NavigationState.READY:
            raise RuntimeError(f"Navigation is not ready: {self._state}")
        self._assert_motors_healthy()

        linear = _clamp(
            linear_mps, -self.limits.max_linear_speed_mps, self.limits.max_linear_speed_mps
        )
        angular = _clamp(
            angular_radps,
            -self.limits.max_angular_speed_radps,
            self.limits.max_angular_speed_radps,
        )
        half_track = self.limits.track_width_m / 2
        left_mps = linear - angular * half_track
        right_mps = linear + angular * half_track
        left_rpm = self._linear_speed_to_rpm(left_mps)
        right_rpm = self._linear_speed_to_rpm(right_mps)

        peak = max(abs(left_rpm), abs(right_rpm))
        if peak > self.limits.max_wheel_rpm:
            scale = self.limits.max_wheel_rpm / peak
            left_rpm *= scale
            right_rpm *= scale

        commanded: dict[str, float] = {}
        try:
            for position in WheelPosition:
                rpm = left_rpm if position.is_left else right_rpm
                self.motors[position].command_rpm(rpm)
                commanded[position.value] = rpm
        except Exception as error:
            self.emergency_stop(f"motor command failure: {error}")
            raise

        self._last_command_at = self.clock()
        return commanded

    def tick(self) -> None:
        """Run periodic safety checks; call from the vehicle control loop."""

        if self._state is not NavigationState.READY:
            return
        try:
            self._assert_motors_healthy()
        except RuntimeError as error:
            self.emergency_stop(str(error))
            return
        if (
            self._last_command_at is not None
            and self.clock() - self._last_command_at > self.limits.command_timeout_s
        ):
            self.emergency_stop("velocity command timeout")

    def emergency_stop(self, reason: str) -> None:
        for motor in self.motors.values():
            motor.stop()
        self._stop_reason = reason
        self._state = NavigationState.EMERGENCY_STOP

    def stop(self) -> None:
        for motor in reversed(tuple(self.motors.values())):
            motor.disable()
        if self._state is not NavigationState.EMERGENCY_STOP:
            self._state = NavigationState.STOPPED

    def health(self) -> dict[str, object]:
        wheel_health = {}
        for position, motor in self.motors.items():
            telemetry = motor.telemetry()
            wheel_health[position.value] = {
                "healthy": telemetry.fault is None
                and telemetry.temperature_c <= self.limits.max_motor_temperature_c,
                "rpm": telemetry.rpm,
                "temperature_c": telemetry.temperature_c,
                "bus_voltage_v": telemetry.bus_voltage_v,
                "fault": telemetry.fault,
            }
        return {
            "healthy": self._state is NavigationState.READY
            and len(wheel_health) == len(WheelPosition)
            and all(item["healthy"] for item in wheel_health.values()),
            "state": self._state.value,
            "stop_reason": self._stop_reason,
            "wheels": wheel_health,
        }

    def _linear_speed_to_rpm(self, speed_mps: float) -> float:
        return speed_mps * 60 / (2 * pi * self.limits.wheel_radius_m)

    def _validate_motor_layout(self) -> None:
        expected = set(WheelPosition)
        actual = set(self.motors)
        if actual != expected:
            missing = sorted(position.value for position in expected - actual)
            extra = sorted(str(position) for position in actual - expected)
            raise ValueError(f"Invalid eight-wheel layout; missing={missing}, extra={extra}")
        for position, motor in self.motors.items():
            if motor.position is not position:
                raise ValueError(f"Motor position mismatch at {position}")

    def _assert_motors_healthy(self) -> None:
        for position, motor in self.motors.items():
            telemetry = motor.telemetry()
            if telemetry.fault:
                raise RuntimeError(f"Motor fault at {position}: {telemetry.fault}")
            if telemetry.temperature_c > self.limits.max_motor_temperature_c:
                raise RuntimeError(
                    f"Motor over-temperature at {position}: {telemetry.temperature_c} C"
                )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))
