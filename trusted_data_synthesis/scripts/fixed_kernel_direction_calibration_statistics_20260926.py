"""Frozen short-run direction calibration statistics; standard library only.

Production ``analyze(tasks, outcomes)`` requires 180 tasks, three groups of 60,
three fixed seeds and three arms. Each task/seed/arm has stochastic repeats 1/2
and greedy repeat 0: exactly 4,860 binary outcomes. The two decoding utilities
are never added together. Outcome fields are task_id, seed, arm, decoding,
repeat, Q; task fields are task_id, group, cik.

Four marginal percentile intervals use exactly the same CIK bootstrap draws.
Each draw duplicates whole source clusters jointly across groups, arms, seeds,
repeats and decoding modes. Empty-group draws are rejected irrespective of Q.
Within a task, seed/repeat differences are averaged first; tasks are averaged
within groups, then the three group means receive equal weight. Exact Fraction
arithmetic governs estimates, interpolated endpoints and strictly-positive
lower-bound decisions. The fixed draw cap cannot be enlarged based on outcomes.

This is short-run mechanism calibration, not a new full-400-step independent
confirmation. Even positive stochastic and greedy flags do not imply that claim.
An interval containing zero is not evidence of equivalence. These intervals
condition on the three fixed trained seeds and do not cover all training noise.
"""

from __future__ import annotations

import hashlib
import random
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction
from typing import Any

GROUPS = ("composition_required", "dual_sufficient", "other_financial")
SEEDS = (11, 29, 47)
ARMS = ("static", "positive", "negative")
DECODING_REPEATS = {"stochastic": (1, 2), "greedy": (0,)}
COMPARISONS = tuple(
    (f"{decoding}_positive_minus_{reference}", decoding, "positive", reference)
    for decoding in DECODING_REPEATS
    for reference in ("negative", "static")
)
TASKS_PER_GROUP = 60
BOOTSTRAP_REPLICATES = 20_000
BOOTSTRAP_MAX_DRAWS = 200_000
BOOTSTRAP_RANDOM_SEED = 20260926


def _require(condition, message):
    if not condition:
        raise ValueError("direction_calibration_statistics." + message)


def _canonical_cik(value):
    if type(value) is int:
        number = value
    elif isinstance(value, str):
        digits = (
            value[4:]
            if value.startswith("cik:")
            else value[3:]
            if value.startswith("CIK")
            else value
        )
        _require(
            bool(digits) and digits.isascii() and digits.isdigit() and len(digits) <= 10,
            "invalid_cik",
        )
        number = int(digits)
    else:
        raise ValueError("direction_calibration_statistics.invalid_cik")
    _require(0 < number < 10**10, "invalid_cik")
    return f"{number:010d}"


def _validate(tasks, outcomes, expected_group_sizes):
    registry, scores = {}, {}
    for row in tasks:
        _require(isinstance(row, Mapping), "task_must_be_mapping")
        _require({"task_id", "group", "cik"} <= row.keys(), "missing_task_field")
        task, group = row["task_id"], row["group"]
        _require(isinstance(task, str) and bool(task), "invalid_task_id")
        _require(task not in registry, "duplicate_task:" + task)
        _require(isinstance(group, str) and group in GROUPS, "unknown_group")
        cik = _canonical_cik(row["cik"])
        if "source_cluster" in row:
            _require(_canonical_cik(row["source_cluster"]) == cik, "changed_task_source_cluster")
        registry[task] = group, cik
    _require(
        Counter(group for group, _ in registry.values()) == Counter(expected_group_sizes),
        "fixed_group_task_counts",
    )
    for row in outcomes:
        _require(isinstance(row, Mapping), "outcome_must_be_mapping")
        _require(
            {"task_id", "seed", "arm", "decoding", "repeat", "Q"} <= row.keys(),
            "missing_outcome_field",
        )
        task, seed, arm = row["task_id"], row["seed"], row["arm"]
        decoding, repeat, value = row["decoding"], row["repeat"], row["Q"]
        _require(isinstance(task, str) and task in registry, "unknown_task")
        _require(type(seed) is int and seed in SEEDS, "unknown_seed")
        _require(isinstance(arm, str) and arm in ARMS, "unknown_arm")
        _require(isinstance(decoding, str) and decoding in DECODING_REPEATS, "unknown_decoding")
        _require(
            type(repeat) is int and repeat in DECODING_REPEATS[decoding],
            "invalid_repeat_for_decoding",
        )
        _require(type(value) in (bool, int) and value in (0, 1), "nonbinary_Q")
        group, cik = registry[task]
        if "group" in row:
            _require(row["group"] == group, "changed_outcome_group")
        if "cik" in row:
            _require(_canonical_cik(row["cik"]) == cik, "changed_outcome_cik")
        if "source_cluster" in row:
            _require(_canonical_cik(row["source_cluster"]) == cik, "changed_outcome_source_cluster")
        if "stochastic" in row:
            _require(
                type(row["stochastic"]) is bool and row["stochastic"] == (decoding == "stochastic"),
                "changed_decoding_flag",
            )
        key = task, seed, arm, decoding, repeat
        _require(key not in scores, "duplicate_outcome:" + repr(key))
        scores[key] = int(value)
    _require(len(scores) == len(registry) * len(SEEDS) * len(ARMS) * 3, "missing_outcomes")
    return registry, scores


