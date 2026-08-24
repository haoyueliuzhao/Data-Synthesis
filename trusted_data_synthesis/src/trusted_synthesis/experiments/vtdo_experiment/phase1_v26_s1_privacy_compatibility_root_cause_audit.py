from __future__ import annotations

import argparse
import hashlib
import inspect
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
    phase1_v26_s1_representation_qualification_online as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_representation_qualification_postrun_audit as postrun,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_representation_qualification_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    prospective_semantic_action_response_grammar as action_grammar,
)

RUN_ID: Final = "finance_v26_136_s1_privacy_compatibility_root_cause_audit_v1_20260824"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_136_s1_privacy_compatibility_root_cause_audit_v1_20260824"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_s1_privacy_compatibility_root_cause_audit.py"
)
POSTRUN_DIR: Final = postrun.OUTPUT_DIR
EXECUTION_DIR: Final = execution.OUTPUT_DIR
NEXT_STAGE: Final = (
    "fresh_s1_privacy_safe_prompt_metadata_rematerialization_and_runner_preflight_only"
)

EXPECTED_POSTRUN_REPORT_ID: Final = (
    "finance_v26_s1_qualification_postrun_audit_report:"
    "4d4ebc3600d44dd29e468f2f386a4fcb50565fa62a36e5da915d5b5002be4fcc"
)
EXPECTED_POSTRUN_REPORT_SHA256: Final = (
    "7c533813325c0703f5e646a93f911ab41a54a3c9f26b42d5f52d82603620c031"
)
EXPECTED_POSTRUN_SOURCE_REPLAY_ID: Final = (
    "finance_v26_s1_postrun_source_replay:"
    "19234bc87a8d9a05373784783fbafb6428db0c603e04259138c400969217d2de"
)
EXPECTED_POSTRUN_TRANSITION_ID: Final = (
    "finance_v26_s1_postrun_transition:"
    "08ed4da1a36805bf0d68f7fcae29d874e7f38023796b4e7f666fa154b66b2452"
)
EXPECTED_EXECUTION_REPORT_ID: Final = postrun.EXPECTED_EXECUTION_REPORT_ID
EXPECTED_PRIVACY_REJECTED_JOB_ID: Final = postrun.EXPECTED_PRIVACY_REJECTED_JOB_ID
EXPECTED_ACTION_GRAMMAR_ID: Final = preflight.EXPECTED_ACTION_GRAMMAR_ID
CLASSIFIER_WHITELIST: Final = (
    "reasoning_content_length",
    "reasoning_content_present",
    "reasoning_tokens",
)
SENSITIVE_PROMPT_KEY_PATHS: Final = (
    "private_reasoning_reused",
    "response_grammar.private_reasoning_content",
)
POSTRUN_FILES: Final = (
    "destructive_audit.json",
    "independent_raw_reconstruction_audit.json",
    "outcome_interpretation.json",
    "privacy_rejection_audit.json",
    "prospective_transition_contract.json",
    "qualification_gate_audit.json",
    "report.json",
    "source_replay_audit.json",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_135_transitive_source",
        "v26_135_output",
        "v26_136_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class RootCauseSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_POSTRUN_REPORT_ID
    predecessor_source_replay_id: str = EXPECTED_POSTRUN_SOURCE_REPLAY_ID
    predecessor_transition_id: str = EXPECTED_POSTRUN_TRANSITION_ID
    predecessor_transitive_file_count: Literal[3864] = 3864
    predecessor_output_file_count: Literal[8] = 8
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[3873] = 3873
    replay_pass_count: Literal[3873] = 3873
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=3873, max_length=3873)
    replay_before_classifier_or_prompt_audit: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_s1_root_cause_source_replay.v1"] = (
        "finance_v26_s1_root_cause_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RootCauseSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.replayed_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.136 source replay changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_s1_root_cause_source_replay:"):
            raise ValueError("v26.136 source replay identity changed")
        return self


class ClassifierCaseResult(FrozenModel):
    case_id: str = Field(min_length=1)
    case_name: str = Field(min_length=1)
    feature: str = Field(min_length=1)
    expected_rejected: bool
    observed_rejected: bool
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_case(self) -> ClassifierCaseResult:
        if self.expected_rejected != self.observed_rejected:
            raise ValueError("v26.136 classifier case changed")
        if self.case_id != _identity(self, "case_id", "finance_v26_privacy_classifier_case:"):
            raise ValueError("v26.136 classifier-case identity changed")
        return self


class PrivacyClassifierTypeSystemAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    classifier_source_sha256: str = Field(min_length=64, max_length=64)
    classifier_module: str = Field(min_length=1)
    matching_rule: Literal["casefolded_mapping_key_substring_reasoning"] = (
        "casefolded_mapping_key_substring_reasoning"
    )
    matching_uses_exact_key_only: Literal[False] = False
    matching_uses_prefix_only: Literal[False] = False
    matching_uses_regular_expression: Literal[False] = False
    matching_uses_casefold: Literal[True] = True
    scans_mapping_keys: Literal[True] = True
    scans_scalar_values: Literal[False] = False
    recursively_scans_nested_mappings: Literal[True] = True
    recursively_scans_lists: Literal[True] = True
    recursively_scans_tuples: Literal[True] = True
    whitelisted_normalized_keys: tuple[str, str, str] = CLASSIFIER_WHITELIST
    analysis_key_rejected: Literal[False] = False
    thought_key_rejected: Literal[False] = False
    rationale_key_rejected: Literal[False] = False
    plan_key_rejected: Literal[False] = False
    arbitrary_scalar_value_can_trigger_rejection: Literal[False] = False
    arbitrary_mapping_key_containing_reasoning_can_trigger_rejection: Literal[True] = True
    synthetic_case_count: Literal[24] = 24
    synthetic_pass_count: Literal[24] = 24
    synthetic_rejected_case_count: Literal[10] = 10
    synthetic_accepted_case_count: Literal[14] = 14
    cases: tuple[ClassifierCaseResult, ...] = Field(min_length=24, max_length=24)
    exact_historical_rejected_payload_or_key_read: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_classifier_type_system_audit.v1"] = (
        "finance_v26_privacy_classifier_type_system_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PrivacyClassifierTypeSystemAudit:
        if (
            len(self.cases) != self.synthetic_case_count
            or sum(item.observed_rejected for item in self.cases)
            != self.synthetic_rejected_case_count
            or len({item.case_id for item in self.cases}) != self.synthetic_case_count
        ):
            raise ValueError("v26.136 classifier denominator changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_classifier_type_system_audit:"
        ):
            raise ValueError("v26.136 classifier audit identity changed")
        return self


class GrammarMutationResult(FrozenModel):
    row_id: str = Field(min_length=1)
    mutation_name: str = Field(min_length=1)
    privacy_rejected: bool
    exact_grammar_accepted: bool
    expected_privacy_rejected: bool
    expected_exact_grammar_accepted: bool

    @model_validator(mode="after")
    def validate_row(self) -> GrammarMutationResult:
        if (
            self.privacy_rejected != self.expected_privacy_rejected
            or self.exact_grammar_accepted != self.expected_exact_grammar_accepted
        ):
            raise ValueError("v26.136 Grammar mutation outcome changed")
        if self.row_id != _identity(self, "row_id", "finance_v26_action_grammar_privacy_mutation:"):
            raise ValueError("v26.136 Grammar-mutation identity changed")
        return self


class ActionGrammarPrivacyCompatibilityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    action_grammar_id: str = EXPECTED_ACTION_GRAMMAR_ID
    exact_field_order: tuple[str, str, str, str] = action_grammar.FIELD_ORDER
    all_exact_fields_are_scalar_strings: Literal[True] = True
    classifier_scans_scalar_values: Literal[False] = False
    exact_field_name_classifier_hit_count: Literal[0] = 0
    grammar_valid_implies_privacy_acceptance: Literal[True] = True
    privacy_acceptance_implies_grammar_valid: Literal[False] = False
    synthetic_legal_payload_count: Literal[16] = 16
    synthetic_legal_grammar_pass_count: Literal[16] = 16
    synthetic_legal_privacy_pass_count: Literal[16] = 16
    historical_exact_action_payload_count: Literal[141] = 141
    historical_exact_action_grammar_pass_count: Literal[141] = 141
    historical_exact_action_privacy_pass_count: Literal[141] = 141
    grammar_external_mutation_count: Literal[8] = 8
    privacy_rejecting_grammar_valid_mutation_count: Literal[0] = 0
    privacy_accepting_grammar_invalid_mutation_count: Literal[4] = 4
    mutations: tuple[GrammarMutationResult, ...] = Field(min_length=8, max_length=8)
    deterministic_grammar_classifier_incompatibility_found: Literal[False] = False
    historical_privacy_rejected_row_reclassified: Literal[False] = False
    exact_historical_rejected_payload_or_key_inferred: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_action_grammar_privacy_compatibility.v1"] = (
        "finance_v26_action_grammar_privacy_compatibility.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ActionGrammarPrivacyCompatibilityAudit:
        if (
            len(self.mutations) != self.grammar_external_mutation_count
            or any(item.privacy_rejected and item.exact_grammar_accepted for item in self.mutations)
            or self.exact_field_name_classifier_hit_count
        ):
            raise ValueError("v26.136 Grammar/privacy implication changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_action_grammar_privacy_compatibility:"
        ):
            raise ValueError("v26.136 Grammar/privacy identity changed")
        return self


class PromptPrivacyCompatibilityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    action_grammar_id: str = EXPECTED_ACTION_GRAMMAR_ID
    registered_state_count: Literal[324] = 324
    phase_prompt_counts: dict[str, int] = {
        "abi_rescue": 324,
        "primary": 324,
        "semantic_recovery": 324,
    }
    regenerated_prompt_count: Literal[972] = 972
    exact_hash_and_byte_match_count: Literal[972] = 972
    exact_state_reconstruction_count: Literal[972] = 972
    intended_four_field_payload_privacy_accept_count: Literal[972] = 972
    model_visible_classifier_sensitive_key_paths: tuple[str, str] = SENSITIVE_PROMPT_KEY_PATHS
    classifier_sensitive_key_occurrence_count: Literal[1944] = 1944
    prompts_containing_classifier_sensitive_keys: Literal[972] = 972
    full_prompt_payload_echo_privacy_rejection_count: Literal[972] = 972
    positive_output_instruction_term_count: Literal[0] = 0
    public_context_plan_substring_occurrence_count: Literal[216] = 216
    action_primary_abi_rescue_semantic_recovery_grammar_aligned: Literal[True] = True
    prompt_explicitly_forbids_private_reasoning_content: Literal[True] = True
    prompt_explicitly_marks_private_reasoning_reuse_false: Literal[True] = True
    deterministic_prompt_classifier_lexical_overlap_found: Literal[True] = True
    deterministic_s1_projection_loss_found: Literal[False] = False
    historical_privacy_rejection_attributed_to_prompt_echo: Literal[False] = False
    exact_historical_rejected_payload_or_key_read: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_s1_prompt_privacy_compatibility.v1"] = (
        "finance_v26_s1_prompt_privacy_compatibility.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PromptPrivacyCompatibilityAudit:
        if (
            sum(self.phase_prompt_counts.values()) != self.regenerated_prompt_count
            or self.classifier_sensitive_key_occurrence_count
            != self.regenerated_prompt_count
            * len(self.model_visible_classifier_sensitive_key_paths)
            or self.prompts_containing_classifier_sensitive_keys != self.regenerated_prompt_count
        ):
            raise ValueError("v26.136 Prompt/privacy denominator changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_s1_prompt_privacy_compatibility:"
        ):
            raise ValueError("v26.136 Prompt/privacy identity changed")
        return self


class AcceptedEntryBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_job_denominator: Literal[32] = 32
    accepted_first_entry_row_count: Literal[31] = 31
    omitted_privacy_rejected_row_count: Literal[1] = 1
    accepted_job_ids: tuple[str, ...] = Field(min_length=31, max_length=31)
    exact_four_field_key_set_count: Literal[31] = 31
    scalar_string_value_count: Literal[124] = 124
    maximum_payload_mapping_depth: Literal[1] = 1
    canonical_payload_utf8_byte_minimum: Literal[326] = 326
    canonical_payload_utf8_byte_median: Literal[326] = 326
    canonical_payload_utf8_byte_maximum: Literal[326] = 326
    provider_public_content_length_minimum: Literal[326] = 326
    provider_public_content_length_median: Literal[326] = 326
    provider_public_content_length_maximum: Literal[343] = 343
    first_entry_phase_counts: dict[str, int] = {"abi_rescue": 5, "primary": 26}
    first_entry_candidate_count_distribution: dict[str, int] = {"4": 9, "6": 22}
    mechanism_path_cell_count: Literal[12] = 12
    accepted_payload_privacy_pass_count: Literal[31] = 31
    accepted_payload_grammar_pass_count: Literal[31] = 31
    neighborhood_mutation_count: Literal[248] = 248
    neighborhood_privacy_rejected_count: Literal[93] = 93
    neighborhood_privacy_accepted_count: Literal[155] = 155
    neighborhood_grammar_accepted_count: Literal[31] = 31
    neighborhood_grammar_rejected_count: Literal[217] = 217
    neighborhood_privacy_rejecting_grammar_valid_count: Literal[0] = 0
    neighborhood_privacy_accepting_grammar_invalid_count: Literal[124] = 124
    accepted_historical_rows_reclassified: Literal[False] = False
    rejected_historical_row_payload_or_key_inferred: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_s1_accepted_entry_boundary_audit.v1"] = (
        "finance_v26_s1_accepted_entry_boundary_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> AcceptedEntryBoundaryAudit:
        if (
            len(self.accepted_job_ids) != self.accepted_first_entry_row_count
            or len(set(self.accepted_job_ids)) != self.accepted_first_entry_row_count
            or sum(self.first_entry_phase_counts.values()) != self.accepted_first_entry_row_count
            or sum(self.first_entry_candidate_count_distribution.values())
            != self.accepted_first_entry_row_count
            or self.neighborhood_privacy_rejected_count + self.neighborhood_privacy_accepted_count
            != self.neighborhood_mutation_count
        ):
            raise ValueError("v26.136 accepted-row boundary changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_s1_accepted_entry_boundary_audit:"
        ):
            raise ValueError("v26.136 accepted-row identity changed")
        return self


class QualificationGateDecompositionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_gate_audit_id: str = Field(min_length=1)
    exact_job_denominator: Literal[32] = 32
    observed_entry_qualified_count: Literal[31] = 31
    entry_identifiable_lower_bound: Literal[31] = 31
    entry_identifiable_upper_bound: Literal[32] = 32
    entry_quantity_gate_passed: Literal[True] = True
    cell_coverage_count: Literal[12] = 12
    cell_coverage_gate_passed: Literal[True] = True
    http_success_exact_model_thinking_usage_call_count: Literal[197] = 197
    instrument_integrity_gate_passed: Literal[True] = True
    privacy_compliant_job_count: Literal[31] = 31
    privacy_rejected_job_count: Literal[1] = 1
    privacy_gate_passed: Literal[False] = False
    overall_authorization_gate_passed: Literal[False] = False
    overall_gate_is_noncompensatory_conjunction: Literal[True] = True
    entry_quantity_and_coverage_positive_evidence_retained: Literal[True] = True
    s1_unreadable_claim_authorized: Literal[False] = False
    role_scale_readability_claim_authorized: Literal[False] = False
    capability_reachability_state_mapping_authorized: Literal[False] = False
    historical_gate_or_terminal_reclassified: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_s1_qualification_gate_decomposition.v1"] = (
        "finance_v26_s1_qualification_gate_decomposition.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> QualificationGateDecompositionAudit:
        if (
            not self.entry_quantity_gate_passed
            or not self.cell_coverage_gate_passed
            or not self.instrument_integrity_gate_passed
            or self.privacy_gate_passed
            or self.overall_authorization_gate_passed
        ):
            raise ValueError("v26.136 Gate decomposition changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_s1_qualification_gate_decomposition:"
        ):
            raise ValueError("v26.136 Gate-decomposition identity changed")
        return self


class RootCauseDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    classifier_audit_id: str = Field(min_length=1)
    grammar_compatibility_audit_id: str = Field(min_length=1)
    prompt_compatibility_audit_id: str = Field(min_length=1)
    accepted_boundary_audit_id: str = Field(min_length=1)
    gate_decomposition_audit_id: str = Field(min_length=1)
    formal_s1_representation_qualification_failed: Literal[True] = True
    entry_quantity_and_coverage_passed: Literal[True] = True
    instrument_integrity_passed: Literal[True] = True
    privacy_authorization_failed: Literal[True] = True
    action_grammar_classifier_compatibility_passed: Literal[True] = True
    deterministic_prompt_classifier_lexical_hazard_identified: Literal[True] = True
    unique_historical_privacy_rejection_cause_identified: Literal[False] = False
    privacy_classifier_false_positive_claimed: Literal[False] = False
    model_private_reasoning_leak_claimed: Literal[False] = False
    prompt_echo_claimed_for_historical_row: Literal[False] = False
    s1_general_unreadability_claimed: Literal[False] = False
    role_scale_readability_claimed: Literal[False] = False
    action_grammar_candidate_s1_model_thinking_resource_or_counter_change_supported: Literal[
        False
    ] = False
    prospective_repair_target: Literal[
        "classifier_sensitive_model_visible_prompt_metadata_only"
    ] = "classifier_sensitive_model_visible_prompt_metadata_only"
    historical_rows_reclassified: Literal[0] = 0
    role_source_model_exposure_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal[
        "prompt_classifier_lexical_hazard_found_without_historical_causal_identification"
    ] = "prompt_classifier_lexical_hazard_found_without_historical_causal_identification"
    schema_version: Literal["finance_v26_s1_privacy_root_cause_decision.v1"] = (
        "finance_v26_s1_privacy_root_cause_decision.v1"
    )

    @model_validator(mode="after")
    def validate_decision(self) -> RootCauseDecision:
        if self.decision_id != _identity(
            self, "decision_id", "finance_v26_s1_privacy_root_cause_decision:"
        ):
            raise ValueError("v26.136 root-cause decision identity changed")
        return self


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    mutation_names: tuple[str, ...] = Field(min_length=16, max_length=16)
    mutation_count: Literal[16] = 16
    rejection_count: Literal[16] = 16
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_s1_privacy_root_cause_destructive.v1"] = (
        "finance_v26_s1_privacy_root_cause_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if (
            len(self.mutation_names) != self.mutation_count
            or len(set(self.mutation_names)) != self.mutation_count
        ):
            raise ValueError("v26.136 destructive denominator changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_s1_privacy_root_cause_destructive:"
        ):
            raise ValueError("v26.136 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    root_cause_decision_id: str = Field(min_length=1)
    predecessor_transition_id: str = EXPECTED_POSTRUN_TRANSITION_ID
    next_permitted_stage: Literal[
        "fresh_s1_privacy_safe_prompt_metadata_rematerialization_and_runner_preflight_only"
    ] = NEXT_STAGE
    formal_qualification_failure_retained: Literal[True] = True
    historical_terminal_or_gate_reclassification_authorized: Literal[False] = False
    exact_rejected_payload_or_key_recovery_or_inference_authorized: Literal[False] = False
    classifier_change_authorized: Literal[False] = False
    classifier_sensitive_prompt_metadata_repair_authorized: Literal[True] = True
    fresh_model_visible_prompt_identity_required: Literal[True] = True
    fresh_taskpackage_path_contract_manifest_job_runner_execution_report_chain_required: Literal[
        True
    ] = True
    exact_s1_candidate_grammar_model_profile_and_bounds_preserved: Literal[True] = True
    future_gate_reports_entry_privacy_instrument_and_overall_separately: Literal[True] = True
    overall_privacy_gate_remains_noncompensatory: Literal[True] = True
    complete_credential_free_runner_preflight_required_before_provider: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    role_provider_calls_authorized: Literal[False] = False
    capability_reachability_state_mapping_authorized: Literal[False] = False
    training_release_or_production_authorized: Literal[False] = False
    role_source_model_exposure_count: Literal[0] = 0
    schema_version: Literal["finance_v26_s1_privacy_root_cause_transition.v1"] = (
        "finance_v26_s1_privacy_root_cause_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_s1_privacy_root_cause_transition:"
        ):
            raise ValueError("v26.136 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class RootCauseAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    predecessor_report_id: str = EXPECTED_POSTRUN_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    classifier_audit_id: str = Field(min_length=1)
    grammar_compatibility_audit_id: str = Field(min_length=1)
    prompt_compatibility_audit_id: str = Field(min_length=1)
    accepted_boundary_audit_id: str = Field(min_length=1)
    gate_decomposition_audit_id: str = Field(min_length=1)
    root_cause_decision_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=9, max_length=9)
    formal_s1_representation_qualification_passed: Literal[False] = False
    entry_quantity_gate_passed: Literal[True] = True
    cell_coverage_gate_passed: Literal[True] = True
    instrument_integrity_gate_passed: Literal[True] = True
    privacy_gate_passed: Literal[False] = False
    grammar_classifier_compatibility_passed: Literal[True] = True
    deterministic_prompt_classifier_lexical_hazard_identified: Literal[True] = True
    unique_historical_rejection_cause_identified: Literal[False] = False
    historical_rows_reclassified: Literal[0] = 0
    role_source_model_exposure_count: Literal[0] = 0
    capability_rows: Literal[0] = 0
    reachability_rows: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    production_contribution: Literal[0] = 0
    next_permitted_stage: str = NEXT_STAGE
    status: Literal[
        "prompt_classifier_lexical_hazard_found_without_historical_causal_identification"
    ] = "prompt_classifier_lexical_hazard_found_without_historical_causal_identification"
    schema_version: Literal["finance_v26_s1_privacy_root_cause_audit_report.v1"] = (
        "finance_v26_s1_privacy_root_cause_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> RootCauseAuditReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_s1_privacy_root_cause_audit_report:",
        ):
            raise ValueError("v26.136 report identity changed")
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
    raise ValueError(f"v26.136 cannot replay bound file: {relative_path}")


def _build_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    postrun_dir: Path,
) -> RootCauseSourceReplayAudit:
    report_path = postrun_dir / "report.json"
    report = postrun.PostrunAuditReport.model_validate(_load(report_path))
    source = postrun.PostrunSourceReplayAudit.model_validate(
        _load(postrun_dir / "source_replay_audit.json")
    )
    transition = postrun.ProspectiveTransitionContract.model_validate(
        _load(postrun_dir / "prospective_transition_contract.json")
    )
    if (
        report.report_id != EXPECTED_POSTRUN_REPORT_ID
        or _sha256(report_path) != EXPECTED_POSTRUN_REPORT_SHA256
        or source.audit_id != EXPECTED_POSTRUN_SOURCE_REPLAY_ID
        or transition.contract_id != EXPECTED_POSTRUN_TRANSITION_ID
        or not transition.credential_free_root_cause_audit_authorized
        or transition.provider_calls_authorized
    ):
        raise ValueError("v26.136 predecessor authorization changed")
    expected_details = {item.relative_path: item.sha256 for item in report.detail_files}
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
            source_kind="v26_135_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
    for name in POSTRUN_FILES:
        path = postrun_dir / name
        expected = (
            EXPECTED_POSTRUN_REPORT_SHA256 if name == "report.json" else expected_details[name]
        )
        relative = str(path.relative_to(package_root))
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_135_output",
            expected_sha256=expected,
            observed_sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
    implementation = implementation_root / IMPLEMENTATION_PATH
    relative = str(implementation.relative_to(implementation_root))
    entries[relative] = SourceReplayEntry(
        relative_path=relative,
        source_kind="v26_136_implementation",
        expected_sha256=_sha256(implementation),
        observed_sha256=_sha256(implementation),
        byte_count=implementation.stat().st_size,
    )
    ordered = tuple(entries[key] for key in sorted(entries))
    provisional = RootCauseSourceReplayAudit.model_construct(audit_id="pending", entries=ordered)
    return RootCauseSourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_s1_root_cause_source_replay:",
        ),
        entries=ordered,
    )


