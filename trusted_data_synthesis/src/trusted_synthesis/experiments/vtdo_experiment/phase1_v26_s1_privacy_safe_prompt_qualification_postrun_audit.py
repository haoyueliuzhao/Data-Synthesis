from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
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
    phase1_v26_s1_privacy_safe_prompt_qualification_online as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_privacy_safe_prompt_runner_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_online as semantic_online,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_139_privacy_safe_s1_qualification_postrun_audit_v1_20260824"
EXECUTION_DIR: Final = execution.OUTPUT_DIR
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_139_privacy_safe_s1_qualification_postrun_audit_v1_20260824"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_s1_privacy_safe_prompt_qualification_postrun_audit.py"
)
NEXT_STAGE: Final = (
    "fresh_privacy_safe_s1_capability_taskpackage_contract_manifest_runner_preflight_only"
)

EXPECTED_EXECUTION_REPORT_ID: Final = (
    "finance_v26_privacy_safe_s1_qualification_execution_report:"
    "f9b1df0929685b8245814ac190c88c822468015680770692b249c935d2838ff9"
)
EXPECTED_EXECUTION_REPORT_SHA256: Final = (
    "9a8656bcb3536e93b754a94f0a5b05c5cc364b43b93fb9372318069b9d122158"
)
EXPECTED_EXECUTION_SOURCE_REPLAY_ID: Final = (
    "finance_v26_privacy_safe_s1_execution_source_replay:"
    "95158b5c06a23946fb4f777c11618dd05f42ae88b19d7a9e9b09d5bdf536b267"
)
EXPECTED_PREEXECUTION_BINDING_ID: Final = (
    "finance_v26_privacy_safe_s1_execution_preexecution_binding:"
    "6837ea4429d13ac231197578b67d9476511206d9b23f4188a3f4b03bdd656cd6"
)
EXPECTED_RAW_LINEAGE_ID: Final = (
    "finance_v26_privacy_safe_s1_qualification_raw_lineage:"
    "9768e142debfe9586efa3c7feaa52f7c24005cf976f70b105cb157f025e734f3"
)
EXPECTED_FAILED_ENTRY_JOB_ID: Final = (
    "finance_v26_privacy_safe_s1_qualification_job:"
    "4bb4c50a51a1708f73445ba1f0c0ffb98b1b6825d40d81cbc8b597df2ea35975"
)
EXPECTED_MANIFEST_ID: Final = execution.EXPECTED_MANIFEST_ID
EXPECTED_RUNNER_CONTRACT_ID: Final = execution.EXPECTED_RUNNER_CONTRACT_ID
EXPECTED_OUTCOME_CONTRACT_ID: Final = execution.EXPECTED_OUTCOME_CONTRACT_ID
EXPECTED_QUALIFICATION_CONTRACT_ID: Final = execution.EXPECTED_QUALIFICATION_CONTRACT_ID
EXPECTED_PROMPT_METADATA_CONTRACT_ID: Final = execution.EXPECTED_PROMPT_METADATA_CONTRACT_ID
EXPECTED_NONINTERFERENCE_AUDIT_ID: Final = execution.EXPECTED_NONINTERFERENCE_AUDIT_ID

EXECUTION_TOP_LEVEL_FILES: Final = (
    "frozen_predecessor_integrity_audit.json",
    "frozen_preflight_transition_contract.json",
    "frozen_privacy_safe_outcome_contract.json",
    "frozen_privacy_safe_path_catalog.json",
    "frozen_privacy_safe_prompt_metadata_contract.json",
    "frozen_privacy_safe_qualification_contract.json",
    "frozen_privacy_safe_qualification_manifest.json",
    "frozen_privacy_safe_resource_contract.json",
    "frozen_privacy_safe_runner_contract.json",
    "frozen_privacy_safe_task_package_catalog.json",
    "frozen_prompt_privacy_noninterference_audit.json",
    "online_source_replay_audit.json",
    "preexecution_binding_audit.json",
    "privacy_safe_s1_qualification_choice_diagnostics.json",
    "privacy_safe_s1_qualification_job_results.checkpoint.jsonl",
    "privacy_safe_s1_qualification_job_results.json",
    "raw_lineage_audit.json",
    "report.json",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_138_transitive_source",
        "v26_138_execution_file",
        "v26_139_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class PostrunSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    execution_source_replay_id: str = EXPECTED_EXECUTION_SOURCE_REPLAY_ID
    transitive_source_file_count: Literal[3901] = 3901
    execution_file_count: Literal[623] = 623
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[4525] = 4525
    replay_pass_count: Literal[4525] = 4525
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=4525, max_length=4525)
    replay_before_profile_parsing: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_privacy_safe_s1_postrun_source_replay.v1"] = (
        "finance_v26_privacy_safe_s1_postrun_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PostrunSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.replayed_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.139 source replay changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_privacy_safe_s1_postrun_source_replay:",
        ):
            raise ValueError("v26.139 source replay identity changed")
        return self


class IndependentRawReconstructionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    raw_lineage_id: str = EXPECTED_RAW_LINEAGE_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    job_result_count: Literal[32] = 32
    checkpoint_row_count: Literal[32] = 32
    raw_execution_count: Literal[32] = 32
    provider_call_count: Literal[191] = 191
    transport_invocation_count: Literal[191] = 191
    provider_envelope_count: Literal[191] = 191
    public_projection_count: Literal[191] = 191
    complete_provider_pair_count: Literal[191] = 191
    validated_public_payload_count: Literal[191] = 191
    privacy_rejected_payload_count: Literal[0] = 0
    provider_failure_no_payload_count: Literal[0] = 0
    http_success_call_count: Literal[191] = 191
    exact_model_call_count: Literal[191] = 191
    thinking_telemetry_call_count: Literal[191] = 191
    complete_usage_call_count: Literal[191] = 191
    semantic_choice_count: Literal[132] = 132
    reversible_commit_count: Literal[132] = 132
    public_observation_count: Literal[115] = 115
    progress_event_count: Literal[115] = 115
    exact_final_payload_count: Literal[15] = 15
    completed_result_count: Literal[15] = 15
    replay_v3_pass_count: Literal[32] = 32
    independently_valid_trajectory_count: Literal[15] = 15
    exact_byte_descriptor_pass_count: Literal[605] = 605
    unique_envelope_id_count: Literal[191] = 191
    unique_projection_id_count: Literal[191] = 191
    unique_transport_certificate_id_count: Literal[191] = 191
    envelope_projection_orphan_count: Literal[0] = 0
    private_reasoning_payload_count: Literal[0] = 0
    invalid_payload_content_persistence_count: Literal[0] = 0
    raw_http_body_persistence_count: Literal[0] = 0
    raw_request_body_persistence_count: Literal[0] = 0
    role_source_job_count: Literal[0] = 0
    role_class_external_action_opportunity_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    report_aggregate_match_count: Literal[34] = 34
    report_aggregate_field_count: Literal[34] = 34
    provider_calls_during_audit: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_s1_independent_raw_reconstruction.v1"] = (
        "finance_v26_privacy_safe_s1_independent_raw_reconstruction.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentRawReconstructionAudit:
        if self.report_aggregate_match_count != self.report_aggregate_field_count:
            raise ValueError("v26.139 independent aggregate reconstruction changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_privacy_safe_s1_independent_raw_reconstruction:",
        ):
            raise ValueError("v26.139 Raw reconstruction identity changed")
        return self


class OnlinePromptNoninterferenceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    prompt_metadata_contract_id: str = EXPECTED_PROMPT_METADATA_CONTRACT_ID
    static_noninterference_audit_id: str = EXPECTED_NONINTERFERENCE_AUDIT_ID
    prompt_protocol: Literal["prospective_role_scalable_semantic_action_prompt.v2"] = (
        "prospective_role_scalable_semantic_action_prompt.v2"
    )
    semantic_action_attempt_count: Literal[173] = 173
    action_primary_attempt_count: Literal[147] = 147
    action_abi_rescue_attempt_count: Literal[26] = 26
    action_semantic_recovery_attempt_count: Literal[0] = 0
    exact_prompt_hash_reconstruction_count: Literal[173] = 173
    exact_prompt_byte_count_match_count: Literal[173] = 173
    v2_protocol_prompt_count: Literal[173] = 173
    classifier_sensitive_key_occurrence_count: Literal[0] = 0
    prompts_with_classifier_sensitive_key_count: Literal[0] = 0
    predecessor_sensitive_key_occurrence_count: Literal[0] = 0
    full_object_fallback_prompt_count: Literal[0] = 0
    exact_state_reconstruction_count: Literal[173] = 173
    exact_candidate_set_and_order_count: Literal[173] = 173
    model_behavior_equivalence_to_v1_claimed: Literal[False] = False
    provider_calls_during_audit: Literal[0] = 0
    status: Literal["online_prompt_output_namespace_noninterference_passed"] = (
        "online_prompt_output_namespace_noninterference_passed"
    )
    schema_version: Literal["finance_v26_online_prompt_noninterference_audit.v1"] = (
        "finance_v26_online_prompt_noninterference_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> OnlinePromptNoninterferenceAudit:
        if (
            self.semantic_action_attempt_count
            != self.action_primary_attempt_count
            + self.action_abi_rescue_attempt_count
            + self.action_semantic_recovery_attempt_count
            or self.classifier_sensitive_key_occurrence_count
            or self.prompts_with_classifier_sensitive_key_count
        ):
            raise ValueError("v26.139 online Prompt noninterference changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_online_prompt_noninterference_audit:",
        ):
            raise ValueError("v26.139 online Prompt audit identity changed")
        return self


class EntryBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    failed_entry_job_id: str = EXPECTED_FAILED_ENTRY_JOB_ID
    mechanism_id: Literal["failure_recovery"] = "failure_recovery"
    path_strategy_id: Literal["search_then_structured"] = "search_then_structured"
    provider_call_count: Literal[2] = 2
    http_success_call_count: Literal[2] = 2
    validated_public_payload_count: Literal[2] = 2
    privacy_rejected_payload_count: Literal[0] = 0
    exact_four_field_key_set_count: Literal[2] = 2
    exact_protocol_count: Literal[2] = 2
    current_state_binding_count: Literal[2] = 2
    visible_action_id_count: Literal[2] = 2
    decision_kind_mismatch_count: Literal[2] = 2
    observed_decision_kinds: tuple[str, str] = ("select", "query_fully_qualified")
    exact_action_abi_count: Literal[0] = 0
    semantic_choice_count: Literal[0] = 0
    reversible_commit_count: Literal[0] = 0
    first_action_interface_qualified: Literal[False] = False
    terminal_category: Literal["model_invalid_trajectory"] = "model_invalid_trajectory"
    failure_family: Literal["response_serialization_failure"] = "response_serialization_failure"
    failure_subtype: Literal["canonical_action_not_exact_four_field_grammar"] = (
        "canonical_action_not_exact_four_field_grammar"
    )
    model_result_not_instrument_failure: Literal[True] = True
    privacy_compliant_public_output: Literal[True] = True
    host_alias_or_decision_kind_repair_authorized: Literal[False] = False
    provider_calls_during_audit: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_s1_entry_boundary_audit.v1"] = (
        "finance_v26_privacy_safe_s1_entry_boundary_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> EntryBoundaryAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_privacy_safe_s1_entry_boundary_audit:",
        ):
            raise ValueError("v26.139 Entry-boundary identity changed")
        return self


class QualificationGateAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    qualification_contract_id: str = EXPECTED_QUALIFICATION_CONTRACT_ID
    outcome_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    exact_job_denominator: Literal[32] = 32
    first_action_interface_minimum_jobs: Literal[24] = 24
    first_action_interface_qualified_job_count: Literal[31] = 31
    required_mechanism_path_cell_coverage: Literal[12] = 12
    qualified_mechanism_path_cell_count: Literal[12] = 12
    entry_quantity_gate_passed: Literal[True] = True
    entry_cell_coverage_gate_passed: Literal[True] = True
    privacy_gate_failure_job_count: Literal[0] = 0
    model_identity_failure_job_count: Literal[0] = 0
    thinking_failure_job_count: Literal[0] = 0
    usage_failure_job_count: Literal[0] = 0
    instrument_failure_job_count: Literal[0] = 0
    combined_integrity_gate_failure_job_count: Literal[0] = 0
    zero_integrity_failure_gate_passed: Literal[True] = True
    representation_qualification_gate_passed: Literal[True] = True
    first_action_failure_job_ids: tuple[str, ...] = (EXPECTED_FAILED_ENTRY_JOB_ID,)
    terminal_counts: dict[str, int] = {
        "model_invalid_trajectory": 17,
        "model_valid_trajectory": 15,
    }
    ordinary_detour_job_distribution: dict[str, int] = {"0": 31, "1": 1, "2+": 0}
    detour_measurement_support_exit_job_count: Literal[0] = 0
    program_closed_job_count: Literal[21] = 21
    exact_final_abi_job_count: Literal[15] = 15
    independently_valid_trajectory_count: Literal[15] = 15
    full_trajectory_values_are_descriptive_not_gate_inputs: Literal[True] = True
    entry_gate_is_not_role_scale_or_full_trajectory_readability: Literal[True] = True
    prior_v1_entry_rows_pooled: Literal[False] = False
    historical_v26_134_gate_reclassified: Literal[False] = False
    status: Literal["passed_exact_v2_engineering_qualification"] = (
        "passed_exact_v2_engineering_qualification"
    )
    provider_calls_during_audit: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_s1_qualification_gate_audit.v1"] = (
        "finance_v26_privacy_safe_s1_qualification_gate_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> QualificationGateAudit:
        if (
            self.entry_quantity_gate_passed
            != (
                self.first_action_interface_qualified_job_count
                >= self.first_action_interface_minimum_jobs
            )
            or self.entry_cell_coverage_gate_passed
            != (
                self.qualified_mechanism_path_cell_count
                == self.required_mechanism_path_cell_coverage
            )
            or self.zero_integrity_failure_gate_passed
            != (self.combined_integrity_gate_failure_job_count == 0)
            or self.representation_qualification_gate_passed
            != (
                self.entry_quantity_gate_passed
                and self.entry_cell_coverage_gate_passed
                and self.zero_integrity_failure_gate_passed
            )
        ):
            raise ValueError("v26.139 qualification Gate changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_privacy_safe_s1_qualification_gate_audit:",
        ):
            raise ValueError("v26.139 Gate-audit identity changed")
        return self


