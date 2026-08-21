from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_feasible_role_task_rematerialization import (  # noqa: E501
    BudgetFeasibleRoleTaskPackage,
    BudgetQualifiedPathAudit,
    CompactPromptContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
    PathStrategy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501
    ThinkingRepairRawProviderCall,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_preflight import (  # noqa: E501
    ThinkingRepairManifest,
    ThinkingRepairPathAudit,
    ThinkingRepairTaskPackage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_repair_execution_failure_audit import (  # noqa: E501
    CompletionLowerBoundAudit,
    FailedExecutionLineageAudit,
    FailedProviderTelemetryAudit,
    FailureSourceReplayAudit,
    ProspectiveFailureTransitionContract,
    ThinkingRepairFailureAuditReport,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import (
    render_compact_witness_prompts,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    CompletionFailureKind,
    CompletionRequestKind,
    render_primary_completion_prompt,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion_bound import (
    CHAT_ENVELOPE_TOKENS,
    FALLBACK_COMPLETION_BOUND_TOKENS,
    FALLBACK_ROLLOUT_BOUND_TOKENS,
    INITIAL_COMPLETION_BOUND_TOKENS,
    INITIAL_ROLLOUT_BOUND_TOKENS,
    PROMPT_UPPER_BOUND_BYTES,
    RESCUE_PROMPT_UPPER_BOUND_BYTES,
    STATIC_REQUEST_MARGIN_TOKENS,
    CompletionBoundCandidate,
    ProspectiveThinkingCompletionBoundProtocol,
    certify_dynamic_primary_pre_call,
    certify_dynamic_rescue_pre_call,
    make_prospective_completion_bound_protocol,
)
from trusted_synthesis.runtime.tools import AgentToolObservation

RUN_ID: Final = "finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822"
FUTURE_EXECUTION_RUN_ID: Final = (
    "finance_v26_98_thinking_8k_completion_calibration_execution_v1_20260822"
)
NEXT_PERMITTED_STAGE: Final = "thinking_8k_completion_calibration_runner_and_preflight_only"

EXPECTED_V26_96_REPORT_ID: Final = (
    "finance_v26_thinking_repair_failure_audit_report:"
    "7ee7fb7963ccaa862496a0ee1664815904fc4a009a1748a45a6920b6496d3cde"
)
EXPECTED_V26_96_TRANSITION_ID: Final = (
    "finance_v26_thinking_repair_failure_transition:"
    "9036133329a0b6cff0e900773b19cd4fd3f7e33b72b09bde388fd49227bea6f4"
)
EXPECTED_V26_94_MANIFEST_ID: Final = (
    "finance_v26_thinking_repair_manifest:"
    "56ada3c9430d56c20c6611986cc0fa51f19c3f80fbee3b7b63b07dffddcf5945"
)

V26_90_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821"
)
V26_94_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821"
)
V26_95_EXECUTION_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_95_thinking_completion_telemetry_repair_execution_v1_20260821"
)
V26_96_DIR = (
    "artifacts/vtdo_experiment/finance_v26_96_thinking_repair_execution_failure_audit_v2_20260821"
)
RUNTIME_SOURCE_PATH = "src/trusted_synthesis/runtime/agent/prospective_thinking_completion_bound.py"
PREFLIGHT_SOURCE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_completion_bound_redesign_preflight.py"
)

RESCUE_FAILURE_TYPES: tuple[CompletionFailureKind, ...] = (
    "empty_final_content",
    "invalid_json",
    "invalid_response_contract",
    "length_truncated_content",
    "reasoning_only_length_truncation",
)
TARGET_MECHANISMS = (
    "context_conditioned_action",
    "failure_recovery",
    "semantic_reconciliation",
    "state_dependent_stopping",
)

SOURCE_REPLAY_VERSION: Final[Literal["finance_v26_completion_bound_source_replay.v1"]] = (
    "finance_v26_completion_bound_source_replay.v1"
)
EVIDENCE_VERSION: Final[Literal["finance_v26_completion_bound_evidence_audit.v1"]] = (
    "finance_v26_completion_bound_evidence_audit.v1"
)
EXPOSURE_VERSION: Final[Literal["finance_v26_completion_bound_source_exposure.v1"]] = (
    "finance_v26_completion_bound_source_exposure.v1"
)
TASK_VERSION: Final[Literal["finance_v26_completion_bound_task_package.v1"]] = (
    "finance_v26_completion_bound_task_package.v1"
)
DYNAMIC_RESCUE_VERSION: Final[Literal["finance_v26_dynamic_rescue_coverage.v1"]] = (
    "finance_v26_dynamic_rescue_coverage.v1"
)
PATH_VERSION: Final[Literal["finance_v26_completion_bound_path_audit.v1"]] = (
    "finance_v26_completion_bound_path_audit.v1"
)
CONTRACT_VERSION: Final[Literal["finance_v26_completion_bound_contract.v1"]] = (
    "finance_v26_completion_bound_contract.v1"
)
JOB_VERSION: Final[Literal["finance_v26_completion_bound_job.v1"]] = (
    "finance_v26_completion_bound_job.v1"
)
MANIFEST_VERSION: Final[Literal["finance_v26_completion_bound_manifest.v1"]] = (
    "finance_v26_completion_bound_manifest.v1"
)
FRESHNESS_VERSION: Final[Literal["finance_v26_completion_bound_freshness.v1"]] = (
    "finance_v26_completion_bound_freshness.v1"
)
DESTRUCTIVE_VERSION: Final[Literal["finance_v26_completion_bound_destructive.v1"]] = (
    "finance_v26_completion_bound_destructive.v1"
)
REPORT_VERSION: Final[Literal["finance_v26_completion_bound_preflight_report.v1"]] = (
    "finance_v26_completion_bound_preflight_report.v1"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_96_transitive_source",
        "v26_96_output",
        "v26_97_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> SourceReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("v26.97 source replay changed")
        return self


class CompletionBoundSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_96_REPORT_ID
    predecessor_transition_contract_id: str = EXPECTED_V26_96_TRANSITION_ID
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=733, max_length=733)
    transitive_source_file_count: Literal[723] = 723
    predecessor_output_file_count: Literal[8] = 8
    implementation_file_count: Literal[2] = 2
    replayed_file_count: Literal[733] = 733
    replay_pass_count: Literal[733] = 733
    replay_before_design_freeze: Literal[True] = True
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_completion_bound_source_replay.v1"] = SOURCE_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CompletionBoundSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))) or len(paths) != self.replayed_file_count:
            raise ValueError("v26.97 replay paths are not a unique canonical denominator")
        if self.audit_id != source_replay_audit_id(self):
            raise ValueError("v26.97 source replay identity mismatch")
        return self


class CompletionBoundEvidenceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_96_REPORT_ID
    v26_95_manifest_job_count: Literal[32] = 32
    complete_raw_job_count: Literal[27] = 27
    complete_raw_completion_unusable_count: Literal[27] = 27
    completion_gate_irrevocably_failed: Literal[True] = True
    exact_denominator_completed: Literal[False] = False
    exact_denominator_interval_reported: Literal[False] = False
    provider_call_count: Literal[184] = 184
    completion_token_count: Literal[444089] = 444_089
    reasoning_token_count: Literal[433062] = 433_062
    reasoning_share_basis_points_floor: Literal[9751] = 9751
    reasoning_only_truncation_call_count: Literal[48] = 48
    partial_length_truncation_call_count: Literal[2] = 2
    same_bound_prompt_only_repair_rejected: Literal[True] = True
    evidence_selects_bound_change_family: Literal[True] = True
    evidence_uniquely_selects_8192_tokens: Literal[False] = False
    evidence_uniquely_selects_16384_tokens: Literal[False] = False
    semantic_outcomes_used_for_bound_selection: Literal[False] = False
    schema_version: Literal["finance_v26_completion_bound_evidence_audit.v1"] = EVIDENCE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CompletionBoundEvidenceAudit:
        if self.audit_id != evidence_audit_id(self):
            raise ValueError("Completion-bound evidence audit identity mismatch")
        return self


class SourceExposureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_task_package_count: Literal[24] = 24
    source_task_overlap_with_v26_95_count: Literal[24] = 24
    model_exposed_source_task_count: Literal[22] = 22
    model_unexposed_source_task_count: Literal[2] = 2
    source_tasks_claimed_fresh: Literal[False] = False
    repeated_source_use: Literal["engineering_completion_calibration_only"] = (
        "engineering_completion_calibration_only"
    )
    repeated_sources_enter_capability_denominator: Literal[False] = False
    repeated_sources_enter_reachability_denominator: Literal[False] = False
    repeated_sources_enter_state_mapping: Literal[False] = False
    v26_95_completion_outcomes_used_to_select_protocol_family: Literal[True] = True
    v26_95_semantic_outcomes_used_to_select_tasks_or_jobs: Literal[False] = False
    v26_95_jobs_rerun_or_continued: Literal[0] = 0
    schema_version: Literal["finance_v26_completion_bound_source_exposure.v1"] = EXPOSURE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SourceExposureAudit:
        if self.model_exposed_source_task_count + self.model_unexposed_source_task_count != 24:
            raise ValueError("Completion-bound source exposure partition changed")
        if self.audit_id != source_exposure_audit_id(self):
            raise ValueError("Completion-bound source exposure identity mismatch")
        return self


class CompletionBoundTaskPackage(FrozenModel):
    task_package_id: str = Field(min_length=1)
    source_repair_task_package_id: str = Field(min_length=1)
    source_role_task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    source_role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    operational_record_id: str = Field(min_length=1)
    operational_task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    compact_prompt_contract_id: str = Field(min_length=1)
    completion_bound_protocol_id: str = Field(min_length=1)
    selected_candidate_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    thinking_binding_id: str = Field(min_length=1)
    source_model_exposed_before_freeze: bool
    source_task_claimed_fresh: Literal[False] = False
    engineering_calibration_only: Literal[True] = True
    empirical_capability_support_eligible: Literal[False] = False
    empirical_reachability_support_eligible: Literal[False] = False
    schema_version: Literal["finance_v26_completion_bound_task_package.v1"] = TASK_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> CompletionBoundTaskPackage:
        if self.task_package_id != completion_bound_task_package_id(self):
            raise ValueError("Completion-bound TaskPackage identity mismatch")
        return self


class RescueProjectionAudit(FrozenModel):
    failure_type: CompletionFailureKind
    rescue_prompt_sha256: str = Field(min_length=64, max_length=64)
    rescue_prompt_utf8_bytes: int = Field(gt=0, le=RESCUE_PROMPT_UPPER_BOUND_BYTES)
    certificate_id: str = Field(min_length=1)
    request_kind_certificate_passed: Literal[True] = True
    primary_certificate_passed: Literal[True] = True
    rescue_certificate_passed: Literal[True] = True
    resource_certificate_passed: Literal[True] = True
    provider_call_count_before_certificate: Literal[0] = 0


class DynamicRescueStateAudit(FrozenModel):
    row_id: str = Field(min_length=1)
    source_kind: Literal["compiler_registered", "v26_95_exposed_primary"]
    source_identity: str = Field(min_length=1)
    request_kind: CompletionRequestKind
    primary_prompt_sha256: str = Field(min_length=64, max_length=64)
    primary_prompt_utf8_bytes: int = Field(gt=0, le=PROMPT_UPPER_BOUND_BYTES)
    primary_certificate_id: str = Field(min_length=1)
    rescue_projections: tuple[RescueProjectionAudit, ...] = Field(min_length=5, max_length=5)
    maximum_rescue_prompt_utf8_bytes: int = Field(gt=0, le=RESCUE_PROMPT_UPPER_BOUND_BYTES)
    full_transcript_present: Literal[False] = False
    failed_arguments_present: Literal[False] = False
    previous_final_content_present: Literal[False] = False
    private_reasoning_content_present: Literal[False] = False
    schema_version: Literal["finance_v26_dynamic_rescue_state.v1"] = (
        "finance_v26_dynamic_rescue_state.v1"
    )

    @model_validator(mode="after")
    def validate_row(self) -> DynamicRescueStateAudit:
        if tuple(item.failure_type for item in self.rescue_projections) != RESCUE_FAILURE_TYPES:
            raise ValueError("dynamic Rescue failure-type coverage changed")
        if self.maximum_rescue_prompt_utf8_bytes != max(
            item.rescue_prompt_utf8_bytes for item in self.rescue_projections
        ):
            raise ValueError("dynamic Rescue row maximum differs")
        if self.row_id != dynamic_rescue_state_id(self):
            raise ValueError("dynamic Rescue row identity mismatch")
        return self


class DynamicRescueCoverageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    selected_candidate_id: str = Field(min_length=1)
    rows: tuple[DynamicRescueStateAudit, ...] = Field(min_length=480, max_length=480)
    compiler_registered_state_count: Literal[324] = 324
    v26_95_exposed_primary_state_count: Literal[156] = 156
    total_state_count: Literal[480] = 480
    failure_type_count_per_state: Literal[5] = 5
    total_rescue_projection_count: Literal[2400] = 2400
    absolute_rescue_prompt_upper_bound_bytes: Literal[6144] = RESCUE_PROMPT_UPPER_BOUND_BYTES
    maximum_observed_rescue_prompt_utf8_bytes: int = Field(gt=0, le=RESCUE_PROMPT_UPPER_BOUND_BYTES)
    minimum_rescue_headroom_bytes: int = Field(ge=0)
    dynamic_request_kind_certificate_pass_count: Literal[2400] = 2400
    dynamic_primary_certificate_pass_count: Literal[2400] = 2400
    dynamic_rescue_certificate_pass_count: Literal[2400] = 2400
    dynamic_resource_certificate_pass_count: Literal[2400] = 2400
    certificate_fixture_cumulative_usage_tokens: Literal[0] = 0
    certificate_fixture_required_future_reserve_tokens: Literal[0] = 0
    online_dynamic_resource_adequacy_established: Literal[False] = False
    execution_runner_resource_logic_materialized: Literal[False] = False
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: Literal["finance_v26_dynamic_rescue_coverage.v1"] = DYNAMIC_RESCUE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DynamicRescueCoverageAudit:
        counts = Counter(item.source_kind for item in self.rows)
        if counts != {"compiler_registered": 324, "v26_95_exposed_primary": 156}:
            raise ValueError("dynamic Rescue state denominator changed")
        maximum = max(item.maximum_rescue_prompt_utf8_bytes for item in self.rows)
        if self.maximum_observed_rescue_prompt_utf8_bytes != maximum:
            raise ValueError("dynamic Rescue aggregate maximum differs")
        if self.minimum_rescue_headroom_bytes != RESCUE_PROMPT_UPPER_BOUND_BYTES - maximum:
            raise ValueError("dynamic Rescue byte headroom differs")
        if self.audit_id != dynamic_rescue_coverage_audit_id(self):
            raise ValueError("dynamic Rescue coverage identity mismatch")
        return self


class CandidatePathBudget(FrozenModel):
    candidate_id: str = Field(min_length=1)
    completion_upper_bound_tokens: Literal[8192, 16384]
    rollout_upper_bound_tokens: Literal[160000, 240000]
    primary_request_token_upper_bound_sum: int = Field(gt=0)
    maximum_rescue_request_token_upper_bound: int = Field(gt=0)
    full_path_token_upper_bound: int = Field(gt=0)
    rollout_headroom_tokens: int = Field(ge=0)
    rollout_ceiling_passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_budget(self) -> CandidatePathBudget:
        if self.full_path_token_upper_bound != (
            self.primary_request_token_upper_bound_sum
            + self.maximum_rescue_request_token_upper_bound
        ):
            raise ValueError("candidate full-path arithmetic changed")
        if self.rollout_headroom_tokens != (
            self.rollout_upper_bound_tokens - self.full_path_token_upper_bound
        ):
            raise ValueError("candidate rollout headroom changed")
        return self


class CompletionBoundPathAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    predecessor_path_audit_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: PathStrategy
    primary_request_count: int = Field(gt=0)
    compiler_state_row_ids: tuple[str, ...] = Field(min_length=1)
    maximum_primary_prompt_utf8_bytes: int = Field(gt=0)
    maximum_rescue_prompt_utf8_bytes: int = Field(gt=0, le=RESCUE_PROMPT_UPPER_BOUND_BYTES)
    candidate_budgets: tuple[CandidatePathBudget, CandidatePathBudget]
    initial_candidate_passed: Literal[True] = True
    fallback_candidate_passed_static_only: Literal[True] = True
    prompt_ceiling_passed: Literal[True] = True
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: Literal["finance_v26_completion_bound_path_audit.v1"] = PATH_VERSION

    @model_validator(mode="after")
    def validate_path(self) -> CompletionBoundPathAudit:
        if self.primary_request_count != len(self.compiler_state_row_ids):
            raise ValueError("Completion-bound path state count changed")
        if tuple(item.completion_upper_bound_tokens for item in self.candidate_budgets) != (
            8192,
            16384,
        ):
            raise ValueError("Completion-bound path candidate order changed")
        if self.maximum_primary_prompt_utf8_bytes > PROMPT_UPPER_BOUND_BYTES:
            raise ValueError("Completion-bound path exceeds Prompt ceiling")
        if self.audit_id != completion_bound_path_audit_id(self):
            raise ValueError("Completion-bound path identity mismatch")
        return self


class CompletionBoundContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_96_REPORT_ID
    predecessor_transition_contract_id: str = EXPECTED_V26_96_TRANSITION_ID
    source_replay_audit_id: str = Field(min_length=1)
    evidence_audit_id: str = Field(min_length=1)
    source_exposure_audit_id: str = Field(min_length=1)
    completion_bound_protocol_id: str = Field(min_length=1)
    dynamic_rescue_coverage_audit_id: str = Field(min_length=1)
    task_package_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    path_audit_ids: tuple[str, ...] = Field(min_length=48, max_length=48)
    initial_candidate_id: str = Field(min_length=1)
    fallback_candidate_id: str = Field(min_length=1)
    prospective_execution_run_id: str = FUTURE_EXECUTION_RUN_ID
    exact_job_denominator: Literal[32] = 32
    initial_completion_upper_bound_tokens: Literal[8192] = INITIAL_COMPLETION_BOUND_TOKENS
    initial_rollout_upper_bound_tokens: Literal[160000] = INITIAL_ROLLOUT_BOUND_TOKENS
    fallback_completion_upper_bound_tokens: Literal[16384] = FALLBACK_COMPLETION_BOUND_TOKENS
    fallback_rollout_upper_bound_tokens: Literal[240000] = FALLBACK_ROLLOUT_BOUND_TOKENS
    fallback_jobs_materialized: Literal[0] = 0
    automatic_bound_escalation_allowed: Literal[False] = False
    zero_failure_completion_gate_retained: Literal[True] = True
    zero_failure_typed_no_call_gate_retained: Literal[True] = True
    transport_and_telemetry_failures_separate: Literal[True] = True
    semantic_validity_cannot_rescue_failure_gates: Literal[True] = True
    any_initial_length_failure_next_stage: Literal["fresh_16k_completion_preflight_only"] = (
        "fresh_16k_completion_preflight_only"
    )
    any_initial_nonlength_completion_failure_next_stage: Literal[
        "completion_contract_root_cause_audit_only"
    ] = "completion_contract_root_cause_audit_only"
    fully_passing_initial_denominator_next_stage: Literal["thinking_role_protocol_freeze_only"] = (
        "thinking_role_protocol_freeze_only"
    )
    execution_runner_materialized: Literal[False] = False
    execution_authorized: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: Literal["finance_v26_completion_bound_contract.v1"] = CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CompletionBoundContract:
        if len(set(self.task_package_ids)) != 24 or len(set(self.path_audit_ids)) != 48:
            raise ValueError("Completion-bound Contract identities are not fresh and unique")
        if self.contract_id != completion_bound_contract_id(self):
            raise ValueError("Completion-bound Contract identity mismatch")
        return self


class CompletionBoundJob(FrozenModel):
    job_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    path_audit_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: PathStrategy
    source_role: Literal["capability", "reachability"]
    job_seed: int = Field(ge=0)
    candidate_id: str = Field(min_length=1)
    completion_upper_bound_tokens: Literal[8192] = INITIAL_COMPLETION_BOUND_TOKENS
    rollout_upper_bound_tokens: Literal[160000] = INITIAL_ROLLOUT_BOUND_TOKENS
    maximum_rescue_calls: Literal[1] = 1
    thinking_type: Literal["enabled"] = "enabled"
    source_repeated_for_engineering_calibration: Literal[True] = True
    schema_version: Literal["finance_v26_completion_bound_job.v1"] = JOB_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> CompletionBoundJob:
        if self.job_id != completion_bound_job_id(self):
            raise ValueError("Completion-bound Job identity mismatch")
        return self


class CompletionBoundManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    prospective_execution_run_id: str = FUTURE_EXECUTION_RUN_ID
    candidate_id: str = Field(min_length=1)
    jobs: tuple[CompletionBoundJob, ...] = Field(min_length=32, max_length=32)
    mechanism_job_counts: dict[str, int]
    path_job_counts: dict[str, int]
    cell_job_counts: dict[str, int]
    distinct_task_package_count: Literal[24] = 24
    fallback_job_count: Literal[0] = 0
    historical_v26_95_job_overlap_count: Literal[0] = 0
    exact_denominator_frozen: Literal[32] = 32
    each_job_execute_at_most_once: Literal[True] = True
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_completion_bound_manifest.v1"] = MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> CompletionBoundManifest:
        if len({item.job_id for item in self.jobs}) != 32:
            raise ValueError("Completion-bound Jobs must be unique")
        if len({item.task_package_id for item in self.jobs}) != 24:
            raise ValueError("Completion-bound Manifest must cover all TaskPackages")
        if self.mechanism_job_counts != {item: 8 for item in TARGET_MECHANISMS}:
            raise ValueError("Completion-bound mechanism balance changed")
        if self.path_job_counts != {
            "search_then_open": 12,
            "search_then_structured": 8,
            "structured_direct": 12,
        }:
            raise ValueError("Completion-bound path balance changed")
        if len(self.cell_job_counts) != 12 or set(self.cell_job_counts.values()) - {2, 3}:
            raise ValueError("Completion-bound cell coverage changed")
        if self.manifest_id != completion_bound_manifest_id(self):
            raise ValueError("Completion-bound Manifest identity mismatch")
        return self


class CompletionBoundFreshnessAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_task_overlap_with_v26_95_count: Literal[24] = 24
    source_task_freshness_claimed: Literal[False] = False
    task_package_overlap_with_v26_94_count: Literal[0] = 0
    task_package_overlap_with_v26_95_count: Literal[0] = 0
    job_overlap_with_v26_95_count: Literal[0] = 0
    contract_overlap_with_v26_95_count: Literal[0] = 0
    manifest_overlap_with_v26_95_count: Literal[0] = 0
    fresh_task_package_identity_count: Literal[24] = 24
    fresh_job_identity_count: Literal[32] = 32
    historical_job_rerun_count: Literal[0] = 0
    historical_job_continuation_count: Literal[0] = 0
    historical_result_reclassification_count: Literal[0] = 0
    task_or_job_selection_uses_v26_95_semantic_outcomes: Literal[False] = False
    repeated_sources_engineering_only: Literal[True] = True
    schema_version: Literal["finance_v26_completion_bound_freshness.v1"] = FRESHNESS_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CompletionBoundFreshnessAudit:
        if self.audit_id != completion_bound_freshness_audit_id(self):
            raise ValueError("Completion-bound freshness identity mismatch")
        return self


class MutationResult(FrozenModel):
    mutation_id: str = Field(min_length=1)
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True
    failure_type: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_mutation(self) -> MutationResult:
        if self.mutation_id != mutation_result_id(self):
            raise ValueError("Completion-bound mutation identity mismatch")
        return self


class CompletionBoundDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=18, max_length=18)
    rejected_mutation_count: Literal[18] = 18
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_completion_bound_destructive.v1"] = DESTRUCTIVE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CompletionBoundDestructiveAudit:
        if not all(item.rejected for item in self.mutation_results):
            raise ValueError("Completion-bound destructive control escaped")
        if self.audit_id != completion_bound_destructive_audit_id(self):
            raise ValueError("Completion-bound destructive identity mismatch")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class CompletionBoundPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    predecessor_report_id: str = EXPECTED_V26_96_REPORT_ID
    predecessor_transition_contract_id: str = EXPECTED_V26_96_TRANSITION_ID
    source_replay_audit_id: str = Field(min_length=1)
    evidence_audit_id: str = Field(min_length=1)
    source_exposure_audit_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    dynamic_rescue_coverage_audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    freshness_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=11, max_length=11)
    source_file_count: Literal[733] = 733
    task_package_count: Literal[24] = 24
    path_audit_count: Literal[48] = 48
    compiler_dynamic_state_count: Literal[324] = 324
    historical_dynamic_state_count: Literal[156] = 156
    dynamic_rescue_projection_count: Literal[2400] = 2400
    job_count: Literal[32] = 32
    initial_completion_upper_bound_tokens: Literal[8192] = INITIAL_COMPLETION_BOUND_TOKENS
    initial_rollout_upper_bound_tokens: Literal[160000] = INITIAL_ROLLOUT_BOUND_TOKENS
    fallback_completion_upper_bound_tokens: Literal[16384] = FALLBACK_COMPLETION_BOUND_TOKENS
    fallback_rollout_upper_bound_tokens: Literal[240000] = FALLBACK_ROLLOUT_BOUND_TOKENS
    fallback_job_count: Literal[0] = 0
    execution_runner_materialized: Literal[False] = False
    execution_authorized: Literal[False] = False
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed_preflight"] = "passed_preflight"
    next_permitted_stage: Literal[
        "thinking_8k_completion_calibration_runner_and_preflight_only"
    ] = NEXT_PERMITTED_STAGE
    role_protocol_frozen: Literal[False] = False
    capability_development_authorized: Literal[False] = False
    state_reachability_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: Literal["finance_v26_completion_bound_preflight_report.v1"] = REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> CompletionBoundPreflightReport:
        if self.run_id != RUN_ID or self.next_permitted_stage != NEXT_PERMITTED_STAGE:
            raise ValueError("Completion-bound report transition changed")
        if self.report_id != completion_bound_report_id(self):
            raise ValueError("Completion-bound report identity mismatch")
        return self


@dataclass(frozen=True)
class CompilerPromptState:
    source_identity: str
    predecessor_path_audit_id: str
    source_repair_task_package_id: str
    source_task_artifact_id: str
    role: Literal["capability", "reachability"]
    mechanism_id: str
    path_strategy_id: PathStrategy
    request_index: int
    request_kind: CompletionRequestKind
    primary_prompt: str


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


