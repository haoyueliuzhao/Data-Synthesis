from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from finraw.entity_normalization import _add_official_china_entities
from finraw.fact_standardization import _time_basis
from finraw.official_facts import _sse_inputs, _szse_inputs


def _row(source_id: str, record_key: str, entity_hint: str) -> dict[str, object]:
    return {
        "source_id": source_id,
        "record_key": record_key,
        "entity_hint": entity_hint,
        "raw_object_id": f"raw_{record_key}",
        "source_publish_date": "2026-01-01",
        "retrieval_time": "2026-07-23T00:00:00Z",
    }


class _FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def get_text(self) -> str:
        return self.text


class _FakeDocument:
    def __init__(self, text: str) -> None:
        self.pages = [_FakePage("") for _ in range(7)]
        self.pages[6] = _FakePage(text)

    def __len__(self) -> int:
        return len(self.pages)

    def __getitem__(self, index: int) -> _FakePage:
        return self.pages[index]

    def __enter__(self) -> "_FakeDocument":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_sse_monthly_market_overview_is_parsed_atomically(monkeypatch: pytest.MonkeyPatch) -> None:
    text = """
    Number of Listed Companies 2037 2017
    Number of Listed Securities 26989 26530
    Total Market Capitalization (100 Million RMB Yuan) 519698 506720
    Total Market Capitalization Negotiable (100 Million RMB Yuan) 435466 420157
    Total Turnover in Value (100 Million RMB Yuan) 483473 454309
    Weighted Average P/E Ratio 18.02 17.63
    """
    monkeypatch.setitem(sys.modules, "fitz", SimpleNamespace(open=lambda _path: _FakeDocument(text)))

    facts = list(
        _sse_inputs(
            _row("sse_market_statistics", "sse_monthly_statistics_2021_12", "SSE_MARKET"),
            Path("unused.pdf"),
        )
    )

    assert len(facts) == 6
    by_metric = {fact["metric_id"]: fact for fact in facts}
    assert by_metric["listed_company_count"]["value"] == Decimal("2037")
    assert by_metric["market_capitalization"]["value"] == Decimal("519698")
    assert by_metric["market_turnover_value"]["period_start"] == "2021-12-01"
    assert by_metric["market_capitalization"]["period_start"] == "2021-12-31"
    assert by_metric["market_average_pe_ratio"]["unit"] == "ratio"


def test_sse_missing_required_label_rejects_the_whole_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        sys.modules,
        "fitz",
        SimpleNamespace(open=lambda _path: _FakeDocument("Number of Listed Companies 2037")),
    )

    with pytest.raises(ValueError, match="required exchange statistic label"):
        list(
            _sse_inputs(
                _row("sse_market_statistics", "sse_monthly_statistics_2021_12", "SSE_MARKET"),
                Path("unused.pdf"),
            )
        )


def test_szse_monthly_market_overview_preserves_source_units(tmp_path: Path) -> None:
    path = tmp_path / "szse.html"
    path.write_text(
        """
        <html><body>
        No. of Listed Companies 2875
        No. of Listed Securities 21460
        Total Market Capitalization (RMB Mil.) 41325012.86
        Total Negotiable Market Capitalization (RMB Mil.) 35642393.55
        Total Turnover (RMB Mil.) 36891737.64
        Average P/E Ratio at End of Month (Times) 30.40
        </body></html>
        """,
        encoding="utf-8",
    )

    facts = list(
        _szse_inputs(
            _row("szse_market_statistics", "szse_monthly_statistics_2025_08", "SZSE_MARKET"),
            path,
        )
    )

    assert len(facts) == 6
    by_metric = {fact["metric_id"]: fact for fact in facts}
    assert by_metric["market_capitalization"]["value"] == Decimal("41325012.86")
    assert by_metric["market_capitalization"]["unit"] == "million CNY"
    assert by_metric["market_turnover_value"]["period_start"] == "2025-08-01"
    assert by_metric["listed_security_count"]["value"] == Decimal("21460")


def test_official_market_and_index_source_entities_become_canonical() -> None:
    source_entities = [
        {
            "source_id": "safe_official_statistics",
            "source_code": "CNY_FX_MARKET",
            "source_name": "China Foreign Exchange Market",
            "raw_metadata": {"kind": "market"},
        },
        {
            "source_id": "sse_market_statistics",
            "source_code": "SSE_MARKET",
            "source_name": "Shanghai Stock Exchange Market",
            "raw_metadata": {"kind": "market"},
        },
        {
            "source_id": "bse_market_statistics",
            "source_code": "899050",
            "source_name": "BSE 50 Index",
            "raw_metadata": {"kind": "index"},
        },
    ]
    entities: dict[str, dict[str, object]] = {}
    aliases: dict[str, dict[str, object]] = {}

    _add_official_china_entities(entities, aliases, source_entities)

    assert entities["CNY_FX_MARKET"]["entity_type"] == "market"
    assert entities["SSE_MARKET"]["exchange"] == "SSE"
    assert entities["BSE_50_INDEX"]["entity_type"] == "index"
    assert any(
        alias["entity_id"] == "BSE_50_INDEX"
        and alias["source_id"] == "bse_market_statistics"
        and alias["source_code"] == "899050"
        for alias in aliases.values()
    )



def test_official_time_basis_distinguishes_positions_from_flows() -> None:
    assert _time_basis(
        {"source_id": "sse_market_statistics"},
        {"period_type": "point_in_time"},
    ) == "calendar_point_in_time"
    assert _time_basis(
        {"source_id": "sse_market_statistics"},
        {"period_type": "period_flow"},
    ) == "calendar_period"
