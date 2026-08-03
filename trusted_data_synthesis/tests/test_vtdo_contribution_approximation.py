from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from trusted_synthesis.core.vtdo import (
    AnchoredEnergyConfig,
    ContributionInterventionRuntimeProtocol,
    ContributionMetricContract,
    ContributionProbeRuntimeProtocol,
    InterventionTrainingResult,
    ProbeAdaptationResult,
    ValidityThresholds,
    contribution_current_distribution_hash,
    empty_optimizer_state_hash,
    estimate_contributions_from_interventions,
    estimate_contributions_from_probes,
    intervention_addition_count,
    make_conditional_distribution,
    make_contribution_data_isolation_contract,
    make_contribution_intervention_observation,
    make_contribution_intervention_protocol,
    make_contribution_metric_contract,
    make_contribution_probe_observation,
    make_contribution_probe_protocol,
    make_contribution_production_authorization,
    make_contribution_rank_validation_evidence,
    make_coverage_prior,
    make_probe_optimizer_contract,
    make_vtdo_role_contract,
    run_contribution_intervention,
    run_contribution_probe,
    update_valid_trajectory_distribution,
)
from trusted_synthesis.core.vtdo.schema import (
    ContributionEstimate,
    ContributionEstimationManifest,
    StateValidityEstimate,
    contribution_estimate_id,
    contribution_manifest_id,
    state_validity_estimate_id,
    validity_region,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import (
    ContributionValidationObservation,
    contribution_validation_observation_id,
)


def test_intervention_implements_frozen_probability_mass_epsilon() -> None:
    assert intervention_addition_count(19, 0.05) == 1
    assert intervention_addition_count(100, 0.05) == 6
    distribution, _, intervention = _contracts()
    observations = (
        make_contribution_intervention_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id="state:a",
            protocol=intervention,
            seed=7,
            training_result=_intervention_result(intervention, "state:proof", 7),
            baseline_performance=0.5,
            intervention_performance=0.55,
        ),
        make_contribution_intervention_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id="state:b",
            protocol=intervention,
            seed=7,
            training_result=_intervention_result(intervention, "state:proof", 7),
            baseline_performance=0.5,
            intervention_performance=0.60,
        ),
    )

    assert observations[0].epsilon == pytest.approx(0.05)
    assert observations[0].normalized_intervention_contribution == pytest.approx(1.0)
    manifest = estimate_contributions_from_interventions(distribution, observations)
    assert manifest.estimator_kind == "finite_intervention"
    assert manifest.usage_scope == "intervention_validation"


def test_data_isolation_rejects_probe_validation_and_final_test_leakage() -> None:
    with pytest.raises(ValueError, match="leak"):
        make_contribution_data_isolation_contract(
            task_condition_id="task:x",
            baseline_training_set_id="train:x",
            baseline_training_instance_ids=("instance:train",),
            probe_update_instance_ids_by_state={
                "state:a": ("instance:validation",),
            },
            internal_validation_set_id="validation:x",
            internal_validation_instance_ids=("instance:validation",),
            final_test_set_id="test:x",
            final_test_instance_ids=("instance:test",),
        )


def test_probe_optimizer_is_local_cold_start_and_at_most_three_steps() -> None:
    with pytest.raises(ValueError):
        make_probe_optimizer_contract(
            optimizer_name="sgd",
            learning_rate=1e-5,
            step_count=4,
        )
    with pytest.raises(ValueError, match="momentum=0"):
        make_probe_optimizer_contract(
            optimizer_name="sgd",
            learning_rate=1e-5,
            step_count=3,
            momentum=0.9,
        )