class OutcomeInterpretation(FrozenModel):
    interpretation_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    gate_audit_id: str = Field(min_length=1)
    prompt_noninterference_audit_id: str = Field(min_length=1)
    entry_boundary_audit_id: str = Field(min_length=1)
    qualification_gate_passed: Literal[True] = True
    exact_v2_engineering_s1_interface_qualified: Literal[True] = True
    qualification_is_for_repeated_engineering_sources_only: Literal[True] = True
    prior_v1_result_not_pooled: Literal[True] = True
    historical_v26_134_gate_remains_failed: Literal[True] = True
    historical_privacy_rejection_cause_identified: Literal[False] = False
    role_scale_s1_readability_claim_authorized: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_or_state_mapping_authorized: Literal[False] = False
    fresh_capability_identity_and_runner_preflight_authorized: Literal[True] = True
    reachability_identity_or_execution_authorized: Literal[False] = False
    classifier_grammar_candidate_s1_model_thinking_or_bounds_change_authorized: Literal[False] = (
        False
    )
    host_alias_or_output_repair_authorized: Literal[False] = False
    full_trajectory_result_is_repeated_engineering_source_diagnostic: Literal[True] = True
    production_contribution: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_s1_outcome_interpretation.v1"] = (
        "finance_v26_privacy_safe_s1_outcome_interpretation.v1"
    )

    @model_validator(mode="after")
    def validate_interpretation(self) -> OutcomeInterpretation:
        if self.interpretation_id != _identity(
            self,
            "interpretation_id",
            "finance_v26_privacy_safe_s1_outcome_interpretation:",
        ):
            raise ValueError("v26.139 outcome interpretation identity changed")
        return self


class MutationResult(FrozenModel):
    mutation: str = Field(min_length=1)
    rejected: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[MutationResult, ...] = Field(min_length=16, max_length=16)
    mutation_count: Literal[16] = 16
    rejection_count: Literal[16] = 16
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_s1_postrun_destructive.v1"] = (
        "finance_v26_privacy_safe_s1_postrun_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if len(self.mutations) != self.mutation_count:
            raise ValueError("v26.139 destructive denominator changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_privacy_safe_s1_postrun_destructive:",
        ):
            raise ValueError("v26.139 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    outcome_interpretation_id: str = Field(min_length=1)
    next_permitted_stage: str = NEXT_STAGE
    qualification_gate_passed: Literal[True] = True
    exact_v2_engineering_s1_interface_qualification_frozen: Literal[True] = True
    fresh_capability_taskpackage_contract_manifest_runner_preflight_authorized: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    role_provider_calls_authorized: Literal[False] = False
    reachability_or_state_mapping_authorized: Literal[False] = False
    role_population_task_tier_or_source_change_authorized: Literal[False] = False
    classifier_grammar_candidate_s1_model_thinking_resource_recovery_change_authorized: Literal[
        False
    ] = False
    historical_rerun_recovery_pooling_or_reclassification_authorized: Literal[False] = False
    training_release_or_production_authorized: Literal[False] = False
    role_source_model_exposure_count: Literal[0] = 0
    status: Literal["privacy_safe_s1_qualified_capability_preflight_only"] = (
        "privacy_safe_s1_qualified_capability_preflight_only"
    )
    schema_version: Literal["finance_v26_privacy_safe_s1_postrun_transition.v1"] = (
        "finance_v26_privacy_safe_s1_postrun_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_privacy_safe_s1_postrun_transition:",
        ):
            raise ValueError("v26.139 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    raw_reconstruction_audit_id: str = Field(min_length=1)
    prompt_noninterference_audit_id: str = Field(min_length=1)
    entry_boundary_audit_id: str = Field(min_length=1)
    qualification_gate_audit_id: str = Field(min_length=1)
    outcome_interpretation_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=8, max_length=8)
    exact_job_denominator: Literal[32] = 32
    provider_call_count: Literal[191] = 191
    first_action_interface_qualified_job_count: Literal[31] = 31
    qualified_mechanism_path_cell_count: Literal[12] = 12
    privacy_rejected_job_count: Literal[0] = 0
    combined_integrity_failure_job_count: Literal[0] = 0
    qualification_gate_passed: Literal[True] = True
    online_v2_action_prompt_count: Literal[173] = 173
    online_classifier_sensitive_key_count: Literal[0] = 0
    independently_valid_trajectory_count: Literal[15] = 15
    ordinary_detour_job_count: Literal[1] = 1
    detour_support_exit_job_count: Literal[0] = 0
    provider_prompt_tokens: Literal[589102] = 589102
    provider_completion_tokens: Literal[866466] = 866466
    provider_reasoning_tokens: Literal[840279] = 840279
    provider_total_tokens: Literal[1455568] = 1455568
    estimated_cost_usd: Literal["0.32318810720000002837"] = "0.32318810720000002837"
    exact_v2_engineering_s1_interface_qualified: Literal[True] = True
    role_scale_s1_readability_claimed: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    historical_rows_reclassified: Literal[0] = 0
    historical_entry_rows_pooled: Literal[0] = 0
    role_source_model_exposure_count: Literal[0] = 0
    capability_rows: Literal[0] = 0
    reachability_rows: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    production_contribution: Literal[0] = 0
    next_permitted_stage: str = NEXT_STAGE
    status: Literal["privacy_safe_s1_qualification_passed_capability_preflight_only"] = (
        "privacy_safe_s1_qualification_passed_capability_preflight_only"
    )
    schema_version: Literal["finance_v26_privacy_safe_s1_postrun_audit_report.v1"] = (
        "finance_v26_privacy_safe_s1_postrun_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> PostrunAuditReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_privacy_safe_s1_postrun_audit_report:",
        ):
            raise ValueError("v26.139 report identity changed")
        return self


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value.model_dump(mode="json")))
    temporary.replace(path)


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
    raise ValueError(f"v26.139 cannot replay bound file: {relative_path}")


def _execution_files(execution_dir: Path) -> tuple[Path, ...]:
    files = tuple(sorted(path for path in execution_dir.rglob("*") if path.is_file()))
    if len(files) != 623:
        raise ValueError("v26.139 execution-file denominator changed")
    roots = {path.name for path in files if path.parent == execution_dir}
    if roots != set(EXECUTION_TOP_LEVEL_FILES):
        raise ValueError("v26.139 execution top-level file set changed")
    return files


def _build_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
) -> PostrunSourceReplayAudit:
    report_path = execution_dir / "report.json"
    report = execution.QualificationExecutionReport.model_validate(_load(report_path))
    source = execution.ExecutionSourceReplayAudit.model_validate(
        _load(execution_dir / "online_source_replay_audit.json")
    )
    if (
        report.report_id != EXPECTED_EXECUTION_REPORT_ID
        or _sha256(report_path) != EXPECTED_EXECUTION_REPORT_SHA256
        or source.audit_id != EXPECTED_EXECUTION_SOURCE_REPLAY_ID
    ):
        raise ValueError("v26.139 execution report or source replay changed")
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
            source_kind="v26_138_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
    for path in _execution_files(execution_dir):
        relative = str(Path(EXECUTION_DIR) / path.relative_to(execution_dir))
        digest = _sha256(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_138_execution_file",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    implementation_path = implementation_root / IMPLEMENTATION_PATH
    digest = _sha256(implementation_path)
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_139_implementation",
        expected_sha256=digest,
        observed_sha256=digest,
        byte_count=implementation_path.stat().st_size,
    )
    values = {"entries": tuple(entries[key] for key in sorted(entries))}
    provisional = PostrunSourceReplayAudit.model_construct(audit_id="pending", **values)
    return PostrunSourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_s1_postrun_source_replay:",
        ),
        **values,
    )


