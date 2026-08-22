from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    ImplementationSourceFile,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_8k_binding_rematerialization import (  # noqa: E501
    EXPECTED_8K_MODEL_CONFIG_ID,
    EXPECTED_8K_THINKING_BINDING_ID,
    EXPECTED_BOUND_PROTOCOL_ID,
    EXPECTED_INITIAL_CANDIDATE_ID,
    PROFILE_PATH,
    Exact8KJob,
    Exact8KRematerializationReport,
    Exact8KSourceReplayAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501
    RawFileDescriptor,
    ThinkingRepairCellSummary,
    ThinkingRepairCompletedResult,
    ThinkingRepairLogicalRequest,
    _contains_private_reasoning_key,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.budget_closed import (
    ProviderTokenBudgetAudit,
    ProviderTokenBudgetCertificate,
)
from trusted_synthesis.runtime.agent.prospective_thinking_8k_client import (
    EXACT_8K_MODEL_ID,
    EXACT_8K_PROFILE_SHA256,
    Exact8KRequestBindingCertificate,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    CompletionFailureKind,
    CompletionProjection,
    CompletionRequestKind,
    ProspectiveThinkingFailureArtifact,
    serialize_validated_failure_artifact,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion_bound import (
    DynamicCompletionPrecallCertificate,
)
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolObservation

RUNNER_PREFLIGHT_RUN_ID: Final = (
    "finance_v26_100_thinking_8k_completion_calibration_runner_preflight_v1_20260822"
)
EXECUTION_RUN_ID: Final = "finance_v26_101_thinking_8k_completion_calibration_execution_v1_20260822"
EXECUTION_REPORT_RUN_ID: Final = (
    "finance_v26_101_thinking_8k_completion_calibration_execution_report_v1_20260822"
)
V26_99_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_99_thinking_8k_binding_rematerialization_v1_20260822"
)
V26_97_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822"
)
V26_94_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821"
)
V26_90_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821"
)
EXPECTED_V26_99_REPORT_ID: Final = (
    "finance_v26_exact_8k_rematerialization_report:"
    "fb21fa81d33db5e7b4622007598bcef27d226e9804385176eb12509ac5069b3f"
)
EXPECTED_V26_99_REPORT_SHA256: Final = (
    "aa96c001199c1f725bc9b0f8ab8a588aa207ddda0506d9d893bd6b7754829dc3"
)
EXPECTED_V26_99_CONTRACT_ID: Final = (
    "finance_v26_exact_8k_completion_contract:"
    "2f752e61533e3a358d7e9ab02c4cb825b9c32ee9340a1310e5f533b53656365d"
)
EXPECTED_V26_99_MANIFEST_ID: Final = (
    "finance_v26_exact_8k_manifest:e50b85b55d76fe3f9e74b24cfde98d40d2c4a1f1608a85fcead6eebe6bd1c118"
)
EXPECTED_V26_99_CROSS_BINDING_ID: Final = (
    "finance_v26_exact_8k_cross_artifact_binding:"
    "8be2fa5e586165f19a2b9f740bf3efac39e71bb1031ca732769631533ea40c3c"
)
CLIENT_SOURCE_PATH: Final = "src/trusted_synthesis/runtime/agent/prospective_thinking_8k_client.py"
CONTRACTS_SOURCE_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_8k_completion_calibration_contracts.py"
)
RUNNER_SOURCE_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_8k_completion_calibration_execution.py"
)
PREFLIGHT_SOURCE_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_8k_completion_calibration_execution_preflight.py"
)
IMPLEMENTATION_SOURCE_PATHS: Final = tuple(
    sorted(
        (
            CLIENT_SOURCE_PATH,
            CONTRACTS_SOURCE_PATH,
            RUNNER_SOURCE_PATH,
            PREFLIGHT_SOURCE_PATH,
        )
    )
)
ROOT_CAUSE_PROVIDER_ARTIFACT: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_95_thinking_completion_telemetry_repair_execution_v1_20260821/"
    "raw_provider_calls/7c26dccffd0d5fdd6f63/call_0006.json"
)

