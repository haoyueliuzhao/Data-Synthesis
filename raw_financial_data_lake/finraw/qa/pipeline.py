from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol
from finraw.kg_query import resolve_kg_build_id
from finraw.qa.schema import ensure_qa_schema
from finraw.qa.store import chunks, execute_many, insert_rows, json_value
from finraw.qa.templates import TEMPLATES, template_for


SIMPLE_DERIVED = {"difference", "yoy_growth", "qoq_growth", "ratio", "share"}
TEMPORAL_DERIVED = {
    "multi_year_argmax",
    "multi_year_argmin",
    "rolling_max",
    "rolling_min",
    "macro_time_series_argmax",
    "macro_time_series_argmin",
    "time_series_argmax",
    "time_series_argmin",
    "long_window_return",
}
SCOPE_DERIVED = {
    "ranking",
    "argmax",
    "argmin",
    "industry_ranking",
    "industry_argmax",
    "industry_argmin",
    "multi_condition_screening",
}
SUPPORTED_DERIVED = SIMPLE_DERIVED | TEMPORAL_DERIVED | SCOPE_DERIVED

BUILD_COLUMNS = [
    "qa_build_id",
    "kg_build_id",
    "graph_schema_version",
    "fact_build_id",
    "derived_build_id",
    "entity_build_id",
    "metric_build_id",
    "source_definition_build_id",
    "document_build_id",
    "config_hash",
    "status",
    "started_at",
    "completed_at",
    "candidate_count",
    "passed_count",
    "sample_count",
    "quality_status",
    "is_active",
    "superseded_by",
    "notes",
]
CANDIDATE_COLUMNS = [
    "candidate_id",
    "stable_candidate_id",
    "qa_build_id",
    "task_family",
    "task_subtype",
    "difficulty",
    "entity_ids",
    "metric_ids",
    "time_scope",
    "entity_scope",
    "source_fact_ids",
    "source_derived_ids",
    "source_document_ids",
    "raw_object_ids",
    "canonical_semantics",
    "answer_payload",
    "kg_path",
    "eligibility_status",
    "rejection_reasons",
]
SAMPLE_COLUMNS = [
    "qa_id",
    "stable_qa_id",
    "qa_group_id",
    "semantic_cluster_id",
    "qa_build_id",
    "candidate_id",
    "task_family",
    "task_subtype",
    "difficulty",
    "language",
    "question",
    "canonical_question",
    "answer_type",
    "answer_value",
    "answer_text",
    "unit",
    "currency",
    "rubric",
    "source_metadata",
    "generation_method",
    "validation_status",
    "split",
]
EVIDENCE_COLUMNS = [
    "path_id",
    "qa_id",
    "path_type",
    "ordered_node_ids",
    "ordered_edge_ids",
    "source_fact_ids",
    "source_derived_ids",
    "raw_object_ids",
    "source_document_ids",
]
CHECK_COLUMNS = [
    "check_id",
    "qa_id",
    "qa_build_id",
    "check_name",
    "check_status",
    "observed_value",
    "expected_value",
    "message",
]


def build_qa_candidates(
    db: DBProtocol,
    config: dict[str, Any],
    *,
    kg_build_id: str | None = None,
    output_dir: str | None = None,
    batch_size: int = 2000,
) -> dict[str, Any]:
    ensure_qa_schema(db)
    _seed_templates(db)
    kg_build_id = resolve_kg_build_id(db, kg_build_id)
    kg = _kg_build(db, kg_build_id)
    if kg.get("status") != "success" or kg.get("quality_status") != "passed":
        raise RuntimeError(f"KG build is not QA eligible: {kg_build_id}")
    policy = _qa_policy(config)
    qa_build_id = _new_build_id()
    build = {
        "qa_build_id": qa_build_id,
        "kg_build_id": kg_build_id,
        "graph_schema_version": kg.get("graph_schema_version"),
        "fact_build_id": kg.get("input_fact_build_id"),
        "derived_build_id": kg.get("input_qa_build_id"),
        "entity_build_id": kg.get("input_entity_build_id"),
        "metric_build_id": kg.get("input_metric_build_id"),
        "source_definition_build_id": kg.get("input_source_definition_build_id"),
        "document_build_id": kg.get("input_document_build_id"),
        "config_hash": _digest(policy),
        "status": "building_candidates",
        "started_at": _now(),
        "completed_at": None,
        "candidate_count": 0,
        "passed_count": 0,
        "sample_count": 0,
        "quality_status": "pending",
        "is_active": False,
        "superseded_by": None,
        "notes": {"policy": policy, "generation": "graph_path_driven_deterministic"},
    }
    insert_rows(db, "qa_builds", [build], BUILD_COLUMNS, {"notes"})

    candidates: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    entity_names = {
        str(row["entity_id"]): str(row["canonical_name"])
        for row in db.fetchall(
            "SELECT entity_id, canonical_name FROM canonical_entities WHERE COALESCE(is_active, 1) = 1"
        )
    }
    metric_names = {
        str(row["metric_id"]): str(row["canonical_name"])
        for row in db.fetchall(
            "SELECT metric_id, canonical_name FROM metrics WHERE COALESCE(is_active, 1) = 1"
        )
    }
    raw_by_fact = {
        str(row["fact_id"]): str(row["raw_object_id"])
        for row in db.fetchall(
            "SELECT fact_id, raw_object_id FROM standardized_facts WHERE build_id = ? AND raw_object_id IS NOT NULL",
            (kg["input_fact_build_id"],),
        )
    }

    def emit(candidate: dict[str, Any]) -> None:
        candidates.append(candidate)
        counts[candidate["task_subtype"]] += 1
        for reason in candidate["rejection_reasons"]:
            rejected[reason] += 1
        if len(candidates) >= batch_size:
            insert_rows(
                db,
                "qa_candidates",
                candidates,
                CANDIDATE_COLUMNS,
                _candidate_json_columns(),
            )
            candidates.clear()

    for pool_name, sources, quota in [
        (
            "single_fact_financial",
            ["sec_companyfacts"],
            policy["quotas"]["single_fact_financial"],
        ),
        (
            "single_fact_macro",
            ["worldbank_indicators", "imf_sdmx"],
            policy["quotas"]["single_fact_macro"],
        ),
        (
            "single_fact_fred",
            ["fred_observations"],
            policy["quotas"]["single_fact_fred"],
        ),
    ]:
        rows = _load_fact_pool(db, kg, sources, quota * 5)
        for row in _sample_fact_rows(rows, quota):
            emit(_fact_candidate(row, qa_build_id, kg_build_id, pool_name))

    for derived_type, quota in policy["derived_quotas"].items():
        if derived_type not in SUPPORTED_DERIVED or quota <= 0:
            continue
        for row in _load_derived_pool(db, kg, derived_type, quota):
            emit(
                _derived_candidate(
                    row,
                    qa_build_id,
                    kg_build_id,
                    entity_names,
                    metric_names,
                    raw_by_fact,
                )
            )

    if candidates:
        insert_rows(
            db,
            "qa_candidates",
            candidates,
            CANDIDATE_COLUMNS,
            _candidate_json_columns(),
        )

    candidate_count = _scalar(
        db,
        "SELECT COUNT(*) AS c FROM qa_candidates WHERE qa_build_id = ?",
        [qa_build_id],
    )
    eligible_count = _scalar(
        db,
        "SELECT COUNT(*) AS c FROM qa_candidates WHERE qa_build_id = ? AND eligibility_status = 'eligible'",
        [qa_build_id],
    )
    persisted_task_counts = _group_counts(
        db, "qa_candidates", "qa_build_id", qa_build_id, "task_subtype"
    )
    db.execute(
        "UPDATE qa_builds SET status = ?, candidate_count = ?, notes = ? WHERE qa_build_id = ?",
        (
            "candidates_built",
            candidate_count,
            _db_json(
                db,
                {
                    "policy": policy,
                    "task_counts": persisted_task_counts,
                    "emitted_task_counts": dict(counts),
                    "rejection_counts": dict(rejected),
                },
            ),
            qa_build_id,
        ),
    )
    report = {
        "qa_build_id": qa_build_id,
        "kg_build_id": kg_build_id,
        "candidate_count": candidate_count,
        "eligible_candidate_count": eligible_count,
        "task_counts": persisted_task_counts,
        "emitted_task_counts": dict(sorted(counts.items())),
        "rejection_counts": dict(sorted(rejected.items())),
    }
    return _write_report(report, output_dir, "qa_candidate_report")


