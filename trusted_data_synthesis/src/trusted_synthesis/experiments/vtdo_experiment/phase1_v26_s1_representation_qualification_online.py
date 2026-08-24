from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
import threading
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_execution as privacy_runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_runner_preflight as final_preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_representation_qualification_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_online as semantic_online,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingVerificationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    MechanismEstimandOutcome,
    evaluate_mechanism_estimand,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    StageOneProspectiveThinkingJsonClient,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = preflight.PROSPECTIVE_EXECUTION_RUN_ID
PREFLIGHT_DIR: Final = preflight.OUTPUT_DIR
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_134_s1_representation_qualification_execution_v1_20260824"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_s1_representation_qualification_online.py"
)
POSTRUN_STAGE: Final = "s1_model_visible_representation_qualification_postrun_audit_only"

EXPECTED_PREFLIGHT_REPORT_ID: Final = (
    "finance_v26_s1_qualification_preflight_report:"
    "9d79af8e43b93f768d615be5aa1ca22ac2f733b5171fb191b87b4f0bf1785c4a"
)
EXPECTED_PREFLIGHT_REPORT_SHA256: Final = (
    "57a190f7e8845e40dbca942b412639a16a374f6346d9959b20b69a85d2e87216"
)
EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID: Final = (
    "finance_v26_s1_qualification_source_replay:"
    "15235e713190c1619799b1be734565c42b387c103c4e617f6279a3c2aa46cdf1"
)
EXPECTED_SOURCE_SEPARATION_ID: Final = (
    "finance_v26_s1_qualification_source_separation:"
    "3caad15982367a4f65aff8a15c7e9b732d2b1e801b3d6867736669dd4ae1ec4d"
)
EXPECTED_PROGRESS_CONTRACT_ID: Final = (
    "finance_v26_public_progress_vector_contract:"
    "c716f6844e51e70751fba628805611223fba6775e905cfe336b78298d7ded785"
)
EXPECTED_PATH_CATALOG_ID: Final = (
    "finance_v26_s1_qualification_path_catalog:"
    "48e21b62dc6be94a204980ccbfa186fad0f3087a8f92f37ee8b3c26856039026"
)
EXPECTED_RESOURCE_CONTRACT_ID: Final = (
    "finance_v26_s1_qualification_resource_contract:"
    "9ba3c63a1c7cfebe6a954eda18e0cd6e3414fcc2fc17a2ac0c95e6e7a199fba6"
)
EXPECTED_QUALIFICATION_CONTRACT_ID: Final = (
    "finance_v26_s1_representation_qualification_contract:"
    "7ab0a66c595c13374380d3ec3464ebae33d7c150ee18ae87a4c3e1130e31fb82"
)
EXPECTED_MANIFEST_ID: Final = (
    "finance_v26_s1_qualification_manifest:"
    "75dd0c9a5e705225bf02063a8ab18cfaaefcc19df62a1c26b2b8c783a83e99eb"
)
EXPECTED_OUTCOME_CONTRACT_ID: Final = (
    "finance_v26_s1_qualification_outcome_contract:"
    "0a276275c4878323227313658ad25642f95b40b7a60ff6f6f575e21f1cc09bdc"
)
EXPECTED_RUNNER_CONTRACT_ID: Final = (
    "finance_v26_s1_qualification_runner_contract:"
    "1aca524bc565c1157f876ad55d2f469c516dd1ff85308cf9719029f914cd750c"
)
EXPECTED_TRANSITION_ID: Final = (
    "finance_v26_s1_qualification_transition:"
    "a6f63cd2e7555ceb9d73c507c844a7e4d3d91cf1805e01e196d03532b68e98fa"
)
EXPECTED_TRANSITION_SHA256: Final = (
    "c91383f858b5c397ddd607dd85017dd16d76f1b14b898a7bcdc2d37589a4814a"
)

PREFLIGHT_OUTPUTS: Final = (
    "destructive_audit.json",
    "frozen_predecessor_binding_audit.json",
    "prospective_transition_contract.json",
    "public_progress_vector_contract.json",
    "qualification_source_separation_audit.json",
    "report.json",
    "s1_qualification_manifest.json",
    "s1_qualification_outcome_contract.json",
    "s1_qualification_path_catalog.json",
    "s1_qualification_resource_contract.json",
    "s1_qualification_runner_contract.json",
    "s1_representation_qualification_contract.json",
    "s1_runner_control_audit.json",
    "s1_runner_fixture_audit.json",
    "source_replay_audit.json",
)

QualificationTerminalCategory = Literal[
    "model_valid_trajectory",
    "model_invalid_trajectory",
    "typed_semantic_rejection",
    "ordinary_detour_allowance_exhausted",
    "typed_budget_no_call",
    "provider_transport_failure",
    "instrument_failure",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_133_transitive_source",
        "v26_133_output",
        "v26_134_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class ExecutionSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    predecessor_source_replay_id: str = EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
    predecessor_transitive_file_count: Literal[3209] = 3209
    predecessor_output_file_count: Literal[15] = 15
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[3225] = 3225
    replay_pass_count: Literal[3225] = 3225
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=3225, max_length=3225)
    replay_before_profile_parsing: Literal[True] = True
    replay_before_credential_lookup: Literal[True] = True
    replay_before_client_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_s1_execution_source_replay.v1"] = (
        "finance_v26_s1_execution_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.replayed_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.134 source replay changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_s1_execution_source_replay:",
        ):
            raise ValueError("v26.134 source replay identity changed")
        return self


class PreexecutionBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    outcome_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    rebuilt_preflight_output_count: Literal[15] = 15
    byte_identical_preflight_output_count: Literal[15] = 15
    exact_job_count: Literal[32] = 32
    distinct_engineering_task_count: Literal[24] = 24
    mechanism_path_cell_count: Literal[12] = 12
    scripted_fixture_job_count: Literal[32] = 32
    scripted_fixture_call_count: Literal[256] = 256
    scripted_first_action_qualified_count: Literal[32] = 32
    role_source_job_count: Literal[0] = 0
    role_source_model_exposure_count: Literal[0] = 0
    role_class_external_action_opportunity_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    real_model_client_constructed: Literal[False] = False
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_s1_execution_preexecution_binding.v1"] = (
        "finance_v26_s1_execution_preexecution_binding.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PreexecutionBindingAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_s1_execution_preexecution_binding:",
        ):
            raise ValueError("v26.134 preexecution binding identity changed")
        return self


