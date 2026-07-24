from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from finraw.db.client import DBProtocol
from finraw.qa.evaluation.rubrics import rubric_for_task
from finraw.qa.schema import ensure_qa_schema
from finraw.qa.store import json_value


def load_evaluation_bundles(
    db: DBProtocol,
    qa_build_id: str,
    *,
    qa_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    ensure_qa_schema(db)
    selected = set(str(item) for item in qa_ids or [])
    samples = [
        _decode_sample(dict(row))
        for row in db.fetchall(
            "SELECT * FROM qa_samples WHERE qa_build_id = ? ORDER BY qa_id",
            (qa_build_id,),
        )
        if not selected or str(row["qa_id"]) in selected
    ]
    candidate_ids = {str(row["candidate_id"]) for row in samples}
    candidates = {
        str(row["candidate_id"]): _decode_candidate(dict(row))
        for row in db.fetchall(
            "SELECT * FROM qa_candidates WHERE qa_build_id = ?",
            (qa_build_id,),
        )
        if str(row["candidate_id"]) in candidate_ids
    }
    plans = {
        str(row["candidate_id"]): _decode_plan(dict(row))
        for row in db.fetchall(
            "SELECT * FROM qa_operation_plans WHERE qa_build_id = ?",
            (qa_build_id,),
        )
        if str(row["candidate_id"]) in candidate_ids
    }
    labels: dict[str, dict[str, Any]] = {}
    for row in db.fetchall(
        "SELECT * FROM qa_distribution_labels WHERE qa_build_id = ? "
        "ORDER BY created_at, alignment_id",
        (qa_build_id,),
    ):
        labels[str(row["qa_id"])] = _decode_label(dict(row))
    evidence = {
        str(row["qa_id"]): _decode_evidence(dict(row))
        for row in db.fetchall(
            "SELECT * FROM qa_evidence_paths WHERE qa_id IN "
            "(SELECT qa_id FROM qa_samples WHERE qa_build_id = ?)",
            (qa_build_id,),
        )
    }
    failed_checks: dict[str, list[str]] = defaultdict(list)
    for row in db.fetchall(
        "SELECT qa_id, check_name, check_status FROM qa_quality_checks "
        "WHERE qa_build_id = ?",
        (qa_build_id,),
    ):
        if str(row["check_status"]) != "passed":
            failed_checks[str(row["qa_id"])].append(str(row["check_name"]))

    bundles = []
    for sample in samples:
        qa_id = str(sample["qa_id"])
        candidate = candidates.get(str(sample["candidate_id"]), {})
        plan = plans.get(str(sample["candidate_id"]), {})
        label = labels.get(qa_id, _fallback_label(sample, candidate, plan))
        path = evidence.get(qa_id, {})
        l0_reasons = []
        if sample.get("validation_status") != "passed":
            l0_reasons.append(
                f"sample_validation_status={sample.get('validation_status')}"
            )
        if candidate.get("eligibility_status") not in {None, "eligible"}:
            l0_reasons.append(
                f"candidate_eligibility_status={candidate.get('eligibility_status')}"
            )
        if failed_checks.get(qa_id):
            l0_reasons.append(
                "failed_quality_checks=" + ",".join(sorted(failed_checks[qa_id]))
            )
        bundle = {
            "qa_id": qa_id,
            "qa_build_id": qa_build_id,
            "sample": sample,
            "candidate": candidate,
            "operation_plan": plan,
            "distribution_label": label,
            "evidence": path,
            "deterministic_gate_status": "passed" if not l0_reasons else "failed",
            "deterministic_gate_reasons": l0_reasons,
        }
        bundle["surface_view"] = surface_view(bundle)
        bundle["grounded_view"] = grounded_view(bundle)
        bundles.append(bundle)
    return bundles


def surface_view(bundle: dict[str, Any]) -> dict[str, Any]:
    sample = bundle["sample"]
    label = bundle["distribution_label"]
    return {
        "question": sample.get("question"),
        "benchmark_task": label.get("benchmark_task", "T2"),
        "language": sample.get("language"),
        "answer_type": sample.get("answer_type"),
        "output_requirement": _rubric_summary(sample.get("rubric") or {}),
    }


def grounded_view(bundle: dict[str, Any]) -> dict[str, Any]:
    sample = bundle["sample"]
    candidate = bundle["candidate"]
    plan = bundle["operation_plan"]
    label = bundle["distribution_label"]
    path = bundle["evidence"]
    canonical = candidate.get("canonical_semantics") or {}
    operations = []
    for step in (plan.get("operator_dag") or {}).get("operators", []):
        operations.append(
            {
                "operator": step.get("operator"),
                "semantic_parameters": _safe_operator_params(step.get("params") or {}),
            }
        )
    source_classes = label.get("source_classes") or []
    scope = candidate.get("entity_scope") or {}
    return {
        "question": sample.get("question"),
        "benchmark_task": label.get("benchmark_task", "T2"),
        "language": sample.get("language"),
        "canonical_semantics": {
            "entity_labels": _first_nonempty(
                canonical, "entity_names", "entities", "entity_labels"
            ),
            "metric_labels": _first_nonempty(
                canonical, "metric_names", "metrics", "metric_labels"
            ),
            "time_scope": candidate.get("time_scope") or canonical.get("time_scope"),
            "scope_description": scope.get("scope_definition")
            or scope.get("description")
            or canonical.get("scope_description"),
            "constraints": _semantic_constraints(canonical),
        },
        "operation_summary": operations,
        "evidence_summary": {
            "source_authority_classes": source_classes,
            "fact_count": len(candidate.get("source_fact_ids") or []),
            "derived_fact_count": len(candidate.get("source_derived_ids") or []),
            "period_count": int(label.get("period_count") or 0),
            "entity_count": len(candidate.get("entity_ids") or []),
            "scope_size": int(label.get("scope_size") or 0),
            "scope_complete": _scope_complete(candidate),
            "evidence_node_count": len(path.get("evidence_node_ids") or []),
            "evidence_edge_count": len(path.get("evidence_edges") or []),
        },
        "answer_schema": candidate.get("answer_schema")
        or {"type": sample.get("answer_type")},
        "rubric_summary": _rubric_summary(sample.get("rubric") or {}),
        "evaluation_rubric": rubric_for_task(label.get("benchmark_task", "T2")),
    }


def _decode_sample(row: dict[str, Any]) -> dict[str, Any]:
    for key, default in {"answer_value": {}, "rubric": {}, "source_metadata": {}}.items():
        row[key] = json_value(row.get(key), default)
    return row


def _decode_candidate(row: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "entity_ids": [],
        "metric_ids": [],
        "time_scope": {},
        "entity_scope": {},
        "source_fact_ids": [],
        "source_derived_ids": [],
        "source_document_ids": [],
        "raw_object_ids": [],
        "canonical_semantics": {},
        "answer_schema": {},
        "graph_features": {},
        "kg_path": {},
    }
    for key, default in defaults.items():
        row[key] = json_value(row.get(key), default)
    return row


def _decode_plan(row: dict[str, Any]) -> dict[str, Any]:
    for key, default in {
        "operator_dag": {},
        "input_bindings": {},
        "intermediate_results": [],
        "output_schema": {},
    }.items():
        row[key] = json_value(row.get(key), default)
    return row


def _decode_label(row: dict[str, Any]) -> dict[str, Any]:
    for key in (
        "metric_families",
        "source_classes",
        "operation_families",
        "structural_features",
        "completeness_checks",
    ):
        row[key] = json_value(row.get(key), [] if key.endswith("families") else {})
    return row


def _decode_evidence(row: dict[str, Any]) -> dict[str, Any]:
    for key in (
        "evidence_node_ids",
        "evidence_edges",
        "evidence_components",
        "source_fact_ids",
        "source_derived_ids",
        "raw_object_ids",
        "source_document_ids",
    ):
        row[key] = json_value(row.get(key), [])
    return row


def _fallback_label(
    sample: dict[str, Any], candidate: dict[str, Any], plan: dict[str, Any]
) -> dict[str, Any]:
    operations = [
        str(step.get("operator"))
        for step in (plan.get("operator_dag") or {}).get("operators", [])
    ]
    period_count = len((candidate.get("time_scope") or {}).get("periods") or [])
    entity_count = len(candidate.get("entity_ids") or [])
    is_t3 = period_count >= 3 or entity_count >= 2 or len(operations) >= 2
    return {
        "benchmark_task": "T3" if is_t3 else "T2",
        "market_subset": "unknown",
        "language": sample.get("language") or "unknown",
        "topic": "unknown",
        "metric_families": candidate.get("metric_ids") or [],
        "source_classes": [],
        "period_count": period_count,
        "answer_type": sample.get("answer_type") or "unknown",
        "operation_families": operations,
        "primary_operation_family": operations[-1] if operations else "lookup",
        "operation_depth": len(operations),
        "scope_size": entity_count,
        "generation_pipeline": _generation_pipeline(candidate),
    }


def _generation_pipeline(candidate: dict[str, Any]) -> str:
    pattern = str(candidate.get("pattern_id") or "")
    if pattern.startswith("walk_"):
        return "typed_edge_walk"
    if candidate.get("pattern_proposal_id"):
        return "automatic_pattern_mining"
    if pattern:
        return "static_graph_pattern"
    if candidate.get("source_derived_ids"):
        return "derived_fact_qa"
    return "fact_qa"


def _rubric_summary(rubric: dict[str, Any]) -> dict[str, Any]:
    return {
        "match_type": rubric.get("match_type") or rubric.get("type"),
        "unit_required": bool(rubric.get("unit") or rubric.get("unit_required")),
        "currency_required": bool(
            rubric.get("currency") or rubric.get("currency_required")
        ),
        "order_required": bool(rubric.get("order_required")),
        "complete_rows_required": bool(rubric.get("require_complete_rows")),
        "precision_rule": rubric.get("decimal_places")
        if "decimal_places" in rubric
        else "tolerance" if rubric.get("value_tolerance") else None,
    }


def _safe_operator_params(params: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "comparison",
        "direction",
        "top_k",
        "threshold",
        "value",
        "metric_id",
        "window",
        "target_rank",
    }
    return {key: params[key] for key in sorted(params) if key in allowed}


def _semantic_constraints(canonical: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "thresholds",
        "ranking",
        "followup",
        "operation_sequence",
        "financial_scope_type",
        "time_basis",
    }
    return {key: canonical[key] for key in sorted(canonical) if key in allowed}


def _first_nonempty(value: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if value.get(key):
            return value[key]
    return []


def _scope_complete(candidate: dict[str, Any]) -> bool:
    scope = candidate.get("entity_scope") or {}
    expected = set(str(item) for item in scope.get("expected_entity_ids") or [])
    represented = set(str(item) for item in candidate.get("entity_ids") or [])
    return not expected or expected == represented
