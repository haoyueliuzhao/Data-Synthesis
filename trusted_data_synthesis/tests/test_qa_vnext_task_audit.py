"""Controls for the separate source auditor, not task-generation evidence."""

import runpy
from decimal import Decimal
from pathlib import Path

import pytest

AUDITOR = runpy.run_path(str(Path(__file__).parents[1] / "scripts/audit_qa_vnext_task_build.py"))


@pytest.mark.parametrize(
    ("text", "expected"),
    [("$ 1,234", "1234"), ("(834 )", "-834"), ("0", "0"), ("-219.5", "-219.5")],
)
def test_source_amount_preserves_printed_sign_and_scale(text, expected):
    assert AUDITOR["amount"](text) == Decimal(expected)


@pytest.mark.parametrize("text", ["—", "–", "", "N/A", "1.2%", "12 or 13"])
def test_missing_or_ambiguous_amount_is_not_zero(text):
    with pytest.raises(ValueError, match="amount"):
        AUDITOR["amount"](text)


def auditor():
    result = object.__new__(AUDITOR["Audit"])
    result.values = {"prior": Decimal(100), "current": Decimal(130)}
    return result


@pytest.mark.parametrize("reference", ["answer", "future"])
def test_source_replay_rejects_self_or_forward_reference(reference):
    witness = {
        "input_bindings": {"x": "prior"},
        "operator_dag": {
            "operators": [
                {
                    "step_id": "answer",
                    "operator": "difference",
                    "inputs": [{"step": reference}, {"binding": "x"}],
                }
            ],
            "output_step": "answer",
        },
    }
    with pytest.raises(KeyError):
        auditor().execute_arithmetic(witness)


def test_source_replay_rejects_duplicate_step():
    step = {
        "step_id": "answer",
        "operator": "difference",
        "inputs": [{"binding": "p"}, {"binding": "c"}],
    }
    witness = {
        "input_bindings": {"p": "prior", "c": "current"},
        "operator_dag": {"operators": [step, step], "output_step": "answer"},
    }
    with pytest.raises(ValueError, match="unique arithmetic step"):
        auditor().execute_arithmetic(witness)


def test_source_arithmetic_replay_ignores_cached_answer():
    witness = {
        "input_bindings": {"p": "prior", "c": "current"},
        "output": {"value": "PRIVATE_WRONG_ANSWER"},
        "operator_dag": {
            "operators": [
                {
                    "step_id": "delta",
                    "operator": "linear_combination",
                    "inputs": [{"binding": "p"}, {"binding": "c"}],
                    "params": {"coefficients": [-1, 1]},
                },
                {
                    "step_id": "rate",
                    "operator": "ratio_percent",
                    "inputs": [{"step": "delta"}, {"binding": "p"}],
                },
            ],
            "output_step": "rate",
        },
    }
    assert auditor().execute_arithmetic(witness) == (Decimal(30), {"prior", "current"})


def public_example():
    return {
        "question": "Calculate the change in Example's Revenue from the period 2020-01-01 "
        "through 2020-12-31 to the period 2021-01-01 through 2021-12-31. "
        "Express the value in USD millions and round to 2 decimal places.",
        "quantity_contract": {
            "unit": "million USD",
            "decimal_places": 2,
            "rounding": "half away from zero",
        },
        "sources": [
            {
                "concept": "us-gaap:Revenues",
                "record": {"start": "2020-01-01", "end": "2020-12-31", "val": 100000000},
            },
            {
                "concept": "us-gaap:Revenues",
                "record": {"start": "2021-01-01", "end": "2021-12-31", "val": 130000000},
            },
        ],
    }


def test_public_target_uses_only_question_units_and_original_records():
    assert auditor().public_target(public_example()) == Decimal(30)


def test_public_target_rejects_wrong_current_question_period():
    public = public_example()
    public["question"] = public["question"].replace("2021-12-31", "2022-12-31")
    with pytest.raises(ValueError, match="question current endpoint"):
        auditor().public_target(public)
