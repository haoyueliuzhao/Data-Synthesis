from __future__ import annotations

from finraw.qa.comparability import comparability_policy
from finraw.qa.scope_matchers import (
    match_industry_filter_rank,
    match_industry_multi_factor,
    match_industry_rank_lookup,
)


def _fact(
    entity_id: str,
    metric_id: str,
    value: int,
    year: int,
) -> dict:
    return {
        "fact_id": f"fact_{entity_id}_{metric_id}_{year}",
        "entity_id": entity_id,
        "entity_scope_id": entity_id,
        "financial_scope_type": "consolidated_entity",
        "metric_id": metric_id,
        "normalized_value": str(value),
        "normalized_unit": "million",
        "normalized_currency": "USD",
        "source_definition_id": f"sec_{metric_id}",
    }


def _scope_fixture() -> dict:
    growth_values = [20, 18, 12, 8, 2]
    margin_values = [30, 25, 20, 10, 5]
    debt_values = [40, 55, 65, 75, 85]
    current = {}
    previous = {}
    for index, entity_id in enumerate(["A", "B", "C", "D", "E"]):
        current_revenue = 100 + growth_values[index]
        current[entity_id] = {
            "revenue": _fact(entity_id, "revenue", current_revenue, 2023),
            "net_income": _fact(entity_id, "net_income", margin_values[index], 2023),
            "total_assets": _fact(entity_id, "total_assets", 200, 2023),
            "total_liabilities": _fact(
                entity_id, "total_liabilities", debt_values[index] * 2, 2023
            ),
        }
        previous[entity_id] = {"revenue": _fact(entity_id, "revenue", 100, 2022)}
    return {
        ("Technology", 2022, "sec_companyfacts", "million", "USD"): previous,
        ("Technology", 2023, "sec_companyfacts", "million", "USD"): current,
    }


def _policy() -> dict:
    return comparability_policy(
        {
            "scope_min_entities": 3,
            "scope_top_ks": [3, 5],
            "growth_thresholds_pct": [0, 10],
            "debt_ratio_thresholds_pct": [50, 70, 90],
            "max_per_stratum": 10,
        }
    )


def test_complex_scope_scenarios_expand_without_weakening_scope(
    monkeypatch,
) -> None:
    scopes = _scope_fixture()
    monkeypatch.setattr(
        "finraw.qa.scope_matchers._scope_financial_groups",
        lambda db, kg, policy: scopes,
    )
    policy = _policy()

    filter_rank = match_industry_filter_rank(None, {}, 100, policy)
    rank_lookup = match_industry_rank_lookup(None, {}, 100, policy)
    multi_factor = match_industry_multi_factor(None, {}, 100, policy)

    filter_scenarios = {
        (
            row["operator_step_params"]["growth_filter"]["value"],
            row["operator_step_params"]["answer"]["top_k"],
        )
        for row in filter_rank
    }
    assert filter_scenarios == {("0", 3), ("0", 5), ("10", 3)}
    assert {
        row["operator_step_params"]["rank_revenue"]["top_k"] for row in rank_lookup
    } == {3, 5}
    assert len(multi_factor) >= 2

    for row in filter_rank + rank_lookup + multi_factor:
        assert row["entity_ids"] == ["A", "B", "C", "D", "E"]
        assert row["financial_scope"]["entity_scope_ids"] == row["entity_ids"]
        assert "complete-case universe" in row["scope_definition"]


def test_complex_scenario_policy_keeps_scalar_backwards_compatibility() -> None:
    policy = comparability_policy(
        {
            "scope_top_k": 4,
            "growth_threshold_pct": 7,
            "debt_ratio_max_pct": 65,
        }
    )
    assert policy["scope_top_ks"] == (4,)
    assert policy["growth_thresholds_pct"] == ("7",)
    assert policy["debt_ratio_thresholds_pct"] == ("65",)
