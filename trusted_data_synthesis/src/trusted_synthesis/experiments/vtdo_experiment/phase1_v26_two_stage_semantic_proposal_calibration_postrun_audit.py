from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    ImplementationSourceFile,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_profile_and_manifest_preflight import (  # noqa: E501
    DetailFile,
    TwoStageManifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_calibration_execution import (  # noqa: E501
    ExecutionSourceReplayAudit,
    PreexecutionValidityAudit,
    TwoStageExecutionReport,
    TwoStageJobResult,
    TwoStageRawLineageAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_execution import (  # noqa: E501
    RawStageOneProviderCall,
    TwoStageRawExecution,
    TwoStageRunnerContract,
    load_two_stage_static_inputs,
    sha256_text,
    two_stage_runtime_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_runner_preflight import (  # noqa: E501
    OutcomeInterpretationContract,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_action_constructibility import (
    build_public_action_state,
    render_action_constructible_decision_prompt,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_semantic_proposal import (
    TWO_STAGE_RESPONSE_PROTOCOL_VERSION,
    StageOneSemanticProposalPayload,
    render_semantic_proposal_rescue_prompt,
)

RUN_ID: Final = "finance_v26_111_two_stage_semantic_proposal_calibration_postrun_audit_v1_20260823"
EXECUTION_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_110_two_stage_semantic_proposal_calibration_v1_20260823"
)
AUDIT_SOURCE_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_two_stage_semantic_proposal_calibration_postrun_audit.py"
)
EXPECTED_EXECUTION_REPORT_ID: Final = (
    "finance_v26_two_stage_execution_report:"
    "c1fe9d9dc947fb2d9ed1898b5f11f43174a1072a79a5b5d7b6515938d415834b"
)
EXPECTED_EXECUTION_REPORT_SHA256: Final = (
    "7794a4e74d62aa8835e01da4646470332ad47a0f5950651fad73604e55b45827"
)
EXPECTED_RAW_LINEAGE_ID: Final = (
    "finance_v26_two_stage_raw_lineage:"
    "519e8948f0d128891dcceb231ab25b5d0e6fb7c10c54016f4b92f88cbaedc951"
)
EXPECTED_RUNNER_CONTRACT_ID: Final = (
    "finance_v26_two_stage_runner_contract:"
    "34c9bc91fbab6fb571127a3904b318bf33ca533fa670aa4ca3eccf1de611bac1"
)
EXPECTED_SOURCE_REPLAY_ID: Final = (
    "finance_v26_two_stage_execution_source_replay:"
    "0f947f1cf99af08f1f17be70242a4182c0d0006e20f9f6e4314226ad694e441f"
)
EXPECTED_PREEXECUTION_AUDIT_ID: Final = (
    "finance_v26_preexecution_validity_audit:"
    "625434163b8129e9e29e248ee4a6b91d89904441654bd32e17831be546405424"
)
EXPECTED_INTERPRETATION_ID: Final = (
    "finance_v26_two_stage_outcome_interpretation:"
    "b0dbdf510758848d0a977d5b56f98dd2f25a7978951f6655408cfa73fbced859"
)
EXPECTED_EXECUTION_SOURCE_COUNT: Final = 1911
EXPECTED_EXECUTION_FILE_COUNT: Final = 105
EXPECTED_SOURCE_REPLAY_COUNT: Final = 2017
EXPECTED_JOB_COUNT: Final = 32
EXPECTED_PROVIDER_CALL_COUNT: Final = 64
EXPECTED_RAW_DESCRIPTOR_COUNT: Final = 96
NEXT_STAGE: Final = (
    "fresh_exact_response_grammar_taskpackage_contract_manifest_and_runner_preflight_only"
)
ROOT_CAUSE: Final = "exact_stage_one_response_grammar_not_model_visible"

SourceKind = Literal[
    "v26_110_bound_source",
    "v26_110_execution_file",
    "v26_111_implementation",
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
            raise ValueError("v26.111 source replay changed")
        return self


class PostrunSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    entries: tuple[SourceReplayEntry, ...] = Field(
        min_length=EXPECTED_SOURCE_REPLAY_COUNT,
        max_length=EXPECTED_SOURCE_REPLAY_COUNT,
    )
    execution_bound_source_count: Literal[1911] = EXPECTED_EXECUTION_SOURCE_COUNT
    execution_output_file_count: Literal[105] = EXPECTED_EXECUTION_FILE_COUNT
    audit_implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[2017] = EXPECTED_SOURCE_REPLAY_COUNT
    replay_pass_count: Literal[2017] = EXPECTED_SOURCE_REPLAY_COUNT
    replay_before_diagnostics: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_postrun_source_replay.v1"] = (
        "finance_v26_two_stage_postrun_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PostrunSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.111 source paths are not canonical")
        if self.audit_id != source_replay_id(self):
            raise ValueError("v26.111 source identity changed")
        return self


class ExecutionLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    execution_report_sha256: str = EXPECTED_EXECUTION_REPORT_SHA256
    source_replay_audit_id: str = EXPECTED_SOURCE_REPLAY_ID
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    raw_lineage_audit_id: str = EXPECTED_RAW_LINEAGE_ID
    checkpoint_row_count: Literal[32] = EXPECTED_JOB_COUNT
    final_result_count: Literal[32] = EXPECTED_JOB_COUNT
    raw_execution_count: Literal[32] = EXPECTED_JOB_COUNT
    provider_artifact_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    unique_provider_artifact_id_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    raw_descriptor_count: Literal[96] = EXPECTED_RAW_DESCRIPTOR_COUNT
    raw_descriptor_hash_pass_count: Literal[96] = EXPECTED_RAW_DESCRIPTOR_COUNT
    canonical_json_file_count: Literal[104] = 104
    canonical_json_file_pass_count: Literal[104] = 104
    canonical_jsonl_row_count: Literal[32] = EXPECTED_JOB_COUNT
    canonical_jsonl_row_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    checkpoint_final_match_count: Literal[32] = EXPECTED_JOB_COUNT
    result_raw_parent_match_count: Literal[32] = EXPECTED_JOB_COUNT
    raw_provider_parent_match_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    provider_telemetry_match_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    dynamic_certificate_match_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    exact_request_certificate_match_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    resource_certificate_match_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    private_reasoning_payload_count: Literal[0] = 0
    private_reasoning_hash_count: Literal[0] = 0
    raw_http_body_payload_count: Literal[0] = 0
    raw_request_body_payload_count: Literal[0] = 0
    historical_job_rerun_count: Literal[0] = 0
    historical_terminal_reclassification_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_execution_lineage_audit.v1"] = (
        "finance_v26_two_stage_execution_lineage_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionLineageAudit:
        if self.audit_id != execution_lineage_id(self):
            raise ValueError("v26.111 execution lineage identity changed")
        return self


class PhaseUsageRow(FrozenModel):
    phase: Literal["primary", "rescue"]
    call_count: Literal[32] = 32
    prompt_tokens: int = Field(gt=0)
    completion_tokens: int = Field(gt=0)
    reasoning_tokens: int = Field(gt=0)
    total_tokens: int = Field(gt=0)
    estimated_cost_usd: str = Field(min_length=1)
    minimum_prompt_utf8_bytes: int = Field(gt=0)
    maximum_prompt_utf8_bytes: int = Field(gt=0)
    reasoning_fraction: str = Field(min_length=1)


class ProviderTelemetryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    provider_call_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    http_success_call_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    exact_requested_model_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    exact_selected_model_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    exact_response_model_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    thinking_telemetry_complete_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    usage_complete_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    fallback_count: Literal[0] = 0
    provider_native_tool_call_count: Literal[0] = 0
    discovery_call_count: Literal[0] = 0
    prompt_tokens_total: Literal[98125] = 98_125
    completion_tokens_total: Literal[641955] = 641_955
    reasoning_tokens_total: Literal[626316] = 626_316
    non_reasoning_completion_tokens_total: Literal[15639] = 15_639
    provider_total_tokens: Literal[740080] = 740_080
    reasoning_content_length_total: Literal[2621540] = 2_621_540
    estimated_cost_usd: Literal["0.1928878056000000200"] = "0.1928878056000000200"
    finish_reason_stop_count: Literal[50] = 50
    finish_reason_length_count: Literal[14] = 14
    below_request_bound_call_count: Literal[51] = 51
    exact_request_bound_call_count: Literal[13] = 13
    one_token_accounting_margin_call_count: Literal[0] = 0
    two_or_more_excess_token_call_count: Literal[0] = 0
    response_payload_present_count: Literal[51] = 51
    response_payload_absent_count: Literal[13] = 13
    phase_rows: tuple[PhaseUsageRow, PhaseUsageRow]
    actual_usage_charged_without_clipping: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_provider_telemetry_audit.v1"] = (
        "finance_v26_two_stage_provider_telemetry_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ProviderTelemetryAudit:
        if tuple(item.phase for item in self.phase_rows) != ("primary", "rescue"):
            raise ValueError("v26.111 phase Usage order changed")
        if self.phase_rows[0].model_dump(mode="json") != {
            "phase": "primary",
            "call_count": 32,
            "prompt_tokens": 48248,
            "completion_tokens": 177998,
            "reasoning_tokens": 169442,
            "total_tokens": 226246,
            "estimated_cost_usd": "0.0559970656000000044",
            "minimum_prompt_utf8_bytes": 4889,
            "maximum_prompt_utf8_bytes": 5677,
            "reasoning_fraction": "0.951932044180",
        }:
            raise ValueError("v26.111 Primary Usage changed")
        if self.phase_rows[1].model_dump(mode="json") != {
            "phase": "rescue",
            "call_count": 32,
            "prompt_tokens": 49877,
            "completion_tokens": 463957,
            "reasoning_tokens": 456874,
            "total_tokens": 513834,
            "estimated_cost_usd": "0.1368907400000000156",
            "minimum_prompt_utf8_bytes": 5091,
            "maximum_prompt_utf8_bytes": 5879,
            "reasoning_fraction": "0.984733499010",
        }:
            raise ValueError("v26.111 Rescue Usage changed")
        if self.audit_id != provider_telemetry_id(self):
            raise ValueError("v26.111 Provider telemetry identity changed")
        return self


class ResponseShapeRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    provider_artifact_id: str = Field(min_length=1)
    phase: Literal["primary", "rescue"]
    response_sha256: str = Field(min_length=64, max_length=64)
    top_level_keys: tuple[str, ...] = Field(min_length=1)
    decision_kind: str | None = None
    state_id_present: bool
    stage_present: bool
    protocol_present: bool
    exact_response_protocol_present: bool
    exact_contract_accepted: Literal[False] = False
    validation_error_locations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_row(self) -> ResponseShapeRow:
        if self.top_level_keys != tuple(sorted(set(self.top_level_keys))):
            raise ValueError("v26.111 response keys are not canonical")
        if self.row_id != response_shape_row_id(self):
            raise ValueError("v26.111 response-shape identity changed")
        return self


class PromptDisclosureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_payload_field_names: tuple[str, ...] = Field(min_length=10, max_length=10)
    primary_response_contract_keys: tuple[str, ...] = Field(min_length=4, max_length=4)
    rescue_response_contract_keys: tuple[str, ...] = Field(min_length=5, max_length=5)
    primary_exact_field_names_disclosed: tuple[str, ...] = ("stage",)
    rescue_exact_field_names_disclosed: tuple[str, ...] = ("stage",)
    exact_payload_field_count: Literal[10] = 10
    primary_exact_field_name_disclosure_count: Literal[1] = 1
    rescue_exact_field_name_disclosure_count: Literal[1] = 1
    state_id_output_binding_explicit: Literal[False] = False
    decision_specific_null_and_empty_defaults_explicit: Literal[False] = False
    exact_protocol_output_field_explicit_in_primary: Literal[False] = False
    exact_protocol_output_field_explicit_in_rescue: Literal[False] = False
    one_proposal_top_level_shape_explicit: Literal[False] = False
    primary_prompt_hash_reproduction_count: Literal[32] = 32
    rescue_prompt_hash_reproduction_count: Literal[32] = 32
    primary_prompt_byte_count_reproduction_count: Literal[32] = 32
    rescue_prompt_byte_count_reproduction_count: Literal[32] = 32
    public_state_retained: Literal[True] = True
    private_reasoning_exposed: Literal[False] = False
    oracle_or_expected_semantics_exposed: Literal[False] = False
    status: Literal["exact_response_grammar_underdisclosed"] = (
        "exact_response_grammar_underdisclosed"
    )
    schema_version: Literal["finance_v26_two_stage_prompt_disclosure_audit.v1"] = (
        "finance_v26_two_stage_prompt_disclosure_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PromptDisclosureAudit:
        if self.exact_payload_field_names != tuple(
            sorted(StageOneSemanticProposalPayload.model_fields)
        ):
            raise ValueError("v26.111 exact response schema changed")
        if self.primary_response_contract_keys != (
            "decision_kinds",
            "low_level_wire_call_must_not_be_guessed",
            "private_reasoning_content_must_not_be_returned",
            "stage",
        ):
            raise ValueError("v26.111 Primary response contract changed")
        if self.rescue_response_contract_keys != (
            "host_will_only_serialize_the_selected_semantics",
            "model_must_select_every_semantic_field",
            "previous_response_content_reused",
            "private_reasoning_reused",
            "stage",
        ):
            raise ValueError("v26.111 Rescue response contract changed")
        if self.audit_id != prompt_disclosure_id(self):
            raise ValueError("v26.111 Prompt disclosure identity changed")
        return self


class ResponseInterfaceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[ResponseShapeRow, ...] = Field(min_length=51, max_length=51)
    response_payload_count: Literal[51] = 51
    primary_response_payload_count: Literal[31] = 31
    rescue_response_payload_count: Literal[20] = 20
    unique_top_level_key_set_count: Literal[46] = 46
    exact_top_level_key_set_count: Literal[0] = 0
    exact_schema_accept_count: Literal[0] = 0
    top_level_state_id_count: Literal[2] = 2
    top_level_decision_kind_count: Literal[28] = 28
    top_level_stage_count: Literal[2] = 2
    top_level_protocol_count: Literal[1] = 1
    exact_response_protocol_count: Literal[0] = 0
    top_level_tool_id_count: Literal[7] = 7
    top_level_direct_arguments_count: Literal[0] = 0
    primary_missing_state_id_count: Literal[31] = 31
    primary_acquire_public_input_count: Literal[28] = 28
    primary_missing_decision_kind_count: Literal[3] = 3
    rescue_missing_state_id_count: Literal[18] = 18
    rescue_missing_decision_kind_count: Literal[20] = 20
    response_serialization_failure_count: Literal[51] = 51
    semantic_compile_attempt_count: Literal[0] = 0
    stage_two_commit_attempt_count: Literal[0] = 0
    historical_terminal_reclassification_count: Literal[0] = 0
    semantic_correctness_inferable_from_rejected_shapes: Literal[False] = False
    status: Literal["response_interface_gate_failed"] = "response_interface_gate_failed"
    schema_version: Literal["finance_v26_two_stage_response_interface_audit.v1"] = (
        "finance_v26_two_stage_response_interface_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ResponseInterfaceAudit:
        row_ids = tuple(item.row_id for item in self.rows)
        if row_ids != tuple(sorted(set(row_ids))):
            raise ValueError("v26.111 response-shape rows are not canonical")
        if self.audit_id != response_interface_id(self):
            raise ValueError("v26.111 response-interface identity changed")
        return self


class CompletionRescueAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_job_denominator: Literal[32] = EXPECTED_JOB_COUNT
    terminal_counts: dict[str, int]
    primary_attempt_count: Literal[32] = 32
    rescue_attempt_count: Literal[32] = 32
    primary_serialization_failure_count: Literal[31] = 31
    primary_reasoning_only_length_failure_count: Literal[1] = 1
    rescue_serialization_failure_count: Literal[20] = 20
    rescue_reasoning_only_length_failure_count: Literal[12] = 12
    direct_usable_request_count: Literal[0] = 0
    rescued_usable_request_count: Literal[0] = 0
    rescue_success_count: Literal[0] = 0
    completion_unusable_job_count: Literal[12] = 12
    completion_unusable_cp95_upper_32: float = Field(gt=0.53, lt=0.54)
    model_invalid_trajectory_count: Literal[20] = 20
    provider_transport_failure_count: Literal[0] = 0
    typed_no_call_count: Literal[0] = 0
    instrument_failure_count: Literal[0] = 0
    primary_completion_tokens: Literal[177998] = 177_998
    rescue_completion_tokens: Literal[463957] = 463_957
    primary_reasoning_fraction: Literal["0.951932044180"] = "0.951932044180"
    rescue_reasoning_fraction: Literal["0.984733499010"] = "0.984733499010"
    rescue_minus_primary_prompt_bytes_minimum: Literal[189] = 189
    rescue_minus_primary_prompt_bytes_maximum: Literal[202] = 202
    rescue_prompt_larger_than_primary_count: Literal[32] = 32
    program_closed_count: Literal[0] = 0
    mechanism_success_count: Literal[0] = 0
    independently_valid_trajectory_count: Literal[0] = 0
    requested_path_adherence_count: Literal[0] = 0
    completion_usability_gate_passed: Literal[False] = False
    response_interface_gate_passed: Literal[False] = False
    semantic_behavior_floor_evaluable: Literal[False] = False
    same_v26_110_job_rerun_authorized: Literal[False] = False
    status: Literal["completion_and_response_interface_gates_failed"] = (
        "completion_and_response_interface_gates_failed"
    )
    schema_version: Literal["finance_v26_two_stage_completion_rescue_audit.v1"] = (
        "finance_v26_two_stage_completion_rescue_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CompletionRescueAudit:
        if self.terminal_counts != {
            "completion_unusable": 12,
            "model_invalid_trajectory": 20,
        }:
            raise ValueError("v26.111 terminal denominator changed")
        if self.audit_id != completion_rescue_id(self):
            raise ValueError("v26.111 Completion/Rescue identity changed")
        return self


class AuthorityInstrumentAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_job_denominator: Literal[32] = EXPECTED_JOB_COUNT
    exact_model_job_count: Literal[32] = EXPECTED_JOB_COUNT
    thinking_continuity_job_count: Literal[32] = EXPECTED_JOB_COUNT
    usage_complete_job_count: Literal[32] = EXPECTED_JOB_COUNT
    dynamic_precall_binding_job_count: Literal[32] = EXPECTED_JOB_COUNT
    exact_request_binding_job_count: Literal[32] = EXPECTED_JOB_COUNT
    rollout_budget_pass_job_count: Literal[32] = EXPECTED_JOB_COUNT
    native_tool_absence_job_count: Literal[32] = EXPECTED_JOB_COUNT
    fallback_absence_job_count: Literal[32] = EXPECTED_JOB_COUNT
    empirical_budget_adequacy_passed: Literal[True] = True
    typed_no_call_count: Literal[0] = 0
    instrument_failure_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    stage_two_commit_count: Literal[0] = 0
    stage_two_reversible_commit_empirical_denominator: Literal[0] = 0
    host_inserted_semantic_action_count: Literal[0] = 0
    observation_count: Literal[0] = 0
    preexecution_computed_validity_job_count: Literal[32] = 32
    preexecution_computed_mechanism_success_count: Literal[32] = 32
    preexecution_scripted_stage_two_commit_count: Literal[224] = 224
    preexecution_stage_two_provider_call_count: Literal[0] = 0
    v26_109_default_count_replaced_by_computed_rows: Literal[True] = True
    static_stage_two_authority_preflight_retained: Literal[True] = True
    empirical_stage_two_semantic_behavior_measured: Literal[False] = False
    capability_rows: Literal[0] = 0
    reachability_rows: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    release_rows: Literal[0] = 0
    production_contribution: Literal[0] = 0
    status: Literal["instrument_passed_behavior_unmeasured"] = (
        "instrument_passed_behavior_unmeasured"
    )
    schema_version: Literal["finance_v26_two_stage_authority_instrument_audit.v1"] = (
        "finance_v26_two_stage_authority_instrument_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> AuthorityInstrumentAudit:
        if self.audit_id != authority_instrument_id(self):
            raise ValueError("v26.111 authority/Instrument identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    observable_result: Literal["all_stage_one_requests_failed_before_first_semantic_commit"] = (
        "all_stage_one_requests_failed_before_first_semantic_commit"
    )
    supported_engineering_root_cause: Literal[
        "exact_stage_one_response_grammar_not_model_visible"
    ] = ROOT_CAUSE
    root_cause_claimed_as_sole_cause_of_model_behavior: Literal[False] = False
    exact_response_field_names_must_be_model_visible: Literal[True] = True
    state_id_binding_must_be_model_visible: Literal[True] = True
    decision_specific_field_requirements_must_be_model_visible: Literal[True] = True
    null_and_empty_defaults_must_be_model_visible: Literal[True] = True
    exact_response_protocol_field_must_be_model_visible: Literal[True] = True
    one_proposal_per_response_must_be_explicit: Literal[True] = True
    rescue_must_expose_same_exact_response_grammar: Literal[True] = True
    rescue_must_request_immediate_serialization: Literal[True] = True
    rescue_may_reuse_previous_response_content: Literal[False] = False
    rescue_may_reuse_private_reasoning: Literal[False] = False
    host_alias_normalization_authorized: Literal[False] = False
    host_semantic_choice_authorized: Literal[False] = False
    stage_two_provider_route_authorized: Literal[False] = False
    completion_profile_change_authorized: Literal[False] = False
    rollout_ceiling_change_authorized: Literal[False] = False
    model_change_authorized: Literal[False] = False
    v26_110_rerun_authorized: Literal[False] = False
    fresh_response_protocol_identity_required: Literal[True] = True
    fresh_prompt_identity_required: Literal[True] = True
    fresh_taskpackage_identity_required: Literal[True] = True
    fresh_contract_manifest_job_identities_required: Literal[True] = True
    exact_runner_preflight_required_before_provider_call: Literal[True] = True
    semantic_behavior_remains_unmeasured: Literal[True] = True
    repeated_engineering_sources_remain_role_ineligible: Literal[True] = True
    capability_reachability_state_release_forbidden: Literal[True] = True
    production_contribution: Literal[0] = 0
    next_permitted_stage: Literal[
        "fresh_exact_response_grammar_taskpackage_contract_manifest_and_runner_preflight_only"
    ] = NEXT_STAGE
    schema_version: Literal["finance_v26_two_stage_postrun_transition.v1"] = (
        "finance_v26_two_stage_postrun_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != transition_contract_id(self):
            raise ValueError("v26.111 transition identity changed")
        return self


class MutationResult(FrozenModel):
    result_id: str = Field(min_length=1)
    mutation: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0

    @model_validator(mode="after")
    def validate_result(self) -> MutationResult:
        if self.result_id != mutation_result_id(self):
            raise ValueError("v26.111 mutation identity changed")
        return self


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=20, max_length=20)
    mutation_count: Literal[20] = 20
    rejected_count: Literal[20] = 20
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_postrun_destructive_audit.v1"] = (
        "finance_v26_two_stage_postrun_destructive_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.mutation for item in self.mutation_results)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.111 mutations are not canonical")
        if self.audit_id != destructive_audit_id(self):
            raise ValueError("v26.111 destructive identity changed")
        return self


class PostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: Literal[
        "finance_v26_111_two_stage_semantic_proposal_calibration_postrun_audit_v1_20260823"
    ] = RUN_ID
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    execution_lineage_audit_id: str = Field(min_length=1)
    provider_telemetry_audit_id: str = Field(min_length=1)
    prompt_disclosure_audit_id: str = Field(min_length=1)
    response_interface_audit_id: str = Field(min_length=1)
    completion_rescue_audit_id: str = Field(min_length=1)
    authority_instrument_audit_id: str = Field(min_length=1)
    prospective_transition_contract_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=9, max_length=9)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=1, max_length=1
    )
    exact_job_denominator: Literal[32] = EXPECTED_JOB_COUNT
    provider_call_count: Literal[64] = EXPECTED_PROVIDER_CALL_COUNT
    execution_instrument_status: Literal["passed"] = "passed"
    response_interface_status: Literal["failed"] = "failed"
    completion_usability_status: Literal["failed"] = "failed"
    semantic_behavior_status: Literal["unmeasured"] = "unmeasured"
    historical_terminal_reclassification_count: Literal[0] = 0
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    next_permitted_stage: Literal[
        "fresh_exact_response_grammar_taskpackage_contract_manifest_and_runner_preflight_only"
    ] = NEXT_STAGE
    schema_version: Literal["finance_v26_two_stage_postrun_audit_report.v1"] = (
        "finance_v26_two_stage_postrun_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> PostrunAuditReport:
        if self.report_id != postrun_report_id(self):
            raise ValueError("v26.111 report identity changed")
        return self


class LoadedExecution(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    source_replay: ExecutionSourceReplayAudit
    contract: TwoStageRunnerContract
    interpretation: OutcomeInterpretationContract
    manifest: TwoStageManifest
    preexecution: PreexecutionValidityAudit
    checkpoint: tuple[TwoStageJobResult, ...]
    results: tuple[TwoStageJobResult, ...]
    raws: tuple[TwoStageRawExecution, ...]
    raw_paths: dict[str, Path]
    providers: tuple[RawStageOneProviderCall, ...]
    provider_paths: dict[str, Path]
    lineage: TwoStageRawLineageAudit
    report: TwoStageExecutionReport


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


def source_replay_id(value: PostrunSourceReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_postrun_source_replay:")


def execution_lineage_id(value: ExecutionLineageAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_execution_lineage:")


def provider_telemetry_id(value: ProviderTelemetryAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_provider_telemetry:")


def response_shape_row_id(value: ResponseShapeRow) -> str:
    return _identity(value, "row_id", "finance_v26_two_stage_response_shape:")


def prompt_disclosure_id(value: PromptDisclosureAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_prompt_disclosure:")


def response_interface_id(value: ResponseInterfaceAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_response_interface:")


def completion_rescue_id(value: CompletionRescueAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_completion_rescue:")


def authority_instrument_id(value: AuthorityInstrumentAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_authority_instrument:")


def transition_contract_id(value: ProspectiveTransitionContract) -> str:
    return _identity(value, "contract_id", "finance_v26_two_stage_postrun_transition:")


def mutation_result_id(value: MutationResult) -> str:
    return _identity(value, "result_id", "finance_v26_two_stage_postrun_mutation:")


def destructive_audit_id(value: DestructiveAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_postrun_destructive:")


def postrun_report_id(value: PostrunAuditReport) -> str:
    return _identity(value, "report_id", "finance_v26_two_stage_postrun_audit_report:")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    raw = path.read_bytes()
    payload = json.loads(raw)
    if raw != _canonical_bytes(payload):
        raise ValueError(f"noncanonical v26.110 JSON: {path}")
    return payload


def _load_jsonl(path: Path) -> tuple[Any, ...]:
    rows = []
    for line in path.read_bytes().splitlines():
        payload = json.loads(line)
        if line != _canonical_bytes(payload):
            raise ValueError(f"noncanonical v26.110 JSONL row: {path}")
        rows.append(payload)
    return tuple(rows)


def _write_json(path: Path, value: Any) -> None:
    raw = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError(f"immutable v26.111 output changed: {path}")
    path.write_bytes(raw)


def _relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def _source_entry(
    *,
    path: Path,
    root: Path,
    source_kind: SourceKind,
    expected_sha256: str,
) -> SourceReplayEntry:
    return SourceReplayEntry(
        relative_path=_relative(path, root),
        source_kind=source_kind,
        expected_sha256=expected_sha256,
        observed_sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def _contains_key(value: Any, key_name: str) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key) == key_name or _contains_key(item, key_name) for key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_key(item, key_name) for item in value)
    return False


def _build_source_replay(
    package_root: Path,
    implementation_root: Path,
) -> PostrunSourceReplayAudit:
    execution_dir = package_root / EXECUTION_DIR
    execution_source = ExecutionSourceReplayAudit.model_validate(
        _load_json(execution_dir / "online_source_replay_audit.json")
    )
    if execution_source.audit_id != EXPECTED_SOURCE_REPLAY_ID:
        raise ValueError("v26.111 execution source replay changed")
    entries = [
        _source_entry(
            path=package_root / item.relative_path,
            root=package_root,
            source_kind="v26_110_bound_source",
            expected_sha256=item.expected_sha256,
        )
        for item in execution_source.entries
    ]
    if len(entries) != EXPECTED_EXECUTION_SOURCE_COUNT:
        raise ValueError("v26.111 inherited source denominator changed")
    execution_files = sorted(path for path in execution_dir.rglob("*") if path.is_file())
    if len(execution_files) != EXPECTED_EXECUTION_FILE_COUNT:
        raise ValueError("v26.111 execution output denominator changed")
    for path in execution_files:
        entries.append(
            _source_entry(
                path=path,
                root=package_root,
                source_kind="v26_110_execution_file",
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
            root=implementation_root,
            source_kind="v26_111_implementation",
            expected_sha256=_sha256(source_path),
        )
    )
    ordered = tuple(sorted(entries, key=lambda item: item.relative_path))
    provisional = PostrunSourceReplayAudit.model_construct(audit_id="pending", entries=ordered)
    return PostrunSourceReplayAudit(audit_id=source_replay_id(provisional), entries=ordered)


def _load_execution(package_root: Path) -> LoadedExecution:
    execution_dir = package_root / EXECUTION_DIR
    source_replay = ExecutionSourceReplayAudit.model_validate(
        _load_json(execution_dir / "online_source_replay_audit.json")
    )
    contract = TwoStageRunnerContract.model_validate(
        _load_json(execution_dir / "execution_contract.json")
    )
    interpretation = OutcomeInterpretationContract.model_validate(
        _load_json(execution_dir / "outcome_interpretation_contract.json")
    )
    manifest = TwoStageManifest.model_validate(
        _load_json(execution_dir / "frozen_two_stage_job_manifest.json")
    )
    preexecution = PreexecutionValidityAudit.model_validate(
        _load_json(execution_dir / "preexecution_independent_validity_audit.json")
    )
    checkpoint = tuple(
        TwoStageJobResult.model_validate(item)
        for item in _load_jsonl(execution_dir / "two_stage_job_results.checkpoint.jsonl")
    )
    results = tuple(
        TwoStageJobResult.model_validate(item)
        for item in _load_json(execution_dir / "two_stage_job_results.json")
    )
    raw_paths = {
        TwoStageRawExecution.model_validate(_load_json(path)).job.job_id: path
        for path in sorted((execution_dir / "raw_execution").glob("*.json"))
    }
    raws = tuple(
        TwoStageRawExecution.model_validate(_load_json(raw_paths[job.job_id]))
        for job in manifest.jobs
    )
    provider_paths: dict[str, Path] = {}
    providers = []
    for path in sorted((execution_dir / "raw_provider_calls").glob("*/*.json")):
        artifact = RawStageOneProviderCall.model_validate(_load_json(path))
        if artifact.artifact_id in provider_paths:
            raise ValueError("v26.111 duplicate Provider artifact identity")
        provider_paths[artifact.artifact_id] = path
        providers.append(artifact)
    lineage = TwoStageRawLineageAudit.model_validate(
        _load_json(execution_dir / "raw_lineage_audit.json")
    )
    report = TwoStageExecutionReport.model_validate(_load_json(execution_dir / "report.json"))
    if (
        source_replay.audit_id != EXPECTED_SOURCE_REPLAY_ID
        or contract.contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or interpretation.contract_id != EXPECTED_INTERPRETATION_ID
        or preexecution.audit_id != EXPECTED_PREEXECUTION_AUDIT_ID
        or lineage.audit_id != EXPECTED_RAW_LINEAGE_ID
        or report.report_id != EXPECTED_EXECUTION_REPORT_ID
        or _sha256(execution_dir / "report.json") != EXPECTED_EXECUTION_REPORT_SHA256
    ):
        raise ValueError("v26.111 execution identity chain changed")
    return LoadedExecution(
        source_replay=source_replay,
        contract=contract,
        interpretation=interpretation,
        manifest=manifest,
        preexecution=preexecution,
        checkpoint=checkpoint,
        results=results,
        raws=raws,
        raw_paths=raw_paths,
        providers=tuple(providers),
        provider_paths=provider_paths,
        lineage=lineage,
        report=report,
    )


def _build_execution_lineage(
    package_root: Path,
    loaded: LoadedExecution,
) -> ExecutionLineageAudit:
    execution_dir = package_root / EXECUTION_DIR
    files = sorted(path for path in execution_dir.rglob("*") if path.is_file())
    json_files = tuple(
        path for path in files if path.name != "two_stage_job_results.checkpoint.jsonl"
    )
    for path in json_files:
        _load_json(path)
    checkpoint_payloads = _load_jsonl(execution_dir / "two_stage_job_results.checkpoint.jsonl")
    if loaded.checkpoint != loaded.results:
        raise ValueError("v26.111 checkpoint and final results differ")
    manifest_ids = tuple(item.job_id for item in loaded.manifest.jobs)
    if tuple(item.job_id for item in loaded.results) != manifest_ids:
        raise ValueError("v26.111 result order differs from the Manifest")
    if tuple(item.job.job_id for item in loaded.raws) != manifest_ids:
        raise ValueError("v26.111 Raw order differs from the Manifest")
    lineage_descriptors = {item.relative_path: item for item in loaded.lineage.files}
    descriptor_passes = 0
    for relative_path, descriptor in lineage_descriptors.items():
        path = execution_dir / relative_path
        if (
            path.is_file()
            and _sha256(path) == descriptor.sha256
            and path.stat().st_size == descriptor.byte_count
        ):
            descriptor_passes += 1
    provider_by_path = {
        _relative(path, execution_dir): next(
            item for item in loaded.providers if item.artifact_id == artifact_id
        )
        for artifact_id, path in loaded.provider_paths.items()
    }
    result_by_job = {item.job_id: item for item in loaded.results}
    raw_provider_parent = 0
    provider_telemetry_match = 0
    dynamic_match = 0
    request_match = 0
    resource_match = 0
    result_raw_match = 0
    for raw in loaded.raws:
        result = result_by_job[raw.job.job_id]
        raw_path = loaded.raw_paths[raw.job.job_id]
        if result.raw_execution_artifact.relative_path == _relative(
            raw_path, execution_dir
        ) and result.raw_execution_artifact.sha256 == _sha256(raw_path):
            result_raw_match += 1
        if len(raw.provider_call_artifacts) != len(raw.provider_telemetry):
            raise ValueError("v26.111 Raw Provider descriptor/telemetry count changed")
        if len(raw.attempts) != len(raw.provider_call_artifacts):
            raise ValueError("v26.111 Raw attempt/Provider count changed")
        for index, descriptor in enumerate(raw.provider_call_artifacts):
            artifact = provider_by_path[descriptor.relative_path]
            attempt = raw.attempts[index]
            if artifact.job_id == raw.job.job_id:
                raw_provider_parent += 1
            if artifact.provider_telemetry == raw.provider_telemetry[index]:
                provider_telemetry_match += 1
            if attempt.dynamic_certificate_id == artifact.dynamic_certificate.certificate_id:
                dynamic_match += 1
            if (
                attempt.request_binding_certificate_id
                == artifact.request_binding_certificate.certificate_id
            ):
                request_match += 1
            if attempt.resource_certificate_id == artifact.resource_certificate_id:
                resource_match += 1
    private_payloads = sum(
        _contains_key(item.response_payload, "private_reasoning_content")
        for item in loaded.providers
        if item.response_payload is not None
    )
    values: dict[str, Any] = {
        "checkpoint_row_count": len(loaded.checkpoint),
        "final_result_count": len(loaded.results),
        "raw_execution_count": len(loaded.raws),
        "provider_artifact_count": len(loaded.providers),
        "unique_provider_artifact_id_count": len(loaded.provider_paths),
        "raw_descriptor_count": len(lineage_descriptors),
        "raw_descriptor_hash_pass_count": descriptor_passes,
        "canonical_json_file_count": len(json_files),
        "canonical_json_file_pass_count": len(json_files),
        "canonical_jsonl_row_count": len(checkpoint_payloads),
        "canonical_jsonl_row_pass_count": len(checkpoint_payloads),
        "checkpoint_final_match_count": sum(
            left == right for left, right in zip(loaded.checkpoint, loaded.results, strict=True)
        ),
        "result_raw_parent_match_count": result_raw_match,
        "raw_provider_parent_match_count": raw_provider_parent,
        "provider_telemetry_match_count": provider_telemetry_match,
        "dynamic_certificate_match_count": dynamic_match,
        "exact_request_certificate_match_count": request_match,
        "resource_certificate_match_count": resource_match,
        "private_reasoning_payload_count": private_payloads,
        "private_reasoning_hash_count": sum(
            item.private_reasoning_content_hashed for item in loaded.providers
        ),
        "raw_http_body_payload_count": sum(
            item.raw_http_body_persisted for item in loaded.providers
        ),
        "raw_request_body_payload_count": sum(
            item.raw_request_body_persisted for item in loaded.providers
        ),
    }
    provisional = ExecutionLineageAudit.model_construct(audit_id="pending", **values)
    return ExecutionLineageAudit(audit_id=execution_lineage_id(provisional), **values)


def _phase_usage(
    phase: Literal["primary", "rescue"],
    providers: Sequence[RawStageOneProviderCall],
) -> PhaseUsageRow:
    rows = tuple(item for item in providers if item.phase == phase)
    telemetry = tuple(item.provider_telemetry for item in rows)
    completion = sum(int(item.completion_tokens or 0) for item in telemetry)
    reasoning = sum(int(item.reasoning_tokens or 0) for item in telemetry)
    cost = sum(
        (Decimal(str(item.estimated_cost)) for item in telemetry),
        Decimal("0"),
    )
    return PhaseUsageRow(
        phase=phase,
        call_count=len(rows),
        prompt_tokens=sum(int(item.prompt_tokens or 0) for item in telemetry),
        completion_tokens=completion,
        reasoning_tokens=reasoning,
        total_tokens=sum(int(item.total_tokens or 0) for item in telemetry),
        estimated_cost_usd=format(cost, "f"),
        minimum_prompt_utf8_bytes=min(item.dynamic_certificate.prompt_utf8_bytes for item in rows),
        maximum_prompt_utf8_bytes=max(item.dynamic_certificate.prompt_utf8_bytes for item in rows),
        reasoning_fraction=format(
            (Decimal(reasoning) / Decimal(completion)).quantize(Decimal("0.000000000001")),
            "f",
        ),
    )


def _build_provider_telemetry(loaded: LoadedExecution) -> ProviderTelemetryAudit:
    telemetry = tuple(item.provider_telemetry for item in loaded.providers)
    completion = sum(int(item.completion_tokens or 0) for item in telemetry)
    reasoning = sum(int(item.reasoning_tokens or 0) for item in telemetry)
    cost = sum(
        (Decimal(str(item.estimated_cost)) for item in telemetry),
        Decimal("0"),
    )
    values: dict[str, Any] = {
        "provider_call_count": len(telemetry),
        "http_success_call_count": sum(item.http_success for item in telemetry),
        "exact_requested_model_count": sum(
            item.model_requested == "deepseek-v4-flash" for item in telemetry
        ),
        "exact_selected_model_count": sum(
            item.model_selected == "deepseek-v4-flash" for item in telemetry
        ),
        "exact_response_model_count": sum(
            item.response_model == "deepseek-v4-flash" for item in telemetry
        ),
        "thinking_telemetry_complete_count": sum(
            bool(item.reasoning_content_present)
            and int(item.reasoning_content_length or 0) > 0
            and int(item.reasoning_tokens or 0) > 0
            for item in telemetry
        ),
        "usage_complete_count": sum(
            item.prompt_tokens is not None
            and item.completion_tokens is not None
            and item.reasoning_tokens is not None
            and item.total_tokens is not None
            for item in telemetry
        ),
        "fallback_count": sum(item.fallback_used for item in telemetry),
        "provider_native_tool_call_count": sum(
            item.response_shape.get("provider_native_tool_call_observed") is not False
            for item in telemetry
        ),
        "discovery_call_count": sum(item.discovery_attempted for item in telemetry),
        "prompt_tokens_total": sum(int(item.prompt_tokens or 0) for item in telemetry),
        "completion_tokens_total": completion,
        "reasoning_tokens_total": reasoning,
        "non_reasoning_completion_tokens_total": completion - reasoning,
        "provider_total_tokens": sum(int(item.total_tokens or 0) for item in telemetry),
        "reasoning_content_length_total": sum(
            int(item.reasoning_content_length or 0) for item in telemetry
        ),
        "estimated_cost_usd": format(cost, "f"),
        "finish_reason_stop_count": sum(item.finish_reason == "stop" for item in telemetry),
        "finish_reason_length_count": sum(item.finish_reason == "length" for item in telemetry),
        "below_request_bound_call_count": sum(
            int(item.completion_tokens or 0) < 16384 for item in telemetry
        ),
        "exact_request_bound_call_count": sum(
            int(item.completion_tokens or 0) == 16384 for item in telemetry
        ),
        "one_token_accounting_margin_call_count": sum(
            int(item.completion_tokens or 0) == 16385 for item in telemetry
        ),
        "two_or_more_excess_token_call_count": sum(
            int(item.completion_tokens or 0) >= 16386 for item in telemetry
        ),
        "response_payload_present_count": sum(
            item.response_payload is not None for item in loaded.providers
        ),
        "response_payload_absent_count": sum(
            item.response_payload is None for item in loaded.providers
        ),
        "phase_rows": (
            _phase_usage("primary", loaded.providers),
            _phase_usage("rescue", loaded.providers),
        ),
    }
    provisional = ProviderTelemetryAudit.model_construct(audit_id="pending", **values)
    return ProviderTelemetryAudit(audit_id=provider_telemetry_id(provisional), **values)


def _response_shape_row(artifact: RawStageOneProviderCall) -> ResponseShapeRow:
    payload = artifact.response_payload
    if payload is None:
        raise ValueError("v26.111 response-shape row lacks a public payload")
    try:
        StageOneSemanticProposalPayload.model_validate(payload)
    except ValidationError as exc:
        locations = tuple(
            sorted(
                f"{'.'.join(str(part) for part in item['loc'])}:{item['type']}"
                for item in exc.errors()
            )
        )
    else:
        raise ValueError("v26.111 unexpectedly accepted a historical semantic proposal")
    values: dict[str, Any] = {
        "job_id": artifact.job_id,
        "provider_artifact_id": artifact.artifact_id,
        "phase": artifact.phase,
        "response_sha256": str(artifact.provider_telemetry.response_hash),
        "top_level_keys": tuple(sorted(str(key) for key in payload)),
        "decision_kind": (
            payload.get("decision_kind") if isinstance(payload.get("decision_kind"), str) else None
        ),
        "state_id_present": isinstance(payload.get("state_id"), str),
        "stage_present": "stage" in payload,
        "protocol_present": "protocol" in payload,
        "exact_response_protocol_present": (
            payload.get("protocol") == TWO_STAGE_RESPONSE_PROTOCOL_VERSION
        ),
        "validation_error_locations": locations,
    }
    provisional = ResponseShapeRow.model_construct(row_id="pending", **values)
    return ResponseShapeRow(row_id=response_shape_row_id(provisional), **values)


def _build_response_interface(loaded: LoadedExecution) -> ResponseInterfaceAudit:
    rows = tuple(
        sorted(
            (
                _response_shape_row(item)
                for item in loaded.providers
                if item.response_payload is not None
            ),
            key=lambda item: item.row_id,
        )
    )
    primary = tuple(item for item in rows if item.phase == "primary")
    rescue = tuple(item for item in rows if item.phase == "rescue")
    expected_keys = tuple(sorted(StageOneSemanticProposalPayload.model_fields))
    values: dict[str, Any] = {
        "rows": rows,
        "response_payload_count": len(rows),
        "primary_response_payload_count": len(primary),
        "rescue_response_payload_count": len(rescue),
        "unique_top_level_key_set_count": len({item.top_level_keys for item in rows}),
        "exact_top_level_key_set_count": sum(item.top_level_keys == expected_keys for item in rows),
        "exact_schema_accept_count": 0,
        "top_level_state_id_count": sum(item.state_id_present for item in rows),
        "top_level_decision_kind_count": sum(item.decision_kind is not None for item in rows),
        "top_level_stage_count": sum(item.stage_present for item in rows),
        "top_level_protocol_count": sum(item.protocol_present for item in rows),
        "exact_response_protocol_count": sum(item.exact_response_protocol_present for item in rows),
        "top_level_tool_id_count": sum("tool_id" in item.top_level_keys for item in rows),
        "top_level_direct_arguments_count": sum(
            "direct_arguments" in item.top_level_keys for item in rows
        ),
        "primary_missing_state_id_count": sum(not item.state_id_present for item in primary),
        "primary_acquire_public_input_count": sum(
            item.decision_kind == "acquire_public_input" for item in primary
        ),
        "primary_missing_decision_kind_count": sum(item.decision_kind is None for item in primary),
        "rescue_missing_state_id_count": sum(not item.state_id_present for item in rescue),
        "rescue_missing_decision_kind_count": sum(item.decision_kind is None for item in rescue),
        "response_serialization_failure_count": sum(
            item.error == "semantic_proposal_not_exact_contract"
            for raw in loaded.raws
            for item in raw.attempts
        ),
        "semantic_compile_attempt_count": sum(len(raw.commits) for raw in loaded.raws),
        "stage_two_commit_attempt_count": sum(len(raw.commits) for raw in loaded.raws),
    }
    provisional = ResponseInterfaceAudit.model_construct(audit_id="pending", **values)
    return ResponseInterfaceAudit(audit_id=response_interface_id(provisional), **values)


def _prompt_payload(prompt: str) -> Mapping[str, Any]:
    _, separator, raw = prompt.partition("\n")
    if not separator:
        raise ValueError("v26.111 Prompt lacks its public JSON payload")
    payload = json.loads(raw)
    if not isinstance(payload, Mapping):
        raise ValueError("v26.111 Prompt payload is not an object")
    return payload


def _build_prompt_disclosure(
    package_root: Path,
    loaded: LoadedExecution,
) -> PromptDisclosureAudit:
    static = load_two_stage_static_inputs(package_root, package_root)
    raw_by_job = {item.job.job_id: item for item in loaded.raws}
    provider_by_job_phase = {(item.job_id, item.phase): item for item in loaded.providers}
    primary_hashes = 0
    rescue_hashes = 0
    primary_bytes = 0
    rescue_bytes = 0
    primary_contracts: set[tuple[str, ...]] = set()
    rescue_contracts: set[tuple[str, ...]] = set()
    for job in static.manifest.jobs:
        binding = two_stage_runtime_binding(static, job)
        state = build_public_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            (),
        )
        condition = (
            None
            if binding.source_registered_path.role == "capability"
            else binding.source_registered_path.path_strategy_id
        )
        primary = render_action_constructible_decision_prompt(
            instruction=binding.record.task_package.task.public.instruction,
            state=state,
            public_path_condition=condition,
        )
        raw = raw_by_job[job.job_id]
        first = raw.attempts[0]
        family = (
            first.model_failure_classification.family
            if first.model_failure_classification is not None
            else "channel_parse_failure"
        )
        subtype = (
            first.model_failure_classification.subtype
            if first.model_failure_classification is not None
            else str(first.completion_failure_type or "completion_failure")
        )
        rescue = render_semantic_proposal_rescue_prompt(
            primary,
            failure_family=family,
            failure_subtype=subtype,
        )
        primary_artifact = provider_by_job_phase[(job.job_id, "primary")]
        rescue_artifact = provider_by_job_phase[(job.job_id, "rescue")]
        primary_hashes += (
            sha256_text(primary) == primary_artifact.dynamic_certificate.request_prompt_sha256
        )
        rescue_hashes += (
            sha256_text(rescue) == rescue_artifact.dynamic_certificate.request_prompt_sha256
        )
        primary_bytes += (
            len(primary.encode("utf-8")) == primary_artifact.dynamic_certificate.prompt_utf8_bytes
        )
        rescue_bytes += (
            len(rescue.encode("utf-8")) == rescue_artifact.dynamic_certificate.prompt_utf8_bytes
        )
        primary_payload = _prompt_payload(primary)
        rescue_payload = _prompt_payload(rescue)
        primary_contract = primary_payload.get("response_contract")
        rescue_contract = rescue_payload.get("response_contract")
        if not isinstance(primary_contract, Mapping) or not isinstance(rescue_contract, Mapping):
            raise ValueError("v26.111 Prompt response contract is missing")
        primary_contracts.add(tuple(sorted(str(key) for key in primary_contract)))
        rescue_contracts.add(tuple(sorted(str(key) for key in rescue_contract)))
    if len(primary_contracts) != 1 or len(rescue_contracts) != 1:
        raise ValueError("v26.111 response-contract projection differs across Jobs")
    exact_fields = tuple(sorted(StageOneSemanticProposalPayload.model_fields))
    primary_keys = next(iter(primary_contracts))
    rescue_keys = next(iter(rescue_contracts))
    values: dict[str, Any] = {
        "exact_payload_field_names": exact_fields,
        "primary_response_contract_keys": primary_keys,
        "rescue_response_contract_keys": rescue_keys,
        "primary_exact_field_names_disclosed": tuple(sorted(set(exact_fields) & set(primary_keys))),
        "rescue_exact_field_names_disclosed": tuple(sorted(set(exact_fields) & set(rescue_keys))),
        "exact_payload_field_count": len(exact_fields),
        "primary_exact_field_name_disclosure_count": len(set(exact_fields) & set(primary_keys)),
        "rescue_exact_field_name_disclosure_count": len(set(exact_fields) & set(rescue_keys)),
        "primary_prompt_hash_reproduction_count": primary_hashes,
        "rescue_prompt_hash_reproduction_count": rescue_hashes,
        "primary_prompt_byte_count_reproduction_count": primary_bytes,
        "rescue_prompt_byte_count_reproduction_count": rescue_bytes,
    }
    provisional = PromptDisclosureAudit.model_construct(audit_id="pending", **values)
    return PromptDisclosureAudit(audit_id=prompt_disclosure_id(provisional), **values)


def _build_completion_rescue(loaded: LoadedExecution) -> CompletionRescueAudit:
    attempts = tuple(item for raw in loaded.raws for item in raw.attempts)
    primary = tuple(item for item in attempts if item.phase == "primary")
    rescue = tuple(item for item in attempts if item.phase == "rescue")
    prompt_deltas = tuple(
        raw.attempts[1].prompt_utf8_bytes - raw.attempts[0].prompt_utf8_bytes for raw in loaded.raws
    )
    terminal_counts = Counter(item.terminal_category for item in loaded.results)
    values: dict[str, Any] = {
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "primary_attempt_count": len(primary),
        "rescue_attempt_count": len(rescue),
        "primary_serialization_failure_count": sum(
            item.error == "semantic_proposal_not_exact_contract" for item in primary
        ),
        "primary_reasoning_only_length_failure_count": sum(
            item.completion_failure_type == "reasoning_only_length_truncation" for item in primary
        ),
        "rescue_serialization_failure_count": sum(
            item.error == "semantic_proposal_not_exact_contract" for item in rescue
        ),
        "rescue_reasoning_only_length_failure_count": sum(
            item.completion_failure_type == "reasoning_only_length_truncation" for item in rescue
        ),
        "direct_usable_request_count": sum(
            item.phase == "primary" and item.disposition == "usable" for item in attempts
        ),
        "rescued_usable_request_count": sum(
            item.phase == "rescue" and item.disposition == "usable" for item in attempts
        ),
        "rescue_success_count": sum(item.rescue_success for item in loaded.results),
        "completion_unusable_job_count": sum(item.completion_unusable for item in loaded.results),
        "completion_unusable_cp95_upper_32": loaded.report.completion_unusable_cp95_upper_32,
        "model_invalid_trajectory_count": sum(
            item.terminal_category == "model_invalid_trajectory" for item in loaded.results
        ),
        "provider_transport_failure_count": sum(
            item.provider_transport_failure for item in loaded.results
        ),
        "typed_no_call_count": sum(item.typed_no_call for item in loaded.results),
        "instrument_failure_count": sum(item.instrument_failure for item in loaded.results),
        "primary_completion_tokens": sum(
            int(item.provider_telemetry.completion_tokens or 0)
            for item in loaded.providers
            if item.phase == "primary"
        ),
        "rescue_completion_tokens": sum(
            int(item.provider_telemetry.completion_tokens or 0)
            for item in loaded.providers
            if item.phase == "rescue"
        ),
        "rescue_minus_primary_prompt_bytes_minimum": min(prompt_deltas),
        "rescue_minus_primary_prompt_bytes_maximum": max(prompt_deltas),
        "rescue_prompt_larger_than_primary_count": sum(item > 0 for item in prompt_deltas),
        "program_closed_count": sum(item.program_closed for item in loaded.results),
        "mechanism_success_count": sum(item.mechanism_success for item in loaded.results),
        "independently_valid_trajectory_count": sum(
            item.independent_validity for item in loaded.results
        ),
        "requested_path_adherence_count": sum(
            item.requested_path_adhered for item in loaded.results
        ),
    }
    provisional = CompletionRescueAudit.model_construct(audit_id="pending", **values)
    return CompletionRescueAudit(audit_id=completion_rescue_id(provisional), **values)


def _build_authority_instrument(loaded: LoadedExecution) -> AuthorityInstrumentAudit:
    values: dict[str, Any] = {
        "exact_model_job_count": sum(item.exact_model_passed for item in loaded.results),
        "thinking_continuity_job_count": sum(
            item.thinking_continuity_passed for item in loaded.results
        ),
        "usage_complete_job_count": sum(item.provider_usage_complete for item in loaded.results),
        "dynamic_precall_binding_job_count": sum(
            item.dynamic_precall_binding_passed for item in loaded.results
        ),
        "exact_request_binding_job_count": sum(
            item.exact_request_binding_passed for item in loaded.results
        ),
        "rollout_budget_pass_job_count": sum(item.rollout_budget_passed for item in loaded.results),
        "native_tool_absence_job_count": sum(item.native_tool_absent for item in loaded.results),
        "fallback_absence_job_count": sum(item.fallback_absent for item in loaded.results),
        "typed_no_call_count": sum(item.typed_no_call for item in loaded.results),
        "instrument_failure_count": sum(item.instrument_failure for item in loaded.results),
        "stage_two_provider_call_count": sum(
            item.stage_two_provider_call_count for item in loaded.results
        ),
        "stage_two_commit_count": sum(len(item.commits) for item in loaded.raws),
        "stage_two_reversible_commit_empirical_denominator": sum(
            len(item.commits) for item in loaded.raws
        ),
        "host_inserted_semantic_action_count": sum(
            item.host_semantic_action_inserted for item in loaded.results
        ),
        "observation_count": sum(item.observation_count for item in loaded.results),
        "preexecution_computed_validity_job_count": (loaded.preexecution.independently_valid_count),
        "preexecution_computed_mechanism_success_count": (
            loaded.preexecution.mechanism_success_count
        ),
        "preexecution_scripted_stage_two_commit_count": (
            sum(item.stage_two_commit_count for item in loaded.preexecution.rows)
        ),
        "preexecution_stage_two_provider_call_count": (
            loaded.preexecution.stage_two_provider_call_count
        ),
    }
    provisional = AuthorityInstrumentAudit.model_construct(audit_id="pending", **values)
    return AuthorityInstrumentAudit(audit_id=authority_instrument_id(provisional), **values)


def _build_transition() -> ProspectiveTransitionContract:
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending")
    return ProspectiveTransitionContract(contract_id=transition_contract_id(provisional))


def _audit_gate(values: Mapping[str, Any]) -> None:
    expected = {
        "execution_report_id": EXPECTED_EXECUTION_REPORT_ID,
        "job_count": 32,
        "provider_call_count": 64,
        "response_payload_count": 51,
        "exact_schema_accept_count": 0,
        "primary_field_disclosure_count": 1,
        "rescue_field_disclosure_count": 1,
        "primary_serialization_failure_count": 31,
        "rescue_serialization_failure_count": 20,
        "reasoning_only_length_failure_count": 13,
        "rescue_success_count": 0,
        "instrument_failure_count": 0,
        "stage_two_provider_call_count": 0,
        "stage_two_commit_count": 0,
        "historical_reclassification_count": 0,
        "root_cause": ROOT_CAUSE,
        "host_alias_normalization_authorized": False,
        "completion_profile_change_authorized": False,
        "fresh_identity_chain_required": True,
        "next_permitted_stage": NEXT_STAGE,
    }
    if dict(values) != expected:
        raise ValueError("v26.111 destructive Gate rejected changed evidence")


def _build_destructive() -> DestructiveAudit:
    baseline: dict[str, Any] = {
        "execution_report_id": EXPECTED_EXECUTION_REPORT_ID,
        "job_count": 32,
        "provider_call_count": 64,
        "response_payload_count": 51,
        "exact_schema_accept_count": 0,
        "primary_field_disclosure_count": 1,
        "rescue_field_disclosure_count": 1,
        "primary_serialization_failure_count": 31,
        "rescue_serialization_failure_count": 20,
        "reasoning_only_length_failure_count": 13,
        "rescue_success_count": 0,
        "instrument_failure_count": 0,
        "stage_two_provider_call_count": 0,
        "stage_two_commit_count": 0,
        "historical_reclassification_count": 0,
        "root_cause": ROOT_CAUSE,
        "host_alias_normalization_authorized": False,
        "completion_profile_change_authorized": False,
        "fresh_identity_chain_required": True,
        "next_permitted_stage": NEXT_STAGE,
    }
    _audit_gate(baseline)
    mutations: dict[str, tuple[str, Any]] = {
        "accept_one_historical_payload": ("exact_schema_accept_count", 1),
        "allow_completion_profile_change": ("completion_profile_change_authorized", True),
        "allow_host_alias_normalization": ("host_alias_normalization_authorized", True),
        "allow_stage_two_provider_call": ("stage_two_provider_call_count", 1),
        "change_execution_report": ("execution_report_id", "changed"),
        "change_root_cause": ("root_cause", "semantic_capability_failure"),
        "drop_fresh_identity_requirement": ("fresh_identity_chain_required", False),
        "drop_one_job": ("job_count", 31),
        "drop_one_primary_serialization_failure": (
            "primary_serialization_failure_count",
            30,
        ),
        "drop_one_provider_call": ("provider_call_count", 63),
        "drop_one_rescue_serialization_failure": (
            "rescue_serialization_failure_count",
            19,
        ),
        "drop_one_response_payload": ("response_payload_count", 50),
        "erase_length_failure": ("reasoning_only_length_failure_count", 12),
        "insert_historical_reclassification": ("historical_reclassification_count", 1),
        "invent_rescue_success": ("rescue_success_count", 1),
        "invent_stage_two_commit": ("stage_two_commit_count", 1),
        "mark_instrument_failure": ("instrument_failure_count", 1),
        "overstate_primary_field_disclosure": ("primary_field_disclosure_count", 10),
        "overstate_rescue_field_disclosure": ("rescue_field_disclosure_count", 10),
        "skip_response_grammar_preflight": (
            "next_permitted_stage",
            "two_stage_semantic_proposal_calibration_execution_only",
        ),
    }
    rows = []
    for name, (field, changed_value) in sorted(mutations.items()):
        changed = dict(baseline)
        changed[field] = changed_value
        try:
            _audit_gate(changed)
        except ValueError:
            provisional = MutationResult.model_construct(result_id="pending", mutation=name)
            rows.append(
                MutationResult(
                    result_id=mutation_result_id(provisional),
                    mutation=name,
                )
            )
        else:
            raise ValueError(f"v26.111 destructive mutation passed: {name}")
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


def build_two_stage_semantic_proposal_calibration_postrun_audit(
    *,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path | None = None,
) -> PostrunAuditReport:
    current_root = implementation_root or Path(__file__).resolve().parents[4]
    source = _build_source_replay(package_root, current_root)
    loaded = _load_execution(package_root)
    lineage = _build_execution_lineage(package_root, loaded)
    provider = _build_provider_telemetry(loaded)
    prompt = _build_prompt_disclosure(package_root, loaded)
    response = _build_response_interface(loaded)
    completion = _build_completion_rescue(loaded)
    authority = _build_authority_instrument(loaded)
    transition = _build_transition()
    destructive = _build_destructive()
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source),
        ("execution_lineage_audit.json", lineage),
        ("provider_telemetry_audit.json", provider),
        ("prompt_disclosure_audit.json", prompt),
        ("response_interface_audit.json", response),
        ("completion_rescue_audit.json", completion),
        ("authority_instrument_audit.json", authority),
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
    values: dict[str, Any] = {
        "source_replay_audit_id": source.audit_id,
        "execution_lineage_audit_id": lineage.audit_id,
        "provider_telemetry_audit_id": provider.audit_id,
        "prompt_disclosure_audit_id": prompt.audit_id,
        "response_interface_audit_id": response.audit_id,
        "completion_rescue_audit_id": completion.audit_id,
        "authority_instrument_audit_id": authority.audit_id,
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
        description="Audit v26.110 two-stage semantic Proposal calibration without generation"
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
    report = build_two_stage_semantic_proposal_calibration_postrun_audit(
        output_dir=args.output_dir,
        package_root=args.package_root,
        implementation_root=args.implementation_root,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
