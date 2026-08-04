from __future__ import annotations

import argparse
import statistics
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.contribution_validation import (
    _cluster_bootstrap_interval,
    _spearman,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_intervention import (
    _pairwise_concordance,
    _permutation_null,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _read_json,
    _write_json,
)
from trusted_synthesis.hashing import canonical_hash

CONTRIBUTION_HORIZON_ANALYSIS_VERSION = "finance_contribution_horizon_analysis.v1"


def _state_values(
    rows: list[dict[str, Any]],
    *,
    value_field: str,
) -> dict[tuple[str, str], float]:
    values = {(str(row["task_id"]), str(row["state_id"])): float(row[value_field]) for row in rows}
    if len(values) != len(rows):
        raise ValueError(f"duplicate task/state rows in {value_field}")
    return values


def _task_vectors(
    left: dict[tuple[str, str], float],
    right: dict[tuple[str, str], float],
) -> list[tuple[str, list[float], list[float]]]:
    if set(left) != set(right):
        raise ValueError("Contribution estimands do not cover the same task/state support")
    states_by_task: defaultdict[str, list[str]] = defaultdict(list)
    for task_id, state_id in left:
        states_by_task[task_id].append(state_id)
    return [
        (
            task_id,
            [left[(task_id, state_id)] for state_id in sorted(state_ids)],
            [right[(task_id, state_id)] for state_id in sorted(state_ids)],
        )
        for task_id, state_ids in sorted(states_by_task.items())
    ]


def _pair_report(
    left_id: str,
    right_id: str,
    left: dict[tuple[str, str], float],
    right: dict[tuple[str, str], float],
    *,
    bootstrap_samples: int,
    permutation_iterations: int,
    seed: int,
) -> dict[str, Any]:
    vectors = _task_vectors(left, right)
    task_rows = []
    spearman_values: list[float] = []
    concordance_values: list[float] = []
    winner_matches = 0
    for task_id, left_values, right_values in vectors:
        left_winner = max(range(len(left_values)), key=left_values.__getitem__)
        right_winner = max(range(len(right_values)), key=right_values.__getitem__)
        winner_matches += int(left_winner == right_winner)
        spearman = _spearman(left_values, right_values)
        concordance = _pairwise_concordance(left_values, right_values)
        spearman_values.append(spearman)
        concordance_values.append(concordance)
        task_rows.append(
            {
                "task_id": task_id,
                "spearman": spearman,
                "pairwise_concordance": concordance,
                "winner_agreement": left_winner == right_winner,
            }
        )
    observed_spearman = statistics.fmean(spearman_values)
    observed_concordance = statistics.fmean(concordance_values)
    null_spearman, null_concordance = _permutation_null(
        [(left_values, right_values) for _, left_values, right_values in vectors],
        iterations=permutation_iterations,
        seed=seed,
    )
    return {
        "comparison_id": f"{left_id}__vs__{right_id}",
        "left_estimand_id": left_id,
        "right_estimand_id": right_id,
        "task_count": len(vectors),
        "macro_task_spearman": observed_spearman,
        "macro_task_spearman_ci95": _cluster_bootstrap_interval(
            spearman_values,
            samples=bootstrap_samples,
            seed=seed + 1,
        ),
        "macro_pairwise_concordance": observed_concordance,
        "macro_pairwise_concordance_ci95": _cluster_bootstrap_interval(
            concordance_values,
            samples=bootstrap_samples,
            seed=seed + 2,
        ),
        "winner_agreement_rate": winner_matches / len(vectors),
        "rank_flip_rate": 1.0 - observed_concordance,
        "permutation_test": {
            "iterations": permutation_iterations,
            "seed": seed,
            "macro_spearman_p_value": (
                1 + sum(value >= observed_spearman for value in null_spearman)
            )
            / (len(null_spearman) + 1),
            "macro_pairwise_concordance_p_value": (
                1 + sum(value >= observed_concordance for value in null_concordance)
            )
            / (len(null_concordance) + 1),
        },
        "task_rows": task_rows,
    }


def analyze_contribution_horizons(
    *,
    population_plan: dict[str, Any],
    population_report: dict[str, Any],
    intervention_runs: list[tuple[dict[str, Any], dict[str, Any]]],
    bootstrap_samples: int = 2000,
    permutation_iterations: int = 10000,
) -> dict[str, Any]:
    if not intervention_runs:
        raise ValueError("at least one Intervention horizon is required")
    probe_step_count = int(population_plan["probe_step_count"])
    estimands: dict[str, dict[tuple[str, str], float]] = {
        f"probe_estimation_h{probe_step_count}_internal_validation": _state_values(
            population_report["state_rows"],
            value_field="estimation_mean_gain",
        ),
        f"probe_validation_h{probe_step_count}_internal_validation": _state_values(
            population_report["state_rows"],
            value_field="validation_mean_gain",
        ),
    }
    intervention_metadata = []
    seen_horizons: set[int] = set()
    for plan, report in intervention_runs:
        horizon = int(plan["intervention_step_count"])
        if horizon in seen_horizons:
            raise ValueError(f"duplicate Intervention horizon:{horizon}")
        seen_horizons.add(horizon)
        if report["source_population_report_hash"] != population_report["report_hash"]:
            raise ValueError("Intervention run uses another Contribution population")
        if report["plan_hash"] != plan["plan_hash"]:
            raise ValueError("Intervention report does not replay its plan")
        estimand_id = f"intervention_h{horizon}_final_test"
        estimands[estimand_id] = _state_values(
            report["state_rows"],
            value_field="intervention_mean_gain",
        )
        intervention_metadata.append(
            {
                "estimand_id": estimand_id,
                "horizon": horizon,
                "plan_hash": plan["plan_hash"],
                "report_hash": report["report_hash"],
                "intervention_estimand_id": plan.get("intervention_estimand_id"),
                "final_test_set_id": plan["final_test_set_id"],
                "learning_rate": plan["learning_rate"],
                "strategy_mean_gain": report["strategy_intervention_mean_gain"],
            }
        )
    support = set(next(iter(estimands.values())))
    if any(set(values) != support for values in estimands.values()):
        raise ValueError("Contribution horizon matrix has inconsistent support")

    comparisons = []
    for index, (left_id, right_id) in enumerate(combinations(sorted(estimands), 2)):
        comparisons.append(
            _pair_report(
                left_id,
                right_id,
                estimands[left_id],
                estimands[right_id],
                bootstrap_samples=bootstrap_samples,
                permutation_iterations=permutation_iterations,
                seed=20260850 + index * 10,
            )
        )
    comparison_by_id = {item["comparison_id"]: item for item in comparisons}
    probe_id = f"probe_estimation_h{probe_step_count}_internal_validation"
    ordered_interventions = sorted(intervention_metadata, key=lambda item: item["horizon"])
    shortest_id = str(ordered_interventions[0]["estimand_id"])
    longest_id = str(ordered_interventions[-1]["estimand_id"])

    def comparison(left_id: str, right_id: str) -> dict[str, Any]:
        direct = f"{left_id}__vs__{right_id}"
        reverse = f"{right_id}__vs__{left_id}"
        return comparison_by_id.get(direct) or comparison_by_id[reverse]

    shortest = comparison(probe_id, shortest_id)
    longest = comparison(probe_id, longest_id)

    def supported(item: dict[str, Any]) -> bool:
        return bool(
            item["macro_task_spearman_ci95"][0] > 0
            and item["permutation_test"]["macro_spearman_p_value"] < 0.05
        )

    probe_horizon_curve = []
    for metadata in ordered_interventions:
        item = comparison(probe_id, str(metadata["estimand_id"]))
        probe_horizon_curve.append(
            {
                "horizon": metadata["horizon"],
                "estimand_id": metadata["estimand_id"],
                "macro_task_spearman": item["macro_task_spearman"],
                "macro_task_spearman_ci95": item["macro_task_spearman_ci95"],
                "macro_pairwise_concordance": item["macro_pairwise_concordance"],
                "winner_agreement_rate": item["winner_agreement_rate"],
                "rank_flip_rate": item["rank_flip_rate"],
                "permutation_spearman_p_value": item["permutation_test"]["macro_spearman_p_value"],
                "supported": supported(item),
            }
        )
    adjacent_horizon_stability = []
    for left_metadata, right_metadata in zip(
        ordered_interventions,
        ordered_interventions[1:],
        strict=False,
    ):
        item = comparison(
            str(left_metadata["estimand_id"]),
            str(right_metadata["estimand_id"]),
        )
        adjacent_horizon_stability.append(
            {
                "left_horizon": left_metadata["horizon"],
                "right_horizon": right_metadata["horizon"],
                "macro_task_spearman": item["macro_task_spearman"],
                "macro_pairwise_concordance": item["macro_pairwise_concordance"],
                "winner_agreement_rate": item["winner_agreement_rate"],
                "rank_flip_rate": item["rank_flip_rate"],
            }
        )
    shortest_supported = supported(shortest)
    longest_supported = supported(longest)
    supported_horizons = [int(item["horizon"]) for item in probe_horizon_curve if item["supported"]]
    unsupported_horizons = [
        int(item["horizon"]) for item in probe_horizon_curve if not item["supported"]
    ]
    if shortest_supported and not longest_supported:
        diagnosis = "local_proxy_supported_but_long_horizon_not_supported"
    elif shortest_supported and longest_supported:
        diagnosis = "proxy_supported_across_observed_horizons"
    else:
        diagnosis = "proxy_not_empirically_supported"
    task_count = len({task_id for task_id, _ in support})
    report = {
        "analysis_version": CONTRIBUTION_HORIZON_ANALYSIS_VERSION,
        "population_plan_hash": population_plan["plan_hash"],
        "population_report_hash": population_report["report_hash"],
        "probe_step_count": probe_step_count,
        "task_count": task_count,
        "state_count": len(support),
        "intervention_runs": ordered_interventions,
        "comparisons": comparisons,
        "probe_horizon_curve": probe_horizon_curve,
        "adjacent_horizon_stability": adjacent_horizon_stability,
        "maximum_observed_supported_horizon": (
            max(supported_horizons) if supported_horizons else None
        ),
        "first_observed_unsupported_horizon": (
            min(unsupported_horizons) if unsupported_horizons else None
        ),
        "diagnosis": diagnosis,
        "local_proxy_supported": shortest_supported,
        "long_horizon_proxy_supported": longest_supported,
        "local_probe_validation_passed": (
            shortest_supported and longest_supported and task_count >= 30
        ),
        "production_usage_allowed": False,
        "claim_boundary": (
            "Contribution is a horizon- and evaluation-distribution-specific estimand. "
            "Evidence at one adaptation horizon cannot be reused for another horizon."
        ),
        "recommended_action": (
            "Retain this result as Local Probe validation evidence. Production updates "
            "require a separately frozen and independently authorized Gradient Projection."
        ),
    }
    report["analysis_hash"] = canonical_hash(
        report,
        prefix="finance_contribution_horizon_analysis:",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare VTDO Contribution estimates across adaptation horizons"
    )
    parser.add_argument("--population-dir", required=True)
    parser.add_argument("--intervention-dirs", required=True, nargs="+")
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--permutation-iterations", type=int, default=10000)
    args = parser.parse_args()
    population_dir = Path(args.population_dir).resolve()
    intervention_runs = []
    for raw_path in args.intervention_dirs:
        path = Path(raw_path).resolve()
        intervention_runs.append((_read_json(path / "plan.json"), _read_json(path / "report.json")))
    report = analyze_contribution_horizons(
        population_plan=_read_json(population_dir / "plan.json"),
        population_report=_read_json(population_dir / "report.json"),
        intervention_runs=intervention_runs,
        bootstrap_samples=args.bootstrap_samples,
        permutation_iterations=args.permutation_iterations,
    )
    _write_json(Path(args.output_path), report)


if __name__ == "__main__":
    main()
