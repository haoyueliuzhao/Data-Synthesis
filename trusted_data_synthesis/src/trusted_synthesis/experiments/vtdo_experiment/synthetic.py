from __future__ import annotations

import math
import random
from collections.abc import Mapping
from typing import Literal, cast

from trusted_synthesis.core.refinement.aggregate import make_synthesis_cell
from trusted_synthesis.core.refinement.schema import (
    CellFeedbackStatistics,
    SynthesisPolicy,
    synthesis_policy_id,
)
from trusted_synthesis.core.refinement.update import (
    update_trajectory_profile_proxy_policy,
)
from trusted_synthesis.core.vtdo import (
    VTDO_ALGORITHM_ID,
    VTDO_ALGORITHM_VERSION,
    AnchoredEnergyConfig,
    ValidityThresholds,
    estimate_centered_contributions,
    make_conditional_distribution,
    make_coverage_prior,
    make_vtdo_role_contract,
    update_valid_trajectory_distribution,
)
from trusted_synthesis.core.vtdo.schema import (
    StateValidityEstimate,
    ValidityRegion,
    state_validity_estimate_id,
)
from trusted_synthesis.hashing import canonical_hash

from .schema import (
    AggregateMetric,
    EtaSensitivityResult,
    SyntheticExperimentConfig,
    SyntheticExperimentReport,
    SyntheticMethod,
    SyntheticMethodSummary,
    SyntheticMetricPoint,
    SyntheticState,
)
from .statistics import aggregate_metric

_MAIN_METHODS: tuple[SyntheticMethod, ...] = (
    "random",
    "contribution_only",
    "novelty_only",
    "ccgr",
    "full_vtdo",
)
_ABLATION_METHODS: tuple[SyntheticMethod, ...] = (
    "no_global_coverage_anchor",
    "no_coverage_prior",
    "no_iteration",
    "no_quotient_exact",
    "no_quotient_noisy",
)
_METHODS = (*_MAIN_METHODS, *_ABLATION_METHODS)