def test_probe_confidence_is_diagnostic_and_does_not_shrink_contribution() -> None:
    distribution, probe, _ = _contracts(probabilities={"state:a": 0.8, "state:b": 0.2})
    observations = (
        make_contribution_probe_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id="state:a",
            protocol=probe,
            seed=7,
            adaptation_result=_adaptation_result(probe, "state:proof", 7),
            baseline_performance=0.5,
            adapted_performance=0.6,
            measurement_confidence=0.1,
        ),
        make_contribution_probe_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id="state:a",
            protocol=probe,
            seed=13,
            adaptation_result=_adaptation_result(probe, "state:proof", 13),
            baseline_performance=0.5,
            adapted_performance=0.6,
            measurement_confidence=0.1,
        ),
        make_contribution_probe_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id="state:b",
            protocol=probe,
            seed=7,
            adaptation_result=_adaptation_result(probe, "state:proof", 7),
            baseline_performance=0.5,
            adapted_performance=0.9,
            measurement_confidence=1.0,
        ),
        make_contribution_probe_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id="state:b",
            protocol=probe,
            seed=13,
            adaptation_result=_adaptation_result(probe, "state:proof", 13),
            baseline_performance=0.5,
            adapted_performance=0.9,
            measurement_confidence=1.0,
        ),
    )

    manifest = estimate_contributions_from_probes(distribution, observations)
    estimates = {item.state_id: item for item in manifest.estimates}

    assert estimates["state:a"].raw_marginal_gain == pytest.approx(0.1)
    assert estimates["state:a"].centered_contribution == pytest.approx(-0.06)
    assert estimates["state:a"].sample_standard_deviation == 0.0
    assert estimates["state:a"].conservative_centered_contribution == pytest.approx(-0.06)
    assert estimates["state:b"].centered_contribution == pytest.approx(0.24)
    assert manifest.weighted_centered_mean == pytest.approx(0.0, abs=1e-12)


def test_uncertainty_penalty_can_reverse_noisy_mean_ranking_and_drives_energy() -> None:
    distribution, probe, _ = _contracts()
    gains = {
        ("state:a", 7): 0.2,
        ("state:a", 13): 0.4,
        ("state:b", 7): 0.25,
        ("state:b", 13): 0.25,
    }
    observations = tuple(
        make_contribution_probe_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id=state_id,
            protocol=probe,
            seed=seed,
            adaptation_result=_adaptation_result(probe, "state:proof", seed),
            baseline_performance=0.5,
            adapted_performance=0.5 + gain,
        )
        for (state_id, seed), gain in gains.items()
    )
    manifest = estimate_contributions_from_probes(distribution, observations)
    estimates = {item.state_id: item for item in manifest.estimates}

    assert estimates["state:a"].centered_contribution > estimates["state:b"].centered_contribution
    assert estimates["state:a"].sample_standard_deviation > 0
    assert estimates["state:a"].conservative_centered_contribution < (
        estimates["state:b"].conservative_centered_contribution
    )
    assert manifest.weighted_conservative_centered_mean == pytest.approx(0.0, abs=1e-12)

    coverage = make_coverage_prior(
        "task:x",
        {"state:a": 0.5, "state:b": 0.5},
        policy="test",
    )
    update = update_valid_trajectory_distribution(
        distribution,
        coverage,
        tuple(_accepted_validity(state_id) for state_id in ("state:a", "state:b")),
        manifest,
        _production_authorization(manifest),
        AnchoredEnergyConfig(
            epsilon=0.01,
            contribution_temperature=1.0,
            novelty_temperature=1.0,
            contribution_weight=0.999999,
            novelty_weight=0.000001,
            history_kl_weight=1.0,
            coverage_kl_weight=1.0,
        ),
        make_vtdo_role_contract(
            explorer_provider_id="explorer:x",
            materialization_provider_id="materializer:x",
            beneficiary_model_state_id="beneficiary:x",
            final_student_model_id="student:x",
        ),
    )
    potentials = {item.state_id: item for item in update.state_potentials}
    assert potentials["state:b"].normalized_contribution > (
        potentials["state:a"].normalized_contribution
    )
    assert all(
        item.contribution_signal_kind == "conservative_centered_contribution"
        for item in potentials.values()
    )


