from __future__ import annotations

from decimal import Decimal

import pytest

from finraw.atomic_facts import refresh_atomic_facts
from finraw.metric_ontology import CNINFO_STRICT_ALIASES, HKEX_STRICT_ALIASES
from finraw.cn_financial_statements import (
    _apply_accounting_identity_checks,
    _apply_cross_checks,
    _configured_entity_hints,
    _configured_object_urls,
    _direct_periods_for_statement_page,
    _is_non_target_statement_boundary,
    _is_terminal_statement_boundary,
    _inferred_statement_identity,
    _logical_table_rows,
    _matched_metric_alias,
    _missing_positioned_fallback_rows,
    _periods_for_statement,
    _positioned_numeric_values,
    _positioned_metric_values,
    _section_unit_info,
    _statement_identity,
    _statement_boundary_top_from_words,
    _table_numeric_values,
    _unit_info,
)
from finraw.db.client import MetadataDB
from finraw.fact_standardization import _normalize_unit


def _candidate(
    metric_id: str,
    value: str,
    *,
    raw_object_id: str = "raw_1",
    period_end: str = "2023-12-31",
) -> dict:
    return {
        "raw_object_id": raw_object_id,
        "entity_id": "CN_000001",
        "matched_metric_id": metric_id,
        "value": value,
        "unit": "million CNY",
        "currency": "CNY",
        "period_end": period_end,
        "financial_scope_type": "consolidated_entity",
        "evidence_status": "verified",
        "candidate_state": "evidence_verified",
        "promotion_status": "not_promoted",
        "review_status": "cn_pdf_programmatic_verified",
        "state_reason": "verified",
        "extraction_metadata": {"validation_errors": []},
        "_validation_errors": [],
    }


def test_positioned_words_recover_split_table_values() -> None:
    words = [
        {"text": "负债合计", "x0": 68.0, "top": 393.1},
        {"text": "4,886,834", "x0": 384.5, "top": 394.0},
        {"text": "4,525,932", "x0": 482.5, "top": 394.0},
    ]
    values = _positioned_numeric_values(words, "负债合计", 2)

    assert values == [
        (1, "4,886,834", Decimal("4886834")),
        (2, "4,525,932", Decimal("4525932")),
    ]


def test_positioned_words_recover_bounded_multiline_primary_label() -> None:
    words = [
        {"text": "本公司擁有人應佔權益", "x0": 68.0, "top": 100.0},
        {"text": "Equity attributable to owners of", "x0": 68.0, "top": 112.0},
        {"text": "the Company", "x0": 68.0, "top": 124.0},
        {"text": "40", "x0": 330.0, "top": 124.0},
        {"text": "264,867,183", "x0": 390.0, "top": 124.0},
        {"text": "244,047,069", "x0": 480.0, "top": 124.0},
    ]

    values = _positioned_numeric_values(
        words,
        "equityattributabletoownersofthecompany",
        2,
    )

    assert values == [
        (2, "264,867,183", Decimal("264867183")),
        (3, "244,047,069", Decimal("244047069")),
    ]


def test_positioned_values_do_not_bind_total_to_noncurrent_liabilities() -> None:
    words = [
        {"text": "非流动负债合计", "x0": 90.0, "top": 100.0},
        {"text": "12,485,016.11", "x0": 360.0, "top": 100.0},
        {"text": "14,090,576.75", "x0": 450.0, "top": 100.0},
        {"text": "负债合计", "x0": 110.0, "top": 120.0},
        {"text": "149,845,006.11", "x0": 360.0, "top": 120.0},
        {"text": "123,042,270.56", "x0": 450.0, "top": 120.0},
    ]

    values = _positioned_numeric_values(words, "负债合计", 2)

    assert [str(item[2]) for item in values] == [
        "149845006.11",
        "123042270.56",
    ]


def test_positioned_metric_values_prefer_specific_registered_alias() -> None:
    words = [
        {"text": "一、营业总收入", "x0": 70.0, "top": 100.0},
        {"text": "7,423,597,248.19", "x0": 350.0, "top": 100.0},
        {"text": "6,430,868,267.12", "x0": 440.0, "top": 100.0},
        {"text": "其中：营业收入", "x0": 70.0, "top": 120.0},
        {"text": "7,423,597,248.19", "x0": 350.0, "top": 120.0},
        {"text": "6,430,868,267.12", "x0": 440.0, "top": 120.0},
    ]

    source_field_name, values = _positioned_metric_values(
        words,
        "营业收入",
        "revenue",
        {
            "营业收入": "revenue",
            "营业总收入": "revenue",
        },
        2,
    )

    assert source_field_name == "营业总收入"
    assert [str(item[2]) for item in values] == [
        "7423597248.19",
        "6430868267.12",
    ]