def _load_execution_objects(execution_dir: Path) -> dict[str, Any]:
    report = execution.QualificationExecutionReport.model_validate(
        _load(execution_dir / "report.json")
    )
    source = execution.ExecutionSourceReplayAudit.model_validate(
        _load(execution_dir / "online_source_replay_audit.json")
    )
    preexecution = execution.PreexecutionBindingAudit.model_validate(
        _load(execution_dir / "preexecution_binding_audit.json")
    )
    prompt_metadata = preflight.PrivacySafePromptMetadataContract.model_validate(
        _load(execution_dir / "frozen_privacy_safe_prompt_metadata_contract.json")
    )
    tasks = preflight.PrivacySafeTaskPackageCatalog.model_validate(
        _load(execution_dir / "frozen_privacy_safe_task_package_catalog.json")
    )
    paths = preflight.PrivacySafePathCatalog.model_validate(
        _load(execution_dir / "frozen_privacy_safe_path_catalog.json")
    )
    noninterference = preflight.PromptPrivacyNoninterferenceAudit.model_validate(
        _load(execution_dir / "frozen_prompt_privacy_noninterference_audit.json")
    )
    predecessor_integrity = preflight.PredecessorIntegrityAudit.model_validate(
        _load(execution_dir / "frozen_predecessor_integrity_audit.json")
    )
    qualification = preflight.PrivacySafeQualificationContract.model_validate(
        _load(execution_dir / "frozen_privacy_safe_qualification_contract.json")
    )
    manifest = preflight.PrivacySafeQualificationManifest.model_validate(
        _load(execution_dir / "frozen_privacy_safe_qualification_manifest.json")
    )
    outcome = preflight.PrivacySafeOutcomeContract.model_validate(
        _load(execution_dir / "frozen_privacy_safe_outcome_contract.json")
    )
    runner = preflight.PrivacySafeRunnerContract.model_validate(
        _load(execution_dir / "frozen_privacy_safe_runner_contract.json")
    )
    resource = preflight.PrivacySafeResourceContract.model_validate(
        _load(execution_dir / "frozen_privacy_safe_resource_contract.json")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate(
        _load(execution_dir / "frozen_preflight_transition_contract.json")
    )
    lineage = execution.QualificationRawLineageAudit.model_validate(
        _load(execution_dir / "raw_lineage_audit.json")
    )
    results = tuple(
        execution.QualificationJobResult.model_validate(item)
        for item in _load(execution_dir / "privacy_safe_s1_qualification_job_results.json")
    )
    checkpoint = tuple(
        execution.QualificationJobResult.model_validate_json(line)
        for line in (execution_dir / "privacy_safe_s1_qualification_job_results.checkpoint.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    )
    diagnostics = tuple(
        semantic_online.ChoiceDiagnostic.model_validate(item)
        for item in _load(execution_dir / "privacy_safe_s1_qualification_choice_diagnostics.json")
    )
    if (
        report.report_id != EXPECTED_EXECUTION_REPORT_ID
        or source.audit_id != EXPECTED_EXECUTION_SOURCE_REPLAY_ID
        or preexecution.audit_id != EXPECTED_PREEXECUTION_BINDING_ID
        or prompt_metadata.contract_id != EXPECTED_PROMPT_METADATA_CONTRACT_ID
        or tasks.catalog_id != execution.EXPECTED_TASK_CATALOG_ID
        or paths.catalog_id != execution.EXPECTED_PATH_CATALOG_ID
        or noninterference.audit_id != EXPECTED_NONINTERFERENCE_AUDIT_ID
        or not predecessor_integrity.formal_qualification_remains_failed
        or qualification.contract_id != EXPECTED_QUALIFICATION_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_MANIFEST_ID
        or outcome.contract_id != EXPECTED_OUTCOME_CONTRACT_ID
        or runner.contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or lineage.audit_id != EXPECTED_RAW_LINEAGE_ID
        or resource.contract_id != execution.EXPECTED_RESOURCE_CONTRACT_ID
        or transition.contract_id != execution.EXPECTED_TRANSITION_ID
        or not report.representation_qualification_gate_passed
        or report.next_permitted_stage != execution.POSTRUN_STAGE
        or len(results) != 32
        or len(checkpoint) != 32
        or len(diagnostics) != 132
    ):
        raise ValueError("v26.139 execution object binding changed")
    if tuple(item.model_dump(mode="json") for item in results) != tuple(
        item.model_dump(mode="json") for item in checkpoint
    ):
        raise ValueError("v26.139 checkpoint and final Job results diverged")
    if tuple(item.job_id for item in results) != tuple(item.job_id for item in manifest.jobs):
        raise ValueError("v26.139 Job-result order changed")
    return {
        "report": report,
        "manifest": manifest,
        "outcome": outcome,
        "runner": runner,
        "resource": resource,
        "lineage": lineage,
        "results": results,
        "diagnostics": diagnostics,
    }


def _reconstruct_raw(
    *,
    objects: Mapping[str, Any],
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
) -> tuple[IndependentRawReconstructionAudit, tuple[dict[str, Any], ...]]:
    report = cast(execution.QualificationExecutionReport, objects["report"])
    manifest = cast(preflight.PrivacySafeQualificationManifest, objects["manifest"])
    lineage = cast(execution.QualificationRawLineageAudit, objects["lineage"])
    results = cast(tuple[execution.QualificationJobResult, ...], objects["results"])
    loaded = preflight._load_inputs(package_root, implementation_root)  # noqa: SLF001
    envelope_ids: list[str] = []
    projection_ids: list[str] = []
    transport_ids: list[str] = []
    raw_rows: list[dict[str, Any]] = []
    call_count = 0
    invocation_count = 0
    validated = 0
    privacy_rejected = 0
    provider_failure = 0
    http_success = 0
    exact_model = 0
    thinking = 0
    usage = 0
    choices = 0
    commits = 0
    observations = 0
    progress_events = 0
    exact_final = 0
    completed = 0
    replay_pass = 0
    independent_valid = 0
    descriptor_passes = 0
    first_qualified = 0
    qualified_cells: set[str] = set()
    private_reasoning_payload_count = 0
    invalid_payload_content_count = 0
    terminal_counts: Counter[str] = Counter()
    detour_distribution: Counter[str] = Counter()
    aggregate_prompt_tokens = 0
    aggregate_completion_tokens = 0
    aggregate_reasoning_tokens = 0
    aggregate_total_tokens = 0
    max_prompt = 0
    max_job_tokens = 0
    for job, result in zip(manifest.jobs, results, strict=True):
        raw_path = execution_dir / result.raw_execution_artifact.relative_path
        if (
            _sha256(raw_path) != result.raw_execution_artifact.sha256
            or raw_path.stat().st_size != result.raw_execution_artifact.byte_count
        ):
            raise ValueError("v26.139 Raw descriptor changed")
        raw = preflight.PrivacySafeRawExecution.model_validate(_load(raw_path))
        if raw.job != job or raw.runner_contract_id != EXPECTED_RUNNER_CONTRACT_ID:
            raise ValueError("v26.139 Raw Job or Runner binding changed")
        descriptor_passes += 1
        old_job, binding = preflight._job_context(loaded, job)  # noqa: SLF001
        if old_job.job_id != job.source_engineering_job_id:
            raise ValueError("v26.139 engineering Job binding changed")
        replay = legacy.replay_v3(
            cast(Any, raw),
            static=loaded.engineering.predecessor.historical,
            binding=binding,
        )
        replay_pass += int(replay.passed)
        valid = False
        if raw.completed_result is not None:
            verification, _ = final_preflight._completed_verification(  # noqa: SLF001
                raw=cast(Any, raw),
                replay=replay,
                binding=binding,
            )
            valid = verification.valid and not result.instrument_failure
        independent_valid += int(valid)
        if valid != result.independent_trajectory_validity:
            raise ValueError("v26.139 independent validity changed")
        first_choice = raw.semantic_choices[0] if raw.semantic_choices else None
        first_exact = bool(
            first_choice is not None
            and any(
                item.request_kind == "semantic_proposal"
                and item.logical_request_index == first_choice.logical_request_index
                and item.exact_four_field_action_payload
                and item.disposition == "usable"
                for item in raw.attempts
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
        independent_first = bool(
            first_exact
            and first_choice is not None
            and first_choice.visible_action_id_match
            and first_choice.decision_kind_match
            and first_commit is not None
            and first_commit.public_state_id == first_choice.state_id
            and first_commit.reversible_same_action_id_passed
            and not first_commit.semantic_choice_inserted_by_host
        )
        if independent_first != raw.first_action_interface_qualified or (
            independent_first != result.first_action_interface_qualified
        ):
            raise ValueError("v26.139 first-action qualification changed")
        first_qualified += int(independent_first)
        if independent_first:
            qualified_cells.add(f"{job.mechanism_id}|{job.path_strategy_id}")
        call_count += raw.stage_one_provider_call_count
        invocation_count += raw.transport_inclusive_invocation_count
        choices += len(raw.semantic_choices)
        commits += len(raw.commits)
        observations += len(raw.observations)
        progress_events += len(raw.progress_events)
        exact_final += raw.exact_two_field_final_payload_count
        completed += int(raw.completed_result is not None)
        terminal_counts[result.terminal_category] += 1
        detour_distribution[
            "2+" if raw.ordinary_detour_count >= 2 else str(raw.ordinary_detour_count)
        ] += 1
        job_tokens = sum(item.total_tokens or 0 for item in raw.provider_telemetry)
        max_job_tokens = max(max_job_tokens, job_tokens)
        for telemetry in raw.provider_telemetry:
            http_success += int(telemetry.http_success)
            exact_model += int(
                telemetry.model_requested == legacy.STAGE_ONE_MODEL_ID
                and telemetry.model_selected == legacy.STAGE_ONE_MODEL_ID
                and telemetry.response_model == legacy.STAGE_ONE_MODEL_ID
            )
            thinking += int(
                telemetry.reasoning_content_present
                and (telemetry.reasoning_content_length or 0) > 0
                and (telemetry.reasoning_tokens or 0) > 0
            )
            usage += int(
                telemetry.prompt_tokens is not None
                and telemetry.completion_tokens is not None
                and telemetry.total_tokens is not None
                and telemetry.prompt_tokens + telemetry.completion_tokens == telemetry.total_tokens
            )
            aggregate_prompt_tokens += telemetry.prompt_tokens or 0
            aggregate_completion_tokens += telemetry.completion_tokens or 0
            aggregate_reasoning_tokens += telemetry.reasoning_tokens or 0
            aggregate_total_tokens += telemetry.total_tokens or 0
        max_prompt = max(
            max_prompt,
            max((item.prompt_utf8_bytes for item in raw.attempts), default=0),
        )
        envelopes: list[privacy_runner.PrivacyFirstProviderEnvelope] = []
        projections: list[privacy_runner.PublicPayloadProjection] = []
        for descriptor in raw.provider_envelope_artifacts:
            path = execution_dir / descriptor.relative_path
            if _sha256(path) != descriptor.sha256 or path.stat().st_size != descriptor.byte_count:
                raise ValueError("v26.139 Envelope descriptor changed")
            envelope = privacy_runner.PrivacyFirstProviderEnvelope.model_validate(_load(path))
            envelopes.append(envelope)
            envelope_ids.append(envelope.envelope_id)
            descriptor_passes += 1
        for descriptor in raw.public_payload_projection_artifacts:
            path = execution_dir / descriptor.relative_path
            if _sha256(path) != descriptor.sha256 or path.stat().st_size != descriptor.byte_count:
                raise ValueError("v26.139 Projection descriptor changed")
            projection = privacy_runner.PublicPayloadProjection.model_validate(_load(path))
            projections.append(projection)
            projection_ids.append(projection.projection_id)
            descriptor_passes += 1
            if projection.projection_status == "validated_public_payload":
                validated += 1
                if projection.response_payload is not None and legacy.contains_private_reasoning(
                    projection.response_payload
                ):
                    private_reasoning_payload_count += 1
            elif projection.projection_status == "privacy_rejected":
                privacy_rejected += 1
            else:
                provider_failure += 1
            if (
                projection.projection_status != "validated_public_payload"
                and projection.response_payload is not None
            ):
                invalid_payload_content_count += 1
        for envelope, projection in zip(envelopes, projections, strict=True):
            privacy_runner.validate_provider_artifact_pair(envelope, projection)
        for descriptor in raw.transport_invocation_artifacts:
            path = execution_dir / descriptor.relative_path
            if _sha256(path) != descriptor.sha256 or path.stat().st_size != descriptor.byte_count:
                raise ValueError("v26.139 Transport descriptor changed")
            certificate = preflight.runner_base.TransportInvocationCertificate.model_validate(
                _load(path)
            )
            transport_ids.append(certificate.certificate_id)
            descriptor_passes += 1
        raw_rows.append(
            {
                "job": job,
                "result": result,
                "raw": raw,
                "binding": binding,
                "grammar": loaded.engineering.action_grammar,
                "projections": tuple(projections),
            }
        )
    combined_integrity = sum(
        item.instrument_failure
        or item.privacy_gate_failure
        or not item.exact_model_passed
        or not item.thinking_continuity_passed
        or not item.provider_usage_complete
        for item in results
    )
    independent_gate_passed = bool(
        first_qualified >= 24 and len(qualified_cells) == 12 and combined_integrity == 0
    )
    independently_reconstructed = {
        "provider_call_count": call_count,
        "transport_inclusive_invocation_count": invocation_count,
        "validated_public_payload_count": validated,
        "privacy_rejected_payload_count": privacy_rejected,
        "provider_failure_no_payload_count": provider_failure,
        "http_success_call_count": http_success,
        "provider_prompt_tokens": aggregate_prompt_tokens,
        "provider_completion_tokens": aggregate_completion_tokens,
        "provider_reasoning_tokens": aggregate_reasoning_tokens,
        "provider_total_tokens": aggregate_total_tokens,
        "maximum_prompt_utf8_bytes": max_prompt,
        "maximum_job_provider_tokens": max_job_tokens,
        "first_action_interface_qualified_job_count": first_qualified,
        "qualified_mechanism_path_cell_count": len(qualified_cells),
        "exact_four_field_action_payload_count": sum(
            item.exact_four_field_action_payload_count for item in results
        ),
        "semantic_choice_count": choices,
        "reversible_stage_two_commit_count": commits,
        "public_observation_count": observations,
        "ordinary_detour_job_distribution": {
            "0": detour_distribution["0"],
            "1": detour_distribution["1"],
            "2+": detour_distribution["2+"],
        },
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
        "independently_valid_trajectory_count": independent_valid,
        "model_invalid_trajectory_count": terminal_counts["model_invalid_trajectory"],
        "privacy_gate_failure_job_count": sum(item.privacy_gate_failure for item in results),
        "model_identity_failure_job_count": sum(not item.exact_model_passed for item in results),
        "thinking_failure_job_count": sum(not item.thinking_continuity_passed for item in results),
        "usage_failure_job_count": sum(not item.provider_usage_complete for item in results),
        "combined_integrity_gate_failure_job_count": combined_integrity,
        "representation_qualification_gate_passed": independent_gate_passed,
        "clean_prompt_privacy_noncompliance_job_count": sum(
            item.privacy_rejected_payload_count > 0 for item in results
        ),
    }
    mismatches = {
        key: (value, getattr(report, key))
        for key, value in independently_reconstructed.items()
        if getattr(report, key) != value
    }
    if mismatches:
        raise ValueError(f"v26.139 report aggregate mismatch: {mismatches}")
    if (
        call_count != lineage.provider_call_count
        or invocation_count != lineage.transport_inclusive_invocation_count
        or descriptor_passes != 605
        or len(set(envelope_ids)) != 191
        or len(set(projection_ids)) != 191
        or len(set(transport_ids)) != 191
        or exact_model != 191
        or thinking != 191
        or usage != 191
        or replay_pass != 32
        or progress_events != observations
        or private_reasoning_payload_count
        or invalid_payload_content_count
        or privacy_rejected
        or provider_failure
    ):
        raise ValueError("v26.139 independent Raw denominator changed")
    values: dict[str, Any] = {
        "semantic_choice_count": choices,
        "reversible_commit_count": commits,
        "public_observation_count": observations,
        "progress_event_count": progress_events,
        "exact_final_payload_count": exact_final,
        "completed_result_count": completed,
        "replay_v3_pass_count": replay_pass,
        "independently_valid_trajectory_count": independent_valid,
        "exact_byte_descriptor_pass_count": descriptor_passes,
        "unique_envelope_id_count": len(set(envelope_ids)),
        "unique_projection_id_count": len(set(projection_ids)),
        "unique_transport_certificate_id_count": len(set(transport_ids)),
        "private_reasoning_payload_count": private_reasoning_payload_count,
        "invalid_payload_content_persistence_count": invalid_payload_content_count,
        "report_aggregate_match_count": len(independently_reconstructed),
        "report_aggregate_field_count": len(independently_reconstructed),
    }
    provisional = IndependentRawReconstructionAudit.model_construct(audit_id="pending", **values)
    return (
        IndependentRawReconstructionAudit(
            audit_id=_identity(
                provisional,
                "audit_id",
                "finance_v26_privacy_safe_s1_independent_raw_reconstruction:",
            ),
            **values,
        ),
        tuple(raw_rows),
    )


def _reconstruct_online_prompts(
    raw_rows: Sequence[Mapping[str, Any]],
) -> OnlinePromptNoninterferenceAudit:
    attempt_count = 0
    primary_count = 0
    abi_count = 0
    semantic_count = 0
    hash_matches = 0
    byte_matches = 0
    protocol_matches = 0
    sensitive_occurrences = 0
    prompts_with_sensitive = 0
    old_sensitive_occurrences = 0
    state_matches = 0
    candidate_matches = 0
    for row in raw_rows:
        job = cast(preflight.PrivacySafeQualificationJob, row["job"])
        raw = cast(preflight.PrivacySafeRawExecution, row["raw"])
        binding = row["binding"]
        observations: list[Any] = []
        rejections: list[Any] = []
        observation_index = 0
        ordinary_detour_count = 0
        choices = {item.logical_request_index: item for item in raw.semantic_choices}
        events = {item.logical_request_index: item for item in raw.progress_events}
        rejection_by_id = {item.rejection_id: item for item in raw.semantic_rejections}
        grouped: dict[int, list[Any]] = {}
        for attempt in raw.attempts:
            if attempt.request_kind == "semantic_proposal":
                grouped.setdefault(attempt.logical_request_index, []).append(attempt)
        condition = (
            None
            if binding.source_registered_path.role == "capability"
            else binding.source_registered_path.path_strategy_id
        )
        for logical_index in sorted(grouped):
            attempts = grouped[logical_index]
            state = preflight.build_semantic_action_state(
                binding.record.task_package.task.public,
                binding.environment,
                tuple(observations),
                semantic_rejections=tuple(rejections),
            )
            presentation_salt = canonical_hash(
                {
                    "qualification_job_id": job.candidate_presentation_salt_parent_job_id,
                    "logical_request_index": logical_index,
                    "state_id": state.state_id,
                    "semantic_recovery_count": len(rejections),
                    "ordinary_detour_count": ordinary_detour_count,
                },
                prefix="finance_v26_s1_qualification_candidate_presentation:",
            )
            public_phase = attempts[0].public_attempt_phase
            if public_phase not in {"primary", "semantic_recovery"}:
                raise ValueError("v26.139 first Action attempt phase changed")
            typed_failure = None
            if public_phase == "semantic_recovery":
                rejection = rejections[-1]
                typed_failure = {
                    "family": "semantic_action_rejection",
                    "subtype": rejection.error_category,
                    "rejection_id": rejection.rejection_id,
                }
            primary_prompt = preflight.render_privacy_safe_s1_action_prompt(
                phase=public_phase,
                instruction=binding.record.task_package.task.public.instruction,
                state=state,
                public_path_condition=condition,
                presentation_salt=presentation_salt,
                typed_failure=typed_failure,
                grammar=row["grammar"],
            )
            for attempt in attempts:
                prompt = primary_prompt
                if attempt.public_attempt_phase == "abi_rescue":
                    first = attempts[0]
                    prompt = preflight.render_privacy_safe_s1_action_prompt(
                        phase="abi_rescue",
                        instruction=binding.record.task_package.task.public.instruction,
                        state=state,
                        public_path_condition=condition,
                        presentation_salt=presentation_salt,
                        typed_failure={
                            "family": first.failure_family or "channel_parse_failure",
                            "subtype": first.failure_subtype
                            or first.completion_failure_type
                            or "completion_failure",
                        },
                        grammar=row["grammar"],
                    )
                    abi_count += 1
                elif attempt.public_attempt_phase == "semantic_recovery":
                    semantic_count += 1
                else:
                    primary_count += 1
                attempt_count += 1
                hash_matches += int(legacy.sha256_text(prompt) == attempt.prompt_sha256)
                byte_matches += int(len(prompt.encode("utf-8")) == attempt.prompt_utf8_bytes)
                payload = preflight._privacy_safe_prompt_payload(prompt)  # noqa: SLF001
                protocol_matches += int(
                    payload.prompt_protocol
                    == f"{preflight.PRIVACY_SAFE_PROMPT_PROTOCOL}.{attempt.public_attempt_phase}"
                )
                sensitive = preflight._sensitive_key_paths(  # noqa: SLF001
                    payload.model_dump(mode="json")
                )
                sensitive_occurrences += len(sensitive)
                prompts_with_sensitive += int(bool(sensitive))
                serialized = json.dumps(payload.model_dump(mode="json"), sort_keys=True)
                old_sensitive_occurrences += serialized.count("private_reasoning_reused")
                old_sensitive_occurrences += serialized.count("private_reasoning_content")
                decoded, _ = (
                    preflight.runner_base.predecessor.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001,E501
                        prompt,
                        presentation_salt=presentation_salt,
                    )
                )
                state_matches += int(decoded == state)
                candidate_matches += int(
                    tuple(item.action_id for item in decoded.action_candidates)
                    == tuple(item.action_id for item in state.action_candidates)
                )
            choice = choices.get(logical_index)
            if choice is not None:
                if choice.observation_status is not None:
                    observation = raw.observations[observation_index]
                    observation_index += 1
                    observations.append(observation)
                if choice.rejection_id is not None:
                    rejection = rejection_by_id.get(choice.rejection_id)
                    if rejection is None:
                        raise ValueError("v26.139 Choice rejection binding changed")
                    rejections.append(rejection)
            event = events.get(logical_index)
            if event is not None:
                ordinary_detour_count = event.ordinary_detour_count_after
        if observation_index != len(raw.observations):
            raise ValueError("v26.139 online Prompt replay missed Observations")
    values: dict[str, Any] = {
        "semantic_action_attempt_count": attempt_count,
        "action_primary_attempt_count": primary_count,
        "action_abi_rescue_attempt_count": abi_count,
        "action_semantic_recovery_attempt_count": semantic_count,
        "exact_prompt_hash_reconstruction_count": hash_matches,
        "exact_prompt_byte_count_match_count": byte_matches,
        "v2_protocol_prompt_count": protocol_matches,
        "classifier_sensitive_key_occurrence_count": sensitive_occurrences,
        "prompts_with_classifier_sensitive_key_count": prompts_with_sensitive,
        "predecessor_sensitive_key_occurrence_count": old_sensitive_occurrences,
        "exact_state_reconstruction_count": state_matches,
        "exact_candidate_set_and_order_count": candidate_matches,
    }
    provisional = OnlinePromptNoninterferenceAudit.model_construct(audit_id="pending", **values)
    return OnlinePromptNoninterferenceAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_online_prompt_noninterference_audit:",
        ),
        **values,
    )


def _make_entry_boundary(
    raw_rows: Sequence[Mapping[str, Any]],
) -> EntryBoundaryAudit:
    rows = [
        item
        for item in raw_rows
        if not cast(
            execution.QualificationJobResult, item["result"]
        ).first_action_interface_qualified
    ]
    if len(rows) != 1:
        raise ValueError("v26.139 failed-Entry denominator changed")
    row = rows[0]
    job = cast(preflight.PrivacySafeQualificationJob, row["job"])
    result = cast(execution.QualificationJobResult, row["result"])
    raw = cast(preflight.PrivacySafeRawExecution, row["raw"])
    binding = row["binding"]
    projections = cast(tuple[privacy_runner.PublicPayloadProjection, ...], row["projections"])
    state = preflight.build_semantic_action_state(
        binding.record.task_package.task.public,
        binding.environment,
        (),
        semantic_rejections=(),
    )
    candidates = {item.action_id: item for item in state.action_candidates}
    key_set_count = 0
    protocol_count = 0
    state_count = 0
    visible_count = 0
    mismatch_count = 0
    observed_kinds: list[str] = []
    for projection in projections:
        payload = projection.response_payload
        if not isinstance(payload, Mapping):
            raise ValueError("v26.139 failed Entry lacks its public payload")
        key_set_count += int(set(payload) == set(preflight.action_grammar.FIELD_ORDER))
        protocol_count += int(
            payload.get("protocol") == preflight.action_grammar.RESPONSE_PROTOCOL_VERSION
        )
        state_count += int(payload.get("state_id") == state.state_id)
        action_id = payload.get("action_id")
        candidate = candidates.get(action_id) if isinstance(action_id, str) else None
        visible_count += int(candidate is not None)
        decision_kind = payload.get("decision_kind")
        if not isinstance(decision_kind, str):
            raise ValueError("v26.139 failed Entry Decision kind is not public text")
        observed_kinds.append(decision_kind)
        mismatch_count += int(candidate is not None and decision_kind != candidate.decision_kind)
        try:
            preflight.action_grammar.parse_exact_canonical_action_payload(payload)
        except preflight.action_grammar.SemanticActionResponseRejection:
            pass
        else:
            raise ValueError("v26.139 failed Entry unexpectedly crossed the exact ABI")
    values: dict[str, Any] = {
        "failed_entry_job_id": job.job_id,
        "mechanism_id": job.mechanism_id,
        "path_strategy_id": job.path_strategy_id,
        "provider_call_count": raw.stage_one_provider_call_count,
        "http_success_call_count": sum(item.http_success for item in raw.provider_telemetry),
        "validated_public_payload_count": sum(
            item.projection_status == "validated_public_payload" for item in projections
        ),
        "privacy_rejected_payload_count": raw.privacy_rejected_payload_count,
        "exact_four_field_key_set_count": key_set_count,
        "exact_protocol_count": protocol_count,
        "current_state_binding_count": state_count,
        "visible_action_id_count": visible_count,
        "decision_kind_mismatch_count": mismatch_count,
        "observed_decision_kinds": tuple(observed_kinds),
        "exact_action_abi_count": raw.exact_four_field_action_payload_count,
        "semantic_choice_count": len(raw.semantic_choices),
        "reversible_commit_count": len(raw.commits),
        "first_action_interface_qualified": result.first_action_interface_qualified,
        "terminal_category": result.terminal_category,
        "failure_family": raw.attempts[-1].failure_family,
        "failure_subtype": raw.terminal_failure_type,
    }
    if (
        job.job_id != EXPECTED_FAILED_ENTRY_JOB_ID
        or result.instrument_failure
        or result.privacy_gate_failure
        or raw.terminal_disposition != "model_result_failure"
    ):
        raise ValueError("v26.139 failed-Entry interpretation changed")
    provisional = EntryBoundaryAudit.model_construct(audit_id="pending", **values)
    return EntryBoundaryAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_s1_entry_boundary_audit:",
        ),
        **values,
    )