class QualificationJobResult(FrozenModel):
    result_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    outcome_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    job_id: str = Field(min_length=1)
    predecessor_job_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: str = Field(min_length=1)
    mechanism_path_cell: str = Field(min_length=1)
    terminal_category: QualificationTerminalCategory
    raw_terminal_disposition: preflight.QualificationTerminal
    terminal_failure_type: str | None = None
    execution_error: str | None = None

    provider_call_count: int = Field(ge=0, le=23)
    transport_inclusive_invocation_count: int = Field(ge=0, le=24)
    provider_envelope_count: int = Field(ge=0, le=23)
    public_payload_projection_count: int = Field(ge=0, le=23)
    validated_public_payload_count: int = Field(ge=0, le=23)
    privacy_rejected_payload_count: int = Field(ge=0, le=23)
    provider_failure_no_payload_count: int = Field(ge=0, le=23)
    http_success_call_count: int = Field(ge=0, le=23)
    provider_prompt_tokens: int = Field(ge=0)
    provider_completion_tokens: int = Field(ge=0)
    provider_reasoning_tokens: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0, le=1120000)
    estimated_cost_usd: str = Field(min_length=1)
    reasoning_content_length_total: int = Field(ge=0)
    maximum_prompt_utf8_bytes: int = Field(ge=0, le=60000)
    maximum_action_prompt_utf8_bytes: int = Field(ge=0, le=60000)
    maximum_final_prompt_utf8_bytes: int = Field(ge=0, le=60000)
    logical_primary_request_count: int = Field(ge=0, le=21)
    primary_attempt_count: int = Field(ge=0, le=21)
    abi_rescue_attempt_count: int = Field(ge=0, le=1)
    semantic_recovery_attempt_count: int = Field(ge=0, le=1)
    transport_replacement_attempt_count: int = Field(ge=0, le=1)

    semantic_response_payload_count: int = Field(ge=0, le=23)
    exact_four_field_action_payload_count: int = Field(ge=0, le=21)
    semantic_choice_count: int = Field(ge=0, le=21)
    first_choice_present: bool
    first_exact_action_abi: bool
    first_current_state_binding: bool
    first_visible_action_binding: bool
    first_decision_kind_binding: bool
    first_reversible_same_action_commit: bool
    first_action_interface_qualified: bool
    first_action_public_progress: bool
    first_action_prompt_only_reference: bool | None = None
    first_action_candidate_count: int | None = Field(default=None, ge=1)
    first_action_zero_based_position: int | None = Field(default=None, ge=0)

    reversible_stage_two_commit_count: int = Field(ge=0, le=21)
    public_observation_count: int = Field(ge=0, le=20)
    successful_observation_count: int = Field(ge=0, le=20)
    failed_observation_count: int = Field(ge=0, le=20)
    progress_vector_change_count: int = Field(ge=0, le=20)
    reference_baseline_no_immediate_progress_count: int = Field(ge=0, le=20)
    nonreference_ordinary_detour_event_count: int = Field(ge=0, le=2)
    diagnostic_state_change_outside_progress_vector_count: int = Field(ge=0, le=20)
    ordinary_detour_count: int = Field(ge=0, le=2)
    detour_measurement_support_exit: bool
    semantic_rejection_count: int = Field(ge=0, le=1)

    completed_program_node_count: int = Field(ge=0)
    program_node_count: int = Field(ge=0)
    program_closed: bool
    terminal_node_completed: bool
    postterminal_verification_completed: bool
    final_commit_count: int = Field(ge=0, le=1)
    final_request_attempt_count: int = Field(ge=0, le=2)
    exact_two_field_final_payload_count: int = Field(ge=0, le=1)
    final_abi_crossed: bool
    final_answer_emitted: bool
    final_answer_semantically_valid: bool
    mechanism_evaluated: bool
    mechanism_success: bool
    independent_trajectory_validity: bool
    actual_route: str = Field(min_length=1)
    requested_path_adhered: bool
    replay_v3_passed: bool
    verification_report: AuthorityPreservingVerificationReport | None = None
    mechanism_outcome: MechanismEstimandOutcome

    exact_model_passed: bool
    fallback_absent: bool
    provider_native_tool_absent: bool
    thinking_continuity_passed: bool
    provider_usage_complete: bool
    dynamic_precall_binding_passed: bool
    exact_request_binding_passed: bool
    privacy_artifact_pairing_passed: bool
    reversible_commit_integrity_passed: bool
    rollout_budget_passed: bool
    rollout_headroom_tokens: int = Field(ge=0, le=1120000)
    instrument_failure: bool
    privacy_gate_failure: bool
    model_identity_thinking_or_usage_gate_failure: bool
    stage_two_provider_call_count: Literal[0] = 0
    role_class_external_action_opportunity_count: Literal[0] = 0
    role_class_external_action_selected_count: Literal[0] = 0
    raw_execution_artifact: legacy.RawFileDescriptor

    engineering_qualification_only: Literal[True] = True
    role_scale_readability_claimed: Literal[False] = False
    capability_reachability_state_mapping_eligible: Literal[False] = False
    schema_version: Literal["finance_v26_s1_qualification_job_result.v1"] = (
        "finance_v26_s1_qualification_job_result.v1"
    )

    @model_validator(mode="after")
    def validate_result(self) -> QualificationJobResult:
        if self.provider_reasoning_tokens > self.provider_completion_tokens:
            raise ValueError("v26.134 Reasoning Usage exceeds Completion Usage")
        if self.provider_call_count != (
            self.validated_public_payload_count
            + self.privacy_rejected_payload_count
            + self.provider_failure_no_payload_count
        ):
            raise ValueError("v26.134 public Projection partition changed")
        if (
            self.provider_envelope_count != self.provider_call_count
            or self.public_payload_projection_count != self.provider_call_count
        ):
            raise ValueError("v26.134 privacy-first Provider denominator changed")
        expected_first = bool(
            self.first_exact_action_abi
            and self.first_current_state_binding
            and self.first_visible_action_binding
            and self.first_decision_kind_binding
            and self.first_reversible_same_action_commit
        )
        if self.first_action_interface_qualified != expected_first:
            raise ValueError("v26.134 first-action qualification changed")
        if self.final_abi_crossed != bool(self.exact_two_field_final_payload_count):
            raise ValueError("v26.134 Final ABI accounting changed")
        if self.final_answer_semantically_valid and not self.final_answer_emitted:
            raise ValueError("v26.134 semantic validity lacks a Final answer")
        if self.detour_measurement_support_exit != (
            self.terminal_category == "ordinary_detour_allowance_exhausted"
        ):
            raise ValueError("v26.134 Detour support-exit classification changed")
        if self.detour_measurement_support_exit and self.independent_trajectory_validity:
            raise ValueError("v26.134 Detour support exit became a valid/model-invalid result")
        if self.independent_trajectory_validity != (
            self.terminal_category == "model_valid_trajectory"
        ):
            raise ValueError("v26.134 independent-validity terminal changed")
        if self.result_id != _identity(
            self,
            "result_id",
            "finance_v26_s1_qualification_job_result:",
        ):
            raise ValueError("v26.134 Job-result identity changed")
        return self


class MechanismPathCellSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: str = Field(min_length=1)
    job_count: int = Field(gt=0)
    first_action_interface_qualified_count: int = Field(ge=0)
    terminal_counts: dict[str, int]

    @model_validator(mode="after")
    def validate_summary(self) -> MechanismPathCellSummary:
        if (
            sum(self.terminal_counts.values()) != self.job_count
            or self.first_action_interface_qualified_count > self.job_count
        ):
            raise ValueError("v26.134 Mechanism x Path summary changed")
        if self.summary_id != _identity(
            self,
            "summary_id",
            "finance_v26_s1_qualification_cell_summary:",
        ):
            raise ValueError("v26.134 cell-summary identity changed")
        return self


class QualificationRawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    job_result_count: Literal[32] = 32
    raw_execution_count: Literal[32] = 32
    provider_call_count: int = Field(ge=0, le=736)
    transport_inclusive_invocation_count: int = Field(ge=0, le=768)
    provider_envelope_count: int = Field(ge=0, le=736)
    public_payload_projection_count: int = Field(ge=0, le=736)
    complete_provider_pair_count: int = Field(ge=0, le=736)
    transport_invocation_certificate_count: int = Field(ge=0, le=768)
    unique_provider_envelope_id_count: int = Field(ge=0, le=736)
    unique_payload_projection_id_count: int = Field(ge=0, le=736)
    unique_transport_certificate_id_count: int = Field(ge=0, le=768)
    validated_public_payload_count: int = Field(ge=0, le=736)
    privacy_rejected_payload_count: int = Field(ge=0, le=736)
    provider_failure_no_payload_count: int = Field(ge=0, le=736)
    complete_raw_count: Literal[32] = 32
    file_count: int = Field(ge=32)
    files: tuple[legacy.RawFileDescriptor, ...] = Field(min_length=32)
    exact_byte_replay_pass_count: int = Field(ge=32)
    private_reasoning_payload_count: Literal[0] = 0
    invalid_payload_content_persistence_count: Literal[0] = 0
    raw_http_body_persistence_count: Literal[0] = 0
    raw_request_body_persistence_count: Literal[0] = 0
    role_source_job_count: Literal[0] = 0
    role_class_external_action_opportunity_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_s1_qualification_raw_lineage.v1"] = (
        "finance_v26_s1_qualification_raw_lineage.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> QualificationRawLineageAudit:
        if (
            self.file_count != len(self.files)
            or self.exact_byte_replay_pass_count != self.file_count
            or self.provider_call_count != self.provider_envelope_count
            or self.provider_call_count != self.public_payload_projection_count
            or self.provider_call_count != self.complete_provider_pair_count
            or self.transport_inclusive_invocation_count
            != self.transport_invocation_certificate_count
            or self.provider_call_count
            != self.validated_public_payload_count
            + self.privacy_rejected_payload_count
            + self.provider_failure_no_payload_count
        ):
            raise ValueError("v26.134 Raw Lineage denominator changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_s1_qualification_raw_lineage:",
        ):
            raise ValueError("v26.134 Raw Lineage identity changed")
        return self


class QualificationExecutionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    preexecution_binding_audit_id: str = Field(min_length=1)
    qualification_contract_id: str = EXPECTED_QUALIFICATION_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    outcome_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    raw_lineage_audit_id: str = Field(min_length=1)
    exact_job_denominator: Literal[32] = 32
    completed_job_result_count: Literal[32] = 32
    terminal_counts: dict[str, int]

    provider_call_count: int = Field(ge=0, le=736)
    transport_inclusive_invocation_count: int = Field(ge=0, le=768)
    provider_envelope_count: int = Field(ge=0, le=736)
    public_payload_projection_count: int = Field(ge=0, le=736)
    validated_public_payload_count: int = Field(ge=0, le=736)
    privacy_rejected_payload_count: int = Field(ge=0, le=736)
    provider_failure_no_payload_count: int = Field(ge=0, le=736)
    http_success_call_count: int = Field(ge=0, le=736)
    provider_prompt_tokens: int = Field(ge=0)
    provider_completion_tokens: int = Field(ge=0)
    provider_reasoning_tokens: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    estimated_cost_usd: str = Field(min_length=1)
    maximum_prompt_utf8_bytes: int = Field(ge=0, le=60000)
    maximum_job_provider_tokens: int = Field(ge=0, le=1120000)

    provider_exposed_job_count: int = Field(ge=0, le=32)
    all_persisted_calls_http_success_job_count: int = Field(ge=0, le=32)
    exact_model_pass_job_count: int = Field(ge=0, le=32)
    thinking_continuity_pass_job_count: int = Field(ge=0, le=32)
    provider_usage_complete_job_count: int = Field(ge=0, le=32)
    exact_action_payload_job_count: int = Field(ge=0, le=32)
    first_exact_action_abi_job_count: int = Field(ge=0, le=32)
    first_current_state_binding_job_count: int = Field(ge=0, le=32)
    first_visible_action_binding_job_count: int = Field(ge=0, le=32)
    first_decision_kind_binding_job_count: int = Field(ge=0, le=32)
    first_reversible_commit_job_count: int = Field(ge=0, le=32)
    first_action_interface_qualified_job_count: int = Field(ge=0, le=32)
    qualified_mechanism_path_cell_count: int = Field(ge=0, le=12)
    mechanism_path_cell_summaries: tuple[MechanismPathCellSummary, ...] = Field(
        min_length=12,
        max_length=12,
    )

    primary_request_count: int = Field(ge=0, le=672)
    abi_rescue_call_count: int = Field(ge=0, le=32)
    semantic_recovery_call_count: int = Field(ge=0, le=32)
    transport_replacement_invocation_count: int = Field(ge=0, le=32)
    no_abi_rescue_job_count: int = Field(ge=0, le=32)
    abi_rescue_job_count: int = Field(ge=0, le=32)
    semantic_recovery_job_count: int = Field(ge=0, le=32)
    transport_replacement_job_count: int = Field(ge=0, le=32)

    exact_four_field_action_payload_count: int = Field(ge=0)
    semantic_choice_count: int = Field(ge=0)
    reversible_stage_two_commit_count: int = Field(ge=0)
    public_observation_count: int = Field(ge=0)
    successful_observation_count: int = Field(ge=0)
    failed_observation_count: int = Field(ge=0)
    progress_vector_change_count: int = Field(ge=0)
    reference_baseline_no_immediate_progress_count: int = Field(ge=0)
    nonreference_ordinary_detour_event_count: int = Field(ge=0)
    diagnostic_state_change_outside_progress_vector_count: int = Field(ge=0)
    ordinary_detour_job_distribution: dict[str, int]
    detour_measurement_support_exit_job_count: int = Field(ge=0, le=32)
    typed_semantic_rejection_job_count: int = Field(ge=0, le=32)
    typed_budget_no_call_job_count: int = Field(ge=0, le=32)
    provider_transport_failure_job_count: int = Field(ge=0, le=32)
    instrument_failure_job_count: int = Field(ge=0, le=32)
    model_invalid_trajectory_count: int = Field(ge=0, le=32)

    program_closed_job_count: int = Field(ge=0, le=32)
    terminal_node_completed_job_count: int = Field(ge=0, le=32)
    postterminal_verification_completed_job_count: int = Field(ge=0, le=32)
    exact_final_abi_job_count: int = Field(ge=0, le=32)
    final_answer_emitted_job_count: int = Field(ge=0, le=32)
    final_answer_semantically_valid_job_count: int = Field(ge=0, le=32)
    mechanism_success_job_count: int = Field(ge=0, le=32)
    independently_valid_trajectory_count: int = Field(ge=0, le=32)

    privacy_gate_failure_job_count: int = Field(ge=0, le=32)
    model_identity_failure_job_count: int = Field(ge=0, le=32)
    thinking_failure_job_count: int = Field(ge=0, le=32)
    usage_failure_job_count: int = Field(ge=0, le=32)
    combined_integrity_gate_failure_job_count: int = Field(ge=0, le=32)
    first_action_interface_minimum_jobs: Literal[24] = 24
    required_mechanism_path_cell_coverage: Literal[12] = 12
    representation_qualification_gate_passed: bool

    stage_two_provider_call_count: Literal[0] = 0
    role_source_job_count: Literal[0] = 0
    role_source_model_exposure_count: Literal[0] = 0
    role_class_external_action_opportunity_count: Literal[0] = 0
    role_class_external_action_selection_frequency_measured: Literal[False] = False
    capability_rows: Literal[0] = 0
    reachability_rows: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    training_rows: Literal[0] = 0
    release_rows: Literal[0] = 0
    production_contribution: Literal[0] = 0
    first_action_gate_is_not_full_trajectory_readability: Literal[True] = True
    repeated_engineering_source_outcomes_are_not_role_generalization_evidence: Literal[True] = True
    detour_support_exit_counts_as_model_invalid: Literal[False] = False
    final_abi_and_answer_validity_reported_separately: Literal[True] = True
    measured_object: Literal["s1_first_action_interface_entry_on_repeated_engineering_sources"] = (
        "s1_first_action_interface_entry_on_repeated_engineering_sources"
    )
    execution_status: Literal[
        "qualification_gate_passed_pending_independent_audit",
        "qualification_gate_failed_pending_independent_audit",
    ]
    next_permitted_stage: Literal[
        "s1_model_visible_representation_qualification_postrun_audit_only"
    ] = POSTRUN_STAGE
    schema_version: Literal["finance_v26_s1_qualification_execution_report.v1"] = (
        "finance_v26_s1_qualification_execution_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> QualificationExecutionReport:
        if sum(self.terminal_counts.values()) != self.exact_job_denominator:
            raise ValueError("v26.134 terminal denominator changed")
        if self.provider_call_count != (
            self.validated_public_payload_count
            + self.privacy_rejected_payload_count
            + self.provider_failure_no_payload_count
        ):
            raise ValueError("v26.134 aggregate Projection partition changed")
        if (
            self.provider_call_count != self.provider_envelope_count
            or self.provider_call_count != self.public_payload_projection_count
        ):
            raise ValueError("v26.134 aggregate privacy-first denominator changed")
        if sum(self.ordinary_detour_job_distribution.values()) != self.exact_job_denominator:
            raise ValueError("v26.134 Detour Job partition changed")
        expected_gate = bool(
            self.first_action_interface_qualified_job_count
            >= self.first_action_interface_minimum_jobs
            and self.qualified_mechanism_path_cell_count
            == self.required_mechanism_path_cell_coverage
            and self.combined_integrity_gate_failure_job_count == 0
        )
        if self.representation_qualification_gate_passed != expected_gate:
            raise ValueError("v26.134 pre-registered qualification Gate changed")
        expected_status = (
            "qualification_gate_passed_pending_independent_audit"
            if expected_gate
            else "qualification_gate_failed_pending_independent_audit"
        )
        if self.execution_status != expected_status:
            raise ValueError("v26.134 execution status changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_s1_qualification_execution_report:",
        ):
            raise ValueError("v26.134 execution-report identity changed")
        return self


class PreparedExecution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    source_replay: ExecutionSourceReplayAudit
    preflight_report: preflight.S1QualificationPreflightReport
    qualification_contract: preflight.S1RepresentationQualificationContract
    manifest: preflight.S1QualificationManifest
    outcome_contract: preflight.S1QualificationOutcomeContract
    runner_contract: preflight.S1QualificationRunnerContract
    resource_contract: preflight.S1QualificationResourceContract
    transition_contract: preflight.ProspectiveTransitionContract
    preexecution_binding: PreexecutionBindingAudit
    loaded: Any


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: Any) -> None:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(payload))
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _descriptor(path: Path, output_dir: Path) -> legacy.RawFileDescriptor:
    return legacy.RawFileDescriptor(
        relative_path=str(path.resolve().relative_to(output_dir.resolve())),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def _find_bound_path(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        candidate = root / relative_path
        if candidate.is_file() and _sha256(candidate) == expected_sha256:
            return candidate
    raise ValueError(f"v26.134 cannot replay bound file: {relative_path}")


def build_execution_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    preflight_dir: Path,
) -> ExecutionSourceReplayAudit:
    source = preflight.SourceReplayAudit.model_validate(
        _load(preflight_dir / "source_replay_audit.json")
    )
    report_path = preflight_dir / "report.json"
    transition_path = preflight_dir / "prospective_transition_contract.json"
    report = preflight.S1QualificationPreflightReport.model_validate(_load(report_path))
    if (
        source.audit_id != EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
        or report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or _sha256(report_path) != EXPECTED_PREFLIGHT_REPORT_SHA256
        or _sha256(transition_path) != EXPECTED_TRANSITION_SHA256
    ):
        raise ValueError("v26.134 predecessor report, transition, or replay bytes changed")
    entries: dict[str, SourceReplayEntry] = {}
    for item in source.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries[item.relative_path] = SourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_133_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
    details = {item.relative_path: item for item in report.detail_files}
    if set(PREFLIGHT_OUTPUTS) != {"report.json", *details}:
        raise ValueError("v26.134 predecessor output set changed")
    for name in PREFLIGHT_OUTPUTS:
        path = preflight_dir / name
        if not path.is_file():
            raise ValueError(f"v26.134 predecessor output missing: {name}")
        observed = _sha256(path)
        if name != "report.json":
            expected = details[name]
            if expected.sha256 != observed or expected.byte_count != path.stat().st_size:
                raise ValueError("v26.134 predecessor detail binding changed")
        relative = str(Path(PREFLIGHT_DIR) / name)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_133_output",
            expected_sha256=observed,
            observed_sha256=observed,
            byte_count=path.stat().st_size,
        )
    implementation_path = implementation_root / IMPLEMENTATION_PATH
    observed = _sha256(implementation_path)
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_134_implementation",
        expected_sha256=observed,
        observed_sha256=observed,
        byte_count=implementation_path.stat().st_size,
    )
    ordered = tuple(entries[key] for key in sorted(entries))
    values: dict[str, Any] = {"entries": ordered}
    provisional = ExecutionSourceReplayAudit.model_construct(audit_id="pending", **values)
    return ExecutionSourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_s1_execution_source_replay:",
        ),
        **values,
    )


def _rebuild_preflight_outputs(
    *,
    package_root: Path,
    implementation_root: Path,
    preflight_dir: Path,
) -> PreexecutionBindingAudit:
    with tempfile.TemporaryDirectory(prefix="v26_134_preexecution_rebuild_") as temporary:
        rebuilt_dir = Path(temporary)
        report = preflight.build_preflight(
            package_root=package_root,
            implementation_root=implementation_root,
            output_dir=rebuilt_dir,
        )
        for name in PREFLIGHT_OUTPUTS:
            if (preflight_dir / name).read_bytes() != (rebuilt_dir / name).read_bytes():
                raise ValueError(f"v26.134 predecessor rebuild changed: {name}")
    fixture = preflight.RunnerFixtureAudit.model_validate(
        _load(preflight_dir / "s1_runner_fixture_audit.json")
    )
    manifest = preflight.S1QualificationManifest.model_validate(
        _load(preflight_dir / "s1_qualification_manifest.json")
    )
    values: dict[str, Any] = {
        "scripted_fixture_job_count": fixture.scripted_job_count,
        "scripted_fixture_call_count": fixture.scripted_local_calls,
        "scripted_first_action_qualified_count": (fixture.first_action_interface_qualified_count),
        "exact_job_count": len(manifest.jobs),
        "distinct_engineering_task_count": len({item.task_package_id for item in manifest.jobs}),
        "mechanism_path_cell_count": len(manifest.cell_job_counts),
    }
    if report.report_id != EXPECTED_PREFLIGHT_REPORT_ID:
        raise ValueError("v26.134 rebuilt preflight report identity changed")
    provisional = PreexecutionBindingAudit.model_construct(audit_id="pending", **values)
    return PreexecutionBindingAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_s1_execution_preexecution_binding:",
        ),
        **values,
    )


