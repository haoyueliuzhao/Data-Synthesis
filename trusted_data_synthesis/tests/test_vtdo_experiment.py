from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.core.vtdo import (
    InterventionTrainingResult,
    ProbeAdaptationResult,
    empty_optimizer_state_hash,
    make_contribution_data_isolation_contract,
    make_contribution_intervention_observation,
    make_contribution_intervention_protocol,
    make_contribution_metric_contract,
    make_contribution_probe_observation,
    make_contribution_probe_protocol,
    make_probe_optimizer_contract,
)
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.vtdo_experiment.contribution_validation import (
    run_contribution_validation,
)
from trusted_synthesis.experiments.vtdo_experiment.dynamics import (
    _controlled_round_dynamics,
    run_refinement_dynamics_experiment,
)
from trusted_synthesis.experiments.vtdo_experiment.evaluation import (
    BENCHMARK_ADAPTER_VERSION,
    BENCHMARK_METRIC_VERSION,
    BenchmarkPrediction,
    benchmark_prediction_id,
    benchmark_snapshot_manifest_hash,
    evaluate_external_benchmark_predictions,
    load_benchmark_examples,
)
from trusted_synthesis.experiments.vtdo_experiment.moving_potential import (
    run_moving_potential_tracking_experiment,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceMultiStateConfig,
    _build_task_artifact,
    _quotient_probe,
)
from trusted_synthesis.experiments.vtdo_experiment.render import _format_optional_float
from trusted_synthesis.experiments.vtdo_experiment.schema import (
    ContributionValidationConfig,
    ContributionValidationObservation,
    ExternalBenchmarkSnapshot,
    MovingPotentialBenchmarkConfig,
    RefinementDynamicsConfig,
    SyntheticExperimentConfig,
    TrainingArmCapacity,
    TrainingExperimentConfig,
    TrainingExperimentPreflight,
    VTDOExperimentConfig,
    VTDOStudentTrainingConfig,
    contribution_validation_observation_id,
    training_experiment_preflight_hash,
)
from trusted_synthesis.experiments.vtdo_experiment.synthetic import (
    run_synthetic_experiment,
)
from trusted_synthesis.experiments.vtdo_experiment.training import (
    _component_arm,
    _external_benchmark_status,
    _host_instrumented_target,
    _vtdo_arm,
    build_refinement_checkpoint_training_arms,
    build_training_experiment_preflight,
    train_vtdo_arm,
)
from trusted_synthesis.hashing import canonical_hash


def test_synthetic_protocol_centers_contribution_and_separates_ablations() -> None:
    config = SyntheticExperimentConfig(state_count=20, rounds=2, seeds=(7,))
    first, catalogs, first_phase = run_synthetic_experiment(
        config,
        experiment_id="test_vtdo",
    )
    second, second_catalogs, second_phase = run_synthetic_experiment(
        config,
        experiment_id="test_vtdo",
    )

    assert first == second
    assert catalogs == second_catalogs
    assert first_phase == second_phase
    assert {item.method for item in first.main_method_summaries} == {
        "random",
        "contribution_only",
        "novelty_only",
        "ccgr",
        "full_vtdo",
    }
    assert {item.method for item in first.ablation_summaries} == {
        "no_global_coverage_anchor",
        "no_coverage_prior",
        "no_iteration",
        "no_quotient_exact",
        "no_quotient_noisy",
    }
    accepted = [item for item in catalogs[7] if item.validity_region == "accepted"]
    total = sum(item.initial_probability for item in accepted)
    centered_mean = sum(
        item.initial_probability / total * item.true_contribution for item in accepted
    )
    assert centered_mean == pytest.approx(0.0, abs=1e-12)
    assert "initial_fixed_target_diagnostic" in first.reference_definitions
    assert all(item.coverage_alignment > 0 for item in first.metric_points)
    assert "contribution_oracle" not in first.model_dump_json()


def test_synthetic_config_rejects_removed_legacy_fields() -> None:
    for field in ("oracle_temperature", "contribution_oracle_temperature", "anchor_sensitivity"):
        with pytest.raises(ValueError, match=field):
            SyntheticExperimentConfig.model_validate({"state_count": 20, "rounds": 2, field: 1.0})


