from __future__ import annotations

import argparse
import hashlib
import json
import threading
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from math import comb
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.core.trajectory.executable_task import (
    matching_sufficient_support_set,
)
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.domains.finance.executable_support_runtime import (
    FinanceExecutableSupportRuntime,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceTypedRecoveryScenario,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
    AuthorityPreservingReplayResult,
    AuthorityPreservingVerificationReport,
    authority_preserving_verification_report_id,
    replay_authority_preserving_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_feasible_role_task_rematerialization import (  # noqa: E501
    BudgetQualifiedPathAudit,
    CompactPromptContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    FAILURE_STAGE_ORDER,
    VERIFICATION_CHECK_IDS,
    MechanismEstimandOutcome,
    evaluate_mechanism_estimand,
    match_empirical_program,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    ImplementationSourceFile,
    OperationalTaskRecord,
    PathStrategy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_preflight import (  # noqa: E501
    FUTURE_EXECUTION_RUN_ID,
    ThinkingCompletionRepairContract,
    ThinkingCompletionTelemetryRepairPreflightReport,
    ThinkingRepairJob,
    ThinkingRepairManifest,
    ThinkingRepairPathAudit,
    ThinkingRepairTaskPackage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    VerifierV2TaskReplayBinding,
    _load_and_replay_verifier_qualification,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import LLMClientError
from trusted_synthesis.runtime.agent.budget_closed import (
    ProviderBudgetNoCallTerminal,
    ProviderTokenBudgetAudit,
    ProviderTokenBudgetCertificate,
    ProviderTokenBudgetContract,
    ProviderTokenUsageRecord,
    provider_budget_no_call_terminal_id,
    provider_token_budget_audit_id,
    provider_token_budget_certificate_id,
    provider_token_usage_record_id,
)
from trusted_synthesis.runtime.agent.compact_budget_prompt import (
    compact_public_progress,
    render_compact_decision_prompt,
    render_compact_final_prompt,
)
from trusted_synthesis.runtime.agent.iterative import (
    _assert_no_model_forbidden_fields,
    _execute_tool,
    _operation_step_rejection,
    _tool_call_signature,
)
from trusted_synthesis.runtime.agent.prospective_thinking import (
    bind_prospective_thinking,
)
from trusted_synthesis.runtime.agent.prospective_thinking_client import (
    ProspectiveThinkingJsonClient,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    CompletionFailureKind,
    CompletionProjection,
    CompletionRequestKind,
    ProspectiveThinkingFailureArtifact,
    RedactedProviderResponseEnvelope,
    make_prospective_thinking_failure_artifact,
    project_model_completion,
    render_primary_completion_prompt,
    render_rescue_completion_prompt,
    serialize_validated_failure_artifact,
)
from trusted_synthesis.runtime.agent.public_operation import (
    public_action_neutral_repair_result,
    public_operation_step_rejection,
    public_postcompletion_action_rejection,
    public_terminal_verification_rejection,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import (
    ARGUMENT_PATCH_REQUIRED_POLICY,
    AgentToolCall,
    AgentToolEnvironmentManifest,
    AgentToolObservation,
    AgentToolResult,
    agent_tool_argument_rejection,
    make_agent_tool_observation,
)

V26_95_PREFLIGHT_REPLAY_VERSION: Final = "finance_v26_thinking_repair_runner_replay.v1"
V26_95_INTERPRETATION_VERSION: Final = "finance_v26_thinking_repair_outcome_interpretation.v1"
V26_95_EXECUTION_CONTRACT_VERSION: Final = "finance_v26_thinking_repair_execution_contract.v1"
V26_95_PREFLIGHT_REPORT_VERSION: Final = "finance_v26_thinking_repair_execution_preflight_report.v1"
V26_95_PROVIDER_CALL_VERSION: Final = "finance_v26_thinking_repair_provider_call.v1"
V26_95_REQUEST_ATTEMPT_VERSION: Final = "finance_v26_thinking_repair_request_attempt.v1"
V26_95_LOGICAL_REQUEST_VERSION: Final = "finance_v26_thinking_repair_logical_request.v1"
V26_95_COMPLETED_RESULT_VERSION: Final = "finance_v26_thinking_repair_completed_result.v1"
V26_95_RAW_EXECUTION_VERSION: Final = "finance_v26_thinking_repair_raw_execution.v1"
V26_95_JOB_RESULT_VERSION: Final = "finance_v26_thinking_repair_job_result.v1"
V26_95_CELL_SUMMARY_VERSION: Final = "finance_v26_thinking_repair_cell_summary.v1"
V26_95_RAW_LINEAGE_VERSION: Final = "finance_v26_thinking_repair_raw_lineage.v1"
V26_95_EXECUTION_REPORT_VERSION: Final = "finance_v26_thinking_repair_execution_report.v1"

V26_94_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821"
)
V26_90_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821"
)
MODEL_PROFILE_PATH: Final = "config/deepseek_v4_flash_agent_thinking_v1.json"
RUNNER_SOURCE_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_completion_telemetry_repair_execution.py"
)
RUNNER_PREFLIGHT_SOURCE_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_completion_telemetry_repair_execution_preflight.py"
)
EXPECTED_V26_94_REPORT_ID: Final = (
    "finance_v26_thinking_completion_telemetry_repair_preflight_report:"
    "efae8ea77b8b67a48cb0cfd90559df7fd77b313855a6088ee778ab1dc8926689"
)
EXPECTED_V26_94_CONTRACT_ID: Final = (
    "finance_v26_thinking_repair_contract:"
    "573eb1493ad87832eade20407db775b093a7c4168c63bf19113ee5ceb4dd4f72"
)
EXPECTED_V26_94_MANIFEST_ID: Final = (
    "finance_v26_thinking_repair_manifest:"
    "56ada3c9430d56c20c6611986cc0fa51f19c3f80fbee3b7b63b07dffddcf5945"
)
EXPECTED_COMPLETION_PROTOCOL_ID: Final = (
    "prospective_thinking_completion_protocol:"
    "4fd11877d7a7ed795efc80e07382cea4dd2ba7c3915bfe05439665301084f5f1"
)
EXPECTED_MODEL_CONFIG_ID: Final = (
    "agent_model_config:727b3867544c4eac844eb260b9673dee41be7b8787b07ea2e3d6c69113e68bd1"
)
EXPECTED_THINKING_BINDING_ID: Final = (
    "prospective_thinking_model_binding:"
    "51315bb03b5df2751c0cfada843fc75627c45b544d26efdd9ddac746a780f77d"
)
EXPECTED_PROVIDER_BUDGET_CONTRACT_ID: Final = (
    "provider_token_budget_contract:"
    "27e7e524cb3139b9dd29b1ca7f2c7eae1956c96af8a982524f814b3ef4415150"
)
EXACT_MODEL_ID: Final = "deepseek-v4-flash"
JOB_COUNT: Final = 32
DEFAULT_WORKERS: Final = 8
ZERO_FAILURE_CP95_AT_32: Final = 0.08936819898626475
ONE_FAILURE_CP95_AT_32: Final = 0.13984946027422601

TerminalCategory = Literal[
    "model_valid_trajectory",
    "model_invalid_trajectory",
    "typed_budget_no_call",
    "completion_unusable",
    "provider_transport_failure",
    "instrument_failure",
]
AttemptPhase = Literal["primary", "rescue"]
AttemptDisposition = Literal[
    "usable",
    "completion_failure",
    "provider_transport_failure",
    "typed_budget_no_call",
    "instrument_failure",
]
LogicalRequestOutcome = Literal[
    "direct_usable",
    "rescued_usable",
    "terminal_completion_unusable",
    "terminal_provider_transport_failure",
    "terminal_typed_budget_no_call",
    "terminal_instrument_failure",
]
ActualRoute = Literal[
    "structured_direct",
    "search_then_structured",
    "search_then_open",
    "search_only",
    "mixed_or_unresolved",
    "none",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=0)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_digest(self) -> ReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("v26.95 Runner source replay digest mismatch")
        return self


class ThinkingRepairRunnerSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_94_REPORT_ID
    entries: tuple[ReplayEntry, ...] = Field(min_length=490)
    v26_94_output_file_count: Literal[11] = 11
    v26_94_replay_binding_file_count: Literal[485] = 485
    new_implementation_file_count: Literal[2] = 2
    replayed_file_count: int = Field(ge=498)
    replay_pass_count: int = Field(ge=498)
    replay_before_credential_lookup: Literal[True] = True
    replay_before_client_construction: Literal[True] = True
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_thinking_repair_runner_replay.v1"] = (
        V26_95_PREFLIGHT_REPLAY_VERSION
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ThinkingRepairRunnerSourceReplayAudit:
        keys = tuple((item.source_kind, item.relative_path) for item in self.entries)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("v26.95 Runner replay entries are not canonical")
        if self.replayed_file_count != len(self.entries):
            raise ValueError("v26.95 Runner replay denominator changed")
        if self.replay_pass_count != self.replayed_file_count:
            raise ValueError("v26.95 Runner replay is incomplete")
        if self.audit_id != thinking_repair_runner_source_replay_audit_id(self):
            raise ValueError("v26.95 Runner replay identity mismatch")
        return self


class ThinkingRepairOutcomeInterpretationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    exact_job_denominator: Literal[32] = 32
    zero_failure_gate_threshold: float = 0.10
    zero_failure_cp95_upper_bound: float = ZERO_FAILURE_CP95_AT_32
    one_failure_cp95_upper_bound: float = ONE_FAILURE_CP95_AT_32
    pass_transition: Literal["thinking_role_protocol_freeze_only"] = (
        "thinking_role_protocol_freeze_only"
    )
    length_failure_transition: Literal[
        "thinking_completion_bound_or_two_stage_protocol_redesign_only"
    ] = "thinking_completion_bound_or_two_stage_protocol_redesign_only"
    nonlength_completion_failure_transition: Literal[
        "thinking_completion_contract_root_cause_audit_only"
    ] = "thinking_completion_contract_root_cause_audit_only"
    telemetry_only_failure_transition: Literal[
        "thinking_response_telemetry_wrapper_repair_only"
    ] = "thinking_response_telemetry_wrapper_repair_only"
    budget_failure_transition: Literal["thinking_repair_budget_deviation_audit_only"] = (
        "thinking_repair_budget_deviation_audit_only"
    )
    transport_failure_transition: Literal[
        "thinking_repair_execution_recovery_or_transport_audit_only"
    ] = "thinking_repair_execution_recovery_or_transport_audit_only"
    other_instrument_failure_transition: Literal[
        "thinking_repair_instrument_root_cause_audit_only"
    ] = "thinking_repair_instrument_root_cause_audit_only"
    same_bound_prompt_only_retuning_after_length_failure_allowed: Literal[False] = False
    completion_success_cannot_establish_capability: Literal[True] = True
    low_program_closure_cannot_reopen_completion_optimization: Literal[True] = True
    telemetry_only_repair_must_hold_completion_protocol_fixed: Literal[True] = True
    fresh_role_population_required_after_pass: Literal[True] = True
    schema_version: Literal["finance_v26_thinking_repair_outcome_interpretation.v1"] = (
        V26_95_INTERPRETATION_VERSION
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ThinkingRepairOutcomeInterpretationContract:
        if not (
            self.zero_failure_cp95_upper_bound
            <= self.zero_failure_gate_threshold
            < self.one_failure_cp95_upper_bound
        ):
            raise ValueError("v26.95 interpretation no longer requires zero failures")
        if self.contract_id != thinking_repair_outcome_interpretation_contract_id(self):
            raise ValueError("v26.95 outcome interpretation identity mismatch")
        return self


class ThinkingRepairExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_run_id: str = FUTURE_EXECUTION_RUN_ID
    predecessor_report_id: str = EXPECTED_V26_94_REPORT_ID
    predecessor_contract_id: str = EXPECTED_V26_94_CONTRACT_ID
    predecessor_manifest_id: str = EXPECTED_V26_94_MANIFEST_ID
    completion_protocol_id: str = EXPECTED_COMPLETION_PROTOCOL_ID
    source_replay_audit_id: str = Field(min_length=1)
    outcome_interpretation_contract_id: str = Field(min_length=1)
    model_config_id: str = EXPECTED_MODEL_CONFIG_ID
    thinking_binding_id: str = EXPECTED_THINKING_BINDING_ID
    provider_budget_contract_id: str = EXPECTED_PROVIDER_BUDGET_CONTRACT_ID
    job_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
    runner_implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=2,
        max_length=2,
    )
    exact_model_id: Literal["deepseek-v4-flash"] = EXACT_MODEL_ID
    thinking_type: Literal["enabled"] = "enabled"
    completion_upper_bound_tokens: Literal[4096] = 4096
    rollout_upper_bound_tokens: Literal[120000] = 120000
    prompt_upper_bound_bytes: Literal[60000] = 60000
    maximum_rescue_calls_per_job: Literal[1] = 1
    model_plan_calls_per_job: Literal[0] = 0
    transient_provider_retries_per_request: Literal[0] = 0
    provider_config_contract_repair_loop_used: Literal[False] = False
    rescue_is_explicitly_typed_for_budget: Literal[True] = True
    raw_redacted_provider_artifact_persisted_before_projection: Literal[True] = True
    response_envelope_captured_before_content_parse: Literal[True] = True
    previous_final_content_persisted: Literal[False] = False
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    every_job_executed_at_most_once: Literal[True] = True
    orphan_provider_artifact_requires_new_recovery: Literal[True] = True
    typed_no_call_gate_requires_zero_failures: Literal[True] = True
    completion_unusable_gate_requires_zero_failures: Literal[True] = True
    semantic_validity_cannot_rescue_failure_gates: Literal[True] = True
    role_population_rows_eligible: Literal[False] = False
    execution_authorized: Literal[True] = True
    schema_version: Literal["finance_v26_thinking_repair_execution_contract.v1"] = (
        V26_95_EXECUTION_CONTRACT_VERSION
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ThinkingRepairExecutionContract:
        if (
            self.execution_run_id,
            self.predecessor_report_id,
            self.predecessor_contract_id,
            self.predecessor_manifest_id,
            self.completion_protocol_id,
            self.model_config_id,
            self.thinking_binding_id,
            self.provider_budget_contract_id,
        ) != (
            FUTURE_EXECUTION_RUN_ID,
            EXPECTED_V26_94_REPORT_ID,
            EXPECTED_V26_94_CONTRACT_ID,
            EXPECTED_V26_94_MANIFEST_ID,
            EXPECTED_COMPLETION_PROTOCOL_ID,
            EXPECTED_MODEL_CONFIG_ID,
            EXPECTED_THINKING_BINDING_ID,
            EXPECTED_PROVIDER_BUDGET_CONTRACT_ID,
        ):
            raise ValueError("v26.95 execution predecessor identity changed")
        if self.job_ids != tuple(sorted(set(self.job_ids))):
            raise ValueError("v26.95 execution Job identities are not canonical")
        paths = tuple(item.relative_path for item in self.runner_implementation_source_files)
        if paths != tuple(sorted((RUNNER_PREFLIGHT_SOURCE_PATH, RUNNER_SOURCE_PATH))):
            raise ValueError("v26.95 execution implementation binding is incomplete")
        if self.contract_id != thinking_repair_execution_contract_id(self):
            raise ValueError("v26.95 execution Contract identity mismatch")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class ThinkingRepairExecutionPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    execution_run_id: str = FUTURE_EXECUTION_RUN_ID
    predecessor_report_id: str = EXPECTED_V26_94_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    outcome_interpretation_contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    runner_fixture_audit_id: str = Field(min_length=1)
    budget_recovery_audit_id: str = Field(min_length=1)
    destructive_preflight_audit_id: str = Field(min_length=1)
    source_replayed_file_count: int = Field(ge=498)
    exact_job_count: Literal[32] = 32
    direct_fixture_job_count: Literal[32] = 32
    rescue_fixture_count: Literal[5] = 5
    detail_files: tuple[DetailFile, ...] = Field(min_length=6, max_length=6)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=2,
        max_length=2,
    )
    formal_independent_rebuild_required: Literal[True] = True
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    execution_runner_materialized: Literal[True] = True
    repair_execution_authorized: Literal[True] = True
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal["thinking_completion_telemetry_repair_execution_only"] = (
        "thinking_completion_telemetry_repair_execution_only"
    )
    schema_version: Literal["finance_v26_thinking_repair_execution_preflight_report.v1"] = (
        V26_95_PREFLIGHT_REPORT_VERSION
    )

    @model_validator(mode="after")
    def validate_report(self) -> ThinkingRepairExecutionPreflightReport:
        if self.execution_run_id != FUTURE_EXECUTION_RUN_ID:
            raise ValueError("v26.95 execution run changed")
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.95 preflight detail files are not canonical")
        if self.report_id != thinking_repair_execution_preflight_report_id(self):
            raise ValueError("v26.95 preflight report identity mismatch")
        return self


