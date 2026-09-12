"""Report-bound finite direction choice and paired, task-weighted CIK inference.

This module reads no sessions, models or private references. The stage must load
sealed reports and fixed task descriptors before passing them here. Content IDs
are checked again; a prospective design record cannot replace an executed run.
"""

from collections import Counter
from fractions import Fraction

import numpy as np

from ..finance_qa_vnext_basis_scale_preparation import design
from .protocol import checked_record, record, require

GROUPS = ("dual_sufficient", "composition_required", "other_financial")
BINDING_FIELDS = (
    "study_freeze_id",
    "surface_manifest_id",
    "materials_manifest_id",
    "training_config_id",
    "decoder_config_id",
)
TASK_FIELDS = ("task_id", "group", "source_cluster", "surface_version_id", "public_messages_sha256")
BOOTSTRAP_REPLICATES = 10000
BOOTSTRAP_SEED = 20260912
MAX_BOOTSTRAP_ATTEMPTS = 1000000


def policy():
    return record(
        "analysis_policy",
        selection_pool="A",
        arms=list(design.ARMS),
        paired_seeds=list(design.SEEDS),
        dev_tasks=180,
        dev_group_tasks=60,
        confirm_tasks=720,
        confirm_group_tasks=240,
        primary_utility="financial_valid: full-trajectory financial qualification",
        unknown_errors_no_Final_retained_in_fixed_denominators=True,
        fine_mapping_pending_does_not_negate_financial_valid=True,
        utility_aggregation="task mean within each group, then equal mean of three groups",
        candidate_requires_strictly_positive_seed_mean_paired_gain=True,
        tie_priority=list(design.ARMS),
        every_seed_positive_required=False,
        NLL_or_method_yield_used_for_selection=False,
        baseline_stops_B_training_and_confirmation=True,
        runner_up_confirmation_allowed=False,
        primary_confirmation_pool="B",
        auxiliary_confirmation_pool="A",
        B_development_sessions=0,
        confirmation_sessions=8640,
        bootstrap_replicates=BOOTSTRAP_REPLICATES,
        bootstrap_seed=BOOTSTRAP_SEED,
        bootstrap_rng="numpy.random.Generator(PCG64)",
        bootstrap_draw="multinomial(K, uniform probability over sorted unique CIK clusters)",
        bootstrap_shared_weights="all arms, seeds, pools and task groups in the same draw",
        bootstrap_estimand="cluster multiplicity times each task; not equal company means",
        bootstrap_empty_group="reject whole draw and redraw; never drop or renormalize a group",
        bootstrap_max_attempts=MAX_BOOTSTRAP_ATTEMPTS,
        bootstrap_attempt_limit_failure="STOP without a partial interval",
        confidence_level=0.95,
        interval="paired percentile, 0.025 and 0.975 quantiles, linear interpolation",
        interval_endpoint_numeric_rounding_decimal_places=15,
        meaningful_benefit=0.05,
        positive_confirmation="B interval lower bound strictly greater than zero",
        zero_inclusive_interval="not confirmed",
        upper_bound_at_least_5pp="cannot exclude a benefit of at least five percentage points",
        source_inference_conditional_on_fixed_trained_checkpoints=True,
        intervals_estimate_all_training_randomness=False,
        pools_and_seeds_multiply_independent_task_count=False,
    )


def _fraction(value):
    value = Fraction(value)
    return {"exact": str(value), "value": float(value)}


def _binding(binding):
    require(isinstance(binding, dict) and set(binding) == set(BINDING_FIELDS), "analysis.binding")
    require(
        all(isinstance(binding[key], str) and binding[key] for key in BINDING_FIELDS),
        "analysis.nonempty_binding_identity",
    )
    return dict(binding)


def _check_binding(value, binding):
    require(all(value.get(key) == val for key, val in binding.items()), "analysis.report_binding")


