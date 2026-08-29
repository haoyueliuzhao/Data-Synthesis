from __future__ import annotations

from typing import Any, Final, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.executed_counterfactual_outcome_closure import (
    REQUIRED_CAPABILITY_OUTCOME_FIELDS,
    CapabilityEstimandEvaluation,
    CapabilityOutcomeRow,
)
from trusted_synthesis.hashing import canonical_hash

V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION: Final = (
    "executed_counterfactual_valid_control_outcome_closure.v1"
)
AUTHORIZED_STAGE: Final = (
    "capability_observation_executed_counterfactual_valid_control_"
    "and_outcome_row_contract_closure_only"
)
BLOCKED_PREDECESSOR_STAGE: Final = (
    "capability_observation_public_feedback_closed_all_typed_rejection_"
    "correction_bound_state_bound_step_runtime_development_runner_preflight_only"
)
NEXT_STAGE: Final = "no_further_experiment_authorized_without_new_audit_decision"
REGISTERED_REJECTION_BRANCHES: Final = (
    ("revise_selector", "typed_current_state_target_mismatch"),
    ("revise_selector", "typed_failure_receipt_mismatch"),
    ("reconcile_record", "typed_current_state_target_mismatch"),
    ("consume_normalized_output", "typed_current_state_target_mismatch"),
    ("assess_dynamic_readiness", "typed_current_state_target_mismatch"),
)
HOST_COUNTERFACTUAL_INTERVENTIONS: Final = (
    "package_id",
    "component_key",
    "source_choice_handle",
    "selected_operation_hash",
    "action_acceptance_report",
    "runtime_event_identities",
    "joint_all_host_parents",
)

T = TypeVar("T", bound=BaseModel)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


def make_identity_model(
    model_type: type[T],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> T:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: identity(provisional, field, prefix)}, **values)


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)
    source_kind: Literal[
        "external_audit_input",
        "predecessor_artifact",
        "implementation_source",
        "formal_output",
    ]


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_byte_count: int = Field(gt=0)
    authorized_stage: Literal[
        "capability_observation_executed_counterfactual_valid_control_"
        "and_outcome_row_contract_closure_only"
    ] = AUTHORIZED_STAGE
    predecessor_runner_preflight_consumption_authorized: Literal[False] = False
    manifest_authorized: Literal[False] = False
    runner_authorized: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    development_jobs_authorized: Literal[False] = False
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_executed_counterfactual_external_authorization:",
        ):
            raise ValueError("v26.178 external Authorization identity is invalid")
        return self


class V177PredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    predecessor_files: tuple[FileBinding, ...] = Field(min_length=15, max_length=15)
    predecessor_file_count: Literal[15] = 15
    independent_rebuild_match_count: Literal[15] = 15
    predecessor_mutation_count: Literal[0] = 0
    blocked_runner_preflight_transition: str = Field(min_length=1)
    blocked_before_manifest_or_runner_construction: Literal[True] = True
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V177PredecessorFreezeAudit:
        if len(self.predecessor_files) != self.predecessor_file_count:
            raise ValueError("v26.177 predecessor file denominator changed")
        if len({item.relative_path for item in self.predecessor_files}) != 15:
            raise ValueError("v26.177 predecessor Freeze repeats a file")
        if self.blocked_runner_preflight_transition != BLOCKED_PREDECESSOR_STAGE:
            raise ValueError("v26.178 did not block the exact v26.177 preflight")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v177_predecessor_freeze_audit:",
        ):
            raise ValueError("v26.177 predecessor Freeze identity is invalid")
        return self


class V177EvidenceIdentityDefectAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    old_projection_row_count: Literal[432] = 432
    old_host_counterfactual_declared_pass_count: Literal[432] = 432
    old_host_counterfactual_executed_count: Literal[0] = 0
    aliased_public_preimage_field_count: Literal[3] = 3
    host_counterfactual_measurement_failed: Literal[True] = True
    public_host_separation_property_falsified: Literal[False] = False
    old_registered_control_count: Literal[312] = 312
    old_registered_control_content_identity_rebuilt_count: Literal[0] = 0
    old_registered_control_evidence_level: Literal[
        "unvalidated_synthetic_production_classifier_branch_probe"
    ] = "unvalidated_synthetic_production_classifier_branch_probe"
    old_outcome_fixture_declared_count: Literal[5] = 5
    old_outcome_fixture_row_count: Literal[0] = 0
    old_outcome_fixture_evidence_level: Literal["declarative_aggregate_count"] = (
        "declarative_aggregate_count"
    )
    old_outcome_eligibility_denominator_identified: Literal[False] = False
    old_fully_rehashed_outcome_erosion_attack_count: Literal[0] = 0
    historical_reclassification_count: Literal[0] = 0
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V177EvidenceIdentityDefectAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v177_evidence_identity_defect_reproduction:",
        ):
            raise ValueError("v26.177 Evidence-identity Defect Audit identity is invalid")
        return self


class ExactCatalogStateScanRow(FrozenModel):
    row_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    component_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    prompt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_count: int = Field(ge=2, le=3)
    acceptance_report_ids: tuple[str, ...] = Field(min_length=2, max_length=3)
    rejected_branch_keys: tuple[str, ...]
    source_catalog_modified: Literal[False] = False
    registry_declaration_used_as_outcome: Literal[False] = False
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> ExactCatalogStateScanRow:
        if len(self.acceptance_report_ids) != self.candidate_count:
            raise ValueError("exact-Catalog scan loses one Candidate report")
        if len(set(self.acceptance_report_ids)) != self.candidate_count:
            raise ValueError("exact-Catalog scan repeats a Candidate report")
        if self.row_id != identity(
            self,
            "row_id",
            "exact_catalog_typed_rejection_state_scan_row:",
        ):
            raise ValueError("exact-Catalog scan row identity is invalid")
        return self


class ExactCatalogReachabilityRow(FrozenModel):
    row_id: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    rejection_code: str = Field(min_length=1)
    observed_rejection_count: int = Field(ge=0)
    exact_catalog_status: Literal[
        "reachable",
        "registered_but_unreachable_under_valid_public_object_model",
    ]
    status_derived_from_complete_scan: Literal[True] = True
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> ExactCatalogReachabilityRow:
        reachable = self.exact_catalog_status == "reachable"
        if reachable != (self.observed_rejection_count > 0):
            raise ValueError("exact-Catalog reachability status is not scan-derived")
        if self.row_id != identity(
            self,
            "row_id",
            "exact_catalog_typed_rejection_reachability_row:",
        ):
            raise ValueError("exact-Catalog reachability row identity is invalid")
        return self


class ExactCatalogReachabilityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    state_rows: tuple[ExactCatalogStateScanRow, ...] = Field(min_length=480, max_length=480)
    reachability_rows: tuple[ExactCatalogReachabilityRow, ...] = Field(
        min_length=5,
        max_length=5,
    )
    package_count: Literal[32] = 32
    component_count: Literal[80] = 80
    replica_count: Literal[6] = 6
    state_scan_count: Literal[480] = 480
    candidate_scan_count: int = Field(gt=0)
    acceptance_count: int = Field(ge=0)
    rejection_count: int = Field(ge=0)
    registered_branch_count: Literal[5] = 5
    reachable_branch_count: Literal[1] = 1
    valid_object_unreachable_branch_count: Literal[4] = 4
    registry_declaration_used_as_outcome_count: Literal[0] = 0
    source_catalog_mutation_count: Literal[0] = 0
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ExactCatalogReachabilityAudit:
        if len(self.state_rows) != self.state_scan_count:
            raise ValueError("exact-Catalog State scan denominator changed")
        if sum(item.candidate_count for item in self.state_rows) != self.candidate_scan_count:
            raise ValueError("exact-Catalog Candidate scan denominator changed")
        if self.acceptance_count + self.rejection_count != self.candidate_scan_count:
            raise ValueError("exact-Catalog Candidate partition changed")
        keys = tuple((item.decision_kind, item.rejection_code) for item in self.reachability_rows)
        if keys != REGISTERED_REJECTION_BRANCHES:
            raise ValueError("exact-Catalog reachability branch order changed")
        if sum(item.exact_catalog_status == "reachable" for item in self.reachability_rows) != 1:
            raise ValueError("exact-Catalog reachable branch count changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_exact_catalog_rejection_reachability_audit:",
        ):
            raise ValueError("exact-Catalog reachability Audit identity is invalid")
        return self


