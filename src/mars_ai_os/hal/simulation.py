"""Deterministic HAL behavior simulator, not a BLDC electrical model."""

from __future__ import annotations

from dataclasses import replace

from mars_ai_os.hal.models import (
    DRIVE_MOTOR_IDS,
    CommandEnvelope,
    CommandResult,
    CommandStatus,
    DeviceIdentity,
    HalConfiguration,
    HalFault,
    LifecycleState,
    TelemetryEnvelope,
    TelemetryQuality,
    fingerprint,
)
from mars_ai_os.hal.runtime import VALID_TRANSITIONS, AuditStream, DeviceRegistry


class SimulatedDriveMotor:
    def __init__(self, identity: DeviceIdentity, configuration: HalConfiguration) -> None:
        self.identity, self.config = identity, configuration
        self.lifecycle = LifecycleState.CREATED
        self.rpm = self.torque = 0.0
        self.temperature_c, self.voltage_v = 25.0, 48.0
        self.last_command_s: float | None = None
        self._seen: set[str] = set()
        self._sequence = 0
        self.faults: list[HalFault] = []

    def transition(self, state: LifecycleState) -> None:
        if state not in VALID_TRANSITIONS[self.lifecycle]:
            raise ValueError(f"Invalid lifecycle transition {self.lifecycle}->{state}")
        self.lifecycle = state

    def initialize_ready(self) -> None:
        self.transition(LifecycleState.INITIALIZED)
        self.transition(LifecycleState.READY)

    def safe_stop(self) -> None:
        self.rpm = self.torque = 0.0
        if self.lifecycle not in {LifecycleState.SHUTDOWN, LifecycleState.SAFE}:
            self.lifecycle = LifecycleState.SAFE

    def process(self, command: CommandEnvelope, now_s: float, estop: bool) -> CommandResult:
        def result(
            status: CommandStatus,
            reason: str | None = None,
            value: float | None = None,
            warnings: tuple[str, ...] = (),
        ) -> CommandResult:
            r = CommandResult(
                command.command_id,
                command.target_device_id,
                status,
                now_s,
                self.lifecycle,
                reason,
                value,
                command.unit if value is not None else None,
                warnings,
            )
            return replace(r, fingerprint=fingerprint(r))

        if command.command_id in self._seen:
            return result(CommandStatus.DUPLICATE, "command already processed")
        self._seen.add(command.command_id)
        if command.target_device_id != self.identity.device_id:
            return result(CommandStatus.REJECTED, "target mismatch")
        if estop:
            return result(CommandStatus.ESTOP_BLOCKED, "rover emergency stop latched")
        if self.lifecycle in {LifecycleState.FAULTED, LifecycleState.SHUTDOWN}:
            return result(CommandStatus.FAULT_BLOCKED, "device is unavailable")
        if now_s >= command.expires_monotonic_s:
            return result(CommandStatus.EXPIRED, "command expired")
        if not command.authorized:
            return result(CommandStatus.REJECTED, "safety authorization missing")
        if self.temperature_c >= self.config.temperature_shutdown_c:
            self.safe_stop()
            return result(CommandStatus.FAULT_BLOCKED, "thermal shutdown")
        if self.voltage_v < self.config.minimum_supply_voltage_v:
            self.safe_stop()
            return result(CommandStatus.FAULT_BLOCKED, "supply voltage too low")
        if command.command_type not in {"set_rpm", "set_torque", "safe_stop"}:
            return result(CommandStatus.UNSUPPORTED, "unsupported command type")
        if command.command_type == "safe_stop":
            self.safe_stop()
            return result(CommandStatus.APPLIED, value=0.0)
        expected_unit = "rpm" if command.command_type == "set_rpm" else "N*m"
        if command.unit != expected_unit:
            return result(CommandStatus.REJECTED, "incompatible unit")
        limit = (
            self.config.max_rpm if command.command_type == "set_rpm" else self.config.max_torque_nm
        )
        if command.command_type == "set_torque" and abs(command.payload) > limit:
            return result(CommandStatus.REJECTED, "hard torque limit exceeded")
        value = max(-limit, min(limit, command.payload))
        limited = value != command.payload
        if command.command_type == "set_rpm":
            self.rpm = value
        else:
            self.torque = value
        self.last_command_s = now_s
        self.lifecycle = LifecycleState.ACTIVE if value else LifecycleState.STOPPED
        return result(
            CommandStatus.LIMITED if limited else CommandStatus.APPLIED,
            value=value,
            warnings=("rpm limited",) if limited else (),
        )

    def watchdog(self, now_s: float) -> bool:
        if (
            self.last_command_s is not None
            and now_s - self.last_command_s > self.config.watchdog_timeout_s
            and self.rpm
        ):
            self.safe_stop()
            return True
        return False

    def telemetry(self, now_s: float) -> tuple[TelemetryEnvelope, ...]:
        quality = (
            TelemetryQuality.DEGRADED
            if self.temperature_c >= self.config.temperature_warning_c
            else TelemetryQuality.VALID
        )
        values = (
            ("applied_rpm", self.rpm, "rpm"),
            ("applied_torque", self.torque, "N*m"),
            ("temperature", self.temperature_c, "C"),
            ("encoder_speed", self.rpm / 60.0, "rev/s"),
        )
        output = []
        for name, value, unit in values:
            self._sequence += 1
            item = TelemetryEnvelope(
                self.identity.device_id,
                self._sequence,
                now_s,
                name,
                value,
                unit,
                quality,
                True,
                (),
                self.identity.configuration_hash,
                "",
            )
            output.append(replace(item, fingerprint=fingerprint(item)))
        return tuple(output)


