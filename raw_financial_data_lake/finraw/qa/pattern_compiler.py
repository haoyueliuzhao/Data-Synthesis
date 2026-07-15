from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from finraw.db.client import DBProtocol
from finraw.qa.graph_patterns import GraphPattern, get_pattern
from finraw.qa.store import json_value


COMPILER_VERSION = "2.0.0"


@dataclass(frozen=True)
class LogicalPatternPlan:
    plan_version: int
    compiler_version: str
    proposal_id: str
    proposal_hash: str
    source_kg_build_id: str
    target_kg_build_id: str
    pinned_builds: dict[str, Any]
    motif_family: str
    task_subtype: str
    metric_ids: list[str]
    binding_roles: list[str]
    graph_scan: dict[str, Any]
    relational_ops: list[dict[str, Any]]
    semantic_constraints: list[dict[str, Any]]
    operator_template: dict[str, Any]
    sampling: dict[str, Any]

    def as_row(self) -> dict[str, Any]:
        return asdict(self)


def compile_pattern_proposal(proposal: dict[str, Any]) -> GraphPattern:
    if proposal.get("status") != "published":
        raise ValueError(
            f"Only published pattern proposals can be compiled: {proposal.get('proposal_id')}"
        )
    spec = json_value(proposal.get("pattern_spec"), {})
    if not spec.get("operator_template"):
        raise ValueError("Pattern proposal has no executable operator template")
    static_pattern_id = proposal.get("static_pattern_id")
    if static_pattern_id:
        return get_pattern(str(static_pattern_id))
    semantic_identity = proposal.get("proposal_semantic_id") or proposal.get(
        "motif_signature"
    )
    pattern_id = str(
        "mined_" + str(semantic_identity)[:20]
    )
    return GraphPattern(
        pattern_id=pattern_id,
        pattern_version=int(spec.get("pattern_version", 1)),
        pattern_family=str(spec["pattern_family"]),
        task_subtype=str(spec["task_subtype"]),
        matcher=None,
        node_constraints=list(spec.get("node_constraints") or []),
        edge_constraints=list(spec.get("edge_constraints") or []),
        semantic_constraints=list(spec.get("semantic_constraints") or []),
        operator_template=dict(spec["operator_template"]),
        answer_schema=dict(spec.get("answer_schema") or {}),
        difficulty_base=str(spec.get("difficulty_base") or "hard"),
        question_intents=tuple(
            spec.get("question_intents") or ["mined_financial_analysis"]
        ),
        is_active=True,
    )


def compile_logical_pattern(
    proposal: dict[str, Any],
    kg: dict[str, Any],
    policy: dict[str, Any],
) -> LogicalPatternPlan:
    pattern = compile_pattern_proposal(proposal)
    spec = json_value(proposal.get("pattern_spec"), {})
    metric_ids = _metric_ids(spec)
    strategy_ops = {
        "cross_metric_comparison": [
            {"op": "group", "keys": ["entity", "period", "semantic_context"]},
            {"op": "join_metric_roles", "roles": ["left", "right"]},
        ],
        "temporal_aggregation": [
            {"op": "group_series", "keys": ["entity", "metric", "semantic_context"]},
            {"op": "latest_contiguous_window"},
        ],
        "temporal_extrema_followup": [
            {"op": "group_series", "keys": ["entity", "metric", "semantic_context"]},
            {"op": "join_series_on_period", "coverage": 1.0},
            {"op": "latest_contiguous_window"},
        ],
        "scope_rank_followup": [
            {"op": "group_scope", "keys": ["industry", "period", "semantic_context"]},
            {"op": "complete_case_metric_join", "roles": ["primary", "secondary"]},
        ],
    }
    if proposal["motif_family"] not in strategy_ops:
        raise ValueError(
            f"Unsupported mined motif family: {proposal['motif_family']}"
        )
    return LogicalPatternPlan(
        plan_version=1,
        compiler_version=COMPILER_VERSION,
        proposal_id=str(proposal["proposal_id"]),
        proposal_hash=str(proposal["proposal_hash"]),
        source_kg_build_id=str(proposal["kg_build_id"]),
        target_kg_build_id=str(kg["kg_build_id"]),
        pinned_builds={
            "fact_build_id": kg.get("input_fact_build_id"),
            "entity_build_id": kg.get("input_entity_build_id"),
            "metric_build_id": kg.get("input_metric_build_id"),
            "source_definition_build_id": kg.get(
                "input_source_definition_build_id"
            ),
        },
        motif_family=str(proposal["motif_family"]),
        task_subtype=pattern.task_subtype,
        metric_ids=metric_ids,
        binding_roles=_binding_roles(pattern.operator_template),
        graph_scan={
            "root_node_type": "Fact",
            "fact_table": "standardized_facts",
            "required_edges": list(pattern.edge_constraints),
            "predicates": {
                "graph_ready": True,
                "is_forecast": False,
                "metric_ids": metric_ids,
                "comparability_level_excludes": [
                    "blocked",
                    "incomparable",
                    "not_comparable",
                    "source_definition_mismatch",
                ],
            },
        },
        relational_ops=[
            {"op": "scan_pinned_fact_nodes"},
            {"op": "join_entity_metric_period"},
            *strategy_ops[str(proposal["motif_family"])],
            {"op": "semantic_constraint_gate"},
            {"op": "operation_execution_gate"},
            {"op": "deterministic_stratified_sample"},
        ],
        semantic_constraints=list(pattern.semantic_constraints),
        operator_template=dict(pattern.operator_template),
        sampling={
            "method": "deterministic_hash_stratified",
            "max_per_stratum": int(policy["compiled_max_per_stratum"]),
            "scan_rows_per_metric": int(
                policy["compiled_scan_rows_per_metric"]
            ),
            "scan_mode": (
                "full" if int(policy["compiled_scan_rows_per_metric"]) == 0
                else "bounded"
            ),
            "scan_multiplier": int(policy["compiled_scan_multiplier"]),
            "audit_examples_are_inputs": False,
            "prefer_non_audit_bindings": True,
        },
    )


def logical_plan_hash(plan: LogicalPatternPlan | dict[str, Any]) -> str:
    payload = plan.as_row() if isinstance(plan, LogicalPatternPlan) else plan
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compile_proposal_matches(
    db: DBProtocol,
    kg: dict[str, Any],
    proposal: dict[str, Any],
    *,
    qa_build_id: str,
    limit: int,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compile and execute a proposal against the pinned KG serving layer."""
    from finraw.qa.binding_executor import execute_compiled_bindings

    logical_plan = compile_logical_pattern(proposal, kg, policy)
    return execute_compiled_bindings(
        db,
        kg,
        proposal,
        logical_plan,
        qa_build_id=qa_build_id,
        limit=limit,
        policy=policy,
    )


def _metric_ids(spec: dict[str, Any]) -> list[str]:
    for constraint in spec.get("node_constraints") or []:
        if constraint.get("variable") == "metrics":
            return [str(value) for value in constraint.get("values") or []]
    return []


def _binding_roles(operator_template: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(reference["binding"])
            for step in operator_template.get("operators") or []
            for reference in step.get("inputs") or []
            if reference.get("binding")
        }
    )
