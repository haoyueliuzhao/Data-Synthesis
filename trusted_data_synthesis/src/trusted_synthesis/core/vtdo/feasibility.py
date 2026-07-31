from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.vtdo.estimation import (
    make_conditional_distribution,
    make_coverage_prior,
)
from trusted_synthesis.core.vtdo.schema import (
    VTDO_SCHEMA_VERSION,
    ConditionalTrajectoryDistribution,
    CoveragePrior,
    StateValidityEstimate,
    ValidityRegion,
)
from trusted_synthesis.hashing import canonical_hash


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StateValidityPartition(FrozenModel):
    """Disjoint feasibility regions induced before any energy optimization."""

    partition_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    estimates: tuple[StateValidityEstimate, ...] = Field(min_length=1)
    accepted_state_ids: tuple[str, ...] = ()
    quarantined_state_ids: tuple[str, ...] = ()
    rejected_state_ids: tuple[str, ...] = ()
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_partition(self) -> StateValidityPartition:
        groups = (
            set(self.accepted_state_ids),
            set(self.quarantined_state_ids),
            set(self.rejected_state_ids),
        )
        if any(
            groups[index] & groups[other] for index in range(3) for other in range(index + 1, 3)
        ):
            raise ValueError("state validity regions must be disjoint")
        if not set.union(*groups):
            raise ValueError("state validity partition cannot be empty")
        state_count = sum(len(group) for group in groups)
        estimates_by_state = {item.state_id: item for item in self.estimates}
        if len(estimates_by_state) != len(self.estimates) or len(self.estimates) != state_count:
            raise ValueError("validity estimates must cover every state exactly")
        if any(item.task_condition_id != self.task_condition_id for item in self.estimates):
            raise ValueError("validity partition estimates cross task conditions")
        expected_groups = {
            ValidityRegion.ACCEPTED: set(self.accepted_state_ids),
            ValidityRegion.QUARANTINED: set(self.quarantined_state_ids),
            ValidityRegion.REJECTED: set(self.rejected_state_ids),
        }
        for region, expected_states in expected_groups.items():
            observed_states = {item.state_id for item in self.estimates if item.region == region}
            if observed_states != expected_states:
                raise ValueError("validity partition region disagrees with its estimates")
        if self.partition_id != state_validity_partition_id(self):
            raise ValueError("state validity partition identity is invalid")
        return self


def make_state_validity_partition(
    estimates: Iterable[StateValidityEstimate],
) -> StateValidityPartition:
    items = tuple(sorted(estimates, key=lambda item: item.state_id))
    if not items:
        raise ValueError("state validity partition requires estimates")
    if len({item.state_id for item in items}) != len(items):
        raise ValueError("state validity partition contains duplicate states")
    conditions = {item.task_condition_id for item in items}
    if len(conditions) != 1:
        raise ValueError("state validity partition crosses task conditions")
    values = {
        "task_condition_id": next(iter(conditions)),
        "estimates": items,
        "accepted_state_ids": tuple(
            item.state_id for item in items if item.region == ValidityRegion.ACCEPTED
        ),
        "quarantined_state_ids": tuple(
            item.state_id for item in items if item.region == ValidityRegion.QUARANTINED
        ),
        "rejected_state_ids": tuple(
            item.state_id for item in items if item.region == ValidityRegion.REJECTED
        ),
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = StateValidityPartition.model_construct(partition_id="pending", **values)
    return StateValidityPartition(
        partition_id=state_validity_partition_id(provisional),
        **values,
    )


def condition_on_accepted_support(
    distribution: ConditionalTrajectoryDistribution,
    coverage_prior: CoveragePrior,
    partition: StateValidityPartition,
) -> tuple[ConditionalTrajectoryDistribution, CoveragePrior]:
    """Condition pi and r on Accepted states; never convert validity into reward."""

    if distribution.task_condition_id != partition.task_condition_id:
        raise ValueError("validity partition belongs to another task condition")
    if coverage_prior.task_condition_id != partition.task_condition_id:
        raise ValueError("coverage prior belongs to another task condition")
    full_support = set(distribution.probabilities)
    if set(coverage_prior.probabilities) != full_support:
        raise ValueError("empirical distribution and coverage prior differ in support")
    partition_support = (
        set(partition.accepted_state_ids)
        | set(partition.quarantined_state_ids)
        | set(partition.rejected_state_ids)
    )
    if partition_support != full_support:
        raise ValueError("validity partition must cover the empirical support exactly")
    accepted = set(partition.accepted_state_ids)
    if not accepted:
        raise ValueError("VTDO has no Accepted state to place on training support")
    conditioned_distribution = make_conditional_distribution(
        distribution.task_condition_id,
        {state_id: distribution.probabilities[state_id] for state_id in accepted},
        round_index=distribution.round_index,
        source_distribution_id=distribution.distribution_id,
        estimator_manifest_hash=canonical_hash(
            {
                "partition_id": partition.partition_id,
                "source_distribution_id": distribution.distribution_id,
            },
            prefix="accepted_support_conditioning:",
        ),
    )
    conditioned_coverage = make_coverage_prior(
        coverage_prior.task_condition_id,
        {state_id: coverage_prior.probabilities[state_id] for state_id in accepted},
        policy=f"conditioned_on_accepted:{partition.partition_id}",
    )
    return conditioned_distribution, conditioned_coverage


def state_validity_partition_id(value: StateValidityPartition) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"partition_id"}),
        prefix="state_validity_partition:",
    )
