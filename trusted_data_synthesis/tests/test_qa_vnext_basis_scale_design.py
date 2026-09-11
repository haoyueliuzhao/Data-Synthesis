"""Pure prospective-design controls: exact Fractions, synthetic losses and IDs only."""

import copy
import hashlib
import json
from collections import Counter
from fractions import Fraction as F

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation import design


def ready_lists(k=40, control=None):
    return {
        group: [f"{group}:{index:03d}" for index in range(2 * k if control is None else control)]
        if group == design.CONTROL_GROUP
        else [f"{group}:{index:03d}" for index in range(k)]
        for group in design.GROUPS
    }


def assert_prospective_identity(value):
    assert value["prospective_not_executed"] is True
    body = {key: item for key, item in value.items() if key != "id"}
    encoded = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    kind, separator, digest = value["id"].partition(":")
    assert separator == ":" and digest == hashlib.sha256(encoded).hexdigest()
    assert value["schema_version"] == "basis_scale_preparation.v1." + kind


def synthetic_task(group, index):
    methods = ("control",) if group == "control" else ("endpoint", "movement")
    return {
        "task_id": f"{group}:{index:03d}",
        "group": group,
        "package_mean_losses": {
            method: [
                F((index + 1) * (position + 3) + method_index * 13, position + 2)
                for position in range(8)
            ]
            for method_index, method in enumerate(methods)
        },
    }


def five_tasks():
    return [synthetic_task(group, index) for index, group in enumerate(design.DUAL_GROUPS)] + [
        synthetic_task("control", 10),
        synthetic_task("control", 11),
    ]


def test_candidate_and_evaluation_caps_are_unexecuted_and_do_not_choose_a_fee():
    result = design.budget_design()
    assert_prospective_identity(result)
    assert result["candidate_dual_tasks"] == 160
    assert result["candidate_control_tasks"] == 100
    assert result["candidate_tasks_total"] == 260
    assert result["maximum_Teacher_sessions_per_pool"] == 12_640
    assert result["maximum_Teacher_sessions"] == 25_280
    assert result["maximum_Teacher_requests"] == 808_960
    assert result["maximum_A_training_runs"] == 9
    assert result["maximum_B_training_runs"] == 6
    assert result["maximum_total_training_runs"] == 15
    assert result["maximum_development_sessions"] == 1_620
    assert result["maximum_confirmation_sessions"] == 8_640
    assert result["maximum_Student_sessions"] == 10_260
    assert result["maximum_Student_generation_requests_if_32_per_session"] == 328_320
    assert result["B_development_sessions"] == 0
    assert result["primary_confirmation_pool"] == "B"
    assert result["auxiliary_confirmation_pool"] == "A"
    assert result["total_Teacher_token_stop_limit"] is None
    assert result["total_provider_cost_stop_limit"] is None
    assert result["generation_or_training_authorized_by_this_record"] is False
    assert result["old_27_package_five_arm_protocol_authorized"] is False
    assert result["resources_are_upper_caps_not_consumption"] is True
    assert "full annual-flow component differences" in result["annual_flow_components_scope"]
    assert result["B0_same_task_greedy_auxiliary_NLL_or_heldout_evaluation_sessions"] == 0
    assert result["evaluation_guidance_directives_included"] is False
    assert result["A_B_fine_class_mixtures_forced_equal"] is False
    assert result["token_length_preference_or_post_result_limit_change_allowed"] is False


