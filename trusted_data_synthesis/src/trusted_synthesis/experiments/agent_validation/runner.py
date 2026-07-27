from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

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
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry
from trusted_synthesis.runtime.critic import LLMQualityCritic
from trusted_synthesis.runtime.tools import InMemoryEvidenceToolRuntime


@dataclass(frozen=True)
class AgentValidationArtifacts:
    report: AgentValidationReport
    critic_dataset: QualityCriticDataset


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
    agent_call_floor = base_task_count * planning_count * (retrieval_count + model_search_tracks)
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
) -> AgentValidationArtifacts:
    cases = _build_validation_cases(config)
    samples: list[AgentValidationSample] = []
    critic_examples: list[QualityCriticExample] = []
    accepted_example_ids: list[str] = []
    reference_sample_ids: list[str] = []
    counterfactual_ids: list[str] = []
    counterfactual_assessments: list[ContractQualityAssessment] = []
    all_telemetry: list[ModelCallTelemetry] = []
    infrastructure_failures: list[str] = []
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
                    "model_config_hash": config.model.public_manifest_hash,
                    "validation_version": AGENT_VALIDATION_VERSION,
                }
                sample_id = canonical_hash(
                    sample_identity,
                    prefix="agent_validation_sample:",
                )
                structure = _task_structure(task.public)
                try:
                    compiled, runtime = _compile_runtime(case, task)
                    reference_sample_ids.append(compiled.sample.sample_id)
                    solve_result = LLMAgentSolver(client, case.registry).solve_with_audit(
                        task.public,
                        InMemoryEvidenceToolRuntime(case.corpus),
                    )
                    all_telemetry.extend(solve_result.audit.telemetry)
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
                            **structure,
                        },
                    )
                    critic_examples.append(example)
                    if assessment.decision == ReleaseDecision.ACCEPTED:
                        accepted_example_ids.append(example.example_id)
                    generated_count = 0
                    if (
                        config.generate_counterfactuals
                        and assessment.decision == ReleaseDecision.ACCEPTED
                    ):
                        generated = _counterfactual_examples(
                            case=case,
                            task=task,
                            compiled=compiled,
                            runtime=runtime,
                            source_trajectory=solve_result.trajectory,
                        )
                        generated_count = len(generated)
                        for generated_example, generated_assessment, counterfactual_id in generated:
                            critic_examples.append(generated_example)
                            counterfactual_assessments.append(generated_assessment)
                            counterfactual_ids.append(counterfactual_id)
                    samples.append(
                        AgentValidationSample(
                            sample_id=sample_id,
                            task_id=task.task_id,
                            domain=case.domain,
                            task_type=structure["task_type"],
                            pattern_id=structure["pattern_id"],
                            program_signature=structure["program_signature"],
                            retrieval_track=retrieval_track,
                            planning_track=planning_track,
                            generation_status="normalized",
                            generation_audit=solve_result.audit,
                            trajectory=solve_result.trajectory,
                            contract_assessment=assessment,
                            quality_vector=vector,
                            critic_example_id=example.example_id,
                            counterfactual_count=generated_count,
                        )
                    )
                except LLMClientError as exc:
                    all_telemetry.extend(exc.telemetry)
                    samples.append(
                        AgentValidationSample(
                            sample_id=sample_id,
                            task_id=task.task_id,
                            domain=case.domain,
                            task_type=structure["task_type"],
                            pattern_id=structure["pattern_id"],
                            program_signature=structure["program_signature"],
                            retrieval_track=retrieval_track,
                            planning_track=planning_track,
                            generation_status="model_failed",
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                    )
                except Exception as exc:
                    infrastructure_failures.append(f"{task.task_id}:{type(exc).__name__}:{exc}")
                    samples.append(
                        AgentValidationSample(
                            sample_id=sample_id,
                            task_id=task.task_id,
                            domain=case.domain,
                            task_type=structure["task_type"],
                            pattern_id=structure["pattern_id"],
                            program_signature=structure["program_signature"],
                            retrieval_track=retrieval_track,
                            planning_track=planning_track,
                            generation_status="infrastructure_failed",
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                    )
    critic_predictions: tuple[QualityCriticPrediction, ...] = ()
    critic_prompt_hashes: dict[str, str] = {}
    critic_telemetry: dict[str, tuple[ModelCallTelemetry, ...]] = {}
    critic_failures: tuple[str, ...] = ()
    critic_attempted_count = 0
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
    )
    return AgentValidationArtifacts(report=report, critic_dataset=dataset)


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
) -> tuple[
    list[QualityCriticExample],
    tuple[QualityCriticPrediction, ...],
    dict[str, str],
    dict[str, tuple[ModelCallTelemetry, ...]],
    tuple[str, ...],
    int,
]:
    selected = _stratified_critic_examples(examples, maximum_examples)
    prediction_by_example: dict[str, QualityCriticPrediction] = {}
    prompt_hash_by_example: dict[str, str] = {}
    telemetry_by_example: dict[str, tuple[ModelCallTelemetry, ...]] = {}
    failures: list[str] = []
    critic = LLMQualityCritic(client)
    for example in selected:
        try:
            result = critic.predict_with_audit(example)
            prediction_by_example[example.example_id] = result.prediction
            prompt_hash_by_example[example.example_id] = result.prompt_manifest_hash
            telemetry_by_example[example.example_id] = result.telemetry
        except LLMClientError as exc:
            telemetry_by_example[example.example_id] = exc.telemetry
            failures.append(f"{example.example_id}:{type(exc).__name__}:{exc}")
        except Exception as exc:
            failures.append(f"{example.example_id}:{type(exc).__name__}:{exc}")
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
        tuple(failures),
        len(selected),
    )


def _stratified_critic_examples(
    examples: tuple[QualityCriticExample, ...],
    maximum_examples: int,
) -> tuple[QualityCriticExample, ...]:
    groups: dict[str, list[QualityCriticExample]] = defaultdict(list)
    for example in sorted(examples, key=lambda item: item.example_id):
        key = "|".join(
            (
                example.domain,
                example.candidate_source,
                example.contract_annotation.acceptability.value,
            )
        )
        groups[key].append(example)
    output: list[QualityCriticExample] = []
    group_keys = sorted(groups)
    index = 0
    while len(output) < min(maximum_examples, len(examples)):
        emitted = False
        for key in group_keys:
            if index < len(groups[key]):
                output.append(groups[key][index])
                emitted = True
                if len(output) >= maximum_examples:
                    break
        if not emitted:
            break
        index += 1
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
        agent_prompt_manifest_hashes=tuple(
            sorted(
                {
                    item.generation_audit.prompt_manifest_hash
                    for item in samples
                    if item.generation_audit is not None
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
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
