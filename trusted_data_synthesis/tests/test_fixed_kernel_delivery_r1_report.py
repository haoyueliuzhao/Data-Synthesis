"""Small pure CPU controls; no raw-session scan, scoring, or model loading."""

import importlib.util
import sys
from pathlib import Path

import pytest


def module():
    directory = Path(__file__).resolve().parents[1] / "scripts"
    name = "fixed_kernel_delivery_r1_report_20260915"
    sys.path.insert(0, str(directory))
    try:
        spec = importlib.util.spec_from_file_location(name, directory / (name + ".py"))
        value = importlib.util.module_from_spec(spec)
        sys.modules[name] = value
        spec.loader.exec_module(value)
        return value
    finally:
        sys.path.pop(0)


def test_paired_doc_delta_keeps_base_separate_and_requires_complete_matrix():
    report = module()
    tasks = ["task_one", "task_two", "task_three"]
    models = [
        {"key": "ft", "model_kind": "finetuned", "arm": "alpha0", "seed": 11},
        {"key": "base", "model_kind": "unfinetuned_base"},
    ]
    rows = []
    for model in models:
        for condition in report.CONDITIONS:
            for task in tasks:
                qualified = (model["key"], condition, task) in {
                    ("ft", "original", "task_one"),
                    ("base", "gamma_doc", "task_two"),
                }
                stages = dict.fromkeys(report.STAGE_DEFINITIONS, False)
                stages.update(financial_qualified=qualified, runtime_recognized_final=qualified)
                rows.append(
                    dict(
                        model_key=model["key"],
                        model_kind=model["model_kind"],
                        condition=condition,
                        task_id=task,
                        financial_valid=qualified,
                        stages=stages,
                        reason="qualified" if qualified else "no_final",
                        runtime_terminal="first_final"
                        if qualified
                        else "response_budget_exhausted",
                        quantity_status="CORRECT" if qualified else "UNDETERMINED",
                        support_status="SUPPORTED" if qualified else "UNDETERMINED",
                    )
                )
    result = report.summarize_matrix(rows, tasks, models)
    assert result["unique_development_tasks"] == 3
    assert result["complete_sessions"] == 12
    assert result["paired_model_task_comparisons"] == 6
    by_model = {row["model_key"]: row for row in result["model_rows"]}
    assert by_model["ft"]["paired_mean_delta_Q"] == -1 / 3
    assert by_model["base"]["paired_mean_delta_Q"] == 1 / 3
    assert by_model["ft"]["transition_counts"] == {"1->0": 1, "0->0": 2}
    populations = result["separate_model_kind_populations"]
    assert populations["finetuned"]["gamma_doc"]["sessions"] == 3
    assert populations["finetuned"]["gamma_doc"]["financial_qualified"] == 0
    assert populations["unfinetuned_base"]["gamma_doc"]["financial_qualified"] == 1
    assert result["base_excluded_from_alpha0_plus_minus_denominators"] is True
    with pytest.raises(ValueError, match="complete_paired_matrix"):
        report.summarize_matrix(rows[:-1], tasks, models)


def test_prefix_semantics_uses_nullable_denominators_not_exact_text_or_autonomous_Q():
    report = module()
    rows = [
        dict(
            model_kind="finetuned",
            boundary="calculate",
            prediction={"exact_reference_response_match": False},
            semantics={"status": "CALCULATION_SEMANTIC_PASS", "semantic_calculation_success": True},
        ),
        dict(
            model_kind="finetuned",
            boundary="calculate",
            prediction={"exact_reference_response_match": True},
            semantics={
                "status": "TOOL_RESPONSE_SEMANTIC_FAIL_OR_UNDETERMINED",
                "semantic_calculation_success": None,
            },
        ),
        dict(
            model_kind="finetuned",
            boundary="final",
            prediction={"exact_reference_response_match": False},
            semantics={
                "status": "CONTINUED_TOOL_NOT_IMMEDIATE_FINAL",
                "immediate_final": False,
                "semantic_immediate_final_success": False,
            },
        ),
    ]
    result = report.summarize_prefixes(rows)
    groups = result["by_model_kind_and_boundary"]["finetuned"]
    values = groups["calculate"]["components"]["semantic_calculation_success"]
    assert values == {
        "true": 1,
        "false": 0,
        "not_applicable_or_undetermined": 1,
        "determined_denominator": 1,
    }
    assert groups["calculate"]["exact_reference_text_matches_descriptive_only"] == 1
    assert groups["final"]["status_counts"] == {"CONTINUED_TOOL_NOT_IMMEDIATE_FINAL": 1}
    assert result["exact_text_match_is_not_semantic_pass_criterion"] is True
    assert result["financial_qualification_score"] is None
    assert result["autonomous_task_success_claimed"] is False
    assert result["continuing_a_tool_does_not_prove_never_final"] is True
