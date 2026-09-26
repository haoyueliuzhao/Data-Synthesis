"""Synthetic regression for explicit original-header localization only."""

from copy import deepcopy

import cross_market_financial_header_revision_20260926 as m
import pytest


def example():
    candidate = dict(
        _period_source_page=1,
        page_number=1,
        source_field_name="Revenue",
        period_start="2024-01-01",
        period_end="2024-12-31",
        column_index=3,
        _raw_value_text="120",
        extraction_metadata=dict(
            statement_title="CONSOLIDATED INCOME STATEMENT",
            period_inference="explicit_statement_header",
        ),
    )
    pages = {
        1: "Report 2024\nCONSOLIDATED INCOME\nSTATEMENT\nFor the year ended 31 December 2024\n"
        "Notes\n2024\n2023\nHK$ million\nRevenue\n6\n120\n100\nCost of sales\n(80)\n(70)"
    }
    table = dict(
        raw_table_json=dict(
            rows=[["Revenue"]],
            periods=[
                dict(fiscal_year=y, period_start=f"{y}-01-01", period_end=f"{y}-12-31")
                for y in (2024, 2023)
            ],
        )
    )
    return candidate, pages, table


def test_fallback_table_has_no_header_but_original_statement_does():
    c, p, t = example()
    result = m.statement_header(c, p, t)
    assert result["printed_year_columns"] == ["2024", "2023"]
    assert "Revenue" not in result["original_header_text"]
    assert m.annual_period(c, p, t)["start"] == "2024-01-01"
    assert m.row_column_certificate(c, p, t)["aligned_amounts"] == ["120", "100"]


def test_late_same_page_statement_header_not_five_row_cutoff():
    c, p, t = example()
    p[1] = "Balance sheet continuation\nCapital 10\nReserves 20\n" * 8 + p[1]
    result = m.statement_header(c, p, t)
    assert result["title_start_line_1based"] > 20


def test_continuation_candidate_uses_explicit_bound_period_page():
    c, p, t = example()
    c["page_number"] = 2
    p[2] = "Revenue\n6\n120\n100\nCost of sales\n(80)\n(70)"
    assert m.row_column_certificate(c, p, t)["aligned_amounts"] == ["120", "100"]


def test_original_table_and_candidate_unchanged():
    c, p, t = example()
    original = deepcopy((c, p, t))
    m.annual_period(c, p, t)
    m.row_column_certificate(c, p, t)
    assert (c, p, t) == original


@pytest.mark.parametrize(
    "mode",
    [
        "missing_columns",
        "only_body_year",
        "another_statement",
        "reversed_columns",
        "third_column",
        "subcolumns",
        "duplicate_title",
    ],
)
def test_no_inference_from_wrong_or_ambiguous_year(mode):
    c, p, t = example()
    if mode == "missing_columns":
        p[1] = p[1].replace("2024\n2023\n", "")
    elif mode == "only_body_year":
        p[1] = p[1].replace("2024\n2023\n", "") + "\n2024\n2023"
    elif mode == "another_statement":
        p[1] = p[1].replace("2024\n2023\n", "") + "\nParent company income statement\n2024\n2023"
    elif mode == "reversed_columns":
        p[1] = p[1].replace("2024\n2023\n", "2023\n2024\n")
    elif mode == "third_column":
        p[1] = p[1].replace("2024\n2023\n", "2024\n2023\n2022\n")
    elif mode == "subcolumns":
        p[1] = p[1].replace(
            "HK$ million", "Results before biological fair value adjustments\nTotal\nHK$ million"
        )
    else:
        p[1] += "\nCONSOLIDATED INCOME STATEMENT\n2024\n2023\nRevenue\n20\n10"
    with pytest.raises(ValueError):
        m.statement_header(c, p, t)


def test_chinese_explicit_printed_columns_with_earlier_other_statement():
    c, p, t = example()
    c["extraction_metadata"]["statement_title"] = "合并利润表"
    p[1] = (
        "资产负债表续页\n未分配利润\n500\n400\n合并利润表\n2024年1—12月\n单位元币种人民币\n项目\n附注\n2024年度\n2023年度\n一、营业总收入\n120\n100"
    )
    assert m.statement_header(c, p, t)["printed_year_columns"] == ["2024", "2023"]


