"""Synthetic-only tests for the finite cache locator amendment."""

from copy import deepcopy

import cross_market_locator_revision_20260926 as m
import cross_market_repaired_geometry_execution_20260926 as adapter
import pytest
from test_cross_market_layout_qualification import candidate, doc, geometry, review, word


def namespace():
    return m.install(adapter.isolated_namespace(m.frozen))


def chinese_case():
    c = candidate()
    c.update(source_field_name="营业收入", currency="CNY", value_scale="元")
    return c, geometry(source="Chinese")


def above_case():
    c, g = chinese_case()
    words = g["pages"][0]["words"]
    words[1].update(text="2024 年12 月31 日止年度", y0=20, y1=30)
    words[3]["text"], words[4]["text"] = "本年金额", "上年金额"
    return c, g


def test_injection_preserves_frozen_globals_and_financial_math():
    before = m.frozen.label_rows, m.frozen.header_lines, m.frozen.certify
    ns = namespace()
    assert before == (m.frozen.label_rows, m.frozen.header_lines, m.frozen.certify)
    assert ns["financial_facts"].__code__ is m.frozen.financial_facts.__code__
    assert ns["old"].compile_candidates is m.frozen.old.compile_candidates
    assert (ns["MAX_HEADER_DISTANCE"], ns["LINE_TOLERANCE"], ns["X_TOLERANCE"]) == (4, 3, 38)


@pytest.mark.parametrize(
    "metric,label,suffix",
    [
        ("operating_income", "营业利润", "（亏损以“－”号填列）"),
        ("net_income", "净利润", "（净亏损以“－”号填列）"),
    ],
)
def test_exact_whitelisted_loss_annotation_retains_negative_amount_and_raw_words(
    metric, label, suffix
):
    c, g = chinese_case()
    c.update(matched_metric_id=metric, source_field_name=label)
    words = g["pages"][0]["words"]
    words[5]["text"] = "五、" + label
    words[5]["x1"] = 100
    words.append(word(suffix, 101, 125, 220))
    words[6]["text"] = "(80)"
    before = deepcopy(g)
    facts = namespace()["financial_facts"](c, doc(), review(), g)
    assert g == before
    assert facts[0]["record"]["val"] == "-80"
    assert facts[1]["record"]["val"] == "90"
    evidence = facts[0]["evidence"]["independent_row_column_certificate"][
        "locator_revision_evidence"
    ]
    assert evidence["exact_ignored_display_annotation"] == m.frozen.old.norm(suffix)
    assert suffix in evidence["original_printed_label"] and evidence["numeric_sign_unchanged"]


@pytest.mark.parametrize(
    "printed", ["归属于母公司股东的净利润", "扣除非经常性损益后的净利润", "净利润（调整后）"]
)
def test_semantic_prefixes_and_unknown_parentheticals_never_stripped(printed):
    c, g = chinese_case()
    c.update(matched_metric_id="net_income", source_field_name="净利润")
    g["pages"][0]["words"][5]["text"] = printed
    with pytest.raises(ValueError):
        namespace()["financial_facts"](c, doc(), review(), g)


def test_split_year_and_annual_suffix_not_misclassified_as_monetary_row():
    c, g = chinese_case()
    words = g["pages"][0]["words"]
    words[1]["text"] = ""
    words.extend([word("项目", 50, 100), word("年度", 397, 100, 16), word("年度", 477, 100, 16)])
    certificate = namespace()["certify"](c, g)
    assert certificate["observations"][0]["end"] == "2024-12-31"
    proof = certificate["locator_revision_evidence"]["split_annual_header_rows"]
    assert len(proof) == 1 and len(proof[0]["columns"][0]["words"]) == 2
    line = deepcopy(proof[0]["line"])
    line["words"][0]["text"] = "营业收入"
    line["text"] = "营业收入 2024 年度 2023 年度"
    assert m._data_line(line)


def test_remote_annual_suffix_not_joined_to_year():
    line = m.frozen.lines_for_page(
        dict(
            words=[
                word("项目", 50, 100),
                word("2024", 150, 100),
                word("年度", 210, 100),
                word("2023", 250, 100),
                word("年度", 310, 100),
            ]
        )
    )[0]
    assert m.split_annual_columns(line) is None and m._data_line(line)


def test_duplicate_same_year_header_rows_remain_ambiguous():
    c, g = chinese_case()
    words = g["pages"][0]["words"]
    words.extend([word("2024", 380, 113), word("2023", 460, 113)])
    with pytest.raises(ValueError, match="multiple_year_header"):
        namespace()["certify"](c, g)


def test_explicit_annual_date_above_title_supports_relative_columns_with_evidence():
    c, g = above_case()
    result = namespace()["certify"](c, g)
    assert [r["end"] for r in result["observations"]] == ["2024-12-31", "2023-12-31"]
    proof = result["locator_revision_evidence"]
    assert len(proof["original_pre_title_date_lines_included"]) == 1
    assert proof["actual_explicit_annual_dates"] == ["2024-12-31"]


@pytest.mark.parametrize("barrier", ["母公司利润表", "附注：期间说明", "营业收入 100 90"])
def test_no_date_borrowing_across_intervening_scope_notes_or_data(barrier):
    c, g = above_case()
    g["pages"][0]["words"].append(word(barrier, 50, 31, 200))
    with pytest.raises(ValueError):
        namespace()["certify"](c, g)


def test_prefix_bounds_and_unit_currency_nonborrowing():
    c, g = above_case()
    words = g["pages"][0]["words"]
    words[1].update(y0=-21, y1=-11)
    with pytest.raises(ValueError, match="annual_date_missing"):
        namespace()["certify"](c, g)
    c, g = above_case()
    words = g["pages"][0]["words"]
    words[1].update(y0=-10, y1=0)
    words.extend(
        [
            word("单位：人民币元", 50, 1),
            word("单位：人民币元", 50, 12),
            word("单位：人民币元", 50, 23),
        ]
    )
    with pytest.raises(ValueError, match="annual_date_missing"):
        namespace()["certify"](c, g)
    c, g = above_case()
    words = g["pages"][0]["words"]
    words[2]["text"] = "单位：元"
    words.append(word("币种：人民币", 50, 31))
    with pytest.raises(ValueError, match="currency_missing"):
        namespace()["certify"](c, g)


@pytest.mark.parametrize("annual", ["2023年12月31日止年度", "2023年度"])
def test_explicit_above_title_year_not_overridden_by_newer_column(annual):
    c, g = above_case()
    words = g["pages"][0]["words"]
    words[1]["text"] = annual
    words[3]["text"], words[4]["text"] = "2024年度", "2023年度"
    with pytest.raises(ValueError, match="actual_header_and_printed_years_disagree"):
        namespace()["certify"](c, g)


def test_bare_date_is_not_annual_flow_proof_and_noncalendar_header_still_rejected():
    c, g = above_case()
    g["pages"][0]["words"][1]["text"] = "2024年12月31日"
    with pytest.raises(ValueError, match="annual_date_missing"):
        namespace()["certify"](c, g)
    c, g = above_case()
    g["pages"][0]["words"].append(word("53 weeks", 50, 115))
    with pytest.raises(ValueError, match="noncalendar"):
        namespace()["certify"](c, g)