def _rational(value):
    return f"{value.numerator}/{value.denominator}"


def _quantity(value):
    return dict(value=float(value), rational=_rational(value))


def _percentile(sorted_values: Sequence[Fraction], probability: Fraction):
    _require(bool(sorted_values), "empty_percentile_input")
    _require(Fraction(0) <= probability <= Fraction(1), "invalid_percentile")
    position = (len(sorted_values) - 1) * probability
    lower = position.numerator // position.denominator
    remainder = position - lower
    return (
        sorted_values[lower]
        if not remainder
        else sorted_values[lower] * (1 - remainder) + sorted_values[lower + 1] * remainder
    )


def _paired_counts(scores, tasks, seeds, decoding, repeats, treatment, reference):
    cells = Counter(
        (
            scores[task, seed, reference, decoding, repeat],
            scores[task, seed, treatment, decoding, repeat],
        )
        for task in tasks
        for seed in seeds
        for repeat in repeats
    )
    return dict(
        pair_count=sum(cells.values()),
        both_fail=cells[0, 0],
        improved=cells[0, 1],
        degraded=cells[1, 0],
        both_pass=cells[1, 1],
        net_improvements=cells[0, 1] - cells[1, 0],
        pairs_are_task_seed_repeat_records_not_independent_tasks=True,
    )


def _description(registry, scores, expected_sizes, comparison):
    name, decoding, treatment, reference = comparison
    repeats = DECODING_REPEATS[decoding]
    grouped = {
        group: [task for task in sorted(registry) if registry[task][0] == group] for group in GROUPS
    }
    by_group, by_seed, by_seed_group_repeat = [], [], []
    effect = Fraction(0)
    for group, tasks in grouped.items():
        means = {
            arm: Fraction(
                sum(
                    scores[task, seed, arm, decoding, repeat]
                    for task in tasks
                    for seed in SEEDS
                    for repeat in repeats
                ),
                len(tasks) * len(SEEDS) * len(repeats),
            )
            for arm in ARMS
        }
        difference = means[treatment] - means[reference]
        effect += difference / len(GROUPS)
        by_group.append(
            dict(
                group=group,
                task_count=len(tasks),
                cik_count=len({registry[task][1] for task in tasks}),
                arm_means={arm: _quantity(mean) for arm, mean in means.items()},
                difference=_quantity(difference),
                paired_counts=_paired_counts(
                    scores, tasks, SEEDS, decoding, repeats, treatment, reference
                ),
            )
        )
    for seed in SEEDS:
        seed_means = {arm: Fraction(0) for arm in ARMS}
        for group, tasks in grouped.items():
            for arm in ARMS:
                seed_means[arm] += Fraction(
                    sum(
                        scores[task, seed, arm, decoding, repeat]
                        for task in tasks
                        for repeat in repeats
                    ),
                    len(tasks) * len(repeats) * len(GROUPS),
                )
            for repeat in repeats:
                means = {
                    arm: Fraction(
                        sum(scores[task, seed, arm, decoding, repeat] for task in tasks), len(tasks)
                    )
                    for arm in ARMS
                }
                by_seed_group_repeat.append(
                    dict(
                        seed=seed,
                        group=group,
                        repeat=repeat,
                        arm_means={arm: _quantity(mean) for arm, mean in means.items()},
                        difference=_quantity(means[treatment] - means[reference]),
                        paired_counts=_paired_counts(
                            scores, tasks, (seed,), decoding, (repeat,), treatment, reference
                        ),
                    )
                )
        by_seed.append(
            dict(
                seed=seed,
                arm_means={arm: _quantity(mean) for arm, mean in seed_means.items()},
                difference=_quantity(seed_means[treatment] - seed_means[reference]),
                paired_counts=_paired_counts(
                    scores, registry, (seed,), decoding, repeats, treatment, reference
                ),
            )
        )
    return dict(
        comparison=name,
        decoding=decoding,
        treatment=treatment,
        reference=reference,
        point_estimate=float(effect),
        point_estimate_rational=_rational(effect),
        paired_counts=_paired_counts(
            scores, registry, SEEDS, decoding, repeats, treatment, reference
        ),
        group_estimates=by_group,
        seed_estimates=by_seed,
        seed_group_repeat_estimates=by_seed_group_repeat,
    )