@pytest.mark.parametrize(
    ("n", "dual", "control", "train", "heldout", "updates"),
    [
        (180, 108, 72, 2304, 576, 360),
        (185, 111, 74, 2368, 592, 370),
        (190, 114, 76, 2432, 608, 380),
        (195, 117, 78, 2496, 624, 390),
        (200, 120, 80, 2560, 640, 400),
    ],
)
def test_population_recomputes_all_counts_when_N_changes(n, dual, control, train, heldout, updates):
    result = design.population(n)
    assert_prospective_identity(result)
    assert (result["dual_tasks"], result["control_tasks"]) == (dual, control)
    assert result["train_packages_per_pool"] == train
    assert result["heldout_packages_per_pool"] == heldout
    assert result["total_packages_per_pool"] == 16 * n
    assert result["optimizer_updates_per_run"] == updates == 2 * n
    assert result["updates_per_epoch"] == n // 5
    assert result["maximum_optimizer_updates_A_and_B_fifteen_runs"] == 30 * n
    assert result["whole_training_package_visits_per_run"] == 10 * train
    assert result["global_mass_moved_from_baseline"] == "1/10"
    assert result["task_marginal"] == str(F(1, n))
    assert result["tasks_by_group"] == {
        **{group: n // 5 for group in design.DUAL_GROUPS},
        "control": 2 * n // 5,
    }
    assert result["actual_token_budgets"] is None
    assert result["pools_combined_for_training"] is False
    assert result["heldout_training_NLL_greedy_or_direction_selection_allowed"] is False
    assert result["training_population_materialized"] is False


@pytest.mark.parametrize("n", [True, 179, 181, 199, 201, 200.0, "200"])
def test_nonregistered_population_or_noninteger_identity_is_rejected(n):
    with pytest.raises(ValueError, match="design.N_180_to_200_step_five"):
        design.population(n)


@pytest.mark.parametrize("n", design.ALLOWED_POPULATIONS)
@pytest.mark.parametrize("arm", design.ARMS)
def test_exact_global_package_mass_and_unchanged_task_marginals(n, arm):
    expected = {
        "alpha0": (F(1, 2), F(1, 2)),
        "plus": (F(1, 3), F(2, 3)),
        "minus": (F(2, 3), F(1, 3)),
    }[arm]
    for group in design.DUAL_GROUPS:
        masses = [design.package_mass(n, arm, group, method) for method in design.METHODS]
        assert masses == [alpha / (8 * n) for alpha in expected]
        assert 8 * sum(masses) == F(1, n)
    control = design.package_mass(n, arm, "control", None)
    assert control == design.package_mass(n, arm, "control", "control") == F(1, 8 * n)
    total = (3 * n // 5) * 8 * sum(
        design.package_mass(n, arm, design.DUAL_GROUPS[0], method) for method in design.METHODS
    ) + (2 * n // 5) * 8 * control
    assert total == 1
    assert (3 * n // 5) * 8 * (
        design.package_mass(n, "plus", design.DUAL_GROUPS[0], "movement")
        - design.package_mass(n, "alpha0", design.DUAL_GROUPS[0], "movement")
    ) == F(1, 10)


def test_N_200_matches_registered_masses_and_update_coefficients():
    group = design.DUAL_GROUPS[0]
    assert design.package_mass(200, "alpha0", group, "endpoint") == F(1, 3200)
    assert design.package_mass(200, "plus", group, "endpoint") == F(1, 4800)
    assert design.package_mass(200, "plus", group, "movement") == F(1, 2400)
    assert design.package_mass(200, "alpha0", "control", None) == F(1, 1600)
    for length in (1, 17, 33_000):
        assert design.update_token_coefficient("alpha0", group, "endpoint", length) == F(
            1, 80 * length
        )
        assert design.update_token_coefficient("plus", group, "endpoint", length) == F(
            1, 120 * length
        )
        assert design.update_token_coefficient("plus", group, "movement", length) == F(
            1, 60 * length
        )
        assert design.update_token_coefficient("minus", group, "endpoint", length) == F(
            1, 60 * length
        )
        assert design.update_token_coefficient("alpha0", "control", None, length) == F(
            1, 40 * length
        )
        for n in design.ALLOWED_POPULATIONS:
            assert (
                design.update_token_coefficient("plus", group, "movement", length)
                == design.package_mass(n, "plus", group, "movement") * F(n, 5) / length
            )


@pytest.mark.parametrize("length", [0, -1, True, 2.0, "2"])
def test_invalid_whole_package_token_denominators_reject(length):
    with pytest.raises(ValueError, match="design.positive_whole_package_target_token_count"):
        design.update_token_coefficient("alpha0", "control", None, length)


@pytest.mark.parametrize(
    ("arm", "group", "method"),
    [
        ("P", "control", None),
        ("alpha0", "unknown", None),
        ("plus", "control", "movement"),
        ("minus", design.DUAL_GROUPS[0], "control"),
        ("alpha0", design.DUAL_GROUPS[0], None),
    ],
)
def test_no_old_arms_unknown_groups_or_guidance_label_for_controls(arm, group, method):
    with pytest.raises(ValueError):
        design.package_mass(200, arm, group, method)


def test_whole_package_mean_preserves_unequal_rows_and_split_merge_invariance():
    mean = design.package_mean_loss([1, 17], [1, 9])
    assert mean == F(9, 5)
    assert mean != (F(1, 1) + F(17, 9)) / 2
    assert mean == design.package_mean_loss([1, 8, 9], [1, 4, 5])
    assert mean == design.package_mean_loss([18], [10])
    assert design.package_mean_loss([0], [1]) == 0
    with pytest.raises(ValueError):
        design.package_mean_loss([1], [0])
    with pytest.raises(ValueError):
        design.package_mean_loss([1.0], [1])


def test_control_and_dual_tasks_receive_equal_task_mass_not_equal_package_mass():
    tasks = five_tasks()
    for task in tasks:
        value = F(9) if task["group"] == "control" else F(1)
        task["package_mean_losses"] = {
            method: [value] * 8 for method in task["package_mean_losses"]
        }
    for arm in design.ARMS:
        assert design.update_loss(arm, tasks) == F(21, 5)
        assert design.update_loss(arm, tasks) != F(3 * 16 + 2 * 8 * 9, 64)


@pytest.mark.parametrize("bad_count", [7, 9, 10])
def test_heldouts_or_incomplete_kernel_cannot_enter_the_eight_package_objective(bad_count):
    values = {"endpoint": [1] * 8, "movement": [2] * bad_count}
    with pytest.raises(ValueError, match="design.eight_training_packages_not_ten_with_holdouts"):
        design.task_loss("plus", design.DUAL_GROUPS[0], values)


def test_task_batch_shape_rejects_duplicate_tasks_or_wrong_subgroup_mix():
    tasks = five_tasks()
    with pytest.raises(ValueError, match="design.exact_five_task_update"):
        design.update_loss("alpha0", tasks[:-1])
    duplicate = copy.deepcopy(tasks)
    duplicate[-1]["task_id"] = duplicate[-2]["task_id"]
    with pytest.raises(ValueError, match="design.one_each_dual_subgroup"):
        design.update_loss("alpha0", duplicate)
    wrong = copy.deepcopy(tasks)
    wrong[1]["group"] = wrong[0]["group"]
    with pytest.raises(ValueError, match="design.one_each_dual_subgroup"):
        design.update_loss("alpha0", wrong)


@pytest.mark.parametrize("n", design.ALLOWED_POPULATIONS)
def test_fraction_batch_mean_equals_global_objective_and_group_mass_difference(n):
    k = n // 5
    tasks = {
        group: [synthetic_task(group, index) for index in range(2 * k if group == "control" else k)]
        for group in design.GROUPS
    }
    task_batches = [
        [tasks[group][index] for group in design.DUAL_GROUPS]
        + tasks["control"][2 * index : 2 * index + 2]
        for index in range(k)
    ]
    losses = {}
    for arm in design.ARMS:
        batch_mean = sum((design.update_loss(arm, batch) for batch in task_batches), F()) / k
        global_loss = F()
        for group, members in tasks.items():
            for task in members:
                for method, packages in task["package_mean_losses"].items():
                    global_loss += sum(packages, F()) * design.package_mass(n, arm, group, method)
        assert batch_mean == global_loss
        losses[arm] = global_loss
    dual_differences = [
        sum(task["package_mean_losses"]["movement"], F()) / 8
        - sum(task["package_mean_losses"]["endpoint"], F()) / 8
        for group in design.DUAL_GROUPS
        for task in tasks[group]
    ]
    mean_difference = sum(dual_differences, F()) / (3 * k)
    assert losses["plus"] - losses["alpha0"] == F(1, 10) * mean_difference
    assert losses["minus"] - losses["alpha0"] == -F(1, 10) * mean_difference
    assert losses["plus"] - losses["minus"] == F(1, 5) * mean_difference


def test_joint_ready_selection_uses_group_bottleneck_and_original_order():
    ready = ready_lists()
    ready[design.DUAL_GROUPS[1]] = ready[design.DUAL_GROUPS[1]][:37]
    ready[design.DUAL_GROUPS[0]].reverse()
    before = copy.deepcopy(ready)
    selection = design.choose_population(ready)
    assert ready == before
    assert_prospective_identity(selection)
    assert selection["status"] == "PROSPECTIVE_POPULATION_SELECTED"
    assert selection["tasks"] == 185
    assert selection["k_per_dual_group"] == 37
    assert len(selection["selected"]) == 185
    assert (
        selection["selected_by_group"][design.DUAL_GROUPS[0]] == ready[design.DUAL_GROUPS[0]][:37]
    )
    assert selection["selected_by_group"]["control"] == ready["control"][:74]
    assert selection["qualifications_or_actual_methods_inferred"] is False
    assert selection["same_selected_task_set_for_A_and_B"] is True
    assert selection["replacement_after_Student_results"] is False


def test_odd_control_count_rounds_down_without_inventing_a_fractional_task():
    selection = design.choose_population(ready_lists(control=73))
    assert selection["tasks"] == 180
    assert len(selection["selected_by_group"]["control"]) == 72


@pytest.mark.parametrize("short_group", design.GROUPS)
def test_insufficient_common_support_stops_all_selection_without_partial_training(short_group):
    ready = ready_lists()
    ready[short_group] = ready[short_group][: 71 if short_group == "control" else 35]
    selection = design.choose_population(ready)
    assert selection["status"] == "INPUT_INADEQUATE"
    assert selection["selected"] == []
    assert all(values == [] for values in selection["selected_by_group"].values())
    assert selection["tasks"] is selection["population_design_id"] is None
    assert selection["training_allowed_by_this_preparation"] is False
    assert selection["extra_generation_or_relaxed_task_categories_allowed"] is False
    with pytest.raises(ValueError, match="design.population_required"):
        design.task_batches(selection, 11)


def test_selector_rejects_duplicates_missing_groups_and_unintersected_pools():
    ready = ready_lists()
    ready["control"][0] = ready[design.DUAL_GROUPS[0]][0]
    with pytest.raises(ValueError, match="design.unique_tasks"):
        design.choose_population(ready)
    with pytest.raises(ValueError, match="design.exact_four_common_ready_groups"):
        design.choose_population({"A": ready_lists(), "B": ready_lists()})
    missing = ready_lists()
    del missing[design.DUAL_GROUPS[0]]
    with pytest.raises(ValueError, match="design.exact_four_common_ready_groups"):
        design.choose_population(missing)


def test_common_ready_counts_cannot_exceed_the_frozen_candidate_population():
    for ready in (ready_lists(54, control=100), ready_lists(control=101)):
        with pytest.raises(ValueError, match="design.common_ready_subset_of_fixed_candidate_caps"):
            design.choose_population(ready)


@pytest.mark.parametrize("n", design.ALLOWED_POPULATIONS)
def test_ten_pass_schedule_has_exact_3plus2_batches_and_each_task_once_per_pass(n):
    selection = design.choose_population(ready_lists(n // 5))
    before = copy.deepcopy(selection)
    schedule = design.task_batches(selection, 11)
    assert selection == before
    assert_prospective_identity(schedule)
    assert schedule["tasks"] == n
    assert schedule["optimizer_updates"] == len(schedule["batches"]) == 2 * n
    assert [batch["optimizer_update"] for batch in schedule["batches"]] == list(range(1, 2 * n + 1))
    expected_ids = {item["task_id"] for item in selection["selected"]}
    for epoch in range(1, 11):
        batches = [batch for batch in schedule["batches"] if batch["epoch"] == epoch]
        assert len(batches) == n // 5
        ids = [task["task_id"] for batch in batches for task in batch["tasks"]]
        assert len(ids) == len(set(ids)) == n and set(ids) == expected_ids
        for batch in batches:
            assert Counter(task["group"] for task in batch["tasks"]) == {
                **{group: 1 for group in design.DUAL_GROUPS},
                "control": 2,
            }
            assert batch["training_package_count"] == 3 * 16 + 2 * 8 == 64
            assert batch["task_mean_coefficient"] == "1/5"
    assert schedule["subgroup_mix_is_new_preregistered_implementation_choice"] is True
    assert schedule["subgroup_mix_was_not_specifically_required_by_user_audit"] is True
    assert schedule["optimizer_or_trainer_constructed"] is False


def test_paired_schedule_reproducibility_and_changed_selection_rejection():
    selection = design.choose_population(ready_lists())
    first = design.task_batches(selection, 11)
    assert first == design.task_batches(selection, 11)
    assert first["batches"] != design.task_batches(selection, 29)["batches"]
    changed = copy.deepcopy(selection)
    changed["selected"][0]["task_id"] = "a replacement"
    with pytest.raises(ValueError, match="design.unchanged_prospective_selection_identity"):
        design.task_batches(changed, 11)
    with pytest.raises(ValueError, match="design.three_registered_paired_seeds"):
        design.task_batches(selection, 99)


def utilities(baseline=F(1, 2)):
    return {arm: {seed: baseline for seed in design.SEEDS} for arm in design.ARMS}


def test_baseline_at_zero_gain_stops_B_training_and_all_confirmation():
    result = design.select_direction(utilities())
    assert_prospective_identity(result)
    assert result["selected_arm"] == "alpha0"
    assert result["planned_B_train_runs"] == result["planned_confirmation_sessions"] == 0
    assert result["planned_B_arms"] == []
    assert result["planned_B_development_sessions"] == 0


def test_strictly_positive_mean_can_select_with_one_negative_seed_and_never_B_dev():
    values = utilities()
    values["plus"] = {11: F(3, 5), 29: F(3, 5), 47: F(2, 5)}
    result = design.select_direction(values)
    assert result["selected_arm"] == "plus"
    assert result["paired_mean_gain"]["plus"] == "1/30"
    assert result["every_seed_positive_required"] is False
    assert result["planned_B_train_runs"] == 6
    assert result["planned_B_arms"] == ["alpha0", "plus"]
    assert result["planned_B_development_sessions"] == 0
    assert result["planned_confirmation_sessions"] == 8640
    assert result["primary_confirmation_pool"] == "B"
    assert result["execution_authorized_by_this_record"] is False


def test_positive_tie_has_frozen_order_and_extra_pool_cannot_choose_direction():
    values = utilities()
    for arm in ("plus", "minus"):
        values[arm] = {seed: F(3, 5) for seed in design.SEEDS}
    assert design.select_direction(values)["selected_arm"] == "plus"
    with pytest.raises(ValueError, match="design.only_complete_A"):
        design.select_direction({"A": values, "B": values})
    values["plus"].pop(47)
    with pytest.raises(ValueError, match="design.only_complete_A"):
        design.select_direction(values)


def test_power_is_only_an_independent_task_approximation_and_does_not_pool_task_counts():
    planning = design.power_planning()
    assert_prospective_identity(planning)
    assert planning == design.power_planning("0.05")
    assert planning["critical_sum_squared"] == "196/25"
    assert planning["planned_effect"] == "1/20"
    assert [row["approximate_required_tasks_rounded_up"] for row in planning["planning_rows"]] == [
        314,
        628,
        941,
    ]
    assert planning["planning_rows"][1]["approximate_detectable_effect_by_unique_task_count"][
        "720"
    ] == pytest.approx(0.04666666666666667)
    assert planning["confirmation_unique_tasks"] == 720
    assert planning["pools_and_seeds_multiply_independent_task_count"] is False
    assert planning["A_and_B_confirmation_tasks_are_the_same_720"] is True
    assert planning["cluster_adjusted_or_seed_averaged_power_established"] is False
    assert planning["actual_source_clusters_verified"] is False
    assert planning["task_cluster_intervals_estimate_all_training_randomness"] is False
    assert planning["prospective_company_report_cluster_simulation_required"] is True
    for effect in (0, -1, "0.2", 0.05, True):
        with pytest.raises(ValueError):
            design.power_planning(effect)