def test_local_probe_update_fails_closed_without_matching_independent_authorization() -> None:
    distribution, probe, _ = _contracts()
    observations = tuple(
        make_contribution_probe_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id=state_id,
            protocol=probe,
            seed=seed,
            adaptation_result=_adaptation_result(probe, "state:proof", seed),
            baseline_performance=0.5,
            adapted_performance=0.6 + state_index * 0.1,
        )
        for state_index, state_id in enumerate(("state:a", "state:b"))
        for seed in (7, 13)
    )
    manifest = estimate_contributions_from_probes(distribution, observations)
    coverage = make_coverage_prior(
        "task:x",
        {"state:a": 0.5, "state:b": 0.5},
        policy="test",
    )
    validity = tuple(_accepted_validity(state_id) for state_id in ("state:a", "state:b"))
    config = AnchoredEnergyConfig(
        epsilon=0.01,
        contribution_temperature=1.0,
        novelty_temperature=1.0,
        contribution_weight=0.5,
        novelty_weight=0.5,
        history_kl_weight=1.0,
        coverage_kl_weight=1.0,
    )
    roles = make_vtdo_role_contract(
        explorer_provider_id="explorer:x",
        materialization_provider_id="materializer:x",
        beneficiary_model_state_id="beneficiary:x",
        final_student_model_id="student:x",
    )

    with pytest.raises(ValueError, match="independent authorization"):
        update_valid_trajectory_distribution(
            distribution,
            coverage,
            validity,
            manifest,
            None,
            config,
            roles,
        )

    authorization = _production_authorization(manifest)
    wrong_horizon = authorization.model_copy(update={"selected_adaptation_horizon": 1})
    with pytest.raises(ValueError, match="does not match"):
        update_valid_trajectory_distribution(
            distribution,
            coverage,
            validity,
            manifest,
            wrong_horizon,
            config,
            roles,
        )


def test_production_authorization_rejects_failed_rank_evidence() -> None:
    distribution, probe, _ = _contracts()
    observations = tuple(
        make_contribution_probe_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id=state_id,
            protocol=probe,
            seed=seed,
            adaptation_result=_adaptation_result(probe, "state:proof", seed),
            baseline_performance=0.5,
            adapted_performance=0.6 + state_index * 0.1,
        )
        for state_index, state_id in enumerate(("state:a", "state:b"))
        for seed in (7, 13)
    )
    manifest = estimate_contributions_from_probes(distribution, observations)
    failed = make_contribution_rank_validation_evidence(
        evaluation_role="cross_seed_stability",
        macro_task_spearman=0.1,
        macro_task_spearman_ci95=(-0.2, 0.4),
        macro_pairwise_concordance=0.55,
        macro_pairwise_concordance_ci95=(0.4, 0.7),
        winner_agreement_rate=0.5,
        macro_spearman_p_value=0.2,
        macro_pairwise_concordance_p_value=0.2,
    )
    valid = _production_authorization(manifest)

    with pytest.raises(ValueError, match="failed rank gate"):
        make_contribution_production_authorization(
            manifest=manifest,
            analysis_version=valid.analysis_version,
            analysis_report_hash=valid.analysis_report_hash,
            task_condition_ids=valid.task_condition_ids,
            task_distribution_hashes=dict(valid.task_distribution_hashes),
            task_count=valid.task_count,
            state_count=valid.state_count,
            internal_validation_record_count=valid.internal_validation_record_count,
            final_test_record_count=valid.final_test_record_count,
            estimation_seed_count=valid.estimation_seed_count,
            validation_seed_count=valid.validation_seed_count,
            intervention_seed_count=valid.intervention_seed_count,
            cross_seed_stability=failed,
            independent_final_test=valid.independent_final_test,
            heldout_final_test=valid.heldout_final_test,
        )

    mismatched_distributions = dict(valid.task_distribution_hashes)
    mismatched_distributions[manifest.task_condition_id] = "current-distribution:wrong"
    with pytest.raises(ValueError, match="distribution mapping does not match"):
        make_contribution_production_authorization(
            manifest=manifest,
            analysis_version=valid.analysis_version,
            analysis_report_hash=valid.analysis_report_hash,
            task_condition_ids=valid.task_condition_ids,
            task_distribution_hashes=mismatched_distributions,
            task_count=valid.task_count,
            state_count=valid.state_count,
            internal_validation_record_count=valid.internal_validation_record_count,
            final_test_record_count=valid.final_test_record_count,
            estimation_seed_count=valid.estimation_seed_count,
            validation_seed_count=valid.validation_seed_count,
            intervention_seed_count=valid.intervention_seed_count,
            cross_seed_stability=valid.cross_seed_stability,
            independent_final_test=valid.independent_final_test,
            heldout_final_test=valid.heldout_final_test,
        )


