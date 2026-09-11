"""Prospective scale, loss and budget mathematics; never an experiment runner.

Only standard-library arithmetic and task-ID scheduling are used. No tokenizer,
model, source generator, training population or optimizer is constructed. Every
record explicitly describes an unexecuted prospective design. Resource totals
are upper bounds, never observed usage or an execution authorization.
"""

import hashlib
import json
import math
import random
from collections import Counter
from fractions import Fraction

DUAL_GROUPS = (
    "stock_rollforward",
    "annual_flow_components",
    "defined_metric_reconstruction",
)
CONTROL_GROUP = "control"
GROUPS = (*DUAL_GROUPS, CONTROL_GROUP)
METHODS = ("endpoint", "movement")
ARMS = ("alpha0", "plus", "minus")
POOLS = ("A", "B")
SEEDS = (11, 29, 47)
ALLOWED_POPULATIONS = tuple(range(180, 201, 5))
EPOCHS = 10
TRAIN_PACKAGES_PER_METHOD = 8
HELDOUT_PACKAGES_PER_METHOD = 2
TASKS_PER_UPDATE = 5
PACKAGES_PER_UPDATE = 64
_ALPHA = {
    "alpha0": (Fraction(1, 2), Fraction(1, 2)),
    "plus": (Fraction(1, 3), Fraction(2, 3)),
    "minus": (Fraction(2, 3), Fraction(1, 3)),
}


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _record(kind, **fields):
    body = {
        "schema_version": "basis_scale_preparation.v1." + kind,
        "prospective_not_executed": True,
        **fields,
    }
    return {**body, "id": kind + ":" + hashlib.sha256(_encode(body)).hexdigest()}


def _fraction(value):
    _require(
        isinstance(value, (int, str, Fraction)) and not isinstance(value, bool),
        "design.exact_fraction_input_not_binary_float",
    )
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError("design.finite_exact_fraction") from error


def _n(n):
    _require(type(n) is int and n in ALLOWED_POPULATIONS, "design.N_180_to_200_step_five")
    return n


def _method_mass(arm, group, method):
    _require(arm in ARMS and group in GROUPS, "design.registered_arm_and_group")
    if group == CONTROL_GROUP:
        _require(method in {None, CONTROL_GROUP}, "design.control_has_no_endpoint_movement_choice")
        return Fraction(1)
    _require(method in METHODS, "design.actual_method_not_requested_guidance")
    return _ALPHA[arm][METHODS.index(method)]


def population(n):
    """Describe the selected common A/B task count; do not create material."""
    n = _n(n)
    k = n // 5
    dual, control = 3 * k, 2 * k
    train = dual * 2 * TRAIN_PACKAGES_PER_METHOD + control * TRAIN_PACKAGES_PER_METHOD
    heldout = dual * 2 * HELDOUT_PACKAGES_PER_METHOD + control * HELDOUT_PACKAGES_PER_METHOD
    return _record(
        "basis_scale_population_design",
        tasks=n,
        task_marginal=str(Fraction(1, n)),
        tasks_by_group={**{group: k for group in DUAL_GROUPS}, CONTROL_GROUP: control},
        dual_tasks=dual,
        control_tasks=control,
        methods_per_dual_task=2,
        train_packages_per_method_or_control=TRAIN_PACKAGES_PER_METHOD,
        heldout_packages_per_method_or_control=HELDOUT_PACKAGES_PER_METHOD,
        train_packages_per_pool=train,
        heldout_packages_per_pool=heldout,
        total_packages_per_pool=train + heldout,
        train_packages_across_two_separate_pools=2 * train,
        heldout_packages_across_two_separate_pools=2 * heldout,
        pools_combined_for_training=False,
        tasks_per_update=TASKS_PER_UPDATE,
        packages_per_update=PACKAGES_PER_UPDATE,
        updates_per_epoch=k,
        epochs=EPOCHS,
        optimizer_updates_per_run=EPOCHS * k,
        maximum_optimizer_updates_A_nine_runs=9 * EPOCHS * k,
        maximum_optimizer_updates_A_and_B_fifteen_runs=15 * EPOCHS * k,
        whole_training_package_visits_per_run=EPOCHS * train,
        global_mass_moved_from_baseline=str(Fraction(dual, n) * Fraction(1, 6)),
        baseline_global_group_mass={"endpoint": "3/10", "movement": "3/10", "control": "2/5"},
        plus_global_group_mass={"endpoint": "1/5", "movement": "2/5", "control": "2/5"},
        minus_global_group_mass={"endpoint": "2/5", "movement": "1/5", "control": "2/5"},
        actual_token_budgets=None,
        token_budget_rule=(
            "per run: 10 times actual selected training target/sequence totals of its own pool"
        ),
        heldout_representation_check_allowed=True,
        heldout_training_NLL_greedy_or_direction_selection_allowed=False,
        training_population_materialized=False,
        training_allowed_by_this_preparation=False,
    )


