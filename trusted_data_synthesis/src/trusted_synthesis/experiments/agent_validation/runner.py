from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.evaluation.contracts import (
    ContractQualityAssessment,
    QualityContractCompiler,
    QualityContractRuntime,
)
from trusted_synthesis.core.evaluation.counterfactual import (
    CounterfactualContext,
    calibrate_counterfactuals,
)
from trusted_synthesis.core.evaluation.critic import (
    QualityAwareSelector,
    QualityCriticDataset,
    QualityCriticExample,
    QualityCriticPrediction,
    QualitySelectionPolicy,
    build_quality_critic_example,
    evaluate_annotation_alignment,
    make_quality_critic_dataset,
    prediction_as_advisory_annotation,
)
from trusted_synthesis.core.evaluation.quality_vector import (
    QualityDimension,
    QualityVectorCompiler,
)
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evaluation.utility import (
    UtilityCohort,
    make_training_utility_protocol,
)
from trusted_synthesis.core.feedback import (
    FeedbackExposure,
    contract_feedback,
    failed_action_feedback,
)
from trusted_synthesis.core.refinement import build_synthesis_cell
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.trajectory.candidate_verifier import (
    CandidateWorkflowVerifier,
)
from trusted_synthesis.domains.finance.verification import FinanceClaimVerifier
from trusted_synthesis.experiments.agent_validation.schema import (
    AGENT_VALIDATION_VERSION,
    AgentValidationCapacityReport,
    AgentValidationConfig,
    AgentValidationReport,
    AgentValidationSample,
)
from trusted_synthesis.experiments.agent_validation.tracks import (
    materialize_track_variant,
)
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_cases,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    ContractCase,
    build_pattern_validation_cases,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    JsonCompletionClient,
    LLMAgentSolver,
    LLMClientError,
)
from trusted_synthesis.runtime.agent.llm_agent import (
    LLM_AGENT_PROMPT_VERSION,
    LLM_AGENT_SOLVER_VERSION,
)
from trusted_synthesis.runtime.agent.schema import (
    AGENT_RESPONSE_SCHEMA_VERSION,
    FailedActionPlan,
    HostInteractionProgress,
    ModelCallTelemetry,
)
from trusted_synthesis.runtime.critic import LLMQualityCritic
from trusted_synthesis.runtime.critic.llm_critic import LLM_CRITIC_PROMPT_VERSION
from trusted_synthesis.runtime.tools import InMemoryEvidenceToolRuntime


@dataclass(frozen=True)
class AgentValidationArtifacts:
    report: AgentValidationReport
    critic_dataset: QualityCriticDataset


AGENT_SAMPLE_CHECKPOINT_VERSION = "agent_sample_checkpoint.v3"
CRITIC_CHECKPOINT_VERSION = "critic_checkpoint.v2"


@dataclass(frozen=True)
class _AgentJob:
    index: int
    case: ContractCase
    task: Any
    sample_id: str
    structure: dict[str, str]


class _AgentJobResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sample: AgentValidationSample
    critic_examples: tuple[QualityCriticExample, ...] = ()
    accepted_example_ids: tuple[str, ...] = ()
    reference_sample_ids: tuple[str, ...] = ()
    counterfactual_ids: tuple[str, ...] = ()
    counterfactual_assessments: tuple[ContractQualityAssessment, ...] = ()
    telemetry: tuple[ModelCallTelemetry, ...] = ()
    infrastructure_failures: tuple[str, ...] = ()


class _CriticJobResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    example_id: str
    prediction: QualityCriticPrediction | None = None
    prompt_manifest_hash: str | None = None
    telemetry: tuple[ModelCallTelemetry, ...] = ()
    failure: str | None = None


def _build_validation_cases(
    config: AgentValidationConfig,
) -> tuple[ContractCase, ...]:
    targets = config.resolved_domain_task_targets
    non_finance = build_pattern_validation_cases(
        per_domain=max(targets["legal"], targets["science"])
    )
    legal = tuple(item for item in non_finance if item.domain == "legal")[: targets["legal"]]
    science = tuple(item for item in non_finance if item.domain == "science")[: targets["science"]]
    return (
        *build_finance_counterfactual_cases(count=targets["finance"]),
        *legal,
        *science,
    )


def audit_agent_validation_capacity(
    config: AgentValidationConfig,
) -> AgentValidationCapacityReport:
    """Materialize task contracts and estimate calls without invoking a model API."""

    cases = _build_validation_cases(config)
    targets = config.resolved_domain_task_targets
    materialized = Counter(item.domain for item in cases)
    unique = {
        domain: len({item.task.task_id for item in cases if item.domain == domain})
        for domain in targets
    }
    structures = tuple(_task_structure(item.task.public) for item in cases)
    blockers = []
    for domain, target in targets.items():
        if materialized.get(domain, 0) != target:
            blockers.append(f"{domain}:materialized={materialized.get(domain, 0)},target={target}")
        if unique[domain] != target:
            blockers.append(f"{domain}:unique={unique[domain]},target={target}")
    retrieval_count = len(config.retrieval_tracks)
    planning_count = len(config.planning_tracks)
    base_task_count = sum(targets.values())
    planned_candidates = base_task_count * retrieval_count * planning_count
    model_search_tracks = sum(track.value != "resolved" for track in config.retrieval_tracks)
    search_calls = base_task_count * planning_count * model_search_tracks
    if config.model.interaction_protocol == "host_instrumented":
        action_calls = planned_candidates
        final_answer_calls = planned_candidates
        full_response_calls = 0
    else:
        action_calls = 0
        final_answer_calls = 0
        full_response_calls = planned_candidates
    agent_call_floor = (
        search_calls + action_calls + final_answer_calls + full_response_calls
    )
    critic_call_ceiling = (
        min(config.model_critic_max_examples, planned_candidates) if config.run_model_critic else 0
    )
    fixture_identity = tuple(
        sorted(
            (
                item.domain,
                item.task.task_id,
                item.task.task_hash,
                item.bundle.bundle_hash,
            )
            for item in cases
        )
    )
    return AgentValidationCapacityReport(
        config_hash=config.config_hash,
        target_task_counts=targets,
        materialized_task_counts=dict(sorted(materialized.items())),
        unique_task_counts=unique,
        pattern_counts=dict(sorted(Counter(item["pattern_id"] for item in structures).items())),
        program_signature_counts=dict(
            sorted(Counter(item["program_signature"] for item in structures).items())
        ),
        retrieval_track_count=retrieval_count,
        planning_track_count=planning_count,
        planned_candidate_count=planned_candidates,
        interaction_protocol=config.model.interaction_protocol,
        planned_search_api_calls=search_calls,
        planned_action_api_calls=action_calls,
        planned_final_answer_api_calls=final_answer_calls,
        planned_full_response_api_calls=full_response_calls,
        planned_agent_api_call_floor=agent_call_floor,
        planned_critic_api_call_ceiling=critic_call_ceiling,
        fixture_manifest_hash=canonical_hash(
            fixture_identity,
            prefix="agent_capacity_fixtures:",
        ),
        blockers=tuple(blockers),
        status="ready" if not blockers else "blocked",
    )


