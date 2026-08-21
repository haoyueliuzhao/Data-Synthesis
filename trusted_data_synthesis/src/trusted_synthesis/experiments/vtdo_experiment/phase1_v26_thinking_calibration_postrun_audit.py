from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal
from math import comb
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_requalification import (  # noqa: E501
    ProviderTokenBudgetAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    ImplementationSourceFile,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_budget_calibration_execution import (  # noqa: E501
    CalibrationCellSummary,
    CalibrationExecutionBinding,
    CalibrationExecutionReport,
    CalibrationJobResult,
    CalibrationRawExecution,
    CalibrationRawLineageAudit,
    CalibrationRawProviderCall,
    CompactRequestAttempt,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.thinking_history import (
    CompletionUsabilityClassification,
    ThinkingHistoryAudit,
)

EXPECTED_EXECUTION_REPORT_ID = (
    "finance_v26_thinking_budget_calibration_execution:"
    "f3bd9954b1c1f8e465bcca968ef5165d037a7da52b0c0f54ec87e1b9a34aec9b"
)
EXPECTED_EXECUTION_REPORT_SHA256 = (
    "320eac44e1b992f9f6e481408e85b91cd9a28cb390177939529284853851bf93"
)
EXPECTED_EXECUTION_BINDING_ID = (
    "finance_v26_thinking_calibration_execution_binding:"
    "bd454756a3be0e7ee578587c6ee407762c9522c27a017780429b04af7ce9e157"
)
EXPECTED_RAW_LINEAGE_ID = (
    "finance_v26_thinking_calibration_raw_lineage:"
    "790b22f989e99875a6044798ef5f412f9106109b88140bc5f290910f6a5b9f73"
)
EXPECTED_JOB_COUNT: Literal[32] = 32
EXPECTED_SOURCE_TASK_COUNT: Literal[31] = 31
EXPECTED_PROVIDER_CALL_COUNT: Literal[318] = 318
EXPECTED_LOGICAL_REQUEST_COUNT: Literal[199] = 199
EXPECTED_PROVIDER_TOTAL_TOKENS: Literal[1294797] = 1_294_797
EXPECTED_ESTIMATED_COST_USD = "0.24562028400000002152"
EXPECTED_COMPLETION_UNUSABLE_COUNT: Literal[30] = 30
EXPECTED_COMPLETION_UNUSABLE_SOURCE_COUNT: Literal[29] = 29
EXPECTED_MODEL_TELEMETRY_GAP_COUNT: Literal[79] = 79
EXPECTED_KNOWN_RESPONSE_MODEL_COUNT: Literal[239] = 239
EXPECTED_REASONING_EXHAUSTED_COUNT: Literal[74] = 74
EXPECTED_JSON_DECODE_ERROR_COUNT: Literal[5] = 5
EXPECTED_LENGTH_RESPONSE_COUNT: Literal[78] = 78
EXPECTED_REPAIR_REQUEST_COUNT: Literal[119] = 119
EXPECTED_REPAIR_SUCCESS_COUNT: Literal[89] = 89
EXPECTED_RAW_LINEAGE_FILE_COUNT: Literal[350] = 350
EXPECTED_SOURCE_REPLAY_FILE_COUNT: Literal[393] = 393

EXECUTION_DIR = (
    "artifacts/vtdo_experiment/finance_v26_92_thinking_budget_calibration_execution_v1_20260821"
)
AUDIT_SOURCE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_calibration_postrun_audit.py"
)

TOP_LEVEL_SHA256 = {
    "calibration_job_results.checkpoint.jsonl": (
        "ecbe98d0734ff5bba057acca49e6c99e0b40a29c38fa2520f0ef5c3829bd5326"
    ),
    "calibration_job_results.json": (
        "d97eac0a53c352e952b2ed77f3781e611a090ab59808ee56890b2afa3fb8ef2c"
    ),
    "cell_summaries.json": ("a747af54c6dde5621fab4e00b5ee5d302c73f0a1dd69904ab3dea8bb2b95df9f"),
    "compact_request_attempts.json": (
        "54e171e03b982cc4069ab297e9f50a48a49ec7df8a33988d0de7f60b04d66145"
    ),
    "completion_usability_classifications.json": (
        "48fef219ecb1405ae8f0eede85fa5aa360621a8fdac54add4c3c240bd2be6799"
    ),
    "execution_binding.json": ("09285df9e2e8b4dfca81e4dbe72371b06d5a688274924a36103667b624616242"),
    "frozen_calibration_contract.json": (
        "26c48daaadf8882dc704bc7281f08994973c3e55b655bf192d773991c0af4d6c"
    ),
    "frozen_calibration_job_manifest.json": (
        "be222341a12217f0b3d574e392bb3fefb5800fdde90b11e3319edabe2a73509c"
    ),
    "mechanism_diagnostics.json": (
        "9b0367c6cc9460dac12e1338c74d711537877e5d5bd818cb8debca54be9bca98"
    ),
    "online_replay_results.json": (
        "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
    ),
    "online_source_replay_audit.json": (
        "e3785344c96495ff49ab80d52be3d11c80d2f59af331a93f9aa44bd3b2cceb97"
    ),
    "provider_budget_audits.json": (
        "c067896433631ed08304261e2353256ff8671268908514889f56fc871dfe8457"
    ),
    "raw_lineage_audit.json": ("93e5a915fffed5413b47b91d313b673962856a8da2c1bfa8ff173d43af19d0dc"),
    "report.json": EXPECTED_EXECUTION_REPORT_SHA256,
    "thinking_continuity_failures.json": (
        "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
    ),
    "thinking_history_audits.json": (
        "9bdb07fed7c771926fb446585f162457e4f454cf01ea3138177617415cfd3829"
    ),
    "verification_reports.json": (
        "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
    ),
}

V26_93_SOURCE_VERSION = "finance_v26_thinking_postrun_source_replay.v1"
V26_93_PERSISTENCE_VERSION = "finance_v26_thinking_postrun_persistence.v1"
V26_93_MODEL_GAP_VERSION = "finance_v26_thinking_response_model_gap.v1"
V26_93_COMPLETION_VERSION = "finance_v26_thinking_completion_root_cause.v1"
V26_93_REPAIR_CONTRACT_VERSION = "finance_v26_thinking_telemetry_repair_contract.v1"
V26_93_REDACTED_ENVELOPE_VERSION = "finance_v26_redacted_provider_envelope.v1"
V26_93_REPAIR_FIXTURE_VERSION = "finance_v26_thinking_telemetry_repair_fixture.v1"
V26_93_REPORT_VERSION = "finance_v26_thinking_postrun_audit_report.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "execution_top_level",
        "execution_raw_lineage",
        "execution_implementation",
        "postrun_audit_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> SourceReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("thinking post-run source bytes changed")
        return self


class ThinkingPostrunSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    execution_binding_id: str = EXPECTED_EXECUTION_BINDING_ID
    entries: tuple[SourceReplayEntry, ...] = Field(
        min_length=EXPECTED_SOURCE_REPLAY_FILE_COUNT,
        max_length=EXPECTED_SOURCE_REPLAY_FILE_COUNT,
    )
    execution_top_level_file_count: Literal[17] = 17
    execution_raw_lineage_file_count: Literal[350] = EXPECTED_RAW_LINEAGE_FILE_COUNT
    execution_implementation_file_count: Literal[25] = 25
    audit_implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[393] = EXPECTED_SOURCE_REPLAY_FILE_COUNT
    replay_pass_count: Literal[393] = EXPECTED_SOURCE_REPLAY_FILE_COUNT
    replay_before_aggregate_reconstruction: Literal[True] = True
    model_client_constructed: Literal[False] = False
    api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = V26_93_SOURCE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ThinkingPostrunSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("thinking post-run replay paths are not canonical")
        if self.replayed_file_count != len(self.entries):
            raise ValueError("thinking post-run replay denominator changed")
        if self.replay_pass_count != self.replayed_file_count:
            raise ValueError("thinking post-run replay is incomplete")
        if self.audit_id != source_replay_audit_id(self):
            raise ValueError("thinking post-run source audit identity is invalid")
        return self


class PersistenceIntegrityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_binding_id: str = EXPECTED_EXECUTION_BINDING_ID
    raw_lineage_audit_id: str = EXPECTED_RAW_LINEAGE_ID
    raw_execution_count: Literal[32] = EXPECTED_JOB_COUNT
    raw_provider_artifact_count: Literal[318] = EXPECTED_PROVIDER_CALL_COUNT
    raw_lineage_descriptor_count: Literal[350] = EXPECTED_RAW_LINEAGE_FILE_COUNT
    raw_execution_canonical_json_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    raw_provider_canonical_json_pass_count: Literal[318] = EXPECTED_PROVIDER_CALL_COUNT
    raw_execution_schema_reparse_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    raw_provider_schema_reparse_pass_count: Literal[318] = EXPECTED_PROVIDER_CALL_COUNT
    final_job_result_count: Literal[32] = EXPECTED_JOB_COUNT
    checkpoint_job_result_count: Literal[32] = EXPECTED_JOB_COUNT
    checkpoint_final_result_match_count: Literal[32] = EXPECTED_JOB_COUNT
    thinking_history_audit_count: Literal[32] = EXPECTED_JOB_COUNT
    provider_budget_audit_count: Literal[32] = EXPECTED_JOB_COUNT
    cell_summary_count: Literal[12] = 12
    failure_artifact_count: Literal[32] = EXPECTED_JOB_COUNT
    solve_result_count: Literal[0] = 0
    unique_provider_artifact_ids: Literal[True] = True
    unique_provider_call_ids: Literal[True] = True
    private_reasoning_payload_count: Literal[0] = 0
    persisted_schema_valid_despite_runtime_serializer_warning: Literal[True] = True
    historical_files_modified: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_93_PERSISTENCE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PersistenceIntegrityAudit:
        if self.raw_lineage_descriptor_count != (
            self.raw_execution_count + self.raw_provider_artifact_count
        ):
            raise ValueError("thinking post-run lineage denominator changed")
        if self.audit_id != persistence_integrity_audit_id(self):
            raise ValueError("thinking post-run persistence identity is invalid")
        return self


class ResponseModelTelemetryGapAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    provider_call_count: Literal[318] = EXPECTED_PROVIDER_CALL_COUNT
    http_success_call_count: Literal[318] = EXPECTED_PROVIDER_CALL_COUNT
    exact_requested_model_call_count: Literal[318] = EXPECTED_PROVIDER_CALL_COUNT
    exact_selected_model_call_count: Literal[318] = EXPECTED_PROVIDER_CALL_COUNT
    fallback_call_count: Literal[0] = 0
    known_response_model_call_count: Literal[239] = EXPECTED_KNOWN_RESPONSE_MODEL_COUNT
    known_exact_response_model_call_count: Literal[239] = EXPECTED_KNOWN_RESPONSE_MODEL_COUNT
    known_response_model_mismatch_count: Literal[0] = 0
    missing_response_model_call_count: Literal[79] = EXPECTED_MODEL_TELEMETRY_GAP_COUNT
    missing_response_model_affected_job_count: Literal[32] = EXPECTED_JOB_COUNT
    missing_response_model_reason_counts: dict[str, int]
    missing_response_model_finish_reason_counts: dict[str, int]
    response_payload_present_count: Literal[239] = EXPECTED_KNOWN_RESPONSE_MODEL_COUNT
    response_payload_absent_count: Literal[79] = EXPECTED_MODEL_TELEMETRY_GAP_COUNT
    missing_response_model_recoverable_from_persisted_payload_count: Literal[0] = 0
    explicit_native_tool_observation_field_count: Literal[0] = 0
    positive_reasoning_telemetry_call_count: Literal[318] = EXPECTED_PROVIDER_CALL_COUNT
    historical_exact_model_job_pass_count: Literal[0] = 0
    observed_provider_model_mismatch: Literal[False] = False
    response_model_telemetry_gap_confirmed: Literal[True] = True
    provider_native_tool_absence_observation_gap_confirmed: Literal[True] = True
    historical_exact_model_result_reclassified: Literal[False] = False
    status: Literal["failed_unrecoverable_telemetry"] = "failed_unrecoverable_telemetry"
    schema_version: str = V26_93_MODEL_GAP_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ResponseModelTelemetryGapAudit:
        if self.known_response_model_call_count + self.missing_response_model_call_count != (
            self.provider_call_count
        ):
            raise ValueError("thinking response-model denominator changed")
        if self.response_payload_present_count + self.response_payload_absent_count != (
            self.provider_call_count
        ):
            raise ValueError("thinking response-payload denominator changed")
        if self.missing_response_model_reason_counts != {
            "JSONDecodeError": EXPECTED_JSON_DECODE_ERROR_COUNT,
            "ReasoningBudgetExhaustedError": EXPECTED_REASONING_EXHAUSTED_COUNT,
        }:
            raise ValueError("thinking response-model gap attribution changed")
        if self.missing_response_model_finish_reason_counts != {"length": 78, "stop": 1}:
            raise ValueError("thinking response-model gap finish reasons changed")
        if self.audit_id != response_model_gap_audit_id(self):
            raise ValueError("thinking response-model gap identity is invalid")
        return self


class CompletionRootCauseAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    job_count: Literal[32] = EXPECTED_JOB_COUNT
    distinct_source_task_count: Literal[31] = EXPECTED_SOURCE_TASK_COUNT
    logical_request_count: Literal[199] = EXPECTED_LOGICAL_REQUEST_COUNT
    provider_call_count: Literal[318] = EXPECTED_PROVIDER_CALL_COUNT
    provider_total_tokens: Literal[1294797] = EXPECTED_PROVIDER_TOTAL_TOKENS
    estimated_cost_usd: str = EXPECTED_ESTIMATED_COST_USD
    typed_no_call_job_count: Literal[0] = 0
    typed_no_call_cp95_upper_32: float = Field(ge=0, le=0.1)
    typed_no_call_gate_passed: Literal[True] = True
    completion_unusable_job_count: Literal[30] = EXPECTED_COMPLETION_UNUSABLE_COUNT
    completion_unusable_cp95_upper_32: float = Field(gt=0.1, le=1)
    completion_usability_gate_passed: Literal[False] = False
    completion_unusable_unique_source_count: Literal[29] = EXPECTED_COMPLETION_UNUSABLE_SOURCE_COUNT
    completion_unusable_cp95_upper_31: float = Field(gt=0.1, le=1)
    completion_outcome_counts: dict[str, int]
    length_finished_provider_call_count: Literal[78] = EXPECTED_LENGTH_RESPONSE_COUNT
    length_affected_logical_request_count: Literal[53] = 53
    length_affected_repaired_usable_request_count: Literal[23] = 23
    length_affected_terminal_failure_request_count: Literal[30] = 30
    multiple_length_calls_in_one_logical_request_count: Literal[25] = 25
    contract_repair_request_count: Literal[119] = EXPECTED_REPAIR_REQUEST_COUNT
    contract_repair_success_count: Literal[89] = EXPECTED_REPAIR_SUCCESS_COUNT
    contract_repair_failure_count: Literal[30] = 30
    contract_repair_affected_job_count: Literal[32] = EXPECTED_JOB_COUNT
    provider_transport_failure_job_count: Literal[0] = 0
    thinking_continuity_failure_job_count: Literal[0] = 0
    provider_budget_failure_job_count: Literal[0] = 0
    reasoning_token_fraction_mean: float = Field(gt=0, le=1)
    reasoning_token_fraction_minimum: float = Field(gt=0, le=1)
    reasoning_token_fraction_maximum: float = Field(gt=0, le=1)
    program_closed_count: Literal[0] = 0
    mechanism_success_count: Literal[6] = 6
    independently_valid_trajectory_count: Literal[0] = 0
    requested_path_adherence_count: Literal[10] = 10
    completion_failure_independently_blocks_release: Literal[True] = True
    telemetry_repair_cannot_rescue_completion_gate: Literal[True] = True
    behavior_diagnostics_descriptive_only: Literal[True] = True
    schema_version: str = V26_93_COMPLETION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CompletionRootCauseAudit:
        expected_outcomes = {
            "invalid_decision_contract_after_repair": 2,
            "length_truncated_content": 1,
            "reasoning_only_length_truncation": 27,
            "usable_after_contract_repair": 89,
            "usable_structured_completion": 80,
        }
        if self.completion_outcome_counts != expected_outcomes:
            raise ValueError("thinking completion outcome distribution changed")
        if sum(self.completion_outcome_counts.values()) != self.logical_request_count:
            raise ValueError("thinking completion logical denominator changed")
        if self.contract_repair_success_count + self.contract_repair_failure_count != (
            self.contract_repair_request_count
        ):
            raise ValueError("thinking completion repair denominator changed")
        if self.audit_id != completion_root_cause_audit_id(self):
            raise ValueError("thinking completion audit identity is invalid")
        return self


class RedactedProviderEnvelope(FrozenModel):
    response_model: str = Field(min_length=1)
    finish_reason: str | None = None
    public_content_sha256: str = Field(min_length=64, max_length=64)
    public_content_length: int = Field(ge=0)
    provider_native_tool_call_observed: bool
    reasoning_content_present: bool
    reasoning_content_length: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    schema_version: str = V26_93_REDACTED_ENVELOPE_VERSION

    @model_validator(mode="after")
    def validate_envelope(self) -> RedactedProviderEnvelope:
        if self.reasoning_content_present != (self.reasoning_content_length > 0):
            raise ValueError("redacted Provider reasoning presence and length disagree")
        if self.reasoning_tokens > self.completion_tokens:
            raise ValueError("redacted Provider reasoning Usage exceeds completion Usage")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True
    failure_type: str = Field(min_length=1)


class TelemetryRepairFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    valid_reasoning_exhausted_envelope: RedactedProviderEnvelope
    valid_invalid_json_envelope: RedactedProviderEnvelope
    mutation_results: tuple[MutationResult, ...] = Field(min_length=5, max_length=5)
    rejected_mutation_count: Literal[5] = 5
    response_model_preserved_before_content_parse: Literal[True] = True
    native_tool_presence_observed_before_content_parse: Literal[True] = True
    private_reasoning_content_absent: Literal[True] = True
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = V26_93_REPAIR_FIXTURE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> TelemetryRepairFixtureAudit:
        if self.rejected_mutation_count != len(self.mutation_results):
            raise ValueError("thinking telemetry repair mutation denominator changed")
        if self.audit_id != repair_fixture_audit_id(self):
            raise ValueError("thinking telemetry repair fixture identity is invalid")
        return self


class ThinkingTelemetryRepairContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    response_envelope_captured_before_content_parse: Literal[True] = True
    response_model_required_for_every_http_success: Literal[True] = True
    response_model_retained_on_http_success_parse_failure: Literal[True] = True
    provider_native_tool_presence_captured_before_content_parse: Literal[True] = True
    provider_native_tool_call_fails_closed: Literal[True] = True
    redacted_envelope_fields: tuple[str, ...] = (
        "response_model",
        "finish_reason",
        "public_content_sha256",
        "public_content_length",
        "provider_native_tool_call_observed",
        "reasoning_content_present",
        "reasoning_content_length",
        "reasoning_tokens",
        "completion_tokens",
    )
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    typed_failure_artifact_validated_before_serialization: Literal[True] = True
    historical_v26_92_result_reclassified: Literal[False] = False
    historical_v26_92_job_rerun_allowed: Literal[False] = False
    fresh_task_contract_manifest_and_job_identities_required: Literal[True] = True
    completion_upper_bound_tokens: Literal[4096] = 4096
    rollout_upper_bound_tokens: Literal[120000] = 120000
    prompt_upper_bound_bytes: Literal[60000] = 60000
    completion_contract_redesign_required_before_execution: Literal[True] = True
    completion_threshold_relaxation_forbidden: Literal[True] = True
    role_protocol_freeze_authorized: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    fixture_audit_id: str = Field(min_length=1)
    schema_version: str = V26_93_REPAIR_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ThinkingTelemetryRepairContract:
        expected_fields = (
            "response_model",
            "finish_reason",
            "public_content_sha256",
            "public_content_length",
            "provider_native_tool_call_observed",
            "reasoning_content_present",
            "reasoning_content_length",
            "reasoning_tokens",
            "completion_tokens",
        )
        if self.redacted_envelope_fields != expected_fields:
            raise ValueError("thinking telemetry repair retained unexpected fields")
        if self.contract_id != telemetry_repair_contract_id(self):
            raise ValueError("thinking telemetry repair Contract identity is invalid")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)


class ThinkingCalibrationPostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    execution_binding_id: str = EXPECTED_EXECUTION_BINDING_ID
    source_replay_audit_id: str = Field(min_length=1)
    persistence_integrity_audit_id: str = Field(min_length=1)
    response_model_gap_audit_id: str = Field(min_length=1)
    completion_root_cause_audit_id: str = Field(min_length=1)
    telemetry_repair_contract_id: str = Field(min_length=1)
    repair_fixture_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=6, max_length=6)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=1, max_length=1
    )
    source_replay_passed: Literal[True] = True
    persistence_integrity_passed: Literal[True] = True
    response_model_telemetry_gap_confirmed: Literal[True] = True
    observed_provider_model_mismatch: Literal[False] = False
    completion_usability_independently_failed: Literal[True] = True
    telemetry_repair_fixture_passed: Literal[True] = True
    historical_execution_report_retained: Literal[True] = True
    historical_job_rerun_count: Literal[0] = 0
    historical_result_reclassification_count: Literal[0] = 0
    model_client_constructed: Literal[False] = False
    api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    role_protocol_frozen: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    status: Literal["blocked"] = "blocked"
    next_permitted_stage: Literal[
        "fresh_thinking_completion_and_response_telemetry_repair_preflight_only"
    ] = "fresh_thinking_completion_and_response_telemetry_repair_preflight_only"
    schema_version: str = V26_93_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> ThinkingCalibrationPostrunAuditReport:
        if self.execution_report_id != EXPECTED_EXECUTION_REPORT_ID:
            raise ValueError("thinking post-run report crosses historical execution")
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("thinking post-run detail files are not canonical")
        if self.implementation_source_files[0].relative_path != AUDIT_SOURCE_PATH:
            raise ValueError("thinking post-run implementation binding changed")
        if self.report_id != postrun_audit_report_id(self):
            raise ValueError("thinking post-run report identity is invalid")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def source_replay_audit_id(value: ThinkingPostrunSourceReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_postrun_source_replay:")


def persistence_integrity_audit_id(value: PersistenceIntegrityAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_postrun_persistence:")


def response_model_gap_audit_id(value: ResponseModelTelemetryGapAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_response_model_gap:")


def completion_root_cause_audit_id(value: CompletionRootCauseAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_completion_root_cause:")


def repair_fixture_audit_id(value: TelemetryRepairFixtureAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_telemetry_repair_fixture:")


def telemetry_repair_contract_id(value: ThinkingTelemetryRepairContract) -> str:
    return _identity(value, "contract_id", "finance_v26_thinking_telemetry_repair_contract:")


def postrun_audit_report_id(value: ThinkingCalibrationPostrunAuditReport) -> str:
    return _identity(value, "report_id", "finance_v26_thinking_postrun_audit_report:")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _load_canonical_json(path: Path) -> Any:
    raw = path.read_bytes()
    payload = json.loads(raw)
    if raw != _canonical_bytes(payload):
        raise ValueError(f"noncanonical JSON artifact: {path}")
    return payload


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical_bytes(value)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError(f"immutable post-run output differs: {path}")
    path.write_bytes(raw)


def _relative(path: Path, package_root: Path) -> str:
    return str(path.resolve().relative_to(package_root.resolve()))


def _contains_private_reasoning_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key) == "reasoning_content" or _contains_private_reasoning_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_private_reasoning_key(item) for item in value)
    return False


def _cp_upper(failures: int, denominator: int, *, alpha: float = 0.05) -> float:
    if not 0 <= failures <= denominator or denominator <= 0:
        raise ValueError("invalid Clopper-Pearson denominator")
    if failures == denominator:
        return 1.0

    def cdf(probability: float) -> float:
        return sum(
            comb(denominator, index)
            * probability**index
            * (1.0 - probability) ** (denominator - index)
            for index in range(failures + 1)
        )

    lower = 0.0
    upper = 1.0
    for _ in range(200):
        midpoint = (lower + upper) / 2.0
        if cdf(midpoint) > alpha:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def _load_rows(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    payload = _load_canonical_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"expected a JSON list: {path}")
    return tuple(model.model_validate(item) for item in payload)


def _build_source_replay(
    *,
    execution_dir: Path,
    package_root: Path,
    binding: CalibrationExecutionBinding,
    lineage: CalibrationRawLineageAudit,
) -> ThinkingPostrunSourceReplayAudit:
    entries: list[SourceReplayEntry] = []

    def add(path: Path, expected: str, source_kind: Any) -> None:
        observed = _sha256(path)
        entries.append(
            SourceReplayEntry(
                relative_path=_relative(path, package_root),
                source_kind=source_kind,
                expected_sha256=expected,
                observed_sha256=observed,
                byte_count=path.stat().st_size,
                passed=observed == expected,
            )
        )

    for name, expected in sorted(TOP_LEVEL_SHA256.items()):
        add(execution_dir / name, expected, "execution_top_level")
    for descriptor in lineage.files:
        add(
            execution_dir / descriptor.relative_path,
            descriptor.sha256,
            "execution_raw_lineage",
        )
    for source in binding.implementation_source_files:
        add(
            package_root / source.relative_path,
            source.sha256,
            "execution_implementation",
        )
    audit_source = package_root / AUDIT_SOURCE_PATH
    add(audit_source, _sha256(audit_source), "postrun_audit_implementation")
    ordered = tuple(sorted(entries, key=lambda item: item.relative_path))
    values = {"entries": ordered}
    provisional = ThinkingPostrunSourceReplayAudit.model_construct(audit_id="pending", **values)
    return ThinkingPostrunSourceReplayAudit(audit_id=source_replay_audit_id(provisional), **values)


def _load_checkpoint(path: Path) -> tuple[CalibrationJobResult, ...]:
    rows = []
    for raw_line in path.read_bytes().splitlines(keepends=True):
        if not raw_line.strip():
            continue
        payload = json.loads(raw_line)
        if raw_line != _canonical_bytes(payload) + b"\n":
            raise ValueError("thinking calibration checkpoint is not canonical JSONL")
        rows.append(CalibrationJobResult.model_validate(payload))
    return tuple(rows)


def _build_persistence_audit(
    *,
    execution_dir: Path,
    lineage: CalibrationRawLineageAudit,
    results: tuple[CalibrationJobResult, ...],
) -> tuple[
    PersistenceIntegrityAudit,
    tuple[CalibrationRawExecution, ...],
    tuple[CalibrationRawProviderCall, ...],
]:
    raw_executions = []
    raw_provider_calls = []
    canonical_raw_count = 0
    canonical_provider_count = 0
    for descriptor in lineage.files:
        path = execution_dir / descriptor.relative_path
        payload = _load_canonical_json(path)
        if descriptor.relative_path.startswith("raw_execution/"):
            canonical_raw_count += 1
            raw_executions.append(CalibrationRawExecution.model_validate(payload))
        elif descriptor.relative_path.startswith("raw_provider_calls/"):
            canonical_provider_count += 1
            raw_provider_calls.append(CalibrationRawProviderCall.model_validate(payload))
        else:
            raise ValueError("thinking raw lineage contains an unknown path")
    checkpoint = _load_checkpoint(execution_dir / "calibration_job_results.checkpoint.jsonl")
    final_by_job = {item.job_id: item for item in results}
    checkpoint_matches = sum(final_by_job.get(item.job_id) == item for item in checkpoint)
    histories = cast(
        tuple[ThinkingHistoryAudit, ...],
        _load_rows(execution_dir / "thinking_history_audits.json", ThinkingHistoryAudit),
    )
    budgets = cast(
        tuple[ProviderTokenBudgetAudit, ...],
        _load_rows(execution_dir / "provider_budget_audits.json", ProviderTokenBudgetAudit),
    )
    cells = cast(
        tuple[CalibrationCellSummary, ...],
        _load_rows(execution_dir / "cell_summaries.json", CalibrationCellSummary),
    )
    private_count = sum(
        _contains_private_reasoning_key(item.response_payload) for item in raw_provider_calls
    )
    values = {
        "raw_execution_count": len(raw_executions),
        "raw_provider_artifact_count": len(raw_provider_calls),
        "raw_lineage_descriptor_count": len(lineage.files),
        "raw_execution_canonical_json_pass_count": canonical_raw_count,
        "raw_provider_canonical_json_pass_count": canonical_provider_count,
        "raw_execution_schema_reparse_pass_count": len(raw_executions),
        "raw_provider_schema_reparse_pass_count": len(raw_provider_calls),
        "final_job_result_count": len(results),
        "checkpoint_job_result_count": len(checkpoint),
        "checkpoint_final_result_match_count": checkpoint_matches,
        "thinking_history_audit_count": len(histories),
        "provider_budget_audit_count": len(budgets),
        "cell_summary_count": len(cells),
        "failure_artifact_count": sum(item.failure_artifact is not None for item in raw_executions),
        "solve_result_count": sum(item.solve_result is not None for item in raw_executions),
        "unique_provider_artifact_ids": (
            len({item.artifact_id for item in raw_provider_calls}) == len(raw_provider_calls)
        ),
        "unique_provider_call_ids": (
            len({item.provider_call_id for item in raw_provider_calls}) == len(raw_provider_calls)
        ),
        "private_reasoning_payload_count": private_count,
    }
    provisional = PersistenceIntegrityAudit.model_construct(audit_id="pending", **values)
    audit = PersistenceIntegrityAudit(
        audit_id=persistence_integrity_audit_id(provisional), **values
    )
    return audit, tuple(raw_executions), tuple(raw_provider_calls)


def _build_response_model_gap_audit(
    *,
    raw_executions: Sequence[CalibrationRawExecution],
    raw_provider_calls: Sequence[CalibrationRawProviderCall],
    results: Sequence[CalibrationJobResult],
) -> ResponseModelTelemetryGapAudit:
    telemetry = tuple(item for raw in raw_executions for item in raw.provider_telemetry)
    missing = tuple(item for item in telemetry if item.http_success and item.response_model is None)
    affected_jobs = sum(
        any(item.http_success and item.response_model is None for item in raw.provider_telemetry)
        for raw in raw_executions
    )
    values = {
        "provider_call_count": len(telemetry),
        "http_success_call_count": sum(item.http_success for item in telemetry),
        "exact_requested_model_call_count": sum(
            item.model_requested == "deepseek-v4-flash" for item in telemetry
        ),
        "exact_selected_model_call_count": sum(
            item.model_selected == "deepseek-v4-flash" for item in telemetry
        ),
        "fallback_call_count": sum(item.fallback_used for item in telemetry),
        "known_response_model_call_count": sum(
            item.response_model is not None for item in telemetry
        ),
        "known_exact_response_model_call_count": sum(
            item.response_model == "deepseek-v4-flash" for item in telemetry
        ),
        "known_response_model_mismatch_count": sum(
            item.response_model not in {None, "deepseek-v4-flash"} for item in telemetry
        ),
        "missing_response_model_call_count": len(missing),
        "missing_response_model_affected_job_count": affected_jobs,
        "missing_response_model_reason_counts": dict(
            sorted(Counter(item.error_type or "none" for item in missing).items())
        ),
        "missing_response_model_finish_reason_counts": dict(
            sorted(Counter(item.finish_reason or "none" for item in missing).items())
        ),
        "response_payload_present_count": sum(
            item.response_payload is not None for item in raw_provider_calls
        ),
        "response_payload_absent_count": sum(
            item.response_payload is None for item in raw_provider_calls
        ),
        "missing_response_model_recoverable_from_persisted_payload_count": sum(
            item.response_payload is not None and item.provider_telemetry.response_model is None
            for item in raw_provider_calls
        ),
        "explicit_native_tool_observation_field_count": sum(
            "provider_native_tool_call_observed" in item.response_shape for item in telemetry
        ),
        "positive_reasoning_telemetry_call_count": sum(
            item.http_success
            and item.reasoning_content_present
            and (item.reasoning_content_length or 0) > 0
            and (item.reasoning_tokens or 0) > 0
            for item in telemetry
        ),
        "historical_exact_model_job_pass_count": sum(item.exact_model_passed for item in results),
    }
    provisional = ResponseModelTelemetryGapAudit.model_construct(audit_id="pending", **values)
    return ResponseModelTelemetryGapAudit(
        audit_id=response_model_gap_audit_id(provisional), **values
    )


def _length_request_diagnostics(
    raw_executions: Sequence[CalibrationRawExecution],
) -> tuple[int, int, int, int]:
    affected = 0
    rescued = 0
    failed = 0
    repeated_length = 0
    usable = {"usable_after_contract_repair", "usable_structured_completion"}
    for raw in raw_executions:
        by_logical: dict[int, list[int]] = defaultdict(list)
        for attempt in raw.compact_attempts:
            index = attempt.provider_request_index
            if index is not None and raw.provider_telemetry[index].finish_reason == "length":
                by_logical[attempt.logical_request_index].append(index)
        outcomes = {
            item.request_index: item.completion_outcome for item in raw.completion_classifications
        }
        for logical_index, indices in by_logical.items():
            affected += 1
            repeated_length += len(indices) > 1
            if outcomes[logical_index] in usable:
                rescued += 1
            else:
                failed += 1
    return affected, rescued, failed, repeated_length


def _build_completion_audit(
    *,
    report: CalibrationExecutionReport,
    raw_executions: Sequence[CalibrationRawExecution],
    results: Sequence[CalibrationJobResult],
    classifications: Sequence[CompletionUsabilityClassification],
) -> CompletionRootCauseAudit:
    affected, rescued, failed, repeated_length = _length_request_diagnostics(raw_executions)
    telemetry = tuple(item for raw in raw_executions for item in raw.provider_telemetry)
    no_call_results = tuple(item for item in results if item.typed_no_call)
    unusable_results = tuple(item for item in results if item.completion_unusable)
    no_call_sources = {item.source_task_artifact_id for item in no_call_results}
    unusable_sources = {item.source_task_artifact_id for item in unusable_results}
    estimated_cost = sum(
        (
            Decimal(str(item.estimated_cost))
            for item in telemetry
            if item.estimated_cost is not None
        ),
        Decimal("0"),
    )
    fractions = tuple(
        cast(int, item.reasoning_tokens) / cast(int, item.completion_tokens)
        for item in telemetry
        if item.http_success
        and item.reasoning_tokens is not None
        and item.completion_tokens not in (None, 0)
    )
    no_call_cp32 = _cp_upper(len(no_call_results), EXPECTED_JOB_COUNT)
    completion_cp32 = _cp_upper(len(unusable_results), EXPECTED_JOB_COUNT)
    completion_cp31 = _cp_upper(len(unusable_sources), EXPECTED_SOURCE_TASK_COUNT)
    values = {
        "job_count": len(results),
        "distinct_source_task_count": len({item.source_task_artifact_id for item in results}),
        "logical_request_count": len(classifications),
        "provider_call_count": len(telemetry),
        "provider_total_tokens": sum(item.total_tokens or 0 for item in telemetry),
        "estimated_cost_usd": str(estimated_cost),
        "typed_no_call_job_count": len(no_call_results),
        "typed_no_call_cp95_upper_32": no_call_cp32,
        "typed_no_call_gate_passed": no_call_cp32 <= 0.10,
        "completion_unusable_job_count": len(unusable_results),
        "completion_unusable_cp95_upper_32": completion_cp32,
        "completion_usability_gate_passed": completion_cp32 <= 0.10,
        "completion_unusable_unique_source_count": len(unusable_sources),
        "completion_unusable_cp95_upper_31": completion_cp31,
        "completion_outcome_counts": dict(
            sorted(Counter(item.completion_outcome for item in classifications).items())
        ),
        "length_finished_provider_call_count": sum(
            item.finish_reason == "length" for item in telemetry
        ),
        "length_affected_logical_request_count": affected,
        "length_affected_repaired_usable_request_count": rescued,
        "length_affected_terminal_failure_request_count": failed,
        "multiple_length_calls_in_one_logical_request_count": repeated_length,
        "contract_repair_request_count": sum(
            item.contract_repair_attempted for item in classifications
        ),
        "contract_repair_success_count": sum(
            item.contract_repair_succeeded for item in classifications
        ),
        "contract_repair_failure_count": sum(
            item.contract_repair_attempted and not item.contract_repair_succeeded
            for item in classifications
        ),
        "contract_repair_affected_job_count": sum(
            any(item.contract_repair for item in raw.compact_attempts) for raw in raw_executions
        ),
        "provider_transport_failure_job_count": sum(
            item.provider_transport_failure for item in results
        ),
        "thinking_continuity_failure_job_count": sum(
            not item.thinking_continuity_passed for item in results
        ),
        "provider_budget_failure_job_count": sum(
            not item.budget_contract_passed for item in results
        ),
        "reasoning_token_fraction_mean": sum(fractions) / len(fractions),
        "reasoning_token_fraction_minimum": min(fractions),
        "reasoning_token_fraction_maximum": max(fractions),
        "program_closed_count": sum(item.program_closed for item in results),
        "mechanism_success_count": sum(item.mechanism_success for item in results),
        "independently_valid_trajectory_count": sum(item.independent_validity for item in results),
        "requested_path_adherence_count": sum(item.requested_path_adhered for item in results),
    }
    report_checks = {
        "typed_no_call_cp32": report.typed_no_call_cp95_upper_32 == no_call_cp32,
        "completion_cp32": report.completion_unusable_cp95_upper_32 == completion_cp32,
        "completion_cp31": report.completion_unusable_cp95_upper_31 == completion_cp31,
        "no_call_source_count": (len(no_call_sources) == report.typed_no_call_unique_source_count),
        "provider_tokens": values["provider_total_tokens"] == report.provider_total_tokens,
        "estimated_cost": values["estimated_cost_usd"] == report.estimated_cost_usd,
    }
    if not all(report_checks.values()):
        failed_checks = tuple(sorted(key for key, passed in report_checks.items() if not passed))
        raise ValueError(f"independent completion reconstruction differs: {failed_checks}")
    provisional = CompletionRootCauseAudit.model_construct(audit_id="pending", **values)
    return CompletionRootCauseAudit(audit_id=completion_root_cause_audit_id(provisional), **values)


def redact_provider_response_envelope(
    response_body: Mapping[str, Any],
) -> RedactedProviderEnvelope:
    model = str(response_body.get("model") or "").strip()
    if not model:
        raise ValueError("HTTP-success response lacks response model before content parsing")
    choices = response_body.get("choices")
    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)) or not choices:
        raise ValueError("HTTP-success response lacks a choice before content parsing")
    choice = choices[0]
    if not isinstance(choice, Mapping):
        raise ValueError("HTTP-success response choice is malformed")
    message = choice.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("HTTP-success response message is malformed")
    raw_content = message.get("content")
    content = "" if raw_content is None else str(raw_content)
    raw_reasoning = message.get("reasoning_content")
    reasoning_length = len(str(raw_reasoning)) if raw_reasoning is not None else 0
    usage = response_body.get("usage")
    if not isinstance(usage, Mapping):
        raise ValueError("HTTP-success response lacks Usage")
    details = usage.get("completion_tokens_details") or {}
    if not isinstance(details, Mapping):
        raise ValueError("HTTP-success response completion Usage is malformed")
    reasoning_tokens = int(details.get("reasoning_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    return RedactedProviderEnvelope(
        response_model=model,
        finish_reason=(
            str(choice["finish_reason"]) if choice.get("finish_reason") is not None else None
        ),
        public_content_sha256=_sha256_text(content),
        public_content_length=len(content),
        provider_native_tool_call_observed=bool(message.get("tool_calls")),
        reasoning_content_present=reasoning_length > 0,
        reasoning_content_length=reasoning_length,
        reasoning_tokens=reasoning_tokens,
        completion_tokens=completion_tokens,
    )


def require_admitted_repaired_envelope(envelope: RedactedProviderEnvelope) -> None:
    if envelope.response_model != "deepseek-v4-flash":
        raise ValueError("repaired telemetry response model is not exact Flash")
    if envelope.provider_native_tool_call_observed:
        raise ValueError("repaired telemetry observed a forbidden Provider-native tool call")
    if (
        not envelope.reasoning_content_present
        or envelope.reasoning_content_length == 0
        or envelope.reasoning_tokens == 0
    ):
        raise ValueError("repaired telemetry lacks positive reasoning telemetry")


def _build_repair_fixture() -> TelemetryRepairFixtureAudit:
    base = {
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "finish_reason": "length",
                "message": {
                    "content": "",
                    "reasoning_content": "synthetic private reasoning",
                },
            }
        ],
        "usage": {
            "completion_tokens": 4096,
            "completion_tokens_details": {"reasoning_tokens": 4096},
        },
    }
    exhausted = redact_provider_response_envelope(base)
    require_admitted_repaired_envelope(exhausted)
    invalid_json_payload = json.loads(json.dumps(base))
    invalid_json_payload["choices"][0]["finish_reason"] = "stop"
    invalid_json_payload["choices"][0]["message"]["content"] = "not-json"
    invalid_json_payload["usage"]["completion_tokens"] = 120
    invalid_json_payload["usage"]["completion_tokens_details"]["reasoning_tokens"] = 100
    invalid_json = redact_provider_response_envelope(invalid_json_payload)
    require_admitted_repaired_envelope(invalid_json)

    mutations: list[MutationResult] = []

    def reject(name: str, operation: Any) -> None:
        try:
            operation()
        except (ValueError, ValidationError) as exc:
            mutations.append(
                MutationResult(
                    mutation_name=name,
                    rejected=True,
                    failure_type=type(exc).__name__,
                )
            )
            return
        raise AssertionError(f"telemetry repair mutation passed: {name}")

    reject(
        "missing_response_model",
        lambda: redact_provider_response_envelope({**base, "model": None}),
    )
    reject(
        "changed_response_model",
        lambda: require_admitted_repaired_envelope(
            exhausted.model_copy(update={"response_model": "deepseek-v4-pro"})
        ),
    )
    reject(
        "provider_native_tool_call",
        lambda: require_admitted_repaired_envelope(
            exhausted.model_copy(update={"provider_native_tool_call_observed": True})
        ),
    )
    reject(
        "missing_reasoning_telemetry",
        lambda: require_admitted_repaired_envelope(
            exhausted.model_copy(
                update={
                    "reasoning_content_present": False,
                    "reasoning_content_length": 0,
                    "reasoning_tokens": 0,
                }
            )
        ),
    )
    reject(
        "private_reasoning_persistence_field",
        lambda: RedactedProviderEnvelope.model_validate(
            {**exhausted.model_dump(mode="json"), "reasoning_content": "forbidden"}
        ),
    )
    values = {
        "valid_reasoning_exhausted_envelope": exhausted,
        "valid_invalid_json_envelope": invalid_json,
        "mutation_results": tuple(mutations),
        "private_reasoning_content_absent": not _contains_private_reasoning_key(
            (exhausted.model_dump(mode="json"), invalid_json.model_dump(mode="json"))
        ),
    }
    provisional = TelemetryRepairFixtureAudit.model_construct(audit_id="pending", **values)
    return TelemetryRepairFixtureAudit(audit_id=repair_fixture_audit_id(provisional), **values)


