from __future__ import annotations

import hashlib
import json
from typing import Any


EVIDENCE_FINALIZER_VERSION = "1.0.0"
_REQUIRED_RELATIONS = {
    "MEASURES",
    "IN_PERIOD",
    "FROM_SOURCE",
    "USES_SOURCE_DEFINITION",
    "TRACED_TO",
    "DERIVED_FROM",
}
_CONTEXT_RELATIONS = {"HAS_SCOPE", "CONTAINS_ENTITY", "HAS_FACT"}


def finalize_evidence(
    binding: dict[str, Any],
    operation_output: dict[str, Any],
) -> dict[str, Any]:
    trace = dict(binding.get("walk_binding_trace") or {})
    roles = dict(trace.get("roles") or {})
    edges = [
        dict(edge) for edge in trace.get("edges") or binding.get("graph_edges") or []
    ]
    node_by_id = {
        str(node["node_id"]): node
        for nodes in roles.values()
        for node in nodes
        if node.get("node_id")
    }
    lineage = dict(operation_output.get("lineage") or {})
    required_fact_ids = sorted(
        str(value)
        for value in lineage.get("selected_fact_ids")
        or lineage.get("input_fact_ids")
        or []
    )
    raw_object_ids = _collect_named_values(operation_output, "raw_object_ids")
    required_seed_ids = {
        node_id
        for node_id, node in node_by_id.items()
        if (
            node.get("node_type") == "Fact"
            and str(node.get("source_pk")) in required_fact_ids
        )
        or (
            node.get("node_type") == "RawObject"
            and str(node.get("source_pk")) in raw_object_ids
        )
    }
    required_edges = [
        edge
        for edge in edges
        if str(edge.get("relation_type")) in _REQUIRED_RELATIONS
        and (
            str(edge.get("src_node_id")) in required_seed_ids
            or str(edge.get("dst_node_id")) in required_seed_ids
        )
    ]
    required_node_ids = set(required_seed_ids)
    for edge in required_edges:
        required_node_ids.update(
            [str(edge.get("src_node_id")), str(edge.get("dst_node_id"))]
        )
    context_edges = [
        edge
        for edge in edges
        if edge not in required_edges
        and (
            str(edge.get("relation_type")) in _CONTEXT_RELATIONS
            or str(edge.get("src_node_id")) in required_node_ids
            or str(edge.get("dst_node_id")) in required_node_ids
        )
    ]
    context_node_ids = {
        str(value)
        for edge in context_edges
        for value in (edge.get("src_node_id"), edge.get("dst_node_id"))
        if str(value) not in required_node_ids
    }
    discarded_edges = [
        edge
        for edge in edges
        if edge not in required_edges and edge not in context_edges
    ]
    mapped_fact_ids = {
        str(node.get("source_pk"))
        for node_id, node in node_by_id.items()
        if node_id in required_node_ids and node.get("node_type") == "Fact"
    }
    missing_fact_ids = sorted(set(required_fact_ids) - mapped_fact_ids)
    result = {
        "finalizer_version": EVIDENCE_FINALIZER_VERSION,
        "required_evidence": {
            "fact_ids": required_fact_ids,
            "node_ids": sorted(required_node_ids),
            "edges": _sorted_edges(required_edges),
        },
        "context_evidence": {
            "node_ids": sorted(context_node_ids),
            "edges": _sorted_edges(context_edges),
        },
        "discarded_evidence": {
            "edge_count": len(discarded_edges),
            "edges": _sorted_edges(discarded_edges),
        },
        "checks": {
            "required_evidence_coverage": 1.0 if not missing_fact_ids else 0.0,
            "missing_required_fact_ids": missing_fact_ids,
            "scope_context_coverage": float(
                bool(binding.get("scope_coverage"))
                or not binding.get("scope_entity_ids")
            ),
            "answer_lineage_consistent": not missing_fact_ids,
        },
    }
    result["finalization_hash"] = _digest(result)
    return result


def _collect_named_values(value: Any, field: str) -> set[str]:
    output: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == field:
                values = item if isinstance(item, list) else [item]
                output.update(str(entry) for entry in values if entry not in {None, ""})
            else:
                output.update(_collect_named_values(item, field))
    elif isinstance(value, list):
        for item in value:
            output.update(_collect_named_values(item, field))
    return output


def _sorted_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [dict(edge) for edge in edges],
        key=lambda edge: (
            str(edge.get("relation_type")),
            str(edge.get("src_node_id")),
            str(edge.get("dst_node_id")),
            str(edge.get("edge_id")),
        ),
    )


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()
