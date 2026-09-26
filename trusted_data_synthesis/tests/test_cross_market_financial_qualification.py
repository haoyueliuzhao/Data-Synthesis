"""Pure synthetic source semantics; no real PDF, models, or network."""

from copy import deepcopy
from decimal import Decimal

import cross_market_financial_qualification_20260926 as m
import pytest


def period_case(year=2024, source="hkex_disclosures"):
    c = dict(
        period_start=f"{year}-01-01",
        period_end=f"{year}-12-31",
        _period_source_page=1,
        extraction_metadata=dict(
            period_inference="explicit_statement_header",
            statement_title="CONSOLIDATED INCOME STATEMENT",
        ),
    )
    page = (
        f"CONSOLIDATED INCOME STATEMENT\nFor the year ended 31 December {year}\n"
        f"{year}\n{year - 1}\nRevenue\n123\n111"
    )
    table = dict(raw_table_json=dict(rows=[[str(year), str(year - 1)], ["Revenue", "123", "111"]]))
    return c, {1: page}, table


def fact(metric, year, val, *, raw="r", row=1, security="s", label=None):
    labels = dict(
        revenue="Revenue",
        cost_of_revenue="Cost of sales",
        gross_profit="Gross profit",
        net_income="Profit for the year",
        operating_income="Operating profit",
    )
    label = label or labels.get(metric, metric)
    return dict(
        fact_id=f"{raw}:{metric}:{year}",
        metric_id=metric,
        security_id=security,
        source_id="hkex_disclosures",
        currency="HKD",
        original_unit="thousand HKD",
        value_scale="thousand",
        source_definition_id=metric + ":" + label,
        statement_scope="consolidated_entity",
        raw_object_id=raw,
        source_publish_date="2025-03-01" if raw == "r2" else "2024-03-01",
        evidence=dict(page=1, table="t", row=row),
        native_definition=dict(normalized_label=m.norm(label)),
        record=dict(start=f"{year}-01-01", end=f"{year}-12-31", val=str(val)),
    )


def document(raw, year, vals):
    facts = []
    for index, (metric, amounts) in enumerate(vals.items()):
        for y, val in zip((year - 1, year), amounts, strict=True):
            facts.append(fact(metric, y, val, raw=raw, row=index + 1))
    return dict(
        document=dict(
            security_id="s",
            raw_object_id=raw,
            publish_date="2025-03-01" if raw == "r2" else "2024-03-01",
        ),
        qualified_facts=facts,
        usable_fact_ids=[f["fact_id"] for f in facts],
    )


def test_actual_annual_header_not_metadata_year():
    c, pages, table = period_case()
    c["extraction_metadata"]["record_period_hint"] = "2001"
    result = m.annual_period(c, pages, table)
    assert result["start"] == "2024-01-01"
    assert result["inference_not_independent_explicit_start"]


@pytest.mark.parametrize(
    "mode", ["inherited", "missing_year_column", "restated", "52weeks", "wrong_actual_end"]
)
def test_period_evidence_failures_not_passed_from_metadata(mode):
    c, pages, table = period_case()
    if mode == "inherited":
        c["extraction_metadata"]["period_inference"] = "audited_statement_section_period"
    elif mode == "missing_year_column":
        table["raw_table_json"]["rows"] = [["Revenue", "1", "2"]]
    elif mode == "restated":
        table["raw_table_json"]["rows"].insert(0, ["2024", "2023 restated"])
    elif mode == "52weeks":
        pages[1] += "\n52 weeks"
    else:
        pages[1] = pages[1].replace("31 December", "30 June")
    with pytest.raises(ValueError):
        m.annual_period(c, pages, table)


def test_explicit_comparative_column_uses_actual_anniversary():
    c, pages, table = period_case(2023)
    pages[1] = pages[1].replace("ended 31 December 2023", "ended 31 December 2024")
    c["extraction_metadata"]["period_inference"] = "explicit_current_date_comparative_column"
    assert m.annual_period(c, pages, table)["end"] == "2023-12-31"