SOURCE_REPLAY_VERSION: Final = "finance_v26_exact_8k_runner_source_replay.v1"
INTERPRETATION_VERSION: Final = "finance_v26_exact_8k_outcome_interpretation.v1"
EXECUTION_CONTRACT_VERSION: Final = "finance_v26_exact_8k_execution_contract.v1"
PREFLIGHT_REPORT_VERSION: Final = "finance_v26_exact_8k_runner_preflight_report.v1"
PROVIDER_CALL_VERSION: Final = "finance_v26_exact_8k_provider_call.v1"
ATTEMPT_VERSION: Final = "finance_v26_exact_8k_request_attempt.v1"
RAW_EXECUTION_VERSION: Final = "finance_v26_exact_8k_raw_execution.v1"
RAW_LINEAGE_VERSION: Final = "finance_v26_exact_8k_raw_lineage.v1"
EXECUTION_REPORT_VERSION: Final = "finance_v26_exact_8k_execution_report.v1"

AttemptPhase = Literal["primary", "rescue"]
AttemptDisposition = Literal[
    "usable",
    "completion_failure",
    "provider_transport_failure",
    "typed_budget_no_call",
    "instrument_failure",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_99_transitive_source",
        "v26_99_output",
        "v26_100_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> ReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("v26.100 source replay changed")
        return self


class Exact8KRunnerSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_99_REPORT_ID
    entries: tuple[ReplayEntry, ...] = Field(min_length=770, max_length=770)
    predecessor_transitive_source_count: Literal[755] = 755
    predecessor_output_count: Literal[11] = 11
    implementation_source_count: Literal[4] = 4
    replayed_file_count: Literal[770] = 770
    replay_pass_count: Literal[770] = 770
    replay_before_profile_parse: Literal[True] = True
    replay_before_credential_lookup: Literal[True] = True
    replay_before_client_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_8k_runner_source_replay.v1"] = SOURCE_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> Exact8KRunnerSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))) or len(paths) != 770:
            raise ValueError("v26.100 source replay denominator is not canonical")
        if self.audit_id != exact_8k_runner_source_replay_id(self):
            raise ValueError("v26.100 source replay identity mismatch")
        return self


class Exact8KOutcomeInterpretationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_contract_id: str = EXPECTED_V26_99_CONTRACT_ID
    exact_job_denominator: Literal[32] = 32
    zero_failure_gate_threshold: float = 0.10
    zero_failure_cp95_upper_bound: float
    one_failure_cp95_upper_bound: float
    typed_no_call_gate_requires_zero_failures: Literal[True] = True
    completion_unusable_gate_requires_zero_failures: Literal[True] = True
    length_failure_transition: Literal["fresh_16k_completion_preflight_only"] = (
        "fresh_16k_completion_preflight_only"
    )
    nonlength_completion_failure_transition: Literal[
        "completion_contract_root_cause_audit_only"
    ] = "completion_contract_root_cause_audit_only"
    dynamic_budget_failure_transition: Literal[
        "thinking_8k_dynamic_budget_root_cause_audit_only"
    ] = "thinking_8k_dynamic_budget_root_cause_audit_only"
    telemetry_only_failure_transition: Literal[
        "thinking_response_telemetry_wrapper_repair_only"
    ] = "thinking_response_telemetry_wrapper_repair_only"
    other_instrument_failure_transition: Literal[
        "thinking_8k_execution_instrument_root_cause_audit_only"
    ] = "thinking_8k_execution_instrument_root_cause_audit_only"
    transport_failure_transition: Literal[
        "thinking_8k_provider_transport_root_cause_audit_only"
    ] = "thinking_8k_provider_transport_root_cause_audit_only"
    pass_transition: Literal["thinking_role_protocol_freeze_only"] = (
        "thinking_role_protocol_freeze_only"
    )
    automatic_16k_escalation_allowed: Literal[False] = False
    semantic_validity_can_rescue_completion_or_budget_gate: Literal[False] = False
    low_program_closure_stops_completion_tuning: Literal[True] = True
    fresh_role_population_required_after_pass: Literal[True] = True
    schema_version: Literal["finance_v26_exact_8k_outcome_interpretation.v1"] = (
        INTERPRETATION_VERSION
    )

    @model_validator(mode="after")
    def validate_contract(self) -> Exact8KOutcomeInterpretationContract:
        if self.zero_failure_gate_threshold != 0.10:
            raise ValueError("v26.100 zero-failure threshold changed")
        if not (
            self.zero_failure_cp95_upper_bound
            <= self.zero_failure_gate_threshold
            < self.one_failure_cp95_upper_bound
        ):
            raise ValueError("v26.100 interpretation no longer requires zero failures")
        if self.contract_id != exact_8k_outcome_interpretation_id(self):
            raise ValueError("v26.100 interpretation identity mismatch")
        return self


class Exact8KExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    runner_preflight_run_id: str = RUNNER_PREFLIGHT_RUN_ID
    execution_run_id: str = EXECUTION_RUN_ID
    execution_report_run_id: str = EXECUTION_REPORT_RUN_ID
    predecessor_report_id: str = EXPECTED_V26_99_REPORT_ID
    predecessor_contract_id: str = EXPECTED_V26_99_CONTRACT_ID
    predecessor_manifest_id: str = EXPECTED_V26_99_MANIFEST_ID
    predecessor_cross_binding_id: str = EXPECTED_V26_99_CROSS_BINDING_ID
    source_replay_audit_id: str = Field(min_length=1)
    outcome_interpretation_contract_id: str = Field(min_length=1)
    provider_budget_contract_id: str = Field(min_length=1)
    completion_bound_protocol_id: str = EXPECTED_BOUND_PROTOCOL_ID
    candidate_id: str = EXPECTED_INITIAL_CANDIDATE_ID
    model_config_id: str = EXPECTED_8K_MODEL_CONFIG_ID
    thinking_binding_id: str = EXPECTED_8K_THINKING_BINDING_ID
    profile_relative_path: str = PROFILE_PATH
    profile_sha256: str = EXACT_8K_PROFILE_SHA256
    exact_model_id: Literal["deepseek-v4-flash"] = EXACT_8K_MODEL_ID
    thinking_type: Literal["enabled"] = "enabled"
    job_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
    runner_implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=4,
        max_length=4,
    )
    completion_upper_bound_tokens: Literal[8192] = 8192
    rollout_upper_bound_tokens: Literal[160000] = 160000
    prompt_upper_bound_bytes: Literal[60000] = 60000
    rescue_prompt_upper_bound_bytes: Literal[6144] = 6144
    chat_envelope_tokens: Literal[256] = 256
    static_request_margin_tokens: Literal[64] = 64
    completion_rescue_reserve_tokens: Literal[8192] = 8192
    final_answer_reserve_tokens: Literal[8192] = 8192
    maximum_rescue_calls_per_job: Literal[1] = 1
    model_plan_calls_per_job: Literal[0] = 0
    model_discovery_calls_per_job: Literal[0] = 0
    transient_provider_retries_per_request: Literal[0] = 0
    automatic_16k_escalation_allowed: Literal[False] = False
    actual_request_kind_certificate_required: Literal[True] = True
    actual_primary_prompt_certificate_required: Literal[True] = True
    actual_rescue_prompt_certificate_required: Literal[True] = True
    actual_resource_certificate_required: Literal[True] = True
    actual_request_body_certificate_required: Literal[True] = True
    provider_invocation_before_all_certificates_allowed: Literal[False] = False
    raw_redacted_provider_artifact_persisted_before_projection: Literal[True] = True
    response_envelope_captured_before_content_parse: Literal[True] = True
    raw_only_recovery_required: Literal[True] = True
    orphan_provider_artifact_requires_fresh_recovery_contract: Literal[True] = True
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    raw_request_body_persisted: Literal[False] = False
    role_population_rows_eligible: Literal[False] = False
    execution_authorized: Literal[True] = True
    schema_version: Literal["finance_v26_exact_8k_execution_contract.v1"] = (
        EXECUTION_CONTRACT_VERSION
    )

    @model_validator(mode="after")
    def validate_contract(self) -> Exact8KExecutionContract:
        if self.job_ids != tuple(sorted(set(self.job_ids))) or len(self.job_ids) != 32:
            raise ValueError("v26.100 execution Job denominator changed")
        paths = tuple(item.relative_path for item in self.runner_implementation_source_files)
        if paths != IMPLEMENTATION_SOURCE_PATHS:
            raise ValueError("v26.100 execution source binding is incomplete")
        if (
            self.candidate_id != EXPECTED_INITIAL_CANDIDATE_ID
            or self.model_config_id != EXPECTED_8K_MODEL_CONFIG_ID
            or self.thinking_binding_id != EXPECTED_8K_THINKING_BINDING_ID
            or self.profile_sha256 != EXACT_8K_PROFILE_SHA256
        ):
            raise ValueError("v26.100 exact 8K execution binding changed")
        if self.contract_id != exact_8k_execution_contract_id(self):
            raise ValueError("v26.100 execution Contract identity mismatch")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class Exact8KRunnerPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUNNER_PREFLIGHT_RUN_ID
    execution_run_id: str = EXECUTION_RUN_ID
    predecessor_report_id: str = EXPECTED_V26_99_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    outcome_interpretation_contract_id: str = Field(min_length=1)
    provider_budget_contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    client_binding_audit_id: str = Field(min_length=1)
    runner_fixture_audit_id: str = Field(min_length=1)
    precall_recovery_audit_id: str = Field(min_length=1)
    destructive_preflight_audit_id: str = Field(min_length=1)
    source_replayed_file_count: Literal[770] = 770
    exact_job_count: Literal[32] = 32
    direct_fixture_job_count: Literal[32] = 32
    rescue_fixture_count: Literal[5] = 5
    off_compiler_fixture_count: Literal[1] = 1
    detail_files: tuple[DetailFile, ...] = Field(min_length=8, max_length=8)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=4,
        max_length=4,
    )
    formal_independent_rebuild_required: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    execution_runner_materialized: Literal[True] = True
    exact_8k_execution_authorized: Literal[True] = True
    fallback_16k_execution_authorized: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal["thinking_8k_completion_calibration_execution_only"] = (
        "thinking_8k_completion_calibration_execution_only"
    )
    schema_version: Literal["finance_v26_exact_8k_runner_preflight_report.v1"] = (
        PREFLIGHT_REPORT_VERSION
    )

    @model_validator(mode="after")
    def validate_report(self) -> Exact8KRunnerPreflightReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.100 report detail files are not canonical")
        source_paths = tuple(item.relative_path for item in self.implementation_source_files)
        if source_paths != IMPLEMENTATION_SOURCE_PATHS:
            raise ValueError("v26.100 report implementation binding changed")
        if self.report_id != exact_8k_runner_preflight_report_id(self):
            raise ValueError("v26.100 preflight report identity mismatch")
        return self


