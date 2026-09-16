"""Minimal new analysis controls, not a repeat of financial grading."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
c = importlib.import_module("fixed_kernel_given_sources_closure_20260916")


def test_final_patterns_keep_unit_and_reference_hypotheses_separate():
    public = {"quantity_contract": {"unit": "percent", "decimal_places": 2}}
    tools = [
        (
            1,
            {
                "call_id": "tool:1",
                "tool": "calculate",
                "status": "ok",
                "result": {"exact_value": "10", "unit": "percent"},
            },
        ),
        (
            2,
            {
                "call_id": "tool:2",
                "tool": "calculate",
                "status": "ok",
                "result": {"exact_value": "1000", "unit": "percent"},
            },
        ),
    ]
    final = {"result_id": "tool:1", "value": "10", "unit": "ratio"}
    result = c.final_mismatch(public, tools, final)
    assert result["flags"]["raw_number_equal_but_unit_labels_differ"]
    assert result["flags"]["exact_factor_100_or_inverse"]
    assert result["flags"]["another_numeric_tool_matches_submitted_amount"]
    assert result["matching_other_result_ids"] == ["tool:2"]
    assert final == {"result_id": "tool:1", "value": "10", "unit": "ratio"}


def test_peak_needs_all_primary_periods_and_real_selection_not_calculate_count():
    public = {
        "period_contract": {
            "metric_ids": ["revenue", "net_income"],
            "periods": [{"period_id": str(i)} for i in range(3)],
        }
    }
    tools = [
        (
            i + 1,
            {
                "call_id": f"tool:{i + 1}",
                "tool": "read_source",
                "status": "ok",
                "result": {
                    "exact_value": str(i + 1),
                    "concept": "us-gaap:Revenues",
                    "actual_period": {"period_id": str(i)},
                },
            },
        )
        for i in range(3)
    ]
    tools.append(
        (
            4,
            {
                "call_id": "tool:4",
                "tool": "select_max",
                "status": "ok",
                "result": {
                    "exact_value": "3",
                    "actual_period": {"period_id": "2"},
                    "selection_candidates": [
                        {"result_id": f"tool:{i + 1}", "actual_period": {"period_id": str(i)}}
                        for i in range(3)
                    ],
                },
            },
        )
    )
    tools.append(
        (
            5,
            {
                "call_id": "tool:5",
                "tool": "read_source",
                "status": "ok",
                "result": {
                    "exact_value": "7",
                    "concept": "us-gaap:NetIncomeLoss",
                    "actual_period": {"period_id": "2"},
                },
            },
        )
    )
    tools.append(
        (
            6,
            {
                "call_id": "tool:6",
                "tool": "lookup_selected",
                "status": "ok",
                "result": {
                    "exact_value": "7",
                    "selection_result_id": "tool:4",
                    "source_result_id": "tool:5",
                },
            },
        )
    )
    result = c.peak_chain(public, tools, {"result_id": "tool:6"})
    assert result["all_three_primary_periods_read"] and result["full_primary_selection_observed"]
    assert result["secondary_read_after_selection"] and result["final_names_linked_lookup"]
    assert not c.peak_chain(public, tools[1:], {"result_id": "tool:6"})[
        "full_primary_selection_observed"
    ]


def test_shared_CIK_draws_preserve_zero_paired_difference_and_fixed_rows():
    tasks = [
        {"task_id": f"{group}_{i}", "group": group, "source_cluster": f"CIK{i % 3}"}
        for group in c.GROUPS
        for i in range(60)
    ]
    models = []
    registered = []
    for name in ["unfinetuned_base"] + [f"A_{arm}_{seed}" for seed in c.SEEDS for arm in c.ARMS]:
        models.append(
            {
                "model_key": name,
                "outcomes": [
                    {
                        **row,
                        "financial_valid": int(row["task_id"].split("_")[-1]) % 2 == 0,
                        "terminal": "first_final",
                        "reason": None,
                    }
                    for row in tasks
                ],
            }
        )
        registered.append(
            {"key": name, "original_model_identity": {"training_configuration_id": "synthetic"}}
        )
    result = c.paired_analysis(
        {"models": models}, {"tasks": tasks, "models": registered}, draws=100, seed=3
    )
    assert len(result["pairs"]) == 540
    assert result["transitions"]["plus"] == {"gain": 0, "loss": 0, "unchanged": 540}
    assert result["source_cluster_bootstrap"]["effects"]["plus_minus_alpha0"]["percentile95"] == [
        0.0,
        0.0,
    ]
    assert result["source_cluster_bootstrap"]["same_weights_all_arms_and_seeds"]
