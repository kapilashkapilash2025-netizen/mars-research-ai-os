"""Hardware-neutral contracts for brushless DC wheel motors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class WheelPosition(StrEnum):
    LEFT_FRONT = "left_front"
    LEFT_MID_FRONT = "left_mid_front"
    LEFT_MID_REAR = "left_mid_rear"
    LEFT_REAR = "left_rear"
    RIGHT_FRONT = "right_front"
    RIGHT_MID_FRONT = "right_mid_front"
    RIGHT_MID_REAR = "right_mid_rear"
    RIGHT_REAR = "right_rear"

    @property
    def is_left(self) -> bool:
        return self.value.startswith("left_")


@dataclass(frozen=True, slots=True)
class MotorTelemetry:
    rpm: float
    temperature_c: float
    bus_voltage_v: float
    fault: str | None = None


class BLDCMotor(Protocol):
    """Interface implemented by a vendor-specific BLDC motor driver."""

    @property
    def position(self) -> WheelPosition: ...

    def enable(self) -> None: ...

    def command_rpm(self, rpm: float) -> None: ...

    def stop(self) -> None: ...

    def disable(self) -> None: ...

    def telemetry(self) -> MotorTelemetry: ...


@dataclass(slots=True)
class SimulatedBLDCMotor:
    """Deterministic motor implementation for tests and software simulation."""

    position: WheelPosition
    temperature_c: float = 20.0
    bus_voltage_v: float = 48.0
    fault: str | None = None
    enabled: bool = False
    rpm: float = 0.0

    def enable(self) -> None:
        if self.fault:
            raise RuntimeError(f"Cannot enable faulted motor {self.position}: {self.fault}")
        self.enabled = True

    def command_rpm(self, rpm: float) -> None:
        if not self.enabled:
            raise RuntimeError(f"Motor is disabled: {self.position}")
        if self.fault:
            raise RuntimeError(f"Motor fault at {self.position}: {self.fault}")
        self.rpm = rpm

    def stop(self) -> None:
        self.rpm = 0.0

    def disable(self) -> None:
        self.stop()
        self.enabled = False

    def telemetry(self) -> MotorTelemetry:
        return MotorTelemetry(
            rpm=self.rpm,
            temperature_c=self.temperature_c,
            bus_voltage_v=self.bus_voltage_v,
            fault=self.fault,
        )

