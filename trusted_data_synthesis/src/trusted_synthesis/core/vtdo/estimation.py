from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping

from trusted_synthesis.core.trajectory.state import TrajectoryStateAssignment
from trusted_synthesis.core.trajectory.validity import TrajectoryValidityReport
from trusted_synthesis.hashing import canonical_hash

from .schema import (
    ConditionalTrajectoryDistribution,
    ContributionEstimate,
    ContributionEstimationManifest,
    CoveragePrior,
    EmpiricalDistributionEstimate,
    StateValidityEstimate,
    ValidityThresholds,
    conditional_distribution_id,
    contribution_estimate_id,
    contribution_manifest_id,
    coverage_prior_id,
    empirical_distribution_estimate_id,
    state_validity_estimate_id,
    validity_region,
)


def make_coverage_prior(
    task_condition_id: str,
    probabilities: Mapping[str, float],
    *,
    policy: str,
) -> CoveragePrior:
    values = {
        "task_condition_id": task_condition_id,
        "probabilities": _normalized_positive(probabilities),
        "policy": policy,
    }
    provisional = CoveragePrior.model_construct(prior_id="pending", **values)
    return CoveragePrior(prior_id=coverage_prior_id(provisional), **values)


def make_uniform_coverage_prior(
    task_condition_id: str,
    state_ids: Iterable[str],
) -> CoveragePrior:
    states = tuple(sorted(set(state_ids)))
    if not states:
        raise ValueError("uniform coverage prior requires at least one state")
    return make_coverage_prior(
        task_condition_id,
        {state_id: 1.0 / len(states) for state_id in states},
        policy="uniform_full_support",
    )


def make_conditional_distribution(
    task_condition_id: str,
    probabilities: Mapping[str, float],
    *,
    round_index: int,
    source_distribution_id: str | None = None,
    estimator_manifest_hash: str | None = None,
) -> ConditionalTrajectoryDistribution:
    values = {
        "task_condition_id": task_condition_id,
        "round_index": round_index,
        "probabilities": _normalized_positive(probabilities),
        "source_distribution_id": source_distribution_id,
        "estimator_manifest_hash": estimator_manifest_hash,
    }
    provisional = ConditionalTrajectoryDistribution.model_construct(
        distribution_id="pending",
        **values,
    )
    return ConditionalTrajectoryDistribution(
        distribution_id=conditional_distribution_id(provisional),
        **values,
    )


def estimate_pushforward_distribution(
    assignments: Iterable[TrajectoryStateAssignment],
    coverage_prior: CoveragePrior,
    *,
    round_index: int,
    prior_strength: float,
) -> EmpiricalDistributionEstimate:
    """Estimate (phi_x)#P with a frozen full-support coverage prior."""

    if prior_strength < 0:
        raise ValueError("push-forward prior strength cannot be negative")
    items = tuple(assignments)
    if not items:
        raise ValueError("push-forward estimation requires observed trajectories")
    if any(item.task_condition_id != coverage_prior.task_condition_id for item in items):
        raise ValueError("push-forward assignments cross task conditions")
    support = set(coverage_prior.probabilities)
    observed = Counter(item.state.state_id for item in items)
    unknown = set(observed) - support
    if unknown:
        raise ValueError(
            f"observed trajectory states are absent from coverage prior: {sorted(unknown)}"
        )
    counts = {state_id: observed.get(state_id, 0) for state_id in sorted(support)}
    weights = {state_id: float(counts[state_id]) for state_id in sorted(support)}
    total_weight = float(len(items))
    denominator = total_weight + prior_strength
    probabilities = {
        state_id: (weights[state_id] + prior_strength * coverage_prior.probabilities[state_id])
        / denominator
        for state_id in sorted(support)
    }
    observation_ids = tuple(sorted(item.assignment_id for item in items))
    manifest_hash = canonical_hash(
        {
            "source_observation_ids": observation_ids,
            "coverage_prior_id": coverage_prior.prior_id,
            "prior_strength": prior_strength,
            "estimator_kind": "unweighted_pushforward",
        },
        prefix="trajectory_pushforward_manifest:",
    )
    distribution = make_conditional_distribution(
        coverage_prior.task_condition_id,
        probabilities,
        round_index=round_index,
        estimator_manifest_hash=manifest_hash,
    )
    values = {
        "task_condition_id": coverage_prior.task_condition_id,
        "state_exposure_counts": counts,
        "state_exposure_weights": weights,
        "total_exposure_count": len(items),
        "total_exposure_weight": total_weight,
        "sum_squared_importance_weights": total_weight,
        "effective_sample_size": total_weight,
        "source_observation_ids": observation_ids,
        "sampling_distribution_id": None,
        "estimator_kind": "unweighted_pushforward",
        "coverage_prior": coverage_prior,
        "prior_strength": prior_strength,
        "distribution": distribution,
    }
    provisional = EmpiricalDistributionEstimate.model_construct(
        estimate_id="pending",
        **values,
    )
    return EmpiricalDistributionEstimate(
        estimate_id=empirical_distribution_estimate_id(provisional),
        **values,
    )


