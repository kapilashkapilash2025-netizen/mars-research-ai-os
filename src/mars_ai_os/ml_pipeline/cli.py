"""Command-line entry point for reproducible dataset preparation."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from mars_ai_os.ml_pipeline.io import read_jsonl, write_artifact
from mars_ai_os.ml_pipeline.pipeline import DatasetPipeline, PipelineConfiguration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="areograph-data-pipeline")
    parser.add_argument("input", help="Source JSONL observations")
    parser.add_argument("output", help="Artifact output directory")
    parser.add_argument(
        "--required-numeric",
        action="append",
        default=[],
        metavar="FIELD",
        help="Required numeric field; repeat for multiple fields",
    )
    parser.add_argument(
        "--range",
        action="append",
        default=[],
        metavar="FIELD:MIN:MAX",
        help="Reviewed numeric range; repeat for multiple fields",
    )
    parser.add_argument("--require-labels", action="store_true")
    parser.add_argument("--maximum-quarantine-fraction", type=float, default=0.25)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ranges = tuple(sorted(_parse_range(value) for value in args.range))
    configuration = PipelineConfiguration(
        required_numeric_fields=tuple(sorted(set(args.required_numeric))),
        allowed_numeric_ranges=ranges,
        require_labels=args.require_labels,
        maximum_quarantine_fraction=args.maximum_quarantine_fraction,
    )
    artifact = DatasetPipeline(configuration).build(read_jsonl(args.input))
    paths = write_artifact(artifact, args.output)
    print(
        json.dumps(
            {
                "dataset_id": artifact.manifest.dataset_id,
                "quality_gate_passed": artifact.manifest.quality.quality_gate_passed,
                "accepted": artifact.manifest.quality.accepted_count,
                "quarantined": artifact.manifest.quality.quarantined_count,
                "artifacts": [str(path) for path in paths],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if artifact.manifest.quality.quality_gate_passed else 2


def _parse_range(value: str) -> tuple[str, float, float]:
    try:
        field, low, high = value.split(":", 2)
        return field, float(low), float(high)
    except ValueError as error:
        raise argparse.ArgumentTypeError("range must be FIELD:MIN:MAX") from error


if __name__ == "__main__":
    raise SystemExit(main())