def _analyze(tasks, outcomes, *, expected_group_sizes, replicates, max_draws, production):
    _require(type(replicates) is int and replicates > 0, "invalid_replicate_count")
    _require(type(max_draws) is int and max_draws > 0, "invalid_draw_cap")
    _require(
        set(expected_group_sizes) == set(GROUPS)
        and all(type(n) is int and n > 0 for n in expected_group_sizes.values()),
        "invalid_expected_group_sizes",
    )
    registry, scores = _validate(tasks, outcomes, expected_group_sizes)
    ciks = sorted({cik for _, cik in registry.values()})
    cik_indices = {cik: index for index, cik in enumerate(ciks)}
    group_indices = {group: index for index, group in enumerate(GROUPS)}
    counts = [[0] * len(GROUPS) for _ in ciks]
    difference_sums = [[[0] * len(COMPARISONS) for _ in GROUPS] for _ in ciks]
    for task in sorted(registry):
        group, cik = registry[task]
        ci, gi = cik_indices[cik], group_indices[group]
        counts[ci][gi] += 1
        for qi, (_, decoding, treatment, reference) in enumerate(COMPARISONS):
            difference_sums[ci][gi][qi] += sum(
                scores[task, seed, treatment, decoding, repeat]
                - scores[task, seed, reference, decoding, repeat]
                for seed in SEEDS
                for repeat in DECODING_REPEATS[decoding]
            )
    descriptions = {
        row[0]: _description(registry, scores, expected_group_sizes, row) for row in COMPARISONS
    }
    rng = random.Random(BOOTSTRAP_RANDOM_SEED)
    values = [[] for _ in COMPARISONS]
    attempted = rejected = 0
    empty_counts = dict.fromkeys(GROUPS, 0)
    weight_hash, effect_hash = hashlib.sha256(), hashlib.sha256()
    while len(values[0]) < replicates and attempted < max_draws:
        attempted += 1
        weights = Counter(rng.randrange(len(ciks)) for _ in ciks)
        weight_hash.update(
            (",".join(str(weights.get(ci, 0)) for ci in range(len(ciks))) + "\n").encode()
        )
        task_counts = [0] * len(GROUPS)
        sums = [[0] * len(COMPARISONS) for _ in GROUPS]
        for ci, weight in weights.items():
            for gi in range(len(GROUPS)):
                task_counts[gi] += weight * counts[ci][gi]
                for qi in range(len(COMPARISONS)):
                    sums[gi][qi] += weight * difference_sums[ci][gi][qi]
        empty = [GROUPS[gi] for gi, count in enumerate(task_counts) if count == 0]
        if empty:
            rejected += 1
            for group in empty:
                empty_counts[group] += 1
            continue
        draw = []
        for qi, (_, decoding, _, _) in enumerate(COMPARISONS):
            effect = sum(
                (
                    Fraction(sums[gi][qi], count * len(SEEDS) * len(DECODING_REPEATS[decoding]))
                    for gi, count in enumerate(task_counts)
                ),
                Fraction(0),
            ) / len(GROUPS)
            values[qi].append(effect)
            draw.append(_rational(effect))
        effect_hash.update((",".join(draw) + "\n").encode())
    complete = len(values[0]) == replicates
    for qi, (name, _, _, _) in enumerate(COMPARISONS):
        interval, positive = None, False
        if complete:
            values[qi].sort()
            lower = _percentile(values[qi], Fraction(1, 40))
            upper = _percentile(values[qi], Fraction(39, 40))
            interval = dict(
                lower=float(lower),
                upper=float(upper),
                lower_rational=_rational(lower),
                upper_rational=_rational(upper),
            )
            positive = lower > 0
        descriptions[name].update(ci95=interval, lower_bound_strictly_positive=positive)
    supported = {
        decoding: complete
        and all(
            descriptions[f"{decoding}_positive_minus_{reference}"]["lower_bound_strictly_positive"]
            for reference in ("negative", "static")
        )
        for decoding in DECODING_REPEATS
    }
    return dict(
        schema_version="fixed_kernel_direction_calibration_statistics.20260926.v1",
        status="COMPLETE" if complete else "INCOMPLETE",
        analysis_scope="short_run_direction_calibration" if production else "synthetic_test_only",
        primary_comparison="stochastic_positive_minus_negative",
        required_concurrent_comparison="stochastic_positive_minus_static",
        task_count=len(registry),
        outcome_count=len(scores),
        seeds=list(SEEDS),
        arms=list(ARMS),
        decoding_repeats={mode: list(repeats) for mode, repeats in DECODING_REPEATS.items()},
        comparisons=descriptions,
        mechanism_support=production and supported["stochastic"],
        short_run_greedy_support=production and supported["greedy"],
        full_400_step_independent_confirmation=False,
        incomplete_reason=None if complete else "draw_cap_reached_before_required_valid_replicates",
        bootstrap=dict(
            unit="unique_CIK_cluster",
            ciks=ciks,
            cluster_count=len(ciks),
            clusters_per_draw=len(ciks),
            cluster_order="lexicographic_ascending_normalized_10_digit_CIK",
            random_generator="random.Random.randrange",
            random_seed=BOOTSTRAP_RANDOM_SEED,
            required_valid_replicates=replicates,
            valid_replicates=len(values[0]),
            max_draws=max_draws,
            attempted_draws=attempted,
            empty_group_draws_rejected=rejected,
            rejected_draws_by_empty_group=empty_counts,
            percentiles_rational=["1/40", "39/40"],
            confidence_level_rational="19/20",
            quantile_rule="linear_interpolation_at_(n-1)*p",
            group_denominators="actual_weighted_task_count_per_draw",
            joint_weights_across_groups_arms_seeds_repeats_decodings_and_all_four_comparisons=True,
            attempted_draw_weights_sha256=weight_hash.hexdigest(),
            valid_joint_effects_sha256=effect_hash.hexdigest(),
            hash_encoding=(
                "ASCII comma-separated fixed-order integers or numerator/denominator, "
                "newline per draw"
            ),
            effect_hash_comparison_order=[row[0] for row in COMPARISONS],
        ),
        interpretation=dict(
            estimand="task_seed_repeat_paired_average_then_group_task_average_then_three_groups_equal_weight",
            mechanism_rule="COMPLETE_and_both_stochastic_exact_CI_lower_bounds_strictly_positive",
            short_run_greedy_rule="COMPLETE_and_both_greedy_exact_CI_lower_bounds_strictly_positive",
            decoding_utilities_combined=False,
            intervals_are_marginal_not_simultaneous=True,
            interval_scope="source_cluster_resampling_conditional_on_fixed_three_trained_seeds_and_repeat_design",
            covers_all_training_randomness=False,
            repeats_counted_as_independent_tasks=False,
            empty_group_rejection="conditional_on_all_three_groups_present",
            draw_acceptance_depends_on_outcomes=False,
            zero_crossing_implies_equivalence=False,
            additional_tasks_or_seeds_allowed=False,
            dropping_any_group_allowed=False,
            outcome_based_candidate_or_decoder_selection_allowed=False,
            new_independent_full_training_confirmation_claim_allowed=False,
        ),
    )


def analyze(
    tasks: Iterable[Mapping[str, Any]], outcomes: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """Strict 180/4860 production entry; no tuning or optional selection arguments."""
    return _analyze(
        tasks,
        outcomes,
        expected_group_sizes=dict.fromkeys(GROUPS, TASKS_PER_GROUP),
        replicates=BOOTSTRAP_REPLICATES,
        max_draws=BOOTSTRAP_MAX_DRAWS,
        production=True,
    )


def analyze_synthetic_for_test(tasks, outcomes, *, expected_group_sizes, replicates, max_draws):
    """Same estimator with smaller fixtures; never issues a production support flag."""
    return _analyze(
        tasks,
        outcomes,
        expected_group_sizes=expected_group_sizes,
        replicates=replicates,
        max_draws=max_draws,
        production=False,
    )
