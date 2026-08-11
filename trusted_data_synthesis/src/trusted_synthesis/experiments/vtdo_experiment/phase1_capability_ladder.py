from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.task.program import InputRefKind, TaskProgram
from trusted_synthesis.core.task.schema import TaskRequirement
from trusted_synthesis.core.trajectory.specification import (
    ReferenceExecutionIdentity,
    TrajectoryVerificationContext,
    make_omega_component_manifest,
    make_oracle_execution_specification,
    make_trajectory_verification_context,
)
from trusted_synthesis.domains.finance.agent_tools import (
    FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
    make_finance_archive_agent_tool_manifest,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION,
)
from trusted_synthesis.domains.finance.iterative_agent_verifier import (
    FINANCE_ITERATIVE_AGENT_VERIFIER_VERSION,
    FinanceIterativeAgentVerifier,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import FinanceTaskStateArtifact
from trusted_synthesis.experiments.vtdo_experiment.phase1_explorer_runtime_factorial import (
    SCRIPTED_TOOL_POLICY_VERSION,
    scripted_tool_policy_hash,
    scripted_tool_sequence,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    EXPECTED_FAMILIES,
    ExplorerArm,
    ExplorerModelContract,
    FinanceProFlashPilotContract,
    _load_artifacts,
    _paired_sampling_contract_hash,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import (
    ITERATIVE_AGENT_SOLVER_VERSION,
    IterativeAgentProtocolProfile,
)
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest

CAPABILITY_LADDER_CONTRACT_VERSION = "finance_capability_ladder_contract.v4"
CAPABILITY_LADDER_DIFFICULTY_VERSION = "finance_agent_difficulty_vector.v1"
CAPABILITY_LADDER_RUNTIME_VIEW_VERSION = "finance_capability_runtime_view.v4"
CAPABILITY_LADDER_SEMANTIC_AUDIT_VERSION = "finance_semantic_ladder_audit.v1"
CAPABILITY_LADDER_RUNNER_VERSION = "finance_capability_ladder_runner.v4"

TOOL_CALL_BUDGET = 12
FAILED_TOOL_CALL_BUDGET = 3
OBSERVATION_BYTE_BUDGET = 1_000_000
MODEL_TOKEN_BUDGET = 90_000
CANDIDATE_LIMIT_PER_FAMILY = 30
QUALIFICATION_TASKS_PER_FAMILY = 3
FRONTIER_TASKS_PER_FAMILY = 5
HARD_CONTROL_TASKS_PER_FAMILY = 2


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DifficultyTier(str, Enum):
    EASY_CONTROL = "easy_control"
    FRONTIER = "frontier"
    HARD_CONTROL = "hard_control"


class PublicGuidanceView(str, Enum):
    FULL = "full"
    ROLES_HIDDEN = "roles_hidden"
    MINIMAL = "minimal"


class DifficultyComponent(FrozenModel):
    score: float = Field(ge=0)
    features: dict[str, float]


class FinanceAgentDifficultyVector(FrozenModel):
    semantic: DifficultyComponent
    agentic: DifficultyComponent
    protocol: DifficultyComponent
    capability_score: float = Field(ge=0)
    vector_hash: str = Field(min_length=1)
    schema_version: str = CAPABILITY_LADDER_DIFFICULTY_VERSION

    @model_validator(mode="after")
    def validate_vector(self) -> FinanceAgentDifficultyVector:
        expected = round(self.semantic.score + self.agentic.score, 6)
        if not math.isclose(self.capability_score, expected, abs_tol=1e-9):
            raise ValueError("capability score must exclude protocol friction")
        if self.vector_hash != finance_agent_difficulty_vector_hash(self):
            raise ValueError("difficulty vector identity is invalid")
        return self


class CandidateTaskContract(FrozenModel):
    candidate_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    source_artifact_id: str = Field(min_length=1)
    source_omega_context_id: str = Field(min_length=1)
    public_corpus_id: str = Field(min_length=1)
    public_corpus_hash: str = Field(min_length=1)
    public_evidence_version_set_hash: str = Field(min_length=1)
    gold_evidence_count: int = Field(ge=1)
    public_evidence_count: int = Field(ge=1)
    difficulty: FinanceAgentDifficultyVector
    deterministic_selection_key: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_candidate(self) -> CandidateTaskContract:
        if self.family not in EXPECTED_FAMILIES:
            raise ValueError("capability candidate has an unknown family")
        if self.public_evidence_count < self.gold_evidence_count:
            raise ValueError("capability candidate Corpus is smaller than Gold Evidence")
        if self.candidate_id != capability_candidate_id(self):
            raise ValueError("capability candidate identity is invalid")
        return self


class RuntimeTaskContract(FrozenModel):
    runtime_task_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    tier: DifficultyTier
    guidance_view: PublicGuidanceView
    runtime_omega_context_id: str = Field(min_length=1)
    runtime_omega_manifest_id: str = Field(min_length=1)
    public_task_view_hash: str = Field(min_length=1)
    tool_environment_manifest_id: str = Field(min_length=1)
    protocol_profile_hash: str = Field(min_length=1)
    difficulty: FinanceAgentDifficultyVector

    @model_validator(mode="after")
    def validate_runtime_task(self) -> RuntimeTaskContract:
        expected_view = {
            DifficultyTier.EASY_CONTROL: PublicGuidanceView.FULL,
            DifficultyTier.FRONTIER: PublicGuidanceView.ROLES_HIDDEN,
            DifficultyTier.HARD_CONTROL: PublicGuidanceView.MINIMAL,
        }[self.tier]
        if self.guidance_view != expected_view:
            raise ValueError("runtime task uses the wrong guidance view for its tier")
        if self.runtime_task_id != capability_runtime_task_id(self):
            raise ValueError("runtime task identity is invalid")
        return self


class ExclusionArtifactContract(FrozenModel):
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    role: Literal["historical_population", "executed_rollouts"]


class RuntimeQualificationThresholds(FrozenModel):
    minimum_completion_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_raw_json_contract_rate: float = Field(default=0.85, ge=0, le=1)
    minimum_bounded_json_resolution_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_tool_technical_success_rate: float = Field(default=0.95, ge=0, le=1)
    minimum_final_answer_emission_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_observation_replay_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_authority_integrity_rate: float = Field(default=1.0, ge=0, le=1)
    maximum_host_verification_repair_rate: float = Field(default=0.15, ge=0, le=1)
    maximum_budget_exhaustion_count: int = Field(default=0, ge=0)


class CapabilityCalibrationThresholds(FrozenModel):
    minimum_pro_autonomous_validity: float = Field(default=0.60, ge=0, le=1)
    maximum_pro_autonomous_validity: float = Field(default=0.90, ge=0, le=1)
    minimum_flash_autonomous_validity: float = Field(default=0.30, ge=0, le=1)
    maximum_flash_autonomous_validity: float = Field(default=0.75, ge=0, le=1)
    minimum_autonomy_necessity_gain: float = Field(default=0.05, ge=0, le=1)
    minimum_paired_model_gap: float = Field(default=0.05, ge=0, le=1)
    calibration_intervals_are_development_only: Literal[True] = True


class SemanticLadderAudit(FrozenModel):
    """Separates task semantics from hidden guidance and runtime friction."""

    qualification_task_count: int = Field(ge=1)
    frontier_task_count: int = Field(ge=1)
    hard_control_task_count: int = Field(ge=1)
    tier_semantic_means: dict[DifficultyTier, float]
    family_semantic_means: dict[str, dict[DifficultyTier, float]]
    frontier_mean_gain: float
    hard_control_mean_gain: float
    minimum_frontier_mean_gain: float = Field(default=1.0, gt=0)
    minimum_family_frontier_gain: float = Field(default=0.5, gt=0)
    minimum_passing_family_count: int = Field(default=4, ge=1)
    passing_family_count: int = Field(ge=0)
    semantic_frontier_ready: bool
    audit_hash: str = Field(min_length=1)
    schema_version: str = CAPABILITY_LADDER_SEMANTIC_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SemanticLadderAudit:
        if set(self.tier_semantic_means) != set(DifficultyTier):
            raise ValueError("semantic ladder audit lacks a difficulty tier")
        if set(self.family_semantic_means) != set(EXPECTED_FAMILIES):
            raise ValueError("semantic ladder audit lacks a Finance family")
        if any(
            set(values) != set(DifficultyTier) for values in self.family_semantic_means.values()
        ):
            raise ValueError("semantic ladder family audit lacks a difficulty tier")
        easy = self.tier_semantic_means[DifficultyTier.EASY_CONTROL]
        frontier = self.tier_semantic_means[DifficultyTier.FRONTIER]
        hard = self.tier_semantic_means[DifficultyTier.HARD_CONTROL]
        if not math.isclose(self.frontier_mean_gain, frontier - easy, abs_tol=1e-9):
            raise ValueError("semantic Frontier gain is inconsistent")
        if not math.isclose(self.hard_control_mean_gain, hard - easy, abs_tol=1e-9):
            raise ValueError("semantic Hard-Control gain is inconsistent")
        passing = sum(
            values[DifficultyTier.FRONTIER] - values[DifficultyTier.EASY_CONTROL]
            >= self.minimum_family_frontier_gain
            for values in self.family_semantic_means.values()
        )
        if self.passing_family_count != passing:
            raise ValueError("semantic ladder passing-family count is inconsistent")
        ready = (
            self.frontier_mean_gain >= self.minimum_frontier_mean_gain
            and passing >= self.minimum_passing_family_count
        )
        if self.semantic_frontier_ready != ready:
            raise ValueError("semantic Frontier authorization is inconsistent")
        if self.audit_hash != semantic_ladder_audit_hash(self):
            raise ValueError("semantic ladder audit identity is invalid")
        return self


class FinanceCapabilityLadderContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    run_role: Literal["development_runtime_then_capability_calibration"] = (
        "development_runtime_then_capability_calibration"
    )
    source_artifacts_path: str = Field(min_length=1)
    source_artifacts_sha256: str = Field(min_length=64, max_length=64)
    model_source_contract_path: str = Field(min_length=1)
    model_source_contract_sha256: str = Field(min_length=64, max_length=64)
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    exclusions: tuple[ExclusionArtifactContract, ...] = Field(min_length=1)
    excluded_task_count: int = Field(ge=0)
    excluded_task_set_hash: str = Field(min_length=1)
    excluded_evidence_version_count: int = Field(ge=0)
    excluded_evidence_version_set_hash: str = Field(min_length=1)
    eligible_task_count: int = Field(ge=1)
    eligible_family_counts: dict[str, int]
    qualification_tasks: tuple[RuntimeTaskContract, ...] = Field(min_length=18, max_length=18)
    candidate_pool: tuple[CandidateTaskContract, ...] = Field(min_length=150, max_length=300)
    frontier_tasks: tuple[RuntimeTaskContract, ...] = Field(min_length=30, max_length=30)
    hard_control_tasks: tuple[RuntimeTaskContract, ...] = Field(min_length=12, max_length=12)
    selected_public_evidence_disjoint: Literal[True] = True
    candidate_population_hash: str = Field(min_length=1)
    model_contracts: tuple[ExplorerModelContract, ...] = Field(min_length=2, max_length=2)
    paired_sampling_contract_hash: str = Field(min_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    semantic_ladder_audit: SemanticLadderAudit
    scripted_tool_policy_version: str = SCRIPTED_TOOL_POLICY_VERSION
    scripted_tool_policy_hash: str = Field(min_length=1)
    qualification_runs_per_task_model_runtime: int = Field(default=3, ge=3, le=3)
    capability_runs_per_task_model_runtime: int = Field(default=10, ge=8, le=12)
    qualification_runtime_arms: tuple[Literal["scripted_tool", "autonomous_agent"], ...] = (
        "scripted_tool",
        "autonomous_agent",
    )
    capability_runtime_arms: tuple[
        Literal["direct_fixed_retrieval", "scripted_tool", "autonomous_agent"], ...
    ] = ("direct_fixed_retrieval", "scripted_tool", "autonomous_agent")
    direct_control_interpretation: Literal["fixed_retrieval_pipeline_not_no_tool"] = (
        "fixed_retrieval_pipeline_not_no_tool"
    )
    model_contract_repair_attempts: int = Field(default=2, ge=2, le=2)
    maximum_tool_calls: int = Field(default=TOOL_CALL_BUDGET, ge=1)
    maximum_failed_tool_calls: int = Field(default=FAILED_TOOL_CALL_BUDGET, ge=0)
    maximum_total_observation_bytes: int = Field(default=OBSERVATION_BYTE_BUDGET, ge=1)
    maximum_model_tokens_per_rollout: int = Field(default=MODEL_TOKEN_BUDGET, ge=1)
    random_seed: int
    sampling_salt: str = Field(min_length=1)
    runtime_qualification_thresholds: RuntimeQualificationThresholds
    capability_calibration_thresholds: CapabilityCalibrationThresholds
    toolset_version: str = FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION
    runtime_version: str = FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION
    solver_version: str = ITERATIVE_AGENT_SOLVER_VERSION
    verifier_version: str = FINANCE_ITERATIVE_AGENT_VERIFIER_VERSION
    verifier_manifest_hash: str = Field(min_length=1)
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    contribution_approximation_authorized: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = CAPABILITY_LADDER_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceCapabilityLadderContract:
        _validate_runtime_balance(
            self.qualification_tasks,
            expected_per_family=QUALIFICATION_TASKS_PER_FAMILY,
            expected_tier=DifficultyTier.EASY_CONTROL,
        )
        _validate_runtime_balance(
            self.frontier_tasks,
            expected_per_family=FRONTIER_TASKS_PER_FAMILY,
            expected_tier=DifficultyTier.FRONTIER,
        )
        _validate_runtime_balance(
            self.hard_control_tasks,
            expected_per_family=HARD_CONTROL_TASKS_PER_FAMILY,
            expected_tier=DifficultyTier.HARD_CONTROL,
        )
        candidate_ids = {item.candidate_id for item in self.candidate_pool}
        if len(candidate_ids) != len(self.candidate_pool):
            raise ValueError("capability candidate pool contains duplicates")
        if tuple(item.candidate_id for item in self.candidate_pool) != tuple(sorted(candidate_ids)):
            raise ValueError("capability candidate pool is not canonically ordered")
        qualification_ids = {item.candidate_id for item in self.qualification_tasks}
        frontier_ids = {item.candidate_id for item in self.frontier_tasks}
        hard_ids = {item.candidate_id for item in self.hard_control_tasks}
        if qualification_ids & candidate_ids:
            raise ValueError("qualification and capability candidate populations overlap")
        if not frontier_ids <= candidate_ids or not hard_ids <= candidate_ids:
            raise ValueError("selected capability tasks are outside the frozen candidate pool")
        if frontier_ids & hard_ids:
            raise ValueError("Frontier and Hard-Control tasks overlap")
        if self.candidate_population_hash != capability_candidate_population_hash(
            self.candidate_pool
        ):
            raise ValueError("candidate population identity is invalid")
        arms = {item.arm for item in self.model_contracts}
        if arms != set(ExplorerArm) or len(arms) != len(self.model_contracts):
            raise ValueError("capability ladder requires one Pro and one Flash contract")
        if self.paired_sampling_contract_hash != _paired_sampling_contract_hash(
            self.model_contracts
        ):
            raise ValueError("Pro and Flash sampling contracts differ")
        if self.scripted_tool_policy_hash != scripted_tool_policy_hash():
            raise ValueError("capability ladder script policy identity is invalid")
        expected_semantic_audit = make_semantic_ladder_audit(
            self.qualification_tasks,
            self.frontier_tasks,
            self.hard_control_tasks,
        )
        if self.semantic_ladder_audit != expected_semantic_audit:
            raise ValueError("semantic ladder audit differs from frozen runtime tasks")
        if self.contract_id != finance_capability_ladder_contract_id(self):
            raise ValueError("capability ladder contract identity is invalid")
        return self


def semantic_ladder_audit_hash(value: SemanticLadderAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_hash"}),
        prefix="finance_semantic_ladder_audit:",
    )


def make_semantic_ladder_audit(
    qualification: tuple[RuntimeTaskContract, ...],
    frontier: tuple[RuntimeTaskContract, ...],
    hard_control: tuple[RuntimeTaskContract, ...],
    *,
    minimum_frontier_mean_gain: float = 1.0,
    minimum_family_frontier_gain: float = 0.5,
    minimum_passing_family_count: int = 4,
) -> SemanticLadderAudit:
    by_tier = {
        DifficultyTier.EASY_CONTROL: qualification,
        DifficultyTier.FRONTIER: frontier,
        DifficultyTier.HARD_CONTROL: hard_control,
    }

    def semantic_mean(items: tuple[RuntimeTaskContract, ...]) -> float:
        if not items:
            raise ValueError("semantic ladder tier cannot be empty")
        return round(
            sum(item.difficulty.semantic.score for item in items) / len(items),
            9,
        )

    tier_means = {tier: semantic_mean(items) for tier, items in by_tier.items()}
    family_means = {
        family: {
            tier: semantic_mean(tuple(item for item in items if item.family == family))
            for tier, items in by_tier.items()
        }
        for family in EXPECTED_FAMILIES
    }
    frontier_gain = round(
        tier_means[DifficultyTier.FRONTIER] - tier_means[DifficultyTier.EASY_CONTROL],
        9,
    )
    hard_gain = round(
        tier_means[DifficultyTier.HARD_CONTROL] - tier_means[DifficultyTier.EASY_CONTROL],
        9,
    )
    passing_family_count = sum(
        values[DifficultyTier.FRONTIER] - values[DifficultyTier.EASY_CONTROL]
        >= minimum_family_frontier_gain
        for values in family_means.values()
    )
    values = {
        "qualification_task_count": len(qualification),
        "frontier_task_count": len(frontier),
        "hard_control_task_count": len(hard_control),
        "tier_semantic_means": tier_means,
        "family_semantic_means": family_means,
        "frontier_mean_gain": frontier_gain,
        "hard_control_mean_gain": hard_gain,
        "minimum_frontier_mean_gain": minimum_frontier_mean_gain,
        "minimum_family_frontier_gain": minimum_family_frontier_gain,
        "minimum_passing_family_count": minimum_passing_family_count,
        "passing_family_count": passing_family_count,
        "semantic_frontier_ready": (
            frontier_gain >= minimum_frontier_mean_gain
            and passing_family_count >= minimum_passing_family_count
        ),
        "schema_version": CAPABILITY_LADDER_SEMANTIC_AUDIT_VERSION,
    }
    provisional = SemanticLadderAudit.model_construct(audit_hash="pending", **values)
    return SemanticLadderAudit(
        audit_hash=semantic_ladder_audit_hash(provisional),
        **values,
    )


class _SourceRow(FrozenModel):
    task_id: str
    family: str
    artifact_id: str
    source_context_id: str
    evidence_version_ids: frozenset[str]


def prepare_finance_capability_ladder_contract(
    *,
    source_artifacts_path: Path,
    model_source_contract_path: Path,
    finance_archive_config_path: Path,
    historical_population_paths: tuple[Path, ...],
    executed_rollout_paths: tuple[Path, ...],
    output_path: Path,
    run_id: str,
    random_seed: int,
    sampling_salt: str,
) -> FinanceCapabilityLadderContract:
    if output_path.exists():
        raise ValueError("capability ladder contract is immutable and already exists")
    source_artifacts_path = source_artifacts_path.resolve()
    model_source_contract_path = model_source_contract_path.resolve()
    finance_archive_config_path = finance_archive_config_path.resolve()
    exclusions = _freeze_exclusions(historical_population_paths, executed_rollout_paths)
    excluded_task_ids: set[str] = set()
    explicitly_excluded_evidence: set[str] = set()
    for item in exclusions:
        with Path(item.path).open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    _collect_exclusion_identities(
                        json.loads(line),
                        excluded_task_ids,
                        explicitly_excluded_evidence,
                    )
    rows = _scan_source_rows(source_artifacts_path)
    by_task = {item.task_id: item for item in rows}
    excluded_evidence = set(explicitly_excluded_evidence)
    for task_id in excluded_task_ids:
        row = by_task.get(task_id)
        if row is not None:
            excluded_evidence.update(row.evidence_version_ids)
    eligible = tuple(
        item
        for item in rows
        if item.task_id not in excluded_task_ids
        and not (item.evidence_version_ids & excluded_evidence)
    )
    eligible_counts = Counter(item.family for item in eligible)
    if set(eligible_counts) != set(EXPECTED_FAMILIES):
        raise ValueError("fresh task pool does not cover every frozen Finance family")
    if min(eligible_counts.values()) < (
        QUALIFICATION_TASKS_PER_FAMILY + FRONTIER_TASKS_PER_FAMILY + HARD_CONTROL_TASKS_PER_FAMILY
    ):
        raise ValueError("fresh task pool cannot support the registered ladder")
    artifacts = _load_artifacts(source_artifacts_path, {item.task_id for item in eligible})
    protocol = IterativeAgentProtocolProfile(
        initial_plan_mode="implicit_public",
        observation_view="compact",
        contract_repair_token_reserve=8_000,
        final_answer_token_reserve=12_000,
        host_repair_missing_verification=True,
    )
    candidates_by_task = {
        row.task_id: _candidate_contract(
            row,
            artifacts[row.task_id],
            sampling_salt=sampling_salt,
            protocol_profile=protocol,
        )
        for row in eligible
    }
    qualification: list[CandidateTaskContract] = []
    candidate_pool: list[CandidateTaskContract] = []
    for family in EXPECTED_FAMILIES:
        family_candidates = [
            candidates_by_task[item.task_id] for item in eligible if item.family == family
        ]
        ordered_easy = sorted(
            family_candidates,
            key=lambda item: (item.difficulty.capability_score, item.deterministic_selection_key),
        )
        selected_easy = ordered_easy[:QUALIFICATION_TASKS_PER_FAMILY]
        qualification.extend(selected_easy)
        easy_ids = {item.candidate_id for item in selected_easy}
        remaining = [item for item in family_candidates if item.candidate_id not in easy_ids]
        sampled = _stratified_candidate_sample(
            remaining,
            limit=min(CANDIDATE_LIMIT_PER_FAMILY, len(remaining)),
        )
        candidate_pool.extend(sampled)
    frontier: list[CandidateTaskContract] = []
    hard: list[CandidateTaskContract] = []
    for family in EXPECTED_FAMILIES:
        sampled = [item for item in candidate_pool if item.family == family]
        ranked = sorted(
            sampled,
            key=lambda item: (item.difficulty.capability_score, item.deterministic_selection_key),
            reverse=True,
        )
        family_hard = ranked[:HARD_CONTROL_TASKS_PER_FAMILY]
        hard.extend(family_hard)
        family_hard_ids = {item.candidate_id for item in family_hard}
        frontier.extend(
            [item for item in ranked if item.candidate_id not in family_hard_ids][
                :FRONTIER_TASKS_PER_FAMILY
            ]
        )
    runtime_qualification = tuple(
        _runtime_task_contract(item, artifacts[item.task_id], DifficultyTier.EASY_CONTROL, protocol)
        for item in qualification
    )
    runtime_frontier = tuple(
        _runtime_task_contract(item, artifacts[item.task_id], DifficultyTier.FRONTIER, protocol)
        for item in frontier
    )
    runtime_hard = tuple(
        _runtime_task_contract(item, artifacts[item.task_id], DifficultyTier.HARD_CONTROL, protocol)
        for item in hard
    )
    _require_selected_evidence_disjoint(
        (*runtime_qualification, *runtime_frontier, *runtime_hard),
        by_task,
    )
    source_models = FinanceProFlashPilotContract.model_validate_json(
        model_source_contract_path.read_text(encoding="utf-8")
    ).model_contracts
    values = {
        "run_id": run_id,
        "run_role": "development_runtime_then_capability_calibration",
        "source_artifacts_path": str(source_artifacts_path),
        "source_artifacts_sha256": _sha256(source_artifacts_path),
        "model_source_contract_path": str(model_source_contract_path),
        "model_source_contract_sha256": _sha256(model_source_contract_path),
        "finance_archive_config_path": str(finance_archive_config_path),
        "finance_archive_config_sha256": _sha256(finance_archive_config_path),
        "exclusions": exclusions,
        "excluded_task_count": len(excluded_task_ids),
        "excluded_task_set_hash": canonical_hash(
            tuple(sorted(excluded_task_ids)), prefix="capability_excluded_tasks:"
        ),
        "excluded_evidence_version_count": len(excluded_evidence),
        "excluded_evidence_version_set_hash": canonical_hash(
            tuple(sorted(excluded_evidence)), prefix="capability_excluded_evidence:"
        ),
        "eligible_task_count": len(eligible),
        "eligible_family_counts": dict(sorted(eligible_counts.items())),
        "qualification_tasks": runtime_qualification,
        "candidate_pool": tuple(sorted(candidate_pool, key=lambda item: item.candidate_id)),
        "frontier_tasks": runtime_frontier,
        "hard_control_tasks": runtime_hard,
        "selected_public_evidence_disjoint": True,
        "candidate_population_hash": capability_candidate_population_hash(candidate_pool),
        "model_contracts": source_models,
        "paired_sampling_contract_hash": _paired_sampling_contract_hash(source_models),
        "protocol_profile": protocol,
        "semantic_ladder_audit": make_semantic_ladder_audit(
            runtime_qualification,
            runtime_frontier,
            runtime_hard,
        ),
        "scripted_tool_policy_version": SCRIPTED_TOOL_POLICY_VERSION,
        "scripted_tool_policy_hash": scripted_tool_policy_hash(),
        "qualification_runs_per_task_model_runtime": 3,
        "capability_runs_per_task_model_runtime": 10,
        "qualification_runtime_arms": ("scripted_tool", "autonomous_agent"),
        "capability_runtime_arms": (
            "direct_fixed_retrieval",
            "scripted_tool",
            "autonomous_agent",
        ),
        "direct_control_interpretation": "fixed_retrieval_pipeline_not_no_tool",
        "model_contract_repair_attempts": 2,
        "maximum_tool_calls": TOOL_CALL_BUDGET,
        "maximum_failed_tool_calls": FAILED_TOOL_CALL_BUDGET,
        "maximum_total_observation_bytes": OBSERVATION_BYTE_BUDGET,
        "maximum_model_tokens_per_rollout": MODEL_TOKEN_BUDGET,
        "random_seed": random_seed,
        "sampling_salt": sampling_salt,
        "runtime_qualification_thresholds": RuntimeQualificationThresholds(),
        "capability_calibration_thresholds": CapabilityCalibrationThresholds(),
        "toolset_version": FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
        "runtime_version": FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION,
        "solver_version": ITERATIVE_AGENT_SOLVER_VERSION,
        "verifier_version": FINANCE_ITERATIVE_AGENT_VERIFIER_VERSION,
        "verifier_manifest_hash": FinanceIterativeAgentVerifier().manifest_hash,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "production_contribution": 0.0,
        "schema_version": CAPABILITY_LADDER_CONTRACT_VERSION,
    }
    provisional = FinanceCapabilityLadderContract.model_construct(contract_id="pending", **values)
    contract = FinanceCapabilityLadderContract(
        contract_id=finance_capability_ladder_contract_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def capability_runtime_context(
    artifact: FinanceTaskStateArtifact,
    tier: DifficultyTier,
    protocol_profile: IterativeAgentProtocolProfile,
) -> tuple[TrajectoryVerificationContext, AgentToolEnvironmentManifest]:
    source = artifact.omega
    corpus = source.public_corpus
    snapshot_id = str(corpus.build_id or f"corpus:{corpus.corpus_id}")
    manifest = make_finance_archive_agent_tool_manifest(
        environment_id=f"finance_v24:{tier.value}:{source.task.task_id}",
        corpus_id=corpus.corpus_id,
        corpus_hash=corpus.corpus_hash,
        archive_snapshot_id=snapshot_id,
        archive_snapshot_hash=corpus.corpus_hash,
        maximum_tool_calls=TOOL_CALL_BUDGET,
        maximum_failed_tool_calls=FAILED_TOOL_CALL_BUDGET,
        maximum_total_observation_bytes=OBSERVATION_BYTE_BUDGET,
    )
    view = _guidance_view_for_tier(tier)
    metadata = _public_metadata_view(source.task.public.metadata, view)
    metadata["capability_ladder_runtime"] = {
        "version": CAPABILITY_LADDER_RUNTIME_VIEW_VERSION,
        "tier": tier.value,
        "guidance_view": view.value,
        "protocol_profile_hash": protocol_profile.profile_hash,
        "tool_environment_manifest_id": manifest.manifest_id,
    }
    public = source.task.public.model_copy(
        update={
            "allowed_tools": tuple(item.tool_id for item in manifest.tools),
            "retrieval_scope": {
                **source.task.public.retrieval_scope,
                "corpus_boundary": {
                    "corpus_id": corpus.corpus_id,
                    "corpus_hash": corpus.corpus_hash,
                    "evidence_count": len(corpus.evidence),
                    "snapshot_id": snapshot_id,
                },
            },
            "metadata": metadata,
        }
    )
    task = source.task.model_copy(update={"public": public})
    references = tuple(
        ReferenceExecutionIdentity(item, digest)
        for item, digest in zip(
            source.oracle_specification.reference_example_ids,
            source.oracle_specification.reference_example_hashes,
            strict=True,
        )
    )
    oracle = make_oracle_execution_specification(
        task,
        source.evidence_bundle,
        corpus,
        source.proof_graph,
        source.quality_contract,
        reference_examples=references,
    )
    context = make_trajectory_verification_context(
        task,
        source.evidence_bundle,
        corpus,
        source.proof_graph,
        source.quality_contract,
        oracle,
    )
    return context, manifest


def finance_agent_difficulty_vector_hash(value: FinanceAgentDifficultyVector) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"vector_hash"}),
        prefix="finance_agent_difficulty_vector:",
    )


def capability_candidate_id(value: CandidateTaskContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"candidate_id"}),
        prefix="finance_capability_candidate:",
    )