def run_agent_validation(
    config: AgentValidationConfig,
    client: JsonCompletionClient,
    *,
    checkpoint_dir: Path | None = None,
) -> AgentValidationArtifacts:
    cases = _build_validation_cases(config)
    jobs = _agent_jobs(config, cases)
    checkpoint_root = checkpoint_dir if config.checkpoint_enabled else None
    results_by_index: dict[int, _AgentJobResult] = {}
    pending_jobs: list[_AgentJob] = []
    agent_checkpoint_loaded_count = 0
    agent_checkpoint_written_count = 0
    for job in jobs:
        checkpoint_path = _checkpoint_path(checkpoint_root, "agent", job.sample_id)
        if checkpoint_path is not None and config.resume_from_checkpoints:
            checkpoint = _load_checkpoint(
                checkpoint_path,
                config_hash=_agent_job_checkpoint_hash(config, job),
                version=AGENT_SAMPLE_CHECKPOINT_VERSION,
                model=_AgentJobResult,
            )
            if checkpoint is not None and not (
                config.retry_failed_checkpoints
                and checkpoint.sample.generation_status != "normalized"
            ):
                results_by_index[job.index] = checkpoint
                agent_checkpoint_loaded_count += 1
                continue
        pending_jobs.append(job)

    def record(job: _AgentJob, result: _AgentJobResult) -> None:
        nonlocal agent_checkpoint_written_count
        results_by_index[job.index] = result
        checkpoint_path = _checkpoint_path(checkpoint_root, "agent", job.sample_id)
        if checkpoint_path is not None:
            _write_checkpoint(
                checkpoint_path,
                config_hash=_agent_job_checkpoint_hash(config, job),
                version=AGENT_SAMPLE_CHECKPOINT_VERSION,
                payload=result,
            )
            agent_checkpoint_written_count += 1

    if config.maximum_concurrency == 1:
        for job in pending_jobs:
            record(job, _execute_agent_job(config, client, job))
    else:
        with ThreadPoolExecutor(max_workers=config.maximum_concurrency) as executor:
            futures = {
                executor.submit(_execute_agent_job, config, client, job): job
                for job in pending_jobs
            }
            for future in as_completed(futures):
                job = futures[future]
                record(job, future.result())

    ordered_results = tuple(results_by_index[index] for index in range(len(jobs)))
    samples = [item.sample for item in ordered_results]
    critic_examples: list[QualityCriticExample] = []
    accepted_example_ids: list[str] = []
    reference_sample_ids: list[str] = []
    counterfactual_ids: list[str] = []
    counterfactual_assessments: list[ContractQualityAssessment] = []
    all_telemetry: list[ModelCallTelemetry] = []
    infrastructure_failures: list[str] = []
    for result in ordered_results:
        critic_examples.extend(result.critic_examples)
        accepted_example_ids.extend(result.accepted_example_ids)
        reference_sample_ids.extend(result.reference_sample_ids)
        counterfactual_ids.extend(result.counterfactual_ids)
        counterfactual_assessments.extend(result.counterfactual_assessments)
        all_telemetry.extend(result.telemetry)
        infrastructure_failures.extend(result.infrastructure_failures)
    critic_predictions: tuple[QualityCriticPrediction, ...] = ()
    critic_prompt_hashes: dict[str, str] = {}
    critic_telemetry: dict[str, tuple[ModelCallTelemetry, ...]] = {}
    critic_failures: tuple[str, ...] = ()
    critic_attempted_count = 0
    critic_checkpoint_stats = {"loaded": 0, "written": 0}
    if config.run_model_critic:
        (
            critic_examples,
            critic_predictions,
            critic_prompt_hashes,
            critic_telemetry,
            critic_failures,
            critic_attempted_count,
        ) = _run_model_critic(
            client,
            tuple(critic_examples),
            config.model_critic_max_examples,
            maximum_concurrency=config.maximum_concurrency,
            checkpoint_dir=checkpoint_root,
            checkpoint_config_hash=config.config_hash,
            resume_from_checkpoints=config.resume_from_checkpoints,
            retry_failed_checkpoints=config.retry_failed_checkpoints,
            checkpoint_stats=critic_checkpoint_stats,
        )
        all_telemetry.extend(call for calls in critic_telemetry.values() for call in calls)
        prediction_by_example = {item.example_id: item for item in critic_predictions}
        updated_samples: list[AgentValidationSample] = []
        for item in samples:
            example_id = item.critic_example_id
            if example_id is None:
                updated_samples.append(item)
                continue
            updated_samples.append(
                item.model_copy(
                    update={
                        "critic_prediction": prediction_by_example.get(example_id),
                        "critic_telemetry": critic_telemetry.get(example_id),
                        "critic_prompt_manifest_hash": critic_prompt_hashes.get(example_id),
                    }
                )
            )
        samples = updated_samples
    dataset = make_quality_critic_dataset(critic_examples)
    alignment = evaluate_annotation_alignment(critic_examples)
    predictions = critic_predictions
    selection = QualityAwareSelector().select(
        dataset.examples,
        QualitySelectionPolicy(target_size=config.selection_target),
        predictions,
    )
    utility_protocol = make_training_utility_protocol(
        base_model=config.training_base_model,
        fixed_hyperparameters={
            "seed": config.random_seed,
            "training_method": "sft",
            "same_steps_across_cohorts": True,
            "same_optimizer_across_cohorts": True,
        },
        cohort_samples={
            # The smoke run has no independent unfiltered synthetic pool. Keeping D1
            # planned is more honest than relabeling real Agent candidates as random.
            UtilityCohort.RANDOM_SYNTHETIC: (),
            UtilityCohort.REFERENCE_WORKFLOW: tuple(sorted(reference_sample_ids)),
            UtilityCohort.CONTRACT_FILTERED: tuple(sorted(accepted_example_ids)),
            UtilityCohort.CONTRACT_COUNTERFACTUAL: tuple(sorted(accepted_example_ids)),
            UtilityCohort.CRITIC_SELECTED: selection.selected_example_ids,
        },
        counterfactual_ids=tuple(sorted(counterfactual_ids)),
        held_out_domains=("finance", "legal", "science"),
    )
    report = _build_report(
        config=config,
        samples=tuple(samples),
        dataset=dataset,
        alignment=alignment,
        selection=selection,
        utility_protocol=utility_protocol,
        counterfactual_assessments=tuple(counterfactual_assessments),
        telemetry=tuple(all_telemetry),
        infrastructure_failures=tuple(infrastructure_failures),
        critic_failures=critic_failures,
        critic_attempted_count=critic_attempted_count,
        critic_prompt_hashes=tuple(sorted(set(critic_prompt_hashes.values()))),
        agent_checkpoint_loaded_count=agent_checkpoint_loaded_count,
        agent_checkpoint_written_count=agent_checkpoint_written_count,
        critic_checkpoint_loaded_count=critic_checkpoint_stats["loaded"],
        critic_checkpoint_written_count=critic_checkpoint_stats["written"],
    )
    return AgentValidationArtifacts(report=report, critic_dataset=dataset)