def source_replay_audit_id(value: CompletionBoundSourceReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_completion_bound_source_replay:")


def evidence_audit_id(value: CompletionBoundEvidenceAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_completion_bound_evidence_audit:")


def source_exposure_audit_id(value: SourceExposureAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_completion_bound_source_exposure:")


def completion_bound_task_package_id(value: CompletionBoundTaskPackage) -> str:
    return _identity(value, "task_package_id", "finance_v26_completion_bound_task_package:")


def dynamic_rescue_state_id(value: DynamicRescueStateAudit) -> str:
    return _identity(value, "row_id", "finance_v26_dynamic_rescue_state:")


def dynamic_rescue_coverage_audit_id(value: DynamicRescueCoverageAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_dynamic_rescue_coverage:")


def completion_bound_path_audit_id(value: CompletionBoundPathAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_completion_bound_path_audit:")


def completion_bound_contract_id(value: CompletionBoundContract) -> str:
    return _identity(value, "contract_id", "finance_v26_completion_bound_contract:")


def completion_bound_job_id(value: CompletionBoundJob) -> str:
    return _identity(value, "job_id", "finance_v26_completion_bound_job:")


def completion_bound_manifest_id(value: CompletionBoundManifest) -> str:
    return _identity(value, "manifest_id", "finance_v26_completion_bound_manifest:")


def completion_bound_freshness_audit_id(value: CompletionBoundFreshnessAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_completion_bound_freshness:")


def mutation_result_id(value: MutationResult) -> str:
    return _identity(value, "mutation_id", "finance_v26_completion_bound_mutation:")


def completion_bound_destructive_audit_id(value: CompletionBoundDestructiveAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_completion_bound_destructive:")


def completion_bound_report_id(value: CompletionBoundPreflightReport) -> str:
    return _identity(value, "report_id", "finance_v26_completion_bound_preflight_report:")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_canonical_json(path: Path) -> Any:
    raw = path.read_bytes()
    payload = json.loads(raw)
    if raw != _canonical_bytes(payload):
        raise ValueError(f"noncanonical v26.97 source JSON: {path}")
    return payload


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    raw = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError(f"immutable v26.97 output changed: {path}")
    path.write_bytes(raw)


def _relative(path: Path, package_root: Path) -> str:
    return str(path.resolve().relative_to(package_root.resolve()))


def _rows(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"expected a list source at {path}")
    return tuple(model.model_validate(item) for item in payload)


def _source_entry(
    *,
    path: Path,
    package_root: Path,
    source_kind: Literal[
        "v26_96_transitive_source",
        "v26_96_output",
        "v26_97_implementation",
    ],
    expected_sha256: str,
) -> SourceReplayEntry:
    return SourceReplayEntry(
        relative_path=_relative(path, package_root),
        source_kind=source_kind,
        expected_sha256=expected_sha256,
        observed_sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def _load_predecessor(
    package_root: Path,
) -> tuple[
    ThinkingRepairFailureAuditReport,
    ProspectiveFailureTransitionContract,
    FailureSourceReplayAudit,
]:
    directory = package_root / V26_96_DIR
    report = ThinkingRepairFailureAuditReport.model_validate_json(
        (directory / "report.json").read_text(encoding="utf-8")
    )
    transition = ProspectiveFailureTransitionContract.model_validate_json(
        (directory / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )
    replay = FailureSourceReplayAudit.model_validate_json(
        (directory / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    if (
        report.report_id != EXPECTED_V26_96_REPORT_ID
        or transition.contract_id != EXPECTED_V26_96_TRANSITION_ID
        or report.next_permitted_stage
        != "thinking_completion_bound_or_two_stage_protocol_redesign_only"
        or transition.next_permitted_stage != report.next_permitted_stage
    ):
        raise ValueError("v26.97 predecessor authorization changed")
    return report, transition, replay


def _build_source_replay(package_root: Path) -> CompletionBoundSourceReplayAudit:
    _, _, predecessor = _load_predecessor(package_root)
    entries = [
        _source_entry(
            path=package_root / item.relative_path,
            package_root=package_root,
            source_kind="v26_96_transitive_source",
            expected_sha256=item.expected_sha256,
        )
        for item in predecessor.entries
    ]
    predecessor_files = sorted(
        path for path in (package_root / V26_96_DIR).iterdir() if path.is_file()
    )
    if len(predecessor_files) != 8:
        raise ValueError("v26.96 output denominator changed")
    for path in predecessor_files:
        _load_canonical_json(path)
        entries.append(
            _source_entry(
                path=path,
                package_root=package_root,
                source_kind="v26_96_output",
                expected_sha256=_sha256(path),
            )
        )
    implementation_root = Path(__file__).resolve().parents[4]
    for relative_path in (RUNTIME_SOURCE_PATH, PREFLIGHT_SOURCE_PATH):
        path = implementation_root / relative_path
        entries.append(
            SourceReplayEntry(
                relative_path=relative_path,
                source_kind="v26_97_implementation",
                expected_sha256=_sha256(path),
                observed_sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    ordered = tuple(sorted(entries, key=lambda item: item.relative_path))
    values = {"entries": ordered}
    provisional = CompletionBoundSourceReplayAudit.model_construct(audit_id="pending", **values)
    return CompletionBoundSourceReplayAudit(
        audit_id=source_replay_audit_id(provisional),
        **values,
    )


def _build_evidence_audit(package_root: Path) -> CompletionBoundEvidenceAudit:
    report, transition, _ = _load_predecessor(package_root)
    completion = CompletionLowerBoundAudit.model_validate_json(
        (package_root / V26_96_DIR / "completion_lower_bound_audit.json").read_text(
            encoding="utf-8"
        )
    )
    provider = FailedProviderTelemetryAudit.model_validate_json(
        (package_root / V26_96_DIR / "provider_telemetry_audit.json").read_text(encoding="utf-8")
    )
    if (
        not report.completion_gate_irrevocably_failed
        or completion.complete_raw_completion_unusable_count != 27
        or provider.provider_artifact_count != 184
        or provider.completion_tokens != 444_089
        or provider.reasoning_tokens != 433_062
        or transition.same_4096_bound_prompt_only_retuning_allowed
        or not transition.future_completion_bound_change_permitted
    ):
        raise ValueError("v26.96 Completion evidence changed")
    provisional = CompletionBoundEvidenceAudit.model_construct(audit_id="pending")
    return CompletionBoundEvidenceAudit(audit_id=evidence_audit_id(provisional))


def _load_v26_94_inputs(
    package_root: Path,
) -> tuple[
    tuple[ThinkingRepairTaskPackage, ...],
    tuple[ThinkingRepairPathAudit, ...],
    ThinkingRepairManifest,
]:
    directory = package_root / V26_94_DIR
    packages = cast(
        tuple[ThinkingRepairTaskPackage, ...],
        _rows(directory / "thinking_repair_task_packages.json", ThinkingRepairTaskPackage),
    )
    paths = cast(
        tuple[ThinkingRepairPathAudit, ...],
        _rows(directory / "thinking_repair_path_audits.json", ThinkingRepairPathAudit),
    )
    manifest = ThinkingRepairManifest.model_validate_json(
        (directory / "thinking_repair_job_manifest.json").read_text(encoding="utf-8")
    )
    if (
        len(packages) != 24
        or len(paths) != 48
        or manifest.manifest_id != EXPECTED_V26_94_MANIFEST_ID
    ):
        raise ValueError("v26.94 source design changed")
    return packages, paths, manifest


def _build_source_exposure(package_root: Path) -> tuple[SourceExposureAudit, set[str]]:
    packages, _, manifest = _load_v26_94_inputs(package_root)
    lineage = FailedExecutionLineageAudit.model_validate_json(
        (package_root / V26_96_DIR / "failed_execution_lineage_audit.json").read_text(
            encoding="utf-8"
        )
    )
    exposed_jobs = {item.job_id for item in lineage.rows if item.model_exposed}
    exposed_task_packages = {
        item.repair_task_package_id for item in manifest.jobs if item.job_id in exposed_jobs
    }
    source_by_repair = {item.task_package_id: item.source_task_artifact_id for item in packages}
    exposed_sources = {source_by_repair[item] for item in exposed_task_packages}
    if len(exposed_task_packages) != 22 or len(exposed_sources) != 22:
        raise ValueError("v26.95 source exposure denominator changed")
    provisional = SourceExposureAudit.model_construct(audit_id="pending")
    return SourceExposureAudit(
        audit_id=source_exposure_audit_id(provisional)
    ), exposed_task_packages


def _build_task_packages(
    *,
    package_root: Path,
    protocol: ProspectiveThinkingCompletionBoundProtocol,
    exposed_task_packages: set[str],
) -> tuple[CompletionBoundTaskPackage, ...]:
    source_packages, _, _ = _load_v26_94_inputs(package_root)
    output = []
    for source in source_packages:
        values = {
            "source_repair_task_package_id": source.task_package_id,
            "source_role_task_package_id": source.source_role_task_package_id,
            "source_task_artifact_id": source.source_task_artifact_id,
            "source_role": source.source_role,
            "mechanism_id": source.mechanism_id,
            "operational_record_id": source.operational_record_id,
            "operational_task_package_id": source.operational_task_package_id,
            "environment_manifest_id": source.environment_manifest_id,
            "semantic_source_id": source.semantic_source_id,
            "compact_prompt_contract_id": source.compact_prompt_contract_id,
            "completion_bound_protocol_id": protocol.protocol_id,
            "selected_candidate_id": protocol.initial_candidate_id,
            "model_config_id": source.model_config_id,
            "thinking_binding_id": source.thinking_binding_id,
            "source_model_exposed_before_freeze": source.task_package_id in exposed_task_packages,
        }
        provisional = CompletionBoundTaskPackage.model_construct(
            task_package_id="pending",
            **values,
        )
        output.append(
            CompletionBoundTaskPackage(
                task_package_id=completion_bound_task_package_id(provisional),
                **values,
            )
        )
    return tuple(sorted(output, key=lambda item: item.task_package_id))


def _trajectory_observations(trajectory: Trajectory) -> tuple[AgentToolObservation, ...]:
    output = []
    for step in trajectory.steps:
        observation = step.observation
        if (
            isinstance(observation, Mapping)
            and observation.get("schema_version") == "agent_tool_observation.v2"
        ):
            output.append(AgentToolObservation.model_validate(observation))
    return tuple(output)


def _compiler_prompt_states(package_root: Path) -> tuple[CompilerPromptState, ...]:
    role_dir = package_root / V26_90_DIR
    role_packages = cast(
        tuple[BudgetFeasibleRoleTaskPackage, ...],
        _rows(role_dir / "budget_feasible_role_task_packages.json", BudgetFeasibleRoleTaskPackage),
    )
    role_paths = cast(
        tuple[BudgetQualifiedPathAudit, ...],
        _rows(role_dir / "budget_qualified_path_audits.json", BudgetQualifiedPathAudit),
    )
    prompt_contracts = cast(
        tuple[CompactPromptContract, ...],
        _rows(role_dir / "compact_prompt_contracts.json", CompactPromptContract),
    )
    records = cast(
        tuple[OperationalTaskRecord, ...],
        _rows(role_dir / "operational_task_records.json", OperationalTaskRecord),
    )
    trajectories = cast(
        tuple[Trajectory, ...],
        _rows(role_dir / "compiler_trajectories.json", Trajectory),
    )
    repair_packages, repair_paths, _ = _load_v26_94_inputs(package_root)
    repair_by_source = {item.source_role_task_package_id: item for item in repair_packages}
    repair_path_by_predecessor = {item.predecessor_path_audit_id: item for item in repair_paths}
    path_by_id = {item.audit_id: item for item in role_paths}
    prompt_by_id = {item.contract_id: item for item in prompt_contracts}
    record_by_id = {item.record_id: item for item in records}
    trajectory_by_id = {item.trajectory_id: item for item in trajectories}
    output = []
    for role_package in sorted(role_packages, key=lambda item: item.task_package_id):
        repair_package = repair_by_source[role_package.task_package_id]
        record = record_by_id[role_package.operational_record_id]
        prompt_contract = prompt_by_id[role_package.compact_prompt_contract_id]
        for predecessor_path_id in role_package.path_audit_ids:
            predecessor = path_by_id[predecessor_path_id]
            historical = repair_path_by_predecessor[predecessor.audit_id]
            trajectory = trajectory_by_id[predecessor.compiler_trajectory_id]
            source_prompts = render_compact_witness_prompts(
                prompt_contract.public_context,
                record.task_package.task.public,
                _trajectory_observations(trajectory),
                public_path_condition=predecessor.public_path_condition,
            )
            if len(source_prompts) != len(predecessor.request_bounds):
                raise ValueError("v26.90 Compiler Prompt denominator changed")
            for prompt, bound in zip(source_prompts, predecessor.request_bounds, strict=True):
                if (
                    _sha256_text(prompt) != bound.prompt_sha256
                    or len(prompt.encode("utf-8")) != bound.prompt_utf8_bytes
                ):
                    raise ValueError("v26.90 Compiler Prompt exact replay failed")
            if predecessor.request_bounds[0].request_kind != "plan":
                raise ValueError("v26.97 predecessor path lacks the removed Plan request")
            if len(historical.request_audits) != len(source_prompts) - 1:
                raise ValueError("v26.94 registered request denominator changed")
            for request_index, (source_prompt, bound, registered) in enumerate(
                zip(
                    source_prompts[1:],
                    predecessor.request_bounds[1:],
                    historical.request_audits,
                    strict=True,
                )
            ):
                request_kind = cast(CompletionRequestKind, bound.request_kind)
                primary = render_primary_completion_prompt(request_kind, source_prompt)
                if (
                    _sha256_text(primary) != registered.primary_prompt_sha256
                    or len(primary.encode("utf-8")) != registered.primary_prompt_utf8_bytes
                ):
                    raise ValueError("v26.94 registered Primary Prompt exact replay failed")
                output.append(
                    CompilerPromptState(
                        source_identity=f"{historical.audit_id}:{request_index}",
                        predecessor_path_audit_id=historical.audit_id,
                        source_repair_task_package_id=repair_package.task_package_id,
                        source_task_artifact_id=repair_package.source_task_artifact_id,
                        role=repair_package.source_role,
                        mechanism_id=repair_package.mechanism_id,
                        path_strategy_id=predecessor.path_strategy_id,
                        request_index=request_index,
                        request_kind=request_kind,
                        primary_prompt=primary,
                    )
                )
    ordered = tuple(sorted(output, key=lambda item: item.source_identity))
    if len(ordered) != 324 or len({item.source_identity for item in ordered}) != 324:
        raise ValueError("v26.97 Compiler dynamic-state denominator changed")
    return ordered


def _historical_primary_states(package_root: Path) -> tuple[tuple[str, str, str], ...]:
    directory = package_root / V26_95_EXECUTION_DIR / "raw_provider_calls"
    output = []
    for path in sorted(directory.glob("*/*.json")):
        artifact = ThinkingRepairRawProviderCall.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if artifact.phase == "primary":
            output.append((artifact.artifact_id, artifact.request_kind, artifact.prompt))
    if len(output) != 156 or len({item[0] for item in output}) != 156:
        raise ValueError("v26.95 Primary state denominator changed")
    return tuple(output)


def _dynamic_row(
    *,
    source_kind: Literal["compiler_registered", "v26_95_exposed_primary"],
    source_identity: str,
    request_kind: CompletionRequestKind,
    primary_prompt: str,
    protocol: ProspectiveThinkingCompletionBoundProtocol,
) -> DynamicRescueStateAudit:
    primary_certificate = certify_dynamic_primary_pre_call(
        protocol=protocol,
        candidate_id=protocol.initial_candidate_id,
        request_kind=request_kind,
        primary_prompt=primary_prompt,
        cumulative_usage_tokens_before_request=0,
        required_future_reserve_tokens=0,
    )
    projections = []
    for failure_type in RESCUE_FAILURE_TYPES:
        rescue_prompt, certificate = certify_dynamic_rescue_pre_call(
            protocol=protocol,
            candidate_id=protocol.initial_candidate_id,
            request_kind=request_kind,
            primary_prompt=primary_prompt,
            failure_type=failure_type,
            cumulative_usage_tokens_before_request=0,
            required_future_reserve_tokens=0,
        )
        projections.append(
            RescueProjectionAudit(
                failure_type=failure_type,
                rescue_prompt_sha256=_sha256_text(rescue_prompt),
                rescue_prompt_utf8_bytes=len(rescue_prompt.encode("utf-8")),
                certificate_id=certificate.certificate_id,
            )
        )
    values = {
        "source_kind": source_kind,
        "source_identity": source_identity,
        "request_kind": request_kind,
        "primary_prompt_sha256": _sha256_text(primary_prompt),
        "primary_prompt_utf8_bytes": len(primary_prompt.encode("utf-8")),
        "primary_certificate_id": primary_certificate.certificate_id,
        "rescue_projections": tuple(projections),
        "maximum_rescue_prompt_utf8_bytes": max(
            item.rescue_prompt_utf8_bytes for item in projections
        ),
    }
    provisional = DynamicRescueStateAudit.model_construct(row_id="pending", **values)
    return DynamicRescueStateAudit(
        row_id=dynamic_rescue_state_id(provisional),
        **values,
    )


def _build_dynamic_coverage(
    *,
    package_root: Path,
    protocol: ProspectiveThinkingCompletionBoundProtocol,
) -> tuple[DynamicRescueCoverageAudit, tuple[CompilerPromptState, ...]]:
    compiler_states = _compiler_prompt_states(package_root)
    rows = [
        _dynamic_row(
            source_kind="compiler_registered",
            source_identity=item.source_identity,
            request_kind=item.request_kind,
            primary_prompt=item.primary_prompt,
            protocol=protocol,
        )
        for item in compiler_states
    ]
    rows.extend(
        _dynamic_row(
            source_kind="v26_95_exposed_primary",
            source_identity=source_identity,
            request_kind=cast(CompletionRequestKind, request_kind),
            primary_prompt=primary_prompt,
            protocol=protocol,
        )
        for source_identity, request_kind, primary_prompt in _historical_primary_states(
            package_root
        )
    )
    ordered = tuple(sorted(rows, key=lambda item: (item.source_kind, item.source_identity)))
    maximum = max(item.maximum_rescue_prompt_utf8_bytes for item in ordered)
    values = {
        "protocol_id": protocol.protocol_id,
        "selected_candidate_id": protocol.initial_candidate_id,
        "rows": ordered,
        "maximum_observed_rescue_prompt_utf8_bytes": maximum,
        "minimum_rescue_headroom_bytes": RESCUE_PROMPT_UPPER_BOUND_BYTES - maximum,
    }
    provisional = DynamicRescueCoverageAudit.model_construct(audit_id="pending", **values)
    return (
        DynamicRescueCoverageAudit(
            audit_id=dynamic_rescue_coverage_audit_id(provisional),
            **values,
        ),
        compiler_states,
    )


def _candidate_path_budget(
    *,
    candidate: CompletionBoundCandidate,
    states: Sequence[CompilerPromptState],
    rows_by_source: Mapping[str, DynamicRescueStateAudit],
) -> CandidatePathBudget:
    primary_sum = sum(
        len(item.primary_prompt.encode("utf-8"))
        + CHAT_ENVELOPE_TOKENS
        + STATIC_REQUEST_MARGIN_TOKENS
        + candidate.completion_upper_bound_tokens
        for item in states
    )
    maximum_rescue = max(
        rows_by_source[item.source_identity].maximum_rescue_prompt_utf8_bytes
        + CHAT_ENVELOPE_TOKENS
        + STATIC_REQUEST_MARGIN_TOKENS
        + candidate.completion_upper_bound_tokens
        for item in states
    )
    full = primary_sum + maximum_rescue
    if full > candidate.rollout_upper_bound_tokens:
        raise ValueError("Completion-bound candidate path exceeds its rollout ceiling")
    return CandidatePathBudget(
        candidate_id=candidate.candidate_id,
        completion_upper_bound_tokens=candidate.completion_upper_bound_tokens,
        rollout_upper_bound_tokens=candidate.rollout_upper_bound_tokens,
        primary_request_token_upper_bound_sum=primary_sum,
        maximum_rescue_request_token_upper_bound=maximum_rescue,
        full_path_token_upper_bound=full,
        rollout_headroom_tokens=candidate.rollout_upper_bound_tokens - full,
    )


def _build_path_audits(
    *,
    protocol: ProspectiveThinkingCompletionBoundProtocol,
    task_packages: Sequence[CompletionBoundTaskPackage],
    compiler_states: Sequence[CompilerPromptState],
    dynamic: DynamicRescueCoverageAudit,
) -> tuple[CompletionBoundPathAudit, ...]:
    package_by_source = {item.source_repair_task_package_id: item for item in task_packages}
    rows_by_source = {
        item.source_identity: item
        for item in dynamic.rows
        if item.source_kind == "compiler_registered"
    }
    states_by_path: dict[str, list[CompilerPromptState]] = {}
    for state in compiler_states:
        states_by_path.setdefault(state.predecessor_path_audit_id, []).append(state)
    output = []
    for predecessor_path_id in sorted(states_by_path):
        states = sorted(states_by_path[predecessor_path_id], key=lambda item: item.request_index)
        package = package_by_source[states[0].source_repair_task_package_id]
        if any(
            item.source_repair_task_package_id != package.source_repair_task_package_id
            for item in states
        ):
            raise ValueError("Completion-bound path crosses TaskPackages")
        candidate_budgets = tuple(
            _candidate_path_budget(
                candidate=candidate,
                states=states,
                rows_by_source=rows_by_source,
            )
            for candidate in protocol.candidates
        )
        values = {
            "task_package_id": package.task_package_id,
            "predecessor_path_audit_id": predecessor_path_id,
            "source_task_artifact_id": states[0].source_task_artifact_id,
            "role": states[0].role,
            "mechanism_id": states[0].mechanism_id,
            "path_strategy_id": states[0].path_strategy_id,
            "primary_request_count": len(states),
            "compiler_state_row_ids": tuple(
                rows_by_source[item.source_identity].row_id for item in states
            ),
            "maximum_primary_prompt_utf8_bytes": max(
                len(item.primary_prompt.encode("utf-8")) for item in states
            ),
            "maximum_rescue_prompt_utf8_bytes": max(
                rows_by_source[item.source_identity].maximum_rescue_prompt_utf8_bytes
                for item in states
            ),
            "candidate_budgets": cast(
                tuple[CandidatePathBudget, CandidatePathBudget],
                candidate_budgets,
            ),
        }
        provisional = CompletionBoundPathAudit.model_construct(audit_id="pending", **values)
        output.append(
            CompletionBoundPathAudit(
                audit_id=completion_bound_path_audit_id(provisional),
                **values,
            )
        )
    ordered = tuple(sorted(output, key=lambda item: item.audit_id))
    if len(ordered) != 48:
        raise ValueError("Completion-bound path denominator changed")
    return ordered


def _build_contract(
    *,
    source: CompletionBoundSourceReplayAudit,
    evidence: CompletionBoundEvidenceAudit,
    exposure: SourceExposureAudit,
    protocol: ProspectiveThinkingCompletionBoundProtocol,
    dynamic: DynamicRescueCoverageAudit,
    task_packages: Sequence[CompletionBoundTaskPackage],
    paths: Sequence[CompletionBoundPathAudit],
) -> CompletionBoundContract:
    values = {
        "source_replay_audit_id": source.audit_id,
        "evidence_audit_id": evidence.audit_id,
        "source_exposure_audit_id": exposure.audit_id,
        "completion_bound_protocol_id": protocol.protocol_id,
        "dynamic_rescue_coverage_audit_id": dynamic.audit_id,
        "task_package_ids": tuple(sorted(item.task_package_id for item in task_packages)),
        "path_audit_ids": tuple(sorted(item.audit_id for item in paths)),
        "initial_candidate_id": protocol.initial_candidate_id,
        "fallback_candidate_id": protocol.fallback_candidate_id,
    }
    provisional = CompletionBoundContract.model_construct(contract_id="pending", **values)
    return CompletionBoundContract(
        contract_id=completion_bound_contract_id(provisional),
        **values,
    )


def _job_seed(index: int, source_job_id: str, contract_id: str) -> int:
    digest = hashlib.sha256(
        _canonical_bytes(
            {
                "contract_id": contract_id,
                "index": index,
                "salt": "finance_v26_97_8k_completion_calibration",
                "source_job_id": source_job_id,
            }
        )
    ).hexdigest()
    return int(digest[:15], 16)


def _build_manifest(
    *,
    package_root: Path,
    contract: CompletionBoundContract,
    protocol: ProspectiveThinkingCompletionBoundProtocol,
    task_packages: Sequence[CompletionBoundTaskPackage],
    paths: Sequence[CompletionBoundPathAudit],
) -> CompletionBoundManifest:
    _, source_paths, source_manifest = _load_v26_94_inputs(package_root)
    package_by_source = {item.source_repair_task_package_id: item for item in task_packages}
    path_by_source = {item.predecessor_path_audit_id: item for item in paths}
    source_path_by_id = {item.audit_id: item for item in source_paths}
    jobs = []
    for index, source_job in enumerate(source_manifest.jobs):
        package = package_by_source[source_job.repair_task_package_id]
        source_path = source_path_by_id[source_job.repair_path_audit_id]
        path = path_by_source[source_path.audit_id]
        values = {
            "contract_id": contract.contract_id,
            "task_package_id": package.task_package_id,
            "path_audit_id": path.audit_id,
            "source_task_artifact_id": source_job.source_task_artifact_id,
            "mechanism_id": source_job.mechanism_id,
            "path_strategy_id": source_job.path_strategy_id,
            "source_role": source_job.source_role,
            "job_seed": _job_seed(index, source_job.job_id, contract.contract_id),
            "candidate_id": protocol.initial_candidate_id,
        }
        provisional = CompletionBoundJob.model_construct(job_id="pending", **values)
        jobs.append(
            CompletionBoundJob(
                job_id=completion_bound_job_id(provisional),
                **values,
            )
        )
    if len({item.job_seed for item in jobs}) != 32:
        raise ValueError("Completion-bound Job seeds are not distinct")
    ordered = tuple(jobs)
    mechanism_counts = dict(sorted(Counter(item.mechanism_id for item in ordered).items()))
    path_counts = dict(sorted(Counter(item.path_strategy_id for item in ordered).items()))
    cell_counts = dict(
        sorted(Counter(f"{item.mechanism_id}|{item.path_strategy_id}" for item in ordered).items())
    )
    values = {
        "contract_id": contract.contract_id,
        "candidate_id": protocol.initial_candidate_id,
        "jobs": ordered,
        "mechanism_job_counts": mechanism_counts,
        "path_job_counts": path_counts,
        "cell_job_counts": cell_counts,
    }
    provisional = CompletionBoundManifest.model_construct(manifest_id="pending", **values)
    return CompletionBoundManifest(
        manifest_id=completion_bound_manifest_id(provisional),
        **values,
    )


def _build_freshness(
    *,
    package_root: Path,
    task_packages: Sequence[CompletionBoundTaskPackage],
    contract: CompletionBoundContract,
    manifest: CompletionBoundManifest,
) -> CompletionBoundFreshnessAudit:
    source_packages, _, source_manifest = _load_v26_94_inputs(package_root)
    if set(item.task_package_id for item in task_packages) & set(
        item.task_package_id for item in source_packages
    ):
        raise ValueError("Completion-bound TaskPackage reused a historical identity")
    if set(item.job_id for item in manifest.jobs) & set(
        item.job_id for item in source_manifest.jobs
    ):
        raise ValueError("Completion-bound Job reused a historical identity")
    if contract.contract_id == source_manifest.repair_contract_id:
        raise ValueError("Completion-bound Contract reused the v26.95 identity")
    if manifest.manifest_id == source_manifest.manifest_id:
        raise ValueError("Completion-bound Manifest reused the v26.95 identity")
    provisional = CompletionBoundFreshnessAudit.model_construct(audit_id="pending")
    return CompletionBoundFreshnessAudit(audit_id=completion_bound_freshness_audit_id(provisional))


def _expect_rejection(name: str, action: Callable[[], Any]) -> MutationResult:
    try:
        action()
    except Exception as exc:
        values = {"mutation_name": name, "failure_type": type(exc).__name__}
        provisional = MutationResult.model_construct(mutation_id="pending", **values)
        return MutationResult(
            mutation_id=mutation_result_id(provisional),
            **values,
        )
    raise ValueError(f"destructive mutation was accepted: {name}")


def _validated_update(model: BaseModel, **updates: Any) -> Any:
    payload = model.model_dump(mode="json")
    payload.update(updates)
    return type(model).model_validate(payload)


def _build_destructive_audit(
    *,
    protocol: ProspectiveThinkingCompletionBoundProtocol,
    dynamic: DynamicRescueCoverageAudit,
    compiler_states: Sequence[CompilerPromptState],
    exposure: SourceExposureAudit,
    contract: CompletionBoundContract,
    manifest: CompletionBoundManifest,
) -> CompletionBoundDestructiveAudit:
    sample = next(item for item in dynamic.rows if item.source_kind == "compiler_registered")
    sample_primary = next(
        item.primary_prompt
        for item in compiler_states
        if _sha256_text(item.primary_prompt) == sample.primary_prompt_sha256
    )
    bloated_payload = json.loads(sample_primary.partition("\n")[2])
    if "public_context" in bloated_payload:
        bloated_payload["public_context"]["task"]["instruction"] = "x" * 7000
    bloated_primary = (
        sample_primary.partition("\n")[0]
        + "\n"
        + json.dumps(
            bloated_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    candidate = protocol.candidates[0]
    candidate_payload = candidate.model_dump(mode="json")
    candidate_payload.update(
        {
            "candidate_id": "mutated",
            "completion_upper_bound_tokens": 4096,
            "rollout_upper_bound_tokens": 120000,
        }
    )
    cert = certify_dynamic_primary_pre_call(
        protocol=protocol,
        candidate_id=protocol.initial_candidate_id,
        request_kind=sample.request_kind,
        primary_prompt=sample_primary,
        cumulative_usage_tokens_before_request=0,
        required_future_reserve_tokens=0,
    )
    if cert.certificate_id != sample.primary_certificate_id:
        raise ValueError("dynamic Primary certificate fixture changed")
    mutations = (
        _expect_rejection(
            "same_4096_completion_candidate",
            lambda: CompletionBoundCandidate.model_validate(candidate_payload),
        ),
        _expect_rejection(
            "automatic_same_run_fallback",
            lambda: _validated_update(protocol, fallback_automatic_execution_allowed=True),
        ),
        _expect_rejection(
            "semantic_outcome_bound_selection",
            lambda: _validated_update(protocol, semantic_validity_can_select_bound=True),
        ),
        _expect_rejection(
            "fallback_execution_jobs_materialized",
            lambda: _validated_update(protocol, fallback_materialized_as_execution_job=True),
        ),
        _expect_rejection(
            "dynamic_rescue_above_absolute_cap",
            lambda: certify_dynamic_rescue_pre_call(
                protocol=protocol,
                candidate_id=protocol.initial_candidate_id,
                request_kind=sample.request_kind,
                primary_prompt=bloated_primary,
                failure_type="invalid_json",
                cumulative_usage_tokens_before_request=0,
                required_future_reserve_tokens=0,
            ),
        ),
        _expect_rejection(
            "dynamic_request_kind_mismatch",
            lambda: certify_dynamic_primary_pre_call(
                protocol=protocol,
                candidate_id=protocol.initial_candidate_id,
                request_kind=("final_answer" if sample.request_kind == "decision" else "decision"),
                primary_prompt=sample_primary,
                cumulative_usage_tokens_before_request=0,
                required_future_reserve_tokens=0,
            ),
        ),
        _expect_rejection(
            "provider_call_before_certificate",
            lambda: _validated_update(cert, provider_call_count_before_certificate=1),
        ),
        _expect_rejection(
            "missing_primary_certificate",
            lambda: _validated_update(cert, actual_primary_prompt_certificate_passed=False),
        ),
        _expect_rejection(
            "missing_resource_certificate",
            lambda: _validated_update(cert, actual_resource_certificate_passed=False),
        ),
        _expect_rejection(
            "one_token_rollout_overflow",
            lambda: certify_dynamic_primary_pre_call(
                protocol=protocol,
                candidate_id=protocol.initial_candidate_id,
                request_kind=sample.request_kind,
                primary_prompt=sample_primary,
                cumulative_usage_tokens_before_request=(
                    candidate.rollout_upper_bound_tokens - cert.request_token_upper_bound + 1
                ),
                required_future_reserve_tokens=0,
            ),
        ),
        _expect_rejection(
            "previous_content_injection",
            lambda: certify_dynamic_primary_pre_call(
                protocol=protocol,
                candidate_id=protocol.initial_candidate_id,
                request_kind=sample.request_kind,
                primary_prompt=sample_primary.replace(
                    '"response_contract":',
                    '"previous_final_content":"forbidden","response_contract":',
                ),
                cumulative_usage_tokens_before_request=0,
                required_future_reserve_tokens=0,
            ),
        ),
        _expect_rejection(
            "private_reasoning_injection",
            lambda: certify_dynamic_primary_pre_call(
                protocol=protocol,
                candidate_id=protocol.initial_candidate_id,
                request_kind=sample.request_kind,
                primary_prompt=sample_primary.replace(
                    '"response_contract":',
                    '"reasoning_content":"forbidden","response_contract":',
                ),
                cumulative_usage_tokens_before_request=0,
                required_future_reserve_tokens=0,
            ),
        ),
        _expect_rejection(
            "source_reuse_claimed_fresh",
            lambda: _validated_update(exposure, source_tasks_claimed_fresh=True),
        ),
        _expect_rejection(
            "completion_gate_relaxation",
            lambda: _validated_update(contract, zero_failure_completion_gate_retained=False),
        ),
        _expect_rejection(
            "execution_without_runner",
            lambda: _validated_update(contract, execution_authorized=True),
        ),
        _expect_rejection(
            "capability_execution_authorization",
            lambda: _validated_update(contract, capability_execution_authorized=True),
        ),
        _expect_rejection(
            "fallback_job_inserted",
            lambda: _validated_update(manifest, fallback_job_count=1),
        ),
        _expect_rejection(
            "historical_job_identity_reuse",
            lambda: _validated_update(
                manifest,
                historical_v26_95_job_overlap_count=1,
            ),
        ),
    )
    values = {"mutation_results": mutations}
    provisional = CompletionBoundDestructiveAudit.model_construct(audit_id="pending", **values)
    return CompletionBoundDestructiveAudit(
        audit_id=completion_bound_destructive_audit_id(provisional),
        **values,
    )


def _detail_file(output_dir: Path, name: str, record_count: int) -> DetailFile:
    return DetailFile(
        relative_path=name,
        sha256=_sha256(output_dir / name),
        record_count=record_count,
    )


def build_thinking_completion_bound_redesign_preflight(
    *,
    run_id: str,
    output_dir: Path,
    package_root: Path,
) -> CompletionBoundPreflightReport:
    if run_id != RUN_ID:
        raise ValueError("v26.97 run identity changed")
    source = _build_source_replay(package_root)
    evidence = _build_evidence_audit(package_root)
    protocol = make_prospective_completion_bound_protocol(
        predecessor_transition_contract_id=EXPECTED_V26_96_TRANSITION_ID
    )
    exposure, exposed_task_packages = _build_source_exposure(package_root)
    task_packages = _build_task_packages(
        package_root=package_root,
        protocol=protocol,
        exposed_task_packages=exposed_task_packages,
    )
    dynamic, compiler_states = _build_dynamic_coverage(
        package_root=package_root,
        protocol=protocol,
    )
    paths = _build_path_audits(
        protocol=protocol,
        task_packages=task_packages,
        compiler_states=compiler_states,
        dynamic=dynamic,
    )
    contract = _build_contract(
        source=source,
        evidence=evidence,
        exposure=exposure,
        protocol=protocol,
        dynamic=dynamic,
        task_packages=task_packages,
        paths=paths,
    )
    manifest = _build_manifest(
        package_root=package_root,
        contract=contract,
        protocol=protocol,
        task_packages=task_packages,
        paths=paths,
    )
    freshness = _build_freshness(
        package_root=package_root,
        task_packages=task_packages,
        contract=contract,
        manifest=manifest,
    )
    destructive = _build_destructive_audit(
        protocol=protocol,
        dynamic=dynamic,
        compiler_states=compiler_states,
        exposure=exposure,
        contract=contract,
        manifest=manifest,
    )

    details: dict[str, tuple[Any, int]] = {
        "source_replay_audit.json": (source.model_dump(mode="json"), len(source.entries)),
        "completion_bound_evidence_audit.json": (evidence.model_dump(mode="json"), 1),
        "completion_bound_protocol.json": (protocol.model_dump(mode="json"), 1),
        "source_exposure_audit.json": (exposure.model_dump(mode="json"), 24),
        "completion_bound_task_packages.json": (
            [item.model_dump(mode="json") for item in task_packages],
            len(task_packages),
        ),
        "dynamic_rescue_coverage_audit.json": (dynamic.model_dump(mode="json"), len(dynamic.rows)),
        "completion_bound_path_audits.json": (
            [item.model_dump(mode="json") for item in paths],
            len(paths),
        ),
        "completion_bound_contract.json": (contract.model_dump(mode="json"), 1),
        "completion_bound_job_manifest.json": (
            manifest.model_dump(mode="json"),
            len(manifest.jobs),
        ),
        "completion_bound_freshness_audit.json": (freshness.model_dump(mode="json"), 1),
        "destructive_preflight_audit.json": (destructive.model_dump(mode="json"), 18),
    }
    for name, (payload, _) in details.items():
        _write_json(output_dir / name, payload)
    detail_files = tuple(
        _detail_file(output_dir, name, count) for name, (_, count) in sorted(details.items())
    )
    values = {
        "source_replay_audit_id": source.audit_id,
        "evidence_audit_id": evidence.audit_id,
        "source_exposure_audit_id": exposure.audit_id,
        "protocol_id": protocol.protocol_id,
        "dynamic_rescue_coverage_audit_id": dynamic.audit_id,
        "contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "freshness_audit_id": freshness.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "detail_files": detail_files,
    }
    provisional = CompletionBoundPreflightReport.model_construct(report_id="pending", **values)
    report = CompletionBoundPreflightReport(
        report_id=completion_bound_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the v26.97 Thinking Completion-bound redesign preflight"
    )
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    report = build_thinking_completion_bound_redesign_preflight(
        run_id=args.run_id,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