def test_production_authorization_rejects_task_outside_validated_population() -> None:
    distribution, probe, _ = _contracts()
    observations = tuple(
        make_contribution_probe_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id=state_id,
            protocol=probe,
            seed=seed,
            adaptation_result=_adaptation_result(probe, "state:proof", seed),
            baseline_performance=0.5,
            adapted_performance=adapted_performance,
        )
        for state_id, adapted_performance in (("state:a", 0.6), ("state:b", 0.9))
        for seed in (7, 13)
    )
    manifest = estimate_contributions_from_probes(distribution, observations)
    valid = _production_authorization(manifest)

    with pytest.raises(ValueError, match="outside the validated population"):
        make_contribution_production_authorization(
            manifest=manifest,
            analysis_version=valid.analysis_version,
            analysis_report_hash=valid.analysis_report_hash,
            task_condition_ids=tuple(f"task:other:{index}" for index in range(30)),
            task_distribution_hashes=dict(valid.task_distribution_hashes),
            task_count=valid.task_count,
            state_count=valid.state_count,
            internal_validation_record_count=valid.internal_validation_record_count,
            final_test_record_count=valid.final_test_record_count,
            estimation_seed_count=valid.estimation_seed_count,
            validation_seed_count=valid.validation_seed_count,
            intervention_seed_count=valid.intervention_seed_count,
            cross_seed_stability=valid.cross_seed_stability,
            independent_final_test=valid.independent_final_test,
            heldout_final_test=valid.heldout_final_test,
        )


def test_manifest_replays_centering_from_raw_gains_and_current_distribution() -> None:
    distribution, probe, _ = _contracts()
    observations = (
        make_contribution_probe_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id="state:a",
            protocol=probe,
            seed=7,
            adaptation_result=_adaptation_result(probe, "state:proof", 7),
            baseline_performance=0.5,
            adapted_performance=0.6,
        ),
        make_contribution_probe_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id="state:a",
            protocol=probe,
            seed=13,
            adaptation_result=_adaptation_result(probe, "state:proof", 13),
            baseline_performance=0.5,
            adapted_performance=0.6,
        ),
        make_contribution_probe_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id="state:b",
            protocol=probe,
            seed=7,
            adaptation_result=_adaptation_result(probe, "state:proof", 7),
            baseline_performance=0.5,
            adapted_performance=0.9,
        ),
        make_contribution_probe_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id="state:b",
            protocol=probe,
            seed=13,
            adaptation_result=_adaptation_result(probe, "state:proof", 13),
            baseline_performance=0.5,
            adapted_performance=0.9,
        ),
    )
    manifest = estimate_contributions_from_probes(distribution, observations)
    tampered_estimates: list[ContributionEstimate] = []
    for item, centered in zip(manifest.estimates, (-1.0, 1.0), strict=True):
        values = item.model_dump(mode="python", exclude={"estimate_id"})
        values["centered_contribution"] = centered
        provisional = ContributionEstimate.model_construct(estimate_id="pending", **values)
        tampered_estimates.append(
            ContributionEstimate(
                estimate_id=contribution_estimate_id(provisional),
                **values,
            )
        )
    values = manifest.model_dump(mode="python", exclude={"manifest_id", "estimates"})
    values["estimates"] = tuple(tampered_estimates)
    values["weighted_centered_mean"] = 0.0
    provisional = ContributionEstimationManifest.model_construct(
        manifest_id="pending",
        **values,
    )

    with pytest.raises(ValueError, match="does not replay"):
        ContributionEstimationManifest(
            manifest_id=contribution_manifest_id(provisional),
            **values,
        )


