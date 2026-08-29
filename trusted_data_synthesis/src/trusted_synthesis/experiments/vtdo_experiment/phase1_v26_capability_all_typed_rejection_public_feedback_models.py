from __future__ import annotations

from typing import Any, Final, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.all_typed_rejection_public_feedback import (
    PUBLIC_FEEDBACK_FIELDS,
)
from trusted_synthesis.hashing import canonical_hash

V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION: Final = (
    "all_typed_rejection_public_feedback_closure.v1"
)
AUTHORIZED_STAGE: Final = (
    "capability_observation_all_typed_rejection_kinds_"
    "public_feedback_and_correction_bound_closure_only"
)
BLOCKED_PREDECESSOR_STAGE: Final = (
    "capability_observation_authoritative_parent_closed_rejection_history_"
    "state_bound_step_runtime_development_runner_preflight_only"
)
NEXT_STAGE: Final = (
    "capability_observation_public_feedback_closed_all_typed_rejection_"
    "correction_bound_state_bound_step_runtime_development_runner_preflight_only"
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
        "capability_observation_all_typed_rejection_kinds_"
        "public_feedback_and_correction_bound_closure_only"
    ] = AUTHORIZED_STAGE
    predecessor_runner_preflight_consumption_authorized: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    development_jobs_authorized: Literal[False] = False
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_all_typed_rejection_external_authorization:",
        ):
            raise ValueError("v26.177 external Authorization identity is invalid")
        return self


class V176PredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    predecessor_files: tuple[FileBinding, ...] = Field(min_length=16, max_length=16)
    predecessor_file_count: Literal[16] = 16
    independent_rebuild_match_count: Literal[16] = 16
    predecessor_mutation_count: Literal[0] = 0
    blocked_runner_preflight_transition: str = Field(min_length=1)
    blocked_before_manifest_or_runner_construction: Literal[True] = True
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V176PredecessorFreezeAudit:
        if len(self.predecessor_files) != self.predecessor_file_count:
            raise ValueError("v26.176 predecessor file denominator changed")
        if len({item.relative_path for item in self.predecessor_files}) != 16:
            raise ValueError("v26.176 predecessor Freeze repeats a file")
        if self.blocked_runner_preflight_transition != BLOCKED_PREDECESSOR_STAGE:
            raise ValueError("v26.177 did not block the exact predecessor preflight")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v176_predecessor_freeze_audit:",
        ):
            raise ValueError("v26.176 predecessor Freeze identity is invalid")
        return self


class V176DefectReproductionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    old_feedback_fields: tuple[str, ...] = Field(min_length=1)
    old_feedback_host_direct_fields: tuple[str, ...] = Field(min_length=3)
    old_feedback_host_derived_identity_fields: tuple[str, ...] = Field(min_length=1)
    old_feedback_host_direct_field_count: int = Field(ge=3)
    exact_catalog_component_count: Literal[80] = 80
    production_classifier_decision_kind_count: Literal[4] = 4
    production_classifier_rejection_kind_count: Literal[5] = 5
    exact_catalog_typed_rejection_state_count: Literal[120] = 120
    exact_catalog_typed_rejection_decision_kind_count: Literal[1] = 1
    exact_catalog_typed_rejection_code_count: Literal[1] = 1
    missing_exact_catalog_rejection_kind_count: Literal[4] = 4
    old_successful_correction_disposition_count: Literal[1] = 1
    old_same_invalid_terminal_count: Literal[120] = 120
    old_different_invalid_terminal_evidence_count: Literal[0] = 0
    old_valid_nonreference_correction_count: Literal[0] = 0
    old_public_only_feedback_schema_proved: Literal[False] = False
    historical_reclassification_count: Literal[0] = 0
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V176DefectReproductionAudit:
        if self.old_feedback_host_direct_field_count != len(self.old_feedback_host_direct_fields):
            raise ValueError("old Feedback Host-field count is inconsistent")
        if not set(self.old_feedback_host_direct_fields) <= set(self.old_feedback_fields):
            raise ValueError("old Feedback direct Host fields are not exact schema fields")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v176_typed_rejection_defect_reproduction:",
        ):
            raise ValueError("v26.176 typed-rejection Defect Audit identity is invalid")
        return self


class PublicFeedbackContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    public_feedback_fields: tuple[str, ...] = PUBLIC_FEEDBACK_FIELDS
    public_observation_fields: tuple[str, ...] = (
        "public_observation_receipt_id",
        "public_state_token",
        "public_rejected_action_id",
        "public_displayed_choice_handle",
        "public_rejection_code",
        "correction_attempt_index",
        "correction_attempt_bound",
        "action_committed",
        "schema_version",
    )
    prohibited_public_fields: tuple[str, ...] = Field(min_length=1)
    identity_preimage_policy: Literal["strict_public_fields_only"] = "strict_public_fields_only"
    host_binding_separate: Literal[True] = True
    host_report_object_model_visible: Literal[False] = False
    host_report_identity_model_visible: Literal[False] = False
    hidden_parent_hash_model_visible: Literal[False] = False
    correction_attempt_bound: Literal[1] = 1
    second_invalid_action_identity_relevant: Literal[False] = False
    any_second_invalid_must_terminalize: Literal[True] = True
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> PublicFeedbackContract:
        if self.public_feedback_fields != PUBLIC_FEEDBACK_FIELDS:
            raise ValueError("public Feedback Contract field list changed")
        if len(set(self.prohibited_public_fields)) != len(self.prohibited_public_fields):
            raise ValueError("public Feedback Contract repeats a prohibited field")
        if self.contract_id != identity(
            self,
            "contract_id",
            "public_typed_rejection_feedback_contract:",
        ):
            raise ValueError("public Feedback Contract identity is invalid")
        return self


class ProductionRejectionKindRow(FrozenModel):
    row_id: str = Field(min_length=1)
    capability_family: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    rejection_code: str = Field(min_length=1)
    choice_count: int = Field(ge=2, le=3)
    production_component_count: int = Field(gt=0)
    replica_count: Literal[6] = 6
    exact_catalog_rejection_state_count: int = Field(ge=0)
    exact_catalog_status: Literal["reachable", "registered_but_unreachable"]
    control_fixture_count: int = Field(gt=0)
    control_rejection_count: int = Field(gt=0)
    public_projection_match_count: int = Field(gt=0)
    reference_correction_accept_count: int = Field(gt=0)
    repeated_invalid_terminal_count: int = Field(gt=0)
    later_prompt_after_terminal_count: Literal[0] = 0
    retry_delta: Literal[0] = 0
    tool_call_delta: Literal[0] = 0
    component_advance_on_rejection_count: Literal[0] = 0
    current_catalog_modified: Literal[False] = False
    empirical_result: Literal[False] = False
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> ProductionRejectionKindRow:
        expected = self.production_component_count * self.replica_count
        if self.control_fixture_count != expected:
            raise ValueError("production rejection-kind control denominator changed")
        if not (
            self.control_rejection_count
            == self.public_projection_match_count
            == self.reference_correction_accept_count
            == self.repeated_invalid_terminal_count
            == expected
        ):
            raise ValueError("production rejection-kind control is incomplete")
        if (self.exact_catalog_rejection_state_count > 0) != (
            self.exact_catalog_status == "reachable"
        ):
            raise ValueError("production rejection-kind reachability status is inconsistent")
        if self.row_id != identity(
            self,
            "row_id",
            "production_typed_rejection_kind_row:",
        ):
            raise ValueError("production rejection-kind row identity is invalid")
        return self


class ProductionRejectionSurfaceCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    rows: tuple[ProductionRejectionKindRow, ...] = Field(min_length=5, max_length=5)
    decision_kind_count: Literal[4] = 4
    rejection_kind_count: Literal[5] = 5
    exact_catalog_reachable_kind_count: Literal[1] = 1
    registered_but_unreachable_kind_count: Literal[4] = 4
    unique_production_component_count: Literal[52] = 52
    registered_component_surface_count: Literal[72] = 72
    control_fixture_count: Literal[432] = 432
    exact_catalog_rejection_state_count: Literal[120] = 120
    silent_omission_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> ProductionRejectionSurfaceCatalog:
        keys = {(item.decision_kind, item.rejection_code) for item in self.rows}
        if len(keys) != self.rejection_kind_count:
            raise ValueError("production rejection Surface repeats a kind")
        if len({item.decision_kind for item in self.rows}) != self.decision_kind_count:
            raise ValueError("production rejection Surface loses a Decision kind")
        if sum(item.production_component_count for item in self.rows) != (
            self.registered_component_surface_count
        ):
            raise ValueError("production rejection Surface component count changed")
        if sum(item.control_fixture_count for item in self.rows) != self.control_fixture_count:
            raise ValueError("production rejection Surface fixture count changed")
        if sum(item.exact_catalog_rejection_state_count for item in self.rows) != (
            self.exact_catalog_rejection_state_count
        ):
            raise ValueError("production rejection Surface exact reachability changed")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_production_typed_rejection_surface_catalog:",
        ):
            raise ValueError("production rejection Surface Catalog identity is invalid")
        return self