def _tasks(tasks, split, groups):
    require(tuple(groups) == GROUPS, "analysis.original_three_groups")
    count = 60 if split == "dev" else 240
    require(isinstance(tasks, list) and len(tasks) == 3 * count, "analysis.fixed_task_denominator")
    rows = []
    for task in tasks:
        require(
            isinstance(task, dict) and all(key in task for key in TASK_FIELDS),
            "analysis.task_fields",
        )
        require(
            all(isinstance(task[key], str) and task[key] for key in TASK_FIELDS),
            "analysis.task_identity_strings",
        )
        cluster = task["source_cluster"]
        require(
            cluster.startswith("cik:") and len(cluster) == 14 and cluster[4:].isdigit(),
            "analysis.CIK_cluster_not_report_or_row",
        )
        rows.append({key: task[key] for key in TASK_FIELDS})
    require(len({row["task_id"] for row in rows}) == len(rows), "analysis.unique_task_ids")
    require(
        Counter(row["group"] for row in rows) == Counter(dict.fromkeys(groups, count)),
        "analysis.complete_equal_group_quotas",
    )
    return sorted(rows, key=lambda row: row["task_id"])


def _task_manifest(tasks, split):
    return record("analysis_task_manifest", split=split, tasks=tasks)


def _training(reports, keys, binding):
    require(
        isinstance(reports, list) and len(reports) == len(keys), "analysis.complete_training_runs"
    )
    found = {}
    for report in reports:
        checked_record(report, "training_report")
        _check_binding(report, binding)
        require(
            report.get("status") == "COMPLETE_FINAL_CHECKPOINT"
            and report.get("actual_complete") is True,
            "analysis.actual_final_checkpoint_required",
        )
        key = (report.get("pool"), report.get("arm"), report.get("seed"))
        require(key in keys and key not in found, "analysis.fixed_unique_training_run")
        require(type(key[2]) is int, "analysis.integer_registered_seed")
        require(
            isinstance(report.get("checkpoint_id"), str) and bool(report["checkpoint_id"]),
            "analysis.checkpoint_identity",
        )
        adapter = report.get("final_adapter")
        require(
            isinstance(adapter, dict)
            and adapter.get("parameter_digest") == report["checkpoint_id"]
            and isinstance(adapter.get("path"), str)
            and bool(adapter["path"])
            and isinstance(adapter.get("sha256"), str)
            and len(adapter["sha256"]) == 64
            and type(adapter.get("bytes")) is int
            and adapter["bytes"] > 0
            and report.get("final_adapter_restored_identity_verified") is True,
            "analysis.saved_and_restored_final_adapter_identity",
        )
        found[key] = report
    require(set(found) == set(keys), "analysis.no_missing_training_run")
    return found


def _scores(reports, training, keys, tasks, split, binding):
    require(
        isinstance(reports, list) and len(reports) == len(keys), "analysis.complete_score_reports"
    )
    expected = {row["task_id"]: row for row in tasks}
    found = {}
    for report in reports:
        checked_record(report, "evaluation_report")
        _check_binding(report, binding)
        key = (report.get("pool"), report.get("arm"), report.get("seed"))
        require(key in keys and key not in found, "analysis.fixed_unique_evaluation_run")
        require(type(key[2]) is int, "analysis.integer_registered_seed")
        require(
            report.get("actual_complete") is True
            and report.get("status") == "COMPLETE_FIXED_EVALUATION"
            and report.get("split") == split,
            "analysis.actual_complete_fixed_split",
        )
        require(
            report.get("training_report_id") == training[key]["id"]
            and report.get("checkpoint_id") == training[key]["checkpoint_id"],
            "analysis.actual_checkpoint_score_join",
        )
        outcomes = report.get("outcomes")
        require(
            isinstance(outcomes, list) and len(outcomes) == len(tasks),
            "analysis.full_outcome_denominator",
        )
        seen, ordered = set(), {}
        for outcome in outcomes:
            task_id = outcome.get("task_id")
            require(task_id in expected and task_id not in seen, "analysis.unique_original_outcome")
            require(
                all(outcome.get(field) == expected[task_id][field] for field in TASK_FIELDS),
                "analysis.outcome_original_source_surface_group",
            )
            require(
                type(outcome.get("financial_valid")) is bool, "analysis.explicit_financial_boolean"
            )
            seen.add(task_id)
            ordered[task_id] = outcome
        require(seen == set(expected), "analysis.no_dropped_failures_or_unknowns")
        found[key] = (report, [ordered[row["task_id"]] for row in tasks])
    require(set(found) == set(keys), "analysis.complete_model_score_cross_product")
    return found