def _classifier_case(
    case_name: str,
    feature: str,
    payload: Any,
    expected: bool,
) -> ClassifierCaseResult:
    values = {
        "case_name": case_name,
        "feature": feature,
        "expected_rejected": expected,
        "observed_rejected": legacy.contains_private_reasoning(payload),
    }
    provisional = ClassifierCaseResult.model_construct(case_id="pending", **values)
    return ClassifierCaseResult(
        case_id=_identity(provisional, "case_id", "finance_v26_privacy_classifier_case:"),
        **values,
    )


def _make_classifier_audit() -> PrivacyClassifierTypeSystemAudit:
    cases = (
        _classifier_case("clean_action", "clean_mapping", {"action_id": "a"}, False),
        _classifier_case("exact_marker", "exact_substring", {"reasoning": "x"}, True),
        _classifier_case("casefold_marker", "casefold", {"ReAsOnInG": "x"}, True),
        _classifier_case("prefix_marker", "prefix", {"pre_reasoning": "x"}, True),
        _classifier_case("suffix_marker", "suffix", {"reasoning_post": "x"}, True),
        _classifier_case("middle_marker", "middle_substring", {"pre_reasoning_post": "x"}, True),
        _classifier_case("analysis_key", "near_term", {"analysis": "x"}, False),
        _classifier_case("thought_key", "near_term", {"thought": "x"}, False),
        _classifier_case("rationale_key", "near_term", {"rationale": "x"}, False),
        _classifier_case("plan_key", "near_term", {"plan": "x"}, False),
        _classifier_case("reason_key", "near_term", {"reason": "x"}, False),
        _classifier_case(
            "whitelist_present", "whitelist", {"reasoning_content_present": True}, False
        ),
        _classifier_case("whitelist_length", "whitelist", {"reasoning_content_length": 1}, False),
        _classifier_case("whitelist_tokens", "whitelist", {"reasoning_tokens": 1}, False),
        _classifier_case(
            "nonwhitelist_content", "near_whitelist", {"reasoning_content": "x"}, True
        ),
        _classifier_case(
            "marker_in_scalar_value", "value_not_scanned", {"note": "reasoning"}, False
        ),
        _classifier_case(
            "marker_in_json_string",
            "value_not_parsed",
            {"note": '{"reasoning":"x"}'},
            False,
        ),
        _classifier_case(
            "nested_mapping", "mapping_recursion", {"outer": {"reasoning": "x"}}, True
        ),
        _classifier_case("nested_list", "list_recursion", {"outer": [{"reasoning": "x"}]}, True),
        _classifier_case("nested_tuple", "tuple_recursion", {"outer": ({"reasoning": "x"},)}, True),
        _classifier_case("numeric_key", "key_stringification", {1: "x"}, False),
        _classifier_case("nested_clean", "mapping_recursion", {"outer": {"note": "x"}}, False),
        _classifier_case(
            "casefold_whitelist", "whitelist_after_casefold", {"Reasoning_Tokens": 1}, False
        ),
        _classifier_case(
            "camel_marker", "substring_without_separator", {"reasoningTokens": 1}, True
        ),
    )
    source = inspect.getsource(legacy.contains_private_reasoning)
    required = (
        "isinstance(value, Mapping)",
        ".casefold()",
        '"reasoning" in normalized',
        "contains_private_reasoning(item)",
        "isinstance(value, (list, tuple))",
    )
    if any(item not in source for item in required):
        raise ValueError("v26.136 classifier source shape changed")
    values = {
        "classifier_source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "classifier_module": legacy.contains_private_reasoning.__module__,
        "cases": cases,
    }
    provisional = PrivacyClassifierTypeSystemAudit.model_construct(audit_id="pending", **values)
    return PrivacyClassifierTypeSystemAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_classifier_type_system_audit:",
        ),
        **values,
    )


