"""Synthetic immutable reports only: no real sessions, materials or models."""

import copy
from fractions import Fraction

import numpy as np
import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_student import analysis
from trusted_synthesis.experiments.finance_qa_vnext_basis_student.protocol import record

BINDING = {key: "synthetic:" + key for key in analysis.BINDING_FIELDS}
ARMS, SEEDS = analysis.design.ARMS, analysis.design.SEEDS


def tasks(split, *, clusters="by_group"):
    n = 60 if split == "dev" else 240
    result = []
    for g, group in enumerate(analysis.GROUPS):
        for index in range(n):
            cluster = g if clusters == "by_group" else index % 7
            result.append(
                {
                    "task_id": f"{split}-{g}-{index:03d}",
                    "group": group,
                    "source_cluster": f"cik:{cluster:010d}",
                    "surface_version_id": f"surface-{split}-{g}-{index}",
                    "public_messages_sha256": f"{g + index:064x}",
                }
            )
    return result


def training(pool, arms):
    return [
        record(
            "training_report",
            **BINDING,
            pool=pool,
            arm=arm,
            seed=seed,
            checkpoint_id=f"synthetic-adapter:{pool}-{arm}-{seed}",
            status="COMPLETE_FINAL_CHECKPOINT",
            actual_complete=True,
            final_adapter={
                "path": "synthetic-final.safetensors",
                "bytes": 123,
                "sha256": "a" * 64,
                "parameter_digest": f"synthetic-adapter:{pool}-{arm}-{seed}",
            },
            final_adapter_restored_identity_verified=True,
        )
        for arm in arms
        for seed in SEEDS
    ]


def scores(train, fixed, split, positive):
    result = []
    for model in train:
        outcomes = []
        for task in fixed:
            index = int(task["task_id"].rsplit("-", 1)[1])
            outcomes.append(
                {
                    **task,
                    "financial_valid": index < positive(model, task),
                    "full_mapping_status": "PENDING",
                    "actual_method": "unknown",
                    "NLL": 999 if model["arm"] == "plus" else -999,
                }
            )
        result.append(
            record(
                "evaluation_report",
                **BINDING,
                pool=model["pool"],
                arm=model["arm"],
                seed=model["seed"],
                split=split,
                checkpoint_id=model["checkpoint_id"],
                training_report_id=model["id"],
                status="COMPLETE_FIXED_EVALUATION",
                actual_complete=True,
                outcomes=outcomes,
            )
        )
    return result


def rerecord(value, **changes):
    body = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    return record(value["schema_version"].rsplit(".", 1)[1], **{**body, **changes})


def decision(positive=None):
    train, fixed = training("A", ARMS), tasks("dev")
    evaluate = scores(
        train, fixed, "dev", positive or (lambda model, _: 31 if model["arm"] == "plus" else 30)
    )
    result = analysis.select_actual_direction(train, evaluate, binding=BINDING, dev_tasks=fixed)
    return result, train, evaluate, fixed


def confirmation(*, a=150, b=120, clusters="by_group"):
    selected, a_train, _, _ = decision()
    train = [*a_train, *training("B", ("alpha0", "plus"))]
    fixed = tasks("confirm", clusters=clusters)
    evaluated = [row for row in train if row["arm"] != "minus"]
    evaluate = scores(
        evaluated,
        fixed,
        "confirm",
        lambda model, _: 120 if model["arm"] == "alpha0" else a if model["pool"] == "A" else b,
    )
    return selected, train, evaluate, fixed


def test_actual_direction_binds_all_nine_reports_and_fixed_1620_financial_outcomes():
    result, train, evaluated, fixed = decision()
    assert result["selected_arm"] == "plus"
    assert result["actual_complete"] and not result["prospective_not_executed"]
    assert result["observed_A_training_runs"] == 9 and result["observed_A_dev_sessions"] == 1620
    assert set(result["training_report_ids"]) == {row["id"] for row in train}
    assert set(result["dev_score_report_ids"]) == {row["id"] for row in evaluated}
    assert result["paired_mean_gain"]["plus"] == "1/60"
    assert result["mean_utility_by_arm"]["plus"]["exact"] == "31/60"
    assert (
        result["planned_B_training_runs"] == 6 and result["planned_confirmation_sessions"] == 8640
    )
    assert all(
        row["group_denominators"] == dict.fromkeys(analysis.GROUPS, 60)
        for row in result["utility_summaries"]
    )
    # Pending fine mapping and a deliberately unfavorable NLL do not change financial utility.
    assert all(row["full_mapping_status"] == "PENDING" for row in evaluated[3]["outcomes"])
    assert len(fixed) == result["fixed_dev_unique_tasks"] == 180


def test_mean_positive_with_two_negative_seeds_and_positive_tie_prefers_plus():
    def positive(model, task):
        if model["arm"] == "alpha0":
            return 30
        return 33 if model["seed"] == 11 else 29

    result, *_ = decision(positive)
    assert result["selected_arm"] == "plus"
    assert result["paired_mean_gain"]["plus"] == result["paired_mean_gain"]["minus"] == "1/180"
    assert not result["every_seed_positive_required"]


