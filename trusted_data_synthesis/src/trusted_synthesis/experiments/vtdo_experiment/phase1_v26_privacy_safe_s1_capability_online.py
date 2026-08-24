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
    phase1_v26_privacy_safe_s1_capability_preflight as preflight,
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
    "artifacts/vtdo_experiment/finance_v26_141_privacy_safe_s1_capability_execution_v1_20260824"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_privacy_safe_s1_capability_online.py"
)
POSTRUN_STAGE: Final = "privacy_safe_s1_capability_postrun_audit_only"

EXPECTED_PREFLIGHT_REPORT_ID: Final = (
    "finance_v26_privacy_safe_capability_preflight_report:"
    "9e74e45831e0c8db50dc5969f680f81732b1ad71d9edd771fcfd40c496bce1f4"
)
EXPECTED_PREFLIGHT_REPORT_SHA256: Final = (
    "52ecfa99813fc40953ca35f7617a2c7c2576b24512b6e4505add3ad2c1845662"
)
EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID: Final = (
    "finance_v26_privacy_safe_capability_source_replay:"
    "1c996f701cc0d2d47fe91df08379d0c36cf72810ac33d4a341b7d3bd823d417e"
)
EXPECTED_TASK_CATALOG_ID: Final = (
    "finance_v26_privacy_safe_capability_task_catalog:"
    "8ed09b94a9d5adbbc53481698def5fbc9cffc4d9969598c2409919ddd306cb82"
)
EXPECTED_PATH_CATALOG_ID: Final = (
    "finance_v26_privacy_safe_capability_path_catalog:"
    "eae754107fb5dda4b61e9236aeabd191b1a129a2c91df52023bce44745e6f0a7"
)
EXPECTED_NONINTERFERENCE_AUDIT_ID: Final = (
    "finance_v26_capability_prompt_noninterference:"
    "be222696fc6a7fa3b2a62065fd7e55020f175e8405db1e163d5f706ec1a896d8"
)
EXPECTED_RESOURCE_CONTRACT_ID: Final = (
    "finance_v26_privacy_safe_capability_resource_binding:"
    "feea459730aa7a41a699106b7cb78a1d2958130e8f2b17bde56e9f98b566a362"
)
EXPECTED_EXECUTION_CONTRACT_ID: Final = (
    "finance_v26_privacy_safe_capability_execution_contract:"
    "e0d40a58cdf970c5842a65a8808147fee5494f46857d4f4f121f1b7b2d44cc10"
)
EXPECTED_MANIFEST_ID: Final = (
    "finance_v26_privacy_safe_capability_manifest:"
    "971a74faf28d07402aa90a31ec202644f617410e4a49ec7f25e5a265458b1301"
)
EXPECTED_OUTCOME_CONTRACT_ID: Final = (
    "finance_v26_privacy_safe_capability_outcome_contract:"
    "a9cfe6d9fe21c26652fb01b75655aa119f50a992d40a93620db5832512d86162"
)
EXPECTED_RUNNER_CONTRACT_ID: Final = (
    "finance_v26_privacy_safe_capability_runner_contract:"
    "e080bd0622b653e73b67a834aefe8b10f54ecf06e95334d574038c21d88ca35d"
)
EXPECTED_TRANSITION_ID: Final = (
    "finance_v26_privacy_safe_capability_transition:"
    "66039fa2eb1b50a3966f259b33c1a6512edf871d3c23f6a53d774b66a20dea89"
)
EXPECTED_TRANSITION_SHA256: Final = (
    "ab75bf3856261c9657cdc4667d097eaa4c53058423071cf1d8f0ba45bb9870b2"
)
EXPECTED_PROSPECTIVE_EXECUTION_ID: Final = (
    "finance_v26_privacy_safe_s1_capability_execution:"
    "d1925103511060775b84b546c2d149926602b6eef249c50e3e57a1bc526f9c4a"
)
EXPECTED_PROSPECTIVE_REPORT_ID: Final = (
    "finance_v26_privacy_safe_s1_capability_execution_report:"
    "325ebb2f2d8fc0d982c5ca53f1f0ffea4501f7a41fc302fa9e8866e2ed57fb7d"
)

PREFLIGHT_OUTPUTS: Final = (
    "capability_dynamic_envelope_audit.json",
    "capability_execution_contract.json",
    "capability_outcome_contract.json",
    "capability_path_catalog.json",
    "capability_prompt_noninterference_audit.json",
    "capability_resource_binding.json",
    "capability_runner_contract.json",
    "capability_runner_control_audit.json",
    "capability_runner_fixture_audit.json",
    "capability_task_package_catalog.json",
    "destructive_audit.json",
    "frozen_capability_input_audit.json",
    "predecessor_integrity_audit.json",
    "privacy_safe_capability_manifest.json",
    "prospective_transition_contract.json",
    "report.json",
    "source_replay_audit.json",
)

CapabilityTerminalCategory = Literal[
    "model_valid_trajectory",
    "model_invalid_trajectory",
    "privacy_rejection",
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
        "v26_140_transitive_source",
        "v26_140_output",
        "v26_141_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class ExecutionSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    predecessor_source_replay_id: str = EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
    predecessor_transitive_file_count: Literal[4535] = 4535
    predecessor_output_file_count: Literal[17] = 17
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[4553] = 4553
    replay_pass_count: Literal[4553] = 4553
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=4553, max_length=4553)
    replay_before_profile_parsing: Literal[True] = True
    replay_before_credential_lookup: Literal[True] = True
    replay_before_client_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_capability_execution_source_replay.v1"] = (
        "finance_v26_capability_execution_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.replayed_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.141 source replay changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_privacy_safe_capability_execution_source_replay:",
        ):
            raise ValueError("v26.141 source replay identity changed")
        return self


class PreexecutionBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    outcome_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    rebuilt_preflight_output_count: Literal[17] = 17
    byte_identical_preflight_output_count: Literal[17] = 17
    exact_job_count: Literal[96] = 96
    distinct_capability_task_count: Literal[12] = 12
    mechanism_tier_cell_count: Literal[12] = 12
    scripted_fixture_job_count: Literal[96] = 96
    scripted_fixture_call_count: Literal[984] = 984
    scripted_first_action_qualified_count: Literal[96] = 96
    reachability_identity_count: Literal[0] = 0
    reachability_job_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    real_model_client_constructed: Literal[False] = False
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    operator_authorized_replacement_rerun: Literal[True] = True
    prior_attempt_artifacts_available: Literal[False] = False
    prior_attempt_auditable_job_count: Literal[0] = 0
    prior_attempt_pooled_job_count: Literal[0] = 0
    pristine_first_exposure_claimed: Literal[False] = False
    exact_v26_140_manifest_reused: Literal[True] = True
    durable_canonical_output_root_required: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_capability_execution_preexecution_binding.v1"] = (
        "finance_v26_capability_execution_preexecution_binding.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PreexecutionBindingAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_privacy_safe_capability_execution_preexecution_binding:",
        ):
            raise ValueError("v26.141 preexecution binding identity changed")
        return self


class CapabilityJobResult(FrozenModel):
    result_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    outcome_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    job_id: str = Field(min_length=1)
    predecessor_job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    tier: Literal["easy_control", "frontier", "hard_control"]
    replicate_index: int = Field(ge=0, lt=8)
    seed: int = Field(ge=0)
    terminal_category: CapabilityTerminalCategory
    raw_terminal_disposition: preflight.CapabilityTerminal
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
    raw_execution_artifact: legacy.RawFileDescriptor

    role: Literal["capability"] = "capability"
    task_is_primary_sampling_unit: Literal[True] = True
    rollout_is_secondary_repeated_measure: Literal[True] = True
    reachability_state_mapping_eligible: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_safe_capability_job_result.v1"] = (
        "finance_v26_privacy_safe_capability_job_result.v1"
    )

    @model_validator(mode="after")
    def validate_result(self) -> CapabilityJobResult:
        if self.provider_reasoning_tokens > self.provider_completion_tokens:
            raise ValueError("v26.141 Reasoning Usage exceeds Completion Usage")
        if self.provider_call_count != (
            self.validated_public_payload_count
            + self.privacy_rejected_payload_count
            + self.provider_failure_no_payload_count
        ):
            raise ValueError("v26.141 public Projection partition changed")
        if (
            self.provider_envelope_count != self.provider_call_count
            or self.public_payload_projection_count != self.provider_call_count
        ):
            raise ValueError("v26.141 privacy-first Provider denominator changed")
        expected_first = bool(
            self.first_exact_action_abi
            and self.first_current_state_binding
            and self.first_visible_action_binding
            and self.first_decision_kind_binding
            and self.first_reversible_same_action_commit
        )
        if self.first_action_interface_qualified != expected_first:
            raise ValueError("v26.141 first-action qualification changed")
        if self.final_abi_crossed != bool(self.exact_two_field_final_payload_count):
            raise ValueError("v26.141 Final ABI accounting changed")
        if self.final_answer_semantically_valid and not self.final_answer_emitted:
            raise ValueError("v26.141 semantic validity lacks a Final answer")
        if self.detour_measurement_support_exit != (
            self.terminal_category == "ordinary_detour_allowance_exhausted"
        ):
            raise ValueError("v26.141 Detour support-exit classification changed")
        if self.detour_measurement_support_exit and self.independent_trajectory_validity:
            raise ValueError("v26.141 Detour support exit became a valid result")
        if self.independent_trajectory_validity != (
            self.terminal_category == "model_valid_trajectory"
        ):
            raise ValueError("v26.141 independent-validity terminal changed")
        if self.result_id != _identity(
            self,
            "result_id",
            "finance_v26_privacy_safe_capability_job_result:",
        ):
            raise ValueError("v26.141 Job-result identity changed")
        return self


