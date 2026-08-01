from __future__ import annotations

import math
import statistics
from collections import defaultdict
from pathlib import Path

from trusted_synthesis.core.vtdo import ContributionProbeObservation
from trusted_synthesis.hashing import canonical_hash

from .schema import (
    BeneficiaryStateShiftConfig,
    BeneficiaryStateShiftReport,
    beneficiary_state_shift_report_id,
)
from .statistics import aggregate_metric


def run_beneficiary_state_shift_experiment(
    config: BeneficiaryStateShiftConfig,
) -> BeneficiaryStateShiftReport:
    """Compare matched Probe estimates at M0 and M1 using a paired confidence bound."""

    blockers: list[str] = []
    baseline = _load(config.baseline_observation_path, "baseline", blockers)
    updated = _load(config.updated_observation_path, "updated", blockers)
    if {item.round_index for item in baseline} != {config.baseline_round_index}:
        blockers.append("baseline_beneficiary_round_identity_mismatch")
    if {item.round_index for item in updated} != {config.updated_round_index}:
        blockers.append("updated_beneficiary_round_identity_mismatch")

    baseline_models = {item.probe_contract.beneficiary_model_state_id for item in baseline}
    updated_models = {item.probe_contract.beneficiary_model_state_id for item in updated}
    baseline_checkpoints = {item.probe_contract.beneficiary_checkpoint_hash for item in baseline}
    updated_checkpoints = {item.probe_contract.beneficiary_checkpoint_hash for item in updated}
    if len(baseline_models) != 1:
        blockers.append("baseline_beneficiary_model_state_not_frozen")
    if len(updated_models) != 1:
        blockers.append("updated_beneficiary_model_state_not_frozen")
    if len(baseline_checkpoints) != 1:
        blockers.append("baseline_beneficiary_checkpoint_not_frozen")
    if len(updated_checkpoints) != 1:
        blockers.append("updated_beneficiary_checkpoint_not_frozen")
    baseline_model = next(iter(baseline_models), None)
    updated_model = next(iter(updated_models), None)
    baseline_checkpoint = next(iter(baseline_checkpoints), None)
    updated_checkpoint = next(iter(updated_checkpoints), None)
    if baseline_model is not None and baseline_model == updated_model:
        blockers.append("beneficiary_model_state_did_not_change")
    if baseline_checkpoint is not None and baseline_checkpoint == updated_checkpoint:
        blockers.append("beneficiary_checkpoint_did_not_change")

    baseline_by_key = {_support_key(item): item for item in baseline}
    updated_by_key = {_support_key(item): item for item in updated}
    if len(baseline_by_key) != len(baseline):
        blockers.append("duplicate_baseline_task_state_seed_observation")
    if len(updated_by_key) != len(updated):
        blockers.append("duplicate_updated_task_state_seed_observation")
    if set(baseline_by_key) != set(updated_by_key):
        blockers.append("beneficiary_shift_atomic_support_mismatch")
    paired_keys = tuple(sorted(set(baseline_by_key) & set(updated_by_key)))

    frozen_identity: dict[str, str] = {}
    comparison_values = {
        "metric_contract_id": {
            item.probe_contract.metric_contract.contract_id
            for key in paired_keys
            for item in (baseline_by_key[key], updated_by_key[key])
        },
        "evaluation_distribution_id": {
            item.probe_contract.metric_contract.evaluation_distribution_id
            for key in paired_keys
            for item in (baseline_by_key[key], updated_by_key[key])
        },
        "target_metric_id": {
            item.probe_contract.metric_contract.target_metric_id
            for key in paired_keys
            for item in (baseline_by_key[key], updated_by_key[key])
        },
        "evaluation_snapshot_hash": {
            item.probe_contract.metric_contract.evaluation_snapshot_hash
            for key in paired_keys
            for item in (baseline_by_key[key], updated_by_key[key])
        },
        "probe_optimizer_contract_id": {
            item.probe_contract.optimizer.contract_id
            for key in paired_keys
            for item in (baseline_by_key[key], updated_by_key[key])
        },
    }
    for field, identities in comparison_values.items():
        if len(identities) != 1:
            blockers.append(f"beneficiary_shift_identity_mismatch:{field}")
        elif identities:
            frozen_identity[field] = next(iter(identities))
    if baseline_checkpoint is not None:
        frozen_identity["baseline_beneficiary_checkpoint_hash"] = baseline_checkpoint
    if updated_checkpoint is not None:
        frozen_identity["updated_beneficiary_checkpoint_hash"] = updated_checkpoint

    support_identity: dict[str, dict[str, str]] = {}
    for key in paired_keys:
        left = baseline_by_key[key]
        right = updated_by_key[key]
        if left.probe_contract.data_isolation != right.probe_contract.data_isolation:
            blockers.append(f"beneficiary_shift_support_identity_mismatch:{key}")
        support_identity["|".join((key[0], key[1], str(key[2])))] = {
            "data_isolation_contract_id": left.probe_contract.data_isolation.contract_id
        }
    if support_identity:
        frozen_identity["paired_support_identity_hash"] = canonical_hash(
            support_identity,
            prefix="beneficiary_shift_support_identity:",
        )

    baseline_states = _aggregate_states(baseline)
    updated_states = _aggregate_states(updated)
    if set(baseline_states) != set(updated_states):
        blockers.append("beneficiary_shift_aggregated_state_support_mismatch")
    state_keys = tuple(sorted(set(baseline_states) & set(updated_states)))
    baseline_groups = _group_states(baseline)
    updated_groups = _group_states(updated)
    seed_sets = {
        key: tuple(sorted(item.seed for item in values)) for key, values in baseline_groups.items()
    }
    updated_seed_sets = {
        key: tuple(sorted(item.seed for item in values)) for key, values in updated_groups.items()
    }
    for role, groups in (("baseline", baseline_groups), ("updated", updated_groups)):
        for state_key, state_observations in groups.items():
            protocol_ids = {item.probe_contract.protocol_id for item in state_observations}
            expected_seed_sets = {
                tuple(sorted(item.probe_contract.probe_seeds)) for item in state_observations
            }
            if len(protocol_ids) != 1 or len(expected_seed_sets) != 1:
                blockers.append(f"beneficiary_shift_{role}_probe_contract_not_frozen:{state_key}")
                continue
            if tuple(sorted(item.seed for item in state_observations)) != next(
                iter(expected_seed_sets)
            ):
                blockers.append(f"beneficiary_shift_{role}_protocol_seed_mismatch:{state_key}")
    if seed_sets != updated_seed_sets:
        blockers.append("beneficiary_shift_seed_support_mismatch")
    canonical_seed_sets = set(seed_sets.values())
    if len(canonical_seed_sets) != 1:
        blockers.append("beneficiary_shift_seed_set_not_frozen")
    probe_seeds = next(iter(canonical_seed_sets), ())
    if len(probe_seeds) < config.minimum_seeds_per_state:
        blockers.append(
            f"beneficiary_shift_seeds_below_minimum:{len(probe_seeds)}<"
            f"{config.minimum_seeds_per_state}"
        )

    by_task: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
    for task_id, state_id in state_keys:
        by_task[task_id].append((task_id, state_id))
    eligible_tasks = {
        task_id: tuple(values)
        for task_id, values in by_task.items()
        if len(values) >= config.minimum_states_per_task
    }
    if len(eligible_tasks) < config.minimum_unique_task_count:
        blockers.append(
            f"beneficiary_shift_tasks_below_minimum:{len(eligible_tasks)}<"
            f"{config.minimum_unique_task_count}"
        )

    task_mean_absolute_shifts = [
        statistics.fmean(abs(updated_states[key] - baseline_states[key]) for key in values)
        for values in eligible_tasks.values()
    ]
    rank_correlations = [
        _spearman(
            [baseline_states[key] for key in values],
            [updated_states[key] for key in values],
        )
        for values in eligible_tasks.values()
    ]
    direction_changes = sum(
        _sign(baseline_states[key]) != _sign(updated_states[key])
        for values in eligible_tasks.values()
        for key in values
    )
    evaluated_state_count = sum(len(values) for values in eligible_tasks.values())
    # The confidence interval is clustered at the task level; treating every state as an
    # independent sample would overstate precision when states share one task context.
    mean_shift = aggregate_metric(task_mean_absolute_shifts) if task_mean_absolute_shifts else None
    lower_bound = (
        max(0.0, mean_shift.mean - mean_shift.ci95_half_width) if mean_shift is not None else None
    )
    rank_metric = aggregate_metric(rank_correlations) if rank_correlations else None
    dependence_observed = (
        lower_bound > config.dependence_tolerance if lower_bound is not None else None
    )
    blockers_tuple = tuple(sorted(set(blockers)))
    report_values = {
        "baseline_model_state_id": baseline_model,
        "updated_model_state_id": updated_model,
        "baseline_round_index": config.baseline_round_index,
        "updated_round_index": config.updated_round_index,
        "atomic_pair_count": len(paired_keys),
        "unique_task_count": len(eligible_tasks),
        "aggregated_state_count": evaluated_state_count,
        "probe_seed_count": len(probe_seeds),
        "mean_absolute_contribution_shift": mean_shift,
        "mean_absolute_shift_ci95_lower_bound": lower_bound,
        "task_rank_correlation": rank_metric,
        "contribution_direction_change_rate": (
            direction_changes / evaluated_state_count if evaluated_state_count else None
        ),
        "model_state_dependence_observed": dependence_observed,
        "dependence_tolerance": config.dependence_tolerance,
        "frozen_comparison_identity": frozen_identity,
        "status": "blocked" if blockers_tuple else "passed",
        "blockers": blockers_tuple,
        "schema_version": "beneficiary_state_shift_report.v4",
    }
    provisional = BeneficiaryStateShiftReport.model_construct(report_id="pending", **report_values)
    return BeneficiaryStateShiftReport(
        report_id=beneficiary_state_shift_report_id(provisional), **report_values
    )