class Prepared8KRequest(FrozenModel):
    preparation_id: str = Field(min_length=1)
    request_index: int = Field(ge=0)
    phase: AttemptPhase
    request_kind: CompletionRequestKind
    primary_prompt: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    failure_type: CompletionFailureKind | None = None
    dynamic_certificate: DynamicCompletionPrecallCertificate | None = None
    request_binding_certificate: Exact8KRequestBindingCertificate
    provider_budget_certificate: ProviderTokenBudgetCertificate
    all_provider_certificates_complete: bool
    provider_invocation_authorized: bool
    provider_calls_for_request_before_preparation: Literal[0] = 0

    @model_validator(mode="after")
    def validate_preparation(self) -> Prepared8KRequest:
        request_hash = sha256_text(self.prompt)
        if (
            self.request_binding_certificate.prompt_sha256 != request_hash
            or self.provider_budget_certificate.request_hash != request_hash
        ):
            raise ValueError("v26.100 prepared request Prompt binding changed")
        if self.dynamic_certificate is not None and (
            self.dynamic_certificate.request_prompt_sha256 != request_hash
            or self.dynamic_certificate.phase != self.phase
            or self.dynamic_certificate.request_kind != self.request_kind
        ):
            raise ValueError("v26.100 dynamic certificate differs from prepared request")
        expected_complete = self.dynamic_certificate is not None
        if self.all_provider_certificates_complete != expected_complete:
            raise ValueError("v26.100 prepared certificate completeness changed")
        expected_authorized = bool(
            expected_complete and self.provider_budget_certificate.provider_call_permitted
        )
        if self.provider_invocation_authorized != expected_authorized:
            raise ValueError("v26.100 prepared Provider authorization changed")
        if self.phase == "rescue":
            if self.failure_type is None or len(self.prompt.encode("utf-8")) > 6144:
                raise ValueError("v26.100 prepared Rescue is not absolutely bounded")
        elif self.failure_type is not None or self.prompt != self.primary_prompt:
            raise ValueError("v26.100 Primary preparation carries Rescue state")
        if self.preparation_id != prepared_8k_request_id(self):
            raise ValueError("v26.100 prepared request identity mismatch")
        return self