class CapabilityCandidatePresentationRow(FrozenModel):
    action_id: str = Field(min_length=1)
    zero_based_position: int = Field(ge=0, le=62)
    description_utf8_bytes: int = Field(gt=0)
    candidate_family: str = Field(min_length=1)
    prompt_only_reference: bool
    selected_by_model: bool


class CapabilityChoiceDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0, le=20)
    choice_phase: Literal["primary", "semantic_recovery"]
    response_attempt_phase: Literal["primary", "abi_rescue", "semantic_recovery"]
    public_state_id: str = Field(min_length=1)
    candidate_count: int = Field(ge=1, le=63)
    decision_load_natural_log: float = Field(ge=0.0)
    candidates: tuple[CapabilityCandidatePresentationRow, ...] = Field(min_length=1, max_length=63)
    selected_action_id: str = Field(min_length=1)
    selected_zero_based_position: int | None = Field(default=None, ge=0, le=62)
    selected_description_utf8_bytes: int | None = Field(default=None, gt=0)
    selected_candidate_family: str | None = Field(default=None, min_length=1)
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
    schema_version: Literal["finance_v26_privacy_safe_capability_choice_diagnostic.v1"] = (
        "finance_v26_privacy_safe_capability_choice_diagnostic.v1"
    )

    @model_validator(mode="after")
    def validate_diagnostic(self) -> CapabilityChoiceDiagnostic:
        if (
            self.candidate_count != len(self.candidates)
            or tuple(item.zero_based_position for item in self.candidates)
            != tuple(range(self.candidate_count))
            or sum(item.selected_by_model for item in self.candidates)
            != int(self.visible_action_id_match)
            or sum(item.prompt_only_reference for item in self.candidates) != 1
        ):
            raise ValueError("v26.141 Candidate presentation denominator changed")
        selected = (
            self.candidates[self.selected_zero_based_position]
            if self.selected_zero_based_position is not None
            else None
        )
        if self.visible_action_id_match and (
            selected is None
            or selected.action_id != self.selected_action_id
            or selected.description_utf8_bytes != self.selected_description_utf8_bytes
            or selected.candidate_family != self.selected_candidate_family
            or selected.prompt_only_reference != self.selected_prompt_only_reference
            or not selected.selected_by_model
        ):
            raise ValueError("v26.141 selected Candidate diagnostic changed")
        if not self.visible_action_id_match and any(
            value is not None
            for value in (
                self.selected_zero_based_position,
                self.selected_description_utf8_bytes,
                self.selected_candidate_family,
                self.selected_prompt_only_reference,
            )
        ):
            raise ValueError("v26.141 invisible action acquired Candidate metadata")
        if self.program_node_progress != (
            self.completed_program_nodes_after > self.completed_program_nodes_before
        ):
            raise ValueError("v26.141 Program-node progress accounting changed")
        if self.diagnostic_id != _identity(
            self,
            "diagnostic_id",
            "finance_v26_privacy_safe_capability_choice_diagnostic:",
        ):
            raise ValueError("v26.141 Choice-diagnostic identity changed")
        return self


class TaskCapabilitySummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    tier: Literal["easy_control", "frontier", "hard_control"]
    job_count: Literal[8] = 8
    instrument_eligible_count: int = Field(ge=0, le=8)
    privacy_compliant_count: int = Field(ge=0, le=8)
    action_entry_count: int = Field(ge=0, le=8)
    reversible_commit_count: int = Field(ge=0, le=8)
    public_progress_count: int = Field(ge=0, le=8)
    program_closure_count: int = Field(ge=0, le=8)
    terminal_verification_count: int = Field(ge=0, le=8)
    exact_final_abi_count: int = Field(ge=0, le=8)
    independently_valid_count: int = Field(ge=0, le=8)
    support_exit_count: int = Field(ge=0, le=8)
    instrument_failure_count: int = Field(ge=0, le=8)
    privacy_rejection_count: int = Field(ge=0, le=8)
    provider_transport_failure_count: int = Field(ge=0, le=8)
    typed_budget_no_call_count: int = Field(ge=0, le=8)
    valid_fraction: str = Field(min_length=1)
    terminal_counts: dict[str, int]

    @model_validator(mode="after")
    def validate_summary(self) -> TaskCapabilitySummary:
        if sum(self.terminal_counts.values()) != self.job_count:
            raise ValueError("v26.141 Task terminal denominator changed")
        if self.summary_id != _identity(
            self, "summary_id", "finance_v26_privacy_safe_capability_task_summary:"
        ):
            raise ValueError("v26.141 Task summary identity changed")
        return self


class GroupCapabilitySummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    group_kind: Literal["mechanism", "tier"]
    group_value: str = Field(min_length=1)
    task_count: int = Field(gt=0)
    job_count: int = Field(gt=0)
    tasks_with_independently_valid_trajectory: int = Field(ge=0)
    independently_valid_count: int = Field(ge=0)
    action_entry_count: int = Field(ge=0)
    program_closure_count: int = Field(ge=0)
    exact_final_abi_count: int = Field(ge=0)
    support_exit_count: int = Field(ge=0)
    nonmodel_failure_count: int = Field(ge=0)
    terminal_counts: dict[str, int]

    @model_validator(mode="after")
    def validate_summary(self) -> GroupCapabilitySummary:
        if (
            sum(self.terminal_counts.values()) != self.job_count
            or self.tasks_with_independently_valid_trajectory > self.task_count
        ):
            raise ValueError("v26.141 Group summary denominator changed")
        if self.summary_id != _identity(
            self, "summary_id", "finance_v26_privacy_safe_capability_group_summary:"
        ):
            raise ValueError("v26.141 Group summary identity changed")
        return self


class MechanismTierCellSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    tier: Literal["easy_control", "frontier", "hard_control"]
    task_package_id: str = Field(min_length=1)
    job_count: Literal[8] = 8
    action_entry_count: int = Field(ge=0, le=8)
    program_closure_count: int = Field(ge=0, le=8)
    exact_final_abi_count: int = Field(ge=0, le=8)
    independently_valid_count: int = Field(ge=0, le=8)
    terminal_counts: dict[str, int]

    @model_validator(mode="after")
    def validate_summary(self) -> MechanismTierCellSummary:
        if sum(self.terminal_counts.values()) != self.job_count:
            raise ValueError("v26.141 Mechanism x Tier denominator changed")
        if self.summary_id != _identity(
            self, "summary_id", "finance_v26_privacy_safe_capability_cell_summary:"
        ):
            raise ValueError("v26.141 Mechanism x Tier summary identity changed")
        return self


class CapabilityRawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    job_result_count: Literal[96] = 96
    raw_execution_count: Literal[96] = 96
    provider_call_count: int = Field(ge=0, le=2208)
    transport_inclusive_invocation_count: int = Field(ge=0, le=2304)
    provider_envelope_count: int = Field(ge=0, le=2208)
    public_payload_projection_count: int = Field(ge=0, le=2208)
    complete_provider_pair_count: int = Field(ge=0, le=2208)
    transport_invocation_certificate_count: int = Field(ge=0, le=2304)
    unique_provider_envelope_id_count: int = Field(ge=0, le=2208)
    unique_payload_projection_id_count: int = Field(ge=0, le=2208)
    unique_transport_certificate_id_count: int = Field(ge=0, le=2304)
    validated_public_payload_count: int = Field(ge=0, le=2208)
    privacy_rejected_payload_count: int = Field(ge=0, le=2208)
    provider_failure_no_payload_count: int = Field(ge=0, le=2208)
    complete_raw_count: Literal[96] = 96
    file_count: int = Field(ge=96)
    files: tuple[legacy.RawFileDescriptor, ...] = Field(min_length=96)
    exact_byte_replay_pass_count: int = Field(ge=96)
    private_reasoning_payload_count: Literal[0] = 0
    invalid_payload_content_persistence_count: Literal[0] = 0
    raw_http_body_persistence_count: Literal[0] = 0
    raw_request_body_persistence_count: Literal[0] = 0
    capability_job_count: Literal[96] = 96
    reachability_job_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_privacy_safe_capability_raw_lineage.v1"] = (
        "finance_v26_privacy_safe_capability_raw_lineage.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CapabilityRawLineageAudit:
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
            raise ValueError("v26.141 Raw Lineage denominator changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_safe_capability_raw_lineage:"
        ):
            raise ValueError("v26.141 Raw Lineage identity changed")
        return self


class CapabilityExecutionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    preexecution_binding_audit_id: str = Field(min_length=1)
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    outcome_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    raw_lineage_audit_id: str = Field(min_length=1)
    task_catalog_id: str = EXPECTED_TASK_CATALOG_ID
    path_catalog_id: str = EXPECTED_PATH_CATALOG_ID
    noninterference_audit_id: str = EXPECTED_NONINTERFERENCE_AUDIT_ID
    preflight_prospective_execution_id: str = EXPECTED_PROSPECTIVE_EXECUTION_ID
    preflight_prospective_report_id: str = EXPECTED_PROSPECTIVE_REPORT_ID
    prompt_protocol: Literal["prospective_role_scalable_semantic_action_prompt.v2"] = (
        "prospective_role_scalable_semantic_action_prompt.v2"
    )
    exact_job_denominator: Literal[96] = 96
    distinct_task_count: Literal[12] = 12
    rollouts_per_task: Literal[8] = 8
    completed_job_result_count: Literal[96] = 96
    complete_raw_execution_count: Literal[96] = 96
    terminal_counts: dict[str, int]

    provider_call_count: int = Field(ge=0, le=2208)
    transport_inclusive_invocation_count: int = Field(ge=0, le=2304)
    provider_envelope_count: int = Field(ge=0, le=2208)
    public_payload_projection_count: int = Field(ge=0, le=2208)
    validated_public_payload_count: int = Field(ge=0, le=2208)
    privacy_rejected_payload_count: int = Field(ge=0, le=2208)
    provider_failure_no_payload_count: int = Field(ge=0, le=2208)
    http_success_call_count: int = Field(ge=0, le=2208)
    provider_prompt_tokens: int = Field(ge=0)
    provider_completion_tokens: int = Field(ge=0)
    provider_reasoning_tokens: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    estimated_cost_usd: str = Field(min_length=1)
    maximum_prompt_utf8_bytes: int = Field(ge=0, le=60000)
    maximum_job_provider_tokens: int = Field(ge=0, le=1120000)

    instrument_eligible_job_count: int = Field(ge=0, le=96)
    privacy_compliant_job_count: int = Field(ge=0, le=96)
    action_entry_job_count: int = Field(ge=0, le=96)
    reversible_commit_job_count: int = Field(ge=0, le=96)
    public_progress_job_count: int = Field(ge=0, le=96)
    program_closed_job_count: int = Field(ge=0, le=96)
    terminal_node_completed_job_count: int = Field(ge=0, le=96)
    postterminal_verification_completed_job_count: int = Field(ge=0, le=96)
    exact_final_abi_job_count: int = Field(ge=0, le=96)
    final_answer_emitted_job_count: int = Field(ge=0, le=96)
    final_answer_semantically_valid_job_count: int = Field(ge=0, le=96)
    mechanism_success_job_count: int = Field(ge=0, le=96)
    independently_valid_trajectory_count: int = Field(ge=0, le=96)

    provider_exposed_job_count: int = Field(ge=0, le=96)
    all_persisted_calls_http_success_job_count: int = Field(ge=0, le=96)
    exact_model_pass_job_count: int = Field(ge=0, le=96)
    thinking_continuity_pass_job_count: int = Field(ge=0, le=96)
    provider_usage_complete_job_count: int = Field(ge=0, le=96)
    first_exact_action_abi_job_count: int = Field(ge=0, le=96)
    first_current_state_binding_job_count: int = Field(ge=0, le=96)
    first_visible_action_binding_job_count: int = Field(ge=0, le=96)
    first_decision_kind_binding_job_count: int = Field(ge=0, le=96)
    first_reversible_commit_job_count: int = Field(ge=0, le=96)

    primary_request_count: int = Field(ge=0, le=2016)
    abi_rescue_call_count: int = Field(ge=0, le=96)
    semantic_recovery_call_count: int = Field(ge=0, le=96)
    transport_replacement_invocation_count: int = Field(ge=0, le=96)
    abi_rescue_job_count: int = Field(ge=0, le=96)
    semantic_recovery_job_count: int = Field(ge=0, le=96)
    transport_replacement_job_count: int = Field(ge=0, le=96)
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

    task_summaries: tuple[TaskCapabilitySummary, ...] = Field(min_length=12, max_length=12)
    mechanism_summaries: tuple[GroupCapabilitySummary, ...] = Field(min_length=4, max_length=4)
    tier_summaries: tuple[GroupCapabilitySummary, ...] = Field(min_length=3, max_length=3)
    mechanism_tier_cell_summaries: tuple[MechanismTierCellSummary, ...] = Field(
        min_length=12, max_length=12
    )
    mechanisms_with_independently_valid_trajectory: int = Field(ge=0, le=4)
    tasks_with_independently_valid_trajectory: int = Field(ge=0, le=12)
    task_weighted_valid_fraction: str = Field(min_length=1)

    detour_measurement_support_exit_job_count: int = Field(ge=0, le=96)
    typed_semantic_rejection_job_count: int = Field(ge=0, le=96)
    typed_budget_no_call_job_count: int = Field(ge=0, le=96)
    provider_transport_failure_job_count: int = Field(ge=0, le=96)
    privacy_rejection_job_count: int = Field(ge=0, le=96)
    instrument_failure_job_count: int = Field(ge=0, le=96)
    model_invalid_trajectory_count: int = Field(ge=0, le=96)
    model_identity_failure_job_count: int = Field(ge=0, le=96)
    thinking_failure_job_count: int = Field(ge=0, le=96)
    usage_failure_job_count: int = Field(ge=0, le=96)
    combined_integrity_gate_failure_job_count: int = Field(ge=0, le=96)
    combined_support_boundary_failure_job_count: int = Field(ge=0, le=96)

    minimum_mechanisms_with_valid_trajectory_for_successor_preflight: Literal[4] = 4
    capability_successor_preflight_gate_passed: bool
    stage_two_provider_call_count: Literal[0] = 0
    reachability_identity_count: Literal[0] = 0
    reachability_job_count: Literal[0] = 0
    reachability_execution_count: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    training_rows: Literal[0] = 0
    release_rows: Literal[0] = 0
    production_contribution: Literal[0] = 0
    classifier_sensitive_action_prompt_key_count: Literal[0] = 0
    historical_engineering_result_pooled_count: Literal[0] = 0
    prior_lost_attempt_artifact_count: Literal[0] = 0
    prior_lost_attempt_auditable_job_count: Literal[0] = 0
    prior_lost_attempt_pooled_job_count: Literal[0] = 0
    operator_authorized_replacement_rerun: Literal[True] = True
    pristine_first_exposure_claimed: Literal[False] = False
    exact_v26_140_manifest_reused: Literal[True] = True
    host_repair_count: Literal[0] = 0
    task_is_primary_sampling_unit: Literal[True] = True
    rollout_is_secondary_repeated_measure: Literal[True] = True
    mechanism_tier_cell_is_single_task_diagnostic: Literal[True] = True
    capability_pass_does_not_authorize_reachability_execution: Literal[True] = True
    pass_requires_independent_postrun_audit: Literal[True] = True
    detour_support_exit_counts_as_model_invalid: Literal[False] = False
    final_abi_and_answer_validity_reported_separately: Literal[True] = True
    measured_object: Literal[
        "independently_valid_complete_trajectory_on_fresh_capability_tasks"
    ] = "independently_valid_complete_trajectory_on_fresh_capability_tasks"
    execution_status: Literal[
        "capability_successor_preflight_gate_passed_pending_independent_audit",
        "capability_successor_preflight_gate_failed_pending_independent_audit",
    ]
    next_permitted_stage: Literal["privacy_safe_s1_capability_postrun_audit_only"] = POSTRUN_STAGE
    schema_version: Literal["finance_v26_privacy_safe_capability_execution_report.v1"] = (
        "finance_v26_privacy_safe_capability_execution_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> CapabilityExecutionReport:
        if (
            sum(self.terminal_counts.values()) != self.exact_job_denominator
            or sum(self.ordinary_detour_job_distribution.values()) != self.exact_job_denominator
        ):
            raise ValueError("v26.141 Job denominator changed")
        if self.provider_call_count != (
            self.validated_public_payload_count
            + self.privacy_rejected_payload_count
            + self.provider_failure_no_payload_count
        ):
            raise ValueError("v26.141 aggregate Projection partition changed")
        if (
            self.provider_call_count != self.provider_envelope_count
            or self.provider_call_count != self.public_payload_projection_count
        ):
            raise ValueError("v26.141 aggregate privacy-first denominator changed")
        expected_gate = bool(
            self.complete_raw_execution_count == self.exact_job_denominator
            and self.mechanisms_with_independently_valid_trajectory
            >= self.minimum_mechanisms_with_valid_trajectory_for_successor_preflight
            and self.combined_integrity_gate_failure_job_count == 0
            and self.combined_support_boundary_failure_job_count == 0
        )
        if self.capability_successor_preflight_gate_passed != expected_gate:
            raise ValueError("v26.141 pre-registered Capability Gate changed")
        expected_status = (
            "capability_successor_preflight_gate_passed_pending_independent_audit"
            if expected_gate
            else "capability_successor_preflight_gate_failed_pending_independent_audit"
        )
        if self.execution_status != expected_status:
            raise ValueError("v26.141 execution status changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_privacy_safe_capability_execution_report:",
        ):
            raise ValueError("v26.141 execution-report identity changed")
        return self


class PreparedExecution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    source_replay: ExecutionSourceReplayAudit
    preflight_report: preflight.CapabilityPreflightReport
    task_package_catalog: preflight.CapabilityTaskPackageCatalog
    path_catalog: preflight.CapabilityPathCatalog
    noninterference_audit: preflight.CapabilityPromptNoninterferenceAudit
    predecessor_integrity: preflight.PredecessorIntegrityAudit
    execution_contract: preflight.CapabilityExecutionContract
    manifest: preflight.CapabilityManifest
    outcome_contract: preflight.CapabilityOutcomeContract
    runner_contract: preflight.CapabilityRunnerContract
    resource_contract: preflight.CapabilityResourceBinding
    transition_contract: preflight.ProspectiveTransitionContract
    preexecution_binding: PreexecutionBindingAudit
    inputs: Any


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
    raise ValueError(f"v26.141 cannot replay bound file: {relative_path}")


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
    report = preflight.CapabilityPreflightReport.model_validate(_load(report_path))
    if (
        source.audit_id != EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
        or report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or _sha256(report_path) != EXPECTED_PREFLIGHT_REPORT_SHA256
        or _sha256(transition_path) != EXPECTED_TRANSITION_SHA256
    ):
        raise ValueError("v26.141 predecessor report, transition, or replay bytes changed")
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
            source_kind="v26_140_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
    details = {item.relative_path: item for item in report.detail_files}
    if set(PREFLIGHT_OUTPUTS) != {"report.json", *details}:
        raise ValueError("v26.141 predecessor output set changed")
    for name in PREFLIGHT_OUTPUTS:
        path = preflight_dir / name
        if not path.is_file():
            raise ValueError(f"v26.141 predecessor output missing: {name}")
        observed = _sha256(path)
        if name != "report.json":
            expected = details[name]
            if expected.sha256 != observed or expected.byte_count != path.stat().st_size:
                raise ValueError("v26.141 predecessor detail binding changed")
        relative = str(Path(PREFLIGHT_DIR) / name)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_140_output",
            expected_sha256=observed,
            observed_sha256=observed,
            byte_count=path.stat().st_size,
        )
    implementation_path = implementation_root / IMPLEMENTATION_PATH
    observed = _sha256(implementation_path)
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_141_implementation",
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
            "finance_v26_privacy_safe_capability_execution_source_replay:",
        ),
        **values,
    )


