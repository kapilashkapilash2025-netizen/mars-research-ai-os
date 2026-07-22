"""Versioned JSON contracts for the Areograph Verifiable Mission Twin."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any

from mars_ai_os.digital_twin.provenance import canonical_json

SCHEMA_VERSION = "areograph.mission.v1"
MODEL_VERSION = "areograph-mission-orchestrator/1.0"
SOURCE_CLASSES = ("source-derived", "synthetic", "inferred", "simulated")


def content_id(prefix: str, value: object) -> str:
    return f"{prefix}_{sha256(canonical_json(value).encode()).hexdigest()[:24]}"


def content_hash(value: object) -> str:
    return sha256(canonical_json(value).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    reference_id: str
    label: str
    source_classification: str
    publisher: str
    locator: str
    limitation: str


@dataclass(frozen=True, slots=True)
class PredictionAssumption:
    assumption_id: str
    text: str
    source_classification: str = "synthetic"


@dataclass(frozen=True, slots=True)
class TerrainSegment:
    segment_id: str
    distance_m: float
    slope_deg: float
    roughness: float
    traction_coefficient: float
    science_value: float


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    route_id: str
    name: str
    strategy: str
    segments: tuple[TerrainSegment, ...]
    science_value: float


@dataclass(frozen=True, slots=True)
class EnvironmentScenario:
    scenario_id: str
    name: str
    dust_opacity: float
    wheel_efficiency: float
    battery_factor: float
    communication_delay_s: float
    assumptions: tuple[PredictionAssumption, ...]


@dataclass(frozen=True, slots=True)
class RoverStateSnapshot:
    snapshot_id: str
    sequence: int
    status: str
    position_m: tuple[float, float, float]
    distance_travelled_m: float
    battery_energy_wh: float
    battery_reserve_percent: float
    velocity_mps: float
    peak_wheel_slip: float
    peak_temperature_c: float
    elapsed_s: float
    source_classification: str = "simulated"


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    name: str
    normalized_value: float
    weight: float
    contribution: float
    explanation: str


@dataclass(frozen=True, slots=True)
class PredictedOutcome:
    prediction_id: str
    route_id: str
    scenario_id: str
    completion_status: str
    estimated_duration_s: float
    estimated_energy_use_wh: float
    battery_reserve_percent: float
    peak_wheel_slip: float
    peak_temperature_c: float
    safety_interventions: tuple[str, ...]
    recovery_events: tuple[str, ...]
    key_risk_factors: tuple[str, ...]
    score: float
    score_components: tuple[ScoreComponent, ...]
    confidence_classification: str
    assumptions: tuple[PredictionAssumption, ...]
    limitations: tuple[str, ...]
    source_classification: str
    model_version: str
    input_hash: str


@dataclass(frozen=True, slots=True)
class MissionPlan:
    schema_version: str
    plan_id: str
    input_hash: str
    mission_name: str
    target: dict[str, Any]
    start_position_m: tuple[float, float, float]
    routes: tuple[RouteCandidate, ...]
    predictions: tuple[PredictedOutcome, ...]
    recommended_route_id: str
    ranking_explanation: tuple[str, ...]
    assumptions: tuple[PredictionAssumption, ...]
    limitations: tuple[str, ...]
    provenance: tuple[EvidenceReference, ...]
    human_review_status: str
    model_version: str = MODEL_VERSION


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    decision_id: str
    allowed: bool
    action: str
    reasons: tuple[str, ...]
    human_authorized: bool


@dataclass(frozen=True, slots=True)
class MissionEvent:
    event_id: str
    run_id: str
    sequence: int
    event_type: str
    previous_snapshot_id: str | None
    new_snapshot_id: str
    command: str
    safety_decision: SafetyDecision
    assumptions: tuple[str, ...]
    model_version: str
    input_hash: str
    human_authorization_status: str


@dataclass(slots=True)
class MissionRun:
    run_id: str
    plan: MissionPlan
    selected_route_id: str
    scenario_id: str
    authorized_by: str
    authorization_status: str
    initial_snapshot: RoverStateSnapshot
    current_snapshot: RoverStateSnapshot
    events: list[MissionEvent] = field(default_factory=list)


def jsonable(value: object) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(item) for item in value]
    return value
