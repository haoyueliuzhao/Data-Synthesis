from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol
from finraw.validation import quality_report


class QualityGateError(RuntimeError):
    pass


def enforce_quality_gates(db: DBProtocol, config: dict[str, Any]) -> dict[str, Any]:
    report = quality_report(db)
    gates = config.get("quality_gates", {})
    failures: list[str] = []

    max_failed_objects = int(gates.get("max_failed_objects", 0))
    max_warning_objects = int(gates.get("max_warning_objects", 10_000_000))
    if report["failed_object_count"] > max_failed_objects:
        failures.append(f"failed_object_count={report['failed_object_count']} > {max_failed_objects}")
    if report["warning_object_count"] > max_warning_objects:
        failures.append(f"warning_object_count={report['warning_object_count']} > {max_warning_objects}")

    min_objects = gates.get("min_raw_objects_by_source", {})
    counts = report.get("object_count_by_source", {})
    for source_id, minimum in min_objects.items():
        actual = int(counts.get(source_id, 0))
        if actual < int(minimum):
            failures.append(f"{source_id} raw_objects={actual} < {minimum}")

    min_records = gates.get("min_raw_records_by_type", {})
    record_counts = {(row["source_id"], row["record_type"]): row["count"] for row in report.get("record_type_counts", [])}
    for key, minimum in min_records.items():
        source_id, record_type = key.split(":", 1)
        actual = int(record_counts.get((source_id, record_type), 0))
        if actual < int(minimum):
            failures.append(f"{source_id}:{record_type} raw_records={actual} < {minimum}")

    storage_root = Path(config["storage_root"])
    storage_policy = config.get("storage_policy", {})
    minimum_free_bytes = int(storage_policy.get("minimum_free_bytes", 0) or 0)
    if storage_root.exists() and minimum_free_bytes:
        usage = shutil.disk_usage(storage_root)
        if usage.free < minimum_free_bytes:
            failures.append(f"free_storage_bytes={usage.free} < {minimum_free_bytes}")
        report["storage_free_bytes"] = usage.free
        report["storage_total_bytes"] = usage.total

    report["quality_gate_failures"] = failures
    report["quality_gate_status"] = "failed" if failures else "passed"
    if failures and gates.get("raise_on_failure", True):
        raise QualityGateError("; ".join(failures))
    return report
