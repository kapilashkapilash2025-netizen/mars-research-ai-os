"""Auditable QUBO problem representation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from math import isfinite


@dataclass(frozen=True, slots=True)
class CardinalityConstraint:
    name: str
    variables: tuple[str, ...]
    minimum: int = 0
    maximum: int | None = None
    penalty: float = 1_000.0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Constraint name cannot be empty")
        if not self.variables or len(set(self.variables)) != len(self.variables):
            raise ValueError("Constraint variables must be unique and non-empty")
        maximum = len(self.variables) if self.maximum is None else self.maximum
        if self.minimum < 0 or maximum < self.minimum or maximum > len(self.variables):
            raise ValueError("Invalid cardinality bounds")
        if self.penalty <= 0 or not isfinite(self.penalty):
            raise ValueError("Constraint penalty must be finite and positive")

    def is_satisfied(self, assignment: Mapping[str, int]) -> bool:
        selected = sum(assignment[name] for name in self.variables)
        maximum = len(self.variables) if self.maximum is None else self.maximum
        return self.minimum <= selected <= maximum

    def energy_penalty(self, assignment: Mapping[str, int]) -> float:
        selected = sum(assignment[name] for name in self.variables)
        maximum = len(self.variables) if self.maximum is None else self.maximum
        if selected < self.minimum:
            return self.penalty * (self.minimum - selected) ** 2
        if selected > maximum:
            return self.penalty * (selected - maximum) ** 2
        return 0.0

    def canonical(self) -> dict[str, object]:
        return {
            "name": self.name,
            "variables": list(self.variables),
            "minimum": self.minimum,
            "maximum": self.maximum,
            "penalty": self.penalty,
        }


@dataclass(frozen=True, slots=True)
class QuboProblem:
    name: str
    variables: tuple[str, ...]
    linear: Mapping[str, float] = field(default_factory=dict)
    quadratic: Mapping[tuple[str, str], float] = field(default_factory=dict)
    constraints: tuple[CardinalityConstraint, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Problem name cannot be empty")
        if not self.variables or len(set(self.variables)) != len(self.variables):
            raise ValueError("Problem variables must be unique and non-empty")
        known = set(self.variables)
        if set(self.linear) - known:
            raise ValueError("Linear coefficients reference unknown variables")
        for pair, coefficient in self.quadratic.items():
            if len(pair) != 2 or pair[0] == pair[1] or not set(pair) <= known:
                raise ValueError(f"Invalid quadratic pair: {pair}")
            if not isfinite(coefficient):
                raise ValueError("Quadratic coefficients must be finite")
        if any(not isfinite(value) for value in self.linear.values()):
            raise ValueError("Linear coefficients must be finite")
        for constraint in self.constraints:
            if not set(constraint.variables) <= known:
                raise ValueError(f"Constraint references unknown variables: {constraint.name}")

    def objective_energy(self, assignment: Mapping[str, int]) -> float:
        self._validate_assignment(assignment)
        energy = sum(self.linear.get(name, 0.0) * assignment[name] for name in self.variables)
        energy += sum(
            coefficient * assignment[left] * assignment[right]
            for (left, right), coefficient in self.quadratic.items()
        )
        return energy

    def energy(self, assignment: Mapping[str, int]) -> float:
        return self.objective_energy(assignment) + sum(
            constraint.energy_penalty(assignment) for constraint in self.constraints
        )

    def is_feasible(self, assignment: Mapping[str, int]) -> bool:
        self._validate_assignment(assignment)
        return all(constraint.is_satisfied(assignment) for constraint in self.constraints)

    def fingerprint(self) -> str:
        payload = {
            "name": self.name,
            "variables": list(self.variables),
            "linear": {key: self.linear[key] for key in sorted(self.linear)},
            "quadratic": [
                [left, right, coefficient]
                for (left, right), coefficient in sorted(self.quadratic.items())
            ],
            "constraints": [constraint.canonical() for constraint in self.constraints],
            "metadata": {key: self.metadata[key] for key in sorted(self.metadata)},
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return sha256(encoded).hexdigest()

    def _validate_assignment(self, assignment: Mapping[str, int]) -> None:
        if set(assignment) != set(self.variables):
            raise ValueError("Assignment must contain every problem variable exactly once")
        if any(value not in (0, 1) for value in assignment.values()):
            raise ValueError("QUBO assignments must be binary")