def test_parser_scope_uses_only_frozen_source_company_codes() -> None:
    assert _configured_entity_hints(
        {
            "cninfo": {"stock_pool": [{"stock_code": "1"}]},
            "bse": {"announcements": [{"stock_code": "920001"}]},
            "hkex": {"announcements": [{"stock_code": "1"}]},
        },
        ("cninfo_announcements", "bse_disclosures", "hkex_disclosures"),
    ) == {
        "cninfo_announcements": {"000001"},
        "bse_disclosures": {"920001"},
        "hkex_disclosures": {"00001"},
    }
    assert _configured_object_urls(
        {
            "cninfo": {"announcements": [{"url": "https://cninfo/a.pdf"}]},
            "bse": {"announcements": [{"url": "https://bse/b.pdf"}]},
            "hkex": {"announcements": [{"url": "https://hkex/h.pdf"}]},
        },
        ("cninfo_announcements", "bse_disclosures", "hkex_disclosures"),
    ) == {
        "cninfo_announcements": {"https://cninfo/a.pdf"},
        "bse_disclosures": {"https://bse/b.pdf"},
        "hkex_disclosures": {"https://hkex/h.pdf"},
    }

def test_same_page_chinese_unit_is_explicit() -> None:
    assert _unit_info("(除特别注明外，金额单位均为人民币百万元)") == {
        "unit_header": "金额单位均为人民币百万元",
        "unit": "million CNY",
        "currency": "CNY",
        "value_scale": "百万元",
    }


def test_cninfo_standard_unit_header_is_eligible() -> None:
    assert _unit_info("编制单位：测试股份有限公司\n单位：元\n币种：人民币") == {
        "unit_header": "单位：元",
        "unit": "CNY",
        "currency": "CNY",
        "value_scale": "元",
    }
    assert _unit_info("(除特别注明外，金额单位为人民币千元)") == {
        "unit_header": "金额单位为人民币千元",
        "unit": "thousand CNY",
        "currency": "CNY",
        "value_scale": "千元",
    }


def test_split_currency_scale_columns_require_primary_statement_evidence() -> None:
    statement_text = (
        "中国石油化工股份有限公司\n"
        "合并资产负债表\n"
        "于2024年12月31日\n"
        "附注\n"
        "2024年\n2023年\n"
        "人民币\n人民币\n百万元\n百万元\n"
        "资产\n流动资产"
    )

    assert _unit_info(statement_text) == {
        "unit_header": "人民币/百万元 comparative value columns",
        "unit": "million CNY",
        "currency": "CNY",
        "value_scale": "百万元",
    }
    assert _unit_info(statement_text.replace("附注\n", "")) is None



def test_chinese_monetary_scales_normalize_to_million_cny() -> None:
    metric = {"default_unit": "million CNY", "default_currency": "CNY"}
    cases = {
        "CNY": ("1000000", "1"),
        "thousand CNY": ("1000", "1"),
        "ten_thousand CNY": ("100", "1"),
        "million CNY": ("1", "1"),
        "hundred_million CNY": ("1", "100"),
        "billion CNY": ("1", "1000"),
    }

    for unit, (raw_value, expected) in cases.items():
        normalized, normalized_unit, currency, scale = _normalize_unit(
            Decimal(raw_value),
            {"unit": unit, "currency": "CNY"},
            metric,
        )
        assert normalized == Decimal(expected)
        assert normalized_unit == "million CNY"
        assert currency == "CNY"
        assert scale == "million"


def test_statement_identity_does_not_require_a_specific_unit_phrase() -> None:
    assert _statement_identity("合并利润表\n2023 年\n单位：元") == {
        "statement_title": "合并利润表",
        "statement_type": "income_statement",
        "value_column_policy": "rightmost_periods",
    }
    periods = _periods_for_statement(
        "合并利润表\n2023 年\n2022 年\n单位：元",
        "income_statement",
    )
    assert [row["fiscal_year"] for row in periods] == [2023, 2022]


def test_hkex_statement_identity_accepts_audited_pdf_text_extraction_variant() -> None:
    assert _statement_identity(
        "CONSOLIDATED STATEMENT OF PROFIT OR LOSS AND OTHER COMPREHENSI\n"
        "E INCOME",
        source_id="hkex_disclosures",
    ) == {
        "statement_title": (
            "CONSOLIDATED STATEMENT OF PROFIT OR LOSS AND OTHER "
            "COMPREHENSIE INCOME"
        ),
        "statement_type": "income_statement",
        "value_column_policy": "rightmost_periods",
    }


