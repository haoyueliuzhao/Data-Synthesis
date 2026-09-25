"""Pure synthetic CPU checks; no original/new panel, models, sessions or Q read."""

import copy
import hashlib
import importlib
import random
import subprocess
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
s = importlib.import_module("fixed_kernel_direction_calibration_statistics_20260926")


def fixture(specs, score=None):
    tasks, outcomes = [], []
    if score is None:

        def score(task, seed, arm, mode, repeat):
            return int(arm == "positive")

    for index, (group, cik) in enumerate(specs):
        task = f"synthetic-{index}"
        tasks.append(dict(task_id=task, group=s.GROUPS[group], cik=cik))
        for seed in s.SEEDS:
            for arm in s.ARMS:
                for mode, repeats in s.DECODING_REPEATS.items():
                    for repeat in repeats:
                        outcomes.append(
                            dict(
                                task_id=task,
                                seed=seed,
                                arm=arm,
                                decoding=mode,
                                repeat=repeat,
                                Q=score(index, seed, arm, mode, repeat),
                            )
                        )
    return tasks, outcomes


def run(tasks, outcomes, replicates=127, max_draws=1000):
    return s.analyze_synthetic_for_test(
        tasks,
        outcomes,
        expected_group_sizes=Counter(row["group"] for row in tasks),
        replicates=replicates,
        max_draws=max_draws,
    )


def basic():
    return fixture([(gi, 1) for gi in range(3)])


def literal_effect(tasks, lookup, mode, treatment, reference):
    group_means = []
    for group in s.GROUPS:
        rows = [task for task in tasks if task["group"] == group]
        differences = [
            Fraction(
                sum(
                    lookup[task["task_id"], seed, treatment, mode, repeat]
                    - lookup[task["task_id"], seed, reference, mode, repeat]
                    for seed in s.SEEDS
                    for repeat in s.DECODING_REPEATS[mode]
                ),
                3 * len(s.DECODING_REPEATS[mode]),
            )
            for task in rows
        ]
        group_means.append(sum(differences) / len(rows))
    return sum(group_means) / 3


def test_all_four_comparisons_share_literal_CIK_draws_and_exact_quantiles():
    specs = [(0, 1), (0, 1), (0, 2), (1, 1), (1, 3), (2, 2), (2, 3)]

    def score(task, seed, arm, mode, repeat):
        return int(
            (
                task * (s.ARMS.index(arm) + 1)
                + s.SEEDS.index(seed)
                + repeat * 2
                + int(mode == "greedy")
            )
            % 3
            == 0
        )

    tasks, outcomes = fixture(specs, score)
    result = run(tasks, outcomes)
    lookup = {
        (row["task_id"], row["seed"], row["arm"], row["decoding"], row["repeat"]): row["Q"]
        for row in outcomes
    }
    rng = random.Random(20260926)
    effects = {row[0]: [] for row in s.COMPARISONS}
    draws = rejected = 0
    empty_counts = dict.fromkeys(s.GROUPS, 0)
    weight_hash = hashlib.sha256()
    while len(next(iter(effects.values()))) < 127:
        draws += 1
        sampled = [rng.randrange(3) + 1 for _ in range(3)]
        counts = Counter(sampled)
        weight_hash.update((",".join(str(counts.get(ci, 0)) for ci in (1, 2, 3)) + "\n").encode())
        duplicated = [task for cik in sampled for task in tasks if task["cik"] == cik]
        empty = [
            group for group in s.GROUPS if not any(task["group"] == group for task in duplicated)
        ]
        if empty:
            rejected += 1
            for group in empty:
                empty_counts[group] += 1
            continue
        for name, mode, treatment, reference in s.COMPARISONS:
            effects[name].append(literal_effect(duplicated, lookup, mode, treatment, reference))
    for name, mode, treatment, reference in s.COMPARISONS:
        row = result["comparisons"][name]
        assert Fraction(row["point_estimate_rational"]) == literal_effect(
            tasks, lookup, mode, treatment, reference
        )
        values = sorted(effects[name])
        assert Fraction(row["ci95"]["lower_rational"]) == values[3] * Fraction(17, 20) + values[
            4
        ] * Fraction(3, 20)
        assert Fraction(row["ci95"]["upper_rational"]) == values[122] * Fraction(3, 20) + values[
            123
        ] * Fraction(17, 20)
        counts = row["paired_counts"]
        assert counts["pair_count"] == len(tasks) * 3 * len(s.DECODING_REPEATS[mode])
        assert counts["net_improvements"] == counts["improved"] - counts["degraded"]
        assert counts["pair_count"] == sum(
            counts[key] for key in ("both_fail", "improved", "degraded", "both_pass")
        )
    assert result["bootstrap"]["attempted_draws"] == draws
    assert result["bootstrap"]["empty_group_draws_rejected"] == rejected > 0
    assert result["bootstrap"]["rejected_draws_by_empty_group"] == empty_counts
    assert result["bootstrap"]["attempted_draw_weights_sha256"] == weight_hash.hexdigest()
    assert result == run(list(reversed(tasks)), list(reversed(outcomes)))


