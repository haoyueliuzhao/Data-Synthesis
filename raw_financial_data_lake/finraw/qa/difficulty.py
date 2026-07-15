from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from finraw.qa.plans import operation_cost, operation_depth


DIFFICULTY_ORDER = ("easy", "medium", "hard", "expert", "research")


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
    hop_depth, branch_count = _graph_shape(edge_rows)
    return {
        "fact_count": len(set(source_fact_ids)),
        "derived_fact_count": len(set(source_derived_ids)),
        "entity_count": len(set(entity_ids)),
        "metric_count": len(set(metric_ids)),
        "period_count": len(periods),
        "source_count": len(sources),
        "node_count": len(evidence.get("evidence_node_ids") or evidence.get("node_ids") or []),
        "edge_count": len(evidence.get("edge_ids") or edge_rows),
        "graph_hop_depth": hop_depth,
        "branch_count": branch_count,
        "operation_count": len((operation_plan or {}).get("operators") or []),
        "operation_depth": operation_depth(operation_plan or {}),
        "operation_cost": operation_cost(operation_plan or {}),
        "scope_size": len(set(entity_ids)),
        "time_span_years": years[-1] - years[0] if len(years) > 1 else 0,
        "answer_cardinality": answer_cardinality,
    }


def difficulty_score(features: dict[str, Any]) -> float:
    score = 0.0
    score += min(float(features.get("fact_count", 0)), 20.0) * 0.35
    score += min(float(features.get("derived_fact_count", 0)), 5.0) * 0.7
    score += max(float(features.get("entity_count", 0)) - 1.0, 0.0) * 0.8
    score += max(float(features.get("metric_count", 0)) - 1.0, 0.0) * 0.9
    score += max(float(features.get("period_count", 0)) - 1.0, 0.0) * 0.35
    score += float(features.get("graph_hop_depth", 0)) * 0.3
    score += min(float(features.get("branch_count", 0)), 10.0) * 0.2
    score += float(features.get("operation_cost", 0))
    score += max(float(features.get("operation_depth", 0)) - 1.0, 0.0) * 1.2
    score += max(float(features.get("answer_cardinality", 0)) - 1.0, 0.0) * 0.15
    score += max(float(features.get("source_count", 0)) - 1.0, 0.0) * 0.5
    return round(score, 3)


def difficulty_level(score: float) -> str:
    if score < 2.5:
        return "easy"
    if score < 5.5:
        return "medium"
    if score < 9.5:
        return "hard"
    if score < 15.0:
        return "expert"
    return "research"


def assess_difficulty(features: dict[str, Any]) -> tuple[str, float]:
    score = difficulty_score(features)
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
