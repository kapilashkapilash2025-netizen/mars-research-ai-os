from __future__ import annotations

from mars_ai_os.intelligence import (
    AnnealingConfig,
    CardinalityConstraint,
    QuboProblem,
    SimulatedAnnealingOptimizer,
)
from mars_ai_os.intelligence.planetary import (
    MissionCandidate,
    build_mission_selection_problem,
)


def test_qubo_energy_includes_linear_quadratic_and_constraint_terms() -> None:
    problem = QuboProblem(
        name="energy-test",
        variables=("a", "b"),
        linear={"a": -2.0, "b": 1.0},
        quadratic={("a", "b"): 3.0},
        constraints=(CardinalityConstraint("choose-one", ("a", "b"), 1, 1, 100.0),),
    )

    assert problem.energy({"a": 1, "b": 0}) == -2.0
    assert problem.energy({"a": 1, "b": 1}) == 102.0


def test_solver_is_deterministic_and_traceable() -> None:
    problem = QuboProblem(
        name="deterministic-test",
        variables=("a", "b", "c"),
        linear={"a": -3.0, "b": -2.0, "c": 1.0},
        constraints=(CardinalityConstraint("choose", ("a", "b", "c"), 1, 2),),
    )
    config = AnnealingConfig(sweeps=30, restarts=3, seed=42)
    optimizer = SimulatedAnnealingOptimizer()

    first = optimizer.solve(problem, config)
    second = optimizer.solve(problem, config)

    assert first == second
    assert first.feasible is True
    assert first.problem_fingerprint == problem.fingerprint()
    assert first.assignment == {"a": 1, "b": 1, "c": 0}


def test_mission_adapter_prefers_science_within_activity_limit() -> None:
    problem = build_mission_selection_problem(
        (
            MissionCandidate("high_science", 10.0, 20.0, 0.2, 5.0),
            MissionCandidate("low_science", 2.0, 20.0, 0.2, 5.0),
            MissionCandidate("high_risk", 12.0, 20.0, 9.0, 5.0),
        ),
        maximum_selected=1,
    )

    result = SimulatedAnnealingOptimizer().solve(
        problem, AnnealingConfig(sweeps=40, restarts=4, seed=7)
    )

    assert result.assignment["high_science"] == 1
    assert sum(result.assignment.values()) == 1


def test_problem_fingerprint_changes_with_scientific_assumptions() -> None:
    first = QuboProblem("trace", ("a",), linear={"a": 1.0}, metadata={"model": "v1"})
    second = QuboProblem("trace", ("a",), linear={"a": 1.0}, metadata={"model": "v2"})

    assert first.fingerprint() != second.fingerprint()