def run_synthetic_experiment(
    config: SyntheticExperimentConfig,
    *,
    experiment_id: str,
) -> tuple[
    SyntheticExperimentReport,
    dict[int, tuple[SyntheticState, ...]],
    tuple[dict[str, float | int | str], ...],
]:
    """Run the frozen K-state experiment through production VTDO and CCGR code."""

    points: list[SyntheticMetricPoint] = []
    catalogs: dict[int, tuple[SyntheticState, ...]] = {}
    phase_rows: list[dict[str, float | int | str]] = []
    accepted_counts: dict[str, int] = {}
    for seed in config.seeds:
        states = _make_states(config, seed)
        catalogs[seed] = states
        accepted = tuple(item for item in states if item.validity_region == "accepted")
        accepted_counts[str(seed)] = len(accepted)
        state_ids = tuple(item.state_id for item in accepted)
        contribution = {item.state_id: item.true_contribution for item in accepted}
        validity = {item.state_id: item.validity for item in accepted}
        coverage = _normalize({item.state_id: item.coverage_prior for item in accepted})
        initial = _normalize({item.state_id: item.initial_probability for item in accepted})
        vtdo_optimum = _fixed_potential_vtdo_optimum(
            coverage,
            contribution,
            initial,
            config,
        )
        raw_methods: tuple[SyntheticMethod, ...] = (
            "no_quotient_exact",
            "no_quotient_noisy",
        )
        distributions: dict[SyntheticMethod, dict[str, float]] = {
            method: dict(initial) for method in _METHODS if method not in raw_methods
        }
        raw_spaces = {
            method: _raw_state_space(
                initial,
                coverage,
                contribution,
                variants=config.raw_variants_per_state,
                seed=seed,
                contribution_noise_standard_deviation=(
                    0.0 if method == "no_quotient_exact" else 0.35
                ),
            )
            for method in raw_methods
        }
        for method in _METHODS:
            if method in raw_spaces:
                raw_distribution, _, _, raw_to_state = raw_spaces[method]
                metric_distribution = _aggregate_raw(raw_distribution, raw_to_state)
                raw_size = len(raw_distribution)
            else:
                metric_distribution = distributions[method]
                raw_size = None
            points.append(
                _metric_point(
                    seed,
                    method,
                    0,
                    metric_distribution,
                    metric_distribution,
                    coverage,
                    contribution,
                    vtdo_optimum,
                    config.coverage_epsilon,
                    raw_support_size=raw_size,
                )
            )
        for round_index in range(1, config.rounds + 1):
            prior_by_method = {key: dict(value) for key, value in distributions.items()}
            distributions["random"] = {state_id: 1.0 / len(state_ids) for state_id in state_ids}
            distributions["novelty_only"] = _analytic_update(
                prior_by_method["novelty_only"],
                coverage,
                contribution,
                config,
                mode="novelty_only",
            )
            distributions["contribution_only"] = _analytic_update(
                prior_by_method["contribution_only"],
                coverage,
                contribution,
                config,
                mode="contribution_only",
            )
            distributions["no_global_coverage_anchor"] = _analytic_update(
                prior_by_method["no_global_coverage_anchor"],
                coverage,
                contribution,
                config,
                mode="no_global_coverage_anchor",
            )
            distributions["no_coverage_prior"] = _analytic_update(
                prior_by_method["no_coverage_prior"],
                coverage,
                contribution,
                config,
                mode="no_coverage_prior",
            )
            distributions["ccgr"] = _ccgr_update(
                prior_by_method["ccgr"],
                coverage,
                validity,
            )
            distributions["full_vtdo"], full_phase = _production_vtdo_update(
                prior_by_method["full_vtdo"],
                coverage,
                contribution,
                validity,
                config,
                round_index=round_index - 1,
            )
            if round_index == 1:
                distributions["no_iteration"], _ = _production_vtdo_update(
                    prior_by_method["no_iteration"],
                    coverage,
                    contribution,
                    validity,
                    config,
                    round_index=0,
                )
            else:
                distributions["no_iteration"] = prior_by_method["no_iteration"]
            raw_priors: dict[str, dict[str, float]] = {}
            for method in raw_methods:
                raw_distribution, raw_coverage, raw_contribution, raw_to_state = raw_spaces[method]
                raw_priors[method] = dict(raw_distribution)
                raw_validity = {
                    raw_id: validity[state_id] for raw_id, state_id in raw_to_state.items()
                }
                next_raw, _ = _production_vtdo_update(
                    raw_distribution,
                    raw_coverage,
                    raw_contribution,
                    raw_validity,
                    config,
                    round_index=round_index - 1,
                    condition_suffix=method,
                )
                raw_spaces[method] = (
                    next_raw,
                    raw_coverage,
                    raw_contribution,
                    raw_to_state,
                )
            for row in full_phase:
                phase_rows.append({"seed": seed, "round_index": round_index, **row})
            for method in _METHODS:
                if method in raw_spaces:
                    raw_distribution, _, _, raw_to_state = raw_spaces[method]
                    current = _aggregate_raw(raw_distribution, raw_to_state)
                    previous = _aggregate_raw(raw_priors[method], raw_to_state)
                    raw_size = len(raw_distribution)
                else:
                    current = distributions[method]
                    previous = prior_by_method[method]
                    raw_size = None
                points.append(
                    _metric_point(
                        seed,
                        method,
                        round_index,
                        current,
                        previous,
                        coverage,
                        contribution,
                        vtdo_optimum,
                        config.coverage_epsilon,
                        raw_support_size=raw_size,
                    )
                )

    main_summaries = tuple(
        _summarize_method(method, points, config.rounds) for method in _MAIN_METHODS
    )
    ablation_summaries = tuple(
        _summarize_method(method, points, config.rounds) for method in _ABLATION_METHODS
    )
    sensitivity = tuple(_eta_sensitivity(config, eta) for eta in config.eta_sensitivity)
    config_hash = canonical_hash(config, prefix="synthetic_vtdo_config:")
    identity = {
        "experiment_id": experiment_id,
        "config_hash": config_hash,
        "points": points,
        "main_summaries": main_summaries,
        "ablation_summaries": ablation_summaries,
        "eta_sensitivity": sensitivity,
    }
    report = SyntheticExperimentReport(
        experiment_id=experiment_id,
        config_hash=config_hash,
        reference_definitions={
            "initial_fixed_target_diagnostic": (
                "The initial fixed-potential target is reported only as a diagnostic. "
                "Production methods recompute Phi_t and are not ranked by distance to Phi_0."
            ),
            "joint_utility": (
                "U(pi)=E_(z~pi)[true_contribution(z) * max(log(r(z|x)/pi(z|x)), 0)]."
            ),
            "coverage_alignment": "exp(-KL(r || pi)); one is exact anchor alignment.",
        },
        production_algorithm_id=VTDO_ALGORITHM_ID,
        production_algorithm_version=VTDO_ALGORITHM_VERSION,
        state_count=config.state_count,
        accepted_state_counts=accepted_counts,
        metric_points=tuple(points),
        main_method_summaries=main_summaries,
        ablation_summaries=ablation_summaries,
        eta_sensitivity=sensitivity,
        artifact_hash=canonical_hash(identity, prefix="synthetic_vtdo_report:"),
    )
    return report, catalogs, tuple(phase_rows)