class CanonicalControlObject(FrozenModel):
    object_id: str = Field(min_length=1)
    control_package_id: str = Field(min_length=1)
    base_v176_package_id: str = Field(min_length=1)
    original_source_package_artifact_id: str = Field(min_length=1)
    control_source_package_artifact_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    original_component_id: str = Field(min_length=1)
    control_component_id: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    rejection_code: str = Field(min_length=1)
    control_origin: Literal["exact_catalog", "canonical_diagnostic"]
    component_content_rematerialized: bool
    source_package_content_rematerialized: bool
    operation_roundtrip_valid: Literal[True] = True
    choice_handle_recomputed: Literal[True] = True
    public_state_roundtrip_valid: Literal[True] = True
    component_id_recomputed: Literal[True] = True
    component_roundtrip_valid: Literal[True] = True
    source_package_roundtrip_valid: Literal[True] = True
    schedule_roundtrip_valid: Literal[True] = True
    validation_bypass_count: Literal[0] = 0
    enters_manifest_or_empirical_denominator: Literal[False] = False
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_object(self) -> CanonicalControlObject:
        diagnostic = self.control_origin == "canonical_diagnostic"
        if diagnostic != (
            self.rejection_code != "typed_current_state_target_mismatch"
            or self.decision_kind != "revise_selector"
        ):
            raise ValueError("canonical control origin is inconsistent with the exact branch")
        if self.object_id != identity(
            self,
            "object_id",
            "canonical_valid_typed_rejection_control_object:",
        ):
            raise ValueError("canonical control object identity is invalid")
        return self


class ValidControlExecutionRow(FrozenModel):
    row_id: str = Field(min_length=1)
    control_object_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    rejection_code: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    control_origin: Literal["exact_catalog", "canonical_diagnostic"]
    initial_prompt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_observation_receipt_id: str = Field(min_length=1)
    public_feedback_id: str = Field(min_length=1)
    host_binding_id: str = Field(min_length=1)
    recovery_prompt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_public_preimage_match: Literal[True] = True
    initial_rejection_emitted: Literal[True] = True
    initial_rejection_retry_delta: Literal[0] = 0
    initial_rejection_tool_delta: Literal[0] = 0
    initial_rejection_component_advance_delta: Literal[0] = 0
    reference_correction_accepted_once: Literal[True] = True
    repeated_invalid_typed_terminal: Literal[True] = True
    later_prompt_after_terminal_count: Literal[0] = 0
    runtime_exception_count: Literal[0] = 0
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> ValidControlExecutionRow:
        if self.row_id != identity(
            self,
            "row_id",
            "canonical_valid_typed_rejection_control_execution_row:",
        ):
            raise ValueError("canonical control execution row identity is invalid")
        return self


class ValidControlExecutionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    control_objects: tuple[CanonicalControlObject, ...] = Field(min_length=72, max_length=72)
    rows: tuple[ValidControlExecutionRow, ...] = Field(min_length=432, max_length=432)
    registered_branch_count: Literal[5] = 5
    control_object_count: Literal[72] = 72
    execution_row_count: Literal[432] = 432
    exact_catalog_execution_count: Literal[120] = 120
    canonical_diagnostic_execution_count: Literal[312] = 312
    rematerialized_component_execution_count: Literal[192] = 192
    valid_public_object_execution_count: Literal[432] = 432
    validation_bypass_count: Literal[0] = 0
    reference_correction_accept_count: Literal[432] = 432
    repeated_invalid_terminal_count: Literal[432] = 432
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ValidControlExecutionAudit:
        if len(self.control_objects) != self.control_object_count:
            raise ValueError("canonical control object denominator changed")
        if len(self.rows) != self.execution_row_count:
            raise ValueError("canonical control execution denominator changed")
        object_ids = {item.object_id for item in self.control_objects}
        if len(object_ids) != self.control_object_count:
            raise ValueError("canonical control Audit repeats an object")
        if any(item.control_object_id not in object_ids for item in self.rows):
            raise ValueError("canonical control execution loses its object parent")
        if sum(item.control_origin == "exact_catalog" for item in self.rows) != 120:
            raise ValueError("canonical control exact-Catalog partition changed")
        if sum(item.control_origin == "canonical_diagnostic" for item in self.rows) != 312:
            raise ValueError("canonical control diagnostic partition changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_canonical_valid_rejection_control_execution_audit:",
        ):
            raise ValueError("canonical control execution Audit identity is invalid")
        return self


class HostCounterfactualInterventionRow(FrozenModel):
    row_id: str = Field(min_length=1)
    control_execution_row_id: str = Field(min_length=1)
    intervention_kind: Literal[
        "package_id",
        "component_key",
        "source_choice_handle",
        "selected_operation_hash",
        "action_acceptance_report",
        "runtime_event_identities",
        "joint_all_host_parents",
    ]
    baseline_host_binding_id: str = Field(min_length=1)
    counterfactual_host_binding_id: str = Field(min_length=1)
    host_binding_bytes_changed: Literal[True] = True
    host_binding_identity_changed: Literal[True] = True
    public_inputs_fixed: Literal[True] = True
    public_observation_bytes_unchanged: Literal[True] = True
    public_feedback_bytes_unchanged: Literal[True] = True
    recovery_prompt_bytes_unchanged: Literal[True] = True
    recovery_prompt_hash_unchanged: Literal[True] = True
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> HostCounterfactualInterventionRow:
        if self.baseline_host_binding_id == self.counterfactual_host_binding_id:
            raise ValueError("Host counterfactual did not change its Binding identity")
        if self.row_id != identity(
            self,
            "row_id",
            "executed_host_counterfactual_intervention_row:",
        ):
            raise ValueError("Host counterfactual intervention row identity is invalid")
        return self


class ExecutedHostCounterfactualAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[HostCounterfactualInterventionRow, ...] = Field(
        min_length=3024,
        max_length=3024,
    )
    base_control_row_count: Literal[432] = 432
    intervention_kind_count: Literal[7] = 7
    intervention_execution_count: Literal[3024] = 3024
    host_binding_change_count: Literal[3024] = 3024
    public_observation_invariance_count: Literal[3024] = 3024
    public_feedback_invariance_count: Literal[3024] = 3024
    recovery_prompt_invariance_count: Literal[3024] = 3024
    measurement_method: Literal["executed_single_factor_and_joint_host_interventions"] = (
        "executed_single_factor_and_joint_host_interventions"
    )
    public_preimage_boolean_reused_as_counterfactual_count: Literal[0] = 0
    property_falsified_count: Literal[0] = 0
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutedHostCounterfactualAudit:
        if len(self.rows) != self.intervention_execution_count:
            raise ValueError("Host counterfactual intervention denominator changed")
        by_control: dict[str, set[str]] = {}
        for row in self.rows:
            by_control.setdefault(row.control_execution_row_id, set()).add(row.intervention_kind)
        if len(by_control) != self.base_control_row_count:
            raise ValueError("Host counterfactual base-control denominator changed")
        if any(
            tuple(sorted(kinds)) != tuple(sorted(HOST_COUNTERFACTUAL_INTERVENTIONS))
            for kinds in by_control.values()
        ):
            raise ValueError("Host counterfactual intervention surface is incomplete")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_executed_host_counterfactual_invariance_audit:",
        ):
            raise ValueError("Host counterfactual Audit identity is invalid")
        return self


class CapabilityOutcomeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    source_v176_runner_input_catalog_id: str = Field(min_length=1)
    source_v177_outcome_contract_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    replica_count: Literal[6] = 6
    future_job_count: Literal[192] = 192
    eligible_job_count: Literal[192] = 192
    eligibility_rule: Literal[
        "all_32_frozen_v176_packages_x_6_replicas_are_eligible_before_outcomes"
    ] = "all_32_frozen_v176_packages_x_6_replicas_are_eligible_before_outcomes"
    typed_exclusion_reasons: tuple[()] = ()
    post_outcome_exclusion_forbidden: Literal[True] = True
    outcome_fields: tuple[str, ...] = REQUIRED_CAPABILITY_OUTCOME_FIELDS
    first_attempt_estimand: Literal["q_first"] = "q_first"
    bounded_correction_estimand: Literal["q_bounded_correction"] = "q_bounded_correction"
    q_first_formula: Literal["sum(first_attempt_qualified_valid)/192"] = (
        "sum(first_attempt_qualified_valid)/192"
    )
    q_bounded_correction_formula: Literal["sum(final_qualified_valid)/192"] = (
        "sum(final_qualified_valid)/192"
    )
    common_denominator_required: Literal[True] = True
    first_attempt_overwrite_forbidden: Literal[True] = True
    estimand_pooling_forbidden: Literal[True] = True
    materialized_manifest_count: Literal[0] = 0
    empirical_outcome_row_count: Literal[0] = 0
    empirical_estimate_count: Literal[0] = 0
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CapabilityOutcomeContract:
        if self.package_count * self.replica_count != self.eligible_job_count:
            raise ValueError("Capability Outcome denominator is not the frozen 32 x 6 surface")
        if self.outcome_fields != REQUIRED_CAPABILITY_OUTCOME_FIELDS:
            raise ValueError("Capability Outcome required field tuple changed")
        if self.contract_id != identity(
            self,
            "contract_id",
            "capability_executed_first_bounded_outcome_contract:",
        ):
            raise ValueError("Capability Outcome Contract identity is invalid")
        return self


class OutcomeRowFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[CapabilityOutcomeRow, ...] = Field(min_length=5, max_length=5)
    evaluation: CapabilityEstimandEvaluation
    fixture_row_count: Literal[5] = 5
    model_validation_roundtrip_count: Literal[5] = 5
    canonical_serialization_roundtrip_count: Literal[5] = 5
    distinct_row_identity_count: Literal[5] = 5
    first_attempt_failure_preserved_count: Literal[5] = 5
    accepted_correction_count: Literal[2] = 2
    terminal_correction_count: Literal[3] = 3
    fixture_q_first_numerator: Literal[0] = 0
    fixture_q_bounded_correction_numerator: Literal[2] = 2
    first_bounded_estimand_conflation_count: Literal[0] = 0
    missing_required_field_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> OutcomeRowFixtureAudit:
        if len(self.rows) != self.fixture_row_count:
            raise ValueError("Outcome fixture row denominator changed")
        if len({item.row_id for item in self.rows}) != self.distinct_row_identity_count:
            raise ValueError("Outcome fixture repeats a row identity")
        if self.evaluation.eligible_job_count != self.fixture_row_count:
            raise ValueError("Outcome fixture evaluation denominator changed")
        if (
            self.evaluation.q_first_numerator != self.fixture_q_first_numerator
            or self.evaluation.q_bounded_correction_numerator
            != self.fixture_q_bounded_correction_numerator
        ):
            raise ValueError("Outcome fixture estimand calculation changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_executed_outcome_row_fixture_audit:",
        ):
            raise ValueError("Outcome row fixture Audit identity is invalid")
        return self


