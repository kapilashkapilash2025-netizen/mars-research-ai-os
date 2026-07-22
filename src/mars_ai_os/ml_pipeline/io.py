"""Safe local JSONL input and atomic dataset artifact output."""

from __future__ import annotations

import json
from pathlib import Path

from mars_ai_os.ml_pipeline.contracts import DatasetArtifact


def read_jsonl(path: str | Path, *, maximum_records: int = 100_000) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with Path(path).open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            if len(records) >= maximum_records:
                raise ValueError(f"input exceeds {maximum_records} records")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number} must be a JSON object")
            records.append(value)
    return records


def write_artifact(artifact: DatasetArtifact, directory: str | Path) -> tuple[Path, Path, Path]:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    manifest = target / "manifest.json"
    examples = target / "examples.jsonl"
    quarantine = target / "quarantine.jsonl"
    _atomic_text(manifest, json.dumps(artifact.to_dict()["manifest"], indent=2, sort_keys=True))
    _atomic_text(
        examples,
        "\n".join(json.dumps(item, sort_keys=True) for item in artifact.to_dict()["examples"])
        + ("\n" if artifact.examples else ""),
    )
    _atomic_text(
        quarantine,
        "\n".join(json.dumps(item, sort_keys=True) for item in artifact.to_dict()["quarantine"])
        + ("\n" if artifact.quarantine else ""),
    )
    return manifest, examples, quarantine


def _atomic_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