def test_probe_runtime_uses_only_update_and_internal_validation_instances() -> None:
    _, probe, _ = _contracts()
    runtime = _ProbeRuntime(probe)

    observation = run_contribution_probe(
        runtime,
        round_index=0,
        protocol=probe,
        state_id="state:a",
        seed=7,
    )

    assert observation.performance_gain == pytest.approx(0.2)
    assert runtime.adapted_with == [("probe:state:a",)]
    assert runtime.evaluated_with == [
        ("validation:0", "validation:1"),
        ("validation:0", "validation:1"),
    ]
    assert runtime.evaluated_checkpoints == [
        "checkpoint:x",
        "checkpoint:x:adapted",
    ]
    assert "final-test:0" not in {
        instance_id for instance_ids in runtime.evaluated_with for instance_id in instance_ids
    }


def test_probe_runtime_rejects_reused_optimizer_state() -> None:
    _, probe, _ = _contracts()
    runtime = _ProbeRuntime(probe, wrong_optimizer_state=True)

    with pytest.raises(ValueError, match="cold-start optimizer"):
        run_contribution_probe(
            runtime,
            round_index=0,
            protocol=probe,
            state_id="state:a",
            seed=7,
        )


def test_intervention_runtime_uses_same_internal_validation_and_never_final_test() -> None:
    _, _, intervention = _contracts()
    runtime = _InterventionRuntime(intervention)

    observation = run_contribution_intervention(
        runtime,
        round_index=0,
        protocol=intervention,
        state_id="state:a",
        seed=7,
    )

    assert observation.epsilon == pytest.approx(0.05)
    assert runtime.training_inputs == [
        (
            tuple(f"train:{index}" for index in range(19)),
            ("probe:state:a",),
        )
    ]
    assert runtime.evaluated_with == [
        ("validation:0", "validation:1"),
        ("validation:0", "validation:1"),
    ]
    assert runtime.evaluated_checkpoints == [
        "checkpoint:x",
        "checkpoint:x:intervention",
    ]


def test_finite_intervention_manifest_cannot_update_production_distribution() -> None:
    distribution, _, intervention = _contracts()
    observations = tuple(
        make_contribution_intervention_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id=state_id,
            protocol=intervention,
            seed=7,
            training_result=_intervention_result(intervention, "state:proof", 7),
            baseline_performance=0.5,
            intervention_performance=0.55 + index * 0.01,
        )
        for index, state_id in enumerate(("state:a", "state:b"))
    )
    manifest = estimate_contributions_from_interventions(distribution, observations)
    coverage = make_coverage_prior(
        "task:x",
        {"state:a": 0.5, "state:b": 0.5},
        policy="test",
    )
    validity = tuple(_accepted_validity(state_id) for state_id in ("state:a", "state:b"))
    roles = make_vtdo_role_contract(
        explorer_provider_id="explorer:x",
        materialization_provider_id="materializer:x",
        beneficiary_model_state_id="beneficiary:x",
        final_student_model_id="student:x",
    )

    with pytest.raises(ValueError, match="validation-only"):
        update_valid_trajectory_distribution(
            distribution,
            coverage,
            validity,
            manifest,
            None,
            AnchoredEnergyConfig(
                epsilon=0.01,
                contribution_temperature=1.0,
                novelty_temperature=1.0,
                contribution_weight=0.5,
                novelty_weight=0.5,
                history_kl_weight=1.0,
                coverage_kl_weight=1.0,
            ),
            roles,
        )


def test_intervention_estimator_rejects_baseline_drift_across_states() -> None:
    distribution, _, intervention = _contracts()
    observations = (
        make_contribution_intervention_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id="state:a",
            protocol=intervention,
            seed=7,
            training_result=_intervention_result(intervention, "state:proof", 7),
            baseline_performance=0.5,
            intervention_performance=0.55,
        ),
        make_contribution_intervention_observation(
            task_condition_id="task:x",
            round_index=0,
            state_id="state:b",
            protocol=intervention,
            seed=7,
            training_result=_intervention_result(intervention, "state:proof", 7),
            baseline_performance=0.4,
            intervention_performance=0.50,
        ),
    )

    with pytest.raises(ValueError, match="baseline is not frozen"):
        estimate_contributions_from_interventions(distribution, observations)


