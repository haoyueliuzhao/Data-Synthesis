import pytest
from test_finance_research_datasets import finqa_record, tatqa_context

from trusted_synthesis.finance_research.datasets import adapt_financemath, adapt_finqa, adapt_tatqa
from trusted_synthesis.finance_research.native_metrics import metric_provenance, score_native


def test_pinned_upstream_source_hashes_are_verified():
    provenance = metric_provenance()
    assert provenance["FinQA"]["revision"] == "0f16e2867befa6840783e58be38c9efb9229d742"
    assert provenance["TAT-QA"]["revision"] == "870accc41953dcde885aabeb963d94aabdc0fbc3"


def test_finqa_answer_alone_is_not_official_execution_accuracy():
    bundle = adapt_finqa([finqa_record()], split="test", revision="fixture-v1")[0]
    score = score_native(bundle, "6")
    assert score["status"] == "unsupported"
    assert score["native"]["execution_accuracy"] is None
    assert score["derived"]["exact_final_answer_match"] == 1


def test_finqa_program_uses_upstream_execution_and_symbolic_equivalence():
    pytest.importorskip("sympy")
    bundle = adapt_finqa([finqa_record()], split="test", revision="fixture-v1")[0]
    right = score_native(bundle, "999", program="subtract(8, 2)")
    assert right["native"] == {"execution_accuracy": 1, "program_accuracy": 1}
    assert right["derived"]["exact_final_answer_match"] == 0
    wrong = score_native(bundle, "6", program="add(8, 2)")
    assert wrong["native"] == {"execution_accuracy": 0, "program_accuracy": 0}


def test_finqa_malformed_program_gets_invalid_prediction_not_unsupported():
    bundle = adapt_finqa([finqa_record()], split="test", revision="fixture-v1")[0]
    score = score_native(bundle, "6", program=["subtract(", "8", "2", ")"])
    assert score["status"] == "invalid_prediction"
    assert score["native"]["execution_accuracy"] == 0


@pytest.mark.parametrize(
    "answer_type,answer,gold_scale,prediction,scale,em,f1",
    [
        ("multi-span", ["China", "USA"], "", ["USA", "China"], "", 1, 1),
        ("multi-span", ["China", "USA"], "", ["China"], "", 0, 0.67),
        ("arithmetic", 123.2, "million", 123.2, "thousand", 0, 0),
        ("arithmetic", 123.2, "million", 123200000, "", 1, 1),
        ("arithmetic", 22.12, "percent", 0.2212, "", 1, 1),
        ("count", 5, "", 5, "", 1, 1),
        ("span", ["a revenue increase"], "", "revenue increase", "", 1, 1),
    ],
)
def test_tatqa_official_type_scale_and_multispan_semantics(
    answer_type, answer, gold_scale, prediction, scale, em, f1
):
    pytest.importorskip("scipy")
    bundle = adapt_tatqa(
        [tatqa_context(answer_type, answer, gold_scale)], split="test", revision="fixture-v1"
    )[0]
    score = score_native(bundle, prediction, scale=scale)
    assert score["status"] == "scored"
    assert score["native"]["exact_match"] == em
    assert score["native"]["f1"] == f1
    assert "CompletePass" not in score["native"]


def test_financemath_metric_is_explicitly_not_yet_bound():
    raw = {
        "question_id": "synthetic",
        "question": "Compute.",
        "tables": [],
        "python_solution": "answer = 3",
        "ground_truth": 3,
        "topic": "fixture",
    }
    bundle = adapt_financemath([raw], split="test", revision="fixture-v1")[0]
    score = score_native(bundle, 3)
    assert score["status"] == "unsupported"
    assert score["native"]["numeric_accuracy"] is None
    assert score["derived"]["exact_final_answer_match"] == 1
