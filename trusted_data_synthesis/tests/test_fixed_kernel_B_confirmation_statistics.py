"""CPU-only synthetic tests: no confirmation registry, model, scoring or network."""

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
s = importlib.import_module("fixed_kernel_B_confirmation_statistics_20260922")


def fixture_rows(specifications):
    """Each spec contains group index, CIK, static 3-tuple, delayed 3-tuple."""
    tasks, outcomes = [], []
    for index, (group, cik, static, delayed) in enumerate(specifications):
        task_id = f"synthetic-{index}"
        tasks.append(dict(task_id=task_id, group=s.GROUPS[group], cik=cik))
        for seed, base, treatment in zip(s.SEEDS, static, delayed, strict=True):
            outcomes.extend(
                (
                    dict(task_id=task_id, seed=seed, arm="static", Q=base),
                    dict(task_id=task_id, seed=seed, arm="delayed_c", Q=treatment),
                )
            )
    return tasks, outcomes


def analyze(tasks, outcomes, *, replicates=100, max_draws=1000):
    return s.analyze_synthetic_for_test(
        tasks,
        outcomes,
        expected_group_sizes=Counter(row["group"] for row in tasks),
        replicates=replicates,
        max_draws=max_draws,
    )


def basic_rows():
    return fixture_rows([(gi, "0000000001", (0, 0, 0), (1, 1, 1)) for gi in range(3)])


def test_equal_group_weighting_seed_pairing_and_cik_canonicalization():
    tasks, outcomes = fixture_rows(
        [
            (0, 1, (0, 0, 0), (1, 1, 1)),
            (1, "0000000001", (1, 1, 0), (0, 0, 0)),
            (1, "CIK0000000001", (1, 0, 0), (0, 0, 0)),
            (2, "cik:0000000001", (0, 1, 0), (1, 0, 0)),
        ]
    )
    result = analyze(tasks, outcomes)
    assert result["point_estimate_rational"] == "1/6"
    assert result["ci95"]["lower_rational"] == result["ci95"]["upper_rational"] == "1/6"
    assert result["bootstrap"]["cluster_count"] == 1
    assert result["lower_bound_strictly_positive"] is True
    assert result["positive_effect_confirmed"] is False  # Explicit synthetic-only output.
    assert result["group_estimates"][1]["paired_difference_rational"] == "-1/2"
    assert result == analyze(list(reversed(tasks)), list(reversed(outcomes)))


def test_joint_cik_resampling_matches_independent_literal_reference():
    tasks, outcomes = fixture_rows(
        [
            (0, 1, (0, 0, 0), (1, 1, 1)),
            (0, 1, (0, 1, 1), (0, 0, 0)),
            (0, 2, (0, 0, 0), (1, 0, 0)),
            (1, 1, (1, 1, 1), (0, 0, 0)),
            (1, 3, (0, 0, 0), (0, 1, 1)),
            (2, 2, (1, 0, 0), (0, 1, 0)),
            (2, 3, (0, 0, 0), (1, 1, 1)),
        ]
    )
    result = analyze(tasks, outcomes, replicates=127)
    lookup = {(row["task_id"], row["seed"], row["arm"]): row["Q"] for row in outcomes}
    rng = random.Random(20260922)
    effects, rejected, draws = [], 0, 0
    empty_counts = dict.fromkeys(s.GROUPS, 0)
    while len(effects) < 127:
        draws += 1
        sampled_ciks = [rng.randrange(3) + 1 for _ in range(3)]
        # Literal duplication of all tasks in each sampled cluster, unlike the
        # implementation's integer sufficient-statistic accumulation.
        duplicated = [task for cik in sampled_ciks for task in tasks if task["cik"] == cik]
        missing = [group for group in s.GROUPS if not any(t["group"] == group for t in duplicated)]
        if missing:
            rejected += 1
            for group in missing:
                empty_counts[group] += 1
            continue
        group_means = []
        for group in s.GROUPS:
            values = [
                Fraction(
                    sum(
                        lookup[task["task_id"], seed, "delayed_c"]
                        - lookup[task["task_id"], seed, "static"]
                        for seed in s.SEEDS
                    ),
                    3,
                )
                for task in duplicated if task["group"] == group
            ]
            group_means.append(sum(values) / len(values))
        effects.append(sum(group_means) / 3)
    effects.sort()
    # 126 * .025 = 3.15; 126 * .975 = 122.85, evaluated exactly.
    lower = effects[3] * Fraction(17, 20) + effects[4] * Fraction(3, 20)
    upper = effects[122] * Fraction(3, 20) + effects[123] * Fraction(17, 20)
    assert Fraction(result["ci95"]["lower_rational"]) == lower
    assert Fraction(result["ci95"]["upper_rational"]) == upper
    assert result["bootstrap"]["attempted_draws"] == draws
    assert result["bootstrap"]["empty_group_draws_rejected"] == rejected > 0
    assert result["bootstrap"]["rejected_draws_by_empty_group"] == empty_counts