def _utility(outcomes, groups=GROUPS):
    means, counts, successes = {}, {}, {}
    for group in groups:
        rows = [row for row in outcomes if row["group"] == group]
        counts[group] = len(rows)
        successes[group] = sum(row["financial_valid"] for row in rows)
        means[group] = Fraction(successes[group], counts[group])
    utility = sum(means.values(), Fraction()) / 3
    return utility, {
        "utility": _fraction(utility),
        "group_utilities": {group: _fraction(means[group]) for group in groups},
        "group_denominators": counts,
        "group_financial_valid": successes,
        "fixed_task_denominator": len(outcomes),
    }


def select_actual_direction(training_reports, dev_reports, *, binding, dev_tasks, groups=GROUPS):
    binding = _binding(binding)
    tasks = _tasks(dev_tasks, "dev", groups)
    keys = [("A", arm, seed) for arm in design.ARMS for seed in design.SEEDS]
    training = _training(training_reports, keys, binding)
    scores = _scores(dev_reports, training, keys, tasks, "dev", binding)
    utilities = {arm: {} for arm in design.ARMS}
    summaries = []
    for key in keys:
        _, arm, seed = key
        value, detail = _utility(scores[key][1])
        utilities[arm][seed] = value
        summaries.append({"pool": "A", "arm": arm, "seed": seed, **detail})
    mathematical = design.select_direction(utilities)
    selected = mathematical["selected_arm"]
    move = selected != "alpha0"
    return record(
        "actual_direction_decision",
        **binding,
        status="MOVE_FIXED_UNIQUE_DIRECTION" if move else "STOP_RETAIN_BASELINE",
        actual_complete=True,
        prospective_not_executed=False,
        analysis_policy_id=policy()["id"],
        task_manifest_id=_task_manifest(tasks, "dev")["id"],
        selection_pool="A",
        selected_arm=selected,
        utility_summaries=summaries,
        mean_utility_by_arm={
            arm: _fraction(sum(utilities[arm].values(), Fraction()) / 3) for arm in design.ARMS
        },
        paired_mean_gain=mathematical["paired_mean_gain"],
        tie_priority=list(design.ARMS),
        strictly_positive_paired_mean_required=True,
        every_seed_positive_required=False,
        primary_metric="financial_valid",
        NLL_or_method_yield_used=False,
        training_report_ids=[training[key]["id"] for key in keys],
        dev_score_report_ids=[scores[key][0]["id"] for key in keys],
        final_checkpoint_ids=[training[key]["checkpoint_id"] for key in keys],
        observed_A_training_runs=len(training),
        observed_A_dev_sessions=sum(len(value[1]) for value in scores.values()),
        fixed_dev_unique_tasks=180,
        source_clusters={
            "unique_CIK_clusters": len({row["source_cluster"] for row in tasks}),
            "group_unique_CIK_clusters": {
                group: len({row["source_cluster"] for row in tasks if row["group"] == group})
                for group in GROUPS
            },
        },
        planned_B_training_runs=6 if move else 0,
        planned_B_arms=["alpha0", selected] if move else [],
        planned_B_dev_sessions=0,
        planned_confirmation_sessions=8640 if move else 0,
        runner_up_after_confirmation_failure_allowed=False,
        prospective_rule_reference_id=mathematical["id"],
        actual_decision_requires_complete_report_bindings=True,
    )


