from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    ImplementationSourceFile,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501
    ThinkingRepairExecutionContract,
    ThinkingRepairExecutionPreflightReport,
    ThinkingRepairJobResult,
    ThinkingRepairRawExecution,
    ThinkingRepairRawProviderCall,
    ThinkingRepairRunnerSourceReplayAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_preflight import (  # noqa: E501
    ThinkingRepairManifest,
    ThinkingRepairPathAudit,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID = "finance_v26_96_thinking_repair_execution_failure_audit_v2_20260821"
EXPECTED_PREFLIGHT_REPORT_ID = (
    "finance_v26_thinking_repair_execution_preflight_report:"
    "986591ddd3b7251cf183f52193bc3868ccec52816cb83715585d76fd4ef07ca5"
)
EXPECTED_EXECUTION_CONTRACT_ID = (
    "finance_v26_thinking_repair_execution_contract:"
    "78e40804aa6fa489223991a40bd84c68935a1b4ce8aa0de311e2663538a469b2"
)
EXPECTED_SOURCE_REPLAY_ID = (
    "finance_v26_thinking_repair_runner_replay:"
    "3481b564d08122b4164f6e317cd3d29fff695f6ca5bae6642eaa49527814bb1a"
)
EXPECTED_MANIFEST_ID = (
    "finance_v26_thinking_repair_manifest:"
    "56ada3c9430d56c20c6611986cc0fa51f19c3f80fbee3b7b63b07dffddcf5945"
)
EXPECTED_REPAIR_CONTRACT_ID = (
    "finance_v26_thinking_repair_contract:"
    "573eb1493ad87832eade20407db775b093a7c4168c63bf19113ee5ceb4dd4f72"
)
EXPECTED_FAILURE_JOB_ID = (
    "finance_v26_thinking_repair_job:"
    "9fa6a03e7f9e692a0f14bc9488d84016a9510c79d79260ca4d104996c1064b19"
)

PREFLIGHT_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_95_thinking_completion_telemetry_repair_execution_preflight_v1_20260821"
)
EXECUTION_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_95_thinking_completion_telemetry_repair_execution_v1_20260821"
)
V26_94_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821"
)
AUDIT_SOURCE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_repair_execution_failure_audit.py"
)

EXPECTED_BOUND_SOURCE_COUNT: Literal[498] = 498
EXPECTED_PREFLIGHT_OUTPUT_COUNT: Literal[7] = 7
EXPECTED_FAILED_EXECUTION_FILE_COUNT: Literal[217] = 217
EXPECTED_SOURCE_REPLAY_COUNT: Literal[723] = 723
EXPECTED_JOB_COUNT: Literal[32] = 32
EXPECTED_CHECKPOINT_COUNT: Literal[19] = 19
EXPECTED_RAW_COUNT: Literal[27] = 27
EXPECTED_RAW_UNCHECKPOINTED_COUNT: Literal[8] = 8
EXPECTED_PROVIDER_ORPHAN_COUNT: Literal[1] = 1
EXPECTED_UNOPENED_COUNT: Literal[4] = 4
EXPECTED_EXPOSED_COUNT: Literal[28] = 28
EXPECTED_PROVIDER_CALL_COUNT: Literal[184] = 184
EXPECTED_RAW_PROVIDER_CALL_COUNT: Literal[176] = 176
EXPECTED_ORPHAN_PROVIDER_CALL_COUNT: Literal[8] = 8
EXPECTED_PROVIDER_TOTAL_TOKENS: Literal[775292] = 775_292
EXPECTED_REASONING_TOKENS: Literal[433062] = 433_062
EXPECTED_COMPLETION_TOKENS: Literal[444089] = 444_089
EXPECTED_ESTIMATED_COST = "0.16411017840000001316"

SOURCE_VERSION = "finance_v26_thinking_repair_failure_source_replay.v1"
EXPOSURE_ROW_VERSION = "finance_v26_thinking_repair_exposure_row.v1"
LINEAGE_VERSION = "finance_v26_thinking_repair_failed_lineage.v1"
PROVIDER_VERSION = "finance_v26_thinking_repair_failed_provider_telemetry.v1"
COMPLETION_VERSION = "finance_v26_thinking_repair_completion_lower_bound.v1"
ROOT_CAUSE_VERSION = "finance_v26_thinking_repair_instrument_root_cause.v1"
TRANSITION_VERSION = "finance_v26_thinking_repair_failure_transition.v1"
MUTATION_VERSION = "finance_v26_thinking_repair_failure_mutation.v1"
DESTRUCTIVE_VERSION = "finance_v26_thinking_repair_failure_destructive.v1"
REPORT_VERSION = "finance_v26_thinking_repair_failure_audit_report.v1"

ExposureState = Literal[
    "checkpoint",
    "raw_uncheckpointed",
    "provider_orphan",
    "unopened",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_95_bound_source",
        "v26_95_preflight_output",
        "failed_execution_file",
        "v26_96_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> SourceReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("v26.96 source replay changed")
        return self


class FailureSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    entries: tuple[SourceReplayEntry, ...] = Field(
        min_length=EXPECTED_SOURCE_REPLAY_COUNT,
        max_length=EXPECTED_SOURCE_REPLAY_COUNT,
    )
    bound_source_file_count: Literal[498] = EXPECTED_BOUND_SOURCE_COUNT
    preflight_output_file_count: Literal[7] = EXPECTED_PREFLIGHT_OUTPUT_COUNT
    failed_execution_file_count: Literal[217] = EXPECTED_FAILED_EXECUTION_FILE_COUNT
    audit_implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[723] = EXPECTED_SOURCE_REPLAY_COUNT
    replay_pass_count: Literal[723] = EXPECTED_SOURCE_REPLAY_COUNT
    replay_before_diagnostics: Literal[True] = True
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_thinking_repair_failure_source_replay.v1"] = (
        "finance_v26_thinking_repair_failure_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FailureSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.96 source paths are not canonical")
        if self.replayed_file_count != len(self.entries):
            raise ValueError("v26.96 source denominator changed")
        if self.audit_id != source_replay_audit_id(self):
            raise ValueError("v26.96 source replay identity changed")
        return self


class JobExposureRow(FrozenModel):
    row_id: str = Field(min_length=1)
    manifest_index: int = Field(ge=0, lt=EXPECTED_JOB_COUNT)
    job_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: str = Field(min_length=1)
    state: ExposureState
    checkpoint_present: bool
    raw_execution_present: bool
    provider_call_count: int = Field(ge=0)
    model_exposed: bool
    eligible_for_automatic_retry: Literal[False] = False
    historical_result_reclassified: Literal[False] = False
    schema_version: Literal["finance_v26_thinking_repair_exposure_row.v1"] = (
        "finance_v26_thinking_repair_exposure_row.v1"
    )

    @model_validator(mode="after")
    def validate_row(self) -> JobExposureRow:
        expected = (
            "checkpoint"
            if self.checkpoint_present
            else "raw_uncheckpointed"
            if self.raw_execution_present
            else "provider_orphan"
            if self.provider_call_count
            else "unopened"
        )
        if self.state != expected:
            raise ValueError("v26.96 exposure state changed")
        if self.model_exposed != (self.provider_call_count > 0):
            raise ValueError("v26.96 exposure flag changed")
        if self.row_id != exposure_row_id(self):
            raise ValueError("v26.96 exposure row identity changed")
        return self


class FailedExecutionLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    rows: tuple[JobExposureRow, ...] = Field(
        min_length=EXPECTED_JOB_COUNT,
        max_length=EXPECTED_JOB_COUNT,
    )
    manifest_job_count: Literal[32] = EXPECTED_JOB_COUNT
    checkpoint_job_count: Literal[19] = EXPECTED_CHECKPOINT_COUNT
    raw_execution_count: Literal[27] = EXPECTED_RAW_COUNT
    raw_uncheckpointed_job_count: Literal[8] = EXPECTED_RAW_UNCHECKPOINTED_COUNT
    provider_orphan_job_count: Literal[1] = EXPECTED_PROVIDER_ORPHAN_COUNT
    unopened_job_count: Literal[4] = EXPECTED_UNOPENED_COUNT
    exposed_job_count: Literal[28] = EXPECTED_EXPOSED_COUNT
    provider_artifact_count: Literal[184] = EXPECTED_PROVIDER_CALL_COUNT
    unique_provider_call_id_count: Literal[184] = EXPECTED_PROVIDER_CALL_COUNT
    raw_bound_provider_artifact_count: Literal[176] = EXPECTED_RAW_PROVIDER_CALL_COUNT
    orphan_provider_artifact_count: Literal[8] = EXPECTED_ORPHAN_PROVIDER_CALL_COUNT
    checkpoint_result_schema_pass_count: Literal[19] = EXPECTED_CHECKPOINT_COUNT
    raw_execution_schema_pass_count: Literal[27] = EXPECTED_RAW_COUNT
    provider_artifact_schema_pass_count: Literal[184] = EXPECTED_PROVIDER_CALL_COUNT
    canonical_json_file_pass_count: Literal[211] = 211
    canonical_jsonl_row_pass_count: Literal[20] = 20
    raw_descriptor_hash_pass_count: Literal[176] = EXPECTED_RAW_PROVIDER_CALL_COUNT
    checkpoint_raw_binding_pass_count: Literal[19] = EXPECTED_CHECKPOINT_COUNT
    failure_checkpoint_count: Literal[1] = 1
    failure_job_id: str = EXPECTED_FAILURE_JOB_ID
    runner_process_exited: Literal[True] = True
    completed_report_materialized: Literal[False] = False
    historical_job_rerun_count: Literal[0] = 0
    historical_result_reclassification_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_thinking_repair_failed_lineage.v1"] = (
        "finance_v26_thinking_repair_failed_lineage.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FailedExecutionLineageAudit:
        if tuple(item.manifest_index for item in self.rows) != tuple(range(EXPECTED_JOB_COUNT)):
            raise ValueError("v26.96 manifest ordering changed")
        counts = Counter(item.state for item in self.rows)
        expected = {
            "checkpoint": EXPECTED_CHECKPOINT_COUNT,
            "raw_uncheckpointed": EXPECTED_RAW_UNCHECKPOINTED_COUNT,
            "provider_orphan": EXPECTED_PROVIDER_ORPHAN_COUNT,
            "unopened": EXPECTED_UNOPENED_COUNT,
        }
        if dict(counts) != expected:
            raise ValueError("v26.96 exposure partition changed")
        if self.audit_id != failed_lineage_audit_id(self):
            raise ValueError("v26.96 lineage identity changed")
        return self


class FailedProviderTelemetryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    provider_artifact_count: Literal[184] = EXPECTED_PROVIDER_CALL_COUNT
    unique_provider_call_id_count: Literal[184] = EXPECTED_PROVIDER_CALL_COUNT
    http_success_call_count: Literal[184] = EXPECTED_PROVIDER_CALL_COUNT
    exact_requested_model_call_count: Literal[184] = EXPECTED_PROVIDER_CALL_COUNT
    exact_selected_model_call_count: Literal[184] = EXPECTED_PROVIDER_CALL_COUNT
    exact_response_model_call_count: Literal[184] = EXPECTED_PROVIDER_CALL_COUNT
    missing_response_model_call_count: Literal[0] = 0
    fallback_call_count: Literal[0] = 0
    native_tool_call_count: Literal[0] = 0
    positive_thinking_telemetry_call_count: Literal[184] = EXPECTED_PROVIDER_CALL_COUNT
    complete_usage_call_count: Literal[184] = EXPECTED_PROVIDER_CALL_COUNT
    primary_call_count: Literal[156] = 156
    rescue_call_count: Literal[28] = 28
    decision_call_count: Literal[184] = EXPECTED_PROVIDER_CALL_COUNT
    final_answer_call_count: Literal[0] = 0
    public_json_payload_call_count: Literal[134] = 134
    reasoning_only_length_truncation_call_count: Literal[48] = 48
    length_truncated_content_call_count: Literal[2] = 2
    provider_total_tokens: Literal[775292] = EXPECTED_PROVIDER_TOTAL_TOKENS
    reasoning_tokens: Literal[433062] = EXPECTED_REASONING_TOKENS
    completion_tokens: Literal[444089] = EXPECTED_COMPLETION_TOKENS
    estimated_cost_usd: str = EXPECTED_ESTIMATED_COST
    private_reasoning_payload_count: Literal[0] = 0
    raw_http_body_count: Literal[0] = 0
    transport_failure_count: Literal[0] = 0
    response_model_mismatch_count: Literal[0] = 0
    telemetry_integrity_passed: Literal[True] = True
    usage_accounting_complete: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_thinking_repair_failed_provider_telemetry.v1"] = (
        "finance_v26_thinking_repair_failed_provider_telemetry.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FailedProviderTelemetryAudit:
        if self.primary_call_count + self.rescue_call_count != self.provider_artifact_count:
            raise ValueError("v26.96 Provider phase denominator changed")
        if (
            self.public_json_payload_call_count
            + self.reasoning_only_length_truncation_call_count
            + self.length_truncated_content_call_count
            != self.provider_artifact_count
        ):
            raise ValueError("v26.96 Provider outcome denominator changed")
        if self.audit_id != provider_telemetry_audit_id(self):
            raise ValueError("v26.96 Provider audit identity changed")
        return self


class CompletionLowerBoundAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    manifest_job_count: Literal[32] = EXPECTED_JOB_COUNT
    exact_denominator_completed: Literal[False] = False
    complete_raw_job_count: Literal[27] = EXPECTED_RAW_COUNT
    complete_raw_completion_unusable_count: Literal[27] = EXPECTED_RAW_COUNT
    checkpoint_completion_unusable_count: Literal[19] = EXPECTED_CHECKPOINT_COUNT
    raw_uncheckpointed_completion_unusable_count: Literal[8] = EXPECTED_RAW_UNCHECKPOINTED_COUNT
    formal_completion_unusable_lower_bound_count: Literal[27] = EXPECTED_RAW_COUNT
    maximum_remaining_nonfailure_job_count: Literal[5] = 5
    zero_failure_gate_threshold: float = 0.10
    zero_failure_gate_requires_zero_failures: Literal[True] = True
    completion_gate_can_still_pass: Literal[False] = False
    exact_denominator_clopper_pearson_reported: Literal[False] = False
    raw_provider_call_count: Literal[176] = EXPECTED_RAW_PROVIDER_CALL_COUNT
    raw_logical_request_count: Literal[149] = 149
    raw_request_attempt_count: Literal[176] = EXPECTED_RAW_PROVIDER_CALL_COUNT
    raw_primary_attempt_count: Literal[149] = 149
    raw_rescue_attempt_count: Literal[27] = EXPECTED_RAW_COUNT
    raw_observation_count: Literal[122] = 122
    raw_completed_result_count: Literal[0] = 0
    raw_budget_pass_count: Literal[27] = EXPECTED_RAW_COUNT
    raw_typed_no_call_count: Literal[0] = 0
    raw_reasoning_only_failure_count: Literal[46] = 46
    raw_length_truncated_failure_count: Literal[2] = 2
    raw_invalid_response_contract_failure_count: Literal[6] = 6
    terminal_reasoning_only_count: Literal[24] = 24
    terminal_length_truncated_count: Literal[1] = 1
    terminal_invalid_response_contract_count: Literal[2] = 2
    raw_rescue_reduction_minimum_basis_points: Literal[1055] = 1055
    raw_rescue_reduction_maximum_basis_points: Literal[3243] = 3243
    orphan_primary_reasoning_only_truncation_observed: Literal[True] = True
    orphan_rescue_reasoning_only_truncation_observed: Literal[True] = True
    orphan_job_terminal_reclassified: Literal[False] = False
    incomplete_denominator_behavior_diagnostics_authorizing: Literal[False] = False
    same_bound_prompt_only_retuning_allowed: Literal[False] = False
    status: Literal["failed"] = "failed"
    schema_version: Literal["finance_v26_thinking_repair_completion_lower_bound.v1"] = (
        "finance_v26_thinking_repair_completion_lower_bound.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CompletionLowerBoundAudit:
        if (
            self.complete_raw_completion_unusable_count
            != self.formal_completion_unusable_lower_bound_count
            or self.formal_completion_unusable_lower_bound_count < 1
        ):
            raise ValueError("v26.96 Completion lower bound changed")
        if self.audit_id != completion_lower_bound_audit_id(self):
            raise ValueError("v26.96 Completion audit identity changed")
        return self


class InstrumentRootCauseAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    failure_job_id: str = EXPECTED_FAILURE_JOB_ID
    failure_mechanism_id: Literal["state_dependent_stopping"] = "state_dependent_stopping"
    failure_path_strategy_id: Literal["search_then_open"] = "search_then_open"
    failure_logical_request_index: Literal[6] = 6
    primary_provider_call_index: Literal[6] = 6
    rescue_provider_call_index: Literal[7] = 7
    registered_request_count: Literal[7] = 7
    registered_request_kind: Literal["final_answer"] = "final_answer"
    online_request_kind: Literal["decision"] = "decision"
    registered_primary_prompt_utf8_bytes: Literal[2865] = 2865
    registered_maximum_rescue_prompt_utf8_bytes: Literal[1609] = 1609
    registered_minimum_rescue_reduction_basis_points: Literal[4383] = 4383
    online_primary_prompt_utf8_bytes: Literal[7914] = 7914
    online_rescue_prompt_utf8_bytes: Literal[7176] = 7176
    online_rescue_reduction_bytes: Literal[738] = 738
    online_rescue_reduction_basis_points: Literal[932] = 932
    frozen_minimum_reduction_basis_points: Literal[1000] = 1000
    reduction_shortfall_basis_points: Literal[68] = 68
    primary_matches_registered_hash: Literal[False] = False
    request_kind_matches_registered: Literal[False] = False
    primary_finish_reason: Literal["length"] = "length"
    rescue_finish_reason: Literal["length"] = "length"
    primary_reasoning_tokens: Literal[4096] = 4096
    rescue_reasoning_tokens: Literal[4096] = 4096
    primary_failure_type: Literal["reasoning_only_length_truncation"] = (
        "reasoning_only_length_truncation"
    )
    rescue_failure_type: Literal["reasoning_only_length_truncation"] = (
        "reasoning_only_length_truncation"
    )
    rescue_http_success_before_gate_failure: Literal[True] = True
    rescue_provider_artifact_persisted_before_gate_failure: Literal[True] = True
    reduction_computed_after_provider_call: Literal[True] = True
    dynamic_request_kind_precall_gate_present: Literal[False] = False
    dynamic_reduction_precall_gate_present: Literal[False] = False
    complete_raw_registered_request_absent_count: Literal[5] = 5
    complete_raw_registered_kind_mismatch_count: Literal[8] = 8
    complete_raw_registered_primary_hash_mismatch_count: Literal[105] = 105
    complete_raw_job_with_kind_mismatch_count: Literal[8] = 8
    complete_raw_job_with_hash_mismatch_count: Literal[26] = 26
    v26_94_registered_compiler_claim_retained: Literal[True] = True
    v26_94_arbitrary_online_state_coverage_claimed: Literal[False] = False
    root_cause: Literal["dynamic_off_path_rescue_contract_not_precall_closed"] = (
        "dynamic_off_path_rescue_contract_not_precall_closed"
    )
    provider_transport_root_cause: Literal[False] = False
    provider_telemetry_root_cause: Literal[False] = False
    provider_budget_root_cause: Literal[False] = False
    model_identity_root_cause: Literal[False] = False
    instrument_failure_confirmed: Literal[True] = True
    historical_execution_report_materialized: Literal[False] = False
    historical_execution_result_reclassified: Literal[False] = False
    status: Literal["failed"] = "failed"
    schema_version: Literal["finance_v26_thinking_repair_instrument_root_cause.v1"] = (
        "finance_v26_thinking_repair_instrument_root_cause.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> InstrumentRootCauseAudit:
        reduction = self.online_primary_prompt_utf8_bytes - self.online_rescue_prompt_utf8_bytes
        basis_points = reduction * 10000 // self.online_primary_prompt_utf8_bytes
        if (
            reduction != self.online_rescue_reduction_bytes
            or basis_points != self.online_rescue_reduction_basis_points
            or self.reduction_shortfall_basis_points
            != self.frozen_minimum_reduction_basis_points - basis_points
        ):
            raise ValueError("v26.96 reduction arithmetic changed")
        if self.audit_id != instrument_root_cause_audit_id(self):
            raise ValueError("v26.96 root-cause identity changed")
        return self


class ProspectiveFailureTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    source_audit_id: str = Field(min_length=1)
    lineage_audit_id: str = Field(min_length=1)
    provider_audit_id: str = Field(min_length=1)
    completion_audit_id: str = Field(min_length=1)
    root_cause_audit_id: str = Field(min_length=1)
    exposed_v26_95_job_count: Literal[28] = EXPECTED_EXPOSED_COUNT
    exposed_v26_95_job_rerun_allowed: Literal[False] = False
    unopened_v26_95_job_count: Literal[4] = EXPECTED_UNOPENED_COUNT
    unopened_v26_95_continuation_allowed: Literal[False] = False
    unopened_v26_95_job_identities_retired: Literal[True] = True
    raw_uncheckpointed_jobs_reclassified: Literal[False] = False
    provider_orphan_job_reclassified: Literal[False] = False
    historical_execution_report_backfilled: Literal[False] = False
    historical_completion_gate_rescued: Literal[False] = False
    same_4096_bound_prompt_only_retuning_allowed: Literal[False] = False
    future_completion_bound_change_permitted: Literal[True] = True
    future_true_two_stage_protocol_permitted: Literal[True] = True
    unique_successor_design_selected: Literal[False] = False
    future_dynamic_request_kind_precall_validation_required: Literal[True] = True
    future_dynamic_rescue_reduction_precall_validation_required: Literal[True] = True
    future_reachable_state_coverage_required: Literal[True] = True
    future_fresh_task_package_identity_required: Literal[True] = True
    future_fresh_contract_identity_required: Literal[True] = True
    future_fresh_manifest_identity_required: Literal[True] = True
    future_fresh_job_identity_required: Literal[True] = True
    future_fresh_execution_identity_required: Literal[True] = True
    thinking_enabled_policy_retained: Literal[True] = True
    calibration_rows_role_eligible: Literal[False] = False
    role_protocol_frozen: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    next_permitted_stage: Literal[
        "thinking_completion_bound_or_two_stage_protocol_redesign_only"
    ] = "thinking_completion_bound_or_two_stage_protocol_redesign_only"
    schema_version: Literal["finance_v26_thinking_repair_failure_transition.v1"] = (
        "finance_v26_thinking_repair_failure_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveFailureTransitionContract:
        if self.contract_id != prospective_transition_contract_id(self):
            raise ValueError("v26.96 transition Contract identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_id: str = Field(min_length=1)
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True
    error: str = Field(min_length=1)
    schema_version: Literal["finance_v26_thinking_repair_failure_mutation.v1"] = (
        "finance_v26_thinking_repair_failure_mutation.v1"
    )


class FailureDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=12, max_length=12)
    rejected_mutation_count: Literal[12] = 12
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_thinking_repair_failure_destructive.v1"] = (
        "finance_v26_thinking_repair_failure_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FailureDestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutation_results)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.96 destructive mutations are not canonical")
        if self.audit_id != destructive_audit_id(self):
            raise ValueError("v26.96 destructive identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class ThinkingRepairFailureAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    repair_contract_id: str = EXPECTED_REPAIR_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    source_replay_audit_id: str = Field(min_length=1)
    lineage_audit_id: str = Field(min_length=1)
    provider_telemetry_audit_id: str = Field(min_length=1)
    completion_lower_bound_audit_id: str = Field(min_length=1)
    instrument_root_cause_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=7, max_length=7)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=1, max_length=1
    )
    source_replay_passed: Literal[True] = True
    failed_lineage_reconstructed: Literal[True] = True
    provider_telemetry_integrity_passed: Literal[True] = True
    instrument_root_cause_confirmed: Literal[True] = True
    completion_gate_irrevocably_failed: Literal[True] = True
    exact_denominator_completed: Literal[False] = False
    historical_execution_report_materialized: Literal[False] = False
    historical_job_rerun_count: Literal[0] = 0
    historical_result_reclassification_count: Literal[0] = 0
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
        "thinking_completion_bound_or_two_stage_protocol_redesign_only"
    ] = "thinking_completion_bound_or_two_stage_protocol_redesign_only"
    schema_version: Literal["finance_v26_thinking_repair_failure_audit_report.v1"] = (
        "finance_v26_thinking_repair_failure_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> ThinkingRepairFailureAuditReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.96 report details are not canonical")
        if self.implementation_source_files[0].relative_path != AUDIT_SOURCE_PATH:
            raise ValueError("v26.96 implementation binding changed")
        if self.report_id != failure_report_id(self):
            raise ValueError("v26.96 report identity changed")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def source_replay_audit_id(value: FailureSourceReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_repair_failure_source:")


def exposure_row_id(value: JobExposureRow) -> str:
    return _identity(value, "row_id", "finance_v26_thinking_repair_exposure:")


def failed_lineage_audit_id(value: FailedExecutionLineageAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_repair_failed_lineage:")


def provider_telemetry_audit_id(value: FailedProviderTelemetryAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_repair_failed_provider:")


def completion_lower_bound_audit_id(value: CompletionLowerBoundAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_repair_completion_lower_bound:")


def instrument_root_cause_audit_id(value: InstrumentRootCauseAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_repair_instrument_root_cause:")


def prospective_transition_contract_id(value: ProspectiveFailureTransitionContract) -> str:
    return _identity(value, "contract_id", "finance_v26_thinking_repair_failure_transition:")


def mutation_result_id(value: MutationResult) -> str:
    return _identity(value, "mutation_id", "finance_v26_thinking_repair_failure_mutation:")


def destructive_audit_id(value: FailureDestructiveAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_repair_failure_destructive:")


def failure_report_id(value: ThinkingRepairFailureAuditReport) -> str:
    return _identity(value, "report_id", "finance_v26_thinking_repair_failure_audit_report:")


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
        raise ValueError(f"noncanonical v26.96 source JSON: {path}")
    return payload


def _load_canonical_jsonl(path: Path) -> tuple[Any, ...]:
    rows = []
    for line in path.read_bytes().splitlines():
        payload = json.loads(line)
        if line != _canonical_bytes(payload):
            raise ValueError(f"noncanonical v26.96 source JSONL row: {path}")
        rows.append(payload)
    return tuple(rows)


def _write_json(path: Path, value: Any) -> None:
    raw = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError(f"immutable v26.96 output changed: {path}")
    path.write_bytes(raw)


def _relative(path: Path, package_root: Path) -> str:
    return str(path.resolve().relative_to(package_root.resolve()))


def _contains_private_reasoning_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key) == "reasoning_content" or _contains_private_reasoning_key(item)
            for key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_private_reasoning_key(item) for item in value)
    return False


def _source_entry(
    *,
    path: Path,
    package_root: Path,
    source_kind: Literal[
        "v26_95_bound_source",
        "v26_95_preflight_output",
        "failed_execution_file",
        "v26_96_implementation",
    ],
    expected_sha256: str,
) -> SourceReplayEntry:
    observed = _sha256(path)
    return SourceReplayEntry(
        relative_path=_relative(path, package_root),
        source_kind=source_kind,
        expected_sha256=expected_sha256,
        observed_sha256=observed,
        byte_count=path.stat().st_size,
        passed=True,
    )


def _build_source_replay(package_root: Path) -> FailureSourceReplayAudit:
    preflight_dir = package_root / PREFLIGHT_DIR
    execution_dir = package_root / EXECUTION_DIR
    preflight_report = ThinkingRepairExecutionPreflightReport.model_validate_json(
        (preflight_dir / "report.json").read_text(encoding="utf-8")
    )
    bound = ThinkingRepairRunnerSourceReplayAudit.model_validate_json(
        (preflight_dir / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    if (
        preflight_report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or preflight_report.execution_contract_id != EXPECTED_EXECUTION_CONTRACT_ID
        or bound.audit_id != EXPECTED_SOURCE_REPLAY_ID
        or not preflight_report.repair_execution_authorized
    ):
        raise ValueError("v26.96 authorizing v26.95 preflight changed")
    entries = []
    for item in bound.entries:
        entries.append(
            _source_entry(
                path=package_root / item.relative_path,
                package_root=package_root,
                source_kind="v26_95_bound_source",
                expected_sha256=item.expected_sha256,
            )
        )
    preflight_files = sorted(path for path in preflight_dir.iterdir() if path.is_file())
    if len(preflight_files) != EXPECTED_PREFLIGHT_OUTPUT_COUNT:
        raise ValueError("v26.96 v26.95 preflight output denominator changed")
    for path in preflight_files:
        entries.append(
            _source_entry(
                path=path,
                package_root=package_root,
                source_kind="v26_95_preflight_output",
                expected_sha256=_sha256(path),
            )
        )
    execution_files = sorted(path for path in execution_dir.rglob("*") if path.is_file())
    if len(execution_files) != EXPECTED_FAILED_EXECUTION_FILE_COUNT:
        raise ValueError("v26.96 failed execution file denominator changed")
    for path in execution_files:
        entries.append(
            _source_entry(
                path=path,
                package_root=package_root,
                source_kind="failed_execution_file",
                expected_sha256=_sha256(path),
            )
        )
    source_path = package_root / AUDIT_SOURCE_PATH
    entries.append(
        _source_entry(
            path=source_path,
            package_root=package_root,
            source_kind="v26_96_implementation",
            expected_sha256=_sha256(source_path),
        )
    )
    ordered = tuple(sorted(entries, key=lambda item: item.relative_path))
    values = {"entries": ordered}
    provisional = FailureSourceReplayAudit.model_construct(audit_id="pending", **values)
    return FailureSourceReplayAudit(
        audit_id=source_replay_audit_id(provisional),
        **values,
    )


def _load_execution_inputs(
    package_root: Path,
) -> tuple[
    Path,
    ThinkingRepairExecutionContract,
    ThinkingRepairManifest,
    tuple[ThinkingRepairPathAudit, ...],
]:
    execution_dir = package_root / EXECUTION_DIR
    contract = ThinkingRepairExecutionContract.model_validate_json(
        (execution_dir / "execution_contract.json").read_text(encoding="utf-8")
    )
    manifest = ThinkingRepairManifest.model_validate_json(
        (execution_dir / "frozen_repair_job_manifest.json").read_text(encoding="utf-8")
    )
    paths_payload = _load_canonical_json(
        package_root / V26_94_DIR / "thinking_repair_path_audits.json"
    )
    paths = tuple(ThinkingRepairPathAudit.model_validate(item) for item in paths_payload)
    if (
        contract.contract_id != EXPECTED_EXECUTION_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_MANIFEST_ID
        or contract.predecessor_contract_id != EXPECTED_REPAIR_CONTRACT_ID
        or tuple(sorted(item.job_id for item in manifest.jobs)) != contract.job_ids
    ):
        raise ValueError("v26.96 frozen execution inputs changed")
    return execution_dir, contract, manifest, paths


def _load_failed_artifacts(
    execution_dir: Path,
) -> tuple[
    tuple[ThinkingRepairJobResult, ...],
    tuple[dict[str, Any], ...],
    dict[str, ThinkingRepairRawExecution],
    tuple[ThinkingRepairRawProviderCall, ...],
]:
    checkpoint_payloads = _load_canonical_jsonl(
        execution_dir / "thinking_repair_job_results.checkpoint.jsonl"
    )
    failure_payloads = cast(
        tuple[dict[str, Any], ...],
        _load_canonical_jsonl(execution_dir / "runner_failures.checkpoint.jsonl"),
    )
    checkpoints = tuple(
        ThinkingRepairJobResult.model_validate(item) for item in checkpoint_payloads
    )
    raw_by_job = {}
    for path in sorted((execution_dir / "raw_execution").glob("*.json")):
        raw = ThinkingRepairRawExecution.model_validate(_load_canonical_json(path))
        raw_by_job[raw.job.job_id] = raw
    providers = tuple(
        ThinkingRepairRawProviderCall.model_validate(_load_canonical_json(path))
        for path in sorted((execution_dir / "raw_provider_calls").rglob("call_*.json"))
    )
    return checkpoints, failure_payloads, raw_by_job, providers


def _build_lineage_audit(
    *,
    execution_dir: Path,
    contract: ThinkingRepairExecutionContract,
    manifest: ThinkingRepairManifest,
    checkpoints: tuple[ThinkingRepairJobResult, ...],
    failure_payloads: tuple[dict[str, Any], ...],
    raw_by_job: dict[str, ThinkingRepairRawExecution],
    providers: tuple[ThinkingRepairRawProviderCall, ...],
) -> FailedExecutionLineageAudit:
    checkpoint_by_job = {item.job_id: item for item in checkpoints}
    provider_by_job: dict[str, list[ThinkingRepairRawProviderCall]] = defaultdict(list)
    for item in providers:
        provider_by_job[item.job_id].append(item)
    rows = []
    descriptor_passes = 0
    checkpoint_binding_passes = 0
    raw_provider_ids: set[str] = set()
    for index, job in enumerate(manifest.jobs):
        checkpoint = checkpoint_by_job.get(job.job_id)
        raw = raw_by_job.get(job.job_id)
        provider_rows = sorted(
            provider_by_job.get(job.job_id, []), key=lambda item: item.call_index
        )
        row_values = {
            "manifest_index": index,
            "job_id": job.job_id,
            "mechanism_id": job.mechanism_id,
            "path_strategy_id": job.path_strategy_id,
            "state": (
                "checkpoint"
                if checkpoint is not None
                else "raw_uncheckpointed"
                if raw is not None
                else "provider_orphan"
                if provider_rows
                else "unopened"
            ),
            "checkpoint_present": checkpoint is not None,
            "raw_execution_present": raw is not None,
            "provider_call_count": len(provider_rows),
            "model_exposed": bool(provider_rows),
        }
        provisional = JobExposureRow.model_construct(row_id="pending", **row_values)
        rows.append(JobExposureRow(row_id=exposure_row_id(provisional), **row_values))
        if raw is not None:
            if tuple(raw.provider_call_ids) != tuple(
                item.provider_call_id for item in provider_rows
            ):
                raise ValueError("v26.96 Raw Provider ordering changed")
            raw_provider_ids.update(raw.provider_call_ids)
            for descriptor in raw.provider_call_artifacts:
                path = execution_dir / descriptor.relative_path
                if _sha256(path) != descriptor.sha256:
                    raise ValueError("v26.96 Raw Provider descriptor changed")
                descriptor_passes += 1
        if checkpoint is not None:
            if raw is None:
                raise ValueError("v26.96 checkpoint lacks Raw Execution")
            raw_path = execution_dir / checkpoint.raw_execution_artifact.relative_path
            if (
                _sha256(raw_path) != checkpoint.raw_execution_artifact.sha256
                or raw.artifact_id
                != ThinkingRepairRawExecution.model_validate_json(
                    raw_path.read_text(encoding="utf-8")
                ).artifact_id
            ):
                raise ValueError("v26.96 checkpoint Raw binding changed")
            checkpoint_binding_passes += 1
    if len(failure_payloads) != 1 or failure_payloads[0].get("job_id") != EXPECTED_FAILURE_JOB_ID:
        raise ValueError("v26.96 Runner failure checkpoint changed")
    orphan_ids = {item.provider_call_id for item in provider_by_job[EXPECTED_FAILURE_JOB_ID]}
    if len(orphan_ids) != EXPECTED_ORPHAN_PROVIDER_CALL_COUNT:
        raise ValueError("v26.96 orphan Provider denominator changed")
    if raw_provider_ids & orphan_ids:
        raise ValueError("v26.96 orphan Provider identity overlaps Raw lineage")
    values = {
        "rows": tuple(rows),
        "unique_provider_call_id_count": len({item.provider_call_id for item in providers}),
        "raw_bound_provider_artifact_count": len(raw_provider_ids),
        "orphan_provider_artifact_count": len(orphan_ids),
        "checkpoint_result_schema_pass_count": len(checkpoints),
        "raw_execution_schema_pass_count": len(raw_by_job),
        "provider_artifact_schema_pass_count": len(providers),
        "canonical_json_file_pass_count": len(raw_by_job) + len(providers),
        "canonical_jsonl_row_pass_count": len(checkpoints) + len(failure_payloads),
        "raw_descriptor_hash_pass_count": descriptor_passes,
        "checkpoint_raw_binding_pass_count": checkpoint_binding_passes,
    }
    provisional = FailedExecutionLineageAudit.model_construct(audit_id="pending", **values)
    return FailedExecutionLineageAudit(
        audit_id=failed_lineage_audit_id(provisional),
        **values,
    )


def _build_provider_audit(
    providers: tuple[ThinkingRepairRawProviderCall, ...],
) -> FailedProviderTelemetryAudit:
    telemetry = tuple(item.provider_telemetry for item in providers)
    failure_counts = Counter(
        item.failure_artifact.failure_type if item.failure_artifact is not None else "payload"
        for item in providers
    )
    private_count = sum(
        item.private_reasoning_content_persisted
        or item.private_reasoning_content_hashed
        or _contains_private_reasoning_key(item.model_dump(mode="json"))
        for item in providers
    )
    total_cost = sum(
        (Decimal(str(item.estimated_cost or 0)) for item in telemetry),
        Decimal(0),
    )
    values = {
        "provider_artifact_count": len(providers),
        "unique_provider_call_id_count": len({item.provider_call_id for item in providers}),
        "http_success_call_count": sum(item.http_success for item in telemetry),
        "exact_requested_model_call_count": sum(
            item.model_requested == "deepseek-v4-flash" for item in telemetry
        ),
        "exact_selected_model_call_count": sum(
            item.model_selected == "deepseek-v4-flash" for item in telemetry
        ),
        "exact_response_model_call_count": sum(
            item.response_model == "deepseek-v4-flash" for item in telemetry
        ),
        "missing_response_model_call_count": sum(item.response_model is None for item in telemetry),
        "fallback_call_count": sum(item.fallback_used for item in telemetry),
        "native_tool_call_count": sum(
            item.response_shape.get("provider_native_tool_call_observed") is True
            for item in telemetry
        ),
        "positive_thinking_telemetry_call_count": sum(
            bool(item.reasoning_content_present)
            and (item.reasoning_content_length or 0) > 0
            and (item.reasoning_tokens or 0) > 0
            for item in telemetry
        ),
        "complete_usage_call_count": sum(
            item.prompt_tokens is not None
            and item.completion_tokens is not None
            and item.total_tokens is not None
            and item.prompt_tokens + item.completion_tokens == item.total_tokens
            for item in telemetry
        ),
        "primary_call_count": sum(item.phase == "primary" for item in providers),
        "rescue_call_count": sum(item.phase == "rescue" for item in providers),
        "decision_call_count": sum(item.request_kind == "decision" for item in providers),
        "final_answer_call_count": sum(item.request_kind == "final_answer" for item in providers),
        "public_json_payload_call_count": failure_counts["payload"],
        "reasoning_only_length_truncation_call_count": failure_counts[
            "reasoning_only_length_truncation"
        ],
        "length_truncated_content_call_count": failure_counts["length_truncated_content"],
        "provider_total_tokens": sum(item.total_tokens or 0 for item in telemetry),
        "reasoning_tokens": sum(item.reasoning_tokens or 0 for item in telemetry),
        "completion_tokens": sum(item.completion_tokens or 0 for item in telemetry),
        "estimated_cost_usd": format(total_cost, "f"),
        "private_reasoning_payload_count": private_count,
        "raw_http_body_count": sum(item.raw_http_body_persisted for item in providers),
        "transport_failure_count": sum(not item.http_success for item in telemetry),
        "response_model_mismatch_count": sum(
            item.response_model not in {None, "deepseek-v4-flash"} for item in telemetry
        ),
    }
    provisional = FailedProviderTelemetryAudit.model_construct(audit_id="pending", **values)
    return FailedProviderTelemetryAudit(
        audit_id=provider_telemetry_audit_id(provisional),
        **values,
    )


def _build_completion_audit(
    *,
    checkpoints: tuple[ThinkingRepairJobResult, ...],
    raw_by_job: dict[str, ThinkingRepairRawExecution],
    providers: tuple[ThinkingRepairRawProviderCall, ...],
) -> CompletionLowerBoundAudit:
    raws = tuple(raw_by_job.values())
    attempts = tuple(item for raw in raws for item in raw.request_attempts)
    failure_counts = Counter(
        attempt.failure_artifact.failure_type
        for attempt in attempts
        if attempt.failure_artifact is not None
    )
    terminal_counts = Counter(raw.terminal_failure_type for raw in raws)
    reductions = tuple(
        cast(int, attempt.rescue_prompt_reduction_basis_points)
        for attempt in attempts
        if attempt.phase == "rescue"
    )
    orphan = sorted(
        (item for item in providers if item.job_id == EXPECTED_FAILURE_JOB_ID),
        key=lambda item: item.call_index,
    )
    if len(orphan) != EXPECTED_ORPHAN_PROVIDER_CALL_COUNT:
        raise ValueError("v26.96 orphan Completion sequence changed")
    checkpoint_ids = {item.job_id for item in checkpoints}
    values = {
        "complete_raw_job_count": len(raws),
        "complete_raw_completion_unusable_count": sum(
            raw.terminal_disposition == "completion_unusable" for raw in raws
        ),
        "checkpoint_completion_unusable_count": sum(
            item.terminal_category == "completion_unusable" for item in checkpoints
        ),
        "raw_uncheckpointed_completion_unusable_count": sum(
            raw.job.job_id not in checkpoint_ids
            and raw.terminal_disposition == "completion_unusable"
            for raw in raws
        ),
        "formal_completion_unusable_lower_bound_count": sum(
            raw.terminal_disposition == "completion_unusable" for raw in raws
        ),
        "raw_provider_call_count": sum(len(raw.provider_call_ids) for raw in raws),
        "raw_logical_request_count": sum(len(raw.logical_requests) for raw in raws),
        "raw_request_attempt_count": len(attempts),
        "raw_primary_attempt_count": sum(item.phase == "primary" for item in attempts),
        "raw_rescue_attempt_count": sum(item.phase == "rescue" for item in attempts),
        "raw_observation_count": sum(len(raw.observations) for raw in raws),
        "raw_completed_result_count": sum(raw.completed_result is not None for raw in raws),
        "raw_budget_pass_count": sum(raw.provider_budget_audit.status == "passed" for raw in raws),
        "raw_typed_no_call_count": sum(
            raw.provider_budget_audit.no_call_terminal is not None for raw in raws
        ),
        "raw_reasoning_only_failure_count": failure_counts["reasoning_only_length_truncation"],
        "raw_length_truncated_failure_count": failure_counts["length_truncated_content"],
        "raw_invalid_response_contract_failure_count": failure_counts["invalid_response_contract"],
        "terminal_reasoning_only_count": terminal_counts["reasoning_only_length_truncation"],
        "terminal_length_truncated_count": terminal_counts["length_truncated_content"],
        "terminal_invalid_response_contract_count": terminal_counts["invalid_response_contract"],
        "raw_rescue_reduction_minimum_basis_points": min(reductions),
        "raw_rescue_reduction_maximum_basis_points": max(reductions),
        "orphan_primary_reasoning_only_truncation_observed": (
            orphan[6].failure_artifact is not None
            and orphan[6].failure_artifact.failure_type == "reasoning_only_length_truncation"
        ),
        "orphan_rescue_reasoning_only_truncation_observed": (
            orphan[7].failure_artifact is not None
            and orphan[7].failure_artifact.failure_type == "reasoning_only_length_truncation"
        ),
    }
    provisional = CompletionLowerBoundAudit.model_construct(audit_id="pending", **values)
    return CompletionLowerBoundAudit(
        audit_id=completion_lower_bound_audit_id(provisional),
        **values,
    )


def _build_root_cause_audit(
    *,
    manifest: ThinkingRepairManifest,
    paths: tuple[ThinkingRepairPathAudit, ...],
    raw_by_job: dict[str, ThinkingRepairRawExecution],
    providers: tuple[ThinkingRepairRawProviderCall, ...],
) -> InstrumentRootCauseAudit:
    job = next(item for item in manifest.jobs if item.job_id == EXPECTED_FAILURE_JOB_ID)
    path = next(item for item in paths if item.audit_id == job.repair_path_audit_id)
    registered = path.request_audits[6]
    orphan = sorted(
        (item for item in providers if item.job_id == EXPECTED_FAILURE_JOB_ID),
        key=lambda item: item.call_index,
    )
    primary = orphan[6]
    rescue = orphan[7]
    attempts = tuple(item for raw in raw_by_job.values() for item in raw.request_attempts)
    online_primary_bytes = len(primary.prompt.encode("utf-8"))
    online_rescue_bytes = len(rescue.prompt.encode("utf-8"))
    values = {
        "failure_mechanism_id": job.mechanism_id,
        "failure_path_strategy_id": job.path_strategy_id,
        "registered_request_count": len(path.request_audits),
        "registered_request_kind": registered.request_kind,
        "online_request_kind": primary.request_kind,
        "registered_primary_prompt_utf8_bytes": registered.primary_prompt_utf8_bytes,
        "registered_maximum_rescue_prompt_utf8_bytes": (
            registered.maximum_rescue_prompt_utf8_bytes
        ),
        "registered_minimum_rescue_reduction_basis_points": (
            registered.minimum_rescue_size_reduction_basis_points
        ),
        "online_primary_prompt_utf8_bytes": online_primary_bytes,
        "online_rescue_prompt_utf8_bytes": online_rescue_bytes,
        "online_rescue_reduction_bytes": online_primary_bytes - online_rescue_bytes,
        "online_rescue_reduction_basis_points": (
            (online_primary_bytes - online_rescue_bytes) * 10000 // online_primary_bytes
        ),
        "reduction_shortfall_basis_points": 1000
        - ((online_primary_bytes - online_rescue_bytes) * 10000 // online_primary_bytes),
        "primary_matches_registered_hash": primary.prompt_sha256
        == registered.primary_prompt_sha256,
        "request_kind_matches_registered": primary.request_kind == registered.request_kind,
        "primary_finish_reason": primary.provider_telemetry.finish_reason,
        "rescue_finish_reason": rescue.provider_telemetry.finish_reason,
        "primary_reasoning_tokens": primary.provider_telemetry.reasoning_tokens,
        "rescue_reasoning_tokens": rescue.provider_telemetry.reasoning_tokens,
        "primary_failure_type": cast(Any, primary.failure_artifact).failure_type,
        "rescue_failure_type": cast(Any, rescue.failure_artifact).failure_type,
        "rescue_http_success_before_gate_failure": rescue.provider_telemetry.http_success,
        "rescue_provider_artifact_persisted_before_gate_failure": True,
        "complete_raw_registered_request_absent_count": sum(
            item.phase == "primary" and not item.registered_request_present for item in attempts
        ),
        "complete_raw_registered_kind_mismatch_count": sum(
            item.phase == "primary"
            and item.registered_request_present
            and not item.registered_request_kind_match
            for item in attempts
        ),
        "complete_raw_registered_primary_hash_mismatch_count": sum(
            item.phase == "primary"
            and item.registered_request_present
            and not item.registered_primary_prompt_match
            for item in attempts
        ),
        "complete_raw_job_with_kind_mismatch_count": sum(
            any(
                item.phase == "primary"
                and item.registered_request_present
                and not item.registered_request_kind_match
                for item in raw.request_attempts
            )
            for raw in raw_by_job.values()
        ),
        "complete_raw_job_with_hash_mismatch_count": sum(
            any(
                item.phase == "primary"
                and item.registered_request_present
                and not item.registered_primary_prompt_match
                for item in raw.request_attempts
            )
            for raw in raw_by_job.values()
        ),
    }
    provisional = InstrumentRootCauseAudit.model_construct(audit_id="pending", **values)
    return InstrumentRootCauseAudit(
        audit_id=instrument_root_cause_audit_id(provisional),
        **values,
    )


def _build_transition_contract(
    *,
    source: FailureSourceReplayAudit,
    lineage: FailedExecutionLineageAudit,
    provider: FailedProviderTelemetryAudit,
    completion: CompletionLowerBoundAudit,
    root_cause: InstrumentRootCauseAudit,
) -> ProspectiveFailureTransitionContract:
    values = {
        "source_audit_id": source.audit_id,
        "lineage_audit_id": lineage.audit_id,
        "provider_audit_id": provider.audit_id,
        "completion_audit_id": completion.audit_id,
        "root_cause_audit_id": root_cause.audit_id,
    }
    provisional = ProspectiveFailureTransitionContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ProspectiveFailureTransitionContract(
        contract_id=prospective_transition_contract_id(provisional),
        **values,
    )


def _mutation_result(name: str, error: Exception) -> MutationResult:
    values = {"mutation_name": name, "error": f"{type(error).__name__}:{error}"}
    provisional = MutationResult.model_construct(mutation_id="pending", **values)
    return MutationResult(
        mutation_id=mutation_result_id(provisional),
        **values,
    )


def _build_destructive_audit(
    contract: ProspectiveFailureTransitionContract,
    root_cause: InstrumentRootCauseAudit,
    completion: CompletionLowerBoundAudit,
) -> FailureDestructiveAudit:
    contract_mutations = {
        "allow_exposed_job_rerun": {"exposed_v26_95_job_rerun_allowed": True},
        "allow_unopened_continuation": {"unopened_v26_95_continuation_allowed": True},
        "backfill_historical_report": {"historical_execution_report_backfilled": True},
        "permit_same_bound_prompt_retuning": {"same_4096_bound_prompt_only_retuning_allowed": True},
        "reclassify_orphan_job": {"provider_orphan_job_reclassified": True},
        "rescue_historical_completion_gate": {"historical_completion_gate_rescued": True},
        "freeze_role_protocol": {"role_protocol_frozen": True},
        "authorize_capability": {"capability_execution_authorized": True},
        "drop_dynamic_kind_precall_gate": {
            "future_dynamic_request_kind_precall_validation_required": False
        },
        "drop_dynamic_reduction_precall_gate": {
            "future_dynamic_rescue_reduction_precall_validation_required": False
        },
    }
    results = []
    base_contract = contract.model_dump(mode="json")
    for name, changes in contract_mutations.items():
        payload = {**base_contract, **changes}
        try:
            ProspectiveFailureTransitionContract.model_validate(payload)
        except ValidationError as exc:
            results.append(_mutation_result(name, exc))
        else:
            raise AssertionError(f"v26.96 mutation passed: {name}")
    root_payload = {
        **root_cause.model_dump(mode="json"),
        "online_rescue_reduction_basis_points": 1000,
    }
    try:
        InstrumentRootCauseAudit.model_validate(root_payload)
    except ValidationError as exc:
        results.append(_mutation_result("change_online_reduction", exc))
    else:
        raise AssertionError("v26.96 mutation passed: change_online_reduction")
    completion_payload = {
        **completion.model_dump(mode="json"),
        "completion_gate_can_still_pass": True,
    }
    try:
        CompletionLowerBoundAudit.model_validate(completion_payload)
    except ValidationError as exc:
        results.append(_mutation_result("reopen_completion_gate", exc))
    else:
        raise AssertionError("v26.96 mutation passed: reopen_completion_gate")
    ordered = tuple(sorted(results, key=lambda item: item.mutation_name))
    values = {
        "transition_contract_id": contract.contract_id,
        "mutation_results": ordered,
    }
    provisional = FailureDestructiveAudit.model_construct(audit_id="pending", **values)
    return FailureDestructiveAudit(
        audit_id=destructive_audit_id(provisional),
        **values,
    )


def _detail_files(output_dir: Path) -> tuple[DetailFile, ...]:
    counts = {
        "completion_lower_bound_audit.json": 27,
        "destructive_audit.json": 12,
        "failed_execution_lineage_audit.json": 32,
        "instrument_root_cause_audit.json": 1,
        "prospective_transition_contract.json": 1,
        "provider_telemetry_audit.json": 184,
        "source_replay_audit.json": EXPECTED_SOURCE_REPLAY_COUNT,
    }
    return tuple(
        DetailFile(
            relative_path=name,
            sha256=_sha256(output_dir / name),
            record_count=count,
        )
        for name, count in sorted(counts.items())
    )


def build_thinking_repair_execution_failure_audit(
    *,
    run_id: str,
    output_dir: Path,
    package_root: Path,
) -> ThinkingRepairFailureAuditReport:
    source = _build_source_replay(package_root)
    execution_dir, contract, manifest, paths = _load_execution_inputs(package_root)
    checkpoints, failures, raw_by_job, providers = _load_failed_artifacts(execution_dir)
    lineage = _build_lineage_audit(
        execution_dir=execution_dir,
        contract=contract,
        manifest=manifest,
        checkpoints=checkpoints,
        failure_payloads=failures,
        raw_by_job=raw_by_job,
        providers=providers,
    )
    provider = _build_provider_audit(providers)
    completion = _build_completion_audit(
        checkpoints=checkpoints,
        raw_by_job=raw_by_job,
        providers=providers,
    )
    root_cause = _build_root_cause_audit(
        manifest=manifest,
        paths=paths,
        raw_by_job=raw_by_job,
        providers=providers,
    )
    transition = _build_transition_contract(
        source=source,
        lineage=lineage,
        provider=provider,
        completion=completion,
        root_cause=root_cause,
    )
    destructive = _build_destructive_audit(transition, root_cause, completion)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "source_replay_audit.json": source,
        "failed_execution_lineage_audit.json": lineage,
        "provider_telemetry_audit.json": provider,
        "completion_lower_bound_audit.json": completion,
        "instrument_root_cause_audit.json": root_cause,
        "prospective_transition_contract.json": transition,
        "destructive_audit.json": destructive,
    }
    for name, value in outputs.items():
        _write_json(output_dir / name, value.model_dump(mode="json"))
    source_path = package_root / AUDIT_SOURCE_PATH
    report_values = {
        "run_id": run_id,
        "source_replay_audit_id": source.audit_id,
        "lineage_audit_id": lineage.audit_id,
        "provider_telemetry_audit_id": provider.audit_id,
        "completion_lower_bound_audit_id": completion.audit_id,
        "instrument_root_cause_audit_id": root_cause.audit_id,
        "transition_contract_id": transition.contract_id,
        "destructive_audit_id": destructive.audit_id,
        "detail_files": _detail_files(output_dir),
        "implementation_source_files": (
            ImplementationSourceFile(
                relative_path=AUDIT_SOURCE_PATH,
                sha256=_sha256(source_path),
            ),
        ),
    }
    provisional = ThinkingRepairFailureAuditReport.model_construct(
        report_id="pending",
        **report_values,
    )
    report = ThinkingRepairFailureAuditReport(
        report_id=failure_report_id(provisional),
        **report_values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit the fail-closed Finance v26.95 Thinking repair execution"
    )
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    args = parser.parse_args()
    report = build_thinking_repair_execution_failure_audit(
        run_id=args.run_id,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