def _rebuild_preflight_outputs(
    *,
    package_root: Path,
    implementation_root: Path,
    preflight_dir: Path,
) -> PreexecutionBindingAudit:
    with tempfile.TemporaryDirectory(prefix="v26_141_preexecution_rebuild_") as temporary:
        rebuilt_dir = Path(temporary)
        report = preflight.build_capability_preflight(
            package_root=package_root,
            implementation_root=implementation_root,
            output_dir=rebuilt_dir,
        )
        for name in PREFLIGHT_OUTPUTS:
            if (preflight_dir / name).read_bytes() != (rebuilt_dir / name).read_bytes():
                raise ValueError(f"v26.141 predecessor rebuild changed: {name}")
    fixture = preflight.RunnerFixtureAudit.model_validate(
        _load(preflight_dir / "capability_runner_fixture_audit.json")
    )
    manifest = preflight.CapabilityManifest.model_validate(
        _load(preflight_dir / "privacy_safe_capability_manifest.json")
    )
    values: dict[str, Any] = {
        "scripted_fixture_job_count": fixture.completed_job_count,
        "scripted_fixture_call_count": fixture.scripted_local_calls,
        "scripted_first_action_qualified_count": (fixture.first_action_interface_qualified_count),
        "exact_job_count": len(manifest.jobs),
        "distinct_capability_task_count": len({item.task_package_id for item in manifest.jobs}),
        "mechanism_tier_cell_count": len(
            {(item.mechanism_id, item.tier) for item in manifest.jobs}
        ),
    }
    if report.report_id != EXPECTED_PREFLIGHT_REPORT_ID:
        raise ValueError("v26.141 rebuilt preflight report identity changed")
    provisional = PreexecutionBindingAudit.model_construct(audit_id="pending", **values)
    return PreexecutionBindingAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_capability_execution_preexecution_binding:",
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
    report = preflight.CapabilityPreflightReport.model_validate(
        _load(preflight_dir / "report.json")
    )
    tasks = preflight.CapabilityTaskPackageCatalog.model_validate(
        _load(preflight_dir / "capability_task_package_catalog.json")
    )
    paths = preflight.CapabilityPathCatalog.model_validate(
        _load(preflight_dir / "capability_path_catalog.json")
    )
    noninterference = preflight.CapabilityPromptNoninterferenceAudit.model_validate(
        _load(preflight_dir / "capability_prompt_noninterference_audit.json")
    )
    predecessor_integrity = preflight.PredecessorIntegrityAudit.model_validate(
        _load(preflight_dir / "predecessor_integrity_audit.json")
    )
    execution = preflight.CapabilityExecutionContract.model_validate(
        _load(preflight_dir / "capability_execution_contract.json")
    )
    manifest = preflight.CapabilityManifest.model_validate(
        _load(preflight_dir / "privacy_safe_capability_manifest.json")
    )
    outcome = preflight.CapabilityOutcomeContract.model_validate(
        _load(preflight_dir / "capability_outcome_contract.json")
    )
    runner = preflight.CapabilityRunnerContract.model_validate(
        _load(preflight_dir / "capability_runner_contract.json")
    )
    resource = preflight.CapabilityResourceBinding.model_validate(
        _load(preflight_dir / "capability_resource_binding.json")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate(
        _load(preflight_dir / "prospective_transition_contract.json")
    )
    if (
        report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or report.source_replay_audit_id != EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
        or report.task_package_catalog_id != EXPECTED_TASK_CATALOG_ID
        or report.path_catalog_id != EXPECTED_PATH_CATALOG_ID
        or report.prompt_noninterference_audit_id != EXPECTED_NONINTERFERENCE_AUDIT_ID
        or report.resource_binding_id != EXPECTED_RESOURCE_CONTRACT_ID
        or report.execution_contract_id != EXPECTED_EXECUTION_CONTRACT_ID
        or report.manifest_id != EXPECTED_MANIFEST_ID
        or report.outcome_contract_id != EXPECTED_OUTCOME_CONTRACT_ID
        or report.runner_contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or report.transition_contract_id != EXPECTED_TRANSITION_ID
        or report.prospective_execution_id != EXPECTED_PROSPECTIVE_EXECUTION_ID
        or report.prospective_report_id != EXPECTED_PROSPECTIVE_REPORT_ID
        or report.status != "privacy_safe_s1_capability_runner_preflight_passed"
        or report.next_permitted_stage != preflight.NEXT_STAGE
        or report.capability_execution_occurred
        or report.fresh_reachability_identity_count
        or report.provider_calls
        or report.stage_two_provider_calls
        or tasks.catalog_id != EXPECTED_TASK_CATALOG_ID
        or paths.catalog_id != EXPECTED_PATH_CATALOG_ID
        or noninterference.audit_id != EXPECTED_NONINTERFERENCE_AUDIT_ID
        or execution.contract_id != EXPECTED_EXECUTION_CONTRACT_ID
        or resource.contract_id != EXPECTED_RESOURCE_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_MANIFEST_ID
        or outcome.contract_id != EXPECTED_OUTCOME_CONTRACT_ID
        or runner.contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or transition.contract_id != EXPECTED_TRANSITION_ID
        or transition.next_permitted_stage != preflight.NEXT_STAGE
        or not transition.exact_fresh_96_job_capability_execution_authorized
        or not transition.provider_calls_authorized_only_for_exact_capability_denominator
        or not transition.capability_execution_authorized
        or transition.reachability_identity_materialization_authorized
        or transition.reachability_execution_authorized
        or transition.state_mapping_authorized
        or len(manifest.jobs) != 96
        or len({item.job_id for item in manifest.jobs}) != 96
        or len({item.task_package_id for item in manifest.jobs}) != 12
        or manifest.reachability_job_count
        or manifest.prospective_execution_run_id != RUN_ID
        or runner.execution_run_id != RUN_ID
        or runner.stage_two_provider_call_upper_bound
        or not runner.v2_privacy_safe_s1_only_action_prompts
        or runner.full_object_fallback_allowed
        or not runner.capability_only
        or runner.reachability_identity_or_route_present
        or outcome.exact_denominator != 96
        or not outcome.independent_postrun_audit_required
    ):
        raise ValueError("v26.141 exact online authorization changed")
    inputs = preflight._load_role_inputs(  # noqa: SLF001
        package_root=package_root,
        implementation_root=implementation_root,
    )
    if (
        inputs.static.agent_model_config.public_manifest_hash
        != preflight.role_base.EXPECTED_MODEL_CONFIG_ID
        or inputs.static.stage_one.profile_id != preflight.role_base.EXPECTED_STAGE_ONE_PROFILE_ID
        or inputs.static.stage_two.profile_id != preflight.role_base.EXPECTED_STAGE_TWO_PROFILE_ID
    ):
        raise ValueError("v26.141 model, Thinking, or Stage 2 profile changed")
    frozen_outputs: tuple[tuple[str, Any], ...] = (
        ("preexecution_binding_audit.json", preexecution),
        ("frozen_capability_task_package_catalog.json", tasks),
        ("frozen_capability_path_catalog.json", paths),
        ("frozen_capability_prompt_noninterference_audit.json", noninterference),
        ("frozen_predecessor_integrity_audit.json", predecessor_integrity),
        ("frozen_capability_execution_contract.json", execution),
        ("frozen_capability_manifest.json", manifest),
        ("frozen_capability_outcome_contract.json", outcome),
        ("frozen_capability_runner_contract.json", runner),
        ("frozen_capability_resource_binding.json", resource),
        ("frozen_preflight_transition_contract.json", transition),
    )
    for name, value in frozen_outputs:
        _write_json_atomic(output_dir / name, value)
    return PreparedExecution(
        source_replay=source,
        preflight_report=report,
        task_package_catalog=tasks,
        path_catalog=paths,
        noninterference_audit=noninterference,
        predecessor_integrity=predecessor_integrity,
        execution_contract=execution,
        manifest=manifest,
        outcome_contract=outcome,
        runner_contract=runner,
        resource_contract=resource,
        transition_contract=transition,
        preexecution_binding=preexecution,
        inputs=inputs,
    )


def _provider_pairs(
    raw: preflight.CapabilityRawExecution,
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
            raise ValueError("v26.141 Provider Envelope binding changed")
        envelopes.append(privacy_runner.PrivacyFirstProviderEnvelope.model_validate(_load(path)))
    for descriptor in raw.public_payload_projection_artifacts:
        path = output_dir / descriptor.relative_path
        if (
            not path.is_file()
            or _sha256(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.141 public Projection binding changed")
        projections.append(privacy_runner.PublicPayloadProjection.model_validate(_load(path)))
    if len(envelopes) != len(projections):
        raise ValueError("v26.141 Envelope/Projection denominator diverged")
    pairs = tuple(zip(envelopes, projections, strict=True))
    for envelope, projection in pairs:
        privacy_runner.validate_provider_artifact_pair(envelope, projection)
    return pairs


def _choice_diagnostics(
    *,
    raw: preflight.CapabilityRawExecution,
    prepared: PreparedExecution,
    binding: Any,
) -> tuple[CapabilityChoiceDiagnostic, ...]:
    observations: list[Any] = []
    rejections: list[Any] = []
    rejection_by_id = {item.rejection_id: item for item in raw.semantic_rejections}
    diagnostics: list[CapabilityChoiceDiagnostic] = []
    previous_legal_no_progress = False
    for choice in raw.semantic_choices:
        state = preflight.build_semantic_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            tuple(observations),
            semantic_rejections=tuple(rejections),
        )
        if state.state_id != choice.state_id:
            raise ValueError("v26.141 reconstructed Choice state differs from Raw binding")
        presentation_salt = preflight.role_base._presentation_salt(  # noqa: SLF001
            selection_id=binding.selection_id,
            package=binding.package.predecessor_package,
            strategy="structured_direct",
            state=state,
            logical_index=choice.logical_request_index,
        )
        typed_failure = None
        if choice.public_attempt_phase == "semantic_recovery":
            if not rejections:
                raise ValueError("v26.141 Semantic Recovery Choice lacks a rejection")
            rejection = rejections[-1]
            typed_failure = {
                "family": "semantic_action_rejection",
                "subtype": rejection.error_category,
                "rejection_id": rejection.rejection_id,
            }
        primary = preflight.prompt_base.render_privacy_safe_s1_action_prompt(
            phase=choice.public_attempt_phase,
            instruction=binding.record.task_package.task.public.instruction,
            state=state,
            public_path_condition=None,
            presentation_salt=presentation_salt,
            typed_failure=typed_failure,
            grammar=prepared.inputs.static.action_grammar,
        )
        attempts = tuple(
            item
            for item in raw.attempts
            if item.request_kind == "semantic_proposal"
            and item.logical_request_index == choice.logical_request_index
        )
        usable = tuple(item for item in attempts if item.disposition == "usable")
        if len(usable) != 1:
            raise ValueError("v26.141 accepted Choice lacks one usable response attempt")
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
            prompt = preflight.prompt_base.render_privacy_safe_s1_action_prompt(
                phase="abi_rescue",
                instruction=binding.record.task_package.task.public.instruction,
                state=state,
                public_path_condition=None,
                presentation_salt=presentation_salt,
                typed_failure={"family": family, "subtype": subtype},
                grammar=prepared.inputs.static.action_grammar,
            )
            response_phase = "abi_rescue"
        if legacy.sha256_text(prompt) != active.prompt_sha256:
            raise ValueError("v26.141 reconstructed S1 Choice Prompt changed")
        decoded_state, _ = (
            preflight.runner_base.predecessor.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: E501, SLF001
                prompt, presentation_salt=presentation_salt
            )
        )
        if decoded_state != state:
            raise ValueError("v26.141 S1 Prompt reconstruction changed its public state")
        reference_action_id = preflight.runner_base._reference_proposal_from_s1_prompt(  # noqa: SLF001
            prompt
        ).action_id
        candidate_rows: list[CapabilityCandidatePresentationRow] = []
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
                CapabilityCandidatePresentationRow(
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
                raise ValueError("v26.141 Choice references a missing Observation")
            observation = raw.observations[observation_index]
            if observation.status != choice.observation_status:
                raise ValueError("v26.141 Choice Observation status changed")
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
        provisional = CapabilityChoiceDiagnostic.model_construct(diagnostic_id="pending", **values)
        diagnostics.append(
            CapabilityChoiceDiagnostic(
                diagnostic_id=_identity(
                    provisional,
                    "diagnostic_id",
                    "finance_v26_privacy_safe_capability_choice_diagnostic:",
                ),
                **values,
            )
        )
        if choice.rejection_id is not None:
            rejection = rejection_by_id.get(choice.rejection_id)
            if rejection is None:
                raise ValueError("v26.141 Choice rejection lacks its public Observation")
            rejections.append(rejection)
        previous_legal_no_progress = legal_no_progress
    if len(observations) != len(raw.observations):
        raise ValueError("v26.141 Choice diagnostics did not consume every Observation")
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
    raw: preflight.CapabilityRawExecution,
    prepared: PreparedExecution,
    binding: Any,
    output_dir: Path,
) -> tuple[CapabilityJobResult, tuple[CapabilityChoiceDiagnostic, ...]]:
    replay = legacy.replay_v3(
        cast(Any, raw),
        static=prepared.inputs.static.predecessor.historical,
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
    diagnostics = _choice_diagnostics(raw=raw, prepared=prepared, binding=binding)
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
    privacy_gate_failure = bool(raw.privacy_rejected_payload_count or not privacy_pairing)
    answer_valid = bool(verification is not None and verification.valid)
    terminal: CapabilityTerminalCategory
    if instrument:
        terminal = "instrument_failure"
    elif privacy_gate_failure:
        terminal = "privacy_rejection"
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
        raise ValueError("v26.141 first Choice and diagnostic diverged")
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
        raise ValueError("v26.141 independently recomputed first-action Gate changed")
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
    telemetry_gate_failure = bool(not exact_model or not thinking or not usage)
    logical_primary_count = len({item.logical_request_index for item in raw.attempts})
    values: dict[str, Any] = {
        "job_id": raw.job.job_id,
        "predecessor_job_id": raw.job.predecessor_job_id,
        "task_package_id": raw.job.task_package_id,
        "source_task_artifact_id": raw.job.source_task_artifact_id,
        "mechanism_id": raw.job.mechanism_id,
        "tier": raw.job.tier,
        "replicate_index": raw.job.replicate_index,
        "seed": raw.job.seed,
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
            preflight._capability_raw_path(output_dir, raw.job),  # noqa: SLF001
            output_dir,
        ),
    }
    provisional = CapabilityJobResult.model_construct(result_id="pending", **values)
    return (
        CapabilityJobResult(
            result_id=_identity(
                provisional,
                "result_id",
                "finance_v26_privacy_safe_capability_job_result:",
            ),
            **values,
        ),
        diagnostics,
    )


def raw_lineage_audit(
    *,
    results: Sequence[CapabilityJobResult],
    raw_by_job: Mapping[str, preflight.CapabilityRawExecution],
    output_dir: Path,
) -> CapabilityRawLineageAudit:
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
        replayed = preflight.CapabilityRawExecution.model_validate(_load(raw_path))
        if (
            replayed.model_dump(mode="json") != raw.model_dump(mode="json")
            or _sha256(raw_path) != result.raw_execution_artifact.sha256
        ):
            raise ValueError(f"v26.141 Raw replay changed: {result.job_id}")
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
                raise ValueError("v26.141 privacy Artifact bytes changed")
            files.append(_descriptor(path, output_dir))
        for descriptor in raw.transport_invocation_artifacts:
            path = output_dir / descriptor.relative_path
            certificate = preflight.runner_base.TransportInvocationCertificate.model_validate(
                _load(path)
            )
            if _sha256(path) != descriptor.sha256 or path.stat().st_size != descriptor.byte_count:
                raise ValueError("v26.141 Transport certificate bytes changed")
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
        raise ValueError("v26.141 duplicate Provider Envelope identity")
    if len(set(projection_ids)) != len(projection_ids):
        raise ValueError("v26.141 duplicate public Projection identity")
    if len(set(transport_ids)) != len(transport_ids):
        raise ValueError("v26.141 duplicate Transport certificate identity")
    provisional = CapabilityRawLineageAudit.model_construct(audit_id="pending", **values)
    return CapabilityRawLineageAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_capability_raw_lineage:",
        ),
        **values,
    )


