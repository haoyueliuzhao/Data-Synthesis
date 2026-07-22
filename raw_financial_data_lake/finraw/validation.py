from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from finraw.db.client import MetadataDB
from finraw.storage import sha256_bytes


def validate_raw_objects(db: MetadataDB) -> tuple[int, int]:
    rows = db.fetchall(
        "SELECT raw_object_id, storage_uri, content_sha256, response_status, "
        "validation_status, notes FROM raw_objects"
    )
    passed = 0
    failed = 0
    for row in rows:
        row = dict(row)
        path = Path(row["storage_uri"])
        if not path.exists():
            db.execute(
                "UPDATE raw_objects SET validation_status = ?, notes = ? WHERE raw_object_id = ?",
                ("failed", "storage file missing", row["raw_object_id"]),
            )
            failed += 1
            continue
        actual = sha256_bytes(path.read_bytes())
        if actual != row["content_sha256"]:
            db.execute(
                "UPDATE raw_objects SET validation_status = ?, notes = ? WHERE raw_object_id = ?",
                ("failed", f"sha256 mismatch actual={actual}", row["raw_object_id"]),
            )
            failed += 1
            continue
        if row.get("validation_status") in {"warning", "superseded", "retired"}:
            passed += 1
            continue
        response_status = row.get("response_status")
        if response_status is not None and not 200 <= int(response_status) < 300:
            db.execute(
                "UPDATE raw_objects SET validation_status = ?, notes = ? WHERE raw_object_id = ?",
                (
                    "failed",
                    f"HTTP status {response_status}; checksum verified",
                    row["raw_object_id"],
                ),
            )
            failed += 1
            continue
        db.execute(
            "UPDATE raw_objects SET validation_status = ? WHERE raw_object_id = ?",
            ("passed", row["raw_object_id"]),
        )
        passed += 1
    return passed, failed


def quality_report(db: MetadataDB) -> dict[str, Any]:
    rows = db.fetchall("SELECT source_id, object_type, validation_status, content_size_bytes, response_status FROM raw_objects")
    by_source = Counter(row["source_id"] for row in rows)
    by_status = Counter(row["validation_status"] for row in rows)
    by_response = Counter(str(row["response_status"]) for row in rows)
    empty_objects = [dict(row) for row in rows if not row["content_size_bytes"]]
    failed_objects = [dict(row) for row in rows if row["validation_status"] == "failed"]
    warning_objects = [dict(row) for row in rows if row["validation_status"] == "warning"]
    jobs = db.fetchall("SELECT source_id, status, COUNT(*) AS count FROM ingestion_jobs GROUP BY source_id, status")
    records = db.fetchall("SELECT source_id, record_type, COUNT(*) AS count FROM raw_records GROUP BY source_id, record_type")
    entities = db.fetchall("SELECT source_id, COUNT(*) AS count FROM source_entities GROUP BY source_id")
    snapshots = db.fetchall("SELECT source_id, COUNT(*) AS count, SUM(total_size_bytes) AS bytes FROM raw_dataset_snapshots GROUP BY source_id")
    return {
        "object_count": len(rows),
        "object_count_by_source": dict(by_source),
        "validation_status_counts": dict(by_status),
        "response_status_counts": dict(by_response),
        "empty_object_count": len(empty_objects),
        "failed_object_count": len(failed_objects),
        "warning_object_count": len(warning_objects),
        "job_status_counts": [dict(row) for row in jobs],
        "record_type_counts": [dict(row) for row in records],
        "entity_counts": [dict(row) for row in entities],
        "snapshot_counts": [dict(row) for row in snapshots],
        "failed_objects": failed_objects[:20],
        "warning_objects": warning_objects[:20],
    }
