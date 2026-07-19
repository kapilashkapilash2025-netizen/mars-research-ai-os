from __future__ import annotations

from dataclasses import dataclass

import pytest

from mars_ai_os.navigation.drive import DriveLimits, EightWheelDrive, NavigationState
from mars_ai_os.navigation.motor import SimulatedBLDCMotor, WheelPosition


def make_motors() -> dict[WheelPosition, SimulatedBLDCMotor]:
    return {position: SimulatedBLDCMotor(position) for position in WheelPosition}


def test_forward_command_drives_all_eight_wheels() -> None:
    motors = make_motors()
    drive = EightWheelDrive(motors)
    drive.start()

    command = drive.command_velocity(linear_mps=0.5, angular_radps=0.0)

    assert len(command) == 8
    assert len({round(rpm, 6) for rpm in command.values()}) == 1
    assert all(motor.rpm > 0 for motor in motors.values())


def test_turn_command_mixes_left_and_right_wheels() -> None:
    drive = EightWheelDrive(make_motors())
    drive.start()

    command = drive.command_velocity(linear_mps=0.4, angular_radps=0.25)

    left = {command[position.value] for position in WheelPosition if position.is_left}
    right = {command[position.value] for position in WheelPosition if not position.is_left}
    assert len(left) == 1
    assert len(right) == 1
    assert left.pop() < right.pop()


@dataclass
class FakeClock:
    now: float = 0.0

    def __call__(self) -> float:
        return self.now


def test_command_timeout_latches_emergency_stop() -> None:
    clock = FakeClock()
    motors = make_motors()
    drive = EightWheelDrive(motors, DriveLimits(command_timeout_s=0.25), clock)
    drive.start()
    drive.command_velocity(0.5, 0.0)

    clock.now = 0.3
    drive.tick()

    assert drive.state is NavigationState.EMERGENCY_STOP
    assert drive.health()["stop_reason"] == "velocity command timeout"
    assert all(motor.rpm == 0 for motor in motors.values())


def test_motor_fault_stops_every_wheel() -> None:
    motors = make_motors()
    drive = EightWheelDrive(motors)
    drive.start()
    drive.command_velocity(0.5, 0.0)
    motors[WheelPosition.RIGHT_REAR].fault = "over-current"

    drive.tick()

    assert drive.state is NavigationState.EMERGENCY_STOP
    assert all(motor.rpm == 0 for motor in motors.values())


def test_requires_exactly_eight_correctly_mapped_motors() -> None:
    motors = make_motors()
    del motors[WheelPosition.LEFT_FRONT]
    drive = EightWheelDrive(motors)

    with pytest.raises(ValueError, match="missing"):
        drive.start()

