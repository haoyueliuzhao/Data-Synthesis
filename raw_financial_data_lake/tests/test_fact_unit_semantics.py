from decimal import Decimal

from finraw.fact_standardization import _normalize_unit
from finraw.metric_ontology import FRED_ALIASES


def test_exchange_rate_is_not_scaled_as_usd_currency() -> None:
    value, unit, currency, scale = _normalize_unit(
        Decimal("28.0949916666667"),
        {"unit": "LCU/USD", "currency": "USD"},
        {
            "metric_id": "official_exchange_rate_lcu_per_usd",
            "default_unit": "LCU/USD",
            "default_currency": None,
        },
    )

    assert value == Decimal("28.0949916666667")
    assert unit == "LCU/USD"
    assert currency is None
    assert scale == "reported_rate"


def test_walcl_uses_concise_canonical_metric() -> None:
    assert FRED_ALIASES["WALCL"] == "federal_reserve_total_assets"
