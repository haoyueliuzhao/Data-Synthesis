from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Any

from finraw.qa.plans import operation_cost, operation_depth


DIFFICULTY_ORDER = ("easy", "medium", "hard", "expert", "research")
DIFFICULTY_BASE_COST = {
    "easy": 0.0,
    "medium": 1.0,
    "hard": 2.0,
    "expert": 4.0,
    "research": 6.0,
}
DIFFICULTY_POLICY = {
    "version": 2,
    "thresholds": {"easy": 2.5, "medium": 5.5, "hard": 9.5, "expert": 18.0},
    "pattern_base_cost": DIFFICULTY_BASE_COST,
    "reasoning_relations": [
        "HAS_FACT",
        "MEASURES",
        "IN_PERIOD",
        "DERIVED_FROM",
        "ABOUT_ENTITY",
        "USES_METRIC",
        "HAS_SCOPE",
        "CONTAINS_ENTITY",
        "BELONGS_TO_YEAR",
        "BELONGS_TO_MONTH",
        "FISCAL_YEAR_OF",
    ],
    "provenance_relations": [
        "FROM_SOURCE",
        "TRACED_TO",
        "USES_SOURCE_DEFINITION",
    ],
}


def graph_features(
    *,
    source_fact_ids: list[str],
    source_derived_ids: list[str],
    entity_ids: list[str],
    metric_ids: list[str],
    facts: list[dict[str, Any]],
    evidence: dict[str, Any],
    operation_plan: dict[str, Any] | None,
    answer_payload: dict[str, Any],
) -> dict[str, Any]:
    edge_rows = evidence.get("evidence_edges") or []
    periods = {
        str(
            fact.get("period_end")
            or fact.get("fiscal_year")
            or fact.get("calendar_year")
            or ""
        )
        for fact in facts
        if fact.get("period_end") or fact.get("fiscal_year") or fact.get("calendar_year")
    }
    years = sorted(
        {
            int(year)
            for fact in facts
            for year in [fact.get("fiscal_year") or fact.get("calendar_year")]
            if year is not None
        }
    )
    sources = {str(fact.get("source_id")) for fact in facts if fact.get("source_id")}
    answer_cardinality = len(answer_payload.get("table") or answer_payload.get("rows") or [])
    if not answer_cardinality and answer_payload:
        answer_cardinality = 1
    reasoning_relations = set(DIFFICULTY_POLICY["reasoning_relations"])
    provenance_relations = set(DIFFICULTY_POLICY["provenance_relations"])
    reasoning_edges = [
        edge
        for edge in edge_rows
        if str(edge.get("relation_type") or edge.get("relation") or "")
        in reasoning_relations
    ]
    provenance_edges = [
        edge
        for edge in edge_rows
        if str(edge.get("relation_type") or edge.get("relation") or "")
        in provenance_relations
    ]
    reasoning_depth, reasoning_branches = _graph_shape(reasoning_edges)
    provenance_depth, provenance_branches = _graph_shape(provenance_edges)
    full_depth, full_branches = _graph_shape(edge_rows)
    return {
        "fact_count": len(set(source_fact_ids)),
        "derived_fact_count": len(set(source_derived_ids)),
        "entity_count": len(set(entity_ids)),
        "metric_count": len(set(metric_ids)),
        "period_count": len(periods),
        "source_count": len(sources),
        "node_count": len(evidence.get("evidence_node_ids") or evidence.get("node_ids") or []),
        "edge_count": len(evidence.get("edge_ids") or edge_rows),
        "graph_hop_depth": full_depth,
        "branch_count": full_branches,
        "reasoning_graph_hop_depth": reasoning_depth,
        "reasoning_branch_count": reasoning_branches,
        "provenance_graph_depth": provenance_depth,
        "provenance_branch_count": provenance_branches,
        "operation_count": len((operation_plan or {}).get("operators") or []),
        "operation_depth": operation_depth(operation_plan or {}),
        "operation_cost": operation_cost(operation_plan or {}),
        "scope_size": len(set(entity_ids)),
        "time_span_years": years[-1] - years[0] if len(years) > 1 else 0,
        "answer_cardinality": answer_cardinality,
    }


def difficulty_score(
    features: dict[str, Any], difficulty_base: str | None = None
) -> float:
    score = DIFFICULTY_BASE_COST.get(str(difficulty_base or "easy"), 0.0)
    score += min(float(features.get("fact_count", 0)), 10.0) * 0.25
    score += min(float(features.get("derived_fact_count", 0)), 5.0) * 0.5
    score += max(float(features.get("entity_count", 0)) - 1.0, 0.0) * 0.6
    score += max(float(features.get("metric_count", 0)) - 1.0, 0.0) * 0.6
    score += min(max(float(features.get("period_count", 0)) - 1.0, 0.0), 4.0) * 0.2
    score += float(features.get("reasoning_graph_hop_depth", 0)) * 0.15
    score += min(float(features.get("reasoning_branch_count", 0)), 5.0) * 0.08
    score += float(features.get("provenance_graph_depth", 0)) * 0.03
    score += float(features.get("operation_cost", 0))
    score += max(float(features.get("operation_depth", 0)) - 1.0, 0.0) * 1.4
    score += min(float(features.get("time_span_years", 0)), 10.0) * 0.08
    scope_size = max(float(features.get("scope_size", 0)), 1.0)
    score += math.log2(scope_size) * 0.2
    score += min(float(features.get("node_count", 0)), 100.0) * 0.003
    score += min(float(features.get("edge_count", 0)), 150.0) * 0.003
    score += max(float(features.get("answer_cardinality", 0)) - 1.0, 0.0) * 0.1
    score += max(float(features.get("source_count", 0)) - 1.0, 0.0) * 0.5
    return round(score, 3)


def difficulty_level(score: float) -> str:
    thresholds = DIFFICULTY_POLICY["thresholds"]
    if score < thresholds["easy"]:
        return "easy"
    if score < thresholds["medium"]:
        return "medium"
    if score < thresholds["hard"]:
        return "hard"
    if score < thresholds["expert"]:
        return "expert"
    return "research"


def assess_difficulty(
    features: dict[str, Any], difficulty_base: str | None = None
) -> tuple[str, float]:
    score = difficulty_score(features, difficulty_base)
    return difficulty_level(score), score


def _graph_shape(edges: list[dict[str, Any]]) -> tuple[int, int]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        src = str(edge.get("src_node_id") or edge.get("src") or "")
        dst = str(edge.get("dst_node_id") or edge.get("dst") or "")
        if not src or not dst:
            continue
        adjacency[src].add(dst)
        adjacency[dst].add(src)
    branch_count = sum(1 for neighbors in adjacency.values() if len(neighbors) > 2)
    max_depth = 0
    for start in adjacency:
        distances = {start: 0}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for neighbor in adjacency[node]:
                if neighbor in distances:
                    continue
                distances[neighbor] = distances[node] + 1
                queue.append(neighbor)
        max_depth = max(max_depth, max(distances.values(), default=0))
    return max_depth, branch_count
