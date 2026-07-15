from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol
from finraw.kg_query import resolve_kg_build_id
from finraw.qa.difficulty import DIFFICULTY_POLICY, assess_difficulty, graph_features
from finraw.qa.graph_matcher import discover_pattern_matches, load_bound_facts
from finraw.qa.graph_patterns import get_pattern, pattern_manifest
from finraw.qa.operators import operator_registry
from finraw.qa.pattern_compiler import compile_pattern_proposal, compile_proposal_matches
from finraw.qa.pattern_mining import load_approved_proposals, mine_qa_patterns, mining_policy
from finraw.qa.plans import execute_plan, operation_depth
from finraw.qa.schema import ensure_qa_schema
from finraw.qa.store import chunks, execute_many, insert_rows, json_value
from finraw.qa.templates import TEMPLATES, template_for
from finraw.qa.verbalizer import realize_question


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
GRAPH_SCOPE_TASKS = {
    "filter_then_rank",
    "rank_then_secondary_lookup",
    "multi_factor_screening",
}
SUPPORTED_DERIVED = SIMPLE_DERIVED | TEMPORAL_DERIVED | SCOPE_DERIVED
GENERATOR_VERSION = "4.2.0"

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
    "template_manifest_hash",
    "pattern_manifest_hash",
    "operator_manifest_hash",
    "difficulty_policy_hash",
    "generator_version",
    "git_commit_sha",
    "split_policy_hash",
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
    "pattern_id",
    "pattern_version",
    "pattern_hash",
    "operation_plan_id",
    "operation_plan_hash",
    "mining_run_id",
    "pattern_proposal_id",
    "pattern_proposal_hash",
    "pattern_score",
    "graph_features",
    "difficulty_score",
    "answer_schema",
    "question_intent",
    "entity_ids",
    "metric_ids",
    "time_scope",
    "entity_scope",
    "source_fact_ids",
    "source_derived_ids",
    "source_document_ids",
    "raw_object_ids",
    "canonical_semantics",
    "derived_payload",
    "recomputed_payload",
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
    "template_id",
    "template_hash",
    "surface_form_id",
    "paraphrase_group_id",
    "linguistic_style",
    "graph_pattern_id",
    "operation_depth",
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
    "evidence_node_ids",
    "evidence_edges",
    "evidence_components",
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
PLAN_COLUMNS = [
    "plan_id",
    "qa_build_id",
    "candidate_id",
    "pattern_id",
    "pattern_version",
    "operator_dag",
    "input_bindings",
    "intermediate_results",
    "output_schema",
    "recompute_status",
    "validation_errors",
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
    _seed_graph_patterns(db)
    kg_build_id = resolve_kg_build_id(db, kg_build_id)
    kg = _kg_build(db, kg_build_id)
    if kg.get("status") != "success" or kg.get("quality_status") != "passed":
        raise RuntimeError(f"KG build is not QA eligible: {kg_build_id}")
    policy = _qa_policy(config)
    effective_mining_policy = mining_policy(config)
    mining_report = None
    if effective_mining_policy["enabled"] and effective_mining_policy["auto_run"]:
        mining_report = mine_qa_patterns(
            db,
            config,
            kg_build_id=kg_build_id,
            output_dir=output_dir,
        )
    mined_proposals = (
        load_approved_proposals(
            db,
            kg_build_id,
            limit=effective_mining_policy["max_proposals"],
        )
        if effective_mining_policy["enabled"]
        else []
    )
    mined_manifest = [
        {
            "proposal_id": proposal["proposal_id"],
            "proposal_hash": proposal["proposal_hash"],
            "motif_signature": proposal["motif_signature"],
            "total_score": proposal["total_score"],
        }
        for proposal in mined_proposals
    ]
    pattern_manifest_data = [*pattern_manifest(), *mined_manifest]
    operator_manifest_data = operator_registry()
    pattern_manifest_hash = _digest(pattern_manifest_data)
    operator_manifest_hash = _digest(operator_manifest_data)
    difficulty_policy_hash = _digest(DIFFICULTY_POLICY)
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
        "config_hash": _digest(
            policy,
            TEMPLATES,
            pattern_manifest_data,
            operator_manifest_data,
            DIFFICULTY_POLICY,
            GENERATOR_VERSION,
        ),
        "template_manifest_hash": _digest(TEMPLATES),
        "pattern_manifest_hash": pattern_manifest_hash,
        "operator_manifest_hash": operator_manifest_hash,
        "difficulty_policy_hash": difficulty_policy_hash,
        "generator_version": GENERATOR_VERSION,
        "git_commit_sha": _git_commit_sha(),
        "split_policy_hash": _digest(
            policy.get("split_policy"), policy.get("temporal_split")
        ),
        "status": "building_candidates",
        "started_at": _now(),
        "completed_at": None,
        "candidate_count": 0,
        "passed_count": 0,
        "sample_count": 0,
        "quality_status": "pending",
        "is_active": False,
        "superseded_by": None,
        "notes": {
            "policy": policy,
            "generation": "graph_path_driven_deterministic",
            "generator_version": GENERATOR_VERSION,
            "template_manifest_hash": _digest(TEMPLATES),
            "pattern_manifest_hash": pattern_manifest_hash,
            "operator_manifest_hash": operator_manifest_hash,
            "difficulty_policy_hash": difficulty_policy_hash,
            "git_worktree_dirty": _git_worktree_dirty(),
            "pattern_mining": {
                "policy": effective_mining_policy,
                "report": mining_report,
                "proposal_manifest": mined_manifest,
            },
        },
    }
    insert_rows(db, "qa_builds", [build], BUILD_COLUMNS, {"notes"})

    candidates: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    entity_names = {
        str(row["entity_id"]): str(row["canonical_name"])
        for row in db.fetchall(
            "SELECT entity_id, canonical_name FROM canonical_entities WHERE build_id = ?",
            (kg["input_entity_build_id"],),
        )
    }
    metric_names = {
        str(row["metric_id"]): str(row["canonical_name"])
        for row in db.fetchall(
            "SELECT metric_id, canonical_name FROM metrics WHERE build_id = ?",
            (kg["input_metric_build_id"],),
        )
    }
    raw_by_fact = {
        str(row["fact_id"]): str(row["raw_object_id"])
        for row in db.fetchall(
            "SELECT fact_id, raw_object_id FROM standardized_facts WHERE build_id = ? AND raw_object_id IS NOT NULL",
            (kg["input_fact_build_id"],),
        )
    }

    def flush() -> None:
        if not candidates:
            return
        insert_rows(
            db,
            "qa_candidates",
            candidates,
            CANDIDATE_COLUMNS,
            _candidate_json_columns(),
        )
        insert_rows(
            db,
            "qa_operation_plans",
            plans,
            PLAN_COLUMNS,
            _plan_json_columns(),
        )
        candidates.clear()
        plans.clear()

    def emit(candidate: dict[str, Any], plan: dict[str, Any] | None = None) -> None:
        candidates.append(candidate)
        if plan:
            plans.append(plan)
        counts[candidate["task_subtype"]] += 1
        for reason in candidate["rejection_reasons"]:
            rejected[reason] += 1
        if len(candidates) >= batch_size:
            flush()

    for pool_name, sources, quota in [
        (
            "single_fact_financial",
            ["sec_companyfacts"],
            policy["quotas"]["single_fact_financial"],
        ),
        (
            "single_fact_worldbank",
            ["worldbank_indicators"],
            policy["quotas"]["single_fact_worldbank"],
        ),
        (
            "single_fact_imf",
            ["imf_sdmx"],
            policy["quotas"]["single_fact_imf"],
        ),
        (
            "single_fact_fred",
            ["fred_observations"],
            policy["quotas"]["single_fact_fred"],
        ),
    ]:
        rows = _load_fact_pool(db, kg, sources, quota * 5)
        for row in _sample_fact_rows(rows, quota):
            emit(_fact_candidate(db, row, qa_build_id, kg_build_id, pool_name))

    scope_fact_cache: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = {}
    for derived_type, quota in policy["derived_quotas"].items():
        if derived_type not in SUPPORTED_DERIVED or quota <= 0:
            continue
        for row in _load_derived_pool(db, kg, derived_type, quota):
            if derived_type in {"share", "ranking", "industry_ranking"}:
                row = _with_scope_inputs(db, kg, row, scope_fact_cache)
            emit(
                _derived_candidate(
                    db,
                    row,
                    qa_build_id,
                    kg_build_id,
                    entity_names,
                    metric_names,
                    raw_by_fact,
                )
            )

    graph_policy = policy.get("graph_patterns", {})
    if graph_policy.get("enabled"):
        for pattern_id, quota in graph_policy.get("quotas", {}).items():
            if int(quota) <= 0:
                continue
            pattern = get_pattern(pattern_id)
            if not pattern.is_active:
                continue
            matches = discover_pattern_matches(
                db,
                kg,
                pattern_id,
                limit=int(quota),
                policy=graph_policy.get("comparability"),
            )
            fact_map = load_bound_facts(
                db,
                kg["input_fact_build_id"],
                [fact_id for match in matches for fact_id in match["fact_ids"]],
            )
            for match in matches:
                candidate, plan = _graph_pattern_candidate(
                    db,
                    match,
                    pattern,
                    fact_map,
                    qa_build_id,
                    kg_build_id,
                    entity_names,
                    metric_names,
                )
                emit(candidate, plan)

    if effective_mining_policy["enabled"]:
        for proposal in mined_proposals:
            pattern = compile_pattern_proposal(proposal)
            matches = compile_proposal_matches(
                proposal,
                limit=effective_mining_policy["max_candidates_per_proposal"],
            )
            fact_map = load_bound_facts(
                db,
                kg["input_fact_build_id"],
                [fact_id for match in matches for fact_id in match["fact_ids"]],
            )
            for match in matches:
                candidate, plan = _graph_pattern_candidate(
                    db,
                    match,
                    pattern,
                    fact_map,
                    qa_build_id,
                    kg_build_id,
                    entity_names,
                    metric_names,
                    proposal=proposal,
                )
                emit(candidate, plan)

    flush()

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
    build_row = db.fetchone("SELECT notes FROM qa_builds WHERE qa_build_id = ?", (qa_build_id,))
    notes = json_value(build_row["notes"] if build_row else None, {})
    notes.update(
        {
            "policy": policy,
            "task_counts": persisted_task_counts,
            "emitted_task_counts": dict(counts),
            "rejection_counts": dict(rejected),
        }
    )
    db.execute(
        "UPDATE qa_builds SET status = ?, candidate_count = ?, notes = ? WHERE qa_build_id = ?",
        (
            "candidates_built",
            candidate_count,
            _db_json(db, notes),
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
        """
        SELECT c.*, p.operator_dag AS operation_plan
        FROM qa_candidates c
        LEFT JOIN qa_operation_plans p ON p.plan_id = c.operation_plan_id
        WHERE c.qa_build_id = ? AND c.eligibility_status = 'eligible'
        ORDER BY c.candidate_id
        """,
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
        SELECT s.*, c.canonical_semantics, c.derived_payload,
               c.recomputed_payload, c.answer_payload, c.kg_path,
               c.source_fact_ids, c.source_derived_ids, c.raw_object_ids,
               c.pattern_id, c.pattern_version, c.operation_plan_id,
               c.graph_features, c.answer_schema, c.question_intent,
               c.mining_run_id, c.pattern_proposal_id,
               c.pattern_proposal_hash, c.pattern_score,
               mp.status AS stored_proposal_status,
               mp.proposal_hash AS stored_proposal_hash,
               mp.total_score AS stored_proposal_score,
               mp.kg_build_id AS proposal_kg_build_id,
               p.operator_dag, p.input_bindings, p.intermediate_results,
               p.output_schema, p.recompute_status AS plan_recompute_status,
               p.validation_errors AS plan_validation_errors
        FROM qa_samples s
        JOIN qa_candidates c ON c.candidate_id = s.candidate_id
        LEFT JOIN qa_operation_plans p ON p.plan_id = c.operation_plan_id
        LEFT JOIN qa_pattern_proposals mp ON mp.proposal_id = c.pattern_proposal_id
        WHERE s.qa_build_id = ? AND s.validation_status = 'pending'
        ORDER BY s.qa_id
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
    existing_nodes = _load_graph_nodes(db, build["kg_build_id"], node_ids)
    existing_edges = _load_graph_edges(db, build["kg_build_id"], edge_ids)
    checks: list[dict[str, Any]] = []
    status_updates: list[tuple[str, str]] = []
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
    total = _scalar(
        db, "SELECT COUNT(*) AS c FROM qa_samples WHERE qa_build_id = ?", [qa_build_id]
    )
    passed = _scalar(
        db,
        "SELECT COUNT(*) AS c FROM qa_samples WHERE qa_build_id = ? AND validation_status = 'passed'",
        [qa_build_id],
    )
    failed = _scalar(
        db,
        "SELECT COUNT(*) AS c FROM qa_samples WHERE qa_build_id = ? AND validation_status = 'rejected'",
        [qa_build_id],
    )
    pending = total - passed - failed
    failure_counts = {
        str(item["check_name"]): int(item["c"])
        for item in db.fetchall(
            """
            SELECT check_name, COUNT(*) AS c
            FROM qa_quality_checks
            WHERE qa_build_id = ? AND check_status <> 'passed'
            GROUP BY check_name ORDER BY check_name
            """,
            (qa_build_id,),
        )
    }
    quality_status = (
        "passed"
        if passed > 0 and failed == 0 and pending == 0
        else ("partial" if passed > 0 else "failed")
    )
    db.execute(
        "UPDATE qa_builds SET status = ?, passed_count = ?, quality_status = ?, completed_at = ? WHERE qa_build_id = ?",
        ("validated", passed, quality_status, _now(), qa_build_id),
    )
    report = {
        "qa_build_id": qa_build_id,
        "kg_build_id": build["kg_build_id"],
        "sample_count": total,
        "resumed_sample_count": len(rows),
        "passed_count": passed,
        "rejected_count": failed,
        "pending_count": pending,
        "pass_rate": passed / total if total else 0,
        "quality_status": quality_status,
        "failure_counts": failure_counts,
    }
    return _write_report(report, output_dir, "qa_quality_report")


def split_qa_samples(
    db: DBProtocol,
    qa_build_id: str,
    *,
    output_dir: str | None = None,
    activate: bool = True,
) -> dict[str, Any]:
    ensure_qa_schema(db)
    build = _qa_build(db, qa_build_id)
    policy = build.get("notes", {}).get("policy", {})
    cutoff_year = int(policy.get("temporal_split", {}).get("cutoff_year", 2025))
    db.execute(
        "UPDATE qa_samples SET split = NULL WHERE qa_build_id = ? AND validation_status <> 'passed'",
        (qa_build_id,),
    )
    rows = [
        dict(row)
        for row in db.fetchall(
            """
        SELECT s.qa_id, s.qa_group_id, s.semantic_cluster_id, s.task_subtype,
               c.entity_ids, c.time_scope
        FROM qa_samples s JOIN qa_candidates c ON c.candidate_id = s.candidate_id
        WHERE s.qa_build_id = ? AND s.validation_status = 'passed'
        ORDER BY s.semantic_cluster_id, s.qa_group_id, s.qa_id
        """,
            (qa_build_id,),
        )
    ]
    cluster_split: dict[str, str] = {}
    split_counts: Counter[str] = Counter()
    task_counts: Counter[str] = Counter()
    challenge = SCOPE_DERIVED | GRAPH_SCOPE_TASKS | {
        "rolling_max",
        "rolling_min",
        "multi_period_average",
        "temporal_peak_followup",
    }
    split_updates: list[tuple[str, str]] = []
    for row in rows:
        cluster = row.get("semantic_cluster_id") or row["qa_group_id"]
        if cluster not in cluster_split:
            bucket = (
                int(hashlib.sha1(cluster.encode("utf-8")).hexdigest()[:8], 16) % 100
            )
            entities = json_value(row.get("entity_ids"), [])
            time_scope = json_value(row.get("time_scope"), {})
            entity_holdout = any(
                int(hashlib.sha1(str(entity).encode("utf-8")).hexdigest()[:8], 16) % 20
                == 0
                for entity in entities
            )
            if row["task_subtype"] in challenge:
                split = _complex_split(bucket)
            elif entity_holdout:
                split = "test_entity_holdout"
            elif _latest_year(time_scope) and _latest_year(time_scope) >= cutoff_year:
                split = "test_temporal_holdout"
            elif bucket < 80:
                split = "train"
            elif bucket < 90:
                split = "dev"
            else:
                split = "test_standard"
            cluster_split[cluster] = split
        split_counts[cluster_split[cluster]] += 1
        task_counts[row["task_subtype"]] += 1
        split_updates.append((cluster_split[cluster], row["qa_id"]))
    execute_many(db, "UPDATE qa_samples SET split = ? WHERE qa_id = ?", split_updates)
    gate_policy = policy.get("quality_gate", {})
    sample_count = int(build.get("sample_count") or 0)
    pass_rate = len(rows) / sample_count if sample_count else 0.0
    failures = []
    minimum_rate = float(gate_policy.get("minimum_overall_pass_rate", 0.95))
    if pass_rate < minimum_rate:
        failures.append(f"pass_rate={pass_rate:.6f} < {minimum_rate:.6f}")
    for task, minimum in gate_policy.get("critical_tasks", {}).items():
        if task_counts.get(task, 0) < int(minimum):
            failures.append(
                f"critical_task_{task}={task_counts.get(task, 0)} < {int(minimum)}"
            )
    graph_sample_counts = {
        str(item["graph_pattern_id"]): int(item["c"])
        for item in db.fetchall(
            """
            SELECT graph_pattern_id, COUNT(*) AS c
            FROM qa_samples
            WHERE qa_build_id = ? AND validation_status = 'passed'
              AND graph_pattern_id IS NOT NULL
            GROUP BY graph_pattern_id
            """,
            (qa_build_id,),
        )
    }
    graph_candidate_stats = {
        str(item["pattern_id"]): {
            "candidate_count": int(item["candidate_count"]),
            "eligible_count": int(item["eligible_count"]),
        }
        for item in db.fetchall(
            """
            SELECT pattern_id, COUNT(*) AS candidate_count,
                   SUM(CASE WHEN eligibility_status = 'eligible' THEN 1 ELSE 0 END)
                       AS eligible_count
            FROM qa_candidates
            WHERE qa_build_id = ? AND pattern_id IS NOT NULL
            GROUP BY pattern_id
            """,
            (qa_build_id,),
        )
    }
    for pattern_id, minimum in gate_policy.get(
        "minimum_graph_pattern_samples", {}
    ).items():
        observed = graph_sample_counts.get(pattern_id, 0)
        if observed < int(minimum):
            failures.append(
                f"graph_pattern_{pattern_id}={observed} < {int(minimum)}"
            )
    minimum_eligibility = gate_policy.get("minimum_graph_pattern_eligibility_rate")
    if minimum_eligibility is not None:
        minimum_eligibility = float(minimum_eligibility)
        for pattern_id, stats in graph_candidate_stats.items():
            count = stats["candidate_count"]
            rate = stats["eligible_count"] / count if count else 0.0
            if rate < minimum_eligibility:
                failures.append(
                    f"graph_pattern_eligibility_{pattern_id}={rate:.6f} "
                    f"< {minimum_eligibility:.6f}"
                )
    graph_sample_count = sum(graph_sample_counts.values())
    graph_feature_coverage = graph_sample_count / len(rows) if rows else 0.0
    minimum_graph_coverage = gate_policy.get("minimum_graph_feature_coverage")
    if minimum_graph_coverage is not None and graph_feature_coverage < float(
        minimum_graph_coverage
    ):
        failures.append(
            f"graph_feature_coverage={graph_feature_coverage:.6f} "
            f"< {float(minimum_graph_coverage):.6f}"
        )
    plan_rows = db.fetchall(
        """
        SELECT p.operator_dag
        FROM qa_operation_plans p
        JOIN qa_samples s ON s.candidate_id = p.candidate_id
        WHERE s.qa_build_id = ? AND s.validation_status = 'passed'
        """,
        (qa_build_id,),
    )
    operation_sequences = {
        " -> ".join(
            str(step.get("operator"))
            for step in json_value(item["operator_dag"], {}).get("operators", [])
        )
        for item in plan_rows
    }
    operation_sequences.discard("")
    minimum_sequences = gate_policy.get("minimum_unique_operation_sequences")
    if minimum_sequences is not None and len(operation_sequences) < int(
        minimum_sequences
    ):
        failures.append(
            f"unique_operation_sequences={len(operation_sequences)} "
            f"< {int(minimum_sequences)}"
        )
    critical_checks = _scalar(
        db,
        """
        SELECT COUNT(*) AS c FROM qa_quality_checks
        WHERE qa_build_id = ? AND check_status <> 'passed'
          AND check_name IN (
              'structure', 'fact_membership', 'evidence_path', 'evidence_semantics',
              'semantic_slots', 'independent_recompute', 'scope_completeness',
              'no_answer_leakage', 'graph_pattern_match',
              'operator_input_complete', 'operator_type_valid',
              'intermediate_result_recompute', 'operation_trace_coverage',
              'pattern_proposal_match', 'question_slot_roundtrip',
              'question_answer_isolation'
          )
        """,
        [qa_build_id],
    )
    max_critical = int(gate_policy.get("max_critical_check_failures", 0))
    if critical_checks > max_critical:
        failures.append(f"critical_check_failures={critical_checks} > {max_critical}")
    gate_passed = bool(rows) and not failures
    notes = dict(build.get("notes") or {})
    notes["build_gate"] = {
        "status": "passed" if gate_passed else "failed",
        "failures": failures,
        "pass_rate": pass_rate,
        "critical_check_failures": critical_checks,
        "graph_pattern_sample_counts": graph_sample_counts,
        "graph_pattern_candidate_stats": graph_candidate_stats,
        "graph_feature_coverage": graph_feature_coverage,
        "unique_operation_sequences": sorted(operation_sequences),
        "temporal_cutoff_year": cutoff_year,
        "activation_requested": activate,
    }
    if gate_passed:
        db.execute(
            "UPDATE qa_builds SET status = ?, is_active = ?, notes = ? WHERE qa_build_id = ?",
            ("ready", activate, _db_json(db, notes), qa_build_id),
        )
        if activate:
            old = db.fetchall(
                "SELECT qa_build_id FROM qa_builds WHERE is_active = ? AND qa_build_id <> ?",
                (True, qa_build_id),
            )
            for item in old:
                db.execute(
                    "UPDATE qa_builds SET is_active = ?, superseded_by = ? WHERE qa_build_id = ?",
                    (False, qa_build_id, item["qa_build_id"]),
                )
    else:
        db.execute(
            "UPDATE qa_builds SET status = ?, is_active = ?, notes = ? WHERE qa_build_id = ?",
            ("quality_failed", False, _db_json(db, notes), qa_build_id),
        )
    report = {
        "qa_build_id": qa_build_id,
        "passed_sample_count": len(rows),
        "semantic_cluster_count": len(cluster_split),
        "temporal_cutoff_year": cutoff_year,
        "split_counts": dict(sorted(split_counts.items())),
        "task_counts": dict(sorted(task_counts.items())),
        "build_gate_status": "passed" if gate_passed else "failed",
        "build_gate_failures": failures,
        "activated": gate_passed and activate,
    }
    return _write_report(report, output_dir, "qa_split_report")


def _complex_split(bucket: int) -> str:
    if bucket < 70:
        return "train_complex"
    if bucket < 80:
        return "dev_complex"
    return "test_complex"


def build_qa(
    db: DBProtocol,
    config: dict[str, Any],
    *,
    kg_build_id: str | None = None,
    output_dir: str = "data/audit/qa_build",
    batch_size: int = 2000,
    activate: bool = True,
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
    split = split_qa_samples(
        db, qa_build_id, output_dir=output_dir, activate=activate
    )
    report = {
        "qa_build_id": qa_build_id,
        "candidate": candidate,
        "generation": generated,
        "quality": quality,
        "split": split,
    }
    return _write_report(report, output_dir, "qa_build_report")


def _fact_candidate(
    db: DBProtocol,
    row: dict[str, Any],
    qa_build_id: str,
    kg_build_id: str,
    pool_name: str,
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
    path = _kg_path_from_graph(db, kg_build_id, fact_ids=[fact_id])
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


def _derived_payload_from_row(row: dict[str, Any]) -> dict[str, Any]:
    time_scope = json_value(row.get("time_scope"), {})
    entity_scope = json_value(row.get("entity_scope"), {})
    output_table = json_value(row.get("output_table"), [])
    return {
        "value": str(row.get("output_value"))
        if row.get("output_value") is not None
        else None,
        "table": output_table,
        "unit": row.get("unit"),
        "currency": row.get("currency"),
        "tolerance": str(row.get("tolerance") or 0),
        "result_period": time_scope.get("result_year")
        or time_scope.get("result_date"),
        "winning_entity_id": entity_scope.get("entity_id")
        if str(row.get("derived_type"))
        in {"argmax", "argmin", "industry_argmax", "industry_argmin"}
        else None,
    }


def _derived_candidate(
    db: DBProtocol,
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
    row["derived_payload"] = json_value(row.get("derived_payload"), {})
    row["recomputed_payload"] = json_value(row.get("recomputed_payload"), {})
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
    derived_payload = row["derived_payload"] or _derived_payload_from_row(row)
    recomputed_payload = row["recomputed_payload"] or derived_payload
    answer = recomputed_payload if row.get("scope_recomputed") else derived_payload
    if answer.get("value") is None and not answer.get("table"):
        reasons.append("missing_answer")
    if derived_type == "share" and not row.get("share_scope_complete"):
        reasons.append("incomplete_share_scope_inputs")
    if derived_type in {"ranking", "industry_ranking"} and not row.get(
        f"{derived_type}_scope_complete"
    ):
        reasons.append(f"incomplete_{derived_type}_scope_inputs")
    if row.get("scope_recomputed") and not row.get("derived_recompute_match"):
        reasons.append("qa_recompute_mismatch")
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
        "entity_scope": entity_scope,
        "time_scope": row["time_scope"],
        "scope_type": row.get("scope_type"),
        "scope_id": row.get("scope_id"),
        "scope_definition": row.get("scope_definition"),
        "calculation_code": row.get("calculation_code"),
        "top_k": len(answer.get("table") or [])
        if derived_type in {"ranking", "industry_ranking"}
        else None,
        "scope_input_complete": bool(row.get(f"{derived_type}_scope_complete"))
        if derived_type in {"share", "ranking", "industry_ranking"}
        else None,
        "answer_basis": "pinned_scope_fact_recompute"
        if row.get("scope_recomputed")
        else "pinned_derived_fact",
        "source_derived_output_value": derived_payload.get("value"),
        "source_derived_output_table": derived_payload.get("table")
        if derived_type in {"ranking", "industry_ranking"}
        else [],
        "derived_recompute_match": bool(row.get("derived_recompute_match", True)),
        "derived_input_fact_ids": row.get(
            "derived_input_fact_ids", row["input_fact_ids"]
        ),
        "expected_table": row["output_table"]
        if derived_type == "multi_condition_screening"
        else [],
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
        "derived_payload": derived_payload,
        "recomputed_payload": recomputed_payload,
        "answer_payload": answer,
        "kg_path": _kg_path_from_graph(
            db,
            kg_build_id,
            derived_id=row["derived_id"],
            fact_ids=row["input_fact_ids"],
            supplemental_fact_ids=[
                fact_id
                for fact_id in row["input_fact_ids"]
                if fact_id
                not in row.get("derived_input_fact_ids", row["input_fact_ids"])
            ],
        ),
        "eligibility_status": "eligible" if not reasons else "rejected",
        "rejection_reasons": reasons,
    }


def _graph_pattern_candidate(
    db: DBProtocol,
    match: dict[str, Any],
    pattern: Any,
    fact_map: dict[str, dict[str, Any]],
    qa_build_id: str,
    kg_build_id: str,
    entity_name_map: dict[str, str],
    metric_name_map: dict[str, str],
    proposal: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    fact_ids = [str(fact_id) for fact_id in match["fact_ids"]]
    facts = [fact_map[fact_id] for fact_id in fact_ids if fact_id in fact_map]
    reasons = []
    if len(facts) != len(fact_ids):
        reasons.append("graph_pattern_missing_bound_fact")
    operator_dag = json.loads(json.dumps(pattern.operator_template))
    if match.get("operator_params") and operator_dag.get("operators"):
        operator_dag["operators"][0]["params"] = dict(match["operator_params"])
    step_params = match.get("operator_step_params") or {}
    for step in operator_dag.get("operators") or []:
        if step.get("step_id") in step_params:
            step["params"] = {
                **dict(step.get("params") or {}),
                **dict(step_params[str(step["step_id"])]),
            }
    execution = execute_plan(operator_dag, match["input_bindings"], fact_map)
    if execution.status != "passed":
        reasons.append("operation_plan_execution_failed")
    answer = execution.output
    if answer.get("value") is None and not answer.get("table") and not answer.get("rows"):
        reasons.append("missing_answer")

    subtype = pattern.task_subtype
    if subtype in {"multi_period_average", "temporal_peak_followup"}:
        time_scope = {
            "start_year": match.get("start_period"),
            "end_year": match.get("end_period"),
            "basis": "multi_period",
            "frequency": match.get("frequency"),
            "observation_count": match.get("observation_count"),
        }
    elif match.get("period") is not None:
        time_scope = _match_time_scope(match)
    else:
        time_scope = _fact_time_scope(facts[0]) if facts else {}
    intent_index = int(_digest(pattern.pattern_id, match)[:8], 16) % len(
        pattern.question_intents
    )
    question_intent = pattern.question_intents[intent_index]
    entity_ids = sorted(set(match["entity_ids"]))
    metric_ids = sorted(set(match["metric_ids"]))
    semantics = {
        "operation": subtype,
        "graph_pattern_id": pattern.pattern_id,
        "graph_pattern_version": pattern.pattern_version,
        "question_intent": question_intent,
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
        "metric_period_type": facts[0].get("metric_period_type") if facts else None,
        "time_scope": time_scope,
        "input_bindings": match["input_bindings"],
        "operation_plan": operator_dag,
        "answer_schema": pattern.answer_schema,
        "comparability": match.get("comparability") or {},
        "scope_type": match.get("scope_type"),
        "scope_definition": match.get("scope_definition"),
        "observation_count": match.get("observation_count"),
        "frequency": match.get("frequency"),
        "primary_metric_id": match.get("primary_metric_id"),
        "secondary_metric_id": match.get("secondary_metric_id"),
        "industry": match.get("industry"),
        "financial_scope": match.get("financial_scope") or {},
        "mining_run_id": proposal.get("mining_run_id") if proposal else None,
        "pattern_proposal_id": proposal.get("proposal_id") if proposal else None,
        "pattern_proposal_hash": proposal.get("proposal_hash") if proposal else None,
        "pattern_score": float(proposal["total_score"]) if proposal else None,
        "growth_threshold_pct": (
            match.get("operator_step_params", {})
            .get("growth_filter", {})
            .get("value")
            or match.get("operator_step_params", {})
            .get("answer", {})
            .get("growth_min_pct")
        ),
        "debt_ratio_max_pct": (
            match.get("operator_step_params", {})
            .get("answer", {})
            .get("debt_max_pct")
        ),
    }
    if len(entity_ids) == 1:
        semantics["entity_id"] = entity_ids[0]
        semantics["entity_name"] = entity_name_map.get(entity_ids[0], entity_ids[0])
    evidence = _kg_path_from_graph(db, kg_build_id, fact_ids=fact_ids)
    features = graph_features(
        source_fact_ids=fact_ids,
        source_derived_ids=[],
        entity_ids=entity_ids,
        metric_ids=metric_ids,
        facts=facts,
        evidence=evidence,
        operation_plan=operator_dag,
        answer_payload=answer,
        semantic_constraint_count=len(pattern.semantic_constraints),
    )
    difficulty, score = assess_difficulty(features, pattern.difficulty_base)
    stable = "qac_" + _digest(
        pattern.pattern_id,
        pattern.pattern_version,
        semantics,
        fact_ids,
    )
    candidate_id = f"{stable}__{qa_build_id}"
    plan_id = "qaplan_" + _digest(stable, operator_dag, match["input_bindings"])
    pattern_hash = _digest(pattern.as_row())
    operation_plan_hash = _digest(operator_dag, match["input_bindings"])
    raw_object_ids = sorted(
        {
            str(fact["raw_object_id"])
            for fact in facts
            if fact.get("raw_object_id")
        }
    )
    candidate = {
        "candidate_id": candidate_id,
        "stable_candidate_id": stable,
        "qa_build_id": qa_build_id,
        "task_family": pattern.pattern_family,
        "task_subtype": subtype,
        "difficulty": difficulty,
        "pattern_id": pattern.pattern_id,
        "pattern_version": pattern.pattern_version,
        "pattern_hash": pattern_hash,
        "operation_plan_id": plan_id,
        "operation_plan_hash": operation_plan_hash,
        "mining_run_id": proposal.get("mining_run_id") if proposal else None,
        "pattern_proposal_id": proposal.get("proposal_id") if proposal else None,
        "pattern_proposal_hash": proposal.get("proposal_hash") if proposal else None,
        "pattern_score": float(proposal["total_score"]) if proposal else None,
        "graph_features": features,
        "difficulty_score": score,
        "answer_schema": pattern.answer_schema,
        "question_intent": question_intent,
        "entity_ids": entity_ids,
        "metric_ids": metric_ids,
        "time_scope": time_scope,
        "entity_scope": {
            "entity_ids": entity_ids,
            "scope_type": match.get("scope_type") or "graph_pattern_binding",
            "scope_definition": match.get("scope_definition"),
        },
        "source_fact_ids": fact_ids,
        "source_derived_ids": [],
        "source_document_ids": [],
        "raw_object_ids": raw_object_ids,
        "canonical_semantics": semantics,
        "derived_payload": {},
        "recomputed_payload": answer,
        "answer_payload": answer,
        "kg_path": evidence,
        "eligibility_status": "eligible" if not reasons else "rejected",
        "rejection_reasons": reasons,
    }
    plan = {
        "plan_id": plan_id,
        "qa_build_id": qa_build_id,
        "candidate_id": candidate_id,
        "pattern_id": pattern.pattern_id,
        "pattern_version": pattern.pattern_version,
        "operator_dag": operator_dag,
        "input_bindings": match["input_bindings"],
        "intermediate_results": execution.intermediate_results,
        "output_schema": pattern.answer_schema,
        "recompute_status": execution.status,
        "validation_errors": execution.errors,
    }
    return candidate, plan


def _sample_from_candidate(
    candidate: dict[str, Any], build: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    semantics = candidate["canonical_semantics"]
    entity_names = _entity_names_from_semantics(semantics, candidate["entity_ids"])
    metric_names = _metric_names_from_semantics(semantics, candidate["metric_ids"])
    slots = _question_slots(candidate, entity_names, metric_names)
    template = template_for(
        candidate["task_subtype"],
        semantics.get("metric_period_type"),
        candidate.get("stable_candidate_id"),
    )
    canonical_question = template["template_text"].format(**slots)
    generation_policy = (
        build.get("notes", {}).get("policy", {}).get("question_generation", {})
    )
    realization = realize_question(
        canonical_question,
        semantics=semantics,
        immutable_slots=slots,
        required_slots=list(template.get("required_slots") or []),
        config=generation_policy,
    )
    question = realization.question
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
        "template_id": template["template_id"],
        "template_hash": _digest(template),
        "surface_form_id": template["template_id"],
        "paraphrase_group_id": "qapg_" + _digest(candidate["stable_candidate_id"]),
        "linguistic_style": candidate.get("question_intent") or "canonical",
        "graph_pattern_id": candidate.get("pattern_id"),
        "operation_depth": operation_depth(candidate.get("operation_plan") or {}),
        "task_family": candidate["task_family"],
        "task_subtype": candidate["task_subtype"],
        "difficulty": candidate["difficulty"],
        "language": "en",
        "question": question,
        "canonical_question": canonical_question,
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
            "derived_payload": candidate.get("derived_payload"),
            "recomputed_payload": candidate.get("recomputed_payload"),
            "graph_pattern_id": candidate.get("pattern_id"),
            "pattern_hash": candidate.get("pattern_hash"),
            "operation_plan_id": candidate.get("operation_plan_id"),
            "operation_plan_hash": candidate.get("operation_plan_hash"),
            "mining_run_id": candidate.get("mining_run_id"),
            "pattern_proposal_id": candidate.get("pattern_proposal_id"),
            "pattern_proposal_hash": candidate.get("pattern_proposal_hash"),
            "pattern_score": candidate.get("pattern_score"),
            "graph_features": candidate.get("graph_features"),
            "question_generation": realization.validation,
        },
        "generation_method": realization.generation_method,
        "validation_status": "pending",
        "split": None,
    }
    path = {
        "path_id": "qap_" + _digest(qa_id, candidate["kg_path"]),
        "qa_id": qa_id,
        "path_type": "graph_pattern_subgraph"
        if candidate.get("pattern_id") and candidate.get("operation_plan_id")
        else (
            "derived_fact_path"
            if candidate["source_derived_ids"]
            else "single_fact_path"
        ),
        "ordered_node_ids": candidate["kg_path"].get("node_ids", []),
        "ordered_edge_ids": candidate["kg_path"].get("edge_ids", []),
        "evidence_node_ids": candidate["kg_path"].get("evidence_node_ids")
        or candidate["kg_path"].get("node_ids", []),
        "evidence_edges": candidate["kg_path"].get("evidence_edges", []),
        "evidence_components": candidate["kg_path"].get("evidence_components", []),
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
    existing_nodes: dict[str, str],
    existing_edges: dict[str, dict[str, Any]],
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
    missing_nodes = sorted(
        node_id for node_id in path.get("node_ids", []) if node_id not in existing_nodes
    )
    missing_edges = sorted(
        edge_id for edge_id in path.get("edge_ids", []) if edge_id not in existing_edges
    )
    add(
        "evidence_path",
        bool(path.get("node_ids") and path.get("edge_ids"))
        and not missing_nodes
        and not missing_edges,
        {"missing_nodes": missing_nodes, "missing_edges": missing_edges},
        {"missing_nodes": [], "missing_edges": []},
        "Every evidence path node and edge must exist in the pinned KG build.",
    )
    path_edges = [
        existing_edges[edge_id]
        for edge_id in path.get("edge_ids", [])
        if edge_id in existing_edges
    ]
    semantic_ok, semantic_detail = _validate_evidence_semantics(
        row["task_subtype"], path, existing_nodes, existing_edges
    )
    add(
        "evidence_semantics",
        semantic_ok,
        semantic_detail,
        {"missing_relations": [], "invalid_edges": []},
        "Evidence edges must connect valid endpoint types and include task-required relations.",
    )
    fact_coverage_ok, fact_coverage_detail = _validate_source_fact_coverage(
        row, path, path_edges, build["kg_build_id"]
    )
    add(
        "source_fact_coverage",
        fact_coverage_ok,
        fact_coverage_detail,
        {"missing_fact_nodes": [], "missing_fact_relations": {}},
        "Every source fact must appear in evidence and include Entity, Metric, Period, and Source edges.",
    )
    derived_edge_ok, derived_edge_detail = _validate_derived_input_edge_coverage(
        row, path, path_edges, build["kg_build_id"]
    )
    add(
        "derived_input_edge_coverage",
        derived_edge_ok,
        derived_edge_detail,
        {"missing_derived_from": []},
        "Original DerivedFact input facts must be connected by DERIVED_FROM evidence edges.",
    )
    scope_ok, scope_detail = _validate_scope_fact_coverage(
        row, path, build["kg_build_id"]
    )
    add(
        "scope_fact_coverage",
        scope_ok,
        scope_detail,
        {"missing_scope_fact_nodes": []},
        "Scope tasks require every declared source fact to be represented in evidence.",
    )
    component_count = len(path.get("evidence_components") or [])
    add(
        "evidence_component_count",
        component_count == 1,
        component_count,
        1,
        "Evidence subgraph should be connected; multiple components indicate a forest.",
    )
    add(
        "semantic_slots",
        _semantic_slots_complete(row),
        True,
        True,
        "Entity, metric, time, unit, and required scope must be explicit.",
    )
    question_generation = row.get("source_metadata", {}).get(
        "question_generation", {}
    )
    add(
        "question_slot_roundtrip",
        bool(question_generation.get("passed"))
        and not question_generation.get("missing_slots"),
        question_generation,
        {"passed": True, "missing_slots": []},
        "Generated questions must preserve every immutable semantic slot.",
    )
    add(
        "question_answer_isolation",
        question_generation.get("answer_exposed_to_generator") is False,
        question_generation.get("answer_exposed_to_generator"),
        False,
        "The question generator must never receive the answer payload.",
    )
    if row.get("pattern_proposal_id"):
        proposal_ok = (
            row.get("stored_proposal_status") == "approved"
            and row.get("stored_proposal_hash") == row.get("pattern_proposal_hash")
            and row.get("proposal_kg_build_id") == build.get("kg_build_id")
            and float(row.get("stored_proposal_score") or 0)
            == float(row.get("pattern_score") or 0)
        )
        add(
            "pattern_proposal_match",
            proposal_ok,
            {
                "proposal_id": row.get("pattern_proposal_id"),
                "status": row.get("stored_proposal_status"),
                "hash": row.get("stored_proposal_hash"),
                "score": row.get("stored_proposal_score"),
                "kg_build_id": row.get("proposal_kg_build_id"),
            },
            {
                "status": "approved",
                "hash": row.get("pattern_proposal_hash"),
                "score": row.get("pattern_score"),
                "kg_build_id": build.get("kg_build_id"),
            },
            "Mined QA must be backed by an approved, hash-pinned proposal from the same KG build.",
        )
    expected = row["answer_payload"]
    if row.get("operation_plan_id"):
        fact_map = {
            str(item["fact_id"]): item for item in source_facts if item
        }
        execution = execute_plan(
            row.get("operator_dag") or {},
            row.get("input_bindings") or {},
            fact_map,
        )
        bound_ids = _bound_fact_ids(row.get("input_bindings") or {})
        add(
            "graph_pattern_match",
            bool(row.get("pattern_id")) and set(bound_ids) == set(row["source_fact_ids"]),
            {"pattern_id": row.get("pattern_id"), "bound_fact_ids": bound_ids},
            {"pattern_id": row.get("pattern_id"), "bound_fact_ids": sorted(row["source_fact_ids"])},
            "The graph pattern must bind exactly the facts declared by the candidate.",
        )
        add(
            "operator_input_complete",
            all(fact_id in fact_map for fact_id in bound_ids),
            sorted(fact_map),
            bound_ids,
            "Every operation-plan input must resolve to a pinned graph-ready fact.",
        )
        add(
            "operator_type_valid",
            execution.status == "passed",
            execution.errors,
            [],
            "Every operator must accept the bound input types, units, and currencies.",
        )
        add(
            "intermediate_result_recompute",
            _digest(execution.intermediate_results)
            == _digest(row.get("intermediate_results") or []),
            execution.intermediate_results,
            row.get("intermediate_results") or [],
            "Stored intermediate results must match a fresh operation-plan replay.",
        )
        add(
            "operation_trace_coverage",
            set(row["source_fact_ids"]).issubset(set(bound_ids)),
            bound_ids,
            sorted(row["source_fact_ids"]),
            "The operation trace must cover every source fact used by the QA.",
        )
        recomputed = execution.output
        reason = "Replayed the registered operation plan from pinned source facts."
    else:
        recomputed, reason = _recompute(
            row["task_subtype"],
            [item for item in source_facts if item],
            row["canonical_semantics"],
        )
    matched = _answers_match(expected, recomputed, row.get("rubric"))
    add("independent_recompute", matched, recomputed, expected, reason)
    if row["task_subtype"] in {"share", "ranking", "industry_ranking"}:
        derived_payload = row.get("derived_payload") or expected
        recomputed_payload = row.get("recomputed_payload") or recomputed
        add(
            "derived_recompute_match",
            _answers_match(derived_payload, recomputed_payload, row.get("rubric")),
            recomputed_payload,
            derived_payload,
            "KG DerivedFact output must match complete scope recomputation before QA use.",
        )
    if row["task_subtype"] in SCOPE_DERIVED | GRAPH_SCOPE_TASKS | {"share"}:
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


def _bound_fact_ids(bindings: dict[str, Any]) -> list[str]:
    output = []
    for value in bindings.values():
        if isinstance(value, list):
            output.extend(str(item) for item in value)
        elif value is not None:
            output.append(str(value))
    return sorted(set(output))


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
    elif task == "share" and values:
        target_entity = semantics.get("entity_scope", {}).get("entity_id")
        positive = [(item, value) for item, value in values if value > 0]
        target = next(
            (
                value
                for item, value in positive
                if item.get("entity_id") == target_entity
            ),
            None,
        )
        denominator = sum((value for _, value in positive), Decimal("0"))
        if (
            target is None
            or denominator == 0
            or not semantics.get("scope_input_complete")
        ):
            return {}, "Share scope inputs are incomplete or denominator is zero."
        result = target / denominator * Decimal("100")
        unit = "percent"
        currency = None
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
        top_k = int(semantics.get("top_k") or len(values))
        table = [
            {
                "rank": index + 1,
                "entity_id": item.get("entity_id"),
                "value": _number(value),
            }
            for index, (item, value) in enumerate(
                sorted(values, key=lambda pair: pair[1], reverse=True)[:top_k]
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
    for field in ("unit", "currency"):
        if expected.get(field) is not None and expected.get(field) != observed.get(
            field
        ):
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
    for field in ("winner_id", "relation"):
        if expected.get(field) != observed.get(field):
            return False
    if expected.get("difference") is not None:
        left = _decimal(expected.get("difference"))
        right = _decimal(observed.get("difference"))
        tolerance = _decimal(expected.get("tolerance")) or Decimal("0.000001")
        if left is None or right is None or abs(left - right) > tolerance:
            return False
    if expected.get("rows") is not None:
        expected_rows = expected.get("rows") or []
        observed_rows = observed.get("rows") or []
        if len(expected_rows) != len(observed_rows):
            return False
        for expected_row, observed_row in zip(expected_rows, observed_rows):
            if expected_row.get("id") != observed_row.get("id"):
                return False
            if _decimal(expected_row.get("value")) != _decimal(observed_row.get("value")):
                return False
    if expected.get("table") is not None:
        expected_table = expected.get("table") or []
        observed_table = observed.get("table") or []
        if len(expected_table) != len(observed_table):
            return False
        tolerance = _decimal(expected.get("tolerance")) or Decimal("0.000001")
        for expected_row, observed_row in zip(expected_table, observed_table):
            if not set(expected_row).issubset(observed_row):
                return False
            for key, expected_value in expected_row.items():
                observed_value = observed_row.get(key)
                left = _decimal(expected_value)
                right = _decimal(observed_value)
                if left is not None and right is not None:
                    if abs(left - right) > max(
                        tolerance, abs(left) * Decimal("0.000001")
                    ):
                        return False
                elif expected_value != observed_value:
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
        JOIN canonical_entities ce ON ce.entity_id = sf.entity_id AND ce.build_id = ?
        JOIN metrics m ON m.metric_id = sf.metric_id AND m.build_id = ?
        LEFT JOIN raw_objects ro ON ro.raw_object_id = sf.raw_object_id
        WHERE sf.build_id = ? AND COALESCE(sf.graph_ready, 0) = 1
          AND sf.verification_status IN ('single_source', 'cross_verified')
          AND COALESCE(CAST(sf.is_forecast AS INTEGER), 0) = 0
          AND sf.source_id IN ({placeholders})
          AND sf.normalized_value IS NOT NULL AND sf.normalized_unit IS NOT NULL
        ORDER BY sf.fact_id LIMIT ?
        """,
        [
            kg["input_entity_build_id"],
            kg["input_metric_build_id"],
            kg["input_fact_build_id"],
            *source_ids,
            limit,
        ],
    )
    return [dict(row) for row in rows]


def _with_scope_inputs(
    db: DBProtocol,
    kg: dict[str, Any],
    row: dict[str, Any],
    cache: dict[tuple[Any, ...], dict[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    out = dict(row)
    derived_type = str(out.get("derived_type"))
    entity_ids = json_value(out.get("scope_entity_ids"), [])
    metric_scope = json_value(out.get("metric_scope"), {})
    entity_scope = json_value(out.get("entity_scope"), {})
    time_scope = json_value(out.get("time_scope"), {})
    input_ids = json_value(out.get("input_fact_ids"), [])
    out["output_table"] = json_value(out.get("output_table"), [])
    out["derived_payload"] = _derived_payload_from_row(out)
    out["recomputed_payload"] = out["derived_payload"]
    out["derived_recompute_match"] = True
    out["derived_input_fact_ids"] = list(input_ids)
    if not entity_ids or not metric_scope.get("metric_id") or not input_ids:
        out["share_scope_complete"] = False
        return out
    cache_key = (
        derived_type,
        kg["input_fact_build_id"],
        out.get("scope_id"),
        metric_scope["metric_id"],
        time_scope.get("basis"),
        time_scope.get("year"),
        tuple(sorted(entity_ids)),
    )
    by_entity = cache.get(cache_key) if cache is not None else None
    if by_entity is None:
        seed = db.fetchone(
            "SELECT source_id, normalized_unit, normalized_currency FROM standardized_facts WHERE build_id = ? AND fact_id = ?",
            (kg["input_fact_build_id"], input_ids[0]),
        )
        if not seed:
            out["share_scope_complete"] = False
            return out
        placeholders = ",".join("?" for _ in entity_ids)
        predicates = [
            "build_id = ?",
            "COALESCE(graph_ready, 0) = 1",
            "verification_status IN ('single_source', 'cross_verified')",
            "metric_id = ?",
            "source_id = ?",
            "normalized_unit = ?",
            "COALESCE(normalized_currency, '') = COALESCE(?, '')",
            f"entity_id IN ({placeholders})",
        ]
        if derived_type == "share":
            predicates.append("CAST(normalized_value AS NUMERIC) > 0")
        params: list[Any] = [
            kg["input_fact_build_id"],
            metric_scope["metric_id"],
            seed["source_id"],
            seed["normalized_unit"],
            seed["normalized_currency"],
            *entity_ids,
        ]
        year = time_scope.get("year")
        if year is not None:
            column = (
                "fiscal_year"
                if time_scope.get("basis") == "fiscal_year"
                else "calendar_year"
            )
            predicates.append(f"{column} = ?")
            params.append(int(year))
        rows = [
            dict(item)
            for item in db.fetchall(
                f"SELECT fact_id, entity_id, normalized_value, verification_status, confidence_score FROM standardized_facts WHERE {' AND '.join(predicates)} ORDER BY entity_id, fact_id",
                params,
            )
        ]
        by_entity = {}
        for item in rows:
            entity_id = str(item["entity_id"])
            current = by_entity.get(entity_id)
            score = (
                item.get("verification_status") == "cross_verified",
                float(item.get("confidence_score") or 0),
                str(item["fact_id"]),
            )
            current_score = (
                (
                    current.get("verification_status") == "cross_verified",
                    float(current.get("confidence_score") or 0),
                    str(current["fact_id"]),
                )
                if current
                else None
            )
            if current is None or score > current_score:
                by_entity[entity_id] = item
        if cache is not None:
            cache[cache_key] = by_entity
    out["input_fact_ids"] = [
        by_entity[entity]["fact_id"] for entity in sorted(by_entity)
    ]
    complete = set(by_entity) == set(entity_ids) and (
        derived_type != "share" or entity_scope.get("entity_id") in by_entity
    )
    out[f"{derived_type}_scope_complete"] = complete
    if complete and derived_type == "share":
        target_entity = str(entity_scope["entity_id"])
        denominator = sum(
            (_decimal(item["normalized_value"]) or Decimal("0"))
            for item in by_entity.values()
        )
        target_value = _decimal(by_entity[target_entity]["normalized_value"])
        if denominator > 0 and target_value is not None:
            out["source_derived_output_value"] = out.get("output_value")
            out["recomputed_payload"] = {
                **out["derived_payload"],
                "value": str(target_value / denominator * Decimal("100")),
                "table": [],
                "unit": "percent",
                "currency": None,
            }
            out["derived_recompute_match"] = _answers_match(
                out["derived_payload"], out["recomputed_payload"], None
            )
            out["scope_recomputed"] = True
        else:
            out["share_scope_complete"] = False
    elif complete and derived_type in {"ranking", "industry_ranking"}:
        top_k = len(json_value(out.get("output_table"), [])) or 10
        ranked = sorted(
            by_entity.values(),
            key=lambda item: (
                _decimal(item.get("normalized_value")) or Decimal("-Infinity"),
                str(item.get("entity_id")),
            ),
            reverse=True,
        )[:top_k]
        out["recomputed_payload"] = {
            **out["derived_payload"],
            "value": None,
            "table": [
                {
                    "rank": rank,
                    "entity_id": item["entity_id"],
                    "value": _number(_decimal(item["normalized_value"])),
                    "fact_id": item["fact_id"],
                }
                for rank, item in enumerate(ranked, start=1)
            ],
        }
        out["derived_recompute_match"] = _answers_match(
            out["derived_payload"], out["recomputed_payload"], None
        )
        out["scope_recomputed"] = True
    return out


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


EDGE_ENDPOINT_TYPES = {
    "HAS_FACT": ("Entity", "Fact"),
    "MEASURES": ("Fact", "Metric"),
    "IN_PERIOD": ({"Fact", "DerivedFact"}, "TimePeriod"),
    "FROM_SOURCE": ({"Fact", "DerivedFact"}, "DataSource"),
    "TRACED_TO": ("Fact", "RawObject"),
    "USES_SOURCE_DEFINITION": ("Fact", "SourceDefinition"),
    "DERIVED_FROM": ("DerivedFact", "Fact"),
    "ABOUT_ENTITY": ("DerivedFact", "Entity"),
    "USES_METRIC": ("DerivedFact", "Metric"),
    "HAS_SCOPE": ("DerivedFact", "EntitySet"),
    "CONTAINS_ENTITY": ("EntitySet", "Entity"),
}


def _load_graph_nodes(
    db: DBProtocol, kg_build_id: str, node_ids: list[str]
) -> dict[str, str]:
    out: dict[str, str] = {}
    for batch in chunks(node_ids, 1000):
        placeholders = ",".join("?" for _ in batch)
        for row in db.fetchall(
            f"SELECT node_id, node_type FROM kg_nodes WHERE kg_build_id = ? AND node_id IN ({placeholders})",
            [kg_build_id, *batch],
        ):
            out[str(row["node_id"])] = str(row["node_type"])
    return out


def _load_graph_edges(
    db: DBProtocol, kg_build_id: str, edge_ids: list[str]
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for batch in chunks(edge_ids, 1000):
        placeholders = ",".join("?" for _ in batch)
        for raw in db.fetchall(
            f"SELECT edge_id, src_node_id, dst_node_id, relation_type FROM kg_edges WHERE kg_build_id = ? AND edge_id IN ({placeholders})",
            [kg_build_id, *batch],
        ):
            row = dict(raw)
            out[str(row["edge_id"])] = row
    return out


def _evidence_node_ids(path: dict[str, Any]) -> set[str]:
    return set(path.get("evidence_node_ids") or path.get("node_ids") or [])


def _fact_node_id(fact_id: str, kg_build_id: str) -> str:
    return f"fact:{fact_id}@@{kg_build_id}"


def _derived_node_id(derived_id: str, kg_build_id: str) -> str:
    return f"derived_fact:{derived_id}@@{kg_build_id}"


def _validate_source_fact_coverage(
    row: dict[str, Any],
    path: dict[str, Any],
    path_edges: list[dict[str, Any]],
    kg_build_id: str,
) -> tuple[bool, dict[str, Any]]:
    path_nodes = _evidence_node_ids(path)
    required = {"HAS_FACT", "MEASURES", "IN_PERIOD", "FROM_SOURCE"}
    fact_nodes = {
        _fact_node_id(str(fact_id), kg_build_id): str(fact_id)
        for fact_id in row.get("source_fact_ids", [])
    }
    relations_by_fact = {fact_id: set() for fact_id in fact_nodes.values()}
    for edge in path_edges:
        src = str(edge.get("src_node_id"))
        dst = str(edge.get("dst_node_id"))
        relation = str(edge.get("relation_type"))
        if src in fact_nodes:
            relations_by_fact[fact_nodes[src]].add(relation)
        if dst in fact_nodes:
            relations_by_fact[fact_nodes[dst]].add(relation)
    missing_nodes = []
    missing_relations: dict[str, list[str]] = {}
    for fact_node, fact_id in fact_nodes.items():
        if fact_node not in path_nodes:
            missing_nodes.append(fact_id)
            missing_relations[fact_id] = sorted(required)
            continue
        missing = sorted(required - relations_by_fact[fact_id])
        if missing:
            missing_relations[fact_id] = missing
    detail = {
        "missing_fact_nodes": sorted(missing_nodes),
        "missing_fact_relations": dict(sorted(missing_relations.items())),
    }
    return not missing_nodes and not missing_relations, detail


def _validate_derived_input_edge_coverage(
    row: dict[str, Any],
    path: dict[str, Any],
    path_edges: list[dict[str, Any]],
    kg_build_id: str,
) -> tuple[bool, dict[str, Any]]:
    derived_ids = row.get("source_derived_ids") or []
    if not derived_ids:
        return True, {"missing_derived_from": []}
    derived_node = _derived_node_id(str(derived_ids[0]), kg_build_id)
    input_fact_ids = row.get("canonical_semantics", {}).get("derived_input_fact_ids")
    if input_fact_ids is None:
        input_fact_ids = row.get("source_fact_ids", [])
    edge_pairs = {
        (str(edge.get("src_node_id")), str(edge.get("dst_node_id")))
        for edge in path_edges
        if str(edge.get("relation_type")) == "DERIVED_FROM"
    }
    missing = []
    for fact_id in input_fact_ids:
        fact_node = _fact_node_id(str(fact_id), kg_build_id)
        if (derived_node, fact_node) not in edge_pairs:
            missing.append(str(fact_id))
    detail = {"missing_derived_from": sorted(missing)}
    return not missing, detail


def _validate_scope_fact_coverage(
    row: dict[str, Any], path: dict[str, Any], kg_build_id: str
) -> tuple[bool, dict[str, Any]]:
    if row.get("task_subtype") not in SCOPE_DERIVED | GRAPH_SCOPE_TASKS | {"share", "ranking"}:
        return True, {"missing_scope_fact_nodes": []}
    path_nodes = _evidence_node_ids(path)
    missing = [
        str(fact_id)
        for fact_id in row.get("source_fact_ids", [])
        if _fact_node_id(str(fact_id), kg_build_id) not in path_nodes
    ]
    detail = {"missing_scope_fact_nodes": sorted(missing)}
    return not missing, detail


def _validate_evidence_semantics(
    task_subtype: str,
    path: dict[str, Any],
    nodes: dict[str, str],
    edges: dict[str, dict[str, Any]],
) -> tuple[bool, dict[str, Any]]:
    path_nodes = _evidence_node_ids(path)
    relations = set()
    invalid_edges = []
    for edge_id in path.get("edge_ids", []):
        edge = edges.get(edge_id)
        if not edge:
            continue
        src = str(edge["src_node_id"])
        dst = str(edge["dst_node_id"])
        relation = str(edge["relation_type"])
        relations.add(relation)
        expected = EDGE_ENDPOINT_TYPES.get(relation)
        if src not in path_nodes or dst not in path_nodes or not expected:
            invalid_edges.append(edge_id)
            continue
        src_expected, dst_expected = expected
        src_types = (
            {src_expected} if isinstance(src_expected, str) else set(src_expected)
        )
        dst_types = (
            {dst_expected} if isinstance(dst_expected, str) else set(dst_expected)
        )
        if nodes.get(src) not in src_types or nodes.get(dst) not in dst_types:
            invalid_edges.append(edge_id)
    if task_subtype in {
        "single_fact",
        "pairwise_entity_comparison",
        "cross_metric_comparison",
        "multi_period_average",
        "temporal_peak_followup",
    } | GRAPH_SCOPE_TASKS:
        required = {
            "HAS_FACT",
            "MEASURES",
            "IN_PERIOD",
            "FROM_SOURCE",
            "TRACED_TO",
            "USES_SOURCE_DEFINITION",
        }
    else:
        required = {"DERIVED_FROM", "USES_METRIC", "IN_PERIOD"}
        if task_subtype in SCOPE_DERIVED | {"share"}:
            required |= {"HAS_SCOPE", "CONTAINS_ENTITY"}
    missing_relations = sorted(required - relations)
    detail = {
        "missing_relations": missing_relations,
        "invalid_edges": sorted(invalid_edges),
    }
    return not missing_relations and not invalid_edges, detail


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
    frequency_buckets: Counter[tuple[Any, ...]] = Counter()
    strata: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
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
        if frequency_buckets[key] >= cap:
            continue
        frequency_buckets[key] += 1
        stratum = (
            str(row.get("source_id") or ""),
            str(row.get("metric_id") or ""),
            str(row.get("entity_id") or ""),
        )
        strata[stratum].append(row)
    selected = []
    depth = 0
    ordered_strata = sorted(strata)
    while len(selected) < quota:
        added = False
        for stratum in ordered_strata:
            if depth < len(strata[stratum]):
                selected.append(strata[stratum][depth])
                added = True
                if len(selected) >= quota:
                    break
        if not added:
            break
        depth += 1
    return selected


def _kg_path_from_graph(
    db: DBProtocol,
    kg_build_id: str,
    *,
    fact_ids: list[str],
    derived_id: str | None = None,
    supplemental_fact_ids: list[str] | None = None,
) -> dict[str, Any]:
    if derived_id:
        seed_nodes = [f"derived_fact:{derived_id}@@{kg_build_id}"]
        seed_nodes.extend(
            f"fact:{fact_id}@@{kg_build_id}"
            for fact_id in (supplemental_fact_ids or [])
        )
    else:
        seed_nodes = [f"fact:{fact_id}@@{kg_build_id}" for fact_id in fact_ids]
    relations = [
        "HAS_FACT",
        "MEASURES",
        "IN_PERIOD",
        "FROM_SOURCE",
        "TRACED_TO",
        "USES_SOURCE_DEFINITION",
    ]
    if derived_id:
        relations.extend(
            ["DERIVED_FROM", "ABOUT_ENTITY", "USES_METRIC", "HAS_SCOPE"]
        )
    edges: dict[str, dict[str, Any]] = {}
    for batch in chunks(seed_nodes, 300):
        placeholders = ",".join("?" for _ in batch)
        relation_placeholders = ",".join("?" for _ in relations)
        for direction in ("src_node_id", "dst_node_id"):
            sql = f"""
                SELECT edge_id, src_node_id, dst_node_id, relation_type
                FROM kg_edges
                WHERE kg_build_id = ?
                  AND {direction} IN ({placeholders})
                  AND relation_type IN ({relation_placeholders})
                ORDER BY relation_type, edge_id
            """
            params = [kg_build_id, *batch, *relations]
            for raw in db.fetchall(sql, params):
                edge = dict(raw)
                edges[str(edge["edge_id"])] = edge
    scope_nodes = sorted(
        {
            str(edge["dst_node_id"])
            for edge in edges.values()
            if edge["relation_type"] == "HAS_SCOPE"
        }
    )
    for batch in chunks(scope_nodes, 300):
        placeholders = ",".join("?" for _ in batch)
        for raw in db.fetchall(
            f"SELECT edge_id, src_node_id, dst_node_id, relation_type FROM kg_edges WHERE kg_build_id = ? AND src_node_id IN ({placeholders}) AND relation_type = 'CONTAINS_ENTITY' ORDER BY edge_id",
            [kg_build_id, *batch],
        ):
            edge = dict(raw)
            edges[str(edge["edge_id"])] = edge
    fact_nodes = sorted(
        {
            node_id
            for edge in edges.values()
            for node_id in (str(edge["src_node_id"]), str(edge["dst_node_id"]))
            if node_id.startswith("fact:")
        }
        | {node_id for node_id in seed_nodes if node_id.startswith("fact:")}
    )
    fact_relations = [
        "HAS_FACT",
        "MEASURES",
        "IN_PERIOD",
        "FROM_SOURCE",
        "TRACED_TO",
        "USES_SOURCE_DEFINITION",
    ]
    for batch in chunks(fact_nodes, 300):
        placeholders = ",".join("?" for _ in batch)
        relation_placeholders = ",".join("?" for _ in fact_relations)
        for direction in ("src_node_id", "dst_node_id"):
            sql = f"""
                SELECT edge_id, src_node_id, dst_node_id, relation_type
                FROM kg_edges
                WHERE kg_build_id = ?
                  AND {direction} IN ({placeholders})
                  AND relation_type IN ({relation_placeholders})
                ORDER BY relation_type, edge_id
            """
            params = [kg_build_id, *batch, *fact_relations]
            for raw in db.fetchall(sql, params):
                edge = dict(raw)
                edges[str(edge["edge_id"])] = edge
    nodes = sorted(
        {
            node_id
            for edge in edges.values()
            for node_id in (str(edge["src_node_id"]), str(edge["dst_node_id"]))
        }
        | set(seed_nodes)
    )
    ordered_edges = sorted(
        edges.values(),
        key=lambda edge: (str(edge["relation_type"]), str(edge["edge_id"])),
    )
    structured_edges = [
        {
            "edge_id": str(edge["edge_id"]),
            "src": str(edge["src_node_id"]),
            "relation": str(edge["relation_type"]),
            "dst": str(edge["dst_node_id"]),
        }
        for edge in ordered_edges
    ]
    components = _evidence_components(nodes, structured_edges)
    return {
        "node_ids": nodes,
        "edge_ids": [str(edge["edge_id"]) for edge in ordered_edges],
        "relations": [str(edge["relation_type"]) for edge in ordered_edges],
        "evidence_node_ids": nodes,
        "evidence_edges": structured_edges,
        "evidence_components": components,
    }


def _evidence_components(
    node_ids: list[str], structured_edges: list[dict[str, str]]
) -> list[dict[str, Any]]:
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    edges_by_node: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for edge in structured_edges:
        src = edge["src"]
        dst = edge["dst"]
        adjacency.setdefault(src, set()).add(dst)
        adjacency.setdefault(dst, set()).add(src)
        edges_by_node.setdefault(src, set()).add(edge["edge_id"])
        edges_by_node.setdefault(dst, set()).add(edge["edge_id"])
    components = []
    seen: set[str] = set()
    for node_id in sorted(adjacency):
        if node_id in seen:
            continue
        stack = [node_id]
        component_nodes = set()
        component_edges = set()
        while stack:
            current = stack.pop()
            if current in component_nodes:
                continue
            component_nodes.add(current)
            component_edges |= edges_by_node.get(current, set())
            for neighbor in adjacency.get(current, set()):
                if neighbor not in component_nodes:
                    stack.append(neighbor)
        seen |= component_nodes
        components.append(
            {
                "component_id": len(components) + 1,
                "node_ids": sorted(component_nodes),
                "edge_ids": sorted(component_edges),
            }
        )
    return components


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
    entity_ids = list(candidate.get("entity_ids") or [])
    metric_ids = list(candidate.get("metric_ids") or [])
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
        "top_k": str(len(candidate.get("answer_payload", {}).get("table") or [])),
        "entity_a": entity_names.get(entity_ids[0], entity_ids[0])
        if entity_ids
        else "the first entity",
        "entity_b": entity_names.get(entity_ids[1], entity_ids[1])
        if len(entity_ids) > 1
        else "the second entity",
        "metric_a": metric_names.get(metric_ids[0], metric_ids[0].replace("_", " "))
        if metric_ids
        else "the first metric",
        "metric_b": metric_names.get(metric_ids[1], metric_ids[1].replace("_", " "))
        if len(metric_ids) > 1
        else "the second metric",
        "primary_metric": metric_names.get(
            semantics.get("primary_metric_id"),
            str(semantics.get("primary_metric_id") or "the primary metric").replace("_", " "),
        ),
        "secondary_metric": metric_names.get(
            semantics.get("secondary_metric_id"),
            str(semantics.get("secondary_metric_id") or "the secondary metric").replace("_", " "),
        ),
        "observation_count": str(
            semantics.get("observation_count")
            or time_scope.get("observation_count")
            or len(candidate.get("source_fact_ids") or [])
        ),
        "frequency": str(
            semantics.get("frequency") or time_scope.get("frequency") or "periodic"
        ),
        "growth_threshold": str(semantics.get("growth_threshold_pct") or "10"),
        "debt_threshold": str(semantics.get("debt_ratio_max_pct") or "70"),
    }


def _answer_text(
    candidate: dict[str, Any], answer: dict[str, Any], entity_names: dict[str, str]
) -> str:
    if candidate["task_subtype"] == "temporal_peak_followup":
        semantics = candidate.get("canonical_semantics", {})
        metric_names = semantics.get("metric_names") or {}
        primary = metric_names.get(
            semantics.get("primary_metric_id"), semantics.get("primary_metric_id")
        )
        secondary = metric_names.get(
            semantics.get("secondary_metric_id"), semantics.get("secondary_metric_id")
        )
        return (
            f"{answer.get('result_period')}: {primary} peaked at "
            f"{_format_value(answer.get('primary_value'))} {answer.get('primary_unit') or ''}; "
            f"{secondary} was {_format_value(answer.get('secondary_value'))} "
            f"{answer.get('secondary_unit') or ''}"
        ).strip()
    if answer.get("relation") and answer.get("rows"):
        labels = dict(entity_names)
        labels.update(candidate.get("canonical_semantics", {}).get("metric_names") or {})
        if answer.get("relation") == "equal":
            return f"Equal; difference: 0 {answer.get('unit') or ''}".strip()
        winner = labels.get(answer.get("winner_id"), answer.get("winner_id"))
        return (
            f"{winner} was higher by {_format_value(answer.get('difference'))} "
            f"{answer.get('unit') or ''}"
        ).strip()
    if answer.get("table"):
        if candidate["task_subtype"] in {
            "ranking",
            "industry_ranking",
            "filter_then_rank",
        }:
            unit = answer.get("unit") or ""
            rows = []
            for index, item in enumerate(answer["table"], start=1):
                rank = item.get("rank") or index
                name = entity_names.get(item.get("entity_id"), item.get("entity_id"))
                value = _format_value(item.get("value"))
                rows.append(f"{rank}. {name}: {value} {unit}".strip())
            return "; ".join(rows)
        if candidate["task_subtype"] == "rank_then_secondary_lookup":
            semantics = candidate.get("canonical_semantics", {})
            metric_names = semantics.get("metric_names") or {}
            primary = metric_names.get(
                semantics.get("primary_metric_id"), semantics.get("primary_metric_id")
            )
            secondary = metric_names.get(
                semantics.get("secondary_metric_id"), semantics.get("secondary_metric_id")
            )
            rows = []
            for item in answer["table"]:
                name = entity_names.get(item.get("entity_id"), item.get("entity_id"))
                rows.append(
                    f"{item.get('rank')}. {name}: {primary} "
                    f"{_format_value(item.get('primary_value'))} "
                    f"{answer.get('primary_unit') or ''}; {secondary} "
                    f"{_format_value(item.get('secondary_value'))} "
                    f"{answer.get('secondary_unit') or ''}"
                )
            return " | ".join(rows)
        if candidate["task_subtype"] == "multi_factor_screening":
            rows = []
            for item in answer["table"]:
                name = entity_names.get(item.get("entity_id"), item.get("entity_id"))
                rows.append(
                    f"{name}: growth {_format_value(item.get('revenue_growth_pct'))}%, "
                    f"net margin {_format_value(item.get('net_margin_pct'))}%, "
                    f"debt ratio {_format_value(item.get('debt_ratio_pct'))}%"
                )
            return "; ".join(rows)
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


def _ranked_value_tolerance(value: Any) -> str:
    tolerance = _decimal(value) or Decimal("0")
    return str(max(tolerance, Decimal("0.001")))


def _rubric(candidate: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    if candidate["task_subtype"] == "temporal_peak_followup":
        return {
            "match_type": "period_metric_lookup",
            "target_period": answer.get("result_period"),
            "primary_metric_id": answer.get("primary_metric_id"),
            "primary_value": answer.get("primary_value"),
            "primary_unit": answer.get("primary_unit"),
            "secondary_metric_id": answer.get("secondary_metric_id"),
            "secondary_value": answer.get("secondary_value"),
            "secondary_unit": answer.get("secondary_unit"),
            "value_tolerance": answer.get("tolerance") or "0.000001",
        }
    if answer.get("relation") and answer.get("rows"):
        return {
            "match_type": "comparison",
            "winner_id": answer.get("winner_id"),
            "relation": answer.get("relation"),
            "difference": answer.get("difference"),
            "target_rows": answer.get("rows"),
            "unit": answer.get("unit"),
            "currency": answer.get("currency"),
            "absolute_tolerance": answer.get("tolerance") or "0.000001",
        }
    if answer.get("table"):
        if candidate["task_subtype"] in {
            "ranking",
            "industry_ranking",
            "filter_then_rank",
        }:
            return {
                "match_type": "ranked_table",
                "target_rows": [
                    {
                        "rank": item.get("rank"),
                        "entity_id": item.get("entity_id"),
                        "value": item.get("value"),
                    }
                    for item in answer["table"]
                ],
                "unit": answer.get("unit"),
                "value_tolerance": _ranked_value_tolerance(answer.get("tolerance")),
                "order_required": True,
                "allow_extra_entities": False,
                "allow_missing_entities": False,
            }
        if candidate["task_subtype"] == "rank_then_secondary_lookup":
            return {
                "match_type": "multi_metric_ranked_table",
                "target_rows": answer["table"],
                "primary_unit": answer.get("primary_unit"),
                "secondary_unit": answer.get("secondary_unit"),
                "value_tolerance": "0.000001",
                "order_required": True,
            }
        if candidate["task_subtype"] == "multi_factor_screening":
            return {
                "match_type": "screening_table",
                "target_rows": answer["table"],
                "industry_average_margin_pct": answer.get(
                    "industry_average_margin_pct"
                ),
                "growth_threshold_pct": answer.get("growth_threshold_pct"),
                "debt_ratio_max_pct": answer.get("debt_ratio_max_pct"),
                "value_tolerance": "0.000001",
                "order_required": True,
            }
        entities = [item.get("entity_id") for item in answer["table"]]
        return {
            "match_type": "set_match",
            "target_entity_ids": entities,
            "order_required": False,
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


def _match_time_scope(match: dict[str, Any]) -> dict[str, Any]:
    period = match.get("period")
    frequency = str(match.get("frequency") or "annual").lower()
    text = str(period or "").strip()
    parts = text.replace("-", " ").split()
    year = next(
        (int(part) for part in parts if len(part) == 4 and part.isdigit()), None
    )
    quarter = next(
        (part.upper() for part in parts if part.upper() in {"Q1", "Q2", "Q3", "Q4"}),
        None,
    )
    if year is not None and (frequency == "quarterly" or quarter):
        return {
            "fiscal_year": year,
            "fiscal_quarter": quarter,
            "basis": "fiscal_year",
            "frequency": "quarterly",
        }
    if year is not None and frequency == "annual":
        return {"year": year, "basis": "fiscal_year", "frequency": "annual"}
    return {
        "observation_date": text,
        "basis": "observation_date",
        "frequency": frequency,
    }


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
    if row["task_subtype"] == "rank_then_secondary_lookup":
        answer = row.get("answer_payload") or {}
        if not answer.get("primary_unit") or not answer.get("secondary_unit"):
            return False
    elif row["task_subtype"] != "multi_condition_screening" and not row.get("unit"):
        return False
    if row["task_subtype"] in SCOPE_DERIVED | GRAPH_SCOPE_TASKS | {"share"} and not semantics.get(
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
        "single_fact_worldbank": 6000,
        "single_fact_imf": 4000,
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
        "industry_argmax": 0,
        "industry_argmin": 0,
        "ranking": 150,
        "argmax": 0,
        "argmin": 0,
        "rolling_max": 50,
        "rolling_min": 50,
        "macro_time_series_argmax": 33,
        "macro_time_series_argmin": 33,
        "time_series_argmax": 17,
        "time_series_argmin": 17,
        "multi_condition_screening": 0,
        "long_window_return": 10,
    }
    graph_config = configured.get("graph_patterns", {})
    question_generation = configured.get(
        "question_generation", {"mode": "controlled_template"}
    )
    return {
        "quotas": {key: int(quotas.get(key, value)) for key, value in defaults.items()},
        "derived_quotas": {
            key: int(configured.get("derived_quotas", {}).get(key, value))
            for key, value in derived_defaults.items()
        },
        "language": "en",
        "forecast_policy": "exclude_historical_questions",
        "generation_method": "deterministic_template",
        "graph_patterns": {
            "enabled": bool(graph_config.get("enabled", False)),
            "comparability": graph_config.get("comparability", {}),
            "quotas": {
                item["pattern_id"]: int(
                    graph_config.get("quotas", {}).get(item["pattern_id"], 0)
                )
                for item in pattern_manifest()
                if item.get("matcher") and item.get("is_active")
            },
        },
        "pattern_mining": mining_policy(config),
        "question_generation": question_generation,
        "temporal_split": configured.get("temporal_split", {"cutoff_year": 2025}),
        "split_policy": configured.get(
            "split_policy", "semantic_cluster_then_entity_fixed_time_task"
        ),
        "quality_gate": configured.get(
            "quality_gate",
            {
                "minimum_overall_pass_rate": 0.95,
                "critical_tasks": {
                    "single_fact": 1000,
                    "yoy_growth": 1000,
                    "qoq_growth": 1000,
                    "ratio": 500,
                },
                "max_critical_check_failures": 0,
            },
        ),
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


def _seed_graph_patterns(db: DBProtocol) -> None:
    rows = []
    for item in pattern_manifest():
        pattern_hash = _digest(item)
        pattern_key = f"{item['pattern_id']}@{item['pattern_version']}"
        db.execute(
            "UPDATE qa_graph_patterns SET is_active = ? "
            "WHERE pattern_id = ? AND pattern_version <> ?",
            (False, item["pattern_id"], item["pattern_version"]),
        )
        existing = db.fetchone(
            "SELECT pattern_hash FROM qa_graph_patterns WHERE pattern_key = ?",
            (pattern_key,),
        )
        if existing and existing["pattern_hash"] and existing["pattern_hash"] != pattern_hash:
            raise RuntimeError(
                f"Published graph pattern changed without a version bump: {pattern_key}"
            )
        rows.append(
            {
                **item,
                "pattern_key": pattern_key,
                "pattern_hash": pattern_hash,
            }
        )
    insert_rows(
        db,
        "qa_graph_patterns",
        rows,
        [
            "pattern_key",
            "pattern_id",
            "pattern_version",
            "pattern_family",
            "matcher",
            "pattern_hash",
            "node_constraints",
            "edge_constraints",
            "semantic_constraints",
            "operator_template",
            "answer_schema",
            "difficulty_base",
            "question_intents",
            "is_active",
        ],
        {
            "node_constraints",
            "edge_constraints",
            "semantic_constraints",
            "operator_template",
            "answer_schema",
            "question_intents",
        },
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_commit_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_repo_root(),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _git_worktree_dirty() -> bool | None:
    try:
        return bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=_repo_root(),
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
    except Exception:
        return None


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
    row["operation_plan"] = json_value(row.get("operation_plan"), {})
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
    for key in [
        "operator_dag",
        "input_bindings",
        "intermediate_results",
        "output_schema",
        "plan_validation_errors",
    ]:
        row[key] = json_value(row.get(key), [] if key in {"intermediate_results", "plan_validation_errors"} else {})
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
        "derived_payload",
        "recomputed_payload",
        "answer_payload",
        "kg_path",
        "rejection_reasons",
        "graph_features",
        "answer_schema",
    }


def _sample_json_columns() -> set[str]:
    return {"answer_value", "rubric", "source_metadata"}


def _plan_json_columns() -> set[str]:
    return {
        "operator_dag",
        "input_bindings",
        "intermediate_results",
        "output_schema",
        "validation_errors",
    }


def _evidence_json_columns() -> set[str]:
    return {
        "ordered_node_ids",
        "ordered_edge_ids",
        "evidence_node_ids",
        "evidence_edges",
        "evidence_components",
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
            value = str(scope[key]).strip()
            if value.isdigit():
                return int(value)
            for token in value.replace("-", " ").split():
                if len(token) == 4 and token.isdigit():
                    return int(token)
    value = scope.get("end_date") or scope.get("observation_date")
    return int(str(value)[:4]) if value and str(value)[:4].isdigit() else None