def test_validation_pair_rejects_different_baseline_performance() -> None:
    _, probe, intervention = _contracts()
    probe_observation = make_contribution_probe_observation(
        task_condition_id="task:x",
        round_index=0,
        state_id="state:a",
        protocol=probe,
        seed=7,
        adaptation_result=_adaptation_result(probe, "state:proof", 7),
        baseline_performance=0.5,
        adapted_performance=0.6,
    )
    intervention_observation = make_contribution_intervention_observation(
        task_condition_id="task:x",
        round_index=0,
        state_id="state:a",
        protocol=intervention,
        seed=7,
        training_result=_intervention_result(intervention, "state:proof", 7),
        baseline_performance=0.4,
        intervention_performance=0.5,
    )
    values = {
        "task_condition_id": "task:x",
        "round_index": 0,
        "state_id": "state:a",
        "seed": 7,
        "baseline_distribution_id": "distribution:x",
        "probe_observation": probe_observation,
        "intervention_observation": intervention_observation,
    }
    provisional = ContributionValidationObservation.model_construct(
        observation_id="pending",
        **values,
    )

    with pytest.raises(ValueError, match="mismatched baseline performance"):
        ContributionValidationObservation(
            observation_id=contribution_validation_observation_id(provisional),
            **values,
        )


def test_validation_pair_rejects_reused_trained_artifact() -> None:
    _, probe, intervention = _contracts()
    probe_observation = make_contribution_probe_observation(
        task_condition_id="task:x",
        round_index=0,
        state_id="state:a",
        protocol=probe,
        seed=7,
        adaptation_result=_adaptation_result(probe, "state:proof", 7),
        baseline_performance=0.5,
        adapted_performance=0.6,
    )
    intervention_observation = make_contribution_intervention_observation(
        task_condition_id="task:x",
        round_index=0,
        state_id="state:a",
        protocol=intervention,
        seed=7,
        training_result=_intervention_result(intervention, "state:proof", 7).model_copy(
            update={
                "intervention_model_state_id": (
                    probe_observation.adaptation_result.adapted_model_state_id
                ),
                "intervention_checkpoint_hash": (
                    probe_observation.adaptation_result.adapted_checkpoint_hash
                ),
            }
        ),
        baseline_performance=0.5,
        intervention_performance=0.6,
    )
    values = {
        "task_condition_id": "task:x",
        "round_index": 0,
        "state_id": "state:a",
        "seed": 7,
        "baseline_distribution_id": "distribution:x",
        "probe_observation": probe_observation,
        "intervention_observation": intervention_observation,
    }
    provisional = ContributionValidationObservation.model_construct(
        observation_id="pending",
        **values,
    )

    with pytest.raises(ValueError, match="reuse one trained artifact"):
        ContributionValidationObservation(
            observation_id=contribution_validation_observation_id(provisional),
            **values,
        )


def _contracts(
    *,
    probabilities: dict[str, float] | None = None,
):
    state_ids = ("state:a", "state:b")
    distribution = make_conditional_distribution(
        "task:x",
        probabilities or {"state:a": 0.5, "state:b": 0.5},
        round_index=0,
    )
    data = make_contribution_data_isolation_contract(
        task_condition_id="task:x",
        baseline_training_set_id="train:x",
        baseline_training_instance_ids=tuple(f"train:{index}" for index in range(19)),
        probe_update_instance_ids_by_state={
            state_id: (f"probe:{state_id}",) for state_id in state_ids
        },
        internal_validation_set_id="validation:x",
        internal_validation_instance_ids=("validation:0", "validation:1"),
        final_test_set_id="test:x",
        final_test_instance_ids=("final-test:0",),
    )
    metric = make_contribution_metric_contract(
        target_metric_id="accuracy",
        evaluation_distribution_id="validation:x",
        evaluation_snapshot_hash="validation-snapshot:x",
        score_transform="identity",
    )
    optimizer = make_probe_optimizer_contract(
        optimizer_name="sgd",
        learning_rate=1e-5,
        step_count=3,
    )
    probe = make_contribution_probe_protocol(
        beneficiary_model_state_id="beneficiary:x",
        beneficiary_checkpoint_hash="checkpoint:x",
        metric_contract=metric,
        data_isolation=data,
        optimizer=optimizer,
        probe_seeds=(7, 13),
    )
    intervention = make_contribution_intervention_protocol(
        beneficiary_model_state_id="beneficiary:x",
        beneficiary_checkpoint_hash="checkpoint:x",
        metric_contract=metric,
        data_isolation=data,
        retraining_protocol_hash="retraining:x",
        intervention_seeds=(7,),
        target_epsilon=0.05,
    )
    return distribution, probe, intervention


