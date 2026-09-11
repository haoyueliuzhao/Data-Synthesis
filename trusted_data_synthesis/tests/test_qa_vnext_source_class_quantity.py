"""Targeted v1.1 controls; old sealed measurements are not a test corpus."""

import ast
import inspect

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration import quantity as old
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import (
    public_quantity_context,
)
from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility import quantity as new


def score(answer, value="46.4", unit="USD_million"):
    final = {"value": value, "unit": unit, "answer": answer}
    return new.score_quantity(
        new.interpret_final(final, public_quantity_context()), "232/5", public_quantity_context()
    )


@pytest.mark.parametrize(
    "text",
    [
        "$46.4M",
        "US$46.4M",
        "USD 46.4M",
        "$46.4m",
        "Net change = $426.6M - $380.2M = $46.4M increase.",
        "$426.6M-$380.2M=$46.4M",
        "The answer is 46.4 million dollars.",
    ],
)
def test_currency_qualified_m_complete_and_consistent(text):
    result = score(text)
    assert result["V_quantity"] == "PASS"
    assert result["V_format"] == "PASS"
    assert result["interpretation"]["policy"] == new.VERSION


@pytest.mark.parametrize("text", ["$46.4", "46.4 USD", "46.4 dollars"])
def test_real_base_dollar_conflict_is_not_hidden(text):
    assert score(text)["V_quantity"] == "FAIL"


@pytest.mark.parametrize("text", ["€46.4M", "EUR 46.4 million", "£46.4M", "C$46.4M"])
def test_explicit_other_currency_not_overwritten_by_context(text):
    assert score(text)["V_quantity"] == "FAIL"


@pytest.mark.parametrize(
    "text",
    [
        "$46.4Mystery",
        "$46.4K",
        "$46.4millionXYZ",
        "$46.4USD_mystery",
        "$46.4M2",
        "$46.4M€",
        "46.4M",
    ],
)
def test_unknown_suffix_retained_and_never_confirmed_prefix(text):
    result = score(text)
    assert result["V_quantity"] == "UNDETERMINED"
    mention = result["interpretation"]["actual_Final_amount_mentions"][0]
    assert mention["interpretation"]["status"] == "UNDETERMINED"
    assert mention["quote"] == text


def test_compact_equation_operands_are_not_competing_final_answers():
    result = score("$426.6M-$380.2M=$46.4M")
    assert result["V_quantity"] == "PASS"
    mentions = result["interpretation"]["actual_Final_amount_mentions"]
    assert len(mentions) == 3
    assert [m["exact_value"] for m in mentions] == ["2133/5", "1901/5", "232/5"]


def test_no_final_no_completion_from_other_messages_or_tools():
    interpreted = new.interpret_final(None, public_quantity_context())
    assert interpreted["status"] == "UNDETERMINED"
    assert not interpreted["reference_tool_or_sibling_message_used_to_complete_Final"]


def test_old_actual_final_priority_and_ambiguity_not_changed():
    assert score("$46.4M", value="45")["V_quantity"] == "FAIL"
    assert (
        new.interpret_final("$426.6M-$380.2M=$46.4M", public_quantity_context())["status"]
        == "UNDETERMINED"
    )
    result = new.interpret_final("$46.4M", public_quantity_context())
    assert result["status"] == "MAPPED" and result["V_format"] == "FAIL"


def test_original_counterexample_still_fails_in_unmodified_old_evaluator():
    final = {"value": 46.4, "unit": "USD_million", "answer": "$46.4M"}
    assert old.interpret_final(final, public_quantity_context())["status"] == "FAIL"
    assert new.interpret_final(final, public_quantity_context())["status"] == "MAPPED"


@pytest.mark.parametrize(
    "name",
    [
        "number",
        "unique_public_currency",
        "interpret_unit",
        "_physical_key",
        "rounding_tolerance",
        "score_quantity",
    ],
)
def test_unaffected_quantity_algorithms_are_ast_identical(name):
    assert ast.dump(ast.parse(inspect.getsource(getattr(new, name)))) == ast.dump(
        ast.parse(inspect.getsource(getattr(old, name)))
    )


def test_no_inherited_money_context_for_ratio_quantity():
    context = dict(
        public_target_currencies=[],
        relevant_source_currencies=[],
        dimension="ratio",
        target_currency=None,
        target_scale="1/100",
        preferred_unit="percent",
    )
    result = new.score_quantity(
        new.interpret_final({"value": "0.464", "unit": "ratio"}, context), "46.4", context
    )
    assert result["V_quantity"] == "PASS"
    wrong = new.score_quantity(
        new.interpret_final({"value": "46.4", "unit": "USD_million"}, context), "46.4", context
    )
    assert wrong["V_quantity"] == "FAIL"
