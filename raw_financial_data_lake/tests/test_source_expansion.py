from __future__ import annotations

import pytest

from finraw import bse_discovery
from finraw import hkex_discovery
from finraw import cninfo_discovery
from finraw.cn_market_universe import (
    _stratified_select,
    _validate_annual_report_coverage,
)
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


def test_cninfo_strategy_resolves_org_id_from_official_announcement_search(monkeypatch):
    class Response:
        status = 200

        @staticmethod
        def json():
            return [
                    {"code": "000002", "orgId": "gssz0000002", "delisted": "false"},
                    {"code": "000020", "orgId": "wrong", "delisted": False},
                ]

    observed: list[dict[str, str]] = []
    monkeypatch.setattr(
        cninfo_discovery,
        "post_form",
        lambda *args, **_: observed.append(args[1]) or Response(),
    )
    monkeypatch.setattr(
        cninfo_discovery,
        "discover_cninfo_announcements",
        lambda **kwargs: observed.append(kwargs) or [],
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
    assert observed[0]["keyWord"] == "000002"
    assert observed[1]["stock"] == "000002,gssz0000002"
    assert observed[1]["market"] == "SZSE"


def test_cninfo_sse_discovery_uses_sse_column(monkeypatch):
    class Response:
        status = 200

        @staticmethod
        def json():
            return {"announcements": [], "hasMore": False}

    observed: list[dict[str, str]] = []
    monkeypatch.setattr(
        cninfo_discovery,
        "post_form",
        lambda *args, **_: observed.append(args[1]) or Response(),
    )

    assert cninfo_discovery.discover_cninfo_announcements(
        stock="600519,gssh0600519",
        market="SSE",
        start_date="2020-01-01",
        end_date="2025-12-31",
    ) == []
    assert observed[0]["column"] == "sse"


def test_cninfo_report_year_prefers_title_and_uses_publish_year_fallback():
    assert cninfo_discovery._infer_year(
        {"announcementTitle": "测试公司2025年度报告"}, "annual"
    ) == "2025"
    assert cninfo_discovery._infer_year(
        {
            "announcementTitle": "测试公司年报全文",
            "announcementTime": "2025-04-01",
        },
        "annual",
    ) == "2024"
    assert cninfo_discovery._infer_year(
        {
            "announcementTitle": "测试公司2023年年报",
            "announcementTime": "2024-04-01",
        },
        "annual",
    ) == "2023"


def test_cninfo_selector_resolution_fails_closed_without_exact_code(monkeypatch):
    class Response:
        status = 200

        @staticmethod
        def json():
            return {
                "announcements": [
                    {"secCode": "600518", "orgId": "gssh0600518"},
                ]
            }

    def post_form(url, *_, **__):
        if url == cninfo_discovery.CNINFO_TOP_SEARCH_URL:
            class EmptyResponse:
                status = 200

                @staticmethod
                def json():
                    return []

            return EmptyResponse()
        return Response()

    monkeypatch.setattr(cninfo_discovery, "post_form", post_form)

    try:
        cninfo_discovery.resolve_cninfo_stock_selectors(
            [{"stock_code": "600519", "market": "SSE"}]
        )
    except ValueError as exc:
        assert "SSE:600519" in str(exc)
    else:
        raise AssertionError("Expected exact-code selector resolution to fail closed")


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


def test_bse_company_directory_and_annual_report_discovery():
    class Response:
        status_code = 200

        def __init__(self, text: str):
            self.text = text

    class Session:
        def post(self, url, data, *, referer):
            if url == bse_discovery.BSE_COMPANY_URL:
                return Response(
                    'cb([{"content":[{"xxzqdm":"920001","xxzqjc":"纬达光电",'
                    '"fxssrq":"20221227","xxhyzl":"计算机、通信和其他电子设备制造业",'
                    '"xxssdq":"广东省"}],"totalPages":1}])'
                )
            assert ("disclosureSubtype[]", "9503-1001") in data
            assert ("disclosureSubtype[]", "9503-1005") in data
            return Response(
                'null([{"listInfo":{"content":[{"companyCd":"920001",'
                '"companyName":"纬达光电","disclosureTitle":"[定期报告]纬达光电:'
                '2024年年度报告","disclosurePostTitle":"","destFilePath":'
                '"/disclosure/2025/report.pdf","publishDate":"2025-04-10",'
                '"fileExt":"pdf"}],"totalPages":1}}])'
            )

    client = Session()
    companies = bse_discovery.discover_bse_companies(session=client)
    reports = bse_discovery.discover_bse_announcements(
        stock_code="920001",
        start_date="2020-01-01",
        end_date="2025-12-31",
        session=client,
    )

    assert companies[0]["market"] == "BSE"
    assert companies[0]["listing_date"] == "2022-12-27"
    assert reports[0]["year"] == "2024"
    assert reports[0]["url"] == "https://www.bse.cn/disclosure/2025/report.pdf"


def test_a_share_stratified_selection_excludes_st_and_round_robins():
    rows = [
        {"stock_code": "1", "company_name": "A1", "industry_code": "A"},
        {"stock_code": "2", "company_name": "A2", "industry_code": "A"},
        {"stock_code": "3", "company_name": "B1", "industry_code": "B"},
        {"stock_code": "4", "company_name": "*ST B2", "industry_code": "B"},
        {"stock_code": "5", "company_name": "C1", "industry_code": "C"},
        {"stock_code": "6", "company_name": "C2退", "industry_code": "C"},
    ]

    selected = _stratified_select(rows, 4)

    assert [row["stock_code"] for row in selected] == ["1", "3", "5", "2"]


def test_expansion_profile_coverage_fails_closed_below_five_years():
    source_config = {
        "selection_policy": {"minimum_annual_years": 5},
        "stock_pool": [{"stock_code": "920001"}],
        "announcements": [
            {"stock_code": "920001", "year": str(year)}
            for year in range(2022, 2025)
        ],
    }

    with pytest.raises(ValueError, match="below 5 years"):
        _validate_annual_report_coverage("bse", source_config)


def test_hkex_active_registry_requires_exact_official_codes():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"i": 7609, "c": "00700", "n": "TENCENT", "s": "HK0000057808"},
                {"i": 42, "c": "00005", "n": "HSBC HOLDINGS", "s": "GB0005405286"},
            ]

    class Session:
        def get(self, url, *, headers, timeout):
            assert url == hkex_discovery.HKEX_ACTIVE_STOCK_URL
            return Response()

    codes = ("00700", "00005") + tuple(f"9{index:04d}" for index in range(28))
    with pytest.raises(ValueError, match="not active"):
        hkex_discovery.discover_hkex_active_companies(
            requested_count=30,
            codes=codes,
            session=Session(),
        )