def test_cninfo_statement_title_can_follow_prior_statement_on_same_page() -> None:
    prior_rows = "\n".join(
        f"资产负债表续页项目{index}\n{index},000.00"
        for index in range(120)
    )

    identity = _statement_identity(
        f"{prior_rows}\n3、合并利润表\n单位：元\n项目\n"
        "2019 年度\n2018 年度"
    )

    assert identity == {
        "statement_title": "合并利润表",
        "statement_type": "income_statement",
        "value_column_policy": "rightmost_periods",
    }
    assert _statement_identity(
        f"{prior_rows}\n1、合并资产负债表\n单位：元\n项目\n"
        "2022 年12 月31 日\n2022 年1 月1 日"
    ) == {
        "statement_title": "合并资产负债表",
        "statement_type": "balance_sheet",
        "value_column_policy": "rightmost_periods",
    }
    assert _statement_identity(
        f"{prior_rows}\n合并利润表\n附注说明"
    ) is None


def test_audited_statement_amounts_presented_in_cny_scale() -> None:
    assert _unit_info(
        "(除另有标明外，所有金额均以人民币百万元列示)"
    ) == {
        "unit_header": "除另有标明外，所有金额均以人民币百万元列示",
        "unit": "million CNY",
        "currency": "CNY",
        "value_scale": "百万元",
    }


@pytest.mark.parametrize(
    ("heading", "statement_type"),
    [
        ("合并资产负债表和资产负债表", "balance_sheet"),
        ("合并利润表和利润表", "income_statement"),
        ("合并现金流量表和现金流量表", "cash_flow"),
        ("合并财务状况表和财务状况表", "balance_sheet"),
        ("合并及银行资产负债表", "balance_sheet"),
        ("合并及银行利润表", "income_statement"),
        ("合并及银行现金流量表", "cash_flow"),
    ],
)
def test_combined_audited_statement_uses_consolidated_columns(
    heading: str, statement_type: str
) -> None:
    assert _statement_identity(f"{heading}\n2024 年度\n2023 年度") == {
        "statement_title": heading,
        "statement_type": statement_type,
        "value_column_policy": "consolidated_first_pair",
    }


def test_dated_combined_balance_sheet_title_is_explicit() -> None:
    assert _statement_identity(
        "中国国际贸易中心股份有限公司\n"
        "2019年12月31日合并及公司资产负债表\n"
        "(除特别注明外，金额单位为人民币元)"
    ) == {
        "statement_title": "合并及公司资产负债表",
        "statement_type": "balance_sheet",
        "value_column_policy": "consolidated_first_pair",
    }


@pytest.mark.parametrize(
    ("heading", "statement_type"),
    [
        ("（一） 合并资产负债表", "balance_sheet"),
        ("（三） 合并利润表", "income_statement"),
        ("（五） 合并现金流量表", "cash_flow"),
        ("(1) 合并利润表", "income_statement"),
    ],
)
def test_bse_chapter_prefixed_consolidated_statement_title(
    heading: str, statement_type: str
) -> None:
    identity = _statement_identity(
        f"二、\n财务报表\n{heading}\n单位：元\n2024 年\n2023 年",
        source_id="bse_disclosures",
    )

    assert identity is not None
    assert identity["statement_type"] == statement_type


def test_bse_statement_title_can_follow_audit_report_on_same_page() -> None:
    audit_lines = "\n".join(f"审计程序说明第 {index} 项" for index in range(35))

    identity = _statement_identity(
        f"{audit_lines}\n（一） 合并资产负债表\n单位：元\n"
        "2024 年12 月31 日\n2023 年12 月31 日",
        source_id="bse_disclosures",
    )

    assert identity == {
        "statement_title": "合并资产负债表",
        "statement_type": "balance_sheet",
        "value_column_policy": "rightmost_periods",
    }


def test_hkex_statement_unit_and_non_december_fiscal_period_are_explicit() -> None:
    assert _statement_identity(
        "CONSOLIDATED STATEMENT OF FINANCIAL POSITION\n"
        "AS AT 31 MARCH 2025",
        source_id="hkex_disclosures",
    ) == {
        "statement_title": "CONSOLIDATED STATEMENT OF FINANCIAL POSITION",
        "statement_type": "balance_sheet",
        "value_column_policy": "rightmost_periods",
    }
    assert _unit_info(
        "Amounts expressed in HK$ million unless otherwise stated",
        source_id="hkex_disclosures",
    ) == {
        "unit_header": "Amounts expressed in HK$ million unless otherwise stated",
        "unit": "million HKD",
        "currency": "HKD",
        "value_scale": "million",
    }
    periods = _periods_for_statement(
        "CONSOLIDATED STATEMENT OF PROFIT OR LOSS\n"
        "FOR THE YEAR ENDED 31 MARCH 2025\n2025 2024",
        "income_statement",
        report_year=2025,
        source_id="hkex_disclosures",
    )
    assert [(row["period_start"], row["period_end"]) for row in periods] == [
        ("2024-04-01", "2025-03-31"),
        ("2023-04-01", "2024-03-31"),
    ]


