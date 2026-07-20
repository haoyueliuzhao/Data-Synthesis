from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol
from finraw.kg_query import resolve_kg_build_id
from finraw.qa.comparability import (
    annual_duration_valid,
    comparability_policy,
    fact_frequency,
    latest_contiguous_window,
    period_index,
    period_label,
)
from finraw.qa.graph_patterns import (
    get_pattern,
    pattern_content_hash,
    pattern_manifest,
    pattern_semantic_components,
    pattern_semantic_digest,
)
from finraw.qa.plans import execute_plan, materialize_plan
from finraw.qa.schema import ensure_qa_schema
from finraw.qa.semantic_constraints import validate_semantic_constraints
from finraw.qa.store import insert_rows, json_value


MINING_VERSION = "2.3.0"

GRAPH_NATIVE_EXECUTABLE_FAMILIES = {
    "derived_fact_composition",
    "fact_provenance",
    "time_hierarchy",
    "entity_set_scope",
}

MINING_RUN_TRANSITIONS = {
    "success": {"reviewed"},
    "reviewed": {"approved_for_qa"},
    "approved_for_qa": {"superseded"},
}


@dataclass(frozen=True, order=True)
class TemporalSeriesKey:
    entity_id: str
    metric_id: str
    source_id: str
    source_definition_id: str
    frequency: str
    time_basis: str
    metric_period_type: str
    financial_scope: tuple[str, str]
    normalized_unit: str
    normalized_currency: str
    seasonal_adjustment: str
    vintage_policy: str
    comparability_level: str


@dataclass(frozen=True)
class ScopeContextKey:
    industry: str
    period: tuple[Any, ...]
    source_id: str
    frequency: str
    time_basis: str
    financial_scope_type: str
    seasonal_adjustment: str
    vintage_policy: str
    comparability_level: str


@dataclass(frozen=True, order=True)
class ScopeMetricVariant:
    metric_id: str
    source_definition_id: str
    metric_period_type: str
    normalized_unit: str
    normalized_currency: str


@dataclass(frozen=True)
class PatternProposal:
    proposal_id: str
    mining_run_id: str
    kg_build_id: str
    motif_family: str
    motif_signature: str
    proposal_semantic_id: str
    proposal_snapshot_id: str
    static_pattern_id: str | None
    pattern_semantic_digest: str
    static_pattern_version: int | None
    static_pattern_hash: str | None
    binding_mode: str
    pattern_spec: dict[str, Any]
    operator_dag_template: dict[str, Any]
    answer_schema: dict[str, Any]
    binding_examples: list[dict[str, Any]]
    heldout_bindings: list[dict[str, Any]]
    semantic_validation_results: dict[str, Any]
    operation_validation_results: dict[str, Any]
    lifecycle_events: list[dict[str, Any]]
    support_count: int
    entity_count: int
    metric_count: int
    period_count: int
    support_score: float
    completeness_score: float
    financial_value_score: float
    complexity_score: float
    novelty_score: float
    total_score: float
    semantic_constraint_pass_rate: float
    operation_execution_pass_rate: float
    example_binding_pass_rate: float
    heldout_binding_pass_rate: float
    static_pattern_overlap: float
    binding_diversity_score: float
    manual_review_status: str
    status: str
    rejection_reasons: list[str]
    proposal_hash: str
    created_at: str

    def as_row(self) -> dict[str, Any]:
        return asdict(self)


def mining_policy(config: dict[str, Any]) -> dict[str, Any]:
    qa = config.get("qa", {})
    raw = qa.get("pattern_mining", {})
    walk_raw = dict(raw.get("walk_mining") or {})
    return {
        "enabled": bool(raw.get("enabled", False)),
        "auto_run": bool(raw.get("auto_run", False)),
        "auto_approve_for_qa": bool(raw.get("auto_approve_for_qa", False)),
        "families": tuple(
            raw.get(
                "families",
                [
                    "cross_metric_comparison",
                    "temporal_aggregation",
                    "temporal_extrema_followup",
                    "scope_rank_followup",
                    "derived_fact_composition",
                    "fact_provenance",
                    "time_hierarchy",
                    "entity_set_scope",
                ],
            )
        ),
        "max_metrics": max(int(raw.get("max_metrics", 24)), 2),
        "rows_per_metric": max(int(raw.get("rows_per_metric", 3000)), 100),
        "pool_scan_rows_per_metric": max(
            int(raw.get("pool_scan_rows_per_metric", 0)), 0
        ),
        "business_value_quota_ratio": min(
            max(float(raw.get("business_value_quota_ratio", 0.4)), 0.0), 1.0
        ),
        "business_value_metric_ids": tuple(
            str(value)
            for value in raw.get(
                "business_value_metric_ids",
                [
                    "revenue",
                    "gross_profit",
                    "operating_income",
                    "net_income",
                    "operating_cash_flow",
                    "cash_and_cash_equivalents",
                    "total_assets",
                    "total_liabilities",
                    "long_term_debt",
                    "research_and_development_expense",
                ],
            )
        ),
        "pool_year_bucket_size": max(int(raw.get("pool_year_bucket_size", 5)), 1),
        "graph_native_mining_enabled": bool(
            raw.get("graph_native_mining_enabled", True)
        ),
        "graph_native_proposals_enabled": bool(
            raw.get("graph_native_proposals_enabled", True)
        ),
        "graph_native_example_limit": max(
            int(raw.get("graph_native_example_limit", 20)), 1
        ),
        "max_proposals": max(int(raw.get("max_proposals", 100)), 1),
        "max_bindings_per_proposal": max(
            int(raw.get("max_bindings_per_proposal", 20)), 1
        ),
        "max_heldout_bindings": max(int(raw.get("max_heldout_bindings", 100)), 1),
        "heldout_fraction": min(max(float(raw.get("heldout_fraction", 0.2)), 0.0), 0.5),
        "minimum_heldout_bindings": max(int(raw.get("minimum_heldout_bindings", 1)), 0),
        "minimum_semantic_constraint_pass_rate": min(
            max(float(raw.get("minimum_semantic_constraint_pass_rate", 0.95)), 0.0),
            1.0,
        ),
        "minimum_operation_execution_pass_rate": min(
            max(float(raw.get("minimum_operation_execution_pass_rate", 0.99)), 0.0),
            1.0,
        ),
        "minimum_heldout_binding_pass_rate": min(
            max(float(raw.get("minimum_heldout_binding_pass_rate", 0.99)), 0.0),
            1.0,
        ),
        "require_manual_review": bool(raw.get("require_manual_review", False)),
        "max_candidates_per_proposal": max(
            int(raw.get("max_candidates_per_proposal", 10)), 1
        ),
        "compiled_metric_fact_cache_enabled": bool(
            raw.get("compiled_metric_fact_cache_enabled", True)
        ),
        "compiled_graph_scan_rows": max(
            int(raw.get("compiled_graph_scan_rows", 5000)), 0
        ),
        "compiled_graph_evaluation_rows": max(
            int(raw.get("compiled_graph_evaluation_rows", 5000)), 0
        ),
        "compiled_scan_rows_per_metric": max(
            int(raw.get("compiled_scan_rows_per_metric", 0)), 0
        ),
        "compiled_scan_multiplier": max(
            int(raw.get("compiled_scan_multiplier", 20)), 1
        ),
        "compiled_max_per_stratum": max(int(raw.get("compiled_max_per_stratum", 4)), 1),
        "min_support": max(int(raw.get("min_support", 3)), 1),
        "target_support": max(int(raw.get("target_support", 20)), 2),
        "min_total_score": float(raw.get("min_total_score", 0.62)),
        "minimum_temporal_observations": max(
            int(raw.get("minimum_temporal_observations", 3)), 2
        ),
        "maximum_temporal_observations": max(
            int(raw.get("maximum_temporal_observations", 5)), 3
        ),
        "minimum_scope_entities": max(int(raw.get("minimum_scope_entities", 3)), 2),
        "top_k": max(int(raw.get("top_k", 3)), 1),
        "require_contiguous_periods": bool(raw.get("require_contiguous_periods", True)),
        "walk_mining": {
            "enabled": bool(walk_raw.get("enabled", False)),
            "grammar_version": str(walk_raw.get("grammar_version") or "1.0.0"),
            "operation_macros": tuple(
                str(value)
                for value in walk_raw.get(
                    "operation_macros",
                    [
                        "temporal_extreme_followup_provenance",
                        "scope_filter_rank_followup",
                        "derived_fact_time_source_trace",
                    ],
                )
            ),
            "beam_width": max(int(walk_raw.get("beam_width", 100)), 1),
            "minimum_estimated_support": max(
                int(walk_raw.get("minimum_estimated_support", 10)), 1
            ),
            "minimum_completion_rate": min(
                max(float(walk_raw.get("minimum_completion_rate", 0.8)), 0.0), 1.0
            ),
            "minimum_unique_answer_rate": min(
                max(float(walk_raw.get("minimum_unique_answer_rate", 0.99)), 0.0), 1.0
            ),
            "maximum_estimated_query_cost": max(
                float(walk_raw.get("maximum_estimated_query_cost", 1000)), 0.0
            ),
            "maximum_query_graph_candidates": max(
                int(walk_raw.get("maximum_query_graph_candidates", 500)), 1
            ),
        },
    }


