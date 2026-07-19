"""Deterministic reviewed authority from motion intent to HAL commands."""

from __future__ import annotations

from dataclasses import replace
from math import pi

from mars_ai_os.control.models import (
    ControlResult,
    DecisionTrace,
    HumanReview,
    MotionAuthorization,
    MotionIntent,
    OperatingMode,
    RoverGeometry,
    RuleOutcome,
    RuleResult,
    SourceType,
    fp,
)
from mars_ai_os.digital_twin.models import TwinSnapshot
from mars_ai_os.hal.models import DRIVE_MOTOR_IDS, CommandEnvelope, CommandStatus
from mars_ai_os.hal.simulation import InMemorySimulationBackend
from mars_ai_os.mars_physics.models import PhysicsResult


class SafetyMotionController:
    def __init__(
        self, backend: InMemorySimulationBackend, geometry: RoverGeometry | None = None
    ) -> None:
        self.backend, self.geometry = backend, geometry or RoverGeometry()
        self.mode = OperatingMode.SAFE
        self._seen: set[str] = set()
        self._last_linear = 0.0
        self._traces: list[DecisionTrace] = []

    @property
    def traces(self) -> tuple[DecisionTrace, ...]:
        return tuple(self._traces)

    def enter_mode(
        self, mode: OperatingMode, authorization: MotionAuthorization | None, now: float
    ) -> None:
        if mode in {
            OperatingMode.MANUAL_REVIEWED,
            OperatingMode.AUTONOMOUS_SUPERVISED,
            OperatingMode.RECOVERY,
            OperatingMode.TEST,
        } and (
            authorization is None
            or mode not in authorization.modes
            or authorization.expires_s <= now
        ):
            raise ValueError("explicit current authorization required")
        self.mode = mode

    def process(
        self,
        intent: MotionIntent,
        snapshot: TwinSnapshot,
        physics: PhysicsResult | None = None,
        review: HumanReview | None = None,
    ) -> ControlResult:
        now = self.backend.clock.now()
        rules: list[RuleResult] = []
        warnings: list[str] = []
        derating = {"terrain": 1.0, "power": 1.0, "thermal": 1.0}

        def fail(rule: str, msg: str) -> ControlResult:
            rules.append(RuleResult(rule, RuleOutcome.FAIL, None, None, "safe_stop", msg))
            return self._finish(
                False, 0, 0, (), (), derating, warnings, True, intent, snapshot, physics, rules
            )

        if intent.intent_id in self._seen:
            return fail("intent.duplicate", "intent already processed")
        self._seen.add(intent.intent_id)
        if now >= intent.expires_s:
            return fail("intent.fresh", "intent expired")
        if self.mode not in {
            OperatingMode.MANUAL_REVIEWED,
            OperatingMode.AUTONOMOUS_SUPERVISED,
            OperatingMode.RECOVERY,
            OperatingMode.TEST,
        }:
            return fail("mode.motion_allowed", "controller mode is safe")
        auth = intent.authorization
        if (
            auth is None
            or auth.expires_s <= now
            or intent.mode not in auth.modes
            or auth.mission_id != intent.mission_id
        ):
            return fail("authorization.valid", "authorization invalid")
        if intent.mode in {OperatingMode.MANUAL_REVIEWED, OperatingMode.RECOVERY} and (
            review is None
            or not review.approved
            or review.intent_id != intent.intent_id
            or review.expires_s <= now
        ):
            return fail("review.valid", "current human review required")
        if self.backend.estop.latched:
            return fail("hal.estop_clear", "emergency stop latched")
        if snapshot.state.power.battery_soc_percent is None:
            return fail("battery.motion_allowed", "battery state unknown")
        if snapshot.state.power.battery_soc_percent < 10 and intent.mode != OperatingMode.RECOVERY:
            return fail("battery.motion_allowed", "critical battery")
        if snapshot.state.power.battery_soc_percent < 30:
            derating["power"] = 0.5
            warnings.append("low battery derating")
        if any(
            m.temperature_c >= self.backend.config.temperature_shutdown_c
            for m in self.backend.registry.drive_motors()
        ):
            return fail("thermal.motion_allowed", "motor thermal shutdown")
        if any(
            m.temperature_c >= self.backend.config.temperature_warning_c
            for m in self.backend.registry.drive_motors()
        ):
            derating["thermal"] = 0.5
            warnings.append("motor thermal derating")
        if physics:
            if physics.confidence < 0.4:
                return fail("terrain.confidence", "physics confidence too low")
            if physics.sinkage_m >= 0.2 or physics.slip_ratio >= 0.8:
                return fail("terrain.immobilization_allowed", "immobilization risk")
            derating["terrain"] = max(
                0.2, 1 - 0.5 * physics.slip_ratio - 0.4 * abs(physics.forces.slope_force_n) / 1500
            )
            rules.append(
                RuleResult(
                    "terrain.risk",
                    RuleOutcome.PASS,
                    physics.slip_ratio,
                    0.8,
                    "derate",
                    "advisory physics estimate",
                )
            )
        factor = min(derating.values())
        max_linear = min(self.geometry.maximum_linear_mps, auth.maximum_linear_mps) * factor
        max_angular = min(self.geometry.maximum_angular_rad_s, auth.maximum_angular_rad_s) * factor
        linear = max(-max_linear, min(max_linear, intent.linear_mps))
        angular = max(-max_angular, min(max_angular, intent.angular_rad_s))
        delta = self.geometry.maximum_acceleration_mps2 * min(
            intent.duration_s, auth.maximum_duration_s
        )
        linear = max(self._last_linear - delta, min(self._last_linear + delta, linear))
        left = linear - angular * self.geometry.track_width_m / 2
        right = linear + angular * self.geometry.track_width_m / 2
        rpm_factor = 60 / (2 * pi * self.geometry.wheel_radius_m)
        wheel = tuple(
            (device, left * rpm_factor if ".left." in device else right * rpm_factor)
            for device in DRIVE_MOTOR_IDS
        )
        commands = []
        statuses = []
        for index, (device, rpm) in enumerate(wheel):
            command = CommandEnvelope(
                f"{intent.intent_id}:{index}",
                device,
                "set_rpm",
                now,
                now
                + min(
                    intent.duration_s,
                    auth.maximum_duration_s,
                    self.backend.config.max_command_duration_s,
                ),
                intent.sequence,
                "safety-motion-controller",
                rpm,
                "rpm",
                intent.correlation_id,
                intent.intent_id,
                True,
                self.backend.config.fingerprint,
            )
            result = self.backend.command(command)
            commands.append(command.command_id)
            statuses.append(result.status.value)
        if not all(
            s in {CommandStatus.APPLIED.value, CommandStatus.LIMITED.value} for s in statuses
        ):
            self.safe_stop(snapshot, "partial HAL acceptance")
            return self._finish(
                False,
                0,
                0,
                wheel,
                tuple(statuses),
                derating,
                warnings,
                True,
                intent,
                snapshot,
                physics,
                rules,
            )
        self._last_linear = linear
        rules.extend(
            (
                RuleResult("intent.valid", RuleOutcome.PASS, None, None, "allow", "validated"),
                RuleResult(
                    "hal.ready",
                    RuleOutcome.PASS,
                    None,
                    None,
                    "allow",
                    "all eight commands accepted",
                ),
            )
        )
        return self._finish(
            True,
            linear,
            angular,
            wheel,
            tuple(statuses),
            derating,
            warnings,
            False,
            intent,
            snapshot,
            physics,
            rules,
            tuple(commands),
        )

    def safe_stop(self, snapshot: TwinSnapshot, reason: str = "requested") -> ControlResult:
        now = self.backend.clock.now()
        intent = MotionIntent(
            f"safe-stop:{len(self._traces)}",
            snapshot.mission_id,
            "controller",
            SourceType.LOCAL_SAFETY_CONTROLLER,
            0,
            0,
            now,
            now + 1,
            len(self._traces),
            MotionAuthorization(
                "safe",
                "controller",
                "safety",
                (OperatingMode.SAFE,),
                0,
                0,
                1,
                now,
                now + 1,
                snapshot.mission_id,
            ),
            OperatingMode.SAFE,
            duration_s=1,
        )
        statuses = []
        wheel = []
        for i, device in enumerate(DRIVE_MOTOR_IDS):
            statuses.append(
                self.backend.command(
                    CommandEnvelope(
                        f"{intent.intent_id}:{i}",
                        device,
                        "safe_stop",
                        now,
                        now + 1,
                        i,
                        "safety-motion-controller",
                        0,
                        "rpm",
                        configuration_hash=self.backend.config.fingerprint,
                    )
                ).status.value
            )
            wheel.append((device, 0.0))
        self.mode = OperatingMode.SAFE
        self._last_linear = 0
        return self._finish(
            True,
            0,
            0,
            tuple(wheel),
            tuple(statuses),
            {"safe_stop": 1.0},
            (reason,),
            True,
            intent,
            snapshot,
            None,
            (),
        )

    def _finish(
        self,
        accepted,
        linear,
        angular,
        wheel,
        statuses,
        derating,
        warnings,
        safe,
        intent,
        snapshot,
        physics,
        rules,
        commands=(),
    ):
        trace = DecisionTrace(
            self.backend.clock.now(),
            intent.fingerprint,
            snapshot.snapshot_id,
            intent.authorization.fingerprint if intent.authorization else None,
            physics.fingerprint if physics else None,
            tuple(sorted(rules, key=lambda r: r.rule_id)),
            commands,
            tuple(sorted(set(warnings))),
            "accepted" if accepted else "rejected",
        )
        trace = replace(trace, fingerprint=fp(trace))
        self._traces.append(trace)
        return ControlResult(
            accepted,
            linear,
            angular,
            wheel,
            statuses,
            tuple(sorted(derating.items())),
            tuple(sorted(set(warnings))),
            safe,
            trace,
        )
