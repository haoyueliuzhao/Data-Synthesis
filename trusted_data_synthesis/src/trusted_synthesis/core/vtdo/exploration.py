from __future__ import annotations

import math

from .schema import (
    ConditionalTrajectoryDistribution,
    CoveragePrior,
    ExplorationDistribution,
    exploration_distribution_id,
)


def make_exploration_distribution(
    training_distribution: ConditionalTrajectoryDistribution,
    coverage_prior: CoveragePrior,
    *,
    exploration_rate: float,
) -> ExplorationDistribution:
    """Construct q_t = (1-xi) pi_t + xi r with auditable importance weights."""

    if not 0 < exploration_rate < 1:
        raise ValueError("exploration rate must be strictly between zero and one")
    if training_distribution.task_condition_id != coverage_prior.task_condition_id:
        raise ValueError("exploration inputs belong to different task conditions")
    training_support = set(training_distribution.probabilities)
    coverage_support = set(coverage_prior.probabilities)
    if not training_support <= coverage_support:
        raise ValueError("training support must be contained in the coverage catalog")
    probabilities = {
        state_id: (
            (1.0 - exploration_rate) * training_distribution.probabilities.get(state_id, 0.0)
            + exploration_rate * coverage_prior.probabilities[state_id]
        )
        for state_id in sorted(coverage_support)
    }
    importance = {
        state_id: training_distribution.probabilities.get(state_id, 0.0) / probabilities[state_id]
        for state_id in sorted(probabilities)
    }
    values = {
        "task_condition_id": training_distribution.task_condition_id,
        "training_distribution": training_distribution,
        "coverage_prior": coverage_prior,
        "exploration_rate": exploration_rate,
        "probabilities": probabilities,
        "importance_weights": importance,
    }
    provisional = ExplorationDistribution.model_construct(
        exploration_id="pending",
        **values,
    )
    return ExplorationDistribution(
        exploration_id=exploration_distribution_id(provisional),
        **values,
    )


def allocate_exploration_budget(
    distribution: ExplorationDistribution,
    total_budget: int,
) -> dict[str, int]:
    """Deterministic largest-remainder allocation over exploration states."""

    if total_budget < 1:
        raise ValueError("exploration budget must be positive")
    exact = {
        state_id: probability * total_budget
        for state_id, probability in distribution.probabilities.items()
    }
    counts = {state_id: math.floor(value) for state_id, value in exact.items()}
    remaining = total_budget - sum(counts.values())
    order = sorted(
        exact,
        key=lambda state_id: (-(exact[state_id] - counts[state_id]), state_id),
    )
    for state_id in order[:remaining]:
        counts[state_id] += 1
    return dict(sorted(counts.items()))