def _adaptation_result(protocol, state_id: str, seed: int) -> ProbeAdaptationResult:
    return ProbeAdaptationResult(
        adapted_model_state_id=f"beneficiary:x:adapted:{state_id}:{seed}",
        adapted_checkpoint_hash=f"checkpoint:x:adapted:{state_id}:{seed}",
        base_model_state_id=protocol.beneficiary_model_state_id,
        base_checkpoint_hash=protocol.beneficiary_checkpoint_hash,
        optimizer_contract_id=protocol.optimizer.contract_id,
        initial_optimizer_state_hash=empty_optimizer_state_hash(protocol.optimizer),
        executed_step_count=protocol.optimizer.step_count,
    )


def _intervention_result(
    protocol,
    state_id: str,
    seed: int,
) -> InterventionTrainingResult:
    return InterventionTrainingResult(
        intervention_model_state_id=f"beneficiary:x:intervention:{state_id}:{seed}",
        intervention_checkpoint_hash=f"checkpoint:x:intervention:{state_id}:{seed}",
        base_model_state_id=protocol.beneficiary_model_state_id,
        base_checkpoint_hash=protocol.beneficiary_checkpoint_hash,
        retraining_protocol_hash=protocol.retraining_protocol_hash,
        baseline_training_set_id=protocol.data_isolation.baseline_training_set_id,
    )


@dataclass
class _ProbeRuntime(ContributionProbeRuntimeProtocol):
    probe_contract: object
    wrong_optimizer_state: bool = False
    evaluated_with: list[tuple[str, ...]] = field(default_factory=list)
    evaluated_checkpoints: list[str] = field(default_factory=list)
    adapted_with: list[tuple[str, ...]] = field(default_factory=list)

    def evaluate(
        self,
        model_state_id: str,
        checkpoint_hash: str,
        instance_ids: tuple[str, ...],
        metric_contract: ContributionMetricContract,
    ) -> float:
        self.evaluated_with.append(instance_ids)
        self.evaluated_checkpoints.append(checkpoint_hash)
        return 0.5 if model_state_id == "beneficiary:x" else 0.7

    def cold_start_adapt(
        self,
        beneficiary_model_state_id: str,
        beneficiary_checkpoint_hash: str,
        update_instance_ids: tuple[str, ...],
        optimizer_contract,
        seed: int,
    ) -> ProbeAdaptationResult:
        self.adapted_with.append(update_instance_ids)
        initial_hash = (
            "optimizer-state:reused"
            if self.wrong_optimizer_state
            else empty_optimizer_state_hash(optimizer_contract)
        )
        return ProbeAdaptationResult(
            adapted_model_state_id="beneficiary:x:adapted",
            adapted_checkpoint_hash="checkpoint:x:adapted",
            base_model_state_id=beneficiary_model_state_id,
            base_checkpoint_hash=beneficiary_checkpoint_hash,
            optimizer_contract_id=optimizer_contract.contract_id,
            initial_optimizer_state_hash=initial_hash,
            executed_step_count=optimizer_contract.step_count,
        )


