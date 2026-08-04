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
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.program import TaskProgramExecutor
from trusted_synthesis.core.operations.schema import OperationInput
from trusted_synthesis.core.synthesis import (
    JointCompilationArtifact,
    ProofCarryingSampleCompiler,
)
from trusted_synthesis.core.task.program import InputRefKind, OperationNode
from trusted_synthesis.core.task.schema import TaskPackage, TaskRequirement
from trusted_synthesis.core.trajectory import (
    TrajectoryStateAssignment,
    TrajectoryValidityEvaluator,
    TrajectoryValidityReport,
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
from trusted_synthesis.core.vtdo import (
    AcquisitionRequirement,
    AdmissibleTrajectoryVariation,
    EvidenceSupportRequirement,
    ExecutionElaboration,
    LineageRequirement,
    RetrievalElaboration,
    TrajectoryStateCatalog,
    TrajectoryStateSpaceCompilation,
    VerificationRequirement,
    compile_trajectory_state_space,
    make_admissible_trajectory_variation,
    make_trajectory_state_catalog,
)
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.domains.finance.verification import FinanceClaimVerifier
from trusted_synthesis.experiments.finance_archive import FinanceArchiveBindingProvider
from trusted_synthesis.hashing import canonical_hash

FINANCE_MULTI_STATE_VERSION = "finance_multi_state.v13"
FINANCE_DETERMINISTIC_STATE_FIXTURE_VERSION = "finance_deterministic_state_fixture.v8"

LineageStrategy = Literal[
    "compact_direct",
    "compact_projection",
    "semantic_direct",
    "semantic_projection",
    "broad_direct",
    "compact_verify_frontier",
    "broad_full_lineage",
    "compact_output_lineage",
]

_STRATEGIES: tuple[LineageStrategy, ...] = (
    "compact_direct",
    "compact_projection",
    "semantic_direct",
    "semantic_projection",
    "broad_direct",
    "compact_verify_frontier",
    "broad_full_lineage",
    "compact_output_lineage",
)


DEFAULT_FINANCE_DISCOVERY_STRATEGIES: tuple[LineageStrategy, ...] = (
    "compact_direct",
    "compact_projection",
    "semantic_direct",
    "semantic_projection",
    "broad_direct",
)


class FinanceDeterministicStateFixtureProvider:
    """Controlled Finance fixture for state-space and verifier tests, not model behavior."""

    fixture_provider_id = "finance_deterministic_state_fixture"
    fixture_provider_version = FINANCE_DETERMINISTIC_STATE_FIXTURE_VERSION
    variation_provider_id = "finance_fixture_variation_compiler"
    variation_provider_version = "1.5.0"

    def compile_variations(
        self,
        context: TrajectoryVerificationContext,
    ) -> tuple[AdmissibleTrajectoryVariation, ...]:
        baseline_execution_elaboration: Literal[
            "baseline_program", "program_projection"
        ] = (
            "program_projection"
            if any(
                node.operator_id == "lookup"
                for node in context.task.oracle.task_program.nodes
            )
            else "baseline_program"
        )
        return tuple(
            self.variation_for(
                strategy,
                baseline_execution_elaboration=baseline_execution_elaboration,
            )
            for strategy in _STRATEGIES
        )

    def variation_for(
        self,
        strategy: LineageStrategy,
        *,
        baseline_execution_elaboration: Literal[
            "baseline_program", "program_projection"
        ] = "baseline_program",
    ) -> AdmissibleTrajectoryVariation:
        variation_values: dict[
            LineageStrategy,
            tuple[
                AcquisitionRequirement,
                EvidenceSupportRequirement,
                VerificationRequirement,
                LineageRequirement,
            ],
        ] = {
            "compact_direct": (
                "bounded",
                "required_roles",
                "full",
                "direct",
            ),
            "compact_projection": (
                "bounded",
                "required_roles",
                "full",
                "direct",
            ),
            "semantic_direct": (
                "bounded",
                "expanded_context",
                "full",
                "direct",
            ),
            "semantic_projection": (
                "bounded",
                "expanded_context",
                "full",
                "direct",
            ),
            "broad_direct": (
                "expanded",
                "expanded_context",
                "full",
                "direct",
            ),
            "compact_verify_frontier": (
                "bounded",
                "required_roles",
                "output",
                "output_upstream",
            ),
            "broad_full_lineage": (
                "expanded",
                "expanded_context",
                "full",
                "full",
            ),
            "compact_output_lineage": (
                "bounded",
                "required_roles",
                "full",
                "output_upstream",
            ),
        }
        acquisition, support, verification, lineage = variation_values[strategy]
        retrieval_elaboration: RetrievalElaboration = (
            "full_corpus"
            if strategy.startswith("broad_")
            else "semantic_context"
            if strategy in {"semantic_direct", "semantic_projection"}
            else "required_only"
        )
        execution_elaboration: ExecutionElaboration = (
            "transparent_projection"
            if strategy in {"compact_projection", "semantic_projection"}
            else baseline_execution_elaboration
        )
        return make_admissible_trajectory_variation(
            acquisition_requirement=acquisition,
            evidence_support_requirement=support,
            verification_requirement=verification,
            lineage_requirement=lineage,
            retrieval_elaboration=retrieval_elaboration,
            execution_elaboration=execution_elaboration,
            required_capabilities=(
                "citation",
                "evidence_selection",
                "multi_step_reasoning",
                "retrieval",
                "verification",
            ),
            minimum_tool_calls=1,
            minimum_evidence_count=1,
            minimum_reasoning_depth=1,
            minimum_verification_degree=1.0,
        )

    def generate_fixture(
        self,
        context: TrajectoryVerificationContext,
        registry,
        strategy: LineageStrategy,
    ) -> Trajectory:
        return _compile_fixture_trajectory(context, registry, strategy)


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
    joint_compilation: JointCompilationArtifact
    state_space_compilation: TrajectoryStateSpaceCompilation
    state_fixture_provider_id: str = Field(min_length=1)
    state_fixture_provider_version: str = Field(min_length=1)
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

    @property
    def omega(self) -> TrajectoryVerificationContext:
        return self.joint_compilation.omega

    @model_validator(mode="after")
    def validate_artifact(self) -> FinanceTaskStateArtifact:
        task_id = self.omega.task.task_id
        if (
            self.state_fixture_provider_id
            != FinanceDeterministicStateFixtureProvider.fixture_provider_id
            or self.state_fixture_provider_version
            != FinanceDeterministicStateFixtureProvider.fixture_provider_version
        ):
            raise ValueError("Finance state artifact has another fixture provider")
        if (
            self.state_space_compilation.joint_compilation_artifact_id
            != self.joint_compilation.artifact_id
            or self.state_space_compilation.omega_context_id != self.omega.context_id
            or self.state_space_compilation.omega_component_manifest
            != self.joint_compilation.component_manifest
            or self.state_space_compilation.variation_provider_id
            != FinanceDeterministicStateFixtureProvider.variation_provider_id
            or self.state_space_compilation.variation_provider_version
            != FinanceDeterministicStateFixtureProvider.variation_provider_version
        ):
            raise ValueError("Finance state-space compilation is detached from Joint Compilation")
        states = tuple(item.assignment.state for item in self.accepted_states)
        if any(item.trajectory.task_id != task_id for item in self.accepted_states):
            raise ValueError("multi-state artifact crosses task conditions")
        if len({state.state_id for state in states}) != len(states):
            raise ValueError("multi-state artifact contains duplicate quotient states")
        if set(self.state_catalog.states) != {state.state_id for state in states}:
            raise ValueError("state catalog does not exactly cover accepted states")
        witness_assignment_ids = {
            witness.assignment_id
            for witnesses in self.state_catalog.discovery_witnesses.values()
            for witness in witnesses
        }
        if witness_assignment_ids != {
            item.assignment.assignment_id for item in self.accepted_states
        }:
            raise ValueError("state catalog witnesses do not exactly cover accepted assignments")
        witness_report_ids = {
            witness.validity_report_id
            for witnesses in self.state_catalog.discovery_witnesses.values()
            for witness in witnesses
        }
        if witness_report_ids != {item.validity_report.report_id for item in self.accepted_states}:
            raise ValueError("state catalog witnesses do not exactly cover validity reports")
        if self.state_catalog.omega_context_id != self.omega.context_id:
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
    state_fixture_provider_id: str = Field(min_length=1)
    state_fixture_provider_version: str = Field(min_length=1)
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
    surface_probe_count: int = Field(ge=0)
    surface_invariance_rate: float = Field(ge=0, le=1)
    independent_order_probe_count: int = Field(ge=0)
    independent_order_invariance_rate: float | None = Field(default=None, ge=0, le=1)
    semantic_mutation_probe_count: int = Field(ge=0)
    semantic_separation_rate: float | None = Field(default=None, ge=0, le=1)
    quotient_false_merge_count: int = Field(ge=0)
    quotient_state_validity_variance: float | None = Field(default=None, ge=0)
    failure_counts: dict[str, int]
    status: Literal["passed", "partial", "blocked"]
    limitations: tuple[str, ...]
    schema_version: str = FINANCE_MULTI_STATE_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceMultiStateReport:
        if (
            self.state_fixture_provider_id
            != FinanceDeterministicStateFixtureProvider.fixture_provider_id
            or self.state_fixture_provider_version
            != FinanceDeterministicStateFixtureProvider.fixture_provider_version
        ):
            raise ValueError("Finance report has another deterministic fixture provider")
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
    quotient = _quotient_probe(artifacts)
    raw_sequence_count = quotient["raw_sequence_count"]
    state_count = quotient["state_count"]
    quotient_raw = int(raw_sequence_count) if raw_sequence_count is not None else 0
    quotient_states = int(state_count) if state_count is not None else 0
    quotient_variance = quotient["state_validity_variance"]
    report_values = {
        "config_hash": canonical_hash(config, prefix="finance_multi_state_config:"),
        "kg_build_id": provider.kg_build_id,
        "state_fixture_provider_id": (FinanceDeterministicStateFixtureProvider.fixture_provider_id),
        "state_fixture_provider_version": (
            FinanceDeterministicStateFixtureProvider.fixture_provider_version
        ),
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
        "surface_probe_count": quotient["surface_probe_count"],
        "surface_invariance_rate": quotient["surface_invariance_rate"],
        "independent_order_probe_count": quotient["independent_order_probe_count"],
        "independent_order_invariance_rate": quotient["independent_order_invariance_rate"],
        "semantic_mutation_probe_count": quotient["semantic_mutation_probe_count"],
        "semantic_separation_rate": quotient["semantic_separation_rate"],
        "quotient_false_merge_count": quotient["false_merge_count"],
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


def build_finance_task_state_artifact(
    case,
    config: FinanceMultiStateConfig,
    *,
    strategies: tuple[LineageStrategy, ...] = DEFAULT_FINANCE_DISCOVERY_STRATEGIES,
    discovery_method: str = "verified_finance_deterministic_fixture",
    revision_reason: str = "verified_finance_fixture_state_space_initialization",
) -> FinanceTaskStateArtifact:
    """Compile one Finance task into a verified quotient-state catalog.

    The deterministic trajectories are discovery witnesses only. Production gradient
    realizations must be regenerated independently by an Explorer/Materializer pair.
    """

    if not 3 <= len(strategies) <= 5 or len(set(strategies)) != len(strategies):
        raise ValueError("Finance state discovery requires 3-5 unique strategies")
    if any(strategy not in _STRATEGIES for strategy in strategies):
        raise ValueError("Finance state discovery contains an unknown strategy")
    if not discovery_method.strip() or not revision_reason.strip():
        raise ValueError("Finance state discovery identity cannot be empty")
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
    joint_compilation = compiled.joint_compilation
    omega = joint_compilation.omega
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
    fixture_provider = FinanceDeterministicStateFixtureProvider()
    state_space_compilation = compile_trajectory_state_space(
        joint_compilation,
        fixture_provider,
    )
    variations = dict(zip(_STRATEGIES, state_space_compilation.variations, strict=True))
    public_conditions_by_assignment_id = {}
    accepted: list[AcceptedFinanceState] = []
    seen_states: set[str] = set()
    strategy_attempt_count = 0
    strategy_verifier_pass_count = 0
    duplicate_state_count = 0
    for strategy in strategies:
        strategy_attempt_count += 1
        trajectory = fixture_provider.generate_fixture(omega, case.registry, strategy)
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
        public_conditions_by_assignment_id[assignment.assignment_id] = (
            state_space_compilation.public_conditions_by_variation_id[
                variations[strategy].variation_id
            ]
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
        ((item.assignment, item.validity_report, item.trajectory) for item in accepted),
        state_space_compilation=state_space_compilation,
        discovery_method=discovery_method,
        revision_reason=revision_reason,
        public_conditions_by_assignment_id=public_conditions_by_assignment_id,
    )
    pattern = case.task.public.metadata.get("task_pattern")
    binding = case.task.oracle.selection_contract.get("pattern_binding")
    pattern_id = (
        str(pattern.get("pattern_id")) if isinstance(pattern, dict) else case.task.public.task_type
    )
    binding_id = str(binding.get("binding_id")) if isinstance(binding, dict) else case.task.task_id
    values = {
        "joint_compilation": joint_compilation,
        "state_space_compilation": state_space_compilation,
        "state_fixture_provider_id": fixture_provider.fixture_provider_id,
        "state_fixture_provider_version": fixture_provider.fixture_provider_version,
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


def _build_task_artifact(case, config: FinanceMultiStateConfig) -> FinanceTaskStateArtifact:
    return build_finance_task_state_artifact(case, config)


def _compile_fixture_trajectory(
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
    if strategy in {"semantic_direct", "semantic_projection"}:
        retrieved_ids = _semantic_context_retrieval_ids(omega)
    else:
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

    projection_specs = []
    projection_ref_by_input: dict[tuple[str, int], str] = {}
    if strategy in {"compact_projection", "semantic_projection"}:
        for node in program.nodes:
            definition = registry.require(node.operator_id)
            if definition.program_role == "transparent_projection":
                continue
            for input_index, ref in enumerate(node.input_refs):
                if ref.kind != InputRefKind.EVIDENCE:
                    continue
                projection_id = f"projection:{node.node_id}:{input_index}"
                projection_specs.append((projection_id, node, input_index, ref))
                if ref.selector:
                    projected_selector = "payload"
                elif "numeric" in definition.input_schema:
                    projected_selector = "payload.value"
                else:
                    projected_selector = "payload"
                projection_ref_by_input[(node.node_id, input_index)] = (
                    f"operation:{projection_id}#{projected_selector}"
                )

    lookup_definition = registry.require("lookup")
    for projection_id, _, _, ref in projection_specs:
        evidence = evidence_by_id[ref.ref_id]
        value = _select_program_input_value(evidence.payload, ref.selector)
        inputs = (OperationInput(ref_id=evidence.evidence_id, value=value),)
        output = lookup_definition.executor.execute(inputs, {})
        registry.validate_inputs(lookup_definition, inputs)
        registry.validate_compatibility(lookup_definition, (evidence,), {})
        registry.validate_output(lookup_definition, output)
        steps.append(
            TrajectoryStep(
                step_index=len(steps) + 1,
                action=ActionType(lookup_definition.action_type),
                tool_name=lookup_definition.tool_capability,
                tool_input={"parameters": {}},
                observation={"result": output},
                evidence_ids=(evidence.evidence_id,),
                program_node_id=projection_id,
                operator_id=lookup_definition.operator_id,
                input_refs=(_program_ref(ref),),
                output_ref=f"operation:{projection_id}",
                rationale_summary="Project one selected Evidence payload.",
                status=StepStatus.SUCCEEDED,
            )
        )

    for node in program.nodes:
        definition = registry.require(node.operator_id)
        input_refs = tuple(
            projection_ref_by_input.get(
                (node.node_id, input_index),
                _fixture_program_ref(ref, definition),
            )
            for input_index, ref in enumerate(node.input_refs)
        )
        direct = tuple(
            ref.ref_id
            for input_index, ref in enumerate(node.input_refs)
            if ref.kind == InputRefKind.EVIDENCE
            and (node.node_id, input_index) not in projection_ref_by_input
        )
        evidence_ids = direct
        if not direct and (
            full_lineage or (output_lineage and node.node_id == program.output_node_id)
        ):
            evidence_ids = tuple(sorted(lineage_by_node[node.node_id] & gold_set))
        steps.append(
            TrajectoryStep(
                step_index=len(steps) + 1,
                action=ActionType(definition.action_type),
                tool_name=definition.tool_capability,
                tool_input={"parameters": node.parameters},
                observation={"result": execution.node_outputs[node.node_id]},
                evidence_ids=evidence_ids,
                program_node_id=node.node_id,
                operator_id=node.operator_id,
                input_refs=input_refs,
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
        "version": FINANCE_DETERMINISTIC_STATE_FIXTURE_VERSION,
    }
    return Trajectory(
        trajectory_id=canonical_hash(identity, prefix="finance_multi_state_trajectory:"),
        task_id=task.task_id,
        workflow_kind=WorkflowKind.CANDIDATE,
        steps=tuple(steps),
        program_execution=execution.model_dump(mode="json"),
        final_answer=final_answer,
        generator_version=FINANCE_DETERMINISTIC_STATE_FIXTURE_VERSION,
    )


def _select_program_input_value(value, selector: str | None):
    if selector is None:
        return value
    current = value
    for segment in selector.split("."):
        if isinstance(current, BaseModel):
            current = current.model_dump(mode="python")
        if not isinstance(current, dict) or segment not in current:
            raise ValueError(f"invalid fixture input selector: {selector}")
        current = current[segment]
    return current


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
            "generator_version": f"{FINANCE_DETERMINISTIC_STATE_FIXTURE_VERSION}.mutation",
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


def _fixture_program_ref(ref, definition) -> str:
    value = _program_ref(ref)
    if (
        ref.kind == InputRefKind.EVIDENCE
        and ref.selector is None
        and definition.program_role != "transparent_projection"
        and "numeric" in definition.input_schema
    ):
        return f"{value}#value"
    return value


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


def _semantic_context_retrieval_ids(
    context: TrajectoryVerificationContext,
) -> tuple[str, ...]:
    evidence_by_id = context.public_corpus.by_id()
    gold = tuple(
        evidence_by_id[evidence_id] for evidence_id in context.task.oracle.gold_evidence_ids
    )
    semantic_keys = {_semantic_context_key(item) for item in gold}
    return tuple(
        item.evidence_id
        for item in context.public_corpus.evidence
        if _semantic_context_key(item) in semantic_keys
    )


def _semantic_context_key(
    item: EvidenceItem,
) -> tuple[str, str, str, str | None, str | None, str, str]:
    temporal = item.temporal_context
    return (
        item.domain,
        item.subject.subject_id,
        item.subject.subject_type,
        temporal.basis,
        temporal.frequency,
        item.source.authority.value,
        item.epistemic_status.value,
    )


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
) -> dict[str, int | float | None]:
    raw_hashes: set[str] = set()
    state_ids: set[str] = set()
    validity_by_state: dict[str, list[float]] = {}
    surface_count = 0
    surface_matches = 0
    order_count = 0
    order_matches = 0
    semantic_count = 0
    semantic_separations = 0
    false_merges = 0
    for artifact in artifacts:
        for item in artifact.accepted_states:
            original = map_trajectory_to_state(
                artifact.omega,
                item.trajectory,
                program_node_aliases=item.validity_report.program_node_mapping,
            )
            surface = _surface_probe(item.trajectory)
            surface_assignment = map_trajectory_to_state(
                artifact.omega,
                surface,
                program_node_aliases=item.validity_report.program_node_mapping,
            )
            surface_count += 1
            surface_matches += int(original.state.state_id == surface_assignment.state.state_id)
            trajectories = [item.trajectory, surface]
            order_probe = _independent_order_probe(artifact, item.trajectory)
            if order_probe is not None:
                order_assignment = map_trajectory_to_state(
                    artifact.omega,
                    order_probe,
                    program_node_aliases=item.validity_report.program_node_mapping,
                )
                order_count += 1
                order_matches += int(original.state.state_id == order_assignment.state.state_id)
                trajectories.append(order_probe)
            for trajectory in trajectories:
                assignment = map_trajectory_to_state(
                    artifact.omega,
                    trajectory,
                    program_node_aliases=item.validity_report.program_node_mapping,
                )
                raw_hashes.add(trajectory.trajectory_hash)
                state_ids.add(assignment.state.state_id)
                validity_by_state.setdefault(assignment.state.state_id, []).append(1.0)
        accepted_state_ids = {item.assignment.state.state_id for item in artifact.accepted_states}
        for rejected in artifact.rejected_attempts:
            assignment = map_trajectory_to_state(
                artifact.omega,
                rejected.trajectory,
                program_node_aliases=rejected.validity_report.program_node_mapping,
            )
            semantic_count += 1
            separated = assignment.state.state_id not in accepted_state_ids
            semantic_separations += int(separated)
            false_merges += int(not separated)
    variances = [
        statistics.pvariance(values) if len(values) > 1 else 0.0
        for values in validity_by_state.values()
    ]
    return {
        "raw_sequence_count": len(raw_hashes),
        "state_count": len(state_ids),
        "state_validity_variance": statistics.fmean(variances) if variances else None,
        "surface_probe_count": surface_count,
        "surface_invariance_rate": surface_matches / surface_count if surface_count else 0.0,
        "independent_order_probe_count": order_count,
        "independent_order_invariance_rate": (order_matches / order_count if order_count else None),
        "semantic_mutation_probe_count": semantic_count,
        "semantic_separation_rate": (
            semantic_separations / semantic_count if semantic_count else None
        ),
        "false_merge_count": false_merges,
    }


def _independent_order_probe(
    artifact: FinanceTaskStateArtifact,
    source: Trajectory,
) -> Trajectory | None:
    nodes = {item.node_id: item for item in artifact.omega.task.oracle.task_program.nodes}
    step_positions = {
        step.program_node_id: index
        for index, step in enumerate(source.steps)
        if step.program_node_id in nodes
    }
    for left_id in sorted(step_positions):
        for right_id in sorted(step_positions):
            if left_id >= right_id:
                continue
            if _depends_on(nodes, left_id, right_id) or _depends_on(nodes, right_id, left_id):
                continue
            steps = list(source.steps)
            left = step_positions[left_id]
            right = step_positions[right_id]
            steps[left], steps[right] = steps[right], steps[left]
            reindexed = tuple(
                step.model_copy(update={"step_index": index})
                for index, step in enumerate(steps, start=1)
            )
            return source.model_copy(
                update={
                    "trajectory_id": canonical_hash(
                        {
                            "source": source.trajectory_id,
                            "probe": "independent_operation_order",
                            "left": left_id,
                            "right": right_id,
                        },
                        prefix="trajectory_quotient_probe:",
                    ),
                    "steps": reindexed,
                    "generator_version": "quotient_order_probe.v1",
                }
            )
    return None


def _depends_on(
    nodes: dict[str, OperationNode],
    node_id: str,
    candidate_ancestor: str,
) -> bool:
    pending = list(nodes[node_id].dependencies)
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current == candidate_ancestor:
            return True
        if current not in visited:
            visited.add(current)
            pending.extend(nodes[current].dependencies)
    return False


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