class PublicFeedbackProjectionRow(FrozenModel):
    row_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    capability_family: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    rejection_code: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    fixture_kind: Literal["exact_catalog", "registered_control"]
    host_binding_id: str = Field(min_length=1)
    public_observation_receipt_id: str = Field(min_length=1)
    public_feedback_id: str = Field(min_length=1)
    recovery_prompt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_public_schema_match: Literal[True] = True
    independent_projection_match: Literal[True] = True
    host_counterfactual_invariant: Literal[True] = True
    identity_preimage_public_only: Literal[True] = True
    prohibited_key_count: Literal[0] = 0
    direct_hidden_scalar_exposure_count: Literal[0] = 0
    derived_host_identity_exposure_count: Literal[0] = 0
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> PublicFeedbackProjectionRow:
        if self.row_id != identity(
            self,
            "row_id",
            "public_typed_rejection_feedback_projection_row:",
        ):
            raise ValueError("public Feedback Projection row identity is invalid")
        return self


class PublicFeedbackProjectionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[PublicFeedbackProjectionRow, ...] = Field(min_length=432, max_length=432)
    projection_count: Literal[432] = 432
    exact_catalog_projection_count: Literal[120] = 120
    registered_control_projection_count: Literal[312] = 312
    exact_schema_match_count: Literal[432] = 432
    independent_projection_match_count: Literal[432] = 432
    host_counterfactual_invariant_count: Literal[432] = 432
    identity_preimage_public_only_count: Literal[432] = 432
    prohibited_key_count: Literal[0] = 0
    direct_hidden_scalar_exposure_count: Literal[0] = 0
    derived_host_identity_exposure_count: Literal[0] = 0
    complete_acceptance_report_model_visible_count: Literal[0] = 0
    acceptance_report_id_model_visible_count: Literal[0] = 0
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PublicFeedbackProjectionAudit:
        if len(self.rows) != self.projection_count:
            raise ValueError("public Feedback Projection denominator changed")
        if (
            self.exact_catalog_projection_count + self.registered_control_projection_count
            != self.projection_count
        ):
            raise ValueError("public Feedback Projection partition changed")
        if sum(item.fixture_kind == "exact_catalog" for item in self.rows) != (
            self.exact_catalog_projection_count
        ):
            raise ValueError("public Feedback exact-Catalog denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_public_typed_rejection_feedback_projection_audit:",
        ):
            raise ValueError("public Feedback Projection Audit identity is invalid")
        return self


