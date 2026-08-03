from __future__ import annotations

import math
from collections.abc import Iterable

from .estimation import make_conditional_distribution
from .schema import (
    AnchoredDistributionUpdate,
    AnchoredEnergyConfig,
    ConditionalTrajectoryDistribution,
    ContributionEstimationManifest,
    ContributionProductionAuthorization,
    CoveragePrior,
    StateEnergyPotential,
    StateReachabilityEstimate,
    StateReachabilityManifest,
    StateValidityEstimate,
    ValidityRegion,
    VTDORoleContract,
    anchored_distribution_update_id,
    validate_contribution_production_authorization,
)


def update_valid_trajectory_distribution(
    prior: ConditionalTrajectoryDistribution,
    coverage_prior: CoveragePrior,
    validity_estimates: Iterable[StateValidityEstimate],
    contribution_manifest: ContributionEstimationManifest,
    contribution_production_authorization: ContributionProductionAuthorization | None,
    config: AnchoredEnergyConfig,
    role_contract: VTDORoleContract,
    reachability_manifest: StateReachabilityManifest | None = None,
) -> AnchoredDistributionUpdate:
    """Apply the frozen anchored energy update on the Accepted quotient states.

    pi_next(z|x) is proportional to
      pi_t(z|x)^rho r(z|x)^(1-rho) Phi_t(x,z)^eta.

    Validity is a feasibility gate. It is intentionally absent from Phi and cannot be
    compensated by contribution or novelty.
    """

    if prior.task_condition_id != coverage_prior.task_condition_id:
        raise ValueError("VTDO prior and coverage anchor belong to different task conditions")
    support = set(prior.probabilities)
    if set(coverage_prior.probabilities) != support:
        raise ValueError("VTDO coverage anchor must have the exact current support")
    estimates = tuple(sorted(validity_estimates, key=lambda item: item.state_id))
    if {item.state_id for item in estimates} != support:
        raise ValueError("state validity estimates must cover the current support exactly")
    if any(item.task_condition_id != prior.task_condition_id for item in estimates):
        raise ValueError("state validity estimate crosses task conditions")
    nonaccepted = tuple(
        item.state_id for item in estimates if item.region != ValidityRegion.ACCEPTED
    )
    if nonaccepted:
        raise ValueError(
            f"VTDO positive training support contains non-Accepted states: {nonaccepted}"
        )
    if contribution_manifest.task_condition_id != prior.task_condition_id:
        raise ValueError("contribution manifest belongs to another task condition")
    if contribution_manifest.distribution_id != prior.distribution_id:
        raise ValueError("contribution manifest was estimated for another model distribution")
    if contribution_manifest.beneficiary_model_state_id != role_contract.beneficiary_model_state_id:
        raise ValueError("contribution manifest disagrees with the VTDO role contract")
    if contribution_manifest.usage_scope not in {
        "production_distribution_update",
        "synthetic_operator_control",
    }:
        raise ValueError(
            "finite Intervention Contribution is validation-only and cannot update pi_t"
        )
    validate_contribution_production_authorization(
        contribution_manifest,
        contribution_production_authorization,
    )
    contributions = {item.state_id: item for item in contribution_manifest.estimates}
    if set(contributions) != support:
        raise ValueError("contribution manifest must cover the current support exactly")
    reachability = {}
    if reachability_manifest is not None:
        if reachability_manifest.task_condition_id != prior.task_condition_id:
            raise ValueError("reachability manifest belongs to another task condition")
        if reachability_manifest.explorer_provider_id != role_contract.explorer_provider_id:
            raise ValueError("reachability manifest uses another Explorer provider")
        reachability = {item.state_id: item for item in reachability_manifest.estimates}
        if set(reachability) != support:
            raise ValueError("reachability manifest must cover current support exactly")
    if config.reachability_weight > 0 and not reachability:
        raise ValueError("reachability-aware energy requires a complete manifest")
    if config.reachability_weight > 0 and any(
        item.attempted_trajectory_count == 0 for item in reachability.values()
    ):
        raise ValueError("reachability-aware energy cannot use unmeasured states")

    if any(
        not math.isclose(
            contributions[state_id].current_probability,
            prior.probabilities[state_id],
            abs_tol=1e-12,
        )
        for state_id in support
    ):
        raise ValueError("contribution manifest does not represent the current pi_t")

    rho = config.history_exponent
    eta = config.energy_exponent
    potentials: list[StateEnergyPotential] = []
    log_weights: dict[str, float] = {}
    for state_id in sorted(support):
        current_probability = prior.probabilities[state_id]
        coverage_probability = coverage_prior.probabilities[state_id]
        centered_contribution = contributions[state_id].centered_contribution
        contribution = contributions[state_id].conservative_centered_contribution
        novelty = max(
            math.log(coverage_probability / current_probability),
            0.0,
        )
        normalized_contribution = _normalize_contribution(
            contribution,
            epsilon=config.epsilon,
            temperature=config.contribution_temperature,
        )
        normalized_novelty = _normalize_novelty(
            novelty,
            epsilon=config.epsilon,
            temperature=config.novelty_temperature,
        )
        reachability_estimate = reachability.get(state_id)
        reachability_probability = (
            _reachability_signal(reachability_estimate, config)
            if reachability_estimate is not None
            else 1.0
        )
        normalized_reachability = max(
            config.reachability_floor,
            reachability_probability,
        )
        potential = (
            normalized_contribution**config.contribution_weight
            * normalized_novelty**config.novelty_weight
            * normalized_reachability**config.reachability_weight
        )
        energy = -math.log(potential)
        potentials.append(
            StateEnergyPotential(
                state_id=state_id,
                current_probability=current_probability,
                coverage_probability=coverage_probability,
                centered_contribution=centered_contribution,
                conservative_centered_contribution=contribution,
                contribution_signal_kind="conservative_centered_contribution",
                normalized_contribution=normalized_contribution,
                coverage_relative_novelty=novelty,
                normalized_novelty=normalized_novelty,
                reachability_estimate_id=(
                    reachability_estimate.estimate_id if reachability_estimate is not None else None
                ),
                reachability_probability=reachability_probability,
                normalized_reachability=normalized_reachability,
                potential=potential,
                energy=energy,
            )
        )
        log_weights[state_id] = (
            rho * math.log(current_probability)
            + (1.0 - rho) * math.log(coverage_probability)
            + eta * math.log(potential)
        )
    maximum = max(log_weights.values())
    unnormalized = {state_id: math.exp(value - maximum) for state_id, value in log_weights.items()}
    total = sum(unnormalized.values())
    next_probabilities = {state_id: unnormalized[state_id] / total for state_id in sorted(support)}
    next_distribution = make_conditional_distribution(
        prior.task_condition_id,
        next_probabilities,
        round_index=prior.round_index + 1,
        source_distribution_id=prior.distribution_id,
        estimator_manifest_hash=contribution_manifest.manifest_id,
    )
    values = {
        "prior_distribution": prior,
        "coverage_prior": coverage_prior,
        "next_distribution": next_distribution,
        "validity_estimates": estimates,
        "contribution_manifest": contribution_manifest,
        "contribution_production_authorization": contribution_production_authorization,
        "role_contract": role_contract,
        "energy_config": config,
        "reachability_manifest": reachability_manifest,
        "state_potentials": tuple(potentials),
        "history_exponent": rho,
        "energy_exponent": eta,
        "kl_to_history": _kl(next_probabilities, prior.probabilities),
        "kl_to_coverage": _kl(next_probabilities, coverage_prior.probabilities),
        "total_variation_from_history": _total_variation(
            next_probabilities,
            prior.probabilities,
        ),
        "prior_entropy": _entropy(prior.probabilities),
        "next_entropy": _entropy(next_probabilities),
    }
    provisional = AnchoredDistributionUpdate.model_construct(
        update_id="pending",
        **values,
    )
    return AnchoredDistributionUpdate(
        update_id=anchored_distribution_update_id(provisional),
        **values,
    )


