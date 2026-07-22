import json
from hashlib import sha256

import pytest

from mars_ai_os.ml_pipeline.adapters import mission_report_observation
from mars_ai_os.ml_pipeline.cli import main
from mars_ai_os.ml_pipeline.io import read_jsonl, write_artifact
from mars_ai_os.ml_pipeline.pipeline import DatasetPipeline, PipelineConfiguration


def record(
    observation_id: str,
    entity_id: str,
    *,
    battery: float = 80.0,
    slip: float = 0.1,
    classification: str = "simulated",
    label: str | None = None,
    review: str = "unreviewed",
):
    content = f"{observation_id}:{entity_id}".encode()
    return {
        "observation_id": observation_id,
        "entity_id": entity_id,
        "mission_id": "mission-1",
        "observed_at_s": 12.0,
        "numeric_values": {"battery_percent": battery, "wheel_slip": slip},
        "categorical_values": {"mode": "simulation"},
        "label": label,
        "label_review_status": review,
        "provenance": {
            "source_id": f"source-{entity_id}",
            "publisher": "Areograph Labs",
            "locator": f"urn:areograph:{observation_id}",
            "content_sha256": sha256(content).hexdigest(),
            "source_classification": classification,
            "license_id": "research-internal-v1",
        },
    }


CONFIG = PipelineConfiguration(
    required_numeric_fields=("battery_percent", "wheel_slip"),
    allowed_numeric_ranges=(("battery_percent", 0, 100), ("wheel_slip", 0, 1)),
)


def test_identical_inputs_produce_identical_dataset_and_examples():
    records = [record("obs-1", "rover-a"), record("obs-2", "rover-b")]
    first = DatasetPipeline(CONFIG).build(records)
    second = DatasetPipeline(CONFIG).build(records)
    assert first == second
    assert first.manifest.dataset_id == second.manifest.dataset_id
    assert first.manifest.examples_content_hash == second.manifest.examples_content_hash


def test_entity_split_prevents_cross_partition_leakage():
    records = [record(f"obs-{index}", "same-rover") for index in range(5)]
    artifact = DatasetPipeline(CONFIG).build(records)
    assert len({item.split for item in artifact.examples}) == 1


def test_invalid_ranges_and_duplicates_are_quarantined():
    valid = record("obs-1", "rover-a")
    invalid = record("obs-2", "rover-b", battery=120)
    artifact = DatasetPipeline(CONFIG).build([valid, valid, invalid])
    assert artifact.manifest.quality.accepted_count == 1
    assert artifact.manifest.quality.quarantined_count == 2
    assert artifact.manifest.quality.duplicate_count == 1
    assert {item.reason_code for item in artifact.quarantine} == {"duplicate", "validation_error"}


def test_unreviewed_labels_are_rejected_and_label_gate_blocks():
    config = PipelineConfiguration(
        required_numeric_fields=("battery_percent", "wheel_slip"),
        require_labels=True,
        maximum_quarantine_fraction=1,
    )
    artifact = DatasetPipeline(config).build([record("obs-1", "rover-a", label="safe")])
    assert artifact.manifest.quality.quality_gate_passed is False
    assert artifact.manifest.human_review_status == "blocked"


def test_human_reviewed_labels_can_pass_training_gate():
    config = PipelineConfiguration(
        required_numeric_fields=("battery_percent", "wheel_slip"),
        require_labels=True,
    )
    artifact = DatasetPipeline(config).build(
        [record("obs-1", "rover-a", label="safe", review="human-reviewed")]
    )
    assert artifact.manifest.quality.quality_gate_passed is True
    assert artifact.manifest.label_schema == ("safe",)
    assert artifact.manifest.human_review_status == "training_authorized"


def test_source_classification_is_preserved():
    artifact = DatasetPipeline(CONFIG).build(
        [record("obs-1", "rover-a", classification="source-derived")]
    )
    assert artifact.examples[0].source_classification == "source-derived"
    assert artifact.manifest.quality.classification_counts == (("source-derived", 1),)


def test_non_finite_values_are_quarantined():
    artifact = DatasetPipeline(CONFIG).build([record("obs-1", "rover-a", slip=float("nan"))])
    assert not artifact.examples
    assert artifact.quarantine[0].reason_code == "validation_error"


def test_atomic_artifact_output_and_jsonl_input(tmp_path):
    source = tmp_path / "input.jsonl"
    source.write_text(json.dumps(record("obs-1", "rover-a")) + "\n", encoding="utf-8")
    artifact = DatasetPipeline(CONFIG).build(read_jsonl(source))
    manifest, examples, quarantine = write_artifact(artifact, tmp_path / "output")
    assert json.loads(manifest.read_text(encoding="utf-8"))["dataset_id"]
    assert len(examples.read_text(encoding="utf-8").splitlines()) == 1
    assert quarantine.read_text(encoding="utf-8") == ""


def test_cli_writes_training_ready_artifact(tmp_path, capsys):
    source = tmp_path / "input.jsonl"
    source.write_text(json.dumps(record("obs-1", "rover-a")) + "\n", encoding="utf-8")
    code = main(
        [
            str(source),
            str(tmp_path / "dataset"),
            "--required-numeric",
            "battery_percent",
            "--required-numeric",
            "wheel_slip",
            "--range",
            "battery_percent:0:100",
            "--range",
            "wheel_slip:0:1",
        ]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out)["quality_gate_passed"] is True


def test_configuration_rejects_invalid_splits():
    with pytest.raises(ValueError, match="total 100"):
        PipelineConfiguration((), train_percent=80, validation_percent=15, test_percent=15)


def test_verified_mission_report_adapter_preserves_simulated_classification():
    from mars_ai_os.mission.orchestrator import MissionOrchestrator

    mission = MissionOrchestrator()
    plan = mission.create_plan({"target": {"id": "delta", "distance_m": 420}})
    run = mission.create_run(
        {
            "plan_id": plan.plan_id,
            "selected_route_id": "safe",
            "human_authorized": True,
            "authorized_by": "reviewer",
        }
    )
    report = mission.report(run.run_id)
    adapted = mission_report_observation(report)
    artifact = DatasetPipeline(
        PipelineConfiguration(
            required_numeric_fields=(
                "battery_reserve_percent",
                "distance_travelled_m",
                "elapsed_s",
                "peak_temperature_c",
                "peak_wheel_slip",
            )
        )
    ).build([adapted])
    assert artifact.manifest.quality.quality_gate_passed is True
    assert artifact.examples[0].source_classification == "simulated"
    assert artifact.examples[0].label is None