class CorrectionMatrixRow(FrozenModel):
    row_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    capability_family: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    rejection_code: str = Field(min_length=1)
    choice_count: Literal[3] = 3
    replica_index: int = Field(ge=0, le=5)
    first_rejected_action_id: str = Field(min_length=1)
    first_public_feedback_id: str = Field(min_length=1)
    disposition: Literal[
        "reference_valid",
        "nonreference_valid",
        "same_current_invalid",
        "different_current_invalid",
        "stale_action_id",
        "foreign_action_id",
        "malformed_abi_valid_action_id",
    ]
    availability: Literal["executed", "registered_but_unreachable"]
    unreachable_reason: str | None = None
    second_action_id: str | None = None
    second_outcome: Literal[
        "accepted",
        "typed_terminal",
        "action_reference_terminal",
        "registered_but_unreachable",
    ]
    corrected_action_accepted: bool | None = None
    component_commit_count: int | None = Field(default=None, ge=0, le=1)
    correction_terminal_id: str | None = None
    later_correction_prompt_count: int | None = Field(default=None, ge=0)
    retry_delta: int | None = Field(default=None, ge=0)
    tool_call_delta: int | None = Field(default=None, ge=0)
    rejection_component_advance_count: int | None = Field(default=None, ge=0)
    final_result_id: str | None = None
    final_base_valid: bool | None = None
    final_mechanism_qualified: bool | None = None
    final_qualified_valid: bool | None = None
    direct_action_acceptance_match: bool | None = None
    direct_public_effect_match: bool | None = None
    direct_base_validity_match: bool | None = None
    direct_mechanism_match: bool | None = None
    direct_qualified_match: bool | None = None
    complete_rejection_lineage_bound: bool | None = None
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> CorrectionMatrixRow:
        if self.availability == "registered_but_unreachable":
            if self.second_outcome != "registered_but_unreachable":
                raise ValueError("unreachable correction row has an executed outcome")
            if self.unreachable_reason is None or self.second_action_id is not None:
                raise ValueError("unreachable correction row is not explicit")
        else:
            if self.unreachable_reason is not None or self.second_action_id is None:
                raise ValueError("executed correction row has invalid availability fields")
            if self.later_correction_prompt_count != 0:
                raise ValueError("executed correction row exposes a later correction Prompt")
            if self.retry_delta != 0 or self.tool_call_delta != 0:
                raise ValueError("correction rejection invoked Retry or a Tool")
            if self.rejection_component_advance_count != 0:
                raise ValueError("initial rejection advanced its Component")
            if self.complete_rejection_lineage_bound is not True:
                raise ValueError("executed correction row loses rejection lineage")
        if self.second_outcome == "accepted":
            if self.corrected_action_accepted is not True or self.component_commit_count != 1:
                raise ValueError("accepted correction did not commit exactly once")
            if self.correction_terminal_id is not None or self.final_result_id is None:
                raise ValueError("accepted correction outcome is incomplete")
        if self.second_outcome in {"typed_terminal", "action_reference_terminal"}:
            if self.corrected_action_accepted is not False or self.component_commit_count != 0:
                raise ValueError("invalid second response committed Runtime behavior")
            if self.correction_terminal_id is None or self.final_result_id is not None:
                raise ValueError("invalid second-response terminal is incomplete")
        if self.disposition == "nonreference_valid" and self.availability == "executed":
            comparisons = (
                self.direct_action_acceptance_match,
                self.direct_public_effect_match,
                self.direct_base_validity_match,
                self.direct_mechanism_match,
                self.direct_qualified_match,
            )
            if any(item is not True for item in comparisons):
                raise ValueError("valid nonreference correction differs from direct execution")
        if self.row_id != identity(
            self,
            "row_id",
            "bounded_correction_matrix_row:",
        ):
            raise ValueError("bounded-correction Matrix row identity is invalid")
        return self


class CorrectionBoundMatrixAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[CorrectionMatrixRow, ...] = Field(min_length=840, max_length=840)
    exact_initial_rejection_state_count: Literal[120] = 120
    disposition_count: Literal[7] = 7
    matrix_row_count: Literal[840] = 840
    executed_row_count: Literal[672] = 672
    registered_but_unreachable_row_count: Literal[168] = 168
    reference_valid_accept_count: Literal[120] = 120
    nonreference_valid_accept_count: Literal[120] = 120
    same_invalid_terminal_count: Literal[120] = 120
    different_current_invalid_unreachable_count: Literal[120] = 120
    stale_terminal_count: Literal[72] = 72
    stale_unreachable_count: Literal[48] = 48
    foreign_terminal_count: Literal[120] = 120
    malformed_abi_valid_terminal_count: Literal[120] = 120
    any_second_invalid_terminal_count: Literal[432] = 432
    later_correction_prompt_count: Literal[0] = 0
    rejection_retry_delta: Literal[0] = 0
    rejection_tool_call_delta: Literal[0] = 0
    rejection_component_advance_count: Literal[0] = 0
    nonreference_direct_equivalence_count: Literal[120] = 120
    final_or_terminal_lineage_binding_count: Literal[672] = 672
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CorrectionBoundMatrixAudit:
        if len(self.rows) != self.matrix_row_count:
            raise ValueError("bounded-correction Matrix denominator changed")
        if sum(item.availability == "executed" for item in self.rows) != self.executed_row_count:
            raise ValueError("bounded-correction executed count changed")
        if sum(item.second_outcome == "accepted" for item in self.rows) != 240:
            raise ValueError("bounded-correction accepted count changed")
        if (
            sum(
                item.second_outcome in {"typed_terminal", "action_reference_terminal"}
                for item in self.rows
            )
            != self.any_second_invalid_terminal_count
        ):
            raise ValueError("bounded-correction terminal count changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_bounded_correction_matrix_audit:",
        ):
            raise ValueError("bounded-correction Matrix Audit identity is invalid")
        return self


class CapabilityOutcomeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    outcome_fields: tuple[str, ...] = (
        "first_response_abi_valid",
        "first_action_state_precondition_valid",
        "first_action_accepted",
        "first_attempt_base_valid",
        "first_attempt_mechanism_qualified",
        "first_attempt_qualified_valid",
        "correction_invoked",
        "correction_feedback_id",
        "corrected_action_accepted",
        "correction_terminal_reason",
        "final_base_valid",
        "final_mechanism_qualified",
        "final_qualified_valid",
    )
    first_attempt_estimand: Literal["q_first"] = "q_first"
    bounded_correction_estimand: Literal["q_bounded_correction"] = "q_bounded_correction"
    q_first_formula: Literal["sum(first_attempt_qualified_valid)/eligible_job_count"] = (
        "sum(first_attempt_qualified_valid)/eligible_job_count"
    )
    q_bounded_correction_formula: Literal["sum(final_qualified_valid)/eligible_job_count"] = (
        "sum(final_qualified_valid)/eligible_job_count"
    )
    first_attempt_overwrite_forbidden: Literal[True] = True
    correction_condition_is_post_first_response: Literal[True] = True
    estimand_pooling_forbidden: Literal[True] = True
    future_job_count: Literal[192] = 192
    materialized_manifest_count: Literal[0] = 0
    empirical_outcome_row_count: Literal[0] = 0
    empirical_estimate_count: Literal[0] = 0
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CapabilityOutcomeContract:
        if len(self.outcome_fields) != len(set(self.outcome_fields)):
            raise ValueError("Capability Outcome Contract repeats a field")
        if self.contract_id != identity(
            self,
            "contract_id",
            "capability_first_and_bounded_correction_outcome_contract:",
        ):
            raise ValueError("Capability Outcome Contract identity is invalid")
        return self


class OutcomeContractFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    fixture_count: Literal[5] = 5
    first_attempt_failure_preserved_count: Literal[5] = 5
    reference_correction_fixture_count: Literal[1] = 1
    nonreference_correction_fixture_count: Literal[1] = 1
    same_invalid_terminal_fixture_count: Literal[1] = 1
    different_invalid_terminal_fixture_count: Literal[1] = 1
    stale_or_foreign_terminal_fixture_count: Literal[1] = 1
    first_bounded_estimand_conflation_count: Literal[0] = 0
    missing_required_field_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> OutcomeContractFixtureAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_first_bounded_outcome_contract_fixture_audit:",
        ):
            raise ValueError("Outcome Contract fixture Audit identity is invalid")
        return self


class DestructiveMutation(FrozenModel):
    mutation: str = Field(min_length=1)
    rejected: Literal[True] = True
    reason: str = Field(min_length=1)


class ProductionDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[DestructiveMutation, ...] = Field(min_length=20)
    mutation_count: int = Field(ge=20)
    rejection_count: int = Field(ge=20)
    acceptance_count: Literal[0] = 0
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ProductionDestructiveAudit:
        if self.mutation_count != len(self.mutations):
            raise ValueError("v26.177 destructive mutation denominator changed")
        if self.rejection_count != self.mutation_count:
            raise ValueError("v26.177 destructive mutation escaped")
        if len({item.mutation for item in self.mutations}) != self.mutation_count:
            raise ValueError("v26.177 destructive Audit repeats a mutation")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_all_typed_rejection_production_destructive_audit:",
        ):
            raise ValueError("v26.177 destructive Audit identity is invalid")
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
    gpu_jobs: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    manifest_count: Literal[0] = 0
    runner_count: Literal[0] = 0
    mapper_call_count: Literal[0] = 0
    state_assignment_count: Literal[0] = 0
    frequency_row_count: Literal[0] = 0
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if self.gate_count != len(self.gates) or self.passed_gate_count != self.gate_count:
            raise ValueError("v26.177 static Gate denominator changed")
        if any(not item.passed or item.observed < item.required for item in self.gates):
            raise ValueError("v26.177 static Gate failed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_all_typed_rejection_static_audit:",
        ):
            raise ValueError("v26.177 Static Audit identity is invalid")
        return self


