from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from trusted_synthesis.core.vtdo import (
    CONTRIBUTION_APPROXIMATION_AUTHORIZATION_VERSION,
    ConditionalTrajectoryDistribution,
    ContributionApproximationAuthorization,
    ContributionDistributionGateThresholds,
    make_contribution_approximation_authorization,
    make_contribution_calibration_contract,
    make_contribution_distribution_validation_evidence,
    make_contribution_optimizer_update_contract,
    make_contribution_rank_validation_evidence,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    TOKEN_REGION_DECOMPOSITION_VERSION,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _read_json,
    _write_json,
)
from trusted_synthesis.hashing import canonical_hash

AUTHORIZATION_VERSION = CONTRIBUTION_APPROXIMATION_AUTHORIZATION_VERSION
CALIBRATION_FLOOR = 1e-12
ENERGY_EPSILON = 1e-4
HISTORY_EXPONENT = 0.5
ENERGY_EXPONENT = 0.5
CONTRIBUTION_WEIGHT = 0.5
DISTRIBUTION_THRESHOLDS = ContributionDistributionGateThresholds(
    maximum_mean_total_variation=0.10,
    maximum_p95_total_variation=0.20,
    maximum_mean_jensen_shannon=0.02,
    maximum_p95_jensen_shannon=0.05,
    minimum_update_direction_agreement=0.75,
    maximum_mean_absolute_target_regret=0.01,
    maximum_p95_absolute_target_regret=0.03,
    maximum_mean_normalized_target_regret=0.25,
    maximum_p95_normalized_target_regret=0.60,
    minimum_mean_attainable_gain=1e-6,
    minimum_normalizable_attainable_gain=1e-6,
    minimum_normalizable_task_rate=0.80,
)


def _assert_canonical_artifact(
    artifact: Mapping[str, Any],
    *,
    hash_field: str,
    prefix: str,
    artifact_name: str,
) -> str:
    unhashed = dict(artifact)
    observed = unhashed.pop(hash_field, None)
    expected = canonical_hash(unhashed, prefix=prefix)
    if observed != expected:
        raise ValueError(f"{artifact_name} identity changed")
    return str(observed)


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values or not 0 <= probability <= 1:
        raise ValueError("authorization percentile input is invalid")
    ordered = sorted(float(value) for value in values)
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    result = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][1] == ordered[cursor][1]:
            end += 1
        rank = (cursor + end - 1) / 2.0
        for index in range(cursor, end):
            result[ordered[index][0]] = rank
        cursor = end
    return result


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    left_rank = _ranks(left)
    right_rank = _ranks(right)
    left_mean = statistics.fmean(left_rank)
    right_mean = statistics.fmean(right_rank)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left_rank, right_rank, strict=True)
    )
    denominator = math.sqrt(
        sum((value - left_mean) ** 2 for value in left_rank)
        * sum((value - right_mean) ** 2 for value in right_rank)
    )
    return numerator / denominator if denominator > 0 else 0.0


def _pairwise_concordance(left: Sequence[float], right: Sequence[float]) -> float:
    agreements = []
    for first in range(len(left)):
        for second in range(first + 1, len(left)):
            left_delta = left[first] - left[second]
            right_delta = right[first] - right[second]
            agreements.append(
                1.0
                if (left_delta == 0 and right_delta == 0) or left_delta * right_delta > 0
                else 0.0
            )
    return statistics.fmean(agreements) if agreements else 1.0


def _bootstrap_ci(values: Sequence[float], *, seed: int) -> tuple[float, float]:
    if not values:
        raise ValueError("authorization bootstrap support is empty")
    randomizer = random.Random(seed)
    samples = sorted(
        statistics.fmean(randomizer.choice(values) for _ in values)
        for _ in range(5000)
    )
    return samples[124], samples[4874]


def _permutation_p_value(
    task_vectors: Sequence[tuple[Sequence[float], Sequence[float]]],
    *,
    statistic: Literal["spearman", "concordance"],
    seed: int,
) -> float:
    function = _spearman if statistic == "spearman" else _pairwise_concordance
    observed = statistics.fmean(function(left, right) for left, right in task_vectors)
    randomizer = random.Random(seed)
    exceedances = 0
    iterations = 10000
    for _ in range(iterations):
        permuted = []
        for left, right in task_vectors:
            shuffled = list(right)
            randomizer.shuffle(shuffled)
            permuted.append(function(left, shuffled))
        exceedances += statistics.fmean(permuted) >= observed
    return (exceedances + 1) / (iterations + 1)


def _rank_metrics(
    state_rows: Sequence[Mapping[str, Any]],
    *,
    seed: int,
) -> dict[str, Any]:
    grouped: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in state_rows:
        grouped[str(row["task_id"])].append(row)
    task_rows = []
    vectors = []
    for task_id, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda row: str(row["state_id"]))
        proxy = [float(row["scaled_gp_c_proxy"]) for row in ordered]
        target = [float(row["finite_target"]) for row in ordered]
        states = [str(row["state_id"]) for row in ordered]
        spearman = _spearman(proxy, target)
        concordance = _pairwise_concordance(proxy, target)
        winner = float(
            states[max(range(len(proxy)), key=proxy.__getitem__)]
            == states[max(range(len(target)), key=target.__getitem__)]
        )
        task_rows.append(
            {
                "task_id": task_id,
                "task_type": ordered[0].get("task_type", "unknown"),
                "spearman": spearman,
                "pairwise_concordance": concordance,
                "winner_agreement": winner,
            }
        )
        vectors.append((proxy, target))
    spearman_values = [float(row["spearman"]) for row in task_rows]
    concordance_values = [float(row["pairwise_concordance"]) for row in task_rows]
    winner_values = [float(row["winner_agreement"]) for row in task_rows]
    return {
        "macro_task_spearman": statistics.fmean(spearman_values),
        "macro_task_spearman_ci95": _bootstrap_ci(spearman_values, seed=seed),
        "macro_pairwise_concordance": statistics.fmean(concordance_values),
        "macro_pairwise_concordance_ci95": _bootstrap_ci(
            concordance_values,
            seed=seed + 1,
        ),
        "winner_agreement_rate": statistics.fmean(winner_values),
        "macro_spearman_p_value": _permutation_p_value(
            vectors,
            statistic="spearman",
            seed=seed + 2,
        ),
        "macro_pairwise_concordance_p_value": _permutation_p_value(
            vectors,
            statistic="concordance",
            seed=seed + 3,
        ),
        "task_rows": task_rows,
    }