def _make_gate_audit(
    objects: Mapping[str, Any],
) -> QualificationGateAudit:
    report = cast(execution.QualificationExecutionReport, objects["report"])
    results = cast(tuple[execution.QualificationJobResult, ...], objects["results"])
    failed = tuple(item.job_id for item in results if not item.first_action_interface_qualified)
    values = {
        "first_action_interface_qualified_job_count": (
            report.first_action_interface_qualified_job_count
        ),
        "qualified_mechanism_path_cell_count": report.qualified_mechanism_path_cell_count,
        "privacy_gate_failure_job_count": report.privacy_gate_failure_job_count,
        "model_identity_failure_job_count": report.model_identity_failure_job_count,
        "thinking_failure_job_count": report.thinking_failure_job_count,
        "usage_failure_job_count": report.usage_failure_job_count,
        "instrument_failure_job_count": report.instrument_failure_job_count,
        "combined_integrity_gate_failure_job_count": (
            report.combined_integrity_gate_failure_job_count
        ),
        "representation_qualification_gate_passed": (
            report.representation_qualification_gate_passed
        ),
        "first_action_failure_job_ids": failed,
        "terminal_counts": report.terminal_counts,
        "ordinary_detour_job_distribution": report.ordinary_detour_job_distribution,
        "detour_measurement_support_exit_job_count": (
            report.detour_measurement_support_exit_job_count
        ),
        "program_closed_job_count": report.program_closed_job_count,
        "exact_final_abi_job_count": report.exact_final_abi_job_count,
        "independently_valid_trajectory_count": report.independently_valid_trajectory_count,
    }
    provisional = QualificationGateAudit.model_construct(audit_id="pending", **values)
    return QualificationGateAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_s1_qualification_gate_audit:",
        ),
        **values,
    )


