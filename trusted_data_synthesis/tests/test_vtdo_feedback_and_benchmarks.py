from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from trusted_synthesis.core.vtdo import (
    AnchoredEnergyConfig,
    ProbeAdaptationResult,
    ValidityThresholds,
    contribution_current_distribution_hash,
    empty_optimizer_state_hash,
    estimate_contributions_from_probes,
    make_conditional_distribution,
    make_contribution_data_isolation_contract,
    make_contribution_metric_contract,
    make_contribution_probe_observation,
    make_contribution_probe_protocol,
    make_contribution_production_authorization,
    make_contribution_rank_validation_evidence,
    make_probe_optimizer_contract,
)
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.vtdo_experiment.benchmark_prediction import (
    BenchmarkGenerationConfig,
    _directory_manifest_hash,
    run_benchmark_predictions,
)
from trusted_synthesis.experiments.vtdo_experiment.beneficiary_shift import (
    run_beneficiary_state_shift_experiment,
)
from trusted_synthesis.experiments.vtdo_experiment.evaluation import (
    BENCHMARK_ADAPTER_VERSION,
    BENCHMARK_METRIC_VERSION,
    BenchmarkExample,
    BenchmarkPrediction,
    _native_answer_metrics,
    _question_skeleton,
    audit_external_benchmark_leakage,
    benchmark_prediction_id,
    evaluate_external_benchmark_predictions,
    load_benchmark_examples,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceMultiStateConfig,
    _build_task_artifact,
)
from trusted_synthesis.experiments.vtdo_experiment.real_feedback import (
    RealFeedbackProductionConfig,
    RecordedContributionProbe,
    RecordedExplorerTrajectory,
    _state_seed,
    _task_round_seed,
    produce_real_vtdo_feedback,
    recorded_contribution_probe_id,
    recorded_explorer_trajectory_id,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import (
    BeneficiaryStateShiftConfig,
    ExternalBenchmarkSnapshot,
    VTDOExperimentConfig,
    VTDOTrainingRunResult,
    vtdo_training_run_result_id,
)
from trusted_synthesis.hashing import canonical_hash


def test_beneficiary_model_state_shift_uses_paired_task_state_seed_observations(
    tmp_path: Path,
) -> None:
    baseline_path = tmp_path / "m0.jsonl"
    updated_path = tmp_path / "m1.jsonl"
    _write_shift_observations(baseline_path, "beneficiary:M0", (-1.0, 0.0, 1.0), round_index=0)
    _write_shift_observations(updated_path, "beneficiary:M1", (1.0, 0.0, -1.0), round_index=1)

    report = run_beneficiary_state_shift_experiment(
        BeneficiaryStateShiftConfig(
            enabled=True,
            baseline_observation_path=baseline_path,
            updated_observation_path=updated_path,
            minimum_unique_task_count=3,
            minimum_states_per_task=3,
            minimum_seeds_per_state=3,
        )
    )

    assert report.status == "passed", report.blockers
    assert report.atomic_pair_count == 27
    assert report.aggregated_state_count == 9
    assert report.model_state_dependence_observed
    assert report.task_rank_correlation is not None
    assert report.task_rank_correlation.mean == pytest.approx(-1.0)
    assert report.contribution_direction_change_rate == pytest.approx(2.0 / 3.0)


def test_beneficiary_shift_rejects_renamed_model_with_same_checkpoint(
    tmp_path: Path,
) -> None:
    baseline_path = tmp_path / "same-checkpoint-m0.jsonl"
    updated_path = tmp_path / "same-checkpoint-m1.jsonl"
    _write_shift_observations(
        baseline_path,
        "beneficiary:M0",
        (-1.0, 0.0, 1.0),
        checkpoint_hash="checkpoint:shared",
        round_index=0,
    )
    _write_shift_observations(
        updated_path,
        "beneficiary:M1",
        (1.0, 0.0, -1.0),
        checkpoint_hash="checkpoint:shared",
        round_index=1,
    )

    report = run_beneficiary_state_shift_experiment(
        BeneficiaryStateShiftConfig(
            enabled=True,
            baseline_observation_path=baseline_path,
            updated_observation_path=updated_path,
            minimum_unique_task_count=3,
            minimum_states_per_task=3,
            minimum_seeds_per_state=3,
        )
    )

    assert report.status == "blocked"
    assert "beneficiary_checkpoint_did_not_change" in report.blockers


def test_real_feedback_replays_explorer_and_multi_seed_probes(
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
    artifact_path = tmp_path / "task_states.jsonl"
    artifact_path.write_text(artifact.model_dump_json() + "\n", encoding="utf-8")
    condition_id = artifact.state_catalog.task_condition_id
    states = {item.assignment.state.state_id: item for item in artifact.accepted_states}
    state_ids = tuple(sorted(states))
    task_seed = _task_round_seed(71, condition_id, 0)
    explorer_records: list[RecordedExplorerTrajectory] = []
    for state_id in state_ids:
        values = {
            "task_condition_id": condition_id,
            "round_index": 0,
            "requested_state_id": state_id,
            "provider_seed": _state_seed(task_seed, state_id),
            "candidate_ordinal": 0,
            "explorer_checkpoint_hash": "explorer-checkpoint:abc",
            "generation_config_hash": "explorer-generation:def",
            "trajectory": states[state_id].trajectory,
        }
        provisional = RecordedExplorerTrajectory.model_construct(
            record_id="pending",
            **values,
        )
        explorer_records.append(
            RecordedExplorerTrajectory(
                record_id=recorded_explorer_trajectory_id(provisional),
                **values,
            )
        )
    explorer_path = tmp_path / "explorer.jsonl"
    _write_models(explorer_path, explorer_records)

    prior = make_conditional_distribution(
        condition_id,
        {state_id: 1.0 / len(state_ids) for state_id in state_ids},
        round_index=0,
    )
    baseline_training_ids = tuple(f"train:{index}" for index in range(19))
    internal_validation_ids = tuple(f"validation:{index}" for index in range(20))
    final_test_ids = tuple(f"final-test:{index}" for index in range(5))
    probe_optimizer = make_probe_optimizer_contract(
        optimizer_name="sgd",
        learning_rate=1e-5,
        step_count=3,
    )
    probe_records: list[RecordedContributionProbe] = []
    for state_index, state_id in enumerate(state_ids):
        for seed in (7, 13, 19):
            delta = (state_index - 2) * 0.01
            values = {
                "task_condition_id": condition_id,
                "round_index": 0,
                "state_id": state_id,
                "seed": seed,
                "beneficiary_model_state_id": "beneficiary:M0",
                "beneficiary_checkpoint_hash": "beneficiary-checkpoint:abc",
                "baseline_distribution_id": prior.distribution_id,
                "baseline_training_set_id": "finance-train:v1",
                "baseline_training_instance_ids": baseline_training_ids,
                "probe_update_instance_ids": (f"probe:{state_id}",),
                "evaluation_distribution_id": "finance-eval:v1",
                "evaluation_snapshot_hash": "evaluation-snapshot:abc",
                "internal_validation_instance_ids": internal_validation_ids,
                "final_test_set_id": "finance-final-test:v1",
                "final_test_instance_ids": final_test_ids,
                "target_metric_id": "answer-accuracy",
                "score_transform": "identity",
                "optimizer_contract": probe_optimizer,
                "initial_optimizer_state_hash": empty_optimizer_state_hash(probe_optimizer),
                "executed_step_count": probe_optimizer.step_count,
                "adapted_model_state_id": f"beneficiary:M0:probe:{state_id}:{seed}",
                "adapted_checkpoint_hash": f"adapted-checkpoint:{state_id}:{seed}",
                "baseline_performance": 0.5,
                "adapted_performance": 0.5 + delta,
                "performance_gain": delta,
                "measurement_confidence": 1.0,
            }
            provisional = RecordedContributionProbe.model_construct(
                record_id="pending",
                **values,
            )
            probe_records.append(
                RecordedContributionProbe(
                    record_id=recorded_contribution_probe_id(provisional),
                    **values,
                )
            )
    invalid_values = probe_records[0].model_dump(mode="python", exclude={"record_id"})
    invalid_values["optimizer_contract"] = probe_optimizer
    invalid_values["initial_optimizer_state_hash"] = "historical-optimizer-state"
    invalid_provisional = RecordedContributionProbe.model_construct(
        record_id="pending",
        **invalid_values,
    )
    with pytest.raises(ValueError, match="zero optimizer state"):
        RecordedContributionProbe(
            record_id=recorded_contribution_probe_id(invalid_provisional),
            **invalid_values,
        )

    probe_path = tmp_path / "probes.jsonl"
    _write_models(probe_path, probe_records)
    isolation = make_contribution_data_isolation_contract(
        task_condition_id=condition_id,
        baseline_training_set_id="finance-train:v1",
        baseline_training_instance_ids=baseline_training_ids,
        probe_update_instance_ids_by_state={
            state_id: (f"probe:{state_id}",) for state_id in state_ids
        },
        internal_validation_set_id="finance-eval:v1",
        internal_validation_instance_ids=internal_validation_ids,
        final_test_set_id="finance-final-test:v1",
        final_test_instance_ids=final_test_ids,
    )
    metric = make_contribution_metric_contract(
        target_metric_id="answer-accuracy",
        evaluation_distribution_id="finance-eval:v1",
        evaluation_snapshot_hash="evaluation-snapshot:abc",
        score_transform="identity",
    )
    protocol = make_contribution_probe_protocol(
        beneficiary_model_state_id="beneficiary:M0",
        beneficiary_checkpoint_hash="beneficiary-checkpoint:abc",
        metric_contract=metric,
        data_isolation=isolation,
        optimizer=probe_optimizer,
        probe_seeds=(7, 13, 19),
    )
    observations = tuple(
        make_contribution_probe_observation(
            task_condition_id=record.task_condition_id,
            round_index=record.round_index,
            state_id=record.state_id,
            protocol=protocol,
            seed=record.seed,
            adaptation_result=ProbeAdaptationResult(
                adapted_model_state_id=record.adapted_model_state_id,
                adapted_checkpoint_hash=record.adapted_checkpoint_hash,
                base_model_state_id=record.beneficiary_model_state_id,
                base_checkpoint_hash=record.beneficiary_checkpoint_hash,
                optimizer_contract_id=probe_optimizer.contract_id,
                initial_optimizer_state_hash=empty_optimizer_state_hash(probe_optimizer),
                executed_step_count=probe_optimizer.step_count,
            ),
            baseline_performance=record.baseline_performance,
            adapted_performance=record.adapted_performance,
        )
        for record in probe_records
    )
    contribution_manifest = estimate_contributions_from_probes(prior, observations)

    def rank_evidence(role):
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
        contribution_manifest.task_condition_id,
        *(f"task:authorized:{index}" for index in range(29)),
    )
    task_distribution_hashes = {
        task_id: (
            contribution_current_distribution_hash(
                contribution_manifest.task_condition_id,
                {
                    item.state_id: item.current_probability
                    for item in contribution_manifest.estimates
                },
            )
            if task_id == contribution_manifest.task_condition_id
            else f"test-current-distribution:{task_id}"
        )
        for task_id in task_condition_ids
    }
    authorization = make_contribution_production_authorization(
        manifest=contribution_manifest,
        analysis_version="test_contribution_validation.v1",
        analysis_report_hash="test-contribution-report:passed",
        task_condition_ids=task_condition_ids,
        task_distribution_hashes=task_distribution_hashes,
        task_count=30,
        state_count=60,
        internal_validation_record_count=len(internal_validation_ids),
        final_test_record_count=len(final_test_ids),
        estimation_seed_count=3,
        validation_seed_count=3,
        intervention_seed_count=3,
        cross_seed_stability=rank_evidence("cross_seed_stability"),
        independent_final_test=rank_evidence("independent_final_test"),
        heldout_final_test=rank_evidence("heldout_final_test"),
    )
    authorization_path = tmp_path / "contribution_authorization.json"
    authorization_path.write_text(
        authorization.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    reports = {
        item.trajectory.trajectory_id: item.validity_report for item in artifact.accepted_states
    }

    class FrozenEvaluator:
        def evaluate(self, context, trajectory):
            assert context.context_id == artifact.omega.context_id
            return reports[trajectory.trajectory_id]

    monkeypatch.setattr(
        "trusted_synthesis.experiments.vtdo_experiment.real_feedback._finance_trajectory_evaluator",
        lambda path: FrozenEvaluator(),
    )
    output_dir = tmp_path / "feedback"
    (tmp_path / "unused.json").write_text("{}", encoding="utf-8")
    report = produce_real_vtdo_feedback(
        RealFeedbackProductionConfig(
            task_state_artifact_path=artifact_path,
            finance_archive_config_path=tmp_path / "unused.json",
            explorer_trajectory_path=explorer_path,
            probe_observation_path=probe_path,
            contribution_production_authorization_path=authorization_path,
            output_dir=output_dir,
            explorer_provider_id="explorer:provider",
            explorer_provider_version="1.0.0",
            materialization_provider_id="materializer:provider",
            explorer_checkpoint_hash="explorer-checkpoint:abc",
            explorer_generation_config_hash="explorer-generation:def",
            beneficiary_model_state_id="beneficiary:M0",
            beneficiary_checkpoint_hash="beneficiary-checkpoint:abc",
            final_student_model_id="student:qwen",
            evaluation_distribution_id="finance-eval:v1",
            target_metric_id="answer-accuracy",
            evaluation_snapshot_hash="evaluation-snapshot:abc",
            probe_optimizer_name="sgd",
            probe_learning_rate=1e-5,
            probe_step_count=3,
            probe_seeds=(7, 13, 19),
            round_count=1,
            exploration_budget_per_task=len(state_ids),
            exploration_seed=71,
            validity_thresholds=ValidityThresholds(
                reject_below=0.2,
                accept_at_or_above=0.8,
            ),
            energy_config=AnchoredEnergyConfig(
                epsilon=0.01,
                contribution_temperature=1.0,
                novelty_temperature=1.0,
                contribution_weight=0.5,
                novelty_weight=0.5,
                history_kl_weight=1.0,
                coverage_kl_weight=1.0,
            ),
            catalog_version="finance-state-catalog:v1",
        )
    )

    assert report.status == "passed"
    assert report.exploration_batch_count == 1
    assert report.contribution_observation_count == len(state_ids) * 3
    assert report.assembled_round_count == 1
    assert (output_dir / "real_round_inputs.jsonl").is_file()
    assert (output_dir / "vtdo_rounds.jsonl").is_file()


def _prediction(
    benchmark_id: str, answer: str, *, scale: str = "", program: str = ""
) -> BenchmarkPrediction:
    values = {
        "prediction_run_id": "benchmark-run:test",
        "benchmark_id": benchmark_id,
        "example_id": "example:test",
        "answer": answer,
        "scale": scale,
        "program": program,
        "contract_success": True,
        "raw_response_hash": canonical_hash(answer, prefix="raw-response:"),
    }
    provisional = BenchmarkPrediction.model_construct(prediction_id="pending", **values)
    return BenchmarkPrediction(prediction_id=benchmark_prediction_id(provisional), **values)


def test_question_skeleton_normalizes_entity_metric_and_period_slots() -> None:
    left = _question_skeleton("What was Apple revenue in 2023?")
    right = _question_skeleton("What was Microsoft revenue in 2024?")
    assert left == right
    assert left == "what was slot in <number>"


def test_finqa_primary_metric_requires_program_execution() -> None:
    example = BenchmarkExample(
        example_id="example:test",
        benchmark_id="finqa",
        prompt="Context: A=2 and B=2. Question: What is A+B?",
        question="What is A+B?",
        gold_answer="4",
        context_hash="context:test",
        metric_id="finqa_answer_and_program_execution.v2",
        metadata={"native_table": [["A", "2"], ["B", "2"]]},
    )
    primary_correct, _, program_correct, answer_correct = _native_answer_metrics(
        example,
        _prediction("finqa", "4", program="subtract(2, 2)"),
    )
    assert answer_correct
    assert program_correct is False
    assert not primary_correct


def test_tatqa_scale_equivalent_answers_are_accepted() -> None:
    example = BenchmarkExample(
        example_id="example:test",
        benchmark_id="tat_qa",
        prompt="Context: margin is 12.5 percent.",
        question="What is the margin?",
        gold_answer="12.5",
        context_hash="context:test",
        metric_id="tat_qa_em_f1_scale.v1",
        metadata={"scale": "percent"},
    )
    exact, f1, _, answer_correct = _native_answer_metrics(example, _prediction("tat_qa", "12.5%"))
    assert exact and answer_correct
    assert f1 == pytest.approx(1.0)


def test_leakage_audit_fails_when_required_document_channel_is_unavailable(
    tmp_path: Path,
) -> None:
    benchmark_path = tmp_path / "financebench.json"
    benchmark_path.write_text(
        json.dumps(
            [{"id": "b1", "question": "What is cash?", "answer": "5", "context": "Cash is 5."}]
        ),
        encoding="utf-8",
    )
    snapshot = ExternalBenchmarkSnapshot(
        benchmark_id="financebench",
        path=benchmark_path,
        sha256=hashlib.sha256(benchmark_path.read_bytes()).hexdigest(),
        source_repository="official/financebench",
        source_revision="a" * 40,
        split="test",
        adapter_version=BENCHMARK_ADAPTER_VERSION,
        metric_version=BENCHMARK_METRIC_VERSION,
    )
    artifact = _build_task_artifact(
        build_finance_counterfactual_case(4),
        FinanceMultiStateConfig(finance_archive_config_path=tmp_path / "unused.json", task_count=1),
    )
    assert all(
        item.provenance.content_hash is None for item in artifact.omega.public_corpus.evidence
    )
    report = audit_external_benchmark_leakage((snapshot,), (artifact,))
    assert report.status == "failed"
    assert report.unavailable_required_hard_channels == ("document_hash",)
    assert "benchmark_leakage_required_channel_unavailable:document_hash" in report.blockers


def test_frozen_finqa_and_tatqa_gold_contracts_replay() -> None:
    root = Path(__file__).resolve().parents[1]
    config = VTDOExperimentConfig.from_json(root / "config/vtdo_experiment_finance.json")
    examples = load_benchmark_examples(config.training.external_benchmarks)
    counts = {"finqa": 0, "tat_qa": 0}
    for example in examples:
        prediction = BenchmarkPrediction.model_construct(
            prediction_id="gold-self-check",
            prediction_run_id="gold-self-check",
            benchmark_id=example.benchmark_id,
            example_id=example.example_id,
            answer=example.gold_answer,
            scale=str(example.metadata.get("scale", "")),
            program=str(example.metadata.get("program", "")),
            contract_success=True,
            raw_response_hash="gold-self-check",
        )
        correct, _, program_correct, answer_correct = _native_answer_metrics(example, prediction)
        assert answer_correct
        if example.benchmark_id == "finqa":
            assert program_correct is True, (
                example.example_id,
                example.metadata.get("program"),
                example.gold_answer,
            )
            assert correct
        counts[example.benchmark_id] += 1
    assert counts == {"finqa": 1_147, "tat_qa": 1_663}


def test_benchmark_prediction_runner_freezes_model_and_snapshot_identity(
    tmp_path: Path,
) -> None:
    benchmark_path = tmp_path / "financebench.json"
    benchmark_path.write_text(
        json.dumps(
            [{"id": "b1", "question": "What is cash?", "answer": "5", "context": "Cash is 5."}]
        ),
        encoding="utf-8",
    )
    snapshot = ExternalBenchmarkSnapshot(
        benchmark_id="financebench",
        path=benchmark_path,
        sha256=hashlib.sha256(benchmark_path.read_bytes()).hexdigest(),
        source_repository="official/financebench",
        source_revision="a" * 40,
        split="test",
        adapter_version=BENCHMARK_ADAPTER_VERSION,
        metric_version=BENCHMARK_METRIC_VERSION,
    )
    adapter_dir = tmp_path / "adapter"
    base_dir = tmp_path / "base"
    adapter_dir.mkdir()
    base_dir.mkdir()
    (adapter_dir / "adapter.safetensors").write_bytes(b"adapter")
    (base_dir / "model.safetensors").write_bytes(b"base")
    training_input_sha256 = {
        "student_config": "1" * 64,
        "preflight": "2" * 64,
        "arm_manifest": "3" * 64,
        "dataset": "4" * 64,
    }
    values = {
        "arm_id": "B5_vtdo",
        "config_hash": "training-config:abc",
        "dataset_hash": "dataset:abc",
        "training_input_sha256": training_input_sha256,
        "training_input_manifest_hash": canonical_hash(
            training_input_sha256, prefix="vtdo_training_input_manifest:"
        ),
        "base_model_manifest_hash": _directory_manifest_hash(
            base_dir, prefix="base_model_manifest:"
        ),
        "adapter_manifest_hash": _directory_manifest_hash(adapter_dir, prefix="adapter_manifest:"),
        "base_model": str(base_dir),
        "model_revision": None,
        "training_seed": 7,
        "adapter_dir": str(adapter_dir),
        "completed_steps": 1,
        "final_train_loss": 0.1,
        "supervised_token_count": 1_000,
        "supervised_token_budget": 1_000,
        "prompt_token_count": 100,
        "processed_token_count": 1_100,
        "scheduled_example_count": 10,
        "unique_scheduled_record_count": 10,
        "repeated_example_rate": 0.0,
        "token_budget_deviation_rate": 0.0,
        "train_runtime_seconds": 1.0,
        "peak_gpu_memory_bytes": 1,
        "dependency_versions": {"torch": "test"},
    }
    provisional = VTDOTrainingRunResult.model_construct(result_id="pending", **values)
    training_result = VTDOTrainingRunResult(
        result_id=vtdo_training_run_result_id(provisional),
        **values,
    )
    training_result_path = tmp_path / "training_result.json"
    training_result_path.write_text(training_result.model_dump_json(), encoding="utf-8")

    class FrozenGenerator:
        generator_manifest_hash = "generator-manifest:test"

        def generate(self, prompt: str, config: BenchmarkGenerationConfig) -> str:
            assert "Cash is 5" in prompt
            return '{"answer": "5", "scale": ""}'

    output_dir = tmp_path / "predictions"
    manifest = run_benchmark_predictions(
        (snapshot,),
        training_result_path,
        BenchmarkGenerationConfig(device="cpu"),
        output_dir,
        generator=FrozenGenerator(),
    )
    assert manifest.status == "completed"
    report = evaluate_external_benchmark_predictions(
        (snapshot,),
        output_dir / "benchmark_predictions.jsonl",
        output_dir / "benchmark_prediction_manifest.json",
    )
    assert report.status == "passed"
    assert report.slices[0].end_to_end_accuracy == pytest.approx(1.0)

    (adapter_dir / "adapter.safetensors").write_bytes(b"mutated-adapter")
    mutated_report = evaluate_external_benchmark_predictions(
        (snapshot,),
        output_dir / "benchmark_predictions.jsonl",
        output_dir / "benchmark_prediction_manifest.json",
    )
    assert mutated_report.status == "blocked"
    assert "benchmark_adapter_content_hash_mismatch" in mutated_report.blockers

    with pytest.raises(ValueError, match="output directory is not empty"):
        run_benchmark_predictions(
            (snapshot,),
            training_result_path,
            BenchmarkGenerationConfig(device="cpu"),
            output_dir,
            generator=FrozenGenerator(),
        )


def _write_shift_observations(
    path: Path,
    model_state: str,
    contributions: tuple[float, float, float],
    *,
    checkpoint_hash: str | None = None,
    round_index: int,
) -> None:
    seeds = (7, 13, 19)
    beneficiary_checkpoint = checkpoint_hash or f"checkpoint:{model_state}"
    observations = []
    for task_index in range(3):
        task_id = f"task:{task_index}"
        state_ids = tuple(f"state:{index}" for index in range(3))
        data_isolation = make_contribution_data_isolation_contract(
            task_condition_id=task_id,
            baseline_training_set_id=f"train:{task_id}",
            baseline_training_instance_ids=tuple(f"{task_id}:train:{index}" for index in range(19)),
            probe_update_instance_ids_by_state={
                state_id: (f"{task_id}:probe:{state_id}",) for state_id in state_ids
            },
            internal_validation_set_id="evaluation:v1",
            internal_validation_instance_ids=tuple(
                f"{task_id}:validation:{index}" for index in range(20)
            ),
            final_test_set_id=f"final-test:{task_id}",
            final_test_instance_ids=(f"{task_id}:final-test:0",),
        )
        metric = make_contribution_metric_contract(
            target_metric_id="accuracy",
            evaluation_distribution_id="evaluation:v1",
            evaluation_snapshot_hash="snapshot:v1",
            score_transform="identity",
        )
        probe_contract = make_contribution_probe_protocol(
            beneficiary_model_state_id=model_state,
            beneficiary_checkpoint_hash=beneficiary_checkpoint,
            metric_contract=metric,
            data_isolation=data_isolation,
            optimizer=make_probe_optimizer_contract(
                optimizer_name="sgd",
                learning_rate=1e-5,
                step_count=3,
            ),
            probe_seeds=seeds,
        )
        for state_index, contribution in enumerate(contributions):
            state_id = state_ids[state_index]
            for seed in seeds:
                probe = make_contribution_probe_observation(
                    task_condition_id=task_id,
                    round_index=round_index,
                    state_id=state_id,
                    protocol=probe_contract,
                    seed=seed,
                    adaptation_result=ProbeAdaptationResult(
                        adapted_model_state_id=f"{model_state}:probe:{state_id}:{seed}",
                        adapted_checkpoint_hash=(
                            f"{beneficiary_checkpoint}:probe:{state_id}:{seed}"
                        ),
                        base_model_state_id=model_state,
                        base_checkpoint_hash=beneficiary_checkpoint,
                        optimizer_contract_id=probe_contract.optimizer.contract_id,
                        initial_optimizer_state_hash=empty_optimizer_state_hash(
                            probe_contract.optimizer
                        ),
                        executed_step_count=probe_contract.optimizer.step_count,
                    ),
                    baseline_performance=0.0,
                    adapted_performance=contribution,
                )
                observations.append(probe)
    _write_models(path, observations)


def _write_models(path: Path, values) -> None:
    path.write_text(
        "".join(item.model_dump_json() + "\n" for item in values),
        encoding="utf-8",
    )