def _agent_jobs(
    config: AgentValidationConfig,
    cases: tuple[ContractCase, ...],
) -> tuple[_AgentJob, ...]:
    jobs: list[_AgentJob] = []
    for case in cases:
        for retrieval_track in config.retrieval_tracks:
            for planning_track in config.planning_tracks:
                task = materialize_track_variant(
                    case.task,
                    case.corpus,
                    retrieval_track=retrieval_track,
                    planning_track=planning_track,
                )
                sample_identity = {
                    "task_id": task.task_id,
                    "retrieval_track": retrieval_track.value,
                    "planning_track": planning_track.value,
                    "model_config_hash": config.model.public_manifest_hash,
                    "validation_version": AGENT_VALIDATION_VERSION,
                }
                jobs.append(
                    _AgentJob(
                        index=len(jobs),
                        case=case,
                        task=task,
                        sample_id=canonical_hash(
                            sample_identity,
                            prefix="agent_validation_sample:",
                        ),
                        structure=_task_structure(task.public),
                    )
                )
    return tuple(jobs)


def _execute_agent_job(
    config: AgentValidationConfig,
    client: JsonCompletionClient,
    job: _AgentJob,
) -> _AgentJobResult:
    case = job.case
    task = job.task
    reference_sample_ids: tuple[str, ...] = ()
    synthesis_cell = None
    try:
        synthesis_cell = build_synthesis_cell(
            task.public,
            case.corpus,
            task.oracle.gold_evidence_ids,
        )
        compiled, runtime = _compile_runtime(case, task)
        reference_sample_ids = (compiled.sample.sample_id,)
        solve_result = LLMAgentSolver(client, case.registry).solve_with_audit(
            task.public,
            InMemoryEvidenceToolRuntime(case.corpus),
        )
        assessment = runtime.evaluate(
            compiled.quality_contract,
            task,
            case.corpus,
            case.proof_graph,
            solve_result.trajectory,
        )
        vector = QualityVectorCompiler().compile(
            compiled.quality_contract,
            assessment,
        )
        feedback_exposures, feedback_signals = contract_feedback(
            domain=case.domain,
            pattern_id=job.structure["pattern_id"],
            contract=compiled.quality_contract,
            assessment=assessment,
        )
        if solve_result.audit.interaction_protocol == "host_instrumented":
            feedback_exposures = (
                *feedback_exposures,
                FeedbackExposure(
                    task_id=task.task_id,
                    domain=case.domain,
                    pattern_id=job.structure["pattern_id"],
                    failure_family="action_execution",
                ),
            )
            feedback_signals = (
                *feedback_signals,
                *(
                    failed_action_feedback(
                        task_id=task.task_id,
                        domain=case.domain,
                        pattern_id=job.structure["pattern_id"],
                        failure_category=item.failure_category,
                        error_code=item.error_code,
                        failed_step_index=item.failed_step_index,
                    )
                    for item in solve_result.audit.action_failure_history
                ),
            )
        example = build_quality_critic_example(
            task=task,
            corpus=case.corpus,
            contract=compiled.quality_contract,
            trajectory=solve_result.trajectory,
            assessment=assessment,
            quality_vector=vector,
            candidate_source="real_agent",
            metadata={
                "model_config_hash": config.model.public_manifest_hash,
                "generation_audit_id": solve_result.audit.audit_id,
                **job.structure,
            },
        )
        examples = [example]
        accepted_ids = (
            (example.example_id,)
            if assessment.decision == ReleaseDecision.ACCEPTED
            else ()
        )
        generated_count = 0
        counterfactual_ids: list[str] = []
        counterfactual_assessments: list[ContractQualityAssessment] = []
        if config.generate_counterfactuals and assessment.decision == ReleaseDecision.ACCEPTED:
            generated = _counterfactual_examples(
                case=case,
                task=task,
                compiled=compiled,
                runtime=runtime,
                source_trajectory=solve_result.trajectory,
            )
            generated_count = len(generated)
            for generated_example, generated_assessment, counterfactual_id in generated:
                examples.append(generated_example)
                counterfactual_assessments.append(generated_assessment)
                counterfactual_ids.append(counterfactual_id)
        return _AgentJobResult(
            sample=AgentValidationSample(
                sample_id=job.sample_id,
                task_id=task.task_id,
                domain=case.domain,
                task_type=job.structure["task_type"],
                pattern_id=job.structure["pattern_id"],
                program_signature=job.structure["program_signature"],
                retrieval_track=task.public.retrieval_track,
                planning_track=task.public.planning_track,
                generation_status="normalized",
                generation_audit=solve_result.audit,
                agent_telemetry=solve_result.audit.telemetry,
                trajectory=solve_result.trajectory,
                quality_contract=compiled.quality_contract,
                contract_assessment=assessment,
                feedback_exposures=feedback_exposures,
                feedback_signals=feedback_signals,
                synthesis_cell=synthesis_cell,
                host_interaction_progress=(
                    HostInteractionProgress(
                        action_plan_attempted=True,
                        action_plan_contract_succeeded=True,
                        host_execution_evaluable=True,
                        answer_decision_attempted=True,
                        answer_decision_contract_succeeded=True,
                        action_contract_repair_count=(
                            solve_result.audit.action_contract_repair_count
                        ),
                        answer_contract_repair_count=(
                            solve_result.audit.answer_contract_repair_count
                        ),
                    )
                    if solve_result.audit.interaction_protocol == "host_instrumented"
                    else None
                ),
                quality_vector=vector,
                critic_example_id=example.example_id,
                counterfactual_count=generated_count,
            ),
            critic_examples=tuple(examples),
            accepted_example_ids=accepted_ids,
            reference_sample_ids=reference_sample_ids,
            counterfactual_ids=tuple(counterfactual_ids),
            counterfactual_assessments=tuple(counterfactual_assessments),
            telemetry=solve_result.audit.telemetry,
        )
    except LLMClientError as exc:
        failed_action = (
            exc.failure_artifact
            if isinstance(exc.failure_artifact, FailedActionPlan)
            else None
        )
        feedback_exposures = (
            (
                FeedbackExposure(
                    task_id=task.task_id,
                    domain=case.domain,
                    pattern_id=job.structure["pattern_id"],
                    failure_family="action_execution",
                ),
            )
            if failed_action is not None
            else ()
        )
        feedback_signals = (
            (
                failed_action_feedback(
                    task_id=task.task_id,
                    domain=case.domain,
                    pattern_id=job.structure["pattern_id"],
                    failure_category=failed_action.failure_category,
                    error_code=failed_action.error_code,
                    failed_step_index=failed_action.failed_step_index,
                ),
            )
            if failed_action is not None
            else ()
        )
        return _AgentJobResult(
            sample=AgentValidationSample(
                sample_id=job.sample_id,
                task_id=task.task_id,
                domain=case.domain,
                task_type=job.structure["task_type"],
                pattern_id=job.structure["pattern_id"],
                program_signature=job.structure["program_signature"],
                retrieval_track=task.public.retrieval_track,
                planning_track=task.public.planning_track,
                generation_status=(
                    "semantic_action_failed"
                    if failed_action is not None
                    and failed_action.failure_category == "semantic_action"
                    else "upstream_action_failed"
                    if failed_action is not None
                    and failed_action.failure_category == "upstream_data"
                    else "model_failed"
                ),
                agent_telemetry=exc.telemetry,
                feedback_exposures=feedback_exposures,
                feedback_signals=feedback_signals,
                synthesis_cell=synthesis_cell,
                failed_action_plan=failed_action,
                host_interaction_progress=exc.interaction_progress,
                error_type=type(exc).__name__,
                error_message=str(exc),
            ),
            reference_sample_ids=reference_sample_ids,
            telemetry=exc.telemetry,
        )
    except Exception as exc:
        failure = f"{task.task_id}:{type(exc).__name__}:{exc}"
        return _AgentJobResult(
            sample=AgentValidationSample(
                sample_id=job.sample_id,
                task_id=task.task_id,
                domain=case.domain,
                task_type=job.structure["task_type"],
                pattern_id=job.structure["pattern_id"],
                program_signature=job.structure["program_signature"],
                retrieval_track=task.public.retrieval_track,
                planning_track=task.public.planning_track,
                generation_status="infrastructure_failed",
                synthesis_cell=synthesis_cell,
                error_type=type(exc).__name__,
                error_message=str(exc),
            ),
            reference_sample_ids=reference_sample_ids,
            infrastructure_failures=(failure,),
        )


