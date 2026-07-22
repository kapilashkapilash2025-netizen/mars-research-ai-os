"""Explicit adapters from verified domain artifacts into raw pipeline observations."""

from __future__ import annotations

from typing import Any

from mars_ai_os.digital_twin.provenance import canonical_json
from mars_ai_os.ml_pipeline.contracts import digest


def mission_report_observation(report: dict[str, Any]) -> dict[str, Any]:
    """Map one verified mission audit report to an unlabeled simulated observation."""
    required = (
        "report_content_hash",
        "mission_plan",
        "current_snapshot",
        "selected_route_id",
        "scenario_id",
    )
    missing = tuple(field for field in required if field not in report)
    if missing:
        raise ValueError(f"mission report missing fields: {', '.join(missing)}")
    report_without_hash = {
        key: value for key, value in report.items() if key != "report_content_hash"
    }
    if digest(report_without_hash) != report["report_content_hash"]:
        raise ValueError("mission report content hash does not match payload")
    plan = report["mission_plan"]
    snapshot = report["current_snapshot"]
    if not isinstance(plan, dict) or not isinstance(snapshot, dict):
        raise TypeError("mission plan and snapshot must be objects")
    run_identity = digest(
        (
            plan.get("plan_id"),
            report["selected_route_id"],
            report["scenario_id"],
        )
    )
    return {
        "observation_id": f"mission-report:{report['report_content_hash'][:24]}",
        "entity_id": f"simulated-run:{run_identity[:24]}",
        "mission_id": str(plan.get("plan_id", "unknown")),
        "observed_at_s": float(snapshot["elapsed_s"]),
        "numeric_values": {
            "battery_reserve_percent": float(snapshot["battery_reserve_percent"]),
            "distance_travelled_m": float(snapshot["distance_travelled_m"]),
            "elapsed_s": float(snapshot["elapsed_s"]),
            "peak_temperature_c": float(snapshot["peak_temperature_c"]),
            "peak_wheel_slip": float(snapshot["peak_wheel_slip"]),
        },
        "categorical_values": {
            "route_id": str(report["selected_route_id"]),
            "scenario_id": str(report["scenario_id"]),
            "status": str(snapshot["status"]),
        },
        "label": None,
        "label_review_status": "unreviewed",
        "provenance": {
            "source_id": str(report["report_content_hash"]),
            "publisher": "Areograph Labs",
            "locator": f"urn:areograph:mission-report:{report['report_content_hash']}",
            "content_sha256": digest(canonical_json(report)),
            "source_classification": "simulated",
            "license_id": "research-internal-v1",
            "processing_lineage": ["mission-audit-report/1"],
        },
    }