def test_hkex_dual_currency_uses_rightmost_statement_value_currency() -> None:
    assert _unit_info(
        "US$ million\nNote\nHK$ million\nHK$ million",
        source_id="hkex_disclosures",
    ) == {
        "unit_header": "HK$ million",
        "unit": "million HKD",
        "currency": "HKD",
        "value_scale": "million",
    }


def test_hkex_information_only_currency_uses_primary_left_pair() -> None:
    assert _unit_info(
        "For information purpose only\n2023\nHK$ Million\n2022\n"
        "HK$ Million\n2023\nRMB Million\n2022\nRMB Million",
        source_id="hkex_disclosures",
    ) == {
        "unit_header": "HK$ Million",
        "unit": "million HKD",
        "currency": "HKD",
        "value_scale": "million",
        "value_column_policy": "consolidated_first_pair",
    }


def test_hkex_split_plural_title_and_shorthand_unit_are_explicit() -> None:
    assert _statement_identity(
        "Consolidated Statements of\nProfit or Loss\n2024\n2023",
        source_id="hkex_disclosures",
    ) == {
        "statement_title": "CONSOLIDATED STATEMENTS OF PROFIT OR LOSS",
        "statement_type": "income_statement",
        "value_column_policy": "rightmost_periods",
    }
    assert _unit_info(
        "Note\n2024\nHK$’M\n2023\nHK$’M",
        source_id="hkex_disclosures",
    ) == {
        "unit_header": "HK$’M",
        "unit": "million HKD",
        "currency": "HKD",
        "value_scale": "million",
    }


def test_hkex_headingless_statement_requires_same_type_metrics_and_audited_period() -> None:
    identity = _inferred_statement_identity(
        "Note\n2019\nHK$’M\n2018\nHK$’M\nRevenue\n"
        "Operating profit\nProfit for the year",
        {
            "revenue": "revenue",
            "operatingprofit": "operating_income",
            "profitfortheyear": "net_income",
        },
        {
            "revenue": "income_statement",
            "operating_income": "income_statement",
            "net_income": "income_statement",
        },
        source_id="hkex_disclosures",
    )
    assert identity == {
        "statement_title": "INFERRED CONSOLIDATED INCOME_STATEMENT",
        "statement_type": "income_statement",
        "value_column_policy": "rightmost_periods",
        "statement_identity_inferred": True,
    }
    periods = _periods_for_statement(
        "Note\n2019\nHK$’M\n2018\nHK$’M",
        "income_statement",
        report_year=2019,
        source_id="hkex_disclosures",
        fallback_period_end=__import__("datetime").date(2019, 12, 31),
    )
    assert [row["period_end"] for row in periods] == [
        "2019-12-31",
        "2018-12-31",
    ]
    assert periods[0]["period_inference"] == "audited_statement_section_period"


def test_hkex_split_label_and_left_translation_column_are_mapped() -> None:
    row = [
        "36,006",
        "",
        "Revenue",
        "",
        "4,5",
        "280,847",
        "266,396",
    ]
    assert _matched_metric_alias(row, {"revenue": "revenue"}) == (
        "revenue",
        "revenue",
    )
    words = [
        {"text": text, "x0": x0, "top": 100}
        for x0, text in enumerate(
            ("36,006", "Revenue", "4,", "5", "280,847", "266,396"),
            start=1,
        )
    ]
    values = _positioned_numeric_values(words, "revenue", 2)
    assert [str(item[2]) for item in values] == ["280847", "266396"]


def test_hkex_bilingual_chinese_prefix_maps_registered_english_label() -> None:
    aliases = {"revenue": "revenue"}

    assert _matched_metric_alias(
        ["收入", "Revenue", "5", "180,736,575", "250,565,107"],
        aliases,
    ) == ("revenue", "revenue")
    words = [
        {"text": text, "x0": x0, "top": 100.0}
        for x0, text in enumerate(
            ("收入", "Revenue", "5", "180,736,575", "250,565,107"),
            start=1,
        )
    ]

    values = _positioned_numeric_values(words, "revenue", 2)

    assert [str(item[2]) for item in values] == [
        "180736575",
        "250565107",
    ]


def test_primary_net_income_label_does_not_match_nearby_scopes() -> None:
    aliases = {"净利润": "net_income"}

    assert _matched_metric_alias(
        ["五、净利润（净亏损以‘－’号填列）", "40", "35"],
        aliases,
    ) == ("净利润", "net_income")
    assert _matched_metric_alias(
        ["、净利润（净亏损以‘－’号填列）", "40", "35"],
        aliases,
    ) == ("净利润", "net_income")
    assert _matched_metric_alias(
        ["1.持续经营净利润（净亏损以‘－’号填列）", "40", "35"],
        aliases,
    ) is None
    assert _matched_metric_alias(
        ["归属于母公司所有者的净利润", "38", "33"],
        aliases,
    ) is None