class Exact8KRawProviderCall(FrozenModel):
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
    dynamic_certificate: DynamicCompletionPrecallCertificate
    request_binding_certificate: Exact8KRequestBindingCertificate
    provider_budget_certificate_id: str = Field(min_length=1)
    response_payload: dict[str, Any] | None = None
    provider_telemetry: ModelCallTelemetry
    failure_artifact: ProspectiveThinkingFailureArtifact | None = None
    all_certificates_constructed_before_provider_call: Literal[True] = True
    captured_before_completion_projection: Literal[True] = True
    request_max_tokens: Literal[8192] = 8192
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    raw_request_body_persisted: Literal[False] = False
    schema_version: Literal["finance_v26_exact_8k_provider_call.v1"] = PROVIDER_CALL_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> Exact8KRawProviderCall:
        if self.prompt_sha256 != sha256_text(self.prompt):
            raise ValueError("v26.100 raw Provider Prompt hash changed")
        if (
            self.provider_telemetry.request_hash != self.prompt_sha256
            or self.dynamic_certificate.request_prompt_sha256 != self.prompt_sha256
            or self.request_binding_certificate.prompt_sha256 != self.prompt_sha256
            or self.request_binding_certificate.request_max_tokens != 8192
        ):
            raise ValueError("v26.100 raw Provider certificate binding changed")
        if self.failure_artifact is not None:
            if self.failure_artifact.request_hash != self.prompt_sha256:
                raise ValueError("v26.100 failure Artifact Prompt hash changed")
            serialize_validated_failure_artifact(self.failure_artifact)
        if _contains_private_reasoning_key(self.response_payload):
            raise ValueError("v26.100 public response payload contains private reasoning")
        if self.provider_call_id != exact_8k_provider_call_id(
            self.job_id,
            self.call_index,
            self.provider_telemetry,
            self.request_binding_certificate.certificate_id,
        ):
            raise ValueError("v26.100 Provider call identity mismatch")
        if self.artifact_id != exact_8k_raw_provider_call_id(self):
            raise ValueError("v26.100 raw Provider Artifact identity mismatch")
        return self