def _make_states(config: SyntheticExperimentConfig, seed: int) -> tuple[SyntheticState, ...]:
    rng = random.Random(seed)
    raw: list[tuple[str, float, str, float, float, float]] = []
    tail_ranks = list(range(config.state_count))
    rng.shuffle(tail_ranks)
    for index in range(config.state_count):
        validity = rng.random()
        region = (
            "rejected"
            if validity < config.reject_below
            else "accepted"
            if validity >= config.accept_at_or_above
            else "quarantined"
        )
        contribution = rng.gauss(0.0, 1.0)
        tail_position = tail_ranks[index] / max(config.state_count - 1, 1)
        coverage_weight = 0.2 + 4.8 * tail_position**2
        initial_weight = math.exp(0.9 * contribution) / (0.35 + coverage_weight)
        raw.append(
            (
                f"synthetic_state:{seed}:{index:03d}",
                validity,
                region,
                contribution,
                coverage_weight,
                initial_weight,
            )
        )
    if sum(item[2] == "accepted" for item in raw) < 10:
        accepted_indexes = {
            item[0] for item in sorted(raw, key=lambda item: item[1], reverse=True)[:10]
        }
        raw = [
            (
                state_id,
                (
                    max(validity, config.accept_at_or_above)
                    if state_id in accepted_indexes
                    else validity
                ),
                "accepted" if state_id in accepted_indexes else region,
                contribution,
                coverage_weight,
                initial_weight,
            )
            for (
                state_id,
                validity,
                region,
                contribution,
                coverage_weight,
                initial_weight,
            ) in raw
        ]
    accepted_initial = _normalize({item[0]: item[5] for item in raw if item[2] == "accepted"})
    accepted_mean = sum(
        accepted_initial[item[0]] * item[3] for item in raw if item[2] == "accepted"
    )
    raw = [
        (state_id, validity, region, contribution - accepted_mean, coverage_weight, initial_weight)
        for state_id, validity, region, contribution, coverage_weight, initial_weight in raw
    ]
    coverage = _normalize({item[0]: item[4] for item in raw})
    initial = _normalize({item[0]: item[5] for item in raw})
    return tuple(
        SyntheticState(
            state_id=state_id,
            validity=validity,
            validity_region=cast(Literal["accepted", "quarantined", "rejected"], region),
            true_contribution=contribution,
            coverage_prior=coverage[state_id],
            initial_probability=initial[state_id],
        )
        for state_id, validity, region, contribution, _, _ in raw
    )