def prepare_execution(
    *,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
) -> PreparedExecution:
    output_dir.mkdir(parents=True, exist_ok=True)
    source = build_execution_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        preflight_dir=preflight_dir,
    )
    _write_json_atomic(output_dir / "online_source_replay_audit.json", source)
    preexecution = _rebuild_preflight_outputs(
        package_root=package_root,
        implementation_root=implementation_root,
        preflight_dir=preflight_dir,
    )
    report = preflight.S1QualificationPreflightReport.model_validate(
        _load(preflight_dir / "report.json")
    )
    qualification = preflight.S1RepresentationQualificationContract.model_validate(
        _load(preflight_dir / "s1_representation_qualification_contract.json")
    )
    manifest = preflight.S1QualificationManifest.model_validate(
        _load(preflight_dir / "s1_qualification_manifest.json")
    )
    outcome = preflight.S1QualificationOutcomeContract.model_validate(
        _load(preflight_dir / "s1_qualification_outcome_contract.json")
    )
    runner = preflight.S1QualificationRunnerContract.model_validate(
        _load(preflight_dir / "s1_qualification_runner_contract.json")
    )
    resource = preflight.S1QualificationResourceContract.model_validate(
        _load(preflight_dir / "s1_qualification_resource_contract.json")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate(
        _load(preflight_dir / "prospective_transition_contract.json")
    )
    separation = preflight.QualificationSourceSeparationAudit.model_validate(
        _load(preflight_dir / "qualification_source_separation_audit.json")
    )
    progress = preflight.PublicProgressVectorContract.model_validate(
        _load(preflight_dir / "public_progress_vector_contract.json")
    )
    path_catalog = preflight.S1QualificationPathCatalog.model_validate(
        _load(preflight_dir / "s1_qualification_path_catalog.json")
    )
    if (
        report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or report.source_replay_audit_id != EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
        or report.source_separation_audit_id != EXPECTED_SOURCE_SEPARATION_ID
        or report.progress_vector_contract_id != EXPECTED_PROGRESS_CONTRACT_ID
        or report.path_catalog_id != EXPECTED_PATH_CATALOG_ID
        or report.resource_contract_id != EXPECTED_RESOURCE_CONTRACT_ID
        or report.qualification_contract_id != EXPECTED_QUALIFICATION_CONTRACT_ID
        or report.manifest_id != EXPECTED_MANIFEST_ID
        or report.outcome_contract_id != EXPECTED_OUTCOME_CONTRACT_ID
        or report.runner_contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or report.transition_contract_id != EXPECTED_TRANSITION_ID
        or report.status != "s1_representation_qualification_runner_preflight_passed"
        or report.next_permitted_stage != preflight.NEXT_STAGE
        or report.provider_calls
        or report.stage_two_provider_calls
        or separation.audit_id != EXPECTED_SOURCE_SEPARATION_ID
        or progress.contract_id != EXPECTED_PROGRESS_CONTRACT_ID
        or path_catalog.catalog_id != EXPECTED_PATH_CATALOG_ID
        or resource.contract_id != EXPECTED_RESOURCE_CONTRACT_ID
        or qualification.contract_id != EXPECTED_QUALIFICATION_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_MANIFEST_ID
        or outcome.contract_id != EXPECTED_OUTCOME_CONTRACT_ID
        or runner.contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or transition.contract_id != EXPECTED_TRANSITION_ID
        or transition.next_permitted_stage != preflight.NEXT_STAGE
        or not transition.provider_calls_authorized
        or not transition.only_exact_fresh_32_job_engineering_manifest_authorized
        or transition.role_provider_calls_authorized
        or transition.capability_reachability_execution_authorized
        or len(manifest.jobs) != 32
        or len({item.job_id for item in manifest.jobs}) != 32
        or manifest.role_source_job_count
        or manifest.prospective_execution_run_id != RUN_ID
        or runner.execution_run_id != RUN_ID
        or runner.stage_two_provider_call_upper_bound
    ):
        raise ValueError("v26.134 exact online authorization changed")
    loaded = preflight._load_inputs(package_root, implementation_root)  # noqa: SLF001
    if (
        loaded.engineering.agent_model_config.public_manifest_hash
        != preflight.EXPECTED_MODEL_CONFIG_ID
        or loaded.engineering.stage_one.profile_id != preflight.EXPECTED_STAGE_ONE_PROFILE_ID
        or loaded.engineering.stage_two.profile_id != preflight.EXPECTED_STAGE_TWO_PROFILE_ID
    ):
        raise ValueError("v26.134 model, Thinking, or Stage 2 profile changed")
    frozen_outputs: tuple[tuple[str, Any], ...] = (
        ("preexecution_binding_audit.json", preexecution),
        ("frozen_s1_qualification_contract.json", qualification),
        ("frozen_s1_qualification_manifest.json", manifest),
        ("frozen_s1_qualification_outcome_contract.json", outcome),
        ("frozen_s1_qualification_runner_contract.json", runner),
        ("frozen_s1_qualification_resource_contract.json", resource),
        ("frozen_public_progress_vector_contract.json", progress),
        ("frozen_qualification_source_separation_audit.json", separation),
        ("frozen_preflight_transition_contract.json", transition),
    )
    for name, value in frozen_outputs:
        _write_json_atomic(output_dir / name, value)
    return PreparedExecution(
        source_replay=source,
        preflight_report=report,
        qualification_contract=qualification,
        manifest=manifest,
        outcome_contract=outcome,
        runner_contract=runner,
        resource_contract=resource,
        transition_contract=transition,
        preexecution_binding=preexecution,
        loaded=loaded,
    )


def _provider_pairs(
    raw: preflight.S1QualificationRawExecution,
    output_dir: Path,
) -> tuple[
    tuple[
        privacy_runner.PrivacyFirstProviderEnvelope,
        privacy_runner.PublicPayloadProjection,
    ],
    ...,
]:
    envelopes: list[privacy_runner.PrivacyFirstProviderEnvelope] = []
    projections: list[privacy_runner.PublicPayloadProjection] = []
    for descriptor in raw.provider_envelope_artifacts:
        path = output_dir / descriptor.relative_path
        if (
            not path.is_file()
            or _sha256(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.134 Provider Envelope binding changed")
        envelopes.append(privacy_runner.PrivacyFirstProviderEnvelope.model_validate(_load(path)))
    for descriptor in raw.public_payload_projection_artifacts:
        path = output_dir / descriptor.relative_path
        if (
            not path.is_file()
            or _sha256(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.134 public Projection binding changed")
        projections.append(privacy_runner.PublicPayloadProjection.model_validate(_load(path)))
    if len(envelopes) != len(projections):
        raise ValueError("v26.134 Envelope/Projection denominator diverged")
    pairs = tuple(zip(envelopes, projections, strict=True))
    for envelope, projection in pairs:
        privacy_runner.validate_provider_artifact_pair(envelope, projection)
    return pairs


def _choice_diagnostics(
    *,
    raw: preflight.S1QualificationRawExecution,
    prepared: PreparedExecution,
    binding: Any,
) -> tuple[semantic_online.ChoiceDiagnostic, ...]:
    observations: list[Any] = []
    rejections: list[Any] = []
    rejection_by_id = {item.rejection_id: item for item in raw.semantic_rejections}
    event_by_index = {item.logical_request_index: item for item in raw.progress_events}
    diagnostics: list[semantic_online.ChoiceDiagnostic] = []
    previous_legal_no_progress = False
    ordinary_detour_count = 0
    condition = (
        None
        if binding.source_registered_path.role == "capability"
        else binding.source_registered_path.path_strategy_id
    )
    for choice in raw.semantic_choices:
        state = preflight.build_semantic_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            tuple(observations),
            semantic_rejections=tuple(rejections),
        )
        if state.state_id != choice.state_id:
            raise ValueError("v26.134 reconstructed Choice state differs from Raw binding")
        presentation_salt = canonical_hash(
            {
                "qualification_job_id": raw.job.job_id,
                "logical_request_index": choice.logical_request_index,
                "state_id": state.state_id,
                "semantic_recovery_count": len(rejections),
                "ordinary_detour_count": ordinary_detour_count,
            },
            prefix="finance_v26_s1_qualification_candidate_presentation:",
        )
        typed_failure = None
        if choice.public_attempt_phase == "semantic_recovery":
            if not rejections:
                raise ValueError("v26.134 Semantic Recovery Choice lacks a rejection")
            rejection = rejections[-1]
            typed_failure = {
                "family": "semantic_action_rejection",
                "subtype": rejection.error_category,
                "rejection_id": rejection.rejection_id,
            }
        primary = preflight.predecessor.predecessor._compact_action_prompt(  # noqa: SLF001
            phase=choice.public_attempt_phase,
            instruction=binding.record.task_package.task.public.instruction,
            state=state,
            public_path_condition=condition,
            presentation_salt=presentation_salt,
            typed_failure=typed_failure,
            grammar=prepared.loaded.engineering.action_grammar,
        )
        attempts = tuple(
            item
            for item in raw.attempts
            if item.request_kind == "semantic_proposal"
            and item.logical_request_index == choice.logical_request_index
        )
        usable = tuple(item for item in attempts if item.disposition == "usable")
        if len(usable) != 1:
            raise ValueError("v26.134 accepted Choice lacks one usable response attempt")
        active = usable[0]
        prompt = primary
        response_phase: Literal["primary", "abi_rescue", "semantic_recovery"] = (
            choice.public_attempt_phase
        )
        if active.public_attempt_phase == "abi_rescue":
            initial = attempts[0]
            family = initial.failure_family or "channel_parse_failure"
            subtype = (
                initial.failure_subtype or initial.completion_failure_type or "completion_failure"
            )
            prompt = preflight.predecessor.predecessor._compact_action_prompt(  # noqa: SLF001
                phase="abi_rescue",
                instruction=binding.record.task_package.task.public.instruction,
                state=state,
                public_path_condition=condition,
                presentation_salt=presentation_salt,
                typed_failure={"family": family, "subtype": subtype},
                grammar=prepared.loaded.engineering.action_grammar,
            )
            response_phase = "abi_rescue"
        if legacy.sha256_text(prompt) != active.prompt_sha256:
            raise ValueError("v26.134 reconstructed S1 Choice Prompt changed")
        decoded_state, _ = preflight._state_from_s1_prompt(prompt)  # noqa: SLF001
        if decoded_state != state:
            raise ValueError("v26.134 S1 Prompt reconstruction changed its public state")
        reference_action_id = preflight._reference_proposal_from_s1_prompt(  # noqa: SLF001
            prompt
        ).action_id
        candidate_rows: list[semantic_online.CandidatePresentationRow] = []
        selected_position: int | None = None
        selected_bytes: int | None = None
        selected_family: str | None = None
        selected_reference: bool | None = None
        for position, candidate in enumerate(decoded_state.action_candidates):
            candidate_value = candidate.model_dump(mode="json")
            description_bytes = len(_canonical_bytes(candidate_value))
            family = semantic_online._candidate_family(candidate_value)  # noqa: SLF001
            is_reference = candidate.action_id == reference_action_id
            is_selected = candidate.action_id == choice.selected_action_id
            candidate_rows.append(
                semantic_online.CandidatePresentationRow(
                    action_id=candidate.action_id,
                    zero_based_position=position,
                    description_utf8_bytes=description_bytes,
                    candidate_family=family,
                    prompt_only_reference=is_reference,
                    selected_by_model=is_selected,
                )
            )
            if is_selected:
                selected_position = position
                selected_bytes = description_bytes
                selected_family = family
                selected_reference = is_reference
        before_nodes = semantic_online._progress_diagnostic(  # noqa: SLF001
            binding.record, tuple(observations)
        )[0]
        if choice.observation_status is not None:
            observation_index = len(observations)
            if observation_index >= len(raw.observations):
                raise ValueError("v26.134 Choice references a missing Observation")
            observation = raw.observations[observation_index]
            if observation.status != choice.observation_status:
                raise ValueError("v26.134 Choice Observation status changed")
            observations.append(observation)
        after_nodes = semantic_online._progress_diagnostic(  # noqa: SLF001
            binding.record, tuple(observations)
        )[0]
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
            "public_state_id": state.state_id,
            "candidate_count": len(candidate_rows),
            "decision_load_natural_log": math.log(len(candidate_rows)),
            "candidates": tuple(candidate_rows),
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
            "completed_program_nodes_before": before_nodes,
            "completed_program_nodes_after": after_nodes,
            "program_node_progress": after_nodes > before_nodes,
            "terminal_verification_ready_before": any(
                item.candidate_family == "verify_terminal_operation" for item in candidate_rows
            ),
            "legal_no_progress_choice": legal_no_progress,
            "ordinary_replan_after_legal_no_progress": previous_legal_no_progress,
        }
        provisional = semantic_online.ChoiceDiagnostic.model_construct(
            diagnostic_id="pending", **values
        )
        diagnostics.append(
            semantic_online.ChoiceDiagnostic(
                diagnostic_id=_identity(
                    provisional,
                    "diagnostic_id",
                    "finance_v26_semantic_action_choice_diagnostic:",
                ),
                **values,
            )
        )
        if choice.rejection_id is not None:
            rejection = rejection_by_id.get(choice.rejection_id)
            if rejection is None:
                raise ValueError("v26.134 Choice rejection lacks its public Observation")
            rejections.append(rejection)
        event = event_by_index.get(choice.logical_request_index)
        if event is not None:
            ordinary_detour_count = event.ordinary_detour_count_after
        previous_legal_no_progress = legal_no_progress
    if len(observations) != len(raw.observations):
        raise ValueError("v26.134 Choice diagnostics did not consume every Observation")
    return tuple(diagnostics)


def _prompt_maximum(
    attempts: Sequence[privacy_runner.PrivacyFirstAttempt],
    request_kind: str | None = None,
) -> int:
    selected = tuple(
        item.prompt_utf8_bytes
        for item in attempts
        if request_kind is None or item.request_kind == request_kind
    )
    return max(selected, default=0)


def project_job_result(
    *,
    raw: preflight.S1QualificationRawExecution,
    prepared: PreparedExecution,
    binding: Any,
    output_dir: Path,
) -> tuple[QualificationJobResult, tuple[semantic_online.ChoiceDiagnostic, ...]]:
    replay = legacy.replay_v3(
        cast(Any, raw),
        static=prepared.loaded.engineering.predecessor.historical,
        binding=binding,
    )
    mechanism = evaluate_mechanism_estimand(
        cast(Any, binding.record),
        raw.observations,
        stopped_by_model=raw.completed_result is not None,
    )
    verification: AuthorityPreservingVerificationReport | None = None
    if raw.completed_result is not None:
        verification, mechanism = final_preflight._completed_verification(  # noqa: SLF001
            raw=cast(Any, raw),
            replay=replay,
            binding=binding,
        )
    diagnostics = _choice_diagnostics(
        raw=raw,
        prepared=prepared,
        binding=binding,
    )
    pairs = _provider_pairs(raw, output_dir)
    projection_counts = Counter(projection.projection_status for _, projection in pairs)
    exact_model, fallback_absent, native_absent, thinking, usage = semantic_online._telemetry_flags(
        raw.provider_telemetry
    )  # noqa: SLF001
    dynamic = all(
        item.dynamic_certificate_id is not None and item.resource_certificate_id is not None
        for item in raw.attempts
        if item.provider_call_made
    )
    exact_request = all(
        item.request_binding_certificate_id is not None
        for item in raw.attempts
        if item.provider_call_made
    )
    privacy_pairing = bool(
        len(pairs)
        == len(raw.provider_envelope_artifacts)
        == len(raw.public_payload_projection_artifacts)
        == raw.stage_one_provider_call_count
    )
    reversible = all(
        item.reversible_same_action_id_passed
        and not item.semantic_choice_inserted_by_host
        and item.stage_two_provider_calls == 0
        for item in raw.commits
    )
    resource_passed = bool(
        raw.cumulative_provider_tokens <= prepared.resource_contract.rollout_upper_bound_tokens
        and raw.stage_one_provider_call_count
        <= prepared.resource_contract.maximum_stage_one_provider_calls
        and raw.transport_inclusive_invocation_count
        <= prepared.resource_contract.maximum_transport_inclusive_invocations
    )
    instrument = bool(
        raw.terminal_disposition == "instrument_failure"
        or not exact_model
        or not fallback_absent
        or not native_absent
        or not thinking
        or not usage
        or not dynamic
        or not exact_request
        or not privacy_pairing
        or not reversible
        or not replay.passed
        or not resource_passed
        or raw.stage_two_provider_call_count
    )
    answer_valid = bool(verification is not None and verification.valid)
    terminal: QualificationTerminalCategory
    if instrument:
        terminal = "instrument_failure"
    elif raw.terminal_disposition == "ordinary_detour_allowance_exhausted":
        terminal = "ordinary_detour_allowance_exhausted"
    elif raw.terminal_disposition == "typed_semantic_rejection":
        terminal = "typed_semantic_rejection"
    elif raw.terminal_disposition == "typed_budget_no_call":
        terminal = "typed_budget_no_call"
    elif raw.terminal_disposition == "provider_transport_failure":
        terminal = "provider_transport_failure"
    elif raw.completed_result is not None and answer_valid:
        terminal = "model_valid_trajectory"
    else:
        terminal = "model_invalid_trajectory"
    semantic_attempts = tuple(
        item for item in raw.attempts if item.request_kind == "semantic_proposal"
    )
    final_attempts = tuple(item for item in raw.attempts if item.request_kind == "final_answer")
    first_choice = raw.semantic_choices[0] if raw.semantic_choices else None
    first_diagnostic = diagnostics[0] if diagnostics else None
    if (first_choice is None) != (first_diagnostic is None):
        raise ValueError("v26.134 first Choice and diagnostic diverged")
    first_exact = bool(
        first_choice is not None
        and any(
            item.logical_request_index == first_choice.logical_request_index
            and item.exact_four_field_action_payload
            and item.disposition == "usable"
            for item in semantic_attempts
        )
    )
    first_commit = next(
        (
            item
            for item in raw.commits
            if first_choice is not None and item.commit.commit_id == first_choice.commit_id
        ),
        None,
    )
    first_state = bool(
        first_choice is not None
        and first_exact
        and (
            first_commit is None
            or (
                first_commit.public_state_id == first_choice.state_id
                and first_commit.proposal.state_id == first_choice.state_id
            )
        )
    )
    first_reversible = bool(
        first_commit is not None
        and first_commit.reversible_same_action_id_passed
        and not first_commit.semantic_choice_inserted_by_host
        and first_commit.stage_two_provider_calls == 0
    )
    first_interface = bool(
        first_exact
        and first_state
        and first_choice is not None
        and first_choice.visible_action_id_match
        and first_choice.decision_kind_match
        and first_reversible
    )
    if first_interface != raw.first_action_interface_qualified:
        raise ValueError("v26.134 independently recomputed first-action Gate changed")
    completed_nodes, node_count, program_closed, terminal_completed, verified = (
        semantic_online._progress_diagnostic(binding.record, raw.observations)  # noqa: SLF001
    )
    route = semantic_online._actual_route(raw.observations)  # noqa: SLF001
    progress_change = sum(
        item.observation_succeeded and item.progress_vector_changed for item in raw.progress_events
    )
    reference_baseline = sum(
        item.observation_succeeded
        and not item.progress_vector_changed
        and item.selected_action_matches_reference
        for item in raw.progress_events
    )
    detour_events = sum(item.ordinary_detour_observed for item in raw.progress_events)
    diagnostic_state_change = sum(
        item.diagnostic_public_state_changed_outside_progress_vector for item in raw.progress_events
    )
    final_commits = tuple(item for item in raw.commits if item.commit.action == "emit_final")
    exact_final = tuple(item for item in final_attempts if item.exact_two_field_final_payload)
    cost = sum(
        (
            Decimal(str(item.estimated_cost))
            for item in raw.provider_telemetry
            if item.estimated_cost is not None
        ),
        Decimal("0"),
    )
    privacy_gate_failure = bool(raw.privacy_rejected_payload_count or not privacy_pairing)
    telemetry_gate_failure = bool(not exact_model or not thinking or not usage)
    logical_primary_count = len({item.logical_request_index for item in raw.attempts})
    values: dict[str, Any] = {
        "job_id": raw.job.job_id,
        "predecessor_job_id": raw.job.predecessor_job_id,
        "source_task_artifact_id": raw.job.source_task_artifact_id,
        "mechanism_id": raw.job.mechanism_id,
        "path_strategy_id": raw.job.path_strategy_id,
        "mechanism_path_cell": f"{raw.job.mechanism_id}|{raw.job.path_strategy_id}",
        "terminal_category": terminal,
        "raw_terminal_disposition": raw.terminal_disposition,
        "terminal_failure_type": raw.terminal_failure_type,
        "execution_error": raw.execution_error,
        "provider_call_count": raw.stage_one_provider_call_count,
        "transport_inclusive_invocation_count": raw.transport_inclusive_invocation_count,
        "provider_envelope_count": len(raw.provider_envelope_artifacts),
        "public_payload_projection_count": len(raw.public_payload_projection_artifacts),
        "validated_public_payload_count": projection_counts["validated_public_payload"],
        "privacy_rejected_payload_count": projection_counts["privacy_rejected"],
        "provider_failure_no_payload_count": projection_counts["provider_failure_no_payload"],
        "http_success_call_count": sum(item.http_success for item in raw.provider_telemetry),
        "provider_prompt_tokens": sum(item.prompt_tokens or 0 for item in raw.provider_telemetry),
        "provider_completion_tokens": sum(
            item.completion_tokens or 0 for item in raw.provider_telemetry
        ),
        "provider_reasoning_tokens": sum(
            item.reasoning_tokens or 0 for item in raw.provider_telemetry
        ),
        "provider_total_tokens": sum(item.total_tokens or 0 for item in raw.provider_telemetry),
        "estimated_cost_usd": format(cost, "f"),
        "reasoning_content_length_total": sum(
            item.reasoning_content_length or 0 for item in raw.provider_telemetry
        ),
        "maximum_prompt_utf8_bytes": _prompt_maximum(raw.attempts),
        "maximum_action_prompt_utf8_bytes": _prompt_maximum(raw.attempts, "semantic_proposal"),
        "maximum_final_prompt_utf8_bytes": _prompt_maximum(raw.attempts, "final_answer"),
        "logical_primary_request_count": logical_primary_count,
        "primary_attempt_count": sum(
            item.public_attempt_phase != "abi_rescue" for item in raw.attempts
        ),
        "abi_rescue_attempt_count": raw.abi_rescue_attempt_count,
        "semantic_recovery_attempt_count": raw.semantic_recovery_attempt_count,
        "transport_replacement_attempt_count": raw.transport_replacement_attempt_count,
        "semantic_response_payload_count": sum(
            item.response_payload_present for item in semantic_attempts
        ),
        "exact_four_field_action_payload_count": raw.exact_four_field_action_payload_count,
        "semantic_choice_count": len(raw.semantic_choices),
        "first_choice_present": first_choice is not None,
        "first_exact_action_abi": first_exact,
        "first_current_state_binding": first_state,
        "first_visible_action_binding": bool(
            first_choice is not None and first_choice.visible_action_id_match
        ),
        "first_decision_kind_binding": bool(
            first_choice is not None and first_choice.decision_kind_match
        ),
        "first_reversible_same_action_commit": first_reversible,
        "first_action_interface_qualified": first_interface,
        "first_action_public_progress": bool(
            first_choice is not None and first_choice.public_progress_after_commit is True
        ),
        "first_action_prompt_only_reference": (
            first_diagnostic.selected_prompt_only_reference
            if first_diagnostic is not None
            else None
        ),
        "first_action_candidate_count": (
            first_diagnostic.candidate_count if first_diagnostic is not None else None
        ),
        "first_action_zero_based_position": (
            first_diagnostic.selected_zero_based_position if first_diagnostic is not None else None
        ),
        "reversible_stage_two_commit_count": len(raw.commits),
        "public_observation_count": len(raw.observations),
        "successful_observation_count": sum(
            item.status == "succeeded" for item in raw.observations
        ),
        "failed_observation_count": sum(item.status == "failed" for item in raw.observations),
        "progress_vector_change_count": progress_change,
        "reference_baseline_no_immediate_progress_count": reference_baseline,
        "nonreference_ordinary_detour_event_count": detour_events,
        "diagnostic_state_change_outside_progress_vector_count": diagnostic_state_change,
        "ordinary_detour_count": raw.ordinary_detour_count,
        "detour_measurement_support_exit": (
            raw.terminal_disposition == "ordinary_detour_allowance_exhausted"
        ),
        "semantic_rejection_count": len(raw.semantic_rejections),
        "completed_program_node_count": completed_nodes,
        "program_node_count": node_count,
        "program_closed": program_closed,
        "terminal_node_completed": terminal_completed,
        "postterminal_verification_completed": verified,
        "final_commit_count": len(final_commits),
        "final_request_attempt_count": len(final_attempts),
        "exact_two_field_final_payload_count": len(exact_final),
        "final_abi_crossed": bool(exact_final),
        "final_answer_emitted": raw.completed_result is not None,
        "final_answer_semantically_valid": answer_valid,
        "mechanism_evaluated": mechanism.evaluated,
        "mechanism_success": mechanism.success,
        "independent_trajectory_validity": terminal == "model_valid_trajectory",
        "actual_route": route,
        "requested_path_adhered": route == raw.job.path_strategy_id,
        "replay_v3_passed": replay.passed,
        "verification_report": verification,
        "mechanism_outcome": mechanism,
        "exact_model_passed": exact_model,
        "fallback_absent": fallback_absent,
        "provider_native_tool_absent": native_absent,
        "thinking_continuity_passed": thinking,
        "provider_usage_complete": usage,
        "dynamic_precall_binding_passed": dynamic,
        "exact_request_binding_passed": exact_request,
        "privacy_artifact_pairing_passed": privacy_pairing,
        "reversible_commit_integrity_passed": reversible,
        "rollout_budget_passed": resource_passed,
        "rollout_headroom_tokens": (
            prepared.resource_contract.rollout_upper_bound_tokens - raw.cumulative_provider_tokens
        ),
        "instrument_failure": instrument,
        "privacy_gate_failure": privacy_gate_failure,
        "model_identity_thinking_or_usage_gate_failure": telemetry_gate_failure,
        "raw_execution_artifact": _descriptor(
            preflight._raw_path(output_dir, raw.job),  # noqa: SLF001
            output_dir,
        ),
    }
    provisional = QualificationJobResult.model_construct(result_id="pending", **values)
    return (
        QualificationJobResult(
            result_id=_identity(
                provisional,
                "result_id",
                "finance_v26_s1_qualification_job_result:",
            ),
            **values,
        ),
        diagnostics,
    )


def raw_lineage_audit(
    *,
    results: Sequence[QualificationJobResult],
    raw_by_job: Mapping[str, preflight.S1QualificationRawExecution],
    output_dir: Path,
) -> QualificationRawLineageAudit:
    files: list[legacy.RawFileDescriptor] = []
    envelope_ids: list[str] = []
    projection_ids: list[str] = []
    transport_ids: list[str] = []
    projection_counts: Counter[str] = Counter()
    private_reasoning_payload_count = 0
    invalid_payload_content_count = 0
    for result in results:
        raw = raw_by_job[result.job_id]
        raw_path = output_dir / result.raw_execution_artifact.relative_path
        replayed = preflight.S1QualificationRawExecution.model_validate(_load(raw_path))
        if (
            replayed.model_dump(mode="json") != raw.model_dump(mode="json")
            or _sha256(raw_path) != result.raw_execution_artifact.sha256
        ):
            raise ValueError(f"v26.134 Raw replay changed: {result.job_id}")
        files.append(_descriptor(raw_path, output_dir))
        pairs = _provider_pairs(raw, output_dir)
        for envelope, projection in pairs:
            envelope_ids.append(envelope.envelope_id)
            projection_ids.append(projection.projection_id)
            projection_counts[projection.projection_status] += 1
            if projection.response_payload is not None and legacy.contains_private_reasoning(
                projection.response_payload
            ):
                private_reasoning_payload_count += 1
            if (
                projection.projection_status != "validated_public_payload"
                and projection.response_payload is not None
            ):
                invalid_payload_content_count += 1
        for descriptor in (
            *raw.provider_envelope_artifacts,
            *raw.public_payload_projection_artifacts,
        ):
            path = output_dir / descriptor.relative_path
            if _sha256(path) != descriptor.sha256 or path.stat().st_size != descriptor.byte_count:
                raise ValueError("v26.134 privacy Artifact bytes changed")
            files.append(_descriptor(path, output_dir))
        for descriptor in raw.transport_invocation_artifacts:
            path = output_dir / descriptor.relative_path
            certificate = preflight.TransportInvocationCertificate.model_validate(_load(path))
            if _sha256(path) != descriptor.sha256 or path.stat().st_size != descriptor.byte_count:
                raise ValueError("v26.134 Transport certificate bytes changed")
            transport_ids.append(certificate.certificate_id)
            files.append(_descriptor(path, output_dir))
    ordered_files = tuple(sorted(files, key=lambda item: item.relative_path))
    values: dict[str, Any] = {
        "provider_call_count": sum(item.provider_call_count for item in results),
        "transport_inclusive_invocation_count": sum(
            item.transport_inclusive_invocation_count for item in results
        ),
        "provider_envelope_count": len(envelope_ids),
        "public_payload_projection_count": len(projection_ids),
        "complete_provider_pair_count": len(envelope_ids),
        "transport_invocation_certificate_count": len(transport_ids),
        "unique_provider_envelope_id_count": len(set(envelope_ids)),
        "unique_payload_projection_id_count": len(set(projection_ids)),
        "unique_transport_certificate_id_count": len(set(transport_ids)),
        "validated_public_payload_count": projection_counts["validated_public_payload"],
        "privacy_rejected_payload_count": projection_counts["privacy_rejected"],
        "provider_failure_no_payload_count": projection_counts["provider_failure_no_payload"],
        "file_count": len(ordered_files),
        "files": ordered_files,
        "exact_byte_replay_pass_count": len(ordered_files),
        "private_reasoning_payload_count": private_reasoning_payload_count,
        "invalid_payload_content_persistence_count": invalid_payload_content_count,
    }
    if len(set(envelope_ids)) != len(envelope_ids):
        raise ValueError("v26.134 duplicate Provider Envelope identity")
    if len(set(projection_ids)) != len(projection_ids):
        raise ValueError("v26.134 duplicate public Projection identity")
    if len(set(transport_ids)) != len(transport_ids):
        raise ValueError("v26.134 duplicate Transport certificate identity")
    provisional = QualificationRawLineageAudit.model_construct(audit_id="pending", **values)
    return QualificationRawLineageAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_s1_qualification_raw_lineage:",
        ),
        **values,
    )


def _cell_summaries(
    results: Sequence[QualificationJobResult],
) -> tuple[MechanismPathCellSummary, ...]:
    cells: list[MechanismPathCellSummary] = []
    grouped: dict[str, list[QualificationJobResult]] = {}
    for item in results:
        grouped.setdefault(item.mechanism_path_cell, []).append(item)
    for key in sorted(grouped):
        rows = grouped[key]
        mechanism_id, path_strategy_id = key.split("|", 1)
        values = {
            "mechanism_id": mechanism_id,
            "path_strategy_id": path_strategy_id,
            "job_count": len(rows),
            "first_action_interface_qualified_count": sum(
                item.first_action_interface_qualified for item in rows
            ),
            "terminal_counts": dict(
                sorted(Counter(item.terminal_category for item in rows).items())
            ),
        }
        provisional = MechanismPathCellSummary.model_construct(summary_id="pending", **values)
        cells.append(
            MechanismPathCellSummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_s1_qualification_cell_summary:",
                ),
                **values,
            )
        )
    return tuple(cells)


