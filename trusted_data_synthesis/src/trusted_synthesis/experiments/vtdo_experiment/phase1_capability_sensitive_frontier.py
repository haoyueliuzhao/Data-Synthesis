from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.program import (
    ProgramExecution,
    ProgramVerification,
    TaskProgramExecutor,
    TaskProgramOracleVerifier,
)
from trusted_synthesis.core.operations.registry import OperationRegistry, default_registry
from trusted_synthesis.core.task.builder import TaskPackageBuilder
from trusted_synthesis.core.task.materialization import temporal_sort_key, time_label
from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    TaskProgram,
    make_program,
)
from trusted_synthesis.core.task.schema import (
    PlanningTrack,
    RetrievalTrack,
    TaskLevel,
    TaskPackage,
    VerifierRequirement,
)
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.hashing import canonical_hash

CAPABILITY_SENSITIVE_FRONTIER_VERSION = "finance_capability_sensitive_frontier.v4"
CAPABILITY_STRUCTURE_VECTOR_VERSION = "finance_capability_structure_vector.v1"
CAPABILITY_INFORMATION_AUDIT_VERSION = "capability_information_audit.v4"
CAPABILITY_FRONTIER_AUDIT_VERSION = "finance_capability_frontier_audit.v4"

CAPABILITY_AXES: tuple[str, ...] = (
    "retrieval",
    "planning",
    "calculation",
    "reconciliation",
    "verification",
    "recovery",
    "stopping",
)

CAPABILITY_SENSITIVE_FAMILIES: tuple[str, ...] = (
    "finance.multi_hop_retrieval_join",
    "finance.branching_operation_plan",
    "finance.calculation_chain",
    "finance.definition_reconciliation",
    "finance.verification_sensitive_selection",
    "finance.recovery_guided_search",
    "finance.stopping_decision_control",
)

# Cross-entity and recovery bindings are materially scarcer than temporal bindings.
# Build order is a frozen capacity policy; task identity remains sorted by family/tier.
CAPABILITY_FAMILY_BUILD_ORDER: tuple[str, ...] = (
    "finance.branching_operation_plan",
    "finance.recovery_guided_search",
    "finance.stopping_decision_control",
    "finance.verification_sensitive_selection",
    "finance.definition_reconciliation",
    "finance.multi_hop_retrieval_join",
    "finance.calculation_chain",
)

# This mapping is used only to audit whether executable structural requirements align
# with the registered family semantics. It never contributes weight to a demand vector.
FAMILY_PRIMARY_CAPABILITY: dict[str, str] = {
    "finance.multi_hop_retrieval_join": "retrieval",
    "finance.branching_operation_plan": "planning",
    "finance.calculation_chain": "calculation",
    "finance.definition_reconciliation": "reconciliation",
    "finance.verification_sensitive_selection": "verification",
    "finance.recovery_guided_search": "recovery",
    "finance.stopping_decision_control": "stopping",
}

TIER_TASKS_PER_FAMILY: dict[DifficultyTier, int] = {
    DifficultyTier.EASY_CONTROL: 3,
    DifficultyTier.FRONTIER: 5,
    DifficultyTier.HARD_CONTROL: 2,
}