def test_nonpositive_candidate_retains_baseline_and_rejects_confirmation():
    result, train, *_ = decision(lambda model, _: 30 if model["arm"] != "minus" else 29)
    assert result["selected_arm"] == "alpha0" and result["status"] == "STOP_RETAIN_BASELINE"
    assert result["planned_B_arms"] == [] and result["planned_B_dev_sessions"] == 0
    assert result["planned_B_training_runs"] == result["planned_confirmation_sessions"] == 0
    with pytest.raises(ValueError, match="unique_positive_direction"):
        analysis.confirm_actual(result, train, [], binding=BINDING, confirm_tasks=tasks("confirm"))


@pytest.mark.parametrize(
    "defect",
    [
        "missing_train",
        "incomplete_train",
        "prospective",
        "wrong_split",
        "missing_outcome",
        "duplicate",
        "wrong_binding",
        "wrong_checkpoint",
        "wrong_source",
        "numeric_valid",
        "unhashed_edit",
    ],
)
def test_actual_selection_rejects_unbound_incomplete_or_reclassified_reports(defect):
    _, train, evaluate, fixed = decision()
    if defect == "missing_train":
        train.pop()
    elif defect == "incomplete_train":
        train[0] = rerecord(train[0], actual_complete=False)
    elif defect == "prospective":
        train[0] = analysis.design.select_direction(
            {arm: {seed: 0 for seed in SEEDS} for arm in ARMS}
        )
    elif defect == "wrong_split":
        evaluate[0] = rerecord(evaluate[0], split="confirm")
    elif defect == "wrong_binding":
        evaluate[0] = rerecord(evaluate[0], decoder_config_id="other")
    elif defect == "wrong_checkpoint":
        evaluate[0] = rerecord(evaluate[0], checkpoint_id="other")
    elif defect == "unhashed_edit":
        evaluate[0]["outcomes"][0]["financial_valid"] = False
    else:
        outcomes = copy.deepcopy(evaluate[0]["outcomes"])
        if defect == "missing_outcome":
            outcomes.pop()
        elif defect == "duplicate":
            outcomes[-1] = outcomes[0]
        elif defect == "wrong_source":
            outcomes[0]["source_cluster"] = "cik:9999999999"
        elif defect == "numeric_valid":
            outcomes[0]["financial_valid"] = 1
        evaluate[0] = rerecord(evaluate[0], outcomes=outcomes)
    with pytest.raises(ValueError):
        analysis.select_actual_direction(train, evaluate, binding=BINDING, dev_tasks=fixed)


def test_zero_B_not_confirmed_despite_positive_A_and_complete_8640_denominator():
    chosen, train, reports, fixed = confirmation()
    result = analysis.confirm_actual(chosen, train, reports, binding=BINDING, confirm_tasks=fixed)
    assert result["status"] == "NOT_CONFIRMED" and result["primary_pool"] == "B"
    assert result["pools"]["B"]["zero_in_interval"]
    assert result["pools"]["A"]["strictly_positive_interval"]
    assert result["observed_confirmation_sessions"] == 8640
    assert result["fixed_confirm_unique_tasks"] == 720
    assert result["bootstrap"]["replicates"] == 10000
    assert result["bootstrap"]["empty_group_rejected_draws"] > 0
    assert (
        result["bootstrap"]["attempts"] == 10000 + result["bootstrap"]["empty_group_rejected_draws"]
    )
    assert result["diagnostics"]["unique_CIK_clusters"] == 3


@pytest.mark.parametrize(
    "b,positive,covers_five",
    [(126, True, False), (132, True, True), (144, True, True), (120, False, False)],
)
def test_B_primary_interval_and_five_percentage_point_claims(b, positive, covers_five):
    chosen, train, reports, fixed = confirmation(b=b)
    result = analysis.confirm_actual(chosen, train, reports, binding=BINDING, confirm_tasks=fixed)
    primary = result["pools"]["B"]
    assert primary["strictly_positive_interval"] is positive
    assert primary["cannot_exclude_benefit_at_least_five_pp"] is covers_five
    assert primary["paired_seed_mean_gain"]["exact"] == str(Fraction(b - 120, 240))
    if b == 132:
        assert primary["five_pp_in_interval"]


def test_bootstrap_pairing_and_sorted_input_order_invariance():
    chosen, train, reports, fixed = confirmation(a=132, b=132, clusters="shared")
    first = analysis.confirm_actual(chosen, train, reports, binding=BINDING, confirm_tasks=fixed)
    reversed_reports = [
        rerecord(row, outcomes=list(reversed(row["outcomes"]))) for row in reversed(reports)
    ]
    second = analysis.confirm_actual(
        chosen,
        list(reversed(train)),
        reversed_reports,
        binding=BINDING,
        confirm_tasks=list(reversed(fixed)),
    )
    assert first["pools"] == second["pools"]
    assert first["bootstrap"] == second["bootstrap"]
    assert first["pools"]["A"]["lower"] == first["pools"]["B"]["lower"]
    assert first["pools"]["A"]["upper"] == first["pools"]["B"]["upper"]
    assert first["bootstrap"]["attempts"] == 10000


