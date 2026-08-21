from __future__ import annotations

import argparse
import hashlib
import json
import threading
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

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
    replay_authority_preserving_observations,
    verify_authority_preserving_agent_result,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    MechanismEstimandOutcome,
    evaluate_mechanism_estimand,
    failure_artifact_mechanism_estimand,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    ImplementationSourceFile,
    OperationalTaskRecord,
    PathStrategy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_budget_calibration_preflight import (  # noqa: E501
    CALIBRATION_JOB_COUNT,
    CALIBRATION_TASK_COUNT,
    CalibrationStressPathAudit,
    CompactPromptContract,
    CompletionUsabilityContract,
    PredecessorReplayAudit,
    ThinkingBudgetCalibrationContract,
    ThinkingBudgetCalibrationJob,
    ThinkingBudgetCalibrationManifest,
    ThinkingBudgetCalibrationPreflightReport,
    _cp_upper,
    _load_and_replay_verifier_qualification,
    _load_predecessor,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    VerifierV2TaskReplayBinding,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    IterativeAgentFailureArtifact,
    IterativeAgentProtocolProfile,
    IterativeAgentSolver,
    IterativeAgentSolveResult,
    LLMClientError,
)
from trusted_synthesis.runtime.agent.budget_closed import (
    BudgetClosedJsonClient,
    ProviderBudgetNoCallTerminal,
    ProviderTokenBudgetAudit,
    ProviderTokenBudgetContract,
)
from trusted_synthesis.runtime.agent.compact_budget_prompt import (
    compact_public_progress,
    render_compact_decision_prompt,
    render_compact_final_prompt,
    render_compact_plan_prompt,
)
from trusted_synthesis.runtime.agent.iterative import (
    AgentLoopDecisionContract,
    AgentLoopPlanContract,
    _assert_no_model_forbidden_fields,
    _execute_tool,
    _noninterference_scanner_manifest_hash,
    _operation_step_rejection,
    _prompt_component_bytes,
    _prompt_noninterference_attestation_hash,
    _tool_call_signature,
    iterative_agent_audit_id,
    iterative_agent_failure_artifact_id,
)
from trusted_synthesis.runtime.agent.prospective_thinking import (
    ThinkingRequiredOpenAICompatibleJsonClient,
    bind_prospective_thinking,
)
from trusted_synthesis.runtime.agent.public_operation import (
    public_action_neutral_repair_result,
    public_operation_step_rejection,
    public_postcompletion_action_rejection,
    public_terminal_verification_rejection,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.agent.thinking_history import (
    CompletionUsabilityClassification,
    ThinkingContinuityContract,
    ThinkingHistoryAudit,
    attest_thinking_turn,
    audit_thinking_history,
    classify_completion_usability,
)
from trusted_synthesis.runtime.tools import (
    ARGUMENT_PATCH_REQUIRED_POLICY,
    AgentToolCall,
    AgentToolEnvironmentManifest,
    AgentToolObservation,
    AgentToolResult,
    agent_tool_argument_rejection,
    make_agent_tool_observation,
)

V26_92_SOURCE_REPLAY_VERSION = "finance_v26_thinking_calibration_online_replay.v1"
V26_92_EXECUTION_BINDING_VERSION = "finance_v26_thinking_calibration_execution_binding.v1"
V26_92_COMPACT_ATTEMPT_VERSION = "finance_v26_compact_calibration_attempt.v1"
V26_92_PROVIDER_CALL_VERSION = "finance_v26_thinking_calibration_provider_call.v1"
V26_92_RAW_EXECUTION_VERSION = "finance_v26_thinking_calibration_raw_execution.v1"
V26_92_JOB_RESULT_VERSION = "finance_v26_thinking_calibration_job_result.v1"
V26_92_CELL_SUMMARY_VERSION = "finance_v26_thinking_calibration_cell_summary.v1"
V26_92_RAW_LINEAGE_VERSION = "finance_v26_thinking_calibration_raw_lineage.v1"
V26_92_REPORT_VERSION = "finance_v26_thinking_budget_calibration_execution_report.v1"

EXPECTED_PREFLIGHT_REPORT_ID = (
    "finance_v26_thinking_budget_calibration_preflight_report:"
    "4af68e0667d05639885b985dd7d9091ed8fba03202e6b6c4ebf1d243586a8324"
)
EXPECTED_CONTRACT_ID = (
    "finance_v26_thinking_budget_calibration_contract:"
    "e147742ac18e0766b84162a25f87880340f0f2c57c79883e75db03fef935973d"
)
EXPECTED_MANIFEST_ID = (
    "finance_v26_thinking_budget_calibration_manifest:"
    "3c6877014f6fdd2de41cc3e0c52983b4242942967ec674fecc3630cbccdc630b"
)
EXPECTED_CONTINUITY_CONTRACT_ID = (
    "thinking_continuity_contract:a4c8025741e13e38025ac6250e18d57ad5e317a2f2db23d66b54d9d8de2144e8"
)
EXPECTED_COMPLETION_CONTRACT_ID = (
    "finance_v26_completion_usability_contract:"
    "e7ebf169c798a6af386024652e5b720d1157cd0c825c3c634bed9629cbe5498b"
)
EXPECTED_MODEL_CONFIG_ID = (
    "agent_model_config:727b3867544c4eac844eb260b9673dee41be7b8787b07ea2e3d6c69113e68bd1"
)
EXPECTED_THINKING_BINDING_ID = (
    "prospective_thinking_model_binding:"
    "51315bb03b5df2751c0cfada843fc75627c45b544d26efdd9ddac746a780f77d"
)
EXPECTED_PROVIDER_BUDGET_CONTRACT_ID = (
    "provider_token_budget_contract:"
    "27e7e524cb3139b9dd29b1ca7f2c7eae1956c96af8a982524f814b3ef4415150"
)
EXPECTED_PREFLIGHT_REPORT_SHA256 = (
    "0cf8363d21e7f785765c0153ca7b1852994657c89233b90285ede6a397e192cb"
)
PREFLIGHT_DIR = (
    "artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821"
)
DEFAULT_WORKERS = 8
REPAIR_MARKER = "\nCONTRACT_REPAIR_JSON:\n"
HOST_PLAN_SUBGOALS = ("public_contract_execution", "terminal_verification")
HOST_PLAN_STOP_CONDITIONS = ("public_stop_ready",)
EXTRA_PREFIX_PADDING_BYTES = 0

EXECUTION_SOURCE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_budget_calibration_execution.py"
)

TerminalCategory = Literal[
    "model_valid_trajectory",
    "model_invalid_trajectory",
    "typed_budget_no_call",
    "completion_unusable",
    "provider_transport_failure",
    "instrument_failure",
]
CompactRequestKind = Literal["plan", "decision", "final_answer"]
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


class CompactPlanResponse(FrozenModel):
    plan_summary: str = Field(min_length=1, max_length=240)


class CompactDecisionResponse(FrozenModel):
    action: Literal["call_tool", "emit_final"]
    rationale_summary: str = Field(min_length=1, max_length=512)
    tool_id: str | None = None
    arguments: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_action(self) -> CompactDecisionResponse:
        if self.action == "call_tool" and (not self.tool_id or self.arguments is None):
            raise ValueError("compact call_tool requires tool_id and arguments")
        if self.action == "emit_final" and (self.tool_id is not None or self.arguments is not None):
            raise ValueError("compact emit_final cannot contain a tool call")
        return self


class CompactFinalResponse(FrozenModel):
    rationale_summary: str = Field(min_length=1, max_length=512)
    answer: dict[str, Any]


class OnlineReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_91_report",
        "v26_91_detail",
        "v26_91_predecessor_binding",
        "v26_91_implementation",
        "v26_92_execution_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_hash(self) -> OnlineReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("online calibration source replay changed")
        return self


class CalibrationOnlineSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    entries: tuple[OnlineReplayEntry, ...] = Field(min_length=150)
    v26_91_output_file_count: Literal[31] = 31
    predecessor_binding_file_count: Literal[104] = 104
    implementation_binding_file_count: int = Field(ge=20)
    replayed_file_count: int = Field(ge=150)
    replay_pass_count: int = Field(ge=150)
    replay_before_credential_lookup: Literal[True] = True
    replay_before_client_construction: Literal[True] = True
    model_client_constructed: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_92_SOURCE_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CalibrationOnlineSourceReplayAudit:
        if self.preflight_report_id != EXPECTED_PREFLIGHT_REPORT_ID:
            raise ValueError("online calibration preflight identity changed")
        keys = tuple((item.source_kind, item.relative_path) for item in self.entries)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("online calibration replay entries are not canonical")
        if self.replayed_file_count != len(self.entries):
            raise ValueError("online calibration replay denominator changed")
        if self.replay_pass_count != self.replayed_file_count:
            raise ValueError("online calibration replay is incomplete")
        if self.audit_id != online_source_replay_audit_id(self):
            raise ValueError("online calibration replay identity is invalid")
        return self


class CalibrationExecutionBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    execution_run_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    calibration_contract_id: str = EXPECTED_CONTRACT_ID
    calibration_manifest_id: str = EXPECTED_MANIFEST_ID
    continuity_contract_id: str = EXPECTED_CONTINUITY_CONTRACT_ID
    completion_contract_id: str = EXPECTED_COMPLETION_CONTRACT_ID
    model_config_id: str = EXPECTED_MODEL_CONFIG_ID
    thinking_binding_id: str = EXPECTED_THINKING_BINDING_ID
    provider_budget_contract_id: str = EXPECTED_PROVIDER_BUDGET_CONTRACT_ID
    online_source_replay_audit_id: str = Field(min_length=1)
    expected_job_count: Literal[32] = CALIBRATION_JOB_COUNT
    expected_distinct_source_task_count: Literal[31] = CALIBRATION_TASK_COUNT
    exact_model_id: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    thinking_type: Literal["enabled"] = "enabled"
    fallback_forbidden: Literal[True] = True
    provider_native_tools_requested: Literal[False] = False
    compact_response_contract_version: Literal["finance_v26_compact_calibration_response.v1"] = (
        "finance_v26_compact_calibration_response.v1"
    )
    host_plan_subgoal_labels: tuple[str, ...] = HOST_PLAN_SUBGOALS
    host_plan_stop_conditions: tuple[str, ...] = HOST_PLAN_STOP_CONDITIONS
    final_citations_projected_from_successfully_selected_public_evidence: Literal[True] = True
    projected_citations_not_capability_evidence: Literal[True] = True
    registered_prefix_padding_reused_for_contract_repair: Literal[True] = True
    unregistered_prefix_padding_bytes: Literal[0] = 0
    unregistered_prefixes_reported_as_model_path_deviation: Literal[True] = True
    request_kind_mismatch_reported_as_model_path_deviation: Literal[True] = True
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_public_payload_persisted_before_contract_validation: Literal[True] = True
    raw_execution_persisted_before_verifier_scoring: Literal[True] = True
    every_job_executed_at_most_once: Literal[True] = True
    raw_only_recovery_required_after_exposure: Literal[True] = True
    calibration_rows_role_denominator_eligible: Literal[False] = False
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(min_length=20)
    schema_version: str = V26_92_EXECUTION_BINDING_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> CalibrationExecutionBinding:
        observed_ids = (
            self.preflight_report_id,
            self.calibration_contract_id,
            self.calibration_manifest_id,
            self.continuity_contract_id,
            self.completion_contract_id,
            self.model_config_id,
            self.thinking_binding_id,
            self.provider_budget_contract_id,
        )
        expected_ids = (
            EXPECTED_PREFLIGHT_REPORT_ID,
            EXPECTED_CONTRACT_ID,
            EXPECTED_MANIFEST_ID,
            EXPECTED_CONTINUITY_CONTRACT_ID,
            EXPECTED_COMPLETION_CONTRACT_ID,
            EXPECTED_MODEL_CONFIG_ID,
            EXPECTED_THINKING_BINDING_ID,
            EXPECTED_PROVIDER_BUDGET_CONTRACT_ID,
        )
        if observed_ids != expected_ids:
            raise ValueError("calibration execution predecessor identities changed")
        paths = tuple(item.relative_path for item in self.implementation_source_files)
        if paths != tuple(sorted(set(paths))) or EXECUTION_SOURCE_PATH not in paths:
            raise ValueError("calibration execution implementation binding is incomplete")
        if self.binding_id != calibration_execution_binding_id(self):
            raise ValueError("calibration execution binding identity is invalid")
        return self


class RawFileDescriptor(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)