STRICT_MONOTONIC_DIMENSIONS: tuple[str, ...] = (
    "evidence_hop_count",
    "public_source_count",
    "operation_dag_depth",
    "query_decomposition_rounds",
    "reconciliation_count",
    "required_verification_count",
    "required_recovery_count",
    "distractor_branch_count",
    "tool_type_count",
    "minimal_tool_calls",
    "stopping_condition_count",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RecoveryBranch(FrozenModel):
    distractor_evidence_id: str = Field(min_length=1)
    mismatch_fields: tuple[str, ...] = Field(min_length=1, max_length=1)
    required_action: Literal["refine_query_after_ambiguous_observation"] = (
        "refine_query_after_ambiguous_observation"
    )


class QueryStage(FrozenModel):
    stage_index: int = Field(ge=1)
    action: Literal[
        "broad_search",
        "typed_refinement",
        "document_inspection",
        "cross_source_join",
    ]
    observation_dependency: str = Field(min_length=1)


class CapabilityStructureVector(FrozenModel):
    evidence_hop_count: int = Field(ge=1)
    gold_evidence_count: int = Field(ge=1)
    gold_subject_count: int = Field(ge=1)
    public_source_count: int = Field(ge=1)
    source_heterogeneity_count: int = Field(ge=1)
    operation_count: int = Field(ge=1)
    operation_dag_depth: int = Field(ge=1)
    operation_branch_count: int = Field(ge=1)
    query_decomposition_rounds: int = Field(ge=1)
    reconciliation_count: int = Field(ge=0)
    required_verification_count: int = Field(ge=0)
    required_recovery_count: int = Field(ge=0)
    distractor_branch_count: int = Field(ge=0)
    tool_type_count: int = Field(ge=1)
    minimal_tool_calls: int = Field(ge=1)
    stopping_condition_count: int = Field(ge=1)
    single_retrieval_solvable: bool
    semantic_score: float = Field(ge=0)
    vector_hash: str = Field(min_length=1)
    schema_version: str = CAPABILITY_STRUCTURE_VECTOR_VERSION

    @model_validator(mode="after")
    def validate_vector(self) -> CapabilityStructureVector:
        if self.evidence_hop_count != self.operation_dag_depth + 1:
            raise ValueError("evidence hop count must include the input Evidence hop")
        if self.vector_hash != capability_structure_vector_hash(self):
            raise ValueError("capability structure vector identity is invalid")
        expected_score = _semantic_score(self)
        if not math.isclose(self.semantic_score, expected_score, abs_tol=1e-9):
            raise ValueError("capability structure semantic score is inconsistent")
        return self


class CapabilityDemandVector(FrozenModel):
    values: dict[str, float]
    vector_hash: str = Field(min_length=1)
    schema_version: str = "capability_demand_vector.v1"

    @model_validator(mode="after")
    def validate_demand(self) -> CapabilityDemandVector:
        if set(self.values) != set(CAPABILITY_AXES):
            raise ValueError("capability demand vector does not cover the frozen axes")
        if any(value <= 0 or not math.isfinite(value) for value in self.values.values()):
            raise ValueError("capability demand values must be finite and positive")
        if self.vector_hash != capability_demand_vector_hash(self):
            raise ValueError("capability demand vector identity is invalid")
        return self


class CapabilitySensitiveTaskArtifact(FrozenModel):
    artifact_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    tier: DifficultyTier
    source_artifact_ids: tuple[str, ...] = Field(min_length=1)
    evidence_bundle: EvidenceBundle
    public_corpus: EvidenceCorpus
    proof_graph: ProofGraph
    task: TaskPackage
    execution: ProgramExecution
    verification: ProgramVerification
    projected_expected_output: dict[str, Any]
    answer_projection: dict[str, str] = Field(default_factory=dict)
    reconciliation_axes: tuple[str, ...]
    verification_checkpoints: tuple[str, ...] = Field(min_length=1)
    recovery_branches: tuple[RecoveryBranch, ...]
    query_stages: tuple[QueryStage, ...] = Field(min_length=1)
    required_tool_ids: tuple[str, ...] = Field(min_length=1)
    stopping_conditions: tuple[str, ...] = Field(min_length=1)
    structure: CapabilityStructureVector
    capability_demand: CapabilityDemandVector
    schema_version: str = CAPABILITY_SENSITIVE_FRONTIER_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> CapabilitySensitiveTaskArtifact:
        if self.family not in CAPABILITY_SENSITIVE_FAMILIES:
            raise ValueError("capability-sensitive task uses an unknown family")
        if self.task.oracle.task_program != self.execution_program:
            raise ValueError("capability task execution is detached from its Oracle Program")
        if self.execution.program_id != self.task.oracle.task_program.program_id:
            raise ValueError("capability task execution belongs to another Program")
        if (
            self.verification.program_id != self.execution.program_id
            or not self.verification.passed
        ):
            raise ValueError("capability task lacks independent Program verification")
        if self.execution.final_output != self.verification.independently_computed_output:
            raise ValueError("executor and independent Oracle outputs differ")
        gold_ids = tuple(item.evidence_id for item in self.evidence_bundle.evidence)
        if gold_ids != self.task.oracle.gold_evidence_ids:
            raise ValueError("capability task Gold Evidence order is inconsistent")
        corpus_ids = {item.evidence_id for item in self.public_corpus.evidence}
        if not set(gold_ids) <= corpus_ids:
            raise ValueError("capability task Corpus omits Gold Evidence")
        distractor_ids = corpus_ids - set(gold_ids)
        if self.structure.distractor_branch_count != len(distractor_ids):
            raise ValueError("distractor branch count is inconsistent")
        if self.structure.gold_subject_count != len(
            {item.subject.subject_id for item in self.evidence_bundle.evidence}
        ):
            raise ValueError("Gold subject count is inconsistent")
        if self.structure.required_recovery_count != len(self.recovery_branches):
            raise ValueError("required recovery count is inconsistent")
        if not {item.distractor_evidence_id for item in self.recovery_branches} <= distractor_ids:
            raise ValueError("a recovery branch does not refer to a Corpus distractor")
        if self.structure.reconciliation_count != len(self.reconciliation_axes):
            raise ValueError("reconciliation count is inconsistent")
        if self.structure.required_verification_count != len(self.verification_checkpoints):
            raise ValueError("verification checkpoint count is inconsistent")
        if self.structure.query_decomposition_rounds != len(self.query_stages):
            raise ValueError("query decomposition count is inconsistent")
        if self.structure.tool_type_count != len(set(self.required_tool_ids)):
            raise ValueError("tool type count is inconsistent")
        if self.structure.stopping_condition_count != len(self.stopping_conditions):
            raise ValueError("stopping condition count is inconsistent")
        if self.structure.operation_count != len(self.task.oracle.task_program.nodes):
            raise ValueError("operation count is inconsistent")
        if self.structure.operation_dag_depth != _program_depth(self.task.oracle.task_program):
            raise ValueError("operation DAG depth is inconsistent")
        if self.structure.operation_branch_count != _program_branch_count(
            self.task.oracle.task_program
        ):
            raise ValueError("operation branch count is inconsistent")
        sources = {item.source.source_id for item in self.public_corpus.evidence}
        authorities = {item.source.authority.value for item in self.public_corpus.evidence}
        if self.structure.public_source_count != len(sources):
            raise ValueError("public source count is inconsistent")
        if self.structure.source_heterogeneity_count != len(authorities):
            raise ValueError("source heterogeneity count is inconsistent")
        if self.artifact_id != capability_sensitive_task_artifact_id(self):
            raise ValueError("capability-sensitive task artifact identity is invalid")
        return self

    @property
    def execution_program(self) -> TaskProgram:
        return self.task.oracle.task_program


class CapabilityInformationAudit(FrozenModel):
    axis_order: tuple[str, ...]
    axis_mean_demand: dict[str, float]
    information_eigenvalues: tuple[float, ...]
    numerical_rank: int = Field(ge=0)
    full_effective_rank: float = Field(ge=0)
    identifiable_subspace_effective_rank: float = Field(ge=0)
    full_condition_number: float = Field(ge=1)
    identifiable_subspace_condition_number: float = Field(ge=1)
    family_axis_contrasts: dict[str, dict[str, float]]
    family_primary_axis_passes: dict[str, bool]
    primary_axis_alignment_ready: bool
    minimum_required_rank: int = Field(default=len(CAPABILITY_AXES) - 1, ge=1)
    minimum_identifiable_subspace_effective_rank: float = Field(default=4.0, ge=1)
    maximum_identifiable_subspace_condition_number: float = Field(default=100.0, ge=1)
    minimum_axis_mean: float = Field(default=0.05, gt=0)
    capability_direction_ready: bool
    audit_hash: str = Field(min_length=1)
    schema_version: str = CAPABILITY_INFORMATION_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_information_audit(self) -> CapabilityInformationAudit:
        if self.axis_order != CAPABILITY_AXES or set(self.axis_mean_demand) != set(CAPABILITY_AXES):
            raise ValueError("capability information audit uses another axis contract")
        if len(self.information_eigenvalues) != len(CAPABILITY_AXES):
            raise ValueError("capability information audit has an invalid spectrum")
        if self.minimum_required_rank > len(CAPABILITY_AXES):
            raise ValueError("required capability rank exceeds the frozen axis count")
        if any(not math.isfinite(value) or value < 0 for value in self.information_eigenvalues):
            raise ValueError("capability information spectrum must be finite and non-negative")
        if set(self.family_axis_contrasts) != set(CAPABILITY_SENSITIVE_FAMILIES) or any(
            set(values) != set(CAPABILITY_AXES) for values in self.family_axis_contrasts.values()
        ):
            raise ValueError("capability family contrasts are incomplete")
        if set(self.family_primary_axis_passes) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("capability family alignment decisions are incomplete")
        if self.primary_axis_alignment_ready != all(self.family_primary_axis_passes.values()):
            raise ValueError("capability family alignment decision is inconsistent")
        ready = (
            self.numerical_rank >= self.minimum_required_rank
            and self.identifiable_subspace_effective_rank
            >= self.minimum_identifiable_subspace_effective_rank
            and self.identifiable_subspace_condition_number
            <= self.maximum_identifiable_subspace_condition_number
            and min(self.axis_mean_demand.values()) >= self.minimum_axis_mean
            and self.primary_axis_alignment_ready
        )
        if self.capability_direction_ready != ready:
            raise ValueError("capability direction authorization is inconsistent")
        if self.audit_hash != capability_information_audit_hash(self):
            raise ValueError("capability information audit identity is invalid")
        return self


class CapabilitySensitiveFrontierAudit(FrozenModel):
    task_count: int = Field(ge=1)
    tier_counts: dict[DifficultyTier, int]
    family_tier_counts: dict[str, dict[DifficultyTier, int]]
    dimension_tier_means: dict[str, dict[DifficultyTier, float]]
    strict_dimension_passes: dict[str, bool]
    family_dimension_tier_means: dict[str, dict[str, dict[DifficultyTier, float]]]
    family_strict_dimension_passes: dict[str, dict[str, bool]]
    single_retrieval_rates: dict[DifficultyTier, float]
    single_retrieval_transition_passed: bool
    family_single_retrieval_rates: dict[str, dict[DifficultyTier, float]]
    family_single_retrieval_transition_passes: dict[str, bool]
    tier_semantic_means: dict[DifficultyTier, float]
    family_semantic_means: dict[str, dict[DifficultyTier, float]]
    frontier_mean_gain: float
    hard_control_mean_gain: float
    minimum_frontier_mean_gain: float = Field(default=1.0, gt=0)
    minimum_family_frontier_gain: float = Field(default=0.5, gt=0)
    minimum_passing_family_count: int = Field(default=len(CAPABILITY_SENSITIVE_FAMILIES), ge=1)
    passing_family_count: int = Field(ge=0)
    execution_pass_rate: float = Field(ge=0, le=1)
    public_evidence_disjoint: bool
    capability_information: CapabilityInformationAudit
    capability_boundary_status: Literal["not_evaluated_requires_model_calibration"] = (
        "not_evaluated_requires_model_calibration"
    )
    structural_frontier_ready: bool
    next_permitted_stage: Literal[
        "paired_model_capability_boundary_calibration",
        "frontier_task_construction_only",
    ]
    audit_hash: str = Field(min_length=1)
    schema_version: str = CAPABILITY_FRONTIER_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CapabilitySensitiveFrontierAudit:
        if set(self.tier_counts) != set(DifficultyTier):
            raise ValueError("Frontier audit lacks a tier")
        if set(self.family_tier_counts) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("Frontier audit lacks a capability family")
        if set(self.dimension_tier_means) != set(STRICT_MONOTONIC_DIMENSIONS):
            raise ValueError("Frontier audit lacks a registered structural dimension")
        if set(self.strict_dimension_passes) != set(STRICT_MONOTONIC_DIMENSIONS):
            raise ValueError("Frontier audit dimension decisions are incomplete")
        if set(self.family_dimension_tier_means) != set(CAPABILITY_SENSITIVE_FAMILIES) or any(
            set(values) != set(STRICT_MONOTONIC_DIMENSIONS)
            for values in self.family_dimension_tier_means.values()
        ):
            raise ValueError("Frontier family dimension means are incomplete")
        if set(self.family_strict_dimension_passes) != set(CAPABILITY_SENSITIVE_FAMILIES) or any(
            set(values) != set(STRICT_MONOTONIC_DIMENSIONS)
            for values in self.family_strict_dimension_passes.values()
        ):
            raise ValueError("Frontier family dimension decisions are incomplete")
        if set(self.family_single_retrieval_rates) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("Frontier family retrieval rates are incomplete")
        if set(self.family_single_retrieval_transition_passes) != set(
            CAPABILITY_SENSITIVE_FAMILIES
        ):
            raise ValueError("Frontier family retrieval decisions are incomplete")
        if any(set(values) != set(DifficultyTier) for values in self.dimension_tier_means.values()):
            raise ValueError("Frontier audit dimension means lack a tier")
        if any(
            set(tiers) != set(DifficultyTier)
            for dimensions in self.family_dimension_tier_means.values()
            for tiers in dimensions.values()
        ) or any(
            set(tiers) != set(DifficultyTier)
            for tiers in self.family_single_retrieval_rates.values()
        ):
            raise ValueError("Frontier family structural means lack a tier")
        if set(self.tier_semantic_means) != set(DifficultyTier):
            raise ValueError("Frontier semantic means lack a tier")
        if set(self.family_semantic_means) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("Frontier family means are incomplete")
        if not math.isclose(
            self.frontier_mean_gain,
            self.tier_semantic_means[DifficultyTier.FRONTIER]
            - self.tier_semantic_means[DifficultyTier.EASY_CONTROL],
            abs_tol=1e-9,
        ):
            raise ValueError("Frontier semantic gain is inconsistent")
        if not math.isclose(
            self.hard_control_mean_gain,
            self.tier_semantic_means[DifficultyTier.HARD_CONTROL]
            - self.tier_semantic_means[DifficultyTier.EASY_CONTROL],
            abs_tol=1e-9,
        ):
            raise ValueError("Hard-Control semantic gain is inconsistent")
        expected_passing = sum(
            values[DifficultyTier.FRONTIER] - values[DifficultyTier.EASY_CONTROL]
            >= self.minimum_family_frontier_gain
            for values in self.family_semantic_means.values()
        )
        if self.passing_family_count != expected_passing:
            raise ValueError("Frontier passing-family count is inconsistent")
        expected_ready = (
            all(self.strict_dimension_passes.values())
            and all(
                passed
                for dimensions in self.family_strict_dimension_passes.values()
                for passed in dimensions.values()
            )
            and self.single_retrieval_transition_passed
            and all(self.family_single_retrieval_transition_passes.values())
            and self.frontier_mean_gain >= self.minimum_frontier_mean_gain
            and self.passing_family_count >= self.minimum_passing_family_count
            and math.isclose(self.execution_pass_rate, 1.0, abs_tol=1e-12)
            and self.public_evidence_disjoint
            and self.capability_information.capability_direction_ready
        )
        if self.structural_frontier_ready != expected_ready:
            raise ValueError("structural Frontier authorization is inconsistent")
        expected_stage = (
            "paired_model_capability_boundary_calibration"
            if expected_ready
            else "frontier_task_construction_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("next experiment stage is inconsistent")
        if self.audit_hash != capability_sensitive_frontier_audit_hash(self):
            raise ValueError("capability-sensitive Frontier audit identity is invalid")
        return self


class CapabilitySensitiveFrontierPopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_artifacts_path: str = Field(min_length=1)
    source_artifacts_sha256: str = Field(min_length=64, max_length=64)
    source_artifact_count: int = Field(ge=1)
    source_artifact_ids: tuple[str, ...] = Field(min_length=1)
    sampling_salt: str = Field(min_length=1)
    tasks: tuple[CapabilitySensitiveTaskArtifact, ...] = Field(min_length=1)
    audit: CapabilitySensitiveFrontierAudit
    model_api_calls: Literal[0] = 0
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = CAPABILITY_SENSITIVE_FRONTIER_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> CapabilitySensitiveFrontierPopulation:
        if (
            len(self.source_artifact_ids) != self.source_artifact_count
            or tuple(sorted(set(self.source_artifact_ids))) != self.source_artifact_ids
        ):
            raise ValueError("Frontier source-artifact manifest is inconsistent")
        referenced = {item for task in self.tasks for item in task.source_artifact_ids}
        if not referenced <= set(self.source_artifact_ids):
            raise ValueError("Frontier tasks reference unknown source artifacts")
        if self.audit != make_capability_sensitive_frontier_audit(self.tasks):
            raise ValueError("Frontier population audit differs from frozen tasks")
        if self.population_id != capability_sensitive_frontier_population_id(self):
            raise ValueError("capability-sensitive Frontier population identity is invalid")
        return self


class _EvidencePool:
    def __init__(self) -> None:
        self.gold: dict[str, EvidenceItem] = {}
        self.public: dict[str, EvidenceItem] = {}
        self.origin_artifacts: dict[str, set[str]] = defaultdict(set)
        self.source_artifact_ids: set[str] = set()
        self.source_artifact_count = 0


def capability_structure_vector_hash(value: CapabilityStructureVector) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"vector_hash"}),
        prefix="finance_capability_structure_vector:",
    )


def capability_demand_vector_hash(value: CapabilityDemandVector) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"vector_hash"}),
        prefix="capability_demand_vector:",
    )