def generate_qa_samples(
    db: DBProtocol,
    qa_build_id: str,
    *,
    output_dir: str | None = None,
    batch_size: int = 2000,
) -> dict[str, Any]:
    ensure_qa_schema(db)
    build = _qa_build(db, qa_build_id)
    candidates = db.fetchall(
        "SELECT * FROM qa_candidates WHERE qa_build_id = ? AND eligibility_status = 'eligible' ORDER BY candidate_id",
        (qa_build_id,),
    )
    samples: list[dict[str, Any]] = []
    paths: list[dict[str, Any]] = []
    task_counts: Counter[str] = Counter()
    for raw in candidates:
        candidate = _decode_candidate(dict(raw))
        sample, path = _sample_from_candidate(candidate, build)
        samples.append(sample)
        paths.append(path)
        task_counts[sample["task_subtype"]] += 1
        if len(samples) >= batch_size:
            insert_rows(
                db, "qa_samples", samples, SAMPLE_COLUMNS, _sample_json_columns()
            )
            insert_rows(
                db,
                "qa_evidence_paths",
                paths,
                EVIDENCE_COLUMNS,
                _evidence_json_columns(),
            )
            samples.clear()
            paths.clear()
    if samples:
        insert_rows(db, "qa_samples", samples, SAMPLE_COLUMNS, _sample_json_columns())
        insert_rows(
            db, "qa_evidence_paths", paths, EVIDENCE_COLUMNS, _evidence_json_columns()
        )
    sample_count = _scalar(
        db, "SELECT COUNT(*) AS c FROM qa_samples WHERE qa_build_id = ?", [qa_build_id]
    )
    persisted_task_counts = _group_counts(
        db, "qa_samples", "qa_build_id", qa_build_id, "task_subtype"
    )
    db.execute(
        "UPDATE qa_builds SET status = ?, sample_count = ? WHERE qa_build_id = ?",
        ("samples_generated", sample_count, qa_build_id),
    )
    return _write_report(
        {
            "qa_build_id": qa_build_id,
            "kg_build_id": build["kg_build_id"],
            "sample_count": sample_count,
            "task_counts": persisted_task_counts,
            "emitted_task_counts": dict(sorted(task_counts.items())),
        },
        output_dir,
        "qa_generation_report",
    )


def validate_qa_samples(
    db: DBProtocol,
    qa_build_id: str,
    *,
    output_dir: str | None = None,
    batch_size: int = 2000,
) -> dict[str, Any]:
    ensure_qa_schema(db)
    build = _qa_build(db, qa_build_id)
    rows = [
        dict(row)
        for row in db.fetchall(
            """
        SELECT s.*, c.canonical_semantics, c.answer_payload, c.kg_path,
               c.source_fact_ids, c.source_derived_ids, c.raw_object_ids
        FROM qa_samples s JOIN qa_candidates c ON c.candidate_id = s.candidate_id
        WHERE s.qa_build_id = ? ORDER BY s.qa_id
        """,
            (qa_build_id,),
        )
    ]
    fact_ids = sorted(
        {
            fact_id
            for row in rows
            for fact_id in json_value(row.get("source_fact_ids"), [])
        }
    )
    facts = _load_facts_by_id(db, fact_ids, build["fact_build_id"])
    node_ids = sorted(
        {
            node_id
            for row in rows
            for node_id in json_value(row.get("kg_path"), {}).get("node_ids", [])
        }
    )
    edge_ids = sorted(
        {
            edge_id
            for row in rows
            for edge_id in json_value(row.get("kg_path"), {}).get("edge_ids", [])
        }
    )
    existing_nodes = _existing_graph_ids(
        db, "kg_nodes", "node_id", build["kg_build_id"], node_ids
    )
    existing_edges = _existing_graph_ids(
        db, "kg_edges", "edge_id", build["kg_build_id"], edge_ids
    )
    checks: list[dict[str, Any]] = []
    status_updates: list[tuple[str, str]] = []
    passed = 0
    failed = 0
    failure_counts: Counter[str] = Counter()
    for row in rows:
        decoded = _decode_validation_row(row)
        sample_checks = _validate_one(
            decoded, build, facts, existing_nodes, existing_edges
        )
        status = (
            "passed"
            if all(check["check_status"] == "passed" for check in sample_checks)
            else "rejected"
        )
        status_updates.append((status, decoded["qa_id"]))
        if status == "passed":
            passed += 1
        else:
            failed += 1
            for check in sample_checks:
                if check["check_status"] != "passed":
                    failure_counts[check["check_name"]] += 1
        checks.extend(sample_checks)
        if len(checks) >= batch_size:
            insert_rows(
                db,
                "qa_quality_checks",
                checks,
                CHECK_COLUMNS,
                {"observed_value", "expected_value"},
            )
            execute_many(
                db,
                "UPDATE qa_samples SET validation_status = ? WHERE qa_id = ?",
                status_updates,
            )
            checks.clear()
            status_updates.clear()
    if checks:
        insert_rows(
            db,
            "qa_quality_checks",
            checks,
            CHECK_COLUMNS,
            {"observed_value", "expected_value"},
        )
    if status_updates:
        execute_many(
            db,
            "UPDATE qa_samples SET validation_status = ? WHERE qa_id = ?",
            status_updates,
        )
    quality_status = (
        "passed"
        if passed > 0 and failed == 0
        else ("partial" if passed > 0 else "failed")
    )
    db.execute(
        "UPDATE qa_builds SET status = ?, passed_count = ?, quality_status = ?, completed_at = ? WHERE qa_build_id = ?",
        ("validated", passed, quality_status, _now(), qa_build_id),
    )
    report = {
        "qa_build_id": qa_build_id,
        "kg_build_id": build["kg_build_id"],
        "sample_count": len(rows),
        "passed_count": passed,
        "rejected_count": failed,
        "pass_rate": passed / len(rows) if rows else 0,
        "quality_status": quality_status,
        "failure_counts": dict(sorted(failure_counts.items())),
    }
    return _write_report(report, output_dir, "qa_quality_report")


