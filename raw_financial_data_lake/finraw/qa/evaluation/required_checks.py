from __future__ import annotations

import hashlib
import json
from typing import Any


REQUIRED_CHECK_MANIFEST_VERSION = "qa_required_checks.v1"

COMMON_CHECKS = frozenset(
    {
        "benchmark_output_contract",
        "derived_input_edge_coverage",
        "evidence_component_count",
        "evidence_path",
        "evidence_semantics",
        "fact_membership",
        "independent_recompute",
        "no_answer_leakage",
        "question_answer_isolation",
        "question_parser_contract",
        "question_semantic_reparse",
        "question_slot_roundtrip",
        "scope_fact_coverage",
        "semantic_slots",
        "source_fact_coverage",
        "structure",
    }
)

GRAPH_CHECKS = frozenset(
    {
        "graph_pattern_match",
        "intermediate_result_recompute",
        "operation_trace_coverage",
        "operator_input_complete",
        "operator_type_valid",
        "semantic_constraint_gate",
    }
)

COMPILED_CHECKS = frozenset(
    {
        "compiled_binding_match",
        "pattern_proposal_match",
    }
)

WALK_CHECKS = frozenset(
    {
        "answer_lineage_match",
        "evidence_finalization_match",
        "query_graph_hash",
        "walk_edge_replay",
        "walk_join_key_match",
        "walk_role_constraint_match",
        "walk_role_type_match",
        "walk_scope_exact_match",
    }
)

PIPELINE_CHECKS = {
    "fact_qa": COMMON_CHECKS,
    "derived_fact_qa": COMMON_CHECKS,
    "static_graph_pattern": COMMON_CHECKS | GRAPH_CHECKS,
    "automatic_pattern_mining": COMMON_CHECKS | GRAPH_CHECKS | COMPILED_CHECKS,
    "typed_edge_walk": COMMON_CHECKS | GRAPH_CHECKS | COMPILED_CHECKS | WALK_CHECKS,
}


def required_checks_for(
    pipeline: str, candidate: dict[str, Any] | None = None
) -> tuple[str, ...]:
    if pipeline not in PIPELINE_CHECKS:
        raise ValueError(f"Unknown QA generation pipeline: {pipeline}")
    checks = set(PIPELINE_CHECKS[pipeline])
    scope = dict((candidate or {}).get("entity_scope") or {})
    if scope.get("expected_entity_ids"):
        checks.add("scope_completeness")
    return tuple(sorted(checks))


def required_check_manifest() -> dict[str, Any]:
    manifest = {
        "version": REQUIRED_CHECK_MANIFEST_VERSION,
        "pipelines": {
            pipeline: sorted(checks)
            for pipeline, checks in sorted(PIPELINE_CHECKS.items())
        },
        "conditional_checks": {
            "scope_completeness": "entity_scope.expected_entity_ids is non-empty"
        },
    }
    manifest["manifest_hash"] = _hash(manifest)
    return manifest


def required_check_manifest_hash() -> str:
    return str(required_check_manifest()["manifest_hash"])


def _hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