def _compile_runtime(case: ContractCase, task):
    compiler = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )
    compiled = ProofCarryingSampleCompiler(
        case.registry,
        compiler,
        case.plugin_set,
        semantic_policy=case.semantic_policy,
    ).compile(task, case.bundle, case.proof_graph)
    verifier = CandidateWorkflowVerifier(
        case.registry,
        semantic_policy=case.semantic_policy,
        claim_verifier=FinanceClaimVerifier() if case.domain == "finance" else None,
    )
    runtime = QualityContractRuntime(
        verifier,
        verifier_registry=compiler.verifier_registry,
    )
    return compiled, runtime


def _counterfactual_examples(
    *,
    case: ContractCase,
    task,
    compiled,
    runtime: QualityContractRuntime,
    source_trajectory,
) -> tuple[tuple[QualityCriticExample, ContractQualityAssessment, str], ...]:
    context = CounterfactualContext(
        source_sample=compiled.sample,
        task=task,
        contract=compiled.quality_contract,
        corpus=case.corpus,
        proof_graph=case.proof_graph,
        source_trajectory=source_trajectory,
    )

    def evaluate(item: CounterfactualContext, trajectory):
        return runtime.evaluate(
            item.contract,
            item.task,
            item.corpus,
            item.proof_graph,
            trajectory,
        )

    _, generated = calibrate_counterfactuals(
        (context,),
        case.counterfactual_registry,
        evaluate,
    )
    output = []
    for counterfactual in generated:
        assessment = evaluate(context, counterfactual.trajectory)
        vector = QualityVectorCompiler().compile(
            compiled.quality_contract,
            assessment,
        )
        example = build_quality_critic_example(
            task=task,
            corpus=case.corpus,
            contract=compiled.quality_contract,
            trajectory=counterfactual.trajectory,
            assessment=assessment,
            quality_vector=vector,
            candidate_source="typed_counterfactual",
            metadata={
                "counterfactual_id": counterfactual.counterfactual_id,
                "mutation_operator_id": counterfactual.mutation_operator_id,
                "mutation_family": counterfactual.mutation_family.value,
                "minimality_score": counterfactual.minimality_score,
            },
        )
        output.append((example, assessment, counterfactual.counterfactual_id))
    return tuple(output)


