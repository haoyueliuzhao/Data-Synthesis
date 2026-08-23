from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_execution as runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_online as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    evaluate_mechanism_estimand,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_semantic_action_rematerialization import (  # noqa: E501
    SemanticActionJob,
    SemanticActionStaticInputs,
    load_semantic_action_static_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501
    _actual_route,
    _progress_diagnostic,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    SemanticActionState,
    build_semantic_action_state,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    prompt_only_reference_payload,
    render_exact_canonical_action_abi_rescue_prompt,
    render_exact_canonical_action_prompt,
    render_exact_canonical_action_semantic_recovery_prompt,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_semantic_proposal import (
    ModelResultRejection,
    StageOneFinalAnswerPayload,
    parse_final_answer_payload,
)

RUN_ID: Final = "finance_v26_121_semantic_action_calibration_failure_audit_v1_20260823"
EXECUTION_DIR: Final = execution.OUTPUT_DIR
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_121_semantic_action_calibration_failure_audit_v1_20260823"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_semantic_action_calibration_failure_audit.py"
)
EXPECTED_EXECUTION_SOURCE_REPLAY_ID: Final = (
    "finance_v26_semantic_action_execution_source_replay:"
    "fc885e37adb84ef04673886809ce1820de4359dc464667b0acab442f626ee98b"
)
EXPECTED_RUNNER_CONTRACT_ID: Final = execution.EXPECTED_RUNNER_CONTRACT_ID
EXPECTED_MANIFEST_ID: Final = execution.EXPECTED_MANIFEST_ID
NEXT_STAGE: Final = (
    "fresh_privacy_first_capture_and_exact_final_response_grammar_"
    "taskpackage_contract_manifest_runner_preflight_only"
)
EXPECTED_PREDECESSOR_SOURCE_COUNT: Final = 2228
EXPECTED_FAILED_FILE_COUNT: Final = 294
EXPECTED_SOURCE_REPLAY_COUNT: Final = 2523
EXPECTED_CHECKPOINT_COUNT: Final = 5
EXPECTED_RAW_COUNT: Final = 31
EXPECTED_PROVIDER_ARTIFACT_COUNT: Final = 256
EXPECTED_RAW_BOUND_PROVIDER_COUNT: Final = 250
EXPECTED_ORPHAN_PROVIDER_COUNT: Final = 6
EXPECTED_COMPLETE_CHOICE_COUNT: Final = 188
EXPECTED_INCOMPLETE_JOB_SUFFIX: Final = (
    "053291d2a6af57a5bc72607a85ac9d87fcd9db72b05f20854cd7d0564509371f"
)

ExposureState = Literal["checkpoint", "raw_uncheckpointed", "provider_orphan"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_120_bound_source",
        "v26_120_failed_execution_file",
        "v26_121_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class FailureSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_source_replay_id: str = EXPECTED_EXECUTION_SOURCE_REPLAY_ID
    predecessor_bound_source_count: Literal[2228] = EXPECTED_PREDECESSOR_SOURCE_COUNT
    failed_execution_file_count: Literal[294] = EXPECTED_FAILED_FILE_COUNT
    audit_implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[2523] = EXPECTED_SOURCE_REPLAY_COUNT
    replay_pass_count: Literal[2523] = EXPECTED_SOURCE_REPLAY_COUNT
    entries: tuple[SourceReplayEntry, ...] = Field(
        min_length=EXPECTED_SOURCE_REPLAY_COUNT,
        max_length=EXPECTED_SOURCE_REPLAY_COUNT,
    )
    replay_before_diagnostics: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_action_failure_source_replay.v1"] = (
        "finance_v26_semantic_action_failure_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FailureSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))) or len(paths) != EXPECTED_SOURCE_REPLAY_COUNT:
            raise ValueError("v26.121 source replay paths changed")
        if any(item.expected_sha256 != item.observed_sha256 for item in self.entries):
            raise ValueError("v26.121 source replay contains a hash mismatch")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_failure_source_replay:"
        ):
            raise ValueError("v26.121 source replay identity changed")
        return self


class JobExposureRow(FrozenModel):
    row_id: str = Field(min_length=1)
    manifest_index: int = Field(ge=0, lt=32)
    job_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: str = Field(min_length=1)
    exposure_state: ExposureState
    checkpoint_present: bool
    raw_execution_present: bool
    persisted_provider_artifact_count: int = Field(gt=0, le=12)
    model_exposed: Literal[True] = True
    eligible_for_automatic_retry: Literal[False] = False
    historical_result_reclassified: Literal[False] = False
    schema_version: Literal["finance_v26_semantic_action_exposure_row.v1"] = (
        "finance_v26_semantic_action_exposure_row.v1"
    )

    @model_validator(mode="after")
    def validate_row(self) -> JobExposureRow:
        expected: ExposureState = (
            "checkpoint"
            if self.checkpoint_present
            else "raw_uncheckpointed"
            if self.raw_execution_present
            else "provider_orphan"
        )
        if self.exposure_state != expected:
            raise ValueError("v26.121 Job exposure state changed")
        if self.row_id != _identity(self, "row_id", "finance_v26_semantic_action_exposure_row:"):
            raise ValueError("v26.121 exposure-row identity changed")
        return self


class FailedExecutionLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    rows: tuple[JobExposureRow, ...] = Field(min_length=32, max_length=32)
    manifest_job_count: Literal[32] = 32
    checkpoint_job_count: Literal[5] = EXPECTED_CHECKPOINT_COUNT
    raw_execution_count: Literal[31] = EXPECTED_RAW_COUNT
    raw_uncheckpointed_job_count: Literal[26] = 26
    provider_orphan_job_count: Literal[1] = 1
    unopened_job_count: Literal[0] = 0
    exposed_job_count: Literal[32] = 32
    persisted_provider_artifact_count: Literal[256] = EXPECTED_PROVIDER_ARTIFACT_COUNT
    unique_provider_artifact_id_count: Literal[256] = EXPECTED_PROVIDER_ARTIFACT_COUNT
    raw_bound_provider_artifact_count: Literal[250] = EXPECTED_RAW_BOUND_PROVIDER_COUNT
    orphan_provider_artifact_count: Literal[6] = EXPECTED_ORPHAN_PROVIDER_COUNT
    operator_observed_unjournaled_response_count: Literal[1] = 1
    artifact_backed_provider_invocation_lower_bound: Literal[256] = EXPECTED_PROVIDER_ARTIFACT_COUNT
    operator_observed_provider_invocation_lower_bound: Literal[257] = 257
    checkpoint_schema_pass_count: Literal[5] = EXPECTED_CHECKPOINT_COUNT
    raw_execution_schema_pass_count: Literal[31] = EXPECTED_RAW_COUNT
    provider_artifact_schema_pass_count: Literal[256] = EXPECTED_PROVIDER_ARTIFACT_COUNT
    raw_descriptor_hash_pass_count: Literal[250] = EXPECTED_RAW_BOUND_PROVIDER_COUNT
    canonical_json_file_pass_count: Literal[293] = 293
    canonical_jsonl_row_pass_count: Literal[5] = EXPECTED_CHECKPOINT_COUNT
    incomplete_job_id: str = Field(min_length=1)
    incomplete_job_suffix: str = EXPECTED_INCOMPLETE_JOB_SUFFIX
    incomplete_job_persisted_call_count: Literal[6] = 6
    completed_execution_report_materialized: Literal[False] = False
    historical_job_rerun_count: Literal[0] = 0
    historical_result_reclassification_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_action_failed_lineage.v1"] = (
        "finance_v26_semantic_action_failed_lineage.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FailedExecutionLineageAudit:
        if tuple(item.manifest_index for item in self.rows) != tuple(range(32)):
            raise ValueError("v26.121 Manifest ordering changed")
        if Counter(item.exposure_state for item in self.rows) != Counter(
            {"checkpoint": 5, "raw_uncheckpointed": 26, "provider_orphan": 1}
        ):
            raise ValueError("v26.121 exposure partition changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_failed_lineage:"
        ):
            raise ValueError("v26.121 failed-lineage identity changed")
        return self


class PersistedProviderTelemetryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    persisted_provider_artifact_count: Literal[256] = EXPECTED_PROVIDER_ARTIFACT_COUNT
    http_success_artifact_count: Literal[225] = 225
    http_400_artifact_count: Literal[31] = 31
    exact_requested_model_count: Literal[256] = 256
    exact_selected_model_count: Literal[256] = 256
    exact_response_model_count: Literal[225] = 225
    missing_response_model_count: Literal[31] = 31
    fallback_count: Literal[0] = 0
    discovery_count: Literal[0] = 0
    provider_native_tool_call_count: Literal[0] = 0
    positive_thinking_telemetry_count: Literal[225] = 225
    complete_usage_count: Literal[225] = 225
    semantic_primary_call_count: Literal[192] = 192
    semantic_recovery_call_count: Literal[2] = 2
    final_primary_call_count: Literal[31] = 31
    final_abi_rescue_call_count: Literal[31] = 31
    exact_four_field_semantic_payload_count: Literal[194] = 194
    exact_prompt_visible_final_payload_count: Literal[31] = 31
    null_response_payload_count: Literal[31] = 31
    prompt_tokens_lower_bound: Literal[727617] = 727617
    completion_tokens_lower_bound: Literal[341264] = 341264
    reasoning_tokens_lower_bound: Literal[314039] = 314039
    provider_total_tokens_lower_bound: Literal[1068881] = 1068881
    reasoning_content_length_lower_bound: Literal[1343464] = 1343464
    estimated_cost_usd_lower_bound: str = "0.19742030000000001688"
    unjournaled_response_usage_unknown: Literal[True] = True
    private_reasoning_content_persisted_count: Literal[0] = 0
    private_reasoning_hash_persisted_count: Literal[0] = 0
    raw_http_body_persisted_count: Literal[0] = 0
    raw_request_body_persisted_count: Literal[0] = 0
    telemetry_values_are_lower_bounds_due_to_unjournaled_response: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_action_failed_provider_telemetry.v1"] = (
        "finance_v26_semantic_action_failed_provider_telemetry.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PersistedProviderTelemetryAudit:
        if (
            self.semantic_primary_call_count
            + self.semantic_recovery_call_count
            + self.final_primary_call_count
            + self.final_abi_rescue_call_count
            != self.persisted_provider_artifact_count
        ):
            raise ValueError("v26.121 request-phase denominator changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_failed_provider_telemetry:"
        ):
            raise ValueError("v26.121 Provider telemetry identity changed")
        return self


class CandidatePresentation(FrozenModel):
    action_id: str = Field(min_length=1)
    zero_based_position: int = Field(ge=0, le=7)
    description_utf8_bytes: int = Field(gt=0)
    candidate_family: str = Field(min_length=1)
    prompt_only_reference: bool
    selected_by_model: bool


class IndependentChoiceRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0, le=10)
    choice_phase: Literal["primary", "semantic_recovery"]
    response_attempt_phase: Literal["primary", "abi_rescue", "semantic_recovery"]
    state_id: str = Field(min_length=1)
    candidate_count: int = Field(ge=1, le=8)
    candidates: tuple[CandidatePresentation, ...] = Field(min_length=1, max_length=8)
    selected_action_id: str = Field(min_length=1)
    selected_zero_based_position: int | None = Field(default=None, ge=0, le=7)
    selected_description_utf8_bytes: int | None = Field(default=None, gt=0)
    selected_candidate_family: str | None = None
    selected_prompt_only_reference: bool | None = None
    visible_action_id_match: bool
    decision_kind_match: bool
    semantic_accepted: bool
    observation_status: Literal["succeeded", "failed"] | None = None
    public_progress_after_commit: bool | None = None
    completed_program_nodes_before: int = Field(ge=0)
    completed_program_nodes_after: int = Field(ge=0)
    program_node_progress: bool
    terminal_verification_ready_before: bool
    legal_no_progress_choice: bool
    ordinary_replan_after_legal_no_progress: bool
    schema_version: Literal["finance_v26_independent_semantic_choice_row.v1"] = (
        "finance_v26_independent_semantic_choice_row.v1"
    )

    @model_validator(mode="after")
    def validate_row(self) -> IndependentChoiceRow:
        if (
            len(self.candidates) != self.candidate_count
            or tuple(item.zero_based_position for item in self.candidates)
            != tuple(range(self.candidate_count))
            or sum(item.prompt_only_reference for item in self.candidates) != 1
            or sum(item.selected_by_model for item in self.candidates)
            != int(self.visible_action_id_match)
        ):
            raise ValueError("v26.121 Candidate presentation changed")
        if self.program_node_progress != (
            self.completed_program_nodes_after > self.completed_program_nodes_before
        ):
            raise ValueError("v26.121 Program-node progress changed")
        if self.row_id != _identity(self, "row_id", "finance_v26_independent_semantic_choice_row:"):
            raise ValueError("v26.121 Choice-row identity changed")
        return self


class CandidateLoadSummary(FrozenModel):
    candidate_count: int = Field(ge=1, le=8)
    choice_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    public_progress_count: int = Field(ge=0)
    program_node_progress_count: int = Field(ge=0)
    selected_reference_count: int = Field(ge=0)


class PublicActionOutcomeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[IndependentChoiceRow, ...] = Field(
        min_length=EXPECTED_COMPLETE_CHOICE_COUNT,
        max_length=EXPECTED_COMPLETE_CHOICE_COUNT,
    )
    complete_raw_job_count: Literal[31] = EXPECTED_RAW_COUNT
    semantic_choice_count: Literal[188] = EXPECTED_COMPLETE_CHOICE_COUNT
    visible_action_id_match_count: Literal[187] = 187
    decision_kind_match_count: Literal[187] = 187
    primary_choice_accept_count: Literal[184] = 184
    reversible_commit_count: Literal[186] = 186
    observation_count: Literal[155] = 155
    successful_observation_count: Literal[147] = 147
    failed_observation_count: Literal[8] = 8
    public_progress_choice_count: Literal[138] = 138
    program_node_progress_choice_count: Literal[45] = 45
    first_choice_job_count: Literal[31] = 31
    first_action_id_legal_job_count: Literal[30] = 30
    first_action_accepted_job_count: Literal[30] = 30
    first_action_public_progress_job_count: Literal[15] = 15
    semantic_rejection_count: Literal[2] = 2
    stale_public_state_rejection_count: Literal[1] = 1
    unknown_action_rejection_count: Literal[1] = 1
    semantic_recovery_job_count: Literal[2] = 2
    recovery_selected_different_action_count: Literal[2] = 2
    recovery_commit_count: Literal[2] = 2
    recovery_public_progress_count: Literal[1] = 1
    legal_no_progress_choice_count: Literal[17] = 17
    ordinary_replan_count: Literal[17] = 17
    ordinary_replan_eventual_progress_count: Literal[17] = 17
    singleton_choice_count: Literal[61] = 61
    multi_candidate_choice_count: Literal[127] = 127
    candidate_count_distribution: dict[str, int]
    candidate_load_summaries: tuple[CandidateLoadSummary, ...] = Field(min_length=8, max_length=8)
    selected_reference_count: Literal[116] = 116
    selected_nonreference_count: Literal[71] = 71
    selected_invisible_action_count: Literal[1] = 1
    selected_position_distribution: dict[str, int]
    first_selected_position_distribution: dict[str, int]
    selected_candidate_family_distribution: dict[str, int]
    selected_description_utf8_bytes_minimum: Literal[546] = 546
    selected_description_utf8_bytes_median: Literal[821] = 821
    selected_description_utf8_bytes_maximum: Literal[1031] = 1031
    program_closed_job_count: Literal[31] = 31
    terminal_node_completed_job_count: Literal[31] = 31
    terminal_verification_choice_count: Literal[31] = 31
    successful_terminal_verification_count: Literal[31] = 31
    final_commit_count: Literal[31] = 31
    final_answer_count: Literal[0] = 0
    mechanism_success_count: Literal[23] = 23
    requested_path_adherence_count: Literal[11] = 11
    independent_validity_count: Literal[0] = 0
    replay_v3_pass_count: Literal[31] = 31
    complete_raw_terminal_instrument_failure_count: Literal[31] = 31
    singleton_is_interface_diagnostic_not_capability_estimate: Literal[True] = True
    candidate_count_association_is_descriptive_not_causal: Literal[True] = True
    position_distribution_is_descriptive_not_position_invariance: Literal[True] = True
    prompt_only_reference_is_not_gold_action: Literal[True] = True
    schema_version: Literal["finance_v26_semantic_action_public_outcome_audit.v1"] = (
        "finance_v26_semantic_action_public_outcome_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PublicActionOutcomeAudit:
        if self.semantic_choice_count != len(self.rows):
            raise ValueError("v26.121 Choice denominator changed")
        if self.singleton_choice_count + self.multi_candidate_choice_count != len(self.rows):
            raise ValueError("v26.121 Singleton/Multi partition changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_public_outcome_audit:"
        ):
            raise ValueError("v26.121 public-outcome identity changed")
        return self


class FinalResponseInterfaceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    complete_raw_job_count: Literal[31] = 31
    final_primary_prompt_hash_match_count: Literal[31] = 31
    final_primary_prompt_json_lexical_cue_count: Literal[31] = 31
    final_primary_prompt_minimum_utf8_bytes: Literal[3029] = 3029
    final_primary_prompt_maximum_utf8_bytes: Literal[4842] = 4842
    model_visible_primary_exact_field_set: tuple[str, str] = (
        "answer",
        "rationale_summary",
    )
    parser_exact_field_set: tuple[str, str, str] = ("answer", "protocol", "stage")
    primary_field_set_alignment_count: Literal[0] = 0
    observed_exact_model_visible_primary_payload_count: Literal[31] = 31
    observed_primary_parser_rejection_count: Literal[31] = 31
    observed_primary_failure_subtype: Literal["final_answer_not_exact_object_contract"] = (
        "final_answer_not_exact_object_contract"
    )
    final_rescue_prompt_hash_match_count: Literal[31] = 31
    final_rescue_prompt_json_lexical_cue_count: Literal[0] = 0
    final_rescue_prompt_minimum_utf8_bytes: Literal[2252] = 2252
    final_rescue_prompt_maximum_utf8_bytes: Literal[2528] = 2528
    model_visible_rescue_exact_field_set: tuple[str] = ("answer",)
    rescue_field_set_alignment_count: Literal[0] = 0
    final_rescue_http_400_count: Literal[31] = 31
    final_rescue_response_model_missing_count: Literal[31] = 31
    final_rescue_response_body_persisted_count: Literal[0] = 0
    final_answer_completed_result_count: Literal[0] = 0
    exact_primary_root_cause: Literal[
        "final_response_contract_not_model_visible_or_parser_aligned"
    ] = "final_response_contract_not_model_visible_or_parser_aligned"
    prospective_rescue_root_cause: Literal[
        "json_object_response_format_without_json_lexical_prompt_cue"
    ] = "json_object_response_format_without_json_lexical_prompt_cue"
    rescue_root_cause_is_strong_localization_not_unique_provider_cause: Literal[True] = True
    provider_http_error_body_absence_prevents_causal_exclusivity: Literal[True] = True
    final_answer_semantics_empirically_unmeasured: Literal[True] = True
    semantic_action_selection_not_reclassified_by_final_interface_failure: Literal[True] = True
    schema_version: Literal["finance_v26_semantic_action_final_interface_audit.v1"] = (
        "finance_v26_semantic_action_final_interface_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FinalResponseInterfaceAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_final_interface_audit:"
        ):
            raise ValueError("v26.121 Final-interface identity changed")
        return self


class PrivacyPersistenceFailureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    incomplete_job_id: str = Field(min_length=1)
    incomplete_job_suffix: str = EXPECTED_INCOMPLETE_JOB_SUFFIX
    persisted_semantic_provider_artifact_count: Literal[6] = 6
    persisted_exact_four_field_payload_count: Literal[6] = 6
    persisted_usage_tokens_lower_bound: Literal[30786] = 30786
    operator_observed_unjournaled_parsed_response_count: Literal[1] = 1
    process_exception_class: Literal["pydantic_core.ValidationError"] = (
        "pydantic_core.ValidationError"
    )
    rejected_schema_name: Literal["RawActionProviderCall"] = "RawActionProviderCall"
    rejection_message: Literal["Raw semantic-action Provider binding or privacy changed"] = (
        "Raw semantic-action Provider binding or privacy changed"
    )
    rejected_payload_triggered_reasoning_key_privacy_scan: Literal[True] = True
    rejected_payload_exact_key_retained: Literal[False] = False
    rejected_payload_content_retained: Literal[False] = False
    rejected_payload_hash_retained: Literal[False] = False
    unjournaled_response_telemetry_retained: Literal[False] = False
    unjournaled_response_usage_retained: Literal[False] = False
    raw_execution_materialized: Literal[False] = False
    provider_artifact_materialized_for_rejected_response: Literal[False] = False
    telemetry_only_fallback_artifact_available: Literal[False] = False
    provider_artifact_validated_before_file_persistence: Literal[True] = True
    telemetry_ledger_append_occurs_after_artifact_validation: Literal[True] = True
    retry_blocked_by_six_orphan_provider_artifacts: Literal[True] = True
    retry_guard_provider_calls: Literal[0] = 0
    exact_failure_root_cause: Literal[
        "public_payload_privacy_rejection_precedes_telemetry_only_raw_persistence"
    ] = "public_payload_privacy_rejection_precedes_telemetry_only_raw_persistence"
    operator_observation_not_independently_replayable_from_payload_bytes: Literal[True] = True
    future_capture_must_persist_telemetry_before_public_payload_validation: Literal[True] = True
    future_invalid_public_payload_must_be_omitted_not_serialized: Literal[True] = True
    private_reasoning_persistence_remains_forbidden: Literal[True] = True
    schema_version: Literal["finance_v26_semantic_action_privacy_persistence_failure.v1"] = (
        "finance_v26_semantic_action_privacy_persistence_failure.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PrivacyPersistenceFailureAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_semantic_action_privacy_persistence_failure:",
        ):
            raise ValueError("v26.121 privacy-persistence identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    status: Literal["failed_execution_audited"] = "failed_execution_audited"
    next_permitted_stage: str = NEXT_STAGE
    all_v26_120_job_identities_retired: Literal[True] = True
    historical_job_rerun_recovery_or_reclassification_authorized: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    exact_semantic_action_protocol_must_be_preserved: Literal[True] = True
    candidate_language_and_authority_must_be_preserved: Literal[True] = True
    model_profile_thinking_completion_and_resource_bounds_must_be_preserved: Literal[True] = True
    abi_and_semantic_recovery_limits_must_be_preserved: Literal[True] = True
    final_response_grammar_must_be_shared_by_prompt_parser_primary_and_rescue: Literal[True] = True
    final_response_prompt_must_satisfy_json_mode_lexical_requirement: Literal[True] = True
    telemetry_must_persist_before_public_payload_validation: Literal[True] = True
    invalid_public_payload_content_persistence_authorized: Literal[False] = False
    fresh_response_protocol_taskpackage_contract_manifest_job_runner_execution_and_report_ids_required: Literal[  # noqa: E501
        True
    ] = True
    credential_free_exact_runner_preflight_required_before_provider_call: Literal[True] = True
    host_semantic_choice_or_repair_authorized: Literal[False] = False
    role_state_mapping_training_release_or_production_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_semantic_action_failure_transition.v1"] = (
        "finance_v26_semantic_action_failure_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_semantic_action_failure_transition:"
        ):
            raise ValueError("v26.121 transition identity changed")
        return self


class MutationResult(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[MutationResult, ...] = Field(min_length=12, max_length=12)
    mutation_count: Literal[12] = 12
    rejection_count: Literal[12] = 12
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_action_failure_destructive.v1"] = (
        "finance_v26_semantic_action_failure_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.name for item in self.mutations)
        if names != tuple(sorted(set(names))) or len(names) != 12:
            raise ValueError("v26.121 destructive controls changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_failure_destructive:"
        ):
            raise ValueError("v26.121 destructive-audit identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class FailureAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    failed_lineage_audit_id: str = Field(min_length=1)
    provider_telemetry_audit_id: str = Field(min_length=1)
    public_action_outcome_audit_id: str = Field(min_length=1)
    final_response_interface_audit_id: str = Field(min_length=1)
    privacy_persistence_failure_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=8, max_length=8)
    manifest_job_count: Literal[32] = 32
    exposed_job_count: Literal[32] = 32
    complete_raw_job_count: Literal[31] = 31
    provider_orphan_job_count: Literal[1] = 1
    complete_raw_instrument_failure_count: Literal[31] = 31
    completed_execution_report_materialized: Literal[False] = False
    exact_empirical_job_denominator_available: Literal[False] = False
    artifact_backed_provider_call_lower_bound: Literal[256] = 256
    operator_observed_provider_call_lower_bound: Literal[257] = 257
    provider_total_tokens_lower_bound: Literal[1068881] = 1068881
    estimated_cost_usd_lower_bound: str = "0.19742030000000001688"
    exact_four_field_semantic_payload_count: Literal[194] = 194
    complete_raw_semantic_choice_count: Literal[188] = 188
    complete_raw_program_closed_count: Literal[31] = 31
    complete_raw_terminal_verification_count: Literal[31] = 31
    final_answer_count: Literal[0] = 0
    independent_validity_count: Literal[0] = 0
    semantic_action_behavior_is_descriptive_complete_raw_evidence_only: Literal[True] = True
    final_answer_behavior_unmeasured_due_to_interface_and_instrument_failure: Literal[True] = True
    same_distribution_as_v26_114_claimed: Literal[False] = False
    general_model_ability_increase_claimed: Literal[False] = False
    historical_result_reclassified: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    capability_rows: Literal[0] = 0
    reachability_rows: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    training_rows: Literal[0] = 0
    release_rows: Literal[0] = 0
    production_contribution: Literal[0] = 0
    status: Literal["failed_execution_independently_audited"] = (
        "failed_execution_independently_audited"
    )
    next_permitted_stage: str = NEXT_STAGE
    schema_version: Literal["finance_v26_semantic_action_failure_audit_report.v1"] = (
        "finance_v26_semantic_action_failure_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> FailureAuditReport:
        if self.report_id != _identity(
            self, "report_id", "finance_v26_semantic_action_failure_audit_report:"
        ):
            raise ValueError("v26.121 report identity changed")
        return self


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _find_bound_path(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        path = root / relative_path
        if path.is_file() and legacy.sha256_file(path) == expected_sha256:
            return path
    raise ValueError(f"v26.121 cannot replay bound file: {relative_path}")


def build_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
) -> FailureSourceReplayAudit:
    predecessor = execution.ExecutionSourceReplayAudit.model_validate(
        _load(execution_dir / "online_source_replay_audit.json")
    )
    if predecessor.audit_id != EXPECTED_EXECUTION_SOURCE_REPLAY_ID:
        raise ValueError("v26.121 predecessor source replay changed")
    entries: dict[str, SourceReplayEntry] = {}
    for item in predecessor.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries[item.relative_path] = SourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_120_bound_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=legacy.sha256_file(path),
            byte_count=path.stat().st_size,
        )
    failed_files = tuple(sorted(path for path in execution_dir.rglob("*") if path.is_file()))
    if len(failed_files) != EXPECTED_FAILED_FILE_COUNT:
        raise ValueError("v26.121 failed execution file denominator changed")
    for path in failed_files:
        relative = str(Path(EXECUTION_DIR) / path.relative_to(execution_dir))
        digest = legacy.sha256_file(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_120_failed_execution_file",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    audit_path = implementation_root / IMPLEMENTATION_PATH
    digest = legacy.sha256_file(audit_path)
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_121_implementation",
        expected_sha256=digest,
        observed_sha256=digest,
        byte_count=audit_path.stat().st_size,
    )
    ordered = tuple(entries[key] for key in sorted(entries))
    values: dict[str, Any] = {"entries": ordered}
    provisional = FailureSourceReplayAudit.model_construct(audit_id="pending", **values)
    return FailureSourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_action_failure_source_replay:",
        ),
        **values,
    )