def capability_candidate_population_hash(
    values: list[CandidateTaskContract] | tuple[CandidateTaskContract, ...],
) -> str:
    normalized = tuple(
        item.model_dump(mode="json") for item in sorted(values, key=lambda item: item.candidate_id)
    )
    return canonical_hash(
        normalized,
        prefix="finance_capability_candidate_population:",
    )


def capability_runtime_task_id(value: RuntimeTaskContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"runtime_task_id"}),
        prefix="finance_capability_runtime_task:",
    )


def finance_capability_ladder_contract_id(value: FinanceCapabilityLadderContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_capability_ladder_contract:",
    )


def _candidate_contract(
    row: _SourceRow,
    artifact: FinanceTaskStateArtifact,
    *,
    sampling_salt: str,
    protocol_profile: IterativeAgentProtocolProfile,
) -> CandidateTaskContract:
    vector = _difficulty_vector(artifact, protocol_profile, PublicGuidanceView.FULL)
    source = artifact.omega
    values = {
        "task_id": row.task_id,
        "family": row.family,
        "source_artifact_id": row.artifact_id,
        "source_omega_context_id": row.source_context_id,
        "public_corpus_id": source.public_corpus.corpus_id,
        "public_corpus_hash": source.public_corpus.corpus_hash,
        "public_evidence_version_set_hash": canonical_hash(
            tuple(sorted(row.evidence_version_ids)),
            prefix="capability_public_evidence_versions:",
        ),
        "gold_evidence_count": len(source.task.oracle.gold_evidence_ids),
        "public_evidence_count": len(source.public_corpus.evidence),
        "difficulty": vector,
        "deterministic_selection_key": canonical_hash(
            {"salt": sampling_salt, "task_id": row.task_id},
            prefix="capability_task_selection:",
        ),
    }
    provisional = CandidateTaskContract.model_construct(candidate_id="pending", **values)
    return CandidateTaskContract(candidate_id=capability_candidate_id(provisional), **values)