def test_stochastic_repeat_average_is_not_added_to_greedy_and_CIK_aliases_merge():
    tasks, outcomes = fixture(
        [(0, "cik:0000000001"), (1, "CIK0000000001"), (2, 1)],
        lambda task, seed, arm, mode, repeat: int(
            arm == "positive" and mode == "stochastic" and repeat == 1
        ),
    )
    result = run(tasks, outcomes)
    assert (
        result["comparisons"]["stochastic_positive_minus_negative"]["point_estimate_rational"]
        == "1/2"
    )
    assert (
        result["comparisons"]["greedy_positive_minus_negative"]["point_estimate_rational"] == "0/1"
    )
    assert result["bootstrap"]["cluster_count"] == 1
    assert result["mechanism_support"] is result["short_run_greedy_support"] is False
    assert result["interpretation"]["decoding_utilities_combined"] is False
    cells = result["comparisons"]["stochastic_positive_minus_static"]["seed_group_repeat_estimates"]
    assert len(cells) == 18 and all(row["paired_counts"]["pair_count"] == 1 for row in cells)


def test_production_requires_both_stochastic_differences_and_is_not_full_confirmation():
    tasks, outcomes = fixture(
        [(gi, 1) for gi in range(3) for _ in range(60)],
        lambda task, seed, arm, mode, repeat: int(
            arm == ("positive" if mode == "stochastic" else "static")
        ),
    )
    result = s.analyze(tasks, outcomes)
    assert result["task_count"] == 180 and result["outcome_count"] == 4860
    assert result["bootstrap"]["valid_replicates"] == 20000
    assert result["mechanism_support"] is True
    assert result["short_run_greedy_support"] is False
    assert result["full_400_step_independent_confirmation"] is False
    assert (
        result["interpretation"]["new_independent_full_training_confirmation_claim_allowed"]
        is False
    )
    for row in outcomes:
        if row["arm"] == "static" and row["decoding"] == "stochastic":
            row["Q"] = 1
    # Smaller private fixture path only to test the same production conjunction.
    second = s._analyze(
        tasks,
        outcomes,
        expected_group_sizes=dict.fromkeys(s.GROUPS, 60),
        replicates=3,
        max_draws=3,
        production=True,
    )
    assert (
        second["comparisons"]["stochastic_positive_minus_negative"]["lower_bound_strictly_positive"]
        is True
    )
    assert (
        second["comparisons"]["stochastic_positive_minus_static"]["lower_bound_strictly_positive"]
        is False
    )
    assert second["mechanism_support"] is False


def test_greedy_support_is_separate_and_requires_both_comparisons():
    tasks, outcomes = fixture(
        [(gi, 1) for gi in range(3)],
        lambda task, seed, arm, mode, repeat: int(arm == "positive" and mode == "greedy"),
    )
    result = s._analyze(
        tasks,
        outcomes,
        expected_group_sizes=dict.fromkeys(s.GROUPS, 1),
        replicates=3,
        max_draws=3,
        production=True,
    )
    assert result["short_run_greedy_support"] is True and result["mechanism_support"] is False
    assert result["full_400_step_independent_confirmation"] is False


def test_rejection_is_outcome_independent_and_cap_incomplete_no_support():
    tasks, outcomes = fixture([(gi, gi + 1) for gi in range(3)])
    result = run(tasks, outcomes, replicates=100, max_draws=10)
    assert result["status"] == "INCOMPLETE"
    assert result["bootstrap"]["attempted_draws"] == 10
    assert result["bootstrap"]["empty_group_draws_rejected"] > 0
    assert all(
        row["ci95"] is None and row["lower_bound_strictly_positive"] is False
        for row in result["comparisons"].values()
    )
    assert result["mechanism_support"] is result["short_run_greedy_support"] is False
    swapped = copy.deepcopy(outcomes)
    for row in swapped:
        row["Q"] = 1 - row["Q"]
    other = run(tasks, swapped, replicates=100, max_draws=10)
    assert (
        result["bootstrap"]["attempted_draw_weights_sha256"]
        == other["bootstrap"]["attempted_draw_weights_sha256"]
    )
    assert (
        result["bootstrap"]["rejected_draws_by_empty_group"]
        == other["bootstrap"]["rejected_draws_by_empty_group"]
    )