class Exact8KRequestAttempt(FrozenModel):
    attempt_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    provider_call_index: int | None = Field(default=None, ge=0)
    phase: AttemptPhase
    request_kind: CompletionRequestKind
    prompt_sha256: str = Field(min_length=64, max_length=64)
    prompt_utf8_bytes: int = Field(gt=0)
    dynamic_certificate: DynamicCompletionPrecallCertificate | None = None
    request_binding_certificate: Exact8KRequestBindingCertificate | None = None
    provider_budget_certificate_id: str | None = None
    precall_certificates_complete: bool
    registered_request_present: bool
    registered_request_kind_match: bool
    registered_primary_prompt_match: bool
    rescue_prompt_within_absolute_ceiling: bool | None = None
    provider_call_made: bool
    response_payload_present: bool
    completion_projection: CompletionProjection | None = None
    failure_artifact: ProspectiveThinkingFailureArtifact | None = None
    disposition: AttemptDisposition
    error: str | None = None
    relative_rescue_reduction_gate_used: Literal[False] = False
    previous_final_content_reused: Literal[False] = False
    private_reasoning_reused: Literal[False] = False
    host_action_inserted: Literal[False] = False
    schema_version: Literal["finance_v26_exact_8k_request_attempt.v1"] = ATTEMPT_VERSION

    @model_validator(mode="after")
    def validate_attempt(self) -> Exact8KRequestAttempt:
        if self.provider_call_made != (self.provider_call_index is not None):
            raise ValueError("v26.100 Provider attempt index accounting changed")
        certificates = (
            self.dynamic_certificate,
            self.request_binding_certificate,
            self.provider_budget_certificate_id,
        )
        if self.precall_certificates_complete != all(item is not None for item in certificates):
            raise ValueError("v26.100 pre-call certificate denominator changed")
        if self.provider_call_made and not self.precall_certificates_complete:
            raise ValueError("v26.100 Provider call preceded its certificates")
        if (self.completion_projection is not None) != (self.disposition == "usable"):
            raise ValueError("v26.100 usable attempt projection accounting changed")
        if self.disposition == "completion_failure" and self.failure_artifact is None:
            raise ValueError("v26.100 Completion failure lacks a typed Artifact")
        if self.phase == "rescue":
            if (
                self.rescue_prompt_within_absolute_ceiling is not True
                or self.prompt_utf8_bytes > 6144
            ):
                raise ValueError("v26.100 Rescue Prompt exceeds its absolute ceiling")
        elif self.rescue_prompt_within_absolute_ceiling is not None:
            raise ValueError("v26.100 Primary attempt carries Rescue accounting")
        if self.request_binding_certificate is not None and (
            self.request_binding_certificate.prompt_sha256 != self.prompt_sha256
            or self.request_binding_certificate.request_max_tokens != 8192
        ):
            raise ValueError("v26.100 request-body certificate differs from the attempt")
        if self.attempt_id != exact_8k_request_attempt_id(self):
            raise ValueError("v26.100 request attempt identity mismatch")
        return self


