"""Deterministic state comparison for scientific audit and debugging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mars_ai_os.digital_twin.models import TwinSnapshot
from mars_ai_os.digital_twin.provenance import canonicalize


@dataclass(frozen=True, slots=True)
class StateDifference:
    path: str
    before: object
    after: object
    delta: float | None
    description: str


def compare_snapshots(before: TwinSnapshot, after: TwinSnapshot) -> tuple[StateDifference, ...]:
    before_flat = _flatten(canonicalize(before.state))
    after_flat = _flatten(canonicalize(after.state))
    differences = []
    for path in sorted(set(before_flat) | set(after_flat)):
        old = before_flat.get(path)
        new = after_flat.get(path)
        if old == new:
            continue
        delta = _numeric_delta(old, new)
        differences.append(
            StateDifference(path, old, new, delta, _describe(path, old, new, delta))
        )
    return tuple(differences)


def _flatten(value: Any, prefix: str = "") -> dict[str, object]:
    if isinstance(value, dict):
        result = {}
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else key
            result.update(_flatten(value[key], path))
        return result
    if isinstance(value, list):
        identifier = _identifier_key(value)
        result = {}
        for index, item in enumerate(value):
            label = item[identifier] if identifier and isinstance(item, dict) else index
            path = f"{prefix}[{label}]"
            result.update(_flatten(item, path))
        return result
    return {prefix: value}


def _identifier_key(values: list[Any]) -> str | None:
    if not values or not all(isinstance(item, dict) for item in values):
        return None
    for candidate in ("motor_id", "name"):
        if all(candidate in item for item in values):
            return candidate
    return None


def _numeric_delta(before: object, after: object) -> float | None:
    if (
        isinstance(before, (int, float))
        and not isinstance(before, bool)
        and isinstance(after, (int, float))
        and not isinstance(after, bool)
    ):
        return float(after - before)
    return None


def _describe(path: str, before: object, after: object, delta: float | None) -> str:
    if delta is not None:
        direction = "increased" if delta > 0 else "decreased"
        return f"{path} {direction} from {before} to {after} (delta {delta:+g})"
    return f"{path} changed from {before!r} to {after!r}"