def _grammar_accepts(payload: Mapping[str, Any]) -> bool:
    try:
        action_grammar.parse_exact_canonical_action_payload(payload)
    except action_grammar.SemanticActionResponseRejection:
        return False
    return True


def _load_execution_rows(
    execution_dir: Path,
) -> tuple[
    preflight.S1QualificationManifest,
    tuple[execution.QualificationJobResult, ...],
    tuple[preflight.S1QualificationRawExecution, ...],
]:
    manifest = preflight.S1QualificationManifest.model_validate(
        _load(execution_dir / "frozen_s1_qualification_manifest.json")
    )
    results = tuple(
        execution.QualificationJobResult.model_validate(item)
        for item in cast(list[Any], _load(execution_dir / "s1_qualification_job_results.json"))
    )
    raws = tuple(
        preflight.S1QualificationRawExecution.model_validate(
            _load(execution_dir / result.raw_execution_artifact.relative_path)
        )
        for result in results
    )
    if (
        len(results) != 32
        or len(raws) != 32
        or tuple(item.job_id for item in results) != tuple(item.job_id for item in manifest.jobs)
        or any(raw.job != job for raw, job in zip(raws, manifest.jobs, strict=True))
    ):
        raise ValueError("v26.136 execution denominator changed")
    return manifest, results, raws


def _provider_pair(
    raw: preflight.S1QualificationRawExecution,
    call_index: int,
    execution_dir: Path,
) -> tuple[privacy_runner.PrivacyFirstProviderEnvelope, privacy_runner.PublicPayloadProjection]:
    envelope_descriptor = raw.provider_envelope_artifacts[call_index]
    projection_descriptor = raw.public_payload_projection_artifacts[call_index]
    envelope_path = execution_dir / envelope_descriptor.relative_path
    projection_path = execution_dir / projection_descriptor.relative_path
    if (
        _sha256(envelope_path) != envelope_descriptor.sha256
        or _sha256(projection_path) != projection_descriptor.sha256
    ):
        raise ValueError("v26.136 Provider-pair descriptor changed")
    envelope = privacy_runner.PrivacyFirstProviderEnvelope.model_validate(_load(envelope_path))
    projection = privacy_runner.PublicPayloadProjection.model_validate(_load(projection_path))
    privacy_runner.validate_provider_artifact_pair(envelope, projection)
    return envelope, projection


def _historical_exact_action_payloads(
    raws: Sequence[preflight.S1QualificationRawExecution],
    execution_dir: Path,
) -> tuple[dict[str, Any], ...]:
    payloads: list[dict[str, Any]] = []
    for raw in raws:
        for attempt in raw.attempts:
            if not attempt.exact_four_field_action_payload:
                continue
            if attempt.provider_call_index is None:
                raise ValueError("v26.136 exact Action attempt lacks Provider index")
            _, projection = _provider_pair(raw, attempt.provider_call_index, execution_dir)
            if (
                projection.projection_status != "validated_public_payload"
                or projection.response_payload is None
            ):
                raise ValueError("v26.136 exact Action payload lacks public Projection")
            payloads.append(dict(projection.response_payload))
    if len(payloads) != 141:
        raise ValueError("v26.136 exact Action denominator changed")
    return tuple(payloads)


def _grammar_mutation(
    mutation_name: str,
    payload: Mapping[str, Any],
    expected_privacy: bool,
    expected_grammar: bool,
) -> GrammarMutationResult:
    values = {
        "mutation_name": mutation_name,
        "privacy_rejected": legacy.contains_private_reasoning(payload),
        "exact_grammar_accepted": _grammar_accepts(payload),
        "expected_privacy_rejected": expected_privacy,
        "expected_exact_grammar_accepted": expected_grammar,
    }
    provisional = GrammarMutationResult.model_construct(row_id="pending", **values)
    return GrammarMutationResult(
        row_id=_identity(
            provisional,
            "row_id",
            "finance_v26_action_grammar_privacy_mutation:",
        ),
        **values,
    )


def _make_grammar_audit(
    historical_payloads: Sequence[Mapping[str, Any]],
) -> ActionGrammarPrivacyCompatibilityAudit:
    grammar = action_grammar.compile_semantic_action_response_grammar()
    if grammar.grammar_id != EXPECTED_ACTION_GRAMMAR_ID:
        raise ValueError("v26.136 Action Grammar changed")
    decisions = (
        "acquire_public_input",
        "emit_final_answer",
        "execute_public_operation",
        "verify_terminal_operation",
    )
    synthetic: list[dict[str, Any]] = []
    for decision in decisions:
        for index in range(4):
            synthetic.append(
                {
                    "state_id": f"synthetic-reasoning-state-{index}",
                    "action_id": f"synthetic-reasoning-action-{index}",
                    "decision_kind": decision,
                    "protocol": action_grammar.RESPONSE_PROTOCOL_VERSION,
                }
            )
    if any(not _grammar_accepts(item) for item in synthetic) or any(
        legacy.contains_private_reasoning(item) for item in synthetic
    ):
        raise ValueError("v26.136 synthetic legal Grammar/privacy implication failed")
    if any(not _grammar_accepts(item) for item in historical_payloads) or any(
        legacy.contains_private_reasoning(item) for item in historical_payloads
    ):
        raise ValueError("v26.136 historical exact Action/privacy implication failed")
    baseline = dict(historical_payloads[0])
    mutations = (
        _grammar_mutation(
            "extra_analysis_key", {**baseline, "analysis": "synthetic"}, False, False
        ),
        _grammar_mutation(
            "extra_reasoning_key", {**baseline, "reasoning": "synthetic"}, True, False
        ),
        _grammar_mutation(
            "extra_casefold_reasoning_key",
            {**baseline, "ReasoningTrace": "synthetic"},
            True,
            False,
        ),
        _grammar_mutation(
            "nested_reasoning_key",
            {**baseline, "action_id": {"reasoning": "synthetic"}},
            True,
            False,
        ),
        _grammar_mutation(
            "extra_whitelisted_reasoning_tokens",
            {**baseline, "reasoning_tokens": 1},
            False,
            False,
        ),
        _grammar_mutation("wrapper", {"response": baseline}, False, False),
        _grammar_mutation(
            "missing_protocol",
            {key: value for key, value in baseline.items() if key != "protocol"},
            False,
            False,
        ),
        _grammar_mutation(
            "reasoning_substring_in_scalar_value",
            {**baseline, "state_id": f"{baseline['state_id']}-reasoning"},
            False,
            True,
        ),
    )
    values = {"mutations": mutations}
    provisional = ActionGrammarPrivacyCompatibilityAudit.model_construct(
        audit_id="pending", **values
    )
    return ActionGrammarPrivacyCompatibilityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_action_grammar_privacy_compatibility:",
        ),
        **values,
    )


