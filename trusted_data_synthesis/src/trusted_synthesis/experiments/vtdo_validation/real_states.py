from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from copy import deepcopy

from trusted_synthesis.core.evaluation.contracts import (
    QualityContractCompiler,
    QualityContractRuntime,
)
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory import (
    TrajectoryValidityEvaluator,
    make_trajectory_verification_context,
    map_trajectory_to_state,
)
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.schema import ActionType, Trajectory
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.domains.finance.verification import FinanceClaimVerifier
from trusted_synthesis.experiments.agent_validation.schema import (
    AgentValidationConfig,
    AgentValidationReport,
)
from trusted_synthesis.experiments.agent_validation.tracks import materialize_track_variant
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    ContractCase,
    build_pattern_validation_cases,
)
from trusted_synthesis.experiments.training_utility_v09.finance_archive_materialization import (
    FinanceArchiveBindingProvider,
)
from trusted_synthesis.hashing import canonical_hash

from .schema import RealStateExperimentConfig, RealStateSpaceReport


def run_real_state_space_experiment(
    config: RealStateExperimentConfig,
) -> tuple[RealStateSpaceReport, tuple[dict[str, object], ...]]:
    """Replay persisted DeepSeek trajectories through the current frozen quotient mapper."""

    report = AgentValidationReport.model_validate_json(
        (config.agent_artifact_dir / "agent_validation_report.json").read_text(encoding="utf-8")
    )
    agent_config = AgentValidationConfig.from_json(config.agent_config_path)
    if report.config_hash != agent_config.config_hash:
        raise ValueError("persisted Agent report and replay config hashes differ")
    cases = _build_cases(agent_config)
    jobs: dict[str, tuple[ContractCase, TaskPackage]] = {}
    for case in cases:
        for retrieval_track in agent_config.retrieval_tracks:
            for planning_track in agent_config.planning_tracks:
                task = materialize_track_variant(
                    case.task,
                    case.corpus,
                    retrieval_track=retrieval_track,
                    planning_track=planning_track,
                )
                jobs[task.task_id] = (case, task)

    failures: Counter[str] = Counter()
    rows: list[dict[str, object]] = []
    state_validity: defaultdict[str, list[float]] = defaultdict(list)
    raw_hashes: set[str] = set()
    state_ids: set[str] = set()
    semantic_mutation_count = 0
    semantic_mutation_separated = 0
    reconstructed_context_count = 0
    source_accepted_trajectory_count = 0
    current_replay_valid_trajectory_count = 0
    requested = 0
    for sample in report.samples:
        if sample.domain not in config.include_domains:
            continue
        requested += 1
        if sample.trajectory is None:
            failures["trajectory_missing"] += 1
            continue
        matched = jobs.get(sample.task_id)
        if matched is None:
            failures["task_reconstruction_missing"] += 1
            continue
        case, task = matched
        if sample.program_signature != _program_signature(task):
            failures["program_signature_drift"] += 1
            continue
        if sample.quality_contract is None:
            failures["frozen_quality_contract_missing"] += 1
            continue
        source_accepted_trajectory_count += int(
            sample.contract_assessment is not None
            and sample.contract_assessment.decision == ReleaseDecision.ACCEPTED
        )
        try:
            compiled, evaluator, context = _compile_context(
                case,
                task,
                frozen_quality_contract=sample.quality_contract,
            )
        except Exception as exc:
            failures[f"context_compile:{type(exc).__name__}"] += 1
            continue
        if sample.quality_contract != compiled.quality_contract:
            failures["quality_contract_drift"] += 1
        reconstructed_context_count += 1
        try:
            original_report = evaluator.evaluate(context, sample.trajectory)
            original = map_trajectory_to_state(
                context,
                sample.trajectory,
                program_node_aliases=original_report.program_node_mapping,
            )
        except Exception as exc:
            failures[f"original_mapping:{type(exc).__name__}"] += 1
            continue
        current_replay_valid_trajectory_count += int(original_report.valid)
        contract_drifted = sample.quality_contract != compiled.quality_contract
        variants = [sample.trajectory]
        variants.extend(
            _surface_variant(sample.trajectory, index)
            for index in range(config.surface_variants_per_trajectory)
        )
        reordered = _independent_reorder(sample.trajectory, task)
        if reordered is not None:
            variants.append(reordered)
        mapped_variant_count = 0
        for variant in variants:
            try:
                variant_report = evaluator.evaluate(context, variant)
                assignment = map_trajectory_to_state(
                    context,
                    variant,
                    program_node_aliases=variant_report.program_node_mapping,
                )
            except Exception as exc:
                failures[f"equivalence_probe:{type(exc).__name__}"] += 1
                continue
            if assignment.state.state_id != original.state.state_id:
                failures["equivalence_probe_state_split"] += 1
                continue
            mapped_variant_count += 1
            raw_hashes.add(assignment.trajectory_hash)
            state_ids.add(assignment.state.state_id)
            if not contract_drifted:
                state_validity[assignment.state.state_id].append(float(variant_report.valid))
            rows.append(
                {
                    "task_id": sample.task_id,
                    "domain": sample.domain,
                    "pattern_id": sample.pattern_id,
                    "trajectory_id": variant.trajectory_id,
                    "trajectory_hash": assignment.trajectory_hash,
                    "state_id": assignment.state.state_id,
                    "valid": variant_report.valid,
                    "variant_kind": (
                        "original"
                        if variant.trajectory_id == sample.trajectory.trajectory_id
                        else "controlled_equivalent"
                    ),
                }
            )
        if mapped_variant_count < 1:
            failures["no_equivalent_variant_mapped"] += 1
            continue
        semantic_mutation_count += 1
        try:
            mutation = _semantic_result_mutation(sample.trajectory)
            mutation_assignment = map_trajectory_to_state(
                context,
                mutation,
                program_node_aliases=original_report.program_node_mapping,
            )
            semantic_mutation_separated += int(
                mutation_assignment.state.state_id != original.state.state_id
            )
        except Exception as exc:
            failures[f"semantic_probe:{type(exc).__name__}"] += 1

    raw_count = len(raw_hashes)
    state_count = len(state_ids)
    merge_rate = (raw_count - state_count) / raw_count if raw_count else 0.0
    variances = [
        statistics.pvariance(values) if len(values) > 1 else 0.0
        for values in state_validity.values()
    ]
    separation_rate = (
        semantic_mutation_separated / semantic_mutation_count if semantic_mutation_count else 0.0
    )
    if raw_count == 0:
        status = "blocked"
    elif failures["quality_contract_drift"] > 0:
        status = "partial"
    elif (
        len({row["task_id"] for row in rows}) < config.minimum_real_trajectory_count
        or separation_rate < 1.0
    ):
        status = "partial"
    else:
        status = "passed"
    identity = {
        "source_run_id": report.run_id,
        "source_config_hash": report.config_hash,
        "requested": requested,
        "context_count": reconstructed_context_count,
        "source_accepted_count": source_accepted_trajectory_count,
        "current_replay_valid_count": current_replay_valid_trajectory_count,
        "raw_count": raw_count,
        "state_count": state_count,
        "failures": dict(sorted(failures.items())),
        "rows": rows,
    }
    output = RealStateSpaceReport(
        source_run_id=report.run_id,
        source_config_hash=report.config_hash,
        requested_trajectory_count=requested,
        reconstructed_context_count=reconstructed_context_count,
        mapped_trajectory_count=len({row["task_id"] for row in rows}),
        source_accepted_trajectory_count=source_accepted_trajectory_count,
        current_replay_valid_trajectory_count=current_replay_valid_trajectory_count,
        quality_contract_drift_count=failures["quality_contract_drift"],
        raw_sequence_count=raw_count,
        canonical_state_count=state_count,
        equivalent_merge_rate=merge_rate,
        mean_state_validity_variance=(statistics.fmean(variances) if variances else None),
        mean_state_contribution_variance=None,
        sequence_noise_ratio=merge_rate,
        semantic_mutation_separation_rate=separation_rate,
        reconstruction_failures=dict(sorted(failures.items())),
        evidence_level="controlled_equivalence_probe",
        status=status,
        report_hash=canonical_hash(identity, prefix="real_trajectory_state_space_report:"),
    )
    return output, tuple(rows)