def _normalize_contribution(value: float, *, temperature: float) -> float:
    scaled = value / temperature
    if scaled >= 0:
        sigmoid = 1.0 / (1.0 + math.exp(-scaled))
    else:
        exponential = math.exp(scaled)
        sigmoid = exponential / (1.0 + exponential)
    return ENERGY_EPSILON + (1.0 - 2.0 * ENERGY_EPSILON) * sigmoid


def _next_distribution(
    probabilities: Sequence[float],
    values: Sequence[float],
    *,
    temperature: float,
) -> tuple[list[float], list[float]]:
    normalized = [_normalize_contribution(value, temperature=temperature) for value in values]
    log_weights = [
        HISTORY_EXPONENT * math.log(probability)
        + (1.0 - HISTORY_EXPONENT) * math.log(probability)
        + ENERGY_EXPONENT * CONTRIBUTION_WEIGHT * math.log(contribution)
        for probability, contribution in zip(probabilities, normalized, strict=True)
    ]
    maximum = max(log_weights)
    unnormalized = [math.exp(value - maximum) for value in log_weights]
    total = sum(unnormalized)
    return [value / total for value in unnormalized], normalized


def _kl(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * math.log(a / b) for a, b in zip(left, right, strict=True))


def _jensen_shannon(left: Sequence[float], right: Sequence[float]) -> float:
    midpoint = [(a + b) / 2.0 for a, b in zip(left, right, strict=True)]
    return 0.5 * _kl(left, midpoint) + 0.5 * _kl(right, midpoint)


def _variational_objective(
    candidate: Sequence[float],
    current: Sequence[float],
    target_normalized: Sequence[float],
) -> float:
    expected = sum(
        probability * CONTRIBUTION_WEIGHT * math.log(value)
        for probability, value in zip(candidate, target_normalized, strict=True)
    )
    return expected - 2.0 * _kl(candidate, current)


def _direction_agreement(
    current: Sequence[float],
    proxy: Sequence[float],
    target: Sequence[float],
) -> float:
    def sign(value: float) -> int:
        return 0 if abs(value) <= 1e-12 else (1 if value > 0 else -1)

    return statistics.fmean(
        float(sign(left - base) == sign(right - base))
        for base, left, right in zip(current, proxy, target, strict=True)
    )