def estimate_state_validity(
    assignments: Iterable[TrajectoryStateAssignment],
    reports: Iterable[TrajectoryValidityReport],
    *,
    thresholds: ValidityThresholds,
    prior_success: float = 0.0,
    prior_failure: float = 0.0,
    confidence_z: float = 1.959963984540054,
) -> StateValidityEstimate:
    """Estimate v(x, state; Omega_x) from independently verified members."""

    if prior_success < 0 or prior_failure < 0:
        raise ValueError("validity prior masses cannot be negative")
    if confidence_z <= 0:
        raise ValueError("validity confidence z-score must be positive")
    members = tuple(assignments)
    observations = tuple(reports)
    if not members or not observations:
        raise ValueError("state validity estimation requires assignments and reports")
    state_ids = {item.state.state_id for item in members}
    conditions = {item.task_condition_id for item in members}
    contexts = {item.state.verification_context_id for item in members}
    if len(state_ids) != 1 or len(conditions) != 1 or len(contexts) != 1:
        raise ValueError("state validity estimation must target one quotient state")
    assignment_by_trajectory = {item.trajectory_id: item for item in members}
    if len(assignment_by_trajectory) != len(members):
        raise ValueError("state validity assignments contain duplicate trajectories")
    report_by_trajectory = {item.trajectory_id: item for item in observations}
    if len(report_by_trajectory) != len(observations):
        raise ValueError("state validity reports contain duplicate trajectories")
    if set(report_by_trajectory) != set(assignment_by_trajectory):
        raise ValueError("validity reports must cover state assignments exactly")
    if any(
        report_by_trajectory[trajectory_id].trajectory_hash != assignment.trajectory_hash
        or report_by_trajectory[trajectory_id].attributes != assignment.attributes
        for trajectory_id, assignment in assignment_by_trajectory.items()
    ):
        raise ValueError("validity reports disagree with quotient assignments")
    context_id = next(iter(contexts))
    if any(item.context_id != context_id for item in observations):
        raise ValueError("validity reports were produced under another Omega context")
    valid_count = sum(item.valid for item in observations)
    denominator = len(observations) + prior_success + prior_failure
    estimate = (valid_count + prior_success) / denominator
    lower, upper = _wilson_interval(
        valid_count + prior_success,
        denominator,
        confidence_z,
    )
    component_values: dict[str, list[float]] = defaultdict(list)
    for report in observations:
        for component, value in report.component_validity.items():
            component_values[component].append(value)
    component_means = {
        component: sum(values) / len(values)
        for component, values in sorted(component_values.items())
    }
    values = {
        "task_condition_id": next(iter(conditions)),
        "state_id": next(iter(state_ids)),
        "attempted_trajectory_count": len(observations),
        "valid_trajectory_count": valid_count,
        "estimated_validity": estimate,
        "confidence_lower": lower,
        "confidence_upper": upper,
        "mean_component_validity": component_means,
        "thresholds": thresholds,
        "classification_statistic": "posterior_mean",
        "region": validity_region(estimate, thresholds),
        "estimator_id": "beta_binomial_state_validity",
        "estimator_version": "1.0.0",
    }
    provisional = StateValidityEstimate.model_construct(estimate_id="pending", **values)
    return StateValidityEstimate(
        estimate_id=state_validity_estimate_id(provisional),
        **values,
    )