class TransitiveSourceRoot(FrozenModel):
    root_id: str = Field(min_length=1)
    entry_modules: tuple[str, ...] = Field(min_length=1)
    files: tuple[FileBinding, ...] = Field(min_length=1)
    file_count: int = Field(gt=0)
    unresolved_imports: tuple[str, ...] = ()
    unresolved_import_count: Literal[0] = 0
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_root(self) -> TransitiveSourceRoot:
        if self.file_count != len(self.files):
            raise ValueError("v26.177 source Root file denominator changed")
        if self.unresolved_imports:
            raise ValueError("v26.177 source Root has unresolved imports")
        if self.root_id != identity(
            self,
            "root_id",
            "finance_v26_all_typed_rejection_transitive_source_root:",
        ):
            raise ValueError("v26.177 source Root identity is invalid")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    predecessor_freeze_audit_id: str = Field(min_length=1)
    defect_reproduction_audit_id: str = Field(min_length=1)
    consumed_stage: Literal[
        "capability_observation_all_typed_rejection_kinds_"
        "public_feedback_and_correction_bound_closure_only"
    ] = AUTHORIZED_STAGE
    blocked_predecessor_stage: str = BLOCKED_PREDECESSOR_STAGE
    next_stage: str = NEXT_STAGE
    source_v176_report_id: str = Field(min_length=1)
    public_feedback_contract_id: str = Field(min_length=1)
    rejection_surface_catalog_id: str = Field(min_length=1)
    public_feedback_projection_audit_id: str = Field(min_length=1)
    correction_matrix_audit_id: str = Field(min_length=1)
    capability_outcome_contract_id: str = Field(min_length=1)
    outcome_fixture_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    future_job_count: Literal[192] = 192
    current_manifest_count: Literal[0] = 0
    current_runner_count: Literal[0] = 0
    current_prompt_count: Literal[0] = 0
    provider_calls_authorized: Literal[False] = False
    development_outcomes_authorized: Literal[False] = False
    credential_free_preflight_only: Literal[True] = True
    confirmation_payload_access_authorized: Literal[False] = False
    historical_reclassification_authorized: Literal[False] = False
    mapper_state_frequency_vtdo_authorized: Literal[False] = False
    training_release_production_authorized: Literal[False] = False
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.blocked_predecessor_stage != BLOCKED_PREDECESSOR_STAGE:
            raise ValueError("v26.177 Transition did not retain the blocked old preflight")
        if self.next_stage != NEXT_STAGE:
            raise ValueError("v26.177 Transition next stage changed")
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_all_typed_rejection_public_feedback_transition:",
        ):
            raise ValueError("v26.177 Transition identity is invalid")
        return self


class ClosureReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    predecessor_freeze_audit_id: str = Field(min_length=1)
    defect_reproduction_audit_id: str = Field(min_length=1)
    public_feedback_contract_id: str = Field(min_length=1)
    rejection_surface_catalog_id: str = Field(min_length=1)
    public_feedback_projection_audit_id: str = Field(min_length=1)
    correction_matrix_audit_id: str = Field(min_length=1)
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
    next_stage: str = Field(min_length=1)
    schema_version: str = V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> ClosureReport:
        if self.detail_file_count != len(self.detail_files):
            raise ValueError("v26.177 Report detail-file denominator changed")
        if self.next_stage != NEXT_STAGE:
            raise ValueError("v26.177 Report next stage changed")
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_all_typed_rejection_public_feedback_closure_report:",
        ):
            raise ValueError("v26.177 Report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    source_root: TransitiveSourceRoot
    predecessor: V176PredecessorFreezeAudit
    defect: V176DefectReproductionAudit
    public_feedback_contract: PublicFeedbackContract
    rejection_surface: ProductionRejectionSurfaceCatalog
    public_feedback_projection: PublicFeedbackProjectionAudit
    correction_matrix: CorrectionBoundMatrixAudit
    capability_outcome_contract: CapabilityOutcomeContract
    outcome_fixture: OutcomeContractFixtureAudit
    destructive: ProductionDestructiveAudit
    static: StaticAudit
    transition: ProspectiveTransition
    report: ClosureReport


__all__ = [
    "AUTHORIZED_STAGE",
    "BLOCKED_PREDECESSOR_STAGE",
    "BuildProducts",
    "CapabilityOutcomeContract",
    "ClosureReport",
    "CorrectionBoundMatrixAudit",
    "CorrectionMatrixRow",
    "DestructiveMutation",
    "ExternalAuditAuthorization",
    "FileBinding",
    "NEXT_STAGE",
    "OutcomeContractFixtureAudit",
    "ProductionDestructiveAudit",
    "ProductionRejectionKindRow",
    "ProductionRejectionSurfaceCatalog",
    "ProspectiveTransition",
    "PublicFeedbackContract",
    "PublicFeedbackProjectionAudit",
    "PublicFeedbackProjectionRow",
    "StaticAudit",
    "StaticGate",
    "TransitiveSourceRoot",
    "V176DefectReproductionAudit",
    "V176PredecessorFreezeAudit",
    "V26_ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION",
    "identity",
    "make_identity_model",
]
