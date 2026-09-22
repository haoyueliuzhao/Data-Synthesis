"""Fixed B-confirmation statistics; standard library only, no model or network access.

The production interface is ``analyze_confirmation(tasks, outcomes)``. ``tasks``
contains the frozen registry's task_id, group and cik; each outcome supplies
task_id, seed, arm and binary Q. All 720 registered tasks and all 4,320 outcomes
are required. The registry must be frozen before outcomes are opened; this pure
analysis function validates its shape, not its external provenance.

The estimand first averages the paired delayed_c - static differences over the
fixed seeds 11, 29 and 47 within each task, then averages tasks within each group,
then gives the three group means equal weight. Each bootstrap draw samples C
clusters with replacement from the C unique CIKs in the complete registry. A
cluster's multiplicity applies jointly to every group, both arms and all seeds;
each group's mean uses that draw's actual weighted task count as denominator.

Draws missing any group are rejected and counted. Thus the bootstrap distribution
is conditional on retaining all three groups. Acceptance never depends on an
effect's magnitude or sign. The 95% percentile interval uses linear interpolation
at (n - 1) * p, with p exactly 1/40 and 39/40. Integer sufficient statistics and
Fraction arithmetic preserve an exact strictly-positive-lower-bound decision.

This interval describes source-cluster resampling conditional on these three
fixed trained seeds. It does not cover all training randomness. Neither the point
estimate nor interval performs data selection; there is no extra-task sampling,
seed choice or significance-driven redraw. The fixed draw cap yields INCOMPLETE
and no positive-effect conclusion if insufficient valid replicates are obtained.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction
from typing import Any

GROUPS = ("composition_required", "dual_sufficient", "other_financial")
SEEDS = (11, 29, 47)
ARMS = ("static", "delayed_c")
TASKS_PER_GROUP = 240
BOOTSTRAP_REPLICATES = 20_000
BOOTSTRAP_MAX_DRAWS = 200_000
BOOTSTRAP_RANDOM_SEED = 20260922


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("B_confirmation_statistics." + message)


def _canonical_cik(value: Any) -> str:
    """Avoid splitting one source when JSON encodes its CIK as integer or text."""
    if type(value) is int:
        number = value
    elif isinstance(value, str):
        if value.startswith("cik:"):
            digits = value[4:]
        else:
            digits = value[3:] if value.startswith("CIK") else value
        _require(
            bool(digits) and digits.isascii() and digits.isdigit() and len(digits) <= 10,
            "invalid_cik",
        )
        number = int(digits)
    else:
        raise ValueError("B_confirmation_statistics.invalid_cik")
    _require(0 < number < 10**10, "invalid_cik")
    return f"{number:010d}"


def _validate(
    tasks: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]],
    expected_group_sizes: Mapping[str, int],
) -> tuple[dict[str, tuple[str, str]], dict[tuple[str, int, str], int]]:
    registry: dict[str, tuple[str, str]] = {}
    for row in tasks:
        _require(isinstance(row, Mapping), "task_must_be_mapping")
        _require({"task_id", "group", "cik"} <= row.keys(), "missing_task_field")
        task_id, group = row["task_id"], row["group"]
        _require(isinstance(task_id, str) and bool(task_id), "invalid_task_id")
        _require(task_id not in registry, "duplicate_task:" + task_id)
        _require(isinstance(group, str) and group in GROUPS, "unknown_group")
        registry[task_id] = group, _canonical_cik(row["cik"])
    _require(
        Counter(group for group, _ in registry.values()) == Counter(expected_group_sizes),
        "fixed_group_task_counts",
    )

    scores: dict[tuple[str, int, str], int] = {}
    for row in outcomes:
        _require(isinstance(row, Mapping), "outcome_must_be_mapping")
        _require({"task_id", "seed", "arm", "Q"} <= row.keys(), "missing_outcome_field")
        task_id, seed, arm, value = row["task_id"], row["seed"], row["arm"], row["Q"]
        _require(isinstance(task_id, str) and task_id in registry, "unknown_task")
        _require(type(seed) is int and seed in SEEDS, "unknown_seed")
        _require(isinstance(arm, str) and arm in ARMS, "unknown_arm")
        _require(type(value) in (bool, int) and value in (0, 1), "nonbinary_Q")
        group, cik = registry[task_id]
        if "group" in row:
            _require(row["group"] == group, "unknown_or_changed_outcome_group")
        if "cik" in row:
            _require(_canonical_cik(row["cik"]) == cik, "changed_outcome_cik")
        key = task_id, seed, arm
        _require(key not in scores, "duplicate_outcome:" + repr(key))
        scores[key] = int(value)
    expected_outcomes = len(registry) * len(SEEDS) * len(ARMS)
    _require(len(scores) == expected_outcomes, "missing_outcomes")
    return registry, scores


def _percentile(sorted_values: Sequence[Fraction], probability: Fraction) -> Fraction:
    _require(bool(sorted_values), "empty_percentile_input")
    _require(Fraction(0) <= probability <= Fraction(1), "invalid_percentile")
    position = (len(sorted_values) - 1) * probability
    lower = position.numerator // position.denominator
    remainder = position - lower
    if not remainder:
        return sorted_values[lower]
    return sorted_values[lower] * (1 - remainder) + sorted_values[lower + 1] * remainder


def _rational(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _analyze(
    tasks: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]],
    *,
    expected_group_sizes: Mapping[str, int],
    replicates: int,
    max_draws: int,
    production: bool,
) -> dict[str, Any]:
    _require(type(replicates) is int and replicates > 0, "invalid_replicate_count")
    _require(type(max_draws) is int and max_draws > 0, "invalid_draw_cap")
    _require(
        set(expected_group_sizes) == set(GROUPS)
        and all(type(n) is int and n > 0 for n in expected_group_sizes.values()),
        "invalid_expected_group_sizes",
    )
    registry, scores = _validate(tasks, outcomes, expected_group_sizes)
    ciks = sorted({cik for _, cik in registry.values()})
    group_indices = {group: index for index, group in enumerate(GROUPS)}
    cik_indices = {cik: index for index, cik in enumerate(ciks)}
    cluster_task_counts = [[0] * len(GROUPS) for _ in ciks]
    cluster_difference_sums = [[0] * len(GROUPS) for _ in ciks]
    group_arm_sums = [[0] * len(ARMS) for _ in GROUPS]
    for task_id in sorted(registry):
        group, cik = registry[task_id]
        gi, ci = group_indices[group], cik_indices[cik]
        sums = [sum(scores[task_id, seed, arm] for seed in SEEDS) for arm in ARMS]
        cluster_task_counts[ci][gi] += 1
        cluster_difference_sums[ci][gi] += sums[1] - sums[0]
        for ai in range(len(ARMS)):
            group_arm_sums[gi][ai] += sums[ai]

    group_estimates = []
    point_estimate = Fraction(0)
    for gi, group in enumerate(GROUPS):
        count = expected_group_sizes[group]
        means = [Fraction(total, len(SEEDS) * count) for total in group_arm_sums[gi]]
        effect = means[1] - means[0]
        point_estimate += effect / len(GROUPS)
        group_estimates.append(
            {
                "group": group,
                "task_count": count,
                "cik_count": sum(row[gi] > 0 for row in cluster_task_counts),
                "paired_difference": float(effect),
                "paired_difference_rational": _rational(effect),
                "arm_means": {
                    arm: {"value": float(mean), "rational": _rational(mean)}
                    for arm, mean in zip(ARMS, means, strict=True)
                },
            }
        )

    rng = random.Random(BOOTSTRAP_RANDOM_SEED)
    valid: list[Fraction] = []
    attempted = rejected = 0
    empty_group_counts = dict.fromkeys(GROUPS, 0)
    while len(valid) < replicates and attempted < max_draws:
        attempted += 1
        # One shared cluster draw; no independently sampled groups, arms or seeds.
        weights = Counter(rng.randrange(len(ciks)) for _ in ciks)
        task_counts, difference_sums = [0] * len(GROUPS), [0] * len(GROUPS)
        for ci, weight in weights.items():
            for gi in range(len(GROUPS)):
                task_counts[gi] += weight * cluster_task_counts[ci][gi]
                difference_sums[gi] += weight * cluster_difference_sums[ci][gi]
        empty_groups = [GROUPS[gi] for gi, count in enumerate(task_counts) if count == 0]
        if empty_groups:
            rejected += 1
            for group in empty_groups:
                empty_group_counts[group] += 1
            continue
        valid.append(
            sum(
                (
                    Fraction(total, len(SEEDS) * count)
                    for total, count in zip(difference_sums, task_counts, strict=True)
                ),
                Fraction(0),
            )
            / len(GROUPS)
        )

    complete = len(valid) == replicates
    interval = None
    lower_is_positive = False
    if complete:
        valid.sort()
        lower = _percentile(valid, Fraction(1, 40))
        upper = _percentile(valid, Fraction(39, 40))
        interval = {
            "lower": float(lower),
            "upper": float(upper),
            "lower_rational": _rational(lower),
            "upper_rational": _rational(upper),
        }
        lower_is_positive = lower > 0
    return {
        "schema_version": "fixed_kernel_B_confirmation_statistics.20260922.v1",
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "analysis_scope": "preregistered_confirmation" if production else "synthetic_test_only",
        "task_count": len(registry),
        "outcome_count": len(scores),
        "seeds": list(SEEDS),
        "arms": list(ARMS),
        "group_estimates": group_estimates,
        "point_estimate": float(point_estimate),
        "point_estimate_rational": _rational(point_estimate),
        "ci95": interval,
        "lower_bound_strictly_positive": lower_is_positive,
        "positive_effect_confirmed": production and complete and lower_is_positive,
        "incomplete_reason": (
            None if complete else "draw_cap_reached_before_required_valid_replicates"
        ),
        "bootstrap": {
            "unit": "unique_CIK_cluster",
            "ciks": ciks,
            "cluster_count": len(ciks),
            "clusters_per_draw": len(ciks),
            "cluster_order": "lexicographic_ascending_normalized_10_digit_CIK",
            "random_generator": "random.Random.randrange",
            "random_seed": BOOTSTRAP_RANDOM_SEED,
            "required_valid_replicates": replicates,
            "valid_replicates": len(valid),
            "max_draws": max_draws,
            "attempted_draws": attempted,
            "empty_group_draws_rejected": rejected,
            "rejected_draws_by_empty_group": empty_group_counts,
            "percentiles_rational": ["1/40", "39/40"],
            "quantile_rule": "linear_interpolation_at_(n-1)*p",
            "confidence_level_rational": "19/20",
            "joint_cluster_weights_across_groups_arms_seeds": True,
            "group_denominators": "actual_weighted_task_count_per_draw",
        },
        "interpretation": {
            "estimand": "equal_weight_mean_of_three_group_means_of_three_seed_paired_differences",
            "positive_effect_rule": (
                "COMPLETE_and_exact_ci95_lower_bound_strictly_greater_than_zero"
            ),
            "interval_scope": "source_cluster_resampling_conditional_on_fixed_three_training_seeds",
            "covers_all_training_randomness": False,
            "empty_group_rejection": "conditional_on_all_three_groups_present_in_the_cluster_draw",
            "draw_acceptance_depends_on_effect": False,
            "point_estimate_or_ci_uses_data_selection": False,
            "additional_tasks_or_seed_selection_allowed": False,
        },
    }


def analyze_confirmation(
    tasks: Iterable[Mapping[str, Any]], outcomes: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """Analyze the frozen 720-task B registry under the immutable fixed contract.

    Reject missing, duplicate or unregistered observations with ValueError. An
    exhausted draw cap returns status=INCOMPLETE, ci95=None and no positive-effect
    confirmation. No statistical tuning arguments are exposed by this interface.
    """
    return _analyze(
        tasks,
        outcomes,
        expected_group_sizes=dict.fromkeys(GROUPS, TASKS_PER_GROUP),
        replicates=BOOTSTRAP_REPLICATES,
        max_draws=BOOTSTRAP_MAX_DRAWS,
        production=True,
    )


def analyze_synthetic_for_test(
    tasks: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]],
    *,
    expected_group_sizes: Mapping[str, int],
    replicates: int,
    max_draws: int,
) -> dict[str, Any]:
    """Explicit small synthetic fixture interface; never a production confirmation.

    Names of groups, arms and the three seeds, the PRNG seed, estimator, quantile
    rule and rejection rule remain fixed. Only group sizes and computational
    counts can differ. The result always has positive_effect_confirmed=False.
    """
    return _analyze(
        tasks,
        outcomes,
        expected_group_sizes=expected_group_sizes,
        replicates=replicates,
        max_draws=max_draws,
        production=False,
    )
