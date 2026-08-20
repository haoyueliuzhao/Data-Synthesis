from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.program import (
    TaskProgramExecutor,
    TaskProgramOracleVerifier,
)
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.task.answer_schema import complete_answer_schema
from trusted_synthesis.core.task.program import InputRefKind, TaskProgram, make_program
from trusted_synthesis.core.task.schema import TaskRequirement
from trusted_synthesis.core.trajectory.executable_support import MechanismNecessityArtifact
from trusted_synthesis.core.trajectory.executable_task import (
    BoundPublicExecutableWitness,
    IntendedTaskUse,
    StaticModelAuthorityPathCatalog,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingTaskAudit,
    SourceArtifactFile,
    _harden_environment,
    _harden_record,
    _task_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    replay_authority_preserving_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_adequacy_contract_preflight import (  # noqa: E501
    BudgetAdequacyContractPreflightReport,
    BudgetAdequacyProtocolContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument import (  # noqa: E501
    CompletedTrajectoryScore,
    compiler_witness_trajectory,
    score_completed_trajectory,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_task_rematerialization import (  # noqa: E501
    IMPLEMENTATION_SOURCE_PATHS as V26_82_IMPLEMENTATION_SOURCE_PATHS,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    MechanismCounterfactualReplayRecord,
    RematerializedExecutableTaskRecord,
    TargetMechanism,
    _TaskDraft,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    V26FreshTaskPopulation,
    load_v26_selected_source_tasks,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_builder import (  # noqa: E501
    MECHANISM_SOURCE_FAMILY,
    _load_population,
    _source_task_values,
    _upgrade_task,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    PATH_STRATEGIES,
    TARGET_MECHANISMS,
    ImmutableArtifactFile,
    ImplementationSourceFile,
    OperationalTaskAdmission,
    OperationalTaskRecord,
    OperationClosureAudit,
    PathStrategy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_witness import (  # noqa: E501
    build_operation_closure_audit,
    build_operational_admission,
    compile_operational_witness,
    mechanism_necessity_and_catalog,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    VerifierV2TaskReplayBinding,
    _bind_verifier_v2,
    _load_and_replay_verifier_qualification,
    _task_replay_binding,
    _verifier_bound_environment,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.budget_closed import (
    ProviderRequestKind,
    ProviderTokenBudgetContract,
    _provider_request_kind,
    _required_reserves,
)
from trusted_synthesis.runtime.agent.compact_budget_prompt import (
    compact_public_task_context,
    render_compact_witness_prompts,
    require_action_neutral_public_projection,
)
from trusted_synthesis.runtime.agent.prospective_thinking import (
    PROSPECTIVE_THINKING_MODE_POLICY,
    ProspectiveThinkingModelBinding,
    bind_prospective_thinking,
    require_prospective_thinking,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig
from trusted_synthesis.runtime.tools import (
    AgentToolEnvironmentManifest,
    AgentToolObservation,
)

V26_BUDGET_FEASIBLE_ROLE_VERSION = "finance_v26_budget_feasible_role_task.v1"
V26_BUDGET_FEASIBLE_PATH_VERSION = "finance_v26_budget_feasible_path_audit.v1"
V26_COMPACT_PROMPT_CONTRACT_VERSION = "finance_v26_compact_prompt_contract.v1"
V26_ROLE_FRESHNESS_VERSION = "finance_v26_budget_feasible_role_freshness.v1"
V26_ROLE_CAPACITY_VERSION = "finance_v26_budget_feasible_role_capacity.v1"
V26_ROLE_DESTRUCTIVE_AUDIT_VERSION = "finance_v26_role_destructive_preflight.v1"
V26_ROLE_REPORT_VERSION = "finance_v26_budget_feasible_role_rematerialization_report.v1"

CAPABILITY_TASK_COUNT: Literal[12] = 12
REACHABILITY_TASK_COUNT: Literal[12] = 12
TASK_COUNT: Literal[24] = 24
TASKS_PER_ROLE_MECHANISM: Literal[3] = 3
CAPABILITY_PATH_COUNT: Literal[12] = 12
REACHABILITY_PATH_COUNT: Literal[36] = 36
TOTAL_PATH_COUNT: Literal[48] = 48

Role = Literal["capability", "reachability"]

FRESHNESS_CHANNELS = (
    "source_task_artifact_id",
    "source_task_semantic_signature",
    "source_task_hash",
    "evidence_id",
    "evidence_version_id",
    "source_record_id",
    "semantic_source_id",
    "task_package_id",
    "job_id",
)

SOURCE_POPULATION_PATHS = (
    "artifacts/vtdo_experiment/finance_v26_29_exposure_grounded_source_20260817/population.json",
    (
        "artifacts/vtdo_experiment/finance_v26_36_no_api_joint_scaffold_20260817/"
        "population/confirmation_source.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_40_no_api_joint_scaffold_20260817/"
        "population/confirmation_source.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_42_no_api_joint_scaffold_20260817/"
        "population/confirmation_source.json"
    ),
)
DEVELOPMENT_POPULATION_PATH = (
    "artifacts/vtdo_experiment/finance_v26_42_no_api_joint_scaffold_20260817/"
    "population/development.json"
)
ZERO_API_SOURCE_RECEIPT_PATHS = (
    "artifacts/vtdo_experiment/finance_v26_36_no_api_joint_scaffold_20260817/report.json",
    "artifacts/vtdo_experiment/finance_v26_40_no_api_joint_scaffold_20260817/report.json",
)
HISTORICAL_TASK_RECORD_PATHS = (
    (
        "artifacts/vtdo_experiment/finance_v26_56_executable_task_rematerialization_20260818/"
        "rematerialized_task_records.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_60_public_operation_rematerialization_20260818/"
        "operational_task_records.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_60_public_operation_rematerialization_v2_20260818/"
        "operational_task_records.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_62_public_operation_instrument_hardening_20260818/"
        "operational_task_records.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_65_authority_preserving_operation_hardening_20260819/"
        "operational_task_records.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_69_fresh_capability_population_20260819/"
        "operational_task_records.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_76_verifier_bound_instrument_population_20260819/"
        "operational_task_records.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_82_budget_closed_verifier_bound_instrument_population_20260820/"
        "operational_task_records.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820/"
        "operational_task_records.json"
    ),
)
HISTORICAL_JOB_MANIFEST_PATHS = (
    "artifacts/vtdo_experiment/finance_v26_33_bridge_development_20260817/job_manifest.json",
    "artifacts/vtdo_experiment/finance_v26_37_bridge_development_20260817/job_manifest.json",
    "artifacts/vtdo_experiment/finance_v26_41_bridge_development_20260817/job_manifest.json",
    "artifacts/vtdo_experiment/finance_v26_43_bridge_development_20260817/job_manifest.json",
    "artifacts/vtdo_experiment/finance_v26_57_empirical_support_pilot_20260818/job_manifest.json",
    (
        "artifacts/vtdo_experiment/finance_v26_61_operation_closure_regression_preflight_20260818/"
        "job_manifest.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_61_operation_closure_regression_preflight_v2_20260818/"
        "job_manifest.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_61_operation_closure_regression_v2_20260818/"
        "job_manifest.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_63_operation_closure_requalification_preflight_20260818/"
        "job_manifest.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_63_operation_closure_requalification_20260818/"
        "job_manifest.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_66_authority_preserving_instrument_requalification_20260819/"
        "job_manifest.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_66_authority_preserving_instrument_requalification_finalization_recovery_20260819/"
        "job_manifest.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_70_capability_development_preflight_20260819/"
        "job_manifest.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_70_state_reachability_preflight_20260819/"
        "job_manifest.json"
    ),
    "artifacts/vtdo_experiment/finance_v26_71_capability_development_20260819/job_manifest.json",
    "artifacts/vtdo_experiment/finance_v26_72_state_reachability_20260819/job_manifest.json",
    (
        "artifacts/vtdo_experiment/finance_v26_77_verifier_bound_instrument_preflight_20260819/"
        "job_manifest.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_79_verifier_bound_recovery_preflight_20260820/"
        "recovery_manifest.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_80_verifier_bound_instrument_recovery_20260820/"
        "recovery_manifest.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_83_budget_closed_verifier_bound_instrument_preflight_20260820/"
        "job_manifest.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820/"
        "job_manifest.json"
    ),
    (
        "artifacts/vtdo_experiment/finance_v26_85_budget_closed_recovery_preflight_20260820/"
        "recovery_manifest.json"
    ),
)
VERIFIER_QUALIFICATION_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
)
V26_82_PROVIDER_BUDGET_PATH = (
    "artifacts/vtdo_experiment/finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820/"
    "provider_token_budget_contract.json"
)
V26_89_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_89_budget_adequacy_contract_and_static_role_preflight_20260820"
)
THINKING_PROFILE_PATH = "config/deepseek_v4_flash_agent_thinking_v1.json"

IMPLEMENTATION_SOURCE_PATHS = tuple(
    sorted(
        {
            *V26_82_IMPLEMENTATION_SOURCE_PATHS,
            (
                "src/trusted_synthesis/experiments/vtdo_experiment/"
                "phase1_v26_budget_adequacy_contract_preflight.py"
            ),
            (
                "src/trusted_synthesis/experiments/vtdo_experiment/"
                "phase1_v26_budget_feasible_role_task_rematerialization.py"
            ),
            "src/trusted_synthesis/runtime/agent/compact_budget_prompt.py",
            "src/trusted_synthesis/runtime/agent/prospective_thinking.py",
        }
    )
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StaticRequestUpperBound(FrozenModel):
    request_index: int = Field(ge=0)
    request_kind: ProviderRequestKind
    prompt_sha256: str = Field(min_length=64, max_length=64)
    prompt_utf8_bytes: int = Field(ge=1)
    prompt_token_upper_bound: int = Field(ge=1)
    completion_token_upper_bound: int = Field(ge=1)
    request_token_upper_bound: int = Field(ge=1)
    cumulative_request_upper_bound: int = Field(ge=1)
    contract_repair_reserve_tokens: int = Field(ge=0)
    final_answer_reserve_tokens: int = Field(ge=0)
    required_reserve_tokens: int = Field(ge=0)
    projected_path_upper_bound: int = Field(ge=1)
    prompt_ceiling_passed: bool
    rollout_ceiling_passed: bool

    @model_validator(mode="after")
    def validate_bound(self) -> StaticRequestUpperBound:
        if self.prompt_token_upper_bound != self.prompt_utf8_bytes + 256:
            raise ValueError("static Prompt upper bound changed")
        if self.completion_token_upper_bound != 4096:
            raise ValueError("static completion upper bound changed")
        if self.request_token_upper_bound != (
            self.prompt_token_upper_bound + self.completion_token_upper_bound
        ):
            raise ValueError("static request upper-bound arithmetic changed")
        if self.required_reserve_tokens != (
            self.contract_repair_reserve_tokens + self.final_answer_reserve_tokens
        ):
            raise ValueError("static reserve arithmetic changed")
        if self.projected_path_upper_bound != (
            self.cumulative_request_upper_bound + self.required_reserve_tokens
        ):
            raise ValueError("static path upper-bound arithmetic changed")
        if self.prompt_ceiling_passed != (self.prompt_utf8_bytes <= 60000):
            raise ValueError("static Prompt Gate changed")
        if self.rollout_ceiling_passed != (self.projected_path_upper_bound <= 120000):
            raise ValueError("static rollout Gate changed")
        return self


class BudgetQualifiedPathAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    operational_task_package_id: str = Field(min_length=1)
    compact_prompt_contract_id: str = Field(min_length=1)
    budget_adequacy_contract_id: str = Field(min_length=1)
    provider_budget_contract_id: str = Field(min_length=1)
    thinking_binding_id: str = Field(min_length=1)
    role: Role
    mechanism_id: TargetMechanism
    path_strategy_id: PathStrategy
    public_path_condition: str | None
    compiler_witness_id: str = Field(min_length=1)
    compiler_trajectory_id: str = Field(min_length=1)
    request_bounds: tuple[StaticRequestUpperBound, ...] = Field(min_length=1)
    request_count: int = Field(ge=1)
    maximum_prompt_utf8_bytes: int = Field(ge=1)
    maximum_cumulative_path_upper_bound: int = Field(ge=1)
    minimum_headroom_tokens: int
    full_path_budget_qualified: Literal[True] = True
    compiler_fixture_only: Literal[True] = True
    empirical_row: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = V26_BUDGET_FEASIBLE_PATH_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetQualifiedPathAudit:
        if tuple(item.request_index for item in self.request_bounds) != tuple(
            range(len(self.request_bounds))
        ):
            raise ValueError("static path request indexes are not contiguous")
        if self.request_count != len(self.request_bounds):
            raise ValueError("static path request denominator changed")
        cumulative = 0
        for item in self.request_bounds:
            cumulative += item.request_token_upper_bound
            if item.cumulative_request_upper_bound != cumulative:
                raise ValueError("static path cumulative request sum changed")
        maximum = max(item.projected_path_upper_bound for item in self.request_bounds)
        if self.maximum_prompt_utf8_bytes != max(
            item.prompt_utf8_bytes for item in self.request_bounds
        ):
            raise ValueError("static path maximum Prompt changed")
        if self.maximum_cumulative_path_upper_bound != maximum:
            raise ValueError("static path maximum bound changed")
        if self.minimum_headroom_tokens != 120000 - maximum:
            raise ValueError("static path headroom changed")
        if not all(
            item.prompt_ceiling_passed and item.rollout_ceiling_passed
            for item in self.request_bounds
        ):
            raise ValueError("unqualified request entered a budget-qualified path")
        if self.role == "capability" and self.public_path_condition is not None:
            raise ValueError("Capability static Witness became path-conditioned")
        if self.role == "reachability" and self.public_path_condition != self.path_strategy_id:
            raise ValueError("Reachability static path lost its public condition")
        if self.audit_id != budget_qualified_path_audit_id(self):
            raise ValueError("budget-qualified path identity is invalid")
        return self


class CompactPromptContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    operational_task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    mechanism_id: TargetMechanism
    role: Role
    public_context: dict[str, Any]
    public_context_hash: str = Field(min_length=1)
    renderer_version: Literal["compact_budget_prompt.v1"] = "compact_budget_prompt.v1"
    observation_projection: Literal["public_selected_fact_operation_failure_state"] = (
        "public_selected_fact_operation_failure_state"
    )
    action_binding_fields_exposed: Literal[False] = False
    private_reasoning_content_requested_or_persisted: Literal[False] = False
    schema_version: str = V26_COMPACT_PROMPT_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CompactPromptContract:
        require_action_neutral_public_projection(self.public_context)
        if self.public_context_hash != canonical_hash(
            self.public_context,
            prefix="finance_v26_compact_public_context:",
        ):
            raise ValueError("compact public context hash changed")
        if self.contract_id != compact_prompt_contract_id(self):
            raise ValueError("compact Prompt Contract identity is invalid")
        return self


class BudgetFeasibleRoleTaskPackage(FrozenModel):
    task_package_id: str = Field(min_length=1)
    role: Role
    mechanism_id: TargetMechanism
    source_task_artifact_id: str = Field(min_length=1)
    operational_record_id: str = Field(min_length=1)
    operational_task_package_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    replay_binding_contract_id: str = Field(min_length=1)
    compact_prompt_contract_id: str = Field(min_length=1)
    budget_adequacy_contract_id: str = Field(min_length=1)
    provider_budget_contract_id: str = Field(min_length=1)
    thinking_policy_id: str = Field(min_length=1)
    thinking_binding_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    path_audit_ids: tuple[str, ...] = Field(min_length=1, max_length=3)
    path_strategy_ids: tuple[PathStrategy, ...] = Field(min_length=1, max_length=3)
    compiler_witness_ids: tuple[str, ...] = Field(min_length=1, max_length=3)
    compiler_trajectory_ids: tuple[str, ...] = Field(min_length=1, max_length=3)
    verifier_replay_result_ids: tuple[str, ...] = Field(min_length=1, max_length=3)
    operation_closure_audit_id: str = Field(min_length=1)
    operational_admission_id: str = Field(min_length=1)
    budget_proved_before_identity_freeze: Literal[True] = True
    all_static_paths_budget_qualified: Literal[True] = True
    thinking_required_before_client_construction: Literal[True] = True
    empirical_contract_materialized: Literal[False] = False
    job_manifest_materialized: Literal[False] = False
    empirical_job_count: Literal[0] = 0
    schema_version: str = V26_BUDGET_FEASIBLE_ROLE_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> BudgetFeasibleRoleTaskPackage:
        expected = ("structured_direct",) if self.role == "capability" else PATH_STRATEGIES
        if self.path_strategy_ids != expected:
            raise ValueError("role TaskPackage static path denominator changed")
        groups = (
            self.path_audit_ids,
            self.compiler_witness_ids,
            self.compiler_trajectory_ids,
            self.verifier_replay_result_ids,
        )
        if any(len(item) != len(expected) for item in groups):
            raise ValueError("role TaskPackage path bindings are incomplete")
        if self.task_package_id != budget_feasible_role_task_package_id(self):
            raise ValueError("budget-feasible role TaskPackage identity is invalid")
        return self


class RoleFreshnessChannelAudit(FrozenModel):
    channel: str = Field(min_length=1)
    prior_count: int = Field(ge=0)
    capability_count: int = Field(ge=0)
    reachability_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    prior_set_hash: str = Field(min_length=1)
    capability_set_hash: str = Field(min_length=1)
    reachability_set_hash: str = Field(min_length=1)
    selected_set_hash: str = Field(min_length=1)
    prior_overlap_count: Literal[0] = 0
    cross_role_overlap_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_channel(self) -> RoleFreshnessChannelAudit:
        if self.channel not in FRESHNESS_CHANNELS:
            raise ValueError("role freshness contains an unknown channel")
        return self


class RoleFreshnessAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_contract_id: str = Field(min_length=1)
    selection_salt: str = Field(min_length=1)
    historical_task_record_file_count: int = Field(ge=1)
    historical_task_record_count: int = Field(ge=1)
    historical_job_manifest_file_count: int = Field(ge=1)
    historical_job_identity_count: int = Field(ge=1)
    channels: tuple[RoleFreshnessChannelAudit, ...] = Field(min_length=9, max_length=9)
    selected_capability_task_count: Literal[12] = CAPABILITY_TASK_COUNT
    selected_reachability_task_count: Literal[12] = REACHABILITY_TASK_COUNT
    selected_job_count: Literal[0] = 0
    historical_model_outcomes_used_for_selection: Literal[False] = False
    compiler_fixtures_used_for_selection: Literal[False] = False
    historical_diagnostic_candidates_used_for_selection: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_ROLE_FRESHNESS_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RoleFreshnessAudit:
        if tuple(item.channel for item in self.channels) != FRESHNESS_CHANNELS:
            raise ValueError("role freshness channels are incomplete")
        if self.audit_id != role_freshness_audit_id(self):
            raise ValueError("role freshness identity is invalid")
        return self


class RoleSourceSelectionRow(FrozenModel):
    row_id: str = Field(min_length=1)
    role: Role
    mechanism_id: TargetMechanism
    source_task_artifact_id: str = Field(min_length=1)
    source_task_hash: str = Field(min_length=1)
    evidence_count: int = Field(ge=1)
    program_node_count: int = Field(ge=1)
    rank_hash: str = Field(min_length=1)
    selection_uses_static_structure_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> RoleSourceSelectionRow:
        if self.row_id != role_source_selection_row_id(self):
            raise ValueError("role source selection row identity is invalid")
        return self


class RoleSourceCapacityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_population_ids: tuple[str, ...] = Field(min_length=4, max_length=4)
    eligible_task_counts: dict[TargetMechanism, int]
    selected_rows: tuple[RoleSourceSelectionRow, ...] = Field(min_length=24, max_length=24)
    role_mechanism_counts: dict[str, int]
    reachability_single_node_two_evidence_count: int = Field(ge=0, le=12)
    source_task_outcomes_loaded: Literal[False] = False
    source_task_outcomes_used: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_ROLE_CAPACITY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RoleSourceCapacityAudit:
        expected = {
            f"{role}:{mechanism}": TASKS_PER_ROLE_MECHANISM
            for role in ("capability", "reachability")
            for mechanism in TARGET_MECHANISMS
        }
        if self.role_mechanism_counts != expected:
            raise ValueError("role source quotas changed")
        if self.audit_id != role_source_capacity_audit_id(self):
            raise ValueError("role source capacity identity is invalid")
        return self


class DestructiveMutationResult(FrozenModel):
    mutation_id: str = Field(min_length=1)
    mutation_kind: str = Field(min_length=1)
    rejected: Literal[True] = True
    rejection_type: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_result(self) -> DestructiveMutationResult:
        if self.mutation_id != destructive_mutation_result_id(self):
            raise ValueError("destructive mutation identity is invalid")
        return self


class RoleDestructivePreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[DestructiveMutationResult, ...] = Field(min_length=10)
    thinking_mutation_count: Literal[4] = 4
    prompt_projection_mutation_count: Literal[4] = 4
    role_package_mutation_count: Literal[3] = 3
    rejected_mutation_count: int = Field(ge=11)
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = V26_ROLE_DESTRUCTIVE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RoleDestructivePreflightAudit:
        if self.rejected_mutation_count != len(self.mutation_results):
            raise ValueError("destructive rejection denominator changed")
        if self.audit_id != role_destructive_preflight_audit_id(self):
            raise ValueError("destructive preflight identity is invalid")
        return self


class BudgetFeasibleRoleRematerializationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_report_sha256: str = Field(min_length=64, max_length=64)
    predecessor_budget_adequacy_contract_id: str = Field(min_length=1)
    provider_budget_contract_id: str = Field(min_length=1)
    thinking_policy_id: str = Field(min_length=1)
    thinking_binding_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    source_capacity_audit_id: str = Field(min_length=1)
    freshness_audit_id: str = Field(min_length=1)
    destructive_preflight_audit_id: str = Field(min_length=1)
    task_count: Literal[24] = TASK_COUNT
    capability_task_count: Literal[12] = CAPABILITY_TASK_COUNT
    reachability_task_count: Literal[12] = REACHABILITY_TASK_COUNT
    role_mechanism_task_counts: dict[str, int]
    compact_prompt_contract_count: Literal[24] = TASK_COUNT
    budget_qualified_path_count: Literal[48] = TOTAL_PATH_COUNT
    capability_budget_qualified_path_count: Literal[12] = CAPABILITY_PATH_COUNT
    reachability_budget_qualified_path_count: Literal[36] = REACHABILITY_PATH_COUNT
    compiler_witness_pass_count: Literal[48] = TOTAL_PATH_COUNT
    verifier_v2_replay_pass_count: Literal[48] = TOTAL_PATH_COUNT
    completed_scoring_pass_count: Literal[48] = TOTAL_PATH_COUNT
    operation_closure_pass_count: Literal[24] = TASK_COUNT
    mechanism_necessity_pass_count: Literal[24] = TASK_COUNT
    operational_admission_pass_count: Literal[24] = TASK_COUNT
    minimum_path_upper_bound: int = Field(ge=1)
    maximum_path_upper_bound: int = Field(ge=1, le=120000)
    minimum_path_headroom: int = Field(ge=0)
    maximum_prompt_utf8_bytes: int = Field(ge=1, le=60000)
    role_task_package_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    source_artifact_files: tuple[SourceArtifactFile, ...] = Field(min_length=20)
    immutable_artifact_files: tuple[ImmutableArtifactFile, ...] = Field(min_length=20)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(min_length=20)
    source_and_artifact_replay_passed: Literal[True] = True
    formal_independent_rebuild_required: Literal[True] = True
    compiler_empirical_row_count: Literal[0] = 0
    empirical_contract_materialized: Literal[False] = False
    job_manifest_materialized: Literal[False] = False
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    historical_artifacts_mutated: Literal[False] = False
    independent_budget_calibration_minimum_job_count: Literal[32] = 32
    independent_budget_calibration_zero_no_call_required_at_32_jobs: Literal[True] = True
    independent_budget_calibration_executed: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal["thinking_budget_calibration_preflight_only"] = (
        "thinking_budget_calibration_preflight_only"
    )
    schema_version: str = V26_ROLE_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> BudgetFeasibleRoleRematerializationReport:
        expected = {
            f"{role}:{mechanism}": TASKS_PER_ROLE_MECHANISM
            for role in ("capability", "reachability")
            for mechanism in TARGET_MECHANISMS
        }
        if self.role_mechanism_task_counts != expected:
            raise ValueError("role report quotas changed")
        if self.role_task_package_ids != tuple(sorted(set(self.role_task_package_ids))):
            raise ValueError("role TaskPackage identities are not canonical")
        if tuple(item.relative_path for item in self.implementation_source_files) != (
            IMPLEMENTATION_SOURCE_PATHS
        ):
            raise ValueError("role implementation source manifest is incomplete")
        detail_names = tuple(item.relative_path for item in self.immutable_artifact_files)
        if detail_names != tuple(sorted(set(detail_names))):
            raise ValueError("role immutable detail files are not canonical")
        if self.report_id != budget_feasible_role_report_id(self):
            raise ValueError("budget-feasible role report identity is invalid")
        return self


def _identity(value: BaseModel, *, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}),
        prefix=prefix,
    )


def budget_qualified_path_audit_id(value: BudgetQualifiedPathAudit) -> str:
    return _identity(
        value,
        field="audit_id",
        prefix="finance_v26_budget_qualified_path_audit:",
    )


def compact_prompt_contract_id(value: CompactPromptContract) -> str:
    return _identity(
        value,
        field="contract_id",
        prefix="finance_v26_compact_prompt_contract:",
    )


def budget_feasible_role_task_package_id(value: BudgetFeasibleRoleTaskPackage) -> str:
    return _identity(
        value,
        field="task_package_id",
        prefix="finance_v26_budget_feasible_role_task_package:",
    )


def role_freshness_audit_id(value: RoleFreshnessAudit) -> str:
    return _identity(
        value,
        field="audit_id",
        prefix="finance_v26_budget_feasible_role_freshness:",
    )


def role_source_selection_row_id(value: RoleSourceSelectionRow) -> str:
    return _identity(
        value,
        field="row_id",
        prefix="finance_v26_budget_feasible_source_selection:",
    )


def role_source_capacity_audit_id(value: RoleSourceCapacityAudit) -> str:
    return _identity(
        value,
        field="audit_id",
        prefix="finance_v26_budget_feasible_role_capacity:",
    )


def destructive_mutation_result_id(value: DestructiveMutationResult) -> str:
    return _identity(
        value,
        field="mutation_id",
        prefix="finance_v26_role_destructive_mutation:",
    )


def role_destructive_preflight_audit_id(value: RoleDestructivePreflightAudit) -> str:
    return _identity(
        value,
        field="audit_id",
        prefix="finance_v26_role_destructive_preflight:",
    )


def budget_feasible_role_report_id(value: BudgetFeasibleRoleRematerializationReport) -> str:
    return _identity(
        value,
        field="report_id",
        prefix="finance_v26_budget_feasible_role_rematerialization_report:",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise ValueError(f"immutable v26.90 artifact exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_models(path: Path, values: Sequence[BaseModel], identity: str) -> None:
    rows = sorted(
        (item.model_dump(mode="json") for item in values),
        key=lambda item: str(item[identity]),
    )
    _write_json(path, rows)


def _artifact_file(path: Path, output_dir: Path, count: int) -> ImmutableArtifactFile:
    return ImmutableArtifactFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        record_count=count,
    )


def _source_file(path: Path, package_root: Path) -> SourceArtifactFile:
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        count = len(payload) if isinstance(payload, list) else 1
    else:
        count = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line)
    return SourceArtifactFile(
        relative_path=str(path.resolve().relative_to(package_root.resolve())),
        sha256=_sha256(path),
        record_count=count,
    )


def _implementation_source_files(package_root: Path) -> tuple[ImplementationSourceFile, ...]:
    return tuple(
        ImplementationSourceFile(
            relative_path=relative,
            sha256=_sha256(package_root / relative),
        )
        for relative in IMPLEMENTATION_SOURCE_PATHS
    )


def _recursive_values(value: Any, keys: set[str]) -> set[str]:
    output: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) in keys and isinstance(item, str):
                output.add(item)
            output.update(_recursive_values(item, keys))
    elif isinstance(value, (list, tuple)):
        for item in value:
            output.update(_recursive_values(item, keys))
    return output


def _record_values(
    records: Sequence[OperationalTaskRecord | RematerializedExecutableTaskRecord],
) -> dict[str, set[str]]:
    return {
        "source_task_artifact_id": {
            value for record in records for value in record.source_task_artifact_ids
        },
        "source_task_semantic_signature": set(),
        "source_task_hash": set(),
        "evidence_id": {
            item.evidence_id for record in records for item in record.public_corpus.evidence
        },
        "evidence_version_id": {
            item.evidence_version_id for record in records for item in record.public_corpus.evidence
        },
        "source_record_id": {
            item.provenance.source_record_id
            for record in records
            for item in record.public_corpus.evidence
        },
        "semantic_source_id": {
            record.task_package.semantic_source.semantic_source_id for record in records
        },
        "task_package_id": {record.task_package.package_id for record in records},
        "job_id": set(),
    }


def _merge_channel_values(*groups: Mapping[str, set[str]]) -> dict[str, set[str]]:
    return {
        channel: set().union(*(group.get(channel, set()) for group in groups))
        for channel in FRESHNESS_CHANNELS
    }


def _load_historical_records(
    package_root: Path,
) -> tuple[
    tuple[OperationalTaskRecord | RematerializedExecutableTaskRecord, ...],
    tuple[Path, ...],
]:
    records: list[OperationalTaskRecord | RematerializedExecutableTaskRecord] = []
    paths = tuple(package_root / relative for relative in HISTORICAL_TASK_RECORD_PATHS)
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"historical task record file is not a row list: {path}")
        model: type[OperationalTaskRecord] | type[RematerializedExecutableTaskRecord]
        model = (
            RematerializedExecutableTaskRecord
            if path.name == "rematerialized_task_records.json"
            else OperationalTaskRecord
        )
        records.extend(model.model_validate(item) for item in payload)
    return tuple(records), paths


def _load_historical_manifest_values(
    package_root: Path,
) -> tuple[set[str], set[str], tuple[Path, ...]]:
    paths = tuple(package_root / relative for relative in HISTORICAL_JOB_MANIFEST_PATHS)
    job_ids: set[str] = set()
    task_package_ids: set[str] = set()
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        job_ids.update(_recursive_values(payload, {"job_id", "recovery_job_id", "control_job_id"}))
        task_package_ids.update(_recursive_values(payload, {"task_package_id"}))
    if not job_ids:
        raise ValueError("historical Job manifest replay produced an empty denominator")
    return job_ids, task_package_ids, paths


def _rank_hash(
    task: CapabilitySensitiveTaskArtifact,
    *,
    role: Role,
    mechanism: TargetMechanism,
    selection_salt: str,
) -> str:
    return canonical_hash(
        {
            "selection_salt": selection_salt,
            "role": role,
            "mechanism": mechanism,
            "source_task_artifact_id": task.artifact_id,
        },
        prefix="finance_v26_budget_feasible_source_rank:",
    )


def _complexity(task: CapabilitySensitiveTaskArtifact) -> tuple[int, int]:
    return len(task.task.oracle.task_program.nodes), len(task.public_corpus.evidence)


def _select_role_source_tasks(
    sources: Sequence[CapabilitySensitiveFrontierPopulation],
    *,
    excluded: Mapping[str, set[str]],
    selection_salt: str,
) -> tuple[
    dict[tuple[Role, TargetMechanism], tuple[CapabilitySensitiveTaskArtifact, ...]],
    RoleSourceCapacityAudit,
]:
    all_tasks = tuple(task for source in sources for task in source.tasks)
    selected: dict[tuple[Role, TargetMechanism], tuple[CapabilitySensitiveTaskArtifact, ...]] = {}
    selected_values: dict[str, set[str]] = {channel: set() for channel in FRESHNESS_CHANNELS[:6]}
    eligible_counts: dict[TargetMechanism, int] = {}
    rows: list[RoleSourceSelectionRow] = []
    family_by_mechanism = {
        **MECHANISM_SOURCE_FAMILY,
        "semantic_reconciliation": "finance.definition_reconciliation",
    }
    for mechanism in TARGET_MECHANISMS:
        family = family_by_mechanism[mechanism]
        eligible = []
        for task in all_tasks:
            if task.family != family:
                continue
            values = _source_task_values((task,))
            try:
                _atomic_leaf_node(task)
            except ValueError:
                continue
            if any(values[channel] & excluded[channel] for channel in FRESHNESS_CHANNELS[:6]):
                continue
            eligible.append(task)
        eligible_counts[mechanism] = len(eligible)
        for role in ("reachability", "capability"):
            candidates = list(eligible)
            candidates.sort(
                key=lambda task: (
                    *_complexity(task),
                    _rank_hash(
                        task,
                        role=cast(Role, role),
                        mechanism=mechanism,
                        selection_salt=selection_salt,
                    ),
                )
            )
            chosen: list[CapabilitySensitiveTaskArtifact] = []
            for task in candidates:
                task_values = _source_task_values((task,))
                if any(
                    task_values[channel] & selected_values[channel]
                    for channel in FRESHNESS_CHANNELS[:6]
                ):
                    continue
                chosen.append(task)
                for channel in FRESHNESS_CHANNELS[:6]:
                    selected_values[channel].update(task_values[channel])
                if len(chosen) == TASKS_PER_ROLE_MECHANISM:
                    break
            if len(chosen) != TASKS_PER_ROLE_MECHANISM:
                raise ValueError(
                    f"fresh source capacity cannot supply {role} tasks for {mechanism}"
                )
            key = (cast(Role, role), mechanism)
            selected[key] = tuple(chosen)
            for task in chosen:
                row_values = {
                    "role": role,
                    "mechanism_id": mechanism,
                    "source_task_artifact_id": task.artifact_id,
                    "source_task_hash": task.task.task_hash,
                    "evidence_count": len(task.public_corpus.evidence),
                    "program_node_count": len(task.task.oracle.task_program.nodes),
                    "rank_hash": _rank_hash(
                        task,
                        role=cast(Role, role),
                        mechanism=mechanism,
                        selection_salt=selection_salt,
                    ),
                }
                provisional = RoleSourceSelectionRow.model_construct(
                    row_id="pending",
                    **row_values,
                )
                rows.append(
                    RoleSourceSelectionRow(
                        row_id=role_source_selection_row_id(provisional),
                        **row_values,
                    )
                )
    ordered_rows = tuple(sorted(rows, key=lambda item: item.row_id))
    role_counts = dict(
        sorted(Counter(f"{item.role}:{item.mechanism_id}" for item in ordered_rows).items())
    )
    capacity_values = {
        "source_population_ids": tuple(sorted(source.population_id for source in sources)),
        "eligible_task_counts": eligible_counts,
        "selected_rows": ordered_rows,
        "role_mechanism_counts": role_counts,
        "reachability_single_node_two_evidence_count": sum(
            item.role == "reachability"
            and item.program_node_count == 1
            and item.evidence_count == 2
            for item in ordered_rows
        ),
    }
    provisional_capacity = RoleSourceCapacityAudit.model_construct(
        audit_id="pending",
        **capacity_values,
    )
    capacity = RoleSourceCapacityAudit(
        audit_id=role_source_capacity_audit_id(provisional_capacity),
        **capacity_values,
    )
    return selected, capacity


def _intended_use(role: Role) -> IntendedTaskUse:
    return "capability_measurement" if role == "capability" else "vtdo_multistate_candidate"


@dataclass(frozen=True)
class _AtomicSourceTask:
    evidence_bundle: EvidenceBundle
    public_corpus: EvidenceCorpus
    proof_graph: ProofGraph
    program: TaskProgram
    projected_expected_output: dict[str, Any]
    answer_schema: dict[str, Any]
    retrieval_scope: dict[str, Any]
    instruction: str
    target_evidence_ids: tuple[str, ...]


def _atomic_leaf_node(task: CapabilitySensitiveTaskArtifact) -> Any:
    candidates = []
    for node in task.task.oracle.task_program.nodes:
        evidence_refs = tuple(
            ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.EVIDENCE
        )
        if (
            not node.dependencies
            and len(evidence_refs) == 2
            and len(evidence_refs) == len(node.input_refs)
        ):
            candidates.append(node)
    if not candidates:
        raise ValueError("source task lacks an independent two-Evidence leaf Operation")
    return sorted(candidates, key=lambda item: item.node_id)[0]


def _atomic_source_task(task: CapabilitySensitiveTaskArtifact) -> _AtomicSourceTask:
    node = _atomic_leaf_node(task)
    target_ids = tuple(ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.EVIDENCE)
    source_evidence = {item.evidence_id: item for item in task.public_corpus.evidence}
    if any(item not in source_evidence for item in target_ids):
        raise ValueError("atomic source Program refers outside its Public Corpus")
    evidence = tuple(
        sorted((source_evidence[item] for item in target_ids), key=lambda item: item.evidence_id)
    )
    graph_build_ids = {
        value
        for item in evidence
        for key, value in item.provenance.build_ids.items()
        if key == "kg"
    }
    graph_build_id = next(iter(graph_build_ids)) if len(graph_build_ids) == 1 else None
    identity_payload = {
        "source_task_artifact_id": task.artifact_id,
        "source_node_id": node.node_id,
        "evidence_versions": tuple(item.evidence_version_id for item in evidence),
    }
    bundle = EvidenceBundle(
        bundle_id=canonical_hash(
            identity_payload,
            prefix="finance_v26_budget_feasible_atomic_bundle:",
        ),
        evidence=evidence,
        purpose="v26.90 budget-feasible role task atomic dependency rematerialization",
        graph_build_id=graph_build_id,
        metadata={
            "source_task_artifact_id": task.artifact_id,
            "source_node_id": node.node_id,
            "construction_version": V26_BUDGET_FEASIBLE_ROLE_VERSION,
        },
    )
    corpus = EvidenceCorpus(
        corpus_id=canonical_hash(
            identity_payload,
            prefix="finance_v26_budget_feasible_atomic_corpus:",
        ),
        evidence=evidence,
        build_id=graph_build_id,
    )
    graph = ProofGraphBuilder().build(bundle)
    program = make_program((node,), node.node_id)
    registry = default_registry()
    execution = TaskProgramExecutor(registry).execute(
        program,
        {item.evidence_id: item for item in evidence},
    )
    verification = TaskProgramOracleVerifier(registry).verify(
        program,
        {item.evidence_id: item for item in evidence},
        execution.node_outputs,
    )
    if not verification.passed:
        raise ValueError("atomic source Program failed independent replay")
    output = dict(execution.final_output)
    required_fields = tuple(sorted(output))
    if not required_fields:
        raise ValueError("atomic source Program produced an empty output")
    answer_schema = complete_answer_schema(
        {
            "type": "capability_sensitive_numeric",
            "required_fields": required_fields,
            "allow_claims": False,
            "additional_result_properties": False,
        }
    )
    aliases = tuple(
        sorted(
            {
                *(item.subject.name for item in evidence),
                *(item.subject.subject_id for item in evidence),
                *(item.predicate for item in evidence),
            }
        )
    )
    periods = tuple(sorted(str(item.temporal_context.label) for item in evidence))
    retrieval_scope = {
        "aliases": aliases,
        "partial_constraints": {
            "period_labels": periods,
            "historical_only": True,
            "query_decomposition_rounds": 1,
        },
        "corpus_boundary": {
            "evidence_count": len(evidence),
            "source_count": len({item.source.source_id for item in evidence}),
            "build_label": graph_build_id or "mixed_frozen_source_artifacts",
        },
    }
    input_labels = ", ".join(
        f"{source_evidence[evidence_id].subject.name}."
        f"{source_evidence[evidence_id].predicate}@"
        f"{source_evidence[evidence_id].temporal_context.label}"
        for evidence_id in target_ids
    )
    instruction = (
        f"Using the two registered public Finance records [{input_labels}] in their "
        f"listed input order, apply the registered {node.operator_id} operation and return "
        f"exactly {', '.join(required_fields)}."
    )
    return _AtomicSourceTask(
        evidence_bundle=bundle,
        public_corpus=corpus,
        proof_graph=graph,
        program=program,
        projected_expected_output=output,
        answer_schema=answer_schema,
        retrieval_scope=retrieval_scope,
        instruction=instruction,
        target_evidence_ids=target_ids,
    )


def _role_draft(
    task: CapabilitySensitiveTaskArtifact,
    *,
    role: Role,
    mechanism: TargetMechanism,
) -> _TaskDraft:
    intended_use = _intended_use(role)
    atomic = _atomic_source_task(task)
    node = atomic.program.nodes[0]
    recovery_fields: tuple[str, ...] = ()
    if mechanism == "context_conditioned_action":
        alternate = "difference" if node.operator_id != "difference" else "compare"
        public_state = {
            "decision_slot_count": 1,
            "registered_actions": tuple(sorted((node.operator_id, alternate))),
            "selection_rule": "choose the operation matching the requested result schema",
        }
        private_state = {
            "expected_first_action": node.operator_id,
            "alternate_action": alternate,
            "decision_irversible": True,
        }
        instruction = (
            f"{atomic.instruction} Choose exactly one registered operation plan from the "
            "public Context before execution; the first plan decision is irreversible."
        )
    elif mechanism == "failure_recovery":
        recovery_fields = ("public_filter",)
        public_state = {
            "failure_code": "typed_selector_requires_refinement",
            "retry_policy": "revise_at_least_one_public_selector_field",
            "mismatch_fields": recovery_fields,
            "identical_retry_invalid": True,
        }
        private_state = {
            "forced_failure_count": 1,
            "identical_retry_invalid": True,
        }
        instruction = (
            f"{atomic.instruction} The first exact selector attempt returns a typed "
            "recoverable failure. Use only its action-neutral error category and unresolved "
            "public semantics, revise at least one public selector field, and continue."
        )
    elif mechanism == "state_dependent_stopping":
        public_state = {
            "completion_requirements": ("final_operation_completed",),
            "early_stop_invalid": True,
            "postcompletion_tool_call_invalid": True,
        }
        private_state = {
            "verification_required_before_stop": True,
            "maximum_postcompletion_calls": 0,
        }
        instruction = (
            f"{atomic.instruction} Emit the answer only after the public completion check "
            "and exact post-terminal verification succeed, then issue no further tool call."
        )
    else:
        evidence_by_id = {item.evidence_id: item for item in atomic.public_corpus.evidence}
        targets = tuple(
            sorted(
                (evidence_by_id[evidence_id] for evidence_id in atomic.target_evidence_ids),
                key=lambda item: str(item.temporal_context.label),
            )
        )
        if len({str(item.temporal_context.label) for item in targets}) != 2:
            raise ValueError("atomic Reconciliation requires two distinct public periods")
        public_state = {
            "target_definitions": tuple(
                {
                    "period": item.temporal_context.label,
                    "predicate": item.predicate,
                    "definition_id": item.definition.definition_id,
                    "unit": getattr(item.payload, "unit", None),
                    "currency": getattr(item.payload, "currency", None),
                    "time_basis": item.temporal_context.basis,
                    "frequency": item.temporal_context.frequency,
                }
                for item in targets
            ),
            "downstream_reference_required": True,
            "raw_evidence_bypass_invalid": True,
        }
        private_state = {
            "target_evidence_ids": atomic.target_evidence_ids,
            "raw_evidence_bypass_invalid": True,
        }
        instruction = (
            f"{atomic.instruction} Normalize each required public record against its "
            "registered metric, definition, unit, currency, period basis, and frequency. "
            "The terminal calculator must consume emitted normalization references rather "
            "than raw Evidence."
        )
    return _TaskDraft(
        mechanism_id=mechanism,
        intended_use=intended_use,
        source_task_artifact_ids=(task.artifact_id,),
        instruction=instruction,
        evidence_bundle=atomic.evidence_bundle,
        public_corpus=atomic.public_corpus,
        proof_graph=atomic.proof_graph,
        program=atomic.program,
        projected_expected_output=atomic.projected_expected_output,
        answer_projection={},
        answer_schema=atomic.answer_schema,
        retrieval_scope=atomic.retrieval_scope,
        requirements=(
            TaskRequirement.RETRIEVE_EVIDENCE,
            TaskRequirement.SELECT_EVIDENCE,
            TaskRequirement.CALCULATE,
            TaskRequirement.CITE_SOURCE,
            TaskRequirement.VERIFY_RESULT,
        ),
        mechanism_public_state=public_state,
        mechanism_private_state=private_state,
        target_program_evidence_ids=atomic.target_evidence_ids,
        recovery_mismatch_fields=recovery_fields,
    )


def _make_compact_prompt_contract(
    *,
    role: Role,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
) -> CompactPromptContract:
    context = compact_public_task_context(
        record.task_package.task.public,
        environment,
        mechanism_public_state=record.mechanism_public_state,
    )
    values = {
        "operational_task_package_id": record.task_package.package_id,
        "environment_manifest_id": environment.manifest_id,
        "mechanism_id": record.mechanism_id,
        "role": role,
        "public_context": context,
        "public_context_hash": canonical_hash(
            context,
            prefix="finance_v26_compact_public_context:",
        ),
    }
    provisional = CompactPromptContract.model_construct(contract_id="pending", **values)
    return CompactPromptContract(
        contract_id=compact_prompt_contract_id(provisional),
        **values,
    )


def _make_budget_qualified_path(
    *,
    role: Role,
    record: OperationalTaskRecord,
    prompt_contract: CompactPromptContract,
    predecessor_contract: BudgetAdequacyProtocolContract,
    provider_contract: ProviderTokenBudgetContract,
    thinking_binding: ProspectiveThinkingModelBinding,
    strategy: PathStrategy,
    witness: BoundPublicExecutableWitness,
    trajectory_id: str,
    observations: tuple[AgentToolObservation, ...],
) -> BudgetQualifiedPathAudit:
    path_condition = strategy if role == "reachability" else None
    prompts = render_compact_witness_prompts(
        prompt_contract.public_context,
        record.task_package.task.public,
        observations,
        public_path_condition=path_condition,
    )
    cumulative = 0
    request_bounds = []
    for index, prompt in enumerate(prompts):
        request_kind, repaired_kind = _provider_request_kind(prompt)
        if request_kind in {"unknown", "contract_repair"} or repaired_kind is not None:
            raise ValueError("compact static path produced an unregistered request kind")
        prompt_bytes = len(prompt.encode("utf-8"))
        prompt_upper = prompt_bytes + provider_contract.provider_chat_envelope_token_upper_bound
        request_upper = prompt_upper + provider_contract.maximum_output_tokens
        cumulative += request_upper
        repair_reserve, final_reserve = _required_reserves(
            request_kind,
            None,
            provider_contract,
        )
        projected = cumulative + repair_reserve + final_reserve
        request_bounds.append(
            StaticRequestUpperBound(
                request_index=index,
                request_kind=request_kind,
                prompt_sha256=_sha256_text(prompt),
                prompt_utf8_bytes=prompt_bytes,
                prompt_token_upper_bound=prompt_upper,
                completion_token_upper_bound=provider_contract.maximum_output_tokens,
                request_token_upper_bound=request_upper,
                cumulative_request_upper_bound=cumulative,
                contract_repair_reserve_tokens=repair_reserve,
                final_answer_reserve_tokens=final_reserve,
                required_reserve_tokens=repair_reserve + final_reserve,
                projected_path_upper_bound=projected,
                prompt_ceiling_passed=(prompt_bytes <= provider_contract.maximum_prompt_utf8_bytes),
                rollout_ceiling_passed=(projected <= provider_contract.maximum_total_tokens),
            )
        )
    bounds = tuple(request_bounds)
    maximum_path = max(item.projected_path_upper_bound for item in bounds)
    qualified = all(item.prompt_ceiling_passed and item.rollout_ceiling_passed for item in bounds)
    if not qualified:
        raise ValueError(
            "unqualified compact static path before TaskPackage identity freeze: "
            f"{role}/{record.mechanism_id}/{strategy}; requests={len(bounds)}; "
            f"maximum_prompt_bytes={max(item.prompt_utf8_bytes for item in bounds)}; "
            f"maximum_path_bound={maximum_path}"
        )
    values = {
        "operational_task_package_id": record.task_package.package_id,
        "compact_prompt_contract_id": prompt_contract.contract_id,
        "budget_adequacy_contract_id": predecessor_contract.contract_id,
        "provider_budget_contract_id": provider_contract.contract_id,
        "thinking_binding_id": thinking_binding.binding_id,
        "role": role,
        "mechanism_id": record.mechanism_id,
        "path_strategy_id": strategy,
        "public_path_condition": path_condition,
        "compiler_witness_id": witness.witness_id,
        "compiler_trajectory_id": trajectory_id,
        "request_bounds": bounds,
        "request_count": len(bounds),
        "maximum_prompt_utf8_bytes": max(item.prompt_utf8_bytes for item in bounds),
        "maximum_cumulative_path_upper_bound": maximum_path,
        "minimum_headroom_tokens": (provider_contract.maximum_total_tokens - maximum_path),
        "full_path_budget_qualified": qualified,
    }
    provisional = BudgetQualifiedPathAudit.model_construct(audit_id="pending", **values)
    return BudgetQualifiedPathAudit(
        audit_id=budget_qualified_path_audit_id(provisional),
        **values,
    )


def _selected_role_values(
    *,
    role: Role,
    selected_tasks: Sequence[CapabilitySensitiveTaskArtifact],
    records: Sequence[OperationalTaskRecord],
    packages: Sequence[BudgetFeasibleRoleTaskPackage],
) -> dict[str, set[str]]:
    source = _source_task_values(selected_tasks)
    role_records = [record for record in records if record.intended_use == _intended_use(role)]
    record_values = _record_values(role_records)
    return {
        **source,
        "evidence_id": record_values["evidence_id"],
        "evidence_version_id": record_values["evidence_version_id"],
        "source_record_id": record_values["source_record_id"],
        "semantic_source_id": record_values["semantic_source_id"],
        "task_package_id": {item.task_package_id for item in packages if item.role == role},
        "job_id": set(),
    }


def _make_freshness_audit(
    *,
    predecessor_contract: BudgetAdequacyProtocolContract,
    selection_salt: str,
    historical_records: Sequence[OperationalTaskRecord | RematerializedExecutableTaskRecord],
    historical_record_paths: Sequence[Path],
    historical_job_ids: set[str],
    historical_manifest_paths: Sequence[Path],
    prior_values: Mapping[str, set[str]],
    selected: Mapping[
        tuple[Role, TargetMechanism],
        tuple[CapabilitySensitiveTaskArtifact, ...],
    ],
    records: Sequence[OperationalTaskRecord],
    packages: Sequence[BudgetFeasibleRoleTaskPackage],
) -> RoleFreshnessAudit:
    capability_tasks = tuple(
        task for mechanism in TARGET_MECHANISMS for task in selected[("capability", mechanism)]
    )
    reachability_tasks = tuple(
        task for mechanism in TARGET_MECHANISMS for task in selected[("reachability", mechanism)]
    )
    capability = _selected_role_values(
        role="capability",
        selected_tasks=capability_tasks,
        records=records,
        packages=packages,
    )
    reachability = _selected_role_values(
        role="reachability",
        selected_tasks=reachability_tasks,
        records=records,
        packages=packages,
    )
    channels = []
    for channel in FRESHNESS_CHANNELS:
        prior = set(prior_values[channel])
        left = set(capability[channel])
        right = set(reachability[channel])
        combined = left | right
        if prior & combined:
            raise ValueError(f"selected role channel overlaps history: {channel}")
        if left & right:
            raise ValueError(f"Capability and Reachability overlap: {channel}")
        channels.append(
            RoleFreshnessChannelAudit(
                channel=channel,
                prior_count=len(prior),
                capability_count=len(left),
                reachability_count=len(right),
                selected_count=len(combined),
                prior_set_hash=canonical_hash(
                    tuple(sorted(prior)),
                    prefix=f"finance_v26_role_prior_{channel}:",
                ),
                capability_set_hash=canonical_hash(
                    tuple(sorted(left)),
                    prefix=f"finance_v26_role_capability_{channel}:",
                ),
                reachability_set_hash=canonical_hash(
                    tuple(sorted(right)),
                    prefix=f"finance_v26_role_reachability_{channel}:",
                ),
                selected_set_hash=canonical_hash(
                    tuple(sorted(combined)),
                    prefix=f"finance_v26_role_selected_{channel}:",
                ),
            )
        )
    values = {
        "predecessor_contract_id": predecessor_contract.contract_id,
        "selection_salt": selection_salt,
        "historical_task_record_file_count": len(historical_record_paths),
        "historical_task_record_count": len(historical_records),
        "historical_job_manifest_file_count": len(historical_manifest_paths),
        "historical_job_identity_count": len(historical_job_ids),
        "channels": tuple(channels),
    }
    provisional = RoleFreshnessAudit.model_construct(audit_id="pending", **values)
    return RoleFreshnessAudit(
        audit_id=role_freshness_audit_id(provisional),
        **values,
    )


def _load_predecessor(
    package_root: Path,
) -> tuple[
    BudgetAdequacyContractPreflightReport,
    BudgetAdequacyProtocolContract,
    ProviderTokenBudgetContract,
    tuple[Path, ...],
]:
    predecessor_dir = package_root / V26_89_DIR
    report_path = predecessor_dir / "report.json"
    report = BudgetAdequacyContractPreflightReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    replayed_paths = [report_path]
    for descriptor in (
        *report.immutable_detail_files,
        *report.immutable_raw_control_files,
    ):
        path = predecessor_dir / descriptor.relative_path
        if _sha256(path) != descriptor.sha256 or path.stat().st_size != descriptor.byte_count:
            raise ValueError(f"v26.89 predecessor detail changed: {path}")
        replayed_paths.append(path)
    contract_path = predecessor_dir / "budget_adequacy_contract.json"
    contract = BudgetAdequacyProtocolContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    provider_path = package_root / V26_82_PROVIDER_BUDGET_PATH
    provider_contract = ProviderTokenBudgetContract.model_validate_json(
        provider_path.read_text(encoding="utf-8")
    )
    if (
        report.budget_adequacy_contract_id != contract.contract_id
        or contract.provider_budget_contract_id != provider_contract.contract_id
    ):
        raise ValueError("v26.89 predecessor budget lineage changed")
    if tuple(contract.freshness_channels) != FRESHNESS_CHANNELS:
        raise ValueError("v26.89 freshness Contract changed")
    if (
        contract.capability_minimum_budgeted_paths_per_task != 1
        or contract.reachability_minimum_budgeted_paths_per_task != 3
        or contract.static_witness_accounting_rule
        != "sum_request_upper_bounds_plus_current_required_reserve"
    ):
        raise ValueError("v26.89 role path Contract changed")
    if (
        provider_contract.maximum_total_tokens != 120000
        or provider_contract.maximum_prompt_utf8_bytes != 60000
        or provider_contract.maximum_output_tokens != 4096
        or provider_contract.provider_chat_envelope_token_upper_bound != 256
        or provider_contract.contract_repair_reserve_tokens != 4096
        or provider_contract.final_answer_reserve_tokens != 4096
    ):
        raise ValueError("frozen Provider budget bounds changed")
    replayed_paths.append(provider_path)
    return report, contract, provider_contract, tuple(replayed_paths)


def _load_thinking_binding(
    package_root: Path,
) -> tuple[AgentModelConfig, ProspectiveThinkingModelBinding, Path]:
    path = package_root / THINKING_PROFILE_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    model_config = AgentModelConfig.model_validate(payload["model"])
    require_prospective_thinking(model_config)
    binding = bind_prospective_thinking(model_config)
    if model_config.max_output_tokens != 4096:
        raise ValueError("thinking profile changed the frozen completion bound")
    return model_config, binding, path


def _mutation_result(kind: str, callback: Any) -> DestructiveMutationResult:
    try:
        callback()
    except (ValueError, ValidationError, TypeError, KeyError) as exc:
        values = {
            "mutation_kind": kind,
            "rejection_type": type(exc).__name__,
        }
        provisional = DestructiveMutationResult.model_construct(
            mutation_id="pending",
            **values,
        )
        return DestructiveMutationResult(
            mutation_id=destructive_mutation_result_id(provisional),
            **values,
        )
    raise ValueError(f"destructive mutation did not fail closed: {kind}")


def _make_destructive_audit(
    *,
    model_config: AgentModelConfig,
    prompt_contract: CompactPromptContract,
    packages: Sequence[BudgetFeasibleRoleTaskPackage],
) -> RoleDestructivePreflightAudit:
    results = []

    def require_mutated_thinking(overrides: dict[str, Any]) -> None:
        payload = model_config.model_dump(mode="python")
        payload["request_body_overrides"] = overrides
        require_prospective_thinking(AgentModelConfig.model_validate(payload))

    base_overrides = dict(model_config.request_body_overrides)
    missing = dict(base_overrides)
    missing.pop("thinking")
    results.append(
        _mutation_result(
            "thinking_missing",
            lambda: require_mutated_thinking(missing),
        )
    )
    disabled = dict(base_overrides)
    disabled["thinking"] = {"type": "disabled"}
    results.append(
        _mutation_result(
            "thinking_disabled",
            lambda: require_mutated_thinking(disabled),
        )
    )
    changed_case = dict(base_overrides)
    changed_case.pop("thinking")
    changed_case["Thinking"] = {"type": "enabled"}
    results.append(
        _mutation_result(
            "thinking_changed_case",
            lambda: require_mutated_thinking(changed_case),
        )
    )
    extended = dict(base_overrides)
    extended["thinking"] = {"type": "enabled", "budget": 4096}
    results.append(
        _mutation_result(
            "thinking_structurally_extended",
            lambda: require_mutated_thinking(extended),
        )
    )

    for kind, injected in (
        ("prompt_oracle_injection", {"oracle": {}}),
        ("prompt_expected_arguments_injection", {"expected_arguments": {}}),
        ("prompt_target_evidence_injection", {"target_evidence_ids": []}),
        ("prompt_action_binding_flag", {"action_binding_fields_exposed": True}),
    ):
        mutated_context = dict(prompt_contract.public_context)
        mutated_context.update(injected)
        results.append(
            _mutation_result(
                kind,
                lambda value=mutated_context: require_action_neutral_public_projection(value),
            )
        )

    reachability = next(item for item in packages if item.role == "reachability")
    missing_path = reachability.model_dump(mode="python")
    for field in (
        "path_audit_ids",
        "path_strategy_ids",
        "compiler_witness_ids",
        "compiler_trajectory_ids",
        "verifier_replay_result_ids",
    ):
        missing_path[field] = tuple(missing_path[field][:-1])
    results.append(
        _mutation_result(
            "reachability_path_ablation",
            lambda: BudgetFeasibleRoleTaskPackage.model_validate(missing_path),
        )
    )
    role_swap = reachability.model_dump(mode="python")
    role_swap["role"] = "capability"
    results.append(
        _mutation_result(
            "reachability_role_swap",
            lambda: BudgetFeasibleRoleTaskPackage.model_validate(role_swap),
        )
    )
    stale_identity = reachability.model_dump(mode="python")
    stale_identity["task_package_id"] = "finance_v26_budget_feasible_role_task_package:stale"
    results.append(
        _mutation_result(
            "role_task_package_stale_identity",
            lambda: BudgetFeasibleRoleTaskPackage.model_validate(stale_identity),
        )
    )

    ordered = tuple(sorted(results, key=lambda item: item.mutation_id))
    values = {
        "mutation_results": ordered,
        "rejected_mutation_count": len(ordered),
    }
    provisional = RoleDestructivePreflightAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return RoleDestructivePreflightAudit(
        audit_id=role_destructive_preflight_audit_id(provisional),
        **values,
    )


def _model_source_paths(
    *,
    package_root: Path,
    predecessor_paths: Sequence[Path],
    historical_record_paths: Sequence[Path],
    historical_manifest_paths: Sequence[Path],
    thinking_profile_path: Path,
) -> tuple[Path, ...]:
    fixed = (
        *(package_root / item for item in SOURCE_POPULATION_PATHS),
        package_root / DEVELOPMENT_POPULATION_PATH,
        *(package_root / item for item in ZERO_API_SOURCE_RECEIPT_PATHS),
        package_root / "artifacts/vtdo_experiment/finance_v26_29_exposure_grounded_source_20260817/"
        "exposure_clean_receipt.json",
        package_root / VERIFIER_QUALIFICATION_DIR / "report.json",
        package_root / VERIFIER_QUALIFICATION_DIR / "replay_contract.json",
        thinking_profile_path,
    )
    return tuple(
        sorted(
            {
                *(path.resolve() for path in fixed),
                *(path.resolve() for path in predecessor_paths),
                *(path.resolve() for path in historical_record_paths),
                *(path.resolve() for path in historical_manifest_paths),
            },
            key=str,
        )
    )


def build_budget_feasible_role_task_rematerialization(
    *,
    run_id: str,
    selection_salt: str,
    output_dir: Path,
    package_root: Path,
) -> BudgetFeasibleRoleRematerializationReport:
    predecessor_report, predecessor_contract, provider_contract, predecessor_paths = (
        _load_predecessor(package_root)
    )
    model_config, thinking_binding, thinking_profile_path = _load_thinking_binding(package_root)

    development_path = package_root / DEVELOPMENT_POPULATION_PATH
    development = V26FreshTaskPopulation.model_validate_json(
        development_path.read_text(encoding="utf-8")
    )
    if development.phase != "development":
        raise ValueError("v26.90 predecessor source is not the frozen Development role")
    development_tasks = load_v26_selected_source_tasks(development)
    sources = tuple(
        _load_population(package_root / relative) for relative in SOURCE_POPULATION_PATHS
    )
    if len({item.population_id for item in sources}) != len(sources):
        raise ValueError("v26.90 requires four distinct immutable source Populations")
    for relative in ZERO_API_SOURCE_RECEIPT_PATHS:
        payload = json.loads((package_root / relative).read_text(encoding="utf-8"))
        if payload.get("model_api_calls") != 0 or payload.get("gpu_jobs") != 0:
            raise ValueError("fresh source Population lacks a zero-API receipt")

    historical_records, historical_record_paths = _load_historical_records(package_root)
    historical_job_ids, manifest_task_package_ids, historical_manifest_paths = (
        _load_historical_manifest_values(package_root)
    )
    all_source_tasks = tuple(task for source in sources for task in source.tasks)
    source_by_id = {item.artifact_id: item for item in all_source_tasks}
    historical_source_ids = {
        source_id for record in historical_records for source_id in record.source_task_artifact_ids
    }
    historical_source_tasks = tuple(
        source_by_id[source_id]
        for source_id in sorted(historical_source_ids)
        if source_id in source_by_id
    )
    source_prior = _source_task_values((*development_tasks, *historical_source_tasks))
    source_prior_extended = {
        **source_prior,
        "semantic_source_id": set(),
        "task_package_id": set(),
        "job_id": set(),
    }
    record_prior = _record_values(historical_records)
    prior_values = _merge_channel_values(source_prior_extended, record_prior)
    prior_values["job_id"].update(historical_job_ids)
    prior_values["task_package_id"].update(manifest_task_package_ids)

    selected, capacity_audit = _select_role_source_tasks(
        sources,
        excluded=prior_values,
        selection_salt=selection_salt,
    )
    qualification, replay_contract = _load_and_replay_verifier_qualification(
        package_root / VERIFIER_QUALIFICATION_DIR,
        package_root,
    )
    qualification_path = package_root / VERIFIER_QUALIFICATION_DIR / "report.json"
    qualification_sha256 = _sha256(qualification_path)

    records: list[OperationalTaskRecord] = []
    environments: list[AgentToolEnvironmentManifest] = []
    replay_bindings: list[VerifierV2TaskReplayBinding] = []
    witnesses: list[BoundPublicExecutableWitness] = []
    observations: list[AgentToolObservation] = []
    necessities: list[MechanismNecessityArtifact] = []
    counterfactuals: list[MechanismCounterfactualReplayRecord] = []
    catalogs: list[StaticModelAuthorityPathCatalog] = []
    closures: list[OperationClosureAudit] = []
    admissions: list[OperationalTaskAdmission] = []
    task_audits: list[AuthorityPreservingTaskAudit] = []
    prompt_contracts: list[CompactPromptContract] = []
    path_audits: list[BudgetQualifiedPathAudit] = []
    role_packages: list[BudgetFeasibleRoleTaskPackage] = []
    compiler_trajectories: list[BaseModel] = []
    compiler_scores: list[CompletedTrajectoryScore] = []
    replay_results: list[BaseModel] = []

    for role in ("capability", "reachability"):
        typed_role = cast(Role, role)
        for mechanism in TARGET_MECHANISMS:
            for source_task in selected[(typed_role, mechanism)]:
                draft = _role_draft(
                    source_task,
                    role=typed_role,
                    mechanism=mechanism,
                )
                source_record, source_environment = _upgrade_task(draft)
                authority_environment = _harden_environment(source_environment)
                environment = _verifier_bound_environment(authority_environment)
                authority_record = _harden_record(source_record, environment)
                replay_binding = _task_replay_binding(
                    authority_record,
                    environment,
                    qualification,
                    qualification_sha256,
                    replay_contract,
                )
                record = _bind_verifier_v2(authority_record, replay_binding)
                strategies: tuple[PathStrategy, ...] = (
                    ("structured_direct",)
                    if role == "capability"
                    else cast(tuple[PathStrategy, ...], PATH_STRATEGIES)
                )
                task_witnesses = []
                task_histories = []
                for strategy in strategies:
                    witness, history = compile_operational_witness(
                        record,
                        environment,
                        strategy=strategy,
                    )
                    task_witnesses.append(witness)
                    task_histories.append(history)
                necessity, task_counterfactuals, catalog = mechanism_necessity_and_catalog(
                    record, task_witnesses
                )
                closure = build_operation_closure_audit(
                    record,
                    task_witnesses,
                    task_histories,
                    necessity,
                    catalog,
                )
                admission = build_operational_admission(
                    record,
                    task_witnesses[0],
                    necessity,
                    catalog,
                    closure,
                )
                task_audit = _task_audit(
                    record,
                    environment,
                    task_witnesses[0],
                    task_histories[0],
                    necessity,
                    closure,
                )
                prompt_contract = _make_compact_prompt_contract(
                    role=typed_role,
                    record=record,
                    environment=environment,
                )

                task_replays = []
                task_trajectories = []
                task_paths = []
                for strategy, witness, history in zip(
                    strategies,
                    task_witnesses,
                    task_histories,
                    strict=True,
                ):
                    replay = replay_authority_preserving_observations(
                        replay_contract,
                        record,
                        environment,
                        history,
                    )
                    if not replay.passed:
                        raise ValueError("v26.90 Compiler path failed Verifier v2 Replay")
                    trajectory = compiler_witness_trajectory(
                        record=record,
                        environment=environment,
                        witness=witness,
                        observations=history,
                    )
                    score = score_completed_trajectory(
                        trajectory=trajectory,
                        source_kind="compiler_fixture",
                        replay_result_id=replay.replay_id,
                        replay_passed=replay.passed,
                        non_replay_checks={
                            "action_neutral_repair": (
                                task_audit.repair_prompt_audit.status == "passed"
                            ),
                            "answer_projection": witness.answer_projection_complete,
                            "citation": witness.citation_complete,
                            "evidence_support": witness.evidence_support_complete,
                            "mechanism": witness.mechanism_complete,
                            "no_postcompletion_violation": (witness.no_postcompletion_violation),
                            "operation_lineage": witness.operation_lineage_complete,
                            "stop_readiness": task_audit.runtime_witness_stop_ready,
                            "terminal_target": (task_audit.exact_terminal_reference_accepted),
                            "verification": witness.verification_complete,
                        },
                        independent_valid=witness.full_validity_passed,
                        resource_budget_audit_id=provider_contract.contract_id,
                        resource_budget_status="not_applicable_no_provider_calls",
                    )
                    if (
                        score.core_terminal != "valid_trajectory"
                        or not score.instrument_admitted
                        or score.trace_sidecar is None
                    ):
                        raise ValueError("v26.90 Compiler completed scoring failed")
                    path_audit = _make_budget_qualified_path(
                        role=typed_role,
                        record=record,
                        prompt_contract=prompt_contract,
                        predecessor_contract=predecessor_contract,
                        provider_contract=provider_contract,
                        thinking_binding=thinking_binding,
                        strategy=strategy,
                        witness=witness,
                        trajectory_id=trajectory.trajectory_id,
                        observations=history,
                    )
                    task_replays.append(replay)
                    task_trajectories.append(trajectory)
                    task_paths.append(path_audit)
                    replay_results.append(replay)
                    compiler_trajectories.append(trajectory)
                    compiler_scores.append(score)
                    path_audits.append(path_audit)
                    witnesses.append(witness)
                    observations.extend(history)

                package_values = {
                    "role": typed_role,
                    "mechanism_id": mechanism,
                    "source_task_artifact_id": source_task.artifact_id,
                    "operational_record_id": record.record_id,
                    "operational_task_package_id": record.task_package.package_id,
                    "semantic_source_id": (record.task_package.semantic_source.semantic_source_id),
                    "environment_manifest_id": environment.manifest_id,
                    "replay_binding_contract_id": replay_binding.contract_id,
                    "compact_prompt_contract_id": prompt_contract.contract_id,
                    "budget_adequacy_contract_id": predecessor_contract.contract_id,
                    "provider_budget_contract_id": provider_contract.contract_id,
                    "thinking_policy_id": PROSPECTIVE_THINKING_MODE_POLICY.policy_id,
                    "thinking_binding_id": thinking_binding.binding_id,
                    "model_config_id": model_config.public_manifest_hash,
                    "path_audit_ids": tuple(item.audit_id for item in task_paths),
                    "path_strategy_ids": strategies,
                    "compiler_witness_ids": tuple(item.witness_id for item in task_witnesses),
                    "compiler_trajectory_ids": tuple(
                        item.trajectory_id for item in task_trajectories
                    ),
                    "verifier_replay_result_ids": tuple(item.replay_id for item in task_replays),
                    "operation_closure_audit_id": closure.audit_id,
                    "operational_admission_id": admission.admission_id,
                }
                provisional_package = BudgetFeasibleRoleTaskPackage.model_construct(
                    task_package_id="pending",
                    **package_values,
                )
                role_package = BudgetFeasibleRoleTaskPackage(
                    task_package_id=budget_feasible_role_task_package_id(provisional_package),
                    **package_values,
                )

                records.append(record)
                environments.append(environment)
                replay_bindings.append(replay_binding)
                necessities.append(necessity)
                counterfactuals.extend(task_counterfactuals)
                catalogs.append(catalog)
                closures.append(closure)
                admissions.append(admission)
                task_audits.append(task_audit)
                prompt_contracts.append(prompt_contract)
                role_packages.append(role_package)

    if len(records) != TASK_COUNT or len(role_packages) != TASK_COUNT:
        raise ValueError("v26.90 role TaskPackage denominator is incomplete")
    if len(path_audits) != TOTAL_PATH_COUNT:
        raise ValueError("v26.90 static path denominator is incomplete")
    if any(record.task_package.package_id in prior_values["task_package_id"] for record in records):
        raise ValueError("v26.90 operational support package overlaps history")
    evidence_ids = [
        item.evidence_id for record in records for item in record.public_corpus.evidence
    ]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("v26.90 selected role tasks reuse Public Evidence")

    freshness_audit = _make_freshness_audit(
        predecessor_contract=predecessor_contract,
        selection_salt=selection_salt,
        historical_records=historical_records,
        historical_record_paths=historical_record_paths,
        historical_job_ids=historical_job_ids,
        historical_manifest_paths=historical_manifest_paths,
        prior_values=prior_values,
        selected=selected,
        records=records,
        packages=role_packages,
    )
    destructive_audit = _make_destructive_audit(
        model_config=model_config,
        prompt_contract=prompt_contracts[0],
        packages=role_packages,
    )
    source_paths = _model_source_paths(
        package_root=package_root,
        predecessor_paths=predecessor_paths,
        historical_record_paths=historical_record_paths,
        historical_manifest_paths=historical_manifest_paths,
        thinking_profile_path=thinking_profile_path,
    )
    source_files = tuple(
        sorted(
            (_source_file(path, package_root) for path in source_paths),
            key=lambda item: item.relative_path,
        )
    )

    paths = {
        "admissions": output_dir / "operational_task_admissions.json",
        "audits": output_dir / "authority_preserving_task_audits.json",
        "budget": output_dir / "provider_token_budget_contract.json",
        "capacity": output_dir / "source_capacity_audit.json",
        "catalogs": output_dir / "static_model_authority_path_catalogs.json",
        "closures": output_dir / "operation_closure_audits.json",
        "counterfactuals": output_dir / "mechanism_counterfactual_replays.json",
        "destructive": output_dir / "destructive_preflight_audit.json",
        "environments": output_dir / "tool_environment_manifests.json",
        "freshness": output_dir / "source_freshness_audit.json",
        "necessities": output_dir / "mechanism_necessity_artifacts.json",
        "observations": output_dir / "operational_witness_observations.json",
        "packages": output_dir / "budget_feasible_role_task_packages.json",
        "path_audits": output_dir / "budget_qualified_path_audits.json",
        "predecessor": output_dir / "predecessor_contract_binding.json",
        "prompt_contracts": output_dir / "compact_prompt_contracts.json",
        "records": output_dir / "operational_task_records.json",
        "replay_bindings": output_dir / "verifier_v2_replay_bindings.json",
        "replay_results": output_dir / "verifier_v2_replay_results.json",
        "scores": output_dir / "completed_compiler_trajectory_scores.json",
        "source_replay": output_dir / "source_replay_audit.json",
        "thinking": output_dir / "thinking_mode_binding.json",
        "trajectories": output_dir / "compiler_trajectories.json",
        "witnesses": output_dir / "operational_public_witnesses.json",
    }
    _write_models(paths["admissions"], admissions, "admission_id")
    _write_models(paths["audits"], task_audits, "audit_id")
    _write_json(paths["budget"], provider_contract.model_dump(mode="json"))
    _write_json(paths["capacity"], capacity_audit.model_dump(mode="json"))
    _write_models(paths["catalogs"], catalogs, "catalog_id")
    _write_models(paths["closures"], closures, "audit_id")
    _write_models(paths["counterfactuals"], counterfactuals, "replay_id")
    _write_json(paths["destructive"], destructive_audit.model_dump(mode="json"))
    _write_models(paths["environments"], environments, "manifest_id")
    _write_json(paths["freshness"], freshness_audit.model_dump(mode="json"))
    _write_models(paths["necessities"], necessities, "artifact_id")
    _write_models(paths["observations"], observations, "observation_id")
    _write_models(paths["packages"], role_packages, "task_package_id")
    _write_models(paths["path_audits"], path_audits, "audit_id")
    _write_json(
        paths["predecessor"],
        {
            "predecessor_report_id": predecessor_report.report_id,
            "predecessor_report_sha256": _sha256(package_root / V26_89_DIR / "report.json"),
            "budget_adequacy_contract_id": predecessor_contract.contract_id,
            "provider_budget_contract_id": provider_contract.contract_id,
            "authorized_input_transition": (
                "fresh_budget_feasible_role_task_rematerialization_only"
            ),
        },
    )
    _write_models(paths["prompt_contracts"], prompt_contracts, "contract_id")
    _write_models(paths["records"], records, "record_id")
    _write_models(paths["replay_bindings"], replay_bindings, "contract_id")
    _write_models(paths["replay_results"], replay_results, "replay_id")
    _write_models(paths["scores"], compiler_scores, "score_id")
    _write_json(
        paths["source_replay"],
        [item.model_dump(mode="json") for item in source_files],
    )
    _write_json(
        paths["thinking"],
        {
            "policy": PROSPECTIVE_THINKING_MODE_POLICY.model_dump(mode="json"),
            "binding": thinking_binding.model_dump(mode="json"),
            "model_config_id": model_config.public_manifest_hash,
            "model_profile_sha256": _sha256(thinking_profile_path),
            "client_construction_permitted_in_this_stage": False,
        },
    )
    _write_models(paths["trajectories"], compiler_trajectories, "trajectory_id")
    _write_models(paths["witnesses"], witnesses, "witness_id")

    counts = {
        "admissions": len(admissions),
        "audits": len(task_audits),
        "budget": 1,
        "capacity": 1,
        "catalogs": len(catalogs),
        "closures": len(closures),
        "counterfactuals": len(counterfactuals),
        "destructive": 1,
        "environments": len(environments),
        "freshness": 1,
        "necessities": len(necessities),
        "observations": len(observations),
        "packages": len(role_packages),
        "path_audits": len(path_audits),
        "predecessor": 1,
        "prompt_contracts": len(prompt_contracts),
        "records": len(records),
        "replay_bindings": len(replay_bindings),
        "replay_results": len(replay_results),
        "scores": len(compiler_scores),
        "source_replay": len(source_files),
        "thinking": 1,
        "trajectories": len(compiler_trajectories),
        "witnesses": len(witnesses),
    }
    detail_files = tuple(
        sorted(
            (_artifact_file(path, output_dir, counts[key]) for key, path in paths.items()),
            key=lambda item: item.relative_path,
        )
    )
    bounds = tuple(item.maximum_cumulative_path_upper_bound for item in path_audits)
    prompt_maxima = tuple(item.maximum_prompt_utf8_bytes for item in path_audits)
    role_counts = dict(
        sorted(Counter(f"{item.role}:{item.mechanism_id}" for item in role_packages).items())
    )
    zero_no_call_upper = 1 - math.pow(0.05, 1 / 32)
    if zero_no_call_upper > 0.10:
        raise ValueError("32-Job zero-no-call calibration no longer meets the frozen Gate")
    values = {
        "run_id": run_id,
        "predecessor_report_id": predecessor_report.report_id,
        "predecessor_report_sha256": _sha256(package_root / V26_89_DIR / "report.json"),
        "predecessor_budget_adequacy_contract_id": predecessor_contract.contract_id,
        "provider_budget_contract_id": provider_contract.contract_id,
        "thinking_policy_id": PROSPECTIVE_THINKING_MODE_POLICY.policy_id,
        "thinking_binding_id": thinking_binding.binding_id,
        "model_config_id": model_config.public_manifest_hash,
        "source_capacity_audit_id": capacity_audit.audit_id,
        "freshness_audit_id": freshness_audit.audit_id,
        "destructive_preflight_audit_id": destructive_audit.audit_id,
        "role_mechanism_task_counts": role_counts,
        "minimum_path_upper_bound": min(bounds),
        "maximum_path_upper_bound": max(bounds),
        "minimum_path_headroom": min(120000 - item for item in bounds),
        "maximum_prompt_utf8_bytes": max(prompt_maxima),
        "role_task_package_ids": tuple(sorted(item.task_package_id for item in role_packages)),
        "source_artifact_files": source_files,
        "immutable_artifact_files": detail_files,
        "implementation_source_files": _implementation_source_files(package_root),
    }
    provisional = BudgetFeasibleRoleRematerializationReport.model_construct(
        report_id="pending",
        **values,
    )
    report = BudgetFeasibleRoleRematerializationReport(
        report_id=budget_feasible_role_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the Finance v26.90 fresh role-separated budget-feasible TaskPackage Population"
        )
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--selection-salt", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    args = parser.parse_args()
    report = build_budget_feasible_role_task_rematerialization(
        run_id=args.run_id,
        selection_salt=args.selection_salt,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