def _build_cases(config: AgentValidationConfig) -> tuple[ContractCase, ...]:
    targets = config.resolved_domain_task_targets
    fixtures = build_pattern_validation_cases(per_domain=max(targets["legal"], targets["science"]))
    legal = tuple(item for item in fixtures if item.domain == "legal")[: targets["legal"]]
    science = tuple(item for item in fixtures if item.domain == "science")[: targets["science"]]
    if config.finance_task_source == "fixture":
        from trusted_synthesis.experiments.counterfactual_finance_fixture import (
            build_finance_counterfactual_cases,
        )

        finance = build_finance_counterfactual_cases(count=targets["finance"])
    else:
        archive_path = config.finance_archive_config_path
        if archive_path is None:
            raise ValueError("archive-backed replay requires a finance archive config")
        adapter = FinanceArchiveAdapter(FinanceArchiveConfig.from_json(archive_path))
        provider = FinanceArchiveBindingProvider(
            adapter,
            candidate_pool_id=config.finance_candidate_pool_id,
            sampling_partition_id=config.finance_sampling_partition,
            pool_split_seed=config.finance_pool_split_seed,
            evidence_scan_limit=config.finance_evidence_scan_limit,
            evidence_sample_size=config.finance_evidence_sample_size,
            stratum_reservoir_size=config.finance_stratum_reservoir_size,
            candidates_per_pattern=config.finance_candidates_per_pattern,
        )
        finance = provider.contract_cases(targets["finance"], seed=config.random_seed)
    return (*finance, *legal, *science)


