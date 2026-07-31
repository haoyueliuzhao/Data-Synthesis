from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.core.refinement.update import _entropy
from trusted_synthesis.experiments.training_utility_mvp.training import (
    _schedule_supervised_token_budget_with_exposures,
)
from trusted_synthesis.experiments.vtdo_validation.dynamics import (
    _controlled_round_dynamics,
    run_refinement_dynamics_experiment,
)
from trusted_synthesis.experiments.vtdo_validation.schema import (
    RealStateExperimentConfig,
    RefinementDynamicsConfig,
    SyntheticExperimentConfig,
    TrainingArmCapacity,
    TrainingExperimentConfig,
    TrainingExperimentPreflight,
    VTDOStudentTrainingConfig,
    VTDOValidationConfig,
    training_experiment_preflight_hash,
)
from trusted_synthesis.experiments.vtdo_validation.synthetic import (
    run_synthetic_experiment,
)
from trusted_synthesis.experiments.vtdo_validation.training import train_vtdo_arm


def test_synthetic_experiment_is_deterministic_and_uses_unambiguous_references() -> None:
    config = SyntheticExperimentConfig(state_count=20, rounds=2, seeds=(7,))

    first, first_states, first_phase = run_synthetic_experiment(
        config,
        experiment_id="test_vtdo",
    )
    second, second_states, second_phase = run_synthetic_experiment(
        config,
        experiment_id="test_vtdo",
    )

    assert first == second
    assert first_states == second_states
    assert first_phase == second_phase
    assert {item.method for item in first.method_summaries} == {
        "random",
        "novelty_only",
        "contribution_only",
        "no_anchor",
        "ccgr",
        "full_vtdo",
        "no_iteration",
        "no_quotient",
    }
    assert "regularized_contribution_oracle" in first.reference_definitions
    assert all(item.coverage_alignment > 0 for item in first.metric_points)
    assert "kl_to_oracle" not in first.model_dump_json()


def test_synthetic_config_rejects_ambiguous_legacy_oracle_field() -> None:
    with pytest.raises(ValueError, match="oracle_temperature"):
        SyntheticExperimentConfig.model_validate(
            {"state_count": 20, "rounds": 2, "oracle_temperature": 1.0}
        )


def test_fixed_potential_control_verifies_theoretical_contraction() -> None:
    synthetic_config = SyntheticExperimentConfig(state_count=20, rounds=5, seeds=(7, 13))
    synthetic, catalogs, phase_rows = run_synthetic_experiment(
        synthetic_config,
        experiment_id="test_refinement_dynamics",
    )
    dynamics_config = RefinementDynamicsConfig(
        analysis_rounds=5,
        checkpoint_rounds=(1, 3, 5),
        primary_training_round=3,
        fixed_potential_rounds=6,
    )

    first = run_refinement_dynamics_experiment(
        dynamics_config,
        synthetic_config,
        synthetic,
        catalogs,
        phase_rows,
        experiment_id="test_refinement_dynamics",
    )
    second = run_refinement_dynamics_experiment(
        dynamics_config,
        synthetic_config,
        synthetic,
        catalogs,
        phase_rows,
        experiment_id="test_refinement_dynamics",
    )

    assert first == second
    contraction = first.report.fixed_potential_contraction
    assert contraction.projective_contraction_verified
    assert contraction.observed_projective_contraction_factor.mean == pytest.approx(
        contraction.history_exponent,
        abs=1e-10,
    )
    assert contraction.final_projective_distance.mean < contraction.initial_projective_distance.mean
    assert not first.report.strict_convergence_claim_supported