class EmergencyStopCoordinator:
    def __init__(self, registry: DeviceRegistry, audit: AuditStream) -> None:
        self.registry, self.audit, self.latched = registry, audit, False

    def activate(self, now_s: float) -> tuple[HalFault, ...]:
        self.latched = True
        faults = []
        for motor in self.registry.drive_motors():
            motor.safe_stop()
        self.audit.append(now_s, "emergency_stop_activated", None, "all drive motors safe-stopped")
        return tuple(faults)

    def clear(self, now_s: float, authorized: bool) -> bool:
        if not authorized:
            return False
        self.latched = False
        for motor in self.registry.drive_motors():
            if motor.lifecycle == LifecycleState.SAFE:
                motor.lifecycle = LifecycleState.STOPPED
        self.audit.append(now_s, "emergency_stop_cleared", None, "no prior motion restored")
        return True


class InMemorySimulationBackend:
    def __init__(self, configuration: HalConfiguration, clock: object) -> None:
        self.config, self.clock = configuration, clock
        self.registry = DeviceRegistry()
        self.audit = AuditStream()
        for device_id in DRIVE_MOTOR_IDS:
            identity = DeviceIdentity(
                device_id,
                "drive-motor",
                device_id,
                "in-memory-simulation",
                "bldc-behavior-model",
                configuration.model_version,
                "actuator",
                ("actuator", "fault", "lifecycle", "telemetry"),
                ("rpm", "N*m", "C"),
                configuration.fingerprint,
            )
            self.registry.register(SimulatedDriveMotor(identity, configuration))
        self.estop = EmergencyStopCoordinator(self.registry, self.audit)

    def initialize(self) -> None:
        for motor in self.registry.drive_motors():
            motor.initialize_ready()
        self.audit.append(
            self.clock.now(), "backend_initialized", None, "eight deterministic drive motors ready"
        )

    def command(self, command: CommandEnvelope) -> CommandResult:
        device = self.registry.get(command.target_device_id)
        if device is None:
            r = CommandResult(
                command.command_id,
                command.target_device_id,
                CommandStatus.REJECTED,
                self.clock.now(),
                LifecycleState.CREATED,
                "unknown device",
            )
            return replace(r, fingerprint=fingerprint(r))
        result = device.process(command, self.clock.now(), self.estop.latched)
        self.audit.append(
            self.clock.now(), "command_processed", command.target_device_id, result.status.value
        )
        return result

    def tick(self) -> tuple[str, ...]:
        expired = []
        for motor in self.registry.drive_motors():
            if motor.watchdog(self.clock.now()):
                expired.append(motor.identity.device_id)
                self.audit.append(
                    self.clock.now(), "watchdog_expired", motor.identity.device_id, "safe stop"
                )
        return tuple(expired)

    def telemetry(self) -> tuple[TelemetryEnvelope, ...]:
        return tuple(t for m in self.registry.drive_motors() for t in m.telemetry(self.clock.now()))