def _instrument_eligible(result: CapabilityJobResult) -> bool:
    return not result.instrument_failure


def _privacy_compliant(result: CapabilityJobResult) -> bool:
    return _instrument_eligible(result) and not result.privacy_gate_failure


def _has_public_progress(result: CapabilityJobResult) -> bool:
    return result.progress_vector_change_count > 0


def _task_summaries(
    results: Sequence[CapabilityJobResult],
) -> tuple[TaskCapabilitySummary, ...]:
    grouped: dict[str, list[CapabilityJobResult]] = {}
    for item in results:
        grouped.setdefault(item.task_package_id, []).append(item)
    summaries: list[TaskCapabilitySummary] = []
    for task_package_id in sorted(grouped):
        rows = grouped[task_package_id]
        first = rows[0]
        valid = sum(item.independent_trajectory_validity for item in rows)
        values: dict[str, Any] = {
            "task_package_id": task_package_id,
            "source_task_artifact_id": first.source_task_artifact_id,
            "mechanism_id": first.mechanism_id,
            "tier": first.tier,
            "job_count": len(rows),
            "instrument_eligible_count": sum(_instrument_eligible(item) for item in rows),
            "privacy_compliant_count": sum(_privacy_compliant(item) for item in rows),
            "action_entry_count": sum(item.first_action_interface_qualified for item in rows),
            "reversible_commit_count": sum(
                item.reversible_stage_two_commit_count > 0 for item in rows
            ),
            "public_progress_count": sum(_has_public_progress(item) for item in rows),
            "program_closure_count": sum(item.program_closed for item in rows),
            "terminal_verification_count": sum(
                item.postterminal_verification_completed for item in rows
            ),
            "exact_final_abi_count": sum(item.final_abi_crossed for item in rows),
            "independently_valid_count": valid,
            "support_exit_count": sum(item.detour_measurement_support_exit for item in rows),
            "instrument_failure_count": sum(item.instrument_failure for item in rows),
            "privacy_rejection_count": sum(
                item.terminal_category == "privacy_rejection" for item in rows
            ),
            "provider_transport_failure_count": sum(
                item.terminal_category == "provider_transport_failure" for item in rows
            ),
            "typed_budget_no_call_count": sum(
                item.terminal_category == "typed_budget_no_call" for item in rows
            ),
            "valid_fraction": format(Decimal(valid) / Decimal(len(rows)), "f"),
            "terminal_counts": dict(
                sorted(Counter(item.terminal_category for item in rows).items())
            ),
        }
        provisional = TaskCapabilitySummary.model_construct(summary_id="pending", **values)
        summaries.append(
            TaskCapabilitySummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_privacy_safe_capability_task_summary:",
                ),
                **values,
            )
        )
    return tuple(summaries)


