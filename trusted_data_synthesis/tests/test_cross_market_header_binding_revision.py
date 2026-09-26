"""Synthetic words only: header representations never bypass semantic gates."""

from copy import deepcopy

import cross_market_header_binding_revision_20260926 as m
import cross_market_repaired_geometry_execution_20260926 as adapter
import cross_market_row_binding_revision_20260926 as rows
import pytest
from test_cross_market_layout_qualification import candidate, doc, geometry, review, word


def namespace():
    ns = adapter.isolated_namespace(m.core)
    m.v3.install(ns)
    m.install_header_namespace(ns)
    rows.install_row_namespace(ns)
    return ns


@pytest.mark.parametrize(
    "sentence",
    [
        "For the year ended 31st December 2024",
        "For the year ended December 31st, 2024",
        "F o r th e y e a r e n d e d 3 1 D e c e m b e r 2 0 2 4",
    ],
)
def test_ordinal_or_spaced_actual_annual_sentence_keeps_raw_words(sentence):
    g = geometry()
    g["pages"][0]["words"][1]["text"] = sentence
    before = deepcopy(g)
    result = namespace()["certify"](candidate(), g)
    assert result["observations"][0]["end"] == "2024-12-31" and g == before
    proof = result["header_binding_revision_evidence"]
    assert proof["original_annual_signals"][0]["original_text"] == sentence


def test_invalid_ordinal_is_not_silently_stripped():
    g = geometry()
    g["pages"][0]["words"][1]["text"] = "For the year ended 31th December 2024"
    with pytest.raises(ValueError, match="invalid_ordinal"):
        namespace()["certify"](candidate(), g)


def test_partial_day_month_binds_only_original_two_four_digit_year_columns():
    g = geometry()
    g["pages"][0]["words"][1]["text"] = "For the year ended 31 December"
    result = namespace()["certify"](candidate(), g)
    assert [o["end"] for o in result["observations"]] == ["2024-12-31", "2023-12-31"]
    g["pages"][0]["words"][3]["text"] = "本年金额"
    g["pages"][0]["words"][4]["text"] = "上年金额"
    with pytest.raises(ValueError, match="requires_one_original_two_year"):
        namespace()["certify"](candidate(), g)


def test_plural_annual_and_short_dates_bound_to_printed_four_digit_years():
    g = geometry()
    words = g["pages"][0]["words"]
    words[1]["text"] = "For the years ended December 31, 2024 and 2023"
    words[3]["text"], words[4]["text"] = "12/31/24", "12/31/23"
    result = namespace()["certify"](candidate(), g)
    assert [o["end"] for o in result["observations"]] == ["2024-12-31", "2023-12-31"]
    assert result["year_columns"][0]["printed_four_digit_annual_years"] == [2023, 2024]
    words[1]["text"] = "For the year ended December 31, 2024"
    with pytest.raises(ValueError, match="short_date_requires_printed_four_digit"):
        namespace()["certify"](candidate(), g)


def test_short_dates_without_four_digit_source_years_or_wrong_day_fail():
    g = geometry()
    words = g["pages"][0]["words"]
    words[1]["text"] = "For the years ended December 31"
    words[3]["text"], words[4]["text"] = "12/31/24", "12/31/23"
    with pytest.raises(ValueError):
        namespace()["certify"](candidate(), g)
    words[1]["text"] = "For the years ended June 30, 2024 and 2023"
    with pytest.raises(ValueError, match="short_date_requires_printed_four_digit"):
        namespace()["certify"](candidate(), g)


def test_three_years_and_duplicate_header_rows_stay_rejected():
    g = geometry()
    g["pages"][0]["words"][1]["text"] = "For the years ended December 31, 2024, 2023 and 2022"
    with pytest.raises(ValueError, match="more_than_two"):
        namespace()["certify"](candidate(), g)
    g = geometry()
    g["pages"][0]["words"].extend([word("2024", 380, 112), word("2023", 460, 112)])
    with pytest.raises(ValueError, match="multiple_year_header"):
        namespace()["certify"](candidate(), g)


def test_HKm_token_boundary_not_lost_between_repeated_units():
    g = geometry()
    words = g["pages"][0]["words"]
    words[2]["text"] = "HK$m"
    words.append(word("HK$m", 460, 80))
    result = namespace()["certify"](candidate(), g)
    assert result["unit"]["scale"] == 1000000 and len(result["unit"]["unit_token_witnesses"]) == 2


@pytest.mark.parametrize(
    "unit,scale",
    [
        ("million", 1000000),
        ("millions", 1000000),
        ("thousand", 1000),
        ("thousands", 1000),
        ("’000", 1000),
    ],
)
def test_exact_bare_unit_keeps_independent_same_header_currency(unit, scale):
    g = geometry()
    words = g["pages"][0]["words"]
    words[2]["text"] = "HK$"
    words.append(word(unit, 500, 80))
    assert namespace()["certify"](candidate(), g)["unit"]["scale"] == scale
    words[-1]["text"] = "millionaire"
    with pytest.raises(ValueError, match="scale_unresolved"):
        namespace()["certify"](candidate(), g)


