"""Finite controls for the new quantity/format split; no provider or old scores."""

import copy

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import (
    public_quantity_context,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.quantity import (
    interpret_final,
    interpret_unit,
    number,
    score_quantity,
)


def score(final, reference="46.4", context=None):
    context = public_quantity_context() if context is None else context
    return score_quantity(interpret_final(final, context), reference, context)


@pytest.mark.parametrize(
    "unit",
    [
        "USD_million",
        "USD millions",
        "million USD",
        "millions of dollars",
        "$ in millions",
        "in millions of U.S. dollars",
        "million",
        "millions",
        "U.S. dollars (millions)",
    ],
)
def test_finite_currency_scale_composition_not_a_task_response_whitelist(unit):
    result = score({"value": "46.4", "unit": unit})
    assert result["V_quantity"] == "PASS"
    assert result["V_format"] == ("PASS" if unit == "USD_million" else "FAIL")
    assert result["format_is_hard_validity_condition"] is False


@pytest.mark.parametrize(
    ("value", "unit"),
    [
        ("46400000", "USD"),
        ("46,400,000", "US dollars"),
        ("46400", "USD thousand"),
        ("0.0464", "USD billion"),
        ("232/5", "USD_million"),
    ],
)
def test_equal_physical_amounts_with_explicit_scale_are_semantically_equal(value, unit):
    assert score({"value": value, "unit": unit})["V_quantity"] == "PASS"


@pytest.mark.parametrize(
    "unit",
    [
        "EUR million",
        "GBP million",
        "CAD million",
        "JPY million",
        "percent",
        "ratio",
        "USD",
        "$",
        "USD billion",
    ],
)
def test_explicit_currency_dimension_or_scale_mismatch_is_not_rescued(unit):
    assert score({"value": "46.4", "unit": unit})["V_quantity"] == "FAIL"


@pytest.mark.parametrize(
    ("target", "source"),
    [
        ([], []),
        (["USD", "CAD"], ["USD", "CAD"]),
        (["USD"], ["CAD"]),
        (["USD"], []),
        ([], ["USD"]),
    ],
)
def test_bare_scale_never_defaults_to_USD_without_unique_public_agreement(target, source):
    context = public_quantity_context()
    context.update(public_target_currencies=target, relevant_source_currencies=source)
    assert (
        score({"value": "46.4", "unit": "million"}, context=context)["V_quantity"] == "UNDETERMINED"
    )
    assert interpret_unit("$ in millions", context)["status"] == "UNDETERMINED"


@pytest.mark.parametrize(
    "final",
    [
        None,
        {},
        {"value": "46.4"},
        {"answer": "See the prior tool."},
        {"unit": "USD_million"},
        {"answer": "The result is 46.4."},
    ],
)
def test_no_value_or_scale_filled_from_question_tool_sibling_or_reference(final):
    assert score(final)["V_quantity"] == "UNDETERMINED"


def test_only_actual_Final_answer_text_can_complete_its_own_unit():
    result = score({"value": "46.4", "answer": "The increase is $46.4 million."})
    assert result["V_quantity"] == "PASS"
    assert result["interpretation"]["extraction"] == "Final.value+Final.answer.unit"
    assert result["V_format"] == "FAIL"


@pytest.mark.parametrize(
    "final",
    [
        "The net increase is $46.4 million.",
        {"answer": "The net increase is 46.4 million U.S. dollars."},
    ],
)
def test_clear_amount_in_actual_Final_text_is_not_rejected_for_missing_preferred_fields(final):
    result = score(final)
    assert result["V_quantity"] == "PASS"
    assert result["V_format"] == "FAIL"


def test_two_possible_Final_amounts_are_not_disambiguated_using_the_reference():
    final = {"answer": "Either $46.4 million or $143.9 million."}
    assert score(final)["V_quantity"] == "UNDETERMINED"


@pytest.mark.parametrize("unit", ["EUR million", "USD", "percent"])
def test_explicit_unit_field_is_not_replaced_by_a_matching_reference_like_answer(unit):
    result = score({"value": "46.4", "unit": unit, "answer": "$46.4 million"})
    assert result["V_quantity"] == "FAIL"


def test_explicit_currencies_inside_one_unit_conflict():
    assert score({"value": "46.4", "unit": "USD EUR million"})["V_quantity"] == "FAIL"


def test_ratio_and_percent_are_distinct_scales_and_can_represent_the_same_quantity():
    context = {
        "dimension": "ratio",
        "target_currency": None,
        "target_scale": "1/100",
        "preferred_unit": "percent",
        "public_target_currencies": [],
        "relevant_source_currencies": [],
    }
    assert score({"value": "0.464", "unit": "ratio"}, context=context)["V_quantity"] == "PASS"
    assert score({"value": "46.4", "unit": "percent"}, context=context)["V_quantity"] == "PASS"
    assert score({"value": "46.4", "unit": "ratio"}, context=context)["V_quantity"] == "FAIL"


@pytest.mark.parametrize("value", [True, "NaN", "inf", None, [], {}, "46.4 or 143.9", "1/0"])
def test_unsupported_or_nonfinite_number_is_not_repaired(value):
    assert score({"value": value, "unit": "USD_million"})["V_quantity"] == "UNDETERMINED"


def test_public_interpretation_is_independent_of_reference_and_nonmutating():
    final = {"value": "46.4", "unit": "$ in millions"}
    before = copy.deepcopy(final)
    context = public_quantity_context()
    interpreted = interpret_final(final, context)
    assert score_quantity(interpreted, "46.4", context)["V_quantity"] == "PASS"
    assert score_quantity(interpreted, "143.9", context)["V_quantity"] == "FAIL"
    assert final == before
    assert interpreted["reference_tool_or_sibling_message_used_to_complete_Final"] is False


def test_source_explicit_foreign_currency_is_not_canonically_changed():
    context = public_quantity_context()
    context["relevant_source_currencies"] = ["EUR"]
    assert interpret_unit("million", context)["status"] == "UNDETERMINED"
    assert interpret_unit("EUR million", context)["currency"] == "EUR"


def test_exact_numeric_lexemes_and_tolerance():
    assert number("46.4000") == number("232/5")
    assert score({"value": "46.4000", "unit": "USD_million"})["rounding_tolerance"] == "1/20000"
    assert score({"value": "46.41", "unit": "USD_million"})["V_quantity"] == "FAIL"


@pytest.mark.parametrize(
    "final",
    [
        {"value": "46.4", "unit": "million", "currency": "EUR"},
        {"value": "46.4", "unit": "USD_million", "currency": "EUR"},
        {"value": "46.4", "unit": "million", "answer": "The currency is EUR."},
        {"value": "46.4", "unit": "million", "answer": "All amounts are in EUR."},
    ],
)
def test_explicit_Final_currency_claim_blocks_contextual_USD_completion(final):
    assert score(final)["V_quantity"] == "FAIL"


def test_matching_explicit_Final_currency_claim_and_unknown_claim():
    assert score({"value": "46.4", "unit": "million", "currency": "USD"})["V_quantity"] == "PASS"
    assert (
        score({"value": "46.4", "unit": "million", "currency": "unresolved"})["V_quantity"]
        == "UNDETERMINED"
    )


@pytest.mark.parametrize("value", ["1e999999", "1e-999999", "9" * 257])
def test_scalar_parsing_is_bounded_without_allocating_unlimited_integers(value):
    assert score({"value": value, "unit": "USD_million"})["V_quantity"] == "UNDETERMINED"
