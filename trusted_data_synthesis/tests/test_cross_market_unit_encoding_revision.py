"""Synthetic words only; no production requalification or source reads."""

from copy import deepcopy

import cross_market_repaired_geometry_execution_20260926 as adapter
import cross_market_row_binding_revision_20260926 as row
import cross_market_unit_encoding_revision_20260927 as m
import pytest
from test_cross_market_layout_qualification import candidate, doc, geometry, review, word


def lines(*texts):
    words = [word(text, 50, 20 + index * 20) for index, text in enumerate(texts)]
    return m.header.core.lines_for_page(dict(words=words))


@pytest.mark.parametrize(
    "text,scale",
    [
        ("单位:元 币种:人民币", 1),
        ("單位：千元，幣種：人民幣", 1000),
        ("单位：人民币百万元；币种：人民币", 1000000),
    ],
)
def test_whole_Chinese_unit_currency_compound(text, scale):
    value = m.unit_certificate({}, lines(text))
    assert value["currency"] == "CNY" and value["scale"] == scale
    assert not value["unit_encoding_revision_evidence"]["currency_only_base_fallback_used"]


@pytest.mark.parametrize(
    "text", ["RMB’Million", "RMB'Millions", "All amounts in RMB millions", "In RMB millions"]
)
def test_explicit_English_unit_encodings(text):
    result = m.unit_certificate({}, lines(text))
    assert result["currency"] == "CNY" and result["scale"] == 1000000


@pytest.mark.parametrize("explicit,scale", [("RMB’000", 1000), ("million", 1000000)])
def test_Expressed_currency_only_does_not_conflict_with_explicit_scale(explicit, scale):
    result = m.unit_certificate({}, lines("(Expressed in RMB)", explicit))
    assert result["scale"] == scale
    assert result["unit_encoding_revision_evidence"]["currency_only_base_fallback_suppressed"]
    assert not result["unit_encoding_revision_evidence"]["currency_only_base_fallback_used"]


def test_six_word_window_preserves_raw_inRMB_millions_without_scale1_competitor():
    values = [
        word(t, x, 20, width)
        for t, x, width in (
            ("All", 50, 12),
            ("amounts", 66, 28),
            ("in", 98, 8),
            ("RMB", 110, 12),
            ("millions", 126, 32),
        )
    ]
    header = m.header.core.lines_for_page(dict(words=values))
    original = deepcopy(header)
    result = m.unit_certificate({}, header)
    assert result["scale"] == 1000000 and header == original
    assert result["unit_encoding_revision_evidence"]["currency_only_base_fallback_suppressed"]


def test_explicit_Chinese_base_unit_and_million_still_conflict():
    with pytest.raises(ValueError, match="scale_unresolved"):
        m.unit_certificate({}, lines("单位:元 币种:人民币", "RMB million"))


def test_currency_only_base_fallback_used_only_without_explicit_scale():
    result = m.unit_certificate({}, lines("In RMB"))
    assert result["scale"] == 1
    assert result["unit_encoding_revision_evidence"]["currency_only_base_fallback_used"]
    with pytest.raises(ValueError, match="scale_unresolved"):
        m.unit_certificate({}, lines("RMB"))


def test_ambiguous_currencies_unknown_suffix_and_conflicting_units_rejected():
    with pytest.raises(ValueError, match="currency_missing_or_multiple"):
        m.unit_certificate({}, lines("单位:元 币种:人民币", "HKD million"))
    with pytest.raises(ValueError, match="scale_unresolved"):
        m.unit_certificate({}, lines("单位:元币种:人民币未知后缀"))
    with pytest.raises(ValueError, match="scale_unresolved"):
        m.unit_certificate({}, lines("RMB'Millionaire"))
    with pytest.raises(ValueError, match="scale_unresolved"):
        m.unit_certificate({}, lines("in RMB", "million", "thousand"))


def test_unit_collection_keeps_original_word_and_gap_bounds():
    assert m.explicit_witnesses.__code__ is m.header.unit_witnesses.__code__
    assert m.explicit_witnesses.__globals__ is not m.header.unit_witnesses.__globals__
    words = [word("RMB’", 50, 20, 20), word("Million", 100, 20, 30)]
    # Remote bare Million independently states its scale, but not an invented
    # two-word apostrophe phrase witness across the 30pt gap.
    collected = m.explicit_witnesses(m.header.core.lines_for_page(dict(words=words))[0])
    assert all(len(w["word_indices"]) == 1 for w in collected)


def test_install_changes_only_unit_function_and_keeps_semantic_guards():
    ns = adapter.isolated_namespace(m.header.core)
    m.header.v3.install(ns)
    m.header.install_header_namespace(ns)
    row.install_row_namespace(ns)
    before = dict(ns)
    original_function = m.header.unit_certificate
    m.install_unit_namespace(ns)
    assert {k for k in ns if ns[k] is not before[k]} == {"unit_certificate"}
    assert m.header.unit_certificate is original_function
    g = geometry()
    g["pages"][0]["words"][2]["text"] = "RMB’Million"
    facts = ns["financial_facts"](candidate(), doc(), review(), g)
    assert facts[0]["currency"] == "CNY" and facts[0]["record"]["val"] == "100000000"
    proof = facts[0]["evidence"]["independent_row_column_certificate"]["unit"]
    assert proof["unit_encoding_revision_evidence"]["version"] == m.VERSION
    g["pages"][0]["words"].append(word("Restated", 450, 112))
    with pytest.raises(ValueError, match="restatement"):
        ns["certify"](candidate(), g)
