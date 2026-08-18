from __future__ import annotations

import argparse
import hashlib
import json
import threading
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.executable_task import StaticModelAuthorityPathCatalog
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingHardeningReport,
    AuthorityPreservingTaskAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_role_protocol import (  # noqa: E501
    EmpiricalRoleProtocolReport,
    ReachabilityJobDesign,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    CapabilityMechanismSummary,
    CapabilityTaskSummary,
    EmpiricalPilotRollout,
    EmpiricalStateSupportFreeze,
    StateReachabilitySummary,
    aggregate_capability_mechanisms,
    aggregate_capability_tasks,
    aggregate_state_reachability,
    freeze_empirical_state_support,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_runner import (  # noqa: E501
    _run_one,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_capability_population import (  # noqa: E501
    FreshCapabilityPopulationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_operation_closure_regression import (  # noqa: E501
    _PRIVATE_PROMPT_FIELD_NAMES,
    _failed_observation_counts,
    _observations,
    _premature_verification,
    _raw_payload,
    _repair_prompt_counts,
    _semantic_progress_projection_passed,
    _stop_decision_readiness,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    TARGET_MECHANISMS,
    OperationalTaskAdmission,
    OperationalTaskRecord,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import OpenAICompatibleJsonClient
from trusted_synthesis.runtime.agent.public_operation import public_operation_progress
from trusted_synthesis.runtime.agent.schema import AgentModelConfig
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest

V26_ROLE_RUNNER_CONTRACT_VERSION = "finance_v26_authority_preserving_role_contract.v1"
V26_ROLE_RUNNER_JOB_VERSION = "finance_v26_authority_preserving_role_job.v1"
V26_ROLE_RUNNER_MANIFEST_VERSION = "finance_v26_authority_preserving_role_manifest.v1"
V26_ROLE_RUNNER_PREFLIGHT_VERSION = "finance_v26_authority_preserving_role_preflight.v1"
V26_ROLE_ROLLOUT_DIAGNOSTIC_VERSION = "finance_v26_authority_preserving_role_diagnostic.v1"
V26_ROLE_RAW_AUDIT_VERSION = "finance_v26_authority_preserving_role_raw_audit.v1"
V26_ROLE_RUNNER_REPORT_VERSION = "finance_v26_authority_preserving_role_report.v1"

CAPABILITY_TASK_COUNT: Literal[12] = 12
CAPABILITY_ROLLOUTS_PER_TASK: Literal[8] = 8
CAPABILITY_JOB_COUNT: Literal[96] = 96
REACHABILITY_TASK_COUNT: Literal[12] = 12
NATURAL_ROLLOUTS_PER_TASK: Literal[12] = 12
CONDITIONED_ROLLOUTS_PER_STATE: Literal[6] = 6
REACHABILITY_JOB_COUNT: Literal[360] = 360
MAXIMUM_MODEL_TOKENS_PER_ROLLOUT: Literal[120000] = 120_000
CAPABILITY_COST_CEILING_USD = 8.0
REACHABILITY_COST_CEILING_USD = 25.0
DEFAULT_WORKERS = 24

IMPLEMENTATION_SOURCE_PATHS = (
    "src/trusted_synthesis/core/trajectory/public_operation.py",
    "src/trusted_synthesis/domains/finance/executable_support_runtime.py",
    "src/trusted_synthesis/domains/finance/public_tool_results.py",
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_authority_preserving_operation_hardening.py"
    ),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_authority_preserving_role_runner.py"
    ),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_role_protocol.py"),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_support_pilot.py"),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_support_runner.py"),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_capability_population.py"),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_operation_closure_regression.py"
    ),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_public_operation_rematerialization.py"
    ),
    "src/trusted_synthesis/runtime/agent/iterative.py",
    "src/trusted_synthesis/runtime/agent/public_operation.py",
)

