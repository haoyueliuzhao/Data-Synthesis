from __future__ import annotations

import math
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.vtdo.estimation import estimate_centered_contributions
from trusted_synthesis.core.vtdo.schema import (
    VTDO_SCHEMA_VERSION,
    ConditionalTrajectoryDistribution,
    ContributionEstimationManifest,
)
from trusted_synthesis.hashing import canonical_hash


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ContributionProbeObservation(FrozenModel):
    """One empirical intervention probe for C_t(x, z; theta_t)."""

    observation_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    beneficiary_model_state_id: str = Field(min_length=1)
    target_evaluation_distribution_id: str = Field(min_length=1)
    target_metric_id: str = Field(min_length=1)
    probe_protocol_hash: str = Field(min_length=1)
    baseline_metric_value: float
    intervention_metric_value: float
    raw_marginal_gain: float
    confidence: float = Field(ge=0, le=1)
    sample_count: int = Field(ge=1)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> ContributionProbeObservation:
        expected = self.intervention_metric_value - self.baseline_metric_value
        if not math.isclose(self.raw_marginal_gain, expected, abs_tol=1e-12):
            raise ValueError("contribution probe marginal gain is inconsistent")
        if self.observation_id != contribution_probe_observation_id(self):
            raise ValueError("contribution probe observation identity is invalid")
        return self


def make_contribution_probe_observation(
    *,
    task_condition_id: str,
    state_id: str,
    beneficiary_model_state_id: str,
    target_evaluation_distribution_id: str,
    target_metric_id: str,
    probe_protocol_hash: str,
    baseline_metric_value: float,
    intervention_metric_value: float,
    confidence: float,
    sample_count: int,
) -> ContributionProbeObservation:
    values = {
        "task_condition_id": task_condition_id,
        "state_id": state_id,
        "beneficiary_model_state_id": beneficiary_model_state_id,
        "target_evaluation_distribution_id": target_evaluation_distribution_id,
        "target_metric_id": target_metric_id,
        "probe_protocol_hash": probe_protocol_hash,
        "baseline_metric_value": baseline_metric_value,
        "intervention_metric_value": intervention_metric_value,
        "raw_marginal_gain": intervention_metric_value - baseline_metric_value,
        "confidence": confidence,
        "sample_count": sample_count,
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = ContributionProbeObservation.model_construct(
        observation_id="pending",
        **values,
    )
    return ContributionProbeObservation(
        observation_id=contribution_probe_observation_id(provisional),
        **values,
    )


def estimate_contributions_from_probes(
    distribution: ConditionalTrajectoryDistribution,
    observations: Iterable[ContributionProbeObservation],
    *,
    estimator_id: str = "paired_model_state_intervention.v1",
) -> ContributionEstimationManifest:
    """Center empirical model-state interventions under the current pi_t."""

    items = tuple(observations)
    if not items:
        raise ValueError("contribution estimation requires empirical probes")
    by_state = {item.state_id: item for item in items}
    if len(by_state) != len(items):
        raise ValueError("contribution probes must contain one aggregate per state")
    if set(by_state) != set(distribution.probabilities):
        raise ValueError("contribution probes must cover the current support exactly")
    conditions = {item.task_condition_id for item in items}
    models = {item.beneficiary_model_state_id for item in items}
    evaluations = {item.target_evaluation_distribution_id for item in items}
    metrics = {item.target_metric_id for item in items}
    protocols = {item.probe_protocol_hash for item in items}
    if conditions != {distribution.task_condition_id}:
        raise ValueError("contribution probes cross task conditions")
    if len(models) != 1 or len(evaluations) != 1 or len(metrics) != 1:
        raise ValueError("contribution probes must share model, evaluation, and metric")
    if len(protocols) != 1:
        raise ValueError("contribution probes must use one frozen protocol")
    return estimate_centered_contributions(
        distribution,
        {state_id: item.raw_marginal_gain for state_id, item in by_state.items()},
        confidences={state_id: item.confidence for state_id, item in by_state.items()},
        probe_sample_counts={state_id: item.sample_count for state_id, item in by_state.items()},
        beneficiary_model_state_id=next(iter(models)),
        target_evaluation_distribution_id=next(iter(evaluations)),
        target_metric_id=next(iter(metrics)),
        estimator_id=f"{estimator_id}:{next(iter(protocols))}",
    )


def contribution_probe_observation_id(value: ContributionProbeObservation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="trajectory_contribution_probe:",
    )