def _run_model_critic(
    client: JsonCompletionClient,
    examples: tuple[QualityCriticExample, ...],
    maximum_examples: int,
    *,
    maximum_concurrency: int = 1,
    checkpoint_dir: Path | None = None,
    checkpoint_config_hash: str | None = None,
    resume_from_checkpoints: bool = True,
    retry_failed_checkpoints: bool = False,
    checkpoint_stats: dict[str, int] | None = None,
) -> tuple[
    list[QualityCriticExample],
    tuple[QualityCriticPrediction, ...],
    dict[str, str],
    dict[str, tuple[ModelCallTelemetry, ...]],
    tuple[str, ...],
    int,
]:
    selected = _stratified_critic_examples(examples, maximum_examples)
    base_config_hash = checkpoint_config_hash or client.config.public_manifest_hash
    result_by_example: dict[str, _CriticJobResult] = {}
    pending: list[QualityCriticExample] = []
    stats = checkpoint_stats if checkpoint_stats is not None else {}
    stats.setdefault("loaded", 0)
    stats.setdefault("written", 0)
    for example in selected:
        checkpoint_path = _checkpoint_path(checkpoint_dir, "critic", example.example_id)
        if checkpoint_path is not None and resume_from_checkpoints:
            checkpoint = _load_checkpoint(
                checkpoint_path,
                config_hash=_critic_job_checkpoint_hash(base_config_hash, example),
                version=CRITIC_CHECKPOINT_VERSION,
                model=_CriticJobResult,
            )
            if checkpoint is not None and not (
                retry_failed_checkpoints and checkpoint.prediction is None
            ):
                result_by_example[example.example_id] = checkpoint
                stats["loaded"] += 1
                continue
        pending.append(example)

    def record(example: QualityCriticExample, result: _CriticJobResult) -> None:
        result_by_example[example.example_id] = result
        checkpoint_path = _checkpoint_path(checkpoint_dir, "critic", example.example_id)
        if checkpoint_path is not None:
            _write_checkpoint(
                checkpoint_path,
                config_hash=_critic_job_checkpoint_hash(base_config_hash, example),
                version=CRITIC_CHECKPOINT_VERSION,
                payload=result,
            )
            stats["written"] += 1

    if maximum_concurrency == 1:
        for example in pending:
            record(example, _execute_critic_job(client, example))
    else:
        with ThreadPoolExecutor(max_workers=maximum_concurrency) as executor:
            futures = {
                executor.submit(_execute_critic_job, client, example): example
                for example in pending
            }
            for future in as_completed(futures):
                example = futures[future]
                record(example, future.result())

    ordered_results = tuple(result_by_example[item.example_id] for item in selected)
    prediction_by_example = {
        item.example_id: item.prediction
        for item in ordered_results
        if item.prediction is not None
    }
    prompt_hash_by_example = {
        item.example_id: item.prompt_manifest_hash
        for item in ordered_results
        if item.prompt_manifest_hash is not None
    }
    telemetry_by_example = {
        item.example_id: item.telemetry for item in ordered_results if item.telemetry
    }
    failures = tuple(item.failure for item in ordered_results if item.failure is not None)
    updated = [
        example.model_copy(
            update={
                "advisory_annotations": (
                    prediction_as_advisory_annotation(prediction_by_example[example.example_id]),
                )
            }
        )
        if example.example_id in prediction_by_example
        else example
        for example in examples
    ]
    predictions = tuple(
        prediction_by_example[item.example_id]
        for item in selected
        if item.example_id in prediction_by_example
    )
    return (
        updated,
        predictions,
        prompt_hash_by_example,
        telemetry_by_example,
        failures,
        len(selected),
    )


def _execute_critic_job(
    client: JsonCompletionClient,
    example: QualityCriticExample,
) -> _CriticJobResult:
    try:
        result = LLMQualityCritic(client).predict_with_audit(example)
        return _CriticJobResult(
            example_id=example.example_id,
            prediction=result.prediction,
            prompt_manifest_hash=result.prompt_manifest_hash,
            telemetry=result.telemetry,
        )
    except LLMClientError as exc:
        return _CriticJobResult(
            example_id=example.example_id,
            telemetry=exc.telemetry,
            failure=f"{example.example_id}:{type(exc).__name__}:{exc}",
        )
    except Exception as exc:
        return _CriticJobResult(
            example_id=example.example_id,
            failure=f"{example.example_id}:{type(exc).__name__}:{exc}",
        )