def _build_repair_contract(
    fixture: TelemetryRepairFixtureAudit,
) -> ThinkingTelemetryRepairContract:
    values = {"fixture_audit_id": fixture.audit_id}
    provisional = ThinkingTelemetryRepairContract.model_construct(contract_id="pending", **values)
    return ThinkingTelemetryRepairContract(
        contract_id=telemetry_repair_contract_id(provisional), **values
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_thinking_calibration_postrun_audit(
    *,
    run_id: str,
    execution_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> ThinkingCalibrationPostrunAuditReport:
    report = CalibrationExecutionReport.model_validate(
        _load_canonical_json(execution_dir / "report.json")
    )
    binding = CalibrationExecutionBinding.model_validate(
        _load_canonical_json(execution_dir / "execution_binding.json")
    )
    lineage = CalibrationRawLineageAudit.model_validate(
        _load_canonical_json(execution_dir / "raw_lineage_audit.json")
    )
    if (
        report.report_id != EXPECTED_EXECUTION_REPORT_ID
        or binding.binding_id != EXPECTED_EXECUTION_BINDING_ID
        or lineage.audit_id != EXPECTED_RAW_LINEAGE_ID
        or report.execution_binding_id != binding.binding_id
        or report.raw_lineage_audit_id != lineage.audit_id
    ):
        raise ValueError("thinking post-run audit received another execution")
    source_replay = _build_source_replay(
        execution_dir=execution_dir,
        package_root=package_root,
        binding=binding,
        lineage=lineage,
    )
    results = cast(
        tuple[CalibrationJobResult, ...],
        _load_rows(execution_dir / "calibration_job_results.json", CalibrationJobResult),
    )
    classifications = cast(
        tuple[CompletionUsabilityClassification, ...],
        _load_rows(
            execution_dir / "completion_usability_classifications.json",
            CompletionUsabilityClassification,
        ),
    )
    attempts = cast(
        tuple[CompactRequestAttempt, ...],
        _load_rows(execution_dir / "compact_request_attempts.json", CompactRequestAttempt),
    )
    if len(attempts) != 318 or len(classifications) != EXPECTED_LOGICAL_REQUEST_COUNT:
        raise ValueError("thinking post-run request denominators changed")
    persistence, raw_executions, raw_provider_calls = _build_persistence_audit(
        execution_dir=execution_dir,
        lineage=lineage,
        results=results,
    )
    model_gap = _build_response_model_gap_audit(
        raw_executions=raw_executions,
        raw_provider_calls=raw_provider_calls,
        results=results,
    )
    completion = _build_completion_audit(
        report=report,
        raw_executions=raw_executions,
        results=results,
        classifications=classifications,
    )
    fixture = _build_repair_fixture()
    repair_contract = _build_repair_contract(fixture)

    output_dir.mkdir(parents=True, exist_ok=True)
    detail_values = {
        "completion_root_cause_audit.json": completion,
        "persistence_integrity_audit.json": persistence,
        "provider_telemetry_gap_audit.json": model_gap,
        "repair_fixture_audit.json": fixture,
        "source_replay_audit.json": source_replay,
        "telemetry_repair_contract.json": repair_contract,
    }
    for name, value in detail_values.items():
        _write_json(output_dir / name, value.model_dump(mode="json"))
    details = tuple(_detail(output_dir / name, output_dir) for name in sorted(detail_values))
    implementation = (
        ImplementationSourceFile(
            relative_path=AUDIT_SOURCE_PATH,
            sha256=_sha256(package_root / AUDIT_SOURCE_PATH),
        ),
    )
    values = {
        "run_id": run_id,
        "source_replay_audit_id": source_replay.audit_id,
        "persistence_integrity_audit_id": persistence.audit_id,
        "response_model_gap_audit_id": model_gap.audit_id,
        "completion_root_cause_audit_id": completion.audit_id,
        "telemetry_repair_contract_id": repair_contract.contract_id,
        "repair_fixture_audit_id": fixture.audit_id,
        "detail_files": details,
        "implementation_source_files": implementation,
    }
    provisional = ThinkingCalibrationPostrunAuditReport.model_construct(
        report_id="pending", **values
    )
    audit_report = ThinkingCalibrationPostrunAuditReport(
        report_id=postrun_audit_report_id(provisional), **values
    )
    _write_json(output_dir / "report.json", audit_report.model_dump(mode="json"))
    return audit_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit v26.92 Thinking Calibration and freeze telemetry repair"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execution-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    args = parser.parse_args()
    report = build_thinking_calibration_postrun_audit(
        run_id=args.run_id,
        execution_dir=args.execution_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