class Exact8KRawExecution(FrozenModel):
    artifact_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    job: Exact8KJob
    operational_record_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    path_audit_id: str = Field(min_length=1)
    source_registered_path_audit_id: str = Field(min_length=1)
    provider_call_artifacts: tuple[RawFileDescriptor, ...]
    provider_call_ids: tuple[str, ...]
    provider_telemetry: tuple[ModelCallTelemetry, ...]
    provider_prompts: tuple[str, ...]
    request_attempts: tuple[Exact8KRequestAttempt, ...] = Field(min_length=1)
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
    rescue_attempt_count: int = Field(ge=0, le=1)
    rescue_provider_call_count: int = Field(ge=0, le=1)
    model_plan_call_count: Literal[0] = 0
    model_discovery_call_count: Literal[0] = 0
    captured_before_verifier_scoring: Literal[True] = True
    private_reasoning_content_persisted: Literal[False] = False
    schema_version: Literal["finance_v26_exact_8k_raw_execution.v1"] = RAW_EXECUTION_VERSION

    @property
    def rescue_call_count(self) -> int:
        return self.rescue_provider_call_count

    @model_validator(mode="after")
    def validate_artifact(self) -> Exact8KRawExecution:
        denominators = (
            len(self.provider_call_artifacts),
            len(self.provider_call_ids),
            len(self.provider_telemetry),
            len(self.provider_prompts),
        )
        if len(set(denominators)) != 1:
            raise ValueError("v26.100 Provider call denominators differ")
        if self.rescue_attempt_count != sum(
            item.phase == "rescue" for item in self.request_attempts
        ):
            raise ValueError("v26.100 Rescue attempt denominator changed")
        if self.rescue_provider_call_count != sum(
            item.phase == "rescue" and item.provider_call_made for item in self.request_attempts
        ):
            raise ValueError("v26.100 Rescue Provider-call denominator changed")
        if self.rescue_attempt_count > self.job.maximum_rescue_calls:
            raise ValueError("v26.100 Job exceeded its Rescue allowance")
        if (self.completed_result is not None) != (self.terminal_disposition == "completed"):
            raise ValueError("v26.100 completed-result disposition changed")
        if any(
            item.provider_call_made and not item.precall_certificates_complete
            for item in self.request_attempts
        ):
            raise ValueError("v26.100 Raw Execution contains an uncertified Provider call")
        if self.artifact_id != exact_8k_raw_execution_id(self):
            raise ValueError("v26.100 Raw Execution identity mismatch")
        return self


