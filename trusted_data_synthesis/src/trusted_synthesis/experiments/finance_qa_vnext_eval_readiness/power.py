"""Prospective source-cluster/window sensitivity, not measured power or effective N."""

from collections import Counter, defaultdict
from math import sqrt
from statistics import NormalDist

from ..finance_qa_vnext_task_build.archive import record, require

SCENARIOS = ((0.0, 0.0), (0.1, 0.0), (0.3, 0.0), (0.5, 0.0), (0.1, 0.2), (0.3, 0.3))
VARIANCES = (0.1, 0.25, 1.0)


def policy():
    return record(
        "prospective_power_sensitivity_policy",
        issuer_and_window_correlations=[list(row) for row in SCENARIOS],
        paired_binary_utility_difference_variances=list(VARIANCES),
        covariance_model=(
            "(1-rho_issuer-rho_window)*I + rho_issuer*issuer_indicator_Gram "
            "+ rho_window*normalized_actual_period_membership_Gram"
        ),
        task_period_vector="one indicator per unique actual period, normalized by sqrt(count)",
        interval="95% normal approximation, two-sided descriptive width",
        minimum_detectable_difference="80% normal-approximation planning sensitivity only",
        effects_are_hypothetical=True,
        correlations_are_not_estimated_from_sources=True,
        no_Student_outputs=True,
        seeds_do_not_multiply_unique_task_count=True,
        overlapping_pair_count_is_not_effective_sample_size=True,
        normal_approximation_fragile_with_few_clusters=True,
        does_not_establish_adequate_power_or_add_selection_threshold=True,
    )


def covariance_sum(tasks, rho_issuer, rho_window):
    require(
        0 <= rho_issuer and 0 <= rho_window and rho_issuer + rho_window <= 1,
        "power.positive_semidefinite_scenario",
    )
    require(
        bool(tasks) and len({row["task_id"] for row in tasks}) == len(tasks),
        "power.unique_actual_tasks_not_seed_multiplication",
    )
    clusters = Counter(row["source_cluster"] for row in tasks)
    membership = defaultdict(float)
    for task in tasks:
        periods = set(task["period_ids"])
        require(bool(periods), "power.actual_periods_required")
        for period in periods:
            membership[task["source_cluster"], period] += 1 / sqrt(len(periods))
    n = len(tasks)
    return (
        (1 - rho_issuer - rho_window) * n
        + rho_issuer * sum(size * size for size in clusters.values())
        + rho_window * sum(value * value for value in membership.values())
    )


def describe(tasks):
    clusters = Counter(row["source_cluster"] for row in tasks)
    n = len(tasks)
    if not tasks:
        return {"tasks": 0, "source_clusters": 0, "status": "NO_SOURCE_QUALIFIED_TASKS"}
    rows = []
    normal = NormalDist()
    for issuer, window in SCENARIOS:
        total = covariance_sum(tasks, issuer, window)
        for variance in VARIANCES:
            se = sqrt(variance * total / (n * n))
            rows.append(
                {
                    "assumed_issuer_correlation": issuer,
                    "assumed_window_correlation": window,
                    "assumed_paired_difference_variance": variance,
                    "model_based_standard_error": se,
                    "normal_95pct_half_width": normal.inv_cdf(0.975) * se,
                    "normal_80pct_minimum_detectable_difference": (
                        normal.inv_cdf(0.975) + normal.inv_cdf(0.8)
                    )
                    * se,
                }
            )
    return {
        "tasks": n,
        "source_clusters": len(clusters),
        "tasks_per_source_cluster": dict(clusters),
        "largest_source_task_share": max(clusters.values()) / n,
        "scenarios": rows,
        "independence_assumed_by_default": False,
        "adequate_power_established": False,
        "effective_sample_size_inferred_from_overlap_counts": False,
    }


def run(panel_tasks):
    result = {}
    for split, tasks in panel_tasks.items():
        result[split] = {"overall": describe(tasks), "by_group": {}}
        for group in ("dual_sufficient", "composition_required", "other_financial"):
            result[split]["by_group"][group] = describe([x for x in tasks if x["family"] == group])
    return record(
        "prospective_source_sensitivity",
        policy_id=policy()["id"],
        panels=result,
        actual_Student_observations=0,
        actual_effect_estimates=None,
        clinical_or_financial_predictions=False,
        no_new_acceptance_or_direction_selection_gate=True,
    )
