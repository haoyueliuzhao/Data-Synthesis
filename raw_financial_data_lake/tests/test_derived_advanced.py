from __future__ import annotations

from collections import Counter
from decimal import Decimal

from finraw.derived_facts import (
    _annual_rows,
    _iter_industry_rankings,
    _iter_long_window_returns,
    _iter_multi_condition_screening,
    _iter_multi_year_extrema,
    _iter_time_series_extrema,
)


def _row(year: int, value: str, metric: str = "revenue", entity: str = "A_US") -> dict:
    return {
        "fact_id": f"{entity}:{metric}:{year}",
        "entity_id": entity,
        "metric_id": metric,
        "source_id": "sec_companyfacts",
        "normalized_unit": "million",
        "normalized_currency": "USD",
        "value_decimal": Decimal(value),
        "normalized_value": Decimal(value),
        "period_end": f"{year}-12-31",
        "calendar_year": year,
        "fiscal_year": year,
        "fiscal_quarter": "FY",
        "time_basis": "fiscal_period",
        "verification_status": "single_source",
        "confidence_score": 1.0,
        "industry": "Software",
        "metric_category": "financial_statement",
        "frequency": "annual",
        "is_forecast": False,
    }


def test_multi_year_extrema_use_complete_windows() -> None:
    report = {"skipped_counts": Counter()}
    annual = _annual_rows([_row(year, str(year)) for year in range(2015, 2025)], report)
    facts = list(_iter_multi_year_extrema(annual, report, [5, 10]))
    assert {fact["derived_type"] for fact in facts} == {
        "multi_year_argmax",
        "multi_year_argmin",
    }
    assert len(facts) == 4
    assert {fact["time_scope"]["window_years"] for fact in facts} == {5, 10}


def test_frequency_aware_extrema_and_long_window_return() -> None:
    report = {"skipped_counts": Counter()}
    rows = []
    for month in range(1, 13):
        row = _row(2024, str(month), metric="consumer_price_index", entity="USA_COUNTRY")
        row.update(
            {
                "fact_id": f"cpi:{month}",
                "source_id": "fred_observations",
                "period_end": f"2024-{month:02d}-01",
                "frequency": "monthly",
                "metric_category": "macro",
            }
        )
        rows.append(row)
    facts = list(_iter_time_series_extrema(rows, report, {"monthly": 12}))
    assert {fact["derived_type"] for fact in facts} == {
        "macro_time_series_argmax",
        "macro_time_series_argmin",
        "rolling_max",
        "rolling_min",
    }

    index_rows = []
    for year in range(2014, 2025):
        row = _row(year, str(100 + year - 2014), metric="broad_us_dollar_index", entity="USD_INDEX")
        row.update(
            {
                "fact_id": f"dollar:{year}",
                "source_id": "fred_observations",
                "period_end": f"{year}-12-31",
                "frequency": "daily",
                "metric_category": "market",
            }
        )
        index_rows.append(row)
    returns = list(_iter_long_window_returns(index_rows, report, [1, 5, 10]))
    assert len(returns) == 3
    assert all(fact["derived_type"] == "long_window_return" for fact in returns)


def test_industry_ranking_and_multi_condition_screening_have_explicit_scopes() -> None:
    report = {"skipped_counts": Counter()}
    rows = [
        _row(2023, "100", entity="A_US"),
        _row(2024, "120", entity="A_US"),
        _row(2024, "10", metric="net_income", entity="A_US"),
        _row(2023, "100", entity="B_US"),
        _row(2024, "90", entity="B_US"),
        _row(2024, "20", metric="net_income", entity="B_US"),
    ]
    annual = _annual_rows(rows, report)
    rankings = list(_iter_industry_rankings(annual, report))
    assert {fact["derived_type"] for fact in rankings} == {
        "industry_ranking",
        "industry_argmax",
        "industry_argmin",
    }
    assert all(fact["scope_type"] == "industry_universe" for fact in rankings)

    screening = list(
        _iter_multi_condition_screening(
            annual,
            report,
            {"sec_us_100": ["A_US", "B_US"]},
        )
    )
    assert len(screening) == 1
    assert screening[0]["derived_type"] == "multi_condition_screening"
    assert screening[0]["scope_id"].endswith("_2024")
    assert screening[0]["output_table"][0]["entity_id"] == "A_US"


def test_forecasts_do_not_enter_historical_annual_derivations() -> None:
    report = {"skipped_counts": Counter()}
    forecast = _row(2027, "150")
    forecast["is_forecast"] = True
    assert _annual_rows([forecast], report) == []
    assert report["skipped_counts"]["forecast_input"] == 1