def test_fixed_potential_operator_verifies_theoretical_contraction() -> None:
    synthetic_config = SyntheticExperimentConfig(state_count=20, rounds=5, seeds=(7, 13))
    synthetic, catalogs, phase_rows = run_synthetic_experiment(
        synthetic_config,
        experiment_id="test_refinement_dynamics",
    )
    execution = run_refinement_dynamics_experiment(
        RefinementDynamicsConfig(
            analysis_rounds=5,
            checkpoint_rounds=(1, 3, 5),
            primary_training_round=3,
            fixed_potential_rounds=6,
        ),
        synthetic_config,
        synthetic,
        catalogs,
        phase_rows,
        experiment_id="test_refinement_dynamics",
    )

    contraction = execution.report.fixed_potential_contraction
    assert contraction.projective_contraction_verified
    assert contraction.observed_projective_contraction_factor.mean == pytest.approx(
        contraction.history_exponent,
        abs=1e-10,
    )
    assert contraction.final_projective_distance.mean < contraction.initial_projective_distance.mean
    assert not execution.report.strict_convergence_claim_supported


def test_moving_potential_tracks_optimum_and_improves_variational_objective() -> None:
    execution = run_moving_potential_tracking_experiment(
        MovingPotentialBenchmarkConfig(rounds=3),
        SyntheticExperimentConfig(state_count=20, rounds=3, seeds=tuple(range(10))),
        experiment_id="test_moving_potential",
    )

    assert execution.summary.status == "passed"
    assert execution.summary.track == "exogenous_shared"
    assert execution.summary.is_primary_track
    assert execution.summary.variational_objective.transition_count == 30
    assert execution.summary.variational_objective.all_transitions_verified
    assert execution.summary.optimization_direction_supported
    summaries = {item.method: item for item in execution.summary.method_summaries}
    assert summaries["full_vtdo"].cumulative_regret.mean < (
        summaries["static_optimization"].cumulative_regret.mean
    )
    assert summaries["full_vtdo"].mean_tracking_error.mean < (
        summaries["no_feedback"].mean_tracking_error.mean
    )


def test_practical_stabilization_uses_combined_score_for_consecutive_rounds() -> None:
    synthetic_config = SyntheticExperimentConfig(state_count=20, rounds=3, seeds=(7,))
    report, _, phase_rows = run_synthetic_experiment(
        synthetic_config,
        experiment_id="test_stability",
    )
    config = RefinementDynamicsConfig(
        analysis_rounds=3,
        checkpoint_rounds=(1, 3),
        primary_training_round=3,
        stabilization_score_threshold=100.0,
        utility_delta_weight=1.0,
        fixed_potential_rounds=3,
        moving_potential_benchmark=MovingPotentialBenchmarkConfig(rounds=3),
    )
    _, summary = _controlled_round_dynamics(
        config,
        report,
        phase_rows,
    )
    assert summary.first_stable_round_by_seed == {"7": 3}
    assert summary.criterion_id == "distribution_stabilization_consecutive_rounds"


def test_real_round_analysis_fails_closed_for_missing_artifact(tmp_path: Path) -> None:
    synthetic_config = SyntheticExperimentConfig(state_count=20, rounds=2, seeds=(7,))
    synthetic, catalogs, phase_rows = run_synthetic_experiment(
        synthetic_config,
        experiment_id="test_missing_real_round",
    )
    execution = run_refinement_dynamics_experiment(
        RefinementDynamicsConfig(
            analysis_rounds=2,
            checkpoint_rounds=(1, 2),
            primary_training_round=2,
            fixed_potential_rounds=2,
            moving_potential_benchmark=MovingPotentialBenchmarkConfig(rounds=2),
            real_round_artifact_paths=(tmp_path / "missing.jsonl",),
            expected_real_task_condition_ids=("task:missing",),
        ),
        synthetic_config,
        synthetic,
        catalogs,
        phase_rows,
        experiment_id="test_missing_real_round",
    )
    assert execution.report.real_refinement.status == "blocked"
    assert any(
        item.startswith("missing_round_artifact_source:")
        for item in execution.report.real_refinement.blockers
    )


def test_experiment_config_rejects_legacy_real_state_section(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="real_state"):
        VTDOExperimentConfig.model_validate(
            {
                "synthetic": {"state_count": 20, "rounds": 3, "seeds": [7]},
                "multi_state": {
                    "finance_archive_config_path": str(tmp_path / "finance.json"),
                    "task_count": 1,
                },
                "training": {"training_config_path": str(tmp_path / "student.json")},
                "real_state": {"agent_artifact_dir": str(tmp_path)},
                "refinement_dynamics": {
                    "analysis_rounds": 3,
                    "checkpoint_rounds": [1, 3],
                    "primary_training_round": 3,
                    "moving_potential_benchmark": {"rounds": 3},
                },
                "output_dir": str(tmp_path / "output"),
            }
        )