def estimate_centered_contributions(
    distribution: ConditionalTrajectoryDistribution,
    raw_marginal_gains: Mapping[str, float],
    *,
    confidences: Mapping[str, float],
    probe_sample_counts: Mapping[str, int],
    beneficiary_model_state_id: str,
    target_evaluation_distribution_id: str,
    target_metric_id: str,
    estimator_id: str,
) -> ContributionEstimationManifest:
    """Center model-state-dependent marginal probes on the probability simplex."""

    support = set(distribution.probabilities)
    if set(raw_marginal_gains) != support:
        raise ValueError("raw contribution probes must cover the current support")
    if set(confidences) != support or set(probe_sample_counts) != support:
        raise ValueError("contribution confidence and sample counts must cover support")
    if any(not 0 <= value <= 1 for value in confidences.values()):
        raise ValueError("contribution confidence must be in [0, 1]")
    if any(value < 1 for value in probe_sample_counts.values()):
        raise ValueError("each contribution probe requires at least one sample")
    adjusted = {
        state_id: raw_marginal_gains[state_id] * confidences[state_id] for state_id in support
    }
    baseline = sum(
        distribution.probabilities[state_id] * adjusted[state_id] for state_id in support
    )
    estimates = []
    for state_id in sorted(support):
        values = {
            "state_id": state_id,
            "raw_marginal_gain": raw_marginal_gains[state_id],
            "confidence": confidences[state_id],
            "confidence_adjusted_gain": adjusted[state_id],
            "centered_contribution": adjusted[state_id] - baseline,
            "current_probability": distribution.probabilities[state_id],
            "probe_sample_count": probe_sample_counts[state_id],
        }
        provisional = ContributionEstimate.model_construct(estimate_id="pending", **values)
        estimates.append(
            ContributionEstimate(
                estimate_id=contribution_estimate_id(provisional),
                **values,
            )
        )
    weighted_mean = sum(item.current_probability * item.centered_contribution for item in estimates)
    manifest_values = {
        "task_condition_id": distribution.task_condition_id,
        "distribution_id": distribution.distribution_id,
        "beneficiary_model_state_id": beneficiary_model_state_id,
        "target_evaluation_distribution_id": target_evaluation_distribution_id,
        "target_metric_id": target_metric_id,
        "estimator_id": estimator_id,
        "estimates": tuple(estimates),
        "weighted_centered_mean": weighted_mean,
    }
    provisional_manifest = ContributionEstimationManifest.model_construct(
        manifest_id="pending",
        **manifest_values,
    )
    return ContributionEstimationManifest(
        manifest_id=contribution_manifest_id(provisional_manifest),
        **manifest_values,
    )


def _normalized_positive(values: Mapping[str, float]) -> dict[str, float]:
    if not values:
        raise ValueError("probability support cannot be empty")
    if any(not key for key in values):
        raise ValueError("probability support contains an empty state ID")
    if any(value <= 0 or not math.isfinite(value) for value in values.values()):
        raise ValueError("probability weights must be finite and strictly positive")
    total = sum(values.values())
    return {key: values[key] / total for key in sorted(values)}


def _wilson_interval(successes: float, total: float, z: float) -> tuple[float, float]:
    if total <= 0:
        raise ValueError("Wilson interval requires positive effective sample size")
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)
