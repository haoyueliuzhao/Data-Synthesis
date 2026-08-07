from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from trusted_synthesis.hashing import canonical_hash

TARGET_OBSERVABILITY_PREREGISTRATION_VERSION = "finance_target_observability_preregistration.v21"
PREREGISTRATION_HASH_PREFIX = "finance_target_observability_preregistration:"
SOURCE_REPORT_HASH_PREFIX = "finance_target_identifiability_report:"
OBJECTIVE_ROLES = ("estimation", "validation")
DIRECT_COORDINATE_COUNT = 7
OBJECTIVE_RECORDS_PER_ROLE = 128
OBJECTIVE_MICRO_SPLIT_COUNT = 32
OBJECTIVE_RECORDS_PER_MICRO_SPLIT = 4
MINIMUM_PRACTICAL_EFFECT = 0.005
ALPHA = 0.05
TARGET_POWER = 0.80
CI_CRITICAL_DF31_95 = 2.039513446
CI_CRITICAL_DF3_95 = 3.182446305
Z_CRITICAL_975 = 1.959963985
Z_POWER_80 = 0.841621234
STEP_RATIO_LADDER = (0.01, 0.005)
PRIMARY_STEP_RATIO = 0.005
POWER_EFFECT_GRID = (0.001, 0.0025, 0.005, 0.01)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"target-observability artifact is not an object:{path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _replay_hash(value: Mapping[str, Any], *, field: str, prefix: str) -> str:
    payload = dict(value)
    observed = payload.pop(field, None)
    expected = canonical_hash(payload, prefix=prefix)
    if observed != expected:
        raise ValueError(f"target-observability identity replay failed:{field}")
    return str(observed)


def effect_interval(
    *,
    mean: float,
    standard_deviation: float,
    sample_count: int,
    critical_value: float,
) -> tuple[float, float]:
    if sample_count < 2:
        raise ValueError("effect interval requires at least two independent micro-splits")
    if standard_deviation < 0 or not all(
        math.isfinite(value) for value in (mean, standard_deviation, critical_value)
    ):
        raise ValueError("effect interval inputs are invalid")
    half_width = critical_value * standard_deviation / math.sqrt(sample_count)
    return mean - half_width, mean + half_width


def classify_effect(
    *,
    mean: float,
    standard_deviation: float,
    sample_count: int,
    minimum_practical_effect: float = MINIMUM_PRACTICAL_EFFECT,
    critical_value: float = CI_CRITICAL_DF31_95,
) -> dict[str, Any]:
    if minimum_practical_effect <= 0:
        raise ValueError("minimum practical effect must be positive")
    lower, upper = effect_interval(
        mean=mean,
        standard_deviation=standard_deviation,
        sample_count=sample_count,
        critical_value=critical_value,
    )
    statistically_nonzero = lower > 0 or upper < 0
    practically_equivalent = (
        lower >= -minimum_practical_effect and upper <= minimum_practical_effect
    )
    meaningful_positive = statistically_nonzero and mean >= minimum_practical_effect
    meaningful_negative = statistically_nonzero and mean <= -minimum_practical_effect
    if meaningful_positive:
        resolution = "meaningful_positive"
    elif meaningful_negative:
        resolution = "meaningful_negative"
    elif practically_equivalent:
        resolution = "practically_equivalent"
    else:
        resolution = "inconclusive"
    return {
        "mean": mean,
        "standard_deviation": standard_deviation,
        "sample_count": sample_count,
        "confidence_interval_95": (lower, upper),
        "statistically_nonzero": statistically_nonzero,
        "practically_equivalent": practically_equivalent,
        "resolution": resolution,
        "resolved": resolution != "inconclusive",
    }


def required_micro_split_count(
    *,
    standard_deviation: float,
    effect_size: float,
    alpha: float = ALPHA,
    power: float = TARGET_POWER,
) -> int:
    if standard_deviation < 0 or effect_size <= 0:
        raise ValueError("power inputs are invalid")
    if not math.isclose(alpha, ALPHA) or not math.isclose(power, TARGET_POWER):
        raise ValueError("v21 power constants are frozen at alpha=.05 and power=.80")
    if standard_deviation == 0:
        return 2
    value = ((Z_CRITICAL_975 + Z_POWER_80) * standard_deviation / effect_size) ** 2
    return max(2, math.ceil(value))


