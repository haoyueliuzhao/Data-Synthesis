"""Prospective V54 paired summaries; three fixed parents, no selection or p-values.

Native UNKNOWNs retain the registered denominator and invalidate only affected
comparisons. Source resampling is sensitivity conditional on the fixed parents.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter

import numpy as np

SEEDS = (137, 251, 389)
ARMS = ("Hold", "C1", "C05")
COMPARISONS = (("C05", "C1"), ("C05", "Hold"), ("C1", "Hold"))
BOOTSTRAP_REPLICATES = 10000
BOOTSTRAP_SEED = 20261018
T95_DF2 = 4.3026527299


def require(condition, message):
    if not condition:
        raise ValueError(message)


def coordinate(seed, arm):
    require(type(seed) is int and seed in SEEDS and arm in ARMS, "unregistered V54 branch")
    return f"seed{seed}/{arm}"


def statistics_contract():
    return dict(
        primary="step894 dev883 greedy native execution accuracy: C05-C1",
        key_secondary="C05-Hold",
        other_comparison="C1-Hold",
        seeds=list(SEEDS), arms=list(ARMS), independent_parent_count=3,
        task_denominator=883,
        estimate="equal-weight mean of three within-parent paired full-denominator differences",
        seed_dispersion=["sample SD ddof=1", "minimum", "maximum", "positive/zero/negative counts"],
        seed_interval=dict(level=0.95, df=2, n=3, critical_value=T95_DF2,
                           formula="mean +/- t(0.975,2) * sample_SD / sqrt(3)",
                           approximate=True, clipped=False, multiplicity_adjusted=False,
                           scope="strong untestable approximately-normal seed-effect assumption at n=3"),
        source_cluster=dict(
            replicates=BOOTSTRAP_REPLICATES, seed=BOOTSTRAP_SEED,
            rng="numpy.random.Generator(numpy.random.PCG64(seed))",
            ordered_clusters="lexicographically sorted original lineage.source_group",
            draw="G iid uniform source-cluster indices with replacement per replicate",
            same_cluster_weights_for_all_three_seeds_and_all_arms=True,
            statistic="sum(sampled cluster paired sums) / sum(sampled cluster question counts)",
            task_weighted=True, percentile_interval=[0.025, 0.975], quantile_method="linear",
            scope="source-composition sensitivity conditional on the same three fixed parents",
            replaces_seed_uncertainty=False),
        transition_orientation="baseline -> candidate; I invalid, W executable wrong, R correct",
        exact_decomposition="(I->R - R->I + W->R - R->W) / full denominator",
        unknown_as_zero=False, unknown_denominator_reduction=False,
        unknown_makes_affected_comparison_incomplete=True,
        advancement="all scientific contracts complete AND C05-C1 > 0 AND C05-Hold > 0",
        advancement_is_directional_development_filter=True,
        exact_zero_retains_baseline=True, no_p_values=True,
        significance_or_stability_confirmation=False,
        nine_branches_or_eighteen_snapshots_are_not_independent_training_repeats=True,
    )


def native_state(row):
    value = row["native"]
    execution = value["native"]["execution_accuracy"]
    require(execution is None or type(execution) in (int, float) and execution in (0, 1),
            "native execution must be binary or explicit UNKNOWN")
    if execution is None:
        require(value["status"] == "unknown", "missing metric must retain native unknown status")
        return "UNKNOWN"
    if value["status"] == "invalid_prediction":
        require(execution == 0 and value["program_executable"] is False,
                "invalid prediction/native execution contradiction")
        return "I"
    require(value["status"] == "scored" and value["program_executable"] is True,
            "known native result requires actual executable or invalid status")
    return "R" if execution == 1 else "W"


def native_metrics(rows, denominator):
    require(len(rows) == denominator, "retain complete registered native denominator")
    states = [native_state(row) for row in rows]
    result = {}
    for metric in ("execution_accuracy", "program_accuracy"):
        values = [row["native"]["native"][metric] for row in rows]
        require(all(v is None or type(v) in (int, float) and v in (0, 1) for v in values),
                "native metrics must be binary or explicit UNKNOWN")
        known = [v for v in values if v is not None]
        result[metric] = dict(denominator=denominator, scored=len(known),
                             unknown=denominator - len(known), correct=sum(known),
                             complete_dataset_mean=(sum(known) / denominator
                                                    if len(known) == denominator else None))
    result["states"] = {state: states.count(state) for state in ("I", "W", "R", "UNKNOWN")}
    return result


def seed_effect_summary(values, *, count_differences=None, denominator=None):
    require(len(values) == 3 and all(math.isfinite(v) for v in values), "exactly three finite seed effects")
    if count_differences is not None:
        require(len(count_differences) == 3 and all(type(n) is int for n in count_differences)
                and type(denominator) is int and denominator > 0
                and values == [n / denominator for n in count_differences],
                "paired integer count differences must match the full denominator")
        # The directional decision must preserve mathematically exact zero;
        # cancellation residue from floating arithmetic cannot promote C05.
        mean = sum(count_differences) / (3 * denominator)
    else:
        mean = math.fsum(values) / 3
    sd = math.sqrt(math.fsum((v - mean) ** 2 for v in values) / 2)
    half = T95_DF2 * sd / math.sqrt(3)
    return dict(n=3, mean=mean, mean_pp=100 * mean, sample_SD=sd, minimum=min(values),
                maximum=max(values), positive=sum(v > 0 for v in values),
                zero=sum(v == 0 for v in values), negative=sum(v < 0 for v in values),
                seed_t_approximate_interval=dict(lower=mean - half, upper=mean + half,
                    level=0.95, df=2, critical_value=T95_DF2, clipped=False,
                    small_sample_warning=True, multiplicity_adjusted=False))


def paired_transitions(candidate, baseline, denominator):
    require(len(candidate) == len(baseline) == denominator, "paired full denominator required")
    left, right = [native_state(v) for v in candidate], [native_state(v) for v in baseline]
    unknown = [i for i, pair in enumerate(zip(left, right, strict=True)) if "UNKNOWN" in pair]
    transitions = Counter(f"{b}->{a}" for a, b in zip(left, right, strict=True))
    value = dict(denominator=denominator, status="INCOMPLETE" if unknown else "COMPLETE",
                 unknown_pair_indices=unknown, unknown_pair_count=len(unknown),
                 transitions={f"{b}->{a}": transitions[f"{b}->{a}"]
                              for b in ("I", "W", "R", "UNKNOWN")
                              for a in ("I", "W", "R", "UNKNOWN")},
                 difference=None, decomposition=None)
    if unknown:
        return value
    invalid_net = transitions["I->R"] - transitions["R->I"]
    wrong_net = transitions["W->R"] - transitions["R->W"]
    numerator = left.count("R") - right.count("R")
    require(numerator == invalid_net + wrong_net, "exact native-accuracy decomposition failed")
    executable = [i for i, (a, b) in enumerate(zip(left, right, strict=True))
                  if a in ("W", "R") and b in ("W", "R")]
    value.update(
        candidate_accuracy=left.count("R") / denominator,
        baseline_accuracy=right.count("R") / denominator,
        difference=numerator / denominator, numerator=numerator,
        decomposition=dict(invalid_correct_net_count=invalid_net, wrong_correct_net_count=wrong_net,
                           invalid_correct_component=invalid_net / denominator,
                           wrong_correct_component=wrong_net / denominator,
                           numerator=numerator, denominator=denominator, exact_count_identity=True),
        both_executable=dict(denominator=len(executable),
            candidate_accuracy=(sum(left[i] == "R" for i in executable) / len(executable)
                                if executable else None),
            baseline_accuracy=(sum(right[i] == "R" for i in executable) / len(executable)
                               if executable else None),
            explanatory_only=True))
    return value


def source_cluster_sensitivity(per_question, groups):
    """One common cluster draw vector for every available paired comparison."""
    require(groups and all(isinstance(g, str) and g for g in groups), "fixed nonempty source groups required")
    labels = sorted(set(groups))
    indices = {g: i for i, g in enumerate(labels)}
    codes = np.asarray([indices[g] for g in groups], dtype=np.int64)
    counts = np.bincount(codes, minlength=len(labels))
    names = sorted(per_question)
    if not names:
        return dict(status="INCOMPLETE", comparisons={}, shared_weight_sha256=None)
    values = np.asarray([per_question[name] for name in names], dtype=np.float64)
    require(values.shape == (len(names), len(groups)) and np.isfinite(values).all(),
            "finite paired task vectors required for source sensitivity")
    sums = np.stack([np.bincount(codes, weights=v, minlength=len(labels)) for v in values])
    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    draws = np.empty((BOOTSTRAP_REPLICATES, len(names)), dtype=np.float64)
    weights_hash = hashlib.sha256()
    for replicate in range(BOOTSTRAP_REPLICATES):
        sampled = rng.integers(0, len(labels), size=len(labels))
        weights_hash.update(sampled.astype("<i8").tobytes())
        draws[replicate] = sums[:, sampled].sum(axis=1) / counts[sampled].sum()
    intervals = np.quantile(draws, [0.025, 0.975], axis=0, method="linear")
    return dict(status="COMPLETE", replicates=BOOTSTRAP_REPLICATES, seed=BOOTSTRAP_SEED,
        cluster_count=len(labels), task_count=len(groups),
        cluster_task_counts=dict(zip(labels, counts.tolist(), strict=True)),
        shared_weight_sha256=weights_hash.hexdigest(),
        same_weights_all_seeds_and_arms=True, task_weighted=True,
        uncertainty_scope=statistics_contract()["source_cluster"]["scope"],
        comparisons={name: dict(mean_difference=float(values[j].mean()),
            lower=float(intervals[0, j]), upper=float(intervals[1, j]), level=0.95,
            bootstrap_values_sha256=hashlib.sha256(draws[:, j].astype("<f8").tobytes()).hexdigest())
            for j, name in enumerate(names)})


def paired_summary(reports, tasks, source_groups, *, denominator=883):
    require(len(tasks) == len(set(tasks)) == denominator and set(source_groups) == set(tasks),
            "identical ordered cohort and original source mapping required")
    require(set(reports) == {coordinate(s, a) for s in SEEDS for a in ARMS},
            "all nine fixed branches must be reported before analysis")
    for key, report in reports.items():
        require(key == coordinate(report["seed"], report["arm"])
                and report["denominator"] == denominator
                and [row["task_key"] for row in report["results"]] == tasks,
                "paired report coordinate or task order changed")
        require(report["metrics"] == native_metrics(report["results"], denominator),
                "native metric aggregate differs from actual result rows")
    comparisons, vectors = {}, {}
    for candidate, baseline in COMPARISONS:
        name = f"{candidate}-{baseline}"
        seeds = {str(seed): paired_transitions(reports[coordinate(seed, candidate)]["results"],
                    reports[coordinate(seed, baseline)]["results"], denominator) for seed in SEEDS}
        complete = all(row["status"] == "COMPLETE" for row in seeds.values())
        comparisons[name] = dict(status="COMPLETE" if complete else "INCOMPLETE",
            denominator=denominator, per_seed=seeds,
            seed_summary=(seed_effect_summary([row["difference"] for row in seeds.values()],
                count_differences=[row["numerator"] for row in seeds.values()], denominator=denominator)
                          if complete else None))
        if complete:
            vectors[name] = [math.fsum(
                reports[coordinate(seed, candidate)]["results"][i]["native"]["native"]["execution_accuracy"]
                - reports[coordinate(seed, baseline)]["results"][i]["native"]["native"]["execution_accuracy"]
                for seed in SEEDS) / 3 for i in range(denominator)]
    groups = [source_groups[t]["group"] if isinstance(source_groups[t], dict)
              else source_groups[t] for t in tasks]
    return dict(comparisons=comparisons,
                source_cluster_sensitivity=source_cluster_sensitivity(vectors, groups),
                independent_parent_count=3, denominator=denominator, unknown_as_zero=False)


def advancement(summary, *, contracts_complete):
    comparisons = summary["comparisons"]
    complete = all(comparisons[name]["status"] == "COMPLETE"
                   for name in ("C05-C1", "C05-Hold", "C1-Hold"))
    if not complete:
        return dict(status="EVALUATION_INCOMPLETE", advance=False,
                    contracts_complete=contracts_complete, directional_development_filter=True)
    temperature = comparisons["C05-C1"]["seed_summary"]["mean"]
    hold = comparisons["C05-Hold"]["seed_summary"]["mean"]
    passed = contracts_complete and temperature > 0 and hold > 0
    return dict(status=("ELIGIBLE_FOR_SEPARATELY_REGISTERED_FOLLOWUP" if passed
                        else "RETAIN_BASELINE" if contracts_complete else "CONTRACT_INCOMPLETE"),
                advance=passed, delta_temperature=temperature, delta_hold=hold,
                contracts_complete=contracts_complete, directional_development_filter=True,
                significance_or_stability_confirmation=False, automatic_followup_authorized=False)
