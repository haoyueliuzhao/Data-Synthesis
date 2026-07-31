from __future__ import annotations

import json
from pathlib import Path

import pytest

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
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceMultiStateConfig,
    _build_task_artifact,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import (
    ContributionValidationConfig,
    ContributionValidationObservation,
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
    build_training_experiment_preflight,
    train_vtdo_arm,
)


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
        "no_anchor",
        "no_iteration",
        "no_quotient",
    }
    accepted = [item for item in catalogs[7] if item.validity_region == "accepted"]
    total = sum(item.initial_probability for item in accepted)
    centered_mean = sum(
        item.initial_probability / total * item.true_contribution for item in accepted
    )
    assert centered_mean == pytest.approx(0.0, abs=1e-12)
    assert "fixed_potential_vtdo_optimum" in first.reference_definitions
    assert all(item.coverage_alignment > 0 for item in first.metric_points)
    assert "contribution_oracle" not in first.model_dump_json()


def test_synthetic_config_rejects_removed_legacy_fields() -> None:
    for field in ("oracle_temperature", "contribution_oracle_temperature", "anchor_sensitivity"):
        with pytest.raises(ValueError, match=field):
            SyntheticExperimentConfig.model_validate({"state_count": 20, "rounds": 2, field: 1.0})


def test_fixed_potential_control_verifies_theoretical_contraction() -> None:
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


def test_practical_convergence_uses_combined_score_for_consecutive_rounds() -> None:
    synthetic_config = SyntheticExperimentConfig(state_count=20, rounds=3, seeds=(7,))
    report, _, _ = run_synthetic_experiment(
        synthetic_config,
        experiment_id="test_stability",
    )
    config = RefinementDynamicsConfig(
        analysis_rounds=3,
        checkpoint_rounds=(1, 3),
        primary_training_round=3,
        stabilization_score_threshold=0.01,
        utility_delta_weight=1.0,
        fixed_potential_rounds=3,
    )
    points = tuple(
        point.model_copy(
            update={
                "kl_to_previous": 0.004,
                "expected_contribution_novelty": 0.1,
            }
        )
        if point.method == "full_vtdo" and point.round_index > 0
        else point
        for point in report.metric_points
    )
    _, summary = _controlled_round_dynamics(
        config,
        report.model_copy(update={"metric_points": points}),
    )
    assert summary.convergence_round_by_seed == {"7": 3}
    assert summary.criterion_id == "combined_score_consecutive_rounds"


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
            real_round_artifact_paths=(tmp_path / "missing.jsonl",),
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


def test_contribution_validation_reports_empirical_spearman(tmp_path: Path) -> None:
    observations = []
    for index in range(100):
        values = {
            "task_condition_id": f"task:{index:03d}",
            "state_id": f"state:{index:03d}",
            "beneficiary_model_state_id": "qwen:round0",
            "evaluation_distribution_id": "finance_eval:v1",
            "target_metric_id": "answer_accuracy",
            "estimated_contribution": float(index),
            "observed_delta_j": float(index) * 0.5,
            "sample_count": 20,
            "schema_version": "contribution_validation_observation.v1",
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
    path = tmp_path / "contribution.jsonl"
    path.write_text(
        "".join(item.model_dump_json() + "\n" for item in observations),
        encoding="utf-8",
    )
    report = run_contribution_validation(ContributionValidationConfig(observation_path=path))
    assert report.status == "passed"
    assert report.spearman_correlation == pytest.approx(1.0)
    assert report.sign_agreement_rate == pytest.approx(1.0)


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
    preflight, arms = build_training_experiment_preflight(
        TrainingExperimentConfig(
            enabled=True,
            training_config_path=student_path,
            target_supervised_tokens=10_000,
            minimum_unique_tasks_per_arm=1,
            minimum_unique_states_per_arm=1,
            gpu_ids=(0,),
            seeds=(student.seed,),
        ),
        artifacts=(artifact,),
        vtdo_round_artifact_paths=(),
    )

    assert len(arms["B1_raw"]) == 6
    assert len(arms["B2_validity"]) == 5
    assert len(arms["B4_random_state"]) == 1
    assert not arms["B3_ccgr"]
    assert not arms["B5_vtdo"]
    assert preflight.pilot_training_ready
    assert not preflight.formal_training_ready
    assert any("ccgr_task_distribution_not_configured" in item for item in preflight.blockers)


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
        requested_supervised_tokens=10_000,
        capacity_status="blocked",
        blockers=("no_materializable_records",),
    )
    values = {
        "training_config_hash": student.config_hash,
        "base_model": student.base_model,
        "model_revision": student.model_revision,
        "supervised_token_budget": student.supervised_token_budget,
        "training_seed": student.seed,
        "arms": (arm,),
        "formal_training_ready": False,
        "pilot_training_ready": False,
        "external_benchmark_status": "not_configured",
        "blockers": ("B5_vtdo:no_materializable_records",),
        "schema_version": "vtdo_experiment.v1",
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

    with pytest.raises(ValueError, match="formal training preflight is not ready"):
        train_vtdo_arm(
            student_config_path=student_path,
            preflight_path=preflight_path,
            arm_manifest_path=manifest_path,
            arm_id="B5_vtdo",
            dataset_path=dataset_path,
            output_dir=tmp_path / "adapter",
        )