class FullyRehashedMutation(FrozenModel):
    mutation: str = Field(min_length=1)
    changed_parent_id: str = Field(min_length=1)
    changed_transition_id: str = Field(min_length=1)
    changed_report_id: str = Field(min_length=1)
    parent_identity_rehashed: Literal[True] = True
    transition_identity_rehashed: Literal[True] = True
    report_identity_rehashed: Literal[True] = True
    rejected: Literal[True] = True
    reason: str = Field(min_length=1)


class FullyRehashedDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[FullyRehashedMutation, ...] = Field(min_length=6)
    mutation_count: int = Field(ge=6)
    rejection_count: int = Field(ge=6)
    acceptance_count: Literal[0] = 0
    required_outcome_field_deletion_count: Literal[1] = 1
    eligibility_rule_replacement_count: Literal[1] = 1
    estimand_pooling_attack_count: Literal[1] = 1
    host_counterfactual_alias_attack_count: Literal[1] = 1
    control_identity_bypass_attack_count: Literal[1] = 1
    reachability_relabel_attack_count: Literal[1] = 1
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FullyRehashedDestructiveAudit:
        if self.mutation_count != len(self.mutations):
            raise ValueError("fully rehashed mutation denominator changed")
        if self.rejection_count != self.mutation_count:
            raise ValueError("fully rehashed mutation escaped")
        if len({item.mutation for item in self.mutations}) != self.mutation_count:
            raise ValueError("fully rehashed destructive Audit repeats a mutation")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_fully_rehashed_evidence_destructive_audit:",
        ):
            raise ValueError("fully rehashed destructive Audit identity is invalid")
        return self


class StaticGate(FrozenModel):
    gate: str = Field(min_length=1)
    passed: Literal[True] = True
    observed: int = Field(ge=0)
    required: int = Field(ge=0)


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=20)
    gate_count: int = Field(ge=20)
    passed_gate_count: int = Field(ge=20)
    failed_gate_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_2_provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    manifest_count: Literal[0] = 0
    runner_count: Literal[0] = 0
    historical_reclassification_count: Literal[0] = 0
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if self.gate_count != len(self.gates):
            raise ValueError("v26.178 static Gate denominator changed")
        if self.passed_gate_count != self.gate_count:
            raise ValueError("v26.178 static Gate failed")
        if len({item.gate for item in self.gates}) != self.gate_count:
            raise ValueError("v26.178 static Audit repeats a Gate")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_executed_counterfactual_outcome_static_audit:",
        ):
            raise ValueError("v26.178 static Audit identity is invalid")
        return self


class TransitiveSourceRoot(FrozenModel):
    root_id: str = Field(min_length=1)
    entry_modules: tuple[str, ...] = Field(min_length=1)
    files: tuple[FileBinding, ...] = Field(min_length=1)
    file_count: int = Field(ge=1)
    unresolved_imports: tuple[str, ...] = ()
    unresolved_import_count: int = Field(ge=0)
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_root(self) -> TransitiveSourceRoot:
        if self.file_count != len(self.files):
            raise ValueError("v26.178 source Root file denominator changed")
        if self.unresolved_import_count != len(self.unresolved_imports):
            raise ValueError("v26.178 source Root unresolved denominator changed")
        if len({item.relative_path for item in self.files}) != self.file_count:
            raise ValueError("v26.178 source Root repeats a file")
        if self.root_id != identity(
            self,
            "root_id",
            "finance_v26_executed_counterfactual_outcome_transitive_source_root:",
        ):
            raise ValueError("v26.178 source Root identity is invalid")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    predecessor_freeze_audit_id: str = Field(min_length=1)
    defect_reproduction_audit_id: str = Field(min_length=1)
    exact_catalog_reachability_audit_id: str = Field(min_length=1)
    valid_control_execution_audit_id: str = Field(min_length=1)
    executed_host_counterfactual_audit_id: str = Field(min_length=1)
    capability_outcome_contract_id: str = Field(min_length=1)
    outcome_fixture_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    consumed_stage: str = Field(min_length=1)
    blocked_predecessor_stage: str = Field(min_length=1)
    next_stage: str = Field(min_length=1)
    current_manifest_count: Literal[0] = 0
    current_runner_count: Literal[0] = 0
    current_development_job_count: Literal[0] = 0
    provider_calls_authorized: Literal[False] = False
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if (
            self.consumed_stage != AUTHORIZED_STAGE
            or self.blocked_predecessor_stage != BLOCKED_PREDECESSOR_STAGE
            or self.next_stage != NEXT_STAGE
        ):
            raise ValueError("v26.178 prospective transition scope changed")
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_executed_counterfactual_outcome_transition:",
        ):
            raise ValueError("v26.178 prospective Transition identity is invalid")
        return self


class ClosureReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    predecessor_freeze_audit_id: str = Field(min_length=1)
    defect_reproduction_audit_id: str = Field(min_length=1)
    exact_catalog_reachability_audit_id: str = Field(min_length=1)
    valid_control_execution_audit_id: str = Field(min_length=1)
    executed_host_counterfactual_audit_id: str = Field(min_length=1)
    capability_outcome_contract_id: str = Field(min_length=1)
    outcome_fixture_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    detail_files: tuple[FileBinding, ...] = Field(min_length=1)
    detail_file_count: int = Field(ge=1)
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    manifest_count: Literal[0] = 0
    runner_count: Literal[0] = 0
    empirical_outcome_row_count: Literal[0] = 0
    next_stage: str = Field(min_length=1)
    schema_version: str = V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> ClosureReport:
        if self.detail_file_count != len(self.detail_files):
            raise ValueError("v26.178 Report detail-file denominator changed")
        if self.next_stage != NEXT_STAGE:
            raise ValueError("v26.178 Report next stage changed")
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_executed_counterfactual_outcome_closure_report:",
        ):
            raise ValueError("v26.178 Report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    source_root: TransitiveSourceRoot
    predecessor: V177PredecessorFreezeAudit
    defect: V177EvidenceIdentityDefectAudit
    exact_catalog_reachability: ExactCatalogReachabilityAudit
    valid_controls: ValidControlExecutionAudit
    host_counterfactuals: ExecutedHostCounterfactualAudit
    capability_outcome_contract: CapabilityOutcomeContract
    outcome_fixtures: OutcomeRowFixtureAudit
    destructive: FullyRehashedDestructiveAudit
    static: StaticAudit
    transition: ProspectiveTransition
    report: ClosureReport


__all__ = [
    "AUTHORIZED_STAGE",
    "BLOCKED_PREDECESSOR_STAGE",
    "BuildProducts",
    "CanonicalControlObject",
    "CapabilityOutcomeContract",
    "ClosureReport",
    "ExactCatalogReachabilityAudit",
    "ExactCatalogReachabilityRow",
    "ExactCatalogStateScanRow",
    "ExecutedHostCounterfactualAudit",
    "ExternalAuditAuthorization",
    "FileBinding",
    "FullyRehashedDestructiveAudit",
    "FullyRehashedMutation",
    "HOST_COUNTERFACTUAL_INTERVENTIONS",
    "HostCounterfactualInterventionRow",
    "NEXT_STAGE",
    "OutcomeRowFixtureAudit",
    "ProspectiveTransition",
    "REGISTERED_REJECTION_BRANCHES",
    "StaticAudit",
    "StaticGate",
    "TransitiveSourceRoot",
    "V177EvidenceIdentityDefectAudit",
    "V177PredecessorFreezeAudit",
    "V26_EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION",
    "ValidControlExecutionAudit",
    "ValidControlExecutionRow",
    "identity",
    "make_identity_model",
]