def _walk_prompt(
    value: Any,
    *,
    path: tuple[str, ...] = (),
) -> tuple[list[str], Counter[str]]:
    sensitive: list[str] = []
    terms: Counter[str] = Counter()
    if isinstance(value, Mapping):
        for key, item in value.items():
            next_path = path + (str(key),)
            normalized = str(key).casefold()
            if "reasoning" in normalized and normalized not in CLASSIFIER_WHITELIST:
                sensitive.append(".".join(next_path))
            nested_sensitive, nested_terms = _walk_prompt(item, path=next_path)
            sensitive.extend(nested_sensitive)
            terms.update(nested_terms)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            nested_sensitive, nested_terms = _walk_prompt(item, path=path + (f"[{index}]",))
            sensitive.extend(nested_sensitive)
            terms.update(nested_terms)
    elif isinstance(value, str):
        lowered = value.casefold()
        for term in ("analysis", "reasoning", "rationale", "thought", "plan"):
            if term in lowered:
                terms[term] += 1
    return sensitive, terms


def _make_prompt_audit(
    *,
    package_root: Path,
    implementation_root: Path,
) -> PromptPrivacyCompatibilityAudit:
    loaded = preflight._load_inputs(package_root, implementation_root)  # noqa: SLF001
    static = loaded.engineering
    catalog = preflight._make_path_catalog(loaded)  # noqa: SLF001
    formal_catalog = preflight.S1QualificationPathCatalog.model_validate(
        _load(package_root / preflight.OUTPUT_DIR / "s1_qualification_path_catalog.json")
    )
    if catalog != formal_catalog:
        raise ValueError("v26.136 frozen S1 path catalog changed")
    path_map = preflight._material_to_final_path_ids(static)  # noqa: SLF001
    catalog_paths = {item.predecessor_path_audit_id: item for item in catalog.paths}
    phase_counts: Counter[str] = Counter()
    sensitive_paths: Counter[str] = Counter()
    term_counts: Counter[str] = Counter()
    hash_matches = 0
    state_matches = 0
    intended_privacy_passes = 0
    echo_rejections = 0
    positive_output_terms = 0
    explicit_private_content_forbids = 0
    explicit_private_reuse_false = 0
    grammar_surfaces: set[str] = set()
    exact_prefixes = {
        "abi_rescue": (
            "Correct only the response ABI and return exactly one four-field JSON object."
        ),
        "primary": "Select one visible action and return exactly one four-field JSON object.",
        "semantic_recovery": (
            "Use the public rejection and select one visible action as a four-field JSON object."
        ),
    }
    for material in loaded.engineering_materials:
        final_path_id = path_map[material.predecessor_path.audit_id]
        path = catalog_paths[final_path_id]
        binding = material.binding
        condition = (
            None
            if binding.source_path.role == "capability"
            else binding.source_path.path_strategy_id
        )
        for index, state in enumerate(material.states):
            row = path.state_rows[index]
            salt = canonical_hash(
                {
                    "predecessor_report_id": preflight.EXPECTED_PREDECESSOR_REPORT_ID,
                    "engineering_path_id": final_path_id,
                    "state_id": state.state_id,
                    "logical_index": index,
                },
                prefix="finance_v26_s1_qualification_candidate_presentation:",
            )
            for phase in ("primary", "abi_rescue", "semantic_recovery"):
                typed_failure = (
                    None
                    if phase == "primary"
                    else {
                        "family": (
                            "response_serialization_failure"
                            if phase == "abi_rescue"
                            else "semantic_action_rejection"
                        ),
                        "subtype": (
                            "canonical_action_not_exact_four_field_grammar"
                            if phase == "abi_rescue"
                            else "fixture_typed_semantic_rejection"
                        ),
                    }
                )
                prompt = preflight.predecessor.predecessor._compact_action_prompt(  # noqa: SLF001
                    phase=cast(Any, phase),
                    instruction=binding.record.task_package.task.public.instruction,
                    state=state,
                    public_path_condition=condition,
                    presentation_salt=salt,
                    typed_failure=typed_failure,
                    grammar=static.action_grammar,
                )
                prefix, separator, serialized = prompt.partition("\n")
                if separator != "\n" or prefix != exact_prefixes[phase]:
                    raise ValueError("v26.136 exact output instruction changed")
                payload = json.loads(serialized)
                expected_hash = getattr(row, f"{phase}_prompt_sha256")
                expected_bytes = getattr(row, f"{phase}_prompt_utf8_bytes")
                hash_matches += int(
                    legacy.sha256_text(prompt) == expected_hash
                    and len(prompt.encode("utf-8")) == expected_bytes
                )
                decoded, _ = (
                    preflight.predecessor.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001
                        prompt,
                        presentation_salt=salt,
                    )
                )
                state_matches += int(decoded == state)
                proposal = preflight.predecessor.predecessor._compact_reference_proposal(  # noqa: SLF001
                    prompt,
                    presentation_salt=salt,
                )
                intended = action_grammar.exact_canonical_action_payload(proposal)
                intended_privacy_passes += int(
                    _grammar_accepts(intended) and not legacy.contains_private_reasoning(intended)
                )
                response_grammar = payload.get("response_grammar")
                _, output_terms = _walk_prompt(
                    {"prefix": prefix, "response_grammar": response_grammar}
                )
                positive_output_terms += sum(output_terms.values())
                grammar_surfaces.add(hashlib.sha256(_canonical_bytes(response_grammar)).hexdigest())
                explicit_private_content_forbids += int(
                    isinstance(response_grammar, Mapping)
                    and response_grammar.get("private_reasoning_content") == "not_allowed"
                )
                explicit_private_reuse_false += int(
                    payload.get("private_reasoning_reused") is False
                )
                sensitive, terms = _walk_prompt(payload)
                sensitive_paths.update(sensitive)
                term_counts.update(terms)
                echo_rejections += int(legacy.contains_private_reasoning(payload))
                phase_counts[phase] += 1
    if (
        hash_matches != 972
        or state_matches != 972
        or intended_privacy_passes != 972
        or tuple(sorted(sensitive_paths)) != SENSITIVE_PROMPT_KEY_PATHS
        or sum(sensitive_paths.values()) != 1944
        or sensitive_paths != Counter({key: 972 for key in SENSITIVE_PROMPT_KEY_PATHS})
        or echo_rejections != 972
        or term_counts != Counter({"plan": 216})
        or positive_output_terms != 0
        or len(grammar_surfaces) != 1
        or explicit_private_content_forbids != 972
        or explicit_private_reuse_false != 972
    ):
        raise ValueError(
            "v26.136 Prompt/privacy surface changed: "
            f"sensitive={sensitive_paths} terms={term_counts}"
        )
    values: dict[str, Any] = {
        "positive_output_instruction_term_count": positive_output_terms,
    }
    provisional = PromptPrivacyCompatibilityAudit.model_construct(audit_id="pending", **values)
    return PromptPrivacyCompatibilityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_s1_prompt_privacy_compatibility:",
        ),
        **values,
    )