def test_chinese_calendar_period():
    c, _, table = period_case()
    c["extraction_metadata"]["statement_title"] = "合并利润表"
    assert (
        m.annual_period(c, {1: "合并利润表\n2024年1—12月\n2024年度\n2023年度"}, table)["end"]
        == "2024-12-31"
    )


def test_month_first_explicit_actual_annual_date():
    c, pages, table = period_case()
    pages[1] = pages[1].replace("31 December 2024", "December 31, 2024")
    assert m.annual_period(c, pages, table)["end"] == "2024-12-31"


def alignment_case():
    c = dict(
        period_start="2024-01-01",
        period_end="2024-12-31",
        column_index=1,
        source_field_name="Cost of sales",
        page_number=1,
        _raw_value_text="(80)",
    )
    periods = [
        dict(period_start=f"{year}-01-01", period_end=f"{year}-12-31", fiscal_year=year)
        for year in (2024, 2023)
    ]
    table = dict(
        raw_table_json=dict(
            periods=periods, rows=[["2024", "2023"], ["Costofsales", "(80)", "(70)"]]
        )
    )
    pages = {
        1: "Consolidated income statement\n2024\n2023\nCost of sales\n6\n"
        "(80)\n(70)\nGross profit\n20\n10"
    }
    return c, pages, table


def test_independent_row_column_alignment_excludes_note_and_preserves_sign():
    c, pages, table = alignment_case()
    result = m.row_column_certificate(c, pages, table)
    assert result["aligned_amounts"] == ["-80", "-70"]
    assert result["parser_flag_alone_not_sufficient"]


@pytest.mark.parametrize(
    "mode", ["wrong_value", "wrong_period", "third_year", "percent", "duplicated_label_conflict"]
)
def test_unresolved_original_alignment_never_accepted_from_parser_flag(mode):
    c, pages, table = alignment_case()
    if mode == "wrong_value":
        c["_raw_value_text"] = "(70)"
    elif mode == "wrong_period":
        c["period_end"] = "2022-12-31"
    elif mode == "third_year":
        table["raw_table_json"]["rows"][0].append("2022")
    elif mode == "percent":
        pages[1] = pages[1].replace("(80)", "80%")
    else:
        pages[1] += "\nCost of sales\n(81)\n(70)\nEnd"
    with pytest.raises(ValueError):
        m.row_column_certificate(c, pages, table)


@pytest.mark.parametrize("cost,coefficient", [(-80, 1), (80, -1)])
def test_signed_original_cost_relation(cost, coefficient):
    gross = fact("gross_profit", 2024, 20, row=3)
    revenue = fact("revenue", 2024, 100, row=1)
    cost_fact = fact("cost_of_revenue", 2024, cost, row=2)
    result = m.signed_relation(gross, revenue, cost_fact)
    assert result["cost_coefficient"] == coefficient
    assert cost_fact["record"]["val"] == str(cost)


@pytest.mark.parametrize("field,changed", [("raw_object_id", "different"), ("currency", "USD")])
def test_numeric_closure_alone_does_not_admit_relation(field, changed):
    g, r, c = (
        fact("gross_profit", 2024, 20, row=3),
        fact("revenue", 2024, 100),
        fact("cost_of_revenue", 2024, -80, row=2),
    )
    c[field] = changed
    with pytest.raises(ValueError):
        m.signed_relation(g, r, c)


def test_cost_must_be_direct_full_statement_relation():
    g, r, c = (
        fact("gross_profit", 2024, 20, row=8),
        fact("revenue", 2024, 100),
        fact("cost_of_revenue", 2024, -80, row=2),
    )
    with pytest.raises(ValueError, match="statement_order"):
        m.signed_relation(g, r, c)