def package_mass(n, arm, group, method):
    """Exact GLOBAL mass of one of the eight training packages in its stratum."""
    return _method_mass(arm, group, method) / (_n(n) * TRAIN_PACKAGES_PER_METHOD)


def update_token_coefficient(arm, group, method, package_target_tokens):
    """Exact coefficient of each target-token NLL in one FIVE-TASK update.

    The denominator is the complete original package's target-token count,
    including all its positive response rows. There is no further row, package,
    microbatch, global-N or global-token normalization. No global N is required.
    """
    _require(
        type(package_target_tokens) is int and package_target_tokens > 0,
        "design.positive_whole_package_target_token_count",
    )
    return _method_mass(arm, group, method) / (
        TASKS_PER_UPDATE * TRAIN_PACKAGES_PER_METHOD * package_target_tokens
    )


def package_mean_loss(row_target_nll_sums, row_target_token_counts):
    """Pure Fraction control for an entire package; does not compute model NLL."""
    _require(
        isinstance(row_target_nll_sums, (list, tuple))
        and isinstance(row_target_token_counts, (list, tuple))
        and len(row_target_nll_sums) == len(row_target_token_counts) > 0
        and all(type(n) is int and n > 0 for n in row_target_token_counts),
        "design.complete_positive_rows_and_counts",
    )
    losses = [_fraction(value) for value in row_target_nll_sums]
    _require(all(value >= 0 for value in losses), "design.nonnegative_token_loss_sums")
    return sum(losses, Fraction()) / sum(row_target_token_counts)


def task_loss(arm, group, package_mean_losses):
    """Pure task objective over exactly eight TRAINING packages per method."""
    _require(group in GROUPS and arm in ARMS, "design.registered_arm_and_group")
    methods = (CONTROL_GROUP,) if group == CONTROL_GROUP else METHODS
    _require(
        isinstance(package_mean_losses, dict) and set(package_mean_losses) == set(methods),
        "design.exact_task_method_kernel",
    )
    total = Fraction()
    for method in methods:
        values = package_mean_losses[method]
        _require(
            isinstance(values, (list, tuple)) and len(values) == TRAIN_PACKAGES_PER_METHOD,
            "design.eight_training_packages_not_ten_with_holdouts",
        )
        losses = [_fraction(value) for value in values]
        _require(all(value >= 0 for value in losses), "design.nonnegative_package_losses")
        total += _method_mass(arm, group, method) * sum(losses, Fraction()) / len(losses)
    return total