def _make_interpretation(
    gate: QualificationGateAudit,
    prompt: OnlinePromptNoninterferenceAudit,
    entry: EntryBoundaryAudit,
) -> OutcomeInterpretation:
    values = {
        "gate_audit_id": gate.audit_id,
        "prompt_noninterference_audit_id": prompt.audit_id,
        "entry_boundary_audit_id": entry.audit_id,
    }
    provisional = OutcomeInterpretation.model_construct(interpretation_id="pending", **values)
    return OutcomeInterpretation(
        interpretation_id=_identity(
            provisional,
            "interpretation_id",
            "finance_v26_privacy_safe_s1_outcome_interpretation:",
        ),
        **values,
    )


def _expect_rejected(name: str, callback: Callable[[], Any]) -> MutationResult:
    try:
        callback()
    except (ValueError, TypeError):
        return MutationResult(mutation=name)
    raise ValueError(f"v26.139 destructive mutation was accepted: {name}")


def _make_destructive(
    *,
    gate: QualificationGateAudit,
    prompt: OnlinePromptNoninterferenceAudit,
    entry: EntryBoundaryAudit,
    interpretation: OutcomeInterpretation,
) -> DestructiveAudit:
    mutations = (
        _expect_rejected(
            "qualification_gate_reversed",
            lambda: QualificationGateAudit.model_validate(
                gate.model_copy(
                    update={"representation_qualification_gate_passed": False}
                ).model_dump(mode="json")
            ),
        ),
        _expect_rejected(
            "entry_quantity_below_minimum",
            lambda: QualificationGateAudit.model_validate(
                gate.model_copy(
                    update={"first_action_interface_qualified_job_count": 23}
                ).model_dump(mode="json")
            ),
        ),
        _expect_rejected(
            "cell_coverage_below_contract",
            lambda: QualificationGateAudit.model_validate(
                gate.model_copy(update={"qualified_mechanism_path_cell_count": 11}).model_dump(
                    mode="json"
                )
            ),
        ),
        _expect_rejected(
            "privacy_failure_inserted",
            lambda: QualificationGateAudit.model_validate(
                gate.model_copy(update={"privacy_gate_failure_job_count": 1}).model_dump(
                    mode="json"
                )
            ),
        ),
        _expect_rejected(
            "combined_integrity_failure_inserted",
            lambda: QualificationGateAudit.model_validate(
                gate.model_copy(update={"combined_integrity_gate_failure_job_count": 1}).model_dump(
                    mode="json"
                )
            ),
        ),
        _expect_rejected(
            "online_sensitive_key_inserted",
            lambda: OnlinePromptNoninterferenceAudit.model_validate(
                prompt.model_copy(
                    update={"classifier_sensitive_key_occurrence_count": 1}
                ).model_dump(mode="json")
            ),
        ),
        _expect_rejected(
            "online_prompt_hash_match_removed",
            lambda: OnlinePromptNoninterferenceAudit.model_validate(
                prompt.model_copy(
                    update={"exact_prompt_hash_reconstruction_count": 172}
                ).model_dump(mode="json")
            ),
        ),
        _expect_rejected(
            "v1_prompt_protocol_claim",
            lambda: OnlinePromptNoninterferenceAudit.model_validate(
                prompt.model_copy(
                    update={
                        "prompt_protocol": "prospective_role_scalable_semantic_action_prompt.v1"
                    }
                ).model_dump(mode="json")
            ),
        ),
        _expect_rejected(
            "failed_entry_reclassified_instrument",
            lambda: EntryBoundaryAudit.model_validate(
                entry.model_copy(update={"model_result_not_instrument_failure": False}).model_dump(
                    mode="json"
                )
            ),
        ),
        _expect_rejected(
            "failed_entry_host_repair",
            lambda: EntryBoundaryAudit.model_validate(
                entry.model_copy(
                    update={"host_alias_or_decision_kind_repair_authorized": True}
                ).model_dump(mode="json")
            ),
        ),
        _expect_rejected(
            "historical_privacy_cause_claim",
            lambda: OutcomeInterpretation.model_validate(
                interpretation.model_copy(
                    update={"historical_privacy_rejection_cause_identified": True}
                ).model_dump(mode="json")
            ),
        ),
        _expect_rejected(
            "role_readability_claim",
            lambda: OutcomeInterpretation.model_validate(
                interpretation.model_copy(
                    update={"role_scale_s1_readability_claim_authorized": True}
                ).model_dump(mode="json")
            ),
        ),
        _expect_rejected(
            "capability_execution_claim",
            lambda: OutcomeInterpretation.model_validate(
                interpretation.model_copy(
                    update={"capability_execution_authorized": True}
                ).model_dump(mode="json")
            ),
        ),
        _expect_rejected(
            "reachability_authorization_claim",
            lambda: OutcomeInterpretation.model_validate(
                interpretation.model_copy(
                    update={"reachability_or_state_mapping_authorized": True}
                ).model_dump(mode="json")
            ),
        ),
        _expect_rejected(
            "provider_call_authorization_claim",
            lambda: ProspectiveTransitionContract.model_validate(
                _make_transition(interpretation)
                .model_copy(update={"provider_calls_authorized": True})
                .model_dump(mode="json")
            ),
        ),
        _expect_rejected(
            "production_contribution_claim",
            lambda: OutcomeInterpretation.model_validate(
                interpretation.model_copy(update={"production_contribution": 1}).model_dump(
                    mode="json"
                )
            ),
        ),
    )
    values = {"mutations": mutations}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_s1_postrun_destructive:",
        ),
        **values,
    )