def _production_vtdo_update(
    prior_values: Mapping[str, float],
    coverage_values: Mapping[str, float],
    contributions: Mapping[str, float],
    validities: Mapping[str, float],
    config: SyntheticExperimentConfig,
    *,
    round_index: int,
    condition_suffix: str = "canonical",
) -> tuple[dict[str, float], tuple[dict[str, float | str], ...]]:
    condition = f"synthetic:{condition_suffix}"
    prior = make_conditional_distribution(
        condition,
        prior_values,
        round_index=round_index,
    )
    coverage = make_coverage_prior(
        condition,
        coverage_values,
        policy="frozen_long_tail_coverage",
    )
    manifest = estimate_centered_contributions(
        prior,
        contributions,
        confidences={state_id: 1.0 for state_id in prior_values},
        probe_sample_counts={state_id: 100 for state_id in prior_values},
        beneficiary_model_state_id="synthetic_beneficiary:v1",
        target_evaluation_distribution_id="synthetic_eval:v1",
        target_metric_id="synthetic_joint_utility",
        estimator_id="synthetic_exact_marginal_probe.v1",
    )
    estimates = tuple(
        _validity_estimate(condition, state_id, validities[state_id], config)
        for state_id in sorted(prior_values)
    )
    update = update_valid_trajectory_distribution(
        prior,
        coverage,
        estimates,
        manifest,
        _energy_config(config),
        make_vtdo_role_contract(
            explorer_provider_id="synthetic_explorer:v1",
            beneficiary_model_state_id="synthetic_beneficiary:v1",
            final_student_model_id="synthetic_student:v1",
        ),
    )
    phase_rows: list[dict[str, float | str]] = []
    for item in update.state_potentials:
        phase_rows.append(
            {
                "state_id": item.state_id,
                "current_probability": item.current_probability,
                "coverage_probability": item.coverage_probability,
                "normalized_contribution": item.normalized_contribution,
                "normalized_novelty": item.normalized_novelty,
                "potential": item.potential,
                "log_potential": math.log(item.potential),
                "next_probability": update.next_distribution.probabilities[item.state_id],
                "probability_delta": (
                    update.next_distribution.probabilities[item.state_id]
                    - update.prior_distribution.probabilities[item.state_id]
                ),
            }
        )
    return dict(update.next_distribution.probabilities), tuple(phase_rows)


def _analytic_update(
    prior: Mapping[str, float],
    coverage: Mapping[str, float],
    contribution: Mapping[str, float],
    config: SyntheticExperimentConfig,
    *,
    mode: Literal[
        "novelty_only",
        "contribution_only",
        "no_global_coverage_anchor",
        "no_coverage_prior",
    ],
) -> dict[str, float]:
    energy = _energy_config(config)
    centered_mean = sum(prior[key] * contribution[key] for key in prior)
    centered = {key: contribution[key] - centered_mean for key in prior}
    log_weights: dict[str, float] = {}
    for state_id in prior:
        novelty = max(math.log(coverage[state_id] / prior[state_id]), 0.0)
        normalized_c = _sigmoid_potential(
            centered[state_id],
            config.contribution_temperature,
            energy.epsilon,
        )
        normalized_n = _novelty_potential(
            novelty,
            config.novelty_temperature,
            energy.epsilon,
        )
        if mode == "novelty_only":
            potential = normalized_n
            log_weights[state_id] = (
                energy.history_exponent * math.log(prior[state_id])
                + (1.0 - energy.history_exponent) * math.log(coverage[state_id])
                + energy.energy_exponent * math.log(potential)
            )
        elif mode == "contribution_only":
            potential = normalized_c
            log_weights[state_id] = (
                energy.history_exponent * math.log(prior[state_id])
                + (1.0 - energy.history_exponent) * math.log(coverage[state_id])
                + energy.energy_exponent * math.log(potential)
            )
        elif mode == "no_global_coverage_anchor":
            potential = (
                normalized_c**config.contribution_weight * normalized_n**config.novelty_weight
            )
            log_weights[state_id] = math.log(prior[state_id]) + (
                energy.energy_exponent * math.log(potential)
            )
        else:
            log_weights[state_id] = math.log(prior[state_id]) + (
                energy.energy_exponent * math.log(normalized_c)
            )
    return _softmax(log_weights)