EmpiricalRole = Literal["capability_development", "state_reachability"]
SamplingMode = Literal[
    "capability_unconditional",
    "reachability_unconditional",
    "reachability_conditioned",
]
PathStrategy = Literal["structured_direct", "search_then_structured", "search_then_open"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RoleSourceFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class RoleImplementationSource(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)


class AuthorityPreservingRoleContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    role: EmpiricalRole
    task_source_report_id: str = Field(min_length=1)
    task_source_report_sha256: str = Field(min_length=64, max_length=64)
    protocol_source_report_id: str | None = None
    protocol_source_report_sha256: str | None = None
    source_protocol_id: str | None = None
    source_reachability_scope_id: str | None = None
    source_artifact_files: tuple[RoleSourceFile, ...] = Field(min_length=6)
    task_record_ids: tuple[str, ...] = Field(min_length=12, max_length=12)
    task_package_ids: tuple[str, ...] = Field(min_length=12, max_length=12)
    mechanism_task_counts: dict[str, int]
    static_state_ids: tuple[str, ...] = Field(max_length=36)
    source_design_job_ids: tuple[str, ...] = Field(min_length=96, max_length=360)
    expected_job_count: Literal[96, 360]
    model_id: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    fallback_models: tuple[str, ...] = ()
    require_requested_model: Literal[True] = True
    model_invocation_config: dict[str, Any]
    model_config_hash: str = Field(min_length=1)
    provider_route: dict[str, str]
    provider_route_hash: str = Field(min_length=1)
    verifier_manifest: dict[str, Any]
    verifier_manifest_hash: str = Field(min_length=1)
    mapper_manifest: dict[str, Any]
    mapper_manifest_hash: str = Field(min_length=1)
    condition_manifest: dict[str, Any]
    condition_manifest_hash: str = Field(min_length=1)
    maximum_total_model_tokens_per_rollout: Literal[120000] = MAXIMUM_MODEL_TOKENS_PER_ROLLOUT
    maximum_total_estimated_cost_usd: float = Field(gt=0.0, le=25.0)
    raw_first_provider_and_prompt_telemetry: Literal[True] = True
    source_replay_before_client_construction: Literal[True] = True
    exact_manifest_before_client_construction: Literal[True] = True
    action_neutral_repair_audit_per_rollout: Literal[True] = True
    terminal_target_audit_per_rollout: Literal[True] = True
    independently_valid_model_trajectories_only_in_state_mapping: Literal[True] = True
    invalid_model_outcomes_retained: Literal[True] = True
    compiler_witnesses_excluded: Literal[True] = True
    capability_and_reachability_denominators_separate: Literal[True] = True
    implementation_source_files: tuple[RoleImplementationSource, ...] = Field(
        min_length=13, max_length=13
    )
    schema_version: str = V26_ROLE_RUNNER_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> AuthorityPreservingRoleContract:
        groups = (
            self.task_record_ids,
            self.task_package_ids,
            self.static_state_ids,
            self.source_design_job_ids,
        )
        if any(group != tuple(sorted(set(group))) for group in groups):
            raise ValueError("role contract identity sets are not canonical")
        if self.mechanism_task_counts != {mechanism: 3 for mechanism in TARGET_MECHANISMS}:
            raise ValueError("role contract mechanism quotas changed")
        if self.model_invocation_config.get("model") != self.model_id:
            raise ValueError("role contract model identity changed")
        if tuple(self.model_invocation_config.get("fallback_models", ())) != self.fallback_models:
            raise ValueError("role contract fallback policy changed")
        if self.model_invocation_config.get("require_requested_model") is not True:
            raise ValueError("role contract does not fail closed on model mismatch")
        manifests = (
            ("model", self.model_invocation_config, self.model_config_hash),
            ("provider", self.provider_route, self.provider_route_hash),
            ("verifier", self.verifier_manifest, self.verifier_manifest_hash),
            ("mapper", self.mapper_manifest, self.mapper_manifest_hash),
            ("condition", self.condition_manifest, self.condition_manifest_hash),
        )
        for label, payload, observed in manifests:
            if observed != canonical_hash(payload, prefix=f"finance_v26_authority_role_{label}:"):
                raise ValueError(f"role contract {label} manifest hash is invalid")
        if tuple(item.relative_path for item in self.implementation_source_files) != tuple(
            sorted(IMPLEMENTATION_SOURCE_PATHS)
        ):
            raise ValueError("role runner implementation manifest is incomplete")
        reachability = self.role == "state_reachability"
        if reachability:
            if (
                self.expected_job_count != REACHABILITY_JOB_COUNT
                or len(self.static_state_ids) != 36
                or len(self.source_design_job_ids) != REACHABILITY_JOB_COUNT
                or not all(
                    (
                        self.protocol_source_report_id,
                        self.protocol_source_report_sha256,
                        self.source_protocol_id,
                        self.source_reachability_scope_id,
                    )
                )
            ):
                raise ValueError("reachability contract source lineage is incomplete")
        elif (
            self.expected_job_count != CAPABILITY_JOB_COUNT
            or self.static_state_ids
            or len(self.source_design_job_ids) != CAPABILITY_JOB_COUNT
            or any(
                (
                    self.protocol_source_report_id,
                    self.protocol_source_report_sha256,
                    self.source_protocol_id,
                    self.source_reachability_scope_id,
                )
            )
        ):
            raise ValueError("capability contract contains Reachability lineage")
        if self.contract_id != authority_preserving_role_contract_id(self):
            raise ValueError("authority-preserving role contract identity is invalid")
        return self


class AuthorityPreservingRoleJob(FrozenModel):
    job_id: str = Field(min_length=1)
    source_design_job_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    role: EmpiricalRole
    task_record_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    intended_use: Literal["capability_measurement", "vtdo_multistate_candidate"]
    sampling_mode: SamplingMode
    replicate_index: int = Field(ge=0, lt=12)
    requested_static_path_id: str | None = None
    requested_path_strategy: PathStrategy | None = None
    requested_quotient_state_id: str | None = None
    public_condition_id: str | None = None
    schema_version: str = V26_ROLE_RUNNER_JOB_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> AuthorityPreservingRoleJob:
        conditioned = self.sampling_mode == "reachability_conditioned"
        condition_values = (
            self.requested_static_path_id,
            self.requested_path_strategy,
            self.requested_quotient_state_id,
            self.public_condition_id,
        )
        if conditioned != all(value is not None for value in condition_values):
            raise ValueError("role job condition identities are incomplete or extraneous")
        if not conditioned and any(value is not None for value in condition_values):
            raise ValueError("unconditional role job carries a state target")
        if self.role == "capability_development":
            if (
                self.intended_use != "capability_measurement"
                or self.sampling_mode != "capability_unconditional"
                or self.replicate_index >= CAPABILITY_ROLLOUTS_PER_TASK
            ):
                raise ValueError("capability role job has the wrong role or denominator")
        elif self.intended_use != "vtdo_multistate_candidate" or self.sampling_mode == (
            "capability_unconditional"
        ):
            raise ValueError("Reachability job has the wrong empirical role")
        elif conditioned and self.replicate_index >= CONDITIONED_ROLLOUTS_PER_STATE:
            raise ValueError("conditioned role job exceeds its denominator")
        if self.job_id != authority_preserving_role_job_id(self):
            raise ValueError("authority-preserving role job identity is invalid")
        return self


class AuthorityPreservingRoleJobManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    role: EmpiricalRole
    jobs: tuple[AuthorityPreservingRoleJob, ...] = Field(min_length=96, max_length=360)
    schema_version: str = V26_ROLE_RUNNER_MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> AuthorityPreservingRoleJobManifest:
        if any(
            item.contract_id != self.contract_id or item.role != self.role for item in self.jobs
        ):
            raise ValueError("role manifest crosses contracts or roles")
        identities = tuple(item.job_id for item in self.jobs)
        designs = tuple(item.source_design_job_id for item in self.jobs)
        if identities != tuple(sorted(set(identities))) or len(designs) != len(set(designs)):
            raise ValueError("role manifest identities are not canonical")
        expected = (
            CAPABILITY_JOB_COUNT
            if self.role == "capability_development"
            else REACHABILITY_JOB_COUNT
        )
        if len(self.jobs) != expected:
            raise ValueError("role manifest denominator changed")
        task_counts = Counter(item.task_package_id for item in self.jobs)
        if self.role == "capability_development":
            if len(task_counts) != 12 or set(task_counts.values()) != {8}:
                raise ValueError("capability manifest task denominators changed")
        else:
            modes = Counter(item.sampling_mode for item in self.jobs)
            if modes != Counter(
                {"reachability_unconditional": 144, "reachability_conditioned": 216}
            ):
                raise ValueError("Reachability manifest mode denominators changed")
        if self.manifest_id != authority_preserving_role_manifest_id(self):
            raise ValueError("authority-preserving role manifest identity is invalid")
        return self


class AuthorityPreservingPreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    role: EmpiricalRole
    expected_job_count: Literal[96, 360]
    source_file_replay_pass_count: int = Field(ge=6)
    source_file_count: int = Field(ge=6)
    task_runtime_binding_pass_count: Literal[12] = 12
    repair_contract_binding_pass_count: Literal[12] = 12
    terminal_target_binding_pass_count: Literal[12] = 12
    verifier_binding_pass_count: Literal[12] = 12
    source_design_binding_pass_count: Literal[96, 360]
    public_condition_noninterference_pass_count: Literal[0, 216]
    raw_first_path_collision_count: Literal[0] = 0
    historical_job_identity_overlap_count: Literal[0] = 0
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = V26_ROLE_RUNNER_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> AuthorityPreservingPreflightAudit:
        if self.source_file_replay_pass_count != self.source_file_count:
            raise ValueError("role preflight source replay is incomplete")
        expected = (
            CAPABILITY_JOB_COUNT
            if self.role == "capability_development"
            else REACHABILITY_JOB_COUNT
        )
        if self.expected_job_count != expected or self.source_design_binding_pass_count != expected:
            raise ValueError("role preflight source design denominator changed")
        condition_count = 0 if self.role == "capability_development" else 216
        if self.public_condition_noninterference_pass_count != condition_count:
            raise ValueError("role preflight condition audit is incomplete")
        if self.audit_id != authority_preserving_preflight_audit_id(self):
            raise ValueError("authority-preserving preflight identity is invalid")
        return self


class AuthorityPreservingRolloutDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    source_design_job_id: str = Field(min_length=1)
    rollout_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    sampling_mode: SamplingMode
    replicate_index: int = Field(ge=0, lt=12)
    terminal_category: str = Field(min_length=1)
    exact_requested_model: bool
    fallback_used: bool
    required_node_count: int = Field(ge=1)
    completed_node_count: int = Field(ge=0)
    full_program_lineage_completed: bool
    terminal_node_completed: bool
    postterminal_verification_completed: bool
    stop_ready: bool
    premature_verification_observed: bool
    postcompletion_violation: bool
    final_answer_before_stop_ready_rejected: bool
    stop_ready_false_positive: bool
    stop_ready_false_negative: bool
    independent_validity: bool
    public_contract_in_initial_prompt: bool
    decision_prompt_observed: bool
    public_progress_projection_passed: bool
    initial_prompt_private_identity_free: bool
    authority_contract_in_initial_prompt: bool
    terminal_target_in_initial_prompt: bool
    repair_prompt_count: int = Field(ge=0)
    action_bearing_repair_prompt_count: int = Field(ge=0)
    failed_observation_count: int = Field(ge=0)
    action_bearing_failed_observation_count: int = Field(ge=0)
    repair_prompts_action_neutral: bool
    failed_observations_action_neutral: bool
    condition_noninterference_passed: bool
    state_mapping_eligible: bool
    path_assignment_present: bool
    schema_version: str = V26_ROLE_ROLLOUT_DIAGNOSTIC_VERSION

    @model_validator(mode="after")
    def validate_diagnostic(self) -> AuthorityPreservingRolloutDiagnostic:
        if self.completed_node_count > self.required_node_count:
            raise ValueError("role diagnostic completed more than the required nodes")
        if self.full_program_lineage_completed != (
            self.completed_node_count == self.required_node_count
        ):
            raise ValueError("role diagnostic full-lineage flag is inconsistent")
        if self.repair_prompts_action_neutral != (
            self.action_bearing_repair_prompt_count == 0
        ) or self.failed_observations_action_neutral != (
            self.action_bearing_failed_observation_count == 0
        ):
            raise ValueError("role diagnostic action-neutrality flags are inconsistent")
        expected_mapping = self.independent_validity and self.sampling_mode != (
            "capability_unconditional"
        )
        if self.state_mapping_eligible != expected_mapping:
            raise ValueError("role diagnostic permits mapping without independent validity")
        if self.path_assignment_present and not self.state_mapping_eligible:
            raise ValueError("role diagnostic maps an invalid trajectory")
        if self.diagnostic_id != authority_preserving_rollout_diagnostic_id(self):
            raise ValueError("authority-preserving rollout diagnostic identity is invalid")
        return self


class AuthorityPreservingRawIntegrityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    role: EmpiricalRole
    expected_rollout_count: Literal[96, 360]
    observed_rollout_count: int = Field(ge=0, le=360)
    byte_hash_pass_count: int = Field(ge=0, le=360)
    identity_pass_count: int = Field(ge=0, le=360)
    prompt_hash_pass_count: int = Field(ge=0, le=360)
    recursive_noninterference_pass_count: int = Field(ge=0, le=360)
    condition_noninterference_pass_count: int = Field(ge=0, le=360)
    authority_contract_pass_count: int = Field(ge=0, le=360)
    terminal_target_pass_count: int = Field(ge=0, le=360)
    repair_neutrality_pass_count: int = Field(ge=0, le=360)
    provider_call_ids_unique: bool
    duplicate_provider_call_ids: tuple[str, ...] = ()
    failed_artifacts: tuple[str, ...] = ()
    status: Literal["passed", "partial", "failed"]
    schema_version: str = V26_ROLE_RAW_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> AuthorityPreservingRawIntegrityAudit:
        expected = (
            CAPABILITY_JOB_COUNT
            if self.role == "capability_development"
            else REACHABILITY_JOB_COUNT
        )
        if self.expected_rollout_count != expected:
            raise ValueError("role raw audit expected denominator changed")
        counts = (
            self.byte_hash_pass_count,
            self.identity_pass_count,
            self.prompt_hash_pass_count,
            self.recursive_noninterference_pass_count,
            self.condition_noninterference_pass_count,
            self.authority_contract_pass_count,
            self.terminal_target_pass_count,
            self.repair_neutrality_pass_count,
        )
        complete = self.observed_rollout_count == expected and all(
            item == expected for item in counts
        )
        partial = all(item == self.observed_rollout_count for item in counts)
        status = (
            "passed"
            if complete and self.provider_call_ids_unique and not self.failed_artifacts
            else "partial"
            if partial and self.provider_call_ids_unique and not self.failed_artifacts
            else "failed"
        )
        if self.status != status:
            raise ValueError("role raw audit status is inconsistent")
        if self.audit_id != authority_preserving_raw_integrity_audit_id(self):
            raise ValueError("authority-preserving raw audit identity is invalid")
        return self


class AuthorityPreservingRoleReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    role: EmpiricalRole
    contract_id: str = Field(min_length=1)
    job_manifest_id: str = Field(min_length=1)
    preflight_audit: AuthorityPreservingPreflightAudit
    discovered_models: tuple[str, ...]
    completed_rollout_count: int = Field(ge=0, le=360)
    sampling_mode_counts: dict[str, int]
    terminal_counts: dict[str, int]
    provider_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    estimated_cost_usd: str = Field(min_length=1)
    raw_integrity_audit: AuthorityPreservingRawIntegrityAudit
    diagnostics: tuple[AuthorityPreservingRolloutDiagnostic, ...]
    capability_task_summaries: tuple[CapabilityTaskSummary, ...] = ()
    capability_mechanism_summaries: tuple[CapabilityMechanismSummary, ...] = ()
    state_reachability_summaries: tuple[StateReachabilitySummary, ...] = ()
    state_support_freeze: EmpiricalStateSupportFreeze | None = None
    model_outcome_count: int = Field(ge=0, le=360)
    runtime_failure_count: int = Field(ge=0, le=360)
    instrument_failure_count: int = Field(ge=0, le=360)
    independently_valid_trajectory_count: int = Field(ge=0, le=360)
    mapped_valid_trajectory_count: int = Field(ge=0, le=360)
    full_program_lineage_count: int = Field(ge=0, le=360)
    terminal_node_completion_count: int = Field(ge=0, le=360)
    postterminal_verification_count: int = Field(ge=0, le=360)
    repair_prompt_count: int = Field(ge=0)
    action_bearing_repair_prompt_count: int = Field(ge=0)
    failed_observation_count: int = Field(ge=0)
    action_bearing_failed_observation_count: int = Field(ge=0)
    stop_ready_false_positive_count: int = Field(ge=0, le=360)
    stop_ready_false_negative_count: int = Field(ge=0, le=360)
    resource_budget_passed: bool
    instrument_ready: bool
    compiler_witness_empirical_count: Literal[0] = 0
    historical_outcomes_reused: Literal[False] = False
    status: Literal["preflight", "partial", "passed", "blocked"]
    next_permitted_stage: Literal[
        "frozen_role_model_execution_only",
        "frozen_role_execution_resume_only",
        "capability_postrun_read_only_audit_only",
        "reachability_postrun_read_only_audit_only",
        "authority_preserving_runner_repair_only",
        "resource_budget_audit_only",
    ]
    model_execution_authorized: bool
    capability_development_complete: bool
    state_reachability_complete: bool
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_ROLE_RUNNER_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> AuthorityPreservingRoleReport:
        if sum(self.terminal_counts.values()) != self.completed_rollout_count:
            raise ValueError("role report terminal denominator is incomplete")
        if len(self.diagnostics) != self.completed_rollout_count:
            raise ValueError("role report diagnostic denominator is incomplete")
        if self.preflight_audit.contract_id != self.contract_id or (
            self.preflight_audit.manifest_id != self.job_manifest_id
        ):
            raise ValueError("role report crosses preflight identities")
        expected_model_outcomes = sum(
            item.terminal_category in {"model_valid_trajectory", "model_invalid_trajectory"}
            for item in self.diagnostics
        )
        if self.model_outcome_count != expected_model_outcomes:
            raise ValueError("role report model-outcome denominator is inconsistent")
        capability = self.role == "capability_development"
        if capability:
            if self.state_reachability_summaries or self.state_support_freeze is not None:
                raise ValueError("capability report contains state-support results")
        elif self.capability_task_summaries or self.capability_mechanism_summaries:
            raise ValueError("Reachability report contains capability summaries")
        if self.model_execution_authorized != (self.status == "preflight"):
            raise ValueError("role report execution authorization is inconsistent")
        if self.report_id != authority_preserving_role_report_id(self):
            raise ValueError("authority-preserving role report identity is invalid")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_count(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return len(payload) if isinstance(payload, list) else 1


def _write_json_atomic(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"role runner immutable JSON changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def _append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def _source_file(path: Path, package_root: Path) -> RoleSourceFile:
    return RoleSourceFile(
        relative_path=str(path.resolve().relative_to(package_root.resolve())),
        sha256=_sha256(path),
        record_count=_record_count(path),
    )


def _implementation_sources(package_root: Path) -> tuple[RoleImplementationSource, ...]:
    return tuple(
        RoleImplementationSource(relative_path=value, sha256=_sha256(package_root / value))
        for value in sorted(IMPLEMENTATION_SOURCE_PATHS)
    )


def _replay_report_artifacts(source_dir: Path, descriptors: Sequence[Any]) -> None:
    for item in descriptors:
        path = source_dir / item.relative_path
        if (
            not path.is_file()
            or _sha256(path) != item.sha256
            or _record_count(path) != item.record_count
        ):
            raise ValueError(f"role runner source Artifact replay failed: {path}")


def _load_models(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    return tuple(
        model.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))
    )


def _validate_task_bundle(
    *,
    role: EmpiricalRole,
    records: Sequence[OperationalTaskRecord],
    environments: Sequence[AgentToolEnvironmentManifest],
    catalogs: Sequence[StaticModelAuthorityPathCatalog],
    admissions: Sequence[OperationalTaskAdmission],
    audits: Sequence[AuthorityPreservingTaskAudit],
) -> None:
    if not (
        len(records) == len(environments) == len(catalogs) == len(admissions) == len(audits) == 12
    ):
        raise ValueError("role runner task bundle cardinality changed")
    environment_by_id = {item.manifest_id: item for item in environments}
    catalog_by_task = {item.task_package_id: item for item in catalogs}
    admission_by_task = {item.task_package_id: item for item in admissions}
    audit_by_task = {item.task_package_id: item for item in audits}
    if not all(
        len(item) == 12
        for item in (environment_by_id, catalog_by_task, admission_by_task, audit_by_task)
    ):
        raise ValueError("role runner source identities are duplicated")
    expected_use = (
        "capability_measurement"
        if role == "capability_development"
        else "vtdo_multistate_candidate"
    )
    for record in records:
        package = record.task_package
        if record.intended_use != expected_use:
            raise ValueError("role runner task carries another intended use")
        environment = environment_by_id.get(record.environment_manifest_id)
        if (
            environment is None
            or canonical_hash(environment, prefix="finance_v26_executable_environment:")
            != record.environment_manifest_hash
        ):
            raise ValueError("role runner task Runtime environment binding changed")
        if (
            package.public_runtime_contract.environment_manifest_hash
            != record.environment_manifest_hash
        ):
            raise ValueError("role runner public Runtime hash changed")
        if package.action_neutral_repair_contract is None:
            raise ValueError("role runner task lacks the v3 repair contract")
        if package.terminal_verification_target is None:
            raise ValueError("role runner task lacks the unified terminal target")
        verifier = package.verifier_binding
        if (
            verifier.action_neutral_repair_contract_id
            != package.action_neutral_repair_contract.contract_id
            or verifier.terminal_verification_target_id
            != package.terminal_verification_target.target_id
            or verifier.operation_contract_id != package.operation_contract.contract_id
            or verifier.public_runtime_contract_id != package.public_runtime_contract.contract_id
        ):
            raise ValueError("role runner Verifier binding changed")
        audit = audit_by_task[package.package_id]
        if (
            audit.status != "passed"
            or audit.repair_prompt_audit.status != "passed"
            or audit.terminal_verification_target_id
            != package.terminal_verification_target.target_id
        ):
            raise ValueError("role runner authority audit is incomplete")
        catalog = catalog_by_task[package.package_id]
        admission = admission_by_task[package.package_id]
        if role == "capability_development":
            if (
                catalog.status != "not_required"
                or catalog.paths
                or not admission.operational_capability_eligible
                or admission.operational_vtdo_candidate_eligible
            ):
                raise ValueError("capability task static admission changed")
        elif (
            catalog.status != "passed"
            or len(catalog.paths) != 3
            or not admission.operational_vtdo_candidate_eligible
        ):
            raise ValueError("Reachability task static admission changed")


def _capability_designs(
    report: FreshCapabilityPopulationReport,
    records: Sequence[OperationalTaskRecord],
) -> tuple[dict[str, Any], ...]:
    output = []
    for record in sorted(records, key=lambda item: item.task_package.package_id):
        for replicate in range(CAPABILITY_ROLLOUTS_PER_TASK):
            values = {
                "source_report_id": report.report_id,
                "task_record_id": record.record_id,
                "task_package_id": record.task_package.package_id,
                "mechanism_id": record.mechanism_id,
                "sampling_mode": "capability_unconditional",
                "replicate_index": replicate,
            }
            output.append(
                {
                    **values,
                    "source_design_job_id": canonical_hash(
                        values,
                        prefix="finance_v26_fresh_capability_job_design:",
                    ),
                }
            )
    return tuple(sorted(output, key=lambda item: str(item["source_design_job_id"])))


def _load_role_inputs(
    *,
    role: EmpiricalRole,
    task_source_dir: Path,
    protocol_source_dir: Path | None,
    package_root: Path,
) -> tuple[
    str,
    str,
    tuple[OperationalTaskRecord, ...],
    tuple[AgentToolEnvironmentManifest, ...],
    tuple[StaticModelAuthorityPathCatalog, ...],
    tuple[OperationalTaskAdmission, ...],
    tuple[AuthorityPreservingTaskAudit, ...],
    tuple[RoleSourceFile, ...],
    tuple[dict[str, Any] | ReachabilityJobDesign, ...],
    EmpiricalRoleProtocolReport | None,
]:
    if role == "capability_development":
        report_path = task_source_dir / "report.json"
        report = FreshCapabilityPopulationReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
        if report.status != "passed" or not report.role_runner_preflight_authorized:
            raise ValueError("fresh Capability Population does not authorize runner preflight")
        _replay_report_artifacts(task_source_dir, report.immutable_artifact_files)
        all_records = tuple(report.task_records)
        designs: tuple[dict[str, Any] | ReachabilityJobDesign, ...] = _capability_designs(
            report, all_records
        )
        descriptors = tuple(report.immutable_artifact_files)
        protocol_report = None
        report_id = report.report_id
    else:
        if protocol_source_dir is None:
            raise ValueError("Reachability runner requires the frozen v26.68 protocol")
        report_path = task_source_dir / "report.json"
        report65 = AuthorityPreservingHardeningReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
        _replay_report_artifacts(task_source_dir, report65.immutable_artifact_files)
        protocol_path = protocol_source_dir / "report.json"
        protocol_report = EmpiricalRoleProtocolReport.model_validate_json(
            protocol_path.read_text(encoding="utf-8")
        )
        if (
            protocol_report.next_permitted_stage
            != "fresh_capability_population_and_authority_preserving_reachability_runner_only"
            or protocol_report.protocol.task_source_report_id != report65.report_id
            or protocol_report.protocol.task_source_report_sha256 != _sha256(report_path)
            or protocol_report.protocol.reachability_api_exposed_task_count != 0
        ):
            raise ValueError("v26.68 Reachability source lineage changed")
        protocol_files = {
            "report.json": 1,
            "protocol.json": 1,
            "reachability_job_design.json": REACHABILITY_JOB_COUNT,
            "task_exposure_audits.json": 24,
        }
        for relative, expected in protocol_files.items():
            path = protocol_source_dir / relative
            if not path.is_file() or _record_count(path) != expected:
                raise ValueError(f"v26.68 protocol Artifact changed: {relative}")
        all_records = tuple(
            item
            for item in report65.task_records
            if item.intended_use == "vtdo_multistate_candidate"
        )
        designs = tuple(protocol_report.protocol.reachability_jobs)
        descriptors = tuple(report65.immutable_artifact_files)
        report_id = report65.report_id

    record_ids = {item.record_id for item in all_records}
    environments = tuple(
        item
        for item in _load_models(
            task_source_dir / "tool_environment_manifests.json", AgentToolEnvironmentManifest
        )
        if item.manifest_id in {record.environment_manifest_id for record in all_records}
    )
    catalogs = tuple(
        item
        for item in _load_models(
            task_source_dir / "static_model_authority_path_catalogs.json",
            StaticModelAuthorityPathCatalog,
        )
        if item.task_package_id in {record.task_package.package_id for record in all_records}
    )
    admissions = tuple(
        item
        for item in _load_models(
            task_source_dir / "operational_task_admissions.json", OperationalTaskAdmission
        )
        if item.task_package_id in {record.task_package.package_id for record in all_records}
    )
    audits = tuple(
        item
        for item in _load_models(
            task_source_dir / "authority_preserving_task_audits.json",
            AuthorityPreservingTaskAudit,
        )
        if item.task_package_id in {record.task_package.package_id for record in all_records}
    )
    if {item.record_id for item in all_records} != record_ids:
        raise ValueError("role runner source task identities are duplicated")
    _validate_task_bundle(
        role=role,
        records=all_records,
        environments=environments,
        catalogs=catalogs,
        admissions=admissions,
        audits=audits,
    )
    source_paths = [task_source_dir / "report.json"]
    source_paths.extend(task_source_dir / item.relative_path for item in descriptors)
    if protocol_source_dir is not None and role == "state_reachability":
        source_paths.extend(
            protocol_source_dir / relative
            for relative in (
                "report.json",
                "protocol.json",
                "reachability_job_design.json",
                "task_exposure_audits.json",
            )
        )
    source_files = tuple(
        sorted(
            (_source_file(path, package_root) for path in source_paths),
            key=lambda item: item.relative_path,
        )
    )
    return (
        report_id,
        _sha256(report_path),
        tuple(sorted(all_records, key=lambda item: item.record_id)),
        tuple(sorted(environments, key=lambda item: item.manifest_id)),
        tuple(sorted(catalogs, key=lambda item: item.catalog_id)),
        tuple(sorted(admissions, key=lambda item: item.admission_id)),
        tuple(sorted(audits, key=lambda item: item.audit_id)),
        source_files,
        designs,
        protocol_report,
    )


def _condition_payload_is_public(value: Mapping[str, Any]) -> bool:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True).casefold()
    return not any(
        marker in serialized
        for marker in (
            "state_id",
            "path_id",
            "compiler_witness",
            "gold_evidence",
            "hidden_program",
            "action_sequence",
            "tool_sequence",
            "evidence:finance:",
        )
    )


def build_authority_preserving_role_contract(
    *,
    run_id: str,
    role: EmpiricalRole,
    task_source_dir: Path,
    protocol_source_dir: Path | None,
    model_config: AgentModelConfig,
    package_root: Path,
) -> tuple[
    AuthorityPreservingRoleContract,
    tuple[OperationalTaskRecord, ...],
    tuple[AgentToolEnvironmentManifest, ...],
    tuple[StaticModelAuthorityPathCatalog, ...],
    tuple[dict[str, Any] | ReachabilityJobDesign, ...],
]:
    (
        task_report_id,
        task_report_sha256,
        records,
        environments,
        catalogs,
        _,
        _,
        source_files,
        designs,
        protocol_report,
    ) = _load_role_inputs(
        role=role,
        task_source_dir=task_source_dir,
        protocol_source_dir=protocol_source_dir,
        package_root=package_root,
    )
    public_model = model_config.model_dump(mode="json")
    endpoint = urlparse(model_config.endpoint)
    provider_route = {
        "provider": model_config.provider,
        "endpoint_host": endpoint.netloc,
        "model": model_config.model,
    }
    verifier_manifest = {
        "task_verifier_binding_ids": tuple(
            sorted(item.task_package.verifier_binding.binding_id for item in records)
        ),
        "verifier_versions": tuple(
            sorted({item.task_package.verifier_binding.verifier_version for item in records})
        ),
        "public_runtime_contract_ids": tuple(
            sorted(item.task_package.public_runtime_contract.contract_id for item in records)
        ),
        "action_neutral_repair_contract_ids": tuple(
            sorted(
                cast(Any, item.task_package.action_neutral_repair_contract).contract_id
                for item in records
            )
        ),
        "terminal_verification_target_ids": tuple(
            sorted(
                cast(Any, item.task_package.terminal_verification_target).target_id
                for item in records
            )
        ),
        "terminal_claim_shape": {"operation_ref": "terminal_operation_ref"},
        "additional_terminal_claim_fields": "forbidden",
        "complete_invalid_outcomes_retained": True,
    }
    mapper_manifest: dict[str, Any]
    condition_manifest: dict[str, Any]
    if role == "capability_development":
        mapper_manifest = {
            "state_mapping": "forbidden",
            "reason": "capability and Reachability empirical roles are separate",
        }
        condition_manifest = {
            "sampling": "unconditional_only",
            "public_condition_count": 0,
        }
        static_states: tuple[str, ...] = ()
        protocol_report_id = protocol_report_sha256 = protocol_id = reachability_scope_id = None
        maximum_cost = CAPABILITY_COST_CEILING_USD
    else:
        if protocol_report is None:
            raise ValueError("Reachability contract lost the v26.68 protocol")
        protocol = protocol_report.protocol
        mapper_manifest = {
            "eligible_input": "independently_valid_model_generated_trajectory_only",
            "classification_precedence": (
                "successful_open_document_before_first_calculation",
                "successful_search_archive_before_first_calculation",
                "successful_query_structured_fact_before_first_calculation",
            ),
            "state_identity_source": "frozen_v26_65_static_catalog",
            "compiler_witness_counted": False,
            "natural_and_conditioned_hits_separate": True,
        }
        condition_manifest = {
            "conditions": tuple(
                item.model_dump(mode="json") for item in protocol.public_conditions
            ),
            "conditioned_job_count": 216,
            "public_payloads_action_neutral": all(
                _condition_payload_is_public(item.public_payload)
                for item in protocol.public_conditions
            ),
        }
        if not condition_manifest["public_payloads_action_neutral"]:
            raise ValueError("Reachability public condition exposes a private identity")
        static_states = tuple(protocol.source_static_state_ids)
        protocol_report_id = protocol_report.report_id
        protocol_report_sha256 = _sha256(cast(Path, protocol_source_dir) / "report.json")
        protocol_id = protocol.protocol_id
        reachability_scope_id = protocol.reachability_job_scope_id
        maximum_cost = REACHABILITY_COST_CEILING_USD
    source_design_ids = tuple(
        sorted(
            str(item["source_design_job_id"] if isinstance(item, dict) else item.job_id)
            for item in designs
        )
    )
    values = {
        "run_id": run_id,
        "role": role,
        "task_source_report_id": task_report_id,
        "task_source_report_sha256": task_report_sha256,
        "protocol_source_report_id": protocol_report_id,
        "protocol_source_report_sha256": protocol_report_sha256,
        "source_protocol_id": protocol_id,
        "source_reachability_scope_id": reachability_scope_id,
        "source_artifact_files": source_files,
        "task_record_ids": tuple(sorted(item.record_id for item in records)),
        "task_package_ids": tuple(sorted(item.task_package.package_id for item in records)),
        "mechanism_task_counts": {
            mechanism: sum(item.mechanism_id == mechanism for item in records)
            for mechanism in TARGET_MECHANISMS
        },
        "static_state_ids": static_states,
        "source_design_job_ids": source_design_ids,
        "expected_job_count": (
            CAPABILITY_JOB_COUNT if role == "capability_development" else REACHABILITY_JOB_COUNT
        ),
        "model_invocation_config": public_model,
        "model_config_hash": canonical_hash(
            public_model, prefix="finance_v26_authority_role_model:"
        ),
        "provider_route": provider_route,
        "provider_route_hash": canonical_hash(
            provider_route, prefix="finance_v26_authority_role_provider:"
        ),
        "verifier_manifest": verifier_manifest,
        "verifier_manifest_hash": canonical_hash(
            verifier_manifest, prefix="finance_v26_authority_role_verifier:"
        ),
        "mapper_manifest": mapper_manifest,
        "mapper_manifest_hash": canonical_hash(
            mapper_manifest, prefix="finance_v26_authority_role_mapper:"
        ),
        "condition_manifest": condition_manifest,
        "condition_manifest_hash": canonical_hash(
            condition_manifest, prefix="finance_v26_authority_role_condition:"
        ),
        "maximum_total_estimated_cost_usd": maximum_cost,
        "implementation_source_files": _implementation_sources(package_root),
    }
    provisional = AuthorityPreservingRoleContract.model_construct(contract_id="pending", **values)
    contract = AuthorityPreservingRoleContract(
        contract_id=authority_preserving_role_contract_id(provisional),
        **values,
    )
    return contract, records, environments, catalogs, designs


def build_authority_preserving_role_manifest(
    contract: AuthorityPreservingRoleContract,
    records: Sequence[OperationalTaskRecord],
    designs: Sequence[dict[str, Any] | ReachabilityJobDesign],
) -> AuthorityPreservingRoleJobManifest:
    record_by_id = {item.record_id: item for item in records}
    jobs = []
    for design in designs:
        if isinstance(design, dict):
            source_design_id = str(design["source_design_job_id"])
            task_record_id = str(design["task_record_id"])
            sampling_mode = cast(SamplingMode, design["sampling_mode"])
            replicate_index = int(design["replicate_index"])
            requested_static_path_id = None
            requested_path_strategy = None
            requested_quotient_state_id = None
            public_condition_id = None
        else:
            source_design_id = design.job_id
            task_record_id = design.task_record_id
            sampling_mode = cast(SamplingMode, design.sampling_mode)
            replicate_index = design.replicate_index
            requested_static_path_id = design.requested_static_path_id
            requested_path_strategy = cast(PathStrategy | None, design.requested_path_strategy)
            requested_quotient_state_id = design.requested_quotient_state_id
            public_condition_id = design.public_condition_id
        record = record_by_id.get(task_record_id)
        if record is None:
            raise ValueError("role design refers to a foreign task record")
        values = {
            "source_design_job_id": source_design_id,
            "contract_id": contract.contract_id,
            "role": contract.role,
            "task_record_id": record.record_id,
            "task_package_id": record.task_package.package_id,
            "mechanism_id": record.mechanism_id,
            "intended_use": record.intended_use,
            "sampling_mode": sampling_mode,
            "replicate_index": replicate_index,
            "requested_static_path_id": requested_static_path_id,
            "requested_path_strategy": requested_path_strategy,
            "requested_quotient_state_id": requested_quotient_state_id,
            "public_condition_id": public_condition_id,
        }
        provisional = AuthorityPreservingRoleJob.model_construct(job_id="pending", **values)
        jobs.append(
            AuthorityPreservingRoleJob(
                job_id=authority_preserving_role_job_id(provisional),
                **values,
            )
        )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    if (
        tuple(sorted(item.source_design_job_id for item in ordered))
        != contract.source_design_job_ids
    ):
        raise ValueError("role manifest does not preserve the frozen source design")
    values = {"contract_id": contract.contract_id, "role": contract.role, "jobs": ordered}
    provisional = AuthorityPreservingRoleJobManifest.model_construct(
        manifest_id="pending", **values
    )
    return AuthorityPreservingRoleJobManifest(
        manifest_id=authority_preserving_role_manifest_id(provisional),
        **values,
    )


def _raw_relative_path(job: AuthorityPreservingRoleJob) -> str:
    task_hash = hashlib.sha256(job.task_package_id.encode()).hexdigest()[:16]
    state = job.requested_path_strategy or "unconditional"
    return str(
        Path("raw")
        / job.sampling_mode
        / task_hash
        / state
        / f"replicate_{job.replicate_index}.json"
    )


def build_authority_preserving_preflight_audit(
    contract: AuthorityPreservingRoleContract,
    manifest: AuthorityPreservingRoleJobManifest,
    records: Sequence[OperationalTaskRecord],
) -> AuthorityPreservingPreflightAudit:
    raw_paths = tuple(_raw_relative_path(item) for item in manifest.jobs)
    if len(raw_paths) != len(set(raw_paths)):
        raise ValueError("role preflight raw-first Artifact paths collide")
    conditioned = tuple(
        item for item in manifest.jobs if item.sampling_mode == "reachability_conditioned"
    )
    if not all(
        cast(str, item.requested_static_path_id) not in json.dumps(contract.condition_manifest)
        and cast(str, item.requested_quotient_state_id)
        not in json.dumps(contract.condition_manifest)
        for item in conditioned
    ):
        raise ValueError("role preflight public condition leaks a target identity")
    values = {
        "contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "role": contract.role,
        "expected_job_count": contract.expected_job_count,
        "source_file_replay_pass_count": len(contract.source_artifact_files),
        "source_file_count": len(contract.source_artifact_files),
        "source_design_binding_pass_count": len(manifest.jobs),
        "public_condition_noninterference_pass_count": len(conditioned),
    }
    if len(records) != 12:
        raise ValueError("role preflight task denominator changed")
    provisional = AuthorityPreservingPreflightAudit.model_construct(audit_id="pending", **values)
    return AuthorityPreservingPreflightAudit(
        audit_id=authority_preserving_preflight_audit_id(provisional),
        **values,
    )


def build_authority_preserving_role_execution_inputs(
    *,
    run_id: str,
    role: EmpiricalRole,
    task_source_dir: Path,
    protocol_source_dir: Path | None,
    model_config: AgentModelConfig,
    package_root: Path,
) -> tuple[
    AuthorityPreservingRoleContract,
    AuthorityPreservingRoleJobManifest,
    AuthorityPreservingPreflightAudit,
    tuple[OperationalTaskRecord, ...],
    tuple[AgentToolEnvironmentManifest, ...],
    tuple[StaticModelAuthorityPathCatalog, ...],
]:
    contract, records, environments, catalogs, designs = build_authority_preserving_role_contract(
        run_id=run_id,
        role=role,
        task_source_dir=task_source_dir,
        protocol_source_dir=protocol_source_dir,
        model_config=model_config,
        package_root=package_root,
    )
    manifest = build_authority_preserving_role_manifest(contract, records, designs)
    preflight = build_authority_preserving_preflight_audit(contract, manifest, records)
    return contract, manifest, preflight, records, environments, catalogs


def _diagnostic(
    rollout: EmpiricalPilotRollout,
    job: AuthorityPreservingRoleJob,
    record: OperationalTaskRecord,
) -> AuthorityPreservingRolloutDiagnostic:
    payload = _raw_payload(rollout)
    observations = _observations(payload)
    progress = public_operation_progress(record.task_package.task.public, observations)
    if progress is None:
        raise ValueError("role rollout lost its public Operation contract")
    prompts = tuple(str(item) for item in payload["actual_model_request_prompts"])
    initial = prompts[0] if prompts else ""
    decision_prompts = tuple(item for item in prompts if '"operation_execution_progress"' in item)
    repair_prompt_count, action_bearing_repair_prompt_count = _repair_prompt_counts(prompts)
    failed_observation_count, action_bearing_failed_observation_count = _failed_observation_counts(
        observations
    )
    stop_rows = _stop_decision_readiness(record, payload)
    early_stop_rejected = any(
        rejected and not stop_ready for _, rejected, stop_ready, _ in stop_rows
    )
    false_positive = any(accepted and not stop_ready for accepted, _, stop_ready, _ in stop_rows)
    false_negative = any(
        stop_gate_rejection and stop_ready for _, _, stop_ready, stop_gate_rejection in stop_rows
    )
    package = record.task_package
    private_values = (
        *record.target_program_evidence_ids,
        package.semantic_source.semantic_source_id,
        package.verifier_binding.binding_id,
        package.verifier_binding.source_program_dag_hash,
        package.verifier_binding.source_verifier_dag_hash,
    )
    independent_validity = bool(rollout.verification and rollout.verification.valid)
    values = {
        "source_design_job_id": job.source_design_job_id,
        "rollout_id": rollout.rollout_id,
        "job_id": rollout.job_id,
        "task_package_id": rollout.task_package_id,
        "mechanism_id": rollout.mechanism_id,
        "sampling_mode": rollout.sampling_mode,
        "replicate_index": rollout.replicate_index,
        "terminal_category": rollout.terminal_category,
        "exact_requested_model": rollout.exact_requested_model,
        "fallback_used": rollout.fallback_used,
        "required_node_count": len(package.stop_readiness_contract.required_node_ids),
        "completed_node_count": len(progress["completed_node_ids"]),
        "full_program_lineage_completed": bool(progress["all_steps_completed"]),
        "terminal_node_completed": bool(progress["terminal_node_completed"]),
        "postterminal_verification_completed": bool(
            progress["verification_after_terminal_completed"]
        ),
        "stop_ready": bool(progress["stop_ready"]),
        "premature_verification_observed": _premature_verification(record, observations),
        "postcompletion_violation": bool(progress["postcompletion_violation"]),
        "final_answer_before_stop_ready_rejected": early_stop_rejected,
        "stop_ready_false_positive": false_positive,
        "stop_ready_false_negative": false_negative,
        "independent_validity": independent_validity,
        "public_contract_in_initial_prompt": "public_operation_execution_contract" in initial,
        "decision_prompt_observed": bool(decision_prompts),
        "public_progress_projection_passed": all(
            _semantic_progress_projection_passed(item) for item in decision_prompts
        ),
        "initial_prompt_private_identity_free": bool(initial)
        and all(str(value) not in initial for value in private_values)
        and all(f'"{field}"' not in initial for field in _PRIVATE_PROMPT_FIELD_NAMES),
        "authority_contract_in_initial_prompt": (
            "public_action_neutral_repair_contract" in initial
            and "public_terminal_verification_target" in initial
        ),
        "terminal_target_in_initial_prompt": (
            '"public_terminal_verification_target"' in initial
            and '"additional_claim_fields_policy":"forbid"' in initial
            and '"terminal_reference_field":"operation_ref"' in initial
        ),
        "repair_prompt_count": repair_prompt_count,
        "action_bearing_repair_prompt_count": action_bearing_repair_prompt_count,
        "failed_observation_count": failed_observation_count,
        "action_bearing_failed_observation_count": action_bearing_failed_observation_count,
        "repair_prompts_action_neutral": action_bearing_repair_prompt_count == 0,
        "failed_observations_action_neutral": action_bearing_failed_observation_count == 0,
        "condition_noninterference_passed": rollout.condition_noninterference_passed,
        "state_mapping_eligible": independent_validity
        and rollout.sampling_mode != "capability_unconditional",
        "path_assignment_present": rollout.path_assignment is not None,
    }
    provisional = AuthorityPreservingRolloutDiagnostic.model_construct(
        diagnostic_id="pending", **values
    )
    return AuthorityPreservingRolloutDiagnostic(
        diagnostic_id=authority_preserving_rollout_diagnostic_id(provisional),
        **values,
    )


def _raw_integrity_audit(
    *,
    role: EmpiricalRole,
    rollouts: Sequence[EmpiricalPilotRollout],
    diagnostics: Sequence[AuthorityPreservingRolloutDiagnostic],
    manifest: AuthorityPreservingRoleJobManifest,
) -> AuthorityPreservingRawIntegrityAudit:
    job_by_id = {item.job_id: item for item in manifest.jobs}
    diagnostic_by_job = {item.job_id: item for item in diagnostics}
    byte_pass = identity_pass = prompt_pass = recursive_pass = condition_pass = 0
    authority_pass = target_pass = repair_pass = 0
    failures = []
    provider_ids = []
    for rollout in rollouts:
        try:
            payload = _raw_payload(rollout)
            byte_pass += 1
            job = job_by_id[rollout.job_id]
            diagnostic = diagnostic_by_job[rollout.job_id]
            raw_job = payload["job"]
            if (
                payload["contract_id"] == rollout.contract_id
                and raw_job["job_id"] == rollout.job_id
                and raw_job["source_design_job_id"] == job.source_design_job_id
                and payload["task_package_id"] == rollout.task_package_id
                and payload["terminal_category"] == rollout.terminal_category
                and tuple(payload["provider_call_ids"]) == rollout.provider_call_ids
            ):
                identity_pass += 1
            else:
                raise ValueError("role raw identity mismatch")
            prompts = tuple(str(item) for item in payload["actual_model_request_prompts"])
            hashes = tuple(hashlib.sha256(item.encode()).hexdigest() for item in prompts)
            if hashes == rollout.actual_prompt_hashes:
                prompt_pass += 1
            else:
                raise ValueError("role raw Prompt hash mismatch")
            if payload["recursive_noninterference_passed"] is True and (
                rollout.recursive_noninterference_passed
            ):
                recursive_pass += 1
            else:
                raise ValueError("role raw recursive noninterference mismatch")
            if payload["condition_noninterference_passed"] is True and (
                diagnostic.condition_noninterference_passed
            ):
                condition_pass += 1
            else:
                raise ValueError("role raw condition noninterference mismatch")
            if diagnostic.authority_contract_in_initial_prompt and (
                diagnostic.initial_prompt_private_identity_free
            ):
                authority_pass += 1
            else:
                raise ValueError("role raw authority contract audit failed")
            if diagnostic.terminal_target_in_initial_prompt:
                target_pass += 1
            else:
                raise ValueError("role raw terminal target audit failed")
            if diagnostic.repair_prompts_action_neutral and (
                diagnostic.failed_observations_action_neutral
            ):
                repair_pass += 1
            else:
                raise ValueError("role raw repair-neutrality audit failed")
            provider_ids.extend(rollout.provider_call_ids)
        except Exception:
            failures.append(rollout.raw_artifact_uri)
    duplicates = tuple(sorted(key for key, count in Counter(provider_ids).items() if count > 1))
    expected = CAPABILITY_JOB_COUNT if role == "capability_development" else REACHABILITY_JOB_COUNT
    counts = (
        byte_pass,
        identity_pass,
        prompt_pass,
        recursive_pass,
        condition_pass,
        authority_pass,
        target_pass,
        repair_pass,
    )
    complete = len(rollouts) == expected and all(item == expected for item in counts)
    partial = all(item == len(rollouts) for item in counts)
    values = {
        "role": role,
        "expected_rollout_count": expected,
        "observed_rollout_count": len(rollouts),
        "byte_hash_pass_count": byte_pass,
        "identity_pass_count": identity_pass,
        "prompt_hash_pass_count": prompt_pass,
        "recursive_noninterference_pass_count": recursive_pass,
        "condition_noninterference_pass_count": condition_pass,
        "authority_contract_pass_count": authority_pass,
        "terminal_target_pass_count": target_pass,
        "repair_neutrality_pass_count": repair_pass,
        "provider_call_ids_unique": not duplicates,
        "duplicate_provider_call_ids": duplicates,
        "failed_artifacts": tuple(sorted(failures)),
        "status": (
            "passed"
            if complete and not duplicates and not failures
            else "partial"
            if partial and not duplicates and not failures
            else "failed"
        ),
    }
    provisional = AuthorityPreservingRawIntegrityAudit.model_construct(audit_id="pending", **values)
    return AuthorityPreservingRawIntegrityAudit(
        audit_id=authority_preserving_raw_integrity_audit_id(provisional),
        **values,
    )


def _make_report(
    *,
    contract: AuthorityPreservingRoleContract,
    manifest: AuthorityPreservingRoleJobManifest,
    preflight: AuthorityPreservingPreflightAudit,
    discovered_models: tuple[str, ...],
    rollouts: tuple[EmpiricalPilotRollout, ...],
    diagnostics: tuple[AuthorityPreservingRolloutDiagnostic, ...],
    raw_audit: AuthorityPreservingRawIntegrityAudit,
    records: tuple[OperationalTaskRecord, ...],
    catalogs: tuple[StaticModelAuthorityPathCatalog, ...],
    preflight_only: bool = False,
) -> AuthorityPreservingRoleReport:
    expected = contract.expected_job_count
    complete = len(rollouts) == expected
    capability_tasks: tuple[CapabilityTaskSummary, ...] = ()
    capability_mechanisms: tuple[CapabilityMechanismSummary, ...] = ()
    state_summaries: tuple[StateReachabilitySummary, ...] = ()
    support_freeze: EmpiricalStateSupportFreeze | None = None
    if complete and contract.role == "capability_development":
        capability_tasks = aggregate_capability_tasks(rollouts)
        capability_mechanisms = aggregate_capability_mechanisms(capability_tasks)
    if complete and contract.role == "state_reachability":
        state_summaries = aggregate_state_reachability(rollouts, catalogs)
        support_freeze = freeze_empirical_state_support(
            cast(Any, contract), state_summaries, cast(Any, records)
        )
    total_cost = sum((Decimal(item.estimated_cost_usd) for item in rollouts), Decimal("0"))
    resource_ok = total_cost <= Decimal(str(contract.maximum_total_estimated_cost_usd))
    terminal_counts = Counter(item.terminal_category for item in rollouts)
    instrument_ok = bool(
        complete
        and raw_audit.status == "passed"
        and terminal_counts["runtime_failure"] == 0
        and terminal_counts["instrument_failure"] == 0
        and all(item.exact_requested_model and not item.fallback_used for item in rollouts)
        and all(
            item.public_contract_in_initial_prompt
            and item.public_progress_projection_passed
            and item.initial_prompt_private_identity_free
            and item.authority_contract_in_initial_prompt
            and item.terminal_target_in_initial_prompt
            and item.repair_prompts_action_neutral
            and item.failed_observations_action_neutral
            and item.condition_noninterference_passed
            and not item.stop_ready_false_positive
            and not item.stop_ready_false_negative
            for item in diagnostics
        )
    )
    if preflight_only:
        status: Literal["preflight", "partial", "passed", "blocked"] = "preflight"
        next_stage = "frozen_role_model_execution_only"
    elif not complete:
        status = "partial"
        next_stage = "frozen_role_execution_resume_only"
    elif not resource_ok:
        status = "blocked"
        next_stage = "resource_budget_audit_only"
    elif not instrument_ok:
        status = "blocked"
        next_stage = "authority_preserving_runner_repair_only"
    else:
        status = "passed"
        next_stage = (
            "capability_postrun_read_only_audit_only"
            if contract.role == "capability_development"
            else "reachability_postrun_read_only_audit_only"
        )
    values = {
        "run_id": contract.run_id,
        "role": contract.role,
        "contract_id": contract.contract_id,
        "job_manifest_id": manifest.manifest_id,
        "preflight_audit": preflight,
        "discovered_models": discovered_models,
        "completed_rollout_count": len(rollouts),
        "sampling_mode_counts": dict(
            sorted(Counter(item.sampling_mode for item in rollouts).items())
        ),
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "provider_call_count": sum(item.provider_call_count for item in rollouts),
        "provider_total_tokens": sum(item.provider_total_tokens for item in rollouts),
        "estimated_cost_usd": str(total_cost),
        "raw_integrity_audit": raw_audit,
        "diagnostics": diagnostics,
        "capability_task_summaries": capability_tasks,
        "capability_mechanism_summaries": capability_mechanisms,
        "state_reachability_summaries": state_summaries,
        "state_support_freeze": support_freeze,
        "model_outcome_count": sum(
            item.terminal_category in {"model_valid_trajectory", "model_invalid_trajectory"}
            for item in diagnostics
        ),
        "runtime_failure_count": terminal_counts["runtime_failure"],
        "instrument_failure_count": terminal_counts["instrument_failure"],
        "independently_valid_trajectory_count": sum(
            item.independent_validity for item in diagnostics
        ),
        "mapped_valid_trajectory_count": sum(item.path_assignment_present for item in diagnostics),
        "full_program_lineage_count": sum(
            item.full_program_lineage_completed for item in diagnostics
        ),
        "terminal_node_completion_count": sum(item.terminal_node_completed for item in diagnostics),
        "postterminal_verification_count": sum(
            item.postterminal_verification_completed for item in diagnostics
        ),
        "repair_prompt_count": sum(item.repair_prompt_count for item in diagnostics),
        "action_bearing_repair_prompt_count": sum(
            item.action_bearing_repair_prompt_count for item in diagnostics
        ),
        "failed_observation_count": sum(item.failed_observation_count for item in diagnostics),
        "action_bearing_failed_observation_count": sum(
            item.action_bearing_failed_observation_count for item in diagnostics
        ),
        "stop_ready_false_positive_count": sum(
            item.stop_ready_false_positive for item in diagnostics
        ),
        "stop_ready_false_negative_count": sum(
            item.stop_ready_false_negative for item in diagnostics
        ),
        "resource_budget_passed": resource_ok,
        "instrument_ready": instrument_ok,
        "status": status,
        "next_permitted_stage": next_stage,
        "model_execution_authorized": status == "preflight",
        "capability_development_complete": complete and contract.role == "capability_development",
        "state_reachability_complete": complete and contract.role == "state_reachability",
    }
    provisional = AuthorityPreservingRoleReport.model_construct(report_id="pending", **values)
    return AuthorityPreservingRoleReport(
        report_id=authority_preserving_role_report_id(provisional),
        **values,
    )


def _load_checkpoint(
    path: Path,
    contract: AuthorityPreservingRoleContract,
    manifest: AuthorityPreservingRoleJobManifest,
) -> tuple[EmpiricalPilotRollout, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        EmpiricalPilotRollout.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("role checkpoint contains duplicate job identities")
    for item in rows:
        job = jobs.get(item.job_id)
        if (
            job is None
            or item.contract_id != contract.contract_id
            or item.task_record_id != job.task_record_id
            or item.task_package_id != job.task_package_id
            or item.sampling_mode != job.sampling_mode
            or item.replicate_index != job.replicate_index
        ):
            raise ValueError("role checkpoint differs from its frozen job")
        payload = _raw_payload(item)
        if payload["job"]["source_design_job_id"] != job.source_design_job_id:
            raise ValueError("role checkpoint loses its source design identity")
    return rows


def run_authority_preserving_role(
    *,
    run_id: str,
    role: EmpiricalRole,
    task_source_dir: Path,
    protocol_source_dir: Path | None,
    model_config_path: Path,
    output_dir: Path,
    package_root: Path,
    workers: int,
    audit_only: bool = False,
) -> AuthorityPreservingRoleReport:
    model_payload = json.loads(model_config_path.read_text(encoding="utf-8"))
    model_config = AgentModelConfig.model_validate(model_payload.get("model", model_payload))
    contract, manifest, preflight, records, environments, catalogs = (
        build_authority_preserving_role_execution_inputs(
            run_id=run_id,
            role=role,
            task_source_dir=task_source_dir,
            protocol_source_dir=protocol_source_dir,
            model_config=model_config,
            package_root=package_root,
        )
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_dir / "execution_contract.json", contract.model_dump(mode="json"))
    _write_json_atomic(output_dir / "job_manifest.json", manifest.model_dump(mode="json"))
    _write_json_atomic(
        output_dir / "static_preflight_audit.json", preflight.model_dump(mode="json")
    )
    empty_raw = _raw_integrity_audit(
        role=role,
        rollouts=(),
        diagnostics=(),
        manifest=manifest,
    )
    if audit_only:
        report = _make_report(
            contract=contract,
            manifest=manifest,
            preflight=preflight,
            discovered_models=(),
            rollouts=(),
            diagnostics=(),
            raw_audit=empty_raw,
            records=records,
            catalogs=catalogs,
            preflight_only=True,
        )
        _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
        return report

    checkpoint_path = output_dir / "rollout_observations.checkpoint.jsonl"
    existing = _load_checkpoint(checkpoint_path, contract, manifest)
    completed = {item.job_id: item for item in existing}
    pending = [item for item in manifest.jobs if item.job_id not in completed]
    prior_report_path = output_dir / "report.json"
    if pending and prior_report_path.exists():
        raise ValueError(
            "formal role output contains a report before completion; "
            "use a separate preflight directory"
        )
    client: OpenAICompatibleJsonClient | None = None
    if pending:
        client = OpenAICompatibleJsonClient(model_config)
        discovered_models = client.discover_models()
        if contract.model_id not in discovered_models:
            raise ValueError("frozen DeepSeek V4-Flash identity is unavailable")
    elif prior_report_path.exists():
        prior_report = AuthorityPreservingRoleReport.model_validate_json(
            prior_report_path.read_text(encoding="utf-8")
        )
        if (
            prior_report.contract_id != contract.contract_id
            or prior_report.job_manifest_id != manifest.manifest_id
        ):
            raise ValueError("completed role report differs from its frozen inputs")
        discovered_models = prior_report.discovered_models
    else:
        discovered_models = (contract.model_id,)
    print(
        f"[v26.70:{role}] resuming {len(completed)}/{contract.expected_job_count}; "
        f"executing {len(pending)} jobs with {workers} workers",
        flush=True,
    )
    record_by_id = {item.record_id: item for item in records}
    environment_by_id = {item.manifest_id: item for item in environments}
    catalog_by_task = {item.task_package_id: item for item in catalogs}
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending) or 1))) as executor:
        future_map = {
            executor.submit(
                _run_one,
                job=cast(Any, job),
                contract=cast(Any, contract),
                record=cast(Any, record_by_id[job.task_record_id]),
                environment=environment_by_id[
                    record_by_id[job.task_record_id].environment_manifest_id
                ],
                catalog=catalog_by_task[job.task_package_id],
                client=cast(OpenAICompatibleJsonClient, client),
                output_dir=output_dir,
            ): job
            for job in pending
        }
        for future in as_completed(future_map):
            job = future_map[future]
            try:
                rollout = future.result()
            except Exception as exc:
                _append_jsonl(
                    output_dir / "runner_failures.checkpoint.jsonl",
                    {
                        "job_id": job.job_id,
                        "source_design_job_id": job.source_design_job_id,
                        "error": f"{type(exc).__name__}:{str(exc)[:500]}",
                    },
                )
                for queued in future_map:
                    if queued is not future:
                        queued.cancel()
                raise RuntimeError(
                    "authority-preserving role worker failed after raw-first capture"
                ) from exc
            with lock:
                if rollout.job_id in completed:
                    raise ValueError("role runner produced a duplicate job result")
                completed[rollout.job_id] = rollout
                _append_jsonl(checkpoint_path, rollout.model_dump(mode="json"))
            if (
                len(completed) % max(1, workers) == 0
                or len(completed) == contract.expected_job_count
            ):
                print(
                    f"[v26.70:{role}] completed {len(completed)}/{contract.expected_job_count}",
                    flush=True,
                )

    ordered = tuple(completed[item.job_id] for item in manifest.jobs if item.job_id in completed)
    job_by_id = {item.job_id: item for item in manifest.jobs}
    diagnostics = tuple(
        _diagnostic(item, job_by_id[item.job_id], record_by_id[item.task_record_id])
        for item in ordered
    )
    raw_audit = _raw_integrity_audit(
        role=role,
        rollouts=ordered,
        diagnostics=diagnostics,
        manifest=manifest,
    )
    report = _make_report(
        contract=contract,
        manifest=manifest,
        preflight=preflight,
        discovered_models=tuple(discovered_models),
        rollouts=ordered,
        diagnostics=diagnostics,
        raw_audit=raw_audit,
        records=records,
        catalogs=catalogs,
    )
    _write_json_atomic(
        output_dir / "empirical_rollouts.json",
        [item.model_dump(mode="json") for item in ordered],
    )
    _write_json_atomic(
        output_dir / "rollout_diagnostics.json",
        [item.model_dump(mode="json") for item in diagnostics],
    )
    _write_json_atomic(output_dir / "raw_integrity_audit.json", raw_audit.model_dump(mode="json"))
    if report.capability_task_summaries:
        _write_json_atomic(
            output_dir / "capability_task_summaries.json",
            [item.model_dump(mode="json") for item in report.capability_task_summaries],
        )
        _write_json_atomic(
            output_dir / "capability_mechanism_summaries.json",
            [item.model_dump(mode="json") for item in report.capability_mechanism_summaries],
        )
    if report.state_reachability_summaries:
        _write_json_atomic(
            output_dir / "state_reachability_summaries.json",
            [item.model_dump(mode="json") for item in report.state_reachability_summaries],
        )
        _write_json_atomic(
            output_dir / "state_support_freeze.json",
            cast(EmpiricalStateSupportFreeze, report.state_support_freeze).model_dump(mode="json"),
        )
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def authority_preserving_role_contract_id(value: AuthorityPreservingRoleContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_v26_authority_preserving_role_contract:",
    )


