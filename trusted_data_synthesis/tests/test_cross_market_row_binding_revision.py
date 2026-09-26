"""Focused synthetic rows; no PDFs, production facts, API or source mutation."""

from copy import deepcopy

import cross_market_repaired_geometry_execution_20260926 as adapter
import cross_market_row_binding_revision_20260926 as m
import pytest
from test_cross_market_layout_qualification import candidate, doc, geometry, review, word


def namespace():
    ns = adapter.isolated_namespace(m.frozen)
    m.v3.install(ns)
    return m.install_row_namespace(ns)


def bilingual_case(metric, english, chinese, chinese_first=False):
    c = candidate(metric)
    c["source_field_name"] = english
    g = geometry()
    index = {"revenue": 5, "cost_of_revenue": 8, "gross_profit": 11}[metric]
    g["pages"][0]["words"][index]["text"] = (
        chinese + " " + english if chinese_first else english + " " + chinese
    )
    return c, g


@pytest.mark.parametrize(
    "metric,english,chinese,chinese_first",
    [
        ("gross_profit", "Gross profit", "毛利", False),
        ("gross_profit", "Gross profit", "毛利", True),
        ("cost_of_revenue", "Cost of sales", "銷售成本", True),
        ("cost_of_revenue", "Cost of revenue", "销售成本", False),
        ("cost_of_revenue", "Cost of revenues", "銷售成本", False),
        ("revenue", "Revenue", "收入", True),
        ("revenue", "Revenues", "收益", False),
    ],
)
def test_exact_bilingual_pairs_keep_raw_words_and_financial_values(
    metric, english, chinese, chinese_first
):
    c, g = bilingual_case(metric, english, chinese, chinese_first)
    before = deepcopy(g)
    result = namespace()["financial_facts"](c, doc(), review(), g)
    assert g == before
    proof = result[0]["evidence"]["independent_row_column_certificate"]
    assert proof["row_binding_revision_evidence"]["display"][
        "authoritative_original_label"
    ] == m.frozen.old.norm(english)
    assert chinese in proof["locator_revision_evidence"]["original_printed_label"]
    assert proof["row_binding_revision_evidence"]["geometry_never_shadowed_or_edited"]
    assert (
        result[0]["record"]["val"]
        == {"gross_profit": "20000000", "cost_of_revenue": "-80000000", "revenue": "100000000"}[
            metric
        ]
    )


@pytest.mark.parametrize(
    "bad",
    [
        "收益",
        "投资收益 Revenue",
        "Revenue from contracts 收入",
        "营业总收入 Revenue",
        "Cost of goods sold 銷售成本",
    ],
)
def test_unregistered_or_single_chinese_semantics_are_not_bilingual_pairs(bad):
    metric = "cost_of_revenue" if bad.startswith("Cost") else "revenue"
    c, g = bilingual_case(
        metric, "Cost of sales" if metric == "cost_of_revenue" else "Revenue", "收入"
    )
    g["pages"][0]["words"][8 if metric == "cost_of_revenue" else 5]["text"] = bad
    with pytest.raises(ValueError):
        namespace()["certify"](c, g)


@pytest.mark.parametrize("raw", ["80", "(80)"])
def test_literal_min_expense_prefix_does_not_change_numeric_sign(raw):
    c, g = bilingual_case("cost_of_revenue", "Cost of sales", "销售成本")
    c["source_field_name"] = "营业成本"
    g["pages"][0]["words"][8]["text"] = "减：营业成本"
    g["pages"][0]["words"][9]["text"] = raw
    observations = namespace()["certify"](c, g)["observations"]
    assert observations[0]["value"] == ("80" if raw == "80" else "-80")


def note_case(tokens, *, bilingual=True):
    c, g = candidate(), geometry()
    words = g["pages"][0]["words"]
    words.append(word("Notes", 295, 100, 24))
    if bilingual:
        words.append(word("附註", 298, 113, 20))
    x = 298
    for token in tokens:
        w = word(token, x, 125, len(token) * 3)
        words.append(w)
        x = w["x1"] + 1
    return c, g


@pytest.mark.parametrize(
    "tokens,refs",
    [(["5,8"], ["5", "8"]), (["5,", "8"], ["5", "8"]), (["5,8,12"], ["5", "8", "12"])],
)
def test_finite_compound_notes_only_in_one_bilingual_physical_column(tokens, refs):
    c, g = note_case(tokens)
    before = deepcopy(g)
    proof = namespace()["certify"](c, g)
    assert g == before and [v["value"] for v in proof["observations"]] == ["100", "90"]
    assert proof["note_binding_certificate"]["note_syntax"]["references"] == refs
    assert proof["note_binding_certificate"]["column"]["bilingual_same_physical_column"]
    assert [w["text"] for w in proof["excluded_note_words"]] == tokens


@pytest.mark.parametrize("token", ["5,8,12,16", "1,234", "5,8(a)", "5,5"])
def test_unknown_or_ambiguous_numeric_notes_rejected(token):
    c, g = note_case([token])
    with pytest.raises(ValueError):
        namespace()["certify"](c, g)


def test_note_list_in_monetary_column_not_parsed_as_amount_58():
    c, g = note_case(["5,8"], bilingual=False)
    g["pages"][0]["words"][-1].update(x0=525, x1=535)
    with pytest.raises(ValueError, match="outside_unique_Notes"):
        namespace()["certify"](c, g)


def test_parenthesized_negative_amount_never_discarded_as_legacy_note():
    c, g = note_case(["(80)"])
    before = deepcopy(g)
    with pytest.raises(ValueError, match="unknown_nonmonetary_row_tokens"):
        namespace()["certify"](c, g)
    assert g == before


def test_same_language_or_different_physical_notes_headers_not_collapsed():
    c, g = note_case(["5,8"])
    g["pages"][0]["words"][-2]["text"] = "Notes"
    with pytest.raises(ValueError):
        namespace()["certify"](c, g)
    c, g = note_case(["5,8"])
    g["pages"][0]["words"][-2].update(x0=250, x1=270)
    with pytest.raises(ValueError):
        namespace()["certify"](c, g)


def test_dynamic_header_guards_and_certificate_hook_not_bypassed():
    ns = namespace()
    original_header = ns["header_lines"]
    ns["header_binding_proof"] = lambda a, h, e, c: dict(version="synthetic_header_v4")
    proof = ns["certify"](candidate(), geometry())
    assert proof["header_binding_revision_evidence"]["version"] == "synthetic_header_v4"

    def pending(*args):
        raise ValueError("header_source_semantics_pending")

    ns["header_lines"] = pending
    with pytest.raises(ValueError, match="source_semantics_pending"):
        ns["certify"](candidate(), geometry())
    ns["header_lines"] = original_header
    g = geometry()
    g["pages"][0]["words"].append(word("Restated", 455, 113))
    with pytest.raises(ValueError, match="restatement"):
        ns["certify"](candidate(), g)


def test_v3_loss_display_proof_and_financial_kernel_identity_preserved():
    c, g = candidate(), geometry()
    c.update(matched_metric_id="operating_income", source_field_name="营业利润")
    g["pages"][0]["words"][5]["text"] = "三、营业利润（亏损以“－”号填列）"
    ns = namespace()
    proof = ns["certify"](c, g)
    assert proof["locator_revision_evidence"]["exact_ignored_display_annotation"]
    assert ns["financial_facts"].__code__ is m.frozen.financial_facts.__code__
    assert ns["_fact"].__code__ is m.frozen._fact.__code__
    assert ns["old"].compile_candidates is m.frozen.old.compile_candidates
