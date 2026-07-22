"""Deterministic ETL, feature engineering, leakage-safe splitting, and quality gates."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from typing import Any

from mars_ai_os.digital_twin.provenance import canonical_json
from mars_ai_os.ml_pipeline.contracts import (
    DATASET_SCHEMA_VERSION,
    PIPELINE_VERSION,
    DataProvenance,
    DatasetArtifact,
    DatasetManifest,
    FeatureValue,
    QualityReport,
    QuarantineRecord,
    RawObservation,
    TrainingExample,
    add_lineage,
    digest,
    stable_id,
)

ASSUMPTIONS = (
    "Input numeric values use the units declared by the producing source contract.",
    "Entity-level splitting prevents the same entity from crossing dataset partitions.",
    "Missing optional values remain absent and are not statistically imputed in version 1.",
)
LIMITATIONS = (
    "This pipeline prepares datasets; it does not train, select, or deploy a model.",
    "Categorical values are retained for audit but are not encoded as numeric features "
    "in version 1.",
    "Quality gates detect structural problems, not scientific truth or hardware calibration.",
    "Synthetic and simulated records remain explicitly classified and must not be presented "
    "as observations.",
)


@dataclass(frozen=True, slots=True)
class PipelineConfiguration:
    required_numeric_fields: tuple[str, ...]
    allowed_numeric_ranges: tuple[tuple[str, float, float], ...] = ()
    train_percent: int = 70
    validation_percent: int = 15
    test_percent: int = 15
    minimum_accepted_records: int = 1
    maximum_quarantine_fraction: float = 0.25
    require_labels: bool = False
    split_salt: str = "areograph-split-v1"

    def __post_init__(self) -> None:
        if tuple(sorted(set(self.required_numeric_fields))) != self.required_numeric_fields:
            raise ValueError("required numeric fields must be unique and sorted")
        if self.train_percent + self.validation_percent + self.test_percent != 100:
            raise ValueError("dataset split percentages must total 100")
        if min(self.train_percent, self.validation_percent, self.test_percent) < 0:
            raise ValueError("dataset split percentages cannot be negative")
        if self.minimum_accepted_records < 1:
            raise ValueError("minimum accepted records must be positive")
        if not 0 <= self.maximum_quarantine_fraction <= 1:
            raise ValueError("maximum quarantine fraction must be between zero and one")
        names = tuple(item[0] for item in self.allowed_numeric_ranges)
        if names != tuple(sorted(set(names))):
            raise ValueError("numeric ranges must have unique, sorted field names")
        if any(low > high for _, low, high in self.allowed_numeric_ranges):
            raise ValueError("numeric range minimum cannot exceed maximum")


class DatasetPipeline:
    def __init__(self, configuration: PipelineConfiguration) -> None:
        self.configuration = configuration

    def build(self, raw_records: list[dict[str, Any]]) -> DatasetArtifact:
        if not isinstance(raw_records, list):
            raise TypeError("pipeline input must be a list of JSON objects")
        normalized_input_hash = self._raw_digest(raw_records)
        observations: list[RawObservation] = []
        quarantined: list[QuarantineRecord] = []
        seen: set[str] = set()
        duplicate_count = 0
        for index, record in enumerate(raw_records):
            try:
                observation = self._parse(record)
                identity = digest(observation)
                if identity in seen:
                    duplicate_count += 1
                    quarantined.append(
                        self._quarantine(index, "duplicate", "Exact canonical duplicate", record)
                    )
                    continue
                seen.add(identity)
                self._validate_scientific_fields(observation)
                observations.append(observation)
            except (KeyError, TypeError, ValueError) as error:
                quarantined.append(self._quarantine(index, "validation_error", str(error), record))

        observations.sort(
            key=lambda item: (item.entity_id, item.observed_at_s, item.observation_id)
        )
        examples = tuple(self._transform(item) for item in observations)
        feature_names = tuple(
            sorted({feature.name for item in examples for feature in item.features})
        )
        label_names = tuple(sorted({item.label for item in examples if item.label is not None}))
        split_counts = Counter(item.split for item in examples)
        class_counts = Counter(item.source_classification for item in examples)
        warnings: list[str] = []
        if not examples:
            warnings.append("No records passed validation.")
        if examples and not label_names:
            warnings.append(
                "Dataset contains no human-reviewed labels; supervised training is blocked."
            )
        quarantine_fraction = len(quarantined) / max(len(raw_records), 1)
        passed = (
            len(examples) >= self.configuration.minimum_accepted_records
            and quarantine_fraction <= self.configuration.maximum_quarantine_fraction
            and (not self.configuration.require_labels or bool(label_names))
        )
        quality = QualityReport(
            len(raw_records),
            len(examples),
            len(quarantined),
            duplicate_count,
            sum(item.label is not None for item in examples),
            len(feature_names),
            tuple(sorted(split_counts.items())),
            tuple(sorted(class_counts.items())),
            passed,
            tuple(warnings),
        )
        config_hash = digest(self.configuration)
        example_hash = digest(examples)
        quarantine_hash = digest(quarantined)
        manifest_seed = {
            "schema": DATASET_SCHEMA_VERSION,
            "pipeline": PIPELINE_VERSION,
            "configuration_hash": config_hash,
            "input_content_hash": normalized_input_hash,
            "examples_content_hash": example_hash,
            "quarantine_content_hash": quarantine_hash,
        }
        manifest = DatasetManifest(
            DATASET_SCHEMA_VERSION,
            stable_id("dataset", manifest_seed),
            PIPELINE_VERSION,
            config_hash,
            normalized_input_hash,
            example_hash,
            quarantine_hash,
            feature_names,
            label_names,
            quality,
            ASSUMPTIONS,
            LIMITATIONS,
            "training_authorized"
            if passed and label_names
            else "dataset_accepted"
            if passed
            else "blocked",
        )
        return DatasetArtifact(manifest, examples, tuple(quarantined))

    def _parse(self, record: dict[str, Any]) -> RawObservation:
        if not isinstance(record, dict):
            raise TypeError("record must be a JSON object")
        provenance_input = record["provenance"]
        if not isinstance(provenance_input, dict):
            raise TypeError("provenance must be an object")
        provenance = DataProvenance(
            source_id=str(provenance_input["source_id"]),
            publisher=str(provenance_input["publisher"]),
            locator=str(provenance_input["locator"]),
            content_sha256=str(provenance_input["content_sha256"]),
            source_classification=str(provenance_input["source_classification"]),
            license_id=str(provenance_input["license_id"]),
            processing_lineage=tuple(
                str(item) for item in provenance_input.get("processing_lineage", ())
            ),
        )
        numeric = self._pairs(record.get("numeric_values", {}), float)
        categorical = self._pairs(record.get("categorical_values", {}), str)
        parsed = RawObservation(
            str(record["observation_id"]),
            str(record["entity_id"]),
            str(record.get("mission_id", "unassigned")),
            float(record["observed_at_s"]),
            numeric,
            categorical,
            str(record["label"]) if record.get("label") is not None else None,
            str(record.get("label_review_status", "unreviewed")),
            add_lineage(provenance, f"validated:{PIPELINE_VERSION}"),
        )
        return parsed

    def _pairs(
        self, value: object, converter: type[float] | type[str]
    ) -> tuple[tuple[str, Any], ...]:
        if not isinstance(value, dict):
            raise TypeError("feature values must be JSON objects")
        return tuple(sorted((str(name), converter(item)) for name, item in value.items()))

    def _validate_scientific_fields(self, item: RawObservation) -> None:
        values = dict(item.numeric_values)
        missing = tuple(
            field for field in self.configuration.required_numeric_fields if field not in values
        )
        if missing:
            raise ValueError(f"missing required numeric fields: {', '.join(missing)}")
        if any(not isfinite(value) for value in values.values()):
            raise ValueError("numeric values must be finite")
        for name, low, high in self.configuration.allowed_numeric_ranges:
            if name in values and not low <= values[name] <= high:
                raise ValueError(f"{name} outside reviewed range [{low}, {high}]")

    def _transform(self, item: RawObservation) -> TrainingExample:
        features = tuple(
            FeatureValue(name, round(value, 9), (name,), "identity/1")
            for name, value in item.numeric_values
        )
        split = self._split(item.entity_id)
        input_hash = digest(item)
        seed = {"observation": item.observation_id, "input_hash": input_hash, "split": split}
        return TrainingExample(
            stable_id("example", seed),
            item.observation_id,
            item.entity_id,
            item.mission_id,
            split,
            features,
            item.label,
            item.label_review_status,
            item.provenance.source_classification,
            digest(item.provenance),
            input_hash,
        )

    def _split(self, entity_id: str) -> str:
        bucket = int(digest((self.configuration.split_salt, entity_id))[:8], 16) % 100
        if bucket < self.configuration.train_percent:
            return "train"
        if bucket < self.configuration.train_percent + self.configuration.validation_percent:
            return "validation"
        return "test"

    def _quarantine(self, index: int, code: str, detail: str, record: object) -> QuarantineRecord:
        input_hash = self._raw_digest(record)
        return QuarantineRecord(
            stable_id("quarantine", (index, code, input_hash)), index, code, detail, input_hash
        )

    def _raw_digest(self, value: object) -> str:
        try:
            return digest(value)
        except (TypeError, ValueError):
            return sha256(repr(value).encode("utf-8")).hexdigest()


def artifact_json(artifact: DatasetArtifact) -> str:
    return canonical_json(artifact.to_dict())