def _group_summaries(
    results: Sequence[CapabilityJobResult],
    *,
    group_kind: Literal["mechanism", "tier"],
) -> tuple[GroupCapabilitySummary, ...]:
    grouped: dict[str, list[CapabilityJobResult]] = {}
    for item in results:
        key = item.mechanism_id if group_kind == "mechanism" else item.tier
        grouped.setdefault(key, []).append(item)
    summaries: list[GroupCapabilitySummary] = []
    nonmodel_terminals = {
        "privacy_rejection",
        "ordinary_detour_allowance_exhausted",
        "typed_budget_no_call",
        "provider_transport_failure",
        "instrument_failure",
    }
    for value in sorted(grouped):
        rows = grouped[value]
        task_ids = {item.task_package_id for item in rows}
        valid_task_ids = {
            item.task_package_id for item in rows if item.independent_trajectory_validity
        }
        values: dict[str, Any] = {
            "group_kind": group_kind,
            "group_value": value,
            "task_count": len(task_ids),
            "job_count": len(rows),
            "tasks_with_independently_valid_trajectory": len(valid_task_ids),
            "independently_valid_count": sum(item.independent_trajectory_validity for item in rows),
            "action_entry_count": sum(item.first_action_interface_qualified for item in rows),
            "program_closure_count": sum(item.program_closed for item in rows),
            "exact_final_abi_count": sum(item.final_abi_crossed for item in rows),
            "support_exit_count": sum(item.detour_measurement_support_exit for item in rows),
            "nonmodel_failure_count": sum(
                item.terminal_category in nonmodel_terminals for item in rows
            ),
            "terminal_counts": dict(
                sorted(Counter(item.terminal_category for item in rows).items())
            ),
        }
        provisional = GroupCapabilitySummary.model_construct(summary_id="pending", **values)
        summaries.append(
            GroupCapabilitySummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_privacy_safe_capability_group_summary:",
                ),
                **values,
            )
        )
    return tuple(summaries)