def _provider_artifacts(
    execution_dir: Path,
) -> tuple[tuple[Path, runner.RawActionProviderCall], ...]:
    rows = []
    for path in sorted((execution_dir / "raw_provider_calls").glob("**/call_*.json")):
        rows.append((path, runner.RawActionProviderCall.model_validate(_load(path))))
    return tuple(rows)


def build_failed_lineage(
    *,
    execution_dir: Path,
    static: SemanticActionStaticInputs,
) -> tuple[
    FailedExecutionLineageAudit,
    tuple[runner.SemanticActionRawExecution, ...],
    tuple[tuple[Path, runner.RawActionProviderCall], ...],
    SemanticActionJob,
]:
    checkpoint_path = execution_dir / "semantic_action_job_results.checkpoint.jsonl"
    checkpoint = tuple(
        execution.SemanticActionJobResult.model_validate_json(line)
        for line in checkpoint_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    checkpoint_ids = {item.job_id for item in checkpoint}
    if len(checkpoint) != EXPECTED_CHECKPOINT_COUNT or len(checkpoint_ids) != len(checkpoint):
        raise ValueError("v26.121 checkpoint denominator changed")
    raw_paths = tuple(sorted((execution_dir / "raw_execution").glob("*.json")))
    raws = tuple(
        runner.SemanticActionRawExecution.model_validate(_load(path)) for path in raw_paths
    )
    raw_by_job = {item.job.job_id: item for item in raws}
    if len(raw_by_job) != EXPECTED_RAW_COUNT:
        raise ValueError("v26.121 Raw denominator changed")
    providers = _provider_artifacts(execution_dir)
    if len(providers) != EXPECTED_PROVIDER_ARTIFACT_COUNT:
        raise ValueError("v26.121 Provider artifact denominator changed")
    provider_ids = tuple(item.artifact_id for _, item in providers)
    if len(set(provider_ids)) != len(provider_ids):
        raise ValueError("v26.121 Provider artifact identities are not unique")
    provider_count_by_job = Counter(item.job_id for _, item in providers)
    raw_descriptor_passes = 0
    for raw in raws:
        for descriptor in raw.provider_call_artifacts:
            path = execution_dir / descriptor.relative_path
            if (
                not path.is_file()
                or legacy.sha256_file(path) != descriptor.sha256
                or path.stat().st_size != descriptor.byte_count
            ):
                raise ValueError("v26.121 Raw Provider descriptor changed")
            raw_descriptor_passes += 1
    if raw_descriptor_passes != EXPECTED_RAW_BOUND_PROVIDER_COUNT:
        raise ValueError("v26.121 Raw-bound Provider denominator changed")
    rows: list[JobExposureRow] = []
    incomplete: SemanticActionJob | None = None
    for index, job in enumerate(static.manifest.jobs):
        raw_present = job.job_id in raw_by_job
        checkpoint_present = job.job_id in checkpoint_ids
        provider_count = provider_count_by_job[job.job_id]
        if not raw_present:
            if incomplete is not None:
                raise ValueError("v26.121 found multiple incomplete Jobs")
            incomplete = job
        values: dict[str, Any] = {
            "manifest_index": index,
            "job_id": job.job_id,
            "mechanism_id": job.mechanism_id,
            "path_strategy_id": job.path_strategy_id,
            "exposure_state": (
                "checkpoint"
                if checkpoint_present
                else "raw_uncheckpointed"
                if raw_present
                else "provider_orphan"
            ),
            "checkpoint_present": checkpoint_present,
            "raw_execution_present": raw_present,
            "persisted_provider_artifact_count": provider_count,
        }
        provisional = JobExposureRow.model_construct(row_id="pending", **values)
        rows.append(
            JobExposureRow(
                row_id=_identity(
                    provisional,
                    "row_id",
                    "finance_v26_semantic_action_exposure_row:",
                ),
                **values,
            )
        )
    if incomplete is None or incomplete.job_id.rsplit(":", 1)[-1] != EXPECTED_INCOMPLETE_JOB_SUFFIX:
        raise ValueError("v26.121 incomplete Job identity changed")
    for item in checkpoint:
        raw = raw_by_job[item.job_id]
        raw_path = runner.raw_execution_path(execution_dir, raw.job)
        if legacy.sha256_file(raw_path) != item.raw_execution_artifact.sha256:
            raise ValueError("v26.121 checkpoint-to-Raw binding changed")
    json_paths = tuple(
        path for path in sorted(execution_dir.rglob("*.json")) if path.name != "report.json"
    )
    canonical_json_passes = 0
    for path in json_paths:
        payload = _load(path)
        if path.read_bytes() != _canonical_bytes(payload):
            raise ValueError(f"v26.121 noncanonical JSON: {path}")
        canonical_json_passes += 1
    canonical_jsonl_passes = sum(
        _canonical_bytes(json.loads(line)) == line.encode("utf-8")
        for line in checkpoint_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    values = {
        "rows": tuple(rows),
        "unique_provider_artifact_id_count": len(set(provider_ids)),
        "raw_descriptor_hash_pass_count": raw_descriptor_passes,
        "canonical_json_file_pass_count": canonical_json_passes,
        "canonical_jsonl_row_pass_count": canonical_jsonl_passes,
        "incomplete_job_id": incomplete.job_id,
    }
    provisional = FailedExecutionLineageAudit.model_construct(audit_id="pending", **values)
    audit = FailedExecutionLineageAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_action_failed_lineage:",
        ),
        **values,
    )
    return audit, raws, providers, incomplete