def test_wrapped_primary_net_income_row_is_reassembled_without_scope_drift() -> None:
    rows = [
        ["五、净利润（净亏损以“－”号填", "", ""],
        ["列）", "-571,026,003.30", "-824,475,261.49"],
        ["1.持续经营净利润（净亏损以", "", ""],
        ["“－”号填列）", "-571,026,003.30", "-824,475,261.49"],
    ]

    logical = _logical_table_rows(rows, 2)

    assert logical[0] == (
        0,
        [0, 1],
        [
            "五、净利润（净亏损以“－”号填列）",
            "-571,026,003.30",
            "-824,475,261.49",
        ],
    )
    assert _matched_metric_alias(logical[0][2], {"净利润": "net_income"}) == (
        "净利润",
        "net_income",
    )
    assert _matched_metric_alias(
        logical[2][2], {"净利润": "net_income"}
    ) is None
    values = _table_numeric_values(
        logical[0][2], 2, value_column_policy="rightmost_periods"
    )
    assert [value for _, _, value in values] == [
        Decimal("-571026003.30"),
        Decimal("-824475261.49"),
    ]


def test_split_english_primary_metric_label_is_reassembled_exactly() -> None:
    aliases = {"profitfortheyear": "net_income"}

    assert _matched_metric_alias(
        ["Profitforth", "eye", "ar", "11", "729,993", "1,124,935"],
        aliases,
    ) == ("profitfortheyear", "net_income")
    assert _matched_metric_alias(
        ["Profitforthe", "year", "attributable", "to:"], aliases
    ) is None


def test_hkex_bilingual_translation_does_not_change_metric_scope() -> None:
    aliases = {
        "profitfortheyear": "net_income",
        "totalassets": "total_assets",
    }

    assert _matched_metric_alias(
        ["Profitfortheye", "ar", "年度內溢利", "3,685", "3,336"],
        aliases,
    ) == ("profitfortheyear", "net_income")
    assert _matched_metric_alias(
        ["TotalAssets", "資產總額", "884,420", "865,198"], aliases
    ) == ("totalassets", "total_assets")
    assert _matched_metric_alias(
        [
            "Profitfortheye",
            "arbeforetaxation",
            "年度內除稅前溢利",
            "3,606",
            "3,198",
        ],
        aliases,
    ) is None


def test_greater_china_strict_aliases_include_only_primary_totals() -> None:
    assert "负债总计" in CNINFO_STRICT_ALIASES["total_liabilities"]
    assert "Profit after tax" in HKEX_STRICT_ALIASES["net_income"]
    assert (
        "Net cash from operating activities"
        in HKEX_STRICT_ALIASES[
            "net_cash_provided_by_used_in_operating_activities"
        ]
    )
    assert "Profit before tax" not in HKEX_STRICT_ALIASES["net_income"]
    assert (
        "Profit attributable to ordinary shareholders"
        not in HKEX_STRICT_ALIASES["net_income"]
    )


def test_hkex_strict_aliases_cover_audited_primary_statement_variants() -> None:
    assert "Operating revenue" in HKEX_STRICT_ALIASES["revenue"]
    assert "Net profit" in HKEX_STRICT_ALIASES["net_income"]
    assert "Net assets" in HKEX_STRICT_ALIASES["shareholders_equity"]
    assert "Shareholders' funds" in HKEX_STRICT_ALIASES["shareholders_equity"]
    assert (
        "Net cash inflow from operating activities"
        in HKEX_STRICT_ALIASES[
            "net_cash_provided_by_used_in_operating_activities"
        ]
    )
    assert (
        "Net cash flows used in investing activities"
        in HKEX_STRICT_ALIASES[
            "net_cash_provided_by_used_in_investing_activities"
        ]
    )


def test_hkex_row_normalization_handles_roman_prefix_and_curly_apostrophe() -> None:
    aliases = {
        "operatingrevenue": "revenue",
        "shareholders'funds": "shareholders_equity",
    }

    assert _matched_metric_alias(
        ["I. Operating revenue", "602,315,354", "424,060,635"],
        aliases,
    ) == ("operatingrevenue", "revenue")
    assert _matched_metric_alias(
        ["Shareholders’ funds", "102,331", "105,498"],
        aliases,
    ) == ("shareholders'funds", "shareholders_equity")


