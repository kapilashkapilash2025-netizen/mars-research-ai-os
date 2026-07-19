"""Seeded classical simulated annealing with reproducible trace records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp
from random import Random

from mars_ai_os.intelligence.qubo import QuboProblem

ALGORITHM_ID = "classical-simulated-annealing/1"


@dataclass(frozen=True, slots=True)
class AnnealingConfig:
    initial_temperature: float = 10.0
    final_temperature: float = 0.01
    sweeps: int = 200
    restarts: int = 8
    seed: int = 13

    def __post_init__(self) -> None:
        if self.initial_temperature <= 0 or self.final_temperature <= 0:
            raise ValueError("Temperatures must be greater than zero")
        if self.final_temperature >= self.initial_temperature:
            raise ValueError("Final temperature must be lower than initial temperature")
        if self.sweeps <= 0 or self.restarts <= 0:
            raise ValueError("Sweeps and restarts must be greater than zero")


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    algorithm: str
    problem_fingerprint: str
    config: dict[str, int | float]
    assignment: dict[str, int]
    objective_energy: float
    feasible: bool
    evaluations: int
    accepted_moves: int
    best_energy_history: tuple[float, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class SimulatedAnnealingOptimizer:
    def solve(
        self, problem: QuboProblem, config: AnnealingConfig | None = None
    ) -> OptimizationResult:
        config = config or AnnealingConfig()
        random = Random(config.seed)
        best_assignment: dict[str, int] | None = None
        best_energy = float("inf")
        evaluations = 0
        accepted_moves = 0
        history: list[float] = []

        for _ in range(config.restarts):
            current = self._initial_feasible_assignment(problem, random)
            current_energy = problem.energy(current)
            evaluations += 1
            if current_energy < best_energy:
                best_assignment = current.copy()
                best_energy = current_energy

            for sweep in range(config.sweeps):
                fraction = sweep / max(1, config.sweeps - 1)
                temperature = config.initial_temperature * (
                    config.final_temperature / config.initial_temperature
                ) ** fraction
                for variable in random.sample(list(problem.variables), len(problem.variables)):
                    candidate = current.copy()
                    candidate[variable] = 1 - candidate[variable]
                    candidate_energy = problem.energy(candidate)
                    evaluations += 1
                    delta = candidate_energy - current_energy
                    if delta <= 0 or random.random() < exp(-delta / temperature):
                        current = candidate
                        current_energy = candidate_energy
                        accepted_moves += 1
                    if problem.is_feasible(current) and current_energy < best_energy:
                        best_assignment = current.copy()
                        best_energy = current_energy
                history.append(best_energy)

        if best_assignment is None:
            raise RuntimeError("No feasible assignment found")
        return OptimizationResult(
            algorithm=ALGORITHM_ID,
            problem_fingerprint=problem.fingerprint(),
            config=asdict(config),
            assignment=best_assignment,
            objective_energy=problem.objective_energy(best_assignment),
            feasible=problem.is_feasible(best_assignment),
            evaluations=evaluations,
            accepted_moves=accepted_moves,
            best_energy_history=tuple(history),
        )

    @staticmethod
    def _initial_feasible_assignment(problem: QuboProblem, random: Random) -> dict[str, int]:
        for _ in range(1_000):
            assignment = {name: random.randint(0, 1) for name in problem.variables}
            if problem.is_feasible(assignment):
                return assignment
        raise RuntimeError("Unable to sample a feasible initial assignment")