def make_execution_report(
    *,
    prepared: PreparedExecution,
    results: Sequence[QualificationJobResult],
    lineage: QualificationRawLineageAudit,
) -> QualificationExecutionReport:
    terminal_counts = Counter(item.terminal_category for item in results)
    cells = _cell_summaries(results)
    qualified_cells = sum(item.first_action_interface_qualified_count > 0 for item in cells)
    detour_distribution = {
        "0": sum(item.ordinary_detour_count == 0 for item in results),
        "1": sum(item.ordinary_detour_count == 1 for item in results),
        "2+": sum(item.ordinary_detour_count >= 2 for item in results),
    }
    privacy_failures = sum(item.privacy_gate_failure for item in results)
    model_failures = sum(not item.exact_model_passed for item in results)
    thinking_failures = sum(not item.thinking_continuity_passed for item in results)
    usage_failures = sum(not item.provider_usage_complete for item in results)
    combined_integrity = sum(
        item.instrument_failure
        or item.privacy_gate_failure
        or not item.exact_model_passed
        or not item.thinking_continuity_passed
        or not item.provider_usage_complete
        for item in results
    )
    first_qualified = sum(item.first_action_interface_qualified for item in results)
    gate_passed = bool(
        first_qualified >= prepared.qualification_contract.first_action_interface_minimum_jobs
        and qualified_cells == prepared.qualification_contract.required_mechanism_path_cell_coverage
        and combined_integrity == 0
    )
    cost = sum((Decimal(item.estimated_cost_usd) for item in results), Decimal("0"))
    values: dict[str, Any] = {
        "source_replay_audit_id": prepared.source_replay.audit_id,
        "preexecution_binding_audit_id": prepared.preexecution_binding.audit_id,
        "raw_lineage_audit_id": lineage.audit_id,
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "provider_call_count": sum(item.provider_call_count for item in results),
        "transport_inclusive_invocation_count": sum(
            item.transport_inclusive_invocation_count for item in results
        ),
        "provider_envelope_count": sum(item.provider_envelope_count for item in results),
        "public_payload_projection_count": sum(
            item.public_payload_projection_count for item in results
        ),
        "validated_public_payload_count": sum(
            item.validated_public_payload_count for item in results
        ),
        "privacy_rejected_payload_count": sum(
            item.privacy_rejected_payload_count for item in results
        ),
        "provider_failure_no_payload_count": sum(
            item.provider_failure_no_payload_count for item in results
        ),
        "http_success_call_count": sum(item.http_success_call_count for item in results),
        "provider_prompt_tokens": sum(item.provider_prompt_tokens for item in results),
        "provider_completion_tokens": sum(item.provider_completion_tokens for item in results),
        "provider_reasoning_tokens": sum(item.provider_reasoning_tokens for item in results),
        "provider_total_tokens": sum(item.provider_total_tokens for item in results),
        "estimated_cost_usd": format(cost, "f"),
        "maximum_prompt_utf8_bytes": max(
            (item.maximum_prompt_utf8_bytes for item in results), default=0
        ),
        "maximum_job_provider_tokens": max(
            (item.provider_total_tokens for item in results), default=0
        ),
        "provider_exposed_job_count": sum(
            item.transport_inclusive_invocation_count > 0 for item in results
        ),
        "all_persisted_calls_http_success_job_count": sum(
            item.provider_call_count > 0
            and item.http_success_call_count == item.provider_call_count
            for item in results
        ),
        "exact_model_pass_job_count": sum(item.exact_model_passed for item in results),
        "thinking_continuity_pass_job_count": sum(
            item.thinking_continuity_passed for item in results
        ),
        "provider_usage_complete_job_count": sum(item.provider_usage_complete for item in results),
        "exact_action_payload_job_count": sum(
            item.exact_four_field_action_payload_count > 0 for item in results
        ),
        "first_exact_action_abi_job_count": sum(item.first_exact_action_abi for item in results),
        "first_current_state_binding_job_count": sum(
            item.first_current_state_binding for item in results
        ),
        "first_visible_action_binding_job_count": sum(
            item.first_visible_action_binding for item in results
        ),
        "first_decision_kind_binding_job_count": sum(
            item.first_decision_kind_binding for item in results
        ),
        "first_reversible_commit_job_count": sum(
            item.first_reversible_same_action_commit for item in results
        ),
        "first_action_interface_qualified_job_count": first_qualified,
        "qualified_mechanism_path_cell_count": qualified_cells,
        "mechanism_path_cell_summaries": cells,
        "primary_request_count": sum(item.logical_primary_request_count for item in results),
        "abi_rescue_call_count": sum(item.abi_rescue_attempt_count for item in results),
        "semantic_recovery_call_count": sum(
            item.semantic_recovery_attempt_count for item in results
        ),
        "transport_replacement_invocation_count": sum(
            item.transport_replacement_attempt_count for item in results
        ),
        "no_abi_rescue_job_count": sum(item.abi_rescue_attempt_count == 0 for item in results),
        "abi_rescue_job_count": sum(item.abi_rescue_attempt_count > 0 for item in results),
        "semantic_recovery_job_count": sum(
            item.semantic_recovery_attempt_count > 0 for item in results
        ),
        "transport_replacement_job_count": sum(
            item.transport_replacement_attempt_count > 0 for item in results
        ),
        "exact_four_field_action_payload_count": sum(
            item.exact_four_field_action_payload_count for item in results
        ),
        "semantic_choice_count": sum(item.semantic_choice_count for item in results),
        "reversible_stage_two_commit_count": sum(
            item.reversible_stage_two_commit_count for item in results
        ),
        "public_observation_count": sum(item.public_observation_count for item in results),
        "successful_observation_count": sum(item.successful_observation_count for item in results),
        "failed_observation_count": sum(item.failed_observation_count for item in results),
        "progress_vector_change_count": sum(item.progress_vector_change_count for item in results),
        "reference_baseline_no_immediate_progress_count": sum(
            item.reference_baseline_no_immediate_progress_count for item in results
        ),
        "nonreference_ordinary_detour_event_count": sum(
            item.nonreference_ordinary_detour_event_count for item in results
        ),
        "diagnostic_state_change_outside_progress_vector_count": sum(
            item.diagnostic_state_change_outside_progress_vector_count for item in results
        ),
        "ordinary_detour_job_distribution": detour_distribution,
        "detour_measurement_support_exit_job_count": terminal_counts[
            "ordinary_detour_allowance_exhausted"
        ],
        "typed_semantic_rejection_job_count": terminal_counts["typed_semantic_rejection"],
        "typed_budget_no_call_job_count": terminal_counts["typed_budget_no_call"],
        "provider_transport_failure_job_count": terminal_counts["provider_transport_failure"],
        "instrument_failure_job_count": terminal_counts["instrument_failure"],
        "model_invalid_trajectory_count": terminal_counts["model_invalid_trajectory"],
        "program_closed_job_count": sum(item.program_closed for item in results),
        "terminal_node_completed_job_count": sum(item.terminal_node_completed for item in results),
        "postterminal_verification_completed_job_count": sum(
            item.postterminal_verification_completed for item in results
        ),
        "exact_final_abi_job_count": sum(item.final_abi_crossed for item in results),
        "final_answer_emitted_job_count": sum(item.final_answer_emitted for item in results),
        "final_answer_semantically_valid_job_count": sum(
            item.final_answer_semantically_valid for item in results
        ),
        "mechanism_success_job_count": sum(item.mechanism_success for item in results),
        "independently_valid_trajectory_count": sum(
            item.independent_trajectory_validity for item in results
        ),
        "privacy_gate_failure_job_count": privacy_failures,
        "model_identity_failure_job_count": model_failures,
        "thinking_failure_job_count": thinking_failures,
        "usage_failure_job_count": usage_failures,
        "combined_integrity_gate_failure_job_count": combined_integrity,
        "representation_qualification_gate_passed": gate_passed,
        "execution_status": (
            "qualification_gate_passed_pending_independent_audit"
            if gate_passed
            else "qualification_gate_failed_pending_independent_audit"
        ),
    }
    provisional = QualificationExecutionReport.model_construct(report_id="pending", **values)
    return QualificationExecutionReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_s1_qualification_execution_report:",
        ),
        **values,
    )


