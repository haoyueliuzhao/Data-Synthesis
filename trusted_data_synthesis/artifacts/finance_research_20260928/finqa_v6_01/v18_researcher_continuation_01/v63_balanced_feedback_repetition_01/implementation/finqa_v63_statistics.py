"""V63 balanced feedback-batch replication, reusing the V54 native mathematics.

Only the new b=1 C05/C1 pair can enter the research-value decision.  The old
Hold result is an explicitly bound, read-only secondary comparator.  Three
parents remain three repeats; old/new feedback batches are never pooled or
selected for the primary decision.
"""

from __future__ import annotations

import finqa_v63_binding as binding

binding.install_scientific_paths()

import finqa_v54_statistics as original

SEEDS = original.SEEDS
ARMS = ("C1", "C05")
FEEDBACK_BATCH = 1
COMPARISONS = original.COMPARISONS
BOOTSTRAP_REPLICATES = original.BOOTSTRAP_REPLICATES
BOOTSTRAP_SEED = original.BOOTSTRAP_SEED
T95_DF2 = original.T95_DF2
PRIMARY_DENOMINATOR = 883
MINIMUM_TEMPERATURE_NET_CORRECT = 27
MINIMUM_HOLD_NET_CORRECT = 1

require = original.require
native_state = original.native_state
native_metrics = original.native_metrics
paired_transitions = original.paired_transitions
seed_effect_summary = original.seed_effect_summary
source_cluster_sensitivity = original.source_cluster_sensitivity


def coordinate(seed, arm):
    require(type(seed) is int and seed in SEEDS and arm in ARMS,
            "unregistered V63 new-batch branch")
    return f"seed{seed}/{arm}"


def statistics_contract():
    value = original.statistics_contract()
    value.update(
        schema="v63_balanced_feedback_replication_statistics.v1",
        primary="step894 dev883 greedy native execution accuracy: C05_b1-C1_b1",
        key_secondary="C05_b1-Hold_reused",
        other_comparison="C1_b1-Hold_reused",
        arms=list(ARMS), feedback_batch=FEEDBACK_BATCH,
        reused_comparator="old sealed Hold, no new generation or scoring",
        independent_parent_count=3, logical_endpoint_conditions=15,
        old_endpoint_conditions_reused=9, new_endpoint_conditions=6,
        primary_uses_only_new_batch=True, old_new_batch_pooling=False,
        best_of_old_new_selection=False,
        advancement=(
            "all scientific contracts complete AND new-batch C05-C1 net correct "
            "sum >= 27 of 2649 AND new-batch C05-old Hold net correct sum >= 1 of 2649"
        ),
        minimum_research_value_pp=1.0,
        minimum_temperature_net_correct=MINIMUM_TEMPERATURE_NET_CORRECT,
        minimum_hold_net_correct=MINIMUM_HOLD_NET_CORRECT,
        advancement_is_directional_development_filter=False,
        advancement_is_minimum_research_value_filter=True,
        significance_or_stability_confirmation=False,
        statistical_power_guarantee=False,
        all_seeds_positive_required=False, all_auxiliary_panels_positive_required=False,
        development_and_calibration_are_unseen_confirmation_sets=False,
        automatic_followup_authorized=False,
        fifteen_conditions_are_not_fifteen_independent_training_repeats=True,
    )
    return value


def _validated_old_hold(report, seed, denominator, tasks):
    """Require the provenance wrapper created from a bound old model report."""
    require(report.get("seed") == seed and report.get("arm") == "Hold"
            and report.get("feedback_batch") is None
            and report.get("reused_old_hold") is True,
            "Hold must be an explicitly reused old result, not a new or mixed batch")
    reference = report.get("old_model_report", {})
    require(isinstance(reference, dict) and isinstance(reference.get("path"), str)
            and reference["path"] and isinstance(reference.get("sha256"), str)
            and len(reference["sha256"]) == 64 and report.get("old_summary_id")
            and report.get("old_registration_id"),
            "old Hold requires bound model, summary and registration provenance")
    require(report["denominator"] == denominator
            and [row["task_key"] for row in report["results"]] == tasks,
            "reused Hold cohort or draw order changed")
    return report