def _compile_context(case: ContractCase, task, *, frozen_quality_contract):
    """Rebuild E/P/G while preserving the persisted Q component of Omega_x."""

    contract_compiler = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )
    compiled = ProofCarryingSampleCompiler(
        case.registry,
        contract_compiler,
        case.plugin_set,
        semantic_policy=case.semantic_policy,
        source_grounding_verifier=case.source_grounding_verifier,
    ).compile(
        task,
        case.bundle,
        case.proof_graph,
        public_corpus=case.corpus,
    )
    verifier = CandidateWorkflowVerifier(
        case.registry,
        semantic_policy=case.semantic_policy,
        claim_verifier=FinanceClaimVerifier() if case.domain == "finance" else None,
        source_grounding_verifier=case.source_grounding_verifier,
    )
    evaluator = TrajectoryValidityEvaluator(
        verifier,
        contract_runtime=QualityContractRuntime(
            verifier,
            verifier_registry=contract_compiler.verifier_registry,
        ),
    )
    context = make_trajectory_verification_context(
        task,
        case.bundle,
        case.corpus,
        case.proof_graph,
        frozen_quality_contract,
        compiled.oracle_execution_specification,
    )
    return compiled, evaluator, context


def _program_signature(task) -> str:
    nodes = tuple(task.public.program_skeleton.nodes) if task.public.program_skeleton else ()
    return canonical_hash(
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


def _surface_variant(source: Trajectory, index: int) -> Trajectory:
    steps = tuple(
        step.model_copy(
            update={
                "rationale_summary": f"Equivalent wording variant {index + 1}: {step.action.value}."
            }
        )
        for step in source.steps
    )
    return source.model_copy(
        update={
            "trajectory_id": canonical_hash(
                {"source": source.trajectory_id, "surface_variant": index},
                prefix="trajectory_surface_probe:",
            ),
            "steps": steps,
            "generator_version": f"controlled_surface_probe.v{index + 1}",
        }
    )


def _independent_reorder(source: Trajectory, task) -> Trajectory | None:
    nodes = {item.node_id: item for item in task.oracle.task_program.nodes}
    candidates = [
        index
        for index, step in enumerate(source.steps)
        if step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}
        and step.program_node_id in nodes
    ]
    for left_position, left_index in enumerate(candidates):
        left = source.steps[left_index]
        left_node = nodes[left.program_node_id]
        for right_index in candidates[left_position + 1 :]:
            right = source.steps[right_index]
            right_node = nodes[right.program_node_id]
            if (
                left_node.node_id in right_node.dependencies
                or right_node.node_id in left_node.dependencies
            ):
                continue
            if left.output_ref and left.output_ref in right.input_refs:
                continue
            if right.output_ref and right.output_ref in left.input_refs:
                continue
            steps = list(source.steps)
            steps[left_index], steps[right_index] = steps[right_index], steps[left_index]
            reindexed = tuple(
                step.model_copy(update={"step_index": index})
                for index, step in enumerate(steps, start=1)
            )
            return source.model_copy(
                update={
                    "trajectory_id": canonical_hash(
                        {
                            "source": source.trajectory_id,
                            "reordered": (left_node.node_id, right_node.node_id),
                        },
                        prefix="trajectory_dependency_probe:",
                    ),
                    "steps": reindexed,
                }
            )
    return None


def _semantic_result_mutation(source: Trajectory) -> Trajectory:
    answer = deepcopy(source.final_answer)
    result = answer.get("result")
    if isinstance(result, dict):
        result = {**result, "semantic_probe_marker": "changed_result"}
    else:
        result = {"original": result, "semantic_probe_marker": "changed_result"}
    answer["result"] = result
    return source.model_copy(
        update={
            "trajectory_id": canonical_hash(
                {"source": source.trajectory_id, "mutation": "result_semantics"},
                prefix="trajectory_semantic_probe:",
            ),
            "final_answer": answer,
        }
    )