def mine_qa_patterns(
    db: DBProtocol,
    config: dict[str, Any],
    *,
    kg_build_id: str | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    ensure_qa_schema(db)
    policy = mining_policy(config)
    if policy["auto_approve_for_qa"] and policy["require_manual_review"]:
        raise ValueError(
            "qa.pattern_mining.auto_approve_for_qa cannot be combined with "
            "require_manual_review"
        )
    semantic_policy = comparability_policy(
        config.get("qa", {}).get("graph_patterns", {}).get("comparability")
    )
    kg_build_id = resolve_kg_build_id(db, kg_build_id)
    kg_row = db.fetchone(
        "SELECT * FROM kg_builds WHERE kg_build_id = ?", (kg_build_id,)
    )
    if not kg_row:
        raise ValueError(f"Unknown KG build: {kg_build_id}")
    kg = dict(kg_row)
    if kg.get("status") != "success" or kg.get("quality_status") != "passed":
        raise RuntimeError(f"KG build is not pattern-mining eligible: {kg_build_id}")

    run_id = (
        "qamining_"
        + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_")
        + uuid.uuid4().hex[:8]
    )
    started_at = _now()
    run = {
        "mining_run_id": run_id,
        "kg_build_id": kg_build_id,
        "mining_version": MINING_VERSION,
        "config_hash": _digest(policy, semantic_policy),
        "status": "running",
        "started_at": started_at,
        "completed_at": None,
        "scanned_fact_count": 0,
        "proposal_count": 0,
        "approved_count": 0,
        "published_proposal_manifest": None,
        "published_proposal_manifest_hash": None,
        "reviewed_at": None,
        "reviewed_by": None,
        "approved_at": None,
        "approved_by": None,
        "superseded_at": None,
        "superseded_by_run_id": None,
        "lifecycle_events": [
            {"stage": "running", "status": "started", "at": started_at}
        ],
        "notes": {"policy": policy, "semantic_policy": semantic_policy},
    }
    insert_rows(
        db,
        "qa_pattern_mining_runs",
        [run],
        list(run),
        {"lifecycle_events", "notes", "published_proposal_manifest"},
    )
    graph_observations: list[dict[str, Any]] = []
    walk_observations: list[dict[str, Any]] = []
    try:
        facts, metrics = _load_mining_pool(db, kg, policy)
        if policy["graph_native_mining_enabled"]:
            graph_observations = _mine_graph_native_topology(
                db, run_id, kg_build_id, policy["graph_native_example_limit"]
            )
        proposals = _discover_proposals(
            facts,
            db,
            kg,
            metrics,
            run_id,
            kg_build_id,
            policy,
            semantic_policy,
            graph_observations,
            walk_observations,
        )
        if walk_observations:
            insert_rows(
                db,
                "qa_graph_walk_observations",
                walk_observations,
                list(walk_observations[0]),
                {"query_graph_ir", "stratum_coverage", "rejection_reasons"},
            )
        rows = [proposal.as_row() for proposal in proposals]
        if rows:
            insert_rows(
                db,
                "qa_pattern_proposals",
                rows,
                list(rows[0]),
                {
                    "pattern_spec",
                    "operator_dag_template",
                    "answer_schema",
                    "binding_examples",
                    "heldout_bindings",
                    "semantic_validation_results",
                    "operation_validation_results",
                    "lifecycle_events",
                    "rejection_reasons",
                },
            )
        approved = sum(proposal.status == "published" for proposal in proposals)
        completed_at = _now()
        graph_summary = {
            "executable_proposal_count": sum(
                proposal.motif_family in GRAPH_NATIVE_EXECUTABLE_FAMILIES
                for proposal in proposals
            ),
            "published_executable_proposal_count": sum(
                proposal.motif_family in GRAPH_NATIVE_EXECUTABLE_FAMILIES
                and proposal.status == "published"
                for proposal in proposals
            ),
            "observation_count": len(graph_observations),
            "supported_count": sum(
                item["status"] == "observed" for item in graph_observations
            ),
            "support_by_family": {
                item["motif_family"]: item["support_count"]
                for item in graph_observations
            },
        }
        run_events = [
            *run["lifecycle_events"],
            {"stage": "success", "status": "passed", "at": completed_at},
        ]
        db.execute(
            "UPDATE qa_pattern_mining_runs SET status = ?, completed_at = ?, "
            "scanned_fact_count = ?, proposal_count = ?, "
            "lifecycle_events = ?, notes = ? "
            "WHERE mining_run_id = ?",
            (
                "success",
                completed_at,
                len(facts),
                len(proposals),
                _db_json(db, run_events),
                _db_json(
                    db,
                    {
                        **run["notes"],
                        "graph_native_mining": graph_summary,
                        "typed_walk_mining": {
                            "enabled": policy["walk_mining"]["enabled"],
                            "observation_count": len(walk_observations),
                            "accepted_count": sum(
                                item["status"] == "observed"
                                for item in walk_observations
                            ),
                            "support_by_macro": {
                                item["operation_macro_id"]: item[
                                    "completed_binding_count"
                                ]
                                for item in walk_observations
                            },
                        },
                    },
                ),
                run_id,
            ),
        )
        run_status = "success"
        if policy["auto_approve_for_qa"]:
            reviewer = "policy:auto_approve_for_qa"
            transition_mining_run(
                db,
                run_id,
                target_status="reviewed",
                reviewer=reviewer,
                notes="Development-only automatic review policy.",
            )
            transition_mining_run(
                db,
                run_id,
                target_status="approved_for_qa",
                reviewer=reviewer,
                notes="Development-only automatic QA approval policy.",
            )
            run_status = "approved_for_qa"
    except Exception as exc:
        _rollback(db)
        failed_at = _now()
        failed_events = [
            *run["lifecycle_events"],
            {
                "stage": "failed",
                "status": "failed",
                "at": failed_at,
                "error": str(exc),
            },
        ]
        db.execute(
            "UPDATE qa_pattern_mining_runs SET status = ?, completed_at = ?, "
            "lifecycle_events = ?, notes = ? "
            "WHERE mining_run_id = ?",
            (
                "failed",
                failed_at,
                _db_json(db, failed_events),
                _db_json(
                    db,
                    {
                        "policy": policy,
                        "semantic_policy": semantic_policy,
                        "error": str(exc),
                    },
                ),
                run_id,
            ),
        )
        raise

    family_counts: dict[str, int] = defaultdict(int)
    approved_family_counts: dict[str, int] = defaultdict(int)
    lifecycle_counts: dict[str, int] = defaultdict(int)
    for proposal in proposals:
        family_counts[proposal.motif_family] += 1
        lifecycle_counts[proposal.status] += 1
        if proposal.status == "published":
            approved_family_counts[proposal.motif_family] += 1
    published_proposals = [
        proposal for proposal in proposals if proposal.status == "published"
    ]
    published_validation = {
        "minimum_semantic_constraint_pass_rate": min(
            (item.semantic_constraint_pass_rate for item in published_proposals),
            default=0.0,
        ),
        "minimum_operation_execution_pass_rate": min(
            (item.operation_execution_pass_rate for item in published_proposals),
            default=0.0,
        ),
        "minimum_example_binding_pass_rate": min(
            (item.example_binding_pass_rate for item in published_proposals),
            default=0.0,
        ),
        "minimum_heldout_binding_pass_rate": min(
            (item.heldout_binding_pass_rate for item in published_proposals),
            default=0.0,
        ),
        "static_pattern_overlap_range": [
            min(
                (item.static_pattern_overlap for item in published_proposals),
                default=0.0,
            ),
            max(
                (item.static_pattern_overlap for item in published_proposals),
                default=0.0,
            ),
        ],
        "binding_diversity_score_range": [
            min(
                (item.binding_diversity_score for item in published_proposals),
                default=0.0,
            ),
            max(
                (item.binding_diversity_score for item in published_proposals),
                default=0.0,
            ),
        ],
    }
    report = {
        "mining_run_id": run_id,
        "kg_build_id": kg_build_id,
        "mining_version": MINING_VERSION,
        "run_status": run_status,
        "scanned_fact_count": len(facts),
        "scanned_metric_count": len(metrics),
        "proposal_count": len(proposals),
        "approved_count": approved,
        "published_count": approved,
        "lifecycle_counts": dict(sorted(lifecycle_counts.items())),
        "published_validation_summary": published_validation,
        "proposal_family_counts": dict(sorted(family_counts.items())),
        "approved_family_counts": dict(sorted(approved_family_counts.items())),
        "published_family_counts": dict(sorted(approved_family_counts.items())),
        "graph_native_motifs": {
            "executable_proposal_count": sum(
                proposal.motif_family in GRAPH_NATIVE_EXECUTABLE_FAMILIES
                for proposal in proposals
            ),
            "published_executable_proposal_count": sum(
                proposal.motif_family in GRAPH_NATIVE_EXECUTABLE_FAMILIES
                and proposal.status == "published"
                for proposal in proposals
            ),
            "observation_count": len(graph_observations),
            "supported_count": sum(
                item["status"] == "observed" for item in graph_observations
            ),
            "support_by_family": {
                item["motif_family"]: item["support_count"]
                for item in graph_observations
            },
        },
        "typed_walk_motifs": {
            "observation_count": len(walk_observations),
            "accepted_count": sum(
                item["status"] == "observed" for item in walk_observations
            ),
            "by_macro": {
                item["operation_macro_id"]: {
                    "status": item["status"],
                    "estimated_support_count": item["estimated_support_count"],
                    "evaluated_binding_count": item["evaluated_binding_count"],
                    "structurally_completed_binding_count": item[
                        "structurally_completed_binding_count"
                    ],
                    "completed_binding_count": item["completed_binding_count"],
                    "structural_completion_rate": item["structural_completion_rate"],
                    "answer_yield_rate": item["answer_yield_rate"],
                    "unique_answer_rate": item["unique_answer_rate"],
                    "root_coverage_rate": item["root_coverage_rate"],
                    "evaluation_coverage_rate": item["evaluation_coverage_rate"],
                    "rejection_reasons": item["rejection_reasons"],
                }
                for item in walk_observations
            },
        },
        "top_proposals": [
            {
                "proposal_id": item.proposal_id,
                "motif_family": item.motif_family,
                "motif_signature": item.motif_signature,
                "proposal_semantic_id": item.proposal_semantic_id,
                "proposal_snapshot_id": item.proposal_snapshot_id,
                "static_pattern_id": item.static_pattern_id,
                "binding_mode": item.binding_mode,
                "support_count": item.support_count,
                "total_score": item.total_score,
                "semantic_constraint_pass_rate": item.semantic_constraint_pass_rate,
                "operation_execution_pass_rate": item.operation_execution_pass_rate,
                "example_binding_pass_rate": item.example_binding_pass_rate,
                "heldout_binding_pass_rate": item.heldout_binding_pass_rate,
                "static_pattern_overlap": item.static_pattern_overlap,
                "binding_diversity_score": item.binding_diversity_score,
                "manual_review_status": item.manual_review_status,
                "status": item.status,
            }
            for family in sorted({item.motif_family for item in proposals})
            for item in [value for value in proposals if value.motif_family == family][
                :5
            ]
        ],
    }
    _write_report(report, output_dir)
    return report


def load_published_proposals(
    db: DBProtocol,
    kg_build_id: str,
    mining_run_id: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    get_approved_mining_run(db, kg_build_id, mining_run_id)
    rows = db.fetchall(
        """
        SELECT p.* FROM qa_pattern_proposals p
        JOIN qa_pattern_mining_runs r ON r.mining_run_id = p.mining_run_id
        WHERE p.kg_build_id = ? AND p.mining_run_id = ?
          AND p.status = 'published' AND r.status = 'approved_for_qa'
        ORDER BY p.total_score DESC, p.support_count DESC, p.proposal_id
        LIMIT ?
        """,
        (kg_build_id, mining_run_id, limit),
    )
    json_columns = {
        "pattern_spec",
        "operator_dag_template",
        "answer_schema",
        "binding_examples",
        "heldout_bindings",
        "semantic_validation_results",
        "operation_validation_results",
        "lifecycle_events",
        "rejection_reasons",
    }
    list_columns = {
        "binding_examples",
        "heldout_bindings",
        "lifecycle_events",
        "rejection_reasons",
    }
    return [
        {
            **dict(row),
            **{
                column: json_value(
                    dict(row).get(column), [] if column in list_columns else {}
                )
                for column in json_columns
            },
        }
        for row in rows
    ]


def load_approved_proposals(
    db: DBProtocol,
    kg_build_id: str,
    mining_run_id: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Compatibility alias; only fully published proposals are returned."""
    return load_published_proposals(db, kg_build_id, mining_run_id, limit=limit)


def get_approved_mining_run(
    db: DBProtocol,
    kg_build_id: str,
    mining_run_id: str,
) -> dict[str, Any]:
    """Return an explicitly pinned Mining Run after formal QA eligibility checks."""
    ensure_qa_schema(db)
    row = db.fetchone(
        "SELECT * FROM qa_pattern_mining_runs WHERE mining_run_id = ?",
        (mining_run_id,),
    )
    if not row:
        raise ValueError(f"Unknown QA pattern Mining Run: {mining_run_id}")
    run = _mining_run_dict(row)
    if str(run.get("kg_build_id")) != kg_build_id:
        raise ValueError(
            f"Mining Run {mining_run_id} belongs to {run.get('kg_build_id')}, "
            f"not {kg_build_id}"
        )
    if run.get("status") != "approved_for_qa":
        raise RuntimeError(
            f"Mining Run {mining_run_id} is not QA eligible: "
            f"status={run.get('status')}; expected approved_for_qa"
        )

    audit = _validate_mining_run_proposals(db, run, require_resolved=True)
    stored_manifest = run.get("published_proposal_manifest")
    stored_hash = str(run.get("published_proposal_manifest_hash") or "")
    if not stored_manifest or not stored_hash:
        raise RuntimeError(
            f"Mining Run {mining_run_id} has no frozen published proposal manifest"
        )
    if int(run.get("approved_count") or 0) != audit["published_count"]:
        raise RuntimeError(
            f"Mining Run {mining_run_id} approved_count no longer matches proposals"
        )
    if stored_manifest != audit["manifest"] or stored_hash != audit["manifest_hash"]:
        raise RuntimeError(
            f"Mining Run {mining_run_id} published proposal manifest changed"
        )
    return run


def transition_mining_run(
    db: DBProtocol,
    mining_run_id: str,
    *,
    target_status: str,
    reviewer: str,
    notes: str | None = None,
    superseded_by_run_id: str | None = None,
) -> dict[str, Any]:
    """Move a completed Mining Run through its audited QA publication lifecycle."""
    ensure_qa_schema(db)
    normalized_target = target_status.strip().lower()
    with db.transaction():
        updated = _transition_mining_run_transaction(
            db,
            mining_run_id,
            target_status=normalized_target,
            reviewer=reviewer,
            notes=notes,
            superseded_by_run_id=superseded_by_run_id,
        )
    if normalized_target == "approved_for_qa":
        return get_approved_mining_run(db, str(updated["kg_build_id"]), mining_run_id)
    return updated


def _transition_mining_run_transaction(
    db: DBProtocol,
    mining_run_id: str,
    *,
    target_status: str,
    reviewer: str,
    notes: str | None,
    superseded_by_run_id: str | None,
) -> dict[str, Any]:
    row = _mining_run_row_for_transition(db, mining_run_id, target_status)
    if not row:
        raise ValueError(f"Unknown QA pattern Mining Run: {mining_run_id}")
    run = _mining_run_dict(row)
    current_status = str(run.get("status") or "")
    if target_status == current_status:
        return run
    allowed = MINING_RUN_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise ValueError(
            f"Invalid Mining Run transition: {current_status} -> {target_status}"
        )

    changed_at = _now()
    event: dict[str, Any] = {
        "stage": target_status,
        "status": "passed",
        "at": changed_at,
        "reviewer": reviewer,
    }
    if notes:
        event["notes"] = notes

    if target_status == "reviewed":
        audit = _validate_mining_run_proposals(db, run, require_resolved=False)
        event["proposal_state_summary"] = audit["state_summary"]
        events = [*run["lifecycle_events"], event]
        run_notes = {
            **run["notes"],
            "proposal_review_snapshot": {
                "reviewed_at": changed_at,
                "published_count": audit["published_count"],
                "state_summary": audit["state_summary"],
            },
        }
        db.execute(
            "UPDATE qa_pattern_mining_runs SET status = ?, reviewed_at = ?, "
            "reviewed_by = ?, approved_count = ?, "
            "published_proposal_manifest = NULL, "
            "published_proposal_manifest_hash = NULL, lifecycle_events = ?, notes = ? "
            "WHERE mining_run_id = ?",
            (
                target_status,
                changed_at,
                reviewer,
                audit["published_count"],
                _db_json(db, events),
                _db_json(db, run_notes),
                mining_run_id,
            ),
        )
    elif target_status == "approved_for_qa":
        audit = _validate_mining_run_proposals(db, run, require_resolved=True)
        event["published_count"] = audit["published_count"]
        event["published_proposal_manifest_hash"] = audit["manifest_hash"]
        event["proposal_state_summary"] = audit["state_summary"]
        events = [*run["lifecycle_events"], event]
        previous = db.fetchall(
            "SELECT * FROM qa_pattern_mining_runs "
            "WHERE kg_build_id = ? AND status = 'approved_for_qa' "
            "AND mining_run_id <> ?",
            (run["kg_build_id"], mining_run_id),
        )
        for old_row in previous:
            old = _mining_run_dict(old_row)
            old_events = [
                *old["lifecycle_events"],
                {
                    "stage": "superseded",
                    "status": "passed",
                    "at": changed_at,
                    "reviewer": reviewer,
                    "superseded_by_run_id": mining_run_id,
                },
            ]
            db.execute(
                "UPDATE qa_pattern_mining_runs SET status = ?, superseded_at = ?, "
                "superseded_by_run_id = ?, lifecycle_events = ? "
                "WHERE mining_run_id = ?",
                (
                    "superseded",
                    changed_at,
                    mining_run_id,
                    _db_json(db, old_events),
                    old["mining_run_id"],
                ),
            )
        run_notes = {
            **run["notes"],
            "publication_audit": {
                "frozen_at": changed_at,
                "published_count": audit["published_count"],
                "published_proposal_manifest_hash": audit["manifest_hash"],
                "proposal_state_summary": audit["state_summary"],
                "thresholds": audit["thresholds"],
            },
        }
        db.execute(
            "UPDATE qa_pattern_mining_runs SET status = ?, approved_at = ?, "
            "approved_by = ?, approved_count = ?, "
            "published_proposal_manifest = ?, "
            "published_proposal_manifest_hash = ?, lifecycle_events = ?, notes = ? "
            "WHERE mining_run_id = ?",
            (
                target_status,
                changed_at,
                reviewer,
                audit["published_count"],
                _db_json(db, audit["manifest"]),
                audit["manifest_hash"],
                _db_json(db, events),
                _db_json(db, run_notes),
                mining_run_id,
            ),
        )
    else:
        if superseded_by_run_id == mining_run_id:
            raise ValueError("A Mining Run cannot supersede itself")
        events = [*run["lifecycle_events"], event]
        db.execute(
            "UPDATE qa_pattern_mining_runs SET status = ?, superseded_at = ?, "
            "superseded_by_run_id = ?, lifecycle_events = ? "
            "WHERE mining_run_id = ?",
            (
                target_status,
                changed_at,
                superseded_by_run_id,
                _db_json(db, events),
                mining_run_id,
            ),
        )

    updated = db.fetchone(
        "SELECT * FROM qa_pattern_mining_runs WHERE mining_run_id = ?",
        (mining_run_id,),
    )
    return _mining_run_dict(updated)


def _mining_run_row_for_transition(
    db: DBProtocol,
    mining_run_id: str,
    target_status: str,
) -> Any | None:
    row = db.fetchone(
        "SELECT * FROM qa_pattern_mining_runs WHERE mining_run_id = ?",
        (mining_run_id,),
    )
    if (
        not row
        or target_status != "approved_for_qa"
        or db.__class__.__name__ != "PostgresMetadataDB"
    ):
        return row

    kg_build_id = str(row["kg_build_id"])
    locked_rows = db.fetchall(
        "SELECT * FROM qa_pattern_mining_runs WHERE kg_build_id = ? "
        "ORDER BY mining_run_id FOR UPDATE",
        (kg_build_id,),
    )
    return next(
        (
            locked
            for locked in locked_rows
            if str(locked["mining_run_id"]) == mining_run_id
        ),
        None,
    )


def _mining_run_dict(row: Any) -> dict[str, Any]:
    run = dict(row)
    run["lifecycle_events"] = json_value(run.get("lifecycle_events"), [])
    run["notes"] = json_value(run.get("notes"), {})
    run["published_proposal_manifest"] = json_value(
        run.get("published_proposal_manifest"), None
    )
    return run


def _published_manifest_entry(proposal: dict[str, Any]) -> dict[str, Any]:
    static_version = proposal.get("static_pattern_version")
    return {
        "proposal_id": str(proposal["proposal_id"]),
        "proposal_hash": str(proposal["proposal_hash"]),
        "proposal_semantic_id": str(proposal.get("proposal_semantic_id") or ""),
        "proposal_snapshot_id": str(proposal.get("proposal_snapshot_id") or ""),
        "motif_family": str(proposal.get("motif_family") or ""),
        "binding_mode": str(proposal.get("binding_mode") or ""),
        "pattern_semantic_digest": str(proposal.get("pattern_semantic_digest") or ""),
        "static_pattern_id": (
            str(proposal["static_pattern_id"])
            if proposal.get("static_pattern_id") is not None
            else None
        ),
        "static_pattern_version": (
            int(static_version) if static_version is not None else None
        ),
        "static_pattern_hash": (
            str(proposal["static_pattern_hash"])
            if proposal.get("static_pattern_hash") is not None
            else None
        ),
        "support_count": int(proposal.get("support_count") or 0),
        "semantic_constraint_pass_rate": float(
            proposal.get("semantic_constraint_pass_rate") or 0.0
        ),
        "operation_execution_pass_rate": float(
            proposal.get("operation_execution_pass_rate") or 0.0
        ),
        "example_binding_pass_rate": float(
            proposal.get("example_binding_pass_rate") or 0.0
        ),
        "heldout_binding_pass_rate": float(
            proposal.get("heldout_binding_pass_rate") or 0.0
        ),
    }


def _validate_mining_run_proposals(
    db: DBProtocol,
    run: dict[str, Any],
    *,
    require_resolved: bool,
) -> dict[str, Any]:
    proposals = [
        dict(row)
        for row in db.fetchall(
            "SELECT * FROM qa_pattern_proposals WHERE mining_run_id = ? "
            "ORDER BY proposal_id",
            (run["mining_run_id"],),
        )
    ]
    errors: list[str] = []
    expected_count = int(run.get("proposal_count") or 0)
    if len(proposals) != expected_count:
        errors.append(
            f"proposal_count mismatch: run={expected_count}, actual={len(proposals)}"
        )

    policy = run.get("notes", {}).get("policy", {})
    thresholds = {
        "semantic_constraint_pass_rate": float(
            policy.get("minimum_semantic_constraint_pass_rate", 0.95)
        ),
        "operation_execution_pass_rate": float(
            policy.get("minimum_operation_execution_pass_rate", 0.99)
        ),
        "example_binding_pass_rate": 1.0,
        "heldout_binding_pass_rate": float(
            policy.get("minimum_heldout_binding_pass_rate", 0.99)
        ),
    }
    state_counts: Counter[str] = Counter()
    unresolved: list[str] = []
    published: list[dict[str, Any]] = []
    manual_rejected_count = 0
    validation_rejected_count = 0

    for proposal in proposals:
        proposal_id = str(proposal["proposal_id"])
        status = str(proposal.get("status") or "")
        manual_status = str(proposal.get("manual_review_status") or "")
        reasons = json_value(proposal.get("rejection_reasons"), [])
        state_counts[status] += 1

        if manual_status == "rejected" and status != "reviewed_rejected":
            errors.append(
                f"{proposal_id}: manual rejection must use reviewed_rejected status"
            )
        if status == "published":
            published.append(proposal)
            if manual_status in {"pending", "rejected", "not_started"}:
                errors.append(
                    f"{proposal_id}: published proposal has manual status {manual_status}"
                )
            if policy.get("require_manual_review") and manual_status != "approved":
                errors.append(
                    f"{proposal_id}: published proposal lacks manual approval"
                )
            for field, minimum in thresholds.items():
                observed = float(proposal.get(field) or 0.0)
                if observed < minimum:
                    errors.append(f"{proposal_id}: {field}={observed} below {minimum}")
        elif status == "reviewed_rejected":
            manual_rejected_count += 1
            if manual_status != "rejected":
                errors.append(
                    f"{proposal_id}: reviewed_rejected lacks rejected manual status"
                )
            if "manual_review_rejected" not in reasons:
                errors.append(
                    f"{proposal_id}: reviewed_rejected lacks rejection reason"
                )
        elif status in {"proposed", "semantic_validated"}:
            validation_rejected_count += 1
            if not reasons:
                unresolved.append(proposal_id)
        elif status in {"execution_validated", "reviewed_approved"}:
            unresolved.append(proposal_id)
        else:
            errors.append(f"{proposal_id}: unsupported proposal status {status}")

    if require_resolved and unresolved:
        errors.append("unresolved proposals: " + ", ".join(sorted(unresolved)))
    if require_resolved and not published:
        errors.append("at least one published proposal is required")

    manifest = {
        "manifest_version": 1,
        "mining_run_id": str(run["mining_run_id"]),
        "kg_build_id": str(run["kg_build_id"]),
        "published_count": len(published),
        "proposals": [
            _published_manifest_entry(proposal)
            for proposal in sorted(published, key=lambda item: str(item["proposal_id"]))
        ],
    }
    manifest_hash = _digest(manifest)
    state_summary = {
        "proposal_count": len(proposals),
        "published_count": len(published),
        "manual_rejected_count": manual_rejected_count,
        "validation_rejected_count": validation_rejected_count,
        "unresolved_count": len(unresolved),
        "status_counts": dict(sorted(state_counts.items())),
    }
    if errors:
        raise RuntimeError(
            f"Mining Run {run['mining_run_id']} proposal validation failed: "
            + "; ".join(errors)
        )
    return {
        "published_count": len(published),
        "manifest": manifest,
        "manifest_hash": manifest_hash,
        "state_summary": state_summary,
        "thresholds": thresholds,
    }


def _refresh_run_published_count(db: DBProtocol, mining_run_id: str) -> int:
    row = db.fetchone(
        "SELECT COUNT(*) AS count FROM qa_pattern_proposals "
        "WHERE mining_run_id = ? AND status = 'published'",
        (mining_run_id,),
    )
    published_count = int(row["count"] if row else 0)
    db.execute(
        "UPDATE qa_pattern_mining_runs SET approved_count = ?, "
        "published_proposal_manifest = NULL, "
        "published_proposal_manifest_hash = NULL "
        "WHERE mining_run_id = ? AND status IN ('success', 'reviewed')",
        (published_count, mining_run_id),
    )
    return published_count


def review_pattern_proposal(
    db: DBProtocol,
    proposal_id: str,
    *,
    decision: str,
    reviewer: str,
    notes: str | None = None,
    publish: bool = True,
) -> dict[str, Any]:
    """Record a manual decision after execution validation."""
    ensure_qa_schema(db)
    row = db.fetchone(
        "SELECT * FROM qa_pattern_proposals WHERE proposal_id = ?",
        (proposal_id,),
    )
    if not row:
        raise ValueError(f"Unknown pattern proposal: {proposal_id}")
    proposal = dict(row)
    run_row = db.fetchone(
        "SELECT * FROM qa_pattern_mining_runs WHERE mining_run_id = ?",
        (proposal["mining_run_id"],),
    )
    if not run_row:
        raise ValueError(
            f"Unknown Mining Run for pattern proposal: {proposal['mining_run_id']}"
        )
    run = _mining_run_dict(run_row)
    if run.get("status") not in {"success", "reviewed"}:
        raise ValueError(
            f"Mining Run {run['mining_run_id']} no longer accepts proposal reviews: "
            f"status={run.get('status')}"
        )

    current_status = str(proposal.get("status") or "")
    if current_status not in {"execution_validated", "reviewed_approved"}:
        raise ValueError(
            "Manual review requires an execution_validated or reviewed_approved proposal: "
            f"{proposal_id}"
        )
    normalized_decision = decision.strip().lower()
    if normalized_decision not in {"approve", "reject"}:
        raise ValueError("decision must be 'approve' or 'reject'")
    if current_status == "reviewed_approved" and (
        normalized_decision != "approve" or not publish
    ):
        raise ValueError(
            "A reviewed_approved proposal can only transition to published"
        )

    reviewed_at = _now()
    events = json_value(proposal.get("lifecycle_events"), [])
    reasons = json_value(proposal.get("rejection_reasons"), [])
    if normalized_decision == "reject":
        status = "reviewed_rejected"
        manual_status = "rejected"
        if "manual_review_rejected" not in reasons:
            reasons.append("manual_review_rejected")
        event = {
            "stage": status,
            "status": "passed",
            "at": reviewed_at,
            "reviewer": reviewer,
            "decision": "reject",
        }
        if notes:
            event["notes"] = notes
        events.append(event)
    else:
        status = "reviewed_approved"
        manual_status = "approved"
        if current_status == "execution_validated":
            event = {
                "stage": status,
                "status": "passed",
                "at": reviewed_at,
                "reviewer": reviewer,
                "decision": "approve",
            }
            if notes:
                event["notes"] = notes
            events.append(event)
        if publish:
            status = "published"
            events.append(
                {
                    "stage": "published",
                    "status": "passed",
                    "at": reviewed_at,
                    "reviewer": reviewer,
                }
            )

    db.execute(
        "UPDATE qa_pattern_proposals SET status = ?, manual_review_status = ?, "
        "lifecycle_events = ?, rejection_reasons = ? WHERE proposal_id = ?",
        (
            status,
            manual_status,
            _db_json(db, events),
            _db_json(db, reasons),
            proposal_id,
        ),
    )
    approved_count = _refresh_run_published_count(db, str(proposal["mining_run_id"]))
    return {
        "proposal_id": proposal_id,
        "status": status,
        "manual_review_status": manual_status,
        "lifecycle_events": events,
        "rejection_reasons": reasons,
        "approved_count": approved_count,
    }


def _mine_graph_native_topology(
    db: DBProtocol,
    mining_run_id: str,
    kg_build_id: str,
    example_limit: int,
) -> list[dict[str, Any]]:
    observations = [
        _edge_motif_observation(
            db,
            mining_run_id,
            kg_build_id,
            "derived_fact_composition",
            ["DerivedFact", "Fact"],
            ["DERIVED_FROM"],
            example_limit,
        ),
        _scope_motif_observation(db, mining_run_id, kg_build_id, example_limit),
        _edge_motif_observation(
            db,
            mining_run_id,
            kg_build_id,
            "time_hierarchy",
            [
                "TimePeriod",
                "CalendarYear",
                "CalendarMonth",
                "CalendarQuarter",
                "FiscalYear",
                "FiscalYearLabel",
            ],
            [
                "BELONGS_TO_YEAR",
                "BELONGS_TO_MONTH",
                "BELONGS_TO_QUARTER",
                "IN_FISCAL_YEAR",
                "IN_FISCAL_YEAR_LABEL",
                "FISCAL_YEAR_OF",
            ],
            example_limit,
        ),
        _provenance_motif_observation(db, mining_run_id, kg_build_id, example_limit),
        _edge_motif_observation(
            db,
            mining_run_id,
            kg_build_id,
            "cross_source_reconciliation",
            ["Fact"],
            ["SEMANTICALLY_EQUIVALENT_TO", "CONFLICTS_WITH", "SUPERSEDES"],
            example_limit,
        ),
    ]
    insert_rows(
        db,
        "qa_graph_motif_observations",
        observations,
        list(observations[0]),
        {"node_types", "edge_types", "binding_examples"},
    )
    return observations


def _edge_motif_observation(
    db: DBProtocol,
    mining_run_id: str,
    kg_build_id: str,
    motif_family: str,
    node_types: list[str],
    edge_types: list[str],
    example_limit: int,
) -> dict[str, Any]:
    placeholders = ",".join("?" for _ in edge_types)
    counts = db.fetchone(
        f"SELECT COUNT(*) AS support_count, "
        f"COUNT(DISTINCT src_node_id) AS root_count FROM kg_edges "
        f"WHERE kg_build_id = ? AND relation_type IN ({placeholders}) "
        "AND COALESCE(is_active, 1) = 1",
        (kg_build_id, *edge_types),
    )
    examples = [
        dict(row)
        for row in db.fetchall(
            f"SELECT src_node_id AS root_node_id, dst_node_id AS related_node_id, "
            f"relation_type, edge_id FROM kg_edges WHERE kg_build_id = ? "
            f"AND relation_type IN ({placeholders}) "
            "AND COALESCE(is_active, 1) = 1 "
            "ORDER BY relation_type, src_node_id, dst_node_id LIMIT ?",
            (kg_build_id, *edge_types, example_limit),
        )
    ]
    return _motif_observation(
        mining_run_id,
        kg_build_id,
        motif_family,
        node_types,
        edge_types,
        int(counts["support_count"] or 0),
        int(counts["root_count"] or 0),
        examples,
    )


def _scope_motif_observation(
    db: DBProtocol, mining_run_id: str, kg_build_id: str, example_limit: int
) -> dict[str, Any]:
    counts = db.fetchone(
        "SELECT COUNT(*) AS support_count, COUNT(DISTINCT hs.src_node_id) AS root_count "
        "FROM kg_edges hs JOIN kg_edges ce ON ce.kg_build_id = hs.kg_build_id "
        "AND ce.src_node_id = hs.dst_node_id AND ce.relation_type = 'CONTAINS_ENTITY' "
        "WHERE hs.kg_build_id = ? AND hs.relation_type = 'HAS_SCOPE' "
        "AND COALESCE(hs.is_active, 1) = 1 "
        "AND COALESCE(ce.is_active, 1) = 1",
        (kg_build_id,),
    )
    examples = [
        dict(row)
        for row in db.fetchall(
            "SELECT hs.src_node_id AS root_node_id, hs.dst_node_id AS scope_node_id, "
            "ce.dst_node_id AS entity_node_id, hs.edge_id AS scope_edge_id, "
            "ce.edge_id AS membership_edge_id FROM kg_edges hs "
            "JOIN kg_edges ce ON ce.kg_build_id = hs.kg_build_id "
            "AND ce.src_node_id = hs.dst_node_id AND ce.relation_type = 'CONTAINS_ENTITY' "
            "WHERE hs.kg_build_id = ? AND hs.relation_type = 'HAS_SCOPE' "
            "AND COALESCE(hs.is_active, 1) = 1 "
            "AND COALESCE(ce.is_active, 1) = 1 "
            "ORDER BY hs.src_node_id, ce.dst_node_id LIMIT ?",
            (kg_build_id, example_limit),
        )
    ]
    return _motif_observation(
        mining_run_id,
        kg_build_id,
        "entity_set_scope",
        ["DerivedFact", "EntitySet", "Entity"],
        ["HAS_SCOPE", "CONTAINS_ENTITY"],
        int(counts["support_count"] or 0),
        int(counts["root_count"] or 0),
        examples,
    )


def _provenance_motif_observation(
    db: DBProtocol, mining_run_id: str, kg_build_id: str, example_limit: int
) -> dict[str, Any]:
    edge_types = ["FROM_SOURCE", "TRACED_TO", "USES_SOURCE_DEFINITION"]
    placeholders = ",".join("?" for _ in edge_types)
    roots = [
        dict(row)
        for row in db.fetchall(
            f"SELECT e.src_node_id AS root_node_id, "
            f"COUNT(DISTINCT e.relation_type) AS relation_count FROM kg_edges e "
            "JOIN kg_nodes n ON n.kg_build_id = e.kg_build_id "
            "AND n.node_id = e.src_node_id AND n.node_type = 'Fact' "
            f"WHERE e.kg_build_id = ? AND e.relation_type IN ({placeholders}) "
            "AND COALESCE(e.is_active, 1) = 1 GROUP BY e.src_node_id "
            "HAVING COUNT(DISTINCT e.relation_type) = 3 ORDER BY e.src_node_id",
            (kg_build_id, *edge_types),
        )
    ]
    return _motif_observation(
        mining_run_id,
        kg_build_id,
        "fact_provenance",
        ["Fact", "DataSource", "SourceDefinition", "RawObject"],
        edge_types,
        len(roots),
        len(roots),
        roots[:example_limit],
    )


def _motif_observation(
    mining_run_id: str,
    kg_build_id: str,
    motif_family: str,
    node_types: list[str],
    edge_types: list[str],
    support_count: int,
    distinct_root_count: int,
    examples: list[dict[str, Any]],
) -> dict[str, Any]:
    signature = _digest(motif_family, sorted(node_types), sorted(edge_types))
    return {
        "observation_id": "qamotif_" + _digest(mining_run_id, signature)[:24],
        "mining_run_id": mining_run_id,
        "kg_build_id": kg_build_id,
        "motif_family": motif_family,
        "motif_signature": signature,
        "node_types": sorted(node_types),
        "edge_types": sorted(edge_types),
        "support_count": support_count,
        "distinct_root_count": distinct_root_count,
        "binding_examples": examples,
        "status": "observed" if support_count else "unsupported",
        "created_at": _now(),
    }


def _load_mining_pool(
    db: DBProtocol, kg: dict[str, Any], policy: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    metric_rows = db.fetchall(
        """
        SELECT sf.metric_id, m.metric_category, m.statement_type,
               COUNT(*) AS fact_count,
               COUNT(DISTINCT sf.source_id) AS source_count,
               COUNT(DISTINCT sf.entity_id) AS entity_count
        FROM standardized_facts sf
        JOIN kg_nodes n ON n.kg_build_id = ? AND n.node_type = 'Fact'
                       AND n.source_pk = sf.fact_id
        JOIN metrics m ON m.build_id = ? AND m.metric_id = sf.metric_id
        WHERE sf.build_id = ? AND sf.graph_ready = 1
          AND sf.normalized_value IS NOT NULL AND sf.normalized_unit IS NOT NULL
          AND COALESCE(sf.is_forecast, 0) = 0
          AND LOWER(COALESCE(sf.comparability_level, 'comparable'))
              NOT IN ('blocked', 'incomparable', 'not_comparable',
                      'source_definition_mismatch')
        GROUP BY sf.metric_id, m.metric_category, m.statement_type
        ORDER BY fact_count DESC, sf.metric_id
        """,
        (
            kg["kg_build_id"],
            kg["input_metric_build_id"],
            kg["input_fact_build_id"],
        ),
    )
    selected_metric_rows = _select_metric_pool(
        [dict(row) for row in metric_rows], policy
    )
    metric_ids = [str(row["metric_id"]) for row in selected_metric_rows]
    if not metric_ids:
        return [], {}
    placeholders = ",".join("?" for _ in metric_ids)
    ontology_rows = db.fetchall(
        f"""
        SELECT metric_id, canonical_name, metric_category, statement_type,
               period_type, aggregation_rule, revision_risk, ambiguity_notes
        FROM metrics
        WHERE build_id = ? AND metric_id IN ({placeholders})
        """,
        (kg["input_metric_build_id"], *metric_ids),
    )
    metrics = {str(row["metric_id"]): dict(row) for row in ontology_rows}
    facts: list[dict[str, Any]] = []
    density_by_metric = {
        str(row["metric_id"]): _density_bucket(int(row["fact_count"]))
        for row in selected_metric_rows
    }
    for metric_id in metric_ids:
        scan_limit = int(policy["pool_scan_rows_per_metric"])
        limit_clause = "LIMIT ?" if scan_limit > 0 else ""
        parameters: list[Any] = [
            kg["kg_build_id"],
            kg["input_entity_build_id"],
            kg["input_metric_build_id"],
            kg["input_fact_build_id"],
            metric_id,
        ]
        if scan_limit > 0:
            parameters.append(scan_limit)
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
            ORDER BY sf.fact_id
            {limit_clause}
            """,
            parameters,
        )
        deduplicated = _deduplicate_facts(dict(row) for row in rows)
        facts.extend(
            _stratified_fact_sample(
                deduplicated,
                policy["rows_per_metric"],
                density_by_metric[metric_id],
                policy["pool_year_bucket_size"],
            )
        )
    return facts, metrics


def _select_metric_pool(
    metric_rows: list[dict[str, Any]], policy: dict[str, Any]
) -> list[dict[str, Any]]:
    if not metric_rows:
        return []
    limit = min(int(policy["max_metrics"]), len(metric_rows))
    business_ids = set(policy["business_value_metric_ids"])
    business_quota = min(
        round(limit * float(policy["business_value_quota_ratio"])),
        limit,
    )
    business = [row for row in metric_rows if str(row["metric_id"]) in business_ids]
    support = sorted(
        metric_rows,
        key=lambda row: (-int(row["fact_count"]), str(row["metric_id"])),
    )
    selected = _round_robin_metric_strata(business, business_quota)
    selected_ids = {str(row["metric_id"]) for row in selected}
    selected.extend(
        row
        for row in _round_robin_metric_strata(support, limit)
        if str(row["metric_id"]) not in selected_ids
    )
    return selected[:limit]


def _round_robin_metric_strata(
    rows: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    strata: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("metric_category") or "unknown"),
            str(row.get("statement_type") or "unknown"),
            _density_bucket(int(row.get("fact_count") or 0)),
        )
        strata[key].append(row)
    for values in strata.values():
        values.sort(
            key=lambda row: (-int(row.get("fact_count") or 0), str(row["metric_id"]))
        )
    return _round_robin_rows(strata, limit)


def _stratified_fact_sample(
    rows: list[dict[str, Any]],
    limit: int,
    density_bucket: str,
    year_bucket_size: int,
) -> list[dict[str, Any]]:
    strata: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        year = row.get("fiscal_year") or row.get("calendar_year")
        try:
            year_bucket = str((int(year) // year_bucket_size) * year_bucket_size)
        except (TypeError, ValueError):
            year_bucket = "unknown"
        key = (
            str(row.get("metric_category") or "unknown"),
            str(row.get("statement_type") or "unknown"),
            str(row.get("source_id") or "unknown"),
            str(row.get("industry") or "unknown"),
            str(row.get("entity_type") or "unknown"),
            year_bucket,
            fact_frequency(row),
            density_bucket,
        )
        strata[key].append(row)
    for values in strata.values():
        values.sort(key=lambda row: _digest(str(row.get("fact_id") or "")))
    return _round_robin_rows(strata, min(limit, len(rows)))


def _round_robin_rows(
    strata: dict[tuple[Any, ...], list[dict[str, Any]]], limit: int
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    depth = 0
    keys = sorted(strata, key=_digest)
    while len(selected) < limit:
        added = False
        for key in keys:
            if depth < len(strata[key]):
                selected.append(strata[key][depth])
                added = True
                if len(selected) >= limit:
                    break
        if not added:
            break
        depth += 1
    return selected


def _density_bucket(count: int) -> str:
    if count >= 10000:
        return "very_high"
    if count >= 1000:
        return "high"
    if count >= 100:
        return "medium"
    return "long_tail"


def _discover_proposals(
    facts: list[dict[str, Any]],
    db: DBProtocol,
    kg: dict[str, Any],
    metrics: dict[str, dict[str, Any]],
    run_id: str,
    kg_build_id: str,
    policy: dict[str, Any],
    semantic_policy: dict[str, Any],
    graph_observations: list[dict[str, Any]],
    walk_observations: list[dict[str, Any]],
) -> list[PatternProposal]:
    raw: list[dict[str, Any]] = []
    families = set(policy["families"])
    if "cross_metric_comparison" in families:
        raw.extend(
            _mine_cross_metric_comparison(facts, metrics, policy, semantic_policy)
        )
    if "temporal_aggregation" in families:
        raw.extend(_mine_temporal_aggregation(facts, metrics, policy, semantic_policy))
    if "temporal_extrema_followup" in families:
        raw.extend(_mine_temporal_followup(facts, metrics, policy, semantic_policy))
    if "scope_rank_followup" in families:
        raw.extend(_mine_scope_rank_followup(facts, metrics, policy, semantic_policy))
    if policy["graph_native_proposals_enabled"]:
        raw.extend(
            _mine_executable_graph_patterns(
                db,
                kg,
                graph_observations,
                policy,
                semantic_policy,
                families,
            )
        )
    if policy["walk_mining"]["enabled"]:
        walk_raw, observed = _mine_executable_typed_walk_patterns(
            db,
            kg,
            policy,
            semantic_policy,
        )
        for item in observed:
            item["mining_run_id"] = run_id
            item["walk_observation_id"] = (
                "qawalkobs_"
                + _digest(run_id, item["query_graph_hash"], item["status"])[:24]
            )
        raw.extend(walk_raw)
        walk_observations.extend(observed)
    raw = [item for item in raw if item["support_count"] > 0]
    proposals = [_proposal_from_raw(item, run_id, kg_build_id, policy) for item in raw]
    proposals.sort(
        key=lambda item: (-item.total_score, -item.support_count, item.proposal_id)
    )
    return _balanced_select(proposals, policy["max_proposals"])


def _mine_executable_graph_patterns(
    db: DBProtocol,
    kg: dict[str, Any],
    observations: list[dict[str, Any]],
    policy: dict[str, Any],
    semantic_policy: dict[str, Any],
    enabled_families: set[str],
) -> list[dict[str, Any]]:
    from finraw.qa.binding_executor import execute_relational_ops
    from finraw.qa.pattern_compiler import compile_logical_pattern

    supported = {
        str(item["motif_family"])
        for item in observations
        if item.get("status") == "observed" and int(item.get("support_count") or 0) > 0
    }
    record_limit = int(policy["max_bindings_per_proposal"]) + int(
        policy["max_heldout_bindings"]
    )
    output: list[dict[str, Any]] = []
    for family, spec in _graph_native_pattern_specs():
        if family not in supported or family not in enabled_families:
            continue
        semantic_id = "graph_discovery_" + _digest(spec)[:20]
        proposal = {
            "proposal_id": semantic_id,
            "proposal_hash": _digest(semantic_id, spec),
            "proposal_semantic_id": semantic_id,
            "proposal_snapshot_id": semantic_id,
            "mining_run_id": "graph_discovery",
            "kg_build_id": kg["kg_build_id"],
            "motif_family": family,
            "motif_signature": _digest(family, spec),
            "pattern_semantic_digest": pattern_semantic_digest(spec),
            "static_pattern_id": None,
            "static_pattern_version": None,
            "static_pattern_hash": None,
            "static_pattern_overlap": 0.0,
            "binding_mode": "new_pattern",
            "pattern_spec": spec,
            "binding_examples": [],
            "heldout_bindings": [],
            "total_score": 0.0,
            "status": "published",
        }
        execution_policy = {**policy, "semantic_policy": semantic_policy}
        plan = compile_logical_pattern(proposal, kg, execution_policy)
        state = execute_relational_ops(
            db,
            kg,
            plan.as_row(),
            proposal,
            execution_policy,
            audit_hashes=set(),
            limit=record_limit,
        )
        raw = _raw_proposal(family, [], spec)
        raw["evaluated_binding_count"] = state.discovered_count
        raw["support_count"] = state.semantic_valid_count
        raw["operation_evaluated_count"] = state.semantic_valid_count
        raw["operation_pass_count"] = state.execution_valid_count
        for reason, count in state.rejection_counts.items():
            if reason.startswith("semantic:"):
                raw["semantic_rejection_counts"][reason[9:]] += count
            elif reason.startswith("operation:"):
                raw["operation_rejection_counts"][reason[10:]] += count
        raw["binding_validation_records"] = [
            {
                "binding": item["binding"],
                "execution_status": "passed",
                "execution_errors": [],
                "output_hash": item["binding_hash"],
            }
            for item in state.relation
        ]
        output.append(raw)
    return output


def _mine_executable_typed_walk_patterns(
    db: DBProtocol,
    kg: dict[str, Any],
    policy: dict[str, Any],
    semantic_policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from finraw.qa.binding_executor import execute_relational_ops
    from finraw.qa.graph_walk.audit import walk_observation_row
    from finraw.qa.graph_walk.explorer import discover_query_graphs
    from finraw.qa.graph_walk.operation_macros import get_operation_macro
    from finraw.qa.graph_walk.proposal_builder import query_graph_pattern_spec
    from finraw.qa.graph_walk.scorer import score_query_graph
    from finraw.qa.pattern_compiler import compile_logical_pattern

    settings = dict(policy["walk_mining"])
    graphs = discover_query_graphs(
        list(settings["operation_macros"]),
        discovery_method="typed_walk",
        beam_width=int(settings["beam_width"]),
    )[: int(settings["maximum_query_graph_candidates"])]
    record_limit = int(policy["max_bindings_per_proposal"]) + int(
        policy["max_heldout_bindings"]
    )
    execution_policy = {**policy, "semantic_policy": semantic_policy}
    output: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    for graph in graphs:
        spec = query_graph_pattern_spec(graph)
        family = str(spec["pattern_family"])
        semantic_id = "typed_walk_" + graph.query_graph_hash[:20]
        proposal = {
            "proposal_id": semantic_id,
            "proposal_hash": _digest(semantic_id, spec),
            "proposal_semantic_id": semantic_id,
            "proposal_snapshot_id": semantic_id,
            "mining_run_id": "typed_walk_discovery",
            "kg_build_id": kg["kg_build_id"],
            "motif_family": family,
            "motif_signature": graph.query_graph_hash,
            "pattern_semantic_digest": pattern_semantic_digest(spec),
            "static_pattern_id": None,
            "static_pattern_version": None,
            "static_pattern_hash": None,
            "static_pattern_overlap": 0.0,
            "binding_mode": "new_pattern",
            "pattern_spec": spec,
            "binding_examples": [],
            "heldout_bindings": [],
            "total_score": 0.0,
            "status": "published",
        }
        state = None
        execution_error = None
        try:
            plan = compile_logical_pattern(proposal, kg, execution_policy)
            state = execute_relational_ops(
                db,
                kg,
                plan.as_row(),
                proposal,
                execution_policy,
                audit_hashes=set(),
                limit=record_limit,
            )
        except (RuntimeError, ValueError) as exc:
            execution_error = str(exc)

        macro = get_operation_macro(graph.operation_macro_id)
        if state is None:
            estimate = {
                "estimated_support_count": 0,
                "evaluated_binding_count": 0,
                "completed_binding_count": 0,
                "structurally_completed_binding_count": 0,
                "structural_completion_rate": 0.0,
                "answer_yield_rate": 0.0,
                "unique_answer_rate": 0.0,
                "total_root_count": 0,
                "scanned_root_count": 0,
                "root_coverage_rate": 0.0,
                "evaluated_root_count": 0,
                "evaluation_coverage_rate": 0.0,
                "stratum_coverage": [],
            }
            scores = {
                "financial_value_score": macro.financial_value_score,
                "answerability_score": 0.0,
                "novelty_score": 1.0,
                "estimated_cost": _typed_walk_cost(graph),
                "total_score": 0.0,
            }
            observations.append(
                walk_observation_row(
                    mining_run_id="pending",
                    kg_build_id=str(kg["kg_build_id"]),
                    graph=graph,
                    estimate=estimate,
                    scores=scores,
                    status="rejected",
                    rejection_reasons=[f"query_execution_failed:{execution_error}"],
                )
            )
            continue

        fact_map = {str(fact["fact_id"]): fact for fact in state.facts}
        executed_records: list[dict[str, Any]] = []
        for item in state.relation:
            binding = item["binding"]
            execution = execute_plan(
                materialize_plan(spec["operator_template"], binding),
                binding["input_bindings"],
                fact_map,
            )
            if execution.status != "passed":
                continue
            executed_records.append(
                {
                    "binding": binding,
                    "execution_status": "passed",
                    "execution_errors": [],
                    "output_hash": _digest(execution.output),
                    "_semantic_binding_hash": _typed_walk_binding_identity(binding),
                }
            )

        records, unique_answer_rate, completed = _unambiguous_typed_walk_records(
            executed_records
        )
        evaluated = int(state.discovered_count)
        structurally_completed = int(state.semantic_valid_count)
        completion_rate = _rate(structurally_completed, evaluated)
        answer_yield_rate = _rate(completed, structurally_completed)
        estimated_cost = _typed_walk_cost(graph)
        answerability = completion_rate * answer_yield_rate * unique_answer_rate
        total_score = score_query_graph(
            support_rate=min(completed / max(int(policy["target_support"]), 1), 1.0),
            financial_value=macro.financial_value_score,
            answerability=answerability,
            novelty=1.0,
            diversity=min(len(records) / max(record_limit, 1), 1.0),
            estimated_cost=estimated_cost,
            ambiguity=1.0 - unique_answer_rate,
        )
        reasons = []
        if completed < int(settings["minimum_estimated_support"]):
            reasons.append("insufficient_estimated_support")
        if completion_rate < float(settings["minimum_completion_rate"]):
            reasons.append("completion_rate_below_threshold")
        if unique_answer_rate < float(settings["minimum_unique_answer_rate"]):
            reasons.append("unique_answer_rate_below_threshold")
        if estimated_cost > float(settings["maximum_estimated_query_cost"]):
            reasons.append("estimated_query_cost_above_threshold")
        scan_audit = dict(state.graph_scan_audit or {})
        estimate = {
            "estimated_support_count": completed,
            "evaluated_binding_count": evaluated,
            "completed_binding_count": completed,
            "structurally_completed_binding_count": structurally_completed,
            "structural_completion_rate": completion_rate,
            "answer_yield_rate": answer_yield_rate,
            "unique_answer_rate": unique_answer_rate,
            "total_root_count": int(scan_audit.get("total_root_count") or 0),
            "scanned_root_count": int(scan_audit.get("scanned_root_count") or 0),
            "root_coverage_rate": float(scan_audit.get("root_coverage_rate") or 0),
            "evaluated_root_count": int(scan_audit.get("evaluated_root_count") or 0),
            "evaluation_coverage_rate": float(
                scan_audit.get("evaluation_coverage_rate") or 0
            ),
            "stratum_coverage": list(scan_audit.get("stratum_coverage") or []),
        }
        scores = {
            "financial_value_score": macro.financial_value_score,
            "answerability_score": answerability,
            "novelty_score": 1.0,
            "estimated_cost": estimated_cost,
            "total_score": total_score,
        }
        observations.append(
            walk_observation_row(
                mining_run_id="pending",
                kg_build_id=str(kg["kg_build_id"]),
                graph=graph,
                estimate=estimate,
                scores=scores,
                status="rejected" if reasons else "observed",
                rejection_reasons=reasons,
            )
        )
        if reasons:
            continue
        raw = _raw_proposal(
            family,
            list(spec.get("required_metric_ids") or []),
            spec,
        )
        raw["evaluated_binding_count"] = completed
        raw["support_count"] = completed
        raw["operation_evaluated_count"] = completed
        raw["operation_pass_count"] = completed
        for reason, count in state.rejection_counts.items():
            if reason.startswith("semantic:"):
                raw["semantic_rejection_counts"][reason[9:]] += count
            elif reason.startswith("operation:"):
                raw["operation_rejection_counts"][reason[10:]] += count
        raw["binding_validation_records"] = records
        output.append(raw)
    return output, observations


def _typed_walk_binding_identity(binding: dict[str, Any]) -> str:
    return _digest(
        {
            "input_bindings": binding.get("input_bindings") or {},
            "fact_ids": sorted(binding.get("fact_ids") or []),
            "entity_ids": sorted(binding.get("entity_ids") or []),
            "metric_ids": sorted(binding.get("metric_ids") or []),
            "scope_entity_ids": sorted(binding.get("scope_entity_ids") or []),
            "scope_definition": binding.get("scope_definition"),
            "query_graph_hash": binding.get("query_graph_hash"),
        }
    )


def _unambiguous_typed_walk_records(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], float, int]:
    records_by_binding: dict[str, dict[str, Any]] = {}
    answers_by_binding: defaultdict[str, set[str]] = defaultdict(set)
    for record in records:
        binding_hash = str(record["_semantic_binding_hash"])
        answers_by_binding[binding_hash].add(str(record["output_hash"]))
        records_by_binding.setdefault(binding_hash, record)

    unambiguous = {
        binding_hash
        for binding_hash, answer_hashes in answers_by_binding.items()
        if len(answer_hashes) == 1
    }
    selected = [
        {
            key: value
            for key, value in records_by_binding[binding_hash].items()
            if key != "_semantic_binding_hash"
        }
        for binding_hash in sorted(unambiguous)
    ]
    return (
        selected,
        _rate(len(unambiguous), len(answers_by_binding)),
        len(answers_by_binding),
    )


def _typed_walk_cost(graph: Any) -> float:
    step_count = sum(len(walk.get("steps") or []) for walk in graph.walks)
    branch_count = max(len(graph.walks) - 1, 0)
    join_count = len(graph.joins)
    scope_count = sum(
        step.get("to_node_type") == "Entity"
        for walk in graph.walks
        for step in walk.get("steps") or []
    )
    return float(step_count + 1.5 * branch_count + 2.0 * join_count + scope_count)


def _graph_native_pattern_specs() -> list[tuple[str, dict[str, Any]]]:
    return [
        (
            "derived_fact_composition",
            _graph_trace_spec(
                task_subtype="derived_input_trace",
                pattern_family="graph_composition",
                difficulty_base="medium",
                node_constraints=[
                    {"variable": "derived", "type": "DerivedFact"},
                    {
                        "variable": "input_fact",
                        "type": "Fact",
                        "cardinality": "many",
                    },
                ],
                edge_constraints=[
                    {
                        "src": "derived",
                        "relation": "DERIVED_FROM",
                        "dst": "input_fact",
                    }
                ],
                relational_ops=[
                    {
                        "op": "scan_pinned_graph_nodes",
                        "role": "derived",
                        "node_type": "DerivedFact",
                    },
                    {
                        "op": "expand_graph_edges",
                        "from_role": "derived",
                        "to_role": "input_fact",
                        "relation": "DERIVED_FROM",
                        "to_node_type": "Fact",
                        "mode": "collect",
                        "minimum_related": 1,
                        "maximum_related": 100,
                    },
                    {
                        "op": "project_graph_binding",
                        "fact_roles": ["input_fact"],
                        "derived_roles": ["derived"],
                        "scope_type": "derived_fact_composition",
                        "answer": {
                            "binding": "graph_answer",
                            "role": "input_fact",
                            "shape": "records",
                            "output_key": "records",
                            "fields": {
                                "fact_id": "source_pk",
                                "entity_id": "properties.entity_id",
                                "metric_id": "properties.metric_id",
                                "period_end": "properties.period_end",
                                "value": "properties.normalized_value",
                                "unit": "properties.normalized_unit",
                            },
                        },
                        "context": {
                            "derived_id": {
                                "role": "derived",
                                "source": "source_pk",
                            },
                            "derived_type": {
                                "role": "derived",
                                "source": "properties.derived_type",
                            },
                        },
                    },
                ],
                stratum_fields=["derived_type", "entity_hash_bucket"],
                answer_schema={"type": "structured_fact_list"},
            ),
        ),
        (
            "fact_provenance",
            _graph_trace_spec(
                task_subtype="provenance_trace",
                pattern_family="graph_provenance",
                difficulty_base="easy",
                node_constraints=[
                    {"variable": "fact", "type": "Fact"},
                    {"variable": "source", "type": "DataSource"},
                    {"variable": "definition", "type": "SourceDefinition"},
                    {"variable": "raw_object", "type": "RawObject"},
                ],
                edge_constraints=[
                    {"src": "fact", "relation": "FROM_SOURCE", "dst": "source"},
                    {
                        "src": "fact",
                        "relation": "USES_SOURCE_DEFINITION",
                        "dst": "definition",
                    },
                    {
                        "src": "fact",
                        "relation": "TRACED_TO",
                        "dst": "raw_object",
                    },
                ],
                relational_ops=[
                    {
                        "op": "scan_pinned_graph_nodes",
                        "role": "fact",
                        "node_type": "Fact",
                    },
                    {
                        "op": "expand_graph_edges",
                        "from_role": "fact",
                        "to_role": "source",
                        "relation": "FROM_SOURCE",
                        "to_node_type": "DataSource",
                    },
                    {
                        "op": "expand_graph_edges",
                        "from_role": "fact",
                        "to_role": "definition",
                        "relation": "USES_SOURCE_DEFINITION",
                        "to_node_type": "SourceDefinition",
                    },
                    {
                        "op": "expand_graph_edges",
                        "from_role": "fact",
                        "to_role": "raw_object",
                        "relation": "TRACED_TO",
                        "to_node_type": "RawObject",
                    },
                    {
                        "op": "project_graph_binding",
                        "fact_roles": ["fact"],
                        "raw_object_roles": ["raw_object"],
                        "scope_type": "fact_provenance_trace",
                        "answer": {
                            "binding": "graph_answer",
                            "shape": "composite",
                            "output_key": "trace",
                            "fields": {
                                "fact_id": {
                                    "role": "fact",
                                    "source": "source_pk",
                                },
                                "source_id": {
                                    "role": "source",
                                    "source": "source_pk",
                                },
                                "source_name": {
                                    "role": "source",
                                    "source": "properties.source_name",
                                },
                                "definition_id": {
                                    "role": "definition",
                                    "source": "source_pk",
                                },
                                "raw_concept_name": {
                                    "role": "definition",
                                    "source": "properties.raw_concept_name",
                                },
                                "raw_object_id": {
                                    "role": "raw_object",
                                    "source": "source_pk",
                                },
                                "storage_uri": {
                                    "role": "raw_object",
                                    "source": "properties.storage_uri",
                                },
                            },
                        },
                        "context": {
                            "fact_id": {"role": "fact", "source": "source_pk"},
                            "source_id": {
                                "role": "source",
                                "source": "source_pk",
                            },
                        },
                    },
                ],
                stratum_fields=["source_id", "entity_hash_bucket"],
                answer_schema={"type": "evidence_trace"},
            ),
        ),
        *[
            (
                "time_hierarchy",
                _time_hierarchy_spec(relation, node_type, label),
            )
            for relation, node_type, label in (
                ("BELONGS_TO_YEAR", "CalendarYear", "calendar year"),
                ("BELONGS_TO_QUARTER", "CalendarQuarter", "calendar quarter"),
                ("IN_FISCAL_YEAR", "FiscalYear", "fiscal year"),
            )
        ],
        (
            "entity_set_scope",
            _graph_trace_spec(
                task_subtype="scope_composition",
                pattern_family="graph_scope",
                difficulty_base="medium",
                node_constraints=[
                    {"variable": "derived", "type": "DerivedFact"},
                    {"variable": "scope", "type": "EntitySet"},
                    {
                        "variable": "entity",
                        "type": "Entity",
                        "cardinality": "many",
                    },
                    {
                        "variable": "input_fact",
                        "type": "Fact",
                        "cardinality": "many",
                    },
                ],
                edge_constraints=[
                    {"src": "derived", "relation": "HAS_SCOPE", "dst": "scope"},
                    {
                        "src": "scope",
                        "relation": "CONTAINS_ENTITY",
                        "dst": "entity",
                    },
                    {
                        "src": "derived",
                        "relation": "DERIVED_FROM",
                        "dst": "input_fact",
                    },
                ],
                relational_ops=[
                    {
                        "op": "scan_pinned_graph_nodes",
                        "role": "derived",
                        "node_type": "DerivedFact",
                    },
                    {
                        "op": "expand_graph_edges",
                        "from_role": "derived",
                        "to_role": "scope",
                        "relation": "HAS_SCOPE",
                        "to_node_type": "EntitySet",
                    },
                    {
                        "op": "expand_graph_edges",
                        "from_role": "scope",
                        "to_role": "entity",
                        "relation": "CONTAINS_ENTITY",
                        "to_node_type": "Entity",
                        "mode": "collect",
                        "minimum_related": 1,
                        "maximum_related": 100,
                    },
                    {
                        "op": "expand_graph_edges",
                        "from_role": "derived",
                        "to_role": "input_fact",
                        "relation": "DERIVED_FROM",
                        "to_node_type": "Fact",
                        "mode": "collect",
                        "minimum_related": 1,
                        "maximum_related": 100,
                    },
                    {
                        "op": "project_graph_binding",
                        "fact_roles": ["input_fact"],
                        "derived_roles": ["derived"],
                        "entity_roles": ["entity"],
                        "scope_role": "scope",
                        "scope_type": "derived_entity_set",
                        "answer": {
                            "binding": "graph_answer",
                            "role": "entity",
                            "shape": "records",
                            "output_key": "records",
                            "fields": {
                                "entity_id": "source_pk",
                                "entity_name": "properties.canonical_name",
                                "entity_type": "properties.entity_type",
                                "industry": "properties.industry",
                            },
                        },
                        "context": {
                            "derived_id": {
                                "role": "derived",
                                "source": "source_pk",
                            },
                            "scope_label": {
                                "role": "scope",
                                "source": "properties.scope_definition",
                            },
                        },
                    },
                ],
                stratum_fields=["scope_label", "entity_hash_bucket"],
                answer_schema={"type": "entity_scope_membership"},
            ),
        ),
    ]


def _time_hierarchy_spec(
    relation: str,
    node_type: str,
    label: str,
) -> dict[str, Any]:
    return _graph_trace_spec(
        pattern_version=2,
        task_subtype="time_hierarchy_membership",
        pattern_family="graph_time_hierarchy",
        difficulty_base="easy",
        node_constraints=[
            {"variable": "fact", "type": "Fact"},
            {"variable": "period", "type": "TimePeriod"},
            {"variable": "hierarchy", "type": node_type},
        ],
        edge_constraints=[
            {"src": "fact", "relation": "IN_PERIOD", "dst": "period"},
            {"src": "period", "relation": relation, "dst": "hierarchy"},
        ],
        relational_ops=[
            {
                "op": "scan_pinned_graph_nodes",
                "role": "fact",
                "node_type": "Fact",
                "source_table": "standardized_facts",
            },
            {
                "op": "expand_graph_edges",
                "from_role": "fact",
                "to_role": "period",
                "relation": "IN_PERIOD",
                "to_node_type": "TimePeriod",
            },
            {
                "op": "expand_graph_edges",
                "from_role": "period",
                "to_role": "hierarchy",
                "relation": relation,
                "to_node_type": node_type,
            },
            {
                "op": "project_graph_binding",
                "fact_roles": ["fact"],
                "scope_type": "time_hierarchy_membership",
                "answer": {
                    "binding": "graph_answer",
                    "shape": "composite",
                    "output_key": "trace",
                    "fields": {
                        "fact_id": {
                            "role": "fact",
                            "source": "source_pk",
                        },
                        "hierarchy_type": label,
                        "hierarchy_id": {
                            "role": "hierarchy",
                            "source": "source_pk",
                        },
                        "hierarchy_properties": {
                            "role": "hierarchy",
                            "source": "properties",
                        },
                    },
                },
                "context": {
                    "fact_id": {"role": "fact", "source": "source_pk"},
                    "hierarchy_type": label,
                    "hierarchy_relation": relation,
                },
            },
        ],
        stratum_fields=["hierarchy_type", "entity_hash_bucket"],
        answer_schema={"type": "time_hierarchy_membership"},
    )


def _graph_trace_spec(
    *,
    pattern_version: int = 1,
    task_subtype: str,
    pattern_family: str,
    difficulty_base: str,
    node_constraints: list[dict[str, Any]],
    edge_constraints: list[dict[str, Any]],
    relational_ops: list[dict[str, Any]],
    stratum_fields: list[str],
    answer_schema: dict[str, Any],
) -> dict[str, Any]:
    return {
        "pattern_version": pattern_version,
        "pattern_family": pattern_family,
        "task_subtype": task_subtype,
        "semantic_profile": "graph_trace",
        "node_constraints": node_constraints,
        "edge_constraints": edge_constraints,
        "semantic_constraints": [
            {"field": "graph_ready", "operator": "eq", "value": True},
            {"field": "is_forecast", "operator": "eq", "value": False},
        ],
        "operator_template": {
            "operators": [
                {
                    "step_id": "answer",
                    "operator": "graph_answer",
                    "inputs": [{"binding": "graph_answer"}],
                }
            ],
            "output_step": "answer",
        },
        "answer_schema": answer_schema,
        "difficulty_base": difficulty_base,
        "question_intents": [
            "graph_evidence_trace",
            "analyst_audit_trace",
        ],
        "binding_query": {
            "ir_version": 1,
            "scan_kind": "graph",
            "relational_ops": relational_ops,
            "stratum_fields": stratum_fields,
        },
    }


def _mine_cross_metric_comparison(
    facts: list[dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    policy: dict[str, Any],
    semantic_policy: dict[str, Any],
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = defaultdict(dict)
    for fact in facts:
        metric = metrics.get(str(fact["metric_id"]), {})
        key = (
            fact["entity_id"],
            _period_key(fact),
            fact.get("source_id"),
            fact_frequency(fact),
            fact.get("time_basis"),
            fact.get("metric_period_type"),
            metric.get("statement_type"),
            _financial_scope(fact),
            fact.get("normalized_unit"),
            fact.get("normalized_currency"),
        )
        groups[key][str(fact["metric_id"])] = fact
    found: dict[tuple[Any, ...], dict[str, Any]] = {}
    for key, by_metric in groups.items():
        metric_ids = sorted(by_metric)
        for left_index, left_metric in enumerate(metric_ids):
            for right_metric in metric_ids[left_index + 1 :]:
                pair_key = (left_metric, right_metric)
                entry = found.setdefault(
                    pair_key,
                    _raw_proposal(
                        "cross_metric_comparison",
                        [left_metric, right_metric],
                        _cross_metric_spec(left_metric, right_metric),
                    ),
                )
                left, right = by_metric[left_metric], by_metric[right_metric]
                _append_binding(
                    entry,
                    {
                        "input_bindings": {
                            "left": left["fact_id"],
                            "right": right["fact_id"],
                        },
                        "fact_ids": [left["fact_id"], right["fact_id"]],
                        "entity_ids": [left["entity_id"]],
                        "metric_ids": [left_metric, right_metric],
                        "period": period_label(left),
                        "frequency": fact_frequency(left),
                        "operator_params": {"id_field": "metric_id"},
                        "scope_type": "single_entity",
                        "scope_definition": str(left["entity_id"]),
                    },
                    policy,
                    facts=[left, right],
                    metrics=metrics,
                    semantic_policy=semantic_policy,
                )
    return list(found.values())


def _mine_temporal_aggregation(
    facts: list[dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    policy: dict[str, Any],
    semantic_policy: dict[str, Any],
) -> list[dict[str, Any]]:
    series = _series_groups(facts)
    found: dict[tuple[Any, ...], dict[str, Any]] = {}
    for key, rows in series.items():
        frequency = key.frequency
        window = latest_contiguous_window(
            rows,
            frequency=frequency,
            minimum=policy["minimum_temporal_observations"],
            maximum=policy["maximum_temporal_observations"],
            require_contiguous=policy["require_contiguous_periods"],
        )
        if not window or any(not annual_duration_valid(row) for row in window):
            continue
        metric_id = key.metric_id
        proposal_key = (metric_id,)
        entry = found.setdefault(
            proposal_key,
            _raw_proposal(
                "temporal_aggregation",
                [metric_id],
                _temporal_average_spec(metric_id),
            ),
        )
        _append_binding(
            entry,
            {
                "input_bindings": {"series": [row["fact_id"] for row in window]},
                "fact_ids": [row["fact_id"] for row in window],
                "entity_ids": [window[0]["entity_id"]],
                "metric_ids": [metric_id],
                "start_period": period_label(window[0]),
                "end_period": period_label(window[-1]),
                "observation_count": len(window),
                "frequency": frequency,
                "scope_type": "single_entity_series",
                "scope_definition": str(window[0]["entity_id"]),
            },
            policy,
            facts=window,
            metrics=metrics,
            semantic_policy=semantic_policy,
        )
    return list(found.values())


def _mine_temporal_followup(
    facts: list[dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    policy: dict[str, Any],
    semantic_policy: dict[str, Any],
) -> list[dict[str, Any]]:
    series = _series_groups(facts)
    by_context: dict[
        tuple[Any, ...],
        dict[str, list[tuple[TemporalSeriesKey, list[dict[str, Any]]]]],
    ] = defaultdict(lambda: defaultdict(list))
    for key, rows in series.items():
        window = latest_contiguous_window(
            rows,
            frequency=key.frequency,
            minimum=policy["minimum_temporal_observations"],
            maximum=policy["maximum_temporal_observations"],
            require_contiguous=policy["require_contiguous_periods"],
        )
        if window and all(annual_duration_valid(row) for row in window):
            context = (
                key.entity_id,
                key.source_id,
                key.frequency,
                key.time_basis,
                key.financial_scope,
                key.normalized_unit,
                key.normalized_currency,
                key.seasonal_adjustment,
                key.vintage_policy,
                key.comparability_level,
            )
            by_context[context][key.metric_id].append((key, window))
    found: dict[tuple[Any, ...], dict[str, Any]] = {}
    for context, by_metric in by_context.items():
        (
            entity_id,
            _,
            frequency,
            _,
            financial_scope,
            _,
            _,
            _,
            _,
            _,
        ) = context
        metric_ids = sorted(by_metric)
        for primary_metric in metric_ids:
            for _, primary in sorted(by_metric[primary_metric]):
                primary_indices = {period_index(row, frequency) for row in primary}
                for secondary_metric in metric_ids:
                    if secondary_metric == primary_metric:
                        continue
                    for _, secondary_rows in sorted(by_metric[secondary_metric]):
                        secondary_by_period = {
                            period_index(row, frequency): row for row in secondary_rows
                        }
                        if None in primary_indices or not primary_indices.issubset(
                            secondary_by_period
                        ):
                            continue
                        secondary = [
                            secondary_by_period[period_index(row, frequency)]
                            for row in primary
                        ]
                        proposal_key = (primary_metric, secondary_metric)
                        entry = found.setdefault(
                            proposal_key,
                            _raw_proposal(
                                "temporal_extrema_followup",
                                [primary_metric, secondary_metric],
                                _temporal_followup_spec(
                                    primary_metric, secondary_metric
                                ),
                            ),
                        )
                        _append_binding(
                            entry,
                            {
                                "input_bindings": {
                                    "primary_series": [
                                        row["fact_id"] for row in primary
                                    ],
                                    "secondary_series": [
                                        row["fact_id"] for row in secondary
                                    ],
                                },
                                "fact_ids": [
                                    *[row["fact_id"] for row in primary],
                                    *[row["fact_id"] for row in secondary],
                                ],
                                "entity_ids": [entity_id],
                                "metric_ids": [
                                    primary_metric,
                                    secondary_metric,
                                ],
                                "primary_metric_id": primary_metric,
                                "secondary_metric_id": secondary_metric,
                                "start_period": period_label(primary[0]),
                                "end_period": period_label(primary[-1]),
                                "observation_count": len(primary),
                                "frequency": frequency,
                                "scope_type": "single_entity_series",
                                "scope_definition": str(entity_id),
                                "financial_scope": {
                                    "entity_scope_id": financial_scope[0],
                                    "financial_scope_type": financial_scope[1],
                                },
                            },
                            policy,
                            facts=[*primary, *secondary],
                            metrics=metrics,
                            semantic_policy=semantic_policy,
                        )
    return list(found.values())


def _mine_scope_rank_followup(
    facts: list[dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    policy: dict[str, Any],
    semantic_policy: dict[str, Any],
) -> list[dict[str, Any]]:
    groups: dict[
        ScopeContextKey,
        dict[ScopeMetricVariant, dict[str, list[dict[str, Any]]]],
    ] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for fact in facts:
        if str(fact.get("entity_type")) != "company" or not fact.get("industry"):
            continue
        if _truthy(fact.get("is_forecast")):
            continue
        if fact_frequency(fact) != "annual":
            continue
        if str(fact.get("fiscal_quarter") or "").upper() != "FY":
            continue
        if not annual_duration_valid(fact):
            continue
        entity_id = str(fact["entity_id"])
        if _financial_scope(fact) != (entity_id, "consolidated_entity"):
            continue
        context = ScopeContextKey(
            industry=str(fact["industry"]),
            period=_period_key(fact),
            source_id=str(fact.get("source_id") or ""),
            frequency=fact_frequency(fact),
            time_basis=str(fact.get("time_basis") or ""),
            financial_scope_type="consolidated_entity",
            seasonal_adjustment=str(fact.get("seasonal_adjustment") or ""),
            vintage_policy=str(fact.get("vintage_policy") or ""),
            comparability_level=str(fact.get("comparability_level") or ""),
        )
        variant = ScopeMetricVariant(
            metric_id=str(fact["metric_id"]),
            source_definition_id=str(fact.get("source_definition_id") or ""),
            metric_period_type=str(fact.get("metric_period_type") or ""),
            normalized_unit=str(fact.get("normalized_unit") or ""),
            normalized_currency=str(fact.get("normalized_currency") or ""),
        )
        groups[context][variant][entity_id].append(fact)
    found: dict[tuple[Any, ...], dict[str, Any]] = {}
    for context, by_variant in groups.items():
        variants = sorted(by_variant)
        for primary_variant in variants:
            primary_by_entity = _unique_scope_entities(by_variant[primary_variant])
            for secondary_variant in variants:
                if primary_variant.metric_id == secondary_variant.metric_id:
                    continue
                secondary_by_entity = _unique_scope_entities(
                    by_variant[secondary_variant]
                )
                common = sorted(set(primary_by_entity) & set(secondary_by_entity))
                if len(common) < policy["minimum_scope_entities"]:
                    continue
                primary = [primary_by_entity[entity] for entity in common]
                secondary = [secondary_by_entity[entity] for entity in common]
                proposal_key = (
                    primary_variant.metric_id,
                    secondary_variant.metric_id,
                )
                entry = found.setdefault(
                    proposal_key,
                    _raw_proposal(
                        "scope_rank_followup",
                        [
                            primary_variant.metric_id,
                            secondary_variant.metric_id,
                        ],
                        _scope_rank_spec(
                            primary_variant.metric_id,
                            secondary_variant.metric_id,
                        ),
                    ),
                )
                _append_binding(
                    entry,
                    {
                        "input_bindings": {
                            "primary": [row["fact_id"] for row in primary],
                            "secondary": [row["fact_id"] for row in secondary],
                        },
                        "fact_ids": [
                            *[row["fact_id"] for row in primary],
                            *[row["fact_id"] for row in secondary],
                        ],
                        "entity_ids": common,
                        "metric_ids": [
                            primary_variant.metric_id,
                            secondary_variant.metric_id,
                        ],
                        "primary_metric_id": primary_variant.metric_id,
                        "secondary_metric_id": secondary_variant.metric_id,
                        "period": period_label(primary[0]),
                        "frequency": context.frequency,
                        "scope_type": "canonical_industry_complete_case",
                        "scope_definition": (
                            f"the canonical '{context.industry}' industry "
                            f"complete-case universe ({len(common)} companies "
                            "with unique consolidated comparable inputs)"
                        ),
                        "industry": context.industry,
                        "source_definitions": {
                            "primary": primary_variant.source_definition_id,
                            "secondary": secondary_variant.source_definition_id,
                        },
                        "scope_input_coverage": 1.0,
                        "financial_scope": {
                            "financial_scope_type": "consolidated_entity",
                            "entity_scope_ids": common,
                        },
                        "operator_step_params": {
                            "rank_primary": {
                                "top_k": min(policy["top_k"], len(common)),
                                "direction": "desc",
                            }
                        },
                    },
                    policy,
                    facts=[*primary, *secondary],
                    metrics=metrics,
                    semantic_policy=semantic_policy,
                )
    return list(found.values())


def _unique_scope_entities(
    rows: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    return {
        entity_id: values[0] for entity_id, values in rows.items() if len(values) == 1
    }


def _proposal_from_raw(
    raw: dict[str, Any],
    run_id: str,
    kg_build_id: str,
    policy: dict[str, Any],
) -> PatternProposal:
    records = sorted(
        raw["binding_validation_records"],
        key=lambda item: _digest(item["binding"]),
    )
    heldout_target = max(
        policy["minimum_heldout_bindings"],
        math.ceil(len(records) * policy["heldout_fraction"]),
    )
    heldout_count = min(
        policy["max_heldout_bindings"],
        heldout_target,
        max(len(records) - 1, 0),
    )
    heldout_records = records[:heldout_count]
    example_records = records[heldout_count:][: policy["max_bindings_per_proposal"]]
    bindings = [item["binding"] for item in example_records]
    heldout_bindings = [item["binding"] for item in heldout_records]
    selected_bindings = [*bindings, *heldout_bindings]
    semantic_pass_rate = _rate(
        int(raw["support_count"]), int(raw["evaluated_binding_count"])
    )
    operation_pass_rate = _rate(
        int(raw["operation_pass_count"]), int(raw["support_count"])
    )
    example_pass_rate = _record_pass_rate(example_records)
    heldout_pass_rate = _record_pass_rate(heldout_records)
    static_pattern_id, static_overlap = _static_pattern_match(raw["pattern_spec"])
    static_pattern = get_pattern(static_pattern_id) if static_pattern_id else None
    static_pattern_version = (
        static_pattern.pattern_version if static_pattern is not None else None
    )
    static_pattern_hash = (
        pattern_content_hash(static_pattern) if static_pattern is not None else None
    )
    diversity_score = _binding_diversity_score(selected_bindings)
    pattern_spec = json.loads(json.dumps(raw["pattern_spec"]))
    pattern_spec["semantic_validation"] = {
        "evaluated_binding_count": int(raw["evaluated_binding_count"]),
        "accepted_binding_count": int(raw["support_count"]),
        "rejection_counts": dict(sorted(raw["semantic_rejection_counts"].items())),
        "validator_version": 1,
    }
    semantic_results = {
        **pattern_spec["semantic_validation"],
        "pass_rate": round(semantic_pass_rate, 6),
    }
    operation_results = {
        "evaluated_binding_count": int(raw["operation_evaluated_count"]),
        "passed_binding_count": int(raw["operation_pass_count"]),
        "pass_rate": round(operation_pass_rate, 6),
        "example_binding_count": len(example_records),
        "example_pass_rate": round(example_pass_rate, 6),
        "heldout_binding_count": len(heldout_records),
        "heldout_pass_rate": round(heldout_pass_rate, 6),
        "example_results": [_execution_summary(item) for item in example_records],
        "heldout_results": [_execution_summary(item) for item in heldout_records],
        "rejection_counts": dict(sorted(raw["operation_rejection_counts"].items())),
        "executor_version": 1,
    }
    support = int(raw["support_count"])
    entity_ids = {
        str(entity)
        for binding in selected_bindings
        for entity in binding.get("entity_ids", [])
    }
    metric_ids = set(raw["metric_ids"])
    periods = {
        str(value)
        for binding in selected_bindings
        for value in [
            binding.get("period"),
            binding.get("start_period"),
            binding.get("end_period"),
        ]
        if value is not None
    }
    support_score = min(
        1.0,
        math.log1p(support) / math.log1p(policy["target_support"]),
    )
    completeness_score = (
        sum(
            bool(binding.get("fact_ids"))
            and bool(binding.get("input_bindings"))
            and set(_binding_fact_ids(binding))
            == {str(value) for value in binding["fact_ids"]}
            for binding in selected_bindings
        )
        / len(selected_bindings)
        if selected_bindings
        else 0.0
    )
    family_value = {
        "cross_metric_comparison": 0.68,
        "temporal_aggregation": 0.78,
        "temporal_extrema_followup": 0.94,
        "scope_rank_followup": 0.92,
        "derived_fact_composition": 0.82,
        "fact_provenance": 0.88,
        "time_hierarchy": 0.72,
        "entity_set_scope": 0.84,
    }
    financial_value_score = float(
        pattern_spec.get("financial_value_score")
        or family_value.get(raw["motif_family"], 0.5)
    )
    operation_count = len(pattern_spec["operator_template"]["operators"])
    complexity_score = min(operation_count / 3.0, 1.0)
    novelty_score = 0.0 if static_pattern_id else 1.0 - static_overlap
    total = round(
        0.25 * support_score
        + 0.20 * completeness_score
        + 0.25 * financial_value_score
        + 0.15 * complexity_score
        + 0.10 * novelty_score
        + 0.05 * diversity_score,
        6,
    )
    created_at = _now()
    lifecycle_events = [{"stage": "proposed", "status": "passed", "at": created_at}]
    reasons: list[str] = []
    if support < policy["min_support"]:
        reasons.append("insufficient_support")
    if completeness_score < 1.0:
        reasons.append("incomplete_operation_bindings")
    if total < policy["min_total_score"]:
        reasons.append("below_value_score_threshold")
    if semantic_pass_rate < policy["minimum_semantic_constraint_pass_rate"]:
        reasons.append("semantic_constraint_pass_rate_below_threshold")
    status = "proposed"
    manual_review_status = "not_started"
    if not reasons:
        status = "semantic_validated"
        lifecycle_events.append({"stage": status, "status": "passed", "at": created_at})
        if example_pass_rate < 1.0:
            reasons.append("binding_example_execution_failed")
        if len(heldout_records) < policy["minimum_heldout_bindings"]:
            reasons.append("insufficient_heldout_bindings")
        if operation_pass_rate < policy["minimum_operation_execution_pass_rate"]:
            reasons.append("operation_execution_pass_rate_below_threshold")
        if heldout_pass_rate < policy["minimum_heldout_binding_pass_rate"]:
            reasons.append("heldout_binding_pass_rate_below_threshold")
        if not reasons:
            status = "execution_validated"
            lifecycle_events.append(
                {"stage": status, "status": "passed", "at": created_at}
            )
            if policy["require_manual_review"]:
                manual_review_status = "pending"
            else:
                manual_review_status = "not_required_by_policy"
                lifecycle_events.append(
                    {
                        "stage": "reviewed_approved",
                        "status": "passed",
                        "at": created_at,
                        "reviewer": "policy:auto",
                    }
                )
                status = "published"
                lifecycle_events.append(
                    {"stage": status, "status": "passed", "at": created_at}
                )
    semantic_payload = _semantic_pattern_payload(pattern_spec)
    canonical_semantic_digest = pattern_semantic_digest(pattern_spec)
    semantic_digest = _digest(semantic_payload)
    semantic_id = "qapatsem_" + semantic_digest[:24]
    signature = semantic_digest
    snapshot_id = (
        "qapatsnap_"
        + _digest(
            semantic_id,
            kg_build_id,
            support,
            bindings,
            heldout_bindings,
            semantic_results,
            operation_results,
        )[:24]
    )
    proposal_hash = _digest(
        snapshot_id,
        pattern_spec,
        canonical_semantic_digest,
        static_pattern_id,
        static_pattern_version,
        static_pattern_hash,
    )
    proposal_id = "qaprop_" + _digest(run_id, snapshot_id)[:24]
    return PatternProposal(
        proposal_id=proposal_id,
        mining_run_id=run_id,
        kg_build_id=kg_build_id,
        motif_family=raw["motif_family"],
        motif_signature=signature,
        proposal_semantic_id=semantic_id,
        proposal_snapshot_id=snapshot_id,
        static_pattern_id=static_pattern_id,
        pattern_semantic_digest=canonical_semantic_digest,
        static_pattern_version=static_pattern_version,
        static_pattern_hash=static_pattern_hash,
        binding_mode=("known_pattern_binding" if static_pattern_id else "new_pattern"),
        pattern_spec=pattern_spec,
        operator_dag_template=pattern_spec["operator_template"],
        answer_schema=pattern_spec["answer_schema"],
        binding_examples=bindings,
        heldout_bindings=heldout_bindings,
        semantic_validation_results=semantic_results,
        operation_validation_results=operation_results,
        lifecycle_events=lifecycle_events,
        support_count=support,
        entity_count=len(entity_ids),
        metric_count=len(metric_ids),
        period_count=len(periods),
        support_score=round(support_score, 6),
        completeness_score=round(completeness_score, 6),
        financial_value_score=financial_value_score,
        complexity_score=round(complexity_score, 6),
        novelty_score=round(novelty_score, 6),
        total_score=total,
        semantic_constraint_pass_rate=round(semantic_pass_rate, 6),
        operation_execution_pass_rate=round(operation_pass_rate, 6),
        example_binding_pass_rate=round(example_pass_rate, 6),
        heldout_binding_pass_rate=round(heldout_pass_rate, 6),
        static_pattern_overlap=round(static_overlap, 6),
        binding_diversity_score=round(diversity_score, 6),
        manual_review_status=manual_review_status,
        status=status,
        rejection_reasons=reasons,
        proposal_hash=proposal_hash,
        created_at=created_at,
    )


def _balanced_select(
    proposals: list[PatternProposal], limit: int
) -> list[PatternProposal]:
    if len(proposals) <= limit:
        return proposals
    by_family: dict[str, list[PatternProposal]] = defaultdict(list)
    for proposal in proposals:
        by_family[proposal.motif_family].append(proposal)
    selected: list[PatternProposal] = []
    family_names = sorted(by_family)
    family_quota = max(limit // len(family_names), 1)
    for family in family_names:
        selected.extend(by_family[family][:family_quota])
        by_family[family] = by_family[family][family_quota:]
    remaining = sorted(
        (item for values in by_family.values() for item in values),
        key=lambda item: (-item.total_score, -item.support_count, item.proposal_id),
    )
    selected.extend(remaining[: max(limit - len(selected), 0)])
    return sorted(
        selected[:limit],
        key=lambda item: (-item.total_score, -item.support_count, item.proposal_id),
    )


def _raw_proposal(
    family: str, metric_ids: list[str], pattern_spec: dict[str, Any]
) -> dict[str, Any]:
    return {
        "motif_family": family,
        "metric_ids": metric_ids,
        "pattern_spec": pattern_spec,
        "binding_validation_records": [],
        "support_count": 0,
        "evaluated_binding_count": 0,
        "semantic_rejection_counts": defaultdict(int),
        "operation_evaluated_count": 0,
        "operation_pass_count": 0,
        "operation_rejection_counts": defaultdict(int),
    }


def _binding_fact_ids(binding: dict[str, Any]) -> list[str]:
    output: set[str] = set()
    for value in dict(binding.get("input_bindings") or {}).values():
        if isinstance(value, dict) and set(value) == {"__literal__"}:
            continue
        if isinstance(value, list):
            output.update(str(item) for item in value)
        elif value is not None:
            output.add(str(value))
    return sorted(output)


def _append_binding(
    proposal: dict[str, Any],
    binding: dict[str, Any],
    policy: dict[str, Any],
    *,
    facts: list[dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    semantic_policy: dict[str, Any],
) -> None:
    proposal["evaluated_binding_count"] += 1
    validation = validate_semantic_constraints(
        proposal["pattern_spec"],
        binding,
        facts,
        metrics,
        semantic_policy,
    )
    if not validation.passed:
        for error in validation.errors:
            proposal["semantic_rejection_counts"][error] += 1
        return
    proposal["support_count"] += 1
    proposal["operation_evaluated_count"] += 1
    plan = materialize_plan(proposal["pattern_spec"]["operator_template"], binding)
    execution = execute_plan(
        plan,
        binding["input_bindings"],
        {str(fact["fact_id"]): fact for fact in facts},
    )
    if execution.status == "passed":
        proposal["operation_pass_count"] += 1
    else:
        for error in execution.errors or ["unknown_execution_error"]:
            proposal["operation_rejection_counts"][error] += 1
    record_limit = policy["max_bindings_per_proposal"] + policy["max_heldout_bindings"]
    if len(proposal["binding_validation_records"]) < record_limit:
        proposal["binding_validation_records"].append(
            {
                "binding": binding,
                "execution_status": execution.status,
                "execution_errors": list(execution.errors),
                "output_hash": _digest(execution.output),
            }
        )


def _base_spec(
    *,
    task_subtype: str,
    pattern_family: str,
    difficulty_base: str,
    metrics: list[str],
    operators: list[dict[str, Any]],
    output_step: str,
    answer_schema: dict[str, Any],
) -> dict[str, Any]:
    return {
        "pattern_version": 1,
        "pattern_family": pattern_family,
        "task_subtype": task_subtype,
        "node_constraints": [
            {"variable": "entity", "type": "Entity"},
            {"variable": "facts", "type": "Fact", "cardinality": "many"},
            {"variable": "metrics", "type": "Metric", "values": metrics},
            {"variable": "periods", "type": "TimePeriod", "cardinality": "many"},
        ],
        "edge_constraints": [
            {"src": "entity", "relation": "HAS_FACT", "dst": "facts"},
            {"src": "facts", "relation": "MEASURES", "dst": "metrics"},
            {"src": "facts", "relation": "IN_PERIOD", "dst": "periods"},
        ],
        "semantic_constraints": [
            {"field": "graph_ready", "operator": "eq", "value": True},
            {"field": "is_forecast", "operator": "eq", "value": False},
            {"field": "source_definition", "operator": "compatible"},
            {"field": "financial_scope", "operator": "same"},
            {"field": "frequency", "operator": "same"},
            {"field": "time_basis", "operator": "same"},
            {"field": "seasonal_adjustment", "operator": "same"},
            {"field": "vintage_policy", "operator": "same"},
        ],
        "operator_template": {"operators": operators, "output_step": output_step},
        "answer_schema": answer_schema,
        "difficulty_base": difficulty_base,
        "question_intents": ["mined_financial_analysis", "analyst_investigation"],
    }


def _binding_query_spec(
    relational_ops: list[dict[str, Any]],
    stratum_fields: list[str],
) -> dict[str, Any]:
    return {
        "ir_version": 1,
        "relational_ops": relational_ops,
        "stratum_fields": stratum_fields,
    }


def _cross_metric_spec(left: str, right: str) -> dict[str, Any]:
    spec = _base_spec(
        task_subtype="cross_metric_comparison",
        pattern_family="mined_comparison",
        difficulty_base="medium",
        metrics=[left, right],
        operators=[
            {
                "step_id": "answer",
                "operator": "compare",
                "inputs": [{"binding": "left"}, {"binding": "right"}],
                "params": {"id_field": "metric_id"},
            }
        ],
        output_step="answer",
        answer_schema={"type": "comparison"},
    )
    spec["semantic_constraints"].extend(
        [
            {"field": "metric_pair", "operator": "registered_comparable_pair"},
            {"field": "statement_type", "operator": "same"},
            {"field": "metric_period_type", "operator": "same"},
        ]
    )
    spec["binding_query"] = _binding_query_spec(
        [
            {
                "op": "group",
                "keys": [
                    "entity",
                    "period",
                    "source",
                    "frequency",
                    "time_basis",
                    "metric_period_type",
                    "statement_type",
                    "financial_scope",
                    "unit",
                    "currency",
                ],
            },
            {
                "op": "join_metric_roles",
                "roles": [
                    {"binding": "left", "metric_id": left},
                    {"binding": "right", "metric_id": right},
                ],
            },
        ],
        ["metric_ids", "frequency", "period", "entity_hash_bucket"],
    )
    return spec


def _temporal_average_spec(metric: str) -> dict[str, Any]:
    spec = _base_spec(
        task_subtype="multi_period_average",
        pattern_family="mined_temporal",
        difficulty_base="hard",
        metrics=[metric],
        operators=[
            {
                "step_id": "answer",
                "operator": "mean",
                "inputs": [{"binding": "series"}],
            }
        ],
        output_step="answer",
        answer_schema={"type": "numeric", "aggregation": "arithmetic_mean"},
    )
    spec["binding_query"] = _binding_query_spec(
        [
            {"op": "group_series"},
            {
                "op": "latest_contiguous_window",
                "binding": "series",
                "require_annual_duration": True,
            },
        ],
        ["metric_ids", "frequency", "end_period", "entity_hash_bucket"],
    )
    return spec


def _temporal_followup_spec(primary: str, secondary: str) -> dict[str, Any]:
    spec = _base_spec(
        task_subtype="temporal_peak_followup",
        pattern_family="mined_multi_stage",
        difficulty_base="expert",
        metrics=[primary, secondary],
        operators=[
            {
                "step_id": "find_peak",
                "operator": "argmax",
                "inputs": [{"binding": "primary_series"}],
                "params": {"selection_key": "period"},
            },
            {
                "step_id": "answer",
                "operator": "select_by_period",
                "inputs": [
                    {"step": "find_peak"},
                    {"binding": "secondary_series"},
                ],
            },
        ],
        output_step="answer",
        answer_schema={"type": "period_metric_lookup"},
    )
    spec["semantic_constraints"].append(
        {"field": "metric_pair", "operator": "registered_followup_pair"}
    )
    spec["binding_query"] = _binding_query_spec(
        [
            {"op": "group_series"},
            {
                "op": "latest_contiguous_window",
                "require_annual_duration": True,
            },
            {
                "op": "join_series_on_period",
                "coverage": 1.0,
                "roles": [
                    {"binding": "primary_series", "metric_id": primary},
                    {"binding": "secondary_series", "metric_id": secondary},
                ],
            },
        ],
        ["metric_ids", "frequency", "end_period", "entity_hash_bucket"],
    )
    return spec


def _scope_rank_spec(primary: str, secondary: str) -> dict[str, Any]:
    spec = _base_spec(
        task_subtype="rank_then_secondary_lookup",
        pattern_family="mined_multi_stage_scope",
        difficulty_base="expert",
        metrics=[primary, secondary],
        operators=[
            {
                "step_id": "rank_primary",
                "operator": "rank",
                "inputs": [{"binding": "primary"}],
                "params": {"direction": "desc", "top_k": 3},
            },
            {
                "step_id": "answer",
                "operator": "lookup_ranked_entities",
                "inputs": [
                    {"step": "rank_primary"},
                    {"binding": "secondary"},
                ],
            },
        ],
        output_step="answer",
        answer_schema={"type": "multi_metric_ranked_table"},
    )
    spec["semantic_constraints"].append(
        {"field": "metric_pair", "operator": "registered_followup_pair"}
    )
    spec["semantic_constraints"].extend(
        [
            {"field": "entity_type", "operator": "eq", "value": "company"},
            {"field": "financial_scope", "operator": "consolidated_entity"},
            {"field": "frequency", "operator": "eq", "value": "annual"},
            {"field": "fiscal_quarter", "operator": "eq", "value": "FY"},
            {
                "field": "annual_flow_duration",
                "operator": "between_days",
                "value": [300, 430],
            },
            {
                "field": "scope_entities",
                "operator": "complete_across_bindings",
                "bindings": ["primary", "secondary"],
            },
            {"field": "primary.entity_id", "operator": "unique"},
            {"field": "secondary.entity_id", "operator": "unique"},
            {"field": "primary.unit", "operator": "same_within_binding"},
            {"field": "primary.currency", "operator": "same_within_binding"},
            {"field": "secondary.unit", "operator": "same_within_binding"},
            {"field": "secondary.currency", "operator": "same_within_binding"},
            {
                "field": "primary.source_definition_id",
                "operator": "same_within_binding",
            },
            {
                "field": "secondary.source_definition_id",
                "operator": "same_within_binding",
            },
        ]
    )
    spec["binding_query"] = _binding_query_spec(
        [
            {
                "op": "group",
                "shape": "scope_metric_variants",
                "keys": [
                    "industry",
                    "period",
                    "source",
                    "frequency",
                    "time_basis",
                    "financial_scope",
                    "seasonal_adjustment",
                    "vintage_policy",
                    "comparability_level",
                ],
                "required_fields": ["industry"],
                "predicates": {
                    "entity_type": "company",
                    "frequency": "annual",
                    "fiscal_quarter": "FY",
                    "financial_scope_type": "consolidated_entity",
                    "entity_scope_matches_entity": True,
                    "annual_duration_valid": True,
                },
            },
            {
                "op": "complete_case_metric_join",
                "roles": [
                    {"binding": "primary", "metric_id": primary},
                    {"binding": "secondary", "metric_id": secondary},
                ],
            },
        ],
        ["metric_ids", "industry", "period"],
    )
    return spec


def _series_groups(
    facts: list[dict[str, Any]],
) -> dict[TemporalSeriesKey, list[dict[str, Any]]]:
    output: dict[TemporalSeriesKey, list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        key = TemporalSeriesKey(
            entity_id=str(fact["entity_id"]),
            metric_id=str(fact["metric_id"]),
            source_id=str(fact.get("source_id") or ""),
            source_definition_id=str(fact.get("source_definition_id") or ""),
            frequency=fact_frequency(fact),
            time_basis=str(fact.get("time_basis") or ""),
            metric_period_type=str(fact.get("metric_period_type") or ""),
            financial_scope=_financial_scope(fact),
            normalized_unit=str(fact.get("normalized_unit") or ""),
            normalized_currency=str(fact.get("normalized_currency") or ""),
            seasonal_adjustment=str(fact.get("seasonal_adjustment") or ""),
            vintage_policy=str(fact.get("vintage_policy") or ""),
            comparability_level=str(fact.get("comparability_level") or ""),
        )
        output[key].append(fact)
    return output


def _deduplicate_facts(rows: Any) -> list[dict[str, Any]]:
    output: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = (
            row.get("entity_id"),
            row.get("metric_id"),
            _period_key(row),
            row.get("source_id"),
            row.get("source_definition_id"),
            fact_frequency(row),
            row.get("time_basis"),
            row.get("metric_period_type"),
            _financial_scope(row),
            row.get("normalized_unit"),
            row.get("normalized_currency"),
            row.get("seasonal_adjustment"),
            row.get("vintage_policy"),
            row.get("comparability_level"),
            row.get("is_forecast"),
        )
        current = output.get(key)
        if current is None or str(row.get("fact_id")) < str(current.get("fact_id")):
            output[key] = row
    return list(output.values())


def _period_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("fiscal_year"),
        row.get("fiscal_quarter"),
        row.get("calendar_year"),
        str(row.get("period_end") or row.get("as_of_date") or ""),
    )


def _financial_scope(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("entity_scope_id") or row.get("entity_id") or ""),
        str(row.get("financial_scope_type") or "consolidated_entity"),
    )


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _record_pass_rate(records: list[dict[str, Any]]) -> float:
    if not records:
        return 1.0
    return sum(item["execution_status"] == "passed" for item in records) / len(records)


def _execution_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "binding_hash": _digest(record["binding"]),
        "status": record["execution_status"],
        "errors": list(record["execution_errors"]),
        "output_hash": record["output_hash"],
    }


def _pattern_feature_set(spec: dict[str, Any]) -> set[str]:
    features = {
        f"node:{item.get('type')}" for item in spec.get("node_constraints") or []
    }
    features.update(
        f"edge:{item.get('relation')}" for item in spec.get("edge_constraints") or []
    )
    template = spec.get("operator_template") or {}
    features.update(
        f"operator:{item.get('operator')}" for item in template.get("operators") or []
    )
    features.add(f"task:{spec.get('task_subtype')}")
    features.add(f"answer:{(spec.get('answer_schema') or {}).get('type')}")
    return features


def _static_pattern_match(spec: dict[str, Any]) -> tuple[str | None, float]:
    proposal = _semantic_pattern_components(spec)
    proposal_digest = pattern_semantic_digest(spec)
    matches: list[tuple[float, str, dict[str, Any]]] = []
    for static in pattern_manifest():
        if not static.get("is_active", True):
            continue
        candidate = _semantic_pattern_components(static)
        component_scores = [
            float(proposal["task_subtype"] == candidate["task_subtype"]),
            _jaccard(proposal["node_grammar"], candidate["node_grammar"]),
            _jaccard(proposal["edge_grammar"], candidate["edge_grammar"]),
            float(proposal["operator_dag"] == candidate["operator_dag"]),
            _jaccard(
                proposal["semantic_constraints"],
                candidate["semantic_constraints"],
            ),
            float(proposal["answer_schema"] == candidate["answer_schema"]),
        ]
        score = sum(component_scores) / len(component_scores)
        matches.append((score, str(static["pattern_id"]), static))
    if not matches:
        return None, 0.0
    score, pattern_id, static = max(matches, key=lambda item: (item[0], item[1]))
    static_components = _semantic_pattern_components(static)
    exact_components = (
        "task_subtype",
        "node_grammar",
        "edge_grammar",
        "operator_dag",
        "semantic_constraints",
        "answer_schema",
    )
    known = (
        score == 1.0
        and all(
            proposal[component] == static_components[component]
            for component in exact_components
        )
        and proposal_digest == pattern_semantic_digest(static)
    )
    return (pattern_id if known else None), score


def _semantic_pattern_payload(spec: dict[str, Any]) -> dict[str, Any]:
    components = _semantic_pattern_components(spec)
    metric_roles = sorted(
        str(value)
        for node in spec.get("node_constraints") or []
        if node.get("type") == "Metric"
        for value in node.get("values") or [node.get("variable")]
        if value
    )
    return {
        **components,
        "metric_roles": metric_roles,
        "query_graph_hash": spec.get("query_graph_hash"),
        "operation_macro_id": spec.get("operation_macro_id"),
    }


def _semantic_pattern_components(spec: dict[str, Any]) -> dict[str, Any]:
    return pattern_semantic_components(spec)


def _jaccard(left: Any, right: Any) -> float:
    left_counts = Counter(left)
    right_counts = Counter(right)
    union = left_counts | right_counts
    return (
        sum((left_counts & right_counts).values()) / sum(union.values())
        if union
        else 1.0
    )


def _binding_diversity_score(bindings: list[dict[str, Any]]) -> float:
    if len(bindings) < 2:
        return 0.0
    dimensions = [
        [tuple(sorted(map(str, item.get("entity_ids") or []))) for item in bindings],
        [
            (
                str(item.get("period") or ""),
                str(item.get("start_period") or ""),
                str(item.get("end_period") or ""),
            )
            for item in bindings
        ],
        [
            (str(item.get("scope_type") or ""), str(item.get("scope_definition") or ""))
            for item in bindings
        ],
    ]
    denominator = len(bindings) - 1
    scores = [(len(set(values)) - 1) / denominator for values in dimensions]
    return sum(scores) / len(scores)


def _digest(*values: Any) -> str:
    payload = json.dumps(
        values, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rollback(db: DBProtocol) -> None:
    connection = getattr(db, "conn", None)
    if connection is not None:
        connection.rollback()


def _db_json(db: DBProtocol, value: Any) -> Any:
    if db.__class__.__name__ == "PostgresMetadataDB":
        from psycopg.types.json import Jsonb

        return Jsonb(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _write_report(report: dict[str, Any], output_dir: str | None) -> None:
    if not output_dir:
        return
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "qa_pattern_mining_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# QA Pattern Mining Report",
        "",
        f"- Mining run: `{report['mining_run_id']}`",
        f"- KG build: `{report['kg_build_id']}`",
        f"- Scanned facts / metrics: `{report['scanned_fact_count']}` / `{report['scanned_metric_count']}`",
        f"- Proposals / published: `{report['proposal_count']}` / `{report['published_count']}`",
        f"- Lifecycle counts: `{report['lifecycle_counts']}`",
        f"- Published validation: `{report['published_validation_summary']}`",
        "",
        "## Published Families",
        "",
    ]
    lines.extend(
        f"- `{family}`: {count}"
        for family, count in report["approved_family_counts"].items()
    )
    walk_summary = report.get("typed_walk_motifs") or {}
    if int(walk_summary.get("observation_count") or 0):
        lines.extend(
            [
                "",
                "## Typed Edge Walk",
                "",
                f"- Observed / accepted: `{walk_summary['observation_count']}` / "
                f"`{walk_summary['accepted_count']}`",
            ]
        )
        for macro_id, item in sorted((walk_summary.get("by_macro") or {}).items()):
            lines.append(
                f"- `{macro_id}`: status=`{item['status']}`, "
                f"support=`{item['estimated_support_count']}`, "
                f"structural=`{item['structural_completion_rate']:.2%}`, "
                f"answer_yield=`{item['answer_yield_rate']:.2%}`, "
                f"unique=`{item['unique_answer_rate']:.2%}`, "
                f"root_coverage=`{item['root_coverage_rate']:.2%}`"
            )
    if report.get("top_proposals"):
        lines.extend(["", "## Top Proposals", ""])
        for item in report["top_proposals"]:
            lines.append(
                f"- `{item['motif_family']}` / `{item['proposal_id']}`: "
                f"status=`{item['status']}`, support=`{item['support_count']}`, "
                f"semantic=`{item['semantic_constraint_pass_rate']:.2%}`, "
                f"operation=`{item['operation_execution_pass_rate']:.2%}`, "
                f"heldout=`{item['heldout_binding_pass_rate']:.2%}`"
            )
    (target / "qa_pattern_mining_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