def test_finance_fixture_produces_five_verified_states_and_rejects_mutation(
    tmp_path: Path,
) -> None:
    artifact = _build_task_artifact(
        build_finance_counterfactual_case(4),
        FinanceMultiStateConfig(
            finance_archive_config_path=tmp_path / "unused.json",
            task_count=1,
        ),
    )

    assert len(artifact.accepted_states) == 5
    assert artifact.strategy_attempt_count == 5
    assert artifact.strategy_verifier_pass_count == 5
    assert len({item.assignment.state.state_id for item in artifact.accepted_states}) == 5
    assert not artifact.rejected_attempts[0].validity_report.valid
    assert not artifact.program_diversity_claimed
    assert artifact.omega.oracle_specification is not None
    quotient = _quotient_probe([artifact])
    assert quotient["surface_invariance_rate"] == pytest.approx(1.0)
    assert quotient["independent_order_invariance_rate"] == pytest.approx(1.0)
    assert quotient["semantic_separation_rate"] == pytest.approx(1.0)
    assert quotient["false_merge_count"] == 0

    host_target = json.loads(_host_instrumented_target(artifact.accepted_states[0].trajectory))
    assert host_target["contract"] == "host_instrumented_decisions.v1"
    assert "observation" not in json.dumps(host_target)
    assert "rationale_summary" not in json.dumps(host_target)


def _write_contribution_observations(
    path: Path,
    *,
    reverse_outcomes: bool = False,
    identity_mismatch: bool = False,
) -> None:
    observations: list[ContributionValidationObservation] = []
    seeds = (7, 13, 19)
    for task_index in range(3):
        task_id = f"task:{task_index:03d}"
        state_ids = tuple(f"state:{index:03d}" for index in range(3))
        data_isolation = make_contribution_data_isolation_contract(
            task_condition_id=task_id,
            baseline_training_set_id=f"train:{task_id}",
            baseline_training_instance_ids=tuple(f"{task_id}:train:{index}" for index in range(19)),
            probe_update_instance_ids_by_state={
                state_id: (f"{task_id}:probe:{state_id}",) for state_id in state_ids
            },
            internal_validation_set_id="finance_eval:v1",
            internal_validation_instance_ids=tuple(
                f"{task_id}:validation:{index}" for index in range(20)
            ),
            final_test_set_id=f"final-test:{task_id}",
            final_test_instance_ids=(f"{task_id}:final-test:0",),
        )
        metric = make_contribution_metric_contract(
            target_metric_id="answer_accuracy",
            evaluation_distribution_id="finance_eval:v1",
            evaluation_snapshot_hash="evaluation:snapshot:v1",
            score_transform="identity",
        )
        optimizer = make_probe_optimizer_contract(
            optimizer_name="sgd",
            learning_rate=1e-5,
            step_count=3,
        )
        for state_index, state_id in enumerate(state_ids):
            for seed in seeds:
                intervention_value = (
                    float(2 - state_index) if reverse_outcomes else float(state_index)
                )
                beneficiary = (
                    "qwen:mismatched"
                    if identity_mismatch
                    and task_index == 2
                    and state_index == 2
                    and seed == seeds[-1]
                    else "qwen:round0"
                )
                probe_contract = make_contribution_probe_protocol(
                    beneficiary_model_state_id=beneficiary,
                    beneficiary_checkpoint_hash=f"checkpoint:{beneficiary}",
                    metric_contract=metric,
                    data_isolation=data_isolation,
                    optimizer=optimizer,
                    probe_seeds=seeds,
                )
                intervention_contract = make_contribution_intervention_protocol(
                    beneficiary_model_state_id=beneficiary,
                    beneficiary_checkpoint_hash=f"checkpoint:{beneficiary}",
                    metric_contract=metric,
                    data_isolation=data_isolation,
                    retraining_protocol_hash="retraining:v1",
                    intervention_seeds=seeds,
                    target_epsilon=0.05,
                )
                probe = make_contribution_probe_observation(
                    task_condition_id=task_id,
                    round_index=0,
                    state_id=state_id,
                    protocol=probe_contract,
                    seed=seed,
                    adaptation_result=ProbeAdaptationResult(
                        adapted_model_state_id=f"{beneficiary}:probe:{task_id}:{state_id}:{seed}",
                        adapted_checkpoint_hash=f"checkpoint:{beneficiary}:probe:{task_id}:{state_id}:{seed}",
                        base_model_state_id=beneficiary,
                        base_checkpoint_hash=f"checkpoint:{beneficiary}",
                        optimizer_contract_id=optimizer.contract_id,
                        initial_optimizer_state_hash=empty_optimizer_state_hash(optimizer),
                        executed_step_count=optimizer.step_count,
                    ),
                    baseline_performance=0.0,
                    adapted_performance=float(state_index),
                )
                epsilon = 1.0 / 20.0
                intervention = make_contribution_intervention_observation(
                    task_condition_id=task_id,
                    round_index=0,
                    state_id=state_id,
                    protocol=intervention_contract,
                    seed=seed,
                    training_result=InterventionTrainingResult(
                        intervention_model_state_id=(
                            f"{beneficiary}:intervention:{task_id}:{state_id}:{seed}"
                        ),
                        intervention_checkpoint_hash=(
                            f"checkpoint:{beneficiary}:intervention:{task_id}:{state_id}:{seed}"
                        ),
                        base_model_state_id=beneficiary,
                        base_checkpoint_hash=f"checkpoint:{beneficiary}",
                        retraining_protocol_hash="retraining:v1",
                        baseline_training_set_id=f"train:{task_id}",
                    ),
                    baseline_performance=0.0,
                    intervention_performance=epsilon * intervention_value,
                )
                values = {
                    "task_condition_id": task_id,
                    "round_index": 0,
                    "state_id": state_id,
                    "seed": seed,
                    "baseline_distribution_id": f"baseline:{task_id}",
                    "probe_observation": probe,
                    "intervention_observation": intervention,
                    "schema_version": "contribution_validation_observation.v6",
                }
                provisional = ContributionValidationObservation.model_construct(
                    observation_id="pending",
                    **values,
                )
                observations.append(
                    ContributionValidationObservation(
                        observation_id=contribution_validation_observation_id(provisional),
                        **values,
                    )
                )
    path.write_text(
        "".join(item.model_dump_json() + "\n" for item in observations),
        encoding="utf-8",
    )