def _mapping_depth(value: Any) -> int:
    if isinstance(value, Mapping):
        return 1 + max((_mapping_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return max((_mapping_depth(item) for item in value), default=0)
    return 0


def _accepted_rows(
    manifest: preflight.S1QualificationManifest,
    results: Sequence[execution.QualificationJobResult],
    raws: Sequence[preflight.S1QualificationRawExecution],
    execution_dir: Path,
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for job, result, raw in zip(manifest.jobs, results, raws, strict=True):
        if not result.first_action_interface_qualified:
            continue
        first = raw.semantic_choices[0]
        usable = next(
            item
            for item in raw.attempts
            if item.request_kind == "semantic_proposal"
            and item.logical_request_index == first.logical_request_index
            and item.disposition == "usable"
        )
        if usable.provider_call_index is None:
            raise ValueError("v26.136 accepted first row lacks Provider index")
        envelope, projection = _provider_pair(raw, usable.provider_call_index, execution_dir)
        if projection.response_payload is None:
            raise ValueError("v26.136 accepted first row lacks public Payload")
        rows.append(
            {
                "job": job,
                "result": result,
                "attempt": usable,
                "payload": dict(projection.response_payload),
                "envelope": envelope,
            }
        )
    if len(rows) != 31:
        raise ValueError("v26.136 accepted-entry denominator changed")
    return tuple(rows)


def _boundary_mutations(payload: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    return (
        {**payload, "analysis": "synthetic"},
        {**payload, "reasoning": "synthetic"},
        {**payload, "ReasoningTrace": "synthetic"},
        {**payload, "action_id": {"reasoning": "synthetic"}},
        {**payload, "reasoning_tokens": 1},
        {"response": dict(payload)},
        {key: value for key, value in payload.items() if key != "protocol"},
        {**payload, "state_id": f"{payload['state_id']}-reasoning"},
    )


def _make_boundary_audit(rows: Sequence[Mapping[str, Any]]) -> AcceptedEntryBoundaryAudit:
    phases: Counter[str] = Counter()
    candidates: Counter[str] = Counter()
    cells: set[str] = set()
    canonical_lengths: list[int] = []
    content_lengths: list[int] = []
    privacy_rejected = 0
    privacy_accepted = 0
    grammar_accepted = 0
    grammar_rejected = 0
    reject_and_valid = 0
    accept_and_invalid = 0
    job_ids: list[str] = []
    depths: list[int] = []
    value_count = 0
    for row in rows:
        job = cast(preflight.S1QualificationJob, row["job"])
        result = cast(execution.QualificationJobResult, row["result"])
        attempt = cast(privacy_runner.PrivacyFirstAttempt, row["attempt"])
        payload = cast(dict[str, Any], row["payload"])
        envelope = cast(privacy_runner.PrivacyFirstProviderEnvelope, row["envelope"])
        if (
            tuple(sorted(payload)) != tuple(sorted(action_grammar.FIELD_ORDER))
            or not all(isinstance(item, str) for item in payload.values())
            or legacy.contains_private_reasoning(payload)
            or not _grammar_accepts(payload)
        ):
            raise ValueError("v26.136 accepted entry row changed")
        job_ids.append(job.job_id)
        phases[attempt.public_attempt_phase] += 1
        candidates[str(result.first_action_candidate_count)] += 1
        cells.add(result.mechanism_path_cell)
        canonical_lengths.append(len(_canonical_bytes(payload)))
        content_lengths.append(envelope.public_content_length or 0)
        depths.append(_mapping_depth(payload))
        value_count += len(payload)
        for mutation in _boundary_mutations(payload):
            rejected = legacy.contains_private_reasoning(mutation)
            valid = _grammar_accepts(mutation)
            privacy_rejected += int(rejected)
            privacy_accepted += int(not rejected)
            grammar_accepted += int(valid)
            grammar_rejected += int(not valid)
            reject_and_valid += int(rejected and valid)
            accept_and_invalid += int(not rejected and not valid)
    content_sorted = sorted(content_lengths)
    if (
        phases != Counter({"primary": 26, "abi_rescue": 5})
        or candidates != Counter({"6": 22, "4": 9})
        or len(cells) != 12
        or set(canonical_lengths) != {326}
        or (min(content_lengths), content_sorted[len(content_sorted) // 2], max(content_lengths))
        != (326, 326, 343)
        or set(depths) != {1}
        or value_count != 124
        or (privacy_rejected, privacy_accepted, grammar_accepted, grammar_rejected)
        != (93, 155, 31, 217)
        or reject_and_valid != 0
        or accept_and_invalid != 124
    ):
        raise ValueError("v26.136 accepted boundary results changed")
    values = {"accepted_job_ids": tuple(sorted(job_ids))}
    provisional = AcceptedEntryBoundaryAudit.model_construct(audit_id="pending", **values)
    return AcceptedEntryBoundaryAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_s1_accepted_entry_boundary_audit:",
        ),
        **values,
    )


def _make_gate_decomposition(postrun_dir: Path) -> QualificationGateDecompositionAudit:
    gate = postrun.QualificationGateAudit.model_validate(
        _load(postrun_dir / "qualification_gate_audit.json")
    )
    privacy = postrun.PrivacyRejectionAudit.model_validate(
        _load(postrun_dir / "privacy_rejection_audit.json")
    )
    if (
        not gate.entry_quantity_gate_passed
        or not gate.entry_cell_coverage_gate_passed
        or gate.zero_integrity_failure_gate_passed
        or gate.representation_qualification_gate_passed
        or privacy.rejected_job_id != EXPECTED_PRIVACY_REJECTED_JOB_ID
        or privacy.exact_rejected_payload_persisted
        or privacy.exact_rejected_key_persisted
    ):
        raise ValueError("v26.136 predecessor Gate interpretation changed")
    values = {"predecessor_gate_audit_id": gate.audit_id}
    provisional = QualificationGateDecompositionAudit.model_construct(audit_id="pending", **values)
    return QualificationGateDecompositionAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_s1_qualification_gate_decomposition:",
        ),
        **values,
    )


def _make_decision(
    classifier: PrivacyClassifierTypeSystemAudit,
    grammar: ActionGrammarPrivacyCompatibilityAudit,
    prompt: PromptPrivacyCompatibilityAudit,
    boundary: AcceptedEntryBoundaryAudit,
    gate: QualificationGateDecompositionAudit,
) -> RootCauseDecision:
    values = {
        "classifier_audit_id": classifier.audit_id,
        "grammar_compatibility_audit_id": grammar.audit_id,
        "prompt_compatibility_audit_id": prompt.audit_id,
        "accepted_boundary_audit_id": boundary.audit_id,
        "gate_decomposition_audit_id": gate.audit_id,
    }
    provisional = RootCauseDecision.model_construct(decision_id="pending", **values)
    return RootCauseDecision(
        decision_id=_identity(
            provisional,
            "decision_id",
            "finance_v26_s1_privacy_root_cause_decision:",
        ),
        **values,
    )


def _rejects(call: Callable[[], Any]) -> bool:
    try:
        call()
    except (TypeError, ValueError):
        return True
    return False


def _make_destructive(
    *,
    classifier: PrivacyClassifierTypeSystemAudit,
    grammar: ActionGrammarPrivacyCompatibilityAudit,
    prompt: PromptPrivacyCompatibilityAudit,
    boundary: AcceptedEntryBoundaryAudit,
    gate: QualificationGateDecompositionAudit,
    decision: RootCauseDecision,
) -> DestructiveAudit:
    mutations: tuple[tuple[str, Callable[[], Any]], ...] = (
        (
            "classifier_value_scan_claim",
            lambda: PrivacyClassifierTypeSystemAudit.model_validate(
                classifier.model_copy(update={"scans_scalar_values": True}).model_dump(mode="json")
            ),
        ),
        (
            "classifier_case_count_change",
            lambda: PrivacyClassifierTypeSystemAudit.model_validate(
                classifier.model_copy(update={"synthetic_case_count": 23}).model_dump(mode="json")
            ),
        ),
        (
            "grammar_classifier_incompatibility_claim",
            lambda: ActionGrammarPrivacyCompatibilityAudit.model_validate(
                grammar.model_copy(
                    update={"deterministic_grammar_classifier_incompatibility_found": True}
                ).model_dump(mode="json")
            ),
        ),
        (
            "grammar_historical_reclassification",
            lambda: ActionGrammarPrivacyCompatibilityAudit.model_validate(
                grammar.model_copy(
                    update={"historical_privacy_rejected_row_reclassified": True}
                ).model_dump(mode="json")
            ),
        ),
        (
            "prompt_sensitive_key_count_zero",
            lambda: PromptPrivacyCompatibilityAudit.model_validate(
                prompt.model_copy(
                    update={"classifier_sensitive_key_occurrence_count": 0}
                ).model_dump(mode="json")
            ),
        ),
        (
            "prompt_historical_echo_attribution",
            lambda: PromptPrivacyCompatibilityAudit.model_validate(
                prompt.model_copy(
                    update={"historical_privacy_rejection_attributed_to_prompt_echo": True}
                ).model_dump(mode="json")
            ),
        ),
        (
            "accepted_row_denominator_change",
            lambda: AcceptedEntryBoundaryAudit.model_validate(
                boundary.model_copy(update={"accepted_first_entry_row_count": 32}).model_dump(
                    mode="json"
                )
            ),
        ),
        (
            "rejected_key_inference_claim",
            lambda: AcceptedEntryBoundaryAudit.model_validate(
                boundary.model_copy(
                    update={"rejected_historical_row_payload_or_key_inferred": True}
                ).model_dump(mode="json")
            ),
        ),
        (
            "entry_quantity_fail_claim",
            lambda: QualificationGateDecompositionAudit.model_validate(
                gate.model_copy(update={"entry_quantity_gate_passed": False}).model_dump(
                    mode="json"
                )
            ),
        ),
        (
            "privacy_gate_pass_claim",
            lambda: QualificationGateDecompositionAudit.model_validate(
                gate.model_copy(update={"privacy_gate_passed": True}).model_dump(mode="json")
            ),
        ),
        (
            "overall_gate_pass_claim",
            lambda: QualificationGateDecompositionAudit.model_validate(
                gate.model_copy(update={"overall_authorization_gate_passed": True}).model_dump(
                    mode="json"
                )
            ),
        ),
        (
            "s1_unreadable_claim",
            lambda: QualificationGateDecompositionAudit.model_validate(
                gate.model_copy(update={"s1_unreadable_claim_authorized": True}).model_dump(
                    mode="json"
                )
            ),
        ),
        (
            "classifier_false_positive_claim",
            lambda: RootCauseDecision.model_validate(
                decision.model_copy(
                    update={"privacy_classifier_false_positive_claimed": True}
                ).model_dump(mode="json")
            ),
        ),
        (
            "model_reasoning_leak_claim",
            lambda: RootCauseDecision.model_validate(
                decision.model_copy(
                    update={"model_private_reasoning_leak_claimed": True}
                ).model_dump(mode="json")
            ),
        ),
        (
            "role_readability_claim",
            lambda: RootCauseDecision.model_validate(
                decision.model_copy(update={"role_scale_readability_claimed": True}).model_dump(
                    mode="json"
                )
            ),
        ),
        (
            "provider_call_claim",
            lambda: RootCauseDecision.model_validate(
                decision.model_copy(update={"provider_calls": 1}).model_dump(mode="json")
            ),
        ),
    )
    rejected = tuple(name for name, call in mutations if _rejects(call))
    if len(rejected) != len(mutations):
        raise ValueError("v26.136 destructive mutation escaped")
    values = {"decision_id": decision.decision_id, "mutation_names": rejected}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_s1_privacy_root_cause_destructive:",
        ),
        **values,
    )