def test_old_fixed_pass_helpers_and_roots_untouched():
    assert m.RAW != m.old.RAW
    namespace = m.helpers()
    assert namespace["financial_fact"] is not m.old.financial_fact
    assert namespace["annual_period"] is m.annual_period
    assert m.old.financial_fact.__globals__["annual_period"] is m.old.annual_period


@pytest.mark.parametrize("numbers", ["6\n1\n2\n3\n4\n120\n100", "1\n2\n3\n4\n120\n100"])
def test_six_money_subcolumns_never_take_rightmost_two(numbers):
    c, p, t = example()
    p[1] = p[1].replace("6\n120\n100", numbers)
    with pytest.raises(ValueError, match="subcolumns"):
        m.row_column_certificate(c, p, t)


def test_extra_numeric_token_without_notes_column_not_silently_discarded():
    c, p, t = example()
    p[1] = p[1].replace("Notes\n", "")
    with pytest.raises(ValueError, match="not_certified_note"):
        m.row_column_certificate(c, p, t)


def test_note_not_recognized_by_small_amount_heuristic():
    c, p, t = example()
    p[1] = p[1].replace("6\n120\n100", "0.6\n120\n100")
    with pytest.raises(ValueError, match="not_certified_note"):
        m.row_column_certificate(c, p, t)


def test_no_notes_column_needed_when_exactly_two_money_tokens():
    c, p, t = example()
    p[1] = p[1].replace("Notes\n", "").replace("6\n120\n100", "120\n100")
    result = m.row_column_certificate(c, p, t)
    assert not result["explicit_note_column"]
    assert result["aligned_amounts"] == ["120", "100"]


@pytest.mark.parametrize(
    "switch", ["Parent company income statement", "母公司利润表", "Consolidated balance sheet"]
)
def test_continuation_target_cannot_cross_statement_scope(switch):
    c, p, t = example()
    c["page_number"] = 2
    p[2] = switch + "\n2024\n2023\nRevenue\n6\n120\n100\nOther\n1"
    with pytest.raises(ValueError, match="scope_crossed"):
        m.row_column_certificate(c, p, t)


def test_earlier_parent_on_header_page_does_not_poison_later_consolidated_statement():
    c, p, t = example()
    p[1] = "母公司利润表\n2024\n2023\n收入\n999\n998\n" + p[1]
    assert m.row_column_certificate(c, p, t)["original_statement_scope_interval"][
        "no_intervening_statement_scope_switch"
    ]


def test_same_page_parent_statement_after_header_before_target_rejected():
    c, p, t = example()
    p[1] = p[1].replace("Revenue\n", "Parent company income statement\nRevenue\n")
    with pytest.raises(ValueError, match="scope_crossed"):
        m.row_column_certificate(c, p, t)


def test_explicitly_continued_same_header_is_recorded():
    c, p, t = example()
    c["page_number"] = 2
    p[2] = "CONSOLIDATED INCOME STATEMENT (continued)\nRevenue\n6\n120\n100\nOther\n1"
    result = m.row_column_certificate(c, p, t)
    assert len(result["original_statement_scope_interval"]["explicitly_continued_headers"]) == 1


def test_repeated_same_title_without_explicit_continued_not_assumed_same_statement():
    c, p, t = example()
    c["page_number"] = 2
    p[2] = "CONSOLIDATED INCOME STATEMENT\nRevenue\n6\n120\n100\nOther\n1"
    with pytest.raises(ValueError, match="without_explicit_continuation"):
        m.row_column_certificate(c, p, t)


def test_separate_full_chinese_date_columns_preserved_for_cash_distractors():
    c, p, t = example()
    c["period_start"] = None
    c["extraction_metadata"]["statement_title"] = "合并资产负债表"
    for period in t["raw_table_json"]["periods"]:
        period["period_start"] = None
    p[1] = (
        "合并资产负债表\n项目\n附注\n2024年12月31日\n2023年12月31日\n单位人民币元\nRevenue\n6\n120\n100"
    )
    assert m.statement_header(c, p, t)["printed_year_columns"] == ["2024", "2023"]
    assert m.instant_period(c, p, t)["end"] == "2024-12-31"


def test_full_date_column_must_match_registered_actual_end_not_merely_year():
    c, p, t = example()
    p[1] = p[1].replace("2024\n2023\n", "2024年6月30日\n2023年12月31日\n")
    with pytest.raises(ValueError, match="not_registered_period_end"):
        m.statement_header(c, p, t)