def _verify_source_report(
    report: Mapping[str, Any],
    *,
    expected_role: Literal["estimation", "validation"],
) -> dict[str, Any]:
    frozen = dict(report)
    _replay_hash(frozen, field="report_hash", prefix=SOURCE_REPORT_HASH_PREFIX)
    if frozen.get("experiment_version") != "finance_target_identifiability_study.v20":
        raise ValueError("v21 power source is not the frozen v20 study")
    if frozen.get("objective_role") != expected_role:
        raise ValueError("v21 power source has another Objective role")
    if frozen.get("authorization_objective_access") != "forbidden":
        raise ValueError("v21 power source opened Authorization")
    if frozen.get("gp_c_evaluated") is not False:
        raise ValueError("v21 power source evaluated GP-C")
    rows = frozen.get("direct_coordinate_rows")
    if not isinstance(rows, list) or len(rows) != DIRECT_COORDINATE_COUNT:
        raise ValueError("v21 power source lacks seven Direct Coordinates")
    coordinate_ids = [
        str(row["coordinate_ids"][0])
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("coordinate_ids"), list)
        and len(row["coordinate_ids"]) == 1
    ]
    if len(coordinate_ids) != DIRECT_COORDINATE_COUNT or len(set(coordinate_ids)) != len(
        coordinate_ids
    ):
        raise ValueError("v21 power source Direct Coordinate identities are invalid")
    return frozen