def test_practical_convergence_requires_consecutive_stable_transitions() -> None:
    synthetic_config = SyntheticExperimentConfig(state_count=20, rounds=3, seeds=(7,))
    report, _, _ = run_synthetic_experiment(
        synthetic_config,
        experiment_id="test_stability",
    )
    config = RefinementDynamicsConfig(
        analysis_rounds=3,
        checkpoint_rounds=(1, 3),
        primary_training_round=3,
        fixed_potential_rounds=3,
    )

    interrupted = []
    for point in report.metric_points:
        if point.method != "full_vtdo":
            interrupted.append(point)
            continue
        kl_shift = {0: 0.0, 1: 0.005, 2: 0.02, 3: 0.005}[point.round_index]
        interrupted.append(
            point.model_copy(
                update={
                    "kl_to_previous": kl_shift,
                    "expected_contribution_novelty": 0.1,
                }
            )
        )
    interrupted_report = report.model_copy(update={"metric_points": tuple(interrupted)})
    _, interrupted_summary = _controlled_round_dynamics(config, interrupted_report)
    assert interrupted_summary.converged_seed_count == 0

    consecutive = tuple(
        point.model_copy(update={"kl_to_previous": 0.005})
        if point.method == "full_vtdo" and point.round_index > 0
        else point
        for point in interrupted_report.metric_points
    )
    consecutive_report = report.model_copy(update={"metric_points": consecutive})
    _, consecutive_summary = _controlled_round_dynamics(config, consecutive_report)
    assert consecutive_summary.convergence_round_by_seed == {"7": 2}


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
    assert execution.report.real_refinement.validated_artifact_count == 0
    assert any(
        item.startswith("missing_round_artifact_source:")
        for item in execution.report.real_refinement.blockers
    )


def test_validation_config_rejects_dynamics_horizon_beyond_synthetic(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exceed the synthetic experiment horizon"):
        VTDOValidationConfig(
            synthetic=SyntheticExperimentConfig(state_count=20, rounds=2, seeds=(7,)),
            real_state=RealStateExperimentConfig(
                agent_artifact_dir=tmp_path,
                agent_config_path=tmp_path / "agent.json",
            ),
            training=TrainingExperimentConfig(
                training_config_path=tmp_path / "student.json",
            ),
            refinement_dynamics=RefinementDynamicsConfig(
                analysis_rounds=3,
                checkpoint_rounds=(1, 3),
                primary_training_round=3,
            ),
            output_dir=tmp_path / "output",
        )


def test_ccgr_entropy_clamps_sub_ulp_negative_cancellation() -> None:
    assert _entropy({"only_profile": 1.0000000000000002}) == 0.0


def test_fixed_token_scheduler_realizes_frozen_sampling_weights() -> None:
    records = (
        SimpleNamespace(record_id="low", sampling_weight=1.0),
        SimpleNamespace(record_id="high", sampling_weight=4.0),
    )
    encoded = [
        {"labels": [1], "input_ids": [1], "attention_mask": [1]},
        {"labels": [1], "input_ids": [1], "attention_mask": [1]},
    ]

    _, token_count, exposures = _schedule_supervised_token_budget_with_exposures(
        encoded,
        records,
        token_budget=10_000,
        examples_per_step=1,
        seed=41,
    )

    assert token_count == 10_000
    assert sum(exposures.values()) == 10_000
    observed_high_share = exposures["high"] / 10_000
    assert observed_high_share == pytest.approx(0.8, abs=0.02)


def test_vtdo_student_training_contract_rejects_legacy_mvp_fields() -> None:
    config = VTDOStudentTrainingConfig(
        base_model="Qwen2.5-7B-Instruct",
        supervised_token_budget=500_000,
    )

    assert config.prompt_version == "training_utility_agent_prompt.v6"
    with pytest.raises(ValueError, match="candidate_tasks_per_domain"):
        VTDOStudentTrainingConfig.model_validate(
            {
                **config.model_dump(mode="json"),
                "candidate_tasks_per_domain": 10,
            }
        )


def test_vtdo_arm_training_fails_closed_before_model_loading(tmp_path: Path) -> None:
    student = VTDOStudentTrainingConfig(
        base_model="Qwen2.5-7B-Instruct",
        supervised_token_budget=500_000,
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
        requested_supervised_tokens=500_000,
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
        "schema_version": "vtdo_validation.v3",
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