def _make_transition(
    interpretation: OutcomeInterpretation,
) -> ProspectiveTransitionContract:
    values = {"outcome_interpretation_id": interpretation.interpretation_id}
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_privacy_safe_s1_postrun_transition:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_postrun_audit(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
    output_dir: Path,
) -> PostrunAuditReport:
    source = _build_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
    )
    objects = _load_execution_objects(execution_dir)
    raw, raw_rows = _reconstruct_raw(
        objects=objects,
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
    )
    prompt = _reconstruct_online_prompts(raw_rows)
    entry = _make_entry_boundary(raw_rows)
    gate = _make_gate_audit(objects)
    interpretation = _make_interpretation(gate, prompt, entry)
    destructive = _make_destructive(
        gate=gate,
        prompt=prompt,
        entry=entry,
        interpretation=interpretation,
    )
    transition = _make_transition(interpretation)
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_values: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source),
        ("independent_raw_reconstruction_audit.json", raw),
        ("online_prompt_noninterference_audit.json", prompt),
        ("entry_boundary_audit.json", entry),
        ("qualification_gate_audit.json", gate),
        ("outcome_interpretation.json", interpretation),
        ("destructive_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    for name, value in detail_values:
        _write_json_atomic(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in sorted(detail_values))
    values = {
        "source_replay_audit_id": source.audit_id,
        "raw_reconstruction_audit_id": raw.audit_id,
        "prompt_noninterference_audit_id": prompt.audit_id,
        "entry_boundary_audit_id": entry.audit_id,
        "qualification_gate_audit_id": gate.audit_id,
        "outcome_interpretation_id": interpretation.interpretation_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = PostrunAuditReport.model_construct(report_id="pending", **values)
    report = PostrunAuditReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_privacy_safe_s1_postrun_audit_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Independently audit the completed v26.138 privacy-safe S1 qualification"
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
    report = build_postrun_audit(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        execution_dir=args.execution_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