def build_preregistration(
    *,
    estimation_report_path: Path,
    validation_report_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    if output_path.exists():
        raise ValueError("v21 target-observability preregistration is immutable")
    source_reports = {
        "estimation": _verify_source_report(
            _read_json(estimation_report_path),
            expected_role="estimation",
        ),
        "validation": _verify_source_report(
            _read_json(validation_report_path),
            expected_role="validation",
        ),
    }
    coordinate_sets = {
        role: {str(row["coordinate_ids"][0]) for row in report["direct_coordinate_rows"]}
        for role, report in source_reports.items()
    }
    if len({frozenset(values) for values in coordinate_sets.values()}) != 1:
        raise ValueError("v20 Direct Coordinates differ across Objective roles")

    variance_rows: dict[str, list[dict[str, Any]]] = {}
    current_resolution_counts: dict[str, dict[str, int]] = {}
    power_analysis: dict[str, dict[str, dict[str, int]]] = {}
    for role, report in source_reports.items():
        rows = []
        resolution_counts: dict[str, int] = {}
        deviations = []
        for source_row in report["direct_coordinate_rows"]:
            deviation = float(source_row["linear_slope_standard_deviation"])
            mean = float(source_row["mean_linear_slope"])
            if deviation < 0 or not math.isfinite(deviation):
                raise ValueError("v20 Direct Coordinate variance is invalid")
            resolution = classify_effect(
                mean=mean,
                standard_deviation=deviation,
                sample_count=4,
                critical_value=CI_CRITICAL_DF3_95,
            )
            key = str(resolution["resolution"])
            resolution_counts[key] = resolution_counts.get(key, 0) + 1
            deviations.append(deviation)
            rows.append(
                {
                    "coordinate_id": str(source_row["coordinate_ids"][0]),
                    "mean_linear_slope": mean,
                    "linear_slope_standard_deviation": deviation,
                    "development_resolution_at_mpe": resolution,
                }
            )
        variance_rows[role] = rows
        current_resolution_counts[role] = dict(sorted(resolution_counts.items()))
        power_analysis[role] = {
            str(effect): {
                "median_variance_required_micro_splits": required_micro_split_count(
                    standard_deviation=statistics.median(deviations),
                    effect_size=effect,
                ),
                "worst_variance_required_micro_splits": required_micro_split_count(
                    standard_deviation=max(deviations),
                    effect_size=effect,
                ),
            }
            for effect in POWER_EFFECT_GRID
        }

    preregistration: dict[str, Any] = {
        "schema_version": TARGET_OBSERVABILITY_PREREGISTRATION_VERSION,
        "source_v20_reports": {
            "estimation": {
                "path": str(estimation_report_path.resolve()),
                "sha256": _sha256(estimation_report_path),
                "report_hash": source_reports["estimation"]["report_hash"],
            },
            "validation": {
                "path": str(validation_report_path.resolve()),
                "sha256": _sha256(validation_report_path),
                "report_hash": source_reports["validation"]["report_hash"],
            },
        },
        "development_variance_rows": variance_rows,
        "development_resolution_counts": current_resolution_counts,
        "power_analysis": power_analysis,
        "alpha": ALPHA,
        "target_power": TARGET_POWER,
        "minimum_practical_effect": MINIMUM_PRACTICAL_EFFECT,
        "minimum_practical_effect_semantics": (
            "development_calibrated_raw_objective_slope_bound;"
            "not_a_downstream_business_or_training_effect_threshold"
        ),
        "objective_roles": list(OBJECTIVE_ROLES),
        "objective_records_per_role": OBJECTIVE_RECORDS_PER_ROLE,
        "objective_micro_split_count": OBJECTIVE_MICRO_SPLIT_COUNT,
        "objective_records_per_micro_split": OBJECTIVE_RECORDS_PER_MICRO_SPLIT,
        "direct_coordinate_count": DIRECT_COORDINATE_COUNT,
        "design_policy": "direct_coordinates_only",
        "step_ratio_ladder": list(STEP_RATIO_LADDER),
        "primary_step_ratio": PRIMARY_STEP_RATIO,
        "radius_agreement_policy": {
            "maximum_absolute_slope_difference": MINIMUM_PRACTICAL_EFFECT,
            "require_resolution_agreement": True,
        },
        "effect_resolution_policy": {
            "meaningful": "ci_excludes_zero_and_absolute_mean_at_least_mpe",
            "equivalent": "ci_fully_contained_within_plus_or_minus_mpe",
            "inconclusive": "neither_meaningful_nor_equivalent",
            "required_role_resolved_rate": 1.0,
            "required_cross_role_resolution_agreement": 1.0,
        },
        "fresh_population_required": True,
        "allowed_objective_access": ["estimation", "validation"],
        "authorization_objective_access": "forbidden",
        "gp_c_execution_allowed": False,
        "exact_hypergradient_role": (
            "implementation_oracle_only_not_an_independent_contribution_target"
        ),
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
        "success_transition": "freeze_independent_gp_c_comparison_protocol",
        "failure_transition": "retain_contribution_zero_and_report_target_unobservability",
        "claim_boundary": (
            "This preregistration tests whether a fresh large-support Direct Coordinate target "
            "can resolve meaningful nonzero or practically equivalent effects. It cannot "
            "evaluate GP-C, open Authorization, authorize Contribution, or update VTDO."
        ),
    }
    preregistration["preregistration_hash"] = canonical_hash(
        preregistration,
        prefix=PREREGISTRATION_HASH_PREFIX,
    )
    verify_preregistration(preregistration)
    _write_json(output_path, preregistration)
    return preregistration


def verify_preregistration(value: Mapping[str, Any]) -> dict[str, Any]:
    frozen = dict(value)
    _replay_hash(
        frozen,
        field="preregistration_hash",
        prefix=PREREGISTRATION_HASH_PREFIX,
    )
    expected = {
        "schema_version": TARGET_OBSERVABILITY_PREREGISTRATION_VERSION,
        "alpha": ALPHA,
        "target_power": TARGET_POWER,
        "minimum_practical_effect": MINIMUM_PRACTICAL_EFFECT,
        "objective_roles": list(OBJECTIVE_ROLES),
        "objective_records_per_role": OBJECTIVE_RECORDS_PER_ROLE,
        "objective_micro_split_count": OBJECTIVE_MICRO_SPLIT_COUNT,
        "objective_records_per_micro_split": OBJECTIVE_RECORDS_PER_MICRO_SPLIT,
        "direct_coordinate_count": DIRECT_COORDINATE_COUNT,
        "design_policy": "direct_coordinates_only",
        "step_ratio_ladder": list(STEP_RATIO_LADDER),
        "primary_step_ratio": PRIMARY_STEP_RATIO,
        "authorization_objective_access": "forbidden",
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
    }
    for field, expected_value in expected.items():
        if frozen.get(field) != expected_value:
            raise ValueError(f"v21 preregistration contract differs:{field}")
    if frozen.get("allowed_objective_access") != ["estimation", "validation"]:
        raise ValueError("v21 preregistration Objective access differs")
    return frozen


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze the v21 target-observability power and equivalence contract"
    )
    parser.add_argument("--estimation-report", required=True)
    parser.add_argument("--validation-report", required=True)
    parser.add_argument("--output-path", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    value = build_preregistration(
        estimation_report_path=Path(args.estimation_report).resolve(),
        validation_report_path=Path(args.validation_report).resolve(),
        output_path=Path(args.output_path).resolve(),
    )
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