def _cell_summaries(
    results: Sequence[CapabilityJobResult],
) -> tuple[MechanismTierCellSummary, ...]:
    grouped: dict[tuple[str, str], list[CapabilityJobResult]] = {}
    for item in results:
        grouped.setdefault((item.mechanism_id, item.tier), []).append(item)
    summaries: list[MechanismTierCellSummary] = []
    for mechanism_id, tier in sorted(grouped):
        rows = grouped[(mechanism_id, tier)]
        task_ids = {item.task_package_id for item in rows}
        if len(task_ids) != 1:
            raise ValueError("v26.141 Mechanism x Tier cell no longer has one task")
        values: dict[str, Any] = {
            "mechanism_id": mechanism_id,
            "tier": tier,
            "task_package_id": next(iter(task_ids)),
            "job_count": len(rows),
            "action_entry_count": sum(item.first_action_interface_qualified for item in rows),
            "program_closure_count": sum(item.program_closed for item in rows),
            "exact_final_abi_count": sum(item.final_abi_crossed for item in rows),
            "independently_valid_count": sum(item.independent_trajectory_validity for item in rows),
            "terminal_counts": dict(
                sorted(Counter(item.terminal_category for item in rows).items())
            ),
        }
        provisional = MechanismTierCellSummary.model_construct(summary_id="pending", **values)
        summaries.append(
            MechanismTierCellSummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_privacy_safe_capability_cell_summary:",
                ),
                **values,
            )
        )
    return tuple(summaries)


def make_execution_report(
    *,
    prepared: PreparedExecution,
    results: Sequence[CapabilityJobResult],
    lineage: CapabilityRawLineageAudit,
) -> CapabilityExecutionReport:
    terminal_counts = Counter(item.terminal_category for item in results)
    tasks = _task_summaries(results)
    mechanisms = _group_summaries(results, group_kind="mechanism")
    tiers = _group_summaries(results, group_kind="tier")
    cells = _cell_summaries(results)
    detour_distribution = {
        "0": sum(item.ordinary_detour_count == 0 for item in results),
        "1": sum(item.ordinary_detour_count == 1 for item in results),
        "2+": sum(item.ordinary_detour_count >= 2 for item in results),
    }
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
    combined_support = sum(
        item.terminal_category
        in {
            "ordinary_detour_allowance_exhausted",
            "typed_budget_no_call",
            "provider_transport_failure",
        }
        for item in results
    )
    valid_mechanisms = {
        item.mechanism_id for item in results if item.independent_trajectory_validity
    }
    valid_tasks = {item.task_package_id for item in results if item.independent_trajectory_validity}
    outcome_values = prepared.outcome_contract.model_dump(mode="json")
    minimum_valid_mechanisms = int(
        outcome_values[
            "minimum_mechanisms_with_independently_valid_trajectory_for_successor_preflight"
        ]
    )
    gate_passed = bool(
        len(valid_mechanisms) >= minimum_valid_mechanisms
        and combined_integrity == 0
        and combined_support == 0
        and len(results) == 96
    )
    cost = sum((Decimal(item.estimated_cost_usd) for item in results), Decimal("0"))
    valid_count = sum(item.independent_trajectory_validity for item in results)
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
        "instrument_eligible_job_count": sum(_instrument_eligible(item) for item in results),
        "privacy_compliant_job_count": sum(_privacy_compliant(item) for item in results),
        "action_entry_job_count": sum(item.first_action_interface_qualified for item in results),
        "reversible_commit_job_count": sum(
            item.reversible_stage_two_commit_count > 0 for item in results
        ),
        "public_progress_job_count": sum(_has_public_progress(item) for item in results),
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
        "independently_valid_trajectory_count": valid_count,
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
        "primary_request_count": sum(item.logical_primary_request_count for item in results),
        "abi_rescue_call_count": sum(item.abi_rescue_attempt_count for item in results),
        "semantic_recovery_call_count": sum(
            item.semantic_recovery_attempt_count for item in results
        ),
        "transport_replacement_invocation_count": sum(
            item.transport_replacement_attempt_count for item in results
        ),
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
        "task_summaries": tasks,
        "mechanism_summaries": mechanisms,
        "tier_summaries": tiers,
        "mechanism_tier_cell_summaries": cells,
        "mechanisms_with_independently_valid_trajectory": len(valid_mechanisms),
        "tasks_with_independently_valid_trajectory": len(valid_tasks),
        "task_weighted_valid_fraction": format(Decimal(valid_count) / Decimal(len(results)), "f"),
        "detour_measurement_support_exit_job_count": terminal_counts[
            "ordinary_detour_allowance_exhausted"
        ],
        "typed_semantic_rejection_job_count": terminal_counts["typed_semantic_rejection"],
        "typed_budget_no_call_job_count": terminal_counts["typed_budget_no_call"],
        "provider_transport_failure_job_count": terminal_counts["provider_transport_failure"],
        "privacy_rejection_job_count": terminal_counts["privacy_rejection"],
        "instrument_failure_job_count": terminal_counts["instrument_failure"],
        "model_invalid_trajectory_count": terminal_counts["model_invalid_trajectory"],
        "model_identity_failure_job_count": model_failures,
        "thinking_failure_job_count": thinking_failures,
        "usage_failure_job_count": usage_failures,
        "combined_integrity_gate_failure_job_count": combined_integrity,
        "combined_support_boundary_failure_job_count": combined_support,
        "capability_successor_preflight_gate_passed": gate_passed,
        "execution_status": (
            "capability_successor_preflight_gate_passed_pending_independent_audit"
            if gate_passed
            else "capability_successor_preflight_gate_failed_pending_independent_audit"
        ),
    }
    provisional = CapabilityExecutionReport.model_construct(report_id="pending", **values)
    return CapabilityExecutionReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_privacy_safe_capability_execution_report:",
        ),
        **values,
    )