def test_chapter_prefixed_company_statement_closes_consolidated_section() -> None:
    text = "（四） 母公司利润表\n单位：元\n2024 年\n2023 年"

    assert _is_non_target_statement_boundary(
        text, source_id="bse_disclosures"
    )
    assert not _is_terminal_statement_boundary(
        text, source_id="bse_disclosures"
    )
    assert _is_terminal_statement_boundary(
        "财务报表附注\n一、公司基本情况",
        source_id="bse_disclosures",
    )
    assert not _is_terminal_statement_boundary(
        "后附的财务报表附注为本财务报表的组成部分。",
        source_id="bse_disclosures",
    )


def test_same_page_company_statement_boundary_returns_crop_position() -> None:
    words = [
        (60, 100, 130, 112, "负债合计", 1, 1, 0),
        (360, 100, 430, 112, "149,845,006.11", 1, 1, 1),
        (100, 500, 140, 512, "（二）", 2, 1, 0),
        (145, 500, 250, 512, "母公司资产负债表", 2, 1, 1),
    ]

    assert _statement_boundary_top_from_words(
        words, source_id="bse_disclosures"
    ) == 500.0


def test_hkex_company_only_statement_is_a_hard_boundary() -> None:
    assert _is_non_target_statement_boundary(
        "COMPANY STATEMENT OF FINANCIAL POSITION",
        source_id="hkex_disclosures",
    )


def test_period_parser_uses_statement_header_and_report_year() -> None:
    text = (
        "审计报告签署日：2025 年4 月19 日\n"
        "1、合并资产负债表\n"
        "2024 年12 月31 日\n"
        "2024 年1 月1 日\n"
    )
    periods = _periods_for_statement(
        text,
        "balance_sheet",
        report_year=2024,
    )
    assert [row["period_end"] for row in periods] == [
        "2024-12-31",
        "2024-01-01",
    ]
    assert [row["fiscal_year"] for row in periods] == [2024, 2023]

    adjustment = (
        "2020 年4 月20 日召开董事会\n"
        "合并资产负债表\n"
        "2019 年12 月31 日\n"
        "2020 年1 月1 日\n"
    )
    assert _periods_for_statement(
        adjustment,
        "balance_sheet",
        report_year=2020,
    ) == []

    relative_headers = (
        "2020 年12 月31 日\n"
        "合并资产负债表\n"
        "本年年末余额 上年年末余额\n"
    )
    relative_periods = _periods_for_statement(
        relative_headers,
        "balance_sheet",
        report_year=2020,
    )
    assert [row["period_end"] for row in relative_periods] == [
        "2020-12-31",
        "2019-12-31",
    ]
    assert relative_periods[1]["period_inference"] == (
        "explicit_relative_comparative_header"
    )

    opening_balance_periods = _periods_for_statement(
        "合并资产负债表\n期末余额 期初余额\n",
        "balance_sheet",
        report_year=2025,
    )
    assert [row["period_end"] for row in opening_balance_periods] == [
        "2025-12-31",
        "2024-12-31",
    ]
    assert all(
        row.get("period_inference")
        == "explicit_relative_comparative_header"
        for row in opening_balance_periods
    )


def test_continuation_page_reuses_explicit_comparative_periods() -> None:
    inherited_periods = [
        {"period_end": "2024-12-31", "fiscal_year": 2024},
        {"period_end": "2023-12-31", "fiscal_year": 2023},
    ]

    direct = _direct_periods_for_statement_page(
        "测试股份有限公司2024 年年度报告\n五、净利润",
        {
            "statement_type": "income_statement",
            "statement_inherited": True,
            "periods": inherited_periods,
        },
        report_year=2024,
        source_id="cninfo_announcements",
    )

    assert direct == []


def test_section_unit_and_combined_statement_layout_are_explicit() -> None:
    combined_units = (
        "财务附注中报表的单位为：千元\n"
        "1、合并资产负债表\n单位：元"
    )
    assert _section_unit_info(combined_units) == {
        "unit_header": "单位为：千元",
        "unit": "thousand CNY",
        "currency": "CNY",
        "value_scale": "千元",
    }
    assert _unit_info(combined_units) == {
        "unit_header": "单位：元",
        "unit": "CNY",
        "currency": "CNY",
        "value_scale": "元",
    }
    assert _section_unit_info(
        "二、财务报表\n财务附注中报表的单位为：千元"
    ) == {
        "unit_header": "单位为：千元",
        "unit": "thousand CNY",
        "currency": "CNY",
        "value_scale": "千元",
    }
    assert _statement_identity(
        "合并及公司资产负债表\n2023 年12 月31 日"
    ) == {
        "statement_title": "合并及公司资产负债表",
        "statement_type": "balance_sheet",
        "value_column_policy": "consolidated_first_pair",
    }


