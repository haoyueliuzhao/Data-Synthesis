"""Finite exact graph correspondence and explicit retained-semantic discrepancies."""

from __future__ import annotations

import itertools
import math
from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any

from .models import (
    DIFFERENT,
    EQUIVALENT,
    UNDETERMINED,
    MeasurementError,
    record,
    require,
    structural_key,
)


def _label(node: Mapping[str, Any]) -> dict[str, Any]:
    return {"kind": node["kind"], "semantics": node["semantics"]}


def canonical_graph(graph: Mapping[str, Any], limit: int = 4096) -> dict[str, Any]:
    """Enumerate all within-label permutations, bounded before enumeration.

    Graph keys do not appear in the selected representation. Hashes never decide
    equality, and exceeding this finite domain is undetermined, not different.
    """
    require(set(graph) == {"nodes", "edges"}, "comparison.graph_fields")
    nodes, edges = graph["nodes"], graph["edges"]
    by_key = {node["key"]: node for node in nodes}
    require(len(by_key) == len(nodes) and len(nodes) > 0, "comparison.node_identity")
    groups: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    for node in nodes:
        require(
            set(node) == {"key", "kind", "semantics"} and isinstance(node["key"], str),
            "comparison.node_fields",
        )
        groups[structural_key(_label(node))].append(node["key"])
    for edge in edges:
        require(
            set(edge) == {"source", "target", "role"}
            and isinstance(edge["role"], str)
            and edge["source"] in by_key
            and edge["target"] in by_key,
            "comparison.edge_fields",
        )
    ordered_groups = [groups[key] for key in sorted(groups)]
    permutation_count = math.prod(math.factorial(len(group)) for group in ordered_groups)
    require(permutation_count <= limit, "comparison.finite_permutation_bound")
    best_key: tuple[Any, ...] | None = None
    best: dict[str, Any] | None = None
    best_order: list[str] = []
    for choices in itertools.product(*(itertools.permutations(group) for group in ordered_groups)):
        order = [key for group in choices for key in group]
        positions = {key: i for i, key in enumerate(order)}
        representation = {
            "nodes": [_label(by_key[key]) for key in order],
            "edges": sorted(
                (
                    {
                        "source": positions[edge["source"]],
                        "target": positions[edge["target"]],
                        "role": edge["role"],
                    }
                    for edge in edges
                ),
                key=structural_key,
            ),
        }
        key = structural_key(representation)
        if best_key is None or key < best_key:
            best_key, best, best_order = key, representation, order
    assert best is not None
    return {"graph": best, "node_order": best_order, "permutations": permutation_count}


def _multiset_rows(
    values: list[dict[str, Any]],
) -> tuple[Counter[tuple[Any, ...]], dict[tuple[Any, ...], dict[str, Any]]]:
    by_key = {structural_key(value): value for value in values}
    return Counter(structural_key(value) for value in values), by_key


def _difference(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any] | None:
    """Show actual typed label/edge facts, never just a graph digest or size."""
    for kind in ("node_semantic_multiset", "edge_semantic_multiset"):

        def facts(graph: Mapping[str, Any], fact_kind: str = kind) -> list[dict[str, Any]]:
            by_key = {node["key"]: _label(node) for node in graph["nodes"]}
            if fact_kind == "node_semantic_multiset":
                return list(by_key.values())
            return [
                {
                    "source": by_key[edge["source"]],
                    "target": by_key[edge["target"]],
                    "role": edge["role"],
                }
                for edge in graph["edges"]
            ]

        lc, lv = _multiset_rows(facts(left))
        rc, rv = _multiset_rows(facts(right))
        if lc != rc:
            return {
                "kind": kind,
                "left_only": [
                    {**lv[key], "multiplicity": count} for key, count in sorted((lc - rc).items())
                ],
                "right_only": [
                    {**rv[key], "multiplicity": count} for key, count in sorted((rc - lc).items())
                ],
                "authority": (
                    "explicit retained source/operation/proposition/typed dependency facts"
                ),
                "graph_hash_or_node_count_is_authority": False,
            }
    return None


def compare_projections(
    left: Mapping[str, Any], right: Mapping[str, Any], rules: Mapping[str, Any]
) -> dict[str, Any]:
    relation, reason = UNDETERMINED, "projection not completely mapped or fixed conditions differ"
    bijection: list[dict[str, str]] = []
    witness = None
    search: dict[str, int | None] = {"left_permutations": None, "right_permutations": None}
    if (
        left["status"] == right["status"] == "mapped"
        and left["condition"] == right["condition"]
        and left["measurement_contract_id"] == right["measurement_contract_id"] == rules["id"]
    ):
        try:
            lc = canonical_graph(left["graph"], rules["canonical_permutation_limit"])
            rc = canonical_graph(right["graph"], rules["canonical_permutation_limit"])
            search = {
                "left_permutations": lc["permutations"],
                "right_permutations": rc["permutations"],
            }
            if structural_key(lc["graph"]) == structural_key(rc["graph"]):
                relation, reason = (
                    EQUIVALENT,
                    "complete semantic-label and typed-edge preserving bijection",
                )
                bijection = [
                    {"left": left_key, "right": right_key}
                    for left_key, right_key in zip(lc["node_order"], rc["node_order"], strict=True)
                ]
            else:
                witness = _difference(left["graph"], right["graph"])
                if witness is not None:
                    relation, reason = (
                        DIFFERENT,
                        "actual retained semantic node or edge facts differ",
                    )
                else:
                    reason = (
                        "canonical graphs differ but this finite discrepancy vocabulary "
                        "has no certificate"
                    )
        except (MeasurementError, KeyError, TypeError, IndexError) as error:
            reason = getattr(error, "code", "comparison.unsupported_graph")
    return record(
        "pair",
        left_session_id=left["session_id"],
        right_session_id=right["session_id"],
        left_projection_id=left["id"],
        right_projection_id=right["id"],
        measurement_contract_id=rules["id"],
        relation=relation,
        reason=reason,
        bijection=bijection,
        difference_witness=witness,
        canonical_search=search,
    )


def compare_all(
    projections: list[dict[str, Any]], rules: Mapping[str, Any]
) -> list[dict[str, Any]]:
    candidates = [
        projection for projection in projections if projection["status"] != "not_qualified"
    ]
    return [
        compare_projections(left, right, rules)
        for left, right in itertools.combinations(candidates, 2)
    ]