def capability_sensitive_task_artifact_id(value: CapabilitySensitiveTaskArtifact) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"artifact_id"}),
        prefix="finance_capability_sensitive_task:",
    )


def capability_information_audit_hash(value: CapabilityInformationAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_hash"}),
        prefix="capability_information_audit:",
    )


def capability_sensitive_frontier_audit_hash(
    value: CapabilitySensitiveFrontierAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_hash"}),
        prefix="finance_capability_sensitive_frontier_audit:",
    )


def capability_sensitive_frontier_population_id(
    value: CapabilitySensitiveFrontierPopulation,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"population_id"}),
        prefix="finance_capability_sensitive_frontier_population:",
    )


def build_capability_sensitive_frontier_population(
    *,
    source_artifacts_path: Path,
    output_path: Path,
    run_id: str,
    sampling_salt: str,
) -> CapabilitySensitiveFrontierPopulation:
    if output_path.exists():
        raise ValueError("capability-sensitive Frontier population is immutable")
    source_artifacts_path = source_artifacts_path.resolve()
    pool = _load_evidence_pool(source_artifacts_path)
    builder = _CapabilityTaskBuilder(pool, sampling_salt=sampling_salt)
    tasks = builder.build_registered_population()
    audit = make_capability_sensitive_frontier_audit(tasks)
    values = {
        "run_id": run_id,
        "source_artifacts_path": str(source_artifacts_path),
        "source_artifacts_sha256": _sha256(source_artifacts_path),
        "source_artifact_count": pool.source_artifact_count,
        "source_artifact_ids": tuple(sorted(pool.source_artifact_ids)),
        "sampling_salt": sampling_salt,
        "tasks": tasks,
        "audit": audit,
        "model_api_calls": 0,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    provisional = CapabilitySensitiveFrontierPopulation.model_construct(
        population_id="pending",
        **values,
    )
    population = CapabilitySensitiveFrontierPopulation(
        population_id=capability_sensitive_frontier_population_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, population.model_dump(mode="json"))
    return population


class _CapabilityTaskBuilder:
    def __init__(self, pool: _EvidencePool, *, sampling_salt: str) -> None:
        self._pool = pool
        self._sampling_salt = sampling_salt
        self._registry = default_registry()
        self._used_evidence_ids: set[str] = set()
        self._temporal_series = _temporal_series(pool.gold.values())
        self._cross_entity_windows = _cross_entity_windows(self._temporal_series)

    def build_registered_population(self) -> tuple[CapabilitySensitiveTaskArtifact, ...]:
        tasks: list[CapabilitySensitiveTaskArtifact] = []
        for tier in (
            DifficultyTier.HARD_CONTROL,
            DifficultyTier.FRONTIER,
            DifficultyTier.EASY_CONTROL,
        ):
            for family in CAPABILITY_FAMILY_BUILD_ORDER:
                target = TIER_TASKS_PER_FAMILY[tier]
                tasks.extend(self._build_family_tier(family, tier, target))
        return tuple(
            sorted(tasks, key=lambda item: (item.family, item.tier.value, item.artifact_id))
        )

    def _build_family_tier(
        self,
        family: str,
        tier: DifficultyTier,
        target: int,
    ) -> tuple[CapabilitySensitiveTaskArtifact, ...]:
        candidates = (
            self._cross_candidates(family, tier)
            if family == "finance.branching_operation_plan"
            else self._temporal_candidates(family, tier)
        )
        built: list[CapabilitySensitiveTaskArtifact] = []
        for gold, program, instruction, answer_projection in candidates:
            gold_ids = {item.evidence_id for item in gold}
            if gold_ids & self._used_evidence_ids:
                continue
            selected = self._select_distractors(family, gold, tier)
            if selected is None:
                continue
            distractors, recovery = selected
            all_ids = gold_ids | {item.evidence_id for item in distractors}
            if all_ids & self._used_evidence_ids:
                continue
            artifact = self._materialize(
                family=family,
                tier=tier,
                gold=gold,
                distractors=distractors,
                recovery_branches=recovery,
                program=program,
                instruction=instruction,
                answer_projection=answer_projection,
            )
            built.append(artifact)
            self._used_evidence_ids.update(all_ids)
            if len(built) == target:
                return tuple(built)
        raise ValueError(
            "real Finance Evidence cannot support "
            f"{target} disjoint tasks for {family}/{tier.value}; built={len(built)}"
        )

    def _temporal_candidates(
        self,
        family: str,
        tier: DifficultyTier,
    ) -> Iterable[tuple[tuple[EvidenceItem, ...], TaskProgram, str, dict[str, str]]]:
        required = {
            DifficultyTier.EASY_CONTROL: 2,
            DifficultyTier.FRONTIER: 3,
            DifficultyTier.HARD_CONTROL: 4,
        }[tier]
        values = []
        for series in self._temporal_series:
            if len(series) < required:
                continue
            for window in _contiguous_windows(series, required):
                key = canonical_hash(
                    {
                        "salt": self._sampling_salt,
                        "family": family,
                        "tier": tier.value,
                        "evidence": tuple(item.evidence_version_id for item in window),
                    },
                    prefix="capability_temporal_candidate:",
                )
                values.append((key, window))
        for _, window in sorted(values, key=lambda item: item[0]):
            yield _temporal_program(self._registry, family, tier, window)

    def _cross_candidates(
        self,
        family: str,
        tier: DifficultyTier,
    ) -> Iterable[tuple[tuple[EvidenceItem, ...], TaskProgram, str, dict[str, str]]]:
        subject_count = 3 if tier == DifficultyTier.HARD_CONTROL else 2
        values = []
        for window_key, by_subject in self._cross_entity_windows.items():
            if len(by_subject) < subject_count:
                continue
            for subject_ids in itertools.combinations(sorted(by_subject), subject_count):
                pairs = tuple(by_subject[item] for item in subject_ids)
                evidence = tuple(item for pair in pairs for item in pair)
                key = canonical_hash(
                    {
                        "salt": self._sampling_salt,
                        "family": family,
                        "tier": tier.value,
                        "window_key": window_key,
                        "evidence": tuple(item.evidence_version_id for item in evidence),
                    },
                    prefix="capability_cross_candidate:",
                )
                values.append((key, pairs))
        for _, pairs in sorted(values, key=lambda item: item[0]):
            yield _cross_entity_program(self._registry, family, tier, pairs)

    def _select_distractors(
        self,
        family: str,
        gold: tuple[EvidenceItem, ...],
        tier: DifficultyTier,
    ) -> tuple[tuple[EvidenceItem, ...], tuple[RecoveryBranch, ...]] | None:
        target_count = {
            DifficultyTier.EASY_CONTROL: 0,
            DifficultyTier.FRONTIER: 3,
            DifficultyTier.HARD_CONTROL: 6,
        }[tier]
        recovery_count = {
            DifficultyTier.EASY_CONTROL: 0,
            DifficultyTier.FRONTIER: 1,
            DifficultyTier.HARD_CONTROL: 2,
        }[tier]
        if family == "finance.recovery_guided_search" and tier != DifficultyTier.EASY_CONTROL:
            recovery_count += 1
        target_source_count = {
            DifficultyTier.EASY_CONTROL: 1,
            DifficultyTier.FRONTIER: 2,
            DifficultyTier.HARD_CONTROL: 3,
        }[tier]
        if target_count == 0:
            return (), ()
        gold_ids = {item.evidence_id for item in gold}
        available = [
            item
            for item in self._pool.public.values()
            if item.evidence_id not in gold_ids and item.evidence_id not in self._used_evidence_ids
        ]
        ranked = sorted(
            available,
            key=lambda item: (
                _minimum_mismatch_count(item, gold),
                canonical_hash(
                    {
                        "salt": self._sampling_salt,
                        "candidate": item.evidence_version_id,
                        "gold": tuple(value.evidence_version_id for value in gold),
                    },
                    prefix="capability_distractor_selection:",
                ),
            ),
        )
        near = [item for item in ranked if len(_minimum_mismatch_fields(item, gold)) == 1]
        if len(near) < recovery_count:
            return None
        selected = near[:recovery_count]
        selected_ids = {item.evidence_id for item in selected}
        source_ids = {item.source.source_id for item in gold} | {
            item.source.source_id for item in selected
        }
        all_sources = sorted({item.source.source_id for item in available} - source_ids)
        for source_id in all_sources:
            if len(source_ids) >= target_source_count:
                break
            candidate = next(
                (
                    item
                    for item in ranked
                    if item.source.source_id == source_id and item.evidence_id not in selected_ids
                ),
                None,
            )
            if candidate is not None:
                selected.append(candidate)
                selected_ids.add(candidate.evidence_id)
                source_ids.add(source_id)
        if len(source_ids) != target_source_count:
            return None
        allowed_sources = source_ids
        for item in ranked:
            if len(selected) >= target_count:
                break
            if item.evidence_id in selected_ids or item.source.source_id not in allowed_sources:
                continue
            selected.append(item)
            selected_ids.add(item.evidence_id)
        if len(selected) != target_count:
            return None
        recovery = tuple(
            RecoveryBranch(
                distractor_evidence_id=item.evidence_id,
                mismatch_fields=_minimum_mismatch_fields(item, gold),
            )
            for item in selected[:recovery_count]
        )
        return tuple(selected), recovery

    def _materialize(
        self,
        *,
        family: str,
        tier: DifficultyTier,
        gold: tuple[EvidenceItem, ...],
        distractors: tuple[EvidenceItem, ...],
        recovery_branches: tuple[RecoveryBranch, ...],
        program: TaskProgram,
        instruction: str,
        answer_projection: dict[str, str],
    ) -> CapabilitySensitiveTaskArtifact:
        graph_build_ids = {
            value
            for item in gold
            for key, value in item.provenance.build_ids.items()
            if key == "kg"
        }
        graph_build_id = next(iter(graph_build_ids)) if len(graph_build_ids) == 1 else None
        bundle = EvidenceBundle(
            bundle_id=canonical_hash(
                {
                    "family": family,
                    "tier": tier.value,
                    "evidence": tuple(item.evidence_version_id for item in gold),
                },
                prefix="capability_frontier_bundle:",
            ),
            evidence=gold,
            purpose="capability-sensitive Finance Frontier task",
            graph_build_id=graph_build_id,
            metadata={"construction_version": CAPABILITY_SENSITIVE_FRONTIER_VERSION},
        )
        corpus_evidence = tuple(sorted((*gold, *distractors), key=lambda item: item.evidence_id))
        corpus = EvidenceCorpus(
            corpus_id=canonical_hash(
                tuple(item.evidence_version_id for item in corpus_evidence),
                prefix="capability_frontier_corpus:",
            ),
            evidence=corpus_evidence,
            build_id=graph_build_id,
        )
        graph = ProofGraphBuilder().build(bundle)
        query_stages = _query_stages(family, tier)
        reconciliation_axes = _reconciliation_axes(family, tier)
        verification_checkpoints = _verification_checkpoints(family, tier)
        required_tool_ids = _required_tool_ids(tier)
        stopping_conditions = _stopping_conditions(family, tier, len(gold))
        structure = _make_structure_vector(
            tier=tier,
            program=program,
            gold=gold,
            corpus=corpus,
            query_stages=query_stages,
            reconciliation_axes=reconciliation_axes,
            verification_checkpoints=verification_checkpoints,
            recovery_branches=recovery_branches,
            required_tool_ids=required_tool_ids,
            stopping_conditions=stopping_conditions,
        )
        demand = _make_capability_demand_vector(structure)
        retrieval_scope = {
            "aliases": sorted(
                {item.subject.name for item in gold} | {item.predicate for item in gold}
            ),
            "partial_constraints": {
                "period_labels": sorted({time_label(item) for item in gold}),
                "historical_only": True,
                "required_source_count": structure.public_source_count,
                "query_decomposition_rounds": structure.query_decomposition_rounds,
            },
            "corpus_boundary": {
                "evidence_count": len(corpus.evidence),
                "source_count": structure.public_source_count,
                "build_label": graph_build_id or "mixed_frozen_source_artifacts",
            },
        }
        task = TaskPackageBuilder(self._registry).build(
            task_domain="finance",
            task_type=family.removeprefix("finance."),
            level=TaskLevel.RESEARCH_WORKFLOW,
            instruction=instruction,
            evidence=gold,
            bundle=bundle,
            proof_graph=graph,
            program=program,
            answer_schema={
                "type": "capability_sensitive_numeric",
                "required_fields": sorted(program_output_fields(program, self._registry)),
            },
            retrieval_scope=retrieval_scope,
            retrieval_track=RetrievalTrack.SEMI_OPEN,
            planning_track=PlanningTrack.PLAN_HIDDEN,
            oracle_selection_contract={
                "answer_projection": answer_projection,
                "capability_structure_hash": structure.vector_hash,
            },
            source_grounding_requirement=VerifierRequirement.REQUIRED,
            metadata={
                "capability_sensitive_frontier": {
                    "version": CAPABILITY_SENSITIVE_FRONTIER_VERSION,
                    "tier": tier.value,
                    "capability_axes": CAPABILITY_AXES,
                    "required_tool_ids": required_tool_ids,
                    "reconciliation_axes": reconciliation_axes,
                    "verification_checkpoints": verification_checkpoints,
                    "stopping_conditions": stopping_conditions,
                    "single_retrieval_solvable": structure.single_retrieval_solvable,
                }
            },
            quality_rubric={
                "evidence_coverage": 1.0,
                "operation_replay": True,
                "source_citation": True,
                "recovery_branch_resolution": len(recovery_branches),
                "verification_checkpoint_coverage": len(verification_checkpoints),
            },
            identity_context={
                "family": family,
                "tier": tier.value,
                "structure_hash": structure.vector_hash,
            },
        )
        task = task.model_copy(
            update={"public": task.public.model_copy(update={"allowed_tools": required_tool_ids})}
        )
        execution = TaskProgramExecutor(self._registry).execute(
            program,
            {item.evidence_id: item for item in gold},
        )
        verification = TaskProgramOracleVerifier(self._registry).verify(
            program,
            {item.evidence_id: item for item in gold},
            execution.node_outputs,
        )
        projected = _project_output(execution.final_output, answer_projection)
        source_artifacts = tuple(
            sorted(
                {
                    artifact_id
                    for item in (*gold, *distractors)
                    for artifact_id in self._pool.origin_artifacts[item.evidence_id]
                }
            )
        )
        values = {
            "family": family,
            "tier": tier,
            "source_artifact_ids": source_artifacts,
            "evidence_bundle": bundle,
            "public_corpus": corpus,
            "proof_graph": graph,
            "task": task,
            "execution": execution,
            "verification": verification,
            "projected_expected_output": projected,
            "answer_projection": answer_projection,
            "reconciliation_axes": reconciliation_axes,
            "verification_checkpoints": verification_checkpoints,
            "recovery_branches": recovery_branches,
            "query_stages": query_stages,
            "required_tool_ids": required_tool_ids,
            "stopping_conditions": stopping_conditions,
            "structure": structure,
            "capability_demand": demand,
        }
        provisional = CapabilitySensitiveTaskArtifact.model_construct(
            artifact_id="pending",
            **values,
        )
        return CapabilitySensitiveTaskArtifact(
            artifact_id=capability_sensitive_task_artifact_id(provisional),
            **values,
        )


def make_capability_sensitive_frontier_audit(
    tasks: tuple[CapabilitySensitiveTaskArtifact, ...],
    *,
    minimum_frontier_mean_gain: float = 1.0,
    minimum_family_frontier_gain: float = 0.5,
    minimum_passing_family_count: int = len(CAPABILITY_SENSITIVE_FAMILIES),
) -> CapabilitySensitiveFrontierAudit:
    if not tasks:
        raise ValueError("capability-sensitive Frontier audit requires tasks")
    by_tier = {tier: tuple(item for item in tasks if item.tier == tier) for tier in DifficultyTier}
    by_family_tier = {
        family: {
            tier: tuple(item for item in tasks if item.family == family and item.tier == tier)
            for tier in DifficultyTier
        }
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    if any(not values for values in by_tier.values()) or any(
        not values for tiers in by_family_tier.values() for values in tiers.values()
    ):
        raise ValueError("capability-sensitive task population is not tier/family complete")

    def mean(values: Sequence[float]) -> float:
        return round(sum(values) / len(values), 9)

    dimension_means = {
        dimension: {
            tier: mean([float(getattr(item.structure, dimension)) for item in values])
            for tier, values in by_tier.items()
        }
        for dimension in STRICT_MONOTONIC_DIMENSIONS
    }
    dimension_passes = {
        dimension: (
            values[DifficultyTier.EASY_CONTROL]
            < values[DifficultyTier.FRONTIER]
            < values[DifficultyTier.HARD_CONTROL]
        )
        for dimension, values in dimension_means.items()
    }
    family_dimension_means = {
        family: {
            dimension: {
                tier: mean([float(getattr(item.structure, dimension)) for item in items])
                for tier, items in tiers.items()
            }
            for dimension in STRICT_MONOTONIC_DIMENSIONS
        }
        for family, tiers in by_family_tier.items()
    }
    family_dimension_passes = {
        family: {
            dimension: (
                values[DifficultyTier.EASY_CONTROL]
                < values[DifficultyTier.FRONTIER]
                < values[DifficultyTier.HARD_CONTROL]
            )
            for dimension, values in dimensions.items()
        }
        for family, dimensions in family_dimension_means.items()
    }
    single_rates = {
        tier: mean([float(item.structure.single_retrieval_solvable) for item in values])
        for tier, values in by_tier.items()
    }
    single_transition = (
        math.isclose(single_rates[DifficultyTier.EASY_CONTROL], 1.0, abs_tol=1e-12)
        and math.isclose(single_rates[DifficultyTier.FRONTIER], 0.0, abs_tol=1e-12)
        and math.isclose(single_rates[DifficultyTier.HARD_CONTROL], 0.0, abs_tol=1e-12)
    )
    family_single_rates = {
        family: {
            tier: mean([float(item.structure.single_retrieval_solvable) for item in items])
            for tier, items in tiers.items()
        }
        for family, tiers in by_family_tier.items()
    }
    family_single_passes = {
        family: (
            math.isclose(values[DifficultyTier.EASY_CONTROL], 1.0, abs_tol=1e-12)
            and math.isclose(values[DifficultyTier.FRONTIER], 0.0, abs_tol=1e-12)
            and math.isclose(values[DifficultyTier.HARD_CONTROL], 0.0, abs_tol=1e-12)
        )
        for family, values in family_single_rates.items()
    }
    tier_semantic = {
        tier: mean([item.structure.semantic_score for item in values])
        for tier, values in by_tier.items()
    }
    family_semantic = {
        family: {
            tier: mean([item.structure.semantic_score for item in values])
            for tier, values in tiers.items()
        }
        for family, tiers in by_family_tier.items()
    }
    frontier_gain = round(
        tier_semantic[DifficultyTier.FRONTIER] - tier_semantic[DifficultyTier.EASY_CONTROL],
        9,
    )
    hard_gain = round(
        tier_semantic[DifficultyTier.HARD_CONTROL] - tier_semantic[DifficultyTier.EASY_CONTROL],
        9,
    )
    passing_family_count = sum(
        values[DifficultyTier.FRONTIER] - values[DifficultyTier.EASY_CONTROL]
        >= minimum_family_frontier_gain
        for values in family_semantic.values()
    )
    execution_pass_rate = mean([float(item.verification.passed) for item in tasks])
    all_evidence = [
        evidence.evidence_id for task in tasks for evidence in task.public_corpus.evidence
    ]
    disjoint = len(all_evidence) == len(set(all_evidence))
    information = make_capability_information_audit(tasks)
    structural_ready = (
        all(dimension_passes.values())
        and all(
            passed
            for dimensions in family_dimension_passes.values()
            for passed in dimensions.values()
        )
        and single_transition
        and all(family_single_passes.values())
        and frontier_gain >= minimum_frontier_mean_gain
        and passing_family_count >= minimum_passing_family_count
        and math.isclose(execution_pass_rate, 1.0, abs_tol=1e-12)
        and disjoint
        and information.capability_direction_ready
    )
    values = {
        "task_count": len(tasks),
        "tier_counts": {tier: len(items) for tier, items in by_tier.items()},
        "family_tier_counts": {
            family: {tier: len(items) for tier, items in tiers.items()}
            for family, tiers in by_family_tier.items()
        },
        "dimension_tier_means": dimension_means,
        "strict_dimension_passes": dimension_passes,
        "family_dimension_tier_means": family_dimension_means,
        "family_strict_dimension_passes": family_dimension_passes,
        "single_retrieval_rates": single_rates,
        "single_retrieval_transition_passed": single_transition,
        "family_single_retrieval_rates": family_single_rates,
        "family_single_retrieval_transition_passes": family_single_passes,
        "tier_semantic_means": tier_semantic,
        "family_semantic_means": family_semantic,
        "frontier_mean_gain": frontier_gain,
        "hard_control_mean_gain": hard_gain,
        "minimum_frontier_mean_gain": minimum_frontier_mean_gain,
        "minimum_family_frontier_gain": minimum_family_frontier_gain,
        "minimum_passing_family_count": minimum_passing_family_count,
        "passing_family_count": passing_family_count,
        "execution_pass_rate": execution_pass_rate,
        "public_evidence_disjoint": disjoint,
        "capability_information": information,
        "capability_boundary_status": "not_evaluated_requires_model_calibration",
        "structural_frontier_ready": structural_ready,
        "next_permitted_stage": (
            "paired_model_capability_boundary_calibration"
            if structural_ready
            else "frontier_task_construction_only"
        ),
    }
    provisional = CapabilitySensitiveFrontierAudit.model_construct(
        audit_hash="pending",
        **values,
    )
    return CapabilitySensitiveFrontierAudit(
        audit_hash=capability_sensitive_frontier_audit_hash(provisional),
        **values,
    )


def make_capability_information_audit(
    tasks: tuple[CapabilitySensitiveTaskArtifact, ...],
) -> CapabilityInformationAudit:
    if not tasks:
        raise ValueError("capability information audit requires tasks")
    observed_families = {task.family for task in tasks}
    if observed_families != set(CAPABILITY_SENSITIVE_FAMILIES):
        raise ValueError("capability information audit requires the complete frozen family set")

    vectors = []
    for task in tasks:
        raw = [task.capability_demand.values[axis] for axis in CAPABILITY_AXES]
        norm = math.sqrt(sum(value * value for value in raw))
        vectors.append([value / norm for value in raw])
    vector_means = [
        sum(vector[index] for vector in vectors) / len(vectors)
        for index in range(len(CAPABILITY_AXES))
    ]
    centered_vectors = [
        [value - vector_means[index] for index, value in enumerate(vector)] for vector in vectors
    ]
    size = len(CAPABILITY_AXES)
    matrix = [[0.0 for _ in range(size)] for _ in range(size)]
    for vector in centered_vectors:
        for row in range(size):
            for column in range(size):
                matrix[row][column] += vector[row] * vector[column] / len(centered_vectors)
    eigenvalues = tuple(
        sorted((_clamp_small(value) for value in _symmetric_eigenvalues(matrix)), reverse=True)
    )
    maximum = max(eigenvalues)
    positive = [value for value in eigenvalues if maximum > 0 and value > maximum * 1e-6]
    numerical_rank = len(positive)
    unidentifiable_condition = 1e12
    full_condition = maximum / min(positive) if positive else unidentifiable_condition
    # Centered normalized demands live on a local sphere; one near-radial mode is not a
    # capability contrast. The frozen identifiable target is therefore the six-dimensional
    # tangent subspace induced by seven independently registered capability families.
    minimum_required_rank = len(CAPABILITY_AXES) - 1
    identifiable_values = positive[:minimum_required_rank]
    identifiable_condition = (
        maximum / identifiable_values[-1]
        if len(identifiable_values) == minimum_required_rank
        else full_condition
    )

    def effective_rank(values: Sequence[float]) -> float:
        total = sum(values)
        probabilities = [value / total for value in values] if total else []
        return (
            math.exp(-sum(value * math.log(value) for value in probabilities if value > 0))
            if probabilities
            else 0.0
        )

    full_effective_rank = effective_rank(positive)
    identifiable_effective_rank = effective_rank(identifiable_values)
    axis_means = {
        axis: round(
            sum(task.capability_demand.values[axis] for task in tasks) / len(tasks),
            9,
        )
        for axis in CAPABILITY_AXES
    }
    family_contrasts = {
        family: {
            axis: round(
                sum(
                    centered_vectors[index][axis_index]
                    for index, task in enumerate(tasks)
                    if task.family == family
                )
                / sum(task.family == family for task in tasks),
                9,
            )
            for axis_index, axis in enumerate(CAPABILITY_AXES)
        }
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    primary_axis_passes = {
        family: (
            values[FAMILY_PRIMARY_CAPABILITY[family]] > 0
            and values[FAMILY_PRIMARY_CAPABILITY[family]]
            > max(
                value for axis, value in values.items() if axis != FAMILY_PRIMARY_CAPABILITY[family]
            )
        )
        for family, values in family_contrasts.items()
    }
    primary_alignment_ready = all(primary_axis_passes.values())
    minimum_effective_rank = 4.0
    maximum_identifiable_condition = 100.0
    ready = (
        numerical_rank >= minimum_required_rank
        and identifiable_effective_rank >= minimum_effective_rank
        and identifiable_condition <= maximum_identifiable_condition
        and min(axis_means.values()) >= 0.05
        and primary_alignment_ready
    )
    values = {
        "axis_order": CAPABILITY_AXES,
        "axis_mean_demand": axis_means,
        "information_eigenvalues": tuple(round(value, 12) for value in eigenvalues),
        "numerical_rank": numerical_rank,
        "full_effective_rank": round(full_effective_rank, 9),
        "identifiable_subspace_effective_rank": round(identifiable_effective_rank, 9),
        "full_condition_number": round(full_condition, 9),
        "identifiable_subspace_condition_number": round(identifiable_condition, 9),
        "family_axis_contrasts": family_contrasts,
        "family_primary_axis_passes": primary_axis_passes,
        "primary_axis_alignment_ready": primary_alignment_ready,
        "minimum_required_rank": minimum_required_rank,
        "minimum_identifiable_subspace_effective_rank": minimum_effective_rank,
        "maximum_identifiable_subspace_condition_number": maximum_identifiable_condition,
        "minimum_axis_mean": 0.05,
        "capability_direction_ready": ready,
    }
    provisional = CapabilityInformationAudit.model_construct(audit_hash="pending", **values)
    return CapabilityInformationAudit(
        audit_hash=capability_information_audit_hash(provisional),
        **values,
    )


def _load_evidence_pool(path: Path) -> _EvidencePool:
    pool = _EvidencePool()
    policy = FinanceSemanticPolicy()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            artifact_id = str(value["artifact_id"])
            pool.source_artifact_count += 1
            pool.source_artifact_ids.add(artifact_id)
            omega = value["joint_compilation"]["omega"]
            for payload in omega["evidence_bundle"]["evidence"]:
                item = EvidenceItem.model_validate(payload)
                pool.gold.setdefault(item.evidence_id, item)
                pool.public.setdefault(item.evidence_id, item)
                pool.origin_artifacts[item.evidence_id].add(artifact_id)
            for payload in omega["public_corpus"]["evidence"]:
                item = EvidenceItem.model_validate(payload)
                pool.public.setdefault(item.evidence_id, item)
                pool.origin_artifacts[item.evidence_id].add(artifact_id)
                # Every source Corpus was already content-bound and grounded. Promotion into
                # the new construction pool is still fail-closed on the current Finance policy;
                # the composite Program is independently executed and replayed later.
                if policy.validate_evidence(item).passed:
                    pool.gold.setdefault(item.evidence_id, item)
    if not pool.gold or len({item.source.source_id for item in pool.public.values()}) < 3:
        raise ValueError("source Finance population lacks the registered Evidence breadth")
    return pool


def _temporal_series(values: Iterable[EvidenceItem]) -> tuple[tuple[EvidenceItem, ...], ...]:
    grouped: dict[tuple[Any, ...], dict[date | datetime, EvidenceItem]] = defaultdict(dict)
    for item in values:
        point = temporal_sort_key(item)
        if not isinstance(item.payload, ScalarObservation) or point is None:
            continue
        payload = item.payload.model_dump(mode="json", exclude_none=True)
        payload_context = tuple(
            sorted(
                (key, json.dumps(value, sort_keys=True))
                for key, value in payload.items()
                if key not in {"kind", "value", "precision"}
            )
        )
        scope = item.scope
        key = (
            item.subject.subject_id,
            item.predicate,
            item.source.source_id,
            item.definition.definition_id,
            canonical_hash(item.definition.attributes, prefix="capability_definition_attributes:"),
            payload_context,
            item.temporal_context.basis,
            item.temporal_context.frequency,
            scope.scope_type if scope else None,
            scope.scope_id if scope else None,
        )
        current = grouped[key].get(point)
        if current is None or item.evidence_id < current.evidence_id:
            grouped[key][point] = item
    return tuple(
        tuple(item for _, item in sorted(points.items(), key=lambda entry: entry[0]))
        for _, points in sorted(grouped.items(), key=lambda entry: str(entry[0]))
        if len(points) >= 2
    )


def _cross_entity_windows(
    series_values: tuple[tuple[EvidenceItem, ...], ...],
) -> dict[str, dict[str, tuple[EvidenceItem, EvidenceItem]]]:
    grouped: dict[str, dict[str, tuple[EvidenceItem, EvidenceItem]]] = defaultdict(dict)
    for series in series_values:
        for left, right in zip(series, series[1:], strict=False):
            if not _periods_are_adjacent(left, right):
                continue
            scope_type = left.scope.scope_type if left.scope else None
            key = canonical_hash(
                {
                    "predicate": left.predicate,
                    "source": left.source.source_id,
                    "definition": left.definition,
                    "payload_context": _payload_context(left),
                    "time_basis": left.temporal_context.basis,
                    "frequency": left.temporal_context.frequency,
                    "scope_type": scope_type,
                    "left_period": _temporal_identity(left),
                    "right_period": _temporal_identity(right),
                },
                prefix="capability_cross_entity_window:",
            )
            grouped[key][left.subject.subject_id] = (left, right)
    return dict(grouped)


def _contiguous_windows(
    series: tuple[EvidenceItem, ...],
    length: int,
) -> Iterable[tuple[EvidenceItem, ...]]:
    for start in range(len(series) - length + 1):
        window = series[start : start + length]
        if all(
            _periods_are_adjacent(left, right)
            for left, right in zip(window, window[1:], strict=False)
        ):
            yield window


def _periods_are_adjacent(left: EvidenceItem, right: EvidenceItem) -> bool:
    left_point = temporal_sort_key(left)
    right_point = temporal_sort_key(right)
    if left_point is None or right_point is None or left_point >= right_point:
        return False
    frequency = str(left.temporal_context.frequency or "").casefold()
    if frequency != str(right.temporal_context.frequency or "").casefold():
        return False
    left_month = left_point.year * 12 + left_point.month
    right_month = right_point.year * 12 + right_point.month
    if frequency in {"annual", "yearly"}:
        return right_point.year == left_point.year + 1
    if frequency == "quarterly":
        return right_month == left_month + 3
    if frequency == "monthly":
        return right_month == left_month + 1
    days = (right_point - left_point).days
    if frequency == "weekly":
        return 5 <= days <= 10
    if frequency == "daily":
        return 1 <= days <= 10
    fiscal_left = str(left.domain_context.get("fiscal_quarter") or "").upper()
    fiscal_right = str(right.domain_context.get("fiscal_quarter") or "").upper()
    if fiscal_left == fiscal_right == "FY":
        return right_point.year == left_point.year + 1
    return False


def _temporal_program(
    registry: OperationRegistry,
    family: str,
    tier: DifficultyTier,
    evidence: tuple[EvidenceItem, ...],
) -> tuple[tuple[EvidenceItem, ...], TaskProgram, str, dict[str, str]]:
    subject = evidence[0].subject.name
    metric = evidence[0].predicate
    labels = tuple(time_label(item) for item in evidence)
    nodes: list[OperationNode] = []
    projection: dict[str, str] = {}
    if family == "finance.calculation_chain":
        interval_nodes = _explicit_relative_change_nodes(registry, nodes, evidence)
        if tier == DifficultyTier.EASY_CONTROL:
            output = interval_nodes[0]
            instruction = (
                f"Calculate {subject}'s {metric} signed change from {labels[0]} to {labels[1]}, "
                "then divide it by the baseline value to obtain the relative-change ratio."
            )
        elif tier == DifficultyTier.FRONTIER:
            output = _append_binary_node(
                registry, nodes, "result", "difference", interval_nodes[0], interval_nodes[1]
            )
            instruction = (
                f"Derive the signed relative-change ratio for {subject}'s {metric} in both "
                f"{labels[0]}–{labels[1]} and {labels[1]}–{labels[2]}, then calculate the "
                "difference between those ratios."
            )
        else:
            baseline = _append_aggregate_node(
                registry, nodes, "prior_mean", interval_nodes[:-1], method="mean"
            )
            output = _append_binary_node(
                registry, nodes, "result", "difference", baseline, interval_nodes[-1]
            )
            instruction = (
                f"Derive each signed relative-change ratio for {subject}'s {metric}; compare "
                f"the latest ratio over {labels[-2]}–{labels[-1]} with the mean ratio across "
                "the two preceding intervals."
            )
    elif family == "finance.definition_reconciliation":
        operator = "difference"
        interval_nodes = _interval_nodes(registry, nodes, evidence, operator)
        if tier == DifficultyTier.EASY_CONTROL:
            output = interval_nodes[0]
            instruction = (
                f"Calculate the signed change in {subject}'s {metric} "
                f"from {labels[0]} to {labels[1]}."
            )
        elif tier == DifficultyTier.FRONTIER:
            output = _append_binary_node(
                registry, nodes, "result", "compare", interval_nodes[0], interval_nodes[1]
            )
            projection = {
                interval_nodes[0]: f"{labels[0]}–{labels[1]}",
                interval_nodes[1]: f"{labels[1]}–{labels[2]}",
            }
            instruction = (
                f"After reconciling the reported definition and period basis, determine which "
                f"of {subject}'s {metric} changes was higher: {labels[0]}–{labels[1]} or "
                f"{labels[1]}–{labels[2]}."
            )
        else:
            baseline = _append_aggregate_node(
                registry, nodes, "prior_mean", interval_nodes[:-1], method="mean"
            )
            output = _append_binary_node(
                registry, nodes, "result", "difference", baseline, interval_nodes[-1]
            )
            instruction = (
                f"Reconcile the definition and period basis for {subject}'s {metric}, then "
                f"measure how the {labels[-2]}–{labels[-1]} change differs from the mean of "
                "the two preceding changes."
            )
    elif family == "finance.multi_hop_retrieval_join":
        if tier == DifficultyTier.EASY_CONTROL:
            output = _append_aggregate_evidence_node(
                registry, nodes, "result", evidence, method="mean"
            )
            instruction = f"Find and average {subject}'s {metric} for {labels[0]} and {labels[1]}."
        elif tier == DifficultyTier.FRONTIER:
            mean_node = _append_aggregate_evidence_node(
                registry, nodes, "baseline_mean", evidence[:-1], method="mean"
            )
            output = _append_operation_evidence_node(
                registry,
                nodes,
                "result",
                "difference",
                mean_node,
                evidence[-1],
            )
            instruction = (
                f"Join {subject}'s {metric} observations for {', '.join(labels[:-1])}; "
                f"compare their mean with {labels[-1]}."
            )
        else:
            mean_node = _append_aggregate_evidence_node(
                registry, nodes, "baseline_mean", evidence[:2], method="mean"
            )
            first_deviation = _append_operation_evidence_node(
                registry, nodes, "intermediate_deviation", "difference", mean_node, evidence[2]
            )
            output = _append_operation_evidence_node(
                registry, nodes, "result", "difference", first_deviation, evidence[3]
            )
            instruction = (
                f"Join all four {subject} {metric} observations from {labels[0]} through "
                f"{labels[-1]}; compute the first two-period mean, its deviation at "
                f"{labels[2]}, and the subsequent change in that deviation at {labels[3]}."
            )
    elif family == "finance.stopping_decision_control":
        interval_nodes = _interval_nodes(registry, nodes, evidence, "growth")
        if tier == DifficultyTier.EASY_CONTROL:
            output = _append_binary_evidence_node(
                registry, nodes, "result", "compare", evidence[0], evidence[1]
            )
            projection = {
                evidence[0].evidence_id: labels[0],
                evidence[1].evidence_id: labels[1],
            }
            instruction = (
                f"Determine whether {subject}'s {metric} was higher in {labels[0]} or "
                f"{labels[1]}; stop only after both observations and the comparison are grounded."
            )
        elif tier == DifficultyTier.FRONTIER:
            output = _append_binary_node(
                registry, nodes, "result", "compare", interval_nodes[0], interval_nodes[1]
            )
            projection = {
                interval_nodes[0]: f"{labels[0]}–{labels[1]}",
                interval_nodes[1]: f"{labels[1]}–{labels[2]}",
            }
            instruction = (
                f"Search until all three adjacent {subject} {metric} observations are resolved, "
                f"compare growth in {labels[0]}–{labels[1]} and {labels[1]}–{labels[2]}, "
                "and stop only when no required period remains unresolved."
            )
        else:
            baseline = _append_aggregate_node(
                registry, nodes, "prior_mean", interval_nodes[:-1], method="mean"
            )
            output = _append_binary_node(
                registry, nodes, "result", "compare", baseline, interval_nodes[-1]
            )
            projection = {
                baseline: "mean of the first two interval growth rates",
                interval_nodes[-1]: f"{labels[-2]}–{labels[-1]}",
            }
            instruction = (
                f"Do not stop at the first matching record: resolve all four {subject} "
                f"{metric} observations from {labels[0]} through {labels[-1]}, reject "
                "inapplicable branches, and compare the latest growth with the verified "
                "mean of the two prior interval growth rates."
            )
    else:
        operator = "growth"
        interval_nodes = _interval_nodes(registry, nodes, evidence, operator)
        if tier == DifficultyTier.EASY_CONTROL:
            output = _append_binary_evidence_node(
                registry, nodes, "result", "compare", evidence[0], evidence[1]
            )
            projection = {
                evidence[0].evidence_id: labels[0],
                evidence[1].evidence_id: labels[1],
            }
            instruction = (
                f"Which {subject} {metric} observation was higher, {labels[0]} or {labels[1]}?"
                if family == "finance.verification_sensitive_selection"
                else (
                    f"Discard the near-match returned by the broad search, refine the query, "
                    f"and determine whether {subject}'s {metric} was higher in {labels[0]} "
                    f"or {labels[1]}."
                )
            )
        elif tier == DifficultyTier.FRONTIER:
            output = _append_binary_node(
                registry, nodes, "result", "compare", interval_nodes[0], interval_nodes[1]
            )
            projection = {
                interval_nodes[0]: f"{labels[0]}–{labels[1]}",
                interval_nodes[1]: f"{labels[1]}–{labels[2]}",
            }
            instruction = (
                (
                    f"Verify which interval had higher {subject} {metric} growth: "
                    f"{labels[0]}–{labels[1]} or {labels[1]}–{labels[2]}."
                )
                if family == "finance.verification_sensitive_selection"
                else (
                    f"When the initial result mismatches one required field, refine the query "
                    f"to recover all three {subject} {metric} observations and compare growth "
                    f"in {labels[0]}–{labels[1]} with {labels[1]}–{labels[2]}."
                )
            )
        else:
            baseline = _append_aggregate_node(
                registry, nodes, "prior_mean", interval_nodes[:-1], method="mean"
            )
            output = _append_binary_node(
                registry, nodes, "result", "compare", baseline, interval_nodes[-1]
            )
            projection = {
                baseline: "mean of the first two interval growth rates",
                interval_nodes[-1]: f"{labels[-2]}–{labels[-1]}",
            }
            instruction = (
                (
                    f"After independently checking every observation, determine whether "
                    f"{subject}'s {metric} growth in {labels[-2]}–{labels[-1]} exceeded the "
                    "mean growth of the two prior intervals."
                )
                if family == "finance.verification_sensitive_selection"
                else (
                    f"Recover from both registered near-match branches, resolve all four "
                    f"{subject} {metric} observations, and determine whether growth in "
                    f"{labels[-2]}–{labels[-1]} exceeded the verified mean growth of the "
                    "two prior intervals."
                )
            )
    return evidence, make_program(tuple(nodes), output), instruction, projection


def _cross_entity_program(
    registry: OperationRegistry,
    family: str,
    tier: DifficultyTier,
    pairs: tuple[tuple[EvidenceItem, EvidenceItem], ...],
) -> tuple[tuple[EvidenceItem, ...], TaskProgram, str, dict[str, str]]:
    evidence = tuple(item for pair in pairs for item in pair)
    metric = evidence[0].predicate
    earlier_label = time_label(pairs[0][0])
    later_label = time_label(pairs[0][1])
    names = tuple(pair[0].subject.name for pair in pairs)
    nodes: list[OperationNode] = []
    projection: dict[str, str] = {}
    if tier == DifficultyTier.EASY_CONTROL:
        output = _append_binary_evidence_node(
            registry, nodes, "result", "compare", pairs[0][1], pairs[1][1]
        )
        projection = {
            pairs[0][1].evidence_id: names[0],
            pairs[1][1].evidence_id: names[1],
        }
        instruction = (
            f"Which had higher {metric} in {later_label}, {names[0]} or {names[1]}, "
            "and by how much?"
        )
    else:
        operator = "growth" if family == "finance.branching_operation_plan" else "difference"
        derived = []
        for index, pair in enumerate(pairs, start=1):
            node_id = f"entity_{index}_{operator}"
            _append_binary_evidence_node(registry, nodes, node_id, operator, pair[0], pair[1])
            derived.append(node_id)
        if tier == DifficultyTier.FRONTIER:
            output = _append_binary_node(
                registry, nodes, "result", "compare", derived[0], derived[1]
            )
            projection = {derived[0]: names[0], derived[1]: names[1]}
            instruction = (
                f"Compare the {operator} in {metric} from {earlier_label} to {later_label} "
                f"for {names[0]} and {names[1]}; identify the higher result and verify it."
            )
        else:
            peer_mean = _append_aggregate_node(
                registry, nodes, "peer_mean", derived[:2], method="mean"
            )
            output = _append_binary_node(
                registry, nodes, "result", "compare", peer_mean, derived[2]
            )
            projection = {
                peer_mean: f"mean of {names[0]} and {names[1]}",
                derived[2]: names[2],
            }
            instruction = (
                f"After resolving ambiguous peer matches, compare {names[2]}'s {metric} "
                f"{operator} from {earlier_label} to {later_label} with the mean {operator} "
                f"for {names[0]} and {names[1]}, then cross-check the result."
            )
    return evidence, make_program(tuple(nodes), output), instruction, projection


def _operation_node(
    registry: OperationRegistry,
    *,
    node_id: str,
    operator_id: str,
    inputs: tuple[ProgramInputRef, ...],
    parameters: dict[str, Any] | None = None,
) -> OperationNode:
    definition = registry.require(operator_id)
    dependencies = tuple(ref.ref_id for ref in inputs if ref.kind == InputRefKind.OPERATION)
    return OperationNode(
        node_id=node_id,
        operator_id=operator_id,
        input_refs=inputs,
        parameters=parameters or {},
        output_schema=definition.output_schema,
        verifier_id=definition.verifier_id,
        dependencies=dependencies,
    )


def _evidence_ref(item: EvidenceItem) -> ProgramInputRef:
    return ProgramInputRef(kind=InputRefKind.EVIDENCE, ref_id=item.evidence_id)


def _operation_ref(node_id: str, selector: str = "value") -> ProgramInputRef:
    return ProgramInputRef(
        kind=InputRefKind.OPERATION,
        ref_id=node_id,
        selector=selector,
    )


def _append_binary_evidence_node(
    registry: OperationRegistry,
    nodes: list[OperationNode],
    node_id: str,
    operator_id: str,
    left: EvidenceItem,
    right: EvidenceItem,
) -> str:
    nodes.append(
        _operation_node(
            registry,
            node_id=node_id,
            operator_id=operator_id,
            inputs=(_evidence_ref(left), _evidence_ref(right)),
        )
    )
    return node_id


def _append_binary_node(
    registry: OperationRegistry,
    nodes: list[OperationNode],
    node_id: str,
    operator_id: str,
    left_node: str,
    right_node: str,
) -> str:
    nodes.append(
        _operation_node(
            registry,
            node_id=node_id,
            operator_id=operator_id,
            inputs=(_operation_ref(left_node), _operation_ref(right_node)),
        )
    )
    return node_id


def _append_operation_evidence_node(
    registry: OperationRegistry,
    nodes: list[OperationNode],
    node_id: str,
    operator_id: str,
    left_node: str,
    right: EvidenceItem,
    *,
    parameters: dict[str, Any] | None = None,
) -> str:
    nodes.append(
        _operation_node(
            registry,
            node_id=node_id,
            operator_id=operator_id,
            inputs=(_operation_ref(left_node), _evidence_ref(right)),
            parameters=parameters,
        )
    )
    return node_id


def _explicit_relative_change_nodes(
    registry: OperationRegistry,
    nodes: list[OperationNode],
    evidence: tuple[EvidenceItem, ...],
) -> tuple[str, ...]:
    outputs = []
    for index, (earlier, later) in enumerate(zip(evidence, evidence[1:], strict=False), start=1):
        difference = _append_binary_evidence_node(
            registry,
            nodes,
            f"interval_{index}_difference",
            "difference",
            earlier,
            later,
        )
        outputs.append(
            _append_operation_evidence_node(
                registry,
                nodes,
                f"interval_{index}_relative_change",
                "ratio",
                difference,
                earlier,
                parameters={"registered_pair": f"{earlier.predicate}/{earlier.predicate}"},
            )
        )
    return tuple(outputs)


def _append_aggregate_node(
    registry: OperationRegistry,
    nodes: list[OperationNode],
    node_id: str,
    input_nodes: Sequence[str],
    *,
    method: str,
) -> str:
    nodes.append(
        _operation_node(
            registry,
            node_id=node_id,
            operator_id="aggregate",
            inputs=tuple(_operation_ref(item) for item in input_nodes),
            parameters={"method": method},
        )
    )
    return node_id


def _append_aggregate_evidence_node(
    registry: OperationRegistry,
    nodes: list[OperationNode],
    node_id: str,
    evidence: Sequence[EvidenceItem],
    *,
    method: str,
) -> str:
    nodes.append(
        _operation_node(
            registry,
            node_id=node_id,
            operator_id="aggregate",
            inputs=tuple(_evidence_ref(item) for item in evidence),
            parameters={"method": method},
        )
    )
    return node_id


def _interval_nodes(
    registry: OperationRegistry,
    nodes: list[OperationNode],
    evidence: tuple[EvidenceItem, ...],
    operator_id: str,
) -> tuple[str, ...]:
    output = []
    for index, (left, right) in enumerate(zip(evidence, evidence[1:], strict=False), start=1):
        node_id = f"interval_{index}_{operator_id}"
        _append_binary_evidence_node(registry, nodes, node_id, operator_id, left, right)
        output.append(node_id)
    return tuple(output)


def _query_stages(family: str, tier: DifficultyTier) -> tuple[QueryStage, ...]:
    count = {
        DifficultyTier.EASY_CONTROL: 1,
        DifficultyTier.FRONTIER: 2,
        DifficultyTier.HARD_CONTROL: 3,
    }[tier]
    actions: tuple[Literal["broad_search", "typed_refinement", "document_inspection"], ...] = (
        "broad_search",
        "typed_refinement",
        "document_inspection",
    )
    dependencies = (
        "public task aliases",
        "candidate summaries returned by the broad search",
        "definition or provenance ambiguity returned by typed refinement",
    )
    stages = tuple(
        QueryStage(
            stage_index=index + 1, action=actions[index], observation_dependency=dependencies[index]
        )
        for index in range(count)
    )
    if family != "finance.multi_hop_retrieval_join":
        return stages
    return (
        *stages,
        QueryStage(
            stage_index=len(stages) + 1,
            action="cross_source_join",
            observation_dependency="typed records returned by all preceding source queries",
        ),
    )


def _reconciliation_axes(family: str, tier: DifficultyTier) -> tuple[str, ...]:
    base = {
        DifficultyTier.EASY_CONTROL: ("metric_definition",),
        DifficultyTier.FRONTIER: ("metric_definition", "period_alignment"),
        DifficultyTier.HARD_CONTROL: (
            "metric_definition",
            "period_alignment",
            "source_or_scope_disambiguation",
        ),
    }[tier]
    emphasis = {
        "finance.definition_reconciliation": ("unit_currency_context",),
    }.get(family, ())
    return tuple(dict.fromkeys((*base, *emphasis)))


def _verification_checkpoints(
    family: str,
    tier: DifficultyTier,
) -> tuple[str, ...]:
    base = {
        DifficultyTier.EASY_CONTROL: ("final_answer_replay",),
        DifficultyTier.FRONTIER: (
            "evidence_compatibility",
            "final_answer_replay",
        ),
        DifficultyTier.HARD_CONTROL: (
            "evidence_compatibility",
            "intermediate_operation_replay",
            "final_answer_replay",
        ),
    }[tier]
    if family == "finance.verification_sensitive_selection":
        return (*base, "selected_branch_cross_check")
    return base


def _required_tool_ids(tier: DifficultyTier) -> tuple[str, ...]:
    return {
        DifficultyTier.EASY_CONTROL: (
            "query_structured_fact",
            "calculator",
            "cross_check_evidence",
        ),
        DifficultyTier.FRONTIER: (
            "search_archive",
            "query_structured_fact",
            "calculator",
            "normalize_metric_unit_period",
            "cross_check_evidence",
        ),
        DifficultyTier.HARD_CONTROL: (
            "search_archive",
            "open_document",
            "query_structured_fact",
            "calculator",
            "normalize_metric_unit_period",
            "cross_check_evidence",
        ),
    }[tier]


def _stopping_conditions(
    family: str,
    tier: DifficultyTier,
    gold_count: int,
) -> tuple[str, ...]:
    base = {
        DifficultyTier.EASY_CONTROL: ("final_operation_completed",),
        DifficultyTier.FRONTIER: (
            "all_required_evidence_roles_resolved",
            "final_operation_verified",
        ),
        DifficultyTier.HARD_CONTROL: (
            "all_required_evidence_roles_resolved",
            "all_ambiguities_reconciled",
            "final_operation_verified",
        ),
    }[tier]
    if family == "finance.stopping_decision_control":
        final_condition = {
            DifficultyTier.EASY_CONTROL: f"grounded_evidence_count_equals_{gold_count}",
            DifficultyTier.FRONTIER: "no_required_period_remains_unresolved",
            DifficultyTier.HARD_CONTROL: "no_candidate_or_recovery_branch_remains_unresolved",
        }[tier]
        return (*base, final_condition)
    return base


def _make_structure_vector(
    *,
    tier: DifficultyTier,
    program: TaskProgram,
    gold: tuple[EvidenceItem, ...],
    corpus: EvidenceCorpus,
    query_stages: tuple[QueryStage, ...],
    reconciliation_axes: tuple[str, ...],
    verification_checkpoints: tuple[str, ...],
    recovery_branches: tuple[RecoveryBranch, ...],
    required_tool_ids: tuple[str, ...],
    stopping_conditions: tuple[str, ...],
) -> CapabilityStructureVector:
    gold_ids = {item.evidence_id for item in gold}
    depth = _program_depth(program)
    operation_count = len(program.nodes)
    minimal_calls = (
        len(query_stages)
        + operation_count
        + len(reconciliation_axes)
        + len(verification_checkpoints)
        + len(recovery_branches)
        + (1 if tier == DifficultyTier.HARD_CONTROL else 0)
    )
    values = {
        "evidence_hop_count": depth + 1,
        "gold_evidence_count": len(gold),
        "gold_subject_count": len({item.subject.subject_id for item in gold}),
        "public_source_count": len({item.source.source_id for item in corpus.evidence}),
        "source_heterogeneity_count": len(
            {item.source.authority.value for item in corpus.evidence}
        ),
        "operation_count": operation_count,
        "operation_dag_depth": depth,
        "operation_branch_count": _program_branch_count(program),
        "query_decomposition_rounds": len(query_stages),
        "reconciliation_count": len(reconciliation_axes),
        "required_verification_count": len(verification_checkpoints),
        "required_recovery_count": len(recovery_branches),
        "distractor_branch_count": len(corpus.evidence) - len(gold_ids),
        "tool_type_count": len(set(required_tool_ids)),
        "minimal_tool_calls": minimal_calls,
        "stopping_condition_count": len(stopping_conditions),
        "single_retrieval_solvable": tier == DifficultyTier.EASY_CONTROL,
    }
    provisional = CapabilityStructureVector.model_construct(
        semantic_score=0.0,
        vector_hash="pending",
        **values,
    )
    score = _semantic_score(provisional)
    with_score = CapabilityStructureVector.model_construct(
        semantic_score=score,
        vector_hash="pending",
        **values,
    )
    return CapabilityStructureVector(
        semantic_score=score,
        vector_hash=capability_structure_vector_hash(with_score),
        **values,
    )


def _semantic_score(value: CapabilityStructureVector) -> float:
    return round(
        value.operation_dag_depth
        + 0.35 * max(0, value.evidence_hop_count - 1)
        + 0.5 * max(0, value.public_source_count - 1)
        + 0.25 * max(0, value.tool_type_count - 1)
        + 0.25 * value.query_decomposition_rounds
        + 0.4 * value.reconciliation_count
        + 0.35 * value.required_verification_count
        + 0.5 * value.required_recovery_count
        + 0.2 * value.distractor_branch_count
        + 0.08 * value.minimal_tool_calls
        + 0.25 * value.stopping_condition_count
        + (0.5 if not value.single_retrieval_solvable else 0.0),
        9,
    )


def _make_capability_demand_vector(
    structure: CapabilityStructureVector,
) -> CapabilityDemandVector:
    values = {
        "retrieval": 0.4 * structure.query_decomposition_rounds
        + 0.2 * structure.public_source_count,
        "planning": 0.35 * structure.operation_dag_depth
        + 0.3 * structure.operation_branch_count
        + 0.5 * max(0, structure.gold_subject_count - 1),
        "calculation": 0.3 * structure.operation_count + 0.3 * structure.operation_dag_depth,
        "reconciliation": 0.7 * structure.reconciliation_count,
        "verification": 0.7 * structure.required_verification_count,
        "recovery": 0.8 * structure.required_recovery_count + 0.1,
        "stopping": 0.7 * structure.stopping_condition_count,
    }
    rounded = {axis: round(values[axis], 9) for axis in CAPABILITY_AXES}
    provisional = CapabilityDemandVector.model_construct(
        values=rounded,
        vector_hash="pending",
    )
    return CapabilityDemandVector(
        values=rounded,
        vector_hash=capability_demand_vector_hash(provisional),
    )


def _program_depth(program: TaskProgram) -> int:
    depth: dict[str, int] = {}
    for node in program.nodes:
        dependencies = [ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.OPERATION]
        depth[node.node_id] = 1 + max((depth[item] for item in dependencies), default=0)
    return max(depth.values())


def _program_branch_count(program: TaskProgram) -> int:
    consumers: dict[str, int] = defaultdict(int)
    independent_nodes = 0
    for node in program.nodes:
        dependencies = {ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.OPERATION}
        if not dependencies:
            independent_nodes += 1
        for dependency in dependencies:
            consumers[dependency] += 1
    return max(1, independent_nodes, max(consumers.values(), default=0))


def program_output_fields(program: TaskProgram, registry: OperationRegistry) -> set[str]:
    definition = registry.require(
        next(item for item in program.nodes if item.node_id == program.output_node_id).operator_id
    )
    if definition.output_model is not None:
        return set(definition.output_model.model_fields)
    return {"value"}


def _project_output(output: dict[str, Any], projection: dict[str, str]) -> dict[str, Any]:
    projected = dict(output)
    if "higher_ref" in projected and projected["higher_ref"] is not None:
        projected["higher_ref"] = projection.get(
            str(projected["higher_ref"]),
            str(projected["higher_ref"]),
        )
    return projected


def _minimum_mismatch_fields(
    candidate: EvidenceItem,
    gold: tuple[EvidenceItem, ...],
) -> tuple[str, ...]:
    candidates = []
    for target in gold:
        fields = tuple(
            field
            for field, differs in (
                ("subject", candidate.subject.subject_id != target.subject.subject_id),
                ("predicate", candidate.predicate != target.predicate),
                ("period", _temporal_identity(candidate) != _temporal_identity(target)),
                ("source", candidate.source.source_id != target.source.source_id),
                (
                    "definition",
                    candidate.definition.definition_id != target.definition.definition_id,
                ),
                ("payload_context", _payload_context(candidate) != _payload_context(target)),
            )
            if differs
        )
        candidates.append(fields)
    return min(candidates, key=lambda item: (len(item), item))


def _minimum_mismatch_count(candidate: EvidenceItem, gold: tuple[EvidenceItem, ...]) -> int:
    return len(_minimum_mismatch_fields(candidate, gold))


def _temporal_identity(item: EvidenceItem) -> tuple[Any, ...]:
    context = item.temporal_context
    return (
        context.label,
        context.valid_from.isoformat() if context.valid_from else None,
        context.valid_to.isoformat() if context.valid_to else None,
        context.observed_at.isoformat() if context.observed_at else None,
    )


def _payload_context(item: EvidenceItem) -> tuple[str | None, str | None]:
    if not isinstance(item.payload, ScalarObservation):
        return None, None
    return item.payload.unit, item.payload.currency


def _symmetric_eigenvalues(matrix: list[list[float]]) -> list[float]:
    values = [row[:] for row in matrix]
    size = len(values)
    for _ in range(100 * size * size):
        row, column = max(
            ((i, j) for i in range(size) for j in range(i + 1, size)),
            key=lambda item: abs(values[item[0]][item[1]]),
        )
        if abs(values[row][column]) < 1e-12:
            break
        angle = 0.5 * math.atan2(
            2 * values[row][column],
            values[column][column] - values[row][row],
        )
        cosine = math.cos(angle)
        sine = math.sin(angle)
        for index in range(size):
            if index in {row, column}:
                continue
            left = values[index][row]
            right = values[index][column]
            values[index][row] = values[row][index] = cosine * left - sine * right
            values[index][column] = values[column][index] = sine * left + cosine * right
        diagonal_left = values[row][row]
        diagonal_right = values[column][column]
        off_diagonal = values[row][column]
        values[row][row] = (
            cosine * cosine * diagonal_left
            - 2 * sine * cosine * off_diagonal
            + sine * sine * diagonal_right
        )
        values[column][column] = (
            sine * sine * diagonal_left
            + 2 * sine * cosine * off_diagonal
            + cosine * cosine * diagonal_right
        )
        values[row][column] = values[column][row] = 0.0
    return [values[index][index] for index in range(size)]


def _clamp_small(value: float) -> float:
    return 0.0 if abs(value) < 1e-12 else value


def render_capability_sensitive_frontier_report(
    population: CapabilitySensitiveFrontierPopulation,
) -> str:
    audit = population.audit
    lines = [
        "# Finance v25 Capability-Sensitive Frontier Construction",
        "",
        "## Result",
        "",
        f"- Population: `{population.population_id}`",
        f"- Real source artifacts: {population.source_artifact_count}",
        f"- Constructed tasks: {audit.task_count}",
        f"- Program replay pass rate: {audit.execution_pass_rate:.2%}",
        f"- Public Evidence disjoint: {audit.public_evidence_disjoint}",
        "- Per-family structural ladders: "
        f"{sum(all(values.values()) for values in audit.family_strict_dimension_passes.values())}"
        f"/{len(CAPABILITY_SENSITIVE_FAMILIES)}",
        f"- Structural Frontier ready: **{audit.structural_frontier_ready}**",
        f"- Next permitted stage: `{audit.next_permitted_stage}`",
        "- Model/API calls in this stage: 0",
        "- Capability boundary: not evaluated; requires paired Pro–Flash calibration.",
        "",
        "## Tier Means",
        "",
        "| Dimension | Easy | Frontier | Hard | Strict monotonic |",
        "| --- | ---: | ---: | ---: | :---: |",
    ]
    for dimension in STRICT_MONOTONIC_DIMENSIONS:
        values = audit.dimension_tier_means[dimension]
        lines.append(
            "| "
            + dimension
            + f" | {values[DifficultyTier.EASY_CONTROL]:.3f}"
            + f" | {values[DifficultyTier.FRONTIER]:.3f}"
            + f" | {values[DifficultyTier.HARD_CONTROL]:.3f}"
            + f" | {audit.strict_dimension_passes[dimension]} |"
        )
    lines.extend(
        [
            "",
            "## Capability Information",
            "",
            f"- Numerical rank: {audit.capability_information.numerical_rank}/7",
            f"- Full effective rank: {audit.capability_information.full_effective_rank:.3f}",
            "- Identifiable-subspace effective rank: "
            f"{audit.capability_information.identifiable_subspace_effective_rank:.3f}",
            "- Minimum identifiable-subspace effective rank: "
            f"{audit.capability_information.minimum_identifiable_subspace_effective_rank:.3f}",
            "- Identifiable-subspace condition number: "
            f"{audit.capability_information.identifiable_subspace_condition_number:.3f}",
            f"- Full condition number: {audit.capability_information.full_condition_number:.3f}",
            "- Family primary-axis alignment ready: "
            f"{audit.capability_information.primary_axis_alignment_ready}",
            "- Direction coverage ready: "
            f"{audit.capability_information.capability_direction_ready}",
            "",
            "| Family | Registered primary axis | Structural primary-axis pass |",
            "| --- | --- | :---: |",
            *(
                "| "
                + family
                + " | "
                + FAMILY_PRIMARY_CAPABILITY[family]
                + " | "
                + str(audit.capability_information.family_primary_axis_passes[family])
                + " |"
                for family in CAPABILITY_SENSITIVE_FAMILIES
            ),
            "",
            "The seven registered families separately exercise Retrieval, Planning, Calculation, "
            "Reconciliation, Verification, Recovery, and Stopping through executable Program or "
            "typed workflow requirements. The matrix is the covariance of centered, normalized "
            "structural-demand vectors; family labels only test expected primary-axis alignment "
            "and never add weight. Because centered normalized vectors have one near-radial mode, "
            "authorization uses the frozen six-dimensional contrast subspace while retaining the "
            "full spectrum as a diagnostic. This rejects low-rank pseudo-distributions before "
            "model calls, but does not establish that any task lies near a model's empirical "
            "capability boundary.",
            "",
            "## Scientific Boundary",
            "",
            "This stage authorizes at most paired capability-boundary calibration. Exact Target, "
            "GP-C, Authorization Objective access, VTDO updates, and production Contribution "
            "remain forbidden.",
        ]
    )
    return "\n".join(lines) + "\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Construct and audit capability-sensitive Finance Frontier tasks offline."
    )
    parser.add_argument("--source-artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sampling-salt", required=True)
    args = parser.parse_args(argv)
    population = build_capability_sensitive_frontier_population(
        source_artifacts_path=args.source_artifacts,
        output_path=args.output,
        run_id=args.run_id,
        sampling_salt=args.sampling_salt,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        render_capability_sensitive_frontier_report(population), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "population_id": population.population_id,
                "task_count": population.audit.task_count,
                "structural_frontier_ready": population.audit.structural_frontier_ready,
                "next_permitted_stage": population.audit.next_permitted_stage,
                "output": str(args.output.resolve()),
                "report": str(args.report.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if population.audit.structural_frontier_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