def _ccgr_update(
    prior: Mapping[str, float],
    coverage: Mapping[str, float],
    validity: Mapping[str, float],
) -> dict[str, float]:
    cells = {
        state_id: make_synthesis_cell(
            pattern_id="synthetic_state",
            binding_stratum_id=state_id,
            difficulty_bucket="controlled",
            distractor_profile_id="none",
        )
        for state_id in sorted(prior)
    }
    policy_values = {
        "round_index": 0,
        "label": "synthetic_ccgr_baseline",
        "cells": tuple(cells.values()),
        "probabilities": {cells[key].cell_id: prior[key] for key in sorted(prior)},
        "target_probabilities": {cells[key].cell_id: coverage[key] for key in sorted(prior)},
        "source_policy_id": None,
    }
    provisional = SynthesisPolicy.model_construct(policy_id="pending", **policy_values)
    policy = SynthesisPolicy(
        policy_id=synthesis_policy_id(provisional),
        **policy_values,
    )
    stats = []
    for state_id in sorted(prior):
        attempts = 100
        valid_count = max(1, min(attempts, round(validity[state_id] * attempts)))
        novelty = max(math.log(coverage[state_id] / prior[state_id]), 0.0)
        diversity = 1.0 - math.exp(-novelty)
        gap = max(0.0, coverage[state_id] - prior[state_id])
        stats.append(
            CellFeedbackStatistics(
                cell_id=cells[state_id].cell_id,
                exposure_count=attempts,
                root_feedback_count=0,
                interface_failure_count=0,
                synthesis_defect_count=attempts - valid_count,
                capability_gap_count=0,
                uncalibrated_feedback_count=0,
                interface_weight_sum=0.0,
                synthesis_defect_weight_sum=1.0 - validity[state_id],
                capability_gap_weight_sum=0.0,
                synthesis_defect_risk=1.0 - validity[state_id],
                capability_gap_demand=0.0,
                target_share=coverage[state_id],
                observed_share=prior[state_id],
                coverage_gap=gap,
                trajectory_attempt_count=attempts,
                valid_trajectory_count=valid_count,
                trajectory_validity_rate=valid_count / attempts,
                mean_trajectory_validity_score=validity[state_id],
                trajectory_attribute_profile_count=1,
                trajectory_attribute_entropy=0.0,
                trajectory_diversity_gain=diversity,
                missing_attribute_rate=0.0,
            )
        )
    result = update_trajectory_profile_proxy_policy(
        policy,
        stats,
        (),
        eta=1.0,
        total_budget=10_000,
        calibration_manifest_hash="synthetic_calibration:v1",
        trajectory_feedback_manifest_hash="synthetic_trajectory_feedback:v1",
        require_calibrated_feedback=False,
    )
    return {
        state_id: result.next_policy.probabilities[cells[state_id].cell_id]
        for state_id in sorted(prior)
    }


def _validity_estimate(
    condition: str,
    state_id: str,
    validity: float,
    config: SyntheticExperimentConfig,
) -> StateValidityEstimate:
    thresholds = ValidityThresholds(
        reject_below=config.reject_below,
        accept_at_or_above=config.accept_at_or_above,
    )
    values = {
        "task_condition_id": condition,
        "state_id": state_id,
        "attempted_trajectory_count": 100,
        "valid_trajectory_count": max(1, round(validity * 100)),
        "estimated_validity": validity,
        "confidence_lower": max(0.0, validity - 0.02),
        "confidence_upper": min(1.0, validity + 0.02),
        "mean_component_validity": {"synthetic_exact_validity": validity},
        "thresholds": thresholds,
        "classification_statistic": "synthetic_ground_truth",
        "region": ValidityRegion.ACCEPTED,
        "estimator_id": "synthetic_exact_validity.v1",
        "estimator_version": "1.0.0",
    }
    provisional = StateValidityEstimate.model_construct(estimate_id="pending", **values)
    return StateValidityEstimate(
        estimate_id=state_validity_estimate_id(provisional),
        **values,
    )


def _energy_config(config: SyntheticExperimentConfig) -> AnchoredEnergyConfig:
    return AnchoredEnergyConfig(
        epsilon=1e-6,
        contribution_temperature=config.contribution_temperature,
        novelty_temperature=config.novelty_temperature,
        contribution_weight=config.contribution_weight,
        novelty_weight=config.novelty_weight,
        history_kl_weight=config.history_kl_weight,
        coverage_kl_weight=config.coverage_kl_weight,
    )


