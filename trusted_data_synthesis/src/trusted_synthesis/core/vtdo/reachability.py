from __future__ import annotations

import math
from collections.abc import Mapping

from trusted_synthesis.core.vtdo.schema import (
    StateReachabilityEstimate,
    StateReachabilityManifest,
    state_reachability_estimate_id,
    state_reachability_manifest_id,
)


def make_state_reachability_estimate(
    *,
    task_condition_id: str,
    state_id: str,
    explorer_provider_id: str,
    explorer_provider_version: str,
    estimation_mode: str,
    protocol_status: str,
    attempted_trajectory_count: int,
    on_target_trajectory_count: int,
    generation_constraints_hash: str | None = None,
    interval_coverage_probability: float = 0.95,
) -> StateReachabilityEstimate:
    if on_target_trajectory_count > attempted_trajectory_count:
        raise ValueError("reachable-state hits cannot exceed attempts")
    alpha = on_target_trajectory_count + 1.0
    beta = attempted_trajectory_count - on_target_trajectory_count + 1.0
    lower, upper = _wilson_interval(
        on_target_trajectory_count,
        attempted_trajectory_count,
        interval_coverage_probability,
    )
    if protocol_status == "protocol_blocked":
        status = "protocol_blocked"
    elif attempted_trajectory_count == 0:
        status = "unmeasured"
    elif on_target_trajectory_count:
        status = "observed_reachable"
    else:
        status = "not_observed"
    values = {
        "task_condition_id": task_condition_id,
        "state_id": state_id,
        "explorer_provider_id": explorer_provider_id,
        "explorer_provider_version": explorer_provider_version,
        "estimation_mode": estimation_mode,
        "protocol_status": protocol_status,
        "generation_constraints_hash": generation_constraints_hash,
        "attempted_trajectory_count": attempted_trajectory_count,
        "on_target_trajectory_count": on_target_trajectory_count,
        "posterior_alpha": alpha,
        "posterior_beta": beta,
        "posterior_mean": alpha / (alpha + beta),
        "interval_coverage_probability": interval_coverage_probability,
        "confidence_lower": lower,
        "confidence_upper": upper,
        "status": status,
        "estimator_id": "beta_binomial_with_wilson_interval",
        "estimator_version": "1.0.0",
        "schema_version": "trajectory_reachability.v2",
    }
    provisional = StateReachabilityEstimate.model_construct(
        estimate_id="pending",
        **values,
    )
    return StateReachabilityEstimate(
        estimate_id=state_reachability_estimate_id(provisional),
        **values,
    )


def make_unconditioned_reachability_manifest(
    *,
    task_condition_id: str,
    explorer_provider_id: str,
    explorer_provider_version: str,
    state_counts: Mapping[str, int],
    attempted_trajectory_count: int,
    source_batch_ids: tuple[str, ...],
) -> StateReachabilityManifest:
    if attempted_trajectory_count < 1:
        raise ValueError("unconditioned reachability requires at least one attempt")
    if not state_counts:
        raise ValueError("reachability support cannot be empty")
    if any(count < 0 or count > attempted_trajectory_count for count in state_counts.values()):
        raise ValueError("unconditioned state counts are outside the attempt budget")
    if sum(state_counts.values()) > attempted_trajectory_count:
        raise ValueError("unconditioned state counts exceed the attempt budget")
    estimates = tuple(
        make_state_reachability_estimate(
            task_condition_id=task_condition_id,
            state_id=state_id,
            explorer_provider_id=explorer_provider_id,
            explorer_provider_version=explorer_provider_version,
            estimation_mode="unconditioned_pushforward",
            protocol_status="unconditioned",
            attempted_trajectory_count=attempted_trajectory_count,
            on_target_trajectory_count=count,
        )
        for state_id, count in sorted(state_counts.items())
    )
    values = {
        "task_condition_id": task_condition_id,
        "explorer_provider_id": explorer_provider_id,
        "explorer_provider_version": explorer_provider_version,
        "estimates": estimates,
        "source_batch_ids": tuple(sorted(source_batch_ids)),
        "schema_version": "trajectory_reachability_manifest.v2",
    }
    provisional = StateReachabilityManifest.model_construct(
        manifest_id="pending",
        **values,
    )
    return StateReachabilityManifest(
        manifest_id=state_reachability_manifest_id(provisional),
        **values,
    )


def _wilson_interval(
    successes: int,
    attempts: int,
    interval_coverage_probability: float,
) -> tuple[float, float]:
    if attempts == 0:
        return 0.0, 1.0
    if not math.isclose(interval_coverage_probability, 0.95, abs_tol=1e-12):
        raise ValueError("reachability currently supports interval_coverage_probability=0.95 only")
    z = 1.959963984540054
    probability = successes / attempts
    denominator = 1.0 + z * z / attempts
    center = (probability + z * z / (2.0 * attempts)) / denominator
    margin = (
        z
        * math.sqrt(
            probability * (1.0 - probability) / attempts + z * z / (4.0 * attempts * attempts)
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)
