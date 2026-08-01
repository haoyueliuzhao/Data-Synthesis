from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from trusted_synthesis.hashing import canonical_hash

from .schema import (
    ContributionValidationConfig,
    ContributionValidationObservation,
    ContributionValidationReport,
    contribution_validation_report_id,
)
from .statistics import aggregate_metric


@dataclass(frozen=True)
class _AggregatedStateObservation:
    task_condition_id: str
    round_index: int
    state_id: str
    probe_contribution: float
    intervention_contribution: float
    intervention_variance: float
    seeds: tuple[int, ...]


def run_contribution_validation(
    config: ContributionValidationConfig,
) -> ContributionValidationReport:
    """Validate local Probes against independent finite Interventions by task-round."""

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
    round_ids = {item.round_index for item in observations}
    task_round_keys = {(item.task_condition_id, item.round_index) for item in observations}
    state_keys = {
        (item.task_condition_id, item.round_index, item.state_id) for item in observations
    }
    atomic_keys = {
        (item.task_condition_id, item.round_index, item.state_id, item.seed)
        for item in observations
    }
    if len(atomic_keys) != len(observations):
        blockers.append("duplicate_task_round_state_seed_contribution_pair")
    trained_artifact_fields = {
        "probe_adapted_model_state": tuple(
            item.probe_observation.adaptation_result.adapted_model_state_id for item in observations
        ),
        "probe_adapted_checkpoint": tuple(
            item.probe_observation.adaptation_result.adapted_checkpoint_hash
            for item in observations
        ),
        "intervention_model_state": tuple(
            item.intervention_observation.training_result.intervention_model_state_id
            for item in observations
        ),
        "intervention_checkpoint": tuple(
            item.intervention_observation.training_result.intervention_checkpoint_hash
            for item in observations
        ),
    }
    for field, identities in trained_artifact_fields.items():
        if len(identities) != len(set(identities)):
            blockers.append(f"contribution_trained_artifact_reused:{field}")
    if len(observations) < config.minimum_observation_count:
        blockers.append(
            f"contribution_observations_below_minimum:{len(observations)}<"
            f"{config.minimum_observation_count}"
        )
    if len(task_ids) < config.minimum_unique_task_count:
        blockers.append(
            f"contribution_tasks_below_minimum:{len(task_ids)}<{config.minimum_unique_task_count}"
        )

    by_state: defaultdict[tuple[str, int, str], list[ContributionValidationObservation]] = (
        defaultdict(list)
    )
    by_task_round: defaultdict[tuple[str, int], list[ContributionValidationObservation]] = (
        defaultdict(list)
    )
    for observation in observations:
        by_state[
            (observation.task_condition_id, observation.round_index, observation.state_id)
        ].append(observation)
        by_task_round[(observation.task_condition_id, observation.round_index)].append(observation)
    seed_sets = {
        key: tuple(sorted({item.seed for item in values})) for key, values in by_state.items()
    }
    canonical_seed_sets = set(seed_sets.values())
    if any(len(value) < config.minimum_seeds_per_state for value in seed_sets.values()):
        blockers.append("contribution_state_seed_coverage_below_minimum")
    if len(canonical_seed_sets) > 1:
        blockers.append("contribution_paired_seed_set_mismatch")
    paired_seeds = next(iter(canonical_seed_sets), ())

    task_round_contract_map: dict[str, dict[str, str]] = {}
    for (task_id, round_index), items in sorted(by_task_round.items()):
        key = f"{task_id}|round={round_index}"
        probe_contracts = {item.probe_observation.probe_contract.protocol_id for item in items}
        intervention_contracts = {
            item.intervention_observation.intervention_contract.protocol_id for item in items
        }
        baseline_distributions = {item.baseline_distribution_id for item in items}
        if len(probe_contracts) != 1:
            blockers.append(f"contribution_probe_contract_not_frozen:{key}")
        if len(intervention_contracts) != 1:
            blockers.append(f"contribution_intervention_contract_not_frozen:{key}")
        if len(baseline_distributions) != 1:
            blockers.append(f"contribution_baseline_distribution_not_frozen:{key}")
        representative = items[0]
        probe = representative.probe_observation.probe_contract
        intervention = representative.intervention_observation.intervention_contract
        task_round_contract_map[key] = {
            "probe_contract_id": next(iter(probe_contracts), "missing"),
            "intervention_contract_id": next(iter(intervention_contracts), "missing"),
            "baseline_distribution_id": next(iter(baseline_distributions), "missing"),
            "beneficiary_model_state_id": probe.beneficiary_model_state_id,
            "beneficiary_checkpoint_hash": probe.beneficiary_checkpoint_hash,
            "evaluation_distribution_id": probe.metric_contract.evaluation_distribution_id,
            "evaluation_snapshot_hash": probe.metric_contract.evaluation_snapshot_hash,
            "target_metric_id": probe.metric_contract.target_metric_id,
            "probe_optimizer_contract_id": probe.optimizer.contract_id,
            "retraining_protocol_hash": intervention.retraining_protocol_hash,
        }
        probe_seed_contract = tuple(sorted(probe.probe_seeds))
        intervention_seed_contract = tuple(sorted(intervention.intervention_seeds))
        observed_seeds = tuple(sorted({item.seed for item in items}))
        if (
            probe_seed_contract != intervention_seed_contract
            or probe_seed_contract != observed_seeds
        ):
            blockers.append(f"contribution_protocol_seed_mismatch:{key}")
    frozen_identity = {
        "task_round_contract_map_hash": canonical_hash(
            task_round_contract_map,
            prefix="contribution_validation_task_round_contract_map:",
        ),
        "task_round_support_hash": canonical_hash(
            tuple(sorted(task_round_keys)),
            prefix="contribution_validation_task_round_support:",
        ),
    }

    aggregated_states: list[_AggregatedStateObservation] = []
    for (task_id, round_index, state_id), values in sorted(by_state.items()):
        probe_values = [item.probe_observation.performance_gain for item in values]
        intervention_values = [
            item.intervention_observation.normalized_intervention_contribution for item in values
        ]
        aggregated_states.append(
            _AggregatedStateObservation(
                task_condition_id=task_id,
                round_index=round_index,
                state_id=state_id,
                probe_contribution=statistics.fmean(probe_values),
                intervention_contribution=statistics.fmean(intervention_values),
                intervention_variance=statistics.pvariance(intervention_values),
                seeds=seed_sets[(task_id, round_index, state_id)],
            )
        )

    grouped: defaultdict[tuple[str, int], list[_AggregatedStateObservation]] = defaultdict(list)
    for item in aggregated_states:
        grouped[(item.task_condition_id, item.round_index)].append(item)
    eligible = {
        key: tuple(sorted(values, key=lambda item: item.state_id))
        for key, values in grouped.items()
        if len({item.state_id for item in values}) >= config.minimum_states_per_task
    }
    eligible_task_ids = {key[0] for key in eligible}
    if len(eligible_task_ids) < config.minimum_unique_task_count:
        blockers.append(
            f"contribution_eligible_tasks_below_minimum:{len(eligible_task_ids)}<"
            f"{config.minimum_unique_task_count}"
        )
    insufficient = sorted(set(grouped) - set(eligible))
    if insufficient:
        rendered = ",".join(f"{task}@{round_index}" for task, round_index in insufficient[:20])
        blockers.append("contribution_task_rounds_below_state_minimum:" + rendered)

    spearman_by_task: defaultdict[str, list[float]] = defaultdict(list)
    concordance_by_task: defaultdict[str, list[float]] = defaultdict(list)
    centered_probes: list[float] = []
    centered_interventions: list[float] = []
    sign_matches = 0
    sign_denominator = 0
    pair_count = 0
    for (task_id, _round_index), state_values in eligible.items():
        probes = [item.probe_contribution for item in state_values]
        interventions = [item.intervention_contribution for item in state_values]
        spearman_by_task[task_id].append(_spearman(probes, interventions))
        probe_mean = statistics.fmean(probes)
        intervention_mean = statistics.fmean(interventions)
        centered_left = [value - probe_mean for value in probes]
        centered_right = [value - intervention_mean for value in interventions]
        centered_probes.extend(centered_left)
        centered_interventions.extend(centered_right)
        for left, right in zip(centered_left, centered_right, strict=True):
            sign_matches += int(_sign(left) == _sign(right))
            sign_denominator += 1
        concordant = 0
        task_pairs = 0
        for left_index, right_index in combinations(range(len(state_values)), 2):
            probe_direction = _sign(probes[left_index] - probes[right_index])
            intervention_direction = _sign(interventions[left_index] - interventions[right_index])
            if probe_direction == 0 and intervention_direction == 0:
                continue
            task_pairs += 1
            concordant += int(probe_direction == intervention_direction)
        if task_pairs:
            concordance_by_task[task_id].append(concordant / task_pairs)
            pair_count += task_pairs

    # A task can contribute several rounds, but it remains one statistical cluster.
    # Macro-average its round metrics before task-cluster bootstrap to avoid
    # pseudo-replication and artificially narrow confidence intervals.
    task_spearman_values = [
        statistics.fmean(spearman_by_task[task_id]) for task_id in sorted(spearman_by_task)
    ]
    task_concordance_values = [
        statistics.fmean(concordance_by_task[task_id]) for task_id in sorted(concordance_by_task)
    ]
    task_rank = aggregate_metric(task_spearman_values) if task_spearman_values else None
    centered_spearman = (
        _spearman(centered_probes, centered_interventions) if len(centered_probes) >= 2 else None
    )
    pairwise_concordance = (
        statistics.fmean(task_concordance_values) if task_concordance_values else None
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
    if task_rank_ci is None:
        blockers.append("contribution_macro_spearman_ci_unavailable")
    elif task_rank_ci[0] < config.minimum_macro_spearman_ci_lower_bound:
        blockers.append(
            "contribution_macro_spearman_ci_lower_bound_below_threshold:"
            f"{task_rank_ci[0]:.6f}<{config.minimum_macro_spearman_ci_lower_bound:.6f}"
        )
    if concordance_ci is None:
        blockers.append("contribution_pairwise_concordance_ci_unavailable")
    elif concordance_ci[0] < config.minimum_pairwise_concordance_ci_lower_bound:
        blockers.append(
            "contribution_pairwise_concordance_ci_lower_bound_below_threshold:"
            f"{concordance_ci[0]:.6f}<"
            f"{config.minimum_pairwise_concordance_ci_lower_bound:.6f}"
        )

    blockers_tuple = tuple(sorted(set(blockers)))
    report_values = {
        "observation_count": len(observations),
        "unique_task_count": len(task_ids),
        "unique_round_count": len(round_ids),
        "unique_task_round_count": len(task_round_keys),
        "unique_state_count": len(state_keys),
        "paired_seed_count": len(paired_seeds),
        "aggregated_state_count": len(aggregated_states),
        "mean_within_state_intervention_variance": (
            statistics.fmean(item.intervention_variance for item in aggregated_states)
            if aggregated_states
            else None
        ),
        "eligible_task_round_count": len(eligible),
        "task_rank_correlation": task_rank,
        "task_rank_bootstrap_ci95": task_rank_ci,
        "centered_global_spearman": centered_spearman,
        "pairwise_concordance_rate": pairwise_concordance,
        "pairwise_concordance_bootstrap_ci95": concordance_ci,
        "pair_count": pair_count,
        "sign_agreement_rate": sign_agreement,
        "frozen_identity": frozen_identity,
        "status": "blocked" if blockers_tuple else "passed",
        "blockers": blockers_tuple,
        "schema_version": "contribution_validation_report.v6",
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
        sum(rng.choice(task_values) for _ in range(count)) / count for _ in range(samples)
    )
    lower_index = max(0, math.floor(0.025 * (samples - 1)))
    upper_index = min(samples - 1, math.ceil(0.975 * (samples - 1)))
    return (draws[lower_index], draws[upper_index])