def test_draw_cap_is_incomplete_even_with_positive_observed_effect():
    tasks, outcomes = fixture_rows(
        [(gi, gi + 1, (0, 0, 0), (1, 1, 1)) for gi in range(3)]
    )
    result = analyze(tasks, outcomes, replicates=100, max_draws=10)
    assert result["status"] == "INCOMPLETE"
    assert result["point_estimate_rational"] == "1/1"
    assert result["ci95"] is None
    assert result["positive_effect_confirmed"] is False
    assert result["lower_bound_strictly_positive"] is False
    assert result["bootstrap"]["attempted_draws"] == 10
    assert result["bootstrap"]["valid_replicates"] < 100
    assert result["bootstrap"]["empty_group_draws_rejected"] > 0


def test_zero_exact_lower_bound_never_counts_as_positive():
    tasks, outcomes = fixture_rows(
        [
            (0, 1, (0, 0, 0), (1, 0, 0)),
            (1, 1, (0, 0, 0), (1, 0, 0)),
            (2, 1, (1, 1, 0), (0, 0, 0)),
        ]
    )
    result = analyze(tasks, outcomes)
    assert result["point_estimate_rational"] == "0/1"
    assert result["ci95"]["lower_rational"] == "0/1"
    assert result["lower_bound_strictly_positive"] is False
    assert s._percentile([Fraction(-1, 3), Fraction(1, 3)], Fraction(1, 2)) == 0
    # The lower percentile is exactly zero despite cancellation of two fractions.
    assert s._percentile([Fraction(-1, 117), Fraction(1, 3)], Fraction(1, 40)) == 0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("task_id", "unregistered", "unknown_task"),
        ("seed", 12, "unknown_seed"),
        ("seed", "11", "unknown_seed"),
        ("arm", "delayed_C", "unknown_arm"),
        ("Q", 2, "nonbinary_Q"),
        ("Q", -1, "nonbinary_Q"),
        ("Q", 1.0, "nonbinary_Q"),
        ("Q", "1", "nonbinary_Q"),
        ("Q", float("nan"), "nonbinary_Q"),
        ("group", "unregistered", "unknown_or_changed_outcome_group"),
        ("cik", 2, "changed_outcome_cik"),
    ],
)
def test_invalid_outcome_is_rejected(field, value, message):
    tasks, outcomes = basic_rows()
    outcomes[0][field] = value
    with pytest.raises(ValueError, match=message):
        analyze(tasks, outcomes)


@pytest.mark.parametrize("field", ["task_id", "seed", "arm", "Q"])
def test_missing_outcome_field_is_rejected(field):
    tasks, outcomes = basic_rows()
    del outcomes[0][field]
    with pytest.raises(ValueError, match="missing_outcome_field"):
        analyze(tasks, outcomes)


def test_duplicate_or_missing_outcomes_are_rejected():
    tasks, outcomes = basic_rows()
    with pytest.raises(ValueError, match="duplicate_outcome"):
        analyze(tasks, outcomes + outcomes[:1])
    with pytest.raises(ValueError, match="missing_outcomes"):
        analyze(tasks, outcomes[:-1])


def test_registry_duplicates_unknown_groups_and_bad_ciks_are_rejected():
    tasks, outcomes = basic_rows()
    with pytest.raises(ValueError, match="duplicate_task"):
        analyze(tasks + tasks[:1], outcomes)
    tasks[0]["group"] = "unregistered"
    with pytest.raises(ValueError, match="unknown_group"):
        s.analyze_confirmation(tasks, outcomes)
    tasks[0]["group"] = s.GROUPS[0]
    tasks[0]["cik"] = "not-a-CIK"
    with pytest.raises(ValueError, match="invalid_cik"):
        analyze(tasks, outcomes)


def test_production_shape_and_parameters_are_fixed():
    tasks, outcomes = basic_rows()
    with pytest.raises(ValueError, match="fixed_group_task_counts"):
        s.analyze_confirmation(tasks, outcomes)
    with pytest.raises(TypeError):
        s.analyze_confirmation(tasks, outcomes, random_seed=1)
    assert (s.BOOTSTRAP_REPLICATES, s.BOOTSTRAP_MAX_DRAWS, s.BOOTSTRAP_RANDOM_SEED) == (
        20_000, 200_000, 20260922
    )


def test_import_does_not_load_torch_or_network_clients():
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(SCRIPTS)!r}); "
        "import fixed_kernel_B_confirmation_statistics_20260922; "
        "assert not {'torch', 'requests', 'httpx', 'urllib.request', 'socket'} & sys.modules.keys()"
    )
    subprocess.run([sys.executable, "-I", "-S", "-c", code], check=True)