def split_qa_samples(
    db: DBProtocol,
    qa_build_id: str,
    *,
    output_dir: str | None = None,
) -> dict[str, Any]:
    ensure_qa_schema(db)
    db.execute(
        "UPDATE qa_samples SET split = NULL WHERE qa_build_id = ? AND validation_status <> 'passed'",
        (qa_build_id,),
    )
    rows = [
        dict(row)
        for row in db.fetchall(
            """
        SELECT s.qa_id, s.qa_group_id, s.task_subtype, c.entity_ids, c.time_scope
        FROM qa_samples s JOIN qa_candidates c ON c.candidate_id = s.candidate_id
        WHERE s.qa_build_id = ? AND s.validation_status = 'passed'
        ORDER BY s.qa_group_id, s.qa_id
        """,
            (qa_build_id,),
        )
    ]
    group_split: dict[str, str] = {}
    split_counts: Counter[str] = Counter()
    challenge = SCOPE_DERIVED | {"rolling_max", "rolling_min"}
    split_updates: list[tuple[str, str]] = []
    for row in rows:
        group = row["qa_group_id"]
        if group not in group_split:
            bucket = int(hashlib.sha1(group.encode("utf-8")).hexdigest()[:8], 16) % 100
            entities = json_value(row.get("entity_ids"), [])
            time_scope = json_value(row.get("time_scope"), {})
            if row["task_subtype"] in challenge:
                split = "test_complex"
            elif (
                entities
                and int(
                    hashlib.sha1(str(entities[0]).encode("utf-8")).hexdigest()[:8], 16
                )
                % 20
                == 0
            ):
                split = "test_entity_holdout"
            elif (
                _latest_year(time_scope)
                and _latest_year(time_scope) >= datetime.now(timezone.utc).year - 1
            ):
                split = "test_temporal_holdout"
            elif bucket < 80:
                split = "train"
            elif bucket < 90:
                split = "dev"
            else:
                split = "test_standard"
            group_split[group] = split
        split_counts[group_split[group]] += 1
        split_updates.append((group_split[group], row["qa_id"]))
    execute_many(db, "UPDATE qa_samples SET split = ? WHERE qa_id = ?", split_updates)
    db.execute(
        "UPDATE qa_builds SET status = ?, is_active = ? WHERE qa_build_id = ?",
        ("ready", True, qa_build_id),
    )
    if rows:
        old = db.fetchall(
            "SELECT qa_build_id FROM qa_builds WHERE is_active = ? AND qa_build_id <> ?",
            (True, qa_build_id),
        )
        for item in old:
            db.execute(
                "UPDATE qa_builds SET is_active = ?, superseded_by = ? WHERE qa_build_id = ?",
                (False, qa_build_id, item["qa_build_id"]),
            )
    report = {
        "qa_build_id": qa_build_id,
        "passed_sample_count": len(rows),
        "qa_group_count": len(group_split),
        "split_counts": dict(sorted(split_counts.items())),
    }
    return _write_report(report, output_dir, "qa_split_report")


def build_qa(
    db: DBProtocol,
    config: dict[str, Any],
    *,
    kg_build_id: str | None = None,
    output_dir: str = "data/audit/qa_build",
    batch_size: int = 2000,
) -> dict[str, Any]:
    candidate = build_qa_candidates(
        db,
        config,
        kg_build_id=kg_build_id,
        output_dir=output_dir,
        batch_size=batch_size,
    )
    qa_build_id = candidate["qa_build_id"]
    generated = generate_qa_samples(
        db, qa_build_id, output_dir=output_dir, batch_size=batch_size
    )
    quality = validate_qa_samples(
        db, qa_build_id, output_dir=output_dir, batch_size=batch_size
    )
    split = split_qa_samples(db, qa_build_id, output_dir=output_dir)
    report = {
        "qa_build_id": qa_build_id,
        "candidate": candidate,
        "generation": generated,
        "quality": quality,
        "split": split,
    }
    return _write_report(report, output_dir, "qa_build_report")


def _fact_candidate(
    row: dict[str, Any], qa_build_id: str, kg_build_id: str, pool_name: str
) -> dict[str, Any]:
    reasons = []
    for key, reason in [
        ("entity_id", "missing_entity"),
        ("metric_id", "missing_metric"),
        ("normalized_value", "missing_value"),
        ("normalized_unit", "missing_unit"),
    ]:
        if row.get(key) in (None, ""):
            reasons.append(reason)
    time_scope = _fact_time_scope(row)
    if not time_scope:
        reasons.append("missing_time")
    semantics = {
        "operation": "lookup",
        "pool": pool_name,
        "entity_id": row.get("entity_id"),
        "entity_name": row.get("entity_name"),
        "entity_type": row.get("entity_type"),
        "metric_id": row.get("metric_id"),
        "metric_name": row.get("metric_name"),
        "metric_period_type": row.get("metric_period_type"),
        "time_scope": time_scope,
        "source_id": row.get("source_id"),
    }
    answer = {
        "value": str(row.get("normalized_value")),
        "unit": row.get("normalized_unit"),
        "currency": row.get("normalized_currency"),
    }
    stable = "qac_" + _digest(semantics)
    fact_id = str(row.get("fact_id"))
    path = _fact_path(row, kg_build_id)
    return {
        "candidate_id": f"{stable}__{qa_build_id}",
        "stable_candidate_id": stable,
        "qa_build_id": qa_build_id,
        "task_family": "single_fact",
        "task_subtype": "single_fact",
        "difficulty": "easy",
        "entity_ids": [row.get("entity_id")],
        "metric_ids": [row.get("metric_id")],
        "time_scope": time_scope,
        "entity_scope": {"entity_id": row.get("entity_id")},
        "source_fact_ids": [fact_id],
        "source_derived_ids": [],
        "source_document_ids": [],
        "raw_object_ids": [row["raw_object_id"]] if row.get("raw_object_id") else [],
        "canonical_semantics": semantics,
        "answer_payload": answer,
        "kg_path": path,
        "eligibility_status": "eligible" if not reasons else "rejected",
        "rejection_reasons": reasons,
    }


