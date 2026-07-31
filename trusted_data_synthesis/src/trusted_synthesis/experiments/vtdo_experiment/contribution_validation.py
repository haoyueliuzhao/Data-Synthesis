from __future__ import annotations

import math

from .schema import (
    ContributionValidationConfig,
    ContributionValidationObservation,
    ContributionValidationReport,
    contribution_validation_report_id,
)


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

    spearman = None
    sign_agreement = None
    if len(observations) >= 2:
        estimates = [item.estimated_contribution for item in observations]
        outcomes = [item.observed_delta_j for item in observations]
        spearman = _spearman(estimates, outcomes)
        sign_agreement = sum(
            _sign(left) == _sign(right) for left, right in zip(estimates, outcomes, strict=True)
        ) / len(observations)
        if abs(spearman) < config.minimum_absolute_spearman:
            blockers.append(
                "contribution_spearman_below_threshold:"
                f"{spearman:.6f}<{config.minimum_absolute_spearman:.6f}"
            )

    values = {
        "observation_count": len(observations),
        "unique_task_count": len(task_ids),
        "unique_state_count": len(state_keys),
        "spearman_correlation": spearman,
        "sign_agreement_rate": sign_agreement,
        "status": "blocked" if blockers else "passed",
        "blockers": tuple(sorted(set(blockers))),
        "schema_version": "contribution_validation_report.v1",
    }
    provisional = ContributionValidationReport.model_construct(report_id="pending", **values)
    return ContributionValidationReport(
        report_id=contribution_validation_report_id(provisional),
        **values,
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
