from __future__ import annotations

from collections import defaultdict
from typing import Any

from finraw.db.client import DBProtocol
from finraw.qa.evidence_finalizer import finalize_evidence
from finraw.qa.graph_walk.query_graph import (
    query_graph_from_dict,
)
from finraw.qa.graph_walk.schema_registry import validate_relation_step
from finraw.qa.store import json_value


WALK_VERIFIER_VERSION = "1.0.0"


def validate_walk_binding(
    db: DBProtocol,
    kg_build_id: str,
    pattern_spec: dict[str, Any],
    binding: dict[str, Any],
    operation_output: dict[str, Any],
) -> dict[str, Any]:
    graph_payload = dict(pattern_spec.get("query_graph_ir") or {})
    stored_hash = str(binding.get("query_graph_hash") or "")
    errors: list[str] = []
    checks: dict[str, Any] = {}
    try:
        graph = query_graph_from_dict(graph_payload)
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "applicable": True,
            "passed": False,
            "verifier_version": WALK_VERIFIER_VERSION,
            "errors": [f"invalid_query_graph:{exc}"],
            "checks": {},
        }

    expected_hash = graph.query_graph_hash
    checks["query_graph_hash"] = {
        "passed": bool(stored_hash)
        and stored_hash == expected_hash
        and str(pattern_spec.get("query_graph_hash") or "") == expected_hash,
        "stored": stored_hash,
        "expected": expected_hash,
    }

    trace = dict(binding.get("walk_binding_trace") or {})
    trace_roles = {
        str(role): [dict(item) for item in nodes or []]
        for role, nodes in dict(trace.get("roles") or {}).items()
    }
    trace_edges = [dict(item) for item in trace.get("edges") or []]
    node_ids = sorted(
        {
            str(node.get("node_id"))
            for nodes in trace_roles.values()
            for node in nodes
            if node.get("node_id")
        }
    )
    edge_ids = sorted(
        str(edge.get("edge_id")) for edge in trace_edges if edge.get("edge_id")
    )
    nodes = _load_nodes(db, kg_build_id, node_ids)
    edges = _load_edges(db, kg_build_id, edge_ids)

    role_errors = []
    node_roles: dict[str, set[str]] = defaultdict(set)
    for role, spec in graph.roles.items():
        bound = trace_roles.get(role, [])
        expected_type = str(spec.get("node_type") or "")
        if spec.get("required", True) and not bound:
            role_errors.append(f"{role}:missing")
        if str(spec.get("cardinality") or "one") == "one" and len(bound) != 1:
            role_errors.append(f"{role}:cardinality")
        for item in bound:
            node_id = str(item.get("node_id") or "")
            node_roles[node_id].add(role)
            actual = nodes.get(node_id)
            if (
                not actual
                or str(actual.get("node_type")) != expected_type
                or str(item.get("node_type")) != expected_type
                or str(item.get("source_pk") or "")
                != str(actual.get("source_pk") or "")
            ):
                role_errors.append(f"{role}:{node_id}:type_or_identity")
    checks["walk_role_type_match"] = {
        "passed": not role_errors,
        "errors": sorted(set(role_errors)),
    }

    edge_errors = []
    declared_steps = [
        {
            "from_role": str(step.get("from_role")),
            "to_role": str(step.get("to_role")),
            "relation": str(step.get("relation")),
            "direction": str(step.get("direction") or "out"),
        }
        for walk in graph.walks
        for step in walk.get("steps") or []
    ]
    for declared in declared_steps:
        try:
            validate_relation_step(
                str(graph.roles[declared["from_role"]]["node_type"]),
                declared["relation"],
                declared["direction"],
                str(graph.roles[declared["to_role"]]["node_type"]),
            )
        except (KeyError, ValueError) as exc:
            edge_errors.append(f"schema:{exc}")
    for item in trace_edges:
        edge_id = str(item.get("edge_id") or "")
        actual = edges.get(edge_id)
        if not actual or any(
            str(item.get(field) or "") != str(actual.get(field) or "")
            for field in ("src_node_id", "dst_node_id", "relation_type")
        ):
            edge_errors.append(f"{edge_id}:missing_or_mutated")
            continue
        src = str(item.get("src_node_id"))
        dst = str(item.get("dst_node_id"))
        matches_declared = any(
            step["relation"] == str(item.get("relation_type"))
            and (
                (
                    step["direction"] == "out"
                    and step["from_role"] in node_roles.get(src, set())
                    and step["to_role"] in node_roles.get(dst, set())
                )
                or (
                    step["direction"] == "in"
                    and step["from_role"] in node_roles.get(dst, set())
                    and step["to_role"] in node_roles.get(src, set())
                )
            )
            for step in declared_steps
        )
        if not matches_declared:
            edge_errors.append(f"{edge_id}:not_declared_by_query_graph")
    checks["walk_edge_replay"] = {
        "passed": bool(trace_edges) and not edge_errors,
        "edge_count": len(trace_edges),
        "errors": sorted(set(edge_errors)),
    }

    join_errors = _validate_joins(graph.joins, trace_roles, nodes)
    checks["walk_join_key_match"] = {
        "passed": not join_errors,
        "errors": join_errors,
        "join_count": len(graph.joins),
    }

    constraint_errors = _validate_role_constraints(
        graph.role_constraints, trace_roles, nodes
    )
    checks["walk_role_constraint_match"] = {
        "passed": not constraint_errors,
        "errors": constraint_errors,
    }

    scope_errors = _validate_scope(graph.role_constraints, trace_roles, nodes, binding)
    checks["walk_scope_exact_match"] = {
        "passed": not scope_errors,
        "errors": scope_errors,
        "scope_coverage": dict(binding.get("scope_coverage") or {}),
    }

    finalized = finalize_evidence(binding, operation_output)
    final_checks = finalized.get("checks") or {}
    checks["answer_lineage_match"] = {
        "passed": bool(final_checks.get("answer_lineage_consistent"))
        and float(final_checks.get("required_evidence_coverage") or 0) == 1.0,
        "details": final_checks,
    }
    checks["evidence_finalization_match"] = {
        "passed": bool(finalized.get("finalization_hash")),
        "finalization": finalized,
    }

    for name, detail in checks.items():
        if not detail.get("passed"):
            errors.append(name)
    return {
        "applicable": True,
        "passed": not errors,
        "verifier_version": WALK_VERIFIER_VERSION,
        "query_graph_hash": expected_hash,
        "errors": errors,
        "checks": checks,
        "evidence_finalization": finalized,
    }


