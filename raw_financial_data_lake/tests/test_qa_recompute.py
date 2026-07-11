from decimal import Decimal

from finraw.qa.pipeline import _answers_match, _recompute, _scope_is_complete


def _fact(fact_id, value, year, metric="revenue"):
    return {
        "fact_id": fact_id,
        "normalized_value": value,
        "normalized_unit": "million USD",
        "normalized_currency": "USD",
        "fiscal_year": year,
        "metric_id": metric,
        "entity_id": "AAPL_US",
    }


def test_independent_yoy_recompute():
    observed, _ = _recompute(
        "yoy_growth",
        [_fact("f1", "100", 2022), _fact("f2", "125", 2023)],
        {},
    )
    assert Decimal(observed["value"]) == Decimal("25")
    assert _answers_match(
        {"value": "25", "unit": "percent", "tolerance": "0.001"},
        observed,
        None,
    )


def test_independent_ratio_recompute():
    observed, _ = _recompute(
        "ratio",
        [
            _fact("f1", "20", 2023, "net_income"),
            _fact("f2", "100", 2023, "revenue"),
        ],
        {"metric_scope": {"numerator": "net_income", "denominator": "revenue"}},
    )
    assert Decimal(observed["value"]) == Decimal("20")


def test_screening_result_set_is_not_a_complete_universe():
    semantics = {
        "scope_type": "screening_result_set",
        "entity_ids": ["AAPL_US", "MSFT_US"],
    }
    assert not _scope_is_complete("multi_condition_screening", semantics, 2)
