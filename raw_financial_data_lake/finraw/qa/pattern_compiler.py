from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from finraw.db.client import DBProtocol
from finraw.qa.graph_patterns import (
    GraphPattern,
    get_pattern,
    pattern_content_hash,
    pattern_semantic_digest,
)
from finraw.qa.store import json_value


COMPILER_VERSION = "2.4.0"


@dataclass(frozen=True)
class LogicalPatternPlan:
    plan_version: int
    compiler_version: str
    ir_version: int
    proposal_id: str
    proposal_hash: str
    pattern_catalog_release_id: str | None
    pattern_catalog_entry_id: str | None
    pattern_catalog_entry_hash: str | None
    catalog_pattern_id: str | None
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
        return _resolve_pinned_static_pattern(proposal, spec)
    if any(
        proposal.get(field) is not None
        for field in ("static_pattern_version", "static_pattern_hash")
    ):
        raise ValueError("Static pattern snapshot fields require static_pattern_id")
    semantic_identity = proposal.get("proposal_semantic_id") or proposal.get(
        "motif_signature"
    )
    pattern_id = str(
        proposal.get("catalog_pattern_id")
        or "mined_" + str(semantic_identity)[:20]
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


def _resolve_pinned_static_pattern(
    proposal: dict[str, Any], spec: dict[str, Any]
) -> GraphPattern:
    proposal_id = proposal.get("proposal_id")
    required = (
        "static_pattern_version",
        "static_pattern_hash",
        "pattern_semantic_digest",
    )
    missing = [field for field in required if proposal.get(field) in (None, "")]
    if missing:
        raise ValueError(
            f"Static pattern binding {proposal_id} is missing snapshot fields: "
            + ", ".join(missing)
        )
    if proposal.get("binding_mode") != "known_pattern_binding":
        raise ValueError(
            f"Static pattern binding {proposal_id} has an invalid binding_mode"
        )
    if float(proposal.get("static_pattern_overlap") or 0.0) != 1.0:
        raise ValueError(
            f"Static pattern binding {proposal_id} requires exact overlap 1.0"
        )

    pattern = get_pattern(str(proposal["static_pattern_id"]))
    pinned_version = int(proposal["static_pattern_version"])
    if pattern.pattern_version != pinned_version:
        raise ValueError(
            f"Static pattern version changed for {pattern.pattern_id}: "
            f"pinned {pinned_version}, current {pattern.pattern_version}"
        )

    pinned_hash = str(proposal["static_pattern_hash"])
    current_hash = pattern_content_hash(pattern)
    if current_hash != pinned_hash:
        raise ValueError(
            f"Static pattern hash changed for {pattern.pattern_id}: "
            f"pinned {pinned_hash}, current {current_hash}"
        )

    pinned_semantic_digest = str(proposal["pattern_semantic_digest"])
    proposal_semantic_digest = pattern_semantic_digest(spec)
    if proposal_semantic_digest != pinned_semantic_digest:
        raise ValueError(
            f"Pattern proposal semantics changed after static binding: {proposal_id}"
        )
    current_semantic_digest = pattern_semantic_digest(pattern)
    if current_semantic_digest != pinned_semantic_digest:
        raise ValueError(
            f"Static pattern semantics do not match proposal {proposal_id}"
        )
    return pattern


def compile_logical_pattern(
    proposal: dict[str, Any],
    kg: dict[str, Any],
    policy: dict[str, Any],
) -> LogicalPatternPlan:
    pattern = compile_pattern_proposal(proposal)
    spec = json_value(proposal.get("pattern_spec"), {})
    metric_ids = _metric_ids(spec)
    binding_query = _binding_query(spec, pattern)
    if binding_query["scan_kind"] == "graph":
        relational_ops = [
            *binding_query["relational_ops"],
            {"op": "semantic_constraint_gate"},
            {"op": "operation_execution_gate"},
            {"op": "sample", "method": "deterministic_hash_stratified"},
        ]
        graph_scan = {
            "scan_kind": "graph",
            "root": dict(binding_query["relational_ops"][0]),
            "required_edges": list(pattern.edge_constraints),
        }
    else:
        relational_ops = [
            {"op": "scan_pinned_fact_nodes"},
            {"op": "join_entity_metric_period"},
            *binding_query["relational_ops"],
            {"op": "semantic_constraint_gate"},
            {"op": "operation_execution_gate"},
            {"op": "sample", "method": "deterministic_hash_stratified"},
        ]
        graph_scan = {
            "scan_kind": "fact",
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
        }
    from finraw.qa.binding_executor import validate_relational_ops

    validate_relational_ops(relational_ops)
    return LogicalPatternPlan(
        plan_version=2,
        ir_version=int(binding_query["ir_version"]),
        compiler_version=COMPILER_VERSION,
        proposal_id=str(proposal["proposal_id"]),
        proposal_hash=str(proposal["proposal_hash"]),
        pattern_catalog_release_id=proposal.get("pattern_catalog_release_id"),
        pattern_catalog_entry_id=proposal.get("pattern_catalog_entry_id"),
        pattern_catalog_entry_hash=proposal.get("pattern_catalog_entry_hash"),
        catalog_pattern_id=proposal.get("catalog_pattern_id"),
        source_kg_build_id=str(proposal["kg_build_id"]),
        target_kg_build_id=str(kg["kg_build_id"]),
        pinned_builds={
            "fact_build_id": kg.get("input_fact_build_id"),
            "entity_build_id": kg.get("input_entity_build_id"),
            "metric_build_id": kg.get("input_metric_build_id"),
            "source_definition_build_id": kg.get("input_source_definition_build_id"),
        },
        motif_family=str(proposal["motif_family"]),
        task_subtype=pattern.task_subtype,
        metric_ids=metric_ids,
        binding_roles=_binding_roles(pattern.operator_template),
        graph_scan=graph_scan,
        relational_ops=relational_ops,
        semantic_constraints=list(pattern.semantic_constraints),
        operator_template=dict(pattern.operator_template),
        sampling={
            "method": "deterministic_hash_stratified",
            "max_per_stratum": int(policy["compiled_max_per_stratum"]),
            "scan_rows_per_metric": int(policy["compiled_scan_rows_per_metric"]),
            "graph_scan_rows": int(policy.get("compiled_graph_scan_rows", 5000)),
            "scan_mode": (
                "full"
                if int(policy["compiled_scan_rows_per_metric"]) == 0
                else "bounded"
            ),
            "scan_multiplier": int(policy["compiled_scan_multiplier"]),
            "audit_examples_are_inputs": False,
            "prefer_non_audit_bindings": True,
            "stratum_fields": list(binding_query["stratum_fields"]),
        },
    )


def _binding_query(spec: dict[str, Any], pattern: GraphPattern) -> dict[str, Any]:
    declared = json_value(spec.get("binding_query"), {})
    if declared:
        query = {
            "ir_version": int(declared.get("ir_version", 0)),
            "scan_kind": str(declared.get("scan_kind") or "fact"),
            "relational_ops": list(declared.get("relational_ops") or []),
            "stratum_fields": list(declared.get("stratum_fields") or []),
        }
    else:
        query = _legacy_binding_query(spec, pattern)
        query.setdefault("scan_kind", "fact")
    if query["ir_version"] != 1:
        raise ValueError(f"Unsupported binding query IR version: {query['ir_version']}")
    if not query["relational_ops"]:
        raise ValueError("Pattern proposal has no declarative relational operators")
    if not query["stratum_fields"]:
        raise ValueError("Pattern proposal has no declarative sampling strata")
    return query


def _legacy_binding_query(
    spec: dict[str, Any], pattern: GraphPattern
) -> dict[str, Any]:
    metric_ids = _metric_ids(spec)
    signature = tuple(
        str(step.get("operator") or "")
        for step in pattern.operator_template.get("operators") or []
    )
    if signature == ("compare",) and len(metric_ids) == 2:
        relational_ops = [
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
                    {"binding": "left", "metric_id": metric_ids[0]},
                    {"binding": "right", "metric_id": metric_ids[1]},
                ],
            },
        ]
        strata = ["metric_ids", "frequency", "period", "entity_hash_bucket"]
    elif signature == ("mean",) and len(metric_ids) == 1:
        relational_ops = [
            {"op": "group_series"},
            {
                "op": "latest_contiguous_window",
                "binding": "series",
                "require_annual_duration": True,
            },
        ]
        strata = ["metric_ids", "frequency", "end_period", "entity_hash_bucket"]
    elif signature == ("argmax", "select_by_period") and len(metric_ids) == 2:
        relational_ops = [
            {"op": "group_series"},
            {
                "op": "latest_contiguous_window",
                "require_annual_duration": True,
            },
            {
                "op": "join_series_on_period",
                "coverage": 1.0,
                "roles": [
                    {"binding": "primary_series", "metric_id": metric_ids[0]},
                    {"binding": "secondary_series", "metric_id": metric_ids[1]},
                ],
            },
        ]
        strata = ["metric_ids", "frequency", "end_period", "entity_hash_bucket"]
    elif signature == ("rank", "lookup_ranked_entities") and len(metric_ids) == 2:
        relational_ops = [
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
                    {"binding": "primary", "metric_id": metric_ids[0]},
                    {"binding": "secondary", "metric_id": metric_ids[1]},
                ],
            },
        ]
        strata = ["metric_ids", "industry", "period"]
    else:
        raise ValueError(
            "Historical proposal has no binding_query and its Operation DAG "
            f"signature is not migratable: {signature}"
        )
    return {
        "ir_version": 1,
        "relational_ops": relational_ops,
        "stratum_fields": strata,
        "migration": "operation_dag_signature_v1",
    }


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
    metric_fact_cache: Any | None = None,
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
        metric_fact_cache=metric_fact_cache,
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