def _contribution_config(path: Path) -> ContributionValidationConfig:
    return ContributionValidationConfig(
        observation_path=path,
        minimum_observation_count=27,
        minimum_unique_task_count=3,
        minimum_states_per_task=3,
        minimum_seeds_per_state=3,
        minimum_macro_spearman_ci_lower_bound=0.2,
        minimum_pairwise_concordance_ci_lower_bound=0.55,
        cluster_bootstrap_samples=100,
    )


def test_contribution_validation_reports_within_task_rank_signal(tmp_path: Path) -> None:
    path = tmp_path / "contribution.jsonl"
    _write_contribution_observations(path)
    report = run_contribution_validation(_contribution_config(path))
    assert report.status == "passed"
    assert report.paired_seed_count == 3
    assert report.aggregated_state_count == 9
    assert report.task_rank_correlation is not None
    assert report.task_rank_correlation.mean == pytest.approx(1.0)
    assert report.centered_global_spearman == pytest.approx(1.0)
    assert report.pairwise_concordance_rate == pytest.approx(1.0)
    assert report.sign_agreement_rate == pytest.approx(1.0)


def test_contribution_validation_clusters_multiple_rounds_by_task(tmp_path: Path) -> None:
    path = tmp_path / "multi_round_contribution.jsonl"
    _write_contribution_observations(path)
    first_round = [
        ContributionValidationObservation.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    second_round = []
    for item in first_round:
        probe = make_contribution_probe_observation(
            task_condition_id=item.task_condition_id,
            round_index=1,
            state_id=item.state_id,
            protocol=item.probe_observation.probe_contract,
            seed=item.seed,
            adaptation_result=item.probe_observation.adaptation_result.model_copy(
                update={
                    "adapted_model_state_id": (
                        item.probe_observation.adaptation_result.adapted_model_state_id + ":round1"
                    ),
                    "adapted_checkpoint_hash": (
                        item.probe_observation.adaptation_result.adapted_checkpoint_hash + ":round1"
                    ),
                }
            ),
            baseline_performance=item.probe_observation.baseline_performance,
            adapted_performance=item.probe_observation.adapted_performance,
        )
        intervention = make_contribution_intervention_observation(
            task_condition_id=item.task_condition_id,
            round_index=1,
            state_id=item.state_id,
            protocol=item.intervention_observation.intervention_contract,
            seed=item.seed,
            training_result=item.intervention_observation.training_result.model_copy(
                update={
                    "intervention_model_state_id": (
                        item.intervention_observation.training_result.intervention_model_state_id
                        + ":round1"
                    ),
                    "intervention_checkpoint_hash": (
                        item.intervention_observation.training_result.intervention_checkpoint_hash
                        + ":round1"
                    ),
                }
            ),
            baseline_performance=item.intervention_observation.baseline_performance,
            intervention_performance=item.intervention_observation.intervention_performance,
        )
        values = {
            "task_condition_id": item.task_condition_id,
            "round_index": 1,
            "state_id": item.state_id,
            "seed": item.seed,
            "baseline_distribution_id": f"baseline:{item.task_condition_id}:round1",
            "probe_observation": probe,
            "intervention_observation": intervention,
            "schema_version": "contribution_validation_observation.v6",
        }
        provisional = ContributionValidationObservation.model_construct(
            observation_id="pending",
            **values,
        )
        second_round.append(
            ContributionValidationObservation(
                observation_id=contribution_validation_observation_id(provisional),
                **values,
            )
        )
    path.write_text(
        "".join(item.model_dump_json() + "\n" for item in (*first_round, *second_round)),
        encoding="utf-8",
    )

    report = run_contribution_validation(_contribution_config(path))

    assert report.status == "passed"
    assert report.unique_round_count == 2
    assert report.unique_task_round_count == 6
    assert report.eligible_task_round_count == 6
    assert report.task_rank_correlation is not None
    assert report.task_rank_correlation.sample_count == 3


def test_contribution_validation_rejects_reused_artifact_across_rounds(
    tmp_path: Path,
) -> None:
    path = tmp_path / "reused_contribution.jsonl"
    _write_contribution_observations(path)
    first = ContributionValidationObservation.model_validate_json(
        path.read_text(encoding="utf-8").splitlines()[0]
    )
    probe = make_contribution_probe_observation(
        task_condition_id=first.task_condition_id,
        round_index=1,
        state_id=first.state_id,
        protocol=first.probe_observation.probe_contract,
        seed=first.seed,
        adaptation_result=first.probe_observation.adaptation_result,
        baseline_performance=first.probe_observation.baseline_performance,
        adapted_performance=first.probe_observation.adapted_performance,
    )
    intervention = make_contribution_intervention_observation(
        task_condition_id=first.task_condition_id,
        round_index=1,
        state_id=first.state_id,
        protocol=first.intervention_observation.intervention_contract,
        seed=first.seed,
        training_result=first.intervention_observation.training_result,
        baseline_performance=first.intervention_observation.baseline_performance,
        intervention_performance=first.intervention_observation.intervention_performance,
    )
    values = {
        "task_condition_id": first.task_condition_id,
        "round_index": 1,
        "state_id": first.state_id,
        "seed": first.seed,
        "baseline_distribution_id": f"baseline:{first.task_condition_id}:round1",
        "probe_observation": probe,
        "intervention_observation": intervention,
        "schema_version": "contribution_validation_observation.v6",
    }
    provisional = ContributionValidationObservation.model_construct(
        observation_id="pending",
        **values,
    )
    reused = ContributionValidationObservation(
        observation_id=contribution_validation_observation_id(provisional),
        **values,
    )
    with path.open("a", encoding="utf-8") as output:
        output.write(reused.model_dump_json() + "\n")

    report = run_contribution_validation(_contribution_config(path))

    assert report.status == "blocked"
    assert any(
        blocker.startswith("contribution_trained_artifact_reused:") for blocker in report.blockers
    )


def test_contribution_validation_rejects_negative_rank_signal(tmp_path: Path) -> None:
    path = tmp_path / "negative_contribution.jsonl"
    _write_contribution_observations(path, reverse_outcomes=True)
    report = run_contribution_validation(_contribution_config(path))
    assert report.status == "blocked"
    assert report.task_rank_correlation is not None
    assert report.task_rank_correlation.mean == pytest.approx(-1.0)
    assert any("macro_spearman_ci_lower_bound_below_threshold" in item for item in report.blockers)


def test_contribution_validation_rejects_identity_drift(tmp_path: Path) -> None:
    path = tmp_path / "identity_drift.jsonl"
    _write_contribution_observations(path, identity_mismatch=True)
    report = run_contribution_validation(_contribution_config(path))
    assert report.status == "blocked"
    assert "contribution_probe_contract_not_frozen:task:002|round=0" in report.blockers
    assert "contribution_intervention_contract_not_frozen:task:002|round=0" in report.blockers


def test_report_formats_missing_contribution_variance_as_not_available() -> None:
    assert _format_optional_float(None) == "n/a"
    assert _format_optional_float(0.125) == "0.125"


def test_training_preflight_uses_new_state_artifacts_and_blocks_missing_b3_b5(
    tmp_path: Path,
) -> None:
    artifact = _build_task_artifact(
        build_finance_counterfactual_case(4),
        FinanceMultiStateConfig(
            finance_archive_config_path=tmp_path / "unused.json",
            task_count=1,
        ),
    )
    student = VTDOStudentTrainingConfig(
        base_model="Qwen/Qwen2.5-7B-Instruct",
        model_revision="a" * 40,
        supervised_token_budget=10_000,
    )
    student_path = tmp_path / "student.json"
    student_path.write_text(student.model_dump_json(), encoding="utf-8")
    preflight, arms, leakage = build_training_experiment_preflight(
        TrainingExperimentConfig(
            enabled=True,
            training_config_path=student_path,
            target_supervised_tokens=10_000,
            minimum_unique_tasks_per_arm=1,
            minimum_unique_states_per_arm=1,
            gpu_ids=(0,),
            seeds=(student.seed, student.seed + 1, student.seed + 2),
        ),
        artifacts=(artifact,),
        vtdo_round_artifact_paths=(),
        primary_training_round=3,
    )

    assert len(arms["B1_raw"]) == 6
    assert len(arms["B2_validity"]) == 5
    assert not arms["B2_contribution_only"]
    assert not arms["B2_novelty_only"]
    assert len(arms["B4_random_state"]) == 1
    assert not arms["B3_ccgr"]
    assert not arms["B5_vtdo"]
    assert preflight.permitted_arm_ids == ()
    assert "external_benchmarks:not_configured" in preflight.shared_training_blockers
    assert not preflight.primary_causal_training_ready
    assert not preflight.full_comparison_matrix_ready
    assert preflight.training_seeds == (student.seed, student.seed + 1, student.seed + 2)
    assert leakage.status == "not_configured"
    capacities = {item.arm_id: item for item in preflight.arms}
    for arm_id in ("B1_raw", "B2_validity", "B4_random_state"):
        assert capacities[arm_id].task_marginal_verified
        assert capacities[arm_id].minimum_task_weight == pytest.approx(1.0)
        assert capacities[arm_id].maximum_task_weight == pytest.approx(1.0)
    assert any("ccgr_task_distribution_not_configured" in item for item in preflight.blockers)


def test_training_benchmark_contract_requires_finqa_and_tatqa(
    tmp_path: Path,
) -> None:
    benchmark_path = tmp_path / "benchmark.json"
    benchmark_path.write_text("[]", encoding="utf-8")
    digest = hashlib.sha256(benchmark_path.read_bytes()).hexdigest()

    def snapshot(benchmark_id: str) -> ExternalBenchmarkSnapshot:
        return ExternalBenchmarkSnapshot(
            benchmark_id=benchmark_id,
            path=benchmark_path,
            sha256=digest,
            source_repository=f"official/{benchmark_id}",
            source_revision="a" * 40,
            split="test",
            adapter_version=BENCHMARK_ADAPTER_VERSION,
            metric_version=BENCHMARK_METRIC_VERSION,
        )

    complete = TrainingExperimentConfig(
        training_config_path=tmp_path / "student.json",
        external_benchmarks=(snapshot("finqa"), snapshot("tat_qa")),
    )
    status, blockers = _external_benchmark_status(complete)
    assert status == "ready"
    assert not blockers

    with_optional = complete.model_copy(
        update={
            "external_benchmarks": (
                *complete.external_benchmarks,
                snapshot("financebench"),
            )
        }
    )
    status, blockers = _external_benchmark_status(with_optional)
    assert status == "ready"
    assert not blockers

    incomplete = complete.model_copy(update={"external_benchmarks": (snapshot("finqa"),)})
    status, blockers = _external_benchmark_status(incomplete)
    assert status == "not_available"
    assert blockers and blockers[0].startswith("required_external_benchmark_missing:")


def test_refinement_checkpoint_training_fails_closed_without_round_artifacts(
    tmp_path: Path,
) -> None:
    artifact = _build_task_artifact(
        build_finance_counterfactual_case(4),
        FinanceMultiStateConfig(
            finance_archive_config_path=tmp_path / "unused.json",
            task_count=1,
        ),
    )

    arms, blockers = build_refinement_checkpoint_training_arms(
        (),
        (artifact,),
        (1, 3, 5),
    )

    assert arms == {}
    assert blockers == ("vtdo_round_artifacts_not_configured",)


def test_vtdo_and_component_arms_use_the_explicit_selected_round(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _build_task_artifact(
        build_finance_counterfactual_case(4),
        FinanceMultiStateConfig(
            finance_archive_config_path=tmp_path / "unused.json",
            task_count=1,
        ),
    )
    state_ids = tuple(sorted(item.assignment.state.state_id for item in artifact.accepted_states))

    def fake_round(round_index: int, prior_id: str, next_id: str):
        current = {state_id: 1.0 / len(state_ids) for state_id in state_ids}
        next_probabilities = {
            state_id: (index + round_index + 1) for index, state_id in enumerate(state_ids)
        }
        total = sum(next_probabilities.values())
        normalized_next = {
            state_id: value / total for state_id, value in next_probabilities.items()
        }
        potentials = tuple(
            SimpleNamespace(
                state_id=state_id,
                current_probability=current[state_id],
                coverage_probability=current[state_id],
                normalized_contribution=0.1 + 0.1 * index,
                normalized_novelty=0.9 - 0.1 * index,
            )
            for index, state_id in enumerate(state_ids)
        )
        return SimpleNamespace(
            task_condition_id=artifact.state_catalog.task_condition_id,
            round_index=round_index,
            round_id=f"round:{round_index}",
            exploration=SimpleNamespace(
                training_distribution=SimpleNamespace(distribution_id=prior_id)
            ),
            update=SimpleNamespace(
                next_distribution=SimpleNamespace(
                    distribution_id=next_id,
                    probabilities=normalized_next,
                ),
                history_exponent=0.5,
                energy_exponent=0.5,
                state_potentials=potentials,
            ),
        )

    rounds = (
        fake_round(0, "distribution:0", "distribution:1"),
        fake_round(1, "distribution:1", "distribution:2"),
        fake_round(2, "distribution:2", "distribution:3"),
    )
    monkeypatch.setattr(
        "trusted_synthesis.experiments.vtdo_experiment.training.load_vtdo_round_artifacts",
        lambda paths: (rounds, ()),
    )
    round_one, blockers = _vtdo_arm(
        (tmp_path,),
        (artifact,),
        selected_round=1,
    )
    assert not blockers
    round_three, blockers = _vtdo_arm(
        (tmp_path,),
        (artifact,),
        selected_round=3,
    )
    assert not blockers
    assert {item.source_distribution_id for item in round_one} == {"distribution:1"}
    assert {item.source_distribution_id for item in round_three} == {"distribution:3"}
    assert {item.metadata["selected_training_round"] for item in round_three} == {3}

    for arm_id, component in (
        ("B2_contribution_only", "contribution"),
        ("B2_novelty_only", "novelty"),
    ):
        records, blockers = _component_arm(
            (tmp_path,),
            (artifact,),
            selected_round=3,
            arm_id=arm_id,
            component=component,
        )
        assert not blockers
        assert sum(item.sampling_weight for item in records) == pytest.approx(1.0)
        assert {item.metadata["selected_training_round"] for item in records} == {3}


def test_vtdo_arm_training_fails_before_model_loading(tmp_path: Path) -> None:
    student = VTDOStudentTrainingConfig(
        base_model="Qwen/Qwen2.5-7B-Instruct",
        model_revision="a" * 40,
        supervised_token_budget=10_000,
    )
    student_path = tmp_path / "student.json"
    student_path.write_text(student.model_dump_json(), encoding="utf-8")
    arm = TrainingArmCapacity(
        arm_id="B5_vtdo",
        source_record_count=0,
        unique_task_count=0,
        unique_state_count=0,
        multi_state_task_count=0,
        maximum_states_per_task=0,
        accepted_only=True,
        comparison_role="primary_fixed_task_marginal",
        task_marginal_policy="uniform_fixed",
        minimum_task_weight=0.0,
        maximum_task_weight=0.0,
        maximum_task_weight_deviation=0.0,
        task_marginal_verified=False,
        requested_supervised_tokens=10_000,
        capacity_status="blocked",
        blockers=("no_materializable_records",),
    )
    values = {
        "training_config_hash": student.config_hash,
        "base_model": student.base_model,
        "model_revision": student.model_revision,
        "supervised_token_budget": student.supervised_token_budget,
        "training_seeds": (student.seed, student.seed + 1, student.seed + 2),
        "arms": (arm,),
        "primary_causal_arms": ("B2_validity", "B4_random_state", "B5_vtdo"),
        "secondary_comparison_arms": ("B1_raw", "B3_ccgr"),
        "primary_task_marginal_contract_verified": False,
        "primary_causal_training_ready": False,
        "full_comparison_matrix_ready": False,
        "permitted_arm_ids": (),
        "external_benchmark_status": "not_configured",
        "benchmark_leakage_status": "not_configured",
        "benchmark_leakage_count": 0,
        "benchmark_leakage_report_hash": None,
        "shared_training_blockers": (),
        "primary_causal_blockers": ("B5_vtdo:no_materializable_records",),
        "secondary_comparison_blockers": (),
        "blockers": ("B5_vtdo:no_materializable_records",),
        "schema_version": "vtdo_experiment.v6",
    }
    provisional = TrainingExperimentPreflight.model_construct(
        **values,
        report_hash="pending",
    )
    preflight = TrainingExperimentPreflight(
        **values,
        report_hash=training_experiment_preflight_hash(provisional),
    )
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(preflight.model_dump_json(), encoding="utf-8")
    manifest_path = tmp_path / "arm_hashes.json"
    manifest_path.write_text(json.dumps({}), encoding="utf-8")
    dataset_path = tmp_path / "B5_vtdo.jsonl"
    dataset_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="arm is not permitted by the frozen preflight"):
        train_vtdo_arm(
            student_config_path=student_path,
            preflight_path=preflight_path,
            arm_manifest_path=manifest_path,
            arm_id="B5_vtdo",
            dataset_path=dataset_path,
            output_dir=tmp_path / "adapter",
            training_seed=student.seed,
        )


def test_external_benchmark_adapters_and_evaluator(tmp_path: Path) -> None:
    payloads = {
        "finqa": [
            {
                "pre_text": ["The filing reports two components."],
                "table": [["component", "value"], ["A", "2"], ["B", "2"]],
                "post_text": ["Both values use the same scale."],
                "qa": {
                    "id": "f1",
                    "question": "What is the sum of A and B?",
                    "exe_ans": "4",
                    "program": ["add(2, 2)"],
                },
            }
        ],
        "tat_qa": [
            {
                "table": {"table": [["metric", "value"], ["revenue", "10"]]},
                "paragraphs": [{"text": "Revenue was reported without a scale."}],
                "questions": [
                    {
                        "uid": "t1",
                        "question": "What is revenue?",
                        "answer": "10",
                        "scale": "",
                        "answer_type": "span",
                    }
                ],
            }
        ],
        "financebench": [
            {"id": "b1", "question": "What is cash?", "answer": "5", "context": "Cash is 5."}
        ],
    }
    snapshots = []
    for benchmark_id, payload in payloads.items():
        path = tmp_path / f"{benchmark_id}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        snapshots.append(
            ExternalBenchmarkSnapshot(
                benchmark_id=benchmark_id,
                path=path,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                source_repository=f"official/{benchmark_id}",
                source_revision="a" * 40,
                split="test",
                adapter_version=BENCHMARK_ADAPTER_VERSION,
                metric_version=BENCHMARK_METRIC_VERSION,
            )
        )
    typed_snapshots = tuple(snapshots)
    examples = load_benchmark_examples(typed_snapshots)
    assert len(examples) == 3
    assert all("Context:" in item.prompt for item in examples)
    assert "component" in next(item.prompt for item in examples if item.benchmark_id == "finqa")
    predictions = tmp_path / "predictions.jsonl"
    answers = {"finqa": "4", "tat_qa": "10", "financebench": "5"}
    run_id = "benchmark_prediction_run:test"
    prediction_values = []
    for item in examples:
        values = {
            "prediction_run_id": run_id,
            "benchmark_id": item.benchmark_id,
            "example_id": item.example_id,
            "answer": answers[item.benchmark_id],
            "scale": "",
            "program": "add(2, 2)" if item.benchmark_id == "finqa" else "",
            "contract_success": True,
            "raw_response_hash": canonical_hash(
                answers[item.benchmark_id],
                prefix="benchmark_raw_response:",
            ),
        }
        provisional = BenchmarkPrediction.model_construct(
            prediction_id="pending",
            **values,
        )
        prediction_values.append(
            BenchmarkPrediction(
                prediction_id=benchmark_prediction_id(provisional),
                **values,
            )
        )
    predictions.write_text(
        "".join(item.model_dump_json() + "\n" for item in prediction_values),
        encoding="utf-8",
    )
    prediction_manifest = tmp_path / "prediction_manifest.json"
    prediction_manifest.write_text(
        json.dumps(
            {
                "prediction_run_id": run_id,
                "predictions_sha256": hashlib.sha256(predictions.read_bytes()).hexdigest(),
                "evaluation_snapshot_hash": benchmark_snapshot_manifest_hash(typed_snapshots),
            }
        ),
        encoding="utf-8",
    )
    report = evaluate_external_benchmark_predictions(
        typed_snapshots,
        predictions,
        prediction_manifest,
    )
    assert report.status == "blocked"
    assert "benchmark_prediction_manifest_invalid_or_incomplete" in report.blockers
