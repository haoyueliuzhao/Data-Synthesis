from __future__ import annotations

import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from finraw.config import load_config
from finraw.db.client import create_metadata_db
from finraw.qa.pattern_mining import transition_mining_run
from finraw.qa.pipeline import validate_qa_samples
from finraw.qa.store import json_value


class ProbeRollback(RuntimeError):
    pass


def question_reparse_probe(db: Any, qa_build_id: str) -> dict[str, Any]:
    sample = db.fetchone(
        "SELECT qa_id, question FROM qa_samples "
        "WHERE qa_build_id = ? AND task_subtype = ? "
        "ORDER BY qa_id LIMIT 1",
        (qa_build_id, "temporal_peak_followup"),
    )
    if not sample:
        raise RuntimeError("No temporal_peak_followup sample available for probe")
    result: dict[str, Any] = {}
    try:
        with db.transaction():
            tampered = (
                str(sample["question"])
                .replace("peak", "trough")
                .replace("highest", "lowest")
            )
            if tampered == sample["question"]:
                raise RuntimeError("Selected question has no directional token to tamper")
            db.execute(
                "UPDATE qa_samples SET question = ?, validation_status = ? "
                "WHERE qa_id = ?",
                (tampered, "pending", sample["qa_id"]),
            )
            validate_qa_samples(db, qa_build_id, batch_size=10)
            check = db.fetchone(
                "SELECT check_status, observed_value FROM qa_quality_checks "
                "WHERE qa_id = ? AND check_name = ?",
                (sample["qa_id"], "question_semantic_reparse"),
            )
            updated = db.fetchone(
                "SELECT validation_status FROM qa_samples WHERE qa_id = ?",
                (sample["qa_id"],),
            )
            observed = json_value(check["observed_value"], {}) if check else {}
            result = {
                "qa_build_id": qa_build_id,
                "qa_id": sample["qa_id"],
                "original_question": sample["question"],
                "tampered_question": tampered,
                "validation_status": updated["validation_status"],
                "check_status": check["check_status"] if check else "missing",
                "contract_errors": observed.get("contract_errors", []),
                "passed": bool(
                    updated["validation_status"] == "rejected"
                    and check
                    and check["check_status"] == "failed"
                    and "question_semantics:extreme_direction_mismatch"
                    in observed.get("contract_errors", [])
                ),
                "transaction_rolled_back": True,
            }
            raise ProbeRollback
    except ProbeRollback:
        pass
    persisted = db.fetchone(
        "SELECT question, validation_status FROM qa_samples WHERE qa_id = ?",
        (sample["qa_id"],),
    )
    result["rollback_verified"] = bool(
        persisted
        and persisted["question"] == sample["question"]
        and persisted["validation_status"] == "passed"
    )
    result["passed"] = bool(result.get("passed") and result["rollback_verified"])
    return result


def concurrent_approval_probe(
    config_path: str,
    first_run_id: str,
    second_run_id: str,
) -> dict[str, Any]:
    barrier = threading.Barrier(2)

    def approve(run_id: str) -> dict[str, str]:
        db = create_metadata_db(load_config(config_path))
        try:
            barrier.wait(timeout=30)
            try:
                row = transition_mining_run(
                    db,
                    run_id,
                    target_status="approved_for_qa",
                    reviewer="production-concurrency-probe",
                    notes="Concurrent PostgreSQL approval probe",
                )
                return {"run_id": run_id, "result": "success", "status": row["status"]}
            except Exception as exc:
                return {
                    "run_id": run_id,
                    "result": "error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(approve, (first_run_id, second_run_id)))

    db = create_metadata_db(load_config(config_path))
    try:
        rows = db.fetchall(
            "SELECT mining_run_id, kg_build_id, status, superseded_by_run_id "
            "FROM qa_pattern_mining_runs WHERE mining_run_id IN (?, ?) "
            "ORDER BY mining_run_id",
            (first_run_id, second_run_id),
        )
        statuses = [dict(row) for row in rows]
        approved = [row for row in statuses if row["status"] == "approved_for_qa"]
        superseded = [row for row in statuses if row["status"] == "superseded"]
        kg_build_id = statuses[0]["kg_build_id"] if statuses else None
        approved_count = db.fetchone(
            "SELECT COUNT(*) AS c FROM qa_pattern_mining_runs "
            "WHERE kg_build_id = ? AND status = 'approved_for_qa'",
            (kg_build_id,),
        )["c"]
    finally:
        db.close()
    return {
        "run_ids": [first_run_id, second_run_id],
        "thread_results": results,
        "final_rows": statuses,
        "approved_run_count_for_kg": int(approved_count),
        "passed": bool(len(approved) == 1 and len(superseded) == 1 and approved_count == 1),
    }


def build_identity_comparison(
    db: Any, source_build_id: str, target_build_id: str
) -> dict[str, Any]:
    queries = {
        "binding_hash": (
            "SELECT binding_hash AS value FROM qa_compiled_bindings "
            "WHERE qa_build_id = ?"
        ),
        "stable_candidate_id": (
            "SELECT stable_candidate_id AS value FROM qa_candidates "
            "WHERE qa_build_id = ?"
        ),
        "stable_qa_id": (
            "SELECT stable_qa_id AS value FROM qa_samples WHERE qa_build_id = ?"
        ),
        "semantic_cluster_id": (
            "SELECT semantic_cluster_id AS value FROM qa_samples "
            "WHERE qa_build_id = ?"
        ),
    }
    comparisons: dict[str, Any] = {}
    for name, sql in queries.items():
        source = {
            str(row["value"])
            for row in db.fetchall(sql, (source_build_id,))
        }
        target = {
            str(row["value"])
            for row in db.fetchall(sql, (target_build_id,))
        }
        comparisons[name] = {
            "source_count": len(source),
            "target_count": len(target),
            "intersection_count": len(source & target),
            "source_only_count": len(source - target),
            "target_only_count": len(target - source),
            "exact_match": source == target,
        }
    return {
        "source_qa_build_id": source_build_id,
        "target_qa_build_id": target_build_id,
        "comparisons": comparisons,
        "passed": all(item["exact_match"] for item in comparisons.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--qa-build-id")
    parser.add_argument("--compare-qa-build-id", action="append", default=[])
    parser.add_argument("--concurrent-run-id", action="append", default=[])
    args = parser.parse_args()
    report: dict[str, Any] = {"probe_version": "1.0.0"}
    if args.qa_build_id:
        db = create_metadata_db(load_config(args.config))
        try:
            report["question_semantic_reparse"] = question_reparse_probe(
                db, args.qa_build_id
            )
        finally:
            db.close()
    if args.compare_qa_build_id:
        if len(args.compare_qa_build_id) != 2:
            parser.error("Exactly two --compare-qa-build-id values are required")
        db = create_metadata_db(load_config(args.config))
        try:
            report["build_identity_comparison"] = build_identity_comparison(
                db, *args.compare_qa_build_id
            )
        finally:
            db.close()
    if args.concurrent_run_id:
        if len(args.concurrent_run_id) != 2:
            parser.error("Exactly two --concurrent-run-id values are required")
        report["concurrent_approval"] = concurrent_approval_probe(
            args.config, *args.concurrent_run_id
        )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