def _load_checkpoint(
    path: Path,
    *,
    prepared: PreparedExecution,
    output_dir: Path,
) -> tuple[QualificationJobResult, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        QualificationJobResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in prepared.manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("v26.134 checkpoint contains duplicate Jobs")
    for result in rows:
        job = jobs.get(result.job_id)
        if job is None or result.runner_contract_id != prepared.runner_contract.contract_id:
            raise ValueError("v26.134 checkpoint crosses the frozen denominator")
        raw_path = preflight._raw_path(output_dir, job)  # noqa: SLF001
        if not raw_path.is_file() or _sha256(raw_path) != result.raw_execution_artifact.sha256:
            raise ValueError("v26.134 checkpoint Raw binding changed")
    return rows


ClientFactory = Callable[[AgentModelConfig, preflight.S1QualificationJob, Any], Any]


def _default_client_factory(
    config: AgentModelConfig,
    _job: preflight.S1QualificationJob,
    _binding: Any,
) -> Any:
    return StageOneProspectiveThinkingJsonClient(config)


def _run_one_job(
    *,
    job: preflight.S1QualificationJob,
    prepared: PreparedExecution,
    client_factory: ClientFactory | None,
    output_dir: Path,
) -> tuple[
    QualificationJobResult,
    preflight.S1QualificationRawExecution,
    tuple[semantic_online.ChoiceDiagnostic, ...],
]:
    old_job, binding = preflight._job_context(prepared.loaded, job)  # noqa: SLF001
    client = (
        None
        if client_factory is None
        else client_factory(prepared.loaded.engineering.agent_model_config, job, binding)
    )
    raw = preflight.execute_s1_qualification_job_raw(
        job=job,
        old_job=old_job,
        runner_contract=prepared.runner_contract,
        resource_contract=prepared.resource_contract,
        static=prepared.loaded.engineering,
        binding=binding,
        client=client,
        output_dir=output_dir,
    )
    result, diagnostics = project_job_result(
        raw=raw,
        prepared=prepared,
        binding=binding,
        output_dir=output_dir,
    )
    return result, raw, diagnostics


def _write_checkpoint(path: Path, rows: Sequence[QualificationJobResult]) -> None:
    payload = b"\n".join(_canonical_bytes(item.model_dump(mode="json")) for item in rows)
    if payload:
        payload += b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _assert_no_orphan_artifacts(
    output_dir: Path,
    job: preflight.S1QualificationJob,
) -> None:
    envelope_dir = privacy_runner.provider_envelope_path(output_dir, cast(Any, job), 0).parent
    projection_dir = privacy_runner.payload_projection_path(output_dir, cast(Any, job), 0).parent
    invocation_dir = preflight._invocation_path(output_dir, job, 0).parent  # noqa: SLF001
    counts = (
        len(tuple(envelope_dir.glob("call_*.json"))) if envelope_dir.exists() else 0,
        len(tuple(projection_dir.glob("call_*.json"))) if projection_dir.exists() else 0,
        len(tuple(invocation_dir.glob("invocation_*.json"))) if invocation_dir.exists() else 0,
    )
    if any(counts):
        raise ValueError(
            "orphan v26.134 Artifacts forbid retry: "
            f"job={job.job_id} envelopes={counts[0]} projections={counts[1]} "
            f"invocations={counts[2]}"
        )


def run_s1_representation_qualification(
    *,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
    workers: int,
    client_factory: ClientFactory = _default_client_factory,
) -> QualificationExecutionReport:
    prepared = prepare_execution(
        preflight_dir=preflight_dir,
        output_dir=output_dir,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    checkpoint_path = output_dir / "s1_qualification_job_results.checkpoint.jsonl"
    existing = _load_checkpoint(
        checkpoint_path,
        prepared=prepared,
        output_dir=output_dir,
    )
    completed = {item.job_id: item for item in existing}
    jobs = prepared.manifest.jobs
    pending = [item for item in jobs if item.job_id not in completed]
    report_path = output_dir / "report.json"
    if pending and report_path.exists():
        raise ValueError("v26.134 completed report exists while Jobs remain pending")
    if not pending and report_path.exists():
        report = QualificationExecutionReport.model_validate(_load(report_path))
        if (
            report.runner_contract_id != prepared.runner_contract.contract_id
            or report.source_replay_audit_id != prepared.source_replay.audit_id
        ):
            raise ValueError("v26.134 completed report crosses frozen bindings")
        return report
    raw_recovery_jobs = [
        item
        for item in pending
        if preflight._raw_path(output_dir, item).exists()  # noqa: SLF001
    ]
    model_pending_jobs = [
        item
        for item in pending
        if not preflight._raw_path(output_dir, item).exists()  # noqa: SLF001
    ]
    for job in model_pending_jobs:
        _assert_no_orphan_artifacts(output_dir, job)
    print(
        f"[v26.134] resuming {len(completed)}/32; "
        f"raw-only recovery {len(raw_recovery_jobs)}; "
        f"executing {len(model_pending_jobs)} Jobs with {workers} workers",
        flush=True,
    )
    raw_by_job: dict[str, preflight.S1QualificationRawExecution] = {}
    diagnostics_by_job: dict[str, tuple[semantic_online.ChoiceDiagnostic, ...]] = {}
    for job in jobs:
        raw_path = preflight._raw_path(output_dir, job)  # noqa: SLF001
        if raw_path.exists() and job.job_id in completed:
            raw = preflight.S1QualificationRawExecution.model_validate(_load(raw_path))
            _, binding = preflight._job_context(prepared.loaded, job)  # noqa: SLF001
            raw_by_job[job.job_id] = raw
            diagnostics_by_job[job.job_id] = _choice_diagnostics(
                raw=raw,
                prepared=prepared,
                binding=binding,
            )
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending) or 1))) as executor:
        future_map = {
            executor.submit(
                _run_one_job,
                job=job,
                prepared=prepared,
                client_factory=(None if job in raw_recovery_jobs else client_factory),
                output_dir=output_dir,
            ): job
            for job in pending
        }
        for future in as_completed(future_map):
            job = future_map[future]
            result, raw, diagnostics = future.result()
            with lock:
                completed[job.job_id] = result
                raw_by_job[job.job_id] = raw
                diagnostics_by_job[job.job_id] = diagnostics
                ordered = tuple(completed[item.job_id] for item in jobs if item.job_id in completed)
                _write_checkpoint(checkpoint_path, ordered)
                print(
                    f"[v26.134] completed {len(completed)}/32 "
                    f"{job.job_id.rsplit(':', 1)[-1][:12]} "
                    f"terminal={result.terminal_category} "
                    f"entry={result.first_action_interface_qualified} "
                    f"detours={result.ordinary_detour_count} "
                    f"calls={result.provider_call_count}",
                    flush=True,
                )
    results = tuple(completed[item.job_id] for item in jobs)
    if len(results) != 32:
        raise ValueError("v26.134 execution denominator is incomplete")
    for job in jobs:
        raw_by_job.setdefault(
            job.job_id,
            preflight.S1QualificationRawExecution.model_validate(
                _load(preflight._raw_path(output_dir, job))  # noqa: SLF001
            ),
        )
        if job.job_id not in diagnostics_by_job:
            _, binding = preflight._job_context(prepared.loaded, job)  # noqa: SLF001
            diagnostics_by_job[job.job_id] = _choice_diagnostics(
                raw=raw_by_job[job.job_id],
                prepared=prepared,
                binding=binding,
            )
    diagnostics = tuple(item for job in jobs for item in diagnostics_by_job[job.job_id])
    lineage = raw_lineage_audit(
        results=results,
        raw_by_job=raw_by_job,
        output_dir=output_dir,
    )
    report = make_execution_report(
        prepared=prepared,
        results=results,
        lineage=lineage,
    )
    _write_json_atomic(
        output_dir / "s1_qualification_job_results.json",
        [item.model_dump(mode="json") for item in results],
    )
    _write_json_atomic(
        output_dir / "s1_qualification_choice_diagnostics.json",
        [item.model_dump(mode="json") for item in diagnostics],
    )
    _write_json_atomic(output_dir / "raw_lineage_audit.json", lineage)
    _write_json_atomic(report_path, report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Run the exact v26.134 S1 model-visible representation qualification"
    )
    parser.add_argument(
        "--preflight-dir",
        type=Path,
        default=package_default / PREFLIGHT_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / OUTPUT_DIR,
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only:
        prepared = prepare_execution(
            preflight_dir=args.preflight_dir,
            output_dir=args.output_dir,
            package_root=args.package_root,
            implementation_root=args.implementation_root,
        )
        print(
            json.dumps(
                {
                    "status": "prepared",
                    "source_replay_audit_id": prepared.source_replay.audit_id,
                    "preexecution_binding_audit_id": (prepared.preexecution_binding.audit_id),
                    "manifest_id": prepared.manifest.manifest_id,
                    "runner_contract_id": prepared.runner_contract.contract_id,
                    "outcome_contract_id": prepared.outcome_contract.contract_id,
                    "expected_jobs": len(prepared.manifest.jobs),
                    "role_source_jobs": prepared.manifest.role_source_job_count,
                    "model_client_constructed": False,
                    "provider_calls": 0,
                    "stage_two_provider_calls": 0,
                },
                indent=2,
            )
        )
        return
    report = run_s1_representation_qualification(
        preflight_dir=args.preflight_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
