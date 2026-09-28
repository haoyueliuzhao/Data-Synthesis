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


def _profile_score(prediction="6", program="subtract(8, 2)", **kwargs):
    bundle = kwargs.pop(
        "bundle", adapt_finqa([finqa_record()], split="test", revision="fixture-v1")[0]
    )
    return score_native(
        bundle,
        prediction,
        program=program,
        submission_profile="finqa_program_v1",
        stop_reason=kwargs.pop("stop_reason", "final_answer"),
        all_provider_calls_settled=kwargs.pop("all_provider_calls_settled", True),
        **kwargs,
    )


@pytest.mark.parametrize(
    "program",
    [
        None,
        "",
        "bad(8, 2)",
        "subtract(8,2)",
        ["subtract(", "8", "2", ")"],
        ["EOF"],
        ["add(", "8", 2, ")", "EOF"],
        "divide(8, 0)",
        "add(#0, 1)",
        "add(nan, 1)",
        "add(inf, 1)",
    ],
)
def test_profile_missing_and_invalid_programs_are_model_zeros(program):
    pytest.importorskip("sympy")
    score = _profile_score(program=program)
    assert score["status"] == "invalid_prediction"
    assert score["native"] == {"execution_accuracy": 0, "program_accuracy": 0}
    assert score["final_program_consistency"]["match"] is None
    assert score["missing_prediction_policy"].endswith("_v1")


@pytest.mark.parametrize(
    "stop_reason",
    [
        "max_steps",
        "no_tool_call",
        "multiple_tool_calls",
        "context_exceeded",
    ],
)
def test_profile_normal_no_final_is_zero_even_if_stale_prediction_was_passed(stop_reason):
    score = _profile_score(stop_reason=stop_reason)
    assert score["native"] == {"execution_accuracy": 0, "program_accuracy": 0}
    assert "no valid explicit Final" in score["reason"]


@pytest.mark.parametrize(
    "settled,stop_reason",
    [
        (False, "final_answer"),
        (None, "final_answer"),
        (True, "provider_error"),
        (True, "receipt_error"),
        (True, None),
        (True, "future_unknown_failure"),
    ],
)
def test_profile_unsettled_or_infrastructure_terminal_is_unknown(settled, stop_reason):
    score = _profile_score(all_provider_calls_settled=settled, stop_reason=stop_reason)
    assert score["status"] == "unknown"
    assert score["native"] == {"execution_accuracy": None, "program_accuracy": None}


def test_profile_final_program_consistency_is_not_native_accuracy_or_trajectory_support():
    right_program_wrong_final = _profile_score(prediction="999")
    assert right_program_wrong_final["native"] == {"execution_accuracy": 1, "program_accuracy": 1}
    consistency = right_program_wrong_final["final_program_consistency"]
    assert consistency["status"] == "inconsistent"
    assert consistency["program_execution_result"] == 6
    assert consistency["match"] == 0
    same_wrong_program_and_final = _profile_score(prediction="10", program="add(8, 2)")
    assert same_wrong_program_and_final["native"]["execution_accuracy"] == 0
    assert same_wrong_program_and_final["final_program_consistency"]["match"] == 1
    assert "not actual tool-trajectory CompletePass" in consistency["definition"]


@pytest.mark.parametrize("program", [None, "subtract(8, 2)"])
def test_profile_reference_contradiction_is_never_model_zero(program):
    raw = finqa_record()
    raw["qa"]["exe_ans"] = 999
    bundle = adapt_finqa([raw], split="test", revision="fixture-v1")[0]
    score = _profile_score(program=program, bundle=bundle)
    assert score["status"] == "reference_inconsistency"
    assert score["native"] == {"execution_accuracy": None, "program_accuracy": None}


def test_profile_missing_scorer_dependency_is_not_missing_prediction_zero(monkeypatch):
    from trusted_synthesis.finance_research import native_metrics

    def missing():
        raise ImportError("fixture missing sympy", name="sympy")

    monkeypatch.setattr(native_metrics, "_load_finqa_scorer", missing)
    score = _profile_score(program=None)
    assert score["status"] == "unsupported"
    assert score["native"]["execution_accuracy"] is None
    assert "sympy" in score["reason"]


def test_profile_metric_binding_error_is_unknown_not_zero(monkeypatch):
    from trusted_synthesis.finance_research import native_metrics

    def changed_source():
        raise RuntimeError("fixture modified native scorer")

    monkeypatch.setattr(native_metrics, "metric_provenance", changed_source)
    score = _profile_score(program=None)
    assert score["status"] == "unknown"
    assert score["native"]["execution_accuracy"] is None


def test_profile_accepts_explicit_eof_token_arrays_and_chained_steps():
    score = _profile_score(program=["subtract(", "8", "2", ")", "EOF"])
    assert score["native"] == {"execution_accuracy": 1, "program_accuracy": 1}
    chained = _profile_score(program="subtract(8, 2), add(#0, const_0)")
    assert chained["native"]["execution_accuracy"] == 1
    assert chained["final_program_consistency"]["match"] == 1


def test_unregistered_scoring_profile_is_rejected():
    bundle = adapt_finqa([finqa_record()], split="test", revision="fixture-v1")[0]
    with pytest.raises(ValueError, match="unknown submission profile"):
        score_native(bundle, 6, submission_profile="unregistered")


@pytest.mark.parametrize(
    "program,answer",
    [
        ("table_sum(2020, none)", 8),
        ("multiply(50%, const_100)", 50),
        ("greater(8, 2)", "yes"),
    ],
)
def test_profile_uses_official_table_constant_percent_and_comparison_semantics(program, answer):
    raw = finqa_record()
    raw["qa"].update(program=program, exe_ans=answer)
    bundle = adapt_finqa([raw], split="test", revision="fixture-v1")[0]
    score = _profile_score(prediction=answer, program=program, bundle=bundle)
    assert score["native"] == {"execution_accuracy": 1, "program_accuracy": 1}
    assert score["final_program_consistency"]["match"] == 1
