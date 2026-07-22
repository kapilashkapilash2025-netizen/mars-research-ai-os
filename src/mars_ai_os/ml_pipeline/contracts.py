"""Immutable, versioned contracts for training-ready scientific datasets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from typing import Any

from mars_ai_os.digital_twin.provenance import canonical_json

DATASET_SCHEMA_VERSION = "areograph.ml-dataset.v1"
PIPELINE_VERSION = "areograph-ml-pipeline/1.0"
VALID_CLASSIFICATIONS = ("source-derived", "synthetic", "inferred", "simulated")


def digest(value: object) -> str:
    return sha256(canonical_json(value).encode()).hexdigest()


def stable_id(prefix: str, value: object) -> str:
    return f"{prefix}_{digest(value)[:24]}"


@dataclass(frozen=True, slots=True)
class DataProvenance:
    source_id: str
    publisher: str
    locator: str
    content_sha256: str
    source_classification: str
    license_id: str
    processing_lineage: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.publisher.strip() or not self.locator.strip():
            raise ValueError("source identity, publisher, and locator are required")
        if len(self.content_sha256) != 64:
            raise ValueError("content_sha256 must be a SHA-256 digest")
        if self.source_classification not in VALID_CLASSIFICATIONS:
            raise ValueError("unsupported source classification")
        if not self.license_id.strip():
            raise ValueError("license identity is required")


@dataclass(frozen=True, slots=True)
class RawObservation:
    observation_id: str
    entity_id: str
    mission_id: str
    observed_at_s: float
    numeric_values: tuple[tuple[str, float], ...]
    categorical_values: tuple[tuple[str, str], ...]
    label: str | None
    label_review_status: str
    provenance: DataProvenance
    schema_version: str = DATASET_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.observation_id.strip() or not self.entity_id.strip():
            raise ValueError("observation and entity identities are required")
        if self.observed_at_s < 0:
            raise ValueError("observed_at_s cannot be negative")
        _require_unique_sorted(self.numeric_values, "numeric values")
        _require_unique_sorted(self.categorical_values, "categorical values")
        if self.label is not None and self.label_review_status != "human-reviewed":
            raise ValueError("training labels require human-reviewed status")


@dataclass(frozen=True, slots=True)
class FeatureValue:
    name: str
    value: float
    source_fields: tuple[str, ...]
    transformation: str


@dataclass(frozen=True, slots=True)
class TrainingExample:
    example_id: str
    observation_id: str
    entity_id: str
    mission_id: str
    split: str
    features: tuple[FeatureValue, ...]
    label: str | None
    label_review_status: str
    source_classification: str
    provenance_hash: str
    input_hash: str


@dataclass(frozen=True, slots=True)
class QuarantineRecord:
    quarantine_id: str
    input_index: int
    reason_code: str
    detail: str
    input_hash: str


@dataclass(frozen=True, slots=True)
class QualityReport:
    input_count: int
    accepted_count: int
    quarantined_count: int
    duplicate_count: int
    labeled_count: int
    feature_count: int
    split_counts: tuple[tuple[str, int], ...]
    classification_counts: tuple[tuple[str, int], ...]
    quality_gate_passed: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    schema_version: str
    dataset_id: str
    pipeline_version: str
    configuration_hash: str
    input_content_hash: str
    examples_content_hash: str
    quarantine_content_hash: str
    feature_schema: tuple[str, ...]
    label_schema: tuple[str, ...]
    quality: QualityReport
    assumptions: tuple[str, ...]
    limitations: tuple[str, ...]
    human_review_status: str


@dataclass(frozen=True, slots=True)
class DatasetArtifact:
    manifest: DatasetManifest
    examples: tuple[TrainingExample, ...]
    quarantine: tuple[QuarantineRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def add_lineage(provenance: DataProvenance, step: str) -> DataProvenance:
    return replace(provenance, processing_lineage=provenance.processing_lineage + (step,))


def _require_unique_sorted(values: tuple[tuple[str, object], ...], label: str) -> None:
    names = tuple(item[0] for item in values)
    if names != tuple(sorted(set(names))):
        raise ValueError(f"{label} must have unique names in sorted order")