def _load(
    path: Path | None,
    role: str,
    blockers: list[str],
) -> tuple[ContributionProbeObservation, ...]:
    if path is None:
        blockers.append(f"beneficiary_shift_{role}_path_not_configured")
        return ()
    if not path.is_file():
        blockers.append(f"beneficiary_shift_{role}_path_missing:{path}")
        return ()
    return tuple(
        ContributionProbeObservation.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _support_key(item: ContributionProbeObservation) -> tuple[str, str, int]:
    return item.task_condition_id, item.state_id, item.seed


def _group_states(
    values: tuple[ContributionProbeObservation, ...],
) -> dict[tuple[str, str], list[ContributionProbeObservation]]:
    grouped: defaultdict[tuple[str, str], list[ContributionProbeObservation]] = defaultdict(list)
    for item in values:
        grouped[(item.task_condition_id, item.state_id)].append(item)
    return dict(grouped)


def _aggregate_states(
    values: tuple[ContributionProbeObservation, ...],
) -> dict[tuple[str, str], float]:
    return {
        key: statistics.fmean(item.performance_gain for item in items)
        for key, items in _group_states(values).items()
    }


def _spearman(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("Spearman correlation requires paired nontrivial observations")
    left_rank = _average_ranks(left)
    right_rank = _average_ranks(right)
    left_mean = statistics.fmean(left_rank)
    right_mean = statistics.fmean(right_rank)
    numerator = sum(
        (a - left_mean) * (b - right_mean) for a, b in zip(left_rank, right_rank, strict=True)
    )
    denominator = math.sqrt(
        sum((value - left_mean) ** 2 for value in left_rank)
        * sum((value - right_mean) ** 2 for value in right_rank)
    )
    return numerator / denominator if denominator else 0.0


def _average_ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        stop = index + 1
        while stop < len(ordered) and ordered[stop][1] == ordered[index][1]:
            stop += 1
        rank = (index + stop - 1) / 2.0 + 1.0
        for original_index, _ in ordered[index:stop]:
            ranks[original_index] = rank
        index = stop
    return ranks


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0
