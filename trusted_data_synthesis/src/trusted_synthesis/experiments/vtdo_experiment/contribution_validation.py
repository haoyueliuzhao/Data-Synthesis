from __future__ import annotations

import math
import random
from collections import defaultdict
from itertools import combinations

from .schema import (
    ContributionValidationConfig,
    ContributionValidationObservation,
    ContributionValidationReport,
    contribution_validation_report_id,
)
from .statistics import aggregate_metric


def run_contribution_validation(
    config: ContributionValidationConfig,
) -> ContributionValidationReport:
    """Compare estimated state contribution with observed downstream delta-J.

    This experiment never synthesizes missing observations. It remains blocked until
    paired intervention results from a frozen beneficiary model and evaluation set exist.
    """

    blockers: list[str] = []
    observations: tuple[ContributionValidationObservation, ...] = ()
    if config.observation_path is None:
        blockers.append("contribution_observation_path_not_configured")
    elif not config.observation_path.is_file():
        blockers.append(f"contribution_observation_path_missing:{config.observation_path}")
    else:
        observations = tuple(
            ContributionValidationObservation.model_validate_json(line)
            for line in config.observation_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    task_ids = {item.task_condition_id for item in observations}
    state_keys = {(item.task_condition_id, item.state_id) for item in observations}
    if len(state_keys) != len(observations):
        blockers.append("duplicate_task_state_contribution_observation")
    if len(observations) < config.minimum_observation_count:
        blockers.append(
            f"contribution_observations_below_minimum:{len(observations)}<"
            f"{config.minimum_observation_count}"
        )
    if len(task_ids) < config.minimum_unique_task_count:
        blockers.append(
            f"contribution_tasks_below_minimum:{len(task_ids)}<{config.minimum_unique_task_count}"
        )

    identity_fields = {
        "beneficiary_model_state_id": {
            item.beneficiary_model_state_id for item in observations
        },
        "evaluation_distribution_id": {
            item.evaluation_distribution_id for item in observations
        },
        "target_metric_id": {item.target_metric_id for item in observations},
        "probe_protocol_hash": {item.probe_protocol_hash for item in observations},
        "baseline_distribution_id": {
            item.baseline_distribution_id for item in observations
        },
        "training_intervention_budget": {
            str(item.training_intervention_budget) for item in observations
        },
        "seed": {str(item.seed) for item in observations},
        "evaluation_snapshot_hash": {
            item.evaluation_snapshot_hash for item in observations
        },
    }
    frozen_identity: dict[str, str] = {}
    if observations:
        for field, identity_values in identity_fields.items():
            if len(identity_values) != 1:
                blockers.append(f"contribution_identity_mismatch:{field}")
            else:
                frozen_identity[field] = next(iter(identity_values))

    grouped: defaultdict[str, list[ContributionValidationObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.task_condition_id].append(observation)
    eligible = {
        task_id: tuple(sorted(values, key=lambda item: item.state_id))
        for task_id, values in grouped.items()
        if len({item.state_id for item in values}) >= config.minimum_states_per_task
    }
    if len(eligible) < config.minimum_unique_task_count:
        blockers.append(
            f"contribution_eligible_tasks_below_minimum:{len(eligible)}<"
            f"{config.minimum_unique_task_count}"
        )
    insufficient = sorted(set(grouped) - set(eligible))
    if insufficient:
        blockers.append(
            "contribution_tasks_below_state_minimum:" + ",".join(insufficient[:20])
        )

    task_spearman_values: list[float] = []
    task_concordance_values: list[float] = []
    centered_estimates: list[float] = []
    centered_outcomes: list[float] = []
    sign_matches = 0
    sign_denominator = 0
    pair_count = 0
    for task_values in eligible.values():
        estimates = [item.estimated_contribution for item in task_values]
        outcomes = [item.observed_delta_j for item in task_values]
        task_spearman_values.append(_spearman(estimates, outcomes))
        estimate_mean = sum(estimates) / len(estimates)
        outcome_mean = sum(outcomes) / len(outcomes)
        centered_left = [value - estimate_mean for value in estimates]
        centered_right = [value - outcome_mean for value in outcomes]
        centered_estimates.extend(centered_left)
        centered_outcomes.extend(centered_right)
        for left, right in zip(centered_left, centered_right, strict=True):
            sign_matches += int(_sign(left) == _sign(right))
            sign_denominator += 1
        concordant = 0
        task_pairs = 0
        for left_index, right_index in combinations(range(len(task_values)), 2):
            estimated_direction = _sign(estimates[left_index] - estimates[right_index])
            observed_direction = _sign(outcomes[left_index] - outcomes[right_index])
            if estimated_direction == 0 and observed_direction == 0:
                continue
            task_pairs += 1
            concordant += int(estimated_direction == observed_direction)
        if task_pairs:
            task_concordance_values.append(concordant / task_pairs)
            pair_count += task_pairs

    task_rank = aggregate_metric(task_spearman_values) if task_spearman_values else None
    centered_spearman = (
        _spearman(centered_estimates, centered_outcomes)
        if len(centered_estimates) >= 2
        else None
    )
    pairwise_concordance = (
        sum(task_concordance_values) / len(task_concordance_values)
        if task_concordance_values
        else None
    )
    sign_agreement = sign_matches / sign_denominator if sign_denominator else None
    task_rank_ci = _cluster_bootstrap_interval(
        task_spearman_values,
        samples=config.cluster_bootstrap_samples,
        seed=config.bootstrap_seed,
    )
    concordance_ci = _cluster_bootstrap_interval(
        task_concordance_values,
        samples=config.cluster_bootstrap_samples,
        seed=config.bootstrap_seed + 1,
    )
    if task_rank is not None and task_rank.mean < config.minimum_macro_spearman:
        blockers.append(
            "contribution_macro_spearman_below_threshold:"
            f"{task_rank.mean:.6f}<{config.minimum_macro_spearman:.6f}"
        )
    if (
        pairwise_concordance is not None
        and pairwise_concordance < config.minimum_pairwise_concordance
    ):
        blockers.append(
            "contribution_pairwise_concordance_below_threshold:"
            f"{pairwise_concordance:.6f}<"
            f"{config.minimum_pairwise_concordance:.6f}"
        )

    report_values = {
        "observation_count": len(observations),
        "unique_task_count": len(task_ids),
        "unique_state_count": len(state_keys),
        "eligible_task_count": len(eligible),
        "task_rank_correlation": task_rank,
        "task_rank_bootstrap_ci95": task_rank_ci,
        "centered_global_spearman": centered_spearman,
        "pairwise_concordance_rate": pairwise_concordance,
        "pairwise_concordance_bootstrap_ci95": concordance_ci,
        "pair_count": pair_count,
        "sign_agreement_rate": sign_agreement,
        "frozen_identity": frozen_identity,
        "status": "blocked" if blockers else "passed",
        "blockers": tuple(sorted(set(blockers))),
        "schema_version": "contribution_validation_report.v2",
    }
    provisional = ContributionValidationReport.model_construct(
        report_id="pending",
        **report_values,
    )
    return ContributionValidationReport(
        report_id=contribution_validation_report_id(provisional),
        **report_values,
    )


def _spearman(left: list[float], right: list[float]) -> float:
    left_ranks = _average_ranks(left)
    right_ranks = _average_ranks(right)
    left_mean = sum(left_ranks) / len(left_ranks)
    right_mean = sum(right_ranks) / len(right_ranks)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left_ranks, right_ranks, strict=True)
    )
    left_scale = sum((value - left_mean) ** 2 for value in left_ranks)
    right_scale = sum((value - right_mean) ** 2 for value in right_ranks)
    denominator = math.sqrt(left_scale * right_scale)
    return numerator / denominator if denominator else 0.0


def _average_ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][1] == ordered[cursor][1]:
            end += 1
        average_rank = ((cursor + 1) + end) / 2.0
        for position in range(cursor, end):
            ranks[ordered[position][0]] = average_rank
        cursor = end
    return ranks


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _cluster_bootstrap_interval(
    task_values: list[float],
    *,
    samples: int,
    seed: int,
) -> tuple[float, float] | None:
    if not task_values:
        return None
    rng = random.Random(seed)
    count = len(task_values)
    draws = sorted(
        sum(rng.choice(task_values) for _ in range(count)) / count
        for _ in range(samples)
    )
    lower_index = max(0, math.floor(0.025 * (samples - 1)))
    upper_index = min(samples - 1, math.ceil(0.975 * (samples - 1)))
    return (draws[lower_index], draws[upper_index])