def _metric_point(
    seed: int,
    method: SyntheticMethod,
    round_index: int,
    current: Mapping[str, float],
    previous: Mapping[str, float],
    coverage: Mapping[str, float],
    contribution: Mapping[str, float],
    vtdo_optimum: Mapping[str, float],
    epsilon: float,
    *,
    raw_support_size: int | None,
) -> SyntheticMetricPoint:
    novelty = {
        state_id: max(math.log(coverage[state_id] / current[state_id]), 0.0) for state_id in current
    }
    return SyntheticMetricPoint(
        seed=seed,
        method=method,
        round_index=round_index,
        kl_to_initial_fixed_target_diagnostic=_kl(current, vtdo_optimum),
        expected_contribution_novelty=sum(
            current[key] * contribution[key] * novelty[key] for key in current
        ),
        expected_contribution=sum(current[key] * contribution[key] for key in current),
        coverage_kl=_kl(coverage, current),
        coverage_alignment=math.exp(-_kl(coverage, current)),
        coverage_count=sum(value > epsilon for value in current.values()),
        entropy=_entropy(current),
        kl_to_previous=_kl(current, previous),
        top_right_mass=sum(
            current[key] for key in current if contribution[key] > 0 and novelty[key] > 0
        ),
        support_size=len(current),
        raw_support_size=raw_support_size,
    )


def _summarize_method(
    method: SyntheticMethod,
    points: list[SyntheticMetricPoint],
    final_round: int,
) -> SyntheticMethodSummary:
    final = [item for item in points if item.method == method and item.round_index == final_round]
    return SyntheticMethodSummary(
        method=method,
        run_count=len(final),
        final_expected_utility=_aggregate([item.expected_contribution_novelty for item in final]),
        final_coverage_kl=_aggregate([item.coverage_kl for item in final]),
        final_coverage_alignment=_aggregate([item.coverage_alignment for item in final]),
        final_coverage_count=_aggregate([float(item.coverage_count) for item in final]),
        final_entropy=_aggregate([item.entropy for item in final]),
        final_top_right_mass=_aggregate([item.top_right_mass for item in final]),
    )


def _eta_sensitivity(
    config: SyntheticExperimentConfig,
    eta: float,
) -> EtaSensitivityResult:
    metrics: list[SyntheticMetricPoint] = []
    regularization_weight = 1.0 / (2.0 * eta)
    tuned = config.model_copy(
        update={
            "history_kl_weight": regularization_weight,
            "coverage_kl_weight": regularization_weight,
        }
    )
    for seed in config.seeds:
        states = _make_states(tuned, seed)
        accepted = tuple(item for item in states if item.validity_region == "accepted")
        contribution = {item.state_id: item.true_contribution for item in accepted}
        validity = {item.state_id: item.validity for item in accepted}
        coverage = _normalize({item.state_id: item.coverage_prior for item in accepted})
        current = _normalize({item.state_id: item.initial_probability for item in accepted})
        vtdo_optimum = _fixed_potential_vtdo_optimum(
            coverage,
            contribution,
            current,
            tuned,
        )
        for round_index in range(1, tuned.rounds + 1):
            previous = current
            current, _ = _production_vtdo_update(
                current,
                coverage,
                contribution,
                validity,
                tuned,
                round_index=round_index - 1,
                condition_suffix=f"eta_{eta:g}",
            )
        metrics.append(
            _metric_point(
                seed,
                "full_vtdo",
                tuned.rounds,
                current,
                previous,
                coverage,
                contribution,
                vtdo_optimum,
                tuned.coverage_epsilon,
                raw_support_size=None,
            )
        )
    return EtaSensitivityResult(
        energy_exponent=eta,
        final_expected_utility=_aggregate([item.expected_contribution_novelty for item in metrics]),
        final_coverage_kl=_aggregate([item.coverage_kl for item in metrics]),
        final_coverage_alignment=_aggregate([item.coverage_alignment for item in metrics]),
        final_entropy=_aggregate([item.entropy for item in metrics]),
    )


