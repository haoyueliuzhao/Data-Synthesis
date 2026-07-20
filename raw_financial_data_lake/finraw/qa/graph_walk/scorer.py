from __future__ import annotations


def score_query_graph(
    *,
    support_rate: float,
    financial_value: float,
    answerability: float,
    novelty: float,
    diversity: float,
    estimated_cost: float,
    ambiguity: float,
    weights: dict[str, float] | None = None,
) -> float:
    w = {
        "support": 0.2,
        "financial": 0.25,
        "answerability": 0.2,
        "novelty": 0.1,
        "diversity": 0.1,
        "cost": 0.1,
        "ambiguity": 0.05,
        **dict(weights or {}),
    }
    bounded_cost = min(max(estimated_cost, 0.0) / 1000.0, 1.0)
    score = (
        w["support"] * support_rate
        + w["financial"] * financial_value
        + w["answerability"] * answerability
        + w["novelty"] * novelty
        + w["diversity"] * diversity
        - w["cost"] * bounded_cost
        - w["ambiguity"] * ambiguity
    )
    return round(min(max(score, 0.0), 1.0), 6)