def test_exact_zero_endpoint_not_positive_and_not_equivalence():
    tasks, outcomes = fixture([(gi, 1) for gi in range(3)], lambda *args: 0)
    result = run(tasks, outcomes)
    assert all(
        row["ci95"]["lower_rational"] == "0/1" and not row["lower_bound_strictly_positive"]
        for row in result["comparisons"].values()
    )
    assert s._percentile([Fraction(-1, 117), Fraction(1, 3)], Fraction(1, 40)) == 0
    assert result["interpretation"]["zero_crossing_implies_equivalence"] is False


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("task_id", "unknown", "unknown_task"),
        ("seed", 12, "unknown_seed"),
        ("seed", "11", "unknown_seed"),
        ("arm", "delayed_c", "unknown_arm"),
        ("decoding", "combined", "unknown_decoding"),
        ("repeat", 0, "invalid_repeat"),
        ("repeat", True, "invalid_repeat"),
        ("Q", 0.5, "nonbinary_Q"),
        ("Q", 1.0, "nonbinary_Q"),
        ("Q", 2, "nonbinary_Q"),
        ("Q", "1", "nonbinary_Q"),
        ("Q", float("nan"), "nonbinary_Q"),
        ("group", "wrong", "changed_outcome_group"),
        ("cik", 2, "changed_outcome_cik"),
        ("source_cluster", 2, "changed_outcome_source_cluster"),
        ("stochastic", False, "changed_decoding_flag"),
    ],
)
def test_invalid_outcomes_fail_closed(field, value, message):
    tasks, outcomes = basic()
    outcomes[0][field] = value
    with pytest.raises(ValueError, match=message):
        run(tasks, outcomes)


@pytest.mark.parametrize("field", ["task_id", "seed", "arm", "decoding", "repeat", "Q"])
def test_missing_fields_are_not_silently_inferred(field):
    tasks, outcomes = basic()
    del outcomes[0][field]
    with pytest.raises(ValueError, match="missing_outcome_field"):
        run(tasks, outcomes)


def test_duplicate_missing_tasks_or_outcomes_and_registry_changes_rejected():
    tasks, outcomes = basic()
    with pytest.raises(ValueError, match="duplicate_outcome"):
        run(tasks, outcomes + outcomes[:1])
    with pytest.raises(ValueError, match="missing_outcomes"):
        run(tasks, outcomes[:-1])
    with pytest.raises(ValueError, match="duplicate_task"):
        run(tasks + tasks[:1], outcomes)
    bad = copy.deepcopy(tasks)
    bad[0]["cik"] = "not-cik"
    with pytest.raises(ValueError, match="invalid_cik"):
        run(bad, outcomes)
    bad = copy.deepcopy(tasks)
    bad[0]["source_cluster"] = 2
    with pytest.raises(ValueError, match="changed_task_source_cluster"):
        run(bad, outcomes)


def test_production_quota_seed_and_counts_are_immutable():
    tasks, outcomes = basic()
    with pytest.raises(ValueError, match="fixed_group_task_counts"):
        s.analyze(tasks, outcomes)
    with pytest.raises(TypeError):
        s.analyze(tasks, outcomes, replicates=10)
    assert (
        s.TASKS_PER_GROUP,
        s.BOOTSTRAP_REPLICATES,
        s.BOOTSTRAP_MAX_DRAWS,
        s.BOOTSTRAP_RANDOM_SEED,
    ) == (60, 20000, 200000, 20260926)


def test_import_is_standard_library_only_without_GPU_or_network_clients():
    code = (
        "import sys; "
        + f"sys.path.insert(0, {str(SCRIPTS)!r}); "
        + "import fixed_kernel_direction_calibration_statistics_20260926; "
        + "forbidden = {'torch', 'requests', 'httpx', 'urllib.request', 'socket'}; "
        + "assert not forbidden & sys.modules.keys()"
    )
    subprocess.run([sys.executable, "-I", "-S", "-c", code], check=True)