def _raw_state_space(
    initial: Mapping[str, float],
    coverage: Mapping[str, float],
    contribution: Mapping[str, float],
    *,
    variants: int,
    seed: int,
    contribution_noise_standard_deviation: float,
) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, str]]:
    rng = random.Random(seed + 99_991)
    raw_initial: dict[str, float] = {}
    raw_coverage: dict[str, float] = {}
    raw_contribution: dict[str, float] = {}
    raw_to_state: dict[str, str] = {}
    for state_id in sorted(initial):
        splits = _normalize({str(index): 0.5 + rng.random() for index in range(variants)})
        for index in range(variants):
            raw_id = f"{state_id}:surface:{index}"
            raw_to_state[raw_id] = state_id
            raw_initial[raw_id] = initial[state_id] * splits[str(index)]
            raw_coverage[raw_id] = coverage[state_id] / variants
            raw_contribution[raw_id] = contribution[state_id] + rng.gauss(
                0.0,
                contribution_noise_standard_deviation,
            )
    return (
        _normalize(raw_initial),
        _normalize(raw_coverage),
        raw_contribution,
        raw_to_state,
    )


def _aggregate_raw(
    probabilities: Mapping[str, float],
    raw_to_state: Mapping[str, str],
) -> dict[str, float]:
    output: dict[str, float] = {}
    for raw_id, probability in probabilities.items():
        state_id = raw_to_state[raw_id]
        output[state_id] = output.get(state_id, 0.0) + probability
    return dict(sorted(output.items()))


def _fixed_potential_vtdo_optimum(
    coverage: Mapping[str, float],
    contribution: Mapping[str, float],
    initial: Mapping[str, float],
    config: SyntheticExperimentConfig,
) -> dict[str, float]:
    energy = _energy_config(config)
    centered_mean = sum(initial[key] * contribution[key] for key in initial)
    centered = {key: contribution[key] - centered_mean for key in initial}
    potentials = {}
    for state_id in initial:
        novelty = max(math.log(coverage[state_id] / initial[state_id]), 0.0)
        normalized_contribution = _sigmoid_potential(
            centered[state_id],
            config.contribution_temperature,
            energy.epsilon,
        )
        normalized_novelty = _novelty_potential(
            novelty,
            config.novelty_temperature,
            energy.epsilon,
        )
        potentials[state_id] = (
            normalized_contribution**config.contribution_weight
            * normalized_novelty**config.novelty_weight
        )
    return _normalize(
        {
            state_id: coverage[state_id] * potentials[state_id] ** (1.0 / config.coverage_kl_weight)
            for state_id in coverage
        }
    )


def _sigmoid_potential(value: float, temperature: float, epsilon: float) -> float:
    scaled = value / temperature
    if scaled >= 0:
        sigmoid = 1.0 / (1.0 + math.exp(-scaled))
    else:
        exponential = math.exp(scaled)
        sigmoid = exponential / (1.0 + exponential)
    return epsilon + (1.0 - 2.0 * epsilon) * sigmoid


def _novelty_potential(value: float, temperature: float, epsilon: float) -> float:
    return epsilon + (1.0 - 2.0 * epsilon) * (1.0 - math.exp(-value / temperature))


def _normalize(values: Mapping[str, float]) -> dict[str, float]:
    total = sum(values.values())
    if total <= 0 or any(value <= 0 for value in values.values()):
        raise ValueError("probability weights must be strictly positive")
    return {key: values[key] / total for key in sorted(values)}


def _softmax(log_weights: Mapping[str, float]) -> dict[str, float]:
    maximum = max(log_weights.values())
    return _normalize({key: math.exp(value - maximum) for key, value in log_weights.items()})


def _kl(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    return sum(left[key] * math.log(left[key] / right[key]) for key in left)


def _entropy(values: Mapping[str, float]) -> float:
    return -sum(value * math.log(value) for value in values.values())


def _aggregate(values: list[float]) -> AggregateMetric:
    return aggregate_metric(values)