def _derived_candidate(
    row: dict[str, Any],
    qa_build_id: str,
    kg_build_id: str,
    entity_name_map: dict[str, str],
    metric_name_map: dict[str, str],
    raw_by_fact: dict[str, str],
) -> dict[str, Any]:
    for key in [
        "input_fact_ids",
        "entity_scope",
        "metric_scope",
        "time_scope",
        "scope_entity_ids",
        "output_table",
    ]:
        row[key] = json_value(
            row.get(key),
            [] if key in {"input_fact_ids", "scope_entity_ids", "output_table"} else {},
        )
    derived_type = row["derived_type"]
    entity_scope = row["entity_scope"]
    metric_scope = row["metric_scope"]
    entity_ids = sorted(
        set(
            row["scope_entity_ids"]
            + ([entity_scope.get("entity_id")] if entity_scope.get("entity_id") else [])
        )
    )
    metric_ids = sorted(
        {
            value
            for key, value in metric_scope.items()
            if key in {"metric_id", "numerator", "denominator"} and value
        }
    )
    reasons = []
    if not row["input_fact_ids"]:
        reasons.append("missing_input_facts")
    if not metric_ids and derived_type != "multi_condition_screening":
        reasons.append("missing_metric")
    if derived_type in SCOPE_DERIVED | {"share"} and not row.get("scope_id"):
        reasons.append("missing_scope")
    if row.get("output_value") is None and not row["output_table"]:
        reasons.append("missing_answer")
    semantics = {
        "operation": derived_type,
        "entity_ids": entity_ids,
        "entity_names": {
            entity_id: entity_name_map.get(entity_id, entity_id)
            for entity_id in entity_ids
        },
        "metric_ids": metric_ids,
        "metric_names": {
            metric_id: metric_name_map.get(metric_id, metric_id.replace("_", " "))
            for metric_id in metric_ids
        },
        "metric_scope": metric_scope,
        "time_scope": row["time_scope"],
        "scope_type": row.get("scope_type"),
        "scope_id": row.get("scope_id"),
        "scope_definition": row.get("scope_definition"),
        "calculation_code": row.get("calculation_code"),
        "expected_table": row["output_table"]
        if derived_type == "multi_condition_screening"
        else [],
    }
    answer = {
        "value": str(row["output_value"])
        if row.get("output_value") is not None
        else None,
        "table": row["output_table"],
        "unit": row.get("unit"),
        "tolerance": str(row.get("tolerance") or 0),
        "result_period": row["time_scope"].get("result_year")
        or row["time_scope"].get("result_date"),
        "winning_entity_id": entity_scope.get("entity_id")
        if derived_type in {"argmax", "argmin", "industry_argmax", "industry_argmin"}
        else None,
    }
    stable = "qac_" + _digest(
        semantics, row["input_fact_ids"], row.get("stable_derived_id")
    )
    raw_object_ids = sorted(
        {
            raw_by_fact[fact_id]
            for fact_id in row["input_fact_ids"]
            if fact_id in raw_by_fact
        }
    )
    return {
        "candidate_id": f"{stable}__{qa_build_id}",
        "stable_candidate_id": stable,
        "qa_build_id": qa_build_id,
        "task_family": _task_family(derived_type),
        "task_subtype": derived_type,
        "difficulty": _difficulty(
            derived_type, len(row["input_fact_ids"]), len(entity_ids)
        ),
        "entity_ids": entity_ids,
        "metric_ids": metric_ids,
        "time_scope": row["time_scope"],
        "entity_scope": {
            **entity_scope,
            "scope_id": row.get("scope_id"),
            "scope_definition": row.get("scope_definition"),
        },
        "source_fact_ids": row["input_fact_ids"],
        "source_derived_ids": [row["derived_id"]],
        "source_document_ids": [],
        "raw_object_ids": raw_object_ids,
        "canonical_semantics": semantics,
        "answer_payload": answer,
        "kg_path": _derived_path(row, kg_build_id),
        "eligibility_status": "eligible" if not reasons else "rejected",
        "rejection_reasons": reasons,
    }