class CompactRequestAttempt(FrozenModel):
    attempt_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    provider_request_index: int | None = Field(default=None, ge=0)
    request_kind: CompactRequestKind
    contract_repair: bool
    registered_stress_row_present: bool
    registered_request_kind: str | None = None
    request_kind_matches_registered: bool
    stress_schedule_exhausted: bool
    unpadded_prompt_sha256: str = Field(min_length=64, max_length=64)
    unpadded_prompt_utf8_bytes: int = Field(ge=1)
    trailing_ascii_space_padding_bytes: int = Field(ge=0)
    padded_base_prompt_sha256: str = Field(min_length=64, max_length=64)
    actual_prompt_sha256: str = Field(min_length=64, max_length=64)
    actual_prompt_utf8_bytes: int = Field(ge=1)
    compiler_unpadded_prefix_match: bool
    compiler_padded_prefix_match: bool
    provider_call_made: bool
    response_payload_present: bool
    compact_contract_valid: bool
    compact_contract_error: str | None = None
    transformed_for_legacy_runtime_only: Literal[True] = True
    private_reasoning_content_persisted: Literal[False] = False
    schema_version: str = V26_92_COMPACT_ATTEMPT_VERSION

    @model_validator(mode="after")
    def validate_attempt(self) -> CompactRequestAttempt:
        if self.stress_schedule_exhausted == self.registered_stress_row_present:
            raise ValueError("compact stress schedule accounting changed")
        if self.provider_call_made != (self.provider_request_index is not None):
            raise ValueError("compact Provider attempt index accounting changed")
        if self.compact_contract_valid and not self.response_payload_present:
            raise ValueError("valid compact response lacks a public payload")
        if self.compact_contract_valid == (self.compact_contract_error is not None):
            raise ValueError("compact contract error accounting changed")
        if self.attempt_id != compact_request_attempt_id(self):
            raise ValueError("compact request attempt identity is invalid")
        return self


class CalibrationRawProviderCall(FrozenModel):
    artifact_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    calibration_contract_id: str = EXPECTED_CONTRACT_ID
    job_id: str = Field(min_length=1)
    call_index: int = Field(ge=0)
    provider_call_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    prompt_sha256: str = Field(min_length=64, max_length=64)
    response_payload: dict[str, Any] | None = None
    provider_telemetry: ModelCallTelemetry
    captured_before_compact_contract_validation: Literal[True] = True
    private_reasoning_content_persisted: Literal[False] = False
    schema_version: str = V26_92_PROVIDER_CALL_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> CalibrationRawProviderCall:
        if self.calibration_contract_id != EXPECTED_CONTRACT_ID:
            raise ValueError("calibration raw Provider Contract changed")
        if self.prompt_sha256 != _sha256_text(self.prompt):
            raise ValueError("calibration raw Prompt hash changed")
        if self.provider_telemetry.request_hash != self.prompt_sha256:
            raise ValueError("calibration raw Prompt differs from Provider telemetry")
        if _contains_private_reasoning_key(self.response_payload):
            raise ValueError("calibration raw public payload contains private reasoning")
        expected = calibration_provider_call_id(
            self.job_id, self.call_index, self.provider_telemetry
        )
        if self.provider_call_id != expected:
            raise ValueError("calibration Provider call identity is invalid")
        if self.artifact_id != calibration_raw_provider_call_id(self):
            raise ValueError("calibration raw Provider Artifact identity is invalid")
        return self


class CalibrationRawExecution(FrozenModel):
    artifact_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    job: ThinkingBudgetCalibrationJob
    operational_record_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    stress_path_audit_id: str = Field(min_length=1)
    provider_call_artifacts: tuple[RawFileDescriptor, ...]
    provider_call_ids: tuple[str, ...]
    provider_telemetry: tuple[ModelCallTelemetry, ...]
    provider_prompts: tuple[str, ...]
    host_telemetry: tuple[ModelCallTelemetry, ...]
    host_prompts: tuple[str, ...]
    compact_attempts: tuple[CompactRequestAttempt, ...] = Field(min_length=1)
    provider_budget_audit: ProviderTokenBudgetAudit
    completion_classifications: tuple[CompletionUsabilityClassification, ...] = Field(min_length=1)
    thinking_history_audit: ThinkingHistoryAudit | None = None
    thinking_continuity_failure_ids: tuple[str, ...] = ()
    thinking_history_not_applicable_no_http_success: bool
    solve_result: IterativeAgentSolveResult | None = None
    failure_artifact: IterativeAgentFailureArtifact | None = None
    execution_error: str | None = None
    simulation_observation_match: bool
    private_reasoning_content_persisted: Literal[False] = False
    captured_before_verifier_scoring: Literal[True] = True
    schema_version: str = V26_92_RAW_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> CalibrationRawExecution:
        if (
            self.operational_record_id != self.job.operational_record_id
            or self.environment_manifest_id != self.job.environment_manifest_id
            or self.stress_path_audit_id != self.job.stress_path_audit_id
        ):
            raise ValueError("calibration raw execution crosses frozen Job inputs")
        calls = len(self.provider_call_ids)
        if not (
            calls
            == len(self.provider_call_artifacts)
            == len(self.provider_telemetry)
            == len(self.provider_prompts)
            == len(self.host_telemetry)
            == len(self.host_prompts)
        ):
            raise ValueError("calibration raw Provider accounting is incomplete")
        if self.provider_prompts != self.host_prompts:
            raise ValueError("calibration Provider and Host Prompt views differ")
        if tuple(_sha256_text(item) for item in self.provider_prompts) != tuple(
            item.request_hash for item in self.provider_telemetry
        ):
            raise ValueError("calibration Provider Prompt telemetry changed")
        if tuple(_sha256_text(item) for item in self.host_prompts) != tuple(
            item.request_hash for item in self.host_telemetry
        ):
            raise ValueError("calibration Host Prompt telemetry changed")
        if self.provider_budget_audit.provider_call_count != calls:
            raise ValueError("calibration Provider budget call count changed")
        if self.provider_budget_audit.actual_request_prompt_hashes != tuple(
            _sha256_text(item) for item in self.provider_prompts
        ):
            raise ValueError("calibration budget audit crosses Provider Prompts")
        if self.solve_result is not None and self.failure_artifact is not None:
            raise ValueError("calibration raw execution has two Agent outcomes")
        if self.solve_result is None and self.failure_artifact is None and not self.execution_error:
            raise ValueError("calibration raw execution lacks failure attribution")
        disposition_count = sum(
            (
                self.thinking_history_audit is not None,
                bool(self.thinking_continuity_failure_ids),
                self.thinking_history_not_applicable_no_http_success,
            )
        )
        if disposition_count != 1:
            raise ValueError("calibration raw execution lacks Thinking continuity disposition")
        if self.artifact_id != calibration_raw_execution_id(self):
            raise ValueError("calibration raw execution identity is invalid")
        return self


class CalibrationJobResult(FrozenModel):
    result_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    requested_path_strategy_id: PathStrategy
    terminal_category: TerminalCategory
    provider_call_count: int = Field(ge=0)
    http_success_call_count: int = Field(ge=0)
    reasoning_present_http_success_call_count: int = Field(ge=0)
    reasoning_content_length_total: int = Field(ge=0)
    reasoning_tokens_total: int = Field(ge=0)
    completion_tokens_total: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    provider_usage_complete: bool
    estimated_cost_usd: str = Field(min_length=1)
    typed_no_call: bool
    completion_unusable: bool
    provider_transport_failure: bool
    thinking_continuity_passed: bool
    exact_model_passed: bool
    fallback_absent: bool
    budget_contract_passed: bool
    simulation_observation_match: bool
    compact_logical_request_count: int = Field(ge=1)
    contract_repair_request_count: int = Field(ge=0)
    completion_limit_hit_count: int = Field(ge=0)
    reasoning_token_fraction_mean: float | None = Field(default=None, ge=0, le=1)
    reasoning_token_fraction_maximum: float | None = Field(default=None, ge=0, le=1)
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
    stress_schedule_exhausted: bool
    stress_request_kind_mismatch_count: int = Field(ge=0)
    compiler_prefix_match_count: int = Field(ge=0)
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
    schema_version: str = V26_92_JOB_RESULT_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> CalibrationJobResult:
        if not (
            self.reasoning_present_http_success_call_count
            <= self.http_success_call_count
            <= self.provider_call_count
        ):
            raise ValueError("calibration Job reasoning-call accounting changed")
        if (
            self.thinking_continuity_passed
            and self.http_success_call_count
            and self.reasoning_present_http_success_call_count != self.http_success_call_count
        ):
            raise ValueError("passing calibration Job lacks reasoning on an HTTP-success call")
        if self.reasoning_tokens_total > self.completion_tokens_total:
            raise ValueError("calibration Job reasoning Usage exceeds completion Usage")
        if self.typed_no_call != (self.no_call_terminal is not None):
            raise ValueError("calibration typed no-call accounting changed")
        if self.terminal_category == "model_valid_trajectory" and not self.independent_validity:
            raise ValueError("calibration valid terminal lacks independent validity")
        if self.independent_validity and self.verification_report is None:
            raise ValueError("calibration validity lacks a Verifier report")
        if self.requested_path_adhered != (self.actual_route == self.requested_path_strategy_id):
            raise ValueError("calibration path adherence arithmetic changed")
        if self.result_id != calibration_job_result_id(self):
            raise ValueError("calibration Job result identity is invalid")
        return self


class CalibrationCellSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: PathStrategy
    job_count: int = Field(ge=2)
    typed_no_call_count: int = Field(ge=0)
    completion_unusable_count: int = Field(ge=0)
    provider_transport_failure_count: int = Field(ge=0)
    thinking_continuity_failure_count: int = Field(ge=0)
    request_count: int = Field(ge=0)
    failed_observation_count: int = Field(ge=0)
    program_closed_count: int = Field(ge=0)
    mechanism_success_count: int = Field(ge=0)
    valid_trajectory_count: int = Field(ge=0)
    requested_path_adherence_count: int = Field(ge=0)
    reasoning_token_fraction_mean: float | None = Field(default=None, ge=0, le=1)
    reasoning_token_fraction_minimum: float | None = Field(default=None, ge=0, le=1)
    reasoning_token_fraction_maximum: float | None = Field(default=None, ge=0, le=1)
    mechanism_floor_observed: bool
    mechanism_saturation_observed: bool
    validity_floor_observed: bool
    validity_saturation_observed: bool
    descriptive_only: Literal[True] = True
    schema_version: str = V26_92_CELL_SUMMARY_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> CalibrationCellSummary:
        if self.mechanism_floor_observed != (self.mechanism_success_count == 0):
            raise ValueError("calibration mechanism floor changed")
        if self.mechanism_saturation_observed != (self.mechanism_success_count == self.job_count):
            raise ValueError("calibration mechanism saturation changed")
        if self.validity_floor_observed != (self.valid_trajectory_count == 0):
            raise ValueError("calibration validity floor changed")
        if self.validity_saturation_observed != (self.valid_trajectory_count == self.job_count):
            raise ValueError("calibration validity saturation changed")
        if self.summary_id != calibration_cell_summary_id(self):
            raise ValueError("calibration cell summary identity is invalid")
        return self


class CalibrationRawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    expected_job_count: Literal[32] = CALIBRATION_JOB_COUNT
    raw_execution_count: Literal[32] = CALIBRATION_JOB_COUNT
    provider_call_count: int = Field(ge=0)
    unique_provider_call_count: int = Field(ge=0)
    files: tuple[RawFileDescriptor, ...] = Field(min_length=32)
    private_reasoning_payload_count: Literal[0] = 0
    exact_byte_replay_pass_count: int = Field(ge=32)
    status: Literal["passed"] = "passed"
    schema_version: str = V26_92_RAW_LINEAGE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CalibrationRawLineageAudit:
        paths = tuple(item.relative_path for item in self.files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("calibration raw lineage paths are not canonical")
        if self.unique_provider_call_count != self.provider_call_count:
            raise ValueError("calibration Provider identities are not unique")
        if self.exact_byte_replay_pass_count != len(self.files):
            raise ValueError("calibration raw lineage replay is incomplete")
        if self.audit_id != calibration_raw_lineage_audit_id(self):
            raise ValueError("calibration raw lineage identity is invalid")
        return self


class CalibrationExecutionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    execution_run_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    calibration_contract_id: str = EXPECTED_CONTRACT_ID
    calibration_manifest_id: str = EXPECTED_MANIFEST_ID
    raw_lineage_audit_id: str = Field(min_length=1)
    discovered_models: tuple[str, ...] = Field(min_length=1)
    expected_job_count: Literal[32] = CALIBRATION_JOB_COUNT
    completed_job_count: Literal[32] = CALIBRATION_JOB_COUNT
    distinct_source_task_count: Literal[31] = CALIBRATION_TASK_COUNT
    terminal_counts: dict[str, int]
    provider_call_count: int = Field(ge=0)
    http_success_call_count: int = Field(ge=0)
    reasoning_present_http_success_call_count: int = Field(ge=0)
    reasoning_content_length_total: int = Field(ge=0)
    reasoning_tokens_total: int = Field(ge=0)
    completion_tokens_total: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    provider_usage_complete: bool
    estimated_cost_usd: str = Field(min_length=1)
    typed_no_call_job_count: int = Field(ge=0)
    typed_no_call_cp95_upper_32: float = Field(ge=0, le=1)
    typed_no_call_gate_passed: bool
    typed_no_call_unique_source_count: int = Field(ge=0)
    typed_no_call_cp95_upper_31: float = Field(ge=0, le=1)
    typed_no_call_unique_source_sensitivity_passed: bool
    completion_unusable_job_count: int = Field(ge=0)
    completion_unusable_cp95_upper_32: float = Field(ge=0, le=1)
    completion_usability_gate_passed: bool
    completion_unusable_unique_source_count: int = Field(ge=0)
    completion_unusable_cp95_upper_31: float = Field(ge=0, le=1)
    completion_unique_source_sensitivity_passed: bool
    provider_transport_failure_job_count: int = Field(ge=0)
    thinking_continuity_failure_job_count: int = Field(ge=0)
    instrument_failure_job_count: int = Field(ge=0)
    completion_limit_hit_count: int = Field(ge=0)
    logical_request_count: int = Field(ge=0)
    contract_repair_request_count: int = Field(ge=0)
    contract_repair_job_count: int = Field(ge=0)
    contract_repair_request_rate: float = Field(ge=0, le=1)
    completion_outcome_counts: dict[str, int]
    failed_observation_count: int = Field(ge=0)
    repeated_call_signature_count: int = Field(ge=0)
    repeated_failed_call_signature_count: int = Field(ge=0)
    requested_path_adherence_count: int = Field(ge=0)
    program_closed_count: int = Field(ge=0)
    mechanism_success_count: int = Field(ge=0)
    independently_valid_trajectory_count: int = Field(ge=0)
    reasoning_token_fraction_mean: float | None = Field(default=None, ge=0, le=1)
    reasoning_token_fraction_minimum: float | None = Field(default=None, ge=0, le=1)
    reasoning_token_fraction_maximum: float | None = Field(default=None, ge=0, le=1)
    cell_summaries: tuple[CalibrationCellSummary, ...] = Field(min_length=12, max_length=12)
    all_jobs_exact_model: bool
    all_jobs_fallback_absent: bool
    all_jobs_budget_contract_passed: bool
    raw_lineage_passed: Literal[True] = True
    empirical_budget_adequacy_passed: bool
    completion_usability_passed: bool
    thinking_instrument_passed: bool
    execution_integrity_passed: bool
    behavior_diagnostics_descriptive_only: Literal[True] = True
    task_depth_informativeness_resolved: Literal[False] = False
    historical_non_thinking_comparison_performed: Literal[False] = False
    role_protocol_frozen: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    status: Literal["passed", "blocked"]
    next_permitted_stage: Literal[
        "thinking_role_protocol_freeze_only",
        "thinking_completion_root_cause_audit_only",
        "thinking_budget_deviation_root_cause_audit_only",
        "thinking_instrument_repair_or_recovery_only",
    ]
    schema_version: str = V26_92_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> CalibrationExecutionReport:
        if (
            self.preflight_report_id,
            self.calibration_contract_id,
            self.calibration_manifest_id,
        ) != (
            EXPECTED_PREFLIGHT_REPORT_ID,
            EXPECTED_CONTRACT_ID,
            EXPECTED_MANIFEST_ID,
        ):
            raise ValueError("calibration report predecessor identities changed")
        if sum(self.terminal_counts.values()) != self.completed_job_count:
            raise ValueError("calibration report terminal denominator changed")
        if sum(self.completion_outcome_counts.values()) != self.logical_request_count:
            raise ValueError("calibration completion outcome denominator changed")
        expected_repair_rate = (
            self.contract_repair_request_count / self.logical_request_count
            if self.logical_request_count
            else 0.0
        )
        if abs(self.contract_repair_request_rate - expected_repair_rate) > 1e-12:
            raise ValueError("calibration Contract-repair rate changed")
        if not (
            self.reasoning_present_http_success_call_count
            <= self.http_success_call_count
            <= self.provider_call_count
        ):
            raise ValueError("calibration report reasoning-call accounting changed")
        if self.reasoning_tokens_total > self.completion_tokens_total:
            raise ValueError("calibration report reasoning Usage exceeds completion Usage")
        if self.typed_no_call_gate_passed != (self.typed_no_call_cp95_upper_32 <= 0.10):
            raise ValueError("calibration no-call Gate arithmetic changed")
        if self.completion_usability_gate_passed != (
            self.completion_unusable_cp95_upper_32 <= 0.10
        ):
            raise ValueError("calibration Completion Gate arithmetic changed")
        passed = (
            self.typed_no_call_gate_passed
            and self.completion_usability_gate_passed
            and self.thinking_instrument_passed
            and self.execution_integrity_passed
        )
        if (self.status == "passed") != passed:
            raise ValueError("calibration report status changed")
        expected_transition = (
            "thinking_role_protocol_freeze_only"
            if passed
            else "thinking_instrument_repair_or_recovery_only"
            if (
                self.instrument_failure_job_count
                or self.provider_transport_failure_job_count
                or self.thinking_continuity_failure_job_count
            )
            else "thinking_budget_deviation_root_cause_audit_only"
            if self.typed_no_call_job_count
            else "thinking_completion_root_cause_audit_only"
            if self.completion_unusable_job_count
            else "thinking_instrument_repair_or_recovery_only"
        )
        if self.next_permitted_stage != expected_transition:
            raise ValueError("calibration report transition changed")
        if self.report_id != calibration_execution_report_id(self):
            raise ValueError("calibration execution report identity is invalid")
        return self


class _PreparedInputs(FrozenModel):
    preflight: ThinkingBudgetCalibrationPreflightReport
    contract: ThinkingBudgetCalibrationContract
    manifest: ThinkingBudgetCalibrationManifest
    continuity_contract: ThinkingContinuityContract
    provider_budget_contract: ProviderTokenBudgetContract
    agent_model_config: AgentModelConfig
    records: tuple[OperationalTaskRecord, ...]
    environments: tuple[AgentToolEnvironmentManifest, ...]
    replay_bindings: tuple[VerifierV2TaskReplayBinding, ...]
    prompt_contracts: tuple[CompactPromptContract, ...]
    stress_paths: tuple[CalibrationStressPathAudit, ...]
    replay_contract: AuthorityPreservingReplayContract
    source_audit: CalibrationOnlineSourceReplayAudit
    execution_binding: CalibrationExecutionBinding


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def online_source_replay_audit_id(value: CalibrationOnlineSourceReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_calibration_online_replay:")


def calibration_execution_binding_id(value: CalibrationExecutionBinding) -> str:
    return _identity(value, "binding_id", "finance_v26_thinking_calibration_execution_binding:")


def compact_request_attempt_id(value: CompactRequestAttempt) -> str:
    return _identity(value, "attempt_id", "finance_v26_compact_calibration_attempt:")


def calibration_raw_provider_call_id(value: CalibrationRawProviderCall) -> str:
    return _identity(value, "artifact_id", "finance_v26_thinking_calibration_provider_call:")


def calibration_raw_execution_id(value: CalibrationRawExecution) -> str:
    return _identity(value, "artifact_id", "finance_v26_thinking_calibration_raw_execution:")


def calibration_job_result_id(value: CalibrationJobResult) -> str:
    return _identity(value, "result_id", "finance_v26_thinking_calibration_job_result:")


def calibration_cell_summary_id(value: CalibrationCellSummary) -> str:
    return _identity(value, "summary_id", "finance_v26_thinking_calibration_cell_summary:")


def calibration_raw_lineage_audit_id(value: CalibrationRawLineageAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_calibration_raw_lineage:")


def calibration_execution_report_id(value: CalibrationExecutionReport) -> str:
    return _identity(value, "report_id", "finance_v26_thinking_budget_calibration_execution:")


def calibration_provider_call_id(
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
            "http_status": telemetry.http_status,
        },
        prefix="finance_v26_thinking_calibration_provider_call_id:",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_error(exc: Exception) -> str:
    return f"{type(exc).__name__}:{str(exc)[:1200]}"


def _contains_private_reasoning_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key) == "reasoning_content" or _contains_private_reasoning_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_private_reasoning_key(item) for item in value)
    return False


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


def _raw_provider_path(
    output_dir: Path,
    job: ThinkingBudgetCalibrationJob,
    call_index: int,
) -> Path:
    job_hash = hashlib.sha256(job.job_id.encode("utf-8")).hexdigest()[:20]
    return output_dir / "raw_provider_calls" / job_hash / f"call_{call_index:04d}.json"


def _raw_execution_path(output_dir: Path, job: ThinkingBudgetCalibrationJob) -> Path:
    job_hash = hashlib.sha256(job.job_id.encode("utf-8")).hexdigest()[:20]
    return output_dir / "raw_execution" / f"{job_hash}.json"


def _relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


class _RawFirstJournalClient:
    """Persist parsed public content and redacted telemetry before Host validation."""

    def __init__(
        self,
        delegate: Any,
        *,
        execution_binding: CalibrationExecutionBinding,
        job: ThinkingBudgetCalibrationJob,
        output_dir: Path,
    ) -> None:
        self._delegate = delegate
        self._execution_binding = execution_binding
        self._job = job
        self._output_dir = output_dir
        self.telemetry: list[ModelCallTelemetry] = []
        self.prompts: list[str] = []
        self.descriptors: list[RawFileDescriptor] = []

    @property
    def config(self) -> AgentModelConfig:
        return self._delegate.config

    def _record(
        self,
        prompt: str,
        response_payload: dict[str, Any] | None,
        telemetry: ModelCallTelemetry,
    ) -> None:
        call_index = len(self.telemetry)
        values = {
            "execution_binding_id": self._execution_binding.binding_id,
            "job_id": self._job.job_id,
            "call_index": call_index,
            "provider_call_id": calibration_provider_call_id(
                self._job.job_id, call_index, telemetry
            ),
            "prompt": prompt,
            "prompt_sha256": _sha256_text(prompt),
            "response_payload": response_payload,
            "provider_telemetry": telemetry,
        }
        provisional = CalibrationRawProviderCall.model_construct(artifact_id="pending", **values)
        artifact = CalibrationRawProviderCall(
            artifact_id=calibration_raw_provider_call_id(provisional),
            **values,
        )
        path = _raw_provider_path(self._output_dir, self._job, call_index)
        digest = _write_json_atomic(path, artifact.model_dump(mode="json"))
        self.telemetry.append(telemetry)
        self.prompts.append(prompt)
        self.descriptors.append(
            RawFileDescriptor(
                relative_path=_relative(path, self._output_dir),
                sha256=digest,
                byte_count=path.stat().st_size,
            )
        )

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        try:
            payload, telemetry = self._delegate.complete_json(prompt)
        except LLMClientError as exc:
            for telemetry in exc.telemetry:
                self._record(prompt, None, telemetry)
            raise
        self._record(prompt, payload, telemetry)
        return payload, telemetry


class _CompactCalibrationClient:
    """Render frozen compact Prompts while preserving the established Agent loop."""

    def __init__(
        self,
        delegate: BudgetClosedJsonClient,
        *,
        task: Any,
        environment: AgentToolEnvironmentManifest,
        runtime: FinanceExecutableSupportRuntime,
        prompt_contract: CompactPromptContract,
        stress_path: CalibrationStressPathAudit,
        path_strategy: PathStrategy,
    ) -> None:
        self._delegate = delegate
        self._task = task
        self._environment = environment
        self._runtime = runtime
        self._prompt_contract = prompt_contract
        self._stress_path = stress_path
        self._path_strategy = path_strategy
        self._observations: list[AgentToolObservation] = []
        self._plan_complete = False
        self._active_index: int | None = None
        self._active_kind: CompactRequestKind | None = None
        self._active_base_prompt: str | None = None
        self._active_validation_error = ""
        self._active_payload_keys: tuple[str, ...] = ()
        self._next_logical_index = 0
        self._provider_request_count = 0
        self.attempts: list[CompactRequestAttempt] = []
        self.actual_provider_prompts: list[str] = []
        self.logical_base_prompts: list[str] = []

    @property
    def config(self) -> AgentModelConfig:
        return self._delegate.config

    @property
    def observations(self) -> tuple[AgentToolObservation, ...]:
        return tuple(self._observations)

    def _request_kind(self) -> CompactRequestKind:
        if not self._plan_complete:
            return "plan"
        progress = compact_public_progress(self._task, tuple(self._observations))
        return "final_answer" if progress["final_answer_allowed"] else "decision"

    def _render(self, kind: CompactRequestKind) -> str:
        context = self._prompt_contract.public_context
        if kind == "plan":
            return render_compact_plan_prompt(
                context,
                public_path_condition=self._path_strategy,
            )
        if kind == "final_answer":
            return render_compact_final_prompt(
                context,
                self._task,
                tuple(self._observations),
                public_path_condition=self._path_strategy,
            )
        return render_compact_decision_prompt(
            context,
            self._task,
            tuple(self._observations),
            public_path_condition=self._path_strategy,
        )

    def _open_logical_request(self) -> tuple[int, CompactRequestKind, str]:
        if self._active_index is None:
            self._active_index = self._next_logical_index
            self._next_logical_index += 1
            self._active_kind = self._request_kind()
            self._active_base_prompt = self._render(self._active_kind)
            self._active_validation_error = ""
            self._active_payload_keys = ()
            self.logical_base_prompts.append(self._active_base_prompt)
        if self._active_kind is None or self._active_base_prompt is None:
            raise RuntimeError("compact logical request state is incomplete")
        return self._active_index, self._active_kind, self._active_base_prompt

    def _repair_suffix(self, kind: CompactRequestKind) -> str:
        model_type: type[BaseModel]
        if kind == "plan":
            model_type = CompactPlanResponse
        elif kind == "decision":
            model_type = CompactDecisionResponse
        else:
            model_type = CompactFinalResponse
        note = json.dumps(
            {
                "validation_error": self._active_validation_error[:1200],
                "previous_payload_keys": self._active_payload_keys,
                "required_json_fields": tuple(model_type.model_fields),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return REPAIR_MARKER + note + "\nReturn only the corrected compact response object."

    def _padded_prompt(
        self,
        *,
        logical_index: int,
        kind: CompactRequestKind,
        base_prompt: str,
        repair: bool,
    ) -> tuple[str, dict[str, Any]]:
        row = (
            self._stress_path.rows[logical_index]
            if logical_index < len(self._stress_path.rows)
            else None
        )
        padding = (
            row.trailing_ascii_space_padding_bytes
            if row is not None
            else EXTRA_PREFIX_PADDING_BYTES
        )
        padded_base = base_prompt + (" " * padding)
        actual = padded_base + (self._repair_suffix(kind) if repair else "")
        metadata = {
            "registered_stress_row_present": row is not None,
            "registered_request_kind": row.request_kind if row is not None else None,
            "request_kind_matches_registered": row is not None and row.request_kind == kind,
            "stress_schedule_exhausted": row is None,
            "unpadded_prompt_sha256": _sha256_text(base_prompt),
            "unpadded_prompt_utf8_bytes": len(base_prompt.encode("utf-8")),
            "trailing_ascii_space_padding_bytes": padding,
            "padded_base_prompt_sha256": _sha256_text(padded_base),
            "actual_prompt_sha256": _sha256_text(actual),
            "actual_prompt_utf8_bytes": len(actual.encode("utf-8")),
            "compiler_unpadded_prefix_match": (
                row is not None and row.unpadded_prompt_sha256 == _sha256_text(base_prompt)
            ),
            "compiler_padded_prefix_match": (
                row is not None and row.padded_prompt_sha256 == _sha256_text(padded_base)
            ),
        }
        return actual, metadata

    def _translated_telemetry(
        self,
        telemetry: ModelCallTelemetry,
        source_prompt: str,
        *,
        compact_contract_valid: bool | None = None,
        contract_error: str | None = None,
    ) -> ModelCallTelemetry:
        updates: dict[str, Any] = {"request_hash": _sha256_text(source_prompt)}
        if compact_contract_valid is False:
            updates.update(
                {
                    "json_contract_success": False,
                    "error_type": "CompactCalibrationContractError",
                    "error_message": contract_error,
                    "contract_errors": (contract_error or "compact contract invalid",),
                }
            )
        return telemetry.model_copy(update=updates)

    def _record_attempt(
        self,
        *,
        logical_index: int,
        kind: CompactRequestKind,
        repair: bool,
        metadata: Mapping[str, Any],
        provider_call_made: bool,
        provider_request_index: int | None,
        response_payload_present: bool,
        compact_contract_valid: bool,
        compact_contract_error: str | None,
    ) -> None:
        values = {
            "logical_request_index": logical_index,
            "provider_request_index": provider_request_index,
            "request_kind": kind,
            "contract_repair": repair,
            **dict(metadata),
            "provider_call_made": provider_call_made,
            "response_payload_present": response_payload_present,
            "compact_contract_valid": compact_contract_valid,
            "compact_contract_error": compact_contract_error,
        }
        provisional = CompactRequestAttempt.model_construct(attempt_id="pending", **values)
        self.attempts.append(
            CompactRequestAttempt(
                attempt_id=compact_request_attempt_id(provisional),
                **values,
            )
        )

    def _simulate_tool(self, decision: AgentLoopDecisionContract) -> None:
        if decision.decision_type != "tool_call":
            return
        if len(self._observations) >= self._environment.maximum_tool_calls:
            return
        selectable = {
            item.tool_id: item for item in self._environment.tools if item.model_selectable
        }
        tool_id = decision.tool_id or ""
        spec = selectable.get(tool_id)
        if spec is None:
            return
        _assert_no_model_forbidden_fields(decision.arguments or {})
        call = AgentToolCall(
            call_index=len(self._observations) + 1,
            tool_id=tool_id,
            arguments=decision.arguments or {},
        )
        failed_signatures: set[str] = set()
        for item in reversed(self._observations):
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
                error_message=("The Host blocked an identical failed action without executing it."),
            )
        else:
            observations = tuple(self._observations)
            result = (
                public_postcompletion_action_rejection(self._task, observations, call)
                or agent_tool_argument_rejection(spec, call)
                or public_terminal_verification_rejection(self._task, observations, call)
                or public_operation_step_rejection(self._task, observations, call)
                or _operation_step_rejection(self._task, observations, call)
                or _execute_tool(self._runtime, call)
            )
        result = public_action_neutral_repair_result(
            self._task,
            tuple(self._observations),
            call,
            result,
        )
        _assert_no_model_forbidden_fields(result.result)
        if result.status == "succeeded":
            spec.validate_output(result.result)
        self._observations.append(
            make_agent_tool_observation(
                environment_manifest_id=self._environment.manifest_id,
                call=call,
                result=result,
                observation_time_hash=canonical_hash(
                    {
                        "snapshot_id": self._environment.snapshot_id,
                        "call_index": call.call_index,
                    },
                    prefix="agent_observation_time:",
                ),
            )
        )

    def _selected_evidence_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    evidence_id
                    for item in self._observations
                    if item.status == "succeeded"
                    and item.call.tool_id in {"query_structured_fact", "open_document"}
                    for evidence_id in item.evidence_ids
                }
            )
        )

    def _validate_and_transform(
        self,
        kind: CompactRequestKind,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if kind == "plan":
            response = CompactPlanResponse.model_validate(payload)
            transformed = AgentLoopPlanContract(
                plan_summary=response.plan_summary,
                subgoal_labels=HOST_PLAN_SUBGOALS,
                stop_conditions=HOST_PLAN_STOP_CONDITIONS,
            )
            self._plan_complete = True
            return transformed.model_dump(mode="json")
        if kind == "final_answer":
            response = CompactFinalResponse.model_validate(payload)
            citations = self._selected_evidence_ids()
            if not citations:
                raise ValueError("compact final response has no selected public Evidence")
            transformed = AgentLoopDecisionContract(
                decision_type="final_answer",
                rationale_summary=response.rationale_summary,
                answer=response.answer,
                cited_evidence_ids=citations,
            )
            return transformed.model_dump(mode="json")
        response = CompactDecisionResponse.model_validate(payload)
        if response.action == "call_tool":
            transformed = AgentLoopDecisionContract(
                decision_type="tool_call",
                rationale_summary=response.rationale_summary,
                tool_id=response.tool_id,
                arguments=response.arguments,
            )
            return transformed.model_dump(mode="json")
        transformed = AgentLoopDecisionContract(
            decision_type="final_answer",
            rationale_summary=response.rationale_summary,
            answer={},
            cited_evidence_ids=("public_early_stop_request",),
        )
        return transformed.model_dump(mode="json")

    def complete_json(self, source_prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        repair = REPAIR_MARKER in source_prompt
        logical_index, kind, base_prompt = self._open_logical_request()
        actual_prompt, metadata = self._padded_prompt(
            logical_index=logical_index,
            kind=kind,
            base_prompt=base_prompt,
            repair=repair,
        )
        provider_index_before = self._provider_request_count
        try:
            payload, telemetry = self._delegate.complete_json(actual_prompt)
        except LLMClientError as exc:
            made = bool(exc.telemetry)
            provider_index = provider_index_before if made else None
            self._provider_request_count += len(exc.telemetry)
            self.actual_provider_prompts.extend(actual_prompt for _ in exc.telemetry)
            error = _safe_error(exc)
            self._active_validation_error = error
            self._active_payload_keys = ()
            self._record_attempt(
                logical_index=logical_index,
                kind=kind,
                repair=repair,
                metadata=metadata,
                provider_call_made=made,
                provider_request_index=provider_index,
                response_payload_present=False,
                compact_contract_valid=False,
                compact_contract_error=error,
            )
            translated = tuple(
                self._translated_telemetry(item, source_prompt) for item in exc.telemetry
            )
            raise LLMClientError(str(exc), translated) from exc
        self._provider_request_count += 1
        self.actual_provider_prompts.append(actual_prompt)
        try:
            transformed = self._validate_and_transform(kind, payload)
        except (ValidationError, ValueError) as exc:
            error = _safe_error(exc)
            self._active_validation_error = error
            self._active_payload_keys = tuple(sorted(str(key) for key in payload))
            self._record_attempt(
                logical_index=logical_index,
                kind=kind,
                repair=repair,
                metadata=metadata,
                provider_call_made=True,
                provider_request_index=provider_index_before,
                response_payload_present=True,
                compact_contract_valid=False,
                compact_contract_error=error,
            )
            translated = self._translated_telemetry(
                telemetry,
                source_prompt,
                compact_contract_valid=False,
                contract_error=error,
            )
            raise LLMClientError(
                "model failed compact calibration contract", (translated,)
            ) from exc
        self._record_attempt(
            logical_index=logical_index,
            kind=kind,
            repair=repair,
            metadata=metadata,
            provider_call_made=True,
            provider_request_index=provider_index_before,
            response_payload_present=True,
            compact_contract_valid=True,
            compact_contract_error=None,
        )
        transformed_decision = (
            AgentLoopDecisionContract.model_validate(transformed) if kind == "decision" else None
        )
        if transformed_decision is not None and transformed_decision.decision_type == "tool_call":
            self._simulate_tool(transformed_decision)
        self._active_index = None
        self._active_kind = None
        self._active_base_prompt = None
        self._active_validation_error = ""
        self._active_payload_keys = ()
        return transformed, self._translated_telemetry(telemetry, source_prompt)


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


def _host_telemetry(
    telemetry: Sequence[ModelCallTelemetry],
    prompts: Sequence[str],
) -> tuple[ModelCallTelemetry, ...]:
    if len(telemetry) != len(prompts):
        raise ValueError("compact Host telemetry and Prompt counts differ")
    output = []
    for item, prompt in zip(telemetry, prompts, strict=True):
        shape = dict(item.response_shape)
        shape["prompt_component_bytes"] = _prompt_component_bytes(prompt)
        output.append(
            item.model_copy(
                update={
                    "request_hash": _sha256_text(prompt),
                    "response_shape": shape,
                }
            )
        )
    return tuple(output)


def _base_prompt_hashes(
    attempts: Sequence[CompactRequestAttempt],
    logical_base_prompts: Sequence[str],
) -> tuple[str, tuple[str, ...]]:
    by_index: dict[int, CompactRequestAttempt] = {}
    for attempt in attempts:
        by_index.setdefault(attempt.logical_request_index, attempt)
    ordered = tuple(by_index[index] for index in sorted(by_index))
    if not ordered or ordered[0].request_kind != "plan":
        raise ValueError("compact Agent history lacks a plan request")
    if len(logical_base_prompts) != len(ordered):
        raise ValueError("compact logical Prompt accounting changed")
    padded = tuple(
        base + (" " * item.trailing_ascii_space_padding_bytes)
        for base, item in zip(logical_base_prompts, ordered, strict=True)
    )
    return (
        canonical_hash(padded[0], prefix="agent_plan_prompt:"),
        tuple(canonical_hash(item, prefix="agent_decision_prompt:") for item in padded[1:]),
    )


def _normalize_solve_result(
    result: IterativeAgentSolveResult,
    adapter: _CompactCalibrationClient,
) -> IterativeAgentSolveResult:
    host_telemetry = _host_telemetry(result.audit.telemetry, adapter.actual_provider_prompts)
    plan_hash, decision_hashes = _base_prompt_hashes(adapter.attempts, adapter.logical_base_prompts)
    scanner = _noninterference_scanner_manifest_hash()
    request_hashes = tuple(_sha256_text(item) for item in adapter.actual_provider_prompts)
    values = result.audit.model_dump(
        mode="python",
        exclude={
            "audit_id",
            "plan_prompt_hash",
            "decision_prompt_hashes",
            "final_model_prompt_hash",
            "plan_prompt_noninterference_attestation_hash",
            "decision_prompt_noninterference_attestation_hashes",
            "model_request_prompts",
            "model_request_prompt_hashes",
            "model_request_prompt_noninterference_attestation_hashes",
            "telemetry",
        },
    )
    values.update(
        {
            "plan_prompt_hash": plan_hash,
            "decision_prompt_hashes": decision_hashes,
            "final_model_prompt_hash": request_hashes[-1],
            "plan_prompt_noninterference_attestation_hash": (
                _prompt_noninterference_attestation_hash(plan_hash, scanner)
            ),
            "decision_prompt_noninterference_attestation_hashes": tuple(
                _prompt_noninterference_attestation_hash(item, scanner) for item in decision_hashes
            ),
            "model_request_prompts": tuple(adapter.actual_provider_prompts),
            "model_request_prompt_hashes": request_hashes,
            "model_request_prompt_noninterference_attestation_hashes": tuple(
                _prompt_noninterference_attestation_hash(item, scanner) for item in request_hashes
            ),
            "telemetry": host_telemetry,
        }
    )
    provisional = type(result.audit).model_construct(audit_id="pending", **values)
    audit = type(result.audit)(audit_id=iterative_agent_audit_id(provisional), **values)
    return IterativeAgentSolveResult(
        trajectory=result.trajectory,
        audit=audit,
        observations=result.observations,
    )


def _normalize_failure_artifact(
    artifact: IterativeAgentFailureArtifact,
    adapter: _CompactCalibrationClient,
) -> IterativeAgentFailureArtifact:
    prompts = tuple(adapter.actual_provider_prompts)
    telemetry = _host_telemetry(artifact.telemetry, prompts)
    scanner = _noninterference_scanner_manifest_hash()
    request_hashes = tuple(_sha256_text(item) for item in prompts)
    if adapter.logical_base_prompts:
        plan_hash, decision_hashes = _base_prompt_hashes(
            adapter.attempts, adapter.logical_base_prompts
        )
    else:
        plan_hash, decision_hashes = None, ()
    values = artifact.model_dump(
        mode="python",
        exclude={
            "artifact_id",
            "telemetry",
            "plan_prompt_hash",
            "decision_prompt_hashes",
            "last_model_prompt_hash",
            "plan_prompt_noninterference_attestation_hash",
            "decision_prompt_noninterference_attestation_hashes",
            "model_request_prompts",
            "model_request_prompt_hashes",
            "model_request_prompt_noninterference_attestation_hashes",
        },
    )
    values.update(
        {
            "telemetry": telemetry,
            "plan_prompt_hash": plan_hash,
            "decision_prompt_hashes": decision_hashes,
            "last_model_prompt_hash": request_hashes[-1] if request_hashes else None,
            "plan_prompt_noninterference_attestation_hash": (
                _prompt_noninterference_attestation_hash(plan_hash, scanner)
                if plan_hash is not None
                else None
            ),
            "decision_prompt_noninterference_attestation_hashes": tuple(
                _prompt_noninterference_attestation_hash(item, scanner) for item in decision_hashes
            ),
            "model_request_prompts": prompts,
            "model_request_prompt_hashes": request_hashes,
            "model_request_prompt_noninterference_attestation_hashes": tuple(
                _prompt_noninterference_attestation_hash(item, scanner) for item in request_hashes
            ),
        }
    )
    provisional = IterativeAgentFailureArtifact.model_construct(artifact_id="pending", **values)
    return IterativeAgentFailureArtifact(
        artifact_id=iterative_agent_failure_artifact_id(provisional),
        **values,
    )


def _completion_classifications(
    attempts: Sequence[CompactRequestAttempt],
    telemetry: Sequence[ModelCallTelemetry],
) -> tuple[CompletionUsabilityClassification, ...]:
    telemetry_by_index = {index: item for index, item in enumerate(telemetry)}
    grouped: dict[int, list[CompactRequestAttempt]] = defaultdict(list)
    for item in attempts:
        grouped[item.logical_request_index].append(item)
    output = []
    for logical_index, rows in sorted(grouped.items()):
        successful = next((item for item in reversed(rows) if item.compact_contract_valid), None)
        selected = successful or rows[-1]
        if selected.provider_request_index is None:
            output.append(
                classify_completion_usability(
                    request_index=logical_index,
                    telemetry=None,
                    typed_no_call=True,
                )
            )
            continue
        call = telemetry_by_index[selected.provider_request_index]
        repair_attempted = any(item.contract_repair for item in rows)
        output.append(
            classify_completion_usability(
                request_index=logical_index,
                telemetry=call,
                final_content_present=bool(call.response_content_length),
                decision_contract_valid=selected.compact_contract_valid,
                contract_repair_attempted=repair_attempted,
                contract_repair_succeeded=(
                    selected.compact_contract_valid and selected.contract_repair
                ),
            )
        )
    return tuple(output)


def _thinking_history(
    contract: ThinkingContinuityContract,
    telemetry: Sequence[ModelCallTelemetry],
) -> tuple[ThinkingHistoryAudit | None, tuple[str, ...]]:
    turns = []
    failures = []
    parent: str | None = None
    for index, item in enumerate(value for value in telemetry if value.http_success):
        try:
            turn = attest_thinking_turn(
                contract=contract,
                call_index=index,
                telemetry=item,
                parent_attestation_id=parent,
                provider_native_tool_call_observed=bool(
                    item.response_shape.get("provider_native_tool_call_observed", False)
                ),
            )
        except ValueError as exc:
            failures.append(
                "thinking_continuity:"
                + type(exc).__name__.casefold()
                + ":"
                + canonical_hash(str(exc), prefix="thinking_continuity_failure:").split(":", 1)[-1]
            )
            continue
        turns.append(turn)
        parent = turn.attestation_id
    if failures:
        return None, tuple(sorted(set(failures)))
    if not turns:
        return None, ()
    return audit_thinking_history(contract, tuple(turns)), ()


def _implementation_sources(
    preflight: ThinkingBudgetCalibrationPreflightReport,
    package_root: Path,
) -> tuple[ImplementationSourceFile, ...]:
    paths = tuple(
        sorted(
            {
                *(item.relative_path for item in preflight.implementation_source_files),
                EXECUTION_SOURCE_PATH,
            }
        )
    )
    return tuple(
        ImplementationSourceFile(
            relative_path=path,
            sha256=_sha256(package_root / path),
        )
        for path in paths
    )


def _build_online_source_replay(
    *,
    preflight: ThinkingBudgetCalibrationPreflightReport,
    preflight_dir: Path,
    package_root: Path,
) -> CalibrationOnlineSourceReplayAudit:
    entries: list[OnlineReplayEntry] = []

    def add(
        *,
        relative_path: str,
        source_kind: Literal[
            "v26_91_report",
            "v26_91_detail",
            "v26_91_predecessor_binding",
            "v26_91_implementation",
            "v26_92_execution_implementation",
        ],
        expected: str,
        path: Path,
    ) -> None:
        observed = _sha256(path)
        entries.append(
            OnlineReplayEntry(
                relative_path=relative_path,
                source_kind=source_kind,
                expected_sha256=expected,
                observed_sha256=observed,
                passed=observed == expected,
            )
        )

    report_path = preflight_dir / "report.json"
    add(
        relative_path=_relative(report_path, package_root),
        source_kind="v26_91_report",
        expected=EXPECTED_PREFLIGHT_REPORT_SHA256,
        path=report_path,
    )
    if len(preflight.detail_files) != 30:
        raise ValueError("authoritative v26.91 output denominator changed")
    for detail in preflight.detail_files:
        add(
            relative_path=_relative(preflight_dir / detail.relative_path, package_root),
            source_kind="v26_91_detail",
            expected=detail.sha256,
            path=preflight_dir / detail.relative_path,
        )

    predecessor = PredecessorReplayAudit.model_validate_json(
        (preflight_dir / "predecessor_replay_audit.json").read_text(encoding="utf-8")
    )
    if (
        predecessor.audit_id != preflight.predecessor_replay_audit_id
        or predecessor.replayed_file_count != 104
    ):
        raise ValueError("v26.91 predecessor replay denominator changed")
    for item in predecessor.entries:
        add(
            relative_path=item.relative_path,
            source_kind="v26_91_predecessor_binding",
            expected=item.expected_sha256,
            path=package_root / item.relative_path,
        )

    for item in preflight.implementation_source_files:
        add(
            relative_path=item.relative_path,
            source_kind="v26_91_implementation",
            expected=item.sha256,
            path=package_root / item.relative_path,
        )
    execution_path = package_root / EXECUTION_SOURCE_PATH
    execution_hash = _sha256(execution_path)
    add(
        relative_path=EXECUTION_SOURCE_PATH,
        source_kind="v26_92_execution_implementation",
        expected=execution_hash,
        path=execution_path,
    )
    ordered = tuple(sorted(entries, key=lambda item: (item.source_kind, item.relative_path)))
    values = {
        "entries": ordered,
        "implementation_binding_file_count": (len(preflight.implementation_source_files) + 1),
        "replayed_file_count": len(ordered),
        "replay_pass_count": sum(item.passed for item in ordered),
    }
    provisional = CalibrationOnlineSourceReplayAudit.model_construct(audit_id="pending", **values)
    return CalibrationOnlineSourceReplayAudit(
        audit_id=online_source_replay_audit_id(provisional),
        **values,
    )


def _validate_online_inputs(
    *,
    contract: ThinkingBudgetCalibrationContract,
    manifest: ThinkingBudgetCalibrationManifest,
    records: Sequence[OperationalTaskRecord],
    environments: Sequence[AgentToolEnvironmentManifest],
    replay_bindings: Sequence[VerifierV2TaskReplayBinding],
    prompt_contracts: Sequence[CompactPromptContract],
    stress_paths: Sequence[CalibrationStressPathAudit],
) -> None:
    record_by_id = {item.record_id: item for item in records}
    environment_by_id = {item.manifest_id: item for item in environments}
    binding_by_semantic_source = {item.semantic_source_id: item for item in replay_bindings}
    prompt_by_operational = {item.operational_task_package_id: item for item in prompt_contracts}
    stress_by_id = {item.audit_id: item for item in stress_paths}
    if not (
        len(record_by_id)
        == len(environment_by_id)
        == len(binding_by_semantic_source)
        == len(prompt_by_operational)
        == CALIBRATION_TASK_COUNT
    ):
        raise ValueError("online calibration task inputs are incomplete")
    if len(stress_by_id) != CALIBRATION_JOB_COUNT:
        raise ValueError("online calibration stress paths are incomplete")
    for job in manifest.jobs:
        record = record_by_id.get(job.operational_record_id)
        environment = environment_by_id.get(job.environment_manifest_id)
        stress = stress_by_id.get(job.stress_path_audit_id)
        prompt = prompt_by_operational.get(job.operational_task_package_id)
        binding = (
            binding_by_semantic_source.get(record.task_package.semantic_source.semantic_source_id)
            if record is not None
            else None
        )
        if any(item is None for item in (record, environment, stress, prompt, binding)):
            raise ValueError(f"online calibration Job input missing: {job.job_id}")
        assert record is not None
        assert environment is not None
        assert stress is not None
        assert prompt is not None
        assert binding is not None
        if (
            job.calibration_contract_id != contract.contract_id
            or record.task_package.package_id != job.operational_task_package_id
            or record.environment_manifest_id != environment.manifest_id
            or stress.operational_task_package_id != job.operational_task_package_id
            or stress.source_task_artifact_id != job.source_task_artifact_id
            or stress.mechanism_id != job.mechanism_id
            or stress.path_strategy_id != job.path_strategy_id
        ):
            raise ValueError(f"online calibration Job binding changed: {job.job_id}")
        if (
            prompt.environment_manifest_id != environment.manifest_id
            or prompt.operational_task_package_id != record.task_package.package_id
            or binding.environment_manifest_id != environment.manifest_id
            or binding.semantic_source_id != record.task_package.semantic_source.semantic_source_id
        ):
            raise ValueError(f"online calibration public binding changed: {job.job_id}")


def prepare_thinking_budget_calibration_execution(
    *,
    execution_run_id: str,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> _PreparedInputs:
    preflight = ThinkingBudgetCalibrationPreflightReport.model_validate_json(
        (preflight_dir / "report.json").read_text(encoding="utf-8")
    )
    contract = ThinkingBudgetCalibrationContract.model_validate_json(
        (preflight_dir / "calibration_contract.json").read_text(encoding="utf-8")
    )
    manifest = ThinkingBudgetCalibrationManifest.model_validate_json(
        (preflight_dir / "calibration_job_manifest.json").read_text(encoding="utf-8")
    )
    continuity_contract = ThinkingContinuityContract.model_validate_json(
        (preflight_dir / "thinking_continuity_contract.json").read_text(encoding="utf-8")
    )
    completion_contract = CompletionUsabilityContract.model_validate_json(
        (preflight_dir / "completion_usability_contract.json").read_text(encoding="utf-8")
    )
    if (
        preflight.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or contract.contract_id != EXPECTED_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_MANIFEST_ID
        or continuity_contract.contract_id != EXPECTED_CONTINUITY_CONTRACT_ID
        or completion_contract.contract_id != EXPECTED_COMPLETION_CONTRACT_ID
        or preflight.calibration_contract_id != contract.contract_id
        or preflight.calibration_manifest_id != manifest.manifest_id
        or contract.thinking_continuity_contract_id != continuity_contract.contract_id
        or contract.completion_usability_contract_id != completion_contract.contract_id
    ):
        raise ValueError("online execution did not receive authoritative v26.91 inputs")

    _, _, provider_budget_contract, _ = _load_predecessor(package_root)
    if provider_budget_contract.contract_id != EXPECTED_PROVIDER_BUDGET_CONTRACT_ID:
        raise ValueError("online calibration Provider budget Contract changed")
    profile_payload = json.loads(
        (package_root / "config/deepseek_v4_flash_agent_thinking_v1.json").read_text(
            encoding="utf-8"
        )
    )
    model_config = AgentModelConfig.model_validate(profile_payload["model"])
    thinking_binding = bind_prospective_thinking(model_config)
    if (
        model_config.public_manifest_hash != EXPECTED_MODEL_CONFIG_ID
        or thinking_binding.binding_id != EXPECTED_THINKING_BINDING_ID
        or contract.model_config_id != model_config.public_manifest_hash
        or contract.thinking_binding_id != thinking_binding.binding_id
    ):
        raise ValueError("online calibration thinking-enabled model binding changed")

    records = cast(
        tuple[OperationalTaskRecord, ...],
        _load_models(
            preflight_dir / "calibration_operational_task_records.json",
            OperationalTaskRecord,
        ),
    )
    environments = cast(
        tuple[AgentToolEnvironmentManifest, ...],
        _load_models(
            preflight_dir / "calibration_tool_environment_manifests.json",
            AgentToolEnvironmentManifest,
        ),
    )
    replay_bindings = cast(
        tuple[VerifierV2TaskReplayBinding, ...],
        _load_models(
            preflight_dir / "calibration_verifier_replay_bindings.json",
            VerifierV2TaskReplayBinding,
        ),
    )
    prompt_contracts = cast(
        tuple[CompactPromptContract, ...],
        _load_models(
            preflight_dir / "calibration_compact_prompt_contracts.json",
            CompactPromptContract,
        ),
    )
    stress_paths = cast(
        tuple[CalibrationStressPathAudit, ...],
        _load_models(
            preflight_dir / "calibration_stress_path_audits.json",
            CalibrationStressPathAudit,
        ),
    )
    _validate_online_inputs(
        contract=contract,
        manifest=manifest,
        records=records,
        environments=environments,
        replay_bindings=replay_bindings,
        prompt_contracts=prompt_contracts,
        stress_paths=stress_paths,
    )
    _, replay_contract = _load_and_replay_verifier_qualification(
        package_root
        / (
            "artifacts/vtdo_experiment/"
            "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
        ),
        package_root,
    )
    source_audit = _build_online_source_replay(
        preflight=preflight,
        preflight_dir=preflight_dir,
        package_root=package_root,
    )
    implementation_sources = _implementation_sources(preflight, package_root)
    binding_values = {
        "execution_run_id": execution_run_id,
        "online_source_replay_audit_id": source_audit.audit_id,
        "implementation_source_files": implementation_sources,
    }
    provisional_binding = CalibrationExecutionBinding.model_construct(
        binding_id="pending", **binding_values
    )
    execution_binding = CalibrationExecutionBinding(
        binding_id=calibration_execution_binding_id(provisional_binding),
        **binding_values,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    existing_binding_path = output_dir / "execution_binding.json"
    if existing_binding_path.exists():
        existing = CalibrationExecutionBinding.model_validate_json(
            existing_binding_path.read_text(encoding="utf-8")
        )
        if existing != execution_binding:
            raise ValueError("existing calibration execution binding changed")
    _write_json_atomic(
        output_dir / "online_source_replay_audit.json",
        source_audit.model_dump(mode="json"),
    )
    _write_json_atomic(
        existing_binding_path,
        execution_binding.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "frozen_calibration_contract.json",
        contract.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "frozen_calibration_job_manifest.json",
        manifest.model_dump(mode="json"),
    )
    return _PreparedInputs(
        preflight=preflight,
        contract=contract,
        manifest=manifest,
        continuity_contract=continuity_contract,
        provider_budget_contract=provider_budget_contract,
        agent_model_config=model_config,
        records=records,
        environments=environments,
        replay_bindings=replay_bindings,
        prompt_contracts=prompt_contracts,
        stress_paths=stress_paths,
        replay_contract=replay_contract,
        source_audit=source_audit,
        execution_binding=execution_binding,
    )


def _load_raw_execution(path: Path) -> CalibrationRawExecution:
    raw = path.read_bytes()
    payload = json.loads(raw)
    if raw != _canonical_bytes(payload):
        raise ValueError(f"calibration raw execution is not canonical JSON: {path}")
    return CalibrationRawExecution.model_validate(payload)


def _execute_and_persist_raw(
    *,
    job: ThinkingBudgetCalibrationJob,
    prepared: _PreparedInputs,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    prompt_contract: CompactPromptContract,
    stress_path: CalibrationStressPathAudit,
    client: Any | None,
    output_dir: Path,
) -> CalibrationRawExecution:
    raw_path = _raw_execution_path(output_dir, job)
    if raw_path.exists():
        artifact = _load_raw_execution(raw_path)
        if (
            artifact.execution_binding_id != prepared.execution_binding.binding_id
            or artifact.job != job
        ):
            raise ValueError("recoverable calibration raw execution crosses frozen identities")
        return artifact
    provider_directory = _raw_provider_path(output_dir, job, 0).parent
    if provider_directory.exists() and any(provider_directory.glob("call_*.json")):
        raise ValueError(
            "orphan calibration Provider calls exist without a raw execution; "
            "automatic model retry is forbidden"
        )
    if client is None:
        raise ValueError("pending calibration Job has no model client")
    if (
        record.record_id != job.operational_record_id
        or record.task_package.package_id != job.operational_task_package_id
        or environment.manifest_id != job.environment_manifest_id
        or prompt_contract.operational_task_package_id != job.operational_task_package_id
        or stress_path.audit_id != job.stress_path_audit_id
    ):
        raise ValueError("calibration execution inputs differ from the frozen Job")

    recording = _RawFirstJournalClient(
        client,
        execution_binding=prepared.execution_binding,
        job=job,
        output_dir=output_dir,
    )
    budget = BudgetClosedJsonClient(recording, prepared.provider_budget_contract)
    adapter = _CompactCalibrationClient(
        budget,
        task=record.task_package.task.public,
        environment=environment,
        runtime=_runtime(record, environment),
        prompt_contract=prompt_contract,
        stress_path=stress_path,
        path_strategy=job.path_strategy_id,
    )
    solve_result: IterativeAgentSolveResult | None = None
    failure_artifact: IterativeAgentFailureArtifact | None = None
    execution_error: str | None = None
    try:
        observed = IterativeAgentSolver(
            adapter,
            mode="autonomous_agent",
            maximum_total_tokens=prepared.provider_budget_contract.maximum_total_tokens,
            protocol_profile=IterativeAgentProtocolProfile(),
        ).solve_with_audit(
            record.task_package.task.public,
            _runtime(record, environment),
        )
        solve_result = _normalize_solve_result(observed, adapter)
    except LLMClientError as exc:
        execution_error = _safe_error(exc)
        if isinstance(exc.failure_artifact, IterativeAgentFailureArtifact):
            failure_artifact = _normalize_failure_artifact(exc.failure_artifact, adapter)
    except Exception as exc:
        execution_error = _safe_error(exc)

    provider_telemetry = tuple(recording.telemetry)
    provider_prompts = tuple(recording.prompts)
    if solve_result is not None:
        host_telemetry = solve_result.audit.telemetry
        host_prompts = solve_result.audit.model_request_prompts
        simulation_match = adapter.observations == solve_result.observations
    elif failure_artifact is not None:
        host_telemetry = failure_artifact.telemetry
        host_prompts = failure_artifact.model_request_prompts
        simulation_match = adapter.observations == failure_artifact.observations
    else:
        host_telemetry = _host_telemetry(provider_telemetry, provider_prompts)
        host_prompts = provider_prompts
        simulation_match = False
    if len(host_telemetry) != len(provider_telemetry):
        raise ValueError("calibration Host and Provider telemetry denominators differ")
    for raw, host in zip(provider_telemetry, host_telemetry, strict=True):
        raw_payload = raw.model_dump(mode="json")
        host_payload = host.model_dump(mode="json")
        raw_payload["request_hash"] = host_payload["request_hash"]
        raw_payload["json_contract_success"] = host_payload["json_contract_success"]
        raw_payload["error_type"] = host_payload["error_type"]
        raw_payload["error_message"] = host_payload["error_message"]
        raw_payload["contract_errors"] = host_payload["contract_errors"]
        host_shape = dict(host_payload["response_shape"])
        host_shape.pop("prompt_component_bytes", None)
        host_payload["response_shape"] = host_shape
        raw_payload["response_shape"] = dict(raw_payload["response_shape"])
        if raw_payload != host_payload:
            raise ValueError("calibration Host telemetry changed Provider fields")

    budget_audit = budget.audit()
    classifications = _completion_classifications(adapter.attempts, provider_telemetry)
    thinking_audit, thinking_failures = _thinking_history(
        prepared.continuity_contract,
        provider_telemetry,
    )
    no_http_success = not any(item.http_success for item in provider_telemetry)
    values = {
        "execution_binding_id": prepared.execution_binding.binding_id,
        "job": job,
        "operational_record_id": record.record_id,
        "environment_manifest_id": environment.manifest_id,
        "stress_path_audit_id": stress_path.audit_id,
        "provider_call_artifacts": tuple(recording.descriptors),
        "provider_call_ids": tuple(
            calibration_provider_call_id(job.job_id, index, item)
            for index, item in enumerate(provider_telemetry)
        ),
        "provider_telemetry": provider_telemetry,
        "provider_prompts": provider_prompts,
        "host_telemetry": tuple(host_telemetry),
        "host_prompts": tuple(host_prompts),
        "compact_attempts": tuple(adapter.attempts),
        "provider_budget_audit": budget_audit,
        "completion_classifications": classifications,
        "thinking_history_audit": thinking_audit,
        "thinking_continuity_failure_ids": thinking_failures,
        "thinking_history_not_applicable_no_http_success": (
            thinking_audit is None and not thinking_failures and no_http_success
        ),
        "solve_result": solve_result,
        "failure_artifact": failure_artifact,
        "execution_error": execution_error,
        "simulation_observation_match": simulation_match,
    }
    provisional = CalibrationRawExecution.model_construct(artifact_id="pending", **values)
    artifact = CalibrationRawExecution(
        artifact_id=calibration_raw_execution_id(provisional),
        **values,
    )
    _write_json_atomic(raw_path, artifact.model_dump(mode="json"))
    return artifact


def _observations(raw: CalibrationRawExecution) -> tuple[AgentToolObservation, ...]:
    if raw.solve_result is not None:
        return raw.solve_result.observations
    if raw.failure_artifact is not None:
        return raw.failure_artifact.observations
    return ()


def _actual_route(observations: Sequence[AgentToolObservation]) -> ActualRoute:
    successful_before_calculation: list[str] = []
    for item in observations:
        if item.call.tool_id == "calculator" and item.status == "succeeded":
            break
        if item.status == "succeeded":
            successful_before_calculation.append(item.call.tool_id)
    tools = set(successful_before_calculation)
    if "open_document" in tools:
        return "search_then_open"
    if "search_archive" in tools:
        return "search_then_structured"
    if "query_structured_fact" in tools:
        return "structured_direct"
    return "none"


def _repetition_counts(
    observations: Sequence[AgentToolObservation],
) -> tuple[int, int]:
    signatures = [
        canonical_hash(
            {
                "tool_id": item.call.tool_id,
                "arguments": item.call.arguments,
            },
            prefix="finance_v26_calibration_call_signature:",
        )
        for item in observations
    ]
    failed = [
        signature
        for signature, item in zip(signatures, observations, strict=True)
        if item.status == "failed"
    ]
    return (
        len(signatures) - len(set(signatures)),
        len(failed) - len(set(failed)),
    )


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
    completed_count = len(progress["completed_node_ids"])
    return (
        completed_count,
        node_count,
        not progress["remaining_node_ids"],
        bool(progress["terminal_node_completed"]),
        bool(progress["verification_after_terminal_completed"]),
    )


def _empty_mechanism(record: OperationalTaskRecord) -> MechanismEstimandOutcome:
    required = tuple(sorted(record.mechanism_contract.required_event_ids))
    return MechanismEstimandOutcome(
        mechanism_id=record.mechanism_id,
        estimand_id=record.mechanism_contract.estimand_id,
        evaluated=False,
        success=False,
        observed_event_ids=(),
        missing_event_ids=required,
    )


def _score_raw_execution(
    *,
    raw: CalibrationRawExecution,
    prepared: _PreparedInputs,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    output_dir: Path,
) -> CalibrationJobResult:
    observations = _observations(raw)
    replay: AuthorityPreservingReplayResult | None = None
    verification: AuthorityPreservingVerificationReport | None = None
    if raw.solve_result is not None:
        replay = replay_authority_preserving_observations(
            prepared.replay_contract,
            record,
            environment,
            raw.solve_result.observations,
        )
        verification = verify_authority_preserving_agent_result(
            prepared.replay_contract,
            record,
            environment,
            raw.solve_result,
        )
        mechanism = evaluate_mechanism_estimand(
            record,
            observations,
            stopped_by_model=raw.solve_result.audit.stopped_by_model,
        )
    elif raw.failure_artifact is not None:
        mechanism = failure_artifact_mechanism_estimand(record, raw.failure_artifact)
    else:
        mechanism = _empty_mechanism(record)
    repeated, repeated_failed = _repetition_counts(observations)
    completed_nodes, node_count, program_closed, terminal_completed, verified = (
        _progress_diagnostic(record, observations)
    )
    successful_telemetry = tuple(item for item in raw.provider_telemetry if item.http_success)
    fractions = tuple(
        item.reasoning_tokens / item.completion_tokens
        for item in successful_telemetry
        if item.reasoning_tokens is not None and item.completion_tokens not in (None, 0)
    )
    typed_no_call = raw.provider_budget_audit.no_call_terminal is not None
    completion_unusable = any(item.completion_unusable for item in raw.completion_classifications)
    transport_failure = any(not item.http_success for item in raw.provider_telemetry)
    exact_model = all(
        item.model_requested == "deepseek-v4-flash"
        and item.model_selected == "deepseek-v4-flash"
        and (
            item.response_model in {None, "deepseek-v4-flash"}
            if not item.http_success
            else item.response_model == "deepseek-v4-flash"
        )
        for item in raw.provider_telemetry
    )
    fallback_absent = not any(item.fallback_used for item in raw.provider_telemetry)
    budget_passed = raw.provider_budget_audit.status == "passed"
    continuity_passed = (
        raw.thinking_history_audit is not None
        or raw.thinking_history_not_applicable_no_http_success
    )
    instrument_failure = bool(
        raw.thinking_continuity_failure_ids
        or not exact_model
        or not fallback_absent
        or not budget_passed
        or (replay is not None and not replay.passed)
        or (raw.solve_result is None and raw.failure_artifact is None and not typed_no_call)
        or (
            (raw.solve_result is not None or raw.failure_artifact is not None)
            and not raw.simulation_observation_match
        )
    )
    independent_valid = bool(verification is not None and verification.valid)
    if instrument_failure:
        terminal: TerminalCategory = "instrument_failure"
    elif typed_no_call:
        terminal = "typed_budget_no_call"
    elif transport_failure and raw.solve_result is None:
        terminal = "provider_transport_failure"
    elif completion_unusable:
        terminal = "completion_unusable"
    elif independent_valid:
        terminal = "model_valid_trajectory"
    else:
        terminal = "model_invalid_trajectory"
    route = _actual_route(observations)
    total_tokens = sum(item.total_tokens or 0 for item in raw.provider_telemetry)
    usage_complete = all(
        item.total_tokens is not None for item in raw.provider_telemetry if item.http_success
    )
    estimated_cost = sum(
        (
            Decimal(str(item.estimated_cost))
            for item in raw.provider_telemetry
            if item.estimated_cost is not None
        ),
        Decimal("0"),
    )
    raw_path = _raw_execution_path(output_dir, raw.job)
    raw_descriptor = RawFileDescriptor(
        relative_path=_relative(raw_path, output_dir),
        sha256=_sha256(raw_path),
        byte_count=raw_path.stat().st_size,
    )
    failure_attribution = None
    if terminal != "model_valid_trajectory":
        failure_attribution = {
            "execution_error": raw.execution_error,
            "thinking_continuity_failure_ids": raw.thinking_continuity_failure_ids,
            "budget_contract_failure_ids": raw.provider_budget_audit.contract_failure_ids,
            "completion_outcomes": tuple(
                item.completion_outcome for item in raw.completion_classifications
            ),
            "verifier_earliest_failure_stage": (
                verification.earliest_failure_stage if verification is not None else None
            ),
        }
    values = {
        "execution_binding_id": prepared.execution_binding.binding_id,
        "job_id": raw.job.job_id,
        "source_task_artifact_id": raw.job.source_task_artifact_id,
        "mechanism_id": raw.job.mechanism_id,
        "requested_path_strategy_id": raw.job.path_strategy_id,
        "terminal_category": terminal,
        "provider_call_count": len(raw.provider_telemetry),
        "http_success_call_count": len(successful_telemetry),
        "reasoning_present_http_success_call_count": sum(
            item.reasoning_content_present for item in successful_telemetry
        ),
        "reasoning_content_length_total": sum(
            item.reasoning_content_length or 0 for item in successful_telemetry
        ),
        "reasoning_tokens_total": sum(item.reasoning_tokens or 0 for item in successful_telemetry),
        "completion_tokens_total": sum(
            item.completion_tokens or 0 for item in successful_telemetry
        ),
        "provider_total_tokens": total_tokens,
        "provider_usage_complete": usage_complete,
        "estimated_cost_usd": str(estimated_cost),
        "typed_no_call": typed_no_call,
        "completion_unusable": completion_unusable,
        "provider_transport_failure": transport_failure,
        "thinking_continuity_passed": continuity_passed,
        "exact_model_passed": exact_model,
        "fallback_absent": fallback_absent,
        "budget_contract_passed": budget_passed,
        "simulation_observation_match": raw.simulation_observation_match,
        "compact_logical_request_count": len(
            {item.logical_request_index for item in raw.compact_attempts}
        ),
        "contract_repair_request_count": sum(item.contract_repair for item in raw.compact_attempts),
        "completion_limit_hit_count": sum(
            item.finish_reason == "length" for item in raw.provider_telemetry
        ),
        "reasoning_token_fraction_mean": (sum(fractions) / len(fractions) if fractions else None),
        "reasoning_token_fraction_maximum": max(fractions) if fractions else None,
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
        "independent_validity": independent_valid,
        "actual_route": route,
        "requested_path_adhered": route == raw.job.path_strategy_id,
        "stress_schedule_exhausted": any(
            item.stress_schedule_exhausted for item in raw.compact_attempts
        ),
        "stress_request_kind_mismatch_count": sum(
            not item.request_kind_matches_registered for item in raw.compact_attempts
        ),
        "compiler_prefix_match_count": sum(
            item.compiler_unpadded_prefix_match and item.compiler_padded_prefix_match
            for item in raw.compact_attempts
        ),
        "replay_result": replay,
        "verification_report": verification,
        "mechanism_outcome": mechanism,
        "no_call_terminal": raw.provider_budget_audit.no_call_terminal,
        "raw_execution_artifact": raw_descriptor,
        "failure_attribution": failure_attribution,
    }
    provisional = CalibrationJobResult.model_construct(result_id="pending", **values)
    return CalibrationJobResult(
        result_id=calibration_job_result_id(provisional),
        **values,
    )


def _cell_summaries(
    results: Sequence[CalibrationJobResult],
    raw_by_job: Mapping[str, CalibrationRawExecution],
) -> tuple[CalibrationCellSummary, ...]:
    grouped: dict[tuple[str, PathStrategy], list[CalibrationJobResult]] = defaultdict(list)
    for item in results:
        grouped[(item.mechanism_id, item.requested_path_strategy_id)].append(item)
    output = []
    for (mechanism, path), rows in sorted(grouped.items()):
        fractions = tuple(
            telemetry.reasoning_tokens / telemetry.completion_tokens
            for row in rows
            for telemetry in raw_by_job[row.job_id].provider_telemetry
            if telemetry.http_success
            and telemetry.reasoning_tokens is not None
            and telemetry.completion_tokens not in (None, 0)
        )
        values = {
            "mechanism_id": mechanism,
            "path_strategy_id": path,
            "job_count": len(rows),
            "typed_no_call_count": sum(item.typed_no_call for item in rows),
            "completion_unusable_count": sum(item.completion_unusable for item in rows),
            "provider_transport_failure_count": sum(
                item.provider_transport_failure for item in rows
            ),
            "thinking_continuity_failure_count": sum(
                not item.thinking_continuity_passed for item in rows
            ),
            "request_count": sum(item.provider_call_count for item in rows),
            "failed_observation_count": sum(item.failed_observation_count for item in rows),
            "program_closed_count": sum(item.program_closed for item in rows),
            "mechanism_success_count": sum(item.mechanism_success for item in rows),
            "valid_trajectory_count": sum(item.independent_validity for item in rows),
            "requested_path_adherence_count": sum(item.requested_path_adhered for item in rows),
            "reasoning_token_fraction_mean": (
                sum(fractions) / len(fractions) if fractions else None
            ),
            "reasoning_token_fraction_minimum": min(fractions) if fractions else None,
            "reasoning_token_fraction_maximum": max(fractions) if fractions else None,
            "mechanism_floor_observed": not any(item.mechanism_success for item in rows),
            "mechanism_saturation_observed": all(item.mechanism_success for item in rows),
            "validity_floor_observed": not any(item.independent_validity for item in rows),
            "validity_saturation_observed": all(item.independent_validity for item in rows),
        }
        provisional = CalibrationCellSummary.model_construct(summary_id="pending", **values)
        output.append(
            CalibrationCellSummary(
                summary_id=calibration_cell_summary_id(provisional),
                **values,
            )
        )
    if len(output) != 12:
        raise ValueError("calibration cell summary denominator changed")
    return tuple(output)


def _raw_lineage_audit(
    *,
    prepared: _PreparedInputs,
    results: Sequence[CalibrationJobResult],
    raw_by_job: Mapping[str, CalibrationRawExecution],
    output_dir: Path,
) -> CalibrationRawLineageAudit:
    files: list[RawFileDescriptor] = []
    provider_ids: list[str] = []
    for result in results:
        raw = raw_by_job[result.job_id]
        raw_path = output_dir / result.raw_execution_artifact.relative_path
        if _sha256(raw_path) != result.raw_execution_artifact.sha256:
            raise ValueError("calibration raw execution changed before aggregation")
        files.append(result.raw_execution_artifact)
        provider_ids.extend(raw.provider_call_ids)
        for descriptor in raw.provider_call_artifacts:
            path = output_dir / descriptor.relative_path
            if _sha256(path) != descriptor.sha256 or path.stat().st_size != descriptor.byte_count:
                raise ValueError("calibration raw Provider Artifact changed")
            payload = json.loads(path.read_text(encoding="utf-8"))
            if _contains_private_reasoning_key(payload.get("response_payload")):
                raise ValueError("calibration raw lineage contains private reasoning")
            CalibrationRawProviderCall.model_validate(payload)
            files.append(descriptor)
    ordered_files = tuple(sorted(files, key=lambda item: item.relative_path))
    values = {
        "execution_binding_id": prepared.execution_binding.binding_id,
        "provider_call_count": len(provider_ids),
        "unique_provider_call_count": len(set(provider_ids)),
        "files": ordered_files,
        "exact_byte_replay_pass_count": len(ordered_files),
    }
    provisional = CalibrationRawLineageAudit.model_construct(audit_id="pending", **values)
    return CalibrationRawLineageAudit(
        audit_id=calibration_raw_lineage_audit_id(provisional),
        **values,
    )


def _make_report(
    *,
    prepared: _PreparedInputs,
    results: tuple[CalibrationJobResult, ...],
    raw_by_job: Mapping[str, CalibrationRawExecution],
    raw_lineage: CalibrationRawLineageAudit,
    discovered_models: tuple[str, ...],
) -> CalibrationExecutionReport:
    if len(results) != CALIBRATION_JOB_COUNT:
        raise ValueError("calibration report requires the exact frozen denominator")
    terminal_counts = dict(sorted(Counter(item.terminal_category for item in results).items()))
    no_call = tuple(item for item in results if item.typed_no_call)
    completion_unusable = tuple(item for item in results if item.completion_unusable)
    no_call_sources = {item.source_task_artifact_id for item in no_call}
    completion_sources = {item.source_task_artifact_id for item in completion_unusable}
    no_call_cp32 = _cp_upper(len(no_call), CALIBRATION_JOB_COUNT)
    completion_cp32 = _cp_upper(len(completion_unusable), CALIBRATION_JOB_COUNT)
    no_call_cp31 = _cp_upper(len(no_call_sources), CALIBRATION_TASK_COUNT)
    completion_cp31 = _cp_upper(len(completion_sources), CALIBRATION_TASK_COUNT)
    fractions = tuple(
        telemetry.reasoning_tokens / telemetry.completion_tokens
        for raw in raw_by_job.values()
        for telemetry in raw.provider_telemetry
        if telemetry.http_success
        and telemetry.reasoning_tokens is not None
        and telemetry.completion_tokens not in (None, 0)
    )
    completion_outcomes = Counter(
        classification.completion_outcome
        for raw in raw_by_job.values()
        for classification in raw.completion_classifications
    )
    logical_request_count = sum(item.compact_logical_request_count for item in results)
    contract_repair_request_count = sum(item.contract_repair_request_count for item in results)
    cells = _cell_summaries(results, raw_by_job)
    transport_count = sum(item.provider_transport_failure for item in results)
    continuity_count = sum(not item.thinking_continuity_passed for item in results)
    instrument_count = sum(item.terminal_category == "instrument_failure" for item in results)
    all_exact = all(item.exact_model_passed for item in results)
    all_fallback_absent = all(item.fallback_absent for item in results)
    all_budget = all(item.budget_contract_passed for item in results)
    no_call_gate = no_call_cp32 <= 0.10
    completion_gate = completion_cp32 <= 0.10
    thinking_pass = continuity_count == 0
    execution_integrity = bool(
        transport_count == 0
        and instrument_count == 0
        and all_exact
        and all_fallback_absent
        and all_budget
    )
    passed = no_call_gate and completion_gate and thinking_pass and execution_integrity
    if passed:
        next_stage = "thinking_role_protocol_freeze_only"
    elif instrument_count or transport_count or continuity_count:
        next_stage = "thinking_instrument_repair_or_recovery_only"
    elif no_call:
        next_stage = "thinking_budget_deviation_root_cause_audit_only"
    else:
        next_stage = "thinking_completion_root_cause_audit_only"
    estimated_cost = sum(
        (Decimal(item.estimated_cost_usd) for item in results),
        Decimal("0"),
    )
    values = {
        "execution_run_id": prepared.execution_binding.execution_run_id,
        "execution_binding_id": prepared.execution_binding.binding_id,
        "raw_lineage_audit_id": raw_lineage.audit_id,
        "discovered_models": discovered_models,
        "terminal_counts": terminal_counts,
        "provider_call_count": sum(item.provider_call_count for item in results),
        "http_success_call_count": sum(item.http_success_call_count for item in results),
        "reasoning_present_http_success_call_count": sum(
            item.reasoning_present_http_success_call_count for item in results
        ),
        "reasoning_content_length_total": sum(
            item.reasoning_content_length_total for item in results
        ),
        "reasoning_tokens_total": sum(item.reasoning_tokens_total for item in results),
        "completion_tokens_total": sum(item.completion_tokens_total for item in results),
        "provider_total_tokens": sum(item.provider_total_tokens for item in results),
        "provider_usage_complete": all(item.provider_usage_complete for item in results),
        "estimated_cost_usd": str(estimated_cost),
        "typed_no_call_job_count": len(no_call),
        "typed_no_call_cp95_upper_32": no_call_cp32,
        "typed_no_call_gate_passed": no_call_gate,
        "typed_no_call_unique_source_count": len(no_call_sources),
        "typed_no_call_cp95_upper_31": no_call_cp31,
        "typed_no_call_unique_source_sensitivity_passed": no_call_cp31 <= 0.10,
        "completion_unusable_job_count": len(completion_unusable),
        "completion_unusable_cp95_upper_32": completion_cp32,
        "completion_usability_gate_passed": completion_gate,
        "completion_unusable_unique_source_count": len(completion_sources),
        "completion_unusable_cp95_upper_31": completion_cp31,
        "completion_unique_source_sensitivity_passed": completion_cp31 <= 0.10,
        "provider_transport_failure_job_count": transport_count,
        "thinking_continuity_failure_job_count": continuity_count,
        "instrument_failure_job_count": instrument_count,
        "completion_limit_hit_count": sum(item.completion_limit_hit_count for item in results),
        "logical_request_count": logical_request_count,
        "contract_repair_request_count": contract_repair_request_count,
        "contract_repair_job_count": sum(
            item.contract_repair_request_count > 0 for item in results
        ),
        "contract_repair_request_rate": (
            contract_repair_request_count / logical_request_count if logical_request_count else 0.0
        ),
        "completion_outcome_counts": dict(sorted(completion_outcomes.items())),
        "failed_observation_count": sum(item.failed_observation_count for item in results),
        "repeated_call_signature_count": sum(
            item.repeated_call_signature_count for item in results
        ),
        "repeated_failed_call_signature_count": sum(
            item.repeated_failed_call_signature_count for item in results
        ),
        "requested_path_adherence_count": sum(item.requested_path_adhered for item in results),
        "program_closed_count": sum(item.program_closed for item in results),
        "mechanism_success_count": sum(item.mechanism_success for item in results),
        "independently_valid_trajectory_count": sum(item.independent_validity for item in results),
        "reasoning_token_fraction_mean": (sum(fractions) / len(fractions) if fractions else None),
        "reasoning_token_fraction_minimum": min(fractions) if fractions else None,
        "reasoning_token_fraction_maximum": max(fractions) if fractions else None,
        "cell_summaries": cells,
        "all_jobs_exact_model": all_exact,
        "all_jobs_fallback_absent": all_fallback_absent,
        "all_jobs_budget_contract_passed": all_budget,
        "empirical_budget_adequacy_passed": no_call_gate,
        "completion_usability_passed": completion_gate,
        "thinking_instrument_passed": thinking_pass,
        "execution_integrity_passed": execution_integrity,
        "status": "passed" if passed else "blocked",
        "next_permitted_stage": next_stage,
    }
    provisional = CalibrationExecutionReport.model_construct(report_id="pending", **values)
    return CalibrationExecutionReport(
        report_id=calibration_execution_report_id(provisional),
        **values,
    )


def _load_checkpoint(
    *,
    path: Path,
    prepared: _PreparedInputs,
    output_dir: Path,
) -> tuple[CalibrationJobResult, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        CalibrationJobResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in prepared.manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("calibration checkpoint contains duplicate Jobs")
    for item in rows:
        job = jobs.get(item.job_id)
        raw_path = output_dir / item.raw_execution_artifact.relative_path
        if (
            job is None
            or item.execution_binding_id != prepared.execution_binding.binding_id
            or item.source_task_artifact_id != job.source_task_artifact_id
            or _sha256(raw_path) != item.raw_execution_artifact.sha256
        ):
            raise ValueError("calibration checkpoint differs from frozen inputs")
    return rows


def _run_one_job(
    *,
    job: ThinkingBudgetCalibrationJob,
    prepared: _PreparedInputs,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    prompt_contract: CompactPromptContract,
    stress_path: CalibrationStressPathAudit,
    client: Any | None,
    output_dir: Path,
) -> CalibrationJobResult:
    raw = _execute_and_persist_raw(
        job=job,
        prepared=prepared,
        record=record,
        environment=environment,
        prompt_contract=prompt_contract,
        stress_path=stress_path,
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


def run_thinking_budget_calibration_execution(
    *,
    execution_run_id: str,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    workers: int,
    client_factory: Callable[[AgentModelConfig], Any] = (
        ThinkingRequiredOpenAICompatibleJsonClient
    ),
) -> CalibrationExecutionReport:
    prepared = prepare_thinking_budget_calibration_execution(
        execution_run_id=execution_run_id,
        preflight_dir=preflight_dir,
        output_dir=output_dir,
        package_root=package_root,
    )
    checkpoint_path = output_dir / "calibration_job_results.checkpoint.jsonl"
    existing = _load_checkpoint(
        path=checkpoint_path,
        prepared=prepared,
        output_dir=output_dir,
    )
    completed = {item.job_id: item for item in existing}
    pending = [item for item in prepared.manifest.jobs if item.job_id not in completed]
    prior_report_path = output_dir / "report.json"
    if pending and prior_report_path.exists():
        raise ValueError("completed calibration report exists while Jobs remain pending")
    if not pending and prior_report_path.exists():
        report = CalibrationExecutionReport.model_validate_json(
            prior_report_path.read_text(encoding="utf-8")
        )
        if report.execution_binding_id != prepared.execution_binding.binding_id:
            raise ValueError("completed calibration report crosses execution bindings")
        return report

    raw_recovery_jobs = [item for item in pending if _raw_execution_path(output_dir, item).exists()]
    model_pending_jobs = [
        item for item in pending if not _raw_execution_path(output_dir, item).exists()
    ]
    for job in model_pending_jobs:
        directory = _raw_provider_path(output_dir, job, 0).parent
        if directory.exists() and any(directory.glob("call_*.json")):
            raise ValueError(
                "orphan calibration Provider calls require a fresh recovery implementation"
            )

    client: Any | None = None
    if model_pending_jobs:
        client = client_factory(prepared.agent_model_config)
        discovered_models = tuple(client.discover_models())
        if "deepseek-v4-flash" not in discovered_models:
            raise ValueError("frozen DeepSeek V4-Flash identity is unavailable")
    else:
        observed_models = {
            item.model_selected
            for job in raw_recovery_jobs
            for item in _load_raw_execution(_raw_execution_path(output_dir, job)).provider_telemetry
            if item.model_selected
        }
        discovered_models = tuple(sorted(observed_models or {"deepseek-v4-flash"}))

    print(
        f"[v26.92] resuming {len(completed)}/{CALIBRATION_JOB_COUNT}; "
        f"raw-only recovery {len(raw_recovery_jobs)}; "
        f"executing {len(model_pending_jobs)} Jobs with {workers} workers",
        flush=True,
    )
    record_by_id = {item.record_id: item for item in prepared.records}
    environment_by_id = {item.manifest_id: item for item in prepared.environments}
    prompt_by_operational = {
        item.operational_task_package_id: item for item in prepared.prompt_contracts
    }
    stress_by_id = {item.audit_id: item for item in prepared.stress_paths}
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending) or 1))) as executor:
        future_map = {
            executor.submit(
                _run_one_job,
                job=job,
                prepared=prepared,
                record=record_by_id[job.operational_record_id],
                environment=environment_by_id[job.environment_manifest_id],
                prompt_contract=prompt_by_operational[job.operational_task_package_id],
                stress_path=stress_by_id[job.stress_path_audit_id],
                client=None if job in raw_recovery_jobs else client,
                output_dir=output_dir,
            ): job
            for job in pending
        }
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
                    "thinking calibration worker failed; raw-only recovery is required"
                ) from exc
            with lock:
                if result.job_id in completed:
                    raise ValueError("calibration Runner produced a duplicate Job result")
                completed[result.job_id] = result
                _append_jsonl(checkpoint_path, result.model_dump(mode="json"))
                print(
                    f"[v26.92] completed {len(completed)}/{CALIBRATION_JOB_COUNT}",
                    flush=True,
                )

    ordered = tuple(
        completed[item.job_id] for item in prepared.manifest.jobs if item.job_id in completed
    )
    if len(ordered) != CALIBRATION_JOB_COUNT:
        raise ValueError("calibration execution ended with an incomplete denominator")
    raw_by_job = {
        item.job_id: _load_raw_execution(
            _raw_execution_path(
                output_dir,
                next(job for job in prepared.manifest.jobs if job.job_id == item.job_id),
            )
        )
        for item in ordered
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
        raw_by_job=raw_by_job,
        raw_lineage=raw_lineage,
        discovered_models=discovered_models,
    )
    _write_json_atomic(
        output_dir / "calibration_job_results.json",
        [item.model_dump(mode="json") for item in ordered],
    )
    _write_json_atomic(
        output_dir / "provider_budget_audits.json",
        [raw_by_job[item.job_id].provider_budget_audit.model_dump(mode="json") for item in ordered],
    )
    _write_json_atomic(
        output_dir / "compact_request_attempts.json",
        [
            attempt.model_dump(mode="json")
            for item in ordered
            for attempt in raw_by_job[item.job_id].compact_attempts
        ],
    )
    _write_json_atomic(
        output_dir / "completion_usability_classifications.json",
        [
            classification.model_dump(mode="json")
            for item in ordered
            for classification in raw_by_job[item.job_id].completion_classifications
        ],
    )
    _write_json_atomic(
        output_dir / "thinking_history_audits.json",
        [
            cast(ThinkingHistoryAudit, raw_by_job[item.job_id].thinking_history_audit).model_dump(
                mode="json"
            )
            for item in ordered
            if raw_by_job[item.job_id].thinking_history_audit is not None
        ],
    )
    _write_json_atomic(
        output_dir / "thinking_continuity_failures.json",
        [
            {
                "job_id": item.job_id,
                "failure_ids": raw_by_job[item.job_id].thinking_continuity_failure_ids,
            }
            for item in ordered
            if raw_by_job[item.job_id].thinking_continuity_failure_ids
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
            cast(AuthorityPreservingVerificationReport, item.verification_report).model_dump(
                mode="json"
            )
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
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute the exact Finance v26.91 Thinking Budget Calibration Manifest"
    )
    parser.add_argument("--execution-run-id", required=True)
    parser.add_argument("--preflight-dir", type=Path, required=True)
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
        prepared = prepare_thinking_budget_calibration_execution(
            execution_run_id=args.execution_run_id,
            preflight_dir=args.preflight_dir,
            output_dir=args.output_dir,
            package_root=args.package_root,
        )
        print(
            json.dumps(
                {
                    "execution_binding_id": prepared.execution_binding.binding_id,
                    "online_source_replay_audit_id": prepared.source_audit.audit_id,
                    "expected_job_count": len(prepared.manifest.jobs),
                    "model_client_constructed": False,
                },
                sort_keys=True,
            )
        )
        return
    report = run_thinking_budget_calibration_execution(
        execution_run_id=args.execution_run_id,
        preflight_dir=args.preflight_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
