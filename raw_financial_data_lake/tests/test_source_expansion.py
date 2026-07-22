from __future__ import annotations

from finraw import cninfo_discovery
from finraw.connectors.fred import FredConnector
from finraw.connectors.sec_filings import SecFilingsConnector


def test_sec_filing_selection_applies_independent_form_limits():
    filings = [
        {"form": "8-K", "accessionNumber": "8k-1"},
        {"form": "8-K", "accessionNumber": "8k-2"},
        {"form": "10-Q", "accessionNumber": "10q-1"},
        {"form": "10-K", "accessionNumber": "10k-1"},
        {"form": "10-Q", "accessionNumber": "10q-2"},
        {"form": "10-K", "accessionNumber": "10k-2"},
    ]

    selected = SecFilingsConnector._select_filings(
        filings,
        {"10-K", "10-Q", "8-K"},
        limit_per_company=2,
        limits_by_form={"10-K": 2, "10-Q": 1, "8-K": 1},
    )

    assert [item["accessionNumber"] for item in selected] == [
        "8k-1",
        "10q-1",
        "10k-1",
        "10k-2",
    ]


def test_cninfo_strategy_excludes_titles_and_deduplicates(monkeypatch):
    discovered = [
        {
            "announcement_id": "annual",
            "title": "2024年年度报告",
            "url": "https://example.test/annual.pdf",
        },
        {
            "announcement_id": "summary",
            "title": "2024年年度报告摘要",
            "url": "https://example.test/summary.pdf",
        },
        {
            "announcement_id": "annual",
            "title": "2024年年度报告",
            "url": "https://example.test/annual.pdf",
        },
    ]
    monkeypatch.setattr(
        cninfo_discovery,
        "discover_cninfo_announcements",
        lambda **_: list(discovered),
    )
    strategy = {
        "cninfo": {
            "stock_pool": [
                {
                    "stock_code": "000001",
                    "selector": "000001,gssz0000001",
                    "company_name": "测试公司",
                }
            ],
            "categories": ["annual"],
            "start_date": "2019-01-01",
            "end_date": "2025-12-31",
            "selection_policy": {"exclude_title_keywords": ["摘要"]},
        }
    }

    rows = cninfo_discovery.discover_cninfo_from_strategy(strategy)

    assert len(rows) == 1
    assert rows[0]["announcement_id"] == "annual"
    assert rows[0]["pool_metadata"]["stock_code"] == "000001"


def test_cninfo_strategy_resolves_org_id_from_official_registry(monkeypatch):
    class Response:
        status = 200

        @staticmethod
        def json():
            return {
                "stockList": [
                    {"code": "000002", "orgId": "gssz0000002"},
                ]
            }

    observed: list[str] = []
    monkeypatch.setattr(cninfo_discovery, "get_url", lambda *_, **__: Response())
    monkeypatch.setattr(
        cninfo_discovery,
        "discover_cninfo_announcements",
        lambda **kwargs: observed.append(kwargs["stock"]) or [],
    )
    strategy = {
        "cninfo": {
            "stock_pool": [
                {"stock_code": "000002", "company_name": "万科A", "market": "SZSE"}
            ],
            "categories": ["annual"],
            "start_date": "2019-01-01",
            "end_date": "2025-12-31",
        }
    }

    assert cninfo_discovery.discover_cninfo_from_strategy(strategy) == []
    assert observed == ["000002,gssz0000002"]


def test_fred_profile_excludes_series_without_vintage_endpoint():
    connector = object.__new__(FredConnector)
    connector.config = {
        "fred": {
            "series_ids": ["SP500", "GDP"],
            "vintage_excluded_series": ["SP500"],
        }
    }

    excluded = set(connector.config["fred"]["vintage_excluded_series"])
    assert "SP500" in excluded
    assert "GDP" not in excluded