def test_hkex_annual_report_discovery_filters_exact_company_and_category():
    html = """
    <table>
      <tr><td>15/04/2025 12:00</td><td>00700</td><td>TENCENT</td>
      <td><div class='headline'>[Annual Report]</div>
      <a href='/listedco/listconews/sehk/2025/0415/report2024.pdf'>Annual Report 2024</a></td></tr>
      <tr><td>15/04/2025 12:00</td><td>00005</td><td>HSBC</td>
      <td><div class='headline'>[Annual Report]</div>
      <a href='/listedco/listconews/sehk/2025/0415/other2024.pdf'>Annual Report 2024</a></td></tr>
    </table>
    """

    class Response:
        text = html

        def raise_for_status(self):
            return None

    class Session:
        def post(self, url, *, data, headers, timeout):
            assert data["stockId"] == "7609"
            return Response()

    rows = hkex_discovery.discover_hkex_annual_reports(
        company={
            "stock_code": "00700",
            "company_name": "TENCENT",
            "hkex_stock_id": 7609,
        },
        start_date="2020-01-01",
        end_date="2025-12-31",
        session=Session(),
    )

    assert len(rows) == 1
    assert rows[0]["year"] == "2024"
    assert rows[0]["publish_date"] == "2025-04-15"
    assert rows[0]["url"].endswith("report2024.pdf")


def test_hkex_pool_size_is_constrained():
    with pytest.raises(ValueError, match="30 to 50"):
        hkex_discovery.discover_hkex_active_companies(requested_count=29)


def test_hkex_split_fiscal_year_uses_period_end_year():
    assert hkex_discovery._report_year("Annual Report 2024/2025", "2025-06-16") == (
        "2025",
        "fiscal_year_range_end",
    )
    assert hkex_discovery._report_year("Annual Report 2024/25", "2025-06-16") == (
        "2025",
        "fiscal_year_range_end",
    )