def _bootstrap(tasks, scores, keys):
    clusters = sorted({row["source_cluster"] for row in tasks})
    cluster_index = {cluster: index for index, cluster in enumerate(clusters)}
    counts = np.zeros((3, len(clusters)), dtype=np.int64)
    successes = np.zeros((len(keys), 3, len(clusters)), dtype=np.int64)
    for index, task in enumerate(tasks):
        group, cluster = GROUPS.index(task["group"]), cluster_index[task["source_cluster"]]
        counts[group, cluster] += 1
        for model, key in enumerate(keys):
            successes[model, group, cluster] += scores[key][1][index]["financial_valid"]
    positions = {key: index for index, key in enumerate(keys)}
    candidate = next(key[1] for key in keys if key[1] != "alpha0")
    # Pair integer success counts first. Subtracting separately rounded utility
    # means can turn an exact zero gain into a tiny spurious positive number.
    differences = np.stack(
        [
            sum(
                successes[positions[(pool, candidate, seed)]]
                - successes[positions[(pool, "alpha0", seed)]]
                for seed in design.SEEDS
            )
            for pool in ("A", "B")
        ]
    )
    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    retained, attempts, rejected = [], 0, 0
    accepted = 0
    while accepted < BOOTSTRAP_REPLICATES and attempts < MAX_BOOTSTRAP_ATTEMPTS:
        size = min(1000, BOOTSTRAP_REPLICATES - accepted, MAX_BOOTSTRAP_ATTEMPTS - attempts)
        weights = rng.multinomial(
            len(clusters), np.full(len(clusters), 1 / len(clusters)), size=size
        )
        denominators = weights @ counts.T
        usable = np.all(denominators > 0, axis=1)
        attempts += size
        rejected += int((~usable).sum())
        weights, denominators = weights[usable], denominators[usable]
        if len(weights):
            numerators = np.einsum("rk,pgk->rpg", weights, differences)
            means = (numerators / denominators[:, None, :] / 3).mean(axis=2)
            retained.append(means)
            accepted += len(weights)
    require(
        accepted == BOOTSTRAP_REPLICATES,
        "analysis.bootstrap_attempt_limit_no_partial_interval:"
        f"attempts={attempts},accepted={accepted},empty_group_rejected={rejected}",
    )
    return np.concatenate(retained), {
        "replicates": accepted,
        "attempts": attempts,
        "empty_group_rejected_draws": rejected,
        "seed": BOOTSTRAP_SEED,
        "maximum_attempts": MAX_BOOTSTRAP_ATTEMPTS,
        "cluster_count": len(clusters),
        "clusters_sorted": clusters,
        "cluster_task_counts": {
            group: {cluster: int(counts[g, c]) for c, cluster in enumerate(clusters)}
            for g, group in enumerate(GROUPS)
        },
        "all_observations_use_same_draw_weights": True,
        "empty_groups_are_whole_draw_rejections": True,
        "task_weighted_group_means_not_company_means": True,
    }


def _interval(point, samples):
    lower, upper = (
        round(float(value), 15) for value in np.quantile(samples, [0.025, 0.975], method="linear")
    )
    return {
        "paired_seed_mean_gain": _fraction(point),
        "lower": lower,
        "upper": upper,
        "confidence_level": 0.95,
        "zero_in_interval": lower <= 0 <= upper,
        "strictly_positive_interval": lower > 0,
        "five_pp_in_interval": lower <= 0.05 <= upper,
        "cannot_exclude_benefit_at_least_five_pp": upper >= 0.05,
        "at_least_five_pp_lower_bound_established": lower >= 0.05,
    }