def build_provider_telemetry_audit(
    providers: Sequence[tuple[Path, runner.RawActionProviderCall]],
) -> PersistedProviderTelemetryAudit:
    artifacts = tuple(item for _, item in providers)
    telemetry = tuple(item.provider_telemetry for item in artifacts)
    payload_key_sets = Counter(
        tuple(sorted(item.response_payload))
        for item in artifacts
        if item.response_payload is not None
    )
    phases = Counter((item.request_kind, item.public_attempt_phase) for item in artifacts)
    cost = sum(
        (
            Decimal(str(item.estimated_cost))
            for item in telemetry
            if item.estimated_cost is not None
        ),
        Decimal("0"),
    )
    values: dict[str, Any] = {
        "http_success_artifact_count": sum(item.http_success for item in telemetry),
        "http_400_artifact_count": sum(item.http_status == 400 for item in telemetry),
        "exact_requested_model_count": sum(
            item.model_requested == legacy.STAGE_ONE_MODEL_ID for item in telemetry
        ),
        "exact_selected_model_count": sum(
            item.model_selected == legacy.STAGE_ONE_MODEL_ID for item in telemetry
        ),
        "exact_response_model_count": sum(
            item.response_model == legacy.STAGE_ONE_MODEL_ID for item in telemetry
        ),
        "missing_response_model_count": sum(item.response_model is None for item in telemetry),
        "fallback_count": sum(item.fallback_used for item in telemetry),
        "discovery_count": sum(item.discovery_attempted for item in telemetry),
        "provider_native_tool_call_count": sum(
            item.response_shape.get("provider_native_tool_call_observed") is True
            for item in telemetry
        ),
        "positive_thinking_telemetry_count": sum(
            bool(
                item.http_success
                and item.reasoning_content_present
                and (item.reasoning_content_length or 0) > 0
                and (item.reasoning_tokens or 0) > 0
            )
            for item in telemetry
        ),
        "complete_usage_count": sum(
            item.prompt_tokens is not None
            and item.completion_tokens is not None
            and item.total_tokens is not None
            for item in telemetry
        ),
        "semantic_primary_call_count": phases[("semantic_proposal", "primary")],
        "semantic_recovery_call_count": phases[("semantic_proposal", "semantic_recovery")],
        "final_primary_call_count": phases[("final_answer", "primary")],
        "final_abi_rescue_call_count": phases[("final_answer", "abi_rescue")],
        "exact_four_field_semantic_payload_count": payload_key_sets[
            ("action_id", "decision_kind", "protocol", "state_id")
        ],
        "exact_prompt_visible_final_payload_count": payload_key_sets[
            ("answer", "rationale_summary")
        ],
        "null_response_payload_count": sum(item.response_payload is None for item in artifacts),
        "prompt_tokens_lower_bound": sum(item.prompt_tokens or 0 for item in telemetry),
        "completion_tokens_lower_bound": sum(item.completion_tokens or 0 for item in telemetry),
        "reasoning_tokens_lower_bound": sum(item.reasoning_tokens or 0 for item in telemetry),
        "provider_total_tokens_lower_bound": sum(item.total_tokens or 0 for item in telemetry),
        "reasoning_content_length_lower_bound": sum(
            item.reasoning_content_length or 0 for item in telemetry
        ),
        "estimated_cost_usd_lower_bound": format(cost, "f"),
    }
    provisional = PersistedProviderTelemetryAudit.model_construct(audit_id="pending", **values)
    return PersistedProviderTelemetryAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_action_failed_provider_telemetry:",
        ),
        **values,
    )


def _prompt_payload(prompt: str) -> dict[str, Any]:
    _, separator, raw = prompt.partition("\n")
    if not separator:
        raise ValueError("v26.121 Prompt lacks a JSON payload")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("v26.121 Prompt payload is not an object")
    return cast(dict[str, Any], payload)


def _candidate_family(candidate: Mapping[str, Any]) -> str:
    decision = str(candidate.get("decision_kind"))
    if decision == "acquire_public_input":
        return f"{decision}/{candidate.get('acquisition_mode')}"
    if decision == "execute_public_operation":
        return f"{decision}/{candidate.get('operator_id') or 'registered_default'}"
    return decision


def _reconstruct_choice_prompt(
    *,
    raw: runner.SemanticActionRawExecution,
    choice: runner.SemanticChoiceRecord,
    state: SemanticActionState,
    binding: Any,
    static: SemanticActionStaticInputs,
    semantic_recovery_count: int,
) -> tuple[str, Literal["primary", "abi_rescue", "semantic_recovery"]]:
    condition = (
        None
        if binding.source_registered_path.role == "capability"
        else binding.source_registered_path.path_strategy_id
    )
    presentation_salt = canonical_hash(
        {
            "job_id": raw.job.job_id,
            "logical_request_index": choice.logical_request_index,
            "state_id": state.state_id,
            "semantic_recovery_count": semantic_recovery_count,
        },
        prefix="finance_v26_runner_candidate_presentation:",
    )
    primary = (
        render_exact_canonical_action_semantic_recovery_prompt(
            instruction=binding.record.task_package.task.public.instruction,
            state=state,
            public_path_condition=condition,
            presentation_salt=presentation_salt,
        )
        if choice.public_attempt_phase == "semantic_recovery"
        else render_exact_canonical_action_prompt(
            instruction=binding.record.task_package.task.public.instruction,
            state=state,
            public_path_condition=condition,
            presentation_salt=presentation_salt,
            grammar=static.grammar,
        )
    )
    attempts = tuple(
        item
        for item in raw.attempts
        if item.request_kind == "semantic_proposal"
        and item.logical_request_index == choice.logical_request_index
    )
    usable = tuple(item for item in attempts if item.disposition == "usable")
    if len(usable) != 1:
        raise ValueError("v26.121 Choice lacks one usable Provider attempt")
    active = usable[0]
    prompt = primary
    phase: Literal["primary", "abi_rescue", "semantic_recovery"] = choice.public_attempt_phase
    if active.public_attempt_phase == "abi_rescue":
        initial = attempts[0]
        prompt = render_exact_canonical_action_abi_rescue_prompt(
            primary,
            failure_family=initial.failure_family or "channel_parse_failure",
            failure_subtype=(
                initial.failure_subtype or initial.completion_failure_type or "completion_failure"
            ),
        )
        phase = "abi_rescue"
    if legacy.sha256_text(prompt) != active.prompt_sha256:
        raise ValueError("v26.121 reconstructed Choice Prompt hash changed")
    return prompt, phase