def paired_summary(reports, tasks, source_groups, *, old_hold_reports, denominator=883):
    """Analyze six new reports against three already-scored old Hold reports.

    Pairing, UNKNOWN semantics, I/W/R decomposition, seed statistics and shared
    source-cluster bootstrap are delegated unchanged to V54.  Only the identity
    guards and research-decision policy differ.
    """
    require(set(reports) == {coordinate(seed, arm) for seed in SEEDS for arm in ARMS},
            "all six new-batch branches are required; no old/new selection or pooling")
    require(set(old_hold_reports) == {original.coordinate(seed, "Hold") for seed in SEEDS},
            "all three old Hold comparators must be reused")
    assembled = {}
    conditions = {}
    for seed in SEEDS:
        for arm in ARMS:
            key = coordinate(seed, arm)
            report = reports[key]
            require(report.get("seed") == seed and report.get("arm") == arm
                    and type(report.get("feedback_batch")) is int
                    and report["feedback_batch"] == FEEDBACK_BATCH
                    and report.get("reused_old_hold", False) is False,
                    "primary comparison requires only b1: mixed feedback batches rejected")
            assembled[key] = report
            conditions[key] = dict(feedback_batch=FEEDBACK_BATCH, source="new_sealed_result")
        key = original.coordinate(seed, "Hold")
        hold = _validated_old_hold(old_hold_reports[key], seed, denominator, tasks)
        assembled[key] = hold
        conditions[key] = dict(feedback_batch=None, source="read_only_old_hold",
            old_model_report=hold["old_model_report"], old_summary_id=hold["old_summary_id"],
            old_registration_id=hold["old_registration_id"])
    value = original.paired_summary(assembled, tasks, source_groups, denominator=denominator)
    value.update(feedback_batch=FEEDBACK_BATCH, primary_uses_only_new_batch=True,
                 old_new_batch_pooling=False, best_of_old_new_selection=False,
                 conditions=conditions, statistics_contract=statistics_contract())
    return value


def batch_replication_diagnostics(new_reports, old_reports, tasks, *, denominator=883):
    """Describe within-temperature b1-b0 changes, without pooling for promotion.

    This uses saved native result rows only.  It does not rescore old output,
    resample old uncertainty, or increase the number of independent parents.
    """
    require(len(tasks) == len(set(tasks)) == denominator, "complete paired batch cohort required")
    require(set(new_reports) == {coordinate(s, a) for s in SEEDS for a in ARMS}
            and set(old_reports) == {original.coordinate(s, a) for s in SEEDS for a in original.ARMS},
            "six new and nine old endpoint reports required for batch diagnostics")
    comparisons = {}
    for arm in ARMS:
        per_seed = {}
        for seed in SEEDS:
            key = coordinate(seed, arm)
            new, old = new_reports[key], old_reports[key]
            require(type(new.get("feedback_batch")) is int and new["feedback_batch"] == FEEDBACK_BATCH
                    and type(old.get("feedback_batch")) is int and old["feedback_batch"] == 0
                    and old.get("old_model_report") and old.get("old_summary_id")
                    and old.get("old_registration_id")
                    and new["seed"] == old["seed"] == seed and new["arm"] == old["arm"] == arm
                    and new["denominator"] == old["denominator"] == denominator
                    and [row["task_key"] for row in new["results"]] == tasks
                    and [row["task_key"] for row in old["results"]] == tasks,
                    "same-temperature comparison requires bound b0 and b1, not selected/mixed batches")
            per_seed[str(seed)] = paired_transitions(new["results"], old["results"], denominator)
        complete = all(row["status"] == "COMPLETE" for row in per_seed.values())
        comparisons[f"{arm}_b1-{arm}_b0"] = dict(
            status="COMPLETE" if complete else "INCOMPLETE", per_seed=per_seed,
            seed_summary=(seed_effect_summary(
                [row["difference"] for row in per_seed.values()],
                count_differences=[row["numerator"] for row in per_seed.values()],
                denominator=denominator) if complete else None))
    return dict(
        comparisons=comparisons, denominator=denominator, independent_parent_count=3,
        feedback_batches=2, explanatory_only=True, used_in_advancement=False,
        old_results_rescored=False, old_bootstrap_rerun=False,
        two_feedback_batches_do_not_estimate_population_variance_precisely=True,
        development_and_calibration_are_unseen_confirmation_sets=False)