def _sample_from_candidate(
    candidate: dict[str, Any], build: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    semantics = candidate["canonical_semantics"]
    entity_names = _entity_names_from_semantics(semantics, candidate["entity_ids"])
    metric_names = _metric_names_from_semantics(semantics, candidate["metric_ids"])
    slots = _question_slots(candidate, entity_names, metric_names)
    template = template_for(
        candidate["task_subtype"], semantics.get("metric_period_type")
    )
    question = template["template_text"].format(**slots)
    answer = candidate["answer_payload"]
    answer_text = _answer_text(candidate, answer, entity_names)
    group_id = "qag_" + _digest(
        candidate["task_subtype"],
        candidate["source_fact_ids"],
        candidate["source_derived_ids"],
        candidate["time_scope"],
        candidate["entity_scope"],
    )
    cluster_id = "qacl_" + _digest(
        candidate["task_subtype"],
        candidate["entity_ids"],
        candidate["metric_ids"],
        candidate["time_scope"],
    )
    stable_qa_id = "qa_" + _digest(_normalise_question(question), answer)
    qa_id = f"{stable_qa_id}__{candidate['qa_build_id']}"
    rubric = _rubric(candidate, answer)
    sample = {
        "qa_id": qa_id,
        "stable_qa_id": stable_qa_id,
        "qa_group_id": group_id,
        "semantic_cluster_id": cluster_id,
        "qa_build_id": candidate["qa_build_id"],
        "candidate_id": candidate["candidate_id"],
        "task_family": candidate["task_family"],
        "task_subtype": candidate["task_subtype"],
        "difficulty": candidate["difficulty"],
        "language": "en",
        "question": question,
        "canonical_question": question,
        "answer_type": template["answer_type"],
        "answer_value": answer,
        "answer_text": answer_text,
        "unit": answer.get("unit"),
        "currency": answer.get("currency"),
        "rubric": rubric,
        "source_metadata": {
            "kg_build_id": build["kg_build_id"],
            "fact_build_id": build["fact_build_id"],
            "derived_build_id": build["derived_build_id"],
            "source_fact_ids": candidate["source_fact_ids"],
            "source_derived_ids": candidate["source_derived_ids"],
            "raw_object_ids": candidate["raw_object_ids"],
        },
        "generation_method": "deterministic_template",
        "validation_status": "pending",
        "split": None,
    }
    path = {
        "path_id": "qap_" + _digest(qa_id, candidate["kg_path"]),
        "qa_id": qa_id,
        "path_type": "derived_fact_path"
        if candidate["source_derived_ids"]
        else "single_fact_path",
        "ordered_node_ids": candidate["kg_path"].get("node_ids", []),
        "ordered_edge_ids": candidate["kg_path"].get("edge_ids", []),
        "source_fact_ids": candidate["source_fact_ids"],
        "source_derived_ids": candidate["source_derived_ids"],
        "raw_object_ids": candidate["raw_object_ids"],
        "source_document_ids": candidate["source_document_ids"],
    }
    return sample, path


def _validate_one(
    row: dict[str, Any],
    build: dict[str, Any],
    facts: dict[str, dict[str, Any]],
    existing_nodes: set[str],
    existing_edges: set[str],
) -> list[dict[str, Any]]:
    checks = []

    def add(
        name: str, passed: bool, observed: Any, expected: Any, message: str
    ) -> None:
        checks.append(
            {
                "check_id": "qacheck_" + _digest(row["qa_id"], name),
                "qa_id": row["qa_id"],
                "qa_build_id": row["qa_build_id"],
                "check_name": name,
                "check_status": "passed" if passed else "failed",
                "observed_value": observed,
                "expected_value": expected,
                "message": message,
            }
        )

    add(
        "structure",
        bool(
            row.get("question")
            and row.get("answer_text")
            and (row["source_fact_ids"] or row["source_derived_ids"])
        ),
        True,
        True,
        "Question, answer, and provenance IDs are required.",
    )
    source_facts = [facts.get(fact_id) for fact_id in row["source_fact_ids"]]
    add(
        "fact_membership",
        all(item and item.get("graph_ready") for item in source_facts),
        len([item for item in source_facts if item and item.get("graph_ready")]),
        len(source_facts),
        "All source facts must belong to the pinned graph-ready fact build.",
    )
    path = row["kg_path"]
    missing_nodes = sorted(set(path.get("node_ids", [])) - existing_nodes)
    missing_edges = sorted(set(path.get("edge_ids", [])) - existing_edges)
    add(
        "evidence_path",
        bool(path.get("node_ids") and path.get("edge_ids"))
        and not missing_nodes
        and not missing_edges,
        {"missing_nodes": missing_nodes, "missing_edges": missing_edges},
        {"missing_nodes": [], "missing_edges": []},
        "Every evidence path node and edge must exist in the pinned KG build.",
    )
    add(
        "semantic_slots",
        _semantic_slots_complete(row),
        True,
        True,
        "Entity, metric, time, unit, and required scope must be explicit.",
    )
    expected = row["answer_payload"]
    recomputed, reason = _recompute(
        row["task_subtype"],
        [item for item in source_facts if item],
        row["canonical_semantics"],
    )
    matched = _answers_match(expected, recomputed, row.get("rubric"))
    add("independent_recompute", matched, recomputed, expected, reason)
    if row["task_subtype"] in SCOPE_DERIVED | {"share"}:
        expected_scope_count = len(row["canonical_semantics"].get("entity_ids", []))
        represented = len({item.get("entity_id") for item in source_facts if item})
        complete = _scope_is_complete(
            row["task_subtype"], row["canonical_semantics"], represented
        )
        add(
            "scope_completeness",
            complete,
            represented,
            expected_scope_count,
            "Scope tasks require input coverage for every declared entity.",
        )
    add(
        "no_answer_leakage",
        row.get("answer_text", "") not in row.get("question", ""),
        False,
        False,
        "Canonical question must not contain the rendered answer.",
    )
    return checks


def _scope_is_complete(
    task_subtype: str, semantics: dict[str, Any], represented_entity_count: int
) -> bool:
    if (
        task_subtype == "multi_condition_screening"
        and semantics.get("scope_type") == "screening_result_set"
    ):
        return False
    expected = len(semantics.get("entity_ids", []))
    return expected <= 1 or represented_entity_count >= expected


def _recompute(
    task: str, facts: list[dict[str, Any]], semantics: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    values = [(item, _decimal(item.get("normalized_value"))) for item in facts]
    values = [(item, value) for item, value in values if value is not None]
    unit = facts[0].get("normalized_unit") if facts else None
    currency = facts[0].get("normalized_currency") if facts else None
    if task == "single_fact" and len(values) == 1:
        return {
            "value": str(values[0][1]),
            "unit": unit,
            "currency": currency,
        }, "Re-read the pinned standardized fact."
    if task == "qoq_growth":
        quarter_order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
        ordered = sorted(
            values,
            key=lambda item: (
                int(item[0].get("fiscal_year") or 0),
                quarter_order.get(item[0].get("fiscal_quarter"), 0),
            ),
        )
    elif task in {"difference", "yoy_growth"}:
        ordered = sorted(
            values,
            key=lambda item: (
                int(item[0].get("fiscal_year") or item[0].get("calendar_year") or 0),
                str(item[0].get("period_end") or ""),
            ),
        )
    else:
        ordered = sorted(values, key=lambda item: _fact_sort_key(item[0]))
    if task == "difference" and len(ordered) == 2:
        result = ordered[1][1] - ordered[0][1]
    elif (
        task in {"yoy_growth", "qoq_growth"}
        and len(ordered) == 2
        and ordered[0][1] != 0
    ):
        result = (ordered[1][1] - ordered[0][1]) / abs(ordered[0][1]) * Decimal("100")
        unit = "percent"
    elif task == "ratio" and len(values) == 2:
        metric_scope = semantics.get("metric_scope", {})
        by_metric = {item.get("metric_id"): value for item, value in values}
        denominator = by_metric.get(metric_scope.get("denominator"))
        numerator = by_metric.get(metric_scope.get("numerator"))
        if denominator in {None, Decimal("0")} or numerator is None:
            return {}, "Ratio inputs are incomplete or denominator is zero."
        result = numerator / denominator * Decimal("100")
        unit = "percent"
    elif task == "long_window_return" and len(ordered) == 2 and ordered[0][1] != 0:
        result = (ordered[1][1] / ordered[0][1] - Decimal("1")) * Decimal("100")
        unit = "percent"
    elif task in TEMPORAL_DERIVED and values:
        choose_max = task.endswith("argmax") or task == "rolling_max"
        winner = (max if choose_max else min)(values, key=lambda item: item[1])
        if task in {"multi_year_argmax", "multi_year_argmin"}:
            result_period = winner[0].get("fiscal_year") or winner[0].get(
                "calendar_year"
            )
        else:
            result_period = winner[0].get("period_end")
        return {
            "value": str(winner[1]),
            "unit": unit,
            "result_period": result_period,
        }, "Recomputed extrema over every declared input fact."
    elif task in {"ranking", "industry_ranking"} and values:
        table = [
            {
                "rank": index + 1,
                "entity_id": item.get("entity_id"),
                "value": _number(value),
            }
            for index, (item, value) in enumerate(
                sorted(values, key=lambda pair: pair[1], reverse=True)
            )
        ]
        return {
            "value": None,
            "table": table,
            "unit": unit,
        }, "Re-ranked all declared scope inputs."
    elif task in {"argmax", "industry_argmax", "argmin", "industry_argmin"} and values:
        choose_max = task.endswith("argmax") or task == "argmax"
        winner = (max if choose_max else min)(values, key=lambda item: item[1])
        return {
            "value": str(winner[1]),
            "unit": unit,
            "winning_entity_id": winner[0].get("entity_id"),
        }, "Recomputed scope extremum from declared facts."
    elif task == "multi_condition_screening" and values:
        return {
            "table": semantics.get("expected_table", [])
        }, "Screening inputs were present; set completeness is checked separately."
    else:
        return (
            {},
            f"No independent recomputation rule for {task} with {len(values)} numeric facts.",
        )
    return {
        "value": str(result),
        "unit": unit,
        "currency": currency,
    }, "Recomputed with an independent Decimal implementation."


def _answers_match(
    expected: dict[str, Any], observed: dict[str, Any], rubric: dict[str, Any] | None
) -> bool:
    if not observed:
        return False
    if expected.get("value") is not None:
        left = _decimal(expected.get("value"))
        right = _decimal(observed.get("value"))
        if left is None or right is None:
            return False
        tolerance = _decimal(expected.get("tolerance")) or Decimal("0.000001")
        if abs(left - right) > max(tolerance, abs(left) * Decimal("0.000001")):
            return False
    if expected.get("result_period") is not None and str(
        expected["result_period"]
    ) != str(observed.get("result_period")):
        return False
    if expected.get("winning_entity_id") and expected[
        "winning_entity_id"
    ] != observed.get("winning_entity_id"):
        return False
    if expected.get("table"):
        expected_entities = [item.get("entity_id") for item in expected["table"]]
        observed_entities = [
            item.get("entity_id") for item in observed.get("table", [])
        ]
        if expected_entities != observed_entities[: len(expected_entities)]:
            return False
    return True


def _load_fact_pool(
    db: DBProtocol, kg: dict[str, Any], source_ids: list[str], limit: int
) -> list[dict[str, Any]]:
    placeholders = ",".join("?" for _ in source_ids)
    rows = db.fetchall(
        f"""
        SELECT sf.*, ce.canonical_name AS entity_name, ce.entity_type,
               m.canonical_name AS metric_name, m.metric_category,
               ro.original_url, ro.storage_uri, ro.content_sha256
        FROM standardized_facts sf
        JOIN canonical_entities ce ON ce.entity_id = sf.entity_id
        JOIN metrics m ON m.metric_id = sf.metric_id
        LEFT JOIN raw_objects ro ON ro.raw_object_id = sf.raw_object_id
        WHERE sf.build_id = ? AND COALESCE(sf.graph_ready, 0) = 1
          AND sf.verification_status IN ('single_source', 'cross_verified')
          AND COALESCE(CAST(sf.is_forecast AS INTEGER), 0) = 0
          AND sf.source_id IN ({placeholders})
          AND sf.normalized_value IS NOT NULL AND sf.normalized_unit IS NOT NULL
        ORDER BY sf.fact_id LIMIT ?
        """,
        [kg["input_fact_build_id"], *source_ids, limit],
    )
    return [dict(row) for row in rows]


def _load_derived_pool(
    db: DBProtocol, kg: dict[str, Any], derived_type: str, limit: int
) -> list[dict[str, Any]]:
    rows = db.fetchall(
        """
        SELECT d.*
        FROM derived_facts d
        WHERE d.build_id = ? AND d.input_build_id = ?
          AND d.verification_status IN ('single_source', 'cross_verified')
          AND d.derived_type = ?
        ORDER BY d.derived_id LIMIT ?
        """,
        (
            kg["input_qa_build_id"],
            kg["input_fact_build_id"],
            derived_type,
            limit,
        ),
    )
    return [dict(row) for row in rows]


def _load_facts_by_id(
    db: DBProtocol, fact_ids: list[str], fact_build_id: str
) -> dict[str, dict[str, Any]]:
    out = {}
    for batch in chunks(fact_ids, 1000):
        placeholders = ",".join("?" for _ in batch)
        rows = db.fetchall(
            f"SELECT * FROM standardized_facts WHERE build_id = ? AND fact_id IN ({placeholders})",
            [fact_build_id, *batch],
        )
        for raw in rows:
            row = dict(raw)
            row["graph_ready"] = bool(row.get("graph_ready"))
            out[row["fact_id"]] = row
    return out


def _existing_graph_ids(
    db: DBProtocol,
    table: str,
    id_column: str,
    kg_build_id: str,
    values: list[str],
) -> set[str]:
    out = set()
    for batch in chunks(values, 1000):
        placeholders = ",".join("?" for _ in batch)
        rows = db.fetchall(
            f"SELECT {id_column} FROM {table} WHERE kg_build_id = ? AND {id_column} IN ({placeholders})",
            [kg_build_id, *batch],
        )
        out.update(str(row[id_column]) for row in rows)
    return out


def _raw_objects_for_facts(db: DBProtocol, fact_ids: list[str]) -> list[str]:
    if not fact_ids:
        return []
    out = set()
    for batch in chunks(fact_ids, 500):
        placeholders = ",".join("?" for _ in batch)
        for row in db.fetchall(
            f"SELECT raw_object_id FROM standardized_facts WHERE fact_id IN ({placeholders})",
            batch,
        ):
            if row["raw_object_id"]:
                out.add(row["raw_object_id"])
    return sorted(out)


def _sample_fact_rows(rows: list[dict[str, Any]], quota: int) -> list[dict[str, Any]]:
    selected = []
    buckets: Counter[tuple[Any, ...]] = Counter()
    for row in rows:
        frequency = str(row.get("frequency") or "").lower()
        period = str(row.get("period_end") or row.get("as_of_date") or "")
        if frequency == "daily":
            key = (row.get("entity_id"), row.get("metric_id"), period[:7])
            cap = 2
        elif frequency == "monthly":
            key = (row.get("entity_id"), row.get("metric_id"), period[:4])
            cap = 3
        else:
            key = (row.get("entity_id"), row.get("metric_id"), period)
            cap = 1
        if buckets[key] >= cap:
            continue
        buckets[key] += 1
        selected.append(row)
        if len(selected) >= quota:
            break
    return selected


def _fact_path(row: dict[str, Any], kg_build_id: str) -> dict[str, list[str]]:
    fact = f"fact:{row['fact_id']}"
    entity = f"entity:{row['entity_id']}"
    metric = f"metric:{row['metric_id']}"
    source = f"source:{row['source_id']}"
    stable_nodes = [entity, fact, metric, source]
    edges = [
        _edge(entity, "HAS_FACT", fact, "standardized_facts", row["fact_id"]),
        _edge(fact, "MEASURES", metric, "standardized_facts", row["fact_id"]),
        _edge(fact, "FROM_SOURCE", source, "standardized_facts", row["fact_id"]),
    ]
    if row.get("raw_object_id"):
        raw = f"raw_object:{row['raw_object_id']}"
        stable_nodes.append(raw)
        edges.append(
            _edge(fact, "TRACED_TO", raw, "standardized_facts", row["fact_id"])
        )
    return {
        "node_ids": [_versioned(item, kg_build_id) for item in stable_nodes],
        "edge_ids": [_versioned(item, kg_build_id) for item in edges],
    }


def _derived_path(row: dict[str, Any], kg_build_id: str) -> dict[str, list[str]]:
    derived = f"derived_fact:{row['derived_id']}"
    nodes = [derived]
    edges = []
    for fact_id in json_value(row.get("input_fact_ids"), []):
        fact = f"fact:{fact_id}"
        nodes.append(fact)
        edges.append(
            _edge(derived, "DERIVED_FROM", fact, "derived_facts", row["derived_id"])
        )
    entity_scope = json_value(row.get("entity_scope"), {})
    if entity_scope.get("entity_id"):
        entity = f"entity:{entity_scope['entity_id']}"
        nodes.append(entity)
        edges.append(
            _edge(derived, "ABOUT_ENTITY", entity, "derived_facts", row["derived_id"])
        )
    metric_scope = json_value(row.get("metric_scope"), {})
    for metric_id in sorted(
        {
            metric_scope.get("metric_id"),
            metric_scope.get("numerator"),
            metric_scope.get("denominator"),
        }
        - {None}
    ):
        metric = f"metric:{metric_id}"
        nodes.append(metric)
        edges.append(
            _edge(derived, "USES_METRIC", metric, "derived_facts", row["derived_id"])
        )
    return {
        "node_ids": [_versioned(item, kg_build_id) for item in dict.fromkeys(nodes)],
        "edge_ids": [_versioned(item, kg_build_id) for item in edges],
    }


def _edge(src: str, relation: str, dst: str, source_table: str, source_pk: str) -> str:
    return "edge:" + _digest(src, relation, dst, source_table, source_pk)


def _versioned(stable_id: str, build_id: str) -> str:
    return f"{stable_id}@@{build_id}"


def _question_slots(
    candidate: dict[str, Any],
    entity_names: dict[str, str],
    metric_names: dict[str, str],
) -> dict[str, str]:
    semantics = candidate["canonical_semantics"]
    time_scope = candidate["time_scope"]
    entity_id = semantics.get("entity_id") or next(
        iter(candidate["entity_ids"]), "the entity"
    )
    metric_id = next(iter(candidate["metric_ids"]), "the metric")
    period = _period_label(time_scope)
    previous = _previous_period_label(time_scope)
    subtype = candidate["task_subtype"]
    return {
        "entity": entity_names.get(entity_id, entity_id),
        "metric": metric_names.get(metric_id, metric_id.replace("_", " ")),
        "ratio": str(
            semantics.get("metric_scope", {}).get("ratio_id") or metric_id
        ).replace("_", " "),
        "period": period,
        "previous_period": previous,
        "start_period": str(
            time_scope.get("start_year") or time_scope.get("start_date") or previous
        ),
        "end_period": str(
            time_scope.get("end_year") or time_scope.get("end_date") or period
        ),
        "extreme": "highest"
        if subtype.endswith("argmax")
        or subtype in {"argmax", "rolling_max", "industry_argmax"}
        else "lowest",
        "scope": semantics.get("scope_definition")
        or "the explicitly configured data scope",
    }


def _answer_text(
    candidate: dict[str, Any], answer: dict[str, Any], entity_names: dict[str, str]
) -> str:
    if answer.get("table"):
        entities = [
            entity_names.get(item.get("entity_id"), item.get("entity_id"))
            for item in answer["table"]
        ]
        return ", ".join(str(value) for value in entities if value)
    if answer.get("winning_entity_id"):
        name = entity_names.get(
            answer["winning_entity_id"], answer["winning_entity_id"]
        )
        return f"{name}: {_format_value(answer.get('value'))} {answer.get('unit') or ''}".strip()
    if answer.get("result_period") is not None:
        return f"{answer['result_period']}: {_format_value(answer.get('value'))} {answer.get('unit') or ''}".strip()
    return f"{_format_value(answer.get('value'))} {answer.get('unit') or ''}".strip()


def _rubric(candidate: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    if answer.get("table"):
        entities = [item.get("entity_id") for item in answer["table"]]
        match_type = (
            "set_match"
            if candidate["task_subtype"] == "multi_condition_screening"
            else "ranked_list"
        )
        return {
            "match_type": match_type,
            "target_entity_ids": entities,
            "order_required": match_type == "ranked_list",
            "allow_extra_entities": False,
            "allow_missing_entities": False,
        }
    if answer.get("winning_entity_id"):
        return {
            "match_type": "entity_and_value",
            "target_entity_id": answer["winning_entity_id"],
            "target_value": answer.get("value"),
            "unit": answer.get("unit"),
            "absolute_tolerance": answer.get("tolerance") or "0.000001",
        }
    if answer.get("result_period") is not None:
        return {
            "match_type": "period_and_value",
            "target_period": answer["result_period"],
            "target_value": answer.get("value"),
            "unit": answer.get("unit"),
            "value_tolerance": answer.get("tolerance") or "0.000001",
        }
    return {
        "match_type": "numeric_tolerance",
        "target_value": answer.get("value"),
        "unit": answer.get("unit"),
        "absolute_tolerance": answer.get("tolerance") or "0.000001",
        "relative_tolerance": "0.000001",
        "accept_percent_decimal_equivalence": answer.get("unit") == "percent",
    }


def _fact_time_scope(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("fiscal_year"):
        return {
            "fiscal_year": int(row["fiscal_year"]),
            "fiscal_quarter": row.get("fiscal_quarter"),
            "basis": "fiscal_year",
        }
    if row.get("calendar_year") and str(row.get("frequency") or "").lower() == "annual":
        return {"calendar_year": int(row["calendar_year"]), "basis": "calendar_year"}
    period = row.get("period_end") or row.get("as_of_date")
    return (
        {"observation_date": str(period), "basis": "observation_date"} if period else {}
    )


def _period_label(scope: dict[str, Any]) -> str:
    if scope.get("fiscal_year"):
        quarter = (
            f" {scope['fiscal_quarter']}"
            if scope.get("fiscal_quarter") not in {None, "FY"}
            else ""
        )
        return f"fiscal year {scope['fiscal_year']}{quarter}"
    if scope.get("calendar_year"):
        return f"calendar year {scope['calendar_year']}"
    if scope.get("year"):
        prefix = (
            "fiscal year" if scope.get("basis") == "fiscal_year" else "calendar year"
        )
        return f"{prefix} {scope['year']}"
    return str(
        scope.get("observation_date") or scope.get("end_date") or "the stated period"
    )


def _previous_period_label(scope: dict[str, Any]) -> str:
    if scope.get("previous_year"):
        prefix = (
            "fiscal year" if scope.get("basis") == "fiscal_year" else "calendar year"
        )
        return f"{prefix} {scope['previous_year']}"
    if scope.get("previous_quarter"):
        return f"{scope.get('fiscal_year')} {scope['previous_quarter']}"
    return str(
        scope.get("start_year") or scope.get("start_date") or "the previous period"
    )


def _semantic_slots_complete(row: dict[str, Any]) -> bool:
    semantics = row["canonical_semantics"]
    if not row["time_scope"]:
        return False
    if row["task_subtype"] != "multi_condition_screening" and not row.get("unit"):
        return False
    if row["task_subtype"] in SCOPE_DERIVED | {"share"} and not semantics.get(
        "scope_definition"
    ):
        return False
    return bool(
        row["source_fact_ids"]
        and (row["metric_ids"] or row["task_subtype"] == "multi_condition_screening")
    )


def _entity_names_from_semantics(
    semantics: dict[str, Any], entity_ids: list[str]
) -> dict[str, str]:
    names = dict(semantics.get("entity_names") or {})
    if semantics.get("entity_id") and semantics.get("entity_name"):
        names[semantics["entity_id"]] = semantics["entity_name"]
    return {entity_id: names.get(entity_id, entity_id) for entity_id in entity_ids}


def _metric_names_from_semantics(
    semantics: dict[str, Any], metric_ids: list[str]
) -> dict[str, str]:
    names = dict(semantics.get("metric_names") or {})
    if semantics.get("metric_id") and semantics.get("metric_name"):
        names[semantics["metric_id"]] = semantics["metric_name"]
    return {
        metric_id: names.get(metric_id, metric_id.replace("_", " "))
        for metric_id in metric_ids
    }


def _task_family(derived_type: str) -> str:
    if derived_type in SIMPLE_DERIVED:
        return "calculation"
    if derived_type in TEMPORAL_DERIVED:
        return "temporal_investigation"
    if derived_type == "multi_condition_screening":
        return "scope_screening"
    return "scope_comparison"


def _difficulty(derived_type: str, input_count: int, entity_count: int) -> str:
    score = 1 if input_count == 2 else 2 if input_count <= 5 else 3
    if derived_type in TEMPORAL_DERIVED:
        score += 2
    if entity_count > 1:
        score += 2
    if derived_type in SCOPE_DERIVED:
        score += 3
    if derived_type == "multi_condition_screening":
        score += 2
    return (
        "easy"
        if score <= 2
        else "medium"
        if score <= 5
        else "hard"
        if score <= 8
        else "expert"
    )


def _qa_policy(config: dict[str, Any]) -> dict[str, Any]:
    configured = config.get("qa", {})
    quotas = configured.get("quotas", {})
    defaults = {
        "single_fact_financial": 20000,
        "single_fact_macro": 10000,
        "single_fact_fred": 5000,
    }
    derived_defaults = {
        "difference": 9000,
        "yoy_growth": 9000,
        "qoq_growth": 7000,
        "ratio": 5000,
        "share": 3000,
        "multi_year_argmax": 3000,
        "multi_year_argmin": 3000,
        "industry_ranking": 1600,
        "industry_argmax": 1200,
        "industry_argmin": 1200,
        "ranking": 150,
        "argmax": 150,
        "argmin": 150,
        "rolling_max": 50,
        "rolling_min": 50,
        "macro_time_series_argmax": 33,
        "macro_time_series_argmin": 33,
        "time_series_argmax": 17,
        "time_series_argmin": 17,
        "multi_condition_screening": 100,
        "long_window_return": 10,
    }
    return {
        "quotas": {key: int(quotas.get(key, value)) for key, value in defaults.items()},
        "derived_quotas": {
            key: int(configured.get("derived_quotas", {}).get(key, value))
            for key, value in derived_defaults.items()
        },
        "language": "en",
        "forecast_policy": "exclude_historical_questions",
        "generation_method": "deterministic_template",
    }


def _seed_templates(db: DBProtocol) -> None:
    columns = [
        "template_id",
        "task_family",
        "source_type",
        "entity_type",
        "metric_category",
        "period_type",
        "language",
        "template_text",
        "required_slots",
        "answer_type",
        "difficulty_base",
        "is_active",
    ]
    rows = [
        {
            **item,
            "source_type": item.get("source_type"),
            "entity_type": item.get("entity_type"),
            "metric_category": item.get("metric_category"),
            "period_type": item.get("period_type"),
            "is_active": True,
        }
        for item in TEMPLATES
    ]
    insert_rows(db, "qa_templates", rows, columns, {"required_slots"})


def _new_build_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"qa_build_{stamp}_{uuid.uuid4().hex[:8]}"


def _kg_build(db: DBProtocol, kg_build_id: str) -> dict[str, Any]:
    row = db.fetchone("SELECT * FROM kg_builds WHERE kg_build_id = ?", (kg_build_id,))
    if not row:
        raise RuntimeError(f"Unknown KG build: {kg_build_id}")
    return dict(row)


def _qa_build(db: DBProtocol, qa_build_id: str) -> dict[str, Any]:
    row = db.fetchone("SELECT * FROM qa_builds WHERE qa_build_id = ?", (qa_build_id,))
    if not row:
        raise RuntimeError(f"Unknown QA build: {qa_build_id}")
    out = dict(row)
    out["notes"] = json_value(out.get("notes"), {})
    return out


def _decode_candidate(row: dict[str, Any]) -> dict[str, Any]:
    for key in _candidate_json_columns():
        row[key] = json_value(
            row.get(key),
            [] if key.endswith("_ids") or key == "rejection_reasons" else {},
        )
    return row


def _decode_validation_row(row: dict[str, Any]) -> dict[str, Any]:
    for key in _candidate_json_columns() | _sample_json_columns():
        if key in row:
            row[key] = json_value(row.get(key), [] if key.endswith("_ids") else {})
    row["metric_ids"] = row["canonical_semantics"].get("metric_ids") or (
        [row["canonical_semantics"].get("metric_id")]
        if row["canonical_semantics"].get("metric_id")
        else []
    )
    row["time_scope"] = row["canonical_semantics"].get("time_scope") or {}
    row["unit"] = row["answer_payload"].get("unit")
    return row


def _candidate_json_columns() -> set[str]:
    return {
        "entity_ids",
        "metric_ids",
        "time_scope",
        "entity_scope",
        "source_fact_ids",
        "source_derived_ids",
        "source_document_ids",
        "raw_object_ids",
        "canonical_semantics",
        "answer_payload",
        "kg_path",
        "rejection_reasons",
    }


def _sample_json_columns() -> set[str]:
    return {"answer_value", "rubric", "source_metadata"}


def _evidence_json_columns() -> set[str]:
    return {
        "ordered_node_ids",
        "ordered_edge_ids",
        "source_fact_ids",
        "source_derived_ids",
        "raw_object_ids",
        "source_document_ids",
    }


def _db_json(db: DBProtocol, value: Any) -> Any:
    if db.__class__.__name__ == "PostgresMetadataDB":
        from psycopg.types.json import Jsonb

        return Jsonb(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _scalar(db: DBProtocol, sql: str, params: list[Any]) -> int:
    row = db.fetchone(sql, params)
    return int(row["c"] if row else 0)


def _group_counts(
    db: DBProtocol,
    table: str,
    build_column: str,
    build_id: str,
    group_column: str,
) -> dict[str, int]:
    rows = db.fetchall(
        f"SELECT {group_column}, COUNT(*) AS c FROM {table} WHERE {build_column} = ? GROUP BY {group_column} ORDER BY {group_column}",
        (build_id,),
    )
    return {str(row[group_column]): int(row["c"]) for row in rows}


def _write_report(
    report: dict[str, Any], output_dir: str | None, stem: str
) -> dict[str, Any]:
    if not output_dir:
        return report
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"{stem}.json"
    md_path = out / f"{stem}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    lines = [f"# {stem.replace('_', ' ').title()}", ""]
    for key, value in report.items():
        lines.append(
            f"- **{key}**: `{json.dumps(value, ensure_ascii=False, default=str)}`"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report["written_files"] = [str(json_path), str(md_path)]
    return report


def _digest(*parts: Any) -> str:
    return hashlib.sha1(
        json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str).encode(
            "utf-8"
        )
    ).hexdigest()[:24]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value)) if value not in (None, "") else None
    except (InvalidOperation, ValueError):
        return None


def _number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def _format_value(value: Any) -> str:
    number = _decimal(value)
    if number is None:
        return str(value)
    return f"{number:,.6f}".rstrip("0").rstrip(".")


def _normalise_question(question: str) -> str:
    return " ".join(question.lower().split())


def _fact_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("period_end") or ""),
        str(row.get("fiscal_year") or row.get("calendar_year") or ""),
        str(row.get("fiscal_quarter") or ""),
    )


def _latest_year(scope: dict[str, Any]) -> int | None:
    for key in ["end_year", "year", "fiscal_year", "calendar_year"]:
        if scope.get(key):
            return int(scope[key])
    value = scope.get("end_date") or scope.get("observation_date")
    return int(str(value)[:4]) if value and str(value)[:4].isdigit() else None
