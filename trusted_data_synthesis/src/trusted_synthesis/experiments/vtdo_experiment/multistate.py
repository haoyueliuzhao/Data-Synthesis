from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.evaluation.contracts import (
    QualityContractCompiler,
    QualityContractRuntime,
)
from trusted_synthesis.core.operations.program import TaskProgramExecutor
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.task.program import InputRefKind
from trusted_synthesis.core.task.schema import TaskPackage, TaskRequirement
from trusted_synthesis.core.trajectory import (
    TrajectoryStateAssignment,
    TrajectoryValidityEvaluator,
    TrajectoryValidityReport,
    make_trajectory_verification_context,
    map_trajectory_to_state,
)
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    TrajectoryStep,
    WorkflowKind,
)
from trusted_synthesis.core.trajectory.specification import TrajectoryVerificationContext
from trusted_synthesis.core.vtdo import TrajectoryStateCatalog, make_trajectory_state_catalog
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.domains.finance.verification import FinanceClaimVerifier
from trusted_synthesis.experiments.finance_archive import FinanceArchiveBindingProvider
from trusted_synthesis.hashing import canonical_hash

FINANCE_MULTI_STATE_VERSION = "finance_multi_state.v2"
MULTI_STATE_GENERATOR_VERSION = "verified_lineage_state_generator.v2"

LineageStrategy = Literal[
    "compact_direct",
    "broad_direct",
    "compact_verify_frontier",
    "broad_full_lineage",
    "compact_output_lineage",
]

_STRATEGIES: tuple[LineageStrategy, ...] = (
    "compact_direct",
    "broad_direct",
    "compact_verify_frontier",
    "broad_full_lineage",
    "compact_output_lineage",
)


class FinanceTaskCapacityError(ValueError):
    """Preserve the full strategy funnel when a task has too few unique states."""

    def __init__(
        self,
        *,
        accepted_state_count: int,
        minimum_state_count: int,
        strategy_attempt_count: int,
        strategy_verifier_pass_count: int,
        duplicate_state_count: int,
    ) -> None:
        super().__init__(f"accepted_state_capacity={accepted_state_count}<{minimum_state_count}")
        self.strategy_attempt_count = strategy_attempt_count
        self.strategy_verifier_pass_count = strategy_verifier_pass_count
        self.duplicate_state_count = duplicate_state_count


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceMultiStateConfig(FrozenModel):
    enabled: bool = True
    finance_archive_config_path: Path
    task_count: int = Field(default=100, ge=1)
    candidate_task_oversampling_factor: float = Field(default=1.25, ge=1.0, le=3.0)
    minimum_states_per_task: int = Field(default=3, ge=2, le=5)
    maximum_states_per_task: int = Field(default=5, ge=3, le=5)
    random_seed: int = 20260731
    candidate_pool_id: str = "vtdo.finance.multi_state.v1"
    sampling_partition: Literal["A", "B"] = "A"
    pool_split_seed: int = 20260731
    evidence_scan_limit: int = Field(default=200_000, ge=1)
    evidence_sample_size: int = Field(default=50_000, ge=1)
    stratum_reservoir_size: int = Field(default=5_000, ge=1)
    candidates_per_pattern: int = Field(default=2_000, ge=1)
    require_corpus_disjoint: bool = True

    @model_validator(mode="after")
    def validate_state_bounds(self) -> FinanceMultiStateConfig:
        if self.minimum_states_per_task > self.maximum_states_per_task:
            raise ValueError("minimum states per task exceeds maximum")
        return self


class AcceptedFinanceState(FrozenModel):
    strategy: LineageStrategy
    trajectory: Trajectory
    validity_report: TrajectoryValidityReport
    assignment: TrajectoryStateAssignment

    @model_validator(mode="after")
    def validate_acceptance(self) -> AcceptedFinanceState:
        if not self.validity_report.valid:
            raise ValueError("an accepted Finance state must pass independent verification")
        if self.validity_report.trajectory_id != self.trajectory.trajectory_id:
            raise ValueError("state validity report belongs to another trajectory")
        if self.assignment.trajectory_id != self.trajectory.trajectory_id:
            raise ValueError("state assignment belongs to another trajectory")
        return self