def _distribution_metrics(
    state_rows: Sequence[Mapping[str, Any]],
    *,
    temperature: float,
    normalizable_gain_floor: float,
) -> dict[str, Any]:
    grouped: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in state_rows:
        grouped[str(row["task_id"])].append(row)
    task_rows = []
    for task_id, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda row: str(row["state_id"]))
        current = [float(row["current_probability"]) for row in ordered]
        proxy_values = [float(row["scaled_gp_c_proxy"]) for row in ordered]
        target_values = [float(row["finite_target"]) for row in ordered]
        proxy_next, _ = _next_distribution(current, proxy_values, temperature=temperature)
        target_next, target_normalized = _next_distribution(
            current,
            target_values,
            temperature=temperature,
        )
        proxy_objective = _variational_objective(
            proxy_next,
            current,
            target_normalized,
        )
        target_objective = _variational_objective(
            target_next,
            current,
            target_normalized,
        )
        current_objective = _variational_objective(
            current,
            current,
            target_normalized,
        )
        regret = max(0.0, target_objective - proxy_objective)
        attainable_task_gain = max(0.0, target_objective - current_objective)
        is_normalizable = attainable_task_gain >= normalizable_gain_floor
        task_rows.append(
            {
                "task_id": task_id,
                "task_type": ordered[0].get("task_type", "unknown"),
                "total_variation": 0.5
                * sum(abs(a - b) for a, b in zip(proxy_next, target_next, strict=True)),
                "jensen_shannon": _jensen_shannon(proxy_next, target_next),
                "update_direction_agreement": _direction_agreement(
                    current,
                    proxy_next,
                    target_next,
                ),
                "absolute_target_regret": regret,
                "attainable_gain": attainable_task_gain,
                "normalized_target_regret": (
                    regret / attainable_task_gain if is_normalizable else None
                ),
                "is_normalizable": is_normalizable,
            }
        )
    by_type: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    ordered_by_gain = sorted(task_rows, key=lambda row: float(row["attainable_gain"]))
    for row in task_rows:
        by_type[str(row["task_type"])].append(row)
    gain_quantiles = {
        label: rows
        for label, rows in (
            ("low", ordered_by_gain[: len(ordered_by_gain) // 3]),
            (
                "mid",
                ordered_by_gain[len(ordered_by_gain) // 3 : 2 * len(ordered_by_gain) // 3],
            ),
            ("high", ordered_by_gain[2 * len(ordered_by_gain) // 3 :]),
        )
    }
    total_variation = [float(row["total_variation"]) for row in task_rows]
    jensen_shannon = [float(row["jensen_shannon"]) for row in task_rows]
    direction = [float(row["update_direction_agreement"]) for row in task_rows]
    absolute_regret = [float(row["absolute_target_regret"]) for row in task_rows]
    normalizable_rows = [row for row in task_rows if bool(row["is_normalizable"])]
    normalized_regret = [
        float(row["normalized_target_regret"])
        for row in normalizable_rows
    ]
    attainable_gains = [float(row["attainable_gain"]) for row in task_rows]
    task_type_summary = {
        task_type: {
            "task_count": len(rows),
            "mean_total_variation": statistics.fmean(
                float(row["total_variation"]) for row in rows
            ),
            "normalizable_task_count": sum(bool(row["is_normalizable"]) for row in rows),
            "normalizable_task_rate": statistics.fmean(
                float(bool(row["is_normalizable"])) for row in rows
            ),
            "mean_normalized_target_regret": (
                statistics.fmean(
                    float(row["normalized_target_regret"])
                    for row in rows
                    if bool(row["is_normalizable"])
                )
                if any(bool(row["is_normalizable"]) for row in rows)
                else None
            ),
        }
        for task_type, rows in sorted(by_type.items())
    }
    gain_quantile_summary = {
        label: {
            "task_count": len(rows),
            "mean_attainable_gain": statistics.fmean(
                float(row["attainable_gain"]) for row in rows
            ),
            "normalizable_task_count": sum(bool(row["is_normalizable"]) for row in rows),
            "mean_normalized_target_regret": (
                statistics.fmean(
                    float(row["normalized_target_regret"])
                    for row in rows
                    if bool(row["is_normalizable"])
                )
                if any(bool(row["is_normalizable"]) for row in rows)
                else None
            ),
        }
        for label, rows in gain_quantiles.items()
        if rows
    }
    return {
        "task_count": len(task_rows),
        "mean_total_variation": statistics.fmean(total_variation),
        "p95_total_variation": _percentile(total_variation, 0.95),
        "mean_jensen_shannon": statistics.fmean(jensen_shannon),
        "p95_jensen_shannon": _percentile(jensen_shannon, 0.95),
        "mean_update_direction_agreement": statistics.fmean(direction),
        "mean_absolute_target_regret": statistics.fmean(absolute_regret),
        "p95_absolute_target_regret": _percentile(absolute_regret, 0.95),
        "mean_normalized_target_regret": (
            statistics.fmean(normalized_regret) if normalized_regret else 0.0
        ),
        "p95_normalized_target_regret": (
            _percentile(normalized_regret, 0.95) if normalized_regret else 0.0
        ),
        "mean_attainable_gain": statistics.fmean(attainable_gains),
        "normalizable_gain_floor": normalizable_gain_floor,
        "normalizable_task_count": len(normalizable_rows),
        "normalizable_task_rate": len(normalizable_rows) / len(task_rows),
        "task_type_stratified_metrics_hash": canonical_hash(
            task_type_summary,
            prefix="finance_authorization_task_type_metrics:",
        ),
        "gain_quantile_metrics_hash": canonical_hash(
            gain_quantile_summary,
            prefix="finance_authorization_gain_quantiles:",
        ),
        "task_type_stratified_metrics": task_type_summary,
        "gain_quantile_metrics": gain_quantile_summary,
        "task_rows": task_rows,
    }


def _role_name(role: str) -> Literal[
    "internal_estimation",
    "internal_validation",
    "independent_authorization",
]:
    if role == "estimation":
        return "internal_estimation"
    if role == "validation":
        return "internal_validation"
    if role == "authorization":
        return "independent_authorization"
    raise ValueError(f"unknown authorization role:{role}")


def _validate_evidence_chain(
    *,
    gradient_plan: Mapping[str, Any],
    gradient_report: Mapping[str, Any],
    support_scaling_report: Mapping[str, Any],
    local_update_manifest: Mapping[str, Any],
    finite_target_plans: Mapping[str, Mapping[str, Any]],
    direction_manifests: Mapping[str, Mapping[str, Any]],
    finite_target_reports: Mapping[str, Mapping[str, Any]],
    proxy_reports: Mapping[str, Mapping[str, Any]],
    objective_gradient_manifests: Mapping[str, Mapping[str, Any]],
) -> tuple[
    dict[str, tuple[str, ...]],
    str,
    dict[str, ConditionalTrajectoryDistribution],
]:
    _assert_canonical_artifact(
        gradient_plan,
        hash_field="plan_hash",
        prefix="finance_contribution_gradient_plan:",
        artifact_name="Gradient Projection plan",
    )
    _assert_canonical_artifact(
        gradient_report,
        hash_field="report_hash",
        prefix="finance_contribution_gradient_report:",
        artifact_name="Gradient Projection report",
    )
    _assert_canonical_artifact(
        support_scaling_report,
        hash_field="report_hash",
        prefix="finance_objective_support_scaling_report:",
        artifact_name="objective-support scaling report",
    )
    if gradient_report.get("plan_hash") != gradient_plan.get("plan_hash"):
        raise ValueError("Gradient Projection report belongs to another plan")
    token_regions = gradient_plan.get("token_region_decomposition", {})
    _assert_canonical_artifact(
        token_regions,
        hash_field="manifest_hash",
        prefix="finance_gradient_token_region_manifest:",
        artifact_name="Gradient Projection token-region manifest",
    )
    token_rows = token_regions.get("records", {})
    jobs = tuple(gradient_plan.get("jobs", ()))
    job_records = tuple(str(row["record_id"]) for row in jobs)
    job_record_ids = set(job_records)
    if (
        token_regions.get("version") != TOKEN_REGION_DECOMPOSITION_VERSION
        or token_regions.get("status") != "passed"
        or token_regions.get("coverage_gate_policy")
        != "minimum_task_pooled_differential_supervised_tokens"
        or token_regions.get("record_level_policy")
        != "non_empty_regions_required_fraction_is_diagnostic"
        or set(token_rows) != job_record_ids
        or len(job_records) != len(job_record_ids)
        or gradient_report.get("token_region_manifest_hash")
        != token_regions.get("manifest_hash")
    ):
        raise ValueError("Gradient Projection token-region support is incomplete")
    token_audit = gradient_plan.get("token_audit", {})
    for record_id, row in token_rows.items():
        common = tuple(int(value) for value in row["common_label_positions"])
        differential = tuple(
            int(value) for value in row["differential_label_positions"]
        )
        if (
            not common
            or not differential
            or tuple(sorted(set(common))) != common
            or tuple(sorted(set(differential))) != differential
            or set(common) & set(differential)
            or len(common) != int(row["common_supervised_token_count"])
            or len(differential) != int(row["differential_supervised_token_count"])
            or len(common) + len(differential)
            != int(token_audit.get(record_id, {}).get("supervised_tokens", -1))
            or not math.isclose(
                float(row["differential_supervised_token_fraction"]),
                len(differential) / (len(common) + len(differential)),
                abs_tol=1e-12,
            )
        ):
            raise ValueError("Gradient Projection token-region partition is invalid")

    records_by_task: defaultdict[str, list[str]] = defaultdict(list)
    records_by_state: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for job in jobs:
        task_id = str(job["task_id"])
        state_id = str(job["state_id"])
        record_id = str(job["record_id"])
        records_by_task[task_id].append(record_id)
        records_by_state[(task_id, state_id)].append(record_id)

    def summarize(record_ids: Sequence[str]) -> dict[str, int | float]:
        rows = [token_rows[record_id] for record_id in record_ids]
        fractions = [
            float(row["differential_supervised_token_fraction"]) for row in rows
        ]
        differential_count = sum(
            int(row["differential_supervised_token_count"]) for row in rows
        )
        supervised_count = sum(
            int(row["common_supervised_token_count"])
            + int(row["differential_supervised_token_count"])
            for row in rows
        )
        return {
            "record_count": len(rows),
            "minimum_record_differential_supervised_token_fraction": min(fractions),
            "mean_record_differential_supervised_token_fraction": statistics.fmean(
                fractions
            ),
            "pooled_differential_supervised_token_fraction": (
                differential_count / supervised_count
            ),
        }

    def assert_summary(
        observed: Mapping[str, Any],
        expected: Mapping[str, int | float],
    ) -> None:
        if int(observed.get("record_count", -1)) != int(expected["record_count"]):
            raise ValueError("Gradient Projection token-region aggregate is invalid")
        for field in (
            "minimum_record_differential_supervised_token_fraction",
            "mean_record_differential_supervised_token_fraction",
            "pooled_differential_supervised_token_fraction",
        ):
            if not math.isclose(
                float(observed.get(field, -1.0)),
                float(expected[field]),
                abs_tol=1e-12,
            ):
                raise ValueError("Gradient Projection token-region aggregate is invalid")

    task_rows = {
        str(row["task_id"]): row for row in token_regions.get("task_rows", ())
    }
    state_rows = {
        (str(row["task_id"]), str(row["state_id"])): row
        for row in token_regions.get("state_rows", ())
    }
    if (
        len(task_rows) != len(token_regions.get("task_rows", ()))
        or set(task_rows) != set(records_by_task)
        or len(state_rows) != len(token_regions.get("state_rows", ()))
        or set(state_rows) != set(records_by_state)
    ):
        raise ValueError("Gradient Projection token-region aggregates are incomplete")
    expected_task_summaries = {
        task_id: summarize(record_ids)
        for task_id, record_ids in records_by_task.items()
    }
    expected_state_summaries = {
        key: summarize(record_ids) for key, record_ids in records_by_state.items()
    }
    for task_id, expected in expected_task_summaries.items():
        assert_summary(task_rows[task_id], expected)
    for key, expected in expected_state_summaries.items():
        assert_summary(state_rows[key], expected)

    minimum_record_fraction = min(
        float(row["differential_supervised_token_fraction"])
        for row in token_rows.values()
    )
    minimum_state_pooled_fraction = min(
        float(row["pooled_differential_supervised_token_fraction"])
        for row in expected_state_summaries.values()
    )
    minimum_task_pooled_fraction = min(
        float(row["pooled_differential_supervised_token_fraction"])
        for row in expected_task_summaries.values()
    )
    threshold = float(
        token_regions.get(
            "minimum_task_pooled_differential_supervised_token_fraction_threshold",
            -1.0,
        )
    )
    observed_values = (
        (
            "minimum_observed_record_differential_supervised_token_fraction",
            minimum_record_fraction,
        ),
        (
            "minimum_observed_state_pooled_differential_supervised_token_fraction",
            minimum_state_pooled_fraction,
        ),
        (
            "minimum_observed_task_pooled_differential_supervised_token_fraction",
            minimum_task_pooled_fraction,
        ),
    )
    if threshold <= 0 or minimum_task_pooled_fraction < threshold or any(
        not math.isclose(float(token_regions.get(field, -1.0)), value, abs_tol=1e-12)
        for field, value in observed_values
    ):
        raise ValueError("Gradient Projection token-region coverage gate is invalid")
    if gradient_plan.get("run_role") != "production_candidate":
        raise ValueError("typed authorization rejects non-production Gradient plans")
    if gradient_report.get("state_count") != len(gradient_report.get("state_rows", ())):
        raise ValueError("Gradient Projection report has incomplete state support")
    if int(gradient_report.get("task_count", 0)) < 30:
        raise ValueError("typed authorization requires at least 30 tasks")
    _assert_canonical_artifact(
        local_update_manifest,
        hash_field="manifest_hash",
        prefix="finance_gp_c_local_update_manifest:",
        artifact_name="local AdamW update manifest",
    )
    expected_local_update_identity = {
        "source_gradient_plan_hash": gradient_plan["plan_hash"],
        "source_gradient_report_hash": gradient_report["report_hash"],
        "beneficiary_model_state_id": gradient_plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": gradient_plan["beneficiary_checkpoint_hash"],
        "optimizer_contract": gradient_plan["local_optimizer_contract"],
        "task_sampling_contract_hash": gradient_plan["task_sampling_contract_hash"],
        "state_realization_manifest_hash": gradient_plan[
            "state_realization_manifest_hash"
        ],
    }
    local_mismatches = tuple(
        field
        for field, expected in expected_local_update_identity.items()
        if local_update_manifest.get(field) != expected
    )
    if local_mismatches:
        raise ValueError(f"local-update manifest identity mismatch:{local_mismatches}")
    task_probabilities = {
        str(task_id): {
            str(state_id): float(probability)
            for state_id, probability in values["probabilities"].items()
        }
        for task_id, values in gradient_plan["task_distributions"].items()
    }
    task_distributions = {
        str(task_id): ConditionalTrajectoryDistribution.model_validate(
            values["distribution"]
        )
        for task_id, values in gradient_plan["task_distributions"].items()
    }
    if any(
        distribution.probabilities != task_probabilities[task_id]
        for task_id, distribution in task_distributions.items()
    ):
        raise ValueError("typed authorization distribution payload changed probabilities")
    if len(task_probabilities) < 30 or any(
        not 3 <= len(probabilities) <= 5
        or not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-9)
        or any(probability <= 0 for probability in probabilities.values())
        for probabilities in task_probabilities.values()
    ):
        raise ValueError("Gradient Projection task distributions are invalid")
    expected_state_pairs = {
        (task_id, state_id)
        for task_id, probabilities in task_probabilities.items()
        for state_id in probabilities
    }
    report_state_pairs = {
        (str(row["task_id"]), str(row["state_id"]))
        for row in gradient_report["state_rows"]
    }
    if report_state_pairs != expected_state_pairs:
        raise ValueError("Gradient Projection report changed task-state support")
    realization_counts = {
        (str(task_id), str(state_id)): int(count)
        for task_id, state_id, count in gradient_plan["state_realization_manifest"][
            "realization_counts"
        ]
    }
    report_realization_ids = {
        (str(row["task_id"]), str(row["state_id"])): tuple(
            str(value) for value in row["realization_ids"]
        )
        for row in gradient_report["state_rows"]
    }
    if (
        set(realization_counts) != expected_state_pairs
        or set(report_realization_ids) != expected_state_pairs
        or any(not 3 <= count <= 5 for count in realization_counts.values())
        or any(
            len(ids) != realization_counts[key] or len(set(ids)) != len(ids)
            for key, ids in report_realization_ids.items()
        )
    ):
        raise ValueError("Gradient Projection realization lineage is incomplete")
    local_state_pairs = {
        (str(row["task_id"]), str(row["state_id"]))
        for row in local_update_manifest["state_artifacts"]
    }
    local_jackknife_rows: defaultdict[tuple[str, str], list[Mapping[str, Any]]] = (
        defaultdict(list)
    )
    for row in local_update_manifest["state_jackknife_artifacts"]:
        local_jackknife_rows[(str(row["task_id"]), str(row["state_id"]))].append(row)
    if (
        local_state_pairs != expected_state_pairs
        or set(local_jackknife_rows) != expected_state_pairs
        or local_update_manifest.get("state_uncertainty_method")
        != "leave_one_realization_out_jackknife_pseudovalues"
    ):
        raise ValueError("local-update Jackknife support is incomplete")
    for key, rows in local_jackknife_rows.items():
        excluded = tuple(str(row["excluded_realization_id"]) for row in rows)
        jackknife_ids = tuple(str(row["jackknife_id"]) for row in rows)
        if (
            len(rows) != realization_counts[key]
            or set(excluded) != set(report_realization_ids[key])
            or len(set(jackknife_ids)) != len(rows)
        ):
            raise ValueError("local-update Jackknife lineage changed realizations")
    if tuple(support_scaling_report.get("support_sizes", ())) != (4, 8, 16, 32):
        raise ValueError("objective-support scaling omitted its preregistered grid")
    selected_size = int(support_scaling_report.get("selected_minimum_support_size", 0))
    selected_rows = [
        row
        for row in support_scaling_report.get("size_rows", ())
        if int(row.get("support_size", 0)) == selected_size
    ]
    if (
        support_scaling_report.get("status") != "passed"
        or selected_size < 16
        or len(selected_rows) != 1
        or not selected_rows[0].get("passes_stability_gate")
    ):
        raise ValueError("typed authorization requires a passing support-scaling gate")

    expected_record_ids = {
        "estimation": tuple(
            str(value) for value in gradient_plan["gradient_estimation_record_ids"]
        ),
        "validation": tuple(
            str(value) for value in gradient_plan["gradient_validation_record_ids"]
        ),
        "authorization": tuple(str(value) for value in gradient_plan["final_test_record_ids"]),
    }
    if any(
        len(values) < 16 or len(values) != len(set(values))
        for values in expected_record_ids.values()
    ):
        raise ValueError("objective partitions lack 16 unique records")
    if any(
        set(expected_record_ids[left]) & set(expected_record_ids[right])
        for left, right in (
            ("estimation", "validation"),
            ("estimation", "authorization"),
            ("validation", "authorization"),
        )
    ):
        raise ValueError("objective partitions overlap")

    local_update_hashes: set[str] = set()
    for role in ("estimation", "validation", "authorization"):
        finite_plan = finite_target_plans[role]
        direction = direction_manifests[role]
        finite = finite_target_reports[role]
        objective = objective_gradient_manifests[role]
        proxy = proxy_reports[role]
        _assert_canonical_artifact(
            finite_plan,
            hash_field="plan_hash",
            prefix="finance_finite_target_plan:",
            artifact_name=f"{role} finite-target plan",
        )
        _assert_canonical_artifact(
            direction,
            hash_field="manifest_hash",
            prefix="finance_gp_c_finite_target_directions:",
            artifact_name=f"{role} finite-target direction manifest",
        )
        _assert_canonical_artifact(
            finite,
            hash_field="report_hash",
            prefix="finance_finite_target_report:",
            artifact_name=f"{role} finite-target report",
        )
        _assert_canonical_artifact(
            objective,
            hash_field="manifest_hash",
            prefix="finance_post_global_objective_gradient_manifest:",
            artifact_name=f"{role} post-global objective-gradient manifest",
        )
        _assert_canonical_artifact(
            proxy,
            hash_field="report_hash",
            prefix="finance_post_global_gp_c_proxy_report:",
            artifact_name=f"{role} GP-C proxy report",
        )
        expected_identity = {
            "objective_role": role,
            "source_gradient_plan_hash": gradient_plan["plan_hash"],
            "beneficiary_model_state_id": gradient_plan["beneficiary_model_state_id"],
            "beneficiary_checkpoint_hash": gradient_plan["beneficiary_checkpoint_hash"],
            "objective_gradient_point": "post_global_update",
        }
        plan_mismatches = tuple(
            field
            for field, expected in expected_identity.items()
            if finite_plan.get(field) != expected
        )
        if plan_mismatches:
            raise ValueError(f"{role} finite-target plan mismatch:{plan_mismatches}")
        for artifact_name, artifact in (
            ("finite target", finite),
            ("objective gradient", objective),
            ("GP-C proxy", proxy),
        ):
            mismatches = tuple(
                field
                for field, expected in expected_identity.items()
                if artifact.get(field) != expected
            )
            if mismatches:
                raise ValueError(
                    f"{role} {artifact_name} identity mismatch:{mismatches}"
                )
        if finite.get("status") != "passed":
            raise ValueError(f"{role} finite target failed")
        if finite.get("plan_hash") != finite_plan.get("plan_hash"):
            raise ValueError(f"{role} finite-target report crosses plans")
        if direction.get("finite_target_plan_hash") != finite_plan.get("plan_hash"):
            raise ValueError(f"{role} direction manifest crosses finite-target plans")
        if direction.get("source_gradient_plan_hash") != gradient_plan.get("plan_hash"):
            raise ValueError(f"{role} direction manifest crosses Gradient plans")
        if direction.get("local_update_manifest_hash") != local_update_manifest.get(
            "manifest_hash"
        ):
            raise ValueError(f"{role} direction manifest crosses local updates")
        if int(direction.get("jackknife_state_count", 0)) != len(expected_state_pairs):
            raise ValueError(f"{role} direction manifest omits Jackknife support")
        if finite.get("direction_manifest_hash") != direction.get("manifest_hash"):
            raise ValueError(f"{role} finite target crosses direction manifests")
        finite_record_ids = tuple(
            str(value) for value in finite.get("objective_record_ids", ())
        )
        if finite_record_ids != expected_record_ids[role]:
            raise ValueError(f"{role} finite target changed objective records")
        if int(finite.get("objective_record_count", 0)) != len(expected_record_ids[role]):
            raise ValueError(f"{role} finite target record count is inconsistent")
        if objective.get("finite_target_plan_hash") != finite.get("plan_hash"):
            raise ValueError(f"{role} objective gradient crosses finite-target plans")
        objective_record_ids = tuple(
            str(value) for value in objective.get("objective_record_ids", ())
        )
        if objective_record_ids != expected_record_ids[role]:
            raise ValueError(f"{role} objective gradient changed objective records")
        if objective.get("objective_records_hash") != finite.get("objective_records_hash"):
            raise ValueError(f"{role} objective content hash is inconsistent")
        if int(objective.get("objective_record_count", 0)) != len(expected_record_ids[role]):
            raise ValueError(f"{role} objective-gradient count is inconsistent")
        if proxy.get("finite_target_plan_hash") != finite.get("plan_hash"):
            raise ValueError(f"{role} GP-C proxy crosses finite-target plans")
        if proxy.get("finite_target_report_hash") != finite.get("report_hash"):
            raise ValueError(f"{role} GP-C proxy crosses finite-target reports")
        if proxy.get("objective_gradient_manifest_hash") != objective.get("manifest_hash"):
            raise ValueError(f"{role} GP-C proxy crosses objective-gradient manifests")
        if proxy.get("objective_records_hash") != finite.get("objective_records_hash"):
            raise ValueError(f"{role} GP-C proxy changed objective content")
        if proxy.get("status") != "passed":
            raise ValueError(f"{role} GP-C proxy report failed")
        if (
            proxy.get("state_uncertainty_method")
            != local_update_manifest.get("state_uncertainty_method")
        ):
            raise ValueError(f"{role} GP-C proxy changed the Jackknife method")
        proxy_rows = {
            (str(row["task_id"]), str(row["state_id"])): row
            for row in proxy.get("state_rows", ())
        }
        if set(proxy_rows) != expected_state_pairs or len(proxy_rows) != len(
            proxy.get("state_rows", ())
        ):
            raise ValueError(f"{role} GP-C proxy changed task-state support")
        if any(
            not math.isclose(
                float(row["current_probability"]),
                task_probabilities[task_id][state_id],
                abs_tol=1e-12,
            )
            for (task_id, state_id), row in proxy_rows.items()
        ):
            raise ValueError(f"{role} GP-C proxy changed current distributions")
        proxy_realization_ids: set[str] = set()
        for key, row in proxy_rows.items():
            values = tuple(
                float(value) for value in row["jackknife_raw_gp_c_proxy_values"]
            )
            realization_ids = tuple(
                str(value) for value in row["jackknife_realization_ids"]
            )
            expected_count = realization_counts[key]
            if (
                int(row["jackknife_realization_count"]) != expected_count
                or len(values) != expected_count
                or len(realization_ids) != expected_count
                or set(realization_ids) != set(report_realization_ids[key])
                or any(not math.isfinite(value) for value in values)
                or not math.isclose(
                    float(row["jackknife_proxy_sample_standard_deviation"]),
                    statistics.stdev(values),
                    rel_tol=1e-9,
                    abs_tol=1e-12,
                )
            ):
                raise ValueError(f"{role} GP-C proxy Jackknife lineage is invalid")
            if proxy_realization_ids & set(realization_ids):
                raise ValueError(f"{role} GP-C proxy reuses realizations across states")
            proxy_realization_ids.update(realization_ids)
        local_update_hash = str(proxy.get("local_update_manifest_hash", ""))
        if (
            not local_update_hash
            or objective.get("local_update_manifest_hash") != local_update_hash
            or local_update_hash != local_update_manifest.get("manifest_hash")
        ):
            raise ValueError(f"{role} GP-C proxy crosses local-update manifests")
        local_update_hashes.add(local_update_hash)
    if len(local_update_hashes) != 1:
        raise ValueError("objective partitions use different local-update maps")

    prerequisite_hashes = finite_target_reports["authorization"].get(
        "authorization_prerequisite_report_hashes",
        {},
    )
    expected_prerequisite_hashes = {
        "estimation": finite_target_reports["estimation"]["report_hash"],
        "validation": finite_target_reports["validation"]["report_hash"],
    }
    if (
        prerequisite_hashes != expected_prerequisite_hashes
        or finite_target_plans["authorization"].get(
            "authorization_prerequisite_report_hashes"
        )
        != expected_prerequisite_hashes
        or not finite_target_reports["authorization"].get(
            "authorization_access_granted"
        )
    ):
        raise ValueError("authorization partition was opened before frozen development gates")
    if any(
        not finite_target_reports[role].get("development_gate_eligible")
        for role in ("estimation", "validation")
    ):
        raise ValueError("development finite-target gate did not pass")
    return (
        expected_record_ids,
        next(iter(local_update_hashes)),
        task_distributions,
    )


def build_typed_authorization(
    *,
    gradient_plan: Mapping[str, Any],
    gradient_report: Mapping[str, Any],
    support_scaling_report: Mapping[str, Any],
    local_update_manifest: Mapping[str, Any],
    finite_target_plans: Mapping[str, Mapping[str, Any]],
    direction_manifests: Mapping[str, Mapping[str, Any]],
    finite_target_reports: Mapping[str, Mapping[str, Any]],
    proxy_reports: Mapping[str, Mapping[str, Any]],
    objective_gradient_manifests: Mapping[str, Mapping[str, Any]],
) -> ContributionApproximationAuthorization:
    roles = {"estimation", "validation", "authorization"}
    if any(
        set(values) != roles
        for values in (
            finite_target_plans,
            direction_manifests,
            finite_target_reports,
            proxy_reports,
            objective_gradient_manifests,
        )
    ):
        raise ValueError("typed authorization requires all three objective partitions")
    (
        expected_record_ids,
        local_update_manifest_hash,
        task_distributions,
    ) = _validate_evidence_chain(
        gradient_plan=gradient_plan,
        gradient_report=gradient_report,
        support_scaling_report=support_scaling_report,
        local_update_manifest=local_update_manifest,
        finite_target_plans=finite_target_plans,
        direction_manifests=direction_manifests,
        finite_target_reports=finite_target_reports,
        proxy_reports=proxy_reports,
        objective_gradient_manifests=objective_gradient_manifests,
    )
    if gradient_report.get("gradient_realization_stability", {}).get("status") != "passed":
        raise ValueError("typed authorization requires stable state realizations")
    if any(report.get("status") != "passed" for report in finite_target_reports.values()):
        raise ValueError("typed authorization requires passing finite targets")
    if any(
        manifest.get("objective_gradient_point") != "post_global_update"
        for manifest in objective_gradient_manifests.values()
    ):
        raise ValueError("typed authorization requires post-global objective gradients")
    estimation_scale = float(proxy_reports["estimation"]["applied_calibration_scale"])
    if proxy_reports["estimation"].get("calibration_source") != "fitted_on_estimation_only":
        raise ValueError("GP-C calibration was not fitted on estimation only")
    if any(
        proxy_reports[role].get("calibration_source") != "frozen_estimation_scale"
        for role in ("validation", "authorization")
    ):
        raise ValueError("GP-C development scale was not frozen for evaluation")
    if any(
        not math.isclose(
            float(proxy_reports[role]["applied_calibration_scale"]),
            estimation_scale,
            rel_tol=0,
            abs_tol=1e-15,
        )
        for role in ("validation", "authorization")
    ):
        raise ValueError("typed authorization calibration was changed after estimation")
    optimizer_source = gradient_plan["local_optimizer_contract"]
    uncertainty_penalty_coefficient = float(
        gradient_report["uncertainty_penalty_coefficient"]
    )
    if uncertainty_penalty_coefficient <= 0:
        raise ValueError("Gradient Projection uncertainty penalty must be positive")
    optimizer_betas = tuple(float(value) for value in optimizer_source["betas"])
    if len(optimizer_betas) != 2:
        raise ValueError("Contribution optimizer contract requires exactly two betas")
    optimizer = make_contribution_optimizer_update_contract(
        learning_rate=float(optimizer_source["learning_rate"]),
        betas=(optimizer_betas[0], optimizer_betas[1]),
        epsilon=float(optimizer_source["epsilon"]),
        maximum_gradient_norm=float(optimizer_source["maximum_gradient_norm"]),
        trainable_parameter_space=str(gradient_plan["gradient_parameter_space"]),
    )
    partition_ids = {
        "estimation": str(gradient_plan["gradient_estimation_set_id"]),
        "validation": str(gradient_plan["gradient_validation_set_id"]),
        "authorization": str(gradient_plan["final_test_set_id"]),
    }
    partition_hashes = {
        role: str(finite_target_reports[role]["objective_records_hash"])
        for role in roles
    }
    partition_counts = {
        role: int(
            next(
                plan_count
                for plan_count in (
                    finite_target_reports[role].get("objective_record_count"),
                    len(expected_record_ids[role]),
                )
                if plan_count is not None
            )
        )
        for role in roles
    }
    calibration_hash = canonical_hash(
        {
            "method": "global_median_absolute_scale_through_zero",
            "scale": estimation_scale,
            "source_proxy_report_hash": proxy_reports["estimation"]["report_hash"],
        },
        prefix="finance_gp_c_calibration:",
    )
    calibration = make_contribution_calibration_contract(
        estimation_set_id=partition_ids["estimation"],
        validation_set_id=partition_ids["validation"],
        authorization_set_id=partition_ids["authorization"],
        calibration_artifact_hash=calibration_hash,
    )
    rank_evidence = {}
    distribution_evidence = {}
    temperature = max(
        statistics.median(
            abs(float(row["finite_target"]))
            for row in proxy_reports["estimation"]["state_rows"]
        ),
        CALIBRATION_FLOOR,
    )
    diagnostics = {}
    for index, role in enumerate(("estimation", "validation", "authorization")):
        rank = _rank_metrics(proxy_reports[role]["state_rows"], seed=20261200 + index * 10)
        distribution = _distribution_metrics(
            proxy_reports[role]["state_rows"],
            temperature=temperature,
            normalizable_gain_floor=(
                DISTRIBUTION_THRESHOLDS.minimum_normalizable_attainable_gain
            ),
        )
        evidence_role = _role_name(role)
        rank_evidence[role] = make_contribution_rank_validation_evidence(
            evaluation_role=evidence_role,
            macro_task_spearman=rank["macro_task_spearman"],
            macro_task_spearman_ci95=rank["macro_task_spearman_ci95"],
            macro_pairwise_concordance=rank["macro_pairwise_concordance"],
            macro_pairwise_concordance_ci95=rank["macro_pairwise_concordance_ci95"],
            winner_agreement_rate=rank["winner_agreement_rate"],
            macro_spearman_p_value=rank["macro_spearman_p_value"],
            macro_pairwise_concordance_p_value=rank[
                "macro_pairwise_concordance_p_value"
            ],
        )
        distribution_evidence[role] = make_contribution_distribution_validation_evidence(
            evaluation_role=evidence_role,
            task_count=distribution["task_count"],
            mean_total_variation=distribution["mean_total_variation"],
            p95_total_variation=distribution["p95_total_variation"],
            mean_jensen_shannon=distribution["mean_jensen_shannon"],
            p95_jensen_shannon=distribution["p95_jensen_shannon"],
            mean_update_direction_agreement=distribution[
                "mean_update_direction_agreement"
            ],
            mean_absolute_target_regret=distribution["mean_absolute_target_regret"],
            p95_absolute_target_regret=distribution["p95_absolute_target_regret"],
            mean_normalized_target_regret=distribution[
                "mean_normalized_target_regret"
            ],
            p95_normalized_target_regret=distribution[
                "p95_normalized_target_regret"
            ],
            mean_attainable_gain=distribution["mean_attainable_gain"],
            normalizable_task_count=distribution["normalizable_task_count"],
            normalizable_task_rate=distribution["normalizable_task_rate"],
            task_type_stratified_metrics_hash=distribution[
                "task_type_stratified_metrics_hash"
            ],
            gain_quantile_metrics_hash=distribution["gain_quantile_metrics_hash"],
            thresholds=DISTRIBUTION_THRESHOLDS,
        )
        diagnostics[role] = {"rank": rank, "distribution": distribution}
    realization_counts = {
        (str(task_id), str(state_id)): int(count)
        for task_id, state_id, count in gradient_plan["state_realization_manifest"][
            "realization_counts"
        ]
    }
    analysis_report_hash = canonical_hash(
        diagnostics,
        prefix="finance_typed_authorization_analysis:",
    )
    return make_contribution_approximation_authorization(
        analysis_report_hash=analysis_report_hash,
        source_plan_hash=str(gradient_plan["plan_hash"]),
        local_update_manifest_hash=local_update_manifest_hash,
        beneficiary_model_state_id=str(gradient_plan["beneficiary_model_state_id"]),
        beneficiary_checkpoint_hash=str(gradient_plan["beneficiary_checkpoint_hash"]),
        target_metric_id="negative_supervised_token_nll",
        optimizer_contract=optimizer,
        calibration_contract=calibration,
        objective_partition_ids=partition_ids,
        objective_partition_hashes=partition_hashes,
        objective_record_counts=partition_counts,
        task_distributions=task_distributions,
        state_realization_counts=realization_counts,
        task_sampling_contract_hash=str(gradient_plan["task_sampling_contract_hash"]),
        state_realization_manifest_hash=str(
            gradient_plan["state_realization_manifest_hash"]
        ),
        gradient_diagnostics_hash=str(gradient_report["gradient_diagnostics_hash"]),
        token_region_manifest_hash=str(
            gradient_plan["token_region_decomposition"]["manifest_hash"]
        ),
        finite_target_report_hashes={
            role: str(finite_target_reports[role]["report_hash"]) for role in roles
        },
        post_global_objective_gradient_hashes={
            role: str(objective_gradient_manifests[role]["manifest_hash"])
            for role in roles
        },
        proxy_report_hashes={
            role: str(proxy_reports[role]["report_hash"]) for role in roles
        },
        uncertainty_penalty_coefficient=uncertainty_penalty_coefficient,
        state_uncertainty_method=(
            "leave_one_realization_out_jackknife_pseudovalues"
        ),
        objective_support_scaling_report_hash=str(support_scaling_report["report_hash"]),
        gradient_realization_stability_report_hash=str(
            gradient_report["gradient_realization_stability"]["evidence_hash"]
        ),
        strict_freshness_contract_hash=canonical_hash(
            {
                "state_realizations": gradient_plan["state_realization_manifest_hash"],
                "task_sampling": gradient_plan["task_sampling_contract_hash"],
                "objective_partition_hashes": partition_hashes,
                "objective_partitions_disjoint": True,
            },
            prefix="finance_gradient_strict_freshness:",
        ),
        internal_estimation_rank=rank_evidence["estimation"],
        internal_validation_rank=rank_evidence["validation"],
        independent_authorization_rank=rank_evidence["authorization"],
        internal_estimation_distribution=distribution_evidence["estimation"],
        internal_validation_distribution=distribution_evidence["validation"],
        independent_authorization_distribution=distribution_evidence[
            "authorization"
        ],
    )


def _authorize(args: argparse.Namespace) -> None:
    gradient_dir = Path(args.gradient_dir).resolve()
    gradient_plan = _read_json(gradient_dir / "plan.json")
    gradient_report = _read_json(gradient_dir / "report.json")
    support_scaling = _read_json(Path(args.support_scaling_report).resolve())
    local_update_manifest = _read_json(Path(args.local_update_manifest).resolve())
    finite_plans = {
        role: _read_json(Path(path).resolve())
        for role, path in (
            ("estimation", args.estimation_finite_plan),
            ("validation", args.validation_finite_plan),
            ("authorization", args.authorization_finite_plan),
        )
    }
    direction_manifests = {
        role: _read_json(Path(path).resolve())
        for role, path in (
            ("estimation", args.estimation_direction_manifest),
            ("validation", args.validation_direction_manifest),
            ("authorization", args.authorization_direction_manifest),
        )
    }
    finite_reports = {
        role: _read_json(Path(path).resolve())
        for role, path in (
            ("estimation", args.estimation_finite_report),
            ("validation", args.validation_finite_report),
            ("authorization", args.authorization_finite_report),
        )
    }
    proxy_reports = {
        role: _read_json(Path(path).resolve())
        for role, path in (
            ("estimation", args.estimation_proxy_report),
            ("validation", args.validation_proxy_report),
            ("authorization", args.authorization_proxy_report),
        )
    }
    objective_manifests = {
        role: _read_json(Path(path).resolve())
        for role, path in (
            ("estimation", args.estimation_objective_manifest),
            ("validation", args.validation_objective_manifest),
            ("authorization", args.authorization_objective_manifest),
        )
    }
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        authorization = build_typed_authorization(
            gradient_plan=gradient_plan,
            gradient_report=gradient_report,
            support_scaling_report=support_scaling,
            local_update_manifest=local_update_manifest,
            finite_target_plans=finite_plans,
            direction_manifests=direction_manifests,
            finite_target_reports=finite_reports,
            proxy_reports=proxy_reports,
            objective_gradient_manifests=objective_manifests,
        )
    except (ValueError, KeyError) as error:
        denial = {
            "experiment_version": AUTHORIZATION_VERSION,
            "artifact_type": "ContributionApproximationDenialReport",
            "status": "denied",
            "reason": str(error),
            "production_credential_issued": False,
        }
        denial["report_hash"] = canonical_hash(
            denial,
            prefix="finance_contribution_authorization_denial:",
        )
        _write_json(output_dir / "denial_report.json", denial)
        print(json.dumps(denial, ensure_ascii=False, indent=2, sort_keys=True))
        return
    _write_json(
        output_dir / "contribution_approximation_authorization.json",
        authorization.model_dump(mode="json"),
    )
    print(authorization.model_dump_json(indent=2))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Issue the only production-valid typed GP-C authorization"
    )
    parser.add_argument("--gradient-dir", required=True)
    parser.add_argument("--support-scaling-report", required=True)
    parser.add_argument("--local-update-manifest", required=True)
    parser.add_argument("--estimation-finite-plan", required=True)
    parser.add_argument("--validation-finite-plan", required=True)
    parser.add_argument("--authorization-finite-plan", required=True)
    parser.add_argument("--estimation-direction-manifest", required=True)
    parser.add_argument("--validation-direction-manifest", required=True)
    parser.add_argument("--authorization-direction-manifest", required=True)
    parser.add_argument("--estimation-finite-report", required=True)
    parser.add_argument("--validation-finite-report", required=True)
    parser.add_argument("--authorization-finite-report", required=True)
    parser.add_argument("--estimation-proxy-report", required=True)
    parser.add_argument("--validation-proxy-report", required=True)
    parser.add_argument("--authorization-proxy-report", required=True)
    parser.add_argument("--estimation-objective-manifest", required=True)
    parser.add_argument("--validation-objective-manifest", required=True)
    parser.add_argument("--authorization-objective-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.set_defaults(handler=_authorize)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
