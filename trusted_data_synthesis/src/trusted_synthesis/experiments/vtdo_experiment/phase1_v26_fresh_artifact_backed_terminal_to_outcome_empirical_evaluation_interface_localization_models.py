from __future__ import annotations

from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.fresh_artifact_backed_terminal_to_outcome_integration import (
    ReachableTerminalKind,
)
from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_terminal_to_outcome_empirical_evaluation_interface_localization.v1"
CONSUMED_STAGE: Final = (
    "v26_200_exact_empirical_evidence_set_evaluation_and_first_response_interface_localization_only"
)
NEXT_DECISION: Final = "no_further_experiment_authorized_without_new_audit_decision"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


def make_identity(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: identity(provisional, field, prefix)}, **values)


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    audit_sha256: Literal["b534d14cf53d5ed6fbb65f59647f8e244e220f3ea160f85b74ac47da2724034e"]
    audit_byte_count: Literal[10706] = 10_706
    audit_decision: Literal[
        "v26_200_v26_201_accepted_with_estimand_correction_and_zero_provider_"
        "exact_set_evaluation_interface_localization_only_authorized"
    ]
    consumed_stage: Literal[
        "v26_200_exact_empirical_evidence_set_evaluation_and_first_response_"
        "interface_localization_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[False] = False
    rerun_authorized: Literal[False] = False
    recovery_authorized: Literal[False] = False
    historical_response_adaptation_authorized: Literal[False] = False
    exact_set_evaluation_authorized: Literal[True] = True
    prompt_reconstruction_authorized: Literal[True] = True
    prompt_or_grammar_change_authorized: Literal[False] = False
    mapper_state_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_202_external_audit_authorization:",
        ):
            raise ValueError("v26.202 external Audit authorization identity differs")
        return self


class V201AuditFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v201_decision_id: str = Field(min_length=1)
    v201_byte_reconstruction_audit_id: str = Field(min_length=1)
    v201_response_interface_audit_id: str = Field(min_length=1)
    v201_artifact_manifest_id: str = Field(min_length=1)
    v201_artifact_root: str = Field(min_length=1)
    v201_source_commit: Literal["42d071da62bfc538e555fbb4200c02627113913a"]
    v201_source_tree: Literal["87ca269b075f629d9b36c21764536c5953a4ecb7"]
    formal_file_count: Literal[8] = 8
    formal_total_byte_count: Literal[285649] = 285_649
    exact_job_count: Literal[192] = 192
    raw_result_trace_outcome_counts: tuple[
        Literal[192], Literal[192], Literal[192], Literal[192]
    ] = (
        192,
        192,
        192,
        192,
    )
    evidence_audit_accepted: Literal[True] = True
    scientific_interpretation: Literal["accepted_with_estimand_correction"] = (
        "accepted_with_estimand_correction"
    )
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V201AuditFreeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_202_v201_audit_freeze:"):
            raise ValueError("v26.202 v26.201 Audit Freeze identity differs")
        return self


class EmpiricalEvidenceSetRow(FrozenModel):
    evaluation_row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    terminal_kind: ReachableTerminalKind
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    outcome_row_id: str = Field(min_length=1)
    formal_empirical_row: Literal[True] = True
    included_in_end_to_end_denominator: Literal[True] = True
    exact_action_abi_crossed: Literal[False] = False
    complete_qualified_endpoint: Literal[False] = False
    q_first_success: Literal[False] = False
    q_bounded_correction_success: Literal[False] = False
    post_action_abi_semantic_evaluable: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> EmpiricalEvidenceSetRow:
        if self.evaluation_row_id != identity(
            self,
            "evaluation_row_id",
            "finance_v26_202_empirical_evidence_set_row:",
        ):
            raise ValueError("v26.202 empirical evidence-set row identity differs")
        return self


class ExactEmpiricalEvidenceSetEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v201_freeze_id: str = Field(min_length=1)
    frozen_v195_evaluator_contract_id: str = Field(min_length=1)
    frozen_v195_evaluator_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frozen_v195_parent_validator_applied: Literal[True] = True
    frozen_v195_public_entrypoint_empirical_compatible: Literal[False] = False
    v202_empirical_authorization_overlay_applied: Literal[True] = True
    rows: tuple[EmpiricalEvidenceSetRow, ...] = Field(min_length=192, max_length=192)
    exact_manifest_job_count: Literal[192] = 192
    formal_empirical_row_count: Literal[192] = 192
    included_job_count: Literal[192] = 192
    excluded_job_count: Literal[0] = 0
    first_response_abi_invalid_count: Literal[188] = 188
    thinking_integrity_failure_count: Literal[4] = 4
    q_first_numerator: Literal[0] = 0
    q_first_denominator: Literal[192] = 192
    q_first_fraction: Literal["0/192"] = "0/192"
    q_bounded_correction_numerator: Literal[0] = 0
    q_bounded_correction_denominator: Literal[192] = 192
    q_bounded_correction_fraction: Literal["0/192"] = "0/192"
    post_action_abi_denominator: Literal[0] = 0
    post_action_abi_conditional_semantic_fraction: None = None
    post_action_abi_trajectory_depth_capability: None = None
    formal_end_to_end_estimate_materialized: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> ExactEmpiricalEvidenceSetEvaluation:
        if (
            len({item.job_id for item in self.rows}) != 192
            or len({item.raw_execution_id for item in self.rows}) != 192
            or len({item.result_id for item in self.rows}) != 192
            or len({item.trace_id for item in self.rows}) != 192
            or len({item.outcome_row_id for item in self.rows}) != 192
            or sum(item.q_first_success for item in self.rows) != 0
            or sum(item.q_bounded_correction_success for item in self.rows) != 0
        ):
            raise ValueError("v26.202 exact empirical denominator differs")
        if self.evaluation_id != identity(
            self,
            "evaluation_id",
            "finance_v26_202_exact_empirical_evidence_set_evaluation:",
        ):
            raise ValueError("v26.202 exact empirical Evaluation identity differs")
        return self


class FirstPromptLocalizationRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_byte_count: int = Field(gt=0, le=60000)
    prepared_request_id: str = Field(min_length=1)
    observed_prepared_request_id: str | None
    dynamic_certificate_id: str = Field(min_length=1)
    observed_dynamic_certificate_id: str | None
    request_hash_match: Literal[True] = True
    persisted_envelope_present: bool
    prepared_request_identity_match: bool | None
    dynamic_certificate_identity_match: bool | None
    response_payload_key_shape: tuple[str, ...] | None
    action_abi_target_fields: tuple[str, ...] = (
        "action_id",
        "decision_kind",
        "protocol",
        "state_id",
    )
    direct_response_abi_fields: tuple[str, ...] = (
        "decision_kind",
        "protocol",
        "state_id",
    )
    action_id_visible_only_in_candidate_rows: Literal[True] = True
    answer_fields: tuple[str, ...]
    operation_output_field_sets: tuple[tuple[str, ...], ...]
    candidate_fields: tuple[str, ...]
    response_matches_answer_schema: bool
    response_matches_operation_output_schema: bool
    answer_schema_offset: int = Field(ge=0)
    operation_output_schema_offset: int = Field(ge=0)
    candidate_schema_offset: int = Field(ge=0)
    response_abi_offset: int = Field(ge=0)
    provider_instruction_offset: int = Field(ge=0)
    single_user_message: Literal[True] = True
    system_message_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> FirstPromptLocalizationRow:
        if self.prompt_sha256 != self.actual_request_sha256 or not (
            self.answer_schema_offset
            < self.operation_output_schema_offset
            < self.response_abi_offset
            < self.provider_instruction_offset
        ):
            raise ValueError("v26.202 exact first-Prompt reconstruction differs")
        expected_match = True if self.persisted_envelope_present else None
        if (
            self.prepared_request_identity_match is not expected_match
            or self.dynamic_certificate_identity_match is not expected_match
            or (
                self.persisted_envelope_present
                and (
                    self.prepared_request_id != self.observed_prepared_request_id
                    or self.dynamic_certificate_id != self.observed_dynamic_certificate_id
                )
            )
            or (
                not self.persisted_envelope_present
                and (
                    self.observed_prepared_request_id is not None
                    or self.observed_dynamic_certificate_id is not None
                )
            )
        ):
            raise ValueError("v26.202 persisted request identity availability differs")
        if self.row_id != identity(
            self,
            "row_id",
            "finance_v26_202_first_prompt_localization_row:",
        ):
            raise ValueError("v26.202 first-Prompt localization row identity differs")
        return self