def _load_checkpoint(
    path: Path,
    *,
    prepared: PreparedExecution,
    output_dir: Path,
) -> tuple[CapabilityJobResult, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        CapabilityJobResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in prepared.manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("v26.141 checkpoint contains duplicate Jobs")
    for result in rows:
        job = jobs.get(result.job_id)
        if job is None or result.runner_contract_id != prepared.runner_contract.contract_id:
            raise ValueError("v26.141 checkpoint crosses the frozen denominator")
        raw_path = preflight._capability_raw_path(output_dir, job)  # noqa: SLF001
        if not raw_path.is_file() or _sha256(raw_path) != result.raw_execution_artifact.sha256:
            raise ValueError("v26.141 checkpoint Raw binding changed")
    return rows


ClientFactory = Callable[[AgentModelConfig, preflight.CapabilityJob, Any], Any]


def _default_client_factory(
    config: AgentModelConfig,
    _job: preflight.CapabilityJob,
    _binding: Any,
) -> Any:
    return StageOneProspectiveThinkingJsonClient(config)


def _run_one_job(
    *,
    job: preflight.CapabilityJob,
    prepared: PreparedExecution,
    client_factory: ClientFactory | None,
    output_dir: Path,
) -> tuple[
    CapabilityJobResult,
    preflight.CapabilityRawExecution,
    tuple[CapabilityChoiceDiagnostic, ...],
]:
    binding = preflight._capability_binding(  # noqa: SLF001
        inputs=prepared.inputs,
        tasks=prepared.task_package_catalog,
        job=job,
    )
    client = (
        None
        if client_factory is None
        else client_factory(prepared.inputs.static.agent_model_config, job, binding)
    )
    raw = preflight.execute_capability_job_raw(
        job=job,
        runner_contract=prepared.runner_contract,
        resource_contract=prepared.resource_contract,
        static=prepared.inputs.static,
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


def _write_checkpoint(path: Path, rows: Sequence[CapabilityJobResult]) -> None:
    payload = b"\n".join(_canonical_bytes(item.model_dump(mode="json")) for item in rows)
    if payload:
        payload += b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _assert_no_orphan_artifacts(
    output_dir: Path,
    job: preflight.CapabilityJob,
) -> None:
    envelope_dir = privacy_runner.provider_envelope_path(output_dir, cast(Any, job), 0).parent
    projection_dir = privacy_runner.payload_projection_path(output_dir, cast(Any, job), 0).parent
    invocation_dir = preflight.runner_base._invocation_path(  # noqa: SLF001
        output_dir, cast(Any, job), 0
    ).parent
    counts = (
        len(tuple(envelope_dir.glob("call_*.json"))) if envelope_dir.exists() else 0,
        len(tuple(projection_dir.glob("call_*.json"))) if projection_dir.exists() else 0,
        len(tuple(invocation_dir.glob("invocation_*.json"))) if invocation_dir.exists() else 0,
    )
    if any(counts):
        raise ValueError(
            "orphan v26.141 Artifacts forbid retry: "
            f"job={job.job_id} envelopes={counts[0]} projections={counts[1]} "
            f"invocations={counts[2]}"
        )


def run_privacy_safe_s1_capability(
    *,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
    workers: int,
    client_factory: ClientFactory = _default_client_factory,
) -> CapabilityExecutionReport:
    prepared = prepare_execution(
        preflight_dir=preflight_dir,
        output_dir=output_dir,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    checkpoint_path = output_dir / "privacy_safe_s1_capability_job_results.checkpoint.jsonl"
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
        raise ValueError("v26.141 completed report exists while Jobs remain pending")
    if not pending and report_path.exists():
        report = CapabilityExecutionReport.model_validate(_load(report_path))
        if (
            report.runner_contract_id != prepared.runner_contract.contract_id
            or report.source_replay_audit_id != prepared.source_replay.audit_id
        ):
            raise ValueError("v26.141 completed report crosses frozen bindings")
        return report
    raw_recovery_jobs = [
        item
        for item in pending
        if preflight._capability_raw_path(output_dir, item).exists()  # noqa: SLF001
    ]
    model_pending_jobs = [
        item
        for item in pending
        if not preflight._capability_raw_path(output_dir, item).exists()  # noqa: SLF001
    ]
    for job in model_pending_jobs:
        _assert_no_orphan_artifacts(output_dir, job)
    print(
        f"[v26.141] resuming {len(completed)}/96; "
        f"raw-only recovery {len(raw_recovery_jobs)}; "
        f"executing {len(model_pending_jobs)} Jobs with {workers} workers",
        flush=True,
    )
    raw_by_job: dict[str, preflight.CapabilityRawExecution] = {}
    diagnostics_by_job: dict[str, tuple[CapabilityChoiceDiagnostic, ...]] = {}
    for job in jobs:
        raw_path = preflight._capability_raw_path(output_dir, job)  # noqa: SLF001
        if raw_path.exists() and job.job_id in completed:
            raw = preflight.CapabilityRawExecution.model_validate(_load(raw_path))
            binding = preflight._capability_binding(  # noqa: SLF001
                inputs=prepared.inputs,
                tasks=prepared.task_package_catalog,
                job=job,
            )
            raw_by_job[job.job_id] = raw
            diagnostics_by_job[job.job_id] = _choice_diagnostics(
                raw=raw,
                prepared=prepared,
                binding=binding,
            )
    lock = threading.Lock()

    def record_completion(
        *,
        job: preflight.CapabilityJob,
        result: CapabilityJobResult,
        raw: preflight.CapabilityRawExecution,
        diagnostics: tuple[CapabilityChoiceDiagnostic, ...],
        recovered_after_worker_exception: bool = False,
    ) -> None:
        with lock:
            completed[job.job_id] = result
            raw_by_job[job.job_id] = raw
            diagnostics_by_job[job.job_id] = diagnostics
            ordered = tuple(completed[item.job_id] for item in jobs if item.job_id in completed)
            _write_checkpoint(checkpoint_path, ordered)
            recovery_label = " recovered" if recovered_after_worker_exception else ""
            print(
                f"[v26.141]{recovery_label} completed {len(completed)}/96 "
                f"{job.job_id.rsplit(':', 1)[-1][:12]} "
                f"task={job.source_task_artifact_id.rsplit(':', 1)[-1][:10]} "
                f"mechanism={job.mechanism_id} tier={job.tier} "
                f"terminal={result.terminal_category} "
                f"entry={result.first_action_interface_qualified} "
                f"valid={result.independent_trajectory_validity} "
                f"detours={result.ordinary_detour_count} "
                f"calls={result.provider_call_count}",
                flush=True,
            )

    worker_failures: list[tuple[preflight.CapabilityJob, str]] = []
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
            try:
                result, raw, diagnostics = future.result()
            except Exception as error:
                worker_failures.append((job, type(error).__name__))
                raw_exists = preflight._capability_raw_path(  # noqa: SLF001
                    output_dir, job
                ).is_file()
                print(
                    "[v26.141] worker exception retained for no-call recovery: "
                    f"job={job.job_id} type={type(error).__name__} "
                    f"raw_persisted={raw_exists}",
                    flush=True,
                )
                continue
            record_completion(job=job, result=result, raw=raw, diagnostics=diagnostics)

    unresolved_worker_failures: list[tuple[preflight.CapabilityJob, str]] = []
    for job, original_failure_type in worker_failures:
        raw_path = preflight._capability_raw_path(output_dir, job)  # noqa: SLF001
        if not raw_path.is_file():
            unresolved_worker_failures.append((job, original_failure_type))
            continue
        try:
            result, raw, diagnostics = _run_one_job(
                job=job,
                prepared=prepared,
                client_factory=None,
                output_dir=output_dir,
            )
        except Exception as error:
            unresolved_worker_failures.append((job, type(error).__name__))
            print(
                "[v26.141] Raw-only worker recovery failed closed: "
                f"job={job.job_id} type={type(error).__name__}",
                flush=True,
            )
            continue
        record_completion(
            job=job,
            result=result,
            raw=raw,
            diagnostics=diagnostics,
            recovered_after_worker_exception=True,
        )
    if unresolved_worker_failures:
        failure_types = Counter(kind for _, kind in unresolved_worker_failures)
        raise RuntimeError(
            "v26.141 worker failures remained after every future was drained; "
            f"count={len(unresolved_worker_failures)} "
            f"types={dict(sorted(failure_types.items()))}"
        )
    results = tuple(completed[item.job_id] for item in jobs)
    if len(results) != 96:
        raise ValueError("v26.141 execution denominator is incomplete")
    for job in jobs:
        raw_by_job.setdefault(
            job.job_id,
            preflight.CapabilityRawExecution.model_validate(
                _load(preflight._capability_raw_path(output_dir, job))  # noqa: SLF001
            ),
        )
        if job.job_id not in diagnostics_by_job:
            binding = preflight._capability_binding(  # noqa: SLF001
                inputs=prepared.inputs,
                tasks=prepared.task_package_catalog,
                job=job,
            )
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
        output_dir / "privacy_safe_s1_capability_job_results.json",
        [item.model_dump(mode="json") for item in results],
    )
    _write_json_atomic(
        output_dir / "privacy_safe_s1_capability_choice_diagnostics.json",
        [item.model_dump(mode="json") for item in diagnostics],
    )
    _write_json_atomic(output_dir / "raw_lineage_audit.json", lineage)
    _write_json_atomic(report_path, report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Run the exact v26.141 privacy-safe S1 Capability denominator"
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
                    "distinct_tasks": len(
                        {item.task_package_id for item in prepared.manifest.jobs}
                    ),
                    "reachability_jobs": prepared.manifest.reachability_job_count,
                    "operator_authorized_replacement_rerun": True,
                    "prior_attempt_artifacts_available": False,
                    "prior_attempt_auditable_jobs": 0,
                    "prior_attempt_pooled_jobs": 0,
                    "pristine_first_exposure_claimed": False,
                    "durable_output_root": str(args.output_dir),
                    "model_client_constructed": False,
                    "provider_calls": 0,
                    "stage_two_provider_calls": 0,
                },
                indent=2,
            )
        )
        return
    report = run_privacy_safe_s1_capability(
        preflight_dir=args.preflight_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