def _load_nodes(
    db: DBProtocol, kg_build_id: str, node_ids: list[str]
) -> dict[str, dict[str, Any]]:
    if not node_ids:
        return {}
    output: dict[str, dict[str, Any]] = {}
    for batch in _chunks(node_ids):
        placeholders = ",".join("?" for _ in batch)
        for raw in db.fetchall(
            "SELECT node_id, node_type, source_pk, properties_json "
            "FROM kg_nodes WHERE kg_build_id = ? "
            f"AND node_id IN ({placeholders}) AND COALESCE(is_active, 1) = 1",
            (kg_build_id, *batch),
        ):
            row = dict(raw)
            row["properties"] = json_value(row.get("properties_json"), {})
            output[str(row["node_id"])] = row
    return output


def _load_edges(
    db: DBProtocol, kg_build_id: str, edge_ids: list[str]
) -> dict[str, dict[str, Any]]:
    if not edge_ids:
        return {}
    output: dict[str, dict[str, Any]] = {}
    for batch in _chunks(edge_ids):
        placeholders = ",".join("?" for _ in batch)
        for raw in db.fetchall(
            "SELECT edge_id, src_node_id, dst_node_id, relation_type "
            "FROM kg_edges WHERE kg_build_id = ? "
            f"AND edge_id IN ({placeholders}) AND COALESCE(is_active, 1) = 1",
            (kg_build_id, *batch),
        ):
            row = dict(raw)
            output[str(row["edge_id"])] = row
    return output


def _validate_joins(
    joins: tuple[dict[str, Any], ...],
    trace_roles: dict[str, list[dict[str, Any]]],
    nodes: dict[str, dict[str, Any]],
) -> list[str]:
    errors = []
    for index, join in enumerate(joins):
        join_type = str(join.get("join_type") or "")
        if join_type == "assert_role_key_equal":
            roles = [str(value) for value in join.get("roles") or []]
            keys = [str(value) for value in join.get("keys") or []]
            key_sets = [
                _role_key_set(trace_roles.get(role, []), nodes, keys) for role in roles
            ]
            if any(not values for values in key_sets):
                errors.append(f"join_{index}:empty_key_set")
                continue
            common = set.intersection(*key_sets)
            minimum = max(int(join.get("minimum_common") or 1), 1)
            if len(common) < minimum:
                errors.append(f"join_{index}:minimum_common")
            if not join.get("intersection") and any(
                values != key_sets[0] for values in key_sets[1:]
            ):
                errors.append(f"join_{index}:unequal_key_sets")
        elif join_type == "assert_role_key_relation":
            left_role = str(join.get("left_role") or "")
            right_role = str(join.get("right_role") or "")
            match_keys = [str(value) for value in join.get("match_keys") or []]
            period_key = str(join.get("key") or "")
            distance = int(join.get("value") or 1)
            left = _period_keys(
                trace_roles.get(left_role, []), nodes, match_keys, period_key
            )
            right = _period_keys(
                trace_roles.get(right_role, []), nodes, match_keys, period_key
            )
            if not left or set(left) != set(right):
                errors.append(f"join_{index}:entity_keys")
                continue
            if any(left[key] - distance != right[key] for key in left):
                errors.append(f"join_{index}:period_relation")
        else:
            errors.append(f"join_{index}:unsupported:{join_type}")
    return errors


