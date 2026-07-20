from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def walk_observation_row(
    *,
    mining_run_id: str,
    kg_build_id: str,
    graph: Any,
    estimate: dict[str, Any],
    scores: dict[str, float],
    status: str,
    rejection_reasons: list[str],
) -> dict[str, Any]:
    row = graph.as_dict()
    walks = list(row.get("walks") or [])
    walk_depth = max((len(item.get("steps") or []) for item in walks), default=0)
    branch_count = max(len(walks) - 1, 0)
    join_count = len(row.get("joins") or [])
    payload = [mining_run_id, kg_build_id, graph.query_graph_hash, estimate, status]
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()
    return {
        "walk_observation_id": "qawalkobs_" + digest[:24],
        "mining_run_id": mining_run_id,
        "kg_build_id": kg_build_id,
        "discovery_method": graph.discovery_method,
        "walk_grammar_version": graph.walk_grammar_version,
        "operation_macro_id": graph.operation_macro_id,
        "walk_signature": _walk_signature(row),
        "query_graph_ir": row,
        "query_graph_hash": graph.query_graph_hash,
        "anchor_node_type": str(row["anchors"][0]["node_type"]),
        "answer_target_type": str(row["answer_target"]["type"]),
        "walk_depth": walk_depth,
        "branch_count": branch_count,
        "join_count": join_count,
        "scope_expansion_count": sum(
            step.get("to_node_type") == "Entity"
            for walk in walks
            for step in walk.get("steps") or []
        ),
        "followup_count": int("followup" in graph.operation_macro_id),
        "estimated_support_count": int(estimate.get("estimated_support_count") or 0),
        "evaluated_binding_count": int(estimate.get("evaluated_binding_count") or 0),
        "completed_binding_count": int(estimate.get("completed_binding_count") or 0),
        "structurally_completed_binding_count": int(
            estimate.get("structurally_completed_binding_count") or 0
        ),
        "structural_completion_rate": float(
            estimate.get("structural_completion_rate") or 0
        ),
        "answer_yield_rate": float(estimate.get("answer_yield_rate") or 0),
        "unique_answer_rate": float(estimate.get("unique_answer_rate") or 0),
        "total_root_count": int(estimate.get("total_root_count") or 0),
        "scanned_root_count": int(estimate.get("scanned_root_count") or 0),
        "root_coverage_rate": float(estimate.get("root_coverage_rate") or 0),
        "evaluated_root_count": int(estimate.get("evaluated_root_count") or 0),
        "evaluation_coverage_rate": float(
            estimate.get("evaluation_coverage_rate") or 0
        ),
        "stratum_coverage": estimate.get("stratum_coverage") or [],
        "financial_value_score": float(scores.get("financial_value_score") or 0),
        "answerability_score": float(scores.get("answerability_score") or 0),
        "novelty_score": float(scores.get("novelty_score") or 0),
        "estimated_cost": float(scores.get("estimated_cost") or 0),
        "total_score": float(scores.get("total_score") or 0),
        "status": status,
        "rejection_reasons": rejection_reasons,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _walk_signature(row: dict[str, Any]) -> str:
    grammar = [
        [
            (
                step.get("from_role"),
                step.get("relation"),
                step.get("direction"),
                step.get("to_role"),
                step.get("to_node_type"),
            )
            for step in walk.get("steps") or []
        ]
        for walk in row.get("walks") or []
    ]
    return hashlib.sha256(json.dumps(grammar, sort_keys=True).encode()).hexdigest()
