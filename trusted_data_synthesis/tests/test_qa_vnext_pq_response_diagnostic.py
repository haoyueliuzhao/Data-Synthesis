"""New CPU-only estimand and route controls; no old training controls or 7B loads."""

import copy
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_pq_response_diagnostic import (
    analysis,
    plan,
    scoring,
)

ROOT = Path(__file__).resolve().parents[2]


def synthetic_scores():
    view = plan.read_json(ROOT / plan.PARENT / "preparation/weight_view.json")
    scored = []
    for row in view["rows"]:
        value = 2.0 if row["session_label"] == "T_L1_03" else 3.0
        if row["response_kind"] == "Final":
            value += 1
        scored.append(
            {
                **{
                    k: row[k]
                    for k in (
                        "row_index",
                        "session_label",
                        "response_kind",
                        "target_token_count",
                        "token_reference",
                    )
                },
                "target_nlls": [value] * row["target_token_count"],
            }
        )
    return view, scored


def test_complete_original_package_normalization_and_identity():
    view, rows = synthetic_scores()
    result = scoring.summarize(view, rows)
    package = result["packages"]["T_L1_03"]
    assert package["whole_mean_nll"] == pytest.approx((2 * 191 + 3 * 175) / 366)
    assert result["identity_absolute_error"] < 1e-14
    assert result["common_objectives"]["Q"] - result["common_objectives"]["P"] == pytest.approx(
        result["C"] / 36
    )


def test_split_means_are_not_equal_weight_whole_loss():
    view, rows = synthetic_scores()
    result = scoring.summarize(view, rows)
    package = result["packages"]["T_L1_03"]
    assert package["whole_mean_nll"] != sum(package["split_means"].values()) / 2
    assert package["whole_mean_nll"] == pytest.approx(
        sum(package["split_original_package_contributions"].values())
    )
    for arm in ("P", "Q"):
        assert result["common_objectives"][arm] == pytest.approx(
            sum(
                s["original_package_normalized_objective_contributions"][arm]
                for s in result["splits"].values()
            )
        )


@pytest.mark.parametrize(
    "mutation", ["missing_row", "reorder", "wrong_count", "nan", "negative", "changed_reference"]
)
def test_bad_scoring_rows_rejected(mutation):
    view, rows = synthetic_scores()
    if mutation == "missing_row":
        rows.pop()
    elif mutation == "reorder":
        rows[0], rows[1] = rows[1], rows[0]
    elif mutation == "wrong_count":
        rows[0]["target_nlls"].pop()
    elif mutation == "nan":
        rows[0]["target_nlls"][0] = float("nan")
    elif mutation == "negative":
        rows[0]["target_nlls"][0] = -1
    else:
        rows[0]["token_reference"] = {}
    with pytest.raises(ValueError):
        scoring.summarize(view, rows)


def test_common_target_pair_differences_not_own_arm_objectives():
    base = scoring.summarize(*synthetic_scores())
    models = {variant: copy.deepcopy(base) for variant in plan.VARIANTS}
    for variant in plan.TRAINED:
        if variant.startswith("Q"):
            models[variant]["common_objectives"]["P"] -= 0.2
            models[variant]["common_objectives"]["Q"] -= 0.3
            models[variant]["C"] -= 0.1
    result = analysis.compare_scores(models)
    assert result["negative_delta_C_count"] == 3
    assert all(
        p["Q_minus_P_common_objectives"]["P"] == pytest.approx(-0.2) for p in result["pairs"]
    )
    assert result["no_exponentiation_or_normalized_route_probability"]