class Exact8KRawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    expected_job_count: Literal[32] = 32
    raw_execution_count: Literal[32] = 32
    provider_call_count: int = Field(ge=0)
    unique_provider_call_count: int = Field(ge=0)
    files: tuple[RawFileDescriptor, ...] = Field(min_length=32)
    private_reasoning_payload_count: Literal[0] = 0
    exact_byte_replay_pass_count: int = Field(ge=32)
    all_provider_calls_dynamically_precertified: Literal[True] = True
    all_provider_calls_exact_8k_request_bound: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_8k_raw_lineage.v1"] = RAW_LINEAGE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> Exact8KRawLineageAudit:
        paths = tuple(item.relative_path for item in self.files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.101 Raw Lineage paths are not canonical")
        if self.unique_provider_call_count != self.provider_call_count:
            raise ValueError("v26.101 Provider identities are not unique")
        if self.exact_byte_replay_pass_count != len(self.files):
            raise ValueError("v26.101 Raw Lineage replay is incomplete")
        if self.audit_id != exact_8k_raw_lineage_audit_id(self):
            raise ValueError("v26.101 Raw Lineage identity mismatch")
        return self


class Exact8KExecutionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = EXECUTION_REPORT_RUN_ID
    execution_run_id: str = EXECUTION_RUN_ID
    execution_contract_id: str = Field(min_length=1)
    preflight_report_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_99_REPORT_ID
    predecessor_manifest_id: str = EXPECTED_V26_99_MANIFEST_ID
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
    rescue_provider_call_count: int = Field(ge=0)
    completion_failure_counts: dict[str, int]
    typed_no_call_job_count: int = Field(ge=0)
    typed_no_call_cp95_upper_32: float = Field(ge=0, le=1)
    typed_no_call_gate_passed: bool
    completion_unusable_job_count: int = Field(ge=0)
    completion_unusable_cp95_upper_32: float = Field(ge=0, le=1)
    completion_usability_gate_passed: bool
    provider_transport_failure_job_count: int = Field(ge=0)
    instrument_failure_job_count: int = Field(ge=0)
    telemetry_only_failure_job_count: int = Field(ge=0)
    program_closed_count: int = Field(ge=0)
    mechanism_success_count: int = Field(ge=0)
    independently_valid_trajectory_count: int = Field(ge=0)
    requested_path_adherence_count: int = Field(ge=0)
    cell_summaries: tuple[ThinkingRepairCellSummary, ...] = Field(min_length=12, max_length=12)
    exact_8k_request_binding_passed: bool
    dynamic_precall_binding_passed: bool
    empirical_budget_adequacy_passed: bool
    completion_usability_passed: bool
    response_telemetry_instrument_passed: bool
    execution_integrity_passed: bool
    behavior_interpretation: Literal[
        "instrument_or_transport_failed",
        "completion_channel_failed",
        "completion_channel_passed_behavior_floor",
        "completion_channel_passed_behavior_nonfloor",
    ]
    status: Literal["passed", "blocked"]
    next_permitted_stage: str = Field(min_length=1)
    calibration_only: Literal[True] = True
    capability_denominator_eligible: Literal[False] = False
    reachability_denominator_eligible: Literal[False] = False
    state_mapping_eligible: Literal[False] = False
    release_eligible: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_8k_execution_report.v1"] = EXECUTION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> Exact8KExecutionReport:
        if sum(self.terminal_counts.values()) != 32:
            raise ValueError("v26.101 terminal denominator changed")
        if self.reasoning_tokens_total > self.completion_tokens_total:
            raise ValueError("v26.101 reasoning Usage exceeds Completion Usage")
        if self.report_id != exact_8k_execution_report_id(self):
            raise ValueError("v26.101 execution report identity mismatch")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def exact_8k_runner_source_replay_id(value: Exact8KRunnerSourceReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_runner_source_replay:")


def exact_8k_outcome_interpretation_id(
    value: Exact8KOutcomeInterpretationContract,
) -> str:
    return _identity(value, "contract_id", "finance_v26_exact_8k_outcome_interpretation:")


def exact_8k_execution_contract_id(value: Exact8KExecutionContract) -> str:
    return _identity(value, "contract_id", "finance_v26_exact_8k_execution_contract:")


def exact_8k_runner_preflight_report_id(value: Exact8KRunnerPreflightReport) -> str:
    return _identity(value, "report_id", "finance_v26_exact_8k_runner_preflight_report:")


def prepared_8k_request_id(value: Prepared8KRequest) -> str:
    return _identity(value, "preparation_id", "finance_v26_exact_8k_prepared_request:")


def exact_8k_provider_call_id(
    job_id: str,
    call_index: int,
    telemetry: ModelCallTelemetry,
    request_certificate_id: str,
) -> str:
    return canonical_hash(
        {
            "job_id": job_id,
            "call_index": call_index,
            "request_hash": telemetry.request_hash,
            "request_certificate_id": request_certificate_id,
            "model_requested": telemetry.model_requested,
            "model_selected": telemetry.model_selected,
            "response_model": telemetry.response_model,
            "response_hash": telemetry.response_hash,
            "finish_reason": telemetry.finish_reason,
            "http_status": telemetry.http_status,
        },
        prefix="finance_v26_exact_8k_provider_call:",
    )


def exact_8k_raw_provider_call_id(value: Exact8KRawProviderCall) -> str:
    return _identity(value, "artifact_id", "finance_v26_exact_8k_provider_artifact:")


def exact_8k_request_attempt_id(value: Exact8KRequestAttempt) -> str:
    return _identity(value, "attempt_id", "finance_v26_exact_8k_request_attempt:")


def exact_8k_raw_execution_id(value: Exact8KRawExecution) -> str:
    return _identity(value, "artifact_id", "finance_v26_exact_8k_raw_execution:")


def exact_8k_raw_lineage_audit_id(value: Exact8KRawLineageAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_raw_lineage:")


def exact_8k_execution_report_id(value: Exact8KExecutionReport) -> str:
    return _identity(value, "report_id", "finance_v26_exact_8k_execution_report:")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_bytes(value)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError(f"immutable v26.100/v26.101 output differs: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(raw)
    temporary.replace(path)


def load_canonical_json(path: Path) -> Any:
    raw = path.read_bytes()
    payload = json.loads(raw)
    if raw != canonical_bytes(payload):
        raise ValueError(f"noncanonical immutable JSON: {path}")
    return payload


def build_runner_source_replay(package_root: Path) -> Exact8KRunnerSourceReplayAudit:
    predecessor_dir = package_root / V26_99_DIR
    source = Exact8KSourceReplayAudit.model_validate(
        load_canonical_json(predecessor_dir / "source_replay_audit.json")
    )
    report_path = predecessor_dir / "report.json"
    report = Exact8KRematerializationReport.model_validate(load_canonical_json(report_path))
    if (
        report.report_id != EXPECTED_V26_99_REPORT_ID
        or sha256(report_path) != EXPECTED_V26_99_REPORT_SHA256
        or source.audit_id != report.source_replay_audit_id
        or source.replayed_file_count != 755
    ):
        raise ValueError("v26.100 predecessor report or source replay changed")

    entries: dict[str, ReplayEntry] = {}

    def add(relative_path: str, expected: str, source_kind: Any) -> None:
        path = package_root / relative_path
        observed = sha256(path)
        entry = ReplayEntry(
            relative_path=relative_path,
            source_kind=source_kind,
            expected_sha256=expected,
            observed_sha256=observed,
            byte_count=path.stat().st_size,
            passed=observed == expected,
        )
        previous = entries.get(relative_path)
        if previous is not None and previous != entry:
            raise ValueError(f"conflicting v26.100 replay binding: {relative_path}")
        entries[relative_path] = entry

    for item in source.entries:
        add(item.relative_path, item.expected_sha256, "v26_99_transitive_source")
    for detail in report.detail_files:
        add(
            f"{V26_99_DIR}/{detail.relative_path}",
            detail.sha256,
            "v26_99_output",
        )
    add(f"{V26_99_DIR}/report.json", EXPECTED_V26_99_REPORT_SHA256, "v26_99_output")
    for relative_path in IMPLEMENTATION_SOURCE_PATHS:
        add(relative_path, sha256(package_root / relative_path), "v26_100_implementation")

    ordered = tuple(entries[key] for key in sorted(entries))
    counts = CounterLike(item.source_kind for item in ordered)
    if counts != {
        "v26_99_transitive_source": 755,
        "v26_99_output": 11,
        "v26_100_implementation": 4,
    }:
        raise ValueError(f"v26.100 source replay classes changed: {counts}")
    values = {"entries": ordered}
    provisional = Exact8KRunnerSourceReplayAudit.model_construct(audit_id="pending", **values)
    return Exact8KRunnerSourceReplayAudit(
        audit_id=exact_8k_runner_source_replay_id(provisional),
        **values,
    )


def validate_runner_source_replay(
    audit: Exact8KRunnerSourceReplayAudit,
    package_root: Path,
) -> None:
    for entry in audit.entries:
        path = package_root / entry.relative_path
        if sha256(path) != entry.expected_sha256 or path.stat().st_size != entry.byte_count:
            raise ValueError(f"v26.100 online source replay changed: {entry.relative_path}")


def CounterLike(values: Any) -> dict[str, int]:
    output: dict[str, int] = {}
    for value in values:
        key = str(value)
        output[key] = output.get(key, 0) + 1
    return output