def test_split_RMB_apostrophe_and_000_do_not_end_header_or_keep_wrong_old_scale():
    c, g = candidate(), geometry()
    words = g["pages"][0]["words"]
    words[2].update(text="RMB’", x0=380, x1=398)
    words.extend([word("000", 401, 80, 16), word("RMB’", 460, 80, 18), word("000", 481, 80, 16)])
    result = namespace()["financial_facts"](c, doc(), review(), g)
    assert result[0]["currency"] == "CNY" and result[0]["record"]["val"] == "100000"
    assert result[0]["original_candidate_bindings"][0]["scale"] == "million"
    assert result[0]["evidence"]["independent_row_column_certificate"]["unit"]["scale"] == 1000


def test_remote_unit_000_or_margin_word_is_not_unit_proof():
    g = geometry()
    words = g["pages"][0]["words"]
    words[2].update(text="RMB’", x0=350, x1=368)
    words.append(word("000", 480, 80))
    with pytest.raises(ValueError, match="scale_unresolved"):
        namespace()["certify"](candidate(), g)
    words[2]["text"] = "HK$MARGIN"
    words.pop()
    with pytest.raises(ValueError, match="scale_unresolved"):
        namespace()["certify"](candidate(), g)


@pytest.mark.parametrize("warning", ["Restated", "Continuing operations", "53 weeks", "Unaudited"])
def test_real_semantic_warnings_not_cleared_by_header_fix(warning):
    g = geometry()
    g["pages"][0]["words"].append(word(warning, 50, 112))
    with pytest.raises(ValueError):
        namespace()["certify"](candidate(), g)


def test_parenthesized_comparative_Note_tokens_pending_but_plain_Note_allowed():
    g = geometry()
    g["pages"][0]["words"].extend(
        [word("Notes", 290, 100), word("(Note", 446, 112, 20), word("1c)", 468, 112, 12)]
    )
    with pytest.raises(ValueError, match="comparative_note_pending"):
        namespace()["certify"](candidate(), g)
    g = geometry()
    g["pages"][0]["words"].append(word("Notes", 290, 100))
    assert namespace()["certify"](candidate(), g)


def test_explicit_transition_footer_pending_generic_IFRS_reference_not_blocked():
    g = geometry()
    words = g["pages"][0]["words"]
    words.append(
        word(
            "The Group has initially applied HKFRS 16; comparative information is not restated.",
            50,
            600,
        )
    )
    with pytest.raises(ValueError, match="accounting_transition"):
        namespace()["certify"](candidate(), g)
    words[-1]["text"] = "Financial statements are prepared in accordance with HKFRS."
    assert namespace()["certify"](candidate(), g)


def navigated_geometry():
    g = geometry()
    words = g["pages"][0]["words"]
    words[0].update(text="CONSOLIDATED", x0=50, x1=150, y0=10, y1=20)
    words.extend(
        [
            word("EDITORIAL", 520, 10, 50),
            word("MANAGEMENT REPORT", 500, 24, 90),
            word("INCOME STATEMENT", 50, 38, 160),
            word("ACCOUNTS", 520, 38, 50),
        ]
    )
    return g


def test_navigation_title_recovery_uses_disjoint_physical_column_and_keeps_indices():
    g = navigated_geometry()
    original = deepcopy(g)
    result = namespace()["certify"](candidate(), g)
    proof = result["header_binding_revision_evidence"]["bounded_title_geometry"]
    assert proof["navigation_outside_title_x_corridor"]
    assert {w["text"] for w in proof["excluded_navigation_words"]} == {
        "EDITORIAL",
        "MANAGEMENT REPORT",
        "ACCOUNTS",
    }
    assert g == original and result["anchor"]["consolidated"]


@pytest.mark.parametrize("mode", ["same_column", "unknown_nav", "parent_title", "too_tall"])
def test_navigation_never_globally_strips_words_or_crosses_parent_title(mode):
    g = navigated_geometry()
    words = g["pages"][0]["words"]
    if mode == "same_column":
        words[-3].update(x0=50, x1=140)
    elif mode == "unknown_nav":
        words[-3]["text"] = "Discussion of consolidated results"
    elif mode == "parent_title":
        words[-3]["text"] = "Company income statement"
    else:
        words[-2].update(y0=120, y1=130)
        words[-1].update(y0=120, y1=130)
    with pytest.raises(ValueError):
        namespace()["certify"](candidate(), g)


def test_AND_SUBSIDIARIES_never_substitutes_for_consolidated_statement_title():
    g = geometry()
    g["pages"][0]["words"][0]["text"] = "Statement of profit or loss"
    g["pages"][0]["words"].append(word("COMPANY AND SUBSIDIARIES", 50, 20))
    with pytest.raises(ValueError, match="consolidated_statement"):
        namespace()["certify"](candidate(), g)


def test_no_above_title_currency_borrowing_and_no_mutation_of_old_modules():
    g = geometry()
    words = g["pages"][0]["words"]
    words[2]["text"] = "单位：元"
    words.append(word("币种：人民币", 50, 25))
    with pytest.raises(ValueError, match="currency_missing"):
        namespace()["certify"](candidate(), g)
    assert m.core.unit_certificate is not m.unit_certificate
    assert (m.core.MAX_HEADER_DISTANCE, m.core.LINE_TOLERANCE, m.core.X_TOLERANCE) == (4, 3, 38)