@pytest.mark.parametrize(
    "defect", ["missing_B_training", "B_dev", "runner_up", "missing_session", "other_A_checkpoint"]
)
def test_confirmation_rejects_partial_cross_product_or_post_selection_changes(defect):
    chosen, train, reports, fixed = confirmation()
    if defect == "missing_B_training":
        train.pop()
    elif defect == "B_dev":
        reports[-1] = rerecord(reports[-1], split="dev")
    elif defect == "runner_up":
        chosen = rerecord(chosen, selected_arm="minus")
    elif defect == "missing_session":
        reports[0] = rerecord(reports[0], outcomes=reports[0]["outcomes"][:-1])
    elif defect == "other_A_checkpoint":
        train[0] = rerecord(train[0], checkpoint_id="other")
    with pytest.raises(ValueError):
        analysis.confirm_actual(chosen, train, reports, binding=BINDING, confirm_tasks=fixed)


def test_task_weighting_is_not_equal_company_weighting_and_failure_denominator_is_fixed():
    fixed = tasks("dev")
    for row in fixed:
        row["source_cluster"] = (
            "cik:0000000000" if int(row["task_id"].rsplit("-", 1)[1]) < 59 else "cik:0000000001"
        )
    train = training("A", ARMS)
    reports = scores(train, fixed, "dev", lambda model, _: 59 if model["arm"] == "plus" else 0)
    result = analysis.select_actual_direction(train, reports, binding=BINDING, dev_tasks=fixed)
    assert result["mean_utility_by_arm"]["plus"]["exact"] == "59/60"  # Not company mean 1/2.


def test_fixed_bootstrap_exhaustion_refuses_partial_interval(monkeypatch):
    chosen, train, reports, fixed = confirmation()

    class EmptyGroupDraws:
        def multinomial(self, n, pvals, size):
            weights = np.zeros((size, len(pvals)), dtype=int)
            weights[:, 0] = n
            return weights

    monkeypatch.setattr(analysis.np.random, "Generator", lambda *_: EmptyGroupDraws())
    with pytest.raises(ValueError, match="attempt_limit_no_partial_interval"):
        analysis.confirm_actual(chosen, train, reports, binding=BINDING, confirm_tasks=fixed)


def test_protocol_is_fixed_before_results_and_no_randomness_or_denominator_tuning():
    value = analysis.policy()
    assert value["bootstrap_seed"] == 20260912
    assert value["bootstrap_replicates"] == 10000
    assert value["bootstrap_max_attempts"] == 1000000
    assert value["B_development_sessions"] == 0
    assert value["primary_confirmation_pool"] == "B"
    assert not value["intervals_estimate_all_training_randomness"]


def test_bootstrap_uses_cluster_multiplicity_times_tasks_not_cluster_average(monkeypatch):
    chosen, train, _, fixed = confirmation()
    for row in fixed:
        row["source_cluster"] = (
            "cik:0000000000" if int(row["task_id"].rsplit("-", 1)[1]) < 239 else "cik:0000000001"
        )
    reports = scores(
        [row for row in train if row["arm"] != "minus"],
        fixed,
        "confirm",
        lambda model, _: 239 if model["arm"] == "alpha0" else 240,
    )

    class OneOfEachCluster:
        def multinomial(self, n, pvals, size):
            assert n == 2 and len(pvals) == 2
            return np.ones((size, 2), dtype=int)

    monkeypatch.setattr(analysis.np.random, "Generator", lambda *_: OneOfEachCluster())
    result = analysis.confirm_actual(chosen, train, reports, binding=BINDING, confirm_tasks=fixed)
    for pool in ("A", "B"):
        interval = result["pools"][pool]
        assert interval["lower"] == interval["upper"] == round(1 / 240, 15)
        assert interval["paired_seed_mean_gain"]["exact"] == "1/240"
        assert interval["lower"] != 0.5  # The forbidden equal-company mean.


@pytest.mark.parametrize("defect", ["no_restore", "wrong_digest", "no_file"])
def test_actual_selection_requires_saved_and_restored_adapter_evidence(defect):
    _, train, evaluate, fixed = decision()
    if defect == "no_restore":
        train[0] = rerecord(train[0], final_adapter_restored_identity_verified=False)
    elif defect == "wrong_digest":
        train[0] = rerecord(
            train[0], final_adapter={**train[0]["final_adapter"], "parameter_digest": "other"}
        )
    else:
        train[0] = rerecord(train[0], final_adapter={})
    with pytest.raises(ValueError, match="saved_and_restored"):
        analysis.select_actual_direction(train, evaluate, binding=BINDING, dev_tasks=fixed)