def test_within_report_conflict_is_not_arbitrarily_chosen():
    first = fact("revenue", 2024, 100)
    second = deepcopy(first)
    second["fact_id"] = "different"
    second["record"]["val"] = "101"
    usable, conflicts = m.unique_facts([first, second])
    assert not usable and len(conflicts) == 1


def test_dual_targets_not_multiplied_by_report_vintages():
    d = document(
        "r", 2024, dict(revenue=(100, 120), cost_of_revenue=(-80, -90), gross_profit=(20, 30))
    )
    tasks, _ = m.compile_candidates([d, deepcopy(d)])
    assert len(tasks) == 2
    assert {t["quantity"] for t in tasks} == {"difference", "relative_change"}
    assert {Decimal(t["answer_exact"]) for t in tasks} == {Decimal(10), Decimal(50)}
    assert not any(t["qa_eligible"] for t in tasks)


def test_three_year_overlap_mean_remains_source_exhaustion_pending():
    docs = [
        document("r", 2023, dict(revenue=(80, 100), net_income=(1, 2))),
        document("r2", 2024, dict(revenue=(100, 120), net_income=(2, 3))),
    ]
    tasks, _ = m.compile_candidates(docs)
    comp = [t for t in tasks if t["group"] == "composition_required"]
    other = [t for t in tasks if t["group"] == "other_financial"]
    assert len(comp) == 2 and len(other) == 1
    assert all(t["status"] == "PENDING_ISSUER_AND_SOURCE_EXHAUSTION" for t in comp)
    assert other[0]["answer_exact"] == "3"
    assert other[0]["raw_object_ids"] == ["r", "r2"]


def test_nonterminating_mean_preserves_exact_rational_target():
    docs = [document("r", 2023, dict(revenue=(1, 1))), document("r2", 2024, dict(revenue=(1, 2)))]
    tasks, _ = m.compile_candidates(docs)
    assert tasks[0]["answer_exact"] == "4/3"


def test_changed_middle_year_rejects_unjustified_vintage_bridge():
    docs = [
        document("r", 2023, dict(revenue=(80, 100))),
        document("r2", 2024, dict(revenue=(101, 120))),
    ]
    tasks, rejected = m.compile_candidates(docs)
    assert tasks == []
    assert rejected[0]["reason"] == "overlap_bridge_native_value_definition_or_unit_disagrees"


def test_argmax_must_be_strictly_unique():
    docs = [
        document("r", 2023, dict(revenue=(120, 100), net_income=(1, 2))),
        document("r2", 2024, dict(revenue=(100, 120), net_income=(2, 3))),
    ]
    tasks, rejected = m.compile_candidates(docs)
    assert not any(t["group"] == "other_financial" for t in tasks)
    assert any(r["reason"] == "revenue_argmax_not_unique" for r in rejected)


def test_no_aggregate_regex_hit_never_means_source_exhaustion_passed():
    result = m.aggregate_locators({1: "Consolidated income statement\nRevenue 100", 2: ""})
    assert result["status"] == "PENDING_INDEPENDENT_SOURCE_EXHAUSTION_REVIEW"
    assert result["locators"] == []
    assert result["all_native_metric_label_pages"] == {"revenue": [1]}
    assert result["empty_text_pages"] == [2]


def test_aggregate_locator_keeps_original_page_and_snippet():
    result = m.aggregate_locators({7: "Average annual revenue for the three years was 100."})
    assert result["locators"] and all(r["page"] == 7 for r in result["locators"])
    assert result["regex_matches_are_locators_not_semantic_verdicts"]


def test_intermediate_cash_generated_is_not_operating_cash_total():
    c = dict(
        matched_metric_id=m.MEAN_METRICS[3],
        source_field_name="Net cash generated from operations",
        financial_scope_type="consolidated_entity",
        statement_type="cash_flow",
    )
    with pytest.raises(ValueError, match="ambiguous_native_metric_label"):
        m.semantic_label(c)
