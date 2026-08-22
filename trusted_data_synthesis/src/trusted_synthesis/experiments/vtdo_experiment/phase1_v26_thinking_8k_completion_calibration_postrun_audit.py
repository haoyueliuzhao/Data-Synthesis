from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal
from math import comb
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    ImplementationSourceFile,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_8k_binding_rematerialization import (  # noqa: E501
    Exact8KManifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_8k_completion_calibration_contracts import (  # noqa: E501
    Exact8KExecutionContract,
    Exact8KExecutionReport,
    Exact8KOutcomeInterpretationContract,
    Exact8KRawExecution,
    Exact8KRawLineageAudit,
    Exact8KRawProviderCall,
    Exact8KRunnerPreflightReport,
    Exact8KRunnerSourceReplayAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501
    ThinkingRepairJobResult,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry

RUN_ID: Literal["finance_v26_102_thinking_8k_completion_calibration_postrun_audit_v2_20260822"] = (
    "finance_v26_102_thinking_8k_completion_calibration_postrun_audit_v2_20260822"
)
PREFLIGHT_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_100_thinking_8k_completion_calibration_runner_preflight_v1_20260822"
)
EXECUTION_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_101_thinking_8k_completion_calibration_execution_v1_20260822"
)
AUDIT_SOURCE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_8k_completion_calibration_postrun_audit.py"
)

EXPECTED_PREFLIGHT_REPORT_ID = (
    "finance_v26_exact_8k_runner_preflight_report:"
    "da74cbc040525571bb636986bbdf198a24948f5967f027cf42422537372968f0"
)
EXPECTED_EXECUTION_CONTRACT_ID = (
    "finance_v26_exact_8k_execution_contract:"
    "bd01f5da28c20b33d693d5c7036bd7f77732a4995829e92773b1a205aced99ce"
)
EXPECTED_EXECUTION_REPORT_ID = (
    "finance_v26_exact_8k_execution_report:"
    "5eb7cc814364afa4cf15a3406d31c4ff4a4919092c6c2c5468f2bdb5bf1aeb52"
)
EXPECTED_RAW_LINEAGE_ID = (
    "finance_v26_exact_8k_raw_lineage:"
    "5ddeb756efe627c3b02489d2ed5b7a43e5507f859ad2666b1728157b92a6add6"
)
EXPECTED_MANIFEST_ID = (
    "finance_v26_exact_8k_manifest:e50b85b55d76fe3f9e74b24cfde98d40d2c4a1f1608a85fcead6eebe6bd1c118"
)
EXPECTED_INTERPRETATION_ID = (
    "finance_v26_exact_8k_outcome_interpretation:"
    "18b6081ee384b23e3f5d39b898d6212f5b20e91d93c2387ec99a0fd6c51db05e"
)
EXPECTED_PREFLIGHT_REPORT_SHA256 = (
    "edc07979c4f470454152e4b6df1fa069beda705c87c0c132f20ae6b26f36c505"
)
EXPECTED_EXECUTION_REPORT_SHA256 = (
    "bf2b3cbd48ac6aeb4c9d6d5d2dc29ab68c184d9aebe50687e46e505798098152"
)
EXPECTED_INSTRUMENT_JOB_ID = (
    "finance_v26_exact_8k_job:a417552048053969774fce4e067c739d42e45a626e7b79a07d78f2304ba8f93a"
)
EXPECTED_OVERRUN_PROVIDER_CALL_ID = (
    "finance_v26_exact_8k_provider_call:"
    "5856d95d303d8d4afd8b847b43705fc62359580bc5835e7150e5453df9eb7902"
)

EXPECTED_BOUND_SOURCE_COUNT: Literal[770] = 770
EXPECTED_PREFLIGHT_OUTPUT_COUNT: Literal[9] = 9
EXPECTED_EXECUTION_FILE_COUNT: Literal[431] = 431
EXPECTED_SOURCE_REPLAY_COUNT: Literal[1211] = 1211
EXPECTED_JOB_COUNT: Literal[32] = 32
EXPECTED_PROVIDER_CALL_COUNT: Literal[391] = 391
EXPECTED_RAW_DESCRIPTOR_COUNT: Literal[423] = 423
EXPECTED_PROVIDER_TOTAL_TOKENS: Literal[2498889] = 2_498_889
EXPECTED_PROMPT_TOKENS: Literal[850715] = 850_715
EXPECTED_COMPLETION_TOKENS: Literal[1648174] = 1_648_174
EXPECTED_REASONING_TOKENS: Literal[1610137] = 1_610_137
EXPECTED_REASONING_LENGTH: Literal[6954719] = 6_954_719
EXPECTED_COST: Literal["0.53245247440000004286"] = "0.53245247440000004286"
EXPECTED_COMPLETION_FAILURES = {
    "invalid_json": 1,
    "invalid_response_contract": 12,
    "length_truncated_content": 3,
    "reasoning_only_length_truncation": 42,
}
NEXT_STAGE: Literal[
    "fresh_16k_profile_binding_and_provider_usage_contract_runner_preflight_only"
] = "fresh_16k_profile_binding_and_provider_usage_contract_runner_preflight_only"

SourceKind = Literal[
    "v26_100_bound_source",
    "v26_100_preflight_output",
    "v26_101_execution_file",
    "v26_102_implementation",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: SourceKind
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> SourceReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("v26.102 source replay changed")
        return self


class PostrunSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    entries: tuple[SourceReplayEntry, ...] = Field(
        min_length=EXPECTED_SOURCE_REPLAY_COUNT,
        max_length=EXPECTED_SOURCE_REPLAY_COUNT,
    )
    bound_source_file_count: Literal[770] = EXPECTED_BOUND_SOURCE_COUNT
    preflight_output_file_count: Literal[9] = EXPECTED_PREFLIGHT_OUTPUT_COUNT
    execution_file_count: Literal[431] = EXPECTED_EXECUTION_FILE_COUNT
    audit_implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[1211] = EXPECTED_SOURCE_REPLAY_COUNT
    replay_pass_count: Literal[1211] = EXPECTED_SOURCE_REPLAY_COUNT
    replay_before_diagnostics: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_8k_postrun_source_replay.v1"] = (
        "finance_v26_exact_8k_postrun_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PostrunSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.102 source paths are not canonical")
        if len(self.entries) != self.replayed_file_count:
            raise ValueError("v26.102 source denominator changed")
        if self.audit_id != source_replay_id(self):
            raise ValueError("v26.102 source identity changed")
        return self


class ExecutionLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    raw_lineage_id: str = EXPECTED_RAW_LINEAGE_ID
    expected_job_count: Literal[32] = EXPECTED_JOB_COUNT
    checkpoint_job_count: Literal[32] = EXPECTED_JOB_COUNT
    result_job_count: Literal[32] = EXPECTED_JOB_COUNT
    raw_execution_count: Literal[32] = EXPECTED_JOB_COUNT
    provider_artifact_count: Literal[391] = EXPECTED_PROVIDER_CALL_COUNT
    unique_provider_call_id_count: Literal[391] = EXPECTED_PROVIDER_CALL_COUNT
    raw_descriptor_count: Literal[423] = EXPECTED_RAW_DESCRIPTOR_COUNT
    raw_descriptor_hash_pass_count: Literal[423] = EXPECTED_RAW_DESCRIPTOR_COUNT
    canonical_json_file_count: Literal[430] = 430
    canonical_json_file_pass_count: Literal[430] = 430
    canonical_jsonl_row_count: Literal[32] = EXPECTED_JOB_COUNT
    canonical_jsonl_row_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    checkpoint_final_result_match_count: Literal[32] = EXPECTED_JOB_COUNT
    checkpoint_raw_binding_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    manifest_job_identity_match_count: Literal[32] = EXPECTED_JOB_COUNT
    provider_parent_binding_pass_count: Literal[391] = EXPECTED_PROVIDER_CALL_COUNT
    all_provider_calls_dynamically_precertified: Literal[True] = True
    all_provider_calls_exact_8k_request_bound: Literal[True] = True
    private_reasoning_payload_count: Literal[0] = 0
    raw_http_body_payload_count: Literal[0] = 0
    raw_request_body_payload_count: Literal[0] = 0
    historical_job_rerun_count: Literal[0] = 0
    historical_result_reclassification_count: Literal[0] = 0
    completed_run_replay_job_count: Literal[32] = EXPECTED_JOB_COUNT
    completed_run_replay_client_factory_call_count: Literal[0] = 0
    completed_run_replay_provider_call_count: Literal[0] = 0
    completed_run_replay_report_byte_identical: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_8k_execution_lineage_audit.v1"] = (
        "finance_v26_exact_8k_execution_lineage_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionLineageAudit:
        if self.audit_id != execution_lineage_id(self):
            raise ValueError("v26.102 execution lineage identity changed")
        return self


class ProviderTelemetryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    provider_call_count: Literal[391] = EXPECTED_PROVIDER_CALL_COUNT
    http_success_call_count: Literal[391] = EXPECTED_PROVIDER_CALL_COUNT
    exact_requested_model_count: Literal[391] = EXPECTED_PROVIDER_CALL_COUNT
    exact_selected_model_count: Literal[391] = EXPECTED_PROVIDER_CALL_COUNT
    exact_response_model_count: Literal[391] = EXPECTED_PROVIDER_CALL_COUNT
    fallback_count: Literal[0] = 0
    provider_native_tool_call_count: Literal[0] = 0
    model_discovery_call_count: Literal[0] = 0
    usage_complete_count: Literal[391] = EXPECTED_PROVIDER_CALL_COUNT
    thinking_telemetry_complete_count: Literal[391] = EXPECTED_PROVIDER_CALL_COUNT
    response_envelope_preparse_count: Literal[391] = EXPECTED_PROVIDER_CALL_COUNT
    exact_8k_request_certificate_count: Literal[391] = EXPECTED_PROVIDER_CALL_COUNT
    dynamic_precall_certificate_count: Literal[391] = EXPECTED_PROVIDER_CALL_COUNT
    primary_provider_call_count: Literal[362] = 362
    rescue_provider_call_count: Literal[29] = 29
    provider_total_tokens: Literal[2498889] = EXPECTED_PROVIDER_TOTAL_TOKENS
    prompt_tokens_total: Literal[850715] = EXPECTED_PROMPT_TOKENS
    completion_tokens_total: Literal[1648174] = EXPECTED_COMPLETION_TOKENS
    reasoning_tokens_total: Literal[1610137] = EXPECTED_REASONING_TOKENS
    reasoning_content_length_total: Literal[6954719] = EXPECTED_REASONING_LENGTH
    estimated_cost_usd: Literal["0.53245247440000004286"] = EXPECTED_COST
    completion_usage_within_request_bound_count: Literal[390] = 390
    completion_usage_over_request_bound_count: Literal[1] = 1
    maximum_completion_usage_tokens: Literal[8193] = 8193
    maximum_request_bound_tokens: Literal[8192] = 8192
    maximum_observed_overrun_tokens: Literal[1] = 1
    private_reasoning_payload_count: Literal[0] = 0
    private_reasoning_hash_count: Literal[0] = 0
    raw_http_body_payload_count: Literal[0] = 0
    raw_request_body_payload_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_8k_provider_telemetry_audit.v1"] = (
        "finance_v26_exact_8k_provider_telemetry_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ProviderTelemetryAudit:
        if self.primary_provider_call_count + self.rescue_provider_call_count != 391:
            raise ValueError("v26.102 Provider phase denominator changed")
        if self.audit_id != provider_telemetry_id(self):
            raise ValueError("v26.102 Provider telemetry identity changed")
        return self


class CompletionOutcomeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_job_denominator: Literal[32] = EXPECTED_JOB_COUNT
    terminal_counts: dict[str, int]
    completion_unusable_job_count: Literal[28] = 28
    instrument_failure_job_count: Literal[1] = 1
    model_valid_trajectory_count: Literal[3] = 3
    typed_no_call_job_count: Literal[0] = 0
    provider_transport_failure_job_count: Literal[0] = 0
    completion_failure_counts: dict[str, int]
    completion_failure_call_count: Literal[58] = 58
    rescue_attempt_job_count: Literal[30] = 30
    rescue_provider_call_job_count: Literal[29] = 29
    completion_unusable_cp95_upper_32: float = Field(gt=0.95, lt=0.97)
    typed_no_call_cp95_upper_32: float = Field(gt=0.08, lt=0.10)
    typed_no_call_gate_passed: Literal[True] = True
    completion_usability_gate_passed: Literal[False] = False
    length_or_reasoning_only_failure_observed: Literal[True] = True
    semantic_validity_can_rescue_completion_gate: Literal[False] = False
    program_closed_count: Literal[3] = 3
    mechanism_success_count: Literal[11] = 11
    independently_valid_trajectory_count: Literal[3] = 3
    requested_path_adherence_count: Literal[12] = 12
    calibration_only: Literal[True] = True
    role_or_state_evidence_row_count: Literal[0] = 0
    status: Literal["completion_gate_failed"] = "completion_gate_failed"
    schema_version: Literal["finance_v26_exact_8k_completion_outcome_audit.v1"] = (
        "finance_v26_exact_8k_completion_outcome_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CompletionOutcomeAudit:
        if self.terminal_counts != {
            "completion_unusable": 28,
            "instrument_failure": 1,
            "model_valid_trajectory": 3,
        }:
            raise ValueError("v26.102 terminal counts changed")
        if self.completion_failure_counts != EXPECTED_COMPLETION_FAILURES:
            raise ValueError("v26.102 Completion failure counts changed")
        if self.audit_id != completion_outcome_id(self):
            raise ValueError("v26.102 Completion outcome identity changed")
        return self


class InstrumentRootCauseAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    root_cause: Literal["provider_reported_completion_usage_one_token_over_exact_request_bound"] = (
        "provider_reported_completion_usage_one_token_over_exact_request_bound"
    )
    instrument_job_id: str = EXPECTED_INSTRUMENT_JOB_ID
    provider_call_id: str = EXPECTED_OVERRUN_PROVIDER_CALL_ID
    provider_artifact_relative_path: Literal[
        "raw_provider_calls/796a577d1c35af580b02/call_0009.json"
    ] = "raw_provider_calls/796a577d1c35af580b02/call_0009.json"
    raw_execution_relative_path: Literal["raw_execution/796a577d1c35af580b02.json"] = (
        "raw_execution/796a577d1c35af580b02.json"
    )
    logical_request_index: Literal[9] = 9
    provider_call_index: Literal[9] = 9
    phase: Literal["primary"] = "primary"
    request_kind: Literal["decision"] = "decision"
    request_max_tokens: Literal[8192] = 8192
    request_certificate_max_tokens: Literal[8192] = 8192
    dynamic_certificate_completion_bound: Literal[8192] = 8192
    provider_budget_completion_bound: Literal[8192] = 8192
    provider_reported_completion_tokens: Literal[8193] = 8193
    provider_reported_reasoning_tokens: Literal[8193] = 8193
    provider_reported_prompt_tokens: Literal[2522] = 2522
    provider_reported_total_tokens: Literal[10715] = 10715
    provider_reported_overrun_tokens: Literal[1] = 1
    response_finish_reason: Literal["length"] = "length"
    public_content_length: Literal[0] = 0
    failure_type: Literal["reasoning_only_length_truncation"] = "reasoning_only_length_truncation"
    exact_model_requested_selected_returned: Literal[True] = True
    fallback_absent: Literal[True] = True
    all_certificates_constructed_before_provider_call: Literal[True] = True
    response_envelope_captured_before_content_parse: Literal[True] = True
    response_envelope_schema_valid: Literal[True] = True
    rescue_attempted_after_primary_failure: Literal[True] = True
    rescue_provider_call_made: Literal[False] = False
    rescue_blocked_after_terminal_budget_state: Literal[True] = True
    other_provider_calls_within_bound_count: Literal[390] = 390
    other_budget_contract_failure_count: Literal[0] = 0
    host_request_binding_failure_observed: Literal[False] = False
    dynamic_precall_failure_observed: Literal[False] = False
    response_telemetry_gap_observed: Literal[False] = False
    underlying_provider_generation_vs_accounting_semantics_uniquely_identified: Literal[False] = (
        False
    )
    historical_terminal_reclassified: Literal[False] = False
    completion_gate_failed_independently_by_other_jobs: Literal[True] = True
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    raw_request_body_persisted: Literal[False] = False
    status: Literal["root_cause_localized"] = "root_cause_localized"
    schema_version: Literal["finance_v26_exact_8k_instrument_root_cause.v1"] = (
        "finance_v26_exact_8k_instrument_root_cause.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> InstrumentRootCauseAudit:
        if self.provider_reported_completion_tokens - self.request_max_tokens != 1:
            raise ValueError("v26.102 observed overrun changed")
        if self.audit_id != instrument_root_cause_id(self):
            raise ValueError("v26.102 Instrument root-cause identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    predecessor_root_cause_audit_id: str = Field(min_length=1)
    next_permitted_stage: Literal[
        "fresh_16k_profile_binding_and_provider_usage_contract_runner_preflight_only"
    ] = NEXT_STAGE
    exact_16k_candidate_id: Literal[
        "prospective_completion_bound_candidate:"
        "6dfb2358d92a7b1e39a8cf741033e43974dad1a77114d01533ef673115a59dc2"
    ] = (
        "prospective_completion_bound_candidate:"
        "6dfb2358d92a7b1e39a8cf741033e43974dad1a77114d01533ef673115a59dc2"
    )
    exact_16k_request_max_tokens: Literal[16384] = 16384
    exact_16k_rollout_ceiling_tokens: Literal[240000] = 240000
    exact_thinking_type: Literal["enabled"] = "enabled"
    persisted_exact_16k_profile_required: Literal[True] = True
    fresh_16k_model_config_and_thinking_binding_required: Literal[True] = True
    fresh_taskpackage_path_contract_manifest_job_identities_required: Literal[True] = True
    fresh_runner_execution_and_report_identities_required: Literal[True] = True
    preserve_source_path_assignment_seed_and_prompt_design: Literal[True] = True
    provider_usage_semantics_contract_required_before_runner: Literal[True] = True
    separate_request_bound_from_provider_reported_usage_accounting: Literal[True] = True
    charge_actual_provider_reported_usage_to_rollout_budget: Literal[True] = True
    observed_accounting_margin_tokens: Literal[1] = 1
    prospective_margin_must_reject_two_or_more_tokens: Literal[True] = True
    accounting_margin_cannot_rescue_length_or_completion_failure: Literal[True] = True
    accounting_margin_is_instrument_repair_not_empirical_threshold_change: Literal[True] = True
    provider_semantics_claim_remains_unresolved: Literal[True] = True
    automatic_16k_escalation_allowed: Literal[False] = False
    direct_16k_execution_authorized: Literal[False] = False
    v26_101_job_rerun_authorized: Literal[False] = False
    v26_101_terminal_reclassification_authorized: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_8k_postrun_transition.v1"] = (
        "finance_v26_exact_8k_postrun_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != transition_contract_id(self):
            raise ValueError("v26.102 transition identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_id: str = Field(min_length=1)
    mutation: str = Field(min_length=1)
    rejected: Literal[True] = True
    rejection_stage: Literal["offline_audit"] = "offline_audit"
    provider_calls_before_rejection: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_8k_postrun_mutation.v1"] = (
        "finance_v26_exact_8k_postrun_mutation.v1"
    )

    @model_validator(mode="after")
    def validate_result(self) -> MutationResult:
        if self.mutation_id != mutation_result_id(self):
            raise ValueError("v26.102 mutation identity changed")
        return self


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=20, max_length=20)
    mutation_count: Literal[20] = 20
    rejected_mutation_count: Literal[20] = 20
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_8k_postrun_destructive.v1"] = (
        "finance_v26_exact_8k_postrun_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.mutation for item in self.mutation_results)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.102 mutations are not canonical")
        if self.audit_id != destructive_audit_id(self):
            raise ValueError("v26.102 destructive identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: Literal[
        "finance_v26_102_thinking_8k_completion_calibration_postrun_audit_v2_20260822"
    ] = RUN_ID
    predecessor_preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    predecessor_execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    source_replay_audit_id: str = Field(min_length=1)
    execution_lineage_audit_id: str = Field(min_length=1)
    provider_telemetry_audit_id: str = Field(min_length=1)
    completion_outcome_audit_id: str = Field(min_length=1)
    instrument_root_cause_audit_id: str = Field(min_length=1)
    prospective_transition_contract_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=7, max_length=7)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=1, max_length=1
    )
    exact_job_denominator: Literal[32] = EXPECTED_JOB_COUNT
    provider_call_count: Literal[391] = EXPECTED_PROVIDER_CALL_COUNT
    completion_unusable_job_count: Literal[28] = 28
    instrument_failure_job_count: Literal[1] = 1
    independently_valid_trajectory_count: Literal[3] = 3
    typed_no_call_job_count: Literal[0] = 0
    provider_transport_failure_job_count: Literal[0] = 0
    exact_8k_request_binding_passed: Literal[True] = True
    dynamic_precall_binding_passed: Literal[True] = True
    empirical_budget_adequacy_passed: Literal[True] = True
    response_telemetry_instrument_passed: Literal[True] = True
    completion_usability_passed: Literal[False] = False
    execution_integrity_passed: Literal[False] = False
    root_cause: Literal["provider_reported_completion_usage_one_token_over_exact_request_bound"] = (
        "provider_reported_completion_usage_one_token_over_exact_request_bound"
    )
    historical_job_rerun_count: Literal[0] = 0
    historical_result_reclassification_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    role_protocol_frozen: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    status: Literal["blocked"] = "blocked"
    next_permitted_stage: Literal[
        "fresh_16k_profile_binding_and_provider_usage_contract_runner_preflight_only"
    ] = NEXT_STAGE
    schema_version: Literal["finance_v26_exact_8k_postrun_audit_report.v1"] = (
        "finance_v26_exact_8k_postrun_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> PostrunAuditReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.102 report detail paths are not canonical")
        if self.implementation_source_files[0].relative_path != AUDIT_SOURCE_PATH:
            raise ValueError("v26.102 implementation binding changed")
        if self.report_id != postrun_report_id(self):
            raise ValueError("v26.102 report identity changed")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def source_replay_id(value: PostrunSourceReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_postrun_source_replay:")


def execution_lineage_id(value: ExecutionLineageAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_execution_lineage_audit:")


def provider_telemetry_id(value: ProviderTelemetryAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_provider_telemetry_audit:")


def completion_outcome_id(value: CompletionOutcomeAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_completion_outcome_audit:")


def instrument_root_cause_id(value: InstrumentRootCauseAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_instrument_root_cause:")


def transition_contract_id(value: ProspectiveTransitionContract) -> str:
    return _identity(value, "contract_id", "finance_v26_exact_8k_postrun_transition:")


def mutation_result_id(value: MutationResult) -> str:
    return _identity(value, "mutation_id", "finance_v26_exact_8k_postrun_mutation:")


def destructive_audit_id(value: DestructiveAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_postrun_destructive:")


def postrun_report_id(value: PostrunAuditReport) -> str:
    return _identity(value, "report_id", "finance_v26_exact_8k_postrun_audit_report:")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        raise ValueError(f"noncanonical v26.102 JSON: {path}")
    return payload


def _load_canonical_jsonl(path: Path) -> tuple[Any, ...]:
    rows = []
    for line in path.read_bytes().splitlines():
        payload = json.loads(line)
        if line != _canonical_bytes(payload):
            raise ValueError(f"noncanonical v26.102 JSONL row: {path}")
        rows.append(payload)
    return tuple(rows)


def _write_json(path: Path, value: Any) -> None:
    raw = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError(f"immutable v26.102 output changed: {path}")
    path.write_bytes(raw)


def _relative(path: Path, package_root: Path) -> str:
    return str(path.absolute().relative_to(package_root.absolute()))


def _contains_key(value: Any, key_name: str) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key) == key_name or _contains_key(item, key_name) for key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_key(item, key_name) for item in value)
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


def _source_entry(
    *,
    path: Path,
    package_root: Path,
    source_kind: SourceKind,
    expected_sha256: str,
) -> SourceReplayEntry:
    return SourceReplayEntry(
        relative_path=_relative(path, package_root),
        source_kind=source_kind,
        expected_sha256=expected_sha256,
        observed_sha256=_sha256(path),
        byte_count=path.stat().st_size,
        passed=True,
    )


def _build_source_replay(package_root: Path) -> PostrunSourceReplayAudit:
    preflight_dir = package_root / PREFLIGHT_DIR
    execution_dir = package_root / EXECUTION_DIR
    preflight = Exact8KRunnerPreflightReport.model_validate(
        _load_canonical_json(preflight_dir / "report.json")
    )
    bound = Exact8KRunnerSourceReplayAudit.model_validate(
        _load_canonical_json(preflight_dir / "source_replay_audit.json")
    )
    if (
        preflight.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or preflight.source_replay_audit_id != bound.audit_id
        or not preflight.exact_8k_execution_authorized
        or _sha256(preflight_dir / "report.json") != EXPECTED_PREFLIGHT_REPORT_SHA256
    ):
        raise ValueError("v26.102 authorizing preflight changed")
    entries = [
        _source_entry(
            path=package_root / item.relative_path,
            package_root=package_root,
            source_kind="v26_100_bound_source",
            expected_sha256=item.expected_sha256,
        )
        for item in bound.entries
    ]
    if len(entries) != EXPECTED_BOUND_SOURCE_COUNT:
        raise ValueError("v26.102 bound source denominator changed")
    preflight_files = sorted(path for path in preflight_dir.iterdir() if path.is_file())
    if len(preflight_files) != EXPECTED_PREFLIGHT_OUTPUT_COUNT:
        raise ValueError("v26.102 preflight output denominator changed")
    detail_hashes = {item.relative_path: item.sha256 for item in preflight.detail_files}
    for path in preflight_files:
        expected = (
            EXPECTED_PREFLIGHT_REPORT_SHA256
            if path.name == "report.json"
            else detail_hashes[path.name]
        )
        entries.append(
            _source_entry(
                path=path,
                package_root=package_root,
                source_kind="v26_100_preflight_output",
                expected_sha256=expected,
            )
        )
    execution_files = sorted(path for path in execution_dir.rglob("*") if path.is_file())
    if len(execution_files) != EXPECTED_EXECUTION_FILE_COUNT:
        raise ValueError("v26.102 execution file denominator changed")
    for path in execution_files:
        entries.append(
            _source_entry(
                path=path,
                package_root=package_root,
                source_kind="v26_101_execution_file",
                expected_sha256=(
                    EXPECTED_EXECUTION_REPORT_SHA256
                    if path.name == "report.json" and path.parent == execution_dir
                    else _sha256(path)
                ),
            )
        )
    source_path = package_root / AUDIT_SOURCE_PATH
    entries.append(
        _source_entry(
            path=source_path,
            package_root=package_root,
            source_kind="v26_102_implementation",
            expected_sha256=_sha256(source_path),
        )
    )
    ordered = tuple(sorted(entries, key=lambda item: item.relative_path))
    provisional = PostrunSourceReplayAudit.model_construct(audit_id="pending", entries=ordered)
    return PostrunSourceReplayAudit(audit_id=source_replay_id(provisional), entries=ordered)


class LoadedExecution(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    preflight: Exact8KRunnerPreflightReport
    source_replay: Exact8KRunnerSourceReplayAudit
    interpretation: Exact8KOutcomeInterpretationContract
    execution_contract: Exact8KExecutionContract
    manifest: Exact8KManifest
    checkpoint: tuple[ThinkingRepairJobResult, ...]
    results: tuple[ThinkingRepairJobResult, ...]
    raw_executions: tuple[Exact8KRawExecution, ...]
    provider_calls: tuple[Exact8KRawProviderCall, ...]
    raw_lineage: Exact8KRawLineageAudit
    report: Exact8KExecutionReport


def _load_execution(package_root: Path) -> LoadedExecution:
    preflight_dir = package_root / PREFLIGHT_DIR
    execution_dir = package_root / EXECUTION_DIR
    preflight = Exact8KRunnerPreflightReport.model_validate(
        _load_canonical_json(preflight_dir / "report.json")
    )
    source_replay = Exact8KRunnerSourceReplayAudit.model_validate(
        _load_canonical_json(execution_dir / "online_source_replay_audit.json")
    )
    interpretation = Exact8KOutcomeInterpretationContract.model_validate(
        _load_canonical_json(preflight_dir / "outcome_interpretation_contract.json")
    )
    execution_contract = Exact8KExecutionContract.model_validate(
        _load_canonical_json(execution_dir / "execution_contract.json")
    )
    manifest = Exact8KManifest.model_validate(
        _load_canonical_json(execution_dir / "frozen_exact_8k_job_manifest.json")
    )
    checkpoint = tuple(
        ThinkingRepairJobResult.model_validate(item)
        for item in _load_canonical_jsonl(execution_dir / "exact_8k_job_results.checkpoint.jsonl")
    )
    result_payload = _load_canonical_json(execution_dir / "exact_8k_job_results.json")
    results = tuple(ThinkingRepairJobResult.model_validate(item) for item in result_payload)
    raw_executions = tuple(
        Exact8KRawExecution.model_validate(_load_canonical_json(path))
        for path in sorted((execution_dir / "raw_execution").glob("*.json"))
    )
    provider_calls = tuple(
        Exact8KRawProviderCall.model_validate(_load_canonical_json(path))
        for path in sorted((execution_dir / "raw_provider_calls").rglob("call_*.json"))
    )
    raw_lineage = Exact8KRawLineageAudit.model_validate(
        _load_canonical_json(execution_dir / "raw_lineage_audit.json")
    )
    report = Exact8KExecutionReport.model_validate(
        _load_canonical_json(execution_dir / "report.json")
    )
    if (
        preflight.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or source_replay.audit_id != preflight.source_replay_audit_id
        or interpretation.contract_id != EXPECTED_INTERPRETATION_ID
        or execution_contract.contract_id != EXPECTED_EXECUTION_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_MANIFEST_ID
        or raw_lineage.audit_id != EXPECTED_RAW_LINEAGE_ID
        or report.report_id != EXPECTED_EXECUTION_REPORT_ID
        or report.raw_lineage_audit_id != raw_lineage.audit_id
    ):
        raise ValueError("v26.102 top-level execution identity changed")
    return LoadedExecution(
        preflight=preflight,
        source_replay=source_replay,
        interpretation=interpretation,
        execution_contract=execution_contract,
        manifest=manifest,
        checkpoint=checkpoint,
        results=results,
        raw_executions=raw_executions,
        provider_calls=provider_calls,
        raw_lineage=raw_lineage,
        report=report,
    )


def _build_execution_lineage(
    package_root: Path,
    loaded: LoadedExecution,
) -> ExecutionLineageAudit:
    execution_dir = package_root / EXECUTION_DIR
    manifest_ids = tuple(item.job_id for item in loaded.manifest.jobs)
    checkpoint_ids = tuple(item.job_id for item in loaded.checkpoint)
    result_ids = tuple(item.job_id for item in loaded.results)
    if manifest_ids != checkpoint_ids or manifest_ids != result_ids:
        raise ValueError("v26.102 checkpoint/result ordering changed")
    raw_by_job = {item.job.job_id: item for item in loaded.raw_executions}
    if tuple(sorted(raw_by_job)) != tuple(sorted(manifest_ids)):
        raise ValueError("v26.102 Raw denominator changed")
    provider_by_id = {item.provider_call_id: item for item in loaded.provider_calls}
    if len(provider_by_id) != EXPECTED_PROVIDER_CALL_COUNT:
        raise ValueError("v26.102 Provider identities are not unique")
    descriptor_passes = 0
    checkpoint_raw_passes = 0
    provider_parent_passes = 0
    for result in loaded.results:
        raw = raw_by_job[result.job_id]
        raw_path = execution_dir / result.raw_execution_artifact.relative_path
        if (
            _sha256(raw_path) != result.raw_execution_artifact.sha256
            or raw_path.stat().st_size != result.raw_execution_artifact.byte_count
        ):
            raise ValueError("v26.102 result-to-Raw binding changed")
        checkpoint_raw_passes += 1
        for descriptor, provider_id in zip(
            raw.provider_call_artifacts,
            raw.provider_call_ids,
            strict=True,
        ):
            provider_path = execution_dir / descriptor.relative_path
            if (
                _sha256(provider_path) != descriptor.sha256
                or provider_path.stat().st_size != descriptor.byte_count
            ):
                raise ValueError("v26.102 Raw-to-Provider descriptor changed")
            descriptor_passes += 1
            provider = provider_by_id[provider_id]
            if (
                provider.job_id != result.job_id
                or provider.artifact_id != json.loads(provider_path.read_bytes())["artifact_id"]
            ):
                raise ValueError("v26.102 Provider parent binding changed")
            provider_parent_passes += 1
    for descriptor in loaded.raw_lineage.files:
        path = execution_dir / descriptor.relative_path
        if _sha256(path) != descriptor.sha256 or path.stat().st_size != descriptor.byte_count:
            raise ValueError("v26.102 persisted Raw Lineage descriptor changed")
    execution_files = sorted(path for path in execution_dir.rglob("*") if path.is_file())
    json_files = [path for path in execution_files if path.suffix == ".json"]
    jsonl_files = [path for path in execution_files if path.suffix == ".jsonl"]
    if len(json_files) != 430 or len(jsonl_files) != 1:
        raise ValueError("v26.102 canonical file partition changed")
    for path in json_files:
        _load_canonical_json(path)
    jsonl_rows = _load_canonical_jsonl(jsonl_files[0])
    payloads = [_load_canonical_json(path) for path in json_files]
    private = sum(_contains_key(item, "reasoning_content") for item in payloads)
    raw_http = sum(_contains_key(item, "raw_http_body") for item in payloads)
    raw_request = sum(_contains_key(item, "raw_request_body") for item in payloads)
    if private or raw_http or raw_request:
        raise ValueError("v26.102 prohibited private payload key observed")
    values = {
        "checkpoint_job_count": len(loaded.checkpoint),
        "result_job_count": len(loaded.results),
        "raw_execution_count": len(loaded.raw_executions),
        "provider_artifact_count": len(loaded.provider_calls),
        "unique_provider_call_id_count": len(provider_by_id),
        "raw_descriptor_count": len(loaded.raw_lineage.files),
        "raw_descriptor_hash_pass_count": len(loaded.raw_lineage.files),
        "canonical_json_file_count": len(json_files),
        "canonical_json_file_pass_count": len(json_files),
        "canonical_jsonl_row_count": len(jsonl_rows),
        "canonical_jsonl_row_pass_count": len(jsonl_rows),
        "checkpoint_final_result_match_count": sum(
            left.model_dump(mode="json") == right.model_dump(mode="json")
            for left, right in zip(loaded.checkpoint, loaded.results, strict=True)
        ),
        "checkpoint_raw_binding_pass_count": checkpoint_raw_passes,
        "manifest_job_identity_match_count": len(manifest_ids),
        "provider_parent_binding_pass_count": provider_parent_passes,
        "all_provider_calls_dynamically_precertified": all(
            item.all_certificates_constructed_before_provider_call for item in loaded.provider_calls
        ),
        "all_provider_calls_exact_8k_request_bound": all(
            item.request_max_tokens == 8192
            and item.request_binding_certificate.request_max_tokens == 8192
            for item in loaded.provider_calls
        ),
        "private_reasoning_payload_count": private,
        "raw_http_body_payload_count": raw_http,
        "raw_request_body_payload_count": raw_request,
    }
    provisional = ExecutionLineageAudit.model_construct(audit_id="pending", **values)
    return ExecutionLineageAudit(audit_id=execution_lineage_id(provisional), **values)


def _telemetry_payload(item: Exact8KRawProviderCall) -> dict[str, Any]:
    return item.provider_telemetry.model_dump(mode="json")


def _required_usage(telemetry: ModelCallTelemetry) -> tuple[int, int, int, int, int]:
    prompt_tokens = telemetry.prompt_tokens
    completion_tokens = telemetry.completion_tokens
    total_tokens = telemetry.total_tokens
    reasoning_tokens = telemetry.reasoning_tokens
    reasoning_content_length = telemetry.reasoning_content_length
    if (
        prompt_tokens is None
        or completion_tokens is None
        or total_tokens is None
        or reasoning_tokens is None
        or reasoning_content_length is None
    ):
        raise ValueError("v26.102 Provider Usage or Thinking telemetry is incomplete")
    return (
        prompt_tokens,
        completion_tokens,
        total_tokens,
        reasoning_tokens,
        reasoning_content_length,
    )


def _build_provider_telemetry(loaded: LoadedExecution) -> ProviderTelemetryAudit:
    calls = loaded.provider_calls
    telemetry = [item.provider_telemetry for item in calls]
    payloads = [_telemetry_payload(item) for item in calls]
    response_models = [item.get("response_model") for item in payloads]
    native = [
        bool(item.get("response_shape", {}).get("provider_native_tool_call_observed"))
        for item in payloads
    ]
    preparse = [
        bool(item.get("response_shape", {}).get("response_envelope_captured_before_content_parse"))
        for item in payloads
    ]
    usage = [_required_usage(item) for item in telemetry]
    prompt_tokens = [item[0] for item in usage]
    completion_tokens = [item[1] for item in usage]
    total_tokens = [item[2] for item in usage]
    reasoning_tokens = [item[3] for item in usage]
    reasoning_content_lengths = [item[4] for item in usage]
    overruns = [
        completion - item.request_max_tokens
        for item, completion in zip(calls, completion_tokens, strict=True)
    ]
    values = {
        "provider_call_count": len(calls),
        "http_success_call_count": sum(item.http_success for item in telemetry),
        "exact_requested_model_count": sum(
            item.model_requested == "deepseek-v4-flash" for item in telemetry
        ),
        "exact_selected_model_count": sum(
            item.model_selected == "deepseek-v4-flash" for item in telemetry
        ),
        "exact_response_model_count": sum(item == "deepseek-v4-flash" for item in response_models),
        "fallback_count": sum(item.fallback_used for item in telemetry),
        "provider_native_tool_call_count": sum(native),
        "model_discovery_call_count": sum(item.discovery_attempted for item in telemetry),
        "usage_complete_count": sum(
            prompt >= 0 and completion >= 0 and total == prompt + completion
            for prompt, completion, total, _, _ in usage
        ),
        "thinking_telemetry_complete_count": sum(
            item.reasoning_content_present and usage_row[4] > 0 and usage_row[3] > 0
            for item, usage_row in zip(telemetry, usage, strict=True)
        ),
        "response_envelope_preparse_count": sum(preparse),
        "exact_8k_request_certificate_count": sum(
            item.request_binding_certificate.request_max_tokens == 8192 for item in calls
        ),
        "dynamic_precall_certificate_count": sum(
            item.dynamic_certificate.provider_invocation_authorized_after_certificate
            for item in calls
        ),
        "primary_provider_call_count": sum(item.phase == "primary" for item in calls),
        "rescue_provider_call_count": sum(item.phase == "rescue" for item in calls),
        "provider_total_tokens": sum(total_tokens),
        "prompt_tokens_total": sum(prompt_tokens),
        "completion_tokens_total": sum(completion_tokens),
        "reasoning_tokens_total": sum(reasoning_tokens),
        "reasoning_content_length_total": sum(reasoning_content_lengths),
        "estimated_cost_usd": format(
            sum((Decimal(item.estimated_cost_usd) for item in loaded.results), Decimal("0")),
            "f",
        ),
        "completion_usage_within_request_bound_count": sum(value <= 0 for value in overruns),
        "completion_usage_over_request_bound_count": sum(value > 0 for value in overruns),
        "maximum_completion_usage_tokens": max(completion_tokens),
        "maximum_request_bound_tokens": max(item.request_max_tokens for item in calls),
        "maximum_observed_overrun_tokens": max(overruns),
        "private_reasoning_payload_count": sum(
            _contains_key(item.model_dump(mode="json"), "reasoning_content") for item in calls
        ),
        "private_reasoning_hash_count": sum(
            item.private_reasoning_content_hashed for item in calls
        ),
        "raw_http_body_payload_count": sum(item.raw_http_body_persisted for item in calls),
        "raw_request_body_payload_count": sum(item.raw_request_body_persisted for item in calls),
    }
    provisional = ProviderTelemetryAudit.model_construct(audit_id="pending", **values)
    return ProviderTelemetryAudit(audit_id=provider_telemetry_id(provisional), **values)


def _build_completion_outcome(loaded: LoadedExecution) -> CompletionOutcomeAudit:
    results = loaded.results
    raw = loaded.raw_executions
    terminals = dict(Counter(item.terminal_category for item in results))
    failure_counts: Counter[str] = Counter()
    for item in results:
        failure_counts.update(item.completion_failure_counts)
    computed_completion_cp = _cp_upper(28, 32)
    computed_no_call_cp = _cp_upper(0, 32)
    values = {
        "terminal_counts": terminals,
        "completion_unusable_job_count": sum(item.completion_unusable for item in results),
        "instrument_failure_job_count": sum(
            item.terminal_category == "instrument_failure" for item in results
        ),
        "model_valid_trajectory_count": sum(
            item.terminal_category == "model_valid_trajectory" for item in results
        ),
        "typed_no_call_job_count": sum(item.typed_no_call for item in results),
        "provider_transport_failure_job_count": sum(
            item.provider_transport_failure for item in results
        ),
        "completion_failure_counts": dict(sorted(failure_counts.items())),
        "completion_failure_call_count": sum(failure_counts.values()),
        "rescue_attempt_job_count": sum(item.rescue_attempt_count for item in raw),
        "rescue_provider_call_job_count": sum(item.rescue_provider_call_count for item in raw),
        "completion_unusable_cp95_upper_32": loaded.report.completion_unusable_cp95_upper_32,
        "typed_no_call_cp95_upper_32": loaded.report.typed_no_call_cp95_upper_32,
        "program_closed_count": sum(item.program_closed for item in results),
        "mechanism_success_count": sum(item.mechanism_success for item in results),
        "independently_valid_trajectory_count": sum(item.independent_validity for item in results),
        "requested_path_adherence_count": sum(item.requested_path_adhered for item in results),
    }
    if (
        abs(loaded.report.completion_unusable_cp95_upper_32 - computed_completion_cp) > 1e-15
        or abs(loaded.report.typed_no_call_cp95_upper_32 - computed_no_call_cp) > 1e-15
    ):
        raise ValueError("v26.102 Clopper-Pearson replay changed")
    provisional = CompletionOutcomeAudit.model_construct(audit_id="pending", **values)
    return CompletionOutcomeAudit(audit_id=completion_outcome_id(provisional), **values)


def _build_root_cause(loaded: LoadedExecution) -> InstrumentRootCauseAudit:
    overrun_calls = [
        item
        for item in loaded.provider_calls
        if _required_usage(item.provider_telemetry)[1] > item.request_max_tokens
    ]
    instrument_results = [
        item for item in loaded.results if item.terminal_category == "instrument_failure"
    ]
    instrument_raw = [
        item for item in loaded.raw_executions if item.terminal_disposition == "instrument_failure"
    ]
    if len(overrun_calls) != 1 or len(instrument_results) != 1 or len(instrument_raw) != 1:
        raise ValueError("v26.102 Instrument root-cause denominator changed")
    call = overrun_calls[0]
    result = instrument_results[0]
    raw = instrument_raw[0]
    telemetry = _telemetry_payload(call)
    response_shape = telemetry["response_shape"]
    envelope = response_shape["redacted_response_envelope"]
    final_attempt = raw.request_attempts[-1]
    if (
        result.job_id != EXPECTED_INSTRUMENT_JOB_ID
        or call.job_id != result.job_id
        or call.provider_call_id != EXPECTED_OVERRUN_PROVIDER_CALL_ID
        or raw.job.job_id != result.job_id
        or raw.provider_budget_audit.contract_failure_ids
        != ("resource_budget:completion_upper_bound_respected",)
        or final_attempt.phase != "rescue"
        or final_attempt.provider_call_made
        or final_attempt.error != "ValueError: v26.100 cannot prepare after a terminal budget state"
    ):
        raise ValueError("v26.102 Instrument root-cause lineage changed")
    prompt_tokens, completion_tokens, total_tokens, reasoning_tokens, _ = _required_usage(
        call.provider_telemetry
    )
    values = {
        "request_certificate_max_tokens": call.request_binding_certificate.request_max_tokens,
        "dynamic_certificate_completion_bound": (
            call.dynamic_certificate.completion_upper_bound_tokens
        ),
        "provider_budget_completion_bound": next(
            item.completion_token_upper_bound
            for item in raw.provider_budget_audit.certificates
            if item.request_index == call.call_index
        ),
        "provider_reported_completion_tokens": completion_tokens,
        "provider_reported_reasoning_tokens": reasoning_tokens,
        "provider_reported_prompt_tokens": prompt_tokens,
        "provider_reported_total_tokens": total_tokens,
        "provider_reported_overrun_tokens": completion_tokens - call.request_max_tokens,
        "public_content_length": envelope["public_content_length"],
        "failure_type": call.failure_artifact.failure_type if call.failure_artifact else None,
        "exact_model_requested_selected_returned": (
            call.provider_telemetry.model_requested == "deepseek-v4-flash"
            and call.provider_telemetry.model_selected == "deepseek-v4-flash"
            and call.provider_telemetry.response_model == "deepseek-v4-flash"
        ),
        "fallback_absent": not call.provider_telemetry.fallback_used,
        "response_envelope_captured_before_content_parse": response_shape[
            "response_envelope_captured_before_content_parse"
        ],
        "response_envelope_schema_valid": response_shape["response_envelope_schema_valid"],
        "other_provider_calls_within_bound_count": sum(
            _required_usage(item.provider_telemetry)[1] <= item.request_max_tokens
            for item in loaded.provider_calls
        ),
        "other_budget_contract_failure_count": sum(
            bool(item.provider_budget_audit.contract_failure_ids)
            for item in loaded.raw_executions
            if item.job.job_id != result.job_id
        ),
    }
    provisional = InstrumentRootCauseAudit.model_construct(audit_id="pending", **values)
    return InstrumentRootCauseAudit(audit_id=instrument_root_cause_id(provisional), **values)


def _build_transition(root_cause: InstrumentRootCauseAudit) -> ProspectiveTransitionContract:
    values = {"predecessor_root_cause_audit_id": root_cause.audit_id}
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=transition_contract_id(provisional),
        **values,
    )


def _audit_gate(payload: dict[str, Any]) -> None:
    required = {
        "job_count": 32,
        "provider_count": 391,
        "completion_unusable": 28,
        "instrument_failures": 1,
        "overrun_count": 1,
        "overrun_tokens": 1,
        "request_max_tokens": 8192,
        "reported_completion_tokens": 8193,
        "thinking_type": "enabled",
        "exact_model": "deepseek-v4-flash",
        "private_payload_count": 0,
        "raw_http_body_count": 0,
        "raw_request_body_count": 0,
        "historical_reclassification_count": 0,
        "historical_rerun_count": 0,
        "automatic_16k": False,
        "direct_16k_execution": False,
        "semantic_rescue": False,
        "actual_usage_charged": True,
        "prospective_margin_tokens": 1,
        "reject_margin_two_or_more": True,
        "next_stage": NEXT_STAGE,
    }
    if payload != required:
        raise ValueError("v26.102 destructive audit Gate rejected a mutation")


def _build_destructive() -> DestructiveAudit:
    baseline: dict[str, Any] = {
        "job_count": 32,
        "provider_count": 391,
        "completion_unusable": 28,
        "instrument_failures": 1,
        "overrun_count": 1,
        "overrun_tokens": 1,
        "request_max_tokens": 8192,
        "reported_completion_tokens": 8193,
        "thinking_type": "enabled",
        "exact_model": "deepseek-v4-flash",
        "private_payload_count": 0,
        "raw_http_body_count": 0,
        "raw_request_body_count": 0,
        "historical_reclassification_count": 0,
        "historical_rerun_count": 0,
        "automatic_16k": False,
        "direct_16k_execution": False,
        "semantic_rescue": False,
        "actual_usage_charged": True,
        "prospective_margin_tokens": 1,
        "reject_margin_two_or_more": True,
        "next_stage": NEXT_STAGE,
    }
    mutations: dict[str, tuple[str, Any]] = {
        "allow_automatic_16k_escalation": ("automatic_16k", True),
        "allow_direct_16k_execution": ("direct_16k_execution", True),
        "allow_historical_job_rerun": ("historical_rerun_count", 1),
        "change_exact_model": ("exact_model", "deepseek-v4-pro"),
        "change_historical_request_bound": ("request_max_tokens", 16384),
        "disable_thinking": ("thinking_type", "disabled"),
        "drop_one_job": ("job_count", 31),
        "drop_one_provider_artifact": ("provider_count", 390),
        "hide_instrument_failure": ("instrument_failures", 0),
        "hide_provider_overrun": ("overrun_count", 0),
        "persist_private_reasoning": ("private_payload_count", 1),
        "persist_raw_http_body": ("raw_http_body_count", 1),
        "persist_raw_request_body": ("raw_request_body_count", 1),
        "reclassify_historical_terminal": ("historical_reclassification_count", 1),
        "relax_future_margin_to_two": ("prospective_margin_tokens", 2),
        "remove_completion_failures": ("completion_unusable", 0),
        "report_completion_at_request_bound": ("reported_completion_tokens", 8192),
        "rescue_completion_with_semantics": ("semantic_rescue", True),
        "stop_charging_actual_provider_usage": ("actual_usage_charged", False),
        "weaken_margin_rejection": ("reject_margin_two_or_more", False),
    }
    rows = []
    for name, (field, value) in sorted(mutations.items()):
        changed = dict(baseline)
        changed[field] = value
        try:
            _audit_gate(changed)
        except ValueError:
            provisional = MutationResult.model_construct(
                mutation_id="pending",
                mutation=name,
            )
            rows.append(
                MutationResult(
                    mutation_id=mutation_result_id(provisional),
                    mutation=name,
                )
            )
        else:
            raise ValueError(f"v26.102 destructive mutation passed: {name}")
    values = {"mutation_results": tuple(rows)}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(audit_id=destructive_audit_id(provisional), **values)


def _detail_file(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def _implementation_source(package_root: Path) -> ImplementationSourceFile:
    path = package_root / AUDIT_SOURCE_PATH
    return ImplementationSourceFile(
        relative_path=AUDIT_SOURCE_PATH,
        sha256=_sha256(path),
    )


def build_thinking_8k_completion_calibration_postrun_audit(
    *,
    output_dir: Path,
    package_root: Path,
) -> PostrunAuditReport:
    source = _build_source_replay(package_root)
    loaded = _load_execution(package_root)
    lineage = _build_execution_lineage(package_root, loaded)
    provider = _build_provider_telemetry(loaded)
    completion = _build_completion_outcome(loaded)
    root_cause = _build_root_cause(loaded)
    transition = _build_transition(root_cause)
    destructive = _build_destructive()
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source),
        ("execution_lineage_audit.json", lineage),
        ("provider_telemetry_audit.json", provider),
        ("completion_outcome_audit.json", completion),
        ("instrument_root_cause_audit.json", root_cause),
        ("prospective_transition_contract.json", transition),
        ("destructive_audit.json", destructive),
    )
    for filename, artifact in outputs:
        _write_json(output_dir / filename, artifact.model_dump(mode="json"))
    details = tuple(
        sorted(
            (_detail_file(output_dir / filename, output_dir) for filename, _ in outputs),
            key=lambda item: item.relative_path,
        )
    )
    values = {
        "source_replay_audit_id": source.audit_id,
        "execution_lineage_audit_id": lineage.audit_id,
        "provider_telemetry_audit_id": provider.audit_id,
        "completion_outcome_audit_id": completion.audit_id,
        "instrument_root_cause_audit_id": root_cause.audit_id,
        "prospective_transition_contract_id": transition.contract_id,
        "destructive_audit_id": destructive.audit_id,
        "detail_files": details,
        "implementation_source_files": (_implementation_source(package_root),),
    }
    provisional = PostrunAuditReport.model_construct(report_id="pending", **values)
    report = PostrunAuditReport(report_id=postrun_report_id(provisional), **values)
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit the completed v26.101 exact-8K calibration without generation"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    args = parser.parse_args()
    report = build_thinking_8k_completion_calibration_postrun_audit(
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