def route_fixture():
    audit = {
        "id": "synthetic",
        "first_final_index": 1,
        "raw_messages": {
            "0": "Closing 134 less opening 116; compute 134 - 116.",
            "1": "Final consumes tool:1, increase 18 million.",
        },
        "calculations": [
            {"call_id": "tool:1", "original_expression": "134 - 116", "response_index": 0}
        ],
    }
    component = {
        "structure": "balance_difference",
        "call_id": "tool:1",
        "actual_expression": "134 - 116",
        "source_fact_ids": ["source:t8c1n0", "source:t4c1n0"],
        "public_relation_and_binding_explanation": "closing less opening from original table",
        "evidence": [{"response_index": 0, "quote": audit["raw_messages"]["0"]}],
    }
    review = {
        **analysis.route_template(audit),
        "author": "synthetic reviewer",
        "observed_executed_structure": "balance_difference",
        "components": [component],
        "final_consumed_call_id": "tool:1",
        "explanation": "actual balance execution and Final consumption",
        "final_evidence": [{"response_index": 1, "quote": audit["raw_messages"]["1"]}],
    }
    grade = {
        "complete_verifiable_trajectory": True,
        "original_calculation_quantity": {"call_id": "tool:1"},
    }
    private = {"facts": {k: {} for ids in analysis.EXPECTED_FACTS.values() for k in ids}}
    return audit, review, grade, private


def test_actual_route_requires_valid_trajectory_separately():
    audit, review, grade, private = route_fixture()
    assert analysis.validate_route(audit, review, grade, private)["valid_complete_trajectory_route"]
    grade["complete_verifiable_trajectory"] = False
    result = analysis.validate_route(audit, review, grade, private)
    assert result["observed_executed_structure"] == "balance_difference"
    assert not result["valid_complete_trajectory_route"]


@pytest.mark.parametrize(
    "mutation",
    [
        "mentioned_dual",
        "fake_call",
        "fake_expression",
        "wrong_sources",
        "post_call_only",
        "missing_Final",
        "double_call",
    ],
)
def test_proposed_route_or_number_alone_not_admitted(mutation):
    audit, review, grade, private = route_fixture()
    if mutation == "mentioned_dual":
        review["observed_executed_structure"] = "actual_dual_check"
    elif mutation == "fake_call":
        review["components"][0]["call_id"] = "tool:2"
    elif mutation == "fake_expression":
        review["components"][0]["actual_expression"] = "155 - 141 + 4"
    elif mutation == "wrong_sources":
        review["components"][0]["source_fact_ids"] = ["source:t5c1n0"]
    elif mutation == "post_call_only":
        review["components"][0]["evidence"] = review["final_evidence"]
    elif mutation == "missing_Final":
        audit["first_final_index"] = None
    else:
        review["components"].append(copy.deepcopy(review["components"][0]))
    with pytest.raises(ValueError):
        analysis.validate_route(audit, review, grade, private)


def test_unresolved_is_retained_not_forced_into_two_classes():
    audit, _, grade, private = route_fixture()
    review = {
        **analysis.route_template(audit),
        "author": "synthetic",
        "explanation": "new meaning unresolved",
    }
    result = analysis.validate_route(audit, review, grade, private)
    assert result["observed_executed_structure"] == "unresolved"
    assert not result["valid_complete_trajectory_route"]


def test_registered_workload_and_no_intervention_escalation():
    config = plan.configuration()
    assert config["score_rows_total"] == 7 * 36 == 252
    assert config["score_sequence_positions"] == 7 * 232603
    assert config["score_target_positions"] == 7 * 4793
    assert config["maximum_generation_responses"] == 6 * 32
    assert config["new_training_updates"] == config["adapter_saves"] == config["teacher_calls"] == 0


def test_unchanged_prior_panel_arithmetic_no_model_or_rescoring():
    result = analysis.side_analysis(ROOT)
    assert result["answer_PASS_indicator_changes"] == {"-1": 3, "0": 31, "1": 2}
    assert result["trace_PASS_indicator_changes"] == {"-1": 3, "0": 30, "1": 3}
    assert len(result["changed_pairs"]) == 7
    assert result["transfer_counts"] == {
        "P": {"sessions": 18, "answer_PASS": 18, "trace_PASS": 14},
        "Q": {"sessions": 18, "answer_PASS": 16, "trace_PASS": 12},
    }