def _stratified_critic_examples(
    examples: tuple[QualityCriticExample, ...],
    maximum_examples: int,
) -> tuple[QualityCriticExample, ...]:
    ordered = tuple(sorted(examples, key=lambda item: item.example_id))
    limit = min(maximum_examples, len(ordered))
    if limit <= 0:
        return ()

    domains = tuple(sorted({item.domain for item in ordered}))
    if domains:
        # D5 needs Critic-reviewed accepted candidates, so reserve roughly two
        # thirds of a production Critic budget for accepted real trajectories.
        # Keep at least one slot per domain for diagnostic examples in tiny runs.
        desired_accepted_per_domain = (
            2 * limit + 3 * len(domains) - 1
        ) // (3 * len(domains))
        diagnostic_cap = max(limit // len(domains) - 1, 0)
        accepted_reserve_per_domain = min(
            desired_accepted_per_domain,
            diagnostic_cap,
        )
    else:
        accepted_reserve_per_domain = 0
    output: list[QualityCriticExample] = []
    selected_ids: set[str] = set()
    for domain in domains:
        accepted = tuple(
            item
            for item in ordered
            if item.domain == domain
            and item.candidate_source == "real_agent"
            and item.contract_annotation.acceptability.value == "accept"
        )
        for example in accepted[:accepted_reserve_per_domain]:
            output.append(example)
            selected_ids.add(example.example_id)

    diagnostic_groups: dict[str, list[QualityCriticExample]] = defaultdict(list)
    accepted_overflow_groups: dict[str, list[QualityCriticExample]] = defaultdict(list)
    for example in ordered:
        if example.example_id in selected_ids:
            continue
        key = "|".join(
            (
                example.domain,
                example.candidate_source,
                example.contract_annotation.acceptability.value,
            )
        )
        is_accepted_real = (
            example.candidate_source == "real_agent"
            and example.contract_annotation.acceptability.value == "accept"
        )
        target = accepted_overflow_groups if is_accepted_real else diagnostic_groups
        target[key].append(example)

    for groups in (diagnostic_groups, accepted_overflow_groups):
        group_keys = sorted(groups)
        index = 0
        while len(output) < limit:
            emitted = False
            for key in group_keys:
                if index < len(groups[key]):
                    output.append(groups[key][index])
                    emitted = True
                    if len(output) >= limit:
                        break
            if not emitted:
                break
            index += 1
        if len(output) >= limit:
            break
    return tuple(output)


def _build_report(
    *,
    config: AgentValidationConfig,
    samples: tuple[AgentValidationSample, ...],
    dataset: QualityCriticDataset,
    alignment,
    selection,
    utility_protocol,
    counterfactual_assessments: tuple[ContractQualityAssessment, ...],
    telemetry: tuple[ModelCallTelemetry, ...],
    infrastructure_failures: tuple[str, ...],
    critic_failures: tuple[str, ...],
    critic_attempted_count: int,
    critic_prompt_hashes: tuple[str, ...],
    agent_checkpoint_loaded_count: int,
    agent_checkpoint_written_count: int,
    critic_checkpoint_loaded_count: int,
    critic_checkpoint_written_count: int,
) -> AgentValidationReport:
    assessments = tuple(
        item.contract_assessment for item in samples if item.contract_assessment is not None
    )
    vectors = tuple(item.quality_vector for item in samples if item.quality_vector is not None)
    track_counts = Counter(
        f"{item.retrieval_track.value}|{item.planning_track.value}" for item in samples
    )
    track_accepted: dict[str, int] = defaultdict(int)
    for item in samples:
        if (
            item.contract_assessment is not None
            and item.contract_assessment.decision == ReleaseDecision.ACCEPTED
        ):
            track_accepted[f"{item.retrieval_track.value}|{item.planning_track.value}"] += 1
    contract_annotations = [
        item.contract_annotation
        for item in dataset.examples
        if item.candidate_source == "real_agent"
    ]
    failure_families = Counter(
        family for item in contract_annotations for family in item.failure_families
    )
    root_types = Counter(
        location.location_type for item in contract_annotations for location in item.root_locations
    )
    dimension_values: dict[str, list[float]] = defaultdict(list)
    for vector in vectors:
        for dimension in QualityDimension:
            score = vector.score_for(dimension)
            if score is not None:
                dimension_values[dimension.value].append(score)
    agent_model_counts = Counter(
        item.generation_audit.selected_model
        for item in samples
        if item.generation_audit is not None and item.generation_audit.selected_model is not None
    )
    critic_model_counts = Counter(
        annotation.model_id
        for item in dataset.examples
        for annotation in item.advisory_annotations
        if annotation.model_id is not None
    )
    critic_success_count = sum(critic_model_counts.values())
    agent_failure_types = Counter(
        call.error_type
        for item in samples
        for call in item.agent_telemetry
        if call.error_type is not None
    )
    agent_contract_errors = Counter(
        error
        for item in samples
        for call in item.agent_telemetry
        for error in call.contract_errors
    )
    total_costs = [item.estimated_cost for item in telemetry if item.estimated_cost is not None]
    normalized_count = sum(item.trajectory is not None for item in samples)
    requested_task_counts = config.resolved_domain_task_targets
    track_multiplier = len(config.retrieval_tracks) * len(config.planning_tracks)
    requested_candidate_counts = {
        domain: count * track_multiplier for domain, count in requested_task_counts.items()
    }
    normalized_by_domain = Counter(item.domain for item in samples if item.trajectory is not None)
    pattern_counts = Counter(item.pattern_id for item in samples)
    normalized_by_pattern = Counter(
        item.pattern_id for item in samples if item.trajectory is not None
    )
    accepted_by_pattern = Counter(
        item.pattern_id
        for item in samples
        if item.contract_assessment is not None
        and item.contract_assessment.decision == ReleaseDecision.ACCEPTED
    )
    domain_completion_rates = {
        domain: normalized_by_domain.get(domain, 0) / requested
        for domain, requested in requested_candidate_counts.items()
    }
    host_protocol = config.model.interaction_protocol == "host_instrumented"
    stage_progress = tuple(
        item.host_interaction_progress
        for item in samples
        if host_protocol and item.host_interaction_progress is not None
    )
    action_plan_attempted_count = sum(
        item.action_plan_attempted for item in stage_progress
    )
    action_plan_contract_success_count = sum(
        item.action_plan_contract_succeeded for item in stage_progress
    )
    host_execution_evaluable_count = sum(
        item.host_execution_evaluable for item in stage_progress
    )
    answer_decision_attempted_count = sum(
        item.answer_decision_attempted for item in stage_progress
    )
    answer_decision_contract_success_count = sum(
        item.answer_decision_contract_succeeded for item in stage_progress
    )
    feedback_route_counts = Counter(
        signal.route.value for item in samples for signal in item.feedback_signals
    )
    status = (
        "failed"
        if not normalized_count
        else "partial"
        if infrastructure_failures or critic_failures or normalized_count != len(samples)
        else "completed"
    )
    identity = {
        "version": AGENT_VALIDATION_VERSION,
        "config_hash": config.config_hash,
        "sample_ids": tuple(item.sample_id for item in samples),
        "critic_dataset_id": dataset.dataset_id,
        "selection_id": selection.selection_id,
        "training_utility_protocol_hash": utility_protocol.protocol_hash,
    }
    return AgentValidationReport(
        run_id=canonical_hash(identity, prefix="agent_validation_run:"),
        config_hash=config.config_hash,
        model_config_hash=config.model.public_manifest_hash,
        requested_model=config.model.model,
        interaction_protocol=config.model.interaction_protocol,
        requested_domain_task_counts=requested_task_counts,
        requested_domain_candidate_counts=requested_candidate_counts,
        domain_completion_rates=domain_completion_rates,
        attempted_count=len(samples),
        api_success_count=sum(item.generation_audit is not None for item in samples),
        normalized_trajectory_count=normalized_count,
        normalized_trajectory_rate=(normalized_count / len(samples) if samples else 0),
        contract_evaluated_count=len(assessments),
        accepted_count=sum(item.decision == ReleaseDecision.ACCEPTED for item in assessments),
        contract_acceptance_rate=(
            sum(item.decision == ReleaseDecision.ACCEPTED for item in assessments)
            / len(assessments)
            if assessments
            else 0
        ),
        quarantined_count=sum(item.decision == ReleaseDecision.QUARANTINED for item in assessments),
        rejected_count=sum(item.decision == ReleaseDecision.REJECTED for item in assessments),
        counterfactual_count=len(counterfactual_assessments),
        counterfactual_rejection_rate=(
            None
            if not counterfactual_assessments
            else sum(
                item.decision == ReleaseDecision.REJECTED for item in counterfactual_assessments
            )
            / len(counterfactual_assessments)
        ),
        domain_counts=dict(sorted(Counter(item.domain for item in samples).items())),
        task_type_counts=dict(sorted(Counter(item.task_type for item in samples).items())),
        pattern_counts=dict(sorted(pattern_counts.items())),
        program_signature_counts=dict(
            sorted(Counter(item.program_signature for item in samples).items())
        ),
        pattern_completion_rates={
            key: normalized_by_pattern.get(key, 0) / count
            for key, count in sorted(pattern_counts.items())
        },
        pattern_acceptance_rates={
            key: accepted_by_pattern.get(key, 0) / count
            for key, count in sorted(pattern_counts.items())
        },
        retrieval_planning_counts=dict(sorted(track_counts.items())),
        retrieval_planning_acceptance_rates={
            key: track_accepted.get(key, 0) / count for key, count in sorted(track_counts.items())
        },
        agent_selected_model_counts=dict(sorted(agent_model_counts.items())),
        critic_selected_model_counts=dict(sorted(critic_model_counts.items())),
        critic_attempted_count=critic_attempted_count,
        critic_success_count=critic_success_count,
        critic_failure_count=len(critic_failures),
        maximum_concurrency=config.maximum_concurrency,
        agent_checkpoint_loaded_count=agent_checkpoint_loaded_count,
        agent_checkpoint_written_count=agent_checkpoint_written_count,
        critic_checkpoint_loaded_count=critic_checkpoint_loaded_count,
        critic_checkpoint_written_count=critic_checkpoint_written_count,
        agent_failure_type_counts=dict(sorted(agent_failure_types.items())),
        agent_contract_error_counts=dict(sorted(agent_contract_errors.items())),
        agent_prompt_manifest_hashes=tuple(
            sorted(
                {
                    item.generation_audit.prompt_manifest_hash
                    for item in samples
                    if item.generation_audit is not None
                }
            )
        ),
        agent_search_prompt_manifest_hashes=tuple(
            sorted(
                {
                    item.generation_audit.search_prompt_manifest_hash
                    for item in samples
                    if item.generation_audit is not None
                    and item.generation_audit.search_prompt_manifest_hash is not None
                }
            )
        ),
        agent_action_prompt_manifest_hashes=tuple(
            sorted(
                {
                    item.generation_audit.action_prompt_manifest_hash
                    for item in samples
                    if item.generation_audit is not None
                    and item.generation_audit.action_prompt_manifest_hash is not None
                }
            )
        ),
        agent_final_answer_prompt_manifest_hashes=tuple(
            sorted(
                {
                    item.generation_audit.final_answer_prompt_manifest_hash
                    for item in samples
                    if item.generation_audit is not None
                    and item.generation_audit.final_answer_prompt_manifest_hash is not None
                }
            )
        ),
        critic_prompt_manifest_hashes=critic_prompt_hashes,
        quality_vector_policy_hashes=tuple(sorted({item.policy_hash for item in vectors})),
        quality_selection_policy_hash=selection.policy_hash,
        failure_family_counts=dict(sorted(failure_families.items())),
        root_location_type_counts=dict(sorted(root_types.items())),
        quality_dimension_means={
            key: mean(values) for key, values in sorted(dimension_values.items())
        },
        prompt_tokens=sum(item.prompt_tokens or 0 for item in telemetry),
        completion_tokens=sum(item.completion_tokens or 0 for item in telemetry),
        total_tokens=sum(item.total_tokens or 0 for item in telemetry),
        estimated_cost=sum(total_costs) if total_costs else None,
        contract_repair_count=sum(
            item.generation_audit.contract_repair_count
            for item in samples
            if item.generation_audit is not None
        ),
        action_plan_attempted_count=action_plan_attempted_count,
        action_plan_contract_success_count=action_plan_contract_success_count,
        action_plan_contract_success_rate=(
            action_plan_contract_success_count / action_plan_attempted_count
            if action_plan_attempted_count
            else 0
        ),
        host_execution_evaluable_count=host_execution_evaluable_count,
        host_execution_evaluable_rate=(
            host_execution_evaluable_count / action_plan_attempted_count
            if action_plan_attempted_count
            else 0
        ),
        answer_decision_attempted_count=answer_decision_attempted_count,
        answer_decision_contract_success_count=answer_decision_contract_success_count,
        answer_decision_contract_success_rate=(
            answer_decision_contract_success_count / answer_decision_attempted_count
            if answer_decision_attempted_count
            else 0
        ),
        action_first_call_success_count=sum(
            item.action_plan_contract_succeeded
            and item.action_contract_repair_count == 0
            for item in stage_progress
        ),
        action_repaired_success_count=sum(
            item.action_plan_contract_succeeded
            and item.action_contract_repair_count > 0
            for item in stage_progress
        ),
        answer_first_call_success_count=sum(
            item.answer_decision_contract_succeeded
            and item.answer_contract_repair_count == 0
            for item in stage_progress
        ),
        answer_repaired_success_count=sum(
            item.answer_decision_contract_succeeded
            and item.answer_contract_repair_count > 0
            for item in stage_progress
        ),
        feedback_route_counts=dict(sorted(feedback_route_counts.items())),
        critic_dataset_id=dataset.dataset_id,
        critic_example_count=len(dataset.examples),
        alignment_report=alignment,
        quality_selection=selection,
        training_utility_protocol=utility_protocol,
        infrastructure_failures=infrastructure_failures,
        critic_failures=critic_failures,
        status=status,
        notes=(
            "DeepSeek quality labels are model_advisory and are not reported as human agreement.",
            "D1-D5 training utility is frozen as a planned protocol; no training gain is claimed.",
            "Contract decisions remain authoritative over Quality Critic scores.",
            "Host replay availability is an execution property, not model self-verification.",
            "Selected, used, and cited evidence are equal by controlled-task assumption.",
        ),
        samples=samples,
    )


def _task_structure(task) -> dict[str, str]:
    pattern = task.metadata.get("task_pattern") or {}
    nodes = tuple(task.program_skeleton.nodes) if task.program_skeleton is not None else ()
    program_signature = canonical_hash(
        tuple(
            (
                node.operator_id,
                tuple(node.dependencies),
                node.parameters,
            )
            for node in nodes
        ),
        prefix="agent_program_signature:",
    )
    return {
        "task_type": task.task_type,
        "pattern_id": str(pattern.get("pattern_id") or task.task_type),
        "program_signature": program_signature,
    }


def _checkpoint_path(
    checkpoint_root: Path | None,
    kind: str,
    identity: str,
) -> Path | None:
    if checkpoint_root is None:
        return None
    token = canonical_hash(
        {"kind": kind, "identity": identity},
        prefix="validation_checkpoint_path:",
    ).split(":", 1)[1]
    return checkpoint_root / kind / f"{token}.json"


def _agent_job_checkpoint_hash(
    config: AgentValidationConfig,
    job: _AgentJob,
) -> str:
    return canonical_hash(
        {
            "model_config_hash": config.model.public_manifest_hash,
            "generate_counterfactuals": config.generate_counterfactuals,
            "agent_validation_version": AGENT_VALIDATION_VERSION,
            "agent_solver_version": LLM_AGENT_SOLVER_VERSION,
            "agent_prompt_version": LLM_AGENT_PROMPT_VERSION,
            "agent_response_schema_version": AGENT_RESPONSE_SCHEMA_VERSION,
            "public_task": job.task.public,
            "operation_registry_manifest": job.case.registry.manifest(),
        },
        prefix="agent_job_checkpoint_contract:",
    )


def _critic_job_checkpoint_hash(
    base_config_hash: str,
    example: QualityCriticExample,
) -> str:
    return canonical_hash(
        {
            "base_config_hash": base_config_hash,
            "critic_prompt_version": LLM_CRITIC_PROMPT_VERSION,
            "critic_example": example,
        },
        prefix="critic_job_checkpoint_contract:",
    )


def _load_checkpoint(
    path: Path,
    *,
    config_hash: str,
    version: str,
    model: type[BaseModel],
) -> Any | None:
    if not path.exists():
        return None
    wrapper = json.loads(path.read_text(encoding="utf-8"))
    if wrapper.get("version") != version or wrapper.get("config_hash") != config_hash:
        return None
    payload = wrapper.get("payload")
    expected_hash = canonical_hash(payload, prefix="validation_checkpoint_payload:")
    if wrapper.get("payload_hash") != expected_hash:
        raise ValueError(f"checkpoint integrity failure: {path}")
    return model.model_validate(payload)


def _write_checkpoint(
    path: Path,
    *,
    config_hash: str,
    version: str,
    payload: BaseModel,
) -> None:
    serialized = payload.model_dump(mode="json", exclude_none=True)
    _write_json(
        path,
        {
            "version": version,
            "config_hash": config_hash,
            "payload_hash": canonical_hash(
                serialized,
                prefix="validation_checkpoint_payload:",
            ),
            "payload": serialized,
        },
    )


def write_agent_validation_artifacts(
    artifacts: AgentValidationArtifacts,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        output_dir / "agent_validation_report.json",
        artifacts.report.model_dump(mode="json", exclude_none=True),
    )
    _write_jsonl(
        output_dir / "agent_validation_samples.jsonl",
        (item.model_dump(mode="json", exclude_none=True) for item in artifacts.report.samples),
    )
    _write_jsonl(
        output_dir / "quality_critic_dataset.jsonl",
        (
            item.model_dump(mode="json", exclude_none=True)
            for item in artifacts.critic_dataset.examples
        ),
    )
    _write_json(
        output_dir / "training_utility_protocol.json",
        artifacts.report.training_utility_protocol.model_dump(
            mode="json",
            exclude_none=True,
        ),
    )
    _write_json(
        output_dir / "manifest.json",
        {
            "run_id": artifacts.report.run_id,
            "report_hash": artifacts.report.report_hash,
            "critic_dataset_id": artifacts.critic_dataset.dataset_id,
            "critic_dataset_hash": artifacts.critic_dataset.dataset_hash,
            "training_utility_protocol_hash": (
                artifacts.report.training_utility_protocol.protocol_hash
            ),
            "model_config_hash": artifacts.report.model_config_hash,
            "agent_prompt_manifest_hashes": (artifacts.report.agent_prompt_manifest_hashes),
            "critic_prompt_manifest_hashes": (artifacts.report.critic_prompt_manifest_hashes),
            "quality_vector_policy_hashes": (artifacts.report.quality_vector_policy_hashes),
            "quality_selection_policy_hash": (artifacts.report.quality_selection_policy_hash),
        },
    )


def _write_json(path: Path, payload) -> None:
    _atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_jsonl(path: Path, rows) -> None:
    _atomic_write_text(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