class RawFileDescriptor(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)


class ThinkingRepairRawProviderCall(FrozenModel):
    artifact_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    call_index: int = Field(ge=0)
    phase: AttemptPhase
    request_kind: CompletionRequestKind
    provider_call_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    prompt_sha256: str = Field(min_length=64, max_length=64)
    response_payload: dict[str, Any] | None = None
    provider_telemetry: ModelCallTelemetry
    failure_artifact: ProspectiveThinkingFailureArtifact | None = None
    captured_before_completion_projection: Literal[True] = True
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    schema_version: Literal["finance_v26_thinking_repair_provider_call.v1"] = (
        V26_95_PROVIDER_CALL_VERSION
    )

    @model_validator(mode="after")
    def validate_artifact(self) -> ThinkingRepairRawProviderCall:
        if self.prompt_sha256 != _sha256_text(self.prompt):
            raise ValueError("v26.95 raw Provider Prompt hash changed")
        if self.provider_telemetry.request_hash != self.prompt_sha256:
            raise ValueError("v26.95 raw Prompt differs from Provider telemetry")
        if self.failure_artifact is not None:
            if self.failure_artifact.request_hash != self.prompt_sha256:
                raise ValueError("v26.95 failure Artifact Prompt hash changed")
            serialize_validated_failure_artifact(self.failure_artifact)
        if _contains_private_reasoning_key(self.response_payload):
            raise ValueError("v26.95 public response payload contains private reasoning")
        expected = thinking_repair_provider_call_id(
            self.job_id,
            self.call_index,
            self.provider_telemetry,
        )
        if self.provider_call_id != expected:
            raise ValueError("v26.95 Provider call identity mismatch")
        if self.artifact_id != thinking_repair_raw_provider_call_id(self):
            raise ValueError("v26.95 raw Provider Artifact identity mismatch")
        return self


class ThinkingRepairRequestAttempt(FrozenModel):
    attempt_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    provider_call_index: int | None = Field(default=None, ge=0)
    phase: AttemptPhase
    request_kind: CompletionRequestKind
    prompt_sha256: str = Field(min_length=64, max_length=64)
    prompt_utf8_bytes: int = Field(gt=0)
    registered_request_present: bool
    registered_request_kind_match: bool
    registered_primary_prompt_match: bool
    rescue_prompt_strictly_shorter: bool | None = None
    rescue_prompt_reduction_basis_points: int | None = Field(default=None, ge=1000)
    provider_call_made: bool
    response_payload_present: bool
    completion_projection: CompletionProjection | None = None
    failure_artifact: ProspectiveThinkingFailureArtifact | None = None
    disposition: AttemptDisposition
    error: str | None = None
    previous_final_content_reused: Literal[False] = False
    private_reasoning_reused: Literal[False] = False
    host_action_inserted: Literal[False] = False
    schema_version: Literal["finance_v26_thinking_repair_request_attempt.v1"] = (
        V26_95_REQUEST_ATTEMPT_VERSION
    )

    @model_validator(mode="after")
    def validate_attempt(self) -> ThinkingRepairRequestAttempt:
        if self.provider_call_made != (self.provider_call_index is not None):
            raise ValueError("v26.95 Provider attempt index accounting changed")
        if (self.completion_projection is not None) != (self.disposition == "usable"):
            raise ValueError("v26.95 usable attempt projection accounting changed")
        if self.disposition == "completion_failure" and self.failure_artifact is None:
            raise ValueError("v26.95 Completion failure lacks a typed Artifact")
        if self.phase == "rescue":
            if self.rescue_prompt_strictly_shorter is not True:
                raise ValueError("v26.95 Rescue Prompt is not strictly shorter")
            if self.rescue_prompt_reduction_basis_points is None:
                raise ValueError("v26.95 Rescue Prompt reduction is missing")
        elif (
            self.rescue_prompt_strictly_shorter is not None
            or self.rescue_prompt_reduction_basis_points is not None
        ):
            raise ValueError("v26.95 Primary attempt carries Rescue diagnostics")
        if self.attempt_id != thinking_repair_request_attempt_id(self):
            raise ValueError("v26.95 request attempt identity mismatch")
        return self


class ThinkingRepairLogicalRequest(FrozenModel):
    request_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    request_kind: CompletionRequestKind
    source_prompt_sha256: str = Field(min_length=64, max_length=64)
    primary_attempt_id: str = Field(min_length=1)
    rescue_attempt_id: str | None = None
    rescue_used: bool
    initial_failure_type: CompletionFailureKind | None = None
    outcome: LogicalRequestOutcome
    usable: bool
    schema_version: Literal["finance_v26_thinking_repair_logical_request.v1"] = (
        V26_95_LOGICAL_REQUEST_VERSION
    )

    @model_validator(mode="after")
    def validate_request(self) -> ThinkingRepairLogicalRequest:
        if self.rescue_used != (self.rescue_attempt_id is not None):
            raise ValueError("v26.95 Rescue identity accounting changed")
        if self.rescue_used != (self.initial_failure_type is not None):
            raise ValueError("v26.95 initial Rescue failure accounting changed")
        if self.usable != (self.outcome in {"direct_usable", "rescued_usable"}):
            raise ValueError("v26.95 logical Completion usability changed")
        if self.request_id != thinking_repair_logical_request_id(self):
            raise ValueError("v26.95 logical request identity mismatch")
        return self


class ThinkingRepairCompletedResult(FrozenModel):
    result_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    observations: tuple[AgentToolObservation, ...] = Field(min_length=1)
    answer: dict[str, Any]
    cited_evidence_ids: tuple[str, ...] = Field(min_length=1)
    final_request_id: str = Field(min_length=1)
    stopped_by_model: Literal[True] = True
    host_plan_materialized: Literal[False] = False
    host_action_insertions: Literal[0] = 0
    schema_version: Literal["finance_v26_thinking_repair_completed_result.v1"] = (
        V26_95_COMPLETED_RESULT_VERSION
    )

    @model_validator(mode="after")
    def validate_result(self) -> ThinkingRepairCompletedResult:
        if self.cited_evidence_ids != tuple(sorted(set(self.cited_evidence_ids))):
            raise ValueError("v26.95 projected citations are not canonical")
        if self.result_id != thinking_repair_completed_result_id(self):
            raise ValueError("v26.95 completed result identity mismatch")
        return self


class ThinkingRepairRawExecution(FrozenModel):
    artifact_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    job: ThinkingRepairJob
    operational_record_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    path_audit_id: str = Field(min_length=1)
    provider_call_artifacts: tuple[RawFileDescriptor, ...]
    provider_call_ids: tuple[str, ...]
    provider_telemetry: tuple[ModelCallTelemetry, ...]
    provider_prompts: tuple[str, ...]
    request_attempts: tuple[ThinkingRepairRequestAttempt, ...] = Field(min_length=1)
    logical_requests: tuple[ThinkingRepairLogicalRequest, ...] = Field(min_length=1)
    provider_budget_audit: ProviderTokenBudgetAudit
    observations: tuple[AgentToolObservation, ...]
    completed_result: ThinkingRepairCompletedResult | None = None
    terminal_disposition: Literal[
        "completed",
        "model_invalid",
        "typed_budget_no_call",
        "completion_unusable",
        "provider_transport_failure",
        "instrument_failure",
    ]
    terminal_failure_type: str | None = None
    execution_error: str | None = None
    rescue_call_count: int = Field(ge=0, le=1)
    model_plan_call_count: Literal[0] = 0
    captured_before_verifier_scoring: Literal[True] = True
    private_reasoning_content_persisted: Literal[False] = False
    schema_version: Literal["finance_v26_thinking_repair_raw_execution.v1"] = (
        V26_95_RAW_EXECUTION_VERSION
    )

    @model_validator(mode="after")
    def validate_artifact(self) -> ThinkingRepairRawExecution:
        denominators = (
            len(self.provider_call_artifacts),
            len(self.provider_call_ids),
            len(self.provider_telemetry),
            len(self.provider_prompts),
        )
        if len(set(denominators)) != 1:
            raise ValueError("v26.95 Provider call denominators differ")
        if self.rescue_call_count != sum(item.phase == "rescue" for item in self.request_attempts):
            raise ValueError("v26.95 Rescue call denominator changed")
        if self.rescue_call_count > self.job.maximum_rescue_calls:
            raise ValueError("v26.95 Job exceeded its Rescue allowance")
        if (self.completed_result is not None) != (self.terminal_disposition == "completed"):
            raise ValueError("v26.95 completed-result disposition changed")
        if self.artifact_id != thinking_repair_raw_execution_id(self):
            raise ValueError("v26.95 raw execution identity mismatch")
        return self


class ThinkingRepairJobResult(FrozenModel):
    result_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    requested_path_strategy_id: PathStrategy
    terminal_category: TerminalCategory
    provider_call_count: int = Field(ge=0)
    http_success_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    provider_usage_complete: bool
    estimated_cost_usd: str = Field(min_length=1)
    reasoning_content_length_total: int = Field(ge=0)
    reasoning_tokens_total: int = Field(ge=0)
    completion_tokens_total: int = Field(ge=0)
    logical_request_count: int = Field(ge=1)
    direct_usable_request_count: int = Field(ge=0)
    rescued_usable_request_count: int = Field(ge=0)
    rescue_call_count: int = Field(ge=0, le=1)
    completion_limit_hit_count: int = Field(ge=0)
    completion_failure_counts: dict[str, int]
    typed_no_call: bool
    completion_unusable: bool
    provider_transport_failure: bool
    telemetry_failure: bool
    telemetry_only_failure: bool
    exact_model_passed: bool
    native_tool_absent: bool
    thinking_continuity_passed: bool
    fallback_absent: bool
    budget_contract_passed: bool
    observation_count: int = Field(ge=0)
    failed_observation_count: int = Field(ge=0)
    repeated_call_signature_count: int = Field(ge=0)
    repeated_failed_call_signature_count: int = Field(ge=0)
    completed_program_node_count: int = Field(ge=0)
    program_node_count: int = Field(ge=0)
    program_closed: bool
    terminal_node_completed: bool
    postterminal_verification_completed: bool
    mechanism_evaluated: bool
    mechanism_success: bool
    independent_validity: bool
    actual_route: ActualRoute
    requested_path_adhered: bool
    registered_primary_prompt_match_count: int = Field(ge=0)
    registered_request_kind_mismatch_count: int = Field(ge=0)
    replay_result: AuthorityPreservingReplayResult | None = None
    verification_report: AuthorityPreservingVerificationReport | None = None
    mechanism_outcome: MechanismEstimandOutcome | None = None
    no_call_terminal: ProviderBudgetNoCallTerminal | None = None
    raw_execution_artifact: RawFileDescriptor
    calibration_only: Literal[True] = True
    capability_denominator_eligible: Literal[False] = False
    reachability_denominator_eligible: Literal[False] = False
    state_mapping_eligible: Literal[False] = False
    release_eligible: Literal[False] = False
    failure_attribution: dict[str, Any] | None = None
    schema_version: Literal["finance_v26_thinking_repair_job_result.v1"] = V26_95_JOB_RESULT_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> ThinkingRepairJobResult:
        if self.reasoning_tokens_total > self.completion_tokens_total:
            raise ValueError("v26.95 reasoning Usage exceeds Completion Usage")
        if self.typed_no_call != (self.no_call_terminal is not None):
            raise ValueError("v26.95 typed no-call accounting changed")
        if self.telemetry_only_failure and (
            self.terminal_category != "instrument_failure" or not self.telemetry_failure
        ):
            raise ValueError("v26.95 telemetry-only classification changed")
        if self.requested_path_adhered != (self.actual_route == self.requested_path_strategy_id):
            raise ValueError("v26.95 requested-path adherence changed")
        if self.terminal_category == "model_valid_trajectory" and not self.independent_validity:
            raise ValueError("v26.95 valid terminal lacks independent validity")
        if self.independent_validity and self.verification_report is None:
            raise ValueError("v26.95 validity lacks a Verifier report")
        if self.result_id != thinking_repair_job_result_id(self):
            raise ValueError("v26.95 Job result identity mismatch")
        return self


class ThinkingRepairCellSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: PathStrategy
    job_count: int = Field(ge=2)
    typed_no_call_count: int = Field(ge=0)
    completion_unusable_count: int = Field(ge=0)
    provider_transport_failure_count: int = Field(ge=0)
    instrument_failure_count: int = Field(ge=0)
    rescue_job_count: int = Field(ge=0)
    rescued_usable_request_count: int = Field(ge=0)
    program_closed_count: int = Field(ge=0)
    mechanism_success_count: int = Field(ge=0)
    valid_trajectory_count: int = Field(ge=0)
    requested_path_adherence_count: int = Field(ge=0)
    mechanism_floor_observed: bool
    mechanism_saturation_observed: bool
    validity_floor_observed: bool
    validity_saturation_observed: bool
    descriptive_only: Literal[True] = True
    schema_version: Literal["finance_v26_thinking_repair_cell_summary.v1"] = (
        V26_95_CELL_SUMMARY_VERSION
    )

    @model_validator(mode="after")
    def validate_summary(self) -> ThinkingRepairCellSummary:
        if self.mechanism_floor_observed != (self.mechanism_success_count == 0):
            raise ValueError("v26.95 mechanism floor changed")
        if self.mechanism_saturation_observed != (self.mechanism_success_count == self.job_count):
            raise ValueError("v26.95 mechanism saturation changed")
        if self.validity_floor_observed != (self.valid_trajectory_count == 0):
            raise ValueError("v26.95 validity floor changed")
        if self.validity_saturation_observed != (self.valid_trajectory_count == self.job_count):
            raise ValueError("v26.95 validity saturation changed")
        if self.summary_id != thinking_repair_cell_summary_id(self):
            raise ValueError("v26.95 cell summary identity mismatch")
        return self


class ThinkingRepairRawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    expected_job_count: Literal[32] = 32
    raw_execution_count: Literal[32] = 32
    provider_call_count: int = Field(ge=0)
    unique_provider_call_count: int = Field(ge=0)
    files: tuple[RawFileDescriptor, ...] = Field(min_length=32)
    private_reasoning_payload_count: Literal[0] = 0
    exact_byte_replay_pass_count: int = Field(ge=32)
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_thinking_repair_raw_lineage.v1"] = (
        V26_95_RAW_LINEAGE_VERSION
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ThinkingRepairRawLineageAudit:
        paths = tuple(item.relative_path for item in self.files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.95 raw lineage paths are not canonical")
        if self.unique_provider_call_count != self.provider_call_count:
            raise ValueError("v26.95 Provider identities are not unique")
        if self.exact_byte_replay_pass_count != len(self.files):
            raise ValueError("v26.95 raw lineage replay is incomplete")
        if self.audit_id != thinking_repair_raw_lineage_audit_id(self):
            raise ValueError("v26.95 raw lineage identity mismatch")
        return self


class ThinkingRepairExecutionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    execution_run_id: str = FUTURE_EXECUTION_RUN_ID
    execution_contract_id: str = Field(min_length=1)
    preflight_report_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_94_REPORT_ID
    repair_contract_id: str = EXPECTED_V26_94_CONTRACT_ID
    repair_manifest_id: str = EXPECTED_V26_94_MANIFEST_ID
    outcome_interpretation_contract_id: str = Field(min_length=1)
    raw_lineage_audit_id: str = Field(min_length=1)
    expected_job_count: Literal[32] = 32
    completed_job_count: Literal[32] = 32
    terminal_counts: dict[str, int]
    provider_call_count: int = Field(ge=0)
    http_success_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    provider_usage_complete: bool
    estimated_cost_usd: str = Field(min_length=1)
    reasoning_content_length_total: int = Field(ge=0)
    reasoning_tokens_total: int = Field(ge=0)
    completion_tokens_total: int = Field(ge=0)
    logical_request_count: int = Field(ge=0)
    direct_usable_request_count: int = Field(ge=0)
    rescued_usable_request_count: int = Field(ge=0)
    rescue_call_count: int = Field(ge=0)
    rescue_job_count: int = Field(ge=0)
    completion_limit_hit_count: int = Field(ge=0)
    completion_failure_counts: dict[str, int]
    typed_no_call_job_count: int = Field(ge=0)
    typed_no_call_cp95_upper_32: float = Field(ge=0, le=1)
    typed_no_call_gate_passed: bool
    completion_unusable_job_count: int = Field(ge=0)
    completion_unusable_cp95_upper_32: float = Field(ge=0, le=1)
    completion_usability_gate_passed: bool
    provider_transport_failure_job_count: int = Field(ge=0)
    telemetry_failure_job_count: int = Field(ge=0)
    telemetry_only_failure_job_count: int = Field(ge=0)
    instrument_failure_job_count: int = Field(ge=0)
    exact_model_failure_job_count: int = Field(ge=0)
    native_tool_failure_job_count: int = Field(ge=0)
    thinking_continuity_failure_job_count: int = Field(ge=0)
    failed_observation_count: int = Field(ge=0)
    repeated_call_signature_count: int = Field(ge=0)
    repeated_failed_call_signature_count: int = Field(ge=0)
    requested_path_adherence_count: int = Field(ge=0)
    program_closed_count: int = Field(ge=0)
    mechanism_success_count: int = Field(ge=0)
    independently_valid_trajectory_count: int = Field(ge=0)
    cell_summaries: tuple[ThinkingRepairCellSummary, ...] = Field(
        min_length=12,
        max_length=12,
    )
    raw_lineage_passed: Literal[True] = True
    empirical_budget_adequacy_passed: bool
    completion_usability_passed: bool
    response_telemetry_instrument_passed: bool
    execution_integrity_passed: bool
    behavior_interpretation: Literal[
        "completion_channel_failed",
        "completion_channel_passed_behavior_floor",
        "completion_channel_passed_behavior_nonfloor",
        "instrument_or_transport_failed",
    ]
    behavior_diagnostics_descriptive_only: Literal[True] = True
    task_depth_informativeness_resolved: Literal[False] = False
    role_protocol_frozen: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    status: Literal["passed", "blocked"]
    next_permitted_stage: Literal[
        "thinking_role_protocol_freeze_only",
        "thinking_completion_bound_or_two_stage_protocol_redesign_only",
        "thinking_completion_contract_root_cause_audit_only",
        "thinking_response_telemetry_wrapper_repair_only",
        "thinking_repair_budget_deviation_audit_only",
        "thinking_repair_execution_recovery_or_transport_audit_only",
        "thinking_repair_instrument_root_cause_audit_only",
    ]
    schema_version: Literal["finance_v26_thinking_repair_execution_report.v1"] = (
        V26_95_EXECUTION_REPORT_VERSION
    )

    @model_validator(mode="after")
    def validate_report(self) -> ThinkingRepairExecutionReport:
        if sum(self.terminal_counts.values()) != self.completed_job_count:
            raise ValueError("v26.95 terminal denominator changed")
        if self.typed_no_call_gate_passed != (self.typed_no_call_cp95_upper_32 <= 0.10):
            raise ValueError("v26.95 no-call Gate arithmetic changed")
        if self.completion_usability_gate_passed != (
            self.completion_unusable_cp95_upper_32 <= 0.10
        ):
            raise ValueError("v26.95 Completion Gate arithmetic changed")
        passed = (
            self.typed_no_call_gate_passed
            and self.completion_usability_gate_passed
            and self.response_telemetry_instrument_passed
            and self.execution_integrity_passed
        )
        if (self.status == "passed") != passed:
            raise ValueError("v26.95 report status changed")
        expected_transition = (
            "thinking_repair_execution_recovery_or_transport_audit_only"
            if self.provider_transport_failure_job_count
            else (
                "thinking_response_telemetry_wrapper_repair_only"
                if (
                    self.instrument_failure_job_count
                    and self.telemetry_only_failure_job_count == self.instrument_failure_job_count
                )
                else "thinking_repair_instrument_root_cause_audit_only"
            )
            if self.instrument_failure_job_count
            else "thinking_repair_budget_deviation_audit_only"
            if self.typed_no_call_job_count
            else (
                "thinking_completion_bound_or_two_stage_protocol_redesign_only"
                if any(
                    self.completion_failure_counts.get(key, 0)
                    for key in (
                        "length_truncated_content",
                        "reasoning_only_length_truncation",
                    )
                )
                else "thinking_completion_contract_root_cause_audit_only"
            )
            if self.completion_unusable_job_count
            else "thinking_role_protocol_freeze_only"
        )
        if self.next_permitted_stage != expected_transition:
            raise ValueError("v26.95 report transition changed")
        expected_behavior = (
            "instrument_or_transport_failed"
            if not (self.response_telemetry_instrument_passed and self.execution_integrity_passed)
            else "completion_channel_failed"
            if self.completion_unusable_job_count
            else "completion_channel_passed_behavior_floor"
            if self.program_closed_count == 0
            else "completion_channel_passed_behavior_nonfloor"
        )
        if self.behavior_interpretation != expected_behavior:
            raise ValueError("v26.95 behavior interpretation changed")
        if self.report_id != thinking_repair_execution_report_id(self):
            raise ValueError("v26.95 execution report identity mismatch")
        return self


class _PreparedInputs(FrozenModel):
    preflight_report: ThinkingRepairExecutionPreflightReport
    execution_contract: ThinkingRepairExecutionContract
    interpretation_contract: ThinkingRepairOutcomeInterpretationContract
    predecessor_report: ThinkingCompletionTelemetryRepairPreflightReport
    repair_contract: ThinkingCompletionRepairContract
    manifest: ThinkingRepairManifest
    task_packages: tuple[ThinkingRepairTaskPackage, ...]
    path_audits: tuple[ThinkingRepairPathAudit, ...]
    records: tuple[OperationalTaskRecord, ...]
    environments: tuple[AgentToolEnvironmentManifest, ...]
    prompt_contracts: tuple[CompactPromptContract, ...]
    predecessor_paths: tuple[BudgetQualifiedPathAudit, ...]
    compiler_trajectories: tuple[Trajectory, ...]
    replay_bindings: tuple[VerifierV2TaskReplayBinding, ...]
    provider_budget_contract: ProviderTokenBudgetContract
    replay_contract: AuthorityPreservingReplayContract
    agent_model_config: AgentModelConfig
    source_replay: ThinkingRepairRunnerSourceReplayAudit


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def thinking_repair_runner_source_replay_audit_id(
    value: ThinkingRepairRunnerSourceReplayAudit,
) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_repair_runner_replay:")


def thinking_repair_outcome_interpretation_contract_id(
    value: ThinkingRepairOutcomeInterpretationContract,
) -> str:
    return _identity(
        value,
        "contract_id",
        "finance_v26_thinking_repair_outcome_interpretation:",
    )


def thinking_repair_execution_contract_id(value: ThinkingRepairExecutionContract) -> str:
    return _identity(value, "contract_id", "finance_v26_thinking_repair_execution_contract:")


def thinking_repair_execution_preflight_report_id(
    value: ThinkingRepairExecutionPreflightReport,
) -> str:
    return _identity(
        value,
        "report_id",
        "finance_v26_thinking_repair_execution_preflight_report:",
    )


def thinking_repair_raw_provider_call_id(value: ThinkingRepairRawProviderCall) -> str:
    return _identity(value, "artifact_id", "finance_v26_thinking_repair_provider_call:")


def thinking_repair_request_attempt_id(value: ThinkingRepairRequestAttempt) -> str:
    return _identity(value, "attempt_id", "finance_v26_thinking_repair_request_attempt:")


def thinking_repair_logical_request_id(value: ThinkingRepairLogicalRequest) -> str:
    return _identity(value, "request_id", "finance_v26_thinking_repair_logical_request:")


def thinking_repair_completed_result_id(value: ThinkingRepairCompletedResult) -> str:
    return _identity(value, "result_id", "finance_v26_thinking_repair_completed_result:")


def thinking_repair_raw_execution_id(value: ThinkingRepairRawExecution) -> str:
    return _identity(value, "artifact_id", "finance_v26_thinking_repair_raw_execution:")


def thinking_repair_job_result_id(value: ThinkingRepairJobResult) -> str:
    return _identity(value, "result_id", "finance_v26_thinking_repair_job_result:")


def thinking_repair_cell_summary_id(value: ThinkingRepairCellSummary) -> str:
    return _identity(value, "summary_id", "finance_v26_thinking_repair_cell_summary:")


def thinking_repair_raw_lineage_audit_id(value: ThinkingRepairRawLineageAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_repair_raw_lineage:")


def thinking_repair_execution_report_id(value: ThinkingRepairExecutionReport) -> str:
    return _identity(value, "report_id", "finance_v26_thinking_repair_execution:")


def thinking_repair_provider_call_id(
    job_id: str,
    call_index: int,
    telemetry: ModelCallTelemetry,
) -> str:
    return canonical_hash(
        {
            "job_id": job_id,
            "call_index": call_index,
            "request_hash": telemetry.request_hash,
            "response_hash": telemetry.response_hash,
            "model_selected": telemetry.model_selected,
            "response_model": telemetry.response_model,
            "http_status": telemetry.http_status,
        },
        prefix="finance_v26_thinking_repair_provider_call_id:",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_error(exc: Exception) -> str:
    return f"{type(exc).__name__}:{str(exc)[:1200]}"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_bytes(value)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)
    return hashlib.sha256(payload).hexdigest()


def _append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_canonical_bytes(value).decode("utf-8"))
        handle.write("\n")


def _load_models(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"expected a JSON list: {path}")
    return tuple(model.model_validate(item) for item in payload)


def _contains_private_reasoning_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key) in {"private_reasoning", "reasoning_content"}
            or _contains_private_reasoning_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_private_reasoning_key(item) for item in value)
    return False


def _relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def _raw_provider_path(output_dir: Path, job: ThinkingRepairJob, call_index: int) -> Path:
    job_hash = hashlib.sha256(job.job_id.encode("utf-8")).hexdigest()[:20]
    return output_dir / "raw_provider_calls" / job_hash / f"call_{call_index:04d}.json"


def _raw_execution_path(output_dir: Path, job: ThinkingRepairJob) -> Path:
    job_hash = hashlib.sha256(job.job_id.encode("utf-8")).hexdigest()[:20]
    return output_dir / "raw_execution" / f"{job_hash}.json"


