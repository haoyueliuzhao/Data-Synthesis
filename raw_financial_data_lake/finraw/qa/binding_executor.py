from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from finraw.db.client import DBProtocol
from finraw.qa.comparability import comparability_policy
from finraw.qa.pattern_mining import (
    _deduplicate_facts,
    _mine_cross_metric_comparison,
    _mine_scope_rank_followup,
    _mine_temporal_aggregation,
    _mine_temporal_followup,
)
from finraw.qa.plans import execute_plan, materialize_plan
from finraw.qa.schema import ensure_qa_schema
from finraw.qa.semantic_constraints import validate_semantic_constraints
from finraw.qa.store import insert_rows, json_value


def execute_compiled_bindings(
    db: DBProtocol,
    kg: dict[str, Any],
    proposal: dict[str, Any],
    logical_plan: Any,
    *,
    qa_build_id: str,
    limit: int,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    ensure_qa_schema(db)
    plan_row = logical_plan.as_row()
    plan_hash = _digest(plan_row)
    compilation_id = (
        "qacomp_"
        + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_")
        + uuid.uuid4().hex[:8]
    )
    started_at = _now()
    compilation = {
        "compilation_id": compilation_id,
        "qa_build_id": qa_build_id,
        "proposal_id": proposal["proposal_id"],
        "proposal_hash": proposal["proposal_hash"],
        "source_kg_build_id": proposal["kg_build_id"],
        "target_kg_build_id": kg["kg_build_id"],
        "fact_build_id": kg["input_fact_build_id"],
        "compiler_version": plan_row["compiler_version"],
        "logical_plan": plan_row,
        "logical_plan_hash": plan_hash,
        "status": "running",
        "started_at": started_at,
        "completed_at": None,
        "discovered_binding_count": 0,
        "semantic_valid_binding_count": 0,
        "execution_valid_binding_count": 0,
        "compiled_binding_count": 0,
        "rejected_binding_count": 0,
        "sampling_summary": {},
        "notes": {"binding_source": "compiled_query"},
    }
    insert_rows(
        db,
        "qa_pattern_compilations",
        [compilation],
        list(compilation),
        {"logical_plan", "sampling_summary", "notes"},
    )
    try:
        facts, metrics = _load_execution_pool(
            db,
            kg,
            plan_row["metric_ids"],
            int(policy["compiled_scan_rows_per_metric"]),
        )
        raw_proposals = _execute_family_miner(
            facts,
            metrics,
            plan_row,
            policy,
        )
        matching = [
            item
            for item in raw_proposals
            if list(item["metric_ids"]) == list(plan_row["metric_ids"])
        ]
        records = [
            record
            for item in matching
            for record in item["binding_validation_records"]
        ]
        discovered = sum(
            int(item["evaluated_binding_count"]) for item in matching
        )
        audit_hashes = {
            _digest(binding)
            for key in ("binding_examples", "heldout_bindings")
            for binding in json_value(proposal.get(key), [])
        }
        executable = []
        semantic_valid = 0
        execution_valid = 0
        fact_map = {str(fact["fact_id"]): fact for fact in facts}
        semantic_policy = comparability_policy(policy.get("semantic_policy"))
        for record in records:
            binding = dict(record["binding"])
            bound_facts = [
                fact_map[str(fact_id)]
                for fact_id in binding.get("fact_ids") or []
                if str(fact_id) in fact_map
            ]
            validation = validate_semantic_constraints(
                proposal["pattern_spec"],
                binding,
                bound_facts,
                metrics,
                semantic_policy,
            )
            if not validation.passed:
                continue
            semantic_valid += 1
            operation_plan = materialize_plan(
                plan_row["operator_template"], binding
            )
            execution = execute_plan(
                operation_plan,
                binding["input_bindings"],
                fact_map,
            )
            if execution.status != "passed":
                continue
            execution_valid += 1
            binding_hash = _digest(binding)
            executable.append(
                {
                    "binding": binding,
                    "binding_hash": binding_hash,
                    "sampling_stratum": _sampling_stratum(
                        plan_row["motif_family"], binding
                    ),
                    "audit_example_overlap": binding_hash in audit_hashes,
                }
            )
        selected = _stratified_sample(
            executable,
            max(limit, 0),
            int(policy["compiled_max_per_stratum"]),
        )
        binding_rows = []
        matches = []
        semantic_identity = proposal.get("proposal_semantic_id") or proposal.get(
            "motif_signature"
        )
        pattern_id = str(
            proposal.get("static_pattern_id")
            or "mined_" + str(semantic_identity)[:20]
        )
        for item in selected:
            compiled_binding_id = "qacbind_" + _digest(
                [compilation_id, item["binding_hash"]]
            )[:24]
            binding_rows.append(
                {
                    "compiled_binding_id": compiled_binding_id,
                    "compilation_id": compilation_id,
                    "qa_build_id": qa_build_id,
                    "proposal_id": proposal["proposal_id"],
                    "kg_build_id": kg["kg_build_id"],
                    "binding_hash": item["binding_hash"],
                    "binding": item["binding"],
                    "sampling_stratum": item["sampling_stratum"],
                    "semantic_status": "passed",
                    "execution_status": "passed",
                    "audit_example_overlap": item["audit_example_overlap"],
                    "rejection_reasons": [],
                    "created_at": _now(),
                }
            )
            matches.append(
                {
                    **item["binding"],
                    "pattern_id": pattern_id,
                    "pattern_proposal_id": proposal["proposal_id"],
                    "mining_run_id": proposal["mining_run_id"],
                    "pattern_proposal_hash": proposal["proposal_hash"],
                    "pattern_score": float(proposal["total_score"]),
                    "pattern_compilation_id": compilation_id,
                    "compiled_binding_id": compiled_binding_id,
                    "compiled_binding_hash": item["binding_hash"],
                    "binding_source": "compiled_query",
                    "audit_example_overlap": item["audit_example_overlap"],
                    "sampling_stratum": item["sampling_stratum"],
                }
            )
        if binding_rows:
            insert_rows(
                db,
                "qa_compiled_bindings",
                binding_rows,
                list(binding_rows[0]),
                {"binding", "sampling_stratum", "rejection_reasons"},
            )
        summary = {
            "selected_count": len(selected),
            "audit_overlap_count": sum(
                bool(item["audit_example_overlap"]) for item in selected
            ),
            "non_audit_count": sum(
                not bool(item["audit_example_overlap"]) for item in selected
            ),
            "stratum_count": len(
                {tuple(item["sampling_stratum"]) for item in selected}
            ),
            "candidate_record_count": len(executable),
        }
        db.execute(
            "UPDATE qa_pattern_compilations SET status = ?, completed_at = ?, "
            "discovered_binding_count = ?, semantic_valid_binding_count = ?, "
            "execution_valid_binding_count = ?, compiled_binding_count = ?, "
            "rejected_binding_count = ?, sampling_summary = ? "
            "WHERE compilation_id = ?",
            (
                "success",
                _now(),
                discovered,
                semantic_valid,
                execution_valid,
                len(selected),
                max(discovered - execution_valid, 0),
                _db_json(db, summary),
                compilation_id,
            ),
        )
        return matches
    except Exception as exc:
        db.execute(
            "UPDATE qa_pattern_compilations SET status = ?, completed_at = ?, "
            "notes = ? WHERE compilation_id = ?",
            (
                "failed",
                _now(),
                _db_json(
                    db,
                    {
                        "binding_source": "compiled_query",
                        "error": str(exc),
                    },
                ),
                compilation_id,
            ),
        )
        raise


def _load_execution_pool(
    db: DBProtocol,
    kg: dict[str, Any],
    metric_ids: list[str],
    rows_per_metric: int,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    selected_metrics = set(metric_ids)
    metrics = {
        str(row["metric_id"]): dict(row)
        for row in db.fetchall(
            "SELECT * FROM metrics WHERE build_id = ?",
            (kg["input_metric_build_id"],),
        )
        if str(row["metric_id"]) in selected_metrics
    }
    facts: list[dict[str, Any]] = []
    for metric_id in metric_ids:
        limit_clause = "LIMIT ?" if rows_per_metric > 0 else ""
        parameters: list[Any] = [
            kg["kg_build_id"],
            kg["input_entity_build_id"],
            kg["input_metric_build_id"],
            kg["input_fact_build_id"],
            metric_id,
        ]
        if rows_per_metric > 0:
            parameters.append(rows_per_metric)
        rows = db.fetchall(
            f"""
            SELECT sf.*, ce.entity_type, ce.market, ce.country, ce.industry,
                   m.canonical_name AS metric_name, m.metric_category,
                   m.statement_type, m.period_type AS ontology_period_type,
                   m.aggregation_rule, m.revision_risk
            FROM standardized_facts sf
            JOIN kg_nodes n ON n.kg_build_id = ? AND n.node_type = 'Fact'
                           AND n.source_pk = sf.fact_id
            JOIN canonical_entities ce ON ce.build_id = ?
                                      AND ce.entity_id = sf.entity_id
            JOIN metrics m ON m.build_id = ? AND m.metric_id = sf.metric_id
            WHERE sf.build_id = ? AND sf.metric_id = ? AND sf.graph_ready = 1
              AND sf.normalized_value IS NOT NULL
              AND sf.normalized_unit IS NOT NULL
              AND COALESCE(sf.is_forecast, 0) = 0
              AND LOWER(COALESCE(sf.comparability_level, 'comparable'))
                  NOT IN ('blocked', 'incomparable', 'not_comparable',
                          'source_definition_mismatch')
            ORDER BY sf.entity_id, sf.period_end DESC, sf.fact_id
            {limit_clause}
            """,
            parameters,
        )
        facts.extend(_deduplicate_facts(dict(row) for row in rows))
    return facts, metrics


def _execute_family_miner(
    facts: list[dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    plan: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    execution_policy = dict(policy)
    record_limit = max(
        len(facts),
        int(policy["max_candidates_per_proposal"])
        * int(policy["compiled_scan_multiplier"]),
    )
    execution_policy["max_bindings_per_proposal"] = record_limit
    execution_policy["max_heldout_bindings"] = 1
    semantic_policy = comparability_policy(policy.get("semantic_policy"))
    miners = {
        "cross_metric_comparison": _mine_cross_metric_comparison,
        "temporal_aggregation": _mine_temporal_aggregation,
        "temporal_extrema_followup": _mine_temporal_followup,
        "scope_rank_followup": _mine_scope_rank_followup,
    }
    return miners[plan["motif_family"]](
        facts,
        metrics,
        execution_policy,
        semantic_policy,
    )


def _sampling_stratum(family: str, binding: dict[str, Any]) -> list[str]:
    metrics = [str(value) for value in binding.get("metric_ids") or []]
    entity_bucket = "entity_bucket_" + str(
        int(_digest(sorted(binding.get("entity_ids") or []))[:8], 16) % 8
    )
    if family == "scope_rank_followup":
        values = [*metrics, binding.get("industry"), binding.get("period")]
    elif family in {"temporal_aggregation", "temporal_extrema_followup"}:
        values = [
            *metrics,
            binding.get("frequency"),
            binding.get("end_period"),
        ]
    else:
        values = [*metrics, binding.get("frequency"), binding.get("period")]
    if family != "scope_rank_followup":
        values.append(entity_bucket)
    return [str(value or "unknown") for value in values]


def _stratified_sample(
    candidates: list[dict[str, Any]], limit: int, max_per_stratum: int
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        groups[tuple(candidate["sampling_stratum"])].append(candidate)
    for rows in groups.values():
        rows.sort(
            key=lambda item: (
                bool(item["audit_example_overlap"]),
                item["binding_hash"],
            )
        )
    selected = []
    for index in range(max_per_stratum):
        for key in sorted(groups, key=lambda value: _digest(value)):
            if index < len(groups[key]):
                selected.append(groups[key][index])
                if len(selected) >= limit:
                    return selected
    return selected


def _digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_json(db: DBProtocol, value: Any) -> Any:
    if db.__class__.__name__ == "PostgresMetadataDB":
        from psycopg.types.json import Jsonb

        return Jsonb(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