def authority_preserving_role_job_id(value: AuthorityPreservingRoleJob) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"job_id"}),
        prefix="finance_v26_authority_preserving_role_job:",
    )


def authority_preserving_role_manifest_id(
    value: AuthorityPreservingRoleJobManifest,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="finance_v26_authority_preserving_role_manifest:",
    )


def authority_preserving_preflight_audit_id(
    value: AuthorityPreservingPreflightAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_authority_preserving_role_preflight:",
    )


def authority_preserving_rollout_diagnostic_id(
    value: AuthorityPreservingRolloutDiagnostic,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"diagnostic_id"}),
        prefix="finance_v26_authority_preserving_role_diagnostic:",
    )


def authority_preserving_raw_integrity_audit_id(
    value: AuthorityPreservingRawIntegrityAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_authority_preserving_role_raw_audit:",
    )


def authority_preserving_role_report_id(value: AuthorityPreservingRoleReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_authority_preserving_role_report:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preflight or run a Finance v26.70 authority-preserving empirical role"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--role",
        choices=("capability_development", "state_reachability"),
        required=True,
    )
    parser.add_argument("--task-source-dir", type=Path, required=True)
    parser.add_argument("--protocol-source-dir", type=Path)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    report = run_authority_preserving_role(
        run_id=args.run_id,
        role=args.role,
        task_source_dir=args.task_source_dir,
        protocol_source_dir=args.protocol_source_dir,
        model_config_path=args.model_config,
        output_dir=args.output_dir,
        package_root=args.package_root,
        workers=args.workers,
        audit_only=args.audit_only,
    )
    print(
        json.dumps(
            {
                "report_id": report.report_id,
                "role": report.role,
                "status": report.status,
                "completed_rollout_count": report.completed_rollout_count,
                "next_permitted_stage": report.next_permitted_stage,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