def _descriptor(path: Path, root: Path) -> RawFileDescriptor:
    return RawFileDescriptor(
        relative_path=_relative(path, root),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def _envelope_from_telemetry(
    telemetry: ModelCallTelemetry,
) -> RedactedProviderResponseEnvelope | None:
    payload = telemetry.response_shape.get("redacted_response_envelope")
    if not isinstance(payload, Mapping):
        return None
    try:
        return RedactedProviderResponseEnvelope.model_validate(payload)
    except ValidationError:
        return None


def _completion_failure_artifact(
    *,
    failure_type: CompletionFailureKind,
    telemetry: ModelCallTelemetry,
) -> ProspectiveThinkingFailureArtifact | None:
    envelope = _envelope_from_telemetry(telemetry)
    if envelope is None:
        return None
    artifact = make_prospective_thinking_failure_artifact(
        failure_type=failure_type,
        request_hash=telemetry.request_hash,
        response_envelope=envelope,
    )
    serialize_validated_failure_artifact(artifact)
    return artifact


class _JournaledBudgetClient:
    """Precertify a typed request and persist its redacted Provider result first."""

    def __init__(
        self,
        delegate: Any,
        *,
        execution_contract: ThinkingRepairExecutionContract,
        job: ThinkingRepairJob,
        provider_contract: ProviderTokenBudgetContract,
        output_dir: Path,
    ) -> None:
        config = delegate.config
        if (
            config.provider != provider_contract.provider
            or config.model != provider_contract.model_id
            or config.max_output_tokens != provider_contract.maximum_output_tokens
            or config.maximum_model_attempts != 1
            or config.fallback_models
            or not config.require_requested_model
        ):
            raise ValueError("v26.95 Provider client differs from the frozen budget route")
        self._delegate = delegate
        self._execution_contract = execution_contract
        self._job = job
        self._provider_contract = provider_contract
        self._output_dir = output_dir
        self._certificates: list[ProviderTokenBudgetCertificate] = []
        self._usage_records: list[ProviderTokenUsageRecord] = []
        self._prompts: list[str] = []
        self._telemetry: list[ModelCallTelemetry] = []
        self._descriptors: list[RawFileDescriptor] = []
        self._provider_call_ids: list[str] = []
        self._contract_failure_ids: set[str] = set()
        self._no_call_terminal: ProviderBudgetNoCallTerminal | None = None
        self._cumulative_tokens = 0

    @property
    def config(self) -> AgentModelConfig:
        return self._delegate.config

    @property
    def provider_call_count(self) -> int:
        return len(self._telemetry)

    @property
    def prompts(self) -> tuple[str, ...]:
        return tuple(self._prompts)

    @property
    def telemetry(self) -> tuple[ModelCallTelemetry, ...]:
        return tuple(self._telemetry)

    @property
    def descriptors(self) -> tuple[RawFileDescriptor, ...]:
        return tuple(self._descriptors)

    @property
    def provider_call_ids(self) -> tuple[str, ...]:
        return tuple(self._provider_call_ids)

    @property
    def no_call_terminal(self) -> ProviderBudgetNoCallTerminal | None:
        return self._no_call_terminal

    def _required_reserves(
        self,
        *,
        phase: AttemptPhase,
        request_kind: CompletionRequestKind,
        rescue_available_before: bool,
    ) -> tuple[int, int]:
        repair = (
            self._provider_contract.contract_repair_reserve_tokens
            if phase == "primary" and rescue_available_before
            else 0
        )
        final = (
            self._provider_contract.final_answer_reserve_tokens if request_kind == "decision" else 0
        )
        return repair, final

    def _make_certificate(
        self,
        prompt: str,
        *,
        phase: AttemptPhase,
        request_kind: CompletionRequestKind,
        rescue_available_before: bool,
    ) -> ProviderTokenBudgetCertificate:
        contract = self._provider_contract
        prompt_bytes = len(prompt.encode("utf-8"))
        prompt_upper = prompt_bytes + contract.provider_chat_envelope_token_upper_bound
        request_upper = prompt_upper + contract.maximum_output_tokens
        repair_reserve, final_reserve = self._required_reserves(
            phase=phase,
            request_kind=request_kind,
            rescue_available_before=rescue_available_before,
        )
        projected_without_reserve = self._cumulative_tokens + request_upper
        projected = projected_without_reserve + repair_reserve + final_reserve
        denial: (
            Literal[
                "oversized_prompt",
                "request_bound_exceeds_remaining_budget",
                "required_reserve_not_available",
            ]
            | None
        ) = None
        if prompt_bytes > contract.maximum_prompt_utf8_bytes:
            denial = "oversized_prompt"
        elif projected_without_reserve > contract.maximum_total_tokens:
            denial = "request_bound_exceeds_remaining_budget"
        elif projected > contract.maximum_total_tokens:
            denial = "required_reserve_not_available"
        values = {
            "contract_id": contract.contract_id,
            "request_index": len(self._certificates),
            "request_kind": "contract_repair" if phase == "rescue" else request_kind,
            "repaired_request_kind": request_kind if phase == "rescue" else None,
            "request_hash": _sha256_text(prompt),
            "prompt_utf8_bytes": prompt_bytes,
            "prompt_token_upper_bound": prompt_upper,
            "completion_token_upper_bound": contract.maximum_output_tokens,
            "request_token_upper_bound": request_upper,
            "cumulative_provider_tokens_before": self._cumulative_tokens,
            "contract_repair_reserve_tokens": repair_reserve,
            "final_answer_reserve_tokens": final_reserve,
            "required_reserve_tokens": repair_reserve + final_reserve,
            "projected_upper_total": projected,
            "maximum_total_tokens": contract.maximum_total_tokens,
            "decision": "denied_no_call" if denial is not None else "allowed",
            "denial_reason": denial,
            "provider_call_permitted": denial is None,
        }
        provisional = ProviderTokenBudgetCertificate.model_construct(
            certificate_id="pending",
            **values,
        )
        return ProviderTokenBudgetCertificate(
            certificate_id=provider_token_budget_certificate_id(provisional),
            **values,
        )

    def _persist_provider_call(
        self,
        *,
        logical_request_index: int,
        phase: AttemptPhase,
        request_kind: CompletionRequestKind,
        prompt: str,
        payload: dict[str, Any] | None,
        telemetry: ModelCallTelemetry,
        failure_artifact: ProspectiveThinkingFailureArtifact | None,
    ) -> None:
        call_index = len(self._telemetry)
        provider_call_id = thinking_repair_provider_call_id(
            self._job.job_id,
            call_index,
            telemetry,
        )
        values = {
            "execution_contract_id": self._execution_contract.contract_id,
            "job_id": self._job.job_id,
            "logical_request_index": logical_request_index,
            "call_index": call_index,
            "phase": phase,
            "request_kind": request_kind,
            "provider_call_id": provider_call_id,
            "prompt": prompt,
            "prompt_sha256": _sha256_text(prompt),
            "response_payload": payload,
            "provider_telemetry": telemetry,
            "failure_artifact": failure_artifact,
        }
        provisional = ThinkingRepairRawProviderCall.model_construct(
            artifact_id="pending",
            **values,
        )
        artifact = ThinkingRepairRawProviderCall(
            artifact_id=thinking_repair_raw_provider_call_id(provisional),
            **values,
        )
        path = _raw_provider_path(self._output_dir, self._job, call_index)
        _write_json_atomic(path, artifact.model_dump(mode="json"))
        self._telemetry.append(telemetry)
        self._prompts.append(prompt)
        self._descriptors.append(_descriptor(path, self._output_dir))
        self._provider_call_ids.append(provider_call_id)

    def _record_usage(
        self,
        certificate: ProviderTokenBudgetCertificate,
        prompt: str,
        telemetry: ModelCallTelemetry,
    ) -> None:
        contract = self._provider_contract
        checks: dict[str, bool] = {
            "request_hash_match": telemetry.request_hash == certificate.request_hash,
            "requested_model_match": telemetry.model_requested == contract.model_id,
            "fallback_absent": not telemetry.fallback_used,
        }
        counted = 0
        if telemetry.http_success:
            prompt_tokens = telemetry.prompt_tokens
            completion_tokens = telemetry.completion_tokens
            total_tokens = telemetry.total_tokens
            checks.update(
                {
                    "successful_usage_present": (
                        prompt_tokens is not None
                        and completion_tokens is not None
                        and total_tokens is not None
                    ),
                    "prompt_completion_sum_match": (
                        prompt_tokens is not None
                        and completion_tokens is not None
                        and total_tokens is not None
                        and prompt_tokens + completion_tokens == total_tokens
                    ),
                    "prompt_upper_bound_respected": (
                        prompt_tokens is not None
                        and prompt_tokens <= certificate.prompt_token_upper_bound
                    ),
                    "completion_upper_bound_respected": (
                        completion_tokens is not None
                        and completion_tokens <= certificate.completion_token_upper_bound
                    ),
                    "request_upper_bound_respected": (
                        total_tokens is not None
                        and total_tokens <= certificate.request_token_upper_bound
                    ),
                    "rollout_ceiling_respected": (
                        total_tokens is not None
                        and self._cumulative_tokens + total_tokens <= contract.maximum_total_tokens
                    ),
                }
            )
            cache_hit = telemetry.prompt_cache_hit_tokens
            cache_miss = telemetry.prompt_cache_miss_tokens
            if cache_hit is not None or cache_miss is not None:
                checks["cache_partition_sum_match"] = (
                    prompt_tokens is not None
                    and cache_hit is not None
                    and cache_miss is not None
                    and cache_hit + cache_miss == prompt_tokens
                )
            if total_tokens is not None:
                counted = total_tokens
        ordered = dict(sorted(checks.items()))
        failures = tuple(f"resource_budget:{key}" for key, passed in ordered.items() if not passed)
        cumulative_after = self._cumulative_tokens + counted
        values = {
            "contract_id": contract.contract_id,
            "certificate_id": certificate.certificate_id,
            "request_index": certificate.request_index,
            "request_hash": certificate.request_hash,
            "http_success": telemetry.http_success,
            "prompt_tokens": telemetry.prompt_tokens,
            "completion_tokens": telemetry.completion_tokens,
            "total_tokens": telemetry.total_tokens,
            "counted_tokens": counted,
            "cumulative_provider_tokens_after": cumulative_after,
            "validation_checks": ordered,
            "failure_ids": failures,
            "passed": not failures,
        }
        provisional = ProviderTokenUsageRecord.model_construct(record_id="pending", **values)
        record = ProviderTokenUsageRecord(
            record_id=provider_token_usage_record_id(provisional),
            **values,
        )
        self._usage_records.append(record)
        self._cumulative_tokens = cumulative_after
        self._contract_failure_ids.update(failures)

    def call(
        self,
        prompt: str,
        *,
        logical_request_index: int,
        phase: AttemptPhase,
        request_kind: CompletionRequestKind,
        rescue_available_before: bool,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        if self._contract_failure_ids:
            raise LLMClientError("v26.95 Provider budget Contract is already failed")
        if self._no_call_terminal is not None:
            raise LLMClientError("v26.95 Provider call follows a typed no-call terminal")
        certificate = self._make_certificate(
            prompt,
            phase=phase,
            request_kind=request_kind,
            rescue_available_before=rescue_available_before,
        )
        self._certificates.append(certificate)
        if not certificate.provider_call_permitted:
            values = {
                "contract_id": self._provider_contract.contract_id,
                "denied_certificate_id": certificate.certificate_id,
                "request_index": certificate.request_index,
                "request_kind": certificate.request_kind,
                "request_hash": certificate.request_hash,
                "reason_code": certificate.denial_reason,
            }
            provisional = ProviderBudgetNoCallTerminal.model_construct(
                terminal_id="pending",
                **values,
            )
            self._no_call_terminal = ProviderBudgetNoCallTerminal(
                terminal_id=provider_budget_no_call_terminal_id(provisional),
                **values,
            )
            raise LLMClientError(
                f"Provider call denied before invocation: {certificate.denial_reason}"
            )
        try:
            payload, telemetry = self._delegate.complete_json(prompt)
        except LLMClientError as exc:
            if len(exc.telemetry) > 1:
                self._contract_failure_ids.add("resource_budget:multiple_model_attempts")
            artifact = (
                exc.failure_artifact
                if isinstance(exc.failure_artifact, ProspectiveThinkingFailureArtifact)
                else None
            )
            for item in exc.telemetry:
                self._persist_provider_call(
                    logical_request_index=logical_request_index,
                    phase=phase,
                    request_kind=request_kind,
                    prompt=prompt,
                    payload=None,
                    telemetry=item,
                    failure_artifact=artifact,
                )
                self._record_usage(certificate, prompt, item)
            if self._contract_failure_ids:
                raise LLMClientError(
                    "v26.95 Provider budget Contract failed",
                    exc.telemetry,
                    failure_artifact=artifact,
                ) from exc
            raise
        self._persist_provider_call(
            logical_request_index=logical_request_index,
            phase=phase,
            request_kind=request_kind,
            prompt=prompt,
            payload=payload,
            telemetry=telemetry,
            failure_artifact=None,
        )
        self._record_usage(certificate, prompt, telemetry)
        if self._contract_failure_ids:
            raise LLMClientError(
                "v26.95 Provider budget Contract failed",
                (telemetry,),
            )
        return payload, telemetry

    def audit(self) -> ProviderTokenBudgetAudit:
        failures = tuple(sorted(self._contract_failure_ids))
        values = {
            "contract_id": self._provider_contract.contract_id,
            "certificates": tuple(self._certificates),
            "usage_records": tuple(self._usage_records),
            "no_call_terminal": self._no_call_terminal,
            "actual_request_prompt_hashes": tuple(_sha256_text(item) for item in self._prompts),
            "provider_call_count": len(self._usage_records),
            "permitted_request_count": sum(
                item.provider_call_permitted for item in self._certificates
            ),
            "denied_no_call_count": sum(
                not item.provider_call_permitted for item in self._certificates
            ),
            "cumulative_provider_tokens": self._cumulative_tokens,
            "maximum_total_tokens": self._provider_contract.maximum_total_tokens,
            "contract_failure_ids": failures,
            "all_provider_calls_precertified": len(self._usage_records)
            <= sum(item.provider_call_permitted for item in self._certificates),
            "strict_budget_closed": not failures,
            "status": "failed" if failures else "passed",
        }
        provisional = ProviderTokenBudgetAudit.model_construct(audit_id="pending", **values)
        return ProviderTokenBudgetAudit(
            audit_id=provider_token_budget_audit_id(provisional),
            **values,
        )


def _attempt_disposition_from_error(
    exc: LLMClientError,
    *,
    ledger: _JournaledBudgetClient,
) -> tuple[
    AttemptDisposition,
    ProspectiveThinkingFailureArtifact | None,
]:
    if ledger.no_call_terminal is not None and not exc.telemetry:
        return "typed_budget_no_call", None
    artifact = (
        exc.failure_artifact
        if isinstance(exc.failure_artifact, ProspectiveThinkingFailureArtifact)
        else None
    )
    if artifact is not None and artifact.failure_type in {
        "empty_final_content",
        "invalid_json",
        "invalid_response_contract",
        "length_truncated_content",
        "reasoning_only_length_truncation",
    }:
        return "completion_failure", artifact
    if exc.telemetry and not all(item.http_success for item in exc.telemetry):
        return "provider_transport_failure", artifact
    return "instrument_failure", artifact


def _request_attempt(
    *,
    ledger: _JournaledBudgetClient,
    path_audit: ThinkingRepairPathAudit,
    logical_index: int,
    request_kind: CompletionRequestKind,
    phase: AttemptPhase,
    prompt: str,
    primary_prompt_bytes: int,
    rescue_available_before: bool,
) -> ThinkingRepairRequestAttempt:
    provider_index_before = ledger.provider_call_count
    registered = (
        path_audit.request_audits[logical_index]
        if logical_index < len(path_audit.request_audits)
        else None
    )
    provider_call_made = False
    projection: CompletionProjection | None = None
    failure_artifact: ProspectiveThinkingFailureArtifact | None = None
    disposition: AttemptDisposition
    error: str | None = None
    payload_present = False
    try:
        payload, telemetry = ledger.call(
            prompt,
            logical_request_index=logical_index,
            phase=phase,
            request_kind=request_kind,
            rescue_available_before=rescue_available_before,
        )
        provider_call_made = True
        payload_present = True
        try:
            projection = project_model_completion(request_kind, payload)
            disposition = "usable"
        except ValueError as exc:
            error = _safe_error(exc)
            failure_artifact = _completion_failure_artifact(
                failure_type="invalid_response_contract",
                telemetry=telemetry,
            )
            disposition = (
                "completion_failure" if failure_artifact is not None else "instrument_failure"
            )
    except LLMClientError as exc:
        provider_call_made = ledger.provider_call_count > provider_index_before
        disposition, failure_artifact = _attempt_disposition_from_error(exc, ledger=ledger)
        error = _safe_error(exc)
    prompt_bytes = len(prompt.encode("utf-8"))
    reduction = (
        (primary_prompt_bytes - prompt_bytes) * 10000 // primary_prompt_bytes
        if phase == "rescue"
        else None
    )
    values = {
        "logical_request_index": logical_index,
        "provider_call_index": provider_index_before if provider_call_made else None,
        "phase": phase,
        "request_kind": request_kind,
        "prompt_sha256": _sha256_text(prompt),
        "prompt_utf8_bytes": prompt_bytes,
        "registered_request_present": registered is not None,
        "registered_request_kind_match": (
            registered is not None and registered.request_kind == request_kind
        ),
        "registered_primary_prompt_match": (
            phase == "primary"
            and registered is not None
            and registered.primary_prompt_sha256 == _sha256_text(prompt)
        ),
        "rescue_prompt_strictly_shorter": (
            prompt_bytes < primary_prompt_bytes if phase == "rescue" else None
        ),
        "rescue_prompt_reduction_basis_points": reduction,
        "provider_call_made": provider_call_made,
        "response_payload_present": payload_present,
        "completion_projection": projection,
        "failure_artifact": failure_artifact,
        "disposition": disposition,
        "error": error,
    }
    provisional = ThinkingRepairRequestAttempt.model_construct(attempt_id="pending", **values)
    return ThinkingRepairRequestAttempt(
        attempt_id=thinking_repair_request_attempt_id(provisional),
        **values,
    )


def _logical_request(
    *,
    logical_index: int,
    request_kind: CompletionRequestKind,
    source_prompt: str,
    primary: ThinkingRepairRequestAttempt,
    rescue: ThinkingRepairRequestAttempt | None,
) -> ThinkingRepairLogicalRequest:
    if primary.disposition == "usable":
        outcome: LogicalRequestOutcome = "direct_usable"
    elif rescue is not None and rescue.disposition == "usable":
        outcome = "rescued_usable"
    else:
        terminal = rescue or primary
        outcome = cast(
            LogicalRequestOutcome,
            {
                "completion_failure": "terminal_completion_unusable",
                "provider_transport_failure": "terminal_provider_transport_failure",
                "typed_budget_no_call": "terminal_typed_budget_no_call",
                "instrument_failure": "terminal_instrument_failure",
            }[terminal.disposition],
        )
    initial = (
        cast(CompletionFailureKind, primary.failure_artifact.failure_type)
        if rescue is not None and primary.failure_artifact is not None
        else None
    )
    values = {
        "logical_request_index": logical_index,
        "request_kind": request_kind,
        "source_prompt_sha256": _sha256_text(source_prompt),
        "primary_attempt_id": primary.attempt_id,
        "rescue_attempt_id": rescue.attempt_id if rescue is not None else None,
        "rescue_used": rescue is not None,
        "initial_failure_type": initial,
        "outcome": outcome,
        "usable": outcome in {"direct_usable", "rescued_usable"},
    }
    provisional = ThinkingRepairLogicalRequest.model_construct(request_id="pending", **values)
    return ThinkingRepairLogicalRequest(
        request_id=thinking_repair_logical_request_id(provisional),
        **values,
    )


def _runtime(
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
) -> FinanceExecutableSupportRuntime:
    recovery = (
        FinanceTypedRecoveryScenario.model_validate(record.recovery_scenario)
        if record.recovery_scenario is not None
        else None
    )
    return FinanceExecutableSupportRuntime(
        record.public_corpus,
        environment,
        recovery_scenario=recovery,
    )


def _execute_observation(
    *,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    runtime: FinanceExecutableSupportRuntime,
    observations: Sequence[AgentToolObservation],
    projection: CompletionProjection,
) -> AgentToolObservation:
    tool_id = projection.tool_id or ""
    selectable = {item.tool_id: item for item in environment.tools if item.model_selectable}
    spec = selectable.get(tool_id)
    arguments = projection.arguments or {}
    _assert_no_model_forbidden_fields(arguments)
    call = AgentToolCall(
        call_index=len(observations) + 1,
        tool_id=tool_id,
        arguments=arguments,
    )
    if spec is None:
        result = AgentToolResult(
            status="failed",
            result={},
            error_code="unknown_or_unselectable_tool",
            error_message="The selected tool is not available in the public environment.",
        )
    else:
        failed_signatures: set[str] = set()
        for item in reversed(observations):
            if item.status == "succeeded":
                break
            failed_signatures.add(_tool_call_signature(item.call))
        if _tool_call_signature(call) in failed_signatures:
            result = AgentToolResult(
                status="failed",
                result={
                    "retry_contract": {
                        "policy": ARGUMENT_PATCH_REQUIRED_POLICY,
                        "suggested_argument_patch": {
                            "rule": (
                                "change at least one argument according to the latest public "
                                "error; the identical failed action remains blocked"
                            )
                        },
                    }
                },
                error_code="identical_failed_action_blocked",
                error_message="The Host blocked an identical failed action without executing it.",
            )
        else:
            task = record.task_package.task.public
            result = (
                public_postcompletion_action_rejection(task, tuple(observations), call)
                or agent_tool_argument_rejection(spec, call)
                or public_terminal_verification_rejection(task, tuple(observations), call)
                or public_operation_step_rejection(task, tuple(observations), call)
                or _operation_step_rejection(task, tuple(observations), call)
                or _execute_tool(runtime, call)
            )
        result = public_action_neutral_repair_result(
            record.task_package.task.public,
            tuple(observations),
            call,
            result,
        )
        _assert_no_model_forbidden_fields(result.result)
        if result.status == "succeeded":
            spec.validate_output(result.result)
    return make_agent_tool_observation(
        environment_manifest_id=environment.manifest_id,
        call=call,
        result=result,
        observation_time_hash=canonical_hash(
            {
                "snapshot_id": environment.snapshot_id,
                "call_index": call.call_index,
            },
            prefix="agent_observation_time:",
        ),
    )


def _selected_evidence_ids(
    observations: Sequence[AgentToolObservation],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                evidence_id
                for item in observations
                if item.status == "succeeded"
                and item.call.tool_id in {"query_structured_fact", "open_document"}
                for evidence_id in item.evidence_ids
            }
        )
    )