def _independent_choice_rows(
    *,
    raw: runner.SemanticActionRawExecution,
    static: SemanticActionStaticInputs,
    binding: Any,
) -> tuple[IndependentChoiceRow, ...]:
    observations: list[Any] = []
    rejections: list[Any] = []
    rejection_by_id = {item.rejection_id: item for item in raw.semantic_rejections}
    rows: list[IndependentChoiceRow] = []
    previous_legal_no_progress = False
    for choice in raw.semantic_choices:
        state = build_semantic_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            tuple(observations),
            semantic_rejections=tuple(rejections),
        )
        if choice.state_id != state.state_id:
            raise ValueError("v26.121 independently reconstructed state changed")
        prompt, response_phase = _reconstruct_choice_prompt(
            raw=raw,
            choice=choice,
            state=state,
            binding=binding,
            static=static,
            semantic_recovery_count=len(rejections),
        )
        payload = _prompt_payload(prompt)
        visible = payload.get("visible_action_candidates")
        if not isinstance(visible, list) or not visible:
            raise ValueError("v26.121 Choice Prompt has no Candidate list")
        reference_id = str(prompt_only_reference_payload(prompt)["action_id"])
        candidates: list[CandidatePresentation] = []
        selected_position: int | None = None
        selected_bytes: int | None = None
        selected_family: str | None = None
        selected_reference: bool | None = None
        for position, raw_candidate in enumerate(visible):
            if not isinstance(raw_candidate, Mapping):
                raise ValueError("v26.121 visible Candidate is not an object")
            candidate = dict(raw_candidate)
            action_id = str(candidate["action_id"])
            byte_count = len(_canonical_bytes(candidate))
            family = _candidate_family(candidate)
            is_reference = action_id == reference_id
            selected = action_id == choice.selected_action_id
            candidates.append(
                CandidatePresentation(
                    action_id=action_id,
                    zero_based_position=position,
                    description_utf8_bytes=byte_count,
                    candidate_family=family,
                    prompt_only_reference=is_reference,
                    selected_by_model=selected,
                )
            )
            if selected:
                selected_position = position
                selected_bytes = byte_count
                selected_family = family
                selected_reference = is_reference
        before = _progress_diagnostic(binding.record, tuple(observations))[0]
        if choice.observation_status is not None:
            if len(observations) >= len(raw.observations):
                raise ValueError("v26.121 Choice references a missing Observation")
            observation = raw.observations[len(observations)]
            if observation.status != choice.observation_status:
                raise ValueError("v26.121 Choice Observation status changed")
            observations.append(observation)
        after = _progress_diagnostic(binding.record, tuple(observations))[0]
        legal_no_progress = bool(
            choice.semantic_accepted
            and choice.observation_status is not None
            and choice.public_progress_after_commit is False
        )
        values: dict[str, Any] = {
            "job_id": raw.job.job_id,
            "logical_request_index": choice.logical_request_index,
            "choice_phase": choice.public_attempt_phase,
            "response_attempt_phase": response_phase,
            "state_id": state.state_id,
            "candidate_count": len(candidates),
            "candidates": tuple(candidates),
            "selected_action_id": choice.selected_action_id,
            "selected_zero_based_position": selected_position,
            "selected_description_utf8_bytes": selected_bytes,
            "selected_candidate_family": selected_family,
            "selected_prompt_only_reference": selected_reference,
            "visible_action_id_match": choice.visible_action_id_match,
            "decision_kind_match": choice.decision_kind_match,
            "semantic_accepted": choice.semantic_accepted,
            "observation_status": choice.observation_status,
            "public_progress_after_commit": choice.public_progress_after_commit,
            "completed_program_nodes_before": before,
            "completed_program_nodes_after": after,
            "program_node_progress": after > before,
            "terminal_verification_ready_before": any(
                item.candidate_family == "verify_terminal_operation" for item in candidates
            ),
            "legal_no_progress_choice": legal_no_progress,
            "ordinary_replan_after_legal_no_progress": previous_legal_no_progress,
        }
        provisional = IndependentChoiceRow.model_construct(row_id="pending", **values)
        rows.append(
            IndependentChoiceRow(
                row_id=_identity(
                    provisional,
                    "row_id",
                    "finance_v26_independent_semantic_choice_row:",
                ),
                **values,
            )
        )
        if choice.rejection_id is not None:
            rejection = rejection_by_id.get(choice.rejection_id)
            if rejection is None:
                raise ValueError("v26.121 Choice rejection is missing")
            rejections.append(rejection)
        previous_legal_no_progress = legal_no_progress
    if len(observations) != len(raw.observations):
        raise ValueError("v26.121 independent Choice audit missed Observations")
    return tuple(rows)


def build_public_action_outcome_audit(
    *,
    raws: Sequence[runner.SemanticActionRawExecution],
    static: SemanticActionStaticInputs,
) -> PublicActionOutcomeAudit:
    all_rows: list[IndependentChoiceRow] = []
    first_rows: list[IndependentChoiceRow] = []
    mechanism_success = 0
    path_adherence = 0
    program_closed = 0
    terminal_completed = 0
    replay_passes = 0
    eventual_progress = 0
    rejection_categories: Counter[str] = Counter()
    recovery_choices: list[runner.SemanticChoiceRecord] = []
    for raw in sorted(raws, key=lambda item: item.job.job_id):
        binding = runner.semantic_action_runtime_binding(static, raw.job)
        rows = _independent_choice_rows(raw=raw, static=static, binding=binding)
        if not rows:
            raise ValueError("v26.121 complete Raw lacks a semantic Choice")
        all_rows.extend(rows)
        first_rows.append(rows[0])
        replay = legacy.replay_v3(raw, static=static.historical, binding=binding)
        replay_passes += int(replay.passed)
        mechanism = evaluate_mechanism_estimand(
            cast(Any, binding.record),
            raw.observations,
            stopped_by_model=False,
        )
        mechanism_success += int(mechanism.success)
        path_adherence += int(_actual_route(raw.observations) == raw.job.path_strategy_id)
        _, _, closed, terminal, _ = _progress_diagnostic(binding.record, raw.observations)
        program_closed += int(closed)
        terminal_completed += int(terminal)
        rejection_categories.update(item.error_category for item in raw.semantic_rejections)
        recovery_choices.extend(
            item
            for item in raw.semantic_choices
            if item.public_attempt_phase == "semantic_recovery"
        )
        for index, row in enumerate(rows):
            if row.legal_no_progress_choice:
                eventual_progress += int(
                    any(later.public_progress_after_commit is True for later in rows[index + 1 :])
                )
    rows_tuple = tuple(all_rows)
    groups: dict[int, list[IndependentChoiceRow]] = defaultdict(list)
    for row in rows_tuple:
        groups[row.candidate_count].append(row)
    load = tuple(
        CandidateLoadSummary(
            candidate_count=count,
            choice_count=len(rows),
            accepted_count=sum(item.semantic_accepted for item in rows),
            observation_count=sum(item.observation_status is not None for item in rows),
            public_progress_count=sum(item.public_progress_after_commit is True for item in rows),
            program_node_progress_count=sum(item.program_node_progress for item in rows),
            selected_reference_count=sum(
                item.selected_prompt_only_reference is True for item in rows
            ),
        )
        for count, rows in sorted(groups.items())
    )
    selected_lengths = tuple(
        item.selected_description_utf8_bytes
        for item in rows_tuple
        if item.selected_description_utf8_bytes is not None
    )
    selected_positions = Counter(
        "invisible"
        if item.selected_zero_based_position is None
        else str(item.selected_zero_based_position)
        for item in rows_tuple
    )
    first_positions = Counter(
        "invisible"
        if item.selected_zero_based_position is None
        else str(item.selected_zero_based_position)
        for item in first_rows
    )
    families = Counter(item.selected_candidate_family or "invisible" for item in rows_tuple)
    terminal_verification = tuple(
        item
        for item in rows_tuple
        if item.selected_candidate_family == "verify_terminal_operation" and item.semantic_accepted
    )
    values: dict[str, Any] = {
        "rows": rows_tuple,
        "semantic_choice_count": len(rows_tuple),
        "visible_action_id_match_count": sum(item.visible_action_id_match for item in rows_tuple),
        "decision_kind_match_count": sum(item.decision_kind_match for item in rows_tuple),
        "primary_choice_accept_count": sum(
            raw_choice.public_attempt_phase == "primary" and raw_choice.semantic_accepted
            for raw in raws
            for raw_choice in raw.semantic_choices
        ),
        "reversible_commit_count": sum(len(raw.commits) for raw in raws),
        "observation_count": sum(len(raw.observations) for raw in raws),
        "successful_observation_count": sum(
            item.status == "succeeded" for raw in raws for item in raw.observations
        ),
        "failed_observation_count": sum(
            item.status == "failed" for raw in raws for item in raw.observations
        ),
        "public_progress_choice_count": sum(
            item.public_progress_after_commit is True
            for raw in raws
            for item in raw.semantic_choices
        ),
        "program_node_progress_choice_count": sum(
            item.program_node_progress for item in rows_tuple
        ),
        "first_action_id_legal_job_count": sum(item.visible_action_id_match for item in first_rows),
        "first_action_accepted_job_count": sum(item.semantic_accepted for item in first_rows),
        "first_action_public_progress_job_count": sum(
            item.public_progress_after_commit is True for item in first_rows
        ),
        "semantic_rejection_count": sum(len(raw.semantic_rejections) for raw in raws),
        "stale_public_state_rejection_count": rejection_categories["stale_public_state"],
        "unknown_action_rejection_count": rejection_categories["unknown_or_unselectable_action"],
        "semantic_recovery_job_count": len(recovery_choices),
        "recovery_selected_different_action_count": sum(
            item.different_action_after_rejection is True for item in recovery_choices
        ),
        "recovery_commit_count": sum(item.semantic_accepted for item in recovery_choices),
        "recovery_public_progress_count": sum(
            item.public_progress_after_commit is True for item in recovery_choices
        ),
        "legal_no_progress_choice_count": sum(item.legal_no_progress_choice for item in rows_tuple),
        "ordinary_replan_count": sum(
            item.ordinary_replan_after_legal_no_progress for item in rows_tuple
        ),
        "ordinary_replan_eventual_progress_count": eventual_progress,
        "singleton_choice_count": sum(item.candidate_count == 1 for item in rows_tuple),
        "multi_candidate_choice_count": sum(item.candidate_count > 1 for item in rows_tuple),
        "candidate_count_distribution": dict(
            sorted(Counter(str(item.candidate_count) for item in rows_tuple).items())
        ),
        "candidate_load_summaries": load,
        "selected_reference_count": sum(
            item.selected_prompt_only_reference is True for item in rows_tuple
        ),
        "selected_nonreference_count": sum(
            item.selected_prompt_only_reference is False for item in rows_tuple
        ),
        "selected_invisible_action_count": sum(
            not item.visible_action_id_match for item in rows_tuple
        ),
        "selected_position_distribution": dict(sorted(selected_positions.items())),
        "first_selected_position_distribution": dict(sorted(first_positions.items())),
        "selected_candidate_family_distribution": dict(sorted(families.items())),
        "selected_description_utf8_bytes_minimum": min(selected_lengths),
        "selected_description_utf8_bytes_median": int(statistics.median(selected_lengths)),
        "selected_description_utf8_bytes_maximum": max(selected_lengths),
        "program_closed_job_count": program_closed,
        "terminal_node_completed_job_count": terminal_completed,
        "terminal_verification_choice_count": len(terminal_verification),
        "successful_terminal_verification_count": sum(
            item.observation_status == "succeeded" for item in terminal_verification
        ),
        "final_commit_count": sum(
            item.commit.action == "emit_final" for raw in raws for item in raw.commits
        ),
        "mechanism_success_count": mechanism_success,
        "requested_path_adherence_count": path_adherence,
        "replay_v3_pass_count": replay_passes,
        "complete_raw_terminal_instrument_failure_count": sum(
            raw.terminal_disposition == "instrument_failure" for raw in raws
        ),
    }
    provisional = PublicActionOutcomeAudit.model_construct(audit_id="pending", **values)
    return PublicActionOutcomeAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_action_public_outcome_audit:",
        ),
        **values,
    )