class RejectedFinanceAttempt(FrozenModel):
    mutation_id: Literal["wrong_answer_payload"] = "wrong_answer_payload"
    trajectory: Trajectory
    validity_report: TrajectoryValidityReport

    @model_validator(mode="after")
    def validate_rejection(self) -> RejectedFinanceAttempt:
        if self.validity_report.valid:
            raise ValueError("a rejected Finance attempt unexpectedly passed verification")
        return self


class FinanceTaskStateArtifact(FrozenModel):
    artifact_id: str = Field(min_length=1)
    omega: TrajectoryVerificationContext
    pattern_id: str = Field(min_length=1)
    binding_id: str = Field(min_length=1)
    state_catalog: TrajectoryStateCatalog
    accepted_states: tuple[AcceptedFinanceState, ...] = Field(min_length=3, max_length=5)
    strategy_attempt_count: int = Field(ge=1)
    strategy_verifier_pass_count: int = Field(ge=0)
    duplicate_state_count: int = Field(ge=0)
    rejected_attempts: tuple[RejectedFinanceAttempt, ...] = Field(min_length=1)
    operation_graph_count: int = Field(ge=1)
    evidence_lineage_count: int = Field(ge=1)
    retrieval_scope_count: int = Field(ge=1)
    program_diversity_claimed: bool = False
    schema_version: str = FINANCE_MULTI_STATE_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> FinanceTaskStateArtifact:
        task_id = self.omega.task.task_id
        states = tuple(item.assignment.state for item in self.accepted_states)
        if any(item.trajectory.task_id != task_id for item in self.accepted_states):
            raise ValueError("multi-state artifact crosses task conditions")
        if len({state.state_id for state in states}) != len(states):
            raise ValueError("multi-state artifact contains duplicate quotient states")
        if set(self.state_catalog.states) != {state.state_id for state in states}:
            raise ValueError("state catalog does not exactly cover accepted states")
        if self.state_catalog.verification_context_id != self.omega.context_id:
            raise ValueError("state catalog belongs to another Omega context")
        if self.strategy_verifier_pass_count < len(self.accepted_states):
            raise ValueError("accepted states exceed independently verified strategies")
        if self.strategy_attempt_count < self.strategy_verifier_pass_count:
            raise ValueError("strategy verifier pass count exceeds attempts")
        if self.program_diversity_claimed:
            raise ValueError("v1 states vary execution and lineage, not frozen Oracle programs")
        if self.artifact_id != finance_task_state_artifact_id(self):
            raise ValueError("Finance task-state artifact identity is invalid")
        return self


class FinanceMultiStateReport(FrozenModel):
    report_id: str = Field(min_length=1)
    config_hash: str = Field(min_length=1)
    kg_build_id: str = Field(min_length=1)
    requested_task_count: int = Field(ge=0)
    attempted_task_count: int = Field(ge=0)
    accepted_task_count: int = Field(ge=0)
    rejected_task_count: int = Field(ge=0)
    accepted_trajectory_count: int = Field(ge=0)
    adversarial_mutation_rejection_count: int = Field(ge=0)
    strategy_attempt_count: int = Field(ge=0)
    strategy_verifier_pass_count: int = Field(ge=0)
    strategy_verifier_failure_count: int = Field(ge=0)
    duplicate_state_count: int = Field(ge=0)
    tasks_with_three_or_more_states: int = Field(ge=0)
    minimum_states_observed: int = Field(ge=0)
    maximum_states_observed: int = Field(ge=0)
    mean_states_per_task: float = Field(ge=0)
    distinct_operation_graph_count: int = Field(ge=0)
    distinct_evidence_lineage_count: int = Field(ge=0)
    distinct_retrieval_scope_count: int = Field(ge=0)
    independent_verifier_pass_rate: float = Field(ge=0, le=1)
    quotient_probe_raw_sequence_count: int = Field(ge=0)
    quotient_probe_state_count: int = Field(ge=0)
    quotient_merge_rate: float = Field(ge=0, le=1)
    quotient_state_validity_variance: float | None = Field(default=None, ge=0)
    failure_counts: dict[str, int]
    status: Literal["passed", "partial", "blocked"]
    limitations: tuple[str, ...]
    schema_version: str = FINANCE_MULTI_STATE_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceMultiStateReport:
        if self.attempted_task_count != self.accepted_task_count + self.rejected_task_count:
            raise ValueError("Finance multi-state task accounting is inconsistent")
        if self.accepted_task_count > self.requested_task_count:
            raise ValueError("Finance multi-state accepted task count exceeds its quota")
        if self.strategy_attempt_count != (
            self.strategy_verifier_pass_count + self.strategy_verifier_failure_count
        ):
            raise ValueError("Finance multi-state strategy accounting is inconsistent")
        if self.status == "passed" and self.accepted_task_count != self.requested_task_count:
            raise ValueError("a passed Finance multi-state report did not fill its task quota")
        if self.report_id != finance_multi_state_report_id(self):
            raise ValueError("Finance multi-state report identity is invalid")
        return self


