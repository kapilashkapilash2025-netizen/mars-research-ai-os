"""Bounded, assumption-explicit prediction of supported rover state."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256

from mars_ai_os.digital_twin.models import (
    CommunicationState,
    MissionState,
    NamedValue,
    PowerState,
    RoverState,
    ThermalState,
    TwinSnapshot,
)
from mars_ai_os.digital_twin.provenance import create_provenance


@dataclass(frozen=True, slots=True)
class PredictionAssumptions:
    battery_efficiency: float | None = 0.9
    thermal_response_per_s: float | None = 0.002
    compute_heat_gain_c: float | None = 15.0
    mission_progress_rate: float | None = 1.0
    communication_period_s: float | None = 900.0
    communication_duration_s: float | None = 600.0

    def __post_init__(self) -> None:
        if self.battery_efficiency is not None and not 0 <= self.battery_efficiency <= 1:
            raise ValueError("battery_efficiency must be between zero and one")
        if self.thermal_response_per_s is not None and self.thermal_response_per_s <= 0:
            raise ValueError("thermal_response_per_s must be positive")
        if self.mission_progress_rate is not None and self.mission_progress_rate < 0:
            raise ValueError("mission_progress_rate cannot be negative")
        if self.communication_period_s is not None and self.communication_period_s <= 0:
            raise ValueError("communication_period_s must be positive")
        if self.communication_duration_s is not None and self.communication_duration_s <= 0:
            raise ValueError("communication_duration_s must be positive")
        if (
            self.communication_period_s is not None
            and self.communication_duration_s is not None
            and self.communication_duration_s > self.communication_period_s
        ):
            raise ValueError("communication duration cannot exceed its period")


@dataclass(frozen=True, slots=True)
class PredictionRequest:
    horizon_s: float
    step_s: float
    assumptions: PredictionAssumptions = PredictionAssumptions()
    author: str = "predictive-twin"

    def __post_init__(self) -> None:
        if self.horizon_s <= 0 or self.step_s <= 0:
            raise ValueError("Prediction horizon and step must be positive")
        if self.step_s > self.horizon_s:
            raise ValueError("Prediction step cannot exceed horizon")
        quotient = self.horizon_s / self.step_s
        if abs(quotient - round(quotient)) > 1e-9:
            raise ValueError("Prediction horizon must be divisible by step")


@dataclass(frozen=True, slots=True)
class PredictionResult:
    prediction_id: str
    parent_snapshot_id: str
    snapshots: tuple[TwinSnapshot, ...]
    unknowns: tuple[str, ...]


class PredictiveTwin:
    def predict(self, base: TwinSnapshot, request: PredictionRequest) -> PredictionResult:
        state = base.state
        snapshots = []
        unknowns = _unknown_assumptions(request.assumptions, state)
        steps = round(request.horizon_s / request.step_s)
        prediction_id = sha256(
            f"{base.snapshot_id}:{request.horizon_s}:{request.step_s}:{request.assumptions}".encode()
        ).hexdigest()
        assumptions_text = tuple(
            sorted(
                {
                    "Prediction is informational and cannot command hardware.",
                    (
                        "Only battery, temperature, mission duration, and communication "
                        "availability are modeled."
                    ),
                    *(f"Unknown: {item}" for item in unknowns),
                }
            )
        )

        for step in range(1, steps + 1):
            timestamp = base.timestamp_s + step * request.step_s
            state = _predict_step(state, timestamp, request.step_s, request.assumptions)
            provenance = create_provenance(
                configuration={
                    "parent_configuration_hash": base.provenance.configuration_hash,
                    "prediction": request,
                },
                seed=base.seed,
                assumptions=assumptions_text,
                author=request.author,
                recorded_at_s=timestamp,
            )
            snapshots.append(
                TwinSnapshot.create(
                    timestamp_s=timestamp,
                    mission_id=base.mission_id,
                    seed=base.seed,
                    environment_id=base.environment_id,
                    state=state,
                    provenance=provenance,
                    metadata=(
                        NamedValue("prediction_id", prediction_id),
                        NamedValue("prediction_parent", base.snapshot_id),
                        NamedValue("prediction_step", step),
                    ),
                )
            )
        return PredictionResult(prediction_id, base.snapshot_id, tuple(snapshots), unknowns)


def _predict_step(
    state: RoverState,
    timestamp_s: float,
    elapsed_s: float,
    assumptions: PredictionAssumptions,
) -> RoverState:
    return replace(
        state,
        power=_predict_power(state.power, elapsed_s, assumptions),
        thermal=_predict_thermal(
            state.thermal,
            state.hardware.cpu_load_percent,
            elapsed_s,
            assumptions,
        ),
        mission=_predict_mission(state.mission, elapsed_s, assumptions),
        communication=_predict_communication(state.communication, timestamp_s, assumptions),
    )


def _predict_power(
    power: PowerState, elapsed_s: float, assumptions: PredictionAssumptions
) -> PowerState:
    required = (
        power.battery_energy_wh,
        power.battery_capacity_wh,
        power.solar_input_w,
        power.load_w,
        assumptions.battery_efficiency,
    )
    if any(value is None for value in required):
        return power
    assert power.battery_energy_wh is not None
    assert power.battery_capacity_wh is not None
    assert power.solar_input_w is not None
    assert power.load_w is not None
    assert assumptions.battery_efficiency is not None
    net_w = power.solar_input_w * assumptions.battery_efficiency - power.load_w
    energy = min(
        power.battery_capacity_wh,
        max(0.0, power.battery_energy_wh + net_w * elapsed_s / 3_600),
    )
    soc = 100 * energy / power.battery_capacity_wh
    return replace(power, battery_energy_wh=energy, battery_soc_percent=soc)


def _predict_thermal(
    thermal: ThermalState,
    cpu_load_percent: float | None,
    elapsed_s: float,
    assumptions: PredictionAssumptions,
) -> ThermalState:
    if (
        thermal.ambient_c is None
        or cpu_load_percent is None
        or assumptions.thermal_response_per_s is None
        or assumptions.compute_heat_gain_c is None
    ):
        return thermal
    target = thermal.ambient_c + assumptions.compute_heat_gain_c * cpu_load_percent / 100
    response = min(1.0, assumptions.thermal_response_per_s * elapsed_s)
    values = tuple(
        NamedValue(item.name, _approach(item.value, target, response), item.unit)
        for item in thermal.components_c
    )
    return replace(thermal, components_c=values)


def _predict_mission(
    mission: MissionState, elapsed_s: float, assumptions: PredictionAssumptions
) -> MissionState:
    if assumptions.mission_progress_rate is None:
        return mission
    progress = elapsed_s * assumptions.mission_progress_rate
    remaining = mission.estimated_remaining_s
    if remaining is not None:
        remaining = max(0.0, remaining - progress)
    return replace(mission, elapsed_s=mission.elapsed_s + progress, estimated_remaining_s=remaining)


def _predict_communication(
    communication: CommunicationState,
    timestamp_s: float,
    assumptions: PredictionAssumptions,
) -> CommunicationState:
    if assumptions.communication_period_s is None or assumptions.communication_duration_s is None:
        return communication
    available = (
        timestamp_s % assumptions.communication_period_s
        < assumptions.communication_duration_s
    )
    return replace(
        communication,
        link_available=available,
        link_quality=communication.link_quality if available else 0.0,
    )


def _unknown_assumptions(
    assumptions: PredictionAssumptions, state: RoverState
) -> tuple[str, ...]:
    unknowns = []
    if assumptions.battery_efficiency is None or any(
        value is None
        for value in (
            state.power.battery_energy_wh,
            state.power.battery_capacity_wh,
            state.power.solar_input_w,
            state.power.load_w,
        )
    ):
        unknowns.append("battery model inputs")
    if (
        assumptions.thermal_response_per_s is None
        or assumptions.compute_heat_gain_c is None
        or state.thermal.ambient_c is None
        or state.hardware.cpu_load_percent is None
    ):
        unknowns.append("thermal model inputs")
    if assumptions.mission_progress_rate is None:
        unknowns.append("mission progress rate")
    if assumptions.communication_period_s is None or assumptions.communication_duration_s is None:
        unknowns.append("communication contact schedule")
    return tuple(sorted(unknowns))


def _approach(value: object, target: float, response: float) -> object:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) + (target - float(value)) * response
    return value
