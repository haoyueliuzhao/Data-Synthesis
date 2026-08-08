from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from trusted_synthesis.hashing import canonical_hash

ANALYSIS_VERSION = "finance_development_target_design_analysis.v22.1"
ANALYSIS_PREFIX = "finance_development_target_design_analysis:"
SOURCE_REPORT_VERSION = "finance_development_exact_target_report.v22"
SOURCE_REPORT_PREFIX = "finance_development_exact_target_report:"
OBJECTIVE_SPLIT_GRID = (8, 16, 32)
REALIZATION_GRID = (5, 8)
EFFECT_RATIO_GRID = (0.0, 0.005, 0.01, 0.025, 0.05, 0.10, 0.25, 0.50, 1.0, 1.25, 1.50)
Z_95 = 1.96


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object:{path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _verify_source_report(path: Path) -> dict[str, Any]:
    report = _read_json(path)
    payload = dict(report)
    observed_hash = payload.pop("report_hash", None)
    expected_hash = canonical_hash(payload, prefix=SOURCE_REPORT_PREFIX)
    if observed_hash != expected_hash:
        raise ValueError("Development exact-target report identity changed")
    if (
        report.get("report_version") != SOURCE_REPORT_VERSION
        or report.get("run_role") != "development_exact_target_only"
        or report.get("status") != "development_target_variance_measured"
        or report.get("target_observation_count") != 4000
        or report.get("primary_coordinate_count") != 30
        or report.get("validation_objective_access") != "forbidden"
        or report.get("authorization_objective_access") != "forbidden"
        or report.get("gp_c_evaluated") is not False
        or report.get("contribution_approximation_authorized") is not False
    ):
        raise ValueError("Development exact-target report contract differs")
    observation = report.get("observation_artifact", {})
    observation_path = Path(str(observation.get("path", ""))).resolve()
    if not observation_path.is_file() or _sha256(observation_path) != observation.get("sha256"):
        raise ValueError("Development target observations changed")
    return report


def classify_effect_interval(
    *, mean: float, ci_lower: float, ci_upper: float, minimum_practical_effect: float
) -> dict[str, Any]:
    if minimum_practical_effect <= 0 or ci_lower > mean or mean > ci_upper:
        raise ValueError("invalid Development effect interval")
    statistical_direction = (
        "positive" if ci_lower > 0 else "negative" if ci_upper < 0 else "unresolved"
    )
    practically_equivalent = (
        ci_lower >= -minimum_practical_effect and ci_upper <= minimum_practical_effect
    )
    meaningful_direction = (
        "positive"
        if ci_lower > minimum_practical_effect
        else "negative"
        if ci_upper < -minimum_practical_effect
        else "unresolved"
    )
    if meaningful_direction != "unresolved":
        joint_resolution = f"meaningful_{meaningful_direction}"
    elif practically_equivalent and statistical_direction != "unresolved":
        joint_resolution = "sub_mpe_nonzero_and_equivalent"
    elif practically_equivalent:
        joint_resolution = "equivalent_including_zero"
    else:
        joint_resolution = "inconclusive_across_mpe_boundary"
    return {
        "statistically_nonzero": statistical_direction != "unresolved",
        "statistical_direction": statistical_direction,
        "practically_equivalent": practically_equivalent,
        "meaningful_beyond_mpe": meaningful_direction != "unresolved",
        "meaningful_direction": meaningful_direction,
        "joint_resolution": joint_resolution,
    }


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _normal_probability_between(lower: float, upper: float, *, mean: float, sd: float) -> float:
    if lower > upper:
        return 0.0
    if sd == 0:
        return float(lower <= mean <= upper)
    return max(0.0, min(1.0, _normal_cdf((upper - mean) / sd) - _normal_cdf((lower - mean) / sd)))


def _measurement_variance_ratio(
    row: Mapping[str, Any], *, objective_split_count: int, realization_count: int
) -> float:
    mpe = float(row["minimum_practical_effect"])
    if mpe <= 0 or objective_split_count <= 1 or realization_count <= 1:
        raise ValueError("invalid Development measurement design")
    return (
        float(row["objective_variance"]) / objective_split_count
        + float(row["realization_variance"]) / realization_count
        + float(row["interaction_variance"]) / (objective_split_count * realization_count)
    ) / (mpe * mpe)


def measurement_design_power(
    primary_rows: Sequence[Mapping[str, Any]],
    *,
    objective_split_grid: Sequence[int] = OBJECTIVE_SPLIT_GRID,
    realization_grid: Sequence[int] = REALIZATION_GRID,
    effect_ratio_grid: Sequence[float] = EFFECT_RATIO_GRID,
) -> list[dict[str, Any]]:
    if not primary_rows:
        raise ValueError("Development power requires primary coordinates")
    results: list[dict[str, Any]] = []
    for objective_split_count in objective_split_grid:
        for realization_count in realization_grid:
            standard_errors = [
                math.sqrt(
                    _measurement_variance_ratio(
                        row,
                        objective_split_count=objective_split_count,
                        realization_count=realization_count,
                    )
                )
                for row in primary_rows
            ]
            for effect_ratio in effect_ratio_grid:
                if effect_ratio < 0:
                    raise ValueError("Development power effect ratio must be nonnegative")
                nonzero_probabilities = []
                equivalence_probabilities = []
                meaningful_probabilities = []
                for standard_error in standard_errors:
                    if standard_error == 0:
                        nonzero_probabilities.append(float(effect_ratio != 0))
                        equivalence_probabilities.append(float(effect_ratio <= 1.0))
                        meaningful_probabilities.append(float(effect_ratio > 1.0))
                        continue
                    nonzero_probabilities.append(
                        1.0
                        - _normal_probability_between(
                            -Z_95 * standard_error,
                            Z_95 * standard_error,
                            mean=effect_ratio,
                            sd=standard_error,
                        )
                    )
                    equivalence_probabilities.append(
                        _normal_probability_between(
                            -1.0 + Z_95 * standard_error,
                            1.0 - Z_95 * standard_error,
                            mean=effect_ratio,
                            sd=standard_error,
                        )
                    )
                    meaningful_probabilities.append(
                        1.0
                        - _normal_cdf((1.0 + Z_95 * standard_error - effect_ratio) / standard_error)
                    )
                results.append(
                    {
                        "objective_micro_split_count": objective_split_count,
                        "objective_record_count_at_eight_per_split": 8 * objective_split_count,
                        "realization_count_per_state": realization_count,
                        "true_effect_ratio_to_mpe": effect_ratio,
                        "mean_nonzero_detection_probability": statistics.fmean(
                            nonzero_probabilities
                        ),
                        "mean_equivalence_declaration_probability": statistics.fmean(
                            equivalence_probabilities
                        ),
                        "mean_meaningful_beyond_mpe_probability": statistics.fmean(
                            meaningful_probabilities
                        ),
                        "median_normalized_standard_error": statistics.median(standard_errors),
                        "maximum_normalized_standard_error": max(standard_errors),
                    }
                )
    return results


def _quantiles(values: Sequence[float]) -> dict[str, float]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("Development summary requires observations")

    def percentile(probability: float) -> float:
        position = (len(ordered) - 1) * probability
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    return {
        "minimum": ordered[0],
        "p25": percentile(0.25),
        "median": percentile(0.50),
        "p75": percentile(0.75),
        "maximum": ordered[-1],
        "mean": statistics.fmean(ordered),
    }


def build_design_analysis(*, source_report_path: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise ValueError("Development design analysis is immutable and already exists")
    source = _verify_source_report(source_report_path)
    enriched_rows = []
    for row in source["state_summaries"]:
        inference = classify_effect_interval(
            mean=float(row["mean"]),
            ci_lower=float(row["ci_lower"]),
            ci_upper=float(row["ci_upper"]),
            minimum_practical_effect=float(row["minimum_practical_effect"]),
        )
        enriched_rows.append({**row, "dual_axis_inference": inference})
    primary = [row for row in enriched_rows if row["is_primary_coordinate"]]
    if len(primary) != 30:
        raise ValueError("Development primary coordinate support changed")
    primary_counts = Counter(row["dual_axis_inference"]["joint_resolution"] for row in primary)
    all_counts = Counter(row["dual_axis_inference"]["joint_resolution"] for row in enriched_rows)
    practical_primary = sum(
        bool(row["dual_axis_inference"]["practically_equivalent"]) for row in primary
    )
    meaningful_primary = sum(
        bool(row["dual_axis_inference"]["meaningful_beyond_mpe"]) for row in primary
    )
    statistically_nonzero_primary = sum(
        bool(row["dual_axis_inference"]["statistically_nonzero"]) for row in primary
    )
    variance = source["variance_components"]
    nested_total = sum(
        float(variance[key])
        for key in (
            "objective_mean",
            "realization_mean",
            "objective_realization_interaction_mean",
        )
    )
    if nested_total <= 0:
        raise ValueError("Development nested variance is degenerate")
    power_rows = measurement_design_power(primary)
    analysis: dict[str, Any] = {
        "analysis_version": ANALYSIS_VERSION,
        "run_role": "development_post_measurement_design_only",
        "source_target_report": {
            "path": str(source_report_path.resolve()),
            "sha256": _sha256(source_report_path),
            "report_hash": source["report_hash"],
            "preserved_unchanged": True,
        },
        "source_observations": source["observation_artifact"],
        "inference_contract": {
            "confidence_interval": "normal_95_percent_from_frozen_crossed_summary",
            "statistical_nonzero": "ci_excludes_zero",
            "practical_equivalence": "ci_fully_contained_within_plus_or_minus_state_mpe",
            "meaningful_beyond_mpe": "ci_fully_beyond_state_mpe_in_one_direction",
            "axes_are_not_mutually_exclusive": True,
            "source_exclusive_resolution_is_not_used_for_next_stage_design": True,
        },
        "primary_coordinate_summary": {
            "count": len(primary),
            "statistically_nonzero_count": statistically_nonzero_primary,
            "practically_equivalent_count": practical_primary,
            "meaningful_beyond_mpe_count": meaningful_primary,
            "joint_resolution_counts": dict(sorted(primary_counts.items())),
            "absolute_target_to_mpe_ratio": _quantiles(
                [
                    abs(float(row["mean"])) / float(row["minimum_practical_effect"])
                    for row in primary
                ]
            ),
            "ci_half_width_to_mpe_ratio": _quantiles(
                [
                    (float(row["ci_upper"]) - float(row["ci_lower"]))
                    / (2.0 * float(row["minimum_practical_effect"]))
                    for row in primary
                ]
            ),
        },
        "all_state_summary": {
            "count": len(enriched_rows),
            "joint_resolution_counts": dict(sorted(all_counts.items())),
            "meaningful_beyond_mpe_count": sum(
                bool(row["dual_axis_inference"]["meaningful_beyond_mpe"]) for row in enriched_rows
            ),
            "practically_equivalent_count": sum(
                bool(row["dual_axis_inference"]["practically_equivalent"]) for row in enriched_rows
            ),
        },
        "variance_diagnostics": {
            "objective_share_of_nested_measurement_variance": float(variance["objective_mean"])
            / nested_total,
            "realization_share_of_nested_measurement_variance": float(variance["realization_mean"])
            / nested_total,
            "interaction_share_of_nested_measurement_variance": float(
                variance["objective_realization_interaction_mean"]
            )
            / nested_total,
            "numeric_maximum_absolute_delta": variance["numeric_maximum_absolute_delta"],
            "simplex_center_maximum_absolute_error": source[
                "simplex_center_maximum_absolute_error"
            ],
        },
        "measurement_design_power": {
            "scope": "per_coordinate_measurement_resolution_not_cross_task_proxy_validation",
            "rows": power_rows,
        },
        "source_task_count_power_diagnostic": {
            **source["empirical_power_contract"],
            "interpretation": (
                "Detecting a homogeneous one-MPE population mean is not sufficient to freeze "
                "the number of task-specific coordinates used for future GP-C validation."
            ),
            "accepted_as_final_validation_task_count": False,
        },
        "next_stage_design_recommendation": {
            "status": "recommended_not_yet_frozen",
            "fresh_validation_task_count": 60,
            "task_family_count": 6,
            "tasks_per_family": 10,
            "states_per_task": "3_to_5",
            "realizations_per_state": 5,
            "objective_micro_split_count": 16,
            "objective_records_per_micro_split": 8,
            "objective_record_count": 128,
            "reasoning": [
                "retain the preregistered 48-to-60 fresh-task range at its balanced upper bound",
                (
                    "double Objective micro-splits because Objective variation dominates "
                    "measurement variance"
                ),
                (
                    "retain five realizations because realization variation is negligible "
                    "in Development"
                ),
                (
                    "freeze a separate proxy-target agreement power contract before any "
                    "GP-C score is opened"
                ),
            ],
            "final_validation_task_count_frozen": False,
        },
        "development_interpretation": {
            "exact_target_observed": True,
            "all_primary_coordinates_practically_equivalent_at_current_mpe": practical_primary
            == len(primary),
            "any_primary_coordinate_meaningful_beyond_mpe": meaningful_primary > 0,
            "interpretation": (
                "The exact one-step Development surrogate is precisely measured but materially "
                "smaller than the update-derived MPE on every preregistered primary coordinate. "
                "A fresh Validation population is needed to test whether this near-zero practical "
                "effect generalizes; it is not evidence for or against GP-C."
            ),
        },
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "production_contribution": 0.0,
        "status": "development_design_recommendation_ready",
        "claim_boundary": (
            "This post-measurement analysis only corrects Development inference and future study "
            "sizing. It preserves the frozen target report, cannot inspect Validation or "
            "Authorization, cannot evaluate GP-C, cannot authorize Contribution, cannot update "
            "VTDO, and cannot support Student claims."
        ),
    }
    analysis["analysis_hash"] = canonical_hash(analysis, prefix=ANALYSIS_PREFIX)
    _write_json(output_path, analysis)
    return analysis


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit Finance v22 Development exact-target inference and study sizing"
    )
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    result = build_design_analysis(
        source_report_path=args.source_report,
        output_path=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
