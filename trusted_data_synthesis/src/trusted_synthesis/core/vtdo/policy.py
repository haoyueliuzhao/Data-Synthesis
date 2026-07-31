from __future__ import annotations

from collections.abc import Mapping

from .schema import (
    AnchoredDistributionUpdate,
    ConditionalTrajectoryDistribution,
    TaskConditionedTrajectoryPolicy,
    task_conditioned_policy_id,
)


def make_task_conditioned_policy(
    task_marginal: Mapping[str, float],
    conditionals: Mapping[str, ConditionalTrajectoryDistribution],
    *,
    round_index: int,
    source_policy_id: str | None = None,
) -> TaskConditionedTrajectoryPolicy:
    values = {
        "round_index": round_index,
        "task_marginal": dict(sorted(task_marginal.items())),
        "conditionals": dict(sorted(conditionals.items())),
        "source_policy_id": source_policy_id,
    }
    provisional = TaskConditionedTrajectoryPolicy.model_construct(
        policy_id="pending",
        **values,
    )
    return TaskConditionedTrajectoryPolicy(
        policy_id=task_conditioned_policy_id(provisional),
        **values,
    )


def apply_conditional_updates(
    prior: TaskConditionedTrajectoryPolicy,
    updates: Mapping[str, AnchoredDistributionUpdate],
) -> TaskConditionedTrajectoryPolicy:
    """Advance every pi(z|x) while preserving the frozen task marginal mu(x)."""

    if set(updates) != set(prior.conditionals):
        raise ValueError("VTDO policy updates must cover every fixed task condition")
    next_conditionals: dict[str, ConditionalTrajectoryDistribution] = {}
    for condition_id, current in prior.conditionals.items():
        update = updates[condition_id]
        if update.prior_distribution != current:
            raise ValueError(
                f"conditional update does not consume the frozen prior: {condition_id}"
            )
        next_conditionals[condition_id] = update.next_distribution
    return make_task_conditioned_policy(
        prior.task_marginal,
        next_conditionals,
        round_index=prior.round_index + 1,
        source_policy_id=prior.policy_id,
    )