def _source_prompt(
    *,
    request_kind: CompletionRequestKind,
    prompt_contract: CompactPromptContract,
    record: OperationalTaskRecord,
    observations: Sequence[AgentToolObservation],
    path_audit: ThinkingRepairPathAudit,
) -> str:
    public_condition = None if path_audit.role == "capability" else path_audit.path_strategy_id
    if request_kind == "final_answer":
        return render_compact_final_prompt(
            prompt_contract.public_context,
            record.task_package.task.public,
            tuple(observations),
            public_path_condition=public_condition,
        )
    return render_compact_decision_prompt(
        prompt_contract.public_context,
        record.task_package.task.public,
        tuple(observations),
        public_path_condition=public_condition,
    )


def _terminal_disposition(
    attempt: ThinkingRepairRequestAttempt,
) -> Literal[
    "typed_budget_no_call",
    "completion_unusable",
    "provider_transport_failure",
    "instrument_failure",
]:
    return cast(
        Literal[
            "typed_budget_no_call",
            "completion_unusable",
            "provider_transport_failure",
            "instrument_failure",
        ],
        {
            "typed_budget_no_call": "typed_budget_no_call",
            "completion_failure": "completion_unusable",
            "provider_transport_failure": "provider_transport_failure",
            "instrument_failure": "instrument_failure",
        }[attempt.disposition],
    )


def _load_raw_execution(path: Path) -> ThinkingRepairRawExecution:
    raw = path.read_bytes()
    payload = json.loads(raw)
    if raw != _canonical_bytes(payload):
        raise ValueError(f"v26.95 raw execution is not canonical JSON: {path}")
    return ThinkingRepairRawExecution.model_validate(payload)


def execute_thinking_repair_job_raw(
    *,
    job: ThinkingRepairJob,
    execution_contract: ThinkingRepairExecutionContract,
    provider_contract: ProviderTokenBudgetContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    prompt_contract: CompactPromptContract,
    path_audit: ThinkingRepairPathAudit,
    client: Any | None,
    output_dir: Path,
) -> ThinkingRepairRawExecution:
    raw_path = _raw_execution_path(output_dir, job)
    if raw_path.exists():
        raw = _load_raw_execution(raw_path)
        if raw.execution_contract_id != execution_contract.contract_id or raw.job != job:
            raise ValueError("v26.95 raw-only recovery crosses frozen identities")
        return raw
    provider_dir = _raw_provider_path(output_dir, job, 0).parent
    if provider_dir.exists() and any(provider_dir.glob("call_*.json")):
        raise ValueError(
            "orphan v26.95 Provider Artifacts exist without a Raw Execution; "
            "automatic model retry is forbidden"
        )
    if client is None:
        raise ValueError("pending v26.95 Job has no model client")
    if (
        job.repair_contract_id != execution_contract.predecessor_contract_id
        or job.repair_path_audit_id != path_audit.audit_id
        or path_audit.repair_task_package_id != job.repair_task_package_id
        or path_audit.source_task_artifact_id != job.source_task_artifact_id
        or path_audit.path_strategy_id != job.path_strategy_id
        or record.task_package.package_id != prompt_contract.operational_task_package_id
        or record.environment_manifest_id != environment.manifest_id
        or prompt_contract.environment_manifest_id != environment.manifest_id
    ):
        raise ValueError("v26.95 execution inputs differ from the frozen Job")

    ledger = _JournaledBudgetClient(
        client,
        execution_contract=execution_contract,
        job=job,
        provider_contract=provider_contract,
        output_dir=output_dir,
    )
    runtime = _runtime(record, environment)
    observations: list[AgentToolObservation] = []
    attempts: list[ThinkingRepairRequestAttempt] = []
    logical_requests: list[ThinkingRepairLogicalRequest] = []
    completed: ThinkingRepairCompletedResult | None = None
    terminal: Literal[
        "completed",
        "model_invalid",
        "typed_budget_no_call",
        "completion_unusable",
        "provider_transport_failure",
        "instrument_failure",
    ] = "model_invalid"
    terminal_failure_type: str | None = None
    execution_error: str | None = None
    rescue_used = False
    maximum_logical_requests = environment.maximum_tool_calls + 1

    for logical_index in range(maximum_logical_requests):
        progress = compact_public_progress(
            record.task_package.task.public,
            tuple(observations),
        )
        request_kind: CompletionRequestKind = (
            "final_answer" if progress["final_answer_allowed"] else "decision"
        )
        source_prompt = _source_prompt(
            request_kind=request_kind,
            prompt_contract=prompt_contract,
            record=record,
            observations=observations,
            path_audit=path_audit,
        )
        primary_prompt = render_primary_completion_prompt(request_kind, source_prompt)
        primary = _request_attempt(
            ledger=ledger,
            path_audit=path_audit,
            logical_index=logical_index,
            request_kind=request_kind,
            phase="primary",
            prompt=primary_prompt,
            primary_prompt_bytes=len(primary_prompt.encode("utf-8")),
            rescue_available_before=not rescue_used,
        )
        attempts.append(primary)
        rescue: ThinkingRepairRequestAttempt | None = None
        active = primary
        if primary.disposition == "completion_failure" and not rescue_used:
            if primary.failure_artifact is None:
                raise ValueError("v26.95 Completion failure lacks a Rescue type")
            failure_type = cast(
                CompletionFailureKind,
                primary.failure_artifact.failure_type,
            )
            rescue_used = True
            rescue_prompt = render_rescue_completion_prompt(
                request_kind,
                source_prompt,
                failure_type,
            )
            rescue = _request_attempt(
                ledger=ledger,
                path_audit=path_audit,
                logical_index=logical_index,
                request_kind=request_kind,
                phase="rescue",
                prompt=rescue_prompt,
                primary_prompt_bytes=len(primary_prompt.encode("utf-8")),
                rescue_available_before=False,
            )
            attempts.append(rescue)
            active = rescue
        logical = _logical_request(
            logical_index=logical_index,
            request_kind=request_kind,
            source_prompt=source_prompt,
            primary=primary,
            rescue=rescue,
        )
        logical_requests.append(logical)
        if active.disposition != "usable":
            terminal = _terminal_disposition(active)
            terminal_failure_type = (
                active.failure_artifact.failure_type
                if active.failure_artifact is not None
                else active.disposition
            )
            execution_error = active.error
            break
        projection = cast(CompletionProjection, active.completion_projection)
        if request_kind == "decision":
            observations.append(
                _execute_observation(
                    record=record,
                    environment=environment,
                    runtime=runtime,
                    observations=observations,
                    projection=projection,
                )
            )
            if len(observations) >= environment.maximum_tool_calls:
                next_progress = compact_public_progress(
                    record.task_package.task.public,
                    tuple(observations),
                )
                if not next_progress["final_answer_allowed"]:
                    terminal = "model_invalid"
                    execution_error = "model exhausted the frozen public tool-call budget"
                    break
            continue
        citations = _selected_evidence_ids(observations)
        if not citations:
            terminal = "model_invalid"
            execution_error = "final answer has no successfully selected public Evidence"
            break
        completed_values = {
            "job_id": job.job_id,
            "observations": tuple(observations),
            "answer": projection.answer or {},
            "cited_evidence_ids": citations,
            "final_request_id": logical.request_id,
        }
        provisional = ThinkingRepairCompletedResult.model_construct(
            result_id="pending",
            **completed_values,
        )
        completed = ThinkingRepairCompletedResult(
            result_id=thinking_repair_completed_result_id(provisional),
            **completed_values,
        )
        terminal = "completed"
        break

    budget_audit = ledger.audit()
    if budget_audit.status != "passed":
        terminal = "instrument_failure"
        terminal_failure_type = "provider_budget_contract_failure"
        execution_error = ";".join(budget_audit.contract_failure_ids)
        completed = None
    raw_values = {
        "execution_contract_id": execution_contract.contract_id,
        "job": job,
        "operational_record_id": record.record_id,
        "environment_manifest_id": environment.manifest_id,
        "path_audit_id": path_audit.audit_id,
        "provider_call_artifacts": ledger.descriptors,
        "provider_call_ids": ledger.provider_call_ids,
        "provider_telemetry": ledger.telemetry,
        "provider_prompts": ledger.prompts,
        "request_attempts": tuple(attempts),
        "logical_requests": tuple(logical_requests),
        "provider_budget_audit": budget_audit,
        "observations": tuple(observations),
        "completed_result": completed,
        "terminal_disposition": terminal,
        "terminal_failure_type": terminal_failure_type,
        "execution_error": execution_error,
        "rescue_call_count": sum(item.phase == "rescue" for item in attempts),
    }
    provisional_raw = ThinkingRepairRawExecution.model_construct(
        artifact_id="pending",
        **raw_values,
    )
    raw = ThinkingRepairRawExecution(
        artifact_id=thinking_repair_raw_execution_id(provisional_raw),
        **raw_values,
    )
    _write_json_atomic(raw_path, raw.model_dump(mode="json"))
    return raw