def build_final_response_interface_audit(
    *,
    raws: Sequence[runner.SemanticActionRawExecution],
    providers: Sequence[tuple[Path, runner.RawActionProviderCall]],
    static: SemanticActionStaticInputs,
) -> FinalResponseInterfaceAudit:
    provider_map = {
        (
            item.job_id,
            item.logical_request_index,
            item.request_kind,
            item.public_attempt_phase,
        ): item
        for _, item in providers
    }
    primary_hash_matches = 0
    rescue_hash_matches = 0
    primary_json_cues = 0
    rescue_json_cues = 0
    primary_bytes: list[int] = []
    rescue_bytes: list[int] = []
    exact_primary_payloads = 0
    parser_rejections = 0
    rescue_http_400 = 0
    rescue_missing_model = 0
    rescue_fields = 0
    for raw in raws:
        binding = runner.semantic_action_runtime_binding(static, raw.job)
        condition = (
            None
            if binding.source_registered_path.role == "capability"
            else binding.source_registered_path.path_strategy_id
        )
        primary_prompt = render_compact_final_prompt(
            binding.prompt_contract.public_context,
            binding.record.task_package.task.public,
            raw.observations,
            public_path_condition=condition,
        )
        final_attempts = tuple(item for item in raw.attempts if item.request_kind == "final_answer")
        if len(final_attempts) != 2:
            raise ValueError("v26.121 final attempt denominator changed")
        primary_attempt, rescue_attempt = final_attempts
        primary_hash_matches += int(
            primary_attempt.prompt_sha256 == legacy.sha256_text(primary_prompt)
        )
        primary_json_cues += int("json" in primary_prompt.casefold())
        primary_bytes.append(len(primary_prompt.encode("utf-8")))
        primary_artifact = provider_map[
            (
                raw.job.job_id,
                primary_attempt.logical_request_index,
                "final_answer",
                "primary",
            )
        ]
        payload = primary_artifact.response_payload
        if payload is None:
            raise ValueError("v26.121 final Primary payload is missing")
        exact_primary_payloads += int(set(payload) == {"answer", "rationale_summary"})
        try:
            parse_final_answer_payload(payload)
        except ModelResultRejection as exc:
            parser_rejections += int(
                exc.classification.subtype == "final_answer_not_exact_object_contract"
            )
        else:
            raise ValueError("v26.121 final Primary unexpectedly crossed the parser")
        rescue_prompt = legacy.render_semantically_sufficient_final_rescue_prompt(
            primary_prompt,
            failure_type=(
                primary_attempt.failure_subtype
                or primary_attempt.completion_failure_type
                or "completion_failure"
            ),
        )
        rescue_hash_matches += int(
            rescue_attempt.prompt_sha256 == legacy.sha256_text(rescue_prompt)
        )
        rescue_json_cues += int("json" in rescue_prompt.casefold())
        rescue_bytes.append(len(rescue_prompt.encode("utf-8")))
        rescue_payload = _prompt_payload(rescue_prompt)
        response_contract = rescue_payload.get("response_contract")
        if not isinstance(response_contract, Mapping):
            raise ValueError("v26.121 final Rescue contract is missing")
        rescue_fields += int(tuple(response_contract.get("fields") or ()) == ("answer",))
        rescue_artifact = provider_map[
            (
                raw.job.job_id,
                rescue_attempt.logical_request_index,
                "final_answer",
                "abi_rescue",
            )
        ]
        rescue_http_400 += int(rescue_artifact.provider_telemetry.http_status == 400)
        rescue_missing_model += int(rescue_artifact.provider_telemetry.response_model is None)
    parser_fields = tuple(sorted(StageOneFinalAnswerPayload.model_fields))
    if parser_fields != ("answer", "protocol", "stage"):
        raise ValueError("v26.121 final parser field set changed")
    values: dict[str, Any] = {
        "final_primary_prompt_hash_match_count": primary_hash_matches,
        "final_primary_prompt_json_lexical_cue_count": primary_json_cues,
        "final_primary_prompt_minimum_utf8_bytes": min(primary_bytes),
        "final_primary_prompt_maximum_utf8_bytes": max(primary_bytes),
        "parser_exact_field_set": parser_fields,
        "observed_exact_model_visible_primary_payload_count": exact_primary_payloads,
        "observed_primary_parser_rejection_count": parser_rejections,
        "final_rescue_prompt_hash_match_count": rescue_hash_matches,
        "final_rescue_prompt_json_lexical_cue_count": rescue_json_cues,
        "final_rescue_prompt_minimum_utf8_bytes": min(rescue_bytes),
        "final_rescue_prompt_maximum_utf8_bytes": max(rescue_bytes),
        "rescue_field_set_alignment_count": int(
            rescue_fields == len(raws) and ("answer",) == parser_fields
        ),
        "final_rescue_http_400_count": rescue_http_400,
        "final_rescue_response_model_missing_count": rescue_missing_model,
    }
    provisional = FinalResponseInterfaceAudit.model_construct(audit_id="pending", **values)
    return FinalResponseInterfaceAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_action_final_interface_audit:",
        ),
        **values,
    )


def build_privacy_persistence_failure_audit(
    *,
    execution_dir: Path,
    providers: Sequence[tuple[Path, runner.RawActionProviderCall]],
    incomplete_job: SemanticActionJob,
    static: SemanticActionStaticInputs,
) -> PrivacyPersistenceFailureAudit:
    incomplete = tuple(item for _, item in providers if item.job_id == incomplete_job.job_id)
    if len(incomplete) != 6:
        raise ValueError("v26.121 incomplete Provider prefix changed")
    exact_payloads = sum(
        item.response_payload is not None
        and set(item.response_payload) == {"state_id", "action_id", "decision_kind", "protocol"}
        for item in incomplete
    )
    usage = sum(item.provider_telemetry.total_tokens or 0 for item in incomplete)
    if runner.raw_execution_path(execution_dir, incomplete_job).exists():
        raise ValueError("v26.121 incomplete Job unexpectedly has a Raw Execution")
    binding = runner.semantic_action_runtime_binding(static, incomplete_job)
    retry_blocked = False
    try:
        runner.execute_semantic_action_job_raw(
            job=incomplete_job,
            runner_contract=runner.make_semantic_action_runner_contract(static),
            static=static,
            binding=binding,
            client=None,
            output_dir=execution_dir,
        )
    except ValueError as exc:
        retry_blocked = "orphan semantic action Provider artifacts forbid retry" in str(exc)
    if not retry_blocked:
        raise ValueError("v26.121 orphan retry guard changed")
    source = (Path(__file__).resolve().parent / runner.__file__.rsplit("/", 1)[-1]).read_text(
        encoding="utf-8"
    )
    persist_block = source[source.index("    def _persist(") : source.index("    def _charge(")]
    if not (
        persist_block.index("RawActionProviderCall(")
        < persist_block.index("write_json_atomic(")
        < persist_block.index("self._telemetry.append(")
        and "legacy.contains_private_reasoning(self.response_payload)" in source
    ):
        raise ValueError("v26.121 privacy-persistence code order changed")
    values: dict[str, Any] = {
        "incomplete_job_id": incomplete_job.job_id,
        "persisted_exact_four_field_payload_count": exact_payloads,
        "persisted_usage_tokens_lower_bound": usage,
        "retry_blocked_by_six_orphan_provider_artifacts": retry_blocked,
    }
    provisional = PrivacyPersistenceFailureAudit.model_construct(audit_id="pending", **values)
    return PrivacyPersistenceFailureAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_action_privacy_persistence_failure:",
        ),
        **values,
    )