def test_combined_statement_selects_consolidated_value_pair() -> None:
    words = [
        {"text": "资产总计", "x0": 60.0, "top": 100.0},
        {"text": "1", "x0": 180.0, "top": 100.0},
        {"text": "100", "x0": 280.0, "top": 100.0},
        {"text": "90", "x0": 380.0, "top": 100.0},
        {"text": "60", "x0": 480.0, "top": 100.0},
        {"text": "50", "x0": 580.0, "top": 100.0},
    ]

    values = _positioned_numeric_values(
        words,
        "资产总计",
        2,
        value_column_policy="consolidated_first_pair",
    )

    assert values == [
        (2, "100", Decimal("100")),
        (3, "90", Decimal("90")),
    ]


def test_positioned_fallback_only_recovers_missing_statement_metrics() -> None:
    rows = _missing_positioned_fallback_rows(
        {
            "page_text": "合并及公司资产负债表\n存货\n资产总计\n营业收入",
            "statement_type": "balance_sheet",
            "periods": [
                {"period_end": "2023-12-31"},
                {"period_end": "2022-12-31"},
            ],
        },
        {
            "存货": "inventory",
            "资产总计": "total_assets",
            "营业收入": "revenue",
        },
        {
            "inventory": "balance_sheet",
            "total_assets": "balance_sheet",
            "revenue": "income_statement",
        },
        [
            {
                "matched_metric_id": "inventory",
                "period_end": "2023-12-31",
            },
            {
                "matched_metric_id": "inventory",
                "period_end": "2022-12-31",
            },
        ],
    )

    assert rows == [["资产总计"]]


def test_non_target_company_statement_stops_consolidated_carry() -> None:
    assert _is_non_target_statement_boundary(
        "5、公司资产负债表\n2023 年12 月31 日"
    )
    assert _is_non_target_statement_boundary("财务报表附注\n一、公司基本情况")
    assert not _is_non_target_statement_boundary(
        "后附财务报表附注为本财务报表的组成部分。"
    )
    assert not _is_non_target_statement_boundary(
        "合并及公司资产负债表\n2023 年12 月31 日"
    )
    assert _is_non_target_statement_boundary(
        ("合并利润表续页内容\n" * 40) + "4、母公司利润表\n单位：元"
    )
    assert _is_non_target_statement_boundary(
        "平安银行股份有限公司\n银行利润表(续)\n2024年度"
    )
    assert _is_non_target_statement_boundary(
        "平安银行股份有限公司\n银行现金流量表\n2024年度"
    )


def test_same_document_later_primary_statement_supersedes_summary() -> None:
    summary = _candidate("total_assets", "90")
    summary["page_number"] = 40
    primary = _candidate("total_assets", "100")
    primary["page_number"] = 160

    _apply_cross_checks([summary, primary], allow_single=True)

    assert summary["promotion_status"] == "rejected_superseded"
    assert summary["cross_check_status"] == (
        "superseded_same_document_summary"
    )
    assert primary["promotion_status"] == "approved_for_atomic_fact"
    assert primary["cross_check_status"] == "single_official_document"
    assert summary["extraction_metadata"][
        "same_document_selected_statement_page"
    ] == 160


def test_same_document_latest_primary_page_conflict_is_rejected() -> None:
    left = _candidate("total_assets", "100")
    left["page_number"] = 160
    right = _candidate("total_assets", "101")
    right["page_number"] = 160

    _apply_cross_checks([left, right], allow_single=True)

    assert all(row["promotion_status"] == "rejected_conflict" for row in [left, right])
    assert all(row["cross_check_status"] == "conflict" for row in [left, right])


def test_latest_official_restatement_supersedes_older_comparative() -> None:
    old = _candidate(
        "total_assets",
        "100",
        raw_object_id="raw_old",
        period_end="2022-12-31",
    )
    old["_source_publish_date"] = "2023-03-01"
    latest = _candidate(
        "total_assets",
        "105",
        raw_object_id="raw_latest",
        period_end="2022-12-31",
    )
    latest["_source_publish_date"] = "2024-03-01"

    _apply_cross_checks([old, latest], allow_single=True)

    assert old["promotion_status"] == "rejected_superseded"
    assert old["cross_check_status"] == "superseded_official_comparative"
    assert latest["promotion_status"] == "approved_for_atomic_fact"
    assert latest["cross_check_status"] == "latest_official_restated_value"
    assert latest["extraction_metadata"]["selected_official_value"] == "105"


def test_parent_attributable_equity_does_not_trigger_total_equity_identity() -> None:
    candidates = [
        _candidate("total_assets", "100"),
        _candidate("total_liabilities", "60"),
        _candidate("shareholders_equity", "35"),
    ]
    candidates[-1]["source_field_name"] = (
        "equityattributabletoownersofthecompany"
    )

    _apply_accounting_identity_checks(candidates)

    assert all(row["evidence_status"] == "verified" for row in candidates)
    assert all(row["promotion_status"] == "not_promoted" for row in candidates)