def confirm_actual(
    decision, training_reports, confirm_reports, *, binding, confirm_tasks, groups=GROUPS
):
    binding = _binding(binding)
    checked_record(decision, "actual_direction_decision")
    _check_binding(decision, binding)
    selected = decision.get("selected_arm")
    require(
        decision.get("actual_complete") is True
        and decision.get("prospective_not_executed") is False
        and decision.get("status") == "MOVE_FIXED_UNIQUE_DIRECTION"
        and decision.get("analysis_policy_id") == policy()["id"]
        and selected in {"plus", "minus"},
        "analysis.actual_unique_positive_direction_before_confirmation",
    )
    tasks = _tasks(confirm_tasks, "confirm", groups)
    a_keys = [("A", arm, seed) for arm in design.ARMS for seed in design.SEEDS]
    b_keys = [("B", arm, seed) for arm in ("alpha0", selected) for seed in design.SEEDS]
    training = _training(training_reports, [*a_keys, *b_keys], binding)
    require(
        decision.get("training_report_ids") == [training[key]["id"] for key in a_keys],
        "analysis.same_A_training_as_actual_selection",
    )
    keys = [
        (pool, arm, seed)
        for pool in ("A", "B")
        for arm in ("alpha0", selected)
        for seed in design.SEEDS
    ]
    scores = _scores(confirm_reports, training, keys, tasks, "confirm", binding)
    utilities, summaries = {}, []
    for key in keys:
        utilities[key], detail = _utility(scores[key][1])
        summaries.append({"pool": key[0], "arm": key[1], "seed": key[2], **detail})
    samples, bootstrap = _bootstrap(tasks, scores, keys)
    pools = {}
    for pool in ("B", "A"):
        point = (
            sum(
                (
                    utilities[(pool, selected, seed)] - utilities[(pool, "alpha0", seed)]
                    for seed in design.SEEDS
                ),
                Fraction(),
            )
            / 3
        )
        draws = samples[:, ("A", "B").index(pool)]
        pools[pool] = {"role": "primary" if pool == "B" else "auxiliary", **_interval(point, draws)}
    return record(
        "confirmation_analysis",
        **binding,
        status="CONFIRMED_POSITIVE_AS_SCOPED"
        if pools["B"]["strictly_positive_interval"]
        else "NOT_CONFIRMED",
        actual_complete=True,
        analysis_policy_id=policy()["id"],
        decision_id=decision["id"],
        selected_arm=selected,
        primary_pool="B",
        auxiliary_pool="A",
        primary_pool_selected_after_results=False,
        task_manifest_id=_task_manifest(tasks, "confirm")["id"],
        fixed_confirm_unique_tasks=720,
        observed_confirmation_sessions=sum(len(value[1]) for value in scores.values()),
        training_report_ids=[training[key]["id"] for key in [*a_keys, *b_keys]],
        confirm_score_report_ids=[scores[key][0]["id"] for key in keys],
        utility_summaries=summaries,
        pools=pools,
        bootstrap=bootstrap,
        diagnostics={
            "unique_CIK_clusters": bootstrap["cluster_count"],
            "group_unique_CIK_clusters": {
                group: len({row["source_cluster"] for row in tasks if row["group"] == group})
                for group in GROUPS
            },
            "largest_cluster_task_fraction": max(
                Counter(row["source_cluster"] for row in tasks).values()
            )
            / 720,
            "source_related_tasks_are_not_independent": True,
        },
        limitations=[
            "Inference concerns the selected common-consumable training population "
            "and fixed A/B material kernels.",
            "The 720 tasks share CIK sources and periods; seeds and pools do not "
            "multiply independent tasks.",
            "The cluster interval conditions on these fixed trained checkpoints "
            "and does not estimate all training randomness.",
            "A development selected the direction; A confirmation is auxiliary "
            "and does not replace primary B.",
            "Positive as-scoped utility does not establish general financial "
            "or unconstrained-language generalization.",
        ],
    )
