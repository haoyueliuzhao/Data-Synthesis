"""Bounded, witnessed isomorphism of the six retained public behavior graphs.

This module executes neither candidates nor providers.  JSON structural keys are
used as exact equality indices, never as graph-hash or answer-based authority.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any

from .projection import EDGE_KINDS, GRAPH_SCHEMA, NODE_ALLOWED_FIELDS, NODE_REQUIRED_FIELDS

EQUIVALENT = "equivalent"
DIFFERENT = "different_retained_semantics"
UNDETERMINED = "undetermined"
PAIR_ORDER = (("B", "C"), ("B", "A"), ("A", "C"))
DEFAULT_MAX_SEARCH_STATES = 100_000

SEMANTIC_FIELD_DOMAIN = {
    "evidence_scalar": ("kind", "role"),
    "growth_percent": ("kind", "metric", "earlier_role", "later_role", "unit"),
    "signed_growth_gap": ("kind", "reference_metric", "observed_metric", "unit"),
    "absolute_growth_spread": ("kind", "unit"),
}
OPERATION_CONTRACT_FIELDS = (
    "action_type",
    "compatibility_policy",
    "downstream_selector_contract",
    "execution_mode",
    "executor_version",
    "formula_id",
    "input_order_policy",
    "input_role_contract",
    "input_schema",
    "invariant_checks",
    "operator_id",
    "output_model_schema",
    "output_schema",
    "parameter_contract",
    "program_role",
    "rounding_policy",
    "schema_version",
    "semantic_version",
    "tolerance_policy",
    "tool_capability",
    "verifier_id",
    "verifier_version",
)
NESTED_REQUIRED_PATHS = {
    "task": (
        "contract.task.task_id",
        "contract.task.public.answer_schema",
        "contract.task.public.requirements",
        "contract.task.oracle.task_program",
        "contract.task.oracle.selection_contract",
        "contract.scope_bindings",
        "contract.binding_snapshot.role_bindings",
    ),
    "evidence": (
        "record.evidence_id",
        "record.evidence_version_id",
        "record.assertion_id",
        "record.evidence_kind",
        "record.payload.kind",
        "record.payload.value",
        "record.payload.unit",
        "record.payload.currency",
        "record.source.source_id",
        "record.source.authority",
        "record.source_locator.raw_object_id",
        "record.source_locator.source_document_id",
        "record.source_locator.document_version",
        "record.source_locator.json_pointer",
        "record.source_locator.table_cell",
        "record.provenance.content_hash",
        "record.provenance.source_record_id",
        "record.subject.subject_id",
        "record.temporal_context.valid_from",
        "record.temporal_context.valid_to",
        "record.definition.definition_id",
    ),
    "operation": ("output.value",),
    "observation": ("output.value",),
    "claim": ("output.value",),
    "final": ("answer.result.value", "answer.result.unit"),
}


def comparison_rule_contract() -> dict[str, Any]:
    """Public, serializable rule specification to persist before measurement."""
    return {
        "schema": "finite_public_behavior_comparison_rules.v1",
        "graph_schema": GRAPH_SCHEMA,
        "node_required_fields": {k: list(v) for k, v in NODE_REQUIRED_FIELDS.items()},
        "node_allowed_fields": {k: list(v) for k, v in NODE_ALLOWED_FIELDS.items()},
        "semantic_field_domain": SEMANTIC_FIELD_DOMAIN,
        "operation_contract_fields": list(OPERATION_CONTRACT_FIELDS),
        "nested_required_paths": NESTED_REQUIRED_PATHS,
        "metadata_float_rule": "finite_float_hex_exact_bit_value_no_tolerance",
        "supported_edge_kinds": sorted(EDGE_KINDS),
        "measurement_timing": "known_candidates_rule_instantiation_not_data_blind",
        "node_comparison": "complete_bijection_preserving_kind_and_every_attribute",
        "edge_comparison": "directed_multiset_both_directions_all_attributes_roles_positions",
        "numeric_normalization": "explicit_exact_decimal_markers_only_no_tolerance",
        "numeric_context": "no_decimal_context_rounding_or_normalize",
        "operational_exclusions": [
            "node_id_spelling",
            "node_and_edge_serialization_order",
            "audit",
        ],
        "non_authorities": ["graph_hash", "final_answer_alone", "route_label", "node_count_alone"],
        "missing_or_unsupported_semantics": UNDETERMINED,
        "incomplete_search": UNDETERMINED,
        "input_not_admitted": "excluded_before_semantic_relation_no_class_assignment",
        "pair_order_per_task": [list(pair) for pair in PAIR_ORDER],
        "task_domain": ["F1", "F2"],
        "primary_candidates": ["B", "A"],
        "regression_control": "C",
        "cross_task_comparison": False,
        "default_max_search_states": DEFAULT_MAX_SEARCH_STATES,
        "class_count_requires": "complete_consistent_relation_on_the_corresponding_finite_domain",
    }


class _Unsupported(ValueError):
    pass


def normalize_decimal(value: Any) -> str:
    """Canonicalize exact finite decimals without context-dependent rounding."""
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise _Unsupported("exact decimal must be a string, integer, or Decimal")
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise _Unsupported("invalid exact decimal") from error
    if not number.is_finite():
        raise _Unsupported("nonfinite exact decimal")
    if number.is_zero():
        return "0"
    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _key(value: Any) -> tuple[Any, ...]:
    """Collision-free typed structural tuple; dictionary order is immaterial."""
    if isinstance(value, Mapping):
        if any(not isinstance(k, str) for k in value):
            raise _Unsupported("semantic object keys must be strings")
        if value.get("numeric_type") == "exact_decimal":
            if set(value) != {"numeric_type", "value"}:
                raise _Unsupported("unexpected fields in exact decimal marker")
            return ("exact_decimal", normalize_decimal(value["value"]))
        return ("object", tuple((k, _key(value[k])) for k in sorted(value)))
    if isinstance(value, (list, tuple)):
        return ("array", tuple(_key(item) for item in value))
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int):
        return ("int", value)
    if isinstance(value, str):
        return ("str", value)
    if isinstance(value, float) and isfinite(value):
        return ("finite_metadata_float", value.hex())
    raise _Unsupported(f"unsupported semantic value type: {type(value).__name__}")


def _edge_attrs(edge: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in edge.items() if k not in {"source", "target"}}


def _node_key(node: Mapping[str, Any]) -> tuple[Any, ...]:
    return _key({"kind": node["kind"], "attrs": node["attrs"]})


def _differences(left: Any, right: Any, path: str = "attrs") -> list[dict[str, Any]]:
    if _key(left) == _key(right):
        return []
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        out = []
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}"
            if key not in left or key not in right:
                out.append(
                    {
                        "path": child,
                        "left_present": key in left,
                        "right_present": key in right,
                        "left": left.get(key),
                        "right": right.get(key),
                    }
                )
            else:
                out.extend(_differences(left[key], right[key], child))
        return out
    if (
        isinstance(left, (list, tuple))
        and isinstance(right, (list, tuple))
        and len(left) == len(right)
    ):
        return [
            row
            for i, (a, b) in enumerate(zip(left, right, strict=True))
            for row in _differences(a, b, f"{path}[{i}]")
        ]
    return [{"path": path, "left": left, "right": right}]


def _semantic_schema(value: Any, path: str) -> list[str]:
    if (
        not isinstance(value, Mapping)
        or not isinstance(value.get("kind"), str)
        or value.get("kind") not in SEMANTIC_FIELD_DOMAIN
    ):
        return [f"{path}: unsupported typed semantic kind"]
    if set(value) != set(SEMANTIC_FIELD_DOMAIN[value["kind"]]):
        return [f"{path}: missing or unsupported typed semantic fields"]
    return []


def _nested_issues(node: Mapping[str, Any], prefix: str) -> list[str]:
    attrs, kind = node["attrs"], node["kind"]
    issues = []
    for path in NESTED_REQUIRED_PATHS.get(kind, ()):
        cursor = attrs
        for component in path.split("."):
            if not isinstance(cursor, Mapping) or component not in cursor:
                issues.append(f"{prefix}.attrs.{path}: required nested semantic field missing")
                break
            cursor = cursor[component]
        else:
            if cursor is None:
                issues.append(f"{prefix}.attrs.{path}: required semantic value is null")
    if kind in {"decision", "claim"}:
        field = "expected_semantic" if kind == "decision" else "semantic"
        issues.extend(_semantic_schema(attrs.get(field), f"{prefix}.attrs.{field}"))
    if kind == "operation":
        contract = attrs.get("contract")
        if not isinstance(contract, Mapping) or set(contract) != set(OPERATION_CONTRACT_FIELDS):
            issues.append(
                f"{prefix}.attrs.contract: missing or unsupported operation contract fields"
            )
        else:
            if contract["schema_version"] != "operation_semantic_contract.v1":
                issues.append(f"{prefix}.attrs.contract.schema_version: unsupported contract")
            for field in ("semantic_version", "formula_id", "input_order_policy", "verifier_id"):
                if not isinstance(contract[field], str) or not contract[field]:
                    issues.append(
                        f"{prefix}.attrs.contract.{field}: required semantic identifier missing"
                    )
            if (
                not isinstance(contract["input_role_contract"], list)
                or not contract["input_role_contract"]
            ):
                issues.append(
                    f"{prefix}.attrs.contract.input_role_contract: ordered roles required"
                )
    return issues


def _graph_issues(graph: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if set(graph) - {"schema", "task_key", "nodes", "edges", "admission", "normalization", "audit"}:
        issues.append("graph: unsupported top-level semantic fields")
    if graph.get("schema") != GRAPH_SCHEMA:
        issues.append("schema: missing or unsupported graph version")
    if not isinstance(graph.get("task_key"), str) or not graph.get("task_key"):
        issues.append("task_key: exact task identity required")
    normalization = graph.get("normalization")
    if not isinstance(normalization, Mapping):
        issues.append("normalization: required rule application record missing")
    elif normalization.get("complete") is not True or normalization.get("issues"):
        issues.append(
            f"normalization: incomplete or unsupported semantics: {normalization.get('issues', [])}"
        )
    elif not isinstance(normalization.get("reductions"), list):
        issues.append("normalization.reductions: complete finite reduction records required")
    nodes, edges = graph.get("nodes"), graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return issues + ["nodes/edges: explicit lists required"]
    if not nodes:
        issues.append("nodes: retained public graph cannot be empty")
    ids: set[str] = set()
    for index, node in enumerate(nodes):
        prefix = f"nodes[{index}]"
        if not isinstance(node, Mapping):
            issues.append(f"{prefix}: typed node object required")
            continue
        if set(node) != {"id", "kind", "attrs"}:
            issues.append(f"{prefix}: missing or unsupported node fields")
        identity, kind, attrs = node.get("id"), node.get("kind"), node.get("attrs")
        if not isinstance(identity, str) or not identity or identity in ids:
            issues.append(f"{prefix}.id: nonempty unique node identity required")
        elif isinstance(identity, str):
            ids.add(identity)
        if not isinstance(kind, str) or kind not in NODE_REQUIRED_FIELDS:
            issues.append(f"{prefix}.kind: unsupported semantic structure {kind!r}")
        elif not isinstance(attrs, Mapping):
            issues.append(f"{prefix}.attrs: typed semantic fields required")
        else:
            missing = sorted(set(NODE_REQUIRED_FIELDS[kind]) - set(attrs))
            if missing:
                issues.append(f"{prefix}.attrs: missing required fields {missing}")
            extra = sorted(set(attrs) - set(NODE_ALLOWED_FIELDS[kind]))
            if extra:
                issues.append(f"{prefix}.attrs: unsupported semantic fields {extra}")
            issues.extend(_nested_issues(node, prefix))
            try:
                _key(attrs)
            except _Unsupported as error:
                issues.append(f"{prefix}.attrs: {error}")
    for index, edge in enumerate(edges):
        prefix = f"edges[{index}]"
        if not isinstance(edge, Mapping):
            issues.append(f"{prefix}: typed edge object required")
            continue
        required = {"source", "target", "kind"}
        allowed = required | {"role", "position", "attrs"}
        if edge.get("kind") == "operand":
            required = required | {"role", "position", "attrs"}
        if not required <= set(edge) or set(edge) - allowed:
            issues.append(f"{prefix}: missing or unsupported edge fields")
        if not isinstance(edge.get("kind"), str) or edge.get("kind") not in EDGE_KINDS:
            issues.append(f"{prefix}.kind: unsupported edge relation")
        if any(
            not isinstance(edge.get(k), str) or edge.get(k) not in ids for k in ("source", "target")
        ):
            issues.append(f"{prefix}: dangling or invalid endpoint")
        if edge.get("position") is not None and (
            isinstance(edge["position"], bool)
            or not isinstance(edge["position"], int)
            or edge["position"] < 0
        ):
            issues.append(f"{prefix}.position: nonnegative integer or null required")
        if edge.get("role") is not None and not isinstance(edge["role"], str):
            issues.append(f"{prefix}.role: string or null required")
        if edge.get("kind") == "operand" and (
            edge.get("role") is None or edge.get("position") is None
        ):
            issues.append(f"{prefix}: operand requires ordered position and role")
        if edge.get("kind") == "operand":
            attrs = edge.get("attrs")
            if not isinstance(attrs, Mapping) or set(attrs) != {
                "selector",
                "selected_value",
                "semantic",
            }:
                issues.append(f"{prefix}.attrs: missing or unsupported operand fields")
            else:
                issues.extend(_semantic_schema(attrs["semantic"], f"{prefix}.attrs.semantic"))
        try:
            _key(_edge_attrs(edge))
        except _Unsupported as error:
            issues.append(f"{prefix}: {error}")
    return issues


def _admission(graph: Mapping[str, Any]) -> dict[str, Any]:
    value = graph.get("admission")
    if not isinstance(value, Mapping):
        return {"admitted": False, "issues": ["own-qualified input admission missing"]}
    issues = value.get("issues", [])
    if not isinstance(issues, list):
        return {"admitted": False, "issues": ["invalid admission issue record"]}
    return {"admitted": value.get("admitted") is True and not issues, "issues": list(issues)}


def _reductions(graph: Mapping[str, Any]) -> Any:
    normalization = graph.get("normalization")
    return normalization.get("reductions", []) if isinstance(normalization, Mapping) else []


def _semantic_edges(graph: Mapping[str, Any], nodes: Mapping[str, Any]) -> Counter:
    return Counter(
        (_node_key(nodes[e["source"]]), _node_key(nodes[e["target"]]), _key(_edge_attrs(e)))
        for e in graph["edges"]
    )


def _edge_counter(graph: Mapping[str, Any]) -> Counter:
    return Counter((e["source"], e["target"], _key(_edge_attrs(e))) for e in graph["edges"])


def _certificate(
    left: Mapping[str, Any], right: Mapping[str, Any], mapping: Mapping[str, str]
) -> dict[str, Any]:
    lnodes = {n["id"]: n for n in left["nodes"]}
    rnodes = {n["id"]: n for n in right["nodes"]}
    bijective = (
        set(mapping) == set(lnodes)
        and set(mapping.values()) == set(rnodes)
        and len(mapping) == len(set(mapping.values()))
    )
    nodes_equal = bijective and all(
        _node_key(lnodes[a]) == _node_key(rnodes[b]) for a, b in mapping.items()
    )
    transformed = Counter(
        (mapping[e["source"]], mapping[e["target"]], _key(_edge_attrs(e))) for e in left["edges"]
    )
    right_edges = _edge_counter(right)
    inverse = {b: a for a, b in mapping.items()}
    back = Counter(
        (inverse[e["source"]], inverse[e["target"]], _key(_edge_attrs(e))) for e in right["edges"]
    )
    forward_equal = transformed == right_edges
    backward_equal = back == _edge_counter(left)
    by_edge: dict[Any, list[int]] = defaultdict(list)
    for i, edge in enumerate(right["edges"]):
        by_edge[(edge["source"], edge["target"], _key(_edge_attrs(edge)))].append(i)
    edge_rows = []
    if forward_equal:
        for i, edge in enumerate(left["edges"]):
            key = (mapping[edge["source"]], mapping[edge["target"]], _key(_edge_attrs(edge)))
            j = by_edge[key].pop()
            edge_rows.append(
                {
                    "left_index": i,
                    "right_index": j,
                    "left": dict(edge),
                    "right": dict(right["edges"][j]),
                    "all_edge_attributes_preserved": True,
                }
            )
    return {
        "complete_node_bijection_verified": bijective,
        "all_node_attributes_verified": nodes_equal,
        "all_directed_edges_forward_verified": forward_equal,
        "all_directed_edges_backward_verified": backward_equal,
        "ordered_roles_and_positions_preserved": forward_equal and backward_equal,
        "node_bijection": [
            {
                "left_id": a,
                "right_id": b,
                "kind": lnodes[a]["kind"],
                "left_attrs": lnodes[a]["attrs"],
                "right_attrs": rnodes[b]["attrs"],
                "all_attributes_preserved": _node_key(lnodes[a]) == _node_key(rnodes[b]),
            }
            for a, b in sorted(mapping.items())
        ],
        "edge_bijection": edge_rows,
        "node_count": len(lnodes),
        "edge_count": len(left["edges"]),
    }


def compare_graphs(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    max_search_states: int = DEFAULT_MAX_SEARCH_STATES,
) -> dict[str, Any]:
    """Return a witnessed three-valued relation, or exclude unadmitted inputs."""
    admission = {"left": _admission(left), "right": _admission(right)}
    eligible = all(item["admitted"] for item in admission.values())
    result: dict[str, Any] = {
        "schema": "finite_public_behavior_pair_result.v1",
        "status": None,
        "input_admission": {**admission, "eligible_for_comparison": eligible},
        "task_key": left.get("task_key"),
        "issues": [],
        "retained_differences": [],
        "correspondence": None,
        "finite_search": {"completed": False, "states_examined": 0, "limit": max_search_states},
        "finite_reductions": {"left": _reductions(left), "right": _reductions(right)},
    }
    if not eligible:
        result["issues"] = ["input rejected before semantic comparison; no class assignment"]
        return result
    result["status"] = UNDETERMINED
    issues = [f"left.{item}" for item in _graph_issues(left)] + [
        f"right.{item}" for item in _graph_issues(right)
    ]
    if left.get("task_key") != right.get("task_key"):
        issues.append("cross-task comparison is outside the finite domain")
    if (
        isinstance(max_search_states, bool)
        or not isinstance(max_search_states, int)
        or max_search_states < 0
    ):
        issues.append("max_search_states must be a nonnegative integer")
    if issues:
        result["issues"] = issues
        return result
    lnodes = {n["id"]: n for n in left["nodes"]}
    rnodes = {n["id"]: n for n in right["nodes"]}
    lcounts, rcounts = (
        Counter(map(_node_key, lnodes.values())),
        Counter(map(_node_key, rnodes.values())),
    )
    if lcounts != rcounts:
        rows = []
        for node in lnodes.values():
            signature = _node_key(node)
            if lcounts[signature] <= rcounts[signature]:
                continue
            alternatives = [n for n in rnodes.values() if n["kind"] == node["kind"]]
            nearest = min(
                alternatives,
                key=lambda n: len(_differences(node["attrs"], n["attrs"])),
                default=None,
            )
            rows.append(
                {
                    "kind": "retained_node_label_multiplicity",
                    "left_node_id": node["id"],
                    "semantic_kind": node["kind"],
                    "left_attributes": node["attrs"],
                    "left_count": lcounts[signature],
                    "right_count": rcounts[signature],
                    "closest_same_kind_right_node": None if nearest is None else nearest["id"],
                    "attribute_differences": []
                    if nearest is None
                    else _differences(node["attrs"], nearest["attrs"]),
                }
            )
        for node in rnodes.values():
            signature = _node_key(node)
            if rcounts[signature] > lcounts[signature]:
                rows.append(
                    {
                        "kind": "retained_node_label_multiplicity",
                        "right_node_id": node["id"],
                        "semantic_kind": node["kind"],
                        "right_attributes": node["attrs"],
                        "left_count": lcounts[signature],
                        "right_count": rcounts[signature],
                    }
                )
        result.update(status=DIFFERENT, retained_differences=rows)
        result["finite_search"].update(
            completed=True, proof="complete_retained_node_label_inventory_incompatibility"
        )
        return result
    ledges, redges = _semantic_edges(left, lnodes), _semantic_edges(right, rnodes)
    if ledges != redges:
        rows = []
        for side, graph, nodes, own, other in (
            ("left", left, lnodes, ledges, redges),
            ("right", right, rnodes, redges, ledges),
        ):
            seen = set()
            for edge in graph["edges"]:
                signature = (
                    _node_key(nodes[edge["source"]]),
                    _node_key(nodes[edge["target"]]),
                    _key(_edge_attrs(edge)),
                )
                if signature in seen or own[signature] <= other[signature]:
                    continue
                seen.add(signature)
                rows.append(
                    {
                        "kind": "retained_directed_edge_label_multiplicity",
                        "side": side,
                        "edge": dict(edge),
                        "source_semantics": {
                            k: v for k, v in nodes[edge["source"]].items() if k != "id"
                        },
                        "target_semantics": {
                            k: v for k, v in nodes[edge["target"]].items() if k != "id"
                        },
                        "this_count": own[signature],
                        "other_count": other[signature],
                    }
                )
        result.update(status=DIFFERENT, retained_differences=rows)
        result["finite_search"].update(
            completed=True, proof="complete_retained_directed_edge_label_inventory_incompatibility"
        )
        return result
    domains = {
        a: sorted(b for b, rn in rnodes.items() if _node_key(ln) == _node_key(rn))
        for a, ln in lnodes.items()
    }
    le, re = _edge_counter(left), _edge_counter(right)
    pair_left: dict[Any, Counter] = defaultdict(Counter)
    pair_right: dict[Any, Counter] = defaultdict(Counter)
    for (a, b, attrs), count in le.items():
        pair_left[(a, b)][attrs] = count
    for (a, b, attrs), count in re.items():
        pair_right[(a, b)][attrs] = count
    degree = Counter(e["source"] for e in left["edges"]) + Counter(
        e["target"] for e in left["edges"]
    )
    order = sorted(lnodes, key=lambda a: (len(domains[a]), -degree[a], a))
    states, exhausted = 0, False
    rejection_witnesses: list[dict[str, Any]] = []

    def search(mapping: dict[str, str], used: set[str]) -> dict[str, str] | None:
        nonlocal states, exhausted
        if len(mapping) == len(order):
            return dict(mapping)
        a = order[len(mapping)]
        for b in domains[a]:
            if b in used:
                continue
            if states >= max_search_states:
                exhausted = True
                return None
            states += 1
            extension = {**mapping, a: b}
            incompatible = next(
                (
                    (u, v)
                    for u, v in [(a, a)] + [(a, x) for x in mapping] + [(x, a) for x in mapping]
                    if pair_left[(u, v)] != pair_right[(extension[u], extension[v])]
                ),
                None,
            )
            if incompatible:
                u, v = incompatible
                rejection_witnesses.append(
                    {
                        "partial_mapping": extension,
                        "incompatible_left_endpoints": [u, v],
                        "incompatible_right_endpoints": [extension[u], extension[v]],
                        "left_edges": [
                            dict(e) for e in left["edges"] if e["source"] == u and e["target"] == v
                        ],
                        "right_edges": [
                            dict(e)
                            for e in right["edges"]
                            if e["source"] == extension[u] and e["target"] == extension[v]
                        ],
                    }
                )
                continue
            found = search(extension, used | {b})
            if found is not None or exhausted:
                return found
        return None

    mapping = search({}, set())
    result["finite_search"].update(completed=not exhausted, states_examined=states)
    if exhausted:
        result["issues"] = [f"bounded node correspondence search unfinished at {states} states"]
        return result
    if mapping is None:
        result.update(
            status=DIFFERENT,
            retained_differences=[
                {
                    "kind": "completed_finite_directed_incidence_incompatibility",
                    "candidate_domains_preserving_all_node_attributes": domains,
                    "search_node_order": order,
                    "all_pruned_branch_edge_witnesses": rejection_witnesses,
                }
            ],
        )
        result["finite_search"]["proof"] = (
            "exhaustive_injective_assignment_with_concrete_edge_obstructions"
        )
        return result
    certificate = _certificate(left, right, mapping)
    if not all(
        certificate[field]
        for field in (
            "complete_node_bijection_verified",
            "all_node_attributes_verified",
            "all_directed_edges_forward_verified",
            "all_directed_edges_backward_verified",
        )
    ):
        result["issues"] = [
            "constructed correspondence failed complete bidirectional certificate verification"
        ]
        return result
    result.update(status=EQUIVALENT, correspondence=certificate)
    result["finite_search"]["proof"] = (
        "explicit_complete_bijection_and_bidirectional_edge_verification"
    )
    return result


def partition_task(
    pair_results: Sequence[Mapping[str, Any]], *, members: tuple[str, ...] = ("B", "A", "C")
) -> dict[str, Any]:
    """Only closed, consistent pair relations authorize a finite partition."""
    relation: dict[frozenset[str], str | None] = {}
    issues = []
    for row in pair_results:
        pair = frozenset((row["left_group"], row["right_group"]))
        if len(pair) != 2:
            issues.append("pair must contain two different candidate members")
        if pair in relation:
            issues.append("duplicate pair result")
        relation[pair] = row.get("status")
    domain_pairs = [frozenset((a, b)) for i, a in enumerate(members) for b in members[i + 1 :]]
    for pair in domain_pairs:
        if relation.get(pair) not in (EQUIVALENT, DIFFERENT):
            issues.append(f"unresolved or unadmitted pair: {sorted(pair)}")
    parents = {a: a for a in members}

    def representative(a: str) -> str:
        while parents[a] != a:
            a = parents[a]
        return a

    for pair in domain_pairs:
        if relation.get(pair) == EQUIVALENT:
            a, b = sorted(pair)
            parents[representative(b)] = representative(a)
    for pair in domain_pairs:
        a, b = sorted(pair)
        if relation.get(pair) == DIFFERENT and representative(a) == representative(b):
            issues.append(
                f"nontransitive relation contradicts retained-difference witness: {a}/{b}"
            )
    classes: dict[str, list[str]] = defaultdict(list)
    for member in members:
        classes[representative(member)].append(member)
    closed = not issues
    return {
        "members": list(members),
        "complete": closed,
        "equivalence_relation_consistent": not any("nontransitive" in issue for issue in issues),
        "formal_semantic_class_count": len(classes) if closed else None,
        "classes": list(classes.values()) if closed else None,
        "issues": issues,
    }


def compare_family(
    graphs: Mapping[str, Mapping[str, Mapping[str, Any]]],
    *,
    max_search_states: int = DEFAULT_MAX_SEARCH_STATES,
) -> dict[str, Any]:
    """Evaluate only B-C, B-A and A-C within each of the two frozen tasks."""
    issues = []
    pairs = []
    partitions: list[dict[str, Any]] = []
    if set(graphs) != {"F1", "F2"}:
        issues.append("finite input domain must contain exactly F1 and F2")
    for fixture_id in ("F1", "F2"):
        task_graphs = graphs.get(fixture_id, {})
        if set(task_graphs) != {"B", "A", "C"}:
            issues.append(f"{fixture_id}: exactly B, A, C required")
            partitions.append(
                {
                    "fixture_id": fixture_id,
                    "complete": False,
                    "formal_semantic_class_count": None,
                    "classes": None,
                    "issues": ["incomplete candidate domain"],
                }
            )
            continue
        task_pairs = []
        for a, b in PAIR_ORDER:
            row = compare_graphs(
                task_graphs[a], task_graphs[b], max_search_states=max_search_states
            )
            row.update(
                fixture_id=fixture_id,
                left_group=a,
                right_group=b,
                left_role="scheduling_regression_control" if a == "C" else "primary",
                right_role="scheduling_regression_control" if b == "C" else "primary",
            )
            task_pairs.append(row)
        pairs.extend(task_pairs)
        complete = partition_task(task_pairs)
        primary = partition_task(task_pairs, members=("B", "A"))
        partitions.append(
            {
                "fixture_id": fixture_id,
                "task_key": task_graphs["B"].get("task_key"),
                "primary": primary,
                "all_candidates_with_control": complete,
                "control": {
                    "group": "C",
                    "role": "scheduling_regression_control",
                    "independent_strategy_witness": False,
                },
                "formal_semantic_class_count": primary["formal_semantic_class_count"],
                "complete": complete["complete"],
            }
        )
    if (
        len(graphs) == 2
        and all("B" in graphs.get(f, {}) for f in ("F1", "F2"))
        and graphs["F1"]["B"].get("task_key") == graphs["F2"]["B"].get("task_key")
    ):
        issues.append("F1 and F2 must bind two distinct frozen task identities")
    closed = not issues and len(pairs) == 6 and all(p["complete"] for p in partitions)
    if issues:
        for partition in partitions:
            partition["formal_semantic_class_count"] = None
    return {
        "schema": "finite_public_behavior_family_comparison.v1",
        "pairs": pairs,
        "partitions": partitions,
        "same_task_unordered_pair_count": len(pairs),
        "comparison_closed": closed,
        "issues": issues,
        "cross_task_pairs": 0,
        "class_counts_are_per_task_only": True,
        "primary_groups": ["B", "A"],
        "control_group": "C",
    }