def test_accounting_identity_rejects_malformed_complete_triple() -> None:
    candidates = [
        _candidate("total_assets", "5321514"),
        _candidate("total_liabilities", "34"),
        _candidate("shareholders_equity", "80"),
    ]

    _apply_accounting_identity_checks(candidates)

    assert all(
        row["evidence_status"] == "failed_accounting_identity"
        for row in candidates
    )
    assert all(
        row["promotion_status"] == "rejected_evidence"
        for row in candidates
    )


def test_crosscheck_requires_distinct_official_documents() -> None:
    candidates = [
        _candidate("total_assets", "5321514", raw_object_id="raw_1"),
        _candidate("total_assets", "5321514", raw_object_id="raw_2"),
    ]

    _apply_cross_checks(candidates, allow_single=True)

    assert all(
        row["cross_check_status"] == "matched_official_comparative"
        for row in candidates
    )
    assert all(
        row["promotion_status"] == "approved_for_atomic_fact"
        for row in candidates
    )


@pytest.mark.parametrize(
    "source_id", ["cninfo_announcements", "bse_disclosures"]
)
def test_approved_candidate_is_promoted_by_atomic_fact_build(
    tmp_path, source_id: str
) -> None:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    db.seed_sources()
    db.execute(
        """
        INSERT INTO canonical_entities (
            entity_id, canonical_name, entity_type, market, country,
            currency, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        ["CN_000001", "测试股份", "company", "CN", "CN", "CNY"],
    )
    db.execute(
        """
        INSERT INTO metrics (
            metric_id, canonical_name, metric_category, statement_type,
            period_type, default_unit, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        [
            "total_assets",
            "Total Assets",
            "financial_statement",
            "balance_sheet",
            "point_in_time",
            "monetary",
        ],
    )
    db.insert_raw_object(
        {
            "raw_object_id": "raw_1",
            "source_id": source_id,
            "object_type": "pdf",
            "storage_uri": "/tmp/report.pdf",
            "original_url": "https://static.cninfo.com.cn/report.pdf",
            "content_sha256": "a" * 64,
            "content_size_bytes": 100,
            "source_publish_date": "2024-03-20",
            "validation_status": "passed",
        }
    )
    db.execute(
        """
        INSERT INTO candidate_facts (
            candidate_id, stable_candidate_id, build_id, is_active,
            raw_object_id, entity_id, metric_hint, value, unit,
            period_hint, period_end, fiscal_year, fiscal_quarter,
            currency, value_scale, source_field_name, statement_type,
            financial_scope_type, page_number, row_index, column_index,
            extraction_metadata, evidence_sha256, evidence_text,
            confidence_score, review_status, candidate_state,
            matched_metric_id, evidence_status, cross_check_status,
            promotion_status, qa_eligible, kg_eligible
        ) VALUES (
            ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0
        )
        """,
        [
            "candidate_1",
            "candidate_stable_1",
            "candidate_build_1",
            "raw_1",
            "CN_000001",
            "total_assets",
            "5321514",
            "million CNY",
            "2023-12-31",
            "2023-12-31",
            2023,
            "FY",
            "CNY",
            "百万元",
            "资产总计",
            "balance_sheet",
            "consolidated_entity",
            10,
            20,
            3,
            "{}",
            "evidence_hash",
            "合并资产负债表 | 资产总计 | 5,321,514",
            0.97,
            "cn_pdf_programmatic_verified",
            "evidence_verified",
            "total_assets",
            "verified",
            "single_official_document",
            "approved_for_atomic_fact",
        ],
    )
    db.execute(
        """
        INSERT INTO candidate_fact_evidence (
            evidence_id, candidate_id, build_id, raw_object_id,
            page_number, source_field_name, raw_value_text,
            evidence_sha256, verification_method, validation_status,
            validation_errors
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "evidence_1",
            "candidate_1",
            "candidate_build_1",
            "raw_1",
            10,
            "资产总计",
            "5,321,514",
            "evidence_hash",
            "pdfplumber_cells+pymupdf_text",
            "verified",
            "[]",
        ],
    )

    report = refresh_atomic_facts(db, {}, batch_size=10)

    assert report["promoted_document_candidate_count"] == 1
    fact = db.fetchone(
        """
        SELECT *
        FROM atomic_facts
        WHERE source_id = ?
          AND is_active = 1
        """,
        [source_id],
    )
    assert fact is not None
    assert fact["entity_id"] == "CN_000001"
    assert fact["metric_id"] == "total_assets"
    assert fact["value"] == 5321514
    candidate = db.fetchone(
        "SELECT promotion_status, promoted_fact_id FROM candidate_facts WHERE candidate_id = ?",
        ["candidate_1"],
    )
    assert candidate["promotion_status"] == "promoted"
    assert candidate["promoted_fact_id"] == fact["fact_id"]
    db.close()