def _successful_observations(
    observations: Sequence[AgentToolObservation],
    tool_id: str,
) -> tuple[AgentToolObservation, ...]:
    return tuple(
        item for item in observations if item.call.tool_id == tool_id and item.status == "succeeded"
    )


def _replace_runtime_references(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, Mapping):
        return {str(key): _replace_runtime_references(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_runtime_references(item, mapping) for item in value]
    return value


def _project_answer(
    value: Mapping[str, Any],
    projection: Mapping[str, str],
) -> dict[str, Any]:
    output = dict(value)
    for field in ("higher_ref", "selected_ref"):
        reference = output.get(field)
        if reference is not None and str(reference) in projection:
            output[field] = projection[str(reference)]
    return output


def _earliest_failure_stage(checks: Mapping[str, bool]) -> str | None:
    return next((stage for check, stage in FAILURE_STAGE_ORDER if not checks[check]), None)


def _verify_completed_result(
    *,
    replay_contract: AuthorityPreservingReplayContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    completed: ThinkingRepairCompletedResult,
) -> tuple[
    AuthorityPreservingReplayResult,
    AuthorityPreservingVerificationReport,
    MechanismEstimandOutcome,
]:
    observations = completed.observations
    replay = replay_authority_preserving_observations(
        replay_contract,
        record,
        environment,
        observations,
    )
    program_complete, matched_nodes, runtime_to_node, operation_lineage = match_empirical_program(
        record, observations
    )
    normalized_answer = _project_answer(
        cast(
            dict[str, Any],
            _replace_runtime_references(completed.answer, runtime_to_node),
        ),
        record.answer_projection,
    )
    lattice = record.task_package.evidence_support_lattice
    selected_support = matching_sufficient_support_set(
        lattice,
        replay.selected_evidence_ids,
    )
    citation_support = matching_sufficient_support_set(
        lattice,
        completed.cited_evidence_ids,
    )
    verification_support = tuple(
        sorted(
            {
                str(evidence_id)
                for item in _successful_observations(observations, "cross_check_evidence")
                if item.result.get("verified") is True
                for evidence_id in item.result.get("support") or ()
            }
        )
    )
    mechanism = evaluate_mechanism_estimand(
        record,
        observations,
        stopped_by_model=True,
    )
    first_verified = next(
        (
            index
            for index, item in enumerate(observations)
            if item.call.tool_id == "cross_check_evidence"
            and item.status == "succeeded"
            and item.result.get("verified") is True
        ),
        None,
    )
    no_postcompletion = first_verified is None or first_verified == len(observations) - 1
    necessary = set(lattice.necessary_evidence_ids)
    checks = {
        "runtime_replay_passed": replay.passed,
        "model_input_noninterference_passed": True,
        "only_allowed_tools": {item.call.tool_id for item in observations}
        <= set(record.task_package.tool_closure.allowed_tool_ids),
        "operation_lineage_complete": (program_complete and necessary <= set(operation_lineage)),
        "evidence_support_complete": selected_support is not None,
        "verification_complete": necessary <= set(verification_support),
        "answer_projection_complete": (normalized_answer == record.projected_expected_output),
        "citation_complete": citation_support is not None,
        "mechanism_complete": mechanism.success,
        "no_postcompletion_violation": no_postcompletion,
    }
    if set(checks) != set(VERIFICATION_CHECK_IDS):
        raise ValueError("v26.95 Verifier Gate vector differs from Verifier v2")
    values = {
        "replay_id": replay.replay_id,
        "task_package_id": record.task_package.package_id,
        "verifier_binding_id": record.task_package.verifier_binding.binding_id,
        "trajectory_id": canonical_hash(
            completed,
            prefix="finance_v26_thinking_repair_trajectory:",
        ),
        "checks": checks,
        "selected_evidence_ids": replay.selected_evidence_ids,
        "operation_lineage_evidence_ids": operation_lineage,
        "verification_support_ids": verification_support,
        "cited_evidence_ids": completed.cited_evidence_ids,
        "satisfying_selected_support_set_id": (
            selected_support.support_set_id if selected_support is not None else None
        ),
        "satisfying_citation_support_set_id": (
            citation_support.support_set_id if citation_support is not None else None
        ),
        "mechanism_event_ids": mechanism.observed_event_ids,
        "normalized_answer": normalized_answer,
        "matched_program_node_ids": matched_nodes,
        "earliest_failure_stage": _earliest_failure_stage(checks),
        "valid": all(checks.values()),
    }
    provisional = AuthorityPreservingVerificationReport.model_construct(
        report_id="pending",
        **values,
    )
    verification = AuthorityPreservingVerificationReport(
        report_id=authority_preserving_verification_report_id(provisional),
        **values,
    )
    return replay, verification, mechanism


def _actual_route(observations: Sequence[AgentToolObservation]) -> ActualRoute:
    successful_before_calculation: list[str] = []
    for item in observations:
        if item.call.tool_id in {"calculator", "normalize_metric_unit_period"}:
            break
        if item.status == "succeeded":
            successful_before_calculation.append(item.call.tool_id)
    has_structured = "query_structured_fact" in successful_before_calculation
    has_search = "search_documents" in successful_before_calculation
    has_open = "open_document" in successful_before_calculation
    if has_search and has_open:
        return "search_then_open"
    if has_search and has_structured:
        return "search_then_structured"
    if has_structured and not has_search:
        return "structured_direct"
    if has_search:
        return "search_only"
    return "none" if not successful_before_calculation else "mixed_or_unresolved"


def _repetition_counts(
    observations: Sequence[AgentToolObservation],
) -> tuple[int, int]:
    signatures = [_tool_call_signature(item.call) for item in observations]
    failed = [_tool_call_signature(item.call) for item in observations if item.status == "failed"]
    return len(signatures) - len(set(signatures)), len(failed) - len(set(failed))


def _progress_diagnostic(
    record: OperationalTaskRecord,
    observations: tuple[AgentToolObservation, ...],
) -> tuple[int, int, bool, bool, bool]:
    guidance = record.task_package.task.public.metadata["agent_contract_guidance"]
    operation = guidance["public_operation_execution_contract"]
    node_count = len(operation["nodes"])
    if not observations:
        return 0, node_count, False, False, False
    progress = compact_public_progress(record.task_package.task.public, observations)
    return (
        len(progress["completed_node_ids"]),
        node_count,
        not progress["remaining_node_ids"],
        bool(progress["terminal_node_completed"]),
        bool(progress["verification_after_terminal_completed"]),
    )


def _telemetry_failure_flags(
    telemetry: Sequence[ModelCallTelemetry],
) -> tuple[bool, bool, bool, bool, bool]:
    http_success = tuple(item for item in telemetry if item.http_success)
    exact_model = all(
        item.model_requested == EXACT_MODEL_ID
        and item.model_selected == EXACT_MODEL_ID
        and (not item.http_success or item.response_model == EXACT_MODEL_ID)
        for item in telemetry
    )
    fallback_absent = all(not item.fallback_used for item in telemetry)
    native_tool_absent = all(
        item.response_shape.get("provider_native_tool_call_observed") is False
        for item in http_success
    )
    thinking_continuity = all(
        item.reasoning_content_present
        and (item.reasoning_content_length or 0) > 0
        and (item.reasoning_tokens or 0) > 0
        for item in http_success
    )
    usage_complete = all(
        item.prompt_tokens is not None
        and item.completion_tokens is not None
        and item.total_tokens is not None
        and item.prompt_tokens + item.completion_tokens == item.total_tokens
        for item in http_success
    )
    return (
        exact_model,
        fallback_absent,
        native_tool_absent,
        thinking_continuity,
        usage_complete,
    )


def _score_raw_execution(
    *,
    raw: ThinkingRepairRawExecution,
    prepared: _PreparedInputs,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    output_dir: Path,
) -> ThinkingRepairJobResult:
    replay = replay_authority_preserving_observations(
        prepared.replay_contract,
        record,
        environment,
        raw.observations,
    )
    verification: AuthorityPreservingVerificationReport | None = None
    mechanism = evaluate_mechanism_estimand(
        record,
        raw.observations,
        stopped_by_model=raw.completed_result is not None,
    )
    if raw.completed_result is not None:
        replay, verification, mechanism = _verify_completed_result(
            replay_contract=prepared.replay_contract,
            record=record,
            environment=environment,
            completed=raw.completed_result,
        )
    observations = raw.observations
    repeated, repeated_failed = _repetition_counts(observations)
    completed_nodes, node_count, program_closed, terminal_completed, verified = (
        _progress_diagnostic(record, observations)
    )
    route = _actual_route(observations)
    exact_model, fallback_absent, native_absent, thinking_passed, usage_complete = (
        _telemetry_failure_flags(raw.provider_telemetry)
    )
    instrument_failure = (
        raw.terminal_disposition == "instrument_failure"
        or not exact_model
        or not fallback_absent
        or not native_absent
        or not thinking_passed
        or not usage_complete
        or raw.provider_budget_audit.status != "passed"
        or (replay is not None and not replay.passed)
    )
    transport = raw.terminal_disposition == "provider_transport_failure"
    typed_no_call = raw.terminal_disposition == "typed_budget_no_call"
    completion_unusable = raw.terminal_disposition == "completion_unusable"
    independent_validity = bool(
        verification is not None and verification.valid and not instrument_failure
    )
    terminal: TerminalCategory
    if instrument_failure:
        terminal = "instrument_failure"
    elif transport:
        terminal = "provider_transport_failure"
    elif typed_no_call:
        terminal = "typed_budget_no_call"
    elif completion_unusable:
        terminal = "completion_unusable"
    elif independent_validity:
        terminal = "model_valid_trajectory"
    else:
        terminal = "model_invalid_trajectory"
    completion_failures = Counter(
        cast(str, attempt.failure_artifact.failure_type)
        for attempt in raw.request_attempts
        if attempt.failure_artifact is not None
        and attempt.failure_artifact.failure_type
        in {
            "empty_final_content",
            "invalid_json",
            "invalid_response_contract",
            "length_truncated_content",
            "reasoning_only_length_truncation",
        }
    )
    total_tokens = sum(item.total_tokens or 0 for item in raw.provider_telemetry)
    cost = sum(
        (
            Decimal(str(item.estimated_cost))
            for item in raw.provider_telemetry
            if item.estimated_cost
        ),
        Decimal("0"),
    )
    raw_path = _raw_execution_path(output_dir, raw.job)
    telemetry_failure = (
        not exact_model or not native_absent or not thinking_passed or not usage_complete
    )
    telemetry_only_failure = bool(
        instrument_failure
        and raw.terminal_failure_type == "response_envelope_invalid"
        and raw.provider_budget_audit.status == "passed"
        and replay.passed
        and native_absent
        and fallback_absent
    )
    values = {
        "execution_contract_id": prepared.execution_contract.contract_id,
        "job_id": raw.job.job_id,
        "source_task_artifact_id": raw.job.source_task_artifact_id,
        "mechanism_id": raw.job.mechanism_id,
        "requested_path_strategy_id": raw.job.path_strategy_id,
        "terminal_category": terminal,
        "provider_call_count": len(raw.provider_telemetry),
        "http_success_call_count": sum(item.http_success for item in raw.provider_telemetry),
        "provider_total_tokens": total_tokens,
        "provider_usage_complete": usage_complete,
        "estimated_cost_usd": format(cost, "f"),
        "reasoning_content_length_total": sum(
            item.reasoning_content_length or 0 for item in raw.provider_telemetry
        ),
        "reasoning_tokens_total": sum(
            item.reasoning_tokens or 0 for item in raw.provider_telemetry
        ),
        "completion_tokens_total": sum(
            item.completion_tokens or 0 for item in raw.provider_telemetry
        ),
        "logical_request_count": len(raw.logical_requests),
        "direct_usable_request_count": sum(
            item.outcome == "direct_usable" for item in raw.logical_requests
        ),
        "rescued_usable_request_count": sum(
            item.outcome == "rescued_usable" for item in raw.logical_requests
        ),
        "rescue_call_count": raw.rescue_call_count,
        "completion_limit_hit_count": sum(
            item.finish_reason == "length" for item in raw.provider_telemetry
        ),
        "completion_failure_counts": dict(sorted(completion_failures.items())),
        "typed_no_call": typed_no_call,
        "completion_unusable": completion_unusable,
        "provider_transport_failure": transport,
        "telemetry_failure": telemetry_failure,
        "telemetry_only_failure": telemetry_only_failure,
        "exact_model_passed": exact_model,
        "native_tool_absent": native_absent,
        "thinking_continuity_passed": thinking_passed,
        "fallback_absent": fallback_absent,
        "budget_contract_passed": raw.provider_budget_audit.status == "passed",
        "observation_count": len(observations),
        "failed_observation_count": sum(item.status == "failed" for item in observations),
        "repeated_call_signature_count": repeated,
        "repeated_failed_call_signature_count": repeated_failed,
        "completed_program_node_count": completed_nodes,
        "program_node_count": node_count,
        "program_closed": program_closed,
        "terminal_node_completed": terminal_completed,
        "postterminal_verification_completed": verified,
        "mechanism_evaluated": mechanism.evaluated,
        "mechanism_success": mechanism.success,
        "independent_validity": independent_validity,
        "actual_route": route,
        "requested_path_adhered": route == raw.job.path_strategy_id,
        "registered_primary_prompt_match_count": sum(
            item.registered_primary_prompt_match for item in raw.request_attempts
        ),
        "registered_request_kind_mismatch_count": sum(
            item.registered_request_present and not item.registered_request_kind_match
            for item in raw.request_attempts
        ),
        "replay_result": replay,
        "verification_report": verification,
        "mechanism_outcome": mechanism,
        "no_call_terminal": raw.provider_budget_audit.no_call_terminal,
        "raw_execution_artifact": _descriptor(raw_path, output_dir),
        "failure_attribution": (
            {
                "raw_terminal_disposition": raw.terminal_disposition,
                "terminal_failure_type": raw.terminal_failure_type,
                "execution_error": raw.execution_error,
            }
            if terminal not in {"model_valid_trajectory", "model_invalid_trajectory"}
            else None
        ),
    }
    provisional = ThinkingRepairJobResult.model_construct(result_id="pending", **values)
    return ThinkingRepairJobResult(
        result_id=thinking_repair_job_result_id(provisional),
        **values,
    )


def _validate_source_replay(
    replay: ThinkingRepairRunnerSourceReplayAudit,
    package_root: Path,
) -> None:
    if replay.predecessor_report_id != EXPECTED_V26_94_REPORT_ID:
        raise ValueError("v26.95 source replay predecessor changed")
    for entry in replay.entries:
        path = package_root / entry.relative_path
        observed = _sha256(path)
        if observed != entry.expected_sha256 or path.stat().st_size != entry.byte_count:
            raise ValueError(f"v26.95 online source replay changed: {entry.relative_path}")


def _validate_online_inputs(
    *,
    execution_contract: ThinkingRepairExecutionContract,
    repair_contract: ThinkingCompletionRepairContract,
    manifest: ThinkingRepairManifest,
    task_packages: Sequence[ThinkingRepairTaskPackage],
    path_audits: Sequence[ThinkingRepairPathAudit],
    records: Sequence[OperationalTaskRecord],
    environments: Sequence[AgentToolEnvironmentManifest],
    prompt_contracts: Sequence[CompactPromptContract],
) -> None:
    package_by_id = {item.task_package_id: item for item in task_packages}
    path_by_id = {item.audit_id: item for item in path_audits}
    record_by_id = {item.record_id: item for item in records}
    environment_by_id = {item.manifest_id: item for item in environments}
    prompt_by_id = {item.contract_id: item for item in prompt_contracts}
    if (
        execution_contract.predecessor_contract_id != repair_contract.contract_id
        or execution_contract.predecessor_manifest_id != manifest.manifest_id
        or execution_contract.job_ids != tuple(sorted(item.job_id for item in manifest.jobs))
    ):
        raise ValueError("v26.95 execution Contract differs from the v26.94 denominator")
    for job in manifest.jobs:
        package = package_by_id.get(job.repair_task_package_id)
        path = path_by_id.get(job.repair_path_audit_id)
        if package is None or path is None:
            raise ValueError(f"v26.95 Job repair binding is missing: {job.job_id}")
        record = record_by_id.get(package.operational_record_id)
        environment = environment_by_id.get(package.environment_manifest_id)
        prompt = prompt_by_id.get(package.compact_prompt_contract_id)
        if record is None or environment is None or prompt is None:
            raise ValueError(f"v26.95 Job operational input is missing: {job.job_id}")
        if (
            path.repair_task_package_id != package.task_package_id
            or path.path_strategy_id != job.path_strategy_id
            or path.mechanism_id != job.mechanism_id
            or record.task_package.package_id != package.operational_task_package_id
            or environment.manifest_id != record.environment_manifest_id
            or prompt.operational_task_package_id != record.task_package.package_id
        ):
            raise ValueError(f"v26.95 Job input binding changed: {job.job_id}")


def prepare_thinking_repair_execution(
    *,
    runner_preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> _PreparedInputs:
    preflight_report = ThinkingRepairExecutionPreflightReport.model_validate_json(
        (runner_preflight_dir / "report.json").read_text(encoding="utf-8")
    )
    execution_contract = ThinkingRepairExecutionContract.model_validate_json(
        (runner_preflight_dir / "execution_contract.json").read_text(encoding="utf-8")
    )
    interpretation = ThinkingRepairOutcomeInterpretationContract.model_validate_json(
        (runner_preflight_dir / "outcome_interpretation_contract.json").read_text(encoding="utf-8")
    )
    source_replay = ThinkingRepairRunnerSourceReplayAudit.model_validate_json(
        (runner_preflight_dir / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    if (
        preflight_report.status != "passed"
        or not preflight_report.repair_execution_authorized
        or preflight_report.execution_contract_id != execution_contract.contract_id
        or preflight_report.source_replay_audit_id != source_replay.audit_id
        or preflight_report.outcome_interpretation_contract_id != interpretation.contract_id
        or execution_contract.source_replay_audit_id != source_replay.audit_id
        or execution_contract.outcome_interpretation_contract_id != interpretation.contract_id
    ):
        raise ValueError("v26.95 Runner did not receive an authorizing preflight")
    for detail in preflight_report.detail_files:
        path = runner_preflight_dir / detail.relative_path
        if _sha256(path) != detail.sha256:
            raise ValueError(f"v26.95 preflight detail changed: {detail.relative_path}")
    _validate_source_replay(source_replay, package_root)

    predecessor_dir = package_root / V26_94_DIR
    predecessor_report = ThinkingCompletionTelemetryRepairPreflightReport.model_validate_json(
        (predecessor_dir / "report.json").read_text(encoding="utf-8")
    )
    repair_contract = ThinkingCompletionRepairContract.model_validate_json(
        (predecessor_dir / "thinking_repair_contract.json").read_text(encoding="utf-8")
    )
    manifest = ThinkingRepairManifest.model_validate_json(
        (predecessor_dir / "thinking_repair_job_manifest.json").read_text(encoding="utf-8")
    )
    if (
        predecessor_report.report_id != EXPECTED_V26_94_REPORT_ID
        or repair_contract.contract_id != EXPECTED_V26_94_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_V26_94_MANIFEST_ID
        or predecessor_report.repair_contract_id != repair_contract.contract_id
        or predecessor_report.repair_manifest_id != manifest.manifest_id
    ):
        raise ValueError("v26.95 predecessor v26.94 identity changed")
    task_packages = cast(
        tuple[ThinkingRepairTaskPackage, ...],
        _load_models(
            predecessor_dir / "thinking_repair_task_packages.json",
            ThinkingRepairTaskPackage,
        ),
    )
    path_audits = cast(
        tuple[ThinkingRepairPathAudit, ...],
        _load_models(
            predecessor_dir / "thinking_repair_path_audits.json",
            ThinkingRepairPathAudit,
        ),
    )
    role_dir = package_root / V26_90_DIR
    records = cast(
        tuple[OperationalTaskRecord, ...],
        _load_models(role_dir / "operational_task_records.json", OperationalTaskRecord),
    )
    environments = cast(
        tuple[AgentToolEnvironmentManifest, ...],
        _load_models(
            role_dir / "tool_environment_manifests.json",
            AgentToolEnvironmentManifest,
        ),
    )
    prompt_contracts = cast(
        tuple[CompactPromptContract, ...],
        _load_models(role_dir / "compact_prompt_contracts.json", CompactPromptContract),
    )
    predecessor_paths = cast(
        tuple[BudgetQualifiedPathAudit, ...],
        _load_models(role_dir / "budget_qualified_path_audits.json", BudgetQualifiedPathAudit),
    )
    compiler_trajectories = cast(
        tuple[Trajectory, ...],
        _load_models(role_dir / "compiler_trajectories.json", Trajectory),
    )
    replay_bindings = cast(
        tuple[VerifierV2TaskReplayBinding, ...],
        _load_models(
            role_dir / "verifier_v2_replay_bindings.json",
            VerifierV2TaskReplayBinding,
        ),
    )
    provider_contract = ProviderTokenBudgetContract.model_validate_json(
        (role_dir / "provider_token_budget_contract.json").read_text(encoding="utf-8")
    )
    if provider_contract.contract_id != EXPECTED_PROVIDER_BUDGET_CONTRACT_ID:
        raise ValueError("v26.95 Provider budget Contract changed")
    profile_payload = json.loads((package_root / MODEL_PROFILE_PATH).read_text(encoding="utf-8"))
    model_config = AgentModelConfig.model_validate(profile_payload["model"])
    thinking_binding = bind_prospective_thinking(model_config)
    if (
        model_config.public_manifest_hash != EXPECTED_MODEL_CONFIG_ID
        or thinking_binding.binding_id != EXPECTED_THINKING_BINDING_ID
    ):
        raise ValueError("v26.95 exact Thinking model binding changed")
    _validate_online_inputs(
        execution_contract=execution_contract,
        repair_contract=repair_contract,
        manifest=manifest,
        task_packages=task_packages,
        path_audits=path_audits,
        records=records,
        environments=environments,
        prompt_contracts=prompt_contracts,
    )
    _, replay_contract = _load_and_replay_verifier_qualification(
        package_root
        / (
            "artifacts/vtdo_experiment/"
            "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
        ),
        package_root,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    existing_contract = output_dir / "execution_contract.json"
    if existing_contract.exists():
        observed = ThinkingRepairExecutionContract.model_validate_json(
            existing_contract.read_text(encoding="utf-8")
        )
        if observed != execution_contract:
            raise ValueError("existing v26.95 execution Contract changed")
    _write_json_atomic(
        output_dir / "online_source_replay_audit.json",
        source_replay.model_dump(mode="json"),
    )
    _write_json_atomic(
        existing_contract,
        execution_contract.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "frozen_repair_contract.json",
        repair_contract.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "frozen_repair_job_manifest.json",
        manifest.model_dump(mode="json"),
    )
    return _PreparedInputs(
        preflight_report=preflight_report,
        execution_contract=execution_contract,
        interpretation_contract=interpretation,
        predecessor_report=predecessor_report,
        repair_contract=repair_contract,
        manifest=manifest,
        task_packages=task_packages,
        path_audits=path_audits,
        records=records,
        environments=environments,
        prompt_contracts=prompt_contracts,
        predecessor_paths=predecessor_paths,
        compiler_trajectories=compiler_trajectories,
        replay_bindings=replay_bindings,
        provider_budget_contract=provider_contract,
        replay_contract=replay_contract,
        agent_model_config=model_config,
        source_replay=source_replay,
    )


def _cp_upper(failures: int, denominator: int, *, alpha: float = 0.05) -> float:
    if not 0 <= failures <= denominator or denominator <= 0:
        raise ValueError("invalid Clopper-Pearson inputs")
    if failures == denominator:
        return 1.0
    if failures == 0:
        return 1.0 - alpha ** (1.0 / denominator)

    def cdf(probability: float) -> float:
        return sum(
            comb(denominator, index)
            * probability**index
            * (1.0 - probability) ** (denominator - index)
            for index in range(failures + 1)
        )

    low = failures / denominator
    high = 1.0
    for _ in range(160):
        middle = (low + high) / 2.0
        if cdf(middle) > alpha:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def _cell_summaries(
    results: Sequence[ThinkingRepairJobResult],
) -> tuple[ThinkingRepairCellSummary, ...]:
    groups: dict[tuple[str, PathStrategy], list[ThinkingRepairJobResult]] = defaultdict(list)
    for item in results:
        groups[(item.mechanism_id, item.requested_path_strategy_id)].append(item)
    output = []
    for (mechanism, path), rows in sorted(groups.items()):
        values = {
            "mechanism_id": mechanism,
            "path_strategy_id": path,
            "job_count": len(rows),
            "typed_no_call_count": sum(item.typed_no_call for item in rows),
            "completion_unusable_count": sum(item.completion_unusable for item in rows),
            "provider_transport_failure_count": sum(
                item.provider_transport_failure for item in rows
            ),
            "instrument_failure_count": sum(
                item.terminal_category == "instrument_failure" for item in rows
            ),
            "rescue_job_count": sum(item.rescue_call_count > 0 for item in rows),
            "rescued_usable_request_count": sum(item.rescued_usable_request_count for item in rows),
            "program_closed_count": sum(item.program_closed for item in rows),
            "mechanism_success_count": sum(item.mechanism_success for item in rows),
            "valid_trajectory_count": sum(item.independent_validity for item in rows),
            "requested_path_adherence_count": sum(item.requested_path_adhered for item in rows),
            "mechanism_floor_observed": not any(item.mechanism_success for item in rows),
            "mechanism_saturation_observed": all(item.mechanism_success for item in rows),
            "validity_floor_observed": not any(item.independent_validity for item in rows),
            "validity_saturation_observed": all(item.independent_validity for item in rows),
        }
        provisional = ThinkingRepairCellSummary.model_construct(summary_id="pending", **values)
        output.append(
            ThinkingRepairCellSummary(
                summary_id=thinking_repair_cell_summary_id(provisional),
                **values,
            )
        )
    if len(output) != 12:
        raise ValueError("v26.95 execution does not cover all Mechanism x Path cells")
    return tuple(output)


def _raw_lineage_audit(
    *,
    prepared: _PreparedInputs,
    results: Sequence[ThinkingRepairJobResult],
    raw_by_job: Mapping[str, ThinkingRepairRawExecution],
    output_dir: Path,
) -> ThinkingRepairRawLineageAudit:
    files = []
    provider_ids: list[str] = []
    private_hits = 0
    for result in results:
        raw = raw_by_job[result.job_id]
        raw_path = output_dir / result.raw_execution_artifact.relative_path
        replayed = _load_raw_execution(raw_path)
        if replayed.model_dump(mode="json") != raw.model_dump(mode="json"):
            raise ValueError(f"v26.95 Raw Execution exact-byte replay changed: {result.job_id}")
        files.append(_descriptor(raw_path, output_dir))
        provider_ids.extend(raw.provider_call_ids)
        for descriptor in raw.provider_call_artifacts:
            path = output_dir / descriptor.relative_path
            payload = json.loads(path.read_bytes())
            if path.read_bytes() != _canonical_bytes(payload):
                raise ValueError("v26.95 Provider Artifact is not canonical JSON")
            reparsed = ThinkingRepairRawProviderCall.model_validate(payload)
            if (
                _sha256(path) != descriptor.sha256
                or reparsed.provider_call_id not in raw.provider_call_ids
            ):
                raise ValueError("v26.95 Provider Artifact binding changed")
            private_hits += int(_contains_private_reasoning_key(payload))
            files.append(_descriptor(path, output_dir))
    ordered = tuple(sorted(files, key=lambda item: item.relative_path))
    values = {
        "execution_contract_id": prepared.execution_contract.contract_id,
        "provider_call_count": len(provider_ids),
        "unique_provider_call_count": len(set(provider_ids)),
        "files": ordered,
        "private_reasoning_payload_count": private_hits,
        "exact_byte_replay_pass_count": len(ordered),
    }
    provisional = ThinkingRepairRawLineageAudit.model_construct(audit_id="pending", **values)
    return ThinkingRepairRawLineageAudit(
        audit_id=thinking_repair_raw_lineage_audit_id(provisional),
        **values,
    )


def _next_transition(
    *,
    prepared: _PreparedInputs,
    results: Sequence[ThinkingRepairJobResult],
) -> str:
    policy = prepared.interpretation_contract
    if any(item.provider_transport_failure for item in results):
        return policy.transport_failure_transition
    instrument_rows = [item for item in results if item.terminal_category == "instrument_failure"]
    if instrument_rows:
        if all(item.telemetry_only_failure for item in instrument_rows):
            return policy.telemetry_only_failure_transition
        return policy.other_instrument_failure_transition
    if any(item.typed_no_call for item in results):
        return policy.budget_failure_transition
    if any(item.completion_unusable for item in results):
        length_types = {
            "length_truncated_content",
            "reasoning_only_length_truncation",
        }
        observed = {
            key
            for item in results
            for key, count in item.completion_failure_counts.items()
            if count
        }
        if observed & length_types:
            return policy.length_failure_transition
        return policy.nonlength_completion_failure_transition
    return policy.pass_transition


def _make_report(
    *,
    prepared: _PreparedInputs,
    results: Sequence[ThinkingRepairJobResult],
    raw_lineage: ThinkingRepairRawLineageAudit,
) -> ThinkingRepairExecutionReport:
    typed_no_call = sum(item.typed_no_call for item in results)
    completion_unusable = sum(item.completion_unusable for item in results)
    transport = sum(item.provider_transport_failure for item in results)
    instrument = sum(item.terminal_category == "instrument_failure" for item in results)
    telemetry_failures = sum(item.telemetry_failure for item in results)
    telemetry_only_failures = sum(item.telemetry_only_failure for item in results)
    exact_failures = sum(not item.exact_model_passed for item in results)
    native_failures = sum(not item.native_tool_absent for item in results)
    thinking_failures = sum(not item.thinking_continuity_passed for item in results)
    usage_complete = all(item.provider_usage_complete for item in results)
    budget_gate = _cp_upper(typed_no_call, JOB_COUNT) <= 0.10
    completion_gate = _cp_upper(completion_unusable, JOB_COUNT) <= 0.10
    telemetry_gate = not (
        telemetry_failures or exact_failures or native_failures or thinking_failures
    )
    execution_integrity = not (transport or instrument) and usage_complete
    passed = budget_gate and completion_gate and telemetry_gate and execution_integrity
    completion_failures = Counter(
        {
            key: sum(item.completion_failure_counts.get(key, 0) for item in results)
            for key in {key for item in results for key in item.completion_failure_counts}
        }
    )
    terminal_counts = dict(sorted(Counter(item.terminal_category for item in results).items()))
    program_closed = sum(item.program_closed for item in results)
    if not (telemetry_gate and execution_integrity):
        behavior_interpretation = "instrument_or_transport_failed"
    elif completion_unusable:
        behavior_interpretation = "completion_channel_failed"
    elif program_closed == 0:
        behavior_interpretation = "completion_channel_passed_behavior_floor"
    else:
        behavior_interpretation = "completion_channel_passed_behavior_nonfloor"
    total_cost = sum(
        (Decimal(item.estimated_cost_usd) for item in results),
        Decimal("0"),
    )
    values = {
        "execution_contract_id": prepared.execution_contract.contract_id,
        "preflight_report_id": prepared.preflight_report.report_id,
        "outcome_interpretation_contract_id": (prepared.interpretation_contract.contract_id),
        "raw_lineage_audit_id": raw_lineage.audit_id,
        "terminal_counts": terminal_counts,
        "provider_call_count": sum(item.provider_call_count for item in results),
        "http_success_call_count": sum(item.http_success_call_count for item in results),
        "provider_total_tokens": sum(item.provider_total_tokens for item in results),
        "provider_usage_complete": usage_complete,
        "estimated_cost_usd": format(total_cost, "f"),
        "reasoning_content_length_total": sum(
            item.reasoning_content_length_total for item in results
        ),
        "reasoning_tokens_total": sum(item.reasoning_tokens_total for item in results),
        "completion_tokens_total": sum(item.completion_tokens_total for item in results),
        "logical_request_count": sum(item.logical_request_count for item in results),
        "direct_usable_request_count": sum(item.direct_usable_request_count for item in results),
        "rescued_usable_request_count": sum(item.rescued_usable_request_count for item in results),
        "rescue_call_count": sum(item.rescue_call_count for item in results),
        "rescue_job_count": sum(item.rescue_call_count > 0 for item in results),
        "completion_limit_hit_count": sum(item.completion_limit_hit_count for item in results),
        "completion_failure_counts": dict(sorted(completion_failures.items())),
        "typed_no_call_job_count": typed_no_call,
        "typed_no_call_cp95_upper_32": _cp_upper(typed_no_call, JOB_COUNT),
        "typed_no_call_gate_passed": budget_gate,
        "completion_unusable_job_count": completion_unusable,
        "completion_unusable_cp95_upper_32": _cp_upper(
            completion_unusable,
            JOB_COUNT,
        ),
        "completion_usability_gate_passed": completion_gate,
        "provider_transport_failure_job_count": transport,
        "telemetry_failure_job_count": telemetry_failures,
        "telemetry_only_failure_job_count": telemetry_only_failures,
        "instrument_failure_job_count": instrument,
        "exact_model_failure_job_count": exact_failures,
        "native_tool_failure_job_count": native_failures,
        "thinking_continuity_failure_job_count": thinking_failures,
        "failed_observation_count": sum(item.failed_observation_count for item in results),
        "repeated_call_signature_count": sum(
            item.repeated_call_signature_count for item in results
        ),
        "repeated_failed_call_signature_count": sum(
            item.repeated_failed_call_signature_count for item in results
        ),
        "requested_path_adherence_count": sum(item.requested_path_adhered for item in results),
        "program_closed_count": program_closed,
        "mechanism_success_count": sum(item.mechanism_success for item in results),
        "independently_valid_trajectory_count": sum(item.independent_validity for item in results),
        "cell_summaries": _cell_summaries(results),
        "empirical_budget_adequacy_passed": budget_gate,
        "completion_usability_passed": completion_gate,
        "response_telemetry_instrument_passed": telemetry_gate,
        "execution_integrity_passed": execution_integrity,
        "behavior_interpretation": behavior_interpretation,
        "status": "passed" if passed else "blocked",
        "next_permitted_stage": _next_transition(
            prepared=prepared,
            results=results,
        ),
    }
    provisional = ThinkingRepairExecutionReport.model_construct(report_id="pending", **values)
    return ThinkingRepairExecutionReport(
        report_id=thinking_repair_execution_report_id(provisional),
        **values,
    )


def _load_checkpoint(
    *,
    path: Path,
    prepared: _PreparedInputs,
    output_dir: Path,
) -> tuple[ThinkingRepairJobResult, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        ThinkingRepairJobResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in prepared.manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("v26.95 checkpoint contains duplicate Jobs")
    for item in rows:
        raw_path = output_dir / item.raw_execution_artifact.relative_path
        if (
            item.job_id not in jobs
            or item.execution_contract_id != prepared.execution_contract.contract_id
            or _sha256(raw_path) != item.raw_execution_artifact.sha256
        ):
            raise ValueError("v26.95 checkpoint differs from frozen inputs")
    return rows


def _run_one_job(
    *,
    job: ThinkingRepairJob,
    prepared: _PreparedInputs,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    prompt_contract: CompactPromptContract,
    path_audit: ThinkingRepairPathAudit,
    client: Any | None,
    output_dir: Path,
) -> ThinkingRepairJobResult:
    raw = execute_thinking_repair_job_raw(
        job=job,
        execution_contract=prepared.execution_contract,
        provider_contract=prepared.provider_budget_contract,
        record=record,
        environment=environment,
        prompt_contract=prompt_contract,
        path_audit=path_audit,
        client=client,
        output_dir=output_dir,
    )
    return _score_raw_execution(
        raw=raw,
        prepared=prepared,
        record=record,
        environment=environment,
        output_dir=output_dir,
    )


def run_thinking_repair_execution(
    *,
    runner_preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    workers: int,
    client_factory: Callable[[AgentModelConfig], Any] = ProspectiveThinkingJsonClient,
) -> ThinkingRepairExecutionReport:
    prepared = prepare_thinking_repair_execution(
        runner_preflight_dir=runner_preflight_dir,
        output_dir=output_dir,
        package_root=package_root,
    )
    checkpoint_path = output_dir / "thinking_repair_job_results.checkpoint.jsonl"
    existing = _load_checkpoint(
        path=checkpoint_path,
        prepared=prepared,
        output_dir=output_dir,
    )
    completed = {item.job_id: item for item in existing}
    pending = [item for item in prepared.manifest.jobs if item.job_id not in completed]
    report_path = output_dir / "report.json"
    if pending and report_path.exists():
        raise ValueError("v26.95 completed report exists while Jobs remain pending")
    if not pending and report_path.exists():
        report = ThinkingRepairExecutionReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
        if report.execution_contract_id != prepared.execution_contract.contract_id:
            raise ValueError("v26.95 completed report crosses execution Contracts")
        return report
    raw_recovery_jobs = [item for item in pending if _raw_execution_path(output_dir, item).exists()]
    model_pending_jobs = [
        item for item in pending if not _raw_execution_path(output_dir, item).exists()
    ]
    for job in model_pending_jobs:
        provider_dir = _raw_provider_path(output_dir, job, 0).parent
        if provider_dir.exists() and any(provider_dir.glob("call_*.json")):
            raise ValueError("orphan v26.95 Provider Artifacts require a fresh Recovery Contract")
    client: Any | None = client_factory(prepared.agent_model_config) if model_pending_jobs else None
    print(
        f"[v26.95] resuming {len(completed)}/{JOB_COUNT}; "
        f"raw-only recovery {len(raw_recovery_jobs)}; "
        f"executing {len(model_pending_jobs)} Jobs with {workers} workers",
        flush=True,
    )
    package_by_id = {item.task_package_id: item for item in prepared.task_packages}
    record_by_id = {item.record_id: item for item in prepared.records}
    environment_by_id = {item.manifest_id: item for item in prepared.environments}
    prompt_by_id = {item.contract_id: item for item in prepared.prompt_contracts}
    path_by_id = {item.audit_id: item for item in prepared.path_audits}
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending) or 1))) as executor:
        future_map = {}
        for job in pending:
            package = package_by_id[job.repair_task_package_id]
            record = record_by_id[package.operational_record_id]
            future = executor.submit(
                _run_one_job,
                job=job,
                prepared=prepared,
                record=record,
                environment=environment_by_id[package.environment_manifest_id],
                prompt_contract=prompt_by_id[package.compact_prompt_contract_id],
                path_audit=path_by_id[job.repair_path_audit_id],
                client=None if job in raw_recovery_jobs else client,
                output_dir=output_dir,
            )
            future_map[future] = job
        for future in as_completed(future_map):
            job = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                with lock:
                    _append_jsonl(
                        output_dir / "runner_failures.checkpoint.jsonl",
                        {"job_id": job.job_id, "error": _safe_error(exc)},
                    )
                for queued in future_map:
                    if queued is not future:
                        queued.cancel()
                raise RuntimeError(
                    "v26.95 worker failed; exposed Jobs require raw-only Recovery"
                ) from exc
            with lock:
                if result.job_id in completed:
                    raise ValueError("v26.95 Runner produced a duplicate Job result")
                completed[result.job_id] = result
                _append_jsonl(checkpoint_path, result.model_dump(mode="json"))
                print(f"[v26.95] completed {len(completed)}/{JOB_COUNT}", flush=True)

    ordered = tuple(completed[item.job_id] for item in prepared.manifest.jobs)
    if len(ordered) != JOB_COUNT:
        raise ValueError("v26.95 execution ended with an incomplete denominator")
    raw_by_job = {
        job.job_id: _load_raw_execution(_raw_execution_path(output_dir, job))
        for job in prepared.manifest.jobs
    }
    raw_lineage = _raw_lineage_audit(
        prepared=prepared,
        results=ordered,
        raw_by_job=raw_by_job,
        output_dir=output_dir,
    )
    report = _make_report(
        prepared=prepared,
        results=ordered,
        raw_lineage=raw_lineage,
    )
    _write_json_atomic(
        output_dir / "thinking_repair_job_results.json",
        [item.model_dump(mode="json") for item in ordered],
    )
    _write_json_atomic(
        output_dir / "request_attempts.json",
        [
            attempt.model_dump(mode="json")
            for job in prepared.manifest.jobs
            for attempt in raw_by_job[job.job_id].request_attempts
        ],
    )
    _write_json_atomic(
        output_dir / "logical_requests.json",
        [
            request.model_dump(mode="json")
            for job in prepared.manifest.jobs
            for request in raw_by_job[job.job_id].logical_requests
        ],
    )
    _write_json_atomic(
        output_dir / "provider_budget_audits.json",
        [
            raw_by_job[job.job_id].provider_budget_audit.model_dump(mode="json")
            for job in prepared.manifest.jobs
        ],
    )
    _write_json_atomic(
        output_dir / "online_replay_results.json",
        [
            cast(AuthorityPreservingReplayResult, item.replay_result).model_dump(mode="json")
            for item in ordered
            if item.replay_result is not None
        ],
    )
    _write_json_atomic(
        output_dir / "verification_reports.json",
        [
            cast(
                AuthorityPreservingVerificationReport,
                item.verification_report,
            ).model_dump(mode="json")
            for item in ordered
            if item.verification_report is not None
        ],
    )
    _write_json_atomic(
        output_dir / "mechanism_diagnostics.json",
        [
            cast(MechanismEstimandOutcome, item.mechanism_outcome).model_dump(mode="json")
            for item in ordered
            if item.mechanism_outcome is not None
        ],
    )
    _write_json_atomic(
        output_dir / "cell_summaries.json",
        [item.model_dump(mode="json") for item in report.cell_summaries],
    )
    _write_json_atomic(
        output_dir / "raw_lineage_audit.json",
        raw_lineage.model_dump(mode="json"),
    )
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute the exact Finance v26.95 Thinking Completion repair Manifest"
    )
    parser.add_argument("--runner-preflight-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only:
        prepared = prepare_thinking_repair_execution(
            runner_preflight_dir=args.runner_preflight_dir,
            output_dir=args.output_dir,
            package_root=args.package_root,
        )
        print(
            json.dumps(
                {
                    "execution_contract_id": prepared.execution_contract.contract_id,
                    "source_replay_audit_id": prepared.source_replay.audit_id,
                    "expected_job_count": len(prepared.manifest.jobs),
                    "model_client_constructed": False,
                },
                sort_keys=True,
            )
        )
        return
    report = run_thinking_repair_execution(
        runner_preflight_dir=args.runner_preflight_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