@dataclass
class _InterventionRuntime(ContributionInterventionRuntimeProtocol):
    intervention_contract: object
    evaluated_with: list[tuple[str, ...]] = field(default_factory=list)
    evaluated_checkpoints: list[str] = field(default_factory=list)
    training_inputs: list[tuple[tuple[str, ...], tuple[str, ...]]] = field(default_factory=list)

    def evaluate(
        self,
        model_state_id: str,
        checkpoint_hash: str,
        instance_ids: tuple[str, ...],
        metric_contract: ContributionMetricContract,
    ) -> float:
        self.evaluated_with.append(instance_ids)
        self.evaluated_checkpoints.append(checkpoint_hash)
        return 0.5 if model_state_id == "beneficiary:x" else 0.55

    def retrain_with_intervention(
        self,
        beneficiary_model_state_id: str,
        beneficiary_checkpoint_hash: str,
        baseline_training_instance_ids: tuple[str, ...],
        added_instance_ids: tuple[str, ...],
        retraining_protocol_hash: str,
        seed: int,
    ) -> InterventionTrainingResult:
        self.training_inputs.append((baseline_training_instance_ids, added_instance_ids))
        return InterventionTrainingResult(
            intervention_model_state_id="beneficiary:x:intervention",
            intervention_checkpoint_hash="checkpoint:x:intervention",
            base_model_state_id=beneficiary_model_state_id,
            base_checkpoint_hash=beneficiary_checkpoint_hash,
            retraining_protocol_hash=retraining_protocol_hash,
            baseline_training_set_id="train:x",
        )


def _accepted_validity(state_id: str) -> StateValidityEstimate:
    thresholds = ValidityThresholds(reject_below=0.2, accept_at_or_above=0.8)
    values = {
        "task_condition_id": "task:x",
        "state_id": state_id,
        "attempted_trajectory_count": 1,
        "valid_trajectory_count": 1,
        "estimated_validity": 1.0,
        "confidence_lower": 0.5,
        "confidence_upper": 1.0,
        "mean_component_validity": {"independent_verifier": 1.0},
        "thresholds": thresholds,
        "classification_statistic": "posterior_mean",
        "region": validity_region(1.0, thresholds),
        "estimator_id": "test",
        "estimator_version": "1.0.0",
    }
    provisional = StateValidityEstimate.model_construct(estimate_id="pending", **values)
    return StateValidityEstimate(
        estimate_id=state_validity_estimate_id(provisional),
        **values,
    )


def _production_authorization(
    manifest: ContributionEstimationManifest,
):
    def evidence(role: str):
        return make_contribution_rank_validation_evidence(
            evaluation_role=role,
            macro_task_spearman=0.8,
            macro_task_spearman_ci95=(0.2, 0.95),
            macro_pairwise_concordance=0.8,
            macro_pairwise_concordance_ci95=(0.6, 0.95),
            winner_agreement_rate=0.8,
            macro_spearman_p_value=0.01,
            macro_pairwise_concordance_p_value=0.01,
        )

    task_condition_ids = (
        manifest.task_condition_id,
        *(f"task:authorized:{index}" for index in range(29)),
    )
    task_distribution_hashes = {
        task_id: (
            contribution_current_distribution_hash(
                manifest.task_condition_id,
                {item.state_id: item.current_probability for item in manifest.estimates},
            )
            if task_id == manifest.task_condition_id
            else f"test-current-distribution:{task_id}"
        )
        for task_id in task_condition_ids
    }
    return make_contribution_production_authorization(
        manifest=manifest,
        analysis_version="test_contribution_validation.v1",
        analysis_report_hash="test-contribution-report:passed",
        task_condition_ids=task_condition_ids,
        task_distribution_hashes=task_distribution_hashes,
        task_count=30,
        state_count=60,
        internal_validation_record_count=10,
        final_test_record_count=10,
        estimation_seed_count=2,
        validation_seed_count=2,
        intervention_seed_count=2,
        cross_seed_stability=evidence("cross_seed_stability"),
        independent_final_test=evidence("independent_final_test"),
        heldout_final_test=evidence("heldout_final_test"),
    )
