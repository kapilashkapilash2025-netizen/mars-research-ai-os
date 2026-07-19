"""Reference adapter for selecting planetary mission activities."""

from __future__ import annotations

from dataclasses import dataclass

from mars_ai_os.intelligence.qubo import CardinalityConstraint, QuboProblem


@dataclass(frozen=True, slots=True)
class MissionCandidate:
    candidate_id: str
    science_value: float
    energy_cost_wh: float
    risk: float
    communication_mb: float


@dataclass(frozen=True, slots=True)
class MissionWeights:
    science: float = 1.0
    energy: float = 0.02
    risk: float = 2.0
    communication: float = 0.01


def build_mission_selection_problem(
    candidates: tuple[MissionCandidate, ...],
    *,
    maximum_selected: int,
    weights: MissionWeights | None = None,
    conflicts: tuple[tuple[str, str], ...] = (),
) -> QuboProblem:
    """Build an advisory QUBO; lower energy represents a preferred activity set."""

    if not candidates:
        raise ValueError("At least one mission candidate is required")
    weights = weights or MissionWeights()
    variables = tuple(candidate.candidate_id for candidate in candidates)
    if len(set(variables)) != len(variables):
        raise ValueError("Mission candidate IDs must be unique")
    linear = {
        candidate.candidate_id: (
            -weights.science * candidate.science_value
            + weights.energy * candidate.energy_cost_wh
            + weights.risk * candidate.risk
            + weights.communication * candidate.communication_mb
        )
        for candidate in candidates
    }
    quadratic = {pair: 10_000.0 for pair in conflicts}
    return QuboProblem(
        name="planetary-mission-selection",
        variables=variables,
        linear=linear,
        quadratic=quadratic,
        constraints=(
            CardinalityConstraint(
                name="activity-count",
                variables=variables,
                minimum=1,
                maximum=maximum_selected,
            ),
        ),
        metadata={"adapter": "mission-selection/1", "result_authority": "advisory"},
    )