class FieldSourceRow(FrozenModel):
    field_source_id: str = Field(min_length=1)
    field_name: str = Field(min_length=1)
    actual_response_count: int = Field(ge=0, le=188)
    answer_schema_prompt_count: int = Field(ge=0, le=192)
    operation_output_schema_prompt_count: int = Field(ge=0, le=192)
    action_abi_prompt_count: int = Field(ge=0, le=192)
    candidate_representation_prompt_count: int = Field(ge=0, le=192)
    source_classification: Literal[
        "action_abi",
        "candidate_representation",
        "task_answer_or_operation_output",
        "mixed_visible_sources",
        "unlocated_visible_field",
    ]
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> FieldSourceRow:
        if self.field_source_id != identity(
            self,
            "field_source_id",
            "finance_v26_202_field_source_row:",
        ):
            raise ValueError("v26.202 field-source row identity differs")
        return self


class FirstResponseInterfaceLocalization(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    evaluation_id: str = Field(min_length=1)
    prompt_rows: tuple[FirstPromptLocalizationRow, ...] = Field(min_length=192, max_length=192)
    field_sources: tuple[FieldSourceRow, ...] = Field(min_length=7)
    exact_first_prompt_count: Literal[192] = 192
    prompt_hash_match_count: Literal[192] = 192
    persisted_envelope_count: Literal[188] = 188
    missing_envelope_thinking_terminal_count: Literal[4] = 4
    prepared_request_identity_match_count: Literal[188] = 188
    dynamic_certificate_identity_match_count: Literal[188] = 188
    exact_action_abi_crossing_count: Literal[0] = 0
    public_response_count: Literal[188] = 188
    response_exact_answer_schema_match_count: int = Field(ge=0, le=188)
    response_exact_operation_output_schema_match_count: int = Field(ge=0, le=188)
    response_exact_answer_or_operation_match_count: int = Field(ge=0, le=188)
    dominant_difference_higher_ref_count: Literal[128] = 128
    value_only_count: Literal[39] = 39
    dominant_two_shape_count: Literal[167] = 167
    response_abi_missing_explicit_action_id_count: Literal[192] = 192
    answer_schema_precedes_response_abi_count: Literal[192] = 192
    operation_schema_precedes_response_abi_count: Literal[192] = 192
    provider_instruction_after_response_abi_count: Literal[192] = 192
    provider_message_role: Literal["user"] = "user"
    system_message_count: Literal[0] = 0
    structural_competing_schema_overlap_confirmed: Literal[True] = True
    causal_attribution_proven: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FirstResponseInterfaceLocalization:
        if (
            len({item.job_id for item in self.prompt_rows}) != 192
            or sum(item.response_payload_key_shape is not None for item in self.prompt_rows) != 188
            or self.response_exact_answer_or_operation_match_count
            != sum(
                item.response_matches_answer_schema or item.response_matches_operation_output_schema
                for item in self.prompt_rows
            )
        ):
            raise ValueError("v26.202 Prompt localization denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_202_first_response_interface_localization:",
        ):
            raise ValueError("v26.202 first-response localization identity differs")
        return self


class AttackResult(FrozenModel):
    attack_id: str = Field(min_length=1)
    attack_name: str = Field(min_length=1)
    target: str = Field(min_length=1)
    expected_reason: str = Field(min_length=1)
    actual_reason: str = Field(min_length=1)
    rejected: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_attack(self) -> AttackResult:
        if self.attack_id != identity(self, "attack_id", "finance_v26_202_attack:"):
            raise ValueError("v26.202 attack identity differs")
        return self


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    evaluation_id: str = Field(min_length=1)
    localization_id: str = Field(min_length=1)
    attacks: tuple[AttackResult, ...] = Field(min_length=8, max_length=8)
    attack_count: Literal[8] = 8
    rejection_count: Literal[8] = 8
    accepted_attack_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if len({item.attack_name for item in self.attacks}) != 8:
            raise ValueError("v26.202 destructive denominator differs")
        if self.audit_id != identity(self, "audit_id", "finance_v26_202_destructive_audit:"):
            raise ValueError("v26.202 destructive Audit identity differs")
        return self


class Decision(FrozenModel):
    decision_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    evaluation_id: str = Field(min_length=1)
    localization_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    decision: Literal[
        "end_to_end_zero_capability_rates_materialized_and_first_response_"
        "interface_structurally_localized"
    ]
    evidence_audit: Literal["accepted"] = "accepted"
    scientific_interpretation: Literal["accepted_with_correction"] = "accepted_with_correction"
    first_fundamental_blocker: Literal["first_response_action_interface_admission"] = (
        "first_response_action_interface_admission"
    )
    q_first_fraction: Literal["0/192"] = "0/192"
    q_bounded_correction_fraction: Literal["0/192"] = "0/192"
    post_action_abi_conditional_capability: None = None
    prompt_interface_repair_completed: Literal[False] = False
    rerun_or_recovery_permitted: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> Decision:
        if self.decision_id != identity(self, "decision_id", "finance_v26_202_decision:"):
            raise ValueError("v26.202 Decision identity differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    next_decision: Literal["no_further_experiment_authorized_without_new_audit_decision"] = (
        NEXT_DECISION
    )
    provider_execution_authorized: Literal[False] = False
    full_192_job_rerun_authorized: Literal[False] = False
    recovery_authorized: Literal[False] = False
    historical_payload_adaptation_authorized: Literal[False] = False
    prompt_interface_repair_authorized: Literal[False] = False
    small_stratified_online_calibration_authorized: Literal[False] = False
    qa_mapper_state_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> Transition:
        if self.transition_id != identity(self, "transition_id", "finance_v26_202_transition:"):
            raise ValueError("v26.202 Transition identity differs")
        return self


class ArtifactMember(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ArtifactManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    members: tuple[ArtifactMember, ...] = Field(min_length=1)
    file_count: int = Field(gt=0)
    total_byte_count: int = Field(gt=0)
    artifact_root: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ArtifactManifest:
        paths = tuple(item.relative_path for item in self.members)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.202 artifact member set differs")
        if self.file_count != len(self.members) or self.total_byte_count != sum(
            item.byte_count for item in self.members
        ):
            raise ValueError("v26.202 artifact aggregate differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_202_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("v26.202 artifact Root differs")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "finance_v26_202_artifact_manifest:",
        ):
            raise ValueError("v26.202 artifact Manifest identity differs")
        return self


def artifact_manifest(*, run_id: str, members: tuple[ArtifactMember, ...]) -> ArtifactManifest:
    root = canonical_hash(
        tuple(item.model_dump(mode="json") for item in members),
        prefix="finance_v26_202_artifact_root:",
    )
    return cast(
        ArtifactManifest,
        make_identity(
            ArtifactManifest,
            {
                "run_id": run_id,
                "members": members,
                "file_count": len(members),
                "total_byte_count": sum(item.byte_count for item in members),
                "artifact_root": root,
            },
            field="manifest_id",
            prefix="finance_v26_202_artifact_manifest:",
        ),
    )