def make_transition_contract() -> ProspectiveTransitionContract:
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending")
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_semantic_action_failure_transition:",
        )
    )


def _expect_rejected(name: str, action: Any) -> MutationResult:
    try:
        action()
    except Exception:
        return MutationResult(name=name)
    raise ValueError(f"v26.121 destructive mutation was admitted: {name}")


def build_destructive_audit(
    *,
    source: FailureSourceReplayAudit,
    lineage: FailedExecutionLineageAudit,
    provider: PersistedProviderTelemetryAudit,
    outcome: PublicActionOutcomeAudit,
    interface: FinalResponseInterfaceAudit,
    privacy: PrivacyPersistenceFailureAudit,
    transition: ProspectiveTransitionContract,
    providers: Sequence[tuple[Path, runner.RawActionProviderCall]],
) -> DestructiveAudit:
    first_provider_payload = providers[0][1].model_dump(mode="json")
    private_payload = dict(first_provider_payload)
    private_response = dict(cast(dict[str, Any], private_payload["response_payload"]))
    private_response["reasoning"] = "forbidden"
    private_payload["response_payload"] = private_response
    first_choice = outcome.rows[0]
    bad_choice_payload = first_choice.model_dump(mode="json")
    bad_candidates = list(cast(list[dict[str, Any]], bad_choice_payload["candidates"]))
    bad_candidates[0] = {**bad_candidates[0], "zero_based_position": 7}
    bad_choice_payload["candidates"] = bad_candidates
    mutations = (
        _expect_rejected(
            "candidate_presentation_position_changed",
            lambda: IndependentChoiceRow.model_validate(bad_choice_payload),
        ),
        _expect_rejected(
            "final_primary_alignment_claim_inserted",
            lambda: FinalResponseInterfaceAudit.model_validate(
                {**interface.model_dump(mode="json"), "primary_field_set_alignment_count": 1}
            ),
        ),
        _expect_rejected(
            "final_rescue_json_cue_fabricated",
            lambda: FinalResponseInterfaceAudit.model_validate(
                {
                    **interface.model_dump(mode="json"),
                    "final_rescue_prompt_json_lexical_cue_count": 31,
                }
            ),
        ),
        _expect_rejected(
            "historical_recovery_authorized",
            lambda: ProspectiveTransitionContract.model_validate(
                {
                    **transition.model_dump(mode="json"),
                    "historical_job_rerun_recovery_or_reclassification_authorized": True,
                }
            ),
        ),
        _expect_rejected(
            "lineage_exposure_removed",
            lambda: FailedExecutionLineageAudit.model_validate(
                {**lineage.model_dump(mode="json"), "exposed_job_count": 31}
            ),
        ),
        _expect_rejected(
            "lineage_orphan_removed",
            lambda: FailedExecutionLineageAudit.model_validate(
                {**lineage.model_dump(mode="json"), "provider_orphan_job_count": 0}
            ),
        ),
        _expect_rejected(
            "private_reasoning_payload_inserted",
            lambda: runner.RawActionProviderCall.model_validate(private_payload),
        ),
        _expect_rejected(
            "provider_http_failure_deleted",
            lambda: PersistedProviderTelemetryAudit.model_validate(
                {**provider.model_dump(mode="json"), "http_400_artifact_count": 30}
            ),
        ),
        _expect_rejected(
            "public_choice_denominator_changed",
            lambda: PublicActionOutcomeAudit.model_validate(
                {**outcome.model_dump(mode="json"), "semantic_choice_count": 187}
            ),
        ),
        _expect_rejected(
            "source_hash_changed",
            lambda: FailureSourceReplayAudit.model_validate(
                {
                    **source.model_dump(mode="json"),
                    "entries": [
                        {
                            **source.entries[0].model_dump(mode="json"),
                            "observed_sha256": "0" * 64,
                        },
                        *[item.model_dump(mode="json") for item in source.entries[1:]],
                    ],
                }
            ),
        ),
        _expect_rejected(
            "telemetry_fallback_artifact_fabricated",
            lambda: PrivacyPersistenceFailureAudit.model_validate(
                {
                    **privacy.model_dump(mode="json"),
                    "telemetry_only_fallback_artifact_available": True,
                }
            ),
        ),
        _expect_rejected(
            "transition_provider_call_authorized",
            lambda: ProspectiveTransitionContract.model_validate(
                {**transition.model_dump(mode="json"), "provider_calls_authorized": True}
            ),
        ),
    )
    ordered = tuple(sorted(mutations, key=lambda item: item.name))
    values: dict[str, Any] = {"mutations": ordered}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_action_failure_destructive:",
        ),
        **values,
    )


def _detail(path: Path) -> DetailFile:
    return DetailFile(
        relative_path=path.name,
        sha256=legacy.sha256_file(path),
        byte_count=path.stat().st_size,
    )


def build(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
    output_dir: Path,
) -> FailureAuditReport:
    source = build_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
    )
    static = load_semantic_action_static_inputs(package_root, implementation_root)
    frozen_manifest = _load(execution_dir / "frozen_semantic_action_job_manifest.json")
    frozen_contract = runner.SemanticActionRunnerContract.model_validate(
        _load(execution_dir / "runner_contract.json")
    )
    if (
        static.manifest.model_dump(mode="json") != frozen_manifest
        or static.manifest.manifest_id != EXPECTED_MANIFEST_ID
        or frozen_contract.contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or runner.make_semantic_action_runner_contract(static) != frozen_contract
        or (execution_dir / "report.json").exists()
    ):
        raise ValueError("v26.121 failed execution identity chain changed")
    lineage, raws, providers, incomplete = build_failed_lineage(
        execution_dir=execution_dir,
        static=static,
    )
    provider = build_provider_telemetry_audit(providers)
    outcome = build_public_action_outcome_audit(raws=raws, static=static)
    interface = build_final_response_interface_audit(
        raws=raws,
        providers=providers,
        static=static,
    )
    privacy = build_privacy_persistence_failure_audit(
        execution_dir=execution_dir,
        providers=providers,
        incomplete_job=incomplete,
        static=static,
    )
    transition = make_transition_contract()
    destructive = build_destructive_audit(
        source=source,
        lineage=lineage,
        provider=provider,
        outcome=outcome,
        interface=interface,
        privacy=privacy,
        transition=transition,
        providers=providers,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source),
        ("failed_execution_lineage_audit.json", lineage),
        ("provider_telemetry_audit.json", provider),
        ("public_action_outcome_audit.json", outcome),
        ("final_response_interface_audit.json", interface),
        ("privacy_persistence_failure_audit.json", privacy),
        ("destructive_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    for name, artifact in artifacts:
        runner.write_json_atomic(output_dir / name, artifact.model_dump(mode="json"))
    details = tuple(_detail(output_dir / name) for name, _ in artifacts)
    values: dict[str, Any] = {
        "source_replay_audit_id": source.audit_id,
        "failed_lineage_audit_id": lineage.audit_id,
        "provider_telemetry_audit_id": provider.audit_id,
        "public_action_outcome_audit_id": outcome.audit_id,
        "final_response_interface_audit_id": interface.audit_id,
        "privacy_persistence_failure_audit_id": privacy.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = FailureAuditReport.model_construct(report_id="pending", **values)
    report = FailureAuditReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_semantic_action_failure_audit_report:",
        ),
        **values,
    )
    runner.write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Independently audit the failed v26.120 Semantic Action calibration"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument(
        "--execution-dir",
        type=Path,
        default=package_default / EXECUTION_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / OUTPUT_DIR,
    )
    args = parser.parse_args()
    report = build(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        execution_dir=args.execution_dir,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
# IMPLEMENTATION_CONTINUES