def _validate_role_constraints(
    constraints: tuple[dict[str, Any], ...],
    trace_roles: dict[str, list[dict[str, Any]]],
    nodes: dict[str, dict[str, Any]],
) -> list[str]:
    errors = []
    for index, constraint in enumerate(constraints):
        kind = str(constraint.get("constraint") or "")
        if kind == "role_predicates":
            role = str(constraint.get("role") or "")
            for item in trace_roles.get(role, []):
                node = nodes.get(str(item.get("node_id")))
                if not node:
                    continue
                for predicate in constraint.get("predicates") or []:
                    if predicate.get("operator") != "eq" or _node_value(
                        node, str(predicate.get("field") or "")
                    ) != predicate.get("value"):
                        errors.append(f"constraint_{index}:predicate")
        elif kind == "deduplicate_role_by_key":
            role = str(constraint.get("role") or "")
            keys = [str(value) for value in constraint.get("keys") or []]
            values = [
                tuple(_node_value(nodes[str(item["node_id"])], key) for key in keys)
                for item in trace_roles.get(role, [])
                if str(item.get("node_id")) in nodes
            ]
            if not values or len(values) != len(set(values)):
                errors.append(f"constraint_{index}:deduplication")
        elif kind == "require_roles_contiguous":
            roles = [str(value) for value in constraint.get("roles") or []]
            group_keys = [str(value) for value in constraint.get("group_keys") or []]
            period_key = str(constraint.get("period_key") or "")
            minimum = int(constraint.get("minimum_observations") or 2)
            signatures = []
            for role in roles:
                grouped: dict[tuple[Any, ...], set[int]] = defaultdict(set)
                for item in trace_roles.get(role, []):
                    node = nodes.get(str(item.get("node_id")))
                    if not node:
                        continue
                    group = tuple(_node_value(node, key) for key in group_keys)
                    try:
                        grouped[group].add(int(_node_value(node, period_key)))
                    except (TypeError, ValueError):
                        errors.append(f"constraint_{index}:period")
                if not grouped or any(
                    len(periods) < minimum
                    or sorted(periods) != list(range(min(periods), max(periods) + 1))
                    for periods in grouped.values()
                ):
                    errors.append(f"constraint_{index}:contiguous")
                signatures.append(
                    {
                        group: tuple(sorted(periods))
                        for group, periods in grouped.items()
                    }
                )
            if signatures and any(value != signatures[0] for value in signatures[1:]):
                errors.append(f"constraint_{index}:role_alignment")
    return sorted(set(errors))


def _validate_scope(
    constraints: tuple[dict[str, Any], ...],
    trace_roles: dict[str, list[dict[str, Any]]],
    nodes: dict[str, dict[str, Any]],
    binding: dict[str, Any],
) -> list[str]:
    errors = []
    for index, constraint in enumerate(constraints):
        scope_role = str(constraint.get("scope_role") or "")
        fact_roles = [str(value) for value in constraint.get("fact_roles") or []]
        if not scope_role or not fact_roles:
            continue
        expected = {
            str(nodes[str(item["node_id"])].get("source_pk"))
            for item in trace_roles.get(scope_role, [])
            if str(item.get("node_id")) in nodes
        }
        represented = {
            role: {
                str(nodes[str(item["node_id"])].get("properties", {}).get("entity_id"))
                for item in trace_roles.get(role, [])
                if str(item.get("node_id")) in nodes
            }
            for role in fact_roles
        }
        if not expected or any(values != expected for values in represented.values()):
            errors.append(f"coverage_{index}:entity_set_mismatch")
        stored = dict(binding.get("scope_coverage") or {})
        if sorted(expected) != sorted(stored.get("expected_entity_ids") or []):
            errors.append(f"coverage_{index}:stored_expected_mismatch")
        stored_represented = dict(stored.get("represented_entity_ids") or {})
        if any(
            sorted(values) != sorted(stored_represented.get(role) or [])
            for role, values in represented.items()
        ):
            errors.append(f"coverage_{index}:stored_represented_mismatch")
    return errors


def _role_key_set(
    role_nodes: list[dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
    keys: list[str],
) -> set[tuple[Any, ...]]:
    return {
        tuple(_node_value(nodes[str(item["node_id"])], key) for key in keys)
        for item in role_nodes
        if str(item.get("node_id")) in nodes
        and all(
            _node_value(nodes[str(item["node_id"])], key) not in {None, ""}
            for key in keys
        )
    }


def _period_keys(
    role_nodes: list[dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
    match_keys: list[str],
    period_key: str,
) -> dict[tuple[Any, ...], int]:
    output: dict[tuple[Any, ...], int] = {}
    duplicate: set[tuple[Any, ...]] = set()
    for item in role_nodes:
        node = nodes.get(str(item.get("node_id")))
        if not node:
            continue
        key = tuple(_node_value(node, field) for field in match_keys)
        try:
            period = int(_node_value(node, period_key))
        except (TypeError, ValueError):
            continue
        if key in output:
            duplicate.add(key)
        output[key] = period
    for key in duplicate:
        output.pop(key, None)
    return output


def _node_value(node: dict[str, Any], field: str) -> Any:
    if field.startswith("properties."):
        return node.get("properties", {}).get(field.split(".", 1)[1])
    return node.get(field)


def _chunks(values: list[str], size: int = 500) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]