def _normalize_contribution(
    value: float,
    *,
    epsilon: float,
    temperature: float,
) -> float:
    scaled = value / temperature
    if scaled >= 0:
        sigmoid = 1.0 / (1.0 + math.exp(-scaled))
    else:
        exponential = math.exp(scaled)
        sigmoid = exponential / (1.0 + exponential)
    return epsilon + (1.0 - 2.0 * epsilon) * sigmoid


def _normalize_novelty(
    value: float,
    *,
    epsilon: float,
    temperature: float,
) -> float:
    return epsilon + (1.0 - 2.0 * epsilon) * (1.0 - math.exp(-value / temperature))


def _reachability_signal(
    estimate: StateReachabilityEstimate,
    config: AnchoredEnergyConfig,
) -> float:
    if config.reachability_signal == "posterior_mean":
        return estimate.posterior_mean
    return estimate.confidence_lower


def _kl(left: dict[str, float], right: dict[str, float]) -> float:
    return sum(left[key] * math.log(left[key] / right[key]) for key in left)


def _total_variation(left: dict[str, float], right: dict[str, float]) -> float:
    return 0.5 * sum(abs(left[key] - right[key]) for key in left)


def _entropy(values: dict[str, float]) -> float:
    return -sum(value * math.log(value) for value in values.values())