def update_loss(arm, task_inputs):
    """Five-task objective; each item has task_id, group, package_mean_losses.

    Taking one task from each dual subgroup is a new preregistered scheduling
    choice, not a claim that the audit required this precise subgroup mix.
    """
    _require(
        isinstance(task_inputs, (list, tuple)) and len(task_inputs) == TASKS_PER_UPDATE,
        "design.exact_five_task_update",
    )
    _require(
        all(
            isinstance(item, dict)
            and isinstance(item.get("task_id"), str)
            and item["task_id"]
            and item.get("group") in GROUPS
            for item in task_inputs
        )
        and len({item["task_id"] for item in task_inputs}) == TASKS_PER_UPDATE
        and Counter(item["group"] for item in task_inputs)
        == {**{group: 1 for group in DUAL_GROUPS}, CONTROL_GROUP: 2},
        "design.one_each_dual_subgroup_two_controls_no_duplicate_task",
    )
    return (
        sum(
            (task_loss(arm, item["group"], item["package_mean_losses"]) for item in task_inputs),
            Fraction(),
        )
        / TASKS_PER_UPDATE
    )


def choose_population(ready_lists):
    """Select from ALREADY jointly ready A/B lists in their preregistered order.

    The caller establishes source/task independence and both pools' financial,
    full-class, method and no-truncation consumability readiness. This selector
    neither recomputes nor infers those facts. It performs no length ranking and
    may not receive separate pool lists in place of their established intersection.
    """
    _require(
        isinstance(ready_lists, dict) and set(ready_lists) == set(GROUPS),
        "design.exact_four_common_ready_groups",
    )
    ready = {}
    seen = set()
    for group in GROUPS:
        values = ready_lists[group]
        _require(
            isinstance(values, (list, tuple))
            and all(isinstance(value, str) and value.strip() for value in values),
            "design.ordered_task_identity_list",
        )
        _require(
            len(values) == len(set(values)) and not seen.intersection(values),
            "design.unique_tasks_with_no_cross_group_duplication",
        )
        ready[group] = list(values)
        seen.update(values)
    _require(
        sum(len(ready[group]) for group in DUAL_GROUPS) <= 160 and len(ready[CONTROL_GROUP]) <= 100,
        "design.common_ready_subset_of_fixed_candidate_caps",
    )
    k = min(40, *(len(ready[group]) for group in DUAL_GROUPS), len(ready[CONTROL_GROUP]) // 2)
    sufficient = k >= 36
    chosen = {
        group: ready[group][: (2 * k if group == CONTROL_GROUP else k)] if sufficient else []
        for group in GROUPS
    }
    selected = [{"task_id": task, "group": group} for group in GROUPS for task in chosen[group]]
    return _record(
        "basis_scale_prospective_population_selection",
        status="PROSPECTIVE_POPULATION_SELECTED" if sufficient else "INPUT_INADEQUATE",
        ready_counts={group: len(ready[group]) for group in GROUPS},
        ready_lists=ready,
        k_per_dual_group=k if sufficient else None,
        tasks=5 * k if sufficient else None,
        selected=selected,
        selected_by_group=chosen,
        population_design_id=population(5 * k)["id"] if sufficient else None,
        selection_order="original preregistered per-group order; no score or token-length sorting",
        readiness_authority=(
            "upstream two-pool intersection after source/financial/full-mapping/consumability gates"
        ),
        independent_financial_task_identity_verified_here=False,
        qualifications_or_actual_methods_inferred=False,
        same_selected_task_set_for_A_and_B=True,
        replacement_after_Student_results=False,
        extra_generation_or_relaxed_task_categories_allowed=False,
        training_allowed_by_this_preparation=False,
        next_step="freeze common task and separate pool material identities"
        if sufficient
        else "stop_no_generation_topup_or_scope_relaxation",
    )


def task_batches(selection, seed):
    """Prospective ten-pass task schedule, shared across arms and material pools."""
    _require(type(seed) is int and seed in SEEDS, "design.three_registered_paired_seeds")
    _require(isinstance(selection, dict), "design.selection_object")
    _require(
        isinstance(selection.get("ready_lists"), dict)
        and selection == choose_population(selection["ready_lists"]),
        "design.unchanged_prospective_selection_identity",
    )
    _require(selection["status"] == "PROSPECTIVE_POPULATION_SELECTED", "design.population_required")
    n, chosen = selection["tasks"], selection["selected_by_group"]
    k = n // 5
    generator = random.Random(seed)
    batches = []
    for epoch in range(1, EPOCHS + 1):
        ordered = {group: list(chosen[group]) for group in GROUPS}
        for group in GROUPS:
            generator.shuffle(ordered[group])
        for index in range(k):
            tasks = [
                {"task_id": ordered[group][index], "group": group} for group in DUAL_GROUPS
            ] + [
                {"task_id": task, "group": CONTROL_GROUP}
                for task in ordered[CONTROL_GROUP][2 * index : 2 * index + 2]
            ]
            batches.append(
                {
                    "epoch": epoch,
                    "batch_within_epoch": index + 1,
                    "optimizer_update": len(batches) + 1,
                    "tasks": tasks,
                    "task_count": TASKS_PER_UPDATE,
                    "training_package_count": PACKAGES_PER_UPDATE,
                    "task_mean_coefficient": "1/5",
                }
            )
    return _record(
        "basis_scale_task_batch_schedule",
        selection_id=selection["id"],
        seed=seed,
        tasks=n,
        epochs=EPOCHS,
        batches=batches,
        updates_per_epoch=k,
        optimizer_updates=EPOCHS * k,
        each_task_once_per_epoch=True,
        every_selected_training_package_of_each_task_in_its_update=True,
        one_each_dual_subgroup_plus_two_controls=True,
        subgroup_mix_is_new_preregistered_implementation_choice=True,
        subgroup_mix_was_not_specifically_required_by_user_audit=True,
        task_schedule_shared_across_arms_and_A_B=True,
        A_B_original_material_not_combined=True,
        update_loss=(
            "mean of five task objectives; per task method mass, eight-package mean, "
            "whole-package target-token mean"
        ),
        no_global_N_microbatch_or_global_token_second_normalization=True,
        epoch_mean_equals_global_objective_only_at_fixed_parameters=True,
        optimizer_or_trainer_constructed=False,
    )


def select_direction(a_utilities):
    """Prospective exact-Fraction A-only direction rule; no execution side effects."""
    _require(
        isinstance(a_utilities, dict)
        and set(a_utilities) == set(ARMS)
        and all(
            isinstance(values, dict) and set(values) == set(SEEDS)
            for values in a_utilities.values()
        ),
        "design.only_complete_A_three_arm_three_seed_utilities",
    )
    values = {
        arm: {seed: _fraction(value) for seed, value in scores.items()}
        for arm, scores in a_utilities.items()
    }
    _require(
        all(0 <= value <= 1 for scores in values.values() for value in scores.values()),
        "design.full_trace_utility_in_unit_interval",
    )
    gains = {
        arm: sum((values[arm][seed] - values["alpha0"][seed] for seed in SEEDS), Fraction())
        / len(SEEDS)
        for arm in ARMS
    }
    selected = "alpha0"
    for arm in ARMS[1:]:
        if gains[arm] > gains[selected]:
            selected = arm
    move = selected != "alpha0"
    return _record(
        "basis_scale_prospective_direction_selection",
        selection_pool="A",
        selected_arm=selected,
        paired_mean_gain={arm: str(gain) for arm, gain in gains.items()},
        tie_priority=list(ARMS),
        strictly_positive_paired_mean_required=True,
        every_seed_positive_required=False,
        pool_B_used_to_choose_direction=False,
        planned_B_train_runs=6 if move else 0,
        planned_B_arms=["alpha0", selected] if move else [],
        planned_B_development_sessions=0,
        planned_confirmation_sessions=8640 if move else 0,
        primary_confirmation_pool="B" if move else None,
        A_confirmation_auxiliary_only=True,
        runner_up_after_confirmation_failure_allowed=False,
        NLL_tie_break_allowed=False,
        baseline_retention_stops_duplicate_confirmation=True,
        execution_authorized_by_this_record=False,
    )


def power_planning(effect=Fraction(1, 20)):
    """Ideal paired-binary planning, not cluster-adjusted or pooled empirical power.

    n ~= (1.96 + .84)^2*q/effect^2 applies to one fixed model pair on independent
    tasks. Three seeds/two material pools do not multiply the 720 task units.
    Actual company/report clustering and seed-averaged outcomes require a separate
    prospectively frozen simulation; this function does not pretend to supply it.
    """
    effect = _fraction(effect)
    _require(0 < effect <= Fraction(1, 10), "design.positive_planning_effect_at_most_discordance")
    critical_squared = (Fraction(49, 25) + Fraction(21, 25)) ** 2
    discordances = (Fraction(1, 10), Fraction(1, 5), Fraction(3, 10))
    rows = []
    for q in discordances:
        exact_n = critical_squared * q / effect**2
        rows.append(
            {
                "hypothetical_discordance": str(q),
                "approximate_required_tasks_exact": str(exact_n),
                "approximate_required_tasks_rounded_up": math.ceil(exact_n),
                "approximate_detectable_effect_by_unique_task_count": {
                    str(n): math.sqrt(float(critical_squared * q / n)) for n in (200, 720)
                },
            }
        )
    return _record(
        "basis_scale_power_planning",
        formula="n approximately (1.96+0.84)^2*q/Delta^2",
        critical_sum_squared=str(critical_squared),
        planned_effect=str(effect),
        nominal_two_sided_alpha="1/20",
        nominal_power="4/5",
        independent_task_normal_approximation=True,
        fixed_model_pair_and_binary_outcomes_assumed=True,
        planning_rows=rows,
        confirmation_unique_tasks=720,
        sample_sizes_count_evaluation_tasks_not_training_tasks=True,
        material_pools=2,
        seeds_per_pool=3,
        pools_and_seeds_multiply_independent_task_count=False,
        A_and_B_confirmation_tasks_are_the_same_720=True,
        primary_confirmation_pool="B",
        actual_source_clusters_verified=False,
        cluster_adjusted_or_seed_averaged_power_established=False,
        prospective_company_report_cluster_simulation_required=True,
        paired_cluster_resampling_must_preserve_all_arm_seed_pool_observations=True,
        task_cluster_intervals_estimate_all_training_randomness=False,
        positive_confirmation="prespecified primary B interval excludes zero on its positive side",
        interval_crosses_zero="not confirmed",
        interval_upper_bound_includes_planned_effect=(
            "cannot exclude the planned practically meaningful benefit"
        ),
        positive_effect_is_not_proof_of_at_least_planned_effect=True,
        planning_is_not_a_yield_forecast_or_effect_guarantee=True,
    )


def budget_design():
    """Upper caps and prospective stopping rules, with resource amount caps unset."""
    dual_candidates, controls = 160, 100
    sessions_per_pool = dual_candidates * 2 * 32 + controls * 24
    teacher_sessions = len(POOLS) * sessions_per_pool
    dev_sessions = 3 * len(SEEDS) * 180
    confirmation_sessions = len(POOLS) * 2 * len(SEEDS) * 720
    return _record(
        "basis_scale_budget_design",
        status="PROSPECTIVE_SOURCE_AND_RESOURCE_FREEZE_REQUIRED",
        resources_are_upper_caps_not_consumption=True,
        candidate_dual_tasks=dual_candidates,
        candidate_control_tasks=controls,
        candidate_tasks_total=dual_candidates + controls,
        dual_groups=list(DUAL_GROUPS),
        annual_flow_components_scope=(
            "explicit driver bridges or sufficient full annual-flow component differences; "
            "not restricted to narrow bridges"
        ),
        pools=list(POOLS),
        generation_guidance_conditions=list(METHODS),
        requested_guidance_is_not_actual_method=True,
        fixed_dual_sessions_per_guidance_per_pool=32,
        fixed_control_sessions_per_pool=24,
        maximum_Teacher_sessions_per_pool=sessions_per_pool,
        maximum_Teacher_sessions=teacher_sessions,
        maximum_requests_per_Teacher_session=32,
        maximum_Teacher_requests=teacher_sessions * 32,
        allowed_final_task_counts=list(ALLOWED_POPULATIONS),
        maximum_population=population(200),
        every_dual_group_final_tasks="k",
        control_final_tasks="2k",
        common_ready_selector=(
            "k=min(40,ready_dual_group_1,ready_dual_group_2,ready_dual_group_3,"
            "floor(ready_control/2)); stop if k<36"
        ),
        source_insufficient=(
            "STOP before generation; do not relax source sufficiency, duplicate tasks "
            "or invent numeric variants"
        ),
        source_ready_is_not_generated_material_ready=True,
        after_fixed_collection=(
            "retain all candidate/failed/unknown denominators; build jointly ready A/B tasks "
            "by frozen financial/full-mapping/consumability criteria"
        ),
        token_consumability_may_be_preregistered_systematic_filter=True,
        token_length_preference_or_post_result_limit_change_allowed=False,
        after_locked_material_failure=(
            "STOP without replacement, cropping, rewritten targets or neutralized guidance"
        ),
        frozen_pool_kernel=(
            "within each pool preserve guidance, fine-class mixture, original text/representation "
            "and selected eight training packages; only alpha changes"
        ),
        A_B_same_task_set_but_independent_original_session_histories=True,
        A_B_fine_class_mixtures_forced_equal=False,
        fixed_kernel_is_not_prompt_isolated_abstract_method_effect=True,
        arms=list(ARMS),
        alpha={
            arm: {method: str(mass) for method, mass in zip(METHODS, masses, strict=True)}
            for arm, masses in _ALPHA.items()
        },
        intervention_scope="all selected dual tasks; controls and task marginals unchanged",
        global_mass_move_from_baseline="1/10",
        seeds=list(SEEDS),
        maximum_A_training_runs=9,
        maximum_B_training_runs=6,
        maximum_total_training_runs=15,
        B_training_only_after_unique_positive_A_direction=True,
        B_training_arms="baseline plus the unique A-selected candidate",
        B_development_sessions=0,
        development_tasks=180,
        development_tasks_per_equal_group=60,
        maximum_development_sessions=dev_sessions,
        confirmation_unique_tasks=720,
        confirmation_tasks_per_equal_group=240,
        maximum_confirmation_sessions=confirmation_sessions,
        maximum_Student_sessions=dev_sessions + confirmation_sessions,
        maximum_Student_generation_requests_if_32_per_session=(dev_sessions + confirmation_sessions)
        * 32,
        primary_confirmation_pool="B",
        auxiliary_confirmation_pool="A",
        no_move="stop after A development; no B training or duplicate-baseline confirmation",
        B0_same_task_greedy_auxiliary_NLL_or_heldout_evaluation_sessions=0,
        main_utility=(
            "equal mean of three full-trace PASS group yields; errors, unknowns and no-Final "
            "stay in original task denominators"
        ),
        evaluation_guidance_directives_included=False,
        old_27_package_five_arm_protocol_authorized=False,
        actual_training_token_budget_rule=(
            "A:10*S_A per run; B:10*S_B per run; maximum 90*S_A+60*S_B; heldouts excluded"
        ),
        target_sequence_lengths_between_pools_must_be_identical=False,
        total_Teacher_token_stop_limit=None,
        total_provider_cost_stop_limit=None,
        resource_amount_stop_limits_authority=(
            "main protocol must freeze explicit limits before generation; "
            "this module chooses no monetary amount"
        ),
        generation_or_training_authorized_by_this_record=False,
        power_planning=power_planning(),
    )
