from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from math import comb
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    ImplementationSourceFile,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_binding_and_usage_semantics import (  # noqa: E501
    Exact16KManifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_completion_calibration_contracts import (  # noqa: E501
    Exact16KExecutionContract,
    Exact16KExecutionReport,
    Exact16KOutcomeInterpretationContract,
    Exact16KRawExecution,
    Exact16KRawLineageAudit,
    Exact16KRawProviderCall,
    Exact16KRunnerPreflightReport,
    Exact16KRunnerSourceReplayAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501
    ThinkingRepairJobResult,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry

RUN_ID: Literal["finance_v26_106_thinking_16k_completion_calibration_postrun_audit_v1_20260822"] = (
    "finance_v26_106_thinking_16k_completion_calibration_postrun_audit_v1_20260822"
)
PREFLIGHT_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_104_thinking_16k_completion_calibration_runner_preflight_v1_20260822"
)
EXECUTION_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_105_thinking_16k_completion_calibration_execution_v1_20260822"
)
ENVIRONMENT_MANIFEST_PATH = (
    "artifacts/vtdo_experiment/"
    "finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/"
    "tool_environment_manifests.json"
)
AUDIT_SOURCE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_16k_completion_calibration_postrun_audit.py"
)
RUNNER_SOURCE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_completion_telemetry_repair_execution.py"
)
VERIFIER_SOURCE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_authority_preserving_verifier_replay.py"
)

EXPECTED_PREFLIGHT_REPORT_ID = (
    "finance_v26_exact_16k_runner_preflight_report:"
    "78d00f0c3134020ba9defd41be87fe767a2903e8988a944434cf8d0ce5fb7ff1"
)
EXPECTED_EXECUTION_CONTRACT_ID = (
    "finance_v26_exact_16k_execution_contract:"
    "2c093dae01b7125ba3321e6efdc61de445b57fbc373b9338fa9d2a94a1d10abc"
)
EXPECTED_EXECUTION_REPORT_ID = (
    "finance_v26_exact_16k_execution_report:"
    "fa01ca877d5f6c50861c6f145a6c3f2ee8ef22a372f57884a8d5714f283658d0"
)
EXPECTED_RAW_LINEAGE_ID = (
    "finance_v26_exact_16k_raw_lineage:"
    "dcc992eb0d2bc23853233e6007e279964366f42f6b07863027d503becf3baff4"
)
EXPECTED_MANIFEST_ID = (
    "finance_v26_exact_16k_manifest:"
    "d429395f73668418bbb5734b574ac52c059b2ed3c7e4988ce12be7b472aa3bdb"
)
EXPECTED_INTERPRETATION_ID = (
    "finance_v26_exact_16k_outcome_interpretation:"
    "a45b7c6bb804797e219a8a1e6f7dc0facff325f37b12743318a430868a23d1c7"
)
EXPECTED_PREFLIGHT_REPORT_SHA256 = (
    "557f28445288b053c79d51d801d90add33f103abb6f924b403b5d096aa1a1803"
)
EXPECTED_EXECUTION_REPORT_SHA256 = (
    "94e461401add1ce315494383454fb1ad9f70ad4ce922eec33d3291136f1b2406"
)

EXPECTED_BOUND_SOURCE_COUNT: Literal[1237] = 1237
EXPECTED_PREFLIGHT_OUTPUT_COUNT: Literal[10] = 10
EXPECTED_EXECUTION_FILE_COUNT: Literal[612] = 612
EXPECTED_SOURCE_REPLAY_COUNT: Literal[1860] = 1860
EXPECTED_JOB_COUNT: Literal[32] = 32
EXPECTED_PROVIDER_CALL_COUNT: Literal[572] = 572
EXPECTED_RAW_DESCRIPTOR_COUNT: Literal[604] = 604
EXPECTED_PROVIDER_TOTAL_TOKENS: Literal[4780636] = 4_780_636
EXPECTED_PROMPT_TOKENS: Literal[1675536] = 1_675_536
EXPECTED_COMPLETION_TOKENS: Literal[3105100] = 3_105_100
EXPECTED_REASONING_TOKENS: Literal[3001271] = 3_001_271
EXPECTED_REASONING_LENGTH: Literal[12925345] = 12_925_345
EXPECTED_COST: Literal["0.98291580800000008797"] = "0.98291580800000008797"
EXPECTED_COMPLETION_FAILURES = {
    "empty_final_content": 1,
    "invalid_json": 2,
    "invalid_response_contract": 33,
    "reasoning_only_length_truncation": 1,
}
INSTRUMENT_ROOT_CAUSE: Literal[
    "runtime_unknown_or_unselectable_tool_observation_not_replayed_by_verifier_v2"
] = "runtime_unknown_or_unselectable_tool_observation_not_replayed_by_verifier_v2"
BUDGET_ROOT_CAUSE: Literal[
    "decision_request_plus_required_reserve_exceeded_remaining_rollout_budget"
] = "decision_request_plus_required_reserve_exceeded_remaining_rollout_budget"
NEXT_STAGE: Literal[
    "authority_preserving_unknown_tool_replay_repair_and_true_two_stage_protocol_preflight_only"
] = "authority_preserving_unknown_tool_replay_repair_and_true_two_stage_protocol_preflight_only"

SourceKind = Literal[
    "v26_104_bound_source",
    "v26_104_preflight_output",
    "v26_105_execution_file",
    "v26_106_implementation",
]
DeltaBucket = Literal["below", "zero", "one", "two_or_more"]


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
            raise ValueError("v26.106 source replay changed")
        return self


class PostrunSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    entries: tuple[SourceReplayEntry, ...] = Field(
        min_length=EXPECTED_SOURCE_REPLAY_COUNT,
        max_length=EXPECTED_SOURCE_REPLAY_COUNT,
    )
    bound_source_file_count: Literal[1237] = EXPECTED_BOUND_SOURCE_COUNT
    preflight_output_file_count: Literal[10] = EXPECTED_PREFLIGHT_OUTPUT_COUNT
    execution_file_count: Literal[612] = EXPECTED_EXECUTION_FILE_COUNT
    audit_implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[1860] = EXPECTED_SOURCE_REPLAY_COUNT
    replay_pass_count: Literal[1860] = EXPECTED_SOURCE_REPLAY_COUNT
    replay_before_diagnostics: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_16k_postrun_source_replay.v1"] = (
        "finance_v26_exact_16k_postrun_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PostrunSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.106 source paths are not canonical")
        if self.audit_id != source_replay_id(self):
            raise ValueError("v26.106 source identity changed")
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
    provider_artifact_count: Literal[572] = EXPECTED_PROVIDER_CALL_COUNT
    unique_provider_call_id_count: Literal[572] = EXPECTED_PROVIDER_CALL_COUNT
    raw_descriptor_count: Literal[604] = EXPECTED_RAW_DESCRIPTOR_COUNT
    raw_descriptor_hash_pass_count: Literal[604] = EXPECTED_RAW_DESCRIPTOR_COUNT
    canonical_json_file_count: Literal[611] = 611
    canonical_json_file_pass_count: Literal[611] = 611
    canonical_jsonl_row_count: Literal[32] = EXPECTED_JOB_COUNT
    canonical_jsonl_row_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    checkpoint_final_result_match_count: Literal[32] = EXPECTED_JOB_COUNT
    checkpoint_raw_binding_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    manifest_job_identity_match_count: Literal[32] = EXPECTED_JOB_COUNT
    provider_parent_binding_pass_count: Literal[572] = EXPECTED_PROVIDER_CALL_COUNT
    all_provider_calls_dynamically_precertified: Literal[True] = True
    all_provider_calls_exact_16k_request_bound: Literal[True] = True
    all_provider_calls_usage_semantics_bound: Literal[True] = True
    all_actual_usage_charged_without_clipping: Literal[True] = True
    private_reasoning_payload_count: Literal[0] = 0
    private_reasoning_hash_count: Literal[0] = 0
    raw_http_body_payload_count: Literal[0] = 0
    raw_request_body_payload_count: Literal[0] = 0
    historical_job_rerun_count: Literal[0] = 0
    historical_result_reclassification_count: Literal[0] = 0
    completed_run_replay_job_count: Literal[32] = EXPECTED_JOB_COUNT
    completed_run_replay_client_factory_call_count: Literal[0] = 0
    completed_run_replay_provider_call_count: Literal[0] = 0
    completed_run_replay_report_sha256: str = EXPECTED_EXECUTION_REPORT_SHA256
    completed_run_replay_report_byte_identical: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_16k_execution_lineage_audit.v1"] = (
        "finance_v26_exact_16k_execution_lineage_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionLineageAudit:
        if self.audit_id != execution_lineage_id(self):
            raise ValueError("v26.106 execution lineage identity changed")
        return self


class UsageDeltaCell(FrozenModel):
    delta_bucket: DeltaBucket
    finish_reason: str = Field(min_length=1)
    completion_classification: str = Field(min_length=1)
    call_count: int = Field(gt=0)


class ProviderTelemetryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    provider_call_count: Literal[572] = EXPECTED_PROVIDER_CALL_COUNT
    http_success_call_count: Literal[572] = EXPECTED_PROVIDER_CALL_COUNT
    exact_requested_model_count: Literal[572] = EXPECTED_PROVIDER_CALL_COUNT
    exact_selected_model_count: Literal[572] = EXPECTED_PROVIDER_CALL_COUNT
    exact_response_model_count: Literal[572] = EXPECTED_PROVIDER_CALL_COUNT
    fallback_count: Literal[0] = 0
    provider_native_tool_call_count: Literal[0] = 0
    model_discovery_call_count: Literal[0] = 0
    usage_complete_count: Literal[572] = EXPECTED_PROVIDER_CALL_COUNT
    thinking_telemetry_complete_count: Literal[572] = EXPECTED_PROVIDER_CALL_COUNT
    response_envelope_preparse_count: Literal[572] = EXPECTED_PROVIDER_CALL_COUNT
    exact_16k_request_certificate_count: Literal[572] = EXPECTED_PROVIDER_CALL_COUNT
    dynamic_precall_certificate_count: Literal[572] = EXPECTED_PROVIDER_CALL_COUNT
    primary_provider_call_count: Literal[549] = 549
    rescue_provider_call_count: Literal[23] = 23
    provider_total_tokens: Literal[4780636] = EXPECTED_PROVIDER_TOTAL_TOKENS
    prompt_tokens_total: Literal[1675536] = EXPECTED_PROMPT_TOKENS
    completion_tokens_total: Literal[3105100] = EXPECTED_COMPLETION_TOKENS
    reasoning_tokens_total: Literal[3001271] = EXPECTED_REASONING_TOKENS
    non_reasoning_completion_tokens_total: Literal[103829] = 103_829
    reasoning_content_length_total: Literal[12925345] = EXPECTED_REASONING_LENGTH
    estimated_cost_usd: Literal["0.98291580800000008797"] = EXPECTED_COST
    aggregate_reasoning_fraction: Literal["0.966561785450"] = "0.966561785450"
    minimum_call_reasoning_fraction: Literal["0.033678756477"] = "0.033678756477"
    median_call_reasoning_fraction: Literal["0.975892584681"] = "0.975892584681"
    p95_call_reasoning_fraction: Literal["0.993100000000"] = "0.993100000000"
    maximum_call_reasoning_fraction: Literal["1.000000000000"] = "1.000000000000"
    zero_reasoning_call_count: Literal[0] = 0
    minimum_completion_tokens: Literal[349] = 349
    median_completion_tokens: Literal[5323] = 5323
    p95_completion_tokens: Literal[11031] = 11031
    maximum_completion_tokens: Literal[16384] = 16384
    completion_usage_below_request_bound_count: Literal[571] = 571
    completion_usage_at_request_bound_count: Literal[1] = 1
    one_token_accounting_margin_call_count: Literal[0] = 0
    two_or_more_excess_token_call_count: Literal[0] = 0
    finish_reason_stop_count: Literal[571] = 571
    finish_reason_length_count: Literal[1] = 1
    usage_delta_cells: tuple[UsageDeltaCell, ...] = Field(min_length=5, max_length=5)
    actual_usage_charged_without_clipping_job_count: Literal[32] = 32
    private_reasoning_payload_count: Literal[0] = 0
    private_reasoning_hash_count: Literal[0] = 0
    raw_http_body_payload_count: Literal[0] = 0
    raw_request_body_payload_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_16k_provider_telemetry_audit.v1"] = (
        "finance_v26_exact_16k_provider_telemetry_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ProviderTelemetryAudit:
        expected = (
            ("below", "stop", "empty_final_content", 1),
            ("below", "stop", "invalid_json", 2),
            ("below", "stop", "invalid_response_contract", 33),
            ("below", "stop", "usable", 535),
            ("zero", "length", "reasoning_only_length_truncation", 1),
        )
        observed = tuple(
            (
                item.delta_bucket,
                item.finish_reason,
                item.completion_classification,
                item.call_count,
            )
            for item in self.usage_delta_cells
        )
        if observed != expected:
            raise ValueError("v26.106 Usage-delta cells changed")
        if self.audit_id != provider_telemetry_id(self):
            raise ValueError("v26.106 Provider telemetry identity changed")
        return self


class CompletionOutcomeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_job_denominator: Literal[32] = EXPECTED_JOB_COUNT
    terminal_counts: dict[str, int]
    completion_unusable_job_count: Literal[14] = 14
    instrument_failure_job_count: Literal[2] = 2
    model_invalid_trajectory_count: Literal[1] = 1
    model_valid_trajectory_count: Literal[0] = 0
    typed_no_call_job_count: Literal[17] = 17
    typed_budget_terminal_count: Literal[15] = 15
    provider_transport_failure_job_count: Literal[0] = 0
    telemetry_only_failure_job_count: Literal[0] = 0
    completion_failure_counts: dict[str, int]
    completion_failure_call_count: Literal[37] = 37
    decision_completion_failure_call_count: Literal[36] = 36
    final_answer_completion_failure_call_count: Literal[1] = 1
    rescue_attempt_job_count: Literal[23] = 23
    rescue_provider_call_job_count: Literal[23] = 23
    rescued_usable_request_count: Literal[23] = 23
    rescue_completion_failure_count: Literal[0] = 0
    terminal_second_completion_failure_after_rescue_count: Literal[14] = 14
    completion_unusable_cp95_upper_32: float = Field(gt=0.59, lt=0.60)
    typed_no_call_cp95_upper_32: float = Field(gt=0.68, lt=0.69)
    typed_no_call_gate_passed: Literal[False] = False
    completion_usability_gate_passed: Literal[False] = False
    reasoning_only_length_failure_observed: Literal[True] = True
    partial_length_failure_observed: Literal[False] = False
    single_stage_completion_bound_ladder_ended: Literal[True] = True
    semantic_validity_can_rescue_completion_or_budget_gate: Literal[False] = False
    program_closed_count: Literal[1] = 1
    terminal_node_completed_count: Literal[1] = 1
    postterminal_verification_completed_count: Literal[1] = 1
    mechanism_success_count: Literal[9] = 9
    independently_valid_trajectory_count: Literal[0] = 0
    requested_path_adherence_count: Literal[12] = 12
    calibration_only: Literal[True] = True
    role_or_state_evidence_row_count: Literal[0] = 0
    status: Literal["completion_and_budget_gates_failed"] = "completion_and_budget_gates_failed"
    schema_version: Literal["finance_v26_exact_16k_completion_outcome_audit.v1"] = (
        "finance_v26_exact_16k_completion_outcome_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CompletionOutcomeAudit:
        if self.terminal_counts != {
            "completion_unusable": 14,
            "instrument_failure": 2,
            "model_invalid_trajectory": 1,
            "typed_budget_no_call": 15,
        }:
            raise ValueError("v26.106 terminal counts changed")
        if self.completion_failure_counts != EXPECTED_COMPLETION_FAILURES:
            raise ValueError("v26.106 Completion failure counts changed")
        if self.audit_id != completion_outcome_id(self):
            raise ValueError("v26.106 Completion outcome identity changed")
        return self


class BudgetTerminalRow(FrozenModel):
    job_id: str = Field(min_length=1)
    historical_terminal_category: Literal["typed_budget_no_call", "instrument_failure"]
    raw_terminal_disposition: Literal["typed_budget_no_call"] = "typed_budget_no_call"
    no_call_reason: Literal["required_reserve_not_available"] = "required_reserve_not_available"
    request_index: int = Field(ge=17, le=24)
    request_kind: Literal["decision"] = "decision"
    cumulative_provider_tokens_before: int = Field(ge=0, le=240000)
    remaining_rollout_tokens_before: int = Field(ge=0, le=240000)
    request_token_upper_bound: int = Field(gt=0)
    required_reserve_tokens: Literal[16385, 32770]
    projected_upper_total: int = Field(gt=240000)
    projected_deficit_tokens: int = Field(gt=0)
    provider_call_made: Literal[False] = False
    rescue_provider_call_count: Literal[0, 1]
    observation_count: int = Field(ge=17, le=23)
    failed_observation_count: int = Field(ge=15, le=20)
    completed_program_node_count: Literal[0, 2]
    program_closed: Literal[False] = False
    terminal_node_completed: Literal[False] = False
    postterminal_verification_completed: Literal[False] = False
    verifier_replay_passed: bool
    repeated_call_signature_count: int = Field(ge=0)
    repeated_failed_call_signature_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_row(self) -> BudgetTerminalRow:
        if self.remaining_rollout_tokens_before != 240000 - self.cumulative_provider_tokens_before:
            raise ValueError("v26.106 budget-terminal remaining Usage changed")
        if self.projected_upper_total != (
            self.cumulative_provider_tokens_before
            + self.request_token_upper_bound
            + self.required_reserve_tokens
        ):
            raise ValueError("v26.106 budget-terminal projection changed")
        if self.projected_deficit_tokens != self.projected_upper_total - 240000:
            raise ValueError("v26.106 budget-terminal deficit changed")
        if self.rescue_provider_call_count == 0 and self.required_reserve_tokens != 32770:
            raise ValueError("v26.106 unused Rescue reserve changed")
        if self.rescue_provider_call_count == 1 and self.required_reserve_tokens != 16385:
            raise ValueError("v26.106 consumed Rescue reserve changed")
        return self


class DynamicBudgetAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    root_cause: Literal[
        "decision_request_plus_required_reserve_exceeded_remaining_rollout_budget"
    ] = BUDGET_ROOT_CAUSE
    exact_job_denominator: Literal[32] = EXPECTED_JOB_COUNT
    typed_no_call_job_count: Literal[17] = 17
    typed_budget_terminal_count: Literal[15] = 15
    instrument_terminal_with_typed_no_call_count: Literal[2] = 2
    terminal_rows: tuple[BudgetTerminalRow, ...] = Field(min_length=17, max_length=17)
    denial_reason_counts: dict[str, int]
    request_kind_counts: dict[str, int]
    cumulative_provider_tokens_minimum: Literal[171114] = 171_114
    cumulative_provider_tokens_maximum: Literal[199811] = 199_811
    remaining_rollout_tokens_minimum: Literal[40189] = 40_189
    remaining_rollout_tokens_maximum: Literal[68886] = 68_886
    projected_deficit_tokens_minimum: Literal[733] = 733
    projected_deficit_tokens_maximum: Literal[14912] = 14_912
    denied_request_index_minimum: Literal[17] = 17
    denied_request_index_maximum: Literal[24] = 24
    unused_rescue_reserve_terminal_count: Literal[9] = 9
    consumed_rescue_terminal_count: Literal[8] = 8
    required_reserve_16385_count: Literal[8] = 8
    required_reserve_32770_count: Literal[9] = 9
    no_call_provider_invocation_count: Literal[0] = 0
    provider_usage_over_rollout_ceiling_count: Literal[0] = 0
    denied_prompt_over_byte_ceiling_count: Literal[0] = 0
    final_answer_no_call_count: Literal[0] = 0
    program_closed_count: Literal[0] = 0
    terminal_node_completed_count: Literal[0] = 0
    postterminal_verification_completed_count: Literal[0] = 0
    completed_program_node_count_distribution: dict[str, int]
    failed_observation_count_minimum: Literal[15] = 15
    failed_observation_count_maximum: Literal[20] = 20
    repeated_call_signature_count_total: Literal[13] = 13
    repeated_failed_call_signature_count_total: Literal[13] = 13
    all_actual_provider_usage_charged_without_clipping: Literal[True] = True
    next_request_projection_does_not_prove_trajectory_completion: Literal[True] = True
    budget_ceiling_change_authorized: Literal[False] = False
    semantic_outcomes_can_rescue_budget_gate: Literal[False] = False
    status: Literal["dynamic_budget_gate_failed"] = "dynamic_budget_gate_failed"
    schema_version: Literal["finance_v26_exact_16k_dynamic_budget_audit.v1"] = (
        "finance_v26_exact_16k_dynamic_budget_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DynamicBudgetAudit:
        if self.denial_reason_counts != {"required_reserve_not_available": 17}:
            raise ValueError("v26.106 budget denial reasons changed")
        if self.request_kind_counts != {"decision": 17}:
            raise ValueError("v26.106 budget request kinds changed")
        if self.completed_program_node_count_distribution != {"0": 14, "2": 3}:
            raise ValueError("v26.106 no-call Program progress changed")
        job_ids = tuple(item.job_id for item in self.terminal_rows)
        if job_ids != tuple(sorted(set(job_ids))):
            raise ValueError("v26.106 budget-terminal rows are not canonical")
        if self.audit_id != dynamic_budget_id(self):
            raise ValueError("v26.106 dynamic-budget identity changed")
        return self


class InstrumentReplayFailureRow(FrozenModel):
    job_id: str = Field(min_length=1)
    historical_result_id: str = Field(min_length=1)
    raw_execution_relative_path: str = Field(min_length=1)
    raw_execution_sha256: str = Field(min_length=64, max_length=64)
    raw_terminal_disposition: Literal["typed_budget_no_call"] = "typed_budget_no_call"
    historical_terminal_category: Literal["instrument_failure"] = "instrument_failure"
    provider_call_count: Literal[17, 19]
    no_call_reason: Literal["required_reserve_not_available"] = "required_reserve_not_available"
    observation_count: Literal[17, 19]
    replayed_observation_count: Literal[16, 18]
    replay_failure_id: Literal["observation:2:unknown_tool", "observation:7:unknown_tool"]
    failing_observation_index: Literal[2, 7]
    failing_observation_id: str = Field(min_length=1)
    selected_tool_id: Literal["open_document"] = "open_document"
    observation_status: Literal["failed"] = "failed"
    observation_error_code: Literal["unknown_or_unselectable_tool"] = "unknown_or_unselectable_tool"
    observation_error_message: Literal[
        "The selected tool is not available in the public environment."
    ] = "The selected tool is not available in the public environment."
    observation_result_is_empty: Literal[True] = True
    environment_manifest_id: str = Field(min_length=1)
    environment_tool_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    selected_tool_absent_from_environment: Literal[True] = True
    runner_typed_rejection_matches_observation: Literal[True] = True
    verifier_recorded_unknown_tool_without_replaying_result: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> InstrumentReplayFailureRow:
        if self.replayed_observation_count != self.observation_count - 1:
            raise ValueError("v26.106 Replay deficit changed")
        if self.replay_failure_id != f"observation:{self.failing_observation_index}:unknown_tool":
            raise ValueError("v26.106 Replay failure index changed")
        if self.selected_tool_id in self.environment_tool_ids:
            raise ValueError("v26.106 unknown tool unexpectedly entered the environment")
        return self


class InstrumentRootCauseAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    root_cause: Literal[
        "runtime_unknown_or_unselectable_tool_observation_not_replayed_by_verifier_v2"
    ] = INSTRUMENT_ROOT_CAUSE
    instrument_failure_job_count: Literal[2] = 2
    failure_rows: tuple[InstrumentReplayFailureRow, ...] = Field(min_length=2, max_length=2)
    raw_typed_budget_no_call_count: Literal[2] = 2
    response_telemetry_failure_count: Literal[0] = 0
    provider_usage_contract_failure_count: Literal[0] = 0
    provider_call_for_denied_request_count: Literal[0] = 0
    runner_source_relative_path: str = RUNNER_SOURCE_PATH
    runner_source_sha256: str = Field(min_length=64, max_length=64)
    verifier_source_relative_path: str = VERIFIER_SOURCE_PATH
    verifier_source_sha256: str = Field(min_length=64, max_length=64)
    runner_missing_tool_typed_rejection_branch_present: Literal[True] = True
    verifier_unknown_tool_early_continue_branch_present: Literal[True] = True
    exact_observable_root_cause_closed: Literal[True] = True
    model_selected_unavailable_tool_observed: Literal[True] = True
    model_error_can_be_reclassified_historically: Literal[False] = False
    historical_terminal_reclassified: Literal[False] = False
    prospective_replay_repair_must_preserve_model_authority: Literal[True] = True
    prospective_replay_repair_must_reconstruct_exact_typed_failure: Literal[True] = True
    completion_gate_failed_independently: Literal[True] = True
    dynamic_budget_gate_failed_independently: Literal[True] = True
    status: Literal["root_cause_localized"] = "root_cause_localized"
    schema_version: Literal["finance_v26_exact_16k_instrument_root_cause.v1"] = (
        "finance_v26_exact_16k_instrument_root_cause.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> InstrumentRootCauseAudit:
        job_ids = tuple(item.job_id for item in self.failure_rows)
        if job_ids != tuple(sorted(set(job_ids))):
            raise ValueError("v26.106 Instrument rows are not canonical")
        if self.audit_id != instrument_root_cause_id(self):
            raise ValueError("v26.106 Instrument root-cause identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    predecessor_instrument_root_cause_audit_id: str = Field(min_length=1)
    predecessor_dynamic_budget_audit_id: str = Field(min_length=1)
    next_permitted_stage: Literal[
        "authority_preserving_unknown_tool_replay_repair_and_true_two_stage_protocol_preflight_only"
    ] = NEXT_STAGE
    single_stage_completion_bound_ladder_ended: Literal[True] = True
    higher_single_stage_completion_bound_allowed: Literal[False] = False
    exact_32k_profile_registration_allowed: Literal[False] = False
    exact_16k_same_protocol_rerun_allowed: Literal[False] = False
    true_two_stage_thinking_decision_design_required: Literal[True] = True
    stage_one_and_stage_two_contracts_must_be_explicit: Literal[True] = True
    every_future_provider_call_thinking_enabled: Literal[True] = True
    private_reasoning_content_may_be_persisted_or_transferred: Literal[False] = False
    only_public_stage_output_may_cross_stage_boundary: Literal[True] = True
    fresh_model_config_taskpackage_contract_manifest_job_identities_required: Literal[True] = True
    fresh_per_stage_completion_and_usage_bounds_required: Literal[True] = True
    fresh_dynamic_rollout_budget_contract_required: Literal[True] = True
    complete_static_and_runner_preflight_required_before_provider_call: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    unknown_tool_runtime_rejection_semantics_frozen: Literal[True] = True
    verifier_must_replay_unknown_or_unselectable_tool_as_exact_typed_failure: Literal[True] = True
    verifier_repair_may_not_insert_or_choose_a_model_action: Literal[True] = True
    verifier_repair_must_pass_destructive_replay_controls: Literal[True] = True
    dynamic_budget_design_must_separate_request_and_required_reserves: Literal[True] = True
    next_request_fit_may_not_be_claimed_as_full_trajectory_adequacy: Literal[True] = True
    historical_v26_105_job_rerun_authorized: Literal[False] = False
    historical_v26_105_terminal_reclassification_authorized: Literal[False] = False
    semantic_outcomes_can_rescue_completion_budget_or_instrument_gate: Literal[False] = False
    calibration_sources_role_or_state_eligible: Literal[False] = False
    role_protocol_frozen: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    release_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_16k_postrun_transition.v1"] = (
        "finance_v26_exact_16k_postrun_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != transition_contract_id(self):
            raise ValueError("v26.106 transition identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_id: str = Field(min_length=1)
    mutation: str = Field(min_length=1)
    rejected: Literal[True] = True
    rejection_stage: Literal["offline_audit"] = "offline_audit"
    provider_calls_before_rejection: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_16k_postrun_mutation.v1"] = (
        "finance_v26_exact_16k_postrun_mutation.v1"
    )

    @model_validator(mode="after")
    def validate_result(self) -> MutationResult:
        if self.mutation_id != mutation_result_id(self):
            raise ValueError("v26.106 mutation identity changed")
        return self


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=30, max_length=30)
    mutation_count: Literal[30] = 30
    rejected_mutation_count: Literal[30] = 30
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_16k_postrun_destructive.v1"] = (
        "finance_v26_exact_16k_postrun_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.mutation for item in self.mutation_results)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.106 mutations are not canonical")
        if self.audit_id != destructive_audit_id(self):
            raise ValueError("v26.106 destructive identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: Literal[
        "finance_v26_106_thinking_16k_completion_calibration_postrun_audit_v1_20260822"
    ] = RUN_ID
    predecessor_preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    predecessor_execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    source_replay_audit_id: str = Field(min_length=1)
    execution_lineage_audit_id: str = Field(min_length=1)
    provider_telemetry_audit_id: str = Field(min_length=1)
    completion_outcome_audit_id: str = Field(min_length=1)
    dynamic_budget_audit_id: str = Field(min_length=1)
    instrument_root_cause_audit_id: str = Field(min_length=1)
    prospective_transition_contract_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=8, max_length=8)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=1, max_length=1
    )
    exact_job_denominator: Literal[32] = EXPECTED_JOB_COUNT
    provider_call_count: Literal[572] = EXPECTED_PROVIDER_CALL_COUNT
    provider_total_tokens: Literal[4780636] = EXPECTED_PROVIDER_TOTAL_TOKENS
    estimated_cost_usd: Literal["0.98291580800000008797"] = EXPECTED_COST
    completion_unusable_job_count: Literal[14] = 14
    instrument_failure_job_count: Literal[2] = 2
    typed_no_call_job_count: Literal[17] = 17
    provider_transport_failure_job_count: Literal[0] = 0
    independently_valid_trajectory_count: Literal[0] = 0
    exact_16k_request_binding_passed: Literal[True] = True
    dynamic_precall_binding_passed: Literal[True] = True
    provider_usage_semantics_passed: Literal[True] = True
    empirical_budget_adequacy_passed: Literal[False] = False
    response_telemetry_instrument_passed: Literal[True] = True
    verifier_replay_instrument_passed: Literal[False] = False
    completion_usability_passed: Literal[False] = False
    execution_integrity_passed: Literal[False] = False
    instrument_root_cause: Literal[
        "runtime_unknown_or_unselectable_tool_observation_not_replayed_by_verifier_v2"
    ] = INSTRUMENT_ROOT_CAUSE
    dynamic_budget_root_cause: Literal[
        "decision_request_plus_required_reserve_exceeded_remaining_rollout_budget"
    ] = BUDGET_ROOT_CAUSE
    reasoning_only_length_failure_observed: Literal[True] = True
    single_stage_completion_bound_ladder_ended: Literal[True] = True
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
    release_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    status: Literal["blocked"] = "blocked"
    next_permitted_stage: Literal[
        "authority_preserving_unknown_tool_replay_repair_and_true_two_stage_protocol_preflight_only"
    ] = NEXT_STAGE
    schema_version: Literal["finance_v26_exact_16k_postrun_audit_report.v1"] = (
        "finance_v26_exact_16k_postrun_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> PostrunAuditReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.106 report detail paths are not canonical")
        if self.implementation_source_files[0].relative_path != AUDIT_SOURCE_PATH:
            raise ValueError("v26.106 implementation binding changed")
        if self.report_id != postrun_report_id(self):
            raise ValueError("v26.106 report identity changed")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def source_replay_id(value: PostrunSourceReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_16k_postrun_source_replay:")


def execution_lineage_id(value: ExecutionLineageAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_16k_execution_lineage_audit:")


def provider_telemetry_id(value: ProviderTelemetryAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_16k_provider_telemetry_audit:")


def completion_outcome_id(value: CompletionOutcomeAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_16k_completion_outcome_audit:")


def dynamic_budget_id(value: DynamicBudgetAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_16k_dynamic_budget_audit:")


def instrument_root_cause_id(value: InstrumentRootCauseAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_16k_instrument_root_cause:")


def transition_contract_id(value: ProspectiveTransitionContract) -> str:
    return _identity(value, "contract_id", "finance_v26_exact_16k_postrun_transition:")


def mutation_result_id(value: MutationResult) -> str:
    return _identity(value, "mutation_id", "finance_v26_exact_16k_postrun_mutation:")


def destructive_audit_id(value: DestructiveAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_16k_postrun_destructive:")


def postrun_report_id(value: PostrunAuditReport) -> str:
    return _identity(value, "report_id", "finance_v26_exact_16k_postrun_audit_report:")


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
        raise ValueError(f"noncanonical v26.106 JSON: {path}")
    return payload


def _load_canonical_jsonl(path: Path) -> tuple[Any, ...]:
    rows = []
    for line in path.read_bytes().splitlines():
        payload = json.loads(line)
        if line != _canonical_bytes(payload):
            raise ValueError(f"noncanonical v26.106 JSONL row: {path}")
        rows.append(payload)
    return tuple(rows)


def _write_json(path: Path, value: Any) -> None:
    raw = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError(f"immutable v26.106 output changed: {path}")
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
    relative_root: Path | None = None,
) -> SourceReplayEntry:
    return SourceReplayEntry(
        relative_path=_relative(path, relative_root or package_root),
        source_kind=source_kind,
        expected_sha256=expected_sha256,
        observed_sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def _build_source_replay(
    package_root: Path,
    implementation_root: Path,
) -> PostrunSourceReplayAudit:
    preflight_dir = package_root / PREFLIGHT_DIR
    execution_dir = implementation_root / EXECUTION_DIR
    preflight = Exact16KRunnerPreflightReport.model_validate(
        _load_canonical_json(preflight_dir / "report.json")
    )
    bound = Exact16KRunnerSourceReplayAudit.model_validate(
        _load_canonical_json(preflight_dir / "source_replay_audit.json")
    )
    if (
        preflight.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or preflight.source_replay_audit_id != bound.audit_id
        or not preflight.exact_16k_execution_authorized
        or _sha256(preflight_dir / "report.json") != EXPECTED_PREFLIGHT_REPORT_SHA256
    ):
        raise ValueError("v26.106 authorizing preflight changed")
    entries = [
        _source_entry(
            path=package_root / item.relative_path,
            package_root=package_root,
            source_kind="v26_104_bound_source",
            expected_sha256=item.expected_sha256,
        )
        for item in bound.entries
    ]
    if len(entries) != EXPECTED_BOUND_SOURCE_COUNT:
        raise ValueError("v26.106 bound source denominator changed")
    preflight_files = sorted(path for path in preflight_dir.iterdir() if path.is_file())
    if len(preflight_files) != EXPECTED_PREFLIGHT_OUTPUT_COUNT:
        raise ValueError("v26.106 preflight output denominator changed")
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
                source_kind="v26_104_preflight_output",
                expected_sha256=expected,
            )
        )
    execution_files = sorted(path for path in execution_dir.rglob("*") if path.is_file())
    if len(execution_files) != EXPECTED_EXECUTION_FILE_COUNT:
        raise ValueError("v26.106 execution file denominator changed")
    for path in execution_files:
        entries.append(
            _source_entry(
                path=path,
                package_root=implementation_root,
                source_kind="v26_105_execution_file",
                expected_sha256=(
                    EXPECTED_EXECUTION_REPORT_SHA256
                    if path == execution_dir / "report.json"
                    else _sha256(path)
                ),
            )
        )
    source_path = implementation_root / AUDIT_SOURCE_PATH
    entries.append(
        _source_entry(
            path=source_path,
            package_root=implementation_root,
            source_kind="v26_106_implementation",
            expected_sha256=_sha256(source_path),
        )
    )
    ordered = tuple(sorted(entries, key=lambda item: item.relative_path))
    provisional = PostrunSourceReplayAudit.model_construct(audit_id="pending", entries=ordered)
    return PostrunSourceReplayAudit(audit_id=source_replay_id(provisional), entries=ordered)


class LoadedExecution(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    preflight: Exact16KRunnerPreflightReport
    source_replay: Exact16KRunnerSourceReplayAudit
    interpretation: Exact16KOutcomeInterpretationContract
    execution_contract: Exact16KExecutionContract
    manifest: Exact16KManifest
    checkpoint: tuple[ThinkingRepairJobResult, ...]
    results: tuple[ThinkingRepairJobResult, ...]
    raw_executions: tuple[Exact16KRawExecution, ...]
    raw_paths_by_job: dict[str, Path]
    provider_calls: tuple[Exact16KRawProviderCall, ...]
    provider_paths_by_id: dict[str, Path]
    raw_lineage: Exact16KRawLineageAudit
    report: Exact16KExecutionReport


def _load_execution(package_root: Path, implementation_root: Path) -> LoadedExecution:
    preflight_dir = package_root / PREFLIGHT_DIR
    execution_dir = implementation_root / EXECUTION_DIR
    preflight = Exact16KRunnerPreflightReport.model_validate(
        _load_canonical_json(preflight_dir / "report.json")
    )
    source_replay = Exact16KRunnerSourceReplayAudit.model_validate(
        _load_canonical_json(execution_dir / "online_source_replay_audit.json")
    )
    interpretation = Exact16KOutcomeInterpretationContract.model_validate(
        _load_canonical_json(preflight_dir / "outcome_interpretation_contract.json")
    )
    execution_contract = Exact16KExecutionContract.model_validate(
        _load_canonical_json(execution_dir / "execution_contract.json")
    )
    manifest = Exact16KManifest.model_validate(
        _load_canonical_json(execution_dir / "frozen_exact_16k_job_manifest.json")
    )
    checkpoint = tuple(
        ThinkingRepairJobResult.model_validate(item)
        for item in _load_canonical_jsonl(execution_dir / "exact_16k_job_results.checkpoint.jsonl")
    )
    results = tuple(
        ThinkingRepairJobResult.model_validate(item)
        for item in _load_canonical_json(execution_dir / "exact_16k_job_results.json")
    )
    raw_paths = sorted((execution_dir / "raw_execution").glob("*.json"))
    raw_executions = tuple(
        Exact16KRawExecution.model_validate(_load_canonical_json(path)) for path in raw_paths
    )
    raw_paths_by_job = {
        raw.job.job_id: path for raw, path in zip(raw_executions, raw_paths, strict=True)
    }
    provider_paths = sorted((execution_dir / "raw_provider_calls").rglob("call_*.json"))
    provider_calls = tuple(
        Exact16KRawProviderCall.model_validate(_load_canonical_json(path))
        for path in provider_paths
    )
    provider_paths_by_id = {
        item.provider_call_id: path
        for item, path in zip(provider_calls, provider_paths, strict=True)
    }
    raw_lineage = Exact16KRawLineageAudit.model_validate(
        _load_canonical_json(execution_dir / "raw_lineage_audit.json")
    )
    report = Exact16KExecutionReport.model_validate(
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
        or _sha256(execution_dir / "report.json") != EXPECTED_EXECUTION_REPORT_SHA256
    ):
        raise ValueError("v26.106 top-level execution identity changed")
    return LoadedExecution(
        preflight=preflight,
        source_replay=source_replay,
        interpretation=interpretation,
        execution_contract=execution_contract,
        manifest=manifest,
        checkpoint=checkpoint,
        results=results,
        raw_executions=raw_executions,
        raw_paths_by_job=raw_paths_by_job,
        provider_calls=provider_calls,
        provider_paths_by_id=provider_paths_by_id,
        raw_lineage=raw_lineage,
        report=report,
    )


def _build_execution_lineage(
    implementation_root: Path,
    loaded: LoadedExecution,
) -> ExecutionLineageAudit:
    execution_dir = implementation_root / EXECUTION_DIR
    manifest_ids = tuple(item.job_id for item in loaded.manifest.jobs)
    checkpoint_ids = tuple(item.job_id for item in loaded.checkpoint)
    result_ids = tuple(item.job_id for item in loaded.results)
    if manifest_ids != checkpoint_ids or manifest_ids != result_ids:
        raise ValueError("v26.106 checkpoint/result ordering changed")
    raw_by_job = {item.job.job_id: item for item in loaded.raw_executions}
    if tuple(sorted(raw_by_job)) != tuple(sorted(manifest_ids)):
        raise ValueError("v26.106 Raw denominator changed")
    provider_by_id = {item.provider_call_id: item for item in loaded.provider_calls}
    if len(provider_by_id) != EXPECTED_PROVIDER_CALL_COUNT:
        raise ValueError("v26.106 Provider identities are not unique")
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
            raise ValueError("v26.106 result-to-Raw binding changed")
        checkpoint_raw_passes += 1
        certificate_ids = {item.certificate_id for item in raw.provider_budget_audit.certificates}
        usage_by_index = {
            item.request_index: item for item in raw.provider_budget_audit.usage_records
        }
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
                raise ValueError("v26.106 Raw-to-Provider descriptor changed")
            descriptor_passes += 1
            provider = provider_by_id[provider_id]
            usage = usage_by_index[provider.call_index]
            if (
                provider.job_id != result.job_id
                or provider.artifact_id != json.loads(provider_path.read_bytes())["artifact_id"]
                or provider.provider_budget_certificate_id not in certificate_ids
                or usage.total_tokens != provider.provider_telemetry.total_tokens
                or usage.counted_tokens != usage.total_tokens
            ):
                raise ValueError("v26.106 Provider parent or Usage binding changed")
            provider_parent_passes += 1
    for descriptor in loaded.raw_lineage.files:
        path = execution_dir / descriptor.relative_path
        if _sha256(path) != descriptor.sha256 or path.stat().st_size != descriptor.byte_count:
            raise ValueError("v26.106 persisted Raw Lineage descriptor changed")
    execution_files = sorted(path for path in execution_dir.rglob("*") if path.is_file())
    json_files = [path for path in execution_files if path.suffix == ".json"]
    jsonl_files = [path for path in execution_files if path.suffix == ".jsonl"]
    if len(json_files) != 611 or len(jsonl_files) != 1:
        raise ValueError("v26.106 canonical file partition changed")
    payloads = [_load_canonical_json(path) for path in json_files]
    jsonl_rows = _load_canonical_jsonl(jsonl_files[0])
    private = sum(_contains_key(item, "reasoning_content") for item in payloads)
    raw_http = sum(_contains_key(item, "raw_http_body") for item in payloads)
    raw_request = sum(_contains_key(item, "raw_request_body") for item in payloads)
    if private or raw_http or raw_request:
        raise ValueError("v26.106 prohibited private payload key observed")
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
        "all_provider_calls_exact_16k_request_bound": all(
            item.request_max_tokens == 16384
            and item.request_binding_certificate.request_max_tokens == 16384
            for item in loaded.provider_calls
        ),
        "all_provider_calls_usage_semantics_bound": all(
            raw.provider_budget_audit.contract_id
            == loaded.execution_contract.provider_usage_semantics_contract_id
            for raw in loaded.raw_executions
        ),
        "all_actual_usage_charged_without_clipping": all(
            raw.provider_budget_audit.actual_usage_charged_without_clipping
            for raw in loaded.raw_executions
        ),
        "private_reasoning_payload_count": private,
        "private_reasoning_hash_count": sum(
            item.private_reasoning_content_hashed for item in loaded.provider_calls
        ),
        "raw_http_body_payload_count": raw_http,
        "raw_request_body_payload_count": raw_request,
    }
    provisional = ExecutionLineageAudit.model_construct(audit_id="pending", **values)
    return ExecutionLineageAudit(audit_id=execution_lineage_id(provisional), **values)


def _telemetry_payload(item: Exact16KRawProviderCall) -> dict[str, Any]:
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
        raise ValueError("v26.106 Provider Usage or Thinking telemetry is incomplete")
    return (
        prompt_tokens,
        completion_tokens,
        total_tokens,
        reasoning_tokens,
        reasoning_content_length,
    )


def _decimal_ratio(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        raise ValueError("v26.106 Completion Usage must be positive")
    return Decimal(numerator) / Decimal(denominator)


def _format_ratio(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_UP), "f")


def _nearest_rank(values: Sequence[Any], percentile: int) -> Any:
    if not values or not 1 <= percentile <= 100:
        raise ValueError("v26.106 invalid nearest-rank input")
    index = (len(values) * percentile + 99) // 100 - 1
    return values[index]


def _delta_bucket(delta: int) -> DeltaBucket:
    if delta < 0:
        return "below"
    if delta == 0:
        return "zero"
    if delta == 1:
        return "one"
    return "two_or_more"


def _attempts_by_provider(
    loaded: LoadedExecution,
) -> dict[tuple[str, int], Any]:
    attempts: dict[tuple[str, int], Any] = {}
    for raw in loaded.raw_executions:
        for attempt in raw.request_attempts:
            if not attempt.provider_call_made or attempt.provider_call_index is None:
                continue
            key = (raw.job.job_id, attempt.provider_call_index)
            if key in attempts:
                raise ValueError("v26.106 duplicate Provider attempt binding")
            attempts[key] = attempt
    if len(attempts) != EXPECTED_PROVIDER_CALL_COUNT:
        raise ValueError("v26.106 Provider attempt denominator changed")
    return attempts


def _build_provider_telemetry(loaded: LoadedExecution) -> ProviderTelemetryAudit:
    calls = loaded.provider_calls
    attempts = _attempts_by_provider(loaded)
    payloads = [_telemetry_payload(item) for item in calls]
    usage = [_required_usage(item.provider_telemetry) for item in calls]
    prompt_tokens = [item[0] for item in usage]
    completion_tokens = [item[1] for item in usage]
    total_tokens = [item[2] for item in usage]
    reasoning_tokens = [item[3] for item in usage]
    reasoning_lengths = [item[4] for item in usage]
    ratios = sorted(
        _decimal_ratio(reasoning, completion)
        for reasoning, completion in zip(reasoning_tokens, completion_tokens, strict=True)
    )
    sorted_completions = sorted(completion_tokens)
    cells: Counter[tuple[DeltaBucket, str, str]] = Counter()
    for call, completion in zip(calls, completion_tokens, strict=True):
        attempt = attempts[(call.job_id, call.call_index)]
        if attempt.disposition == "usable":
            classification = "usable"
        elif attempt.disposition == "completion_failure" and attempt.failure_artifact is not None:
            classification = attempt.failure_artifact.failure_type
        else:
            raise ValueError("v26.106 Provider attempt Completion classification changed")
        cells[
            (
                _delta_bucket(completion - call.request_max_tokens),
                call.provider_telemetry.finish_reason or "missing",
                classification,
            )
        ] += 1
    cell_rows = tuple(
        UsageDeltaCell(
            delta_bucket=bucket,
            finish_reason=finish_reason,
            completion_classification=classification,
            call_count=count,
        )
        for (bucket, finish_reason, classification), count in sorted(cells.items())
    )
    response_models = [item.get("response_model") for item in payloads]
    response_shapes = [item.get("response_shape", {}) for item in payloads]
    deltas = [
        completion - call.request_max_tokens
        for call, completion in zip(calls, completion_tokens, strict=True)
    ]
    values = {
        "provider_call_count": len(calls),
        "http_success_call_count": sum(item.provider_telemetry.http_success for item in calls),
        "exact_requested_model_count": sum(
            item.provider_telemetry.model_requested == "deepseek-v4-flash" for item in calls
        ),
        "exact_selected_model_count": sum(
            item.provider_telemetry.model_selected == "deepseek-v4-flash" for item in calls
        ),
        "exact_response_model_count": sum(item == "deepseek-v4-flash" for item in response_models),
        "fallback_count": sum(item.provider_telemetry.fallback_used for item in calls),
        "provider_native_tool_call_count": sum(
            bool(item.get("provider_native_tool_call_observed")) for item in response_shapes
        ),
        "model_discovery_call_count": sum(
            item.provider_telemetry.discovery_attempted for item in calls
        ),
        "usage_complete_count": sum(
            prompt >= 0 and completion >= 0 and total == prompt + completion
            for prompt, completion, total, _, _ in usage
        ),
        "thinking_telemetry_complete_count": sum(
            item.provider_telemetry.reasoning_content_present
            and reasoning_length > 0
            and reasoning > 0
            for item, reasoning, reasoning_length in zip(
                calls, reasoning_tokens, reasoning_lengths, strict=True
            )
        ),
        "response_envelope_preparse_count": sum(
            bool(item.get("response_envelope_captured_before_content_parse"))
            for item in response_shapes
        ),
        "exact_16k_request_certificate_count": sum(
            item.request_binding_certificate.request_max_tokens == 16384 for item in calls
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
        "non_reasoning_completion_tokens_total": sum(completion_tokens) - sum(reasoning_tokens),
        "reasoning_content_length_total": sum(reasoning_lengths),
        "estimated_cost_usd": format(
            sum((Decimal(item.estimated_cost_usd) for item in loaded.results), Decimal("0")),
            "f",
        ),
        "aggregate_reasoning_fraction": _format_ratio(
            _decimal_ratio(sum(reasoning_tokens), sum(completion_tokens))
        ),
        "minimum_call_reasoning_fraction": _format_ratio(ratios[0]),
        "median_call_reasoning_fraction": _format_ratio(_nearest_rank(ratios, 50)),
        "p95_call_reasoning_fraction": _format_ratio(_nearest_rank(ratios, 95)),
        "maximum_call_reasoning_fraction": _format_ratio(ratios[-1]),
        "zero_reasoning_call_count": sum(item == 0 for item in reasoning_tokens),
        "minimum_completion_tokens": sorted_completions[0],
        "median_completion_tokens": _nearest_rank(sorted_completions, 50),
        "p95_completion_tokens": _nearest_rank(sorted_completions, 95),
        "maximum_completion_tokens": sorted_completions[-1],
        "completion_usage_below_request_bound_count": sum(item < 0 for item in deltas),
        "completion_usage_at_request_bound_count": sum(item == 0 for item in deltas),
        "one_token_accounting_margin_call_count": sum(item == 1 for item in deltas),
        "two_or_more_excess_token_call_count": sum(item >= 2 for item in deltas),
        "finish_reason_stop_count": sum(
            item.provider_telemetry.finish_reason == "stop" for item in calls
        ),
        "finish_reason_length_count": sum(
            item.provider_telemetry.finish_reason == "length" for item in calls
        ),
        "usage_delta_cells": cell_rows,
        "actual_usage_charged_without_clipping_job_count": sum(
            item.provider_budget_audit.actual_usage_charged_without_clipping
            for item in loaded.raw_executions
        ),
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
    attempts = [attempt for raw in loaded.raw_executions for attempt in raw.request_attempts]
    completion_attempts = [item for item in attempts if item.disposition == "completion_failure"]
    failure_counts: Counter[str] = Counter()
    for item in results:
        failure_counts.update(item.completion_failure_counts)
    terminal_second_failures = sum(
        raw.terminal_disposition == "completion_unusable"
        and raw.rescue_provider_call_count == 1
        and raw.request_attempts[-1].phase == "primary"
        and raw.request_attempts[-1].disposition == "completion_failure"
        for raw in loaded.raw_executions
    )
    completion_cp = _cp_upper(14, 32)
    no_call_cp = _cp_upper(17, 32)
    if (
        abs(loaded.report.completion_unusable_cp95_upper_32 - completion_cp) > 1e-15
        or abs(loaded.report.typed_no_call_cp95_upper_32 - no_call_cp) > 1e-15
        or loaded.interpretation.length_failure_transition
        != "true_two_stage_thinking_decision_protocol_only"
    ):
        raise ValueError("v26.106 Gate or Clopper-Pearson replay changed")
    values = {
        "terminal_counts": dict(Counter(item.terminal_category for item in results)),
        "completion_unusable_job_count": sum(item.completion_unusable for item in results),
        "instrument_failure_job_count": sum(
            item.terminal_category == "instrument_failure" for item in results
        ),
        "model_invalid_trajectory_count": sum(
            item.terminal_category == "model_invalid_trajectory" for item in results
        ),
        "model_valid_trajectory_count": sum(
            item.terminal_category == "model_valid_trajectory" for item in results
        ),
        "typed_no_call_job_count": sum(item.typed_no_call for item in results),
        "typed_budget_terminal_count": sum(
            item.terminal_category == "typed_budget_no_call" for item in results
        ),
        "provider_transport_failure_job_count": sum(
            item.provider_transport_failure for item in results
        ),
        "telemetry_only_failure_job_count": sum(item.telemetry_only_failure for item in results),
        "completion_failure_counts": dict(sorted(failure_counts.items())),
        "completion_failure_call_count": len(completion_attempts),
        "decision_completion_failure_call_count": sum(
            item.request_kind == "decision" for item in completion_attempts
        ),
        "final_answer_completion_failure_call_count": sum(
            item.request_kind == "final_answer" for item in completion_attempts
        ),
        "rescue_attempt_job_count": sum(raw.rescue_attempt_count for raw in loaded.raw_executions),
        "rescue_provider_call_job_count": sum(
            raw.rescue_provider_call_count for raw in loaded.raw_executions
        ),
        "rescued_usable_request_count": sum(
            item.phase == "rescue" and item.disposition == "usable" for item in attempts
        ),
        "rescue_completion_failure_count": sum(
            item.phase == "rescue" and item.disposition == "completion_failure" for item in attempts
        ),
        "terminal_second_completion_failure_after_rescue_count": terminal_second_failures,
        "completion_unusable_cp95_upper_32": loaded.report.completion_unusable_cp95_upper_32,
        "typed_no_call_cp95_upper_32": loaded.report.typed_no_call_cp95_upper_32,
        "program_closed_count": sum(item.program_closed for item in results),
        "terminal_node_completed_count": sum(item.terminal_node_completed for item in results),
        "postterminal_verification_completed_count": sum(
            item.postterminal_verification_completed for item in results
        ),
        "mechanism_success_count": sum(item.mechanism_success for item in results),
        "independently_valid_trajectory_count": sum(item.independent_validity for item in results),
        "requested_path_adherence_count": sum(item.requested_path_adhered for item in results),
    }
    provisional = CompletionOutcomeAudit.model_construct(audit_id="pending", **values)
    return CompletionOutcomeAudit(audit_id=completion_outcome_id(provisional), **values)


def _build_dynamic_budget(loaded: LoadedExecution) -> DynamicBudgetAudit:
    results_by_job = {item.job_id: item for item in loaded.results}
    rows = []
    for raw in loaded.raw_executions:
        terminal = raw.provider_budget_audit.no_call_terminal
        if terminal is None:
            continue
        result = results_by_job[raw.job.job_id]
        certificates = {
            item.certificate_id: item for item in raw.provider_budget_audit.certificates
        }
        certificate = certificates[terminal.denied_certificate_id]
        final_attempt = raw.request_attempts[-1]
        if (
            terminal.provider_call_made
            or final_attempt.provider_call_made
            or final_attempt.disposition != "typed_budget_no_call"
            or certificate.provider_call_permitted
            or certificate.denial_reason != terminal.reason_code
            or certificate.request_index != terminal.request_index
            or raw.provider_budget_audit.cumulative_provider_tokens
            != certificate.cumulative_provider_tokens_before
        ):
            raise ValueError("v26.106 typed no-call lineage changed")
        rows.append(
            BudgetTerminalRow(
                job_id=result.job_id,
                historical_terminal_category=result.terminal_category,
                no_call_reason=terminal.reason_code,
                request_index=certificate.request_index,
                request_kind=certificate.request_kind,
                cumulative_provider_tokens_before=certificate.cumulative_provider_tokens_before,
                remaining_rollout_tokens_before=(
                    certificate.maximum_total_tokens - certificate.cumulative_provider_tokens_before
                ),
                request_token_upper_bound=certificate.request_token_upper_bound,
                required_reserve_tokens=certificate.required_reserve_tokens,
                projected_upper_total=certificate.projected_upper_total,
                projected_deficit_tokens=(
                    certificate.projected_upper_total - certificate.maximum_total_tokens
                ),
                rescue_provider_call_count=raw.rescue_provider_call_count,
                observation_count=len(raw.observations),
                failed_observation_count=result.failed_observation_count,
                completed_program_node_count=result.completed_program_node_count,
                program_closed=result.program_closed,
                terminal_node_completed=result.terminal_node_completed,
                postterminal_verification_completed=(result.postterminal_verification_completed),
                verifier_replay_passed=result.replay_result.passed,
                repeated_call_signature_count=result.repeated_call_signature_count,
                repeated_failed_call_signature_count=(result.repeated_failed_call_signature_count),
            )
        )
    ordered = tuple(sorted(rows, key=lambda item: item.job_id))
    deficits = [item.projected_deficit_tokens for item in ordered]
    cumulative = [item.cumulative_provider_tokens_before for item in ordered]
    remaining = [item.remaining_rollout_tokens_before for item in ordered]
    values = {
        "terminal_rows": ordered,
        "denial_reason_counts": dict(Counter(item.no_call_reason for item in ordered)),
        "request_kind_counts": dict(Counter(item.request_kind for item in ordered)),
        "cumulative_provider_tokens_minimum": min(cumulative),
        "cumulative_provider_tokens_maximum": max(cumulative),
        "remaining_rollout_tokens_minimum": min(remaining),
        "remaining_rollout_tokens_maximum": max(remaining),
        "projected_deficit_tokens_minimum": min(deficits),
        "projected_deficit_tokens_maximum": max(deficits),
        "denied_request_index_minimum": min(item.request_index for item in ordered),
        "denied_request_index_maximum": max(item.request_index for item in ordered),
        "unused_rescue_reserve_terminal_count": sum(
            item.rescue_provider_call_count == 0 for item in ordered
        ),
        "consumed_rescue_terminal_count": sum(
            item.rescue_provider_call_count == 1 for item in ordered
        ),
        "required_reserve_16385_count": sum(
            item.required_reserve_tokens == 16385 for item in ordered
        ),
        "required_reserve_32770_count": sum(
            item.required_reserve_tokens == 32770 for item in ordered
        ),
        "no_call_provider_invocation_count": sum(item.provider_call_made for item in ordered),
        "provider_usage_over_rollout_ceiling_count": sum(
            raw.provider_budget_audit.cumulative_provider_tokens > 240000
            for raw in loaded.raw_executions
        ),
        "denied_prompt_over_byte_ceiling_count": sum(
            next(
                item
                for item in raw.provider_budget_audit.certificates
                if raw.provider_budget_audit.no_call_terminal is not None
                and item.certificate_id
                == raw.provider_budget_audit.no_call_terminal.denied_certificate_id
            ).prompt_utf8_bytes
            > 60000
            for raw in loaded.raw_executions
            if raw.provider_budget_audit.no_call_terminal is not None
        ),
        "final_answer_no_call_count": sum(item.request_kind == "final_answer" for item in ordered),
        "program_closed_count": sum(item.program_closed for item in ordered),
        "terminal_node_completed_count": sum(item.terminal_node_completed for item in ordered),
        "postterminal_verification_completed_count": sum(
            item.postterminal_verification_completed for item in ordered
        ),
        "completed_program_node_count_distribution": {
            str(key): value
            for key, value in sorted(
                Counter(item.completed_program_node_count for item in ordered).items()
            )
        },
        "failed_observation_count_minimum": min(item.failed_observation_count for item in ordered),
        "failed_observation_count_maximum": max(item.failed_observation_count for item in ordered),
        "repeated_call_signature_count_total": sum(
            item.repeated_call_signature_count for item in ordered
        ),
        "repeated_failed_call_signature_count_total": sum(
            item.repeated_failed_call_signature_count for item in ordered
        ),
    }
    provisional = DynamicBudgetAudit.model_construct(audit_id="pending", **values)
    return DynamicBudgetAudit(audit_id=dynamic_budget_id(provisional), **values)


def _verify_root_cause_source(implementation_root: Path) -> tuple[str, str]:
    runner_path = implementation_root / RUNNER_SOURCE_PATH
    verifier_path = implementation_root / VERIFIER_SOURCE_PATH
    runner_source = runner_path.read_text()
    verifier_source = verifier_path.read_text()
    runner_needles = (
        "if spec is None:\n        result = AgentToolResult(",
        'error_code="unknown_or_unselectable_tool"',
        'error_message="The selected tool is not available in the public environment."',
    )
    verifier_needle = (
        'if spec is None:\n            failures.append(f"observation:{index}:unknown_tool")\n'
        "            observed.append(observation)\n            continue"
    )
    if (
        not all(item in runner_source for item in runner_needles)
        or verifier_needle not in verifier_source
    ):
        raise ValueError("v26.106 observable unknown-tool source branches changed")
    return _sha256(runner_path), _sha256(verifier_path)


def _build_instrument_root_cause(
    package_root: Path,
    implementation_root: Path,
    loaded: LoadedExecution,
) -> InstrumentRootCauseAudit:
    execution_dir = implementation_root / EXECUTION_DIR
    environments = {
        item["manifest_id"]: item
        for item in json.loads((package_root / ENVIRONMENT_MANIFEST_PATH).read_bytes())
    }
    raw_by_job = {item.job.job_id: item for item in loaded.raw_executions}
    instrument_results = sorted(
        (item for item in loaded.results if item.terminal_category == "instrument_failure"),
        key=lambda item: item.job_id,
    )
    rows = []
    for result in instrument_results:
        raw = raw_by_job[result.job_id]
        failures = result.replay_result.failure_ids
        if len(failures) != 1:
            raise ValueError("v26.106 Instrument Replay failure denominator changed")
        match = re.fullmatch(r"observation:(\d+):unknown_tool", failures[0])
        if match is None:
            raise ValueError("v26.106 Instrument Replay failure type changed")
        index = int(match.group(1))
        observation = raw.observations[index]
        environment = environments[raw.environment_manifest_id]
        tool_ids = tuple(item["tool_id"] for item in environment["tools"])
        terminal = raw.provider_budget_audit.no_call_terminal
        raw_path = execution_dir / result.raw_execution_artifact.relative_path
        if (
            terminal is None
            or raw.terminal_disposition != "typed_budget_no_call"
            or result.replay_result.passed
            or result.replay_result.replayed_observation_count != len(raw.observations) - 1
            or observation.call.tool_id != "open_document"
            or observation.status != "failed"
            or observation.error_code != "unknown_or_unselectable_tool"
            or observation.error_message
            != "The selected tool is not available in the public environment."
            or observation.result != {}
            or observation.call.tool_id in tool_ids
            or raw.provider_budget_audit.contract_failure_ids
        ):
            raise ValueError("v26.106 Instrument observable root cause changed")
        rows.append(
            InstrumentReplayFailureRow(
                job_id=result.job_id,
                historical_result_id=result.result_id,
                raw_execution_relative_path=result.raw_execution_artifact.relative_path,
                raw_execution_sha256=_sha256(raw_path),
                provider_call_count=len(raw.provider_call_ids),
                no_call_reason=terminal.reason_code,
                observation_count=len(raw.observations),
                replayed_observation_count=result.replay_result.replayed_observation_count,
                replay_failure_id=failures[0],
                failing_observation_index=index,
                failing_observation_id=observation.observation_id,
                observation_error_message=observation.error_message,
                environment_manifest_id=environment["manifest_id"],
                environment_tool_ids=tool_ids,
            )
        )
    runner_sha, verifier_sha = _verify_root_cause_source(implementation_root)
    values = {
        "failure_rows": tuple(rows),
        "response_telemetry_failure_count": sum(
            item.telemetry_failure for item in instrument_results
        ),
        "provider_usage_contract_failure_count": sum(
            bool(raw_by_job[item.job_id].provider_budget_audit.contract_failure_ids)
            for item in instrument_results
        ),
        "provider_call_for_denied_request_count": sum(
            bool(raw_by_job[item.job_id].request_attempts[-1].provider_call_made)
            for item in instrument_results
        ),
        "runner_source_sha256": runner_sha,
        "verifier_source_sha256": verifier_sha,
    }
    provisional = InstrumentRootCauseAudit.model_construct(audit_id="pending", **values)
    return InstrumentRootCauseAudit(audit_id=instrument_root_cause_id(provisional), **values)


def _build_transition(
    root_cause: InstrumentRootCauseAudit,
    budget: DynamicBudgetAudit,
) -> ProspectiveTransitionContract:
    values = {
        "predecessor_instrument_root_cause_audit_id": root_cause.audit_id,
        "predecessor_dynamic_budget_audit_id": budget.audit_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=transition_contract_id(provisional),
        **values,
    )


def _audit_gate(payload: dict[str, Any]) -> None:
    required = {
        "job_count": 32,
        "raw_count": 32,
        "provider_count": 572,
        "completion_unusable": 14,
        "typed_no_call": 17,
        "instrument_failures": 2,
        "length_failures": 1,
        "unknown_tool_replay_failures": 2,
        "one_token_margin_calls": 0,
        "two_plus_excess_calls": 0,
        "actual_usage_charged": True,
        "private_payload_count": 0,
        "raw_http_body_count": 0,
        "raw_request_body_count": 0,
        "historical_rerun_count": 0,
        "historical_reclassification_count": 0,
        "higher_single_stage_bound": False,
        "same_protocol_rerun": False,
        "two_stage_required": True,
        "unknown_tool_replay_repair_required": True,
        "private_reasoning_transfer": False,
        "provider_calls_authorized": False,
        "fresh_identities_required": True,
        "dynamic_budget_preflight_required": True,
        "semantic_rescue": False,
        "thinking_enabled": True,
        "role_authorized": False,
        "state_mapping_authorized": False,
        "production_contribution": 0,
        "next_stage": NEXT_STAGE,
    }
    if payload != required:
        raise ValueError("v26.106 destructive audit Gate rejected a mutation")


def _build_destructive() -> DestructiveAudit:
    baseline: dict[str, Any] = {
        "job_count": 32,
        "raw_count": 32,
        "provider_count": 572,
        "completion_unusable": 14,
        "typed_no_call": 17,
        "instrument_failures": 2,
        "length_failures": 1,
        "unknown_tool_replay_failures": 2,
        "one_token_margin_calls": 0,
        "two_plus_excess_calls": 0,
        "actual_usage_charged": True,
        "private_payload_count": 0,
        "raw_http_body_count": 0,
        "raw_request_body_count": 0,
        "historical_rerun_count": 0,
        "historical_reclassification_count": 0,
        "higher_single_stage_bound": False,
        "same_protocol_rerun": False,
        "two_stage_required": True,
        "unknown_tool_replay_repair_required": True,
        "private_reasoning_transfer": False,
        "provider_calls_authorized": False,
        "fresh_identities_required": True,
        "dynamic_budget_preflight_required": True,
        "semantic_rescue": False,
        "thinking_enabled": True,
        "role_authorized": False,
        "state_mapping_authorized": False,
        "production_contribution": 0,
        "next_stage": NEXT_STAGE,
    }
    mutations: dict[str, tuple[str, Any]] = {
        "allow_higher_single_stage_bound": ("higher_single_stage_bound", True),
        "allow_historical_job_rerun": ("historical_rerun_count", 1),
        "allow_historical_terminal_reclassification": (
            "historical_reclassification_count",
            1,
        ),
        "allow_private_reasoning_transfer": ("private_reasoning_transfer", True),
        "allow_provider_calls_before_preflight": ("provider_calls_authorized", True),
        "allow_role_execution": ("role_authorized", True),
        "allow_same_protocol_rerun": ("same_protocol_rerun", True),
        "allow_state_mapping": ("state_mapping_authorized", True),
        "change_next_stage": ("next_stage", "thinking_role_protocol_freeze_only"),
        "disable_thinking": ("thinking_enabled", False),
        "drop_one_job": ("job_count", 31),
        "drop_one_provider_artifact": ("provider_count", 571),
        "drop_one_raw_execution": ("raw_count", 31),
        "hide_completion_failures": ("completion_unusable", 0),
        "hide_instrument_failures": ("instrument_failures", 0),
        "hide_length_failure": ("length_failures", 0),
        "hide_typed_no_calls": ("typed_no_call", 0),
        "hide_unknown_tool_replay_failures": ("unknown_tool_replay_failures", 0),
        "invent_one_token_margin_call": ("one_token_margin_calls", 1),
        "invent_two_token_excess_call": ("two_plus_excess_calls", 1),
        "permit_stale_identities": ("fresh_identities_required", False),
        "persist_private_reasoning": ("private_payload_count", 1),
        "persist_raw_http_body": ("raw_http_body_count", 1),
        "persist_raw_request_body": ("raw_request_body_count", 1),
        "rescue_gate_with_semantics": ("semantic_rescue", True),
        "set_production_contribution": ("production_contribution", 1),
        "skip_dynamic_budget_preflight": ("dynamic_budget_preflight_required", False),
        "skip_true_two_stage_design": ("two_stage_required", False),
        "skip_unknown_tool_replay_repair": (
            "unknown_tool_replay_repair_required",
            False,
        ),
        "stop_charging_actual_usage": ("actual_usage_charged", False),
    }
    rows = []
    for name, (field, value) in sorted(mutations.items()):
        changed = dict(baseline)
        changed[field] = value
        try:
            _audit_gate(changed)
        except ValueError:
            provisional = MutationResult.model_construct(mutation_id="pending", mutation=name)
            rows.append(
                MutationResult(
                    mutation_id=mutation_result_id(provisional),
                    mutation=name,
                )
            )
        else:
            raise ValueError(f"v26.106 destructive mutation passed: {name}")
    values = {"mutation_results": tuple(rows)}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(audit_id=destructive_audit_id(provisional), **values)


def _detail_file(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def _implementation_source(implementation_root: Path) -> ImplementationSourceFile:
    path = implementation_root / AUDIT_SOURCE_PATH
    return ImplementationSourceFile(
        relative_path=AUDIT_SOURCE_PATH,
        sha256=_sha256(path),
    )


def build_thinking_16k_completion_calibration_postrun_audit(
    *,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path | None = None,
) -> PostrunAuditReport:
    current_root = implementation_root or Path(__file__).resolve().parents[4]
    source = _build_source_replay(package_root, current_root)
    loaded = _load_execution(package_root, current_root)
    lineage = _build_execution_lineage(current_root, loaded)
    provider = _build_provider_telemetry(loaded)
    completion = _build_completion_outcome(loaded)
    budget = _build_dynamic_budget(loaded)
    root_cause = _build_instrument_root_cause(package_root, current_root, loaded)
    transition = _build_transition(root_cause, budget)
    destructive = _build_destructive()
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source),
        ("execution_lineage_audit.json", lineage),
        ("provider_telemetry_audit.json", provider),
        ("completion_outcome_audit.json", completion),
        ("dynamic_budget_audit.json", budget),
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
        "dynamic_budget_audit_id": budget.audit_id,
        "instrument_root_cause_audit_id": root_cause.audit_id,
        "prospective_transition_contract_id": transition.contract_id,
        "destructive_audit_id": destructive.audit_id,
        "detail_files": details,
        "implementation_source_files": (_implementation_source(current_root),),
    }
    provisional = PostrunAuditReport.model_construct(report_id="pending", **values)
    report = PostrunAuditReport(report_id=postrun_report_id(provisional), **values)
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit the completed v26.105 exact-16K calibration without generation"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    parser.add_argument(
        "--implementation-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    args = parser.parse_args()
    report = build_thinking_16k_completion_calibration_postrun_audit(
        output_dir=args.output_dir,
        package_root=args.package_root,
        implementation_root=args.implementation_root,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