def _integer_comparison(comparison, name):
    require(comparison.get("denominator") == PRIMARY_DENOMINATOR
            and set(comparison.get("per_seed", {})) == {str(seed) for seed in SEEDS},
            "research-value decision requires all three parents and dev883 denominator")
    counts = []
    for seed in SEEDS:
        row = comparison["per_seed"][str(seed)]
        require(row.get("status") == "COMPLETE"
                and row.get("denominator") == PRIMARY_DENOMINATOR
                and row.get("unknown_pair_count") == 0
                and type(row.get("numerator")) is int
                and -PRIMARY_DENOMINATOR <= row["numerator"] <= PRIMARY_DENOMINATOR
                and row.get("difference") == row["numerator"] / PRIMARY_DENOMINATOR,
                "complete exact integer paired counts required for " + name)
        counts.append(row["numerator"])
    total = sum(counts)
    require(comparison["seed_summary"]["mean"] == total / (3 * PRIMARY_DENOMINATOR),
            "paired mean differs from exact counts for " + name)
    return total


def advancement(summary, *, contracts_complete):
    """Use integers for the prospective >=1 pp gate; 26 fails and 27 passes."""
    require(type(contracts_complete) is bool, "scientific contract completion must be explicit")
    require(type(summary.get("feedback_batch")) is int
            and summary["feedback_batch"] == FEEDBACK_BATCH
            and summary.get("primary_uses_only_new_batch") is True
            and summary.get("old_new_batch_pooling") is False
            and summary.get("best_of_old_new_selection") is False,
            "research-value decision rejects old, pooled or selected feedback batches")
    require(summary.get("denominator") == PRIMARY_DENOMINATOR
            and summary.get("independent_parent_count") == 3,
            "only the registered dev883 main panel can nominate followup")
    conditions = summary.get("conditions", {})
    require(set(conditions) == {original.coordinate(s, a) for s in SEEDS for a in original.ARMS},
            "complete primary condition identities required")
    for seed in SEEDS:
        for arm in ARMS:
            condition = conditions[coordinate(seed, arm)]
            require(type(condition.get("feedback_batch")) is int
                    and condition == dict(feedback_batch=FEEDBACK_BATCH, source="new_sealed_result"),
                    "promotion cannot mix or select old/new feedback realizations")
        hold = conditions[original.coordinate(seed, "Hold")]
        require(hold.get("feedback_batch") is None and hold.get("source") == "read_only_old_hold"
                and hold.get("old_model_report") and hold.get("old_summary_id")
                and hold.get("old_registration_id"), "promotion needs original bound Hold")
    comparisons = summary["comparisons"]
    require(set(comparisons) == {f"{a}-{b}" for a, b in COMPARISONS},
            "registered paired comparisons changed")
    common = dict(
        contracts_complete=contracts_complete, feedback_batch=FEEDBACK_BATCH,
        primary_uses_only_new_batch=True, old_new_batch_pooling=False,
        minimum_research_value_filter=True, minimum_research_value_pp=1.0,
        minimum_temperature_net_correct=MINIMUM_TEMPERATURE_NET_CORRECT,
        minimum_hold_net_correct=MINIMUM_HOLD_NET_CORRECT,
        total_paired_denominator=3 * PRIMARY_DENOMINATOR,
        significance_or_stability_confirmation=False, statistical_power_guarantee=False,
        all_seeds_positive_required=False, all_auxiliary_panels_positive_required=False,
        automatic_followup_authorized=False,
    )
    if not all(row.get("status") == "COMPLETE" for row in comparisons.values()):
        return dict(common, status="EVALUATION_INCOMPLETE", advance=False)
    totals = {name: _integer_comparison(value, name) for name, value in comparisons.items()}
    require(totals["C05-Hold"] == totals["C05-C1"] + totals["C1-Hold"],
            "paired exact count contrasts do not add up")
    passed = (contracts_complete and totals["C05-C1"] >= MINIMUM_TEMPERATURE_NET_CORRECT
              and totals["C05-Hold"] >= MINIMUM_HOLD_NET_CORRECT)
    return dict(common, status=("ELIGIBLE_FOR_SEPARATELY_REGISTERED_BOUNDED_FOLLOWUP" if passed
                else "RETAIN_T1_BASELINE" if contracts_complete else "CONTRACT_INCOMPLETE"),
                advance=passed, temperature_net_correct=totals["C05-C1"],
                hold_net_correct=totals["C05-Hold"], c1_hold_net_correct=totals["C1-Hold"],
                delta_temperature=totals["C05-C1"] / (3 * PRIMARY_DENOMINATOR),
                delta_hold=totals["C05-Hold"] / (3 * PRIMARY_DENOMINATOR))