def build_finance_multi_state_dataset(
    config: FinanceMultiStateConfig,
    output_dir: Path,
) -> tuple[FinanceMultiStateReport, tuple[FinanceTaskStateArtifact, ...]]:
    """Materialize 3-5 verified quotient states for each real Finance task."""

    adapter = FinanceArchiveAdapter(
        FinanceArchiveConfig.from_json(config.finance_archive_config_path)
    )
    provider = FinanceArchiveBindingProvider(
        adapter,
        candidate_pool_id=config.candidate_pool_id,
        sampling_partition_id=config.sampling_partition,
        pool_split_seed=config.pool_split_seed,
        evidence_scan_limit=config.evidence_scan_limit,
        evidence_sample_size=config.evidence_sample_size,
        stratum_reservoir_size=config.stratum_reservoir_size,
        candidates_per_pattern=config.candidates_per_pattern,
    )
    candidate_task_count = math.ceil(config.task_count * config.candidate_task_oversampling_factor)
    cases = provider.contract_cases(
        candidate_task_count,
        seed=config.random_seed,
        require_corpus_disjoint=config.require_corpus_disjoint,
    )
    artifacts: list[FinanceTaskStateArtifact] = []
    failures: Counter[str] = Counter()
    attempted_task_count = 0
    strategy_attempt_count = 0
    strategy_verifier_pass_count = 0
    duplicate_state_count = 0
    for case in cases:
        if len(artifacts) >= config.task_count:
            break
        attempted_task_count += 1
        try:
            artifact = _build_task_artifact(case, config)
        except FinanceTaskCapacityError as exc:
            strategy_attempt_count += exc.strategy_attempt_count
            strategy_verifier_pass_count += exc.strategy_verifier_pass_count
            duplicate_state_count += exc.duplicate_state_count
            failures[f"{type(exc).__name__}:{exc}"] += 1
            continue
        except Exception as exc:
            failures[f"{type(exc).__name__}:{str(exc).split(':', 1)[0]}"] += 1
            continue
        artifacts.append(artifact)
        strategy_attempt_count += artifact.strategy_attempt_count
        strategy_verifier_pass_count += artifact.strategy_verifier_pass_count
        duplicate_state_count += artifact.duplicate_state_count

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "finance_multi_state_tasks.jsonl"
    with artifact_path.open("w", encoding="utf-8") as output:
        for artifact in artifacts:
            output.write(artifact.model_dump_json() + "\n")
    state_path = output_dir / "finance_accepted_states.jsonl"
    with state_path.open("w", encoding="utf-8") as output:
        for artifact in artifacts:
            for state in artifact.accepted_states:
                output.write(
                    json.dumps(
                        {
                            "artifact_id": artifact.artifact_id,
                            "task_id": artifact.omega.task.task_id,
                            "context_id": artifact.omega.context_id,
                            **state.model_dump(mode="json"),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )

    state_counts = [len(item.accepted_states) for item in artifacts]
    operation_hashes = {
        state.assignment.state.operation_graph_hash
        for artifact in artifacts
        for state in artifact.accepted_states
    }
    lineage_hashes = {
        state.assignment.state.evidence_lineage_hash
        for artifact in artifacts
        for state in artifact.accepted_states
    }
    retrieval_hashes = {
        _retrieval_signature(state.trajectory)
        for artifact in artifacts
        for state in artifact.accepted_states
    }
    quotient_raw, quotient_states, quotient_variance = _quotient_probe(artifacts)
    report_values = {
        "config_hash": canonical_hash(config, prefix="finance_multi_state_config:"),
        "kg_build_id": provider.kg_build_id,
        "requested_task_count": config.task_count,
        "attempted_task_count": attempted_task_count,
        "accepted_task_count": len(artifacts),
        "rejected_task_count": attempted_task_count - len(artifacts),
        "accepted_trajectory_count": sum(state_counts),
        "adversarial_mutation_rejection_count": sum(
            len(item.rejected_attempts) for item in artifacts
        ),
        "strategy_attempt_count": strategy_attempt_count,
        "strategy_verifier_pass_count": strategy_verifier_pass_count,
        "strategy_verifier_failure_count": (strategy_attempt_count - strategy_verifier_pass_count),
        "duplicate_state_count": duplicate_state_count,
        "tasks_with_three_or_more_states": sum(value >= 3 for value in state_counts),
        "minimum_states_observed": min(state_counts, default=0),
        "maximum_states_observed": max(state_counts, default=0),
        "mean_states_per_task": statistics.fmean(state_counts) if state_counts else 0.0,
        "distinct_operation_graph_count": len(operation_hashes),
        "distinct_evidence_lineage_count": len(lineage_hashes),
        "distinct_retrieval_scope_count": len(retrieval_hashes),
        "independent_verifier_pass_rate": (
            strategy_verifier_pass_count / strategy_attempt_count if strategy_attempt_count else 0.0
        ),
        "quotient_probe_raw_sequence_count": quotient_raw,
        "quotient_probe_state_count": quotient_states,
        "quotient_merge_rate": (
            (quotient_raw - quotient_states) / quotient_raw if quotient_raw else 0.0
        ),
        "quotient_state_validity_variance": quotient_variance,
        "failure_counts": dict(sorted(failures.items())),
        "status": (
            "passed"
            if len(artifacts) == config.task_count
            and all(value >= config.minimum_states_per_task for value in state_counts)
            else "partial"
            if artifacts
            else "blocked"
        ),
        "limitations": (
            "States are deterministic, independently verified executions over real financial "
            "evidence; they are not yet observed model trajectories.",
            "State diversity comes from retrieval breadth, verification frontier, and evidence "
            "lineage under one frozen Oracle program. Program-DAG diversity is not claimed.",
            "Contribution consistency requires empirical training probes and is reported by the "
            "separate contribution-validation experiment.",
        ),
        "schema_version": FINANCE_MULTI_STATE_VERSION,
    }
    provisional = FinanceMultiStateReport.model_construct(report_id="pending", **report_values)
    report = FinanceMultiStateReport(
        report_id=finance_multi_state_report_id(provisional),
        **report_values,
    )
    (output_dir / "finance_multi_state_report.json").write_text(
        report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return report, tuple(artifacts)


def load_finance_multi_state_artifacts(path: Path) -> tuple[FinanceTaskStateArtifact, ...]:
    return tuple(
        FinanceTaskStateArtifact.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _build_task_artifact(case, config: FinanceMultiStateConfig) -> FinanceTaskStateArtifact:
    compiled = ProofCarryingSampleCompiler(
        case.registry,
        QualityContractCompiler(case.registry, domain_provider=case.quality_clause_provider),
        case.plugin_set,
        semantic_policy=case.semantic_policy,
        source_grounding_verifier=case.source_grounding_verifier,
    ).compile(
        case.task,
        case.bundle,
        case.proof_graph,
        public_corpus=case.corpus,
    )
    omega = make_trajectory_verification_context(
        compiled.task,
        compiled.evidence_bundle,
        compiled.public_corpus,
        compiled.proof_graph,
        compiled.quality_contract,
        compiled.oracle_execution_specification,
    )
    verifier = CandidateWorkflowVerifier(
        case.registry,
        semantic_policy=case.semantic_policy,
        claim_verifier=FinanceClaimVerifier(),
        source_grounding_verifier=case.source_grounding_verifier,
    )
    evaluator = TrajectoryValidityEvaluator(
        verifier,
        contract_runtime=QualityContractRuntime(
            verifier,
            verifier_registry=QualityContractCompiler(
                case.registry,
                domain_provider=case.quality_clause_provider,
            ).verifier_registry,
        ),
    )
    accepted: list[AcceptedFinanceState] = []
    seen_states: set[str] = set()
    strategy_attempt_count = 0
    strategy_verifier_pass_count = 0
    duplicate_state_count = 0
    for strategy in _STRATEGIES:
        strategy_attempt_count += 1
        trajectory = _compile_candidate(omega, case.registry, strategy)
        validity = evaluator.evaluate(omega, trajectory)
        if not validity.valid:
            continue
        strategy_verifier_pass_count += 1
        assignment = map_trajectory_to_state(
            omega,
            trajectory,
            program_node_aliases=validity.program_node_mapping,
        )
        if assignment.state.state_id in seen_states:
            duplicate_state_count += 1
            continue
        seen_states.add(assignment.state.state_id)
        accepted.append(
            AcceptedFinanceState(
                strategy=strategy,
                trajectory=trajectory,
                validity_report=validity,
                assignment=assignment,
            )
        )
        if len(accepted) >= config.maximum_states_per_task:
            break
    if len(accepted) < config.minimum_states_per_task:
        raise FinanceTaskCapacityError(
            accepted_state_count=len(accepted),
            minimum_state_count=config.minimum_states_per_task,
            strategy_attempt_count=strategy_attempt_count,
            strategy_verifier_pass_count=strategy_verifier_pass_count,
            duplicate_state_count=duplicate_state_count,
        )

    rejected_trajectory = _wrong_answer_attempt(accepted[0].trajectory)
    rejected_report = evaluator.evaluate(omega, rejected_trajectory)
    rejected = RejectedFinanceAttempt(
        trajectory=rejected_trajectory,
        validity_report=rejected_report,
    )
    catalog = make_trajectory_state_catalog(
        (item.assignment.state for item in accepted),
        revision_reason="verified_real_finance_multi_state_initialization",
    )
    pattern = case.task.public.metadata.get("task_pattern")
    binding = case.task.oracle.selection_contract.get("pattern_binding")
    pattern_id = (
        str(pattern.get("pattern_id")) if isinstance(pattern, dict) else case.task.public.task_type
    )
    binding_id = str(binding.get("binding_id")) if isinstance(binding, dict) else case.task.task_id
    values = {
        "omega": omega,
        "pattern_id": pattern_id,
        "binding_id": binding_id,
        "state_catalog": catalog,
        "accepted_states": tuple(accepted),
        "strategy_attempt_count": strategy_attempt_count,
        "strategy_verifier_pass_count": strategy_verifier_pass_count,
        "duplicate_state_count": duplicate_state_count,
        "rejected_attempts": (rejected,),
        "operation_graph_count": len(
            {item.assignment.state.operation_graph_hash for item in accepted}
        ),
        "evidence_lineage_count": len(
            {item.assignment.state.evidence_lineage_hash for item in accepted}
        ),
        "retrieval_scope_count": len({_retrieval_signature(item.trajectory) for item in accepted}),
        "program_diversity_claimed": False,
        "schema_version": FINANCE_MULTI_STATE_VERSION,
    }
    provisional = FinanceTaskStateArtifact.model_construct(artifact_id="pending", **values)
    return FinanceTaskStateArtifact(
        artifact_id=finance_task_state_artifact_id(provisional),
        **values,
    )


def _compile_candidate(
    omega: TrajectoryVerificationContext,
    registry,
    strategy: LineageStrategy,
) -> Trajectory:
    task = omega.task
    program = task.oracle.task_program
    evidence_by_id = omega.public_corpus.by_id()
    execution = TaskProgramExecutor(registry).execute(program, evidence_by_id)
    gold_ids = tuple(task.oracle.gold_evidence_ids)
    gold_set = set(gold_ids)
    corpus_ids = tuple(item.evidence_id for item in omega.public_corpus.evidence)
    broad = strategy.startswith("broad_")
    retrieved_ids = corpus_ids if broad else gold_ids
    full_lineage = strategy == "broad_full_lineage"
    output_lineage = strategy in {"compact_output_lineage", "compact_verify_frontier"}
    verify_frontier = strategy != "compact_verify_frontier"
    lineage_by_node = _lineage_by_node(task)

    steps: list[TrajectoryStep] = [
        TrajectoryStep(
            step_index=1,
            action=ActionType.PLAN,
            observation={
                "planning_track": task.public.planning_track.value,
                "strategy": strategy,
            },
            rationale_summary="Plan a verified execution over the frozen public task contract.",
            status=StepStatus.SUCCEEDED,
        ),
        TrajectoryStep(
            step_index=2,
            action=ActionType.SEARCH,
            tool_name="evidence.search",
            tool_input=task.public.retrieval_scope,
            observation={"matched_count": len(retrieved_ids)},
            evidence_ids=retrieved_ids,
            rationale_summary="Search the frozen public corpus under its semantic constraints.",
            status=StepStatus.SUCCEEDED,
        ),
        TrajectoryStep(
            step_index=3,
            action=ActionType.SELECT_EVIDENCE,
            observation={"selected_count": len(gold_ids)},
            evidence_ids=gold_ids,
            rationale_summary="Select the complete evidence set required by the public program.",
            status=StepStatus.SUCCEEDED,
        ),
    ]
    for node in program.nodes:
        definition = registry.require(node.operator_id)
        direct = tuple(ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.EVIDENCE)
        evidence_ids = direct
        if not direct and (
            full_lineage or (output_lineage and node.node_id == program.output_node_id)
        ):
            evidence_ids = tuple(sorted(lineage_by_node[node.node_id] & gold_set))
        action = (
            ActionType.SELECT_EVIDENCE if node.operator_id == "lookup" else ActionType.CALCULATE
        )
        steps.append(
            TrajectoryStep(
                step_index=len(steps) + 1,
                action=action,
                tool_name=definition.tool_capability,
                tool_input={"parameters": node.parameters},
                observation={"result": execution.node_outputs[node.node_id]},
                evidence_ids=evidence_ids,
                program_node_id=node.node_id,
                operator_id=node.operator_id,
                input_refs=tuple(_program_ref(ref) for ref in node.input_refs),
                output_ref=f"operation:{node.node_id}",
                rationale_summary=(
                    "Execute one typed node and preserve its chosen evidence frontier."
                ),
                status=StepStatus.SUCCEEDED,
            )
        )
    if TaskRequirement.VERIFY_RESULT in task.public.requirements:
        output_ref = f"operation:{program.output_node_id}"
        steps.append(
            TrajectoryStep(
                step_index=len(steps) + 1,
                action=ActionType.VERIFY,
                observation={
                    "verified_output_ref": output_ref,
                    "verified_result": execution.final_output,
                },
                evidence_ids=gold_ids if verify_frontier else (),
                program_node_id=program.output_node_id,
                input_refs=(output_ref,),
                rationale_summary="Request independent replay of the typed output.",
                status=StepStatus.SUCCEEDED,
            )
        )
    selected = tuple(evidence_by_id[item] for item in gold_ids)
    result = CandidateAnswerNormalizer().normalize_oracle(
        task,
        execution.final_output,
        selected,
        node_outputs=execution.node_outputs,
    )
    citations = [
        {
            "evidence_id": item.evidence_id,
            "source_id": item.source.source_id,
            "source_locator": item.source_locator.model_dump(mode="json", exclude_none=True),
        }
        for item in selected
    ]
    final_answer = {"result": result, "citations": citations}
    steps.append(
        TrajectoryStep(
            step_index=len(steps) + 1,
            action=ActionType.ANSWER,
            observation=final_answer,
            evidence_ids=gold_ids,
            rationale_summary="Return the normalized result with complete citations.",
            status=StepStatus.SUCCEEDED,
        )
    )
    identity = {
        "context_id": omega.context_id,
        "strategy": strategy,
        "steps": steps,
        "final_answer": final_answer,
        "version": MULTI_STATE_GENERATOR_VERSION,
    }
    return Trajectory(
        trajectory_id=canonical_hash(identity, prefix="finance_multi_state_trajectory:"),
        task_id=task.task_id,
        workflow_kind=WorkflowKind.CANDIDATE,
        steps=tuple(steps),
        program_execution=execution.model_dump(mode="json"),
        final_answer=final_answer,
        generator_version=MULTI_STATE_GENERATOR_VERSION,
    )


def _wrong_answer_attempt(source: Trajectory) -> Trajectory:
    final_answer = {
        "result": {"invalid_result": "deterministic_wrong_answer"},
        "citations": source.final_answer.get("citations", []),
    }
    steps = list(source.steps)
    steps[-1] = steps[-1].model_copy(update={"observation": final_answer})
    return source.model_copy(
        update={
            "trajectory_id": canonical_hash(
                {"source": source.trajectory_id, "mutation": "wrong_answer_payload"},
                prefix="finance_multi_state_rejected_attempt:",
            ),
            "steps": tuple(steps),
            "final_answer": final_answer,
            "generator_version": f"{MULTI_STATE_GENERATOR_VERSION}.mutation",
        }
    )


def _lineage_by_node(task: TaskPackage) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for node in task.oracle.task_program.nodes:
        lineage = {ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.EVIDENCE}
        for dependency in node.dependencies:
            lineage.update(result[dependency])
        result[node.node_id] = lineage
    return result


def _program_ref(ref) -> str:
    value = f"{ref.kind.value}:{ref.ref_id}"
    return f"{value}#{ref.selector}" if ref.selector else value


def _retrieval_signature(trajectory: Trajectory) -> str:
    evidence_ids = tuple(
        sorted(
            evidence_id
            for step in trajectory.steps
            if step.action == ActionType.SEARCH
            for evidence_id in step.evidence_ids
        )
    )
    return canonical_hash(evidence_ids, prefix="trajectory_retrieval_scope:")


def _surface_probe(source: Trajectory) -> Trajectory:
    steps = tuple(
        step.model_copy(
            update={"rationale_summary": f"Equivalent controlled phrasing: {step.action.value}."}
        )
        for step in source.steps
    )
    return source.model_copy(
        update={
            "trajectory_id": canonical_hash(
                {"source": source.trajectory_id, "probe": "surface_equivalence"},
                prefix="trajectory_quotient_probe:",
            ),
            "steps": steps,
            "generator_version": "quotient_surface_probe.v1",
        }
    )


def _quotient_probe(
    artifacts: list[FinanceTaskStateArtifact],
) -> tuple[int, int, float | None]:
    raw_hashes: set[str] = set()
    state_ids: set[str] = set()
    validity_by_state: dict[str, list[float]] = {}
    for artifact in artifacts:
        for item in artifact.accepted_states:
            for trajectory in (item.trajectory, _surface_probe(item.trajectory)):
                assignment = map_trajectory_to_state(
                    artifact.omega,
                    trajectory,
                    program_node_aliases=item.validity_report.program_node_mapping,
                )
                raw_hashes.add(trajectory.trajectory_hash)
                state_ids.add(assignment.state.state_id)
                validity_by_state.setdefault(assignment.state.state_id, []).append(1.0)
    variances = [
        statistics.pvariance(values) if len(values) > 1 else 0.0
        for values in validity_by_state.values()
    ]
    return (
        len(raw_hashes),
        len(state_ids),
        statistics.fmean(variances) if variances else None,
    )


def finance_task_state_artifact_id(value: FinanceTaskStateArtifact) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"artifact_id"}),
        prefix="finance_task_state_artifact:",
    )


def finance_multi_state_report_id(value: FinanceMultiStateReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_multi_state_report:",
    )