def _runtime_task_contract(
    candidate: CandidateTaskContract,
    artifact: FinanceTaskStateArtifact,
    tier: DifficultyTier,
    protocol_profile: IterativeAgentProtocolProfile,
) -> RuntimeTaskContract:
    context, manifest = capability_runtime_context(artifact, tier, protocol_profile)
    view = _guidance_view_for_tier(tier)
    difficulty = _difficulty_vector(artifact, protocol_profile, view)
    values = {
        "candidate_id": candidate.candidate_id,
        "task_id": candidate.task_id,
        "family": candidate.family,
        "tier": tier,
        "guidance_view": view,
        "runtime_omega_context_id": context.context_id,
        "runtime_omega_manifest_id": make_omega_component_manifest(context).manifest_id,
        "public_task_view_hash": canonical_hash(
            context.task.public, prefix="capability_public_task_view:"
        ),
        "tool_environment_manifest_id": manifest.manifest_id,
        "protocol_profile_hash": protocol_profile.profile_hash,
        "difficulty": difficulty,
    }
    provisional = RuntimeTaskContract.model_construct(runtime_task_id="pending", **values)
    return RuntimeTaskContract(runtime_task_id=capability_runtime_task_id(provisional), **values)


def _difficulty_vector(
    artifact: FinanceTaskStateArtifact,
    protocol_profile: IterativeAgentProtocolProfile,
    guidance_view: PublicGuidanceView,
) -> FinanceAgentDifficultyVector:
    omega = artifact.omega
    evidence_by_id = omega.public_corpus.by_id()
    gold = tuple(evidence_by_id[item] for item in omega.task.oracle.gold_evidence_ids)
    gold_ids = set(omega.task.oracle.gold_evidence_ids)
    distractors = tuple(
        item for item in omega.public_corpus.evidence if item.evidence_id not in gold_ids
    )
    program = omega.task.oracle.task_program
    operation_count = len(program.nodes)
    derived_operation_count = sum(item.operator_id != "lookup" for item in program.nodes)
    program_depth = _program_depth(program)
    subject_count = len({item.subject.subject_id for item in gold})
    metric_count = len({item.predicate for item in gold})
    period_count = len({_temporal_key(item) for item in gold})
    source_count = len({item.source.source_id for item in gold})
    definition_count = len({_definition_key(item) for item in gold})
    semantic_features = {
        "gold_evidence_count": float(len(gold)),
        "operation_count": float(operation_count),
        "derived_operation_count": float(derived_operation_count),
        "program_depth": float(program_depth),
        "subject_count": float(subject_count),
        "metric_count": float(metric_count),
        "period_count": float(period_count),
        "source_count": float(source_count),
        "definition_count": float(definition_count),
        "cross_source": float(source_count > 1),
    }
    semantic_score = round(
        len(gold)
        + 0.75 * derived_operation_count
        + 0.5 * max(0, program_depth - 1)
        + 0.5 * max(0, subject_count - 1)
        + 0.5 * max(0, metric_count - 1)
        + 0.35 * max(0, period_count - 1)
        + 0.75 * max(0, source_count - 1)
        + 0.25 * max(0, definition_count - 1),
        6,
    )
    single_violation = sum(_minimum_semantic_mismatches(item, gold) == 1 for item in distractors)
    broad = sum(_minimum_semantic_mismatches(item, gold) > 1 for item in distractors)
    scripted_steps = len(scripted_tool_sequence(artifact.pattern_id))
    source_guidance = dict(omega.task.public.metadata.get("agent_contract_guidance", {}))
    role_guidance_visible = float(
        guidance_view == PublicGuidanceView.FULL and "evidence_roles" in source_guidance
    )
    operation_guidance_visible = float(
        guidance_view != PublicGuidanceView.MINIMAL
        and bool(
            set(source_guidance)
            - {"evidence_roles", "general_rules", "terminal_operation_contract"}
        )
    )
    distractor_count = len(distractors)
    single_rate = single_violation / distractor_count if distractor_count else 0.0
    agentic_features = {
        "public_evidence_count": float(len(omega.public_corpus.evidence)),
        "distractor_count": float(distractor_count),
        "single_violation_distractor_count": float(single_violation),
        "broad_distractor_count": float(broad),
        "single_violation_rate": single_rate,
        "scripted_tool_step_count": float(scripted_steps),
        "verification_required": float(
            TaskRequirement.VERIFY_RESULT in omega.task.public.requirements
        ),
        "exact_role_guidance_visible": role_guidance_visible,
        "operation_guidance_visible": operation_guidance_visible,
    }
    agentic_score = round(
        math.log1p(distractor_count)
        + 2.0 * single_rate
        + 0.2 * scripted_steps
        + float(TaskRequirement.VERIFY_RESULT in omega.task.public.requirements)
        - role_guidance_visible
        - 0.5 * operation_guidance_visible,
        6,
    )
    serialized_public_bytes = len(
        json.dumps(
            omega.task.public.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    )
    mean_evidence_bytes = _mean(
        [
            float(len(json.dumps(item.model_dump(mode="json"), sort_keys=True).encode("utf-8")))
            for item in omega.public_corpus.evidence
        ]
    )
    protocol_features = {
        "public_task_bytes": float(serialized_public_bytes),
        "mean_evidence_bytes": mean_evidence_bytes,
        "answer_required_field_count": float(
            len(omega.task.public.answer_schema.get("required_fields", ()))
        ),
        "expected_scripted_calls": float(scripted_steps),
        "separate_model_plan_call": float(protocol_profile.initial_plan_mode == "model_contract"),
        "full_observation_view": float(protocol_profile.observation_view == "full"),
        "repair_token_reserve": float(protocol_profile.contract_repair_token_reserve),
        "final_answer_token_reserve": float(protocol_profile.final_answer_token_reserve),
    }
    protocol_score = round(
        serialized_public_bytes / 10_000
        + mean_evidence_bytes / 20_000
        + 0.15 * scripted_steps
        + float(protocol_profile.initial_plan_mode == "model_contract")
        + float(protocol_profile.observation_view == "full"),
        6,
    )
    values = {
        "semantic": DifficultyComponent(score=semantic_score, features=semantic_features),
        "agentic": DifficultyComponent(score=agentic_score, features=agentic_features),
        "protocol": DifficultyComponent(score=protocol_score, features=protocol_features),
        "capability_score": round(semantic_score + agentic_score, 6),
        "schema_version": CAPABILITY_LADDER_DIFFICULTY_VERSION,
    }
    provisional = FinanceAgentDifficultyVector.model_construct(vector_hash="pending", **values)
    return FinanceAgentDifficultyVector(
        vector_hash=finance_agent_difficulty_vector_hash(provisional),
        **values,
    )


def _program_depth(program: TaskProgram) -> int:
    depth: dict[str, int] = {}
    for node in program.nodes:
        dependencies = [ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.OPERATION]
        depth[node.node_id] = 1 + max((depth[item] for item in dependencies), default=0)
    return max(depth.values())


def _minimum_semantic_mismatches(
    candidate: EvidenceItem,
    gold: tuple[EvidenceItem, ...],
) -> int:
    return min(
        sum(
            (
                candidate.subject.subject_id != target.subject.subject_id,
                candidate.predicate != target.predicate,
                _temporal_key(candidate) != _temporal_key(target),
                candidate.source.source_id != target.source.source_id,
                _definition_key(candidate) != _definition_key(target),
                _payload_context(candidate) != _payload_context(target),
            )
        )
        for target in gold
    )


def _temporal_key(item: EvidenceItem) -> str:
    return canonical_hash(item.temporal_context, prefix="capability_temporal:")


def _definition_key(item: EvidenceItem) -> str:
    return canonical_hash(item.definition, prefix="capability_definition:")


def _payload_context(item: EvidenceItem) -> tuple[str, str]:
    payload = item.payload.model_dump(mode="json")
    unit = str(payload.get("normalized_unit") or payload.get("unit") or "")
    currency = str(payload.get("normalized_currency") or payload.get("currency") or "")
    return unit, currency


def _public_metadata_view(
    metadata: dict[str, Any],
    view: PublicGuidanceView,
) -> dict[str, Any]:
    output = dict(metadata)
    guidance = dict(output.get("agent_contract_guidance", {}))
    if view == PublicGuidanceView.ROLES_HIDDEN:
        guidance.pop("evidence_roles", None)
    elif view == PublicGuidanceView.MINIMAL:
        guidance = {
            key: value
            for key, value in guidance.items()
            if key in {"general_rules", "terminal_operation_contract"}
        }
    output["agent_contract_guidance"] = guidance
    return output


def _guidance_view_for_tier(tier: DifficultyTier) -> PublicGuidanceView:
    return {
        DifficultyTier.EASY_CONTROL: PublicGuidanceView.FULL,
        DifficultyTier.FRONTIER: PublicGuidanceView.ROLES_HIDDEN,
        DifficultyTier.HARD_CONTROL: PublicGuidanceView.MINIMAL,
    }[tier]


def _stratified_candidate_sample(
    values: list[CandidateTaskContract],
    *,
    limit: int,
) -> list[CandidateTaskContract]:
    ordered = sorted(
        values,
        key=lambda item: (item.difficulty.capability_score, item.deterministic_selection_key),
    )
    if len(ordered) <= limit:
        return ordered
    indices = {round(index * (len(ordered) - 1) / (limit - 1)) for index in range(limit)}
    if len(indices) != limit:
        raise ValueError("stratified capability sampling produced duplicate positions")
    return [ordered[index] for index in sorted(indices)]


def _scan_source_rows(path: Path) -> tuple[_SourceRow, ...]:
    rows: list[_SourceRow] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            omega = value["joint_compilation"]["omega"]
            rows.append(
                _SourceRow(
                    task_id=str(omega["task"]["task_id"]),
                    family=str(value["pattern_id"]),
                    artifact_id=str(value["artifact_id"]),
                    source_context_id=str(omega["context_id"]),
                    evidence_version_ids=frozenset(
                        str(item["evidence_version_id"])
                        for item in omega["public_corpus"]["evidence"]
                    ),
                )
            )
    if len({item.task_id for item in rows}) != len(rows):
        raise ValueError("source Agent population contains duplicate task IDs")
    return tuple(rows)


def _freeze_exclusions(
    historical_paths: tuple[Path, ...],
    rollout_paths: tuple[Path, ...],
) -> tuple[ExclusionArtifactContract, ...]:
    values: list[ExclusionArtifactContract] = []
    resolved: set[Path] = set()
    for role, paths in (
        ("historical_population", historical_paths),
        ("executed_rollouts", rollout_paths),
    ):
        for path in paths:
            path = path.resolve()
            if path in resolved:
                raise ValueError("capability exclusion path is duplicated")
            if not path.is_file():
                raise ValueError(f"capability exclusion is not a file: {path}")
            resolved.add(path)
            values.append(
                ExclusionArtifactContract(path=str(path), sha256=_sha256(path), role=role)
            )
    return tuple(sorted(values, key=lambda item: item.path))


def _collect_exclusion_identities(
    value: Any,
    task_ids: set[str],
    evidence_versions: set[str],
) -> None:
    if isinstance(value, dict):
        task_id = value.get("task_id")
        evidence_version = value.get("evidence_version_id")
        if isinstance(task_id, str) and task_id:
            task_ids.add(task_id)
        if isinstance(evidence_version, str) and evidence_version:
            evidence_versions.add(evidence_version)
        for nested in value.values():
            _collect_exclusion_identities(nested, task_ids, evidence_versions)
    elif isinstance(value, list):
        for nested in value:
            _collect_exclusion_identities(nested, task_ids, evidence_versions)


def _require_selected_evidence_disjoint(
    tasks: tuple[RuntimeTaskContract, ...],
    rows: dict[str, _SourceRow],
) -> None:
    owners: dict[str, str] = {}
    for task in tasks:
        for evidence_version in rows[task.task_id].evidence_version_ids:
            previous = owners.setdefault(evidence_version, task.task_id)
            if previous != task.task_id:
                raise ValueError("selected ladder tasks share public Evidence")


def _validate_runtime_balance(
    tasks: tuple[RuntimeTaskContract, ...],
    *,
    expected_per_family: int,
    expected_tier: DifficultyTier,
) -> None:
    if len({item.runtime_task_id for item in tasks}) != len(tasks):
        raise ValueError("runtime population contains duplicate contracts")
    if any(item.tier != expected_tier for item in tasks):
        raise ValueError("runtime population mixes difficulty tiers")
    if Counter(item.family for item in tasks) != Counter(
        {family: expected_per_family for family in EXPECTED_FAMILIES}
    ):
        raise ValueError("runtime population is not family-balanced")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Freeze the Finance v24 capability ladder")
    parser.add_argument("--source-artifacts", type=Path, required=True)
    parser.add_argument("--model-source-contract", type=Path, required=True)
    parser.add_argument("--finance-archive-config", type=Path, required=True)
    parser.add_argument("--historical-populations", type=Path, nargs="+", required=True)
    parser.add_argument("--executed-rollouts", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--sampling-salt", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    contract = prepare_finance_capability_ladder_contract(
        source_artifacts_path=args.source_artifacts,
        model_source_contract_path=args.model_source_contract,
        finance_archive_config_path=args.finance_archive_config,
        historical_population_paths=tuple(args.historical_populations),
        executed_rollout_paths=tuple(args.executed_rollouts),
        output_path=args.output,
        run_id=args.run_id,
        random_seed=args.seed,
        sampling_salt=args.sampling_salt,
    )
    print(contract.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
