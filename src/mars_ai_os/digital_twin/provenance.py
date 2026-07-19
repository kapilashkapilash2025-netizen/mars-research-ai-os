"""Canonical hashing and provenance records for reproducible twin state."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from hashlib import sha256
from typing import Any

from mars_ai_os import __version__
from mars_ai_os.intelligence.annealing import ALGORITHM_ID


def canonicalize(value: Any) -> Any:
    """Convert supported scientific records into deterministic JSON values."""

    if is_dataclass(value):
        return {item.name: canonicalize(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (tuple, list)):
        return [canonicalize(item) for item in value]
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("Non-finite values cannot be recorded in canonical state")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"Unsupported canonical value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(canonicalize(value), sort_keys=True, separators=(",", ":"))


def configuration_hash(configuration: Any) -> str:
    return sha256(canonical_json(configuration).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    configuration_hash: str
    software_version: str
    optimizer_version: str
    seed: int
    assumptions: tuple[str, ...]
    author: str
    recorded_at_s: float

    def __post_init__(self) -> None:
        if len(self.configuration_hash) != 64:
            raise ValueError("configuration_hash must be a SHA-256 hex digest")
        if not self.author.strip():
            raise ValueError("Provenance author cannot be empty")
        if tuple(sorted(set(self.assumptions))) != self.assumptions:
            raise ValueError("Assumptions must be unique and sorted")


def create_provenance(
    *,
    configuration: Any,
    seed: int,
    assumptions: tuple[str, ...],
    author: str,
    recorded_at_s: float,
    software_version: str = __version__,
    optimizer_version: str = ALGORITHM_ID,
) -> ProvenanceRecord:
    return ProvenanceRecord(
        configuration_hash=configuration_hash(configuration),
        software_version=software_version,
        optimizer_version=optimizer_version,
        seed=seed,
        assumptions=tuple(sorted(set(assumptions))),
        author=author,
        recorded_at_s=recorded_at_s,
    )