def _make_transition(decision: RootCauseDecision) -> ProspectiveTransitionContract:
    values = {"root_cause_decision_id": decision.decision_id}
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_s1_privacy_root_cause_transition:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_root_cause_audit(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
    postrun_dir: Path,
    output_dir: Path,
) -> RootCauseAuditReport:
    source = _build_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        postrun_dir=postrun_dir,
    )
    classifier = _make_classifier_audit()
    manifest, results, raws = _load_execution_rows(execution_dir)
    historical_payloads = _historical_exact_action_payloads(raws, execution_dir)
    grammar = _make_grammar_audit(historical_payloads)
    prompt = _make_prompt_audit(
        package_root=package_root,
        implementation_root=implementation_root,
    )
    rows = _accepted_rows(manifest, results, raws, execution_dir)
    boundary = _make_boundary_audit(rows)
    gate = _make_gate_decomposition(postrun_dir)
    decision = _make_decision(classifier, grammar, prompt, boundary, gate)
    destructive = _make_destructive(
        classifier=classifier,
        grammar=grammar,
        prompt=prompt,
        boundary=boundary,
        gate=gate,
        decision=decision,
    )
    transition = _make_transition(decision)
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_values: tuple[tuple[str, BaseModel], ...] = (
        ("accepted_entry_boundary_audit.json", boundary),
        ("action_grammar_privacy_compatibility_audit.json", grammar),
        ("destructive_audit.json", destructive),
        ("privacy_classifier_type_system_audit.json", classifier),
        ("prompt_privacy_compatibility_audit.json", prompt),
        ("prospective_transition_contract.json", transition),
        ("qualification_gate_decomposition_audit.json", gate),
        ("root_cause_decision.json", decision),
        ("source_replay_audit.json", source),
    )
    for name, value in detail_values:
        _write_json_atomic(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in detail_values)
    values = {
        "source_replay_audit_id": source.audit_id,
        "classifier_audit_id": classifier.audit_id,
        "grammar_compatibility_audit_id": grammar.audit_id,
        "prompt_compatibility_audit_id": prompt.audit_id,
        "accepted_boundary_audit_id": boundary.audit_id,
        "gate_decomposition_audit_id": gate.audit_id,
        "root_cause_decision_id": decision.decision_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = RootCauseAuditReport.model_construct(report_id="pending", **values)
    report = RootCauseAuditReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_s1_privacy_root_cause_audit_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Credential-free v26.136 S1/privacy compatibility root-cause audit"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--execution-dir", type=Path, default=package_default / EXECUTION_DIR)
    parser.add_argument("--postrun-dir", type=Path, default=package_default / POSTRUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    args = parser.parse_args()
    report = build_root_cause_audit(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        execution_dir=args.execution_dir,
        postrun_dir=args.postrun_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
