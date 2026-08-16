from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.schema import TaskPackage, TaskPublicSpec
from trusted_synthesis.domains.finance.agent_tools import FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    RUNTIME_AXIS_RESPONSIBILITY,
    CapabilityRuntimeArm,
    RuntimeTaskBinding,
    _make_runtime_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    CapabilityRolloutOutcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_runner import (
    CapabilityBoundaryRolloutRecord,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import DifficultyTier
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CAPABILITY_SENSITIVE_FAMILIES,
    CapabilitySensitiveTaskArtifact,
    capability_sensitive_task_artifact_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_matched_capability_ladder import (
    MatchedLadderGroup,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_capability_population import (
    FINANCE_OPERATION_EXECUTION_CONTRACT_VERSION,
    MultiTierCapabilityPopulation,
    _public_contract_metadata,
    finance_operation_execution_contract,
    finance_public_calculation_instruction,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_confirmation import (
    WORKFLOW_RUNTIME_ARMS,
    _execute_stage,
    _write_immutable_json,
    _write_immutable_model,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
    ExplorerModelContract,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import (
    ITERATIVE_AGENT_DECISION_PROMPT_VERSION,
    ITERATIVE_AGENT_SOLVER_VERSION,
    IterativeAgentFailureArtifact,
    IterativeAgentProtocolProfile,
)

RUNTIME_RESOLUTION_CONTRACT_VERSION = "finance_runtime_resolution_contract.v2"
RUNTIME_TERMINAL_OUTCOME_VERSION = "finance_runtime_terminal_outcome.v2"
RUNTIME_RESOLUTION_REPORT_VERSION = "finance_runtime_resolution_report.v2"
RUNTIME_RESOLUTION_RUNNER_VERSION = "finance_runtime_resolution_runner.v2"
RUNTIME_RESOLUTION_POLICY_VERSION = "finance_runtime_resolution_policy.v3"
RUNTIME_FAILURE_TAXONOMY_VERSION = "finance_runtime_failure_taxonomy.v2"
GROUP_COUNT = len(CAPABILITY_SENSITIVE_FAMILIES)
TASK_COUNT = GROUP_COUNT * len(DifficultyTier)
BINDING_COUNT = TASK_COUNT * len(WORKFLOW_RUNTIME_ARMS)
REPLICAS = 2
ROLLOUT_COUNT = BINDING_COUNT * REPLICAS
MODEL_TOKEN_BUDGET = 120_000
MAXIMUM_OBSERVATION_SUMMARY_BYTES = 48_000
MAXIMUM_PUBLIC_CONTEXT_BYTES = 96_000


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RuntimeResolutionStage(str, Enum):
    RESIDUAL_DEVELOPMENT = "residual_failure_development"
    HELDOUT_CONFIRMATION = "fresh_heldout_runtime_confirmation"


class FailureLayer(str, Enum):
    L0_EXTERNAL_INFRASTRUCTURE = "l0_external_infrastructure"
    L1_TASK_RUNTIME_CONTRACT = "l1_task_runtime_contract"
    L2_TOOL_ENVIRONMENT = "l2_tool_environment"
    L3_MODEL_PROTOCOL = "l3_model_protocol"
    L4_MODEL_AGENT_DECISION = "l4_model_agent_decision"
    L5_MODEL_SEMANTIC = "l5_model_semantic"
    L6_SUCCESS = "l6_success"
    UNATTRIBUTED_MIXED = "unattributed_or_mixed_failure"


class TerminalClass(str, Enum):
    SUCCESSFUL_ANSWER = "successful_answer"
    INVALID_ANSWER = "invalid_answer"
    PREMATURE_STOP = "premature_stop"
    DETERMINISTIC_RECOVERY_FAILURE = "deterministic_recovery_failure"
    TOOL_CALL_BUDGET = "tool_call_budget"
    MODEL_TOKEN_BUDGET = "model_token_budget"
    OBSERVATION_BUDGET = "observation_budget"
    MODEL_CONTRACT_FAILURE = "model_contract_failure"
    UNAVAILABLE_TOOL = "unavailable_tool"
    PROVIDER_FAILURE = "provider_failure"
    RUNTIME_CONTRACT_FAILURE = "runtime_contract_failure"
    TOOL_ENVIRONMENT_FAILURE = "tool_environment_failure"
    UNKNOWN_FAILURE = "unknown_failure"


class RuntimeResolutionThresholds(FrozenModel):
    minimum_api_transport_resolution_rate: float = Field(default=1.0, ge=1, le=1)
    minimum_bounded_json_rate: float = Field(default=1.0, ge=1, le=1)
    minimum_observation_replay_rate: float = Field(default=1.0, ge=1, le=1)
    minimum_authority_integrity_rate: float = Field(default=1.0, ge=1, le=1)
    minimum_terminal_resolution_rate: float = Field(default=1.0, ge=1, le=1)
    minimum_failure_attribution_coverage_rate: float = Field(default=1.0, ge=1, le=1)
    maximum_external_failure_rate: float = Field(default=0.0, ge=0, le=0)
    maximum_runtime_contract_failure_rate: float = Field(default=0.0, ge=0, le=0)
    maximum_tool_environment_failure_rate: float = Field(default=0.0, ge=0, le=0)
    maximum_unattributed_failure_rate: float = Field(default=0.0, ge=0, le=0)
    maximum_runtime_prompt_pathology_rate: float = Field(default=0.05, ge=0, le=0.05)
    minimum_valid_success_rate: float = Field(default=0.10, ge=0, le=1)
    maximum_valid_success_rate: float = Field(default=0.90, ge=0, le=1)
    minimum_boundary_cell_fraction: float = Field(default=0.10, ge=0, le=1)

    @model_validator(mode="after")
    def validate_interval(self) -> RuntimeResolutionThresholds:
        if self.minimum_valid_success_rate >= self.maximum_valid_success_rate:
            raise ValueError("runtime capability interval is empty")
        return self


class FreshnessAudit(FrozenModel):
    excluded_group_count: int = Field(ge=GROUP_COUNT)
    selected_group_count: int = Field(ge=GROUP_COUNT, le=GROUP_COUNT)
    group_overlap_count: Literal[0] = 0
    source_task_overlap_count: Literal[0] = 0
    evidence_overlap_count: Literal[0] = 0
    evidence_version_overlap_count: Literal[0] = 0
    semantic_signature_overlap_count: Literal[0] = 0
    trajectory_seed_overlap_count: Literal[0] = 0


class FinanceRuntimeResolutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    stage: RuntimeResolutionStage
    source_population_path: str = Field(min_length=1)
    source_population_sha256: str = Field(min_length=64, max_length=64)
    source_population_id: str = Field(min_length=1)
    source_confirmation_contract_path: str = Field(min_length=1)
    source_confirmation_contract_sha256: str = Field(min_length=64, max_length=64)
    source_confirmation_contract_id: str = Field(min_length=1)
    source_v25_16_contract_path: str = Field(min_length=1)
    source_v25_16_contract_sha256: str = Field(min_length=64, max_length=64)
    source_v25_16_report_path: str = Field(min_length=1)
    source_v25_16_report_sha256: str = Field(min_length=64, max_length=64)
    source_v25_16_report_id: str = Field(min_length=1)
    prior_development_contract_path: str | None = None
    prior_development_contract_sha256: str | None = None
    prior_development_report_path: str | None = None
    prior_development_report_sha256: str | None = None
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    iterative_agent_solver_version: str = ITERATIVE_AGENT_SOLVER_VERSION
    iterative_agent_decision_prompt_version: str = ITERATIVE_AGENT_DECISION_PROMPT_VERSION
    finance_interactive_runtime_version: str = FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION
    finance_agent_toolset_version: str = FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION
    operation_execution_contract_version: str = FINANCE_OPERATION_EXECUTION_CONTRACT_VERSION
    runtime_resolution_policy_version: str = RUNTIME_RESOLUTION_POLICY_VERSION
    failure_taxonomy_version: str = RUNTIME_FAILURE_TAXONOMY_VERSION
    implementation_manifest: dict[str, str] = Field(min_length=1)
    implementation_manifest_hash: str = Field(min_length=1)
    model_contracts: tuple[ExplorerModelContract, ...] = Field(min_length=1, max_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    thresholds: RuntimeResolutionThresholds
    excluded_group_ids: dict[str, tuple[str, ...]] = Field(min_length=GROUP_COUNT)
    selected_group_ids: dict[str, str] = Field(min_length=GROUP_COUNT)
    tasks: tuple[CapabilitySensitiveTaskArtifact, ...] = Field(
        min_length=TASK_COUNT, max_length=TASK_COUNT
    )
    source_task_artifact_ids: dict[str, str] = Field(min_length=TASK_COUNT, max_length=TASK_COUNT)
    task_semantic_signatures: dict[str, str] = Field(min_length=TASK_COUNT, max_length=TASK_COUNT)
    task_evidence_ids: dict[str, tuple[str, ...]] = Field(
        min_length=TASK_COUNT, max_length=TASK_COUNT
    )
    task_evidence_version_ids: dict[str, tuple[str, ...]] = Field(
        min_length=TASK_COUNT, max_length=TASK_COUNT
    )
    bindings: tuple[RuntimeTaskBinding, ...] = Field(
        min_length=BINDING_COUNT, max_length=BINDING_COUNT
    )
    freshness: FreshnessAudit
    replicas: int = Field(default=REPLICAS, ge=REPLICAS, le=REPLICAS)
    requested_rollout_count: int = Field(default=ROLLOUT_COUNT, ge=ROLLOUT_COUNT, le=ROLLOUT_COUNT)
    maximum_model_tokens_per_rollout: int = Field(
        default=MODEL_TOKEN_BUDGET, ge=MODEL_TOKEN_BUDGET, le=MODEL_TOKEN_BUDGET
    )
    maximum_observation_summary_bytes: int = Field(
        default=MAXIMUM_OBSERVATION_SUMMARY_BYTES,
        ge=MAXIMUM_OBSERVATION_SUMMARY_BYTES,
        le=MAXIMUM_OBSERVATION_SUMMARY_BYTES,
    )
    maximum_public_context_bytes: int = Field(
        default=MAXIMUM_PUBLIC_CONTEXT_BYTES,
        ge=MAXIMUM_PUBLIC_CONTEXT_BYTES,
        le=MAXIMUM_PUBLIC_CONTEXT_BYTES,
    )
    rollout_identity_tokens: dict[str, str] = Field(
        min_length=ROLLOUT_COUNT, max_length=ROLLOUT_COUNT
    )
    model_contract_repair_attempts: int = Field(default=2, ge=2, le=2)
    selection_salt: str = Field(min_length=1)
    pro_api_calls_authorized: Literal[False] = False
    information_matrix_evaluation_authorized: Literal[False] = False
    model_ranking_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = RUNTIME_RESOLUTION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceRuntimeResolutionContract:
        if self.schema_version != RUNTIME_RESOLUTION_CONTRACT_VERSION:
            raise ValueError("runtime-resolution contract version is unsupported")
        expected_versions = (
            self.iterative_agent_solver_version == ITERATIVE_AGENT_SOLVER_VERSION,
            self.iterative_agent_decision_prompt_version == ITERATIVE_AGENT_DECISION_PROMPT_VERSION,
            self.finance_interactive_runtime_version == FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION,
            self.finance_agent_toolset_version == FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
            self.operation_execution_contract_version
            == FINANCE_OPERATION_EXECUTION_CONTRACT_VERSION,
        )
        if not all(expected_versions):
            raise ValueError("runtime-resolution implementation identity is stale")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest, prefix="runtime_resolution_implementation:"
        ):
            raise ValueError("runtime-resolution implementation manifest is invalid")
        if {item.arm for item in self.model_contracts} != {ExplorerArm.FLASH}:
            raise ValueError("runtime-resolution experiment is Flash-only")
        if self.protocol_profile.observation_view != "bounded_summary":
            raise ValueError("runtime-resolution requires bounded public observations")
        if set(self.selected_group_ids) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("runtime-resolution omits a capability family")
        if set(self.excluded_group_ids) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("runtime-resolution exclusions omit a capability family")
        if any(
            self.selected_group_ids[family] in self.excluded_group_ids[family]
            for family in CAPABILITY_SENSITIVE_FAMILIES
        ):
            raise ValueError("runtime-resolution group freshness failed")
        task_ids = {item.artifact_id for item in self.tasks}
        if len(task_ids) != TASK_COUNT or set(self.source_task_artifact_ids) != task_ids:
            raise ValueError("runtime-resolution task identity is incomplete")
        if (
            set(self.task_semantic_signatures) != task_ids
            or set(self.task_evidence_ids) != task_ids
            or set(self.task_evidence_version_ids) != task_ids
        ):
            raise ValueError("runtime-resolution task freshness identity is incomplete")
        expected_counts = Counter(
            (family, tier) for family in CAPABILITY_SENSITIVE_FAMILIES for tier in DifficultyTier
        )
        if Counter((item.family, item.tier) for item in self.tasks) != expected_counts:
            raise ValueError("runtime-resolution tasks are not family/Tier balanced")
        binding_counts = Counter(
            (item.task_artifact_id, item.runtime_arm) for item in self.bindings
        )
        if (
            set(binding_counts.values()) != {1}
            or set(item.task_artifact_id for item in self.bindings) != task_ids
        ):
            raise ValueError("runtime-resolution tasks lack one binding per Runtime")
        if {item.runtime_arm for item in self.bindings} != set(WORKFLOW_RUNTIME_ARMS):
            raise ValueError("runtime-resolution includes another Runtime")
        expected_rollout_keys = {
            _rollout_identity_key(item.binding_id, replicate)
            for item in self.bindings
            for replicate in range(self.replicas)
        }
        if set(self.rollout_identity_tokens) != expected_rollout_keys:
            raise ValueError("runtime-resolution rollout identities are incomplete")
        for item in self.tasks:
            guidance = item.task.public.metadata.get("agent_contract_guidance")
            observed = (
                guidance.get("operation_execution_contract")
                if isinstance(guidance, Mapping)
                else None
            )
            expected = finance_operation_execution_contract(
                family=item.family,
                tier=item.tier,
                gold=item.evidence_bundle.evidence,
                program=item.task.oracle.task_program,
            )
            if canonical_hash(observed) != canonical_hash(expected):
                raise ValueError("public Operation Contract differs from Oracle Program")
        requires_prior = self.stage == RuntimeResolutionStage.HELDOUT_CONFIRMATION
        prior_values = (
            self.prior_development_contract_path,
            self.prior_development_contract_sha256,
            self.prior_development_report_path,
            self.prior_development_report_sha256,
        )
        if requires_prior != all(item is not None for item in prior_values):
            raise ValueError("held-out stage has invalid Development lineage")
        if self.contract_id != runtime_resolution_contract_id(self):
            raise ValueError("runtime-resolution contract identity is invalid")
        return self


class RuntimeTerminalOutcome(FrozenModel):
    terminal_outcome_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    stage: RuntimeResolutionStage
    record_id: str = Field(min_length=1)
    binding_id: str = Field(min_length=1)
    task_artifact_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    tier: DifficultyTier
    runtime_arm: CapabilityRuntimeArm
    replicate: int = Field(ge=0)
    terminal_class: TerminalClass
    primary_failure_layer: FailureLayer
    secondary_failure_layers: tuple[FailureLayer, ...] = ()
    attribution_confidence: Literal["high", "medium", "low"]
    attribution_evidence: tuple[str, ...] = Field(min_length=1)
    terminal_resolved: bool
    failure_attributed: bool
    runtime_eligible_for_capability_denominator: bool
    runtime_pathology: bool
    prompt_pathology: bool
    api_transport_resolved: bool
    execution_integrity_passed: bool
    raw_json_contract_success: bool
    bounded_json_resolution_success: bool
    observation_replay_success: bool
    authority_integrity_success: bool
    deterministic_valid: bool
    semantic_answer_correct: bool
    valid_success: bool
    capability_outcomes: dict[str, bool | None]
    stop_rejection_count: int = Field(ge=0)
    identical_failed_action_block_count: int = Field(ge=0)
    maximum_prompt_component_bytes: int = Field(ge=0)
    maximum_public_context_bytes: int = Field(ge=0)
    maximum_observation_summary_bytes: int = Field(ge=0)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    error_type: str | None = None
    error_code: str | None = None
    schema_version: str = RUNTIME_TERMINAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_terminal_outcome(self) -> RuntimeTerminalOutcome:
        if self.schema_version != RUNTIME_TERMINAL_OUTCOME_VERSION:
            raise ValueError("runtime terminal outcome version is unsupported")
        if set(self.capability_outcomes) != {*CAPABILITY_AXES, "semantic", "final_valid"}:
            raise ValueError("runtime terminal outcome omits a capability axis")
        is_success = self.primary_failure_layer == FailureLayer.L6_SUCCESS
        if is_success != (self.terminal_class == TerminalClass.SUCCESSFUL_ANSWER):
            raise ValueError("runtime terminal success classification is inconsistent")
        if is_success != self.valid_success:
            raise ValueError("runtime terminal success differs from verified success")
        expected_eligible = self.primary_failure_layer in {
            FailureLayer.L3_MODEL_PROTOCOL,
            FailureLayer.L4_MODEL_AGENT_DECISION,
            FailureLayer.L5_MODEL_SEMANTIC,
            FailureLayer.L6_SUCCESS,
        }
        if self.runtime_eligible_for_capability_denominator != expected_eligible:
            raise ValueError("runtime capability denominator is inconsistent")
        if self.failure_attributed and not self.terminal_resolved:
            raise ValueError("failure attribution lacks a resolved terminal class")
        if self.terminal_outcome_id != runtime_terminal_outcome_id(self):
            raise ValueError("runtime terminal outcome identity is invalid")
        return self


class RuntimeResolutionMetrics(FrozenModel):
    attempted_count: int = Field(ge=1)
    terminal_outcome_count: int = Field(ge=1)
    api_transport_resolution_rate: float = Field(ge=0, le=1)
    raw_json_contract_rate: float = Field(ge=0, le=1)
    bounded_json_resolution_rate: float = Field(ge=0, le=1)
    observation_replay_rate: float = Field(ge=0, le=1)
    authority_integrity_rate: float = Field(ge=0, le=1)
    execution_integrity_rate: float = Field(ge=0, le=1)
    terminal_resolution_rate: float = Field(ge=0, le=1)
    failure_attribution_coverage_rate: float = Field(ge=0, le=1)
    external_infrastructure_failure_rate: float = Field(ge=0, le=1)
    task_runtime_contract_failure_rate: float = Field(ge=0, le=1)
    tool_environment_failure_rate: float = Field(ge=0, le=1)
    unattributed_failure_rate: float = Field(ge=0, le=1)
    runtime_prompt_pathology_rate: float = Field(ge=0, le=1)
    runtime_eligible_count: int = Field(ge=0)
    semantic_accuracy_given_runtime_eligible: float = Field(ge=0, le=1)
    valid_success_given_runtime_eligible: float = Field(ge=0, le=1)
    end_to_end_semantic_accuracy: float = Field(ge=0, le=1)
    deterministic_valid_rate: float = Field(ge=0, le=1)
    end_to_end_valid_success_rate: float = Field(ge=0, le=1)
    boundary_cell_fraction: float = Field(ge=0, le=1)
    success_entropy: float = Field(ge=0)
    premature_stop_rate: float = Field(ge=0, le=1)
    deterministic_recovery_failure_rate: float = Field(ge=0, le=1)
    identical_failed_action_block_rate: float = Field(ge=0, le=1)
    primary_failure_layer_counts: dict[str, int]
    terminal_class_counts: dict[str, int]
    error_code_counts: dict[str, int]
    capability_axis_rates: dict[str, float | None]
    capability_axis_denominators: dict[str, int]
    tier_valid_success_given_runtime_eligible: dict[str, float]
    runtime_valid_success_given_runtime_eligible: dict[str, float]
    tier_end_to_end_valid_success_rates: dict[str, float]
    runtime_end_to_end_valid_success_rates: dict[str, float]
    maximum_prompt_component_bytes: int = Field(ge=0)
    maximum_public_context_bytes: int = Field(ge=0)
    maximum_observation_summary_bytes: int = Field(ge=0)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_metrics(self) -> RuntimeResolutionMetrics:
        if self.terminal_outcome_count != self.attempted_count:
            raise ValueError("runtime-resolution metrics lack a complete denominator")
        if set(self.capability_axis_rates) != {*CAPABILITY_AXES, "semantic", "final_valid"}:
            raise ValueError("runtime-resolution metrics omit capability rates")
        if set(self.capability_axis_denominators) != set(self.capability_axis_rates):
            raise ValueError("runtime-resolution capability denominators are incomplete")
        return self


class RuntimeResolutionCell(FrozenModel):
    family: str = Field(min_length=1)
    tier: DifficultyTier
    runtime_arm: CapabilityRuntimeArm
    rollout_count: int = Field(ge=1)
    runtime_eligible_count: int = Field(ge=0)
    semantic_success_given_runtime_eligible: float = Field(ge=0, le=1)
    valid_success_given_runtime_eligible: float = Field(ge=0, le=1)
    end_to_end_valid_success_rate: float = Field(ge=0, le=1)
    boundary_cell: bool
    primary_failure_layer_counts: dict[str, int]


class RuntimeResolutionGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    passed: bool
    observed: float
    requirement: str = Field(min_length=1)
    category: Literal[
        "execution_integrity",
        "terminal_resolution",
        "runtime_pathology",
        "failure_attribution",
        "capability_measurement",
    ]


class FinanceRuntimeResolutionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    stage: RuntimeResolutionStage
    requested_rollout_count: int = Field(ge=ROLLOUT_COUNT, le=ROLLOUT_COUNT)
    recorded_rollout_count: int = Field(ge=ROLLOUT_COUNT, le=ROLLOUT_COUNT)
    metrics: RuntimeResolutionMetrics
    cells: tuple[RuntimeResolutionCell, ...] = Field(
        min_length=BINDING_COUNT, max_length=BINDING_COUNT
    )
    gates: tuple[RuntimeResolutionGate, ...] = Field(min_length=1)
    execution_integrity_passed: bool
    terminal_resolution_passed: bool
    runtime_pathology_passed: bool
    failure_attribution_passed: bool
    capability_measurement_suitable: bool
    runtime_qualification_passed: bool
    joint_stage_ready: bool
    outcome_set_hash: str = Field(min_length=1)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    pro_api_call_count: Literal[0] = 0
    pro_api_calls_authorized: Literal[False] = False
    information_matrix_evaluation_authorized: bool
    model_ranking_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "fresh_flash_runtime_confirmation",
        "flash_information_matrix_evaluation",
        "capability_support_redesign_only",
        "runtime_resolution_repair_only",
    ]
    schema_version: str = RUNTIME_RESOLUTION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceRuntimeResolutionReport:
        if self.schema_version != RUNTIME_RESOLUTION_REPORT_VERSION:
            raise ValueError("runtime-resolution report version is unsupported")
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("runtime-resolution report lacks its complete denominator")
        category_passes = {
            category: all(item.passed for item in self.gates if item.category == category)
            for category in (
                "execution_integrity",
                "terminal_resolution",
                "runtime_pathology",
                "failure_attribution",
                "capability_measurement",
            )
        }
        observed = (
            self.execution_integrity_passed,
            self.terminal_resolution_passed,
            self.runtime_pathology_passed,
            self.failure_attribution_passed,
            self.capability_measurement_suitable,
        )
        if observed != tuple(category_passes.values()):
            raise ValueError("runtime-resolution aggregate gates are inconsistent")
        expected_runtime = all(observed[:4])
        if self.runtime_qualification_passed != expected_runtime:
            raise ValueError("runtime qualification decision is inconsistent")
        expected_joint = expected_runtime and observed[4]
        if self.joint_stage_ready != expected_joint:
            raise ValueError("runtime-resolution joint readiness is inconsistent")
        expected_information = bool(
            self.stage == RuntimeResolutionStage.HELDOUT_CONFIRMATION and expected_joint
        )
        if self.information_matrix_evaluation_authorized != expected_information:
            raise ValueError("runtime-resolution downstream authorization is inconsistent")
        expected_next = _next_permitted_stage(
            stage=self.stage,
            runtime_qualified=expected_runtime,
            capability_suitable=observed[4],
        )
        if self.next_permitted_stage != expected_next:
            raise ValueError("runtime-resolution transition is not fail-closed")
        if self.report_id != runtime_resolution_report_id(self):
            raise ValueError("runtime-resolution report identity is invalid")
        return self


def prepare_runtime_resolution_contract(
    *,
    stage: RuntimeResolutionStage,
    source_population_path: Path,
    source_confirmation_contract_path: Path,
    source_v25_16_contract_path: Path,
    source_v25_16_report_path: Path,
    finance_archive_config_path: Path,
    output_path: Path,
    run_id: str,
    selection_salt: str,
    prior_development_contract_path: Path | None = None,
    prior_development_report_path: Path | None = None,
) -> FinanceRuntimeResolutionContract:
    if output_path.exists():
        raise ValueError("runtime-resolution contract is immutable and already exists")
    population_path = source_population_path.resolve()
    confirmation_path = source_confirmation_contract_path.resolve()
    v25_contract_path = source_v25_16_contract_path.resolve()
    v25_report_path = source_v25_16_report_path.resolve()
    finance_config_path = finance_archive_config_path.resolve()
    population = MultiTierCapabilityPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    confirmation_raw = _load_json_object(confirmation_path)
    v25_contract_raw = _load_json_object(v25_contract_path)
    v25_report_raw = _load_json_object(v25_report_path)
    if v25_report_raw.get("contract_id") != v25_contract_raw.get("contract_id"):
        raise ValueError("v25.16 report belongs to another contract")
    if v25_report_raw.get("next_permitted_stage") != "runtime_contract_repair_only":
        raise ValueError("v25.17 requires the frozen fail-closed v25.16 result")
    if int(v25_report_raw.get("recorded_rollout_count", -1)) != ROLLOUT_COUNT:
        raise ValueError("v25.16 report lacks its complete denominator")
    v25_selected = _group_ids_by_family(v25_contract_raw.get("selected_group_ids"))
    excluded: dict[str, tuple[str, ...]] = {
        family: (v25_selected[family],) for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    prior_contract: FinanceRuntimeResolutionContract | None = None
    prior_report: FinanceRuntimeResolutionReport | None = None
    if stage == RuntimeResolutionStage.HELDOUT_CONFIRMATION:
        if prior_development_contract_path is None or prior_development_report_path is None:
            raise ValueError("held-out confirmation requires frozen Development artifacts")
        prior_contract_path = prior_development_contract_path.resolve()
        prior_report_path = prior_development_report_path.resolve()
        prior_contract = FinanceRuntimeResolutionContract.model_validate_json(
            prior_contract_path.read_text(encoding="utf-8")
        )
        prior_report = FinanceRuntimeResolutionReport.model_validate_json(
            prior_report_path.read_text(encoding="utf-8")
        )
        if (
            prior_contract.stage != RuntimeResolutionStage.RESIDUAL_DEVELOPMENT
            or prior_report.contract_id != prior_contract.contract_id
            or not prior_report.joint_stage_ready
            or prior_report.next_permitted_stage != "fresh_flash_runtime_confirmation"
        ):
            raise ValueError("held-out confirmation lacks a passing Development stage")
        if prior_contract.source_population_id != population.population_id:
            raise ValueError("Development and held-out stages use different populations")
        for family in CAPABILITY_SENSITIVE_FAMILIES:
            excluded[family] = tuple(
                sorted({v25_selected[family], prior_contract.selected_group_ids[family]})
            )
    elif prior_development_contract_path is not None or prior_development_report_path is not None:
        raise ValueError("Development stage cannot consume prior Development artifacts")

    selected = _select_fresh_groups(population, excluded, selection_salt)
    repaired: list[CapabilitySensitiveTaskArtifact] = []
    source_ids: dict[str, str] = {}
    semantic_signatures: dict[str, str] = {}
    evidence_ids: dict[str, tuple[str, ...]] = {}
    evidence_version_ids: dict[str, tuple[str, ...]] = {}
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        group = selected[family]
        for source in sorted(group.variants, key=lambda item: item.tier.value):
            task = _repair_task(source, run_id=run_id, stage=stage)
            repaired.append(task)
            source_ids[task.artifact_id] = source.artifact_id
            semantic_signatures[task.artifact_id] = group.core_semantic_signature
            evidence_ids[task.artifact_id] = tuple(
                sorted(item.evidence_id for item in source.public_corpus.evidence)
            )
            evidence_version_ids[task.artifact_id] = tuple(
                sorted(item.evidence_version_id for item in source.public_corpus.evidence)
            )
    tasks = tuple(sorted(repaired, key=lambda item: (item.family, item.tier.value)))
    source_profile = IterativeAgentProtocolProfile.model_validate(
        v25_contract_raw.get("protocol_profile")
    )
    profile = source_profile.model_copy(update={"observation_view": "bounded_summary"})
    bindings = tuple(
        _make_runtime_binding(task, runtime, profile)
        for task in tasks
        for runtime in WORKFLOW_RUNTIME_ARMS
    )
    rollout_tokens = {
        _rollout_identity_key(binding.binding_id, replicate): canonical_hash(
            {
                "run_id": run_id,
                "stage": stage.value,
                "binding_id": binding.binding_id,
                "replicate": replicate,
                "selection_salt": selection_salt,
            },
            prefix="finance_runtime_resolution_rollout_identity:",
        )
        for binding in bindings
        for replicate in range(REPLICAS)
    }
    flash_contracts = tuple(
        ExplorerModelContract.model_validate(item)
        for item in confirmation_raw.get("model_contracts", ())
        if item.get("arm") == ExplorerArm.FLASH.value
    )
    if len(flash_contracts) != 1:
        raise ValueError("source confirmation does not freeze exactly one Flash model")
    implementation_manifest = _implementation_manifest()
    if prior_contract is not None and prior_contract.implementation_manifest_hash != canonical_hash(
        implementation_manifest,
        prefix="runtime_resolution_implementation:",
    ):
        raise ValueError("implementation changed after Development; rerun Development")

    excluded_group_id_set = {item for values in excluded.values() for item in values}
    excluded_groups = tuple(
        group for group in population.groups if group.group_id in excluded_group_id_set
    )
    selected_groups = tuple(selected.values())
    selected_source_ids = {item.artifact_id for group in selected_groups for item in group.variants}
    excluded_source_ids = {item.artifact_id for group in excluded_groups for item in group.variants}
    selected_evidence, selected_versions = _group_evidence_sets(selected_groups)
    prior_evidence, prior_versions = _group_evidence_sets(excluded_groups)
    excluded_evidence = set(population.excluded_evidence_ids) | prior_evidence
    excluded_versions = set(population.excluded_evidence_version_ids) | prior_versions
    selected_signatures = {item.core_semantic_signature for item in selected_groups}
    excluded_signatures = set(population.excluded_core_signatures) | {
        item.core_semantic_signature for item in excluded_groups
    }
    prior_tokens = set(prior_contract.rollout_identity_tokens.values()) if prior_contract else set()
    freshness = FreshnessAudit(
        excluded_group_count=len(excluded_group_id_set),
        selected_group_count=len(selected_groups),
        group_overlap_count=len(
            {selected[group].group_id for group in selected} & excluded_group_id_set
        ),
        source_task_overlap_count=len(selected_source_ids & excluded_source_ids),
        evidence_overlap_count=len(selected_evidence & excluded_evidence),
        evidence_version_overlap_count=len(selected_versions & excluded_versions),
        semantic_signature_overlap_count=len(selected_signatures & excluded_signatures),
        trajectory_seed_overlap_count=len(set(rollout_tokens.values()) & prior_tokens),
    )
    prior_contract_path_value = (
        str(prior_development_contract_path.resolve())
        if prior_development_contract_path is not None
        else None
    )
    prior_report_path_value = (
        str(prior_development_report_path.resolve())
        if prior_development_report_path is not None
        else None
    )
    values = {
        "run_id": run_id,
        "stage": stage,
        "source_population_path": str(population_path),
        "source_population_sha256": _sha256(population_path),
        "source_population_id": population.population_id,
        "source_confirmation_contract_path": str(confirmation_path),
        "source_confirmation_contract_sha256": _sha256(confirmation_path),
        "source_confirmation_contract_id": str(confirmation_raw.get("contract_id")),
        "source_v25_16_contract_path": str(v25_contract_path),
        "source_v25_16_contract_sha256": _sha256(v25_contract_path),
        "source_v25_16_report_path": str(v25_report_path),
        "source_v25_16_report_sha256": _sha256(v25_report_path),
        "source_v25_16_report_id": str(v25_report_raw.get("report_id")),
        "prior_development_contract_path": prior_contract_path_value,
        "prior_development_contract_sha256": (
            _sha256(Path(prior_contract_path_value)) if prior_contract_path_value else None
        ),
        "prior_development_report_path": prior_report_path_value,
        "prior_development_report_sha256": (
            _sha256(Path(prior_report_path_value)) if prior_report_path_value else None
        ),
        "finance_archive_config_path": str(finance_config_path),
        "finance_archive_config_sha256": _sha256(finance_config_path),
        "implementation_manifest": implementation_manifest,
        "implementation_manifest_hash": canonical_hash(
            implementation_manifest, prefix="runtime_resolution_implementation:"
        ),
        "model_contracts": flash_contracts,
        "protocol_profile": profile,
        "thresholds": RuntimeResolutionThresholds(),
        "excluded_group_ids": excluded,
        "selected_group_ids": {
            family: selected[family].group_id for family in CAPABILITY_SENSITIVE_FAMILIES
        },
        "tasks": tasks,
        "source_task_artifact_ids": source_ids,
        "task_semantic_signatures": semantic_signatures,
        "task_evidence_ids": evidence_ids,
        "task_evidence_version_ids": evidence_version_ids,
        "bindings": bindings,
        "freshness": freshness,
        "replicas": REPLICAS,
        "requested_rollout_count": ROLLOUT_COUNT,
        "maximum_model_tokens_per_rollout": MODEL_TOKEN_BUDGET,
        "maximum_observation_summary_bytes": MAXIMUM_OBSERVATION_SUMMARY_BYTES,
        "maximum_public_context_bytes": MAXIMUM_PUBLIC_CONTEXT_BYTES,
        "rollout_identity_tokens": rollout_tokens,
        "model_contract_repair_attempts": int(
            v25_contract_raw.get("model_contract_repair_attempts", 2)
        ),
        "selection_salt": selection_salt,
    }
    provisional = FinanceRuntimeResolutionContract.model_construct(contract_id="pending", **values)
    contract = FinanceRuntimeResolutionContract(
        contract_id=runtime_resolution_contract_id(provisional), **values
    )
    _write_immutable_model(output_path, contract)
    return contract


def _select_fresh_groups(
    population: MultiTierCapabilityPopulation,
    excluded: Mapping[str, Sequence[str]],
    salt: str,
) -> dict[str, MatchedLadderGroup]:
    selected: dict[str, MatchedLadderGroup] = {}
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        candidates = tuple(
            group
            for group in population.groups
            if group.family == family and group.group_id not in set(excluded[family])
        )
        if not candidates:
            raise ValueError(f"source population lacks a fresh group for {family}")
        selected[family] = min(
            candidates,
            key=lambda item: canonical_hash(
                {"selection_salt": salt, "group_id": item.group_id},
                prefix="finance_runtime_resolution_group_selection:",
            ),
        )
    return selected


def _repair_task(
    source: CapabilitySensitiveTaskArtifact,
    *,
    run_id: str,
    stage: RuntimeResolutionStage,
) -> CapabilitySensitiveTaskArtifact:
    gold = source.evidence_bundle.evidence
    metadata = _public_contract_metadata(
        family=source.family,
        tier=source.tier,
        gold=gold,
        program=source.task.oracle.task_program,
        answer_projection=source.answer_projection,
        recovery_branches=source.recovery_branches,
    )
    public_payload = source.task.public.model_dump(mode="json")
    public_payload.update(
        {
            "instruction": finance_public_calculation_instruction(
                source.task.public.instruction,
                family=source.family,
                tier=source.tier,
                gold=gold,
                program=source.task.oracle.task_program,
            ),
            "metadata": {
                **source.task.public.metadata,
                **metadata,
                "runtime_resolution_experiment": {
                    "version": RUNTIME_RESOLUTION_CONTRACT_VERSION,
                    "run_id": run_id,
                    "stage": stage.value,
                    "source_artifact_id": source.artifact_id,
                    "oracle_program_unchanged": True,
                    "public_evidence_unchanged": True,
                    "full_operation_dag_model_visible": False,
                },
            },
        }
    )
    public = TaskPublicSpec.model_validate(public_payload)
    task_payload = source.task.model_dump(mode="json")
    task_payload["public"] = public.model_dump(mode="json")
    package = TaskPackage.model_validate(task_payload)
    provisional = source.model_copy(update={"artifact_id": "pending", "task": package})
    payload = source.model_dump(mode="json")
    payload.update(
        {
            "artifact_id": capability_sensitive_task_artifact_id(provisional),
            "task": package.model_dump(mode="json"),
        }
    )
    return CapabilitySensitiveTaskArtifact.model_validate(payload)


def run_runtime_resolution_stage(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceRuntimeResolutionReport:
    contract = FinanceRuntimeResolutionContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_frozen_inputs(contract)
    prefix = f"runtime_resolution_{contract.stage.value}"
    outcomes, discovered = _execute_stage(
        contract=contract,
        tasks={item.artifact_id: item for item in contract.tasks},
        bindings=contract.bindings,
        model_arm=ExplorerArm.FLASH,
        replicas=contract.replicas,
        output_dir=output_dir,
        prefix=prefix,
        workers=workers,
    )
    records_path = output_dir / f"{prefix}_records.jsonl"
    outcomes_path = output_dir / f"{prefix}_outcomes.jsonl"
    records = _load_records(records_path)
    terminals = make_runtime_terminal_outcomes(contract, records, outcomes)
    terminal_path = output_dir / f"{prefix}_terminal_outcomes.jsonl"
    _write_jsonl_atomic(
        terminal_path,
        (item.model_dump(mode="json") for item in terminals),
    )
    report = make_runtime_resolution_report(contract, terminals)
    report_path = output_dir / "finance_runtime_resolution_report.json"
    _write_immutable_model(report_path, report)
    _write_immutable_json(
        output_dir / "runtime_resolution_manifest.json",
        {
            "contract_id": contract.contract_id,
            "stage": contract.stage.value,
            "runner_version": RUNTIME_RESOLUTION_RUNNER_VERSION,
            "failure_taxonomy_version": RUNTIME_FAILURE_TAXONOMY_VERSION,
            "requested_model": contract.model_contracts[0].requested_model,
            "discovered_models": discovered,
            "records_sha256": _sha256(records_path),
            "outcomes_sha256": _sha256(outcomes_path),
            "terminal_outcomes_sha256": _sha256(terminal_path),
            "report_id": report.report_id,
            "report_sha256": _sha256(report_path),
            "pro_api_call_count": 0,
        },
    )
    return report


def make_runtime_terminal_outcomes(
    contract: FinanceRuntimeResolutionContract,
    records: Sequence[CapabilityBoundaryRolloutRecord],
    outcomes: Sequence[CapabilityRolloutOutcome],
) -> tuple[RuntimeTerminalOutcome, ...]:
    if len(records) != contract.requested_rollout_count or len(outcomes) != len(records):
        raise ValueError("runtime-resolution stage has an incomplete denominator")
    record_by_key = {(item.binding_id, item.replicate): item for item in records}
    outcome_by_key = {(item.binding_id, item.replicate): item for item in outcomes}
    if set(record_by_key) != set(outcome_by_key):
        raise ValueError("runtime-resolution records and outcomes differ")
    binding_by_id = {item.binding_id: item for item in contract.bindings}
    terminals = tuple(
        _make_terminal_outcome(
            contract,
            record_by_key[key],
            outcome_by_key[key],
            binding_by_id[key[0]],
        )
        for key in sorted(record_by_key)
    )
    if len({item.terminal_outcome_id for item in terminals}) != len(terminals):
        raise ValueError("runtime-resolution duplicates a terminal outcome")
    return terminals


def _make_terminal_outcome(
    contract: FinanceRuntimeResolutionContract,
    record: CapabilityBoundaryRolloutRecord,
    outcome: CapabilityRolloutOutcome,
    binding: RuntimeTaskBinding,
) -> RuntimeTerminalOutcome:
    prompt = _prompt_diagnostics(record)
    classification = _classify_terminal(
        record,
        outcome,
        prompt_pathology=bool(
            prompt["maximum_observation_summary_bytes"] > contract.maximum_observation_summary_bytes
            or prompt["maximum_public_context_bytes"] > contract.maximum_public_context_bytes
        ),
    )
    layer = classification[1]
    eligible = layer in {
        FailureLayer.L3_MODEL_PROTOCOL,
        FailureLayer.L4_MODEL_AGENT_DECISION,
        FailureLayer.L5_MODEL_SEMANTIC,
        FailureLayer.L6_SUCCESS,
    }
    observations = _record_observations(record)
    capability_outcomes = _capability_outcomes(binding, record, outcome, observations)
    api_resolved = bool(record.telemetry) and record.telemetry[-1].http_success
    runtime_pathology = bool(
        layer
        in {
            FailureLayer.L1_TASK_RUNTIME_CONTRACT,
            FailureLayer.L2_TOOL_ENVIRONMENT,
            FailureLayer.UNATTRIBUTED_MIXED,
        }
        or classification[5]
    )
    execution_integrity = bool(
        api_resolved
        and outcome.bounded_json_resolution_success
        and outcome.observation_replay_success
        and outcome.authority_integrity_success
        and layer
        not in {
            FailureLayer.L0_EXTERNAL_INFRASTRUCTURE,
            FailureLayer.L1_TASK_RUNTIME_CONTRACT,
            FailureLayer.L2_TOOL_ENVIRONMENT,
            FailureLayer.UNATTRIBUTED_MIXED,
        }
    )
    failed_observations = tuple(item for item in observations if item.status == "failed")
    identical_blocks = sum(
        item.error_code == "identical_failed_action_blocked" for item in failed_observations
    )
    values = {
        "contract_id": contract.contract_id,
        "stage": contract.stage,
        "record_id": record.record_id,
        "binding_id": record.binding_id,
        "task_artifact_id": record.task_artifact_id,
        "family": record.family,
        "tier": binding.tier,
        "runtime_arm": record.runtime_arm,
        "replicate": record.replicate,
        "terminal_class": classification[0],
        "primary_failure_layer": layer,
        "secondary_failure_layers": classification[2],
        "attribution_confidence": classification[3],
        "attribution_evidence": classification[4],
        "terminal_resolved": layer != FailureLayer.UNATTRIBUTED_MIXED,
        "failure_attributed": (
            layer == FailureLayer.L6_SUCCESS or layer != FailureLayer.UNATTRIBUTED_MIXED
        ),
        "runtime_eligible_for_capability_denominator": eligible,
        "runtime_pathology": runtime_pathology,
        "prompt_pathology": classification[5],
        "api_transport_resolved": api_resolved,
        "execution_integrity_passed": execution_integrity,
        "raw_json_contract_success": outcome.raw_json_contract_success,
        "bounded_json_resolution_success": outcome.bounded_json_resolution_success,
        "observation_replay_success": outcome.observation_replay_success,
        "authority_integrity_success": outcome.authority_integrity_success,
        "deterministic_valid": outcome.deterministic_valid,
        "semantic_answer_correct": outcome.semantic_answer_correct,
        "valid_success": outcome.valid_success,
        "capability_outcomes": capability_outcomes,
        "stop_rejection_count": _stop_rejection_count(record),
        "identical_failed_action_block_count": identical_blocks,
        "maximum_prompt_component_bytes": prompt["maximum_prompt_component_bytes"],
        "maximum_public_context_bytes": prompt["maximum_public_context_bytes"],
        "maximum_observation_summary_bytes": prompt["maximum_observation_summary_bytes"],
        "api_call_count": outcome.api_call_count,
        "total_model_tokens": outcome.total_model_tokens,
        "estimated_cost_usd": outcome.estimated_cost_usd,
        "error_type": record.error_type,
        "error_code": _terminal_error_code(record, classification[0]),
    }
    provisional = RuntimeTerminalOutcome.model_construct(terminal_outcome_id="pending", **values)
    return RuntimeTerminalOutcome(
        terminal_outcome_id=runtime_terminal_outcome_id(provisional), **values
    )


def _classify_terminal(
    record: CapabilityBoundaryRolloutRecord,
    outcome: CapabilityRolloutOutcome,
    *,
    prompt_pathology: bool,
) -> tuple[
    TerminalClass,
    FailureLayer,
    tuple[FailureLayer, ...],
    Literal["high", "medium", "low"],
    tuple[str, ...],
    bool,
]:
    evidence = [f"record:{record.record_id}"]
    if record.status == "completed":
        if outcome.valid_success:
            return (
                TerminalClass.SUCCESSFUL_ANSWER,
                FailureLayer.L6_SUCCESS,
                (),
                "high",
                (*evidence, "verifier:valid_success"),
                prompt_pathology,
            )
        failed_checks = _failed_verifier_checks(record)
        evidence.extend(f"verifier:{item}" for item in failed_checks[:8])
        return (
            TerminalClass.INVALID_ANSWER,
            FailureLayer.L5_MODEL_SEMANTIC,
            (),
            "high" if failed_checks else "medium",
            tuple(evidence or ("completed_invalid_answer",)),
            prompt_pathology,
        )

    message = (record.error_message or "").casefold()
    error_type = (record.error_type or "").casefold()
    observations = _record_observations(record)
    error_codes = tuple(item.error_code for item in observations if item.error_code is not None)
    evidence.extend(f"tool_error:{item}" for item in error_codes[-4:])
    if record.error_message:
        evidence.append(f"message:{_normalized_failure_code(record.error_message)}")
    provider_failure = bool(
        bool(record.telemetry)
        and (
            not record.telemetry[-1].http_success
            or record.telemetry[-1].http_status in {408, 429}
            or (record.telemetry[-1].http_status or 0) >= 500
        )
        or (
            record.failure_artifact is None
            and any(
                token in message
                for token in ("connection", "timeout", "rate limit", "provider unavailable")
            )
        )
        or (
            not record.telemetry
            and error_type in {"connectionerror", "timeouterror", "providererror", "httperror"}
        )
    )
    if provider_failure:
        return (
            TerminalClass.PROVIDER_FAILURE,
            FailureLayer.L0_EXTERNAL_INFRASTRUCTURE,
            (),
            "high",
            tuple(evidence),
            prompt_pathology,
        )
    if any(item.startswith("runtime_exception:") for item in error_codes):
        return (
            TerminalClass.TOOL_ENVIRONMENT_FAILURE,
            FailureLayer.L2_TOOL_ENVIRONMENT,
            (),
            "high",
            tuple(evidence),
            prompt_pathology,
        )
    if "agent tool result" in message and any(
        token in message for token in ("unknown fields", "lacks required fields")
    ):
        return (
            TerminalClass.TOOL_ENVIRONMENT_FAILURE,
            FailureLayer.L2_TOOL_ENVIRONMENT,
            (),
            "high",
            tuple(evidence),
            prompt_pathology,
        )
    if "observation" in message and "budget" in message:
        return (
            TerminalClass.OBSERVATION_BUDGET,
            FailureLayer.L1_TASK_RUNTIME_CONTRACT,
            (),
            "high",
            tuple(evidence),
            True,
        )
    if "model-token budget" in message:
        return (
            TerminalClass.MODEL_TOKEN_BUDGET,
            (
                FailureLayer.L1_TASK_RUNTIME_CONTRACT
                if prompt_pathology
                else FailureLayer.L4_MODEL_AGENT_DECISION
            ),
            ((FailureLayer.L4_MODEL_AGENT_DECISION,) if prompt_pathology else ()),
            "high",
            tuple(evidence),
            prompt_pathology,
        )
    if "stop-rejection budget" in message:
        return (
            TerminalClass.PREMATURE_STOP,
            FailureLayer.L4_MODEL_AGENT_DECISION,
            (),
            "high",
            tuple(evidence),
            prompt_pathology,
        )
    if any(
        token in message
        for token in (
            "failed-tool-call budget",
            "identical failed tool call",
            "identical failed action",
        )
    ):
        return (
            TerminalClass.DETERMINISTIC_RECOVERY_FAILURE,
            FailureLayer.L4_MODEL_AGENT_DECISION,
            (),
            "high",
            tuple(evidence),
            prompt_pathology,
        )
    if "tool-call budget" in message:
        return (
            TerminalClass.TOOL_CALL_BUDGET,
            FailureLayer.L4_MODEL_AGENT_DECISION,
            (),
            "high",
            tuple(evidence),
            prompt_pathology,
        )
    if any(token in message for token in ("unknown tool", "unavailable tool")):
        return (
            TerminalClass.UNAVAILABLE_TOOL,
            FailureLayer.L3_MODEL_PROTOCOL,
            (),
            "high",
            tuple(evidence),
            prompt_pathology,
        )
    if (
        any(token in message for token in ("json", "contract", "model failed the iterative agent"))
        and "valueerror" not in error_type
    ):
        return (
            TerminalClass.MODEL_CONTRACT_FAILURE,
            FailureLayer.L3_MODEL_PROTOCOL,
            (),
            "medium",
            tuple(evidence),
            prompt_pathology,
        )
    if error_type == "valueerror" and record.failure_artifact is None:
        return (
            TerminalClass.RUNTIME_CONTRACT_FAILURE,
            FailureLayer.L1_TASK_RUNTIME_CONTRACT,
            (),
            "medium",
            tuple(evidence),
            prompt_pathology,
        )
    if record.failure_artifact is not None:
        return (
            TerminalClass.DETERMINISTIC_RECOVERY_FAILURE,
            FailureLayer.L4_MODEL_AGENT_DECISION,
            (),
            "medium",
            tuple(evidence),
            prompt_pathology,
        )
    return (
        TerminalClass.UNKNOWN_FAILURE,
        FailureLayer.UNATTRIBUTED_MIXED,
        (),
        "low",
        tuple(evidence),
        prompt_pathology,
    )


def make_runtime_resolution_report(
    contract: FinanceRuntimeResolutionContract,
    terminals: tuple[RuntimeTerminalOutcome, ...],
) -> FinanceRuntimeResolutionReport:
    if len(terminals) != contract.requested_rollout_count:
        raise ValueError("runtime-resolution report lacks its complete denominator")
    metrics = _metrics(terminals)
    cells = tuple(
        _cell(terminals, family, tier, runtime)
        for family in CAPABILITY_SENSITIVE_FAMILIES
        for tier in DifficultyTier
        for runtime in WORKFLOW_RUNTIME_ARMS
    )
    thresholds = contract.thresholds
    gates = (
        _gate(
            "api_transport_resolution",
            metrics.api_transport_resolution_rate
            >= thresholds.minimum_api_transport_resolution_rate,
            metrics.api_transport_resolution_rate,
            f">={thresholds.minimum_api_transport_resolution_rate}",
            "execution_integrity",
        ),
        _gate(
            "bounded_json_resolution",
            metrics.bounded_json_resolution_rate >= thresholds.minimum_bounded_json_rate,
            metrics.bounded_json_resolution_rate,
            f">={thresholds.minimum_bounded_json_rate}",
            "execution_integrity",
        ),
        _gate(
            "observation_replay",
            metrics.observation_replay_rate >= thresholds.minimum_observation_replay_rate,
            metrics.observation_replay_rate,
            f">={thresholds.minimum_observation_replay_rate}",
            "execution_integrity",
        ),
        _gate(
            "authority_integrity",
            metrics.authority_integrity_rate >= thresholds.minimum_authority_integrity_rate,
            metrics.authority_integrity_rate,
            f">={thresholds.minimum_authority_integrity_rate}",
            "execution_integrity",
        ),
        _gate(
            "typed_terminal_resolution",
            metrics.terminal_resolution_rate >= thresholds.minimum_terminal_resolution_rate,
            metrics.terminal_resolution_rate,
            f">={thresholds.minimum_terminal_resolution_rate}",
            "terminal_resolution",
        ),
        _gate(
            "external_infrastructure_failure",
            metrics.external_infrastructure_failure_rate
            <= thresholds.maximum_external_failure_rate,
            metrics.external_infrastructure_failure_rate,
            f"<={thresholds.maximum_external_failure_rate}",
            "runtime_pathology",
        ),
        _gate(
            "task_runtime_contract_failure",
            metrics.task_runtime_contract_failure_rate
            <= thresholds.maximum_runtime_contract_failure_rate,
            metrics.task_runtime_contract_failure_rate,
            f"<={thresholds.maximum_runtime_contract_failure_rate}",
            "runtime_pathology",
        ),
        _gate(
            "tool_environment_failure",
            metrics.tool_environment_failure_rate
            <= thresholds.maximum_tool_environment_failure_rate,
            metrics.tool_environment_failure_rate,
            f"<={thresholds.maximum_tool_environment_failure_rate}",
            "runtime_pathology",
        ),
        _gate(
            "unattributed_failure",
            metrics.unattributed_failure_rate <= thresholds.maximum_unattributed_failure_rate,
            metrics.unattributed_failure_rate,
            f"<={thresholds.maximum_unattributed_failure_rate}",
            "runtime_pathology",
        ),
        _gate(
            "runtime_prompt_pathology",
            metrics.runtime_prompt_pathology_rate
            <= thresholds.maximum_runtime_prompt_pathology_rate,
            metrics.runtime_prompt_pathology_rate,
            f"<={thresholds.maximum_runtime_prompt_pathology_rate}",
            "runtime_pathology",
        ),
        _gate(
            "failure_attribution_coverage",
            metrics.failure_attribution_coverage_rate
            >= thresholds.minimum_failure_attribution_coverage_rate,
            metrics.failure_attribution_coverage_rate,
            f">={thresholds.minimum_failure_attribution_coverage_rate}",
            "failure_attribution",
        ),
        _gate(
            "non_saturated_valid_success_lower",
            metrics.valid_success_given_runtime_eligible >= thresholds.minimum_valid_success_rate,
            metrics.valid_success_given_runtime_eligible,
            f">={thresholds.minimum_valid_success_rate}",
            "capability_measurement",
        ),
        _gate(
            "non_saturated_valid_success_upper",
            metrics.valid_success_given_runtime_eligible <= thresholds.maximum_valid_success_rate,
            metrics.valid_success_given_runtime_eligible,
            f"<={thresholds.maximum_valid_success_rate}",
            "capability_measurement",
        ),
        _gate(
            "boundary_cell_fraction",
            metrics.boundary_cell_fraction >= thresholds.minimum_boundary_cell_fraction,
            metrics.boundary_cell_fraction,
            f">={thresholds.minimum_boundary_cell_fraction}",
            "capability_measurement",
        ),
    )
    category_pass = {
        category: all(item.passed for item in gates if item.category == category)
        for category in (
            "execution_integrity",
            "terminal_resolution",
            "runtime_pathology",
            "failure_attribution",
            "capability_measurement",
        )
    }
    runtime_passed = all(
        category_pass[item]
        for item in (
            "execution_integrity",
            "terminal_resolution",
            "runtime_pathology",
            "failure_attribution",
        )
    )
    joint_ready = runtime_passed and category_pass["capability_measurement"]
    information_authorized = bool(
        contract.stage == RuntimeResolutionStage.HELDOUT_CONFIRMATION and joint_ready
    )
    next_stage = _next_permitted_stage(
        stage=contract.stage,
        runtime_qualified=runtime_passed,
        capability_suitable=category_pass["capability_measurement"],
    )
    values = {
        "contract_id": contract.contract_id,
        "stage": contract.stage,
        "requested_rollout_count": contract.requested_rollout_count,
        "recorded_rollout_count": len(terminals),
        "metrics": metrics,
        "cells": cells,
        "gates": gates,
        "execution_integrity_passed": category_pass["execution_integrity"],
        "terminal_resolution_passed": category_pass["terminal_resolution"],
        "runtime_pathology_passed": category_pass["runtime_pathology"],
        "failure_attribution_passed": category_pass["failure_attribution"],
        "capability_measurement_suitable": category_pass["capability_measurement"],
        "runtime_qualification_passed": runtime_passed,
        "joint_stage_ready": joint_ready,
        "outcome_set_hash": canonical_hash(
            tuple(sorted(item.terminal_outcome_id for item in terminals)),
            prefix=f"finance_runtime_resolution_{contract.stage.value}_outcomes:",
        ),
        "api_call_count": metrics.api_call_count,
        "total_model_tokens": metrics.total_model_tokens,
        "estimated_cost_usd": metrics.estimated_cost_usd,
        "information_matrix_evaluation_authorized": information_authorized,
        "next_permitted_stage": next_stage,
    }
    provisional = FinanceRuntimeResolutionReport.model_construct(report_id="pending", **values)
    return FinanceRuntimeResolutionReport(
        report_id=runtime_resolution_report_id(provisional), **values
    )


def _metrics(terminals: Sequence[RuntimeTerminalOutcome]) -> RuntimeResolutionMetrics:
    if not terminals:
        raise ValueError("runtime-resolution metrics require outcomes")
    count = len(terminals)
    failures = tuple(
        item for item in terminals if item.primary_failure_layer != FailureLayer.L6_SUCCESS
    )
    eligible = tuple(item for item in terminals if item.runtime_eligible_for_capability_denominator)
    cells = {(item.family, item.tier, item.runtime_arm) for item in terminals}
    boundary_count = 0
    cell_probabilities = []
    for family, tier, runtime in cells:
        values = tuple(
            item
            for item in terminals
            if (item.family, item.tier, item.runtime_arm) == (family, tier, runtime)
        )
        probability = _conditional_valid_rate(values)
        cell_probabilities.append(probability)
        boundary_count += int(0 < probability < 1)
    capability_rates: dict[str, float | None] = {}
    capability_denominators: dict[str, int] = {}
    for axis in (*CAPABILITY_AXES, "semantic", "final_valid"):
        capability_values = tuple(
            item.capability_outcomes[axis] is True
            for item in terminals
            if item.runtime_eligible_for_capability_denominator
            and item.capability_outcomes[axis] is not None
        )
        capability_denominators[axis] = len(capability_values)
        capability_rates[axis] = (
            _rate(sum(capability_values), len(capability_values)) if capability_values else None
        )
    layer_counts = Counter(item.primary_failure_layer.value for item in terminals)
    terminal_counts = Counter(item.terminal_class.value for item in terminals)
    error_counts = Counter(item.error_code for item in terminals if item.error_code)
    tier_rates = {
        tier.value: _rate(
            sum(item.valid_success for item in terminals if item.tier == tier),
            sum(item.tier == tier for item in terminals),
        )
        for tier in DifficultyTier
    }
    runtime_rates = {
        runtime.value: _rate(
            sum(item.valid_success for item in terminals if item.runtime_arm == runtime),
            sum(item.runtime_arm == runtime for item in terminals),
        )
        for runtime in WORKFLOW_RUNTIME_ARMS
    }
    return RuntimeResolutionMetrics(
        attempted_count=count,
        terminal_outcome_count=count,
        api_transport_resolution_rate=_rate(
            sum(item.api_transport_resolved for item in terminals), count
        ),
        raw_json_contract_rate=_rate(
            sum(item.raw_json_contract_success for item in terminals), count
        ),
        bounded_json_resolution_rate=_rate(
            sum(item.bounded_json_resolution_success for item in terminals), count
        ),
        observation_replay_rate=_rate(
            sum(item.observation_replay_success for item in terminals), count
        ),
        authority_integrity_rate=_rate(
            sum(item.authority_integrity_success for item in terminals), count
        ),
        execution_integrity_rate=_rate(
            sum(item.execution_integrity_passed for item in terminals), count
        ),
        terminal_resolution_rate=_rate(sum(item.terminal_resolved for item in terminals), count),
        failure_attribution_coverage_rate=(
            _rate(sum(item.failure_attributed for item in failures), len(failures))
            if failures
            else 1.0
        ),
        external_infrastructure_failure_rate=_rate(
            layer_counts[FailureLayer.L0_EXTERNAL_INFRASTRUCTURE.value], count
        ),
        task_runtime_contract_failure_rate=_rate(
            layer_counts[FailureLayer.L1_TASK_RUNTIME_CONTRACT.value], count
        ),
        tool_environment_failure_rate=_rate(
            layer_counts[FailureLayer.L2_TOOL_ENVIRONMENT.value], count
        ),
        unattributed_failure_rate=_rate(layer_counts[FailureLayer.UNATTRIBUTED_MIXED.value], count),
        runtime_prompt_pathology_rate=_rate(
            sum(item.prompt_pathology for item in terminals), count
        ),
        runtime_eligible_count=len(eligible),
        semantic_accuracy_given_runtime_eligible=(
            _rate(sum(item.semantic_answer_correct for item in eligible), len(eligible))
            if eligible
            else 0.0
        ),
        valid_success_given_runtime_eligible=(
            _rate(sum(item.valid_success for item in eligible), len(eligible)) if eligible else 0.0
        ),
        end_to_end_semantic_accuracy=_rate(
            sum(item.semantic_answer_correct for item in terminals), count
        ),
        deterministic_valid_rate=_rate(sum(item.deterministic_valid for item in terminals), count),
        end_to_end_valid_success_rate=_rate(sum(item.valid_success for item in terminals), count),
        boundary_cell_fraction=_rate(boundary_count, len(cells)),
        success_entropy=round(
            sum(_binary_entropy(item) for item in cell_probabilities) / len(cell_probabilities),
            9,
        ),
        premature_stop_rate=_rate(terminal_counts[TerminalClass.PREMATURE_STOP.value], count),
        deterministic_recovery_failure_rate=_rate(
            terminal_counts[TerminalClass.DETERMINISTIC_RECOVERY_FAILURE.value], count
        ),
        identical_failed_action_block_rate=_rate(
            sum(item.identical_failed_action_block_count > 0 for item in terminals), count
        ),
        primary_failure_layer_counts=dict(sorted(layer_counts.items())),
        terminal_class_counts=dict(sorted(terminal_counts.items())),
        error_code_counts=dict(sorted(error_counts.items())),
        capability_axis_rates=capability_rates,
        capability_axis_denominators=capability_denominators,
        tier_valid_success_given_runtime_eligible={
            tier.value: _conditional_valid_rate(
                tuple(item for item in terminals if item.tier == tier)
            )
            for tier in DifficultyTier
        },
        runtime_valid_success_given_runtime_eligible={
            runtime.value: _conditional_valid_rate(
                tuple(item for item in terminals if item.runtime_arm == runtime)
            )
            for runtime in WORKFLOW_RUNTIME_ARMS
        },
        tier_end_to_end_valid_success_rates=tier_rates,
        runtime_end_to_end_valid_success_rates=runtime_rates,
        maximum_prompt_component_bytes=max(
            item.maximum_prompt_component_bytes for item in terminals
        ),
        maximum_public_context_bytes=max(item.maximum_public_context_bytes for item in terminals),
        maximum_observation_summary_bytes=max(
            item.maximum_observation_summary_bytes for item in terminals
        ),
        api_call_count=sum(item.api_call_count for item in terminals),
        total_model_tokens=sum(item.total_model_tokens for item in terminals),
        estimated_cost_usd=round(sum(item.estimated_cost_usd for item in terminals), 9),
    )


def _cell(
    terminals: Sequence[RuntimeTerminalOutcome],
    family: str,
    tier: DifficultyTier,
    runtime: CapabilityRuntimeArm,
) -> RuntimeResolutionCell:
    values = tuple(
        item
        for item in terminals
        if (item.family, item.tier, item.runtime_arm) == (family, tier, runtime)
    )
    if len(values) != REPLICAS:
        raise ValueError("runtime-resolution Cell lacks its frozen replicates")
    end_to_end_valid_rate = _rate(sum(item.valid_success for item in values), len(values))
    eligible = tuple(item for item in values if item.runtime_eligible_for_capability_denominator)
    conditional_valid_rate = _conditional_valid_rate(values)
    return RuntimeResolutionCell(
        family=family,
        tier=tier,
        runtime_arm=runtime,
        rollout_count=len(values),
        runtime_eligible_count=len(eligible),
        semantic_success_given_runtime_eligible=(
            _rate(sum(item.semantic_answer_correct for item in eligible), len(eligible))
            if eligible
            else 0.0
        ),
        valid_success_given_runtime_eligible=conditional_valid_rate,
        end_to_end_valid_success_rate=end_to_end_valid_rate,
        boundary_cell=0 < conditional_valid_rate < 1,
        primary_failure_layer_counts=dict(
            sorted(Counter(item.primary_failure_layer.value for item in values).items())
        ),
    )


def _conditional_valid_rate(terminals: Sequence[RuntimeTerminalOutcome]) -> float:
    eligible = tuple(item for item in terminals if item.runtime_eligible_for_capability_denominator)
    return _rate(sum(item.valid_success for item in eligible), len(eligible)) if eligible else 0.0


def _next_permitted_stage(
    *,
    stage: RuntimeResolutionStage,
    runtime_qualified: bool,
    capability_suitable: bool,
) -> Literal[
    "fresh_flash_runtime_confirmation",
    "flash_information_matrix_evaluation",
    "capability_support_redesign_only",
    "runtime_resolution_repair_only",
]:
    if not runtime_qualified:
        return "runtime_resolution_repair_only"
    if not capability_suitable:
        return "capability_support_redesign_only"
    if stage == RuntimeResolutionStage.RESIDUAL_DEVELOPMENT:
        return "fresh_flash_runtime_confirmation"
    return "flash_information_matrix_evaluation"


def _capability_outcomes(
    binding: RuntimeTaskBinding,
    record: CapabilityBoundaryRolloutRecord,
    outcome: CapabilityRolloutOutcome,
    observations: Sequence[Any],
) -> dict[str, bool | None]:
    successful = tuple(item for item in observations if item.status == "succeeded")
    tool_ids = {item.call.tool_id for item in successful}
    demanded = {
        axis: bool(RUNTIME_AXIS_RESPONSIBILITY[binding.runtime_arm][axis])
        for axis in CAPABILITY_AXES
    }
    values: dict[str, bool | None] = {
        "retrieval": bool(any(item.evidence_ids for item in successful)),
        "planning": (
            bool(record.status == "completed" and outcome.deterministic_valid)
            if demanded["planning"]
            else None
        ),
        "calculation": "calculator" in tool_ids,
        "reconciliation": "normalize_metric_unit_period" in tool_ids,
        "verification": outcome.verification_success,
        "recovery": outcome.recovery_success if outcome.recovery_opportunity else None,
        "stopping": outcome.stop_quality_success,
        "semantic": outcome.semantic_answer_correct,
        "final_valid": outcome.valid_success,
    }
    for axis in CAPABILITY_AXES:
        if not demanded[axis]:
            values[axis] = None
    return values


def _prompt_diagnostics(record: CapabilityBoundaryRolloutRecord) -> dict[str, int]:
    maximum_component = 0
    maximum_context = 0
    maximum_observations = 0
    for telemetry in record.telemetry:
        raw = telemetry.response_shape.get("prompt_component_bytes")
        if not isinstance(raw, Mapping):
            continue
        numeric = {
            str(key): int(value)
            for key, value in raw.items()
            if isinstance(value, int) and value >= 0
        }
        maximum_component = max(maximum_component, *(numeric.values() or (0,)))
        context_size = sum(
            value for key, value in numeric.items() if key.startswith("public_context.")
        )
        maximum_context = max(maximum_context, context_size)
        maximum_observations = max(
            maximum_observations,
            numeric.get("public_context.observations", 0),
        )
    return {
        "maximum_prompt_component_bytes": maximum_component,
        "maximum_public_context_bytes": maximum_context,
        "maximum_observation_summary_bytes": maximum_observations,
    }


def _record_observations(record: CapabilityBoundaryRolloutRecord) -> tuple[Any, ...]:
    if record.observations:
        return record.observations
    artifact = record.failure_artifact
    if isinstance(artifact, IterativeAgentFailureArtifact):
        return artifact.observations
    return ()


def _stop_rejection_count(record: CapabilityBoundaryRolloutRecord) -> int:
    if isinstance(record.failure_artifact, IterativeAgentFailureArtifact):
        return len(record.failure_artifact.stop_rejections)
    audit = record.agent_audit or {}
    raw = audit.get("stop_rejections", ())
    return len(raw) if isinstance(raw, (list, tuple)) else 0


def _failed_verifier_checks(record: CapabilityBoundaryRolloutRecord) -> tuple[str, ...]:
    payload = record.verification_payload or {}
    raw = payload.get("checks", ())
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(
        str(item.get("check_id", "unknown"))
        for item in raw
        if isinstance(item, Mapping) and item.get("passed") is False
    )


def _terminal_error_code(
    record: CapabilityBoundaryRolloutRecord,
    terminal_class: TerminalClass,
) -> str | None:
    if terminal_class == TerminalClass.SUCCESSFUL_ANSWER:
        return None
    observations = _record_observations(record)
    errors = tuple(item.error_code for item in observations if item.error_code)
    if errors:
        return str(errors[-1])
    if record.error_message:
        return _normalized_failure_code(record.error_message)
    return terminal_class.value


def _normalized_failure_code(message: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", message.casefold()).strip("_")
    return value[:120] or "unknown_failure"


def _binary_entropy(probability: float) -> float:
    if probability <= 0 or probability >= 1:
        return 0.0
    return -(probability * math.log(probability) + (1 - probability) * math.log(1 - probability))


def _gate(
    gate_id: str,
    passed: bool,
    observed: float,
    requirement: str,
    category: Literal[
        "execution_integrity",
        "terminal_resolution",
        "runtime_pathology",
        "failure_attribution",
        "capability_measurement",
    ],
) -> RuntimeResolutionGate:
    return RuntimeResolutionGate(
        gate_id=gate_id,
        passed=passed,
        observed=round(float(observed), 9),
        requirement=requirement,
        category=category,
    )


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        raise ValueError("rate denominator must be positive")
    return round(numerator / denominator, 9)


def _group_ids_by_family(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("source group manifest must be an object")
    output = {str(key): str(item) for key, item in value.items()}
    if set(output) != set(CAPABILITY_SENSITIVE_FAMILIES):
        raise ValueError("source group manifest omits a capability family")
    return output


def _group_evidence_sets(
    groups: Sequence[MatchedLadderGroup],
) -> tuple[set[str], set[str]]:
    evidence_ids = {
        evidence.evidence_id
        for group in groups
        for task in group.variants
        for evidence in task.public_corpus.evidence
    }
    version_ids = {
        evidence.evidence_version_id
        for group in groups
        for task in group.variants
        for evidence in task.public_corpus.evidence
    }
    return evidence_ids, version_ids


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        Path(__file__).resolve(),
        root / "src/trusted_synthesis/runtime/agent/iterative.py",
        root / "src/trusted_synthesis/runtime/tools.py",
        root / "src/trusted_synthesis/domains/finance/agent_tools.py",
        root / "src/trusted_synthesis/domains/finance/interactive_agent_runtime.py",
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_multitier_capability_population.py"
        ),
        root / "src/trusted_synthesis/experiments/vtdo_experiment/phase1_multitier_confirmation.py",
    )
    return {str(path.relative_to(root)): _sha256(path) for path in paths}


def _verify_frozen_inputs(contract: FinanceRuntimeResolutionContract) -> None:
    pairs = (
        (contract.source_population_path, contract.source_population_sha256),
        (
            contract.source_confirmation_contract_path,
            contract.source_confirmation_contract_sha256,
        ),
        (contract.source_v25_16_contract_path, contract.source_v25_16_contract_sha256),
        (contract.source_v25_16_report_path, contract.source_v25_16_report_sha256),
        (contract.finance_archive_config_path, contract.finance_archive_config_sha256),
    )
    for path_value, expected in pairs:
        if _sha256(Path(path_value)) != expected:
            raise ValueError(f"runtime-resolution frozen input changed:{path_value}")
    optional = (
        (
            contract.prior_development_contract_path,
            contract.prior_development_contract_sha256,
        ),
        (contract.prior_development_report_path, contract.prior_development_report_sha256),
    )
    for optional_path, optional_expected in optional:
        if optional_path is not None and (
            optional_expected is None or _sha256(Path(optional_path)) != optional_expected
        ):
            raise ValueError(f"runtime-resolution prior artifact changed:{optional_path}")
    manifest = _implementation_manifest()
    if manifest != contract.implementation_manifest:
        raise ValueError("runtime-resolution implementation changed after contract freeze")
    population = MultiTierCapabilityPopulation.model_validate_json(
        Path(contract.source_population_path).read_text(encoding="utf-8")
    )
    if population.population_id != contract.source_population_id:
        raise ValueError("runtime-resolution source population identity changed")


def _load_records(path: Path) -> tuple[CapabilityBoundaryRolloutRecord, ...]:
    return tuple(
        CapabilityBoundaryRolloutRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"expected JSON object:{path}")
    return raw


def _write_jsonl_atomic(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rollout_identity_key(binding_id: str, replicate: int) -> str:
    return f"{binding_id}|{replicate}"


def runtime_resolution_contract_id(value: FinanceRuntimeResolutionContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_runtime_resolution_contract:",
    )


def runtime_terminal_outcome_id(value: RuntimeTerminalOutcome) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"terminal_outcome_id"}),
        prefix="finance_runtime_terminal_outcome:",
    )


def runtime_resolution_report_id(value: FinanceRuntimeResolutionReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_runtime_resolution_report:",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare and run the v25.17 Flash runtime-resolution experiment."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--stage", type=RuntimeResolutionStage, required=True)
    prepare.add_argument("--source-population", type=Path, required=True)
    prepare.add_argument("--source-confirmation-contract", type=Path, required=True)
    prepare.add_argument("--source-v25-16-contract", type=Path, required=True)
    prepare.add_argument("--source-v25-16-report", type=Path, required=True)
    prepare.add_argument("--finance-archive-config", type=Path, required=True)
    prepare.add_argument("--prior-development-contract", type=Path)
    prepare.add_argument("--prior-development-report", type=Path)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--selection-salt", required=True)
    run = commands.add_parser("run")
    run.add_argument("--contract", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--workers", type=int, default=24)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        contract = prepare_runtime_resolution_contract(
            stage=args.stage,
            source_population_path=args.source_population,
            source_confirmation_contract_path=args.source_confirmation_contract,
            source_v25_16_contract_path=args.source_v25_16_contract,
            source_v25_16_report_path=args.source_v25_16_report,
            finance_archive_config_path=args.finance_archive_config,
            output_path=args.output,
            run_id=args.run_id,
            selection_salt=args.selection_salt,
            prior_development_contract_path=args.prior_development_contract,
            prior_development_report_path=args.prior_development_report,
        )
        print(
            json.dumps(
                {
                    "contract_id": contract.contract_id,
                    "stage": contract.stage.value,
                    "task_count": len(contract.tasks),
                    "binding_count": len(contract.bindings),
                    "rollout_count": contract.requested_rollout_count,
                    "freshness": contract.freshness.model_dump(mode="json"),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    report = run_runtime_resolution_stage(
        contract_path=args.contract,
        output_dir=args.output_dir,
        workers=args.workers,
    )
    print(
        json.dumps(
            {
                "report_id": report.report_id,
                "stage": report.stage.value,
                "runtime_qualification_passed": report.runtime_qualification_passed,
                "capability_measurement_suitable": report.capability_measurement_suitable,
                "joint_stage_ready": report.joint_stage_ready,
                "next_permitted_stage": report.next_permitted_stage,
                "metrics": report.metrics.model_dump(mode="json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
