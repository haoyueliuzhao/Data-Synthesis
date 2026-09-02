# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = (
    "fresh_first_response_action_interface_disambiguation_paired_postrun_independent_audit.v1"
)
CONSUMED_STAGE: Final = (
    "fresh_first_response_action_interface_disambiguation_paired_24_call_"
    "online_calibration_postrun_independent_audit_only"
)
NEXT_STAGE: Final = (
    "fresh_repaired_action_interface_full_condition_integration_and_identity_preflight_only"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda item: item.model_dump(mode="json", warnings=False),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


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


class ExternalPostrunAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    audit_sha256: Literal["37c146cd27119983506520f1d5bbdabe3ca2003165d52510b184803eaa9a2d3d"]
    audit_byte_count: Literal[13644] = 13_644
    audited_experiment: Literal["Finance v26.204"] = "Finance v26.204"
    audit_decision: Literal["PASS_AS_SCOPED"] = "PASS_AS_SCOPED"
    scientific_result_accepted_as_scoped: Literal[True] = True
    report_revision_required: Literal[False] = False
    only_authorized_successor: Literal[
        "fresh_first_response_action_interface_disambiguation_paired_24_call_"
        "online_calibration_postrun_independent_audit_only"
    ] = CONSUMED_STAGE
    actual_artifact_independent_reconstruction_required: Literal[True] = True
    provider_calls_authorized: Literal[0] = 0
    additional_first_response_calibration_authorized: Literal[False] = False
    full_repaired_192_job_execution_authorized: Literal[False] = False
    parser_relaxation_or_response_adaptation_authorized: Literal[False] = False
    qa_mapper_state_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalPostrunAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_205_external_postrun_audit_authorization:",
        ):
            raise ValueError("v26.205 external postrun Audit Authorization identity differs")
        return self


class V204ExecutionFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v204_online_authorization_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    execution_summary_id: str = Field(min_length=1)
    saved_paired_evaluation_id: str = Field(min_length=1)
    saved_gate_evaluation_id: str = Field(min_length=1)
    execution_artifact_manifest_id: str = Field(min_length=1)
    execution_artifact_root: str = Field(min_length=1)
    v203_manifest_id: str = Field(min_length=1)
    v203_population_id: str = Field(min_length=1)
    v203_action_contract_id: str = Field(min_length=1)
    v203_gate_contract_id: str = Field(min_length=1)
    execution_source_commit: Literal["01924d88f9e57502cd981c9d3be16b298b2ad45c"]
    execution_source_tree: Literal["70db179b44eb8834c5fc09d77a7ca89b56ce3d44"]
    execution_status: Literal["completed"] = "completed"
    authorization_consumed_once: Literal[True] = True
    formal_directory_file_count: Literal[108] = 108
    formal_directory_total_byte_count: Literal[276582] = 276_582
    manifest_member_count: Literal[107] = 107
    manifest_member_total_byte_count: Literal[261434] = 261_434
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V204ExecutionFreeze:
        if self.freeze_id != identity(
            self,
            "freeze_id",
            "finance_v26_205_v204_execution_freeze:",
        ):
            raise ValueError("v26.205 v26.204 Execution Freeze identity differs")
        return self


class ArtifactByteReconstructionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    actual_directory_file_count: Literal[108] = 108
    actual_directory_total_byte_count: Literal[276582] = 276_582
    self_excluding_manifest_member_count: Literal[107] = 107
    self_excluding_manifest_total_byte_count: Literal[261434] = 261_434
    actual_path_match_count: Literal[107] = 107
    actual_sha256_match_count: Literal[107] = 107
    actual_byte_count_match_count: Literal[107] = 107
    unmanifested_path_count: Literal[0] = 0
    missing_path_count: Literal[0] = 0
    duplicate_manifest_path_count: Literal[0] = 0
    independently_recomputed_artifact_root: str = Field(min_length=1)
    saved_artifact_root: str = Field(min_length=1)
    artifact_root_match: Literal[True] = True
    saved_summary_used_as_outcome_oracle: Literal[False] = False
    saved_observation_used_as_outcome_oracle: Literal[False] = False
    saved_paired_evaluation_used_as_outcome_oracle: Literal[False] = False
    saved_gate_evaluation_used_as_outcome_oracle: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ArtifactByteReconstructionAudit:
        if self.independently_recomputed_artifact_root != self.saved_artifact_root:
            raise ValueError("v26.205 independently reconstructed Artifact Root differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_205_artifact_byte_reconstruction_audit:",
        ):
            raise ValueError("v26.205 Artifact Byte Reconstruction Audit identity differs")
        return self


class RequestIdentityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    v203_formal_file_count: Literal[15] = 15
    v203_formal_total_byte_count: Literal[582364] = 582_364
    v203_manifest_member_match_count: Literal[14] = 14
    exact_job_count: Literal[24] = 24
    exact_request_count: Literal[24] = 24
    reconstructed_request_body_hash_match_count: Literal[24] = 24
    raw_request_hash_parent_match_count: Literal[24] = 24
    telemetry_request_hash_match_count: Literal[24] = 24
    job_request_cell_arm_parent_match_count: Literal[24] = 24
    paired_semantic_parent_mismatch_count: Literal[0] = 0
    control_first_pair_count: Literal[6] = 6
    repair_first_pair_count: Literal[6] = 6
    adjacent_pair_count: Literal[12] = 12
    exact_sequential_ordinal_match_count: Literal[24] = 24
    stage_one_call_count: Literal[24] = 24
    stage_two_call_count: Literal[0] = 0
    retry_count: Literal[0] = 0
    recovery_call_count: Literal[0] = 0
    correction_call_count: Literal[0] = 0
    final_call_count: Literal[0] = 0
    http_success_count: Literal[24] = 24
    exact_model_match_count: Literal[24] = 24
    thinking_present_count: Literal[24] = 24
    complete_usage_count: Literal[24] = 24
    private_reasoning_content_persisted_count: Literal[0] = 0
    typed_outer_terminal_count: Literal[0] = 0
    source_commit_tree_match: Literal[True] = True
    authorization_single_consumption_match: Literal[True] = True
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RequestIdentityAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_205_request_identity_and_execution_geometry_audit:",
        ):
            raise ValueError("v26.205 Request Identity Audit identity differs")
        return self


class IndependentObservationRow(FrozenModel):
    row_id: str = Field(min_length=1)
    ordinal: int = Field(ge=0, le=23)
    job_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    source_cell_id: str = Field(min_length=1)
    stratum_id: str = Field(min_length=1)
    arm: Literal["C", "R"]
    raw_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    response_id: str = Field(min_length=1)
    saved_observation_id: str = Field(min_length=1)
    observation_record_id: str = Field(min_length=1)
    checkpoint_id: str = Field(min_length=1)
    public_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_response_shape: tuple[str, ...]
    exact_four_field_abi_valid: bool
    action_reference_valid: bool | None
    state_binding_valid: bool | None
    runtime_step_committed: None = None
    answer_schema_exact_match: bool
    operation_output_schema_exact_match: bool
    parser_rejection_reason: str | None
    independently_reconstructed_response_matches_saved: Literal[True] = True
    independently_reconstructed_observation_matches_saved: Literal[True] = True
    raw_result_observation_checkpoint_parent_chain_matches: Literal[True] = True
    downstream_null_when_abi_invalid: Literal[True] = True
    historical_payload_adaptation: Literal[False] = False
    parser_relaxation: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> IndependentObservationRow:
        if self.exact_four_field_abi_valid:
            if self.action_reference_valid is None or self.state_binding_valid is None:
                raise ValueError("v26.205 ABI-valid row lacks reference or State evaluation")
        elif self.action_reference_valid is not None or self.state_binding_valid is not None:
            raise ValueError("v26.205 ABI-invalid row fabricates downstream evaluation")
        if self.row_id != identity(
            self,
            "row_id",
            "finance_v26_205_independent_first_action_interface_observation_row:",
        ):
            raise ValueError("v26.205 independent Observation Row identity differs")
        return self


class IndependentObservationCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    request_identity_audit_id: str = Field(min_length=1)
    rows: tuple[IndependentObservationRow, ...] = Field(min_length=24, max_length=24)
    row_count: Literal[24] = 24
    unique_job_count: Literal[24] = 24
    unique_raw_count: Literal[24] = 24
    unique_result_count: Literal[24] = 24
    unique_response_count: Literal[24] = 24
    unique_observation_count: Literal[24] = 24
    unique_checkpoint_count: Literal[24] = 24
    saved_response_match_count: Literal[24] = 24
    saved_observation_match_count: Literal[24] = 24
    parent_chain_match_count: Literal[24] = 24
    frozen_parser_source_match: Literal[True] = True
    frozen_grammar_source_match: Literal[True] = True
    repair_four_action_named_field_count: Literal[12] = 12
    repair_invalid_decision_kind_count: Literal[1] = 1
    invalid_repair_downstream_null_count: Literal[1] = 1
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> IndependentObservationCatalog:
        if (
            tuple(row.ordinal for row in self.rows) != tuple(range(24))
            or len({row.job_id for row in self.rows}) != 24
            or len({row.raw_id for row in self.rows}) != 24
            or len({row.result_id for row in self.rows}) != 24
            or len({row.response_id for row in self.rows}) != 24
            or len({row.saved_observation_id for row in self.rows}) != 24
            or len({row.checkpoint_id for row in self.rows}) != 24
        ):
            raise ValueError("v26.205 independent Observation Catalog denominator differs")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_205_independent_observation_catalog:",
        ):
            raise ValueError("v26.205 independent Observation Catalog identity differs")
        return self


class IndependentPairedEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    catalog_id: str = Field(min_length=1)
    exact_job_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    row_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    source_cell_count: Literal[12] = 12
    control_abi_success_count: Literal[0] = 0
    repair_abi_success_count: Literal[11] = 11
    control_reference_state_valid_count: Literal[0] = 0
    repair_reference_state_valid_count: Literal[11] = 11
    control_answer_schema_exact_count: Literal[10] = 10
    repair_answer_schema_exact_count: Literal[0] = 0
    control_operation_output_exact_count: Literal[10] = 10
    repair_operation_output_exact_count: Literal[0] = 0
    paired_repair_only_abi_success_count: Literal[11] = 11
    paired_control_only_abi_success_count: Literal[0] = 0
    delta_abi_numerator: Literal[11] = 11
    delta_abi_denominator: Literal[12] = 12
    stratum_repair_reference_state_valid_counts: dict[str, int]
    saved_paired_evaluation_exact_match: Literal[True] = True
    capability_estimate: None = None
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> IndependentPairedEvaluation:
        if (
            len(set(self.exact_job_ids)) != 24
            or len(set(self.row_ids)) != 24
            or sorted(self.stratum_repair_reference_state_valid_counts.values()) != [2, 3, 3, 3]
        ):
            raise ValueError("v26.205 independent paired Evaluation geometry differs")
        if self.evaluation_id != identity(
            self,
            "evaluation_id",
            "finance_v26_205_independent_paired_calibration_evaluation:",
        ):
            raise ValueError("v26.205 independent Paired Evaluation identity differs")
        return self


class IndependentGateReconstruction(FrozenModel):
    gate_reconstruction_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    evaluation_id: str = Field(min_length=1)
    g0_actual_complete_evidence_count: Literal[24] = 24
    g1_actual_paired_semantic_parent_mismatch_count: Literal[0] = 0
    g2_actual_parser_grammar_candidate_change_count: Literal[0] = 0
    g3_actual_repair_exact_action_abi_count: Literal[11] = 11
    g4_actual_repair_reference_state_valid_count: Literal[11] = 11
    g5_actual_paired_repair_only_abi_success_count: Literal[11] = 11
    g6_actual_paired_control_only_abi_success_count: Literal[0] = 0
    g7_actual_adaptation_relaxation_retry_count: Literal[0] = 0
    g8_actual_qa_mapper_state_contribution_vtdo_count: Literal[0] = 0
    g0_passed: Literal[True] = True
    g1_passed: Literal[True] = True
    g2_passed: Literal[True] = True
    g3_passed: Literal[True] = True
    g4_passed: Literal[True] = True
    g5_passed: Literal[True] = True
    g6_passed: Literal[True] = True
    g7_passed: Literal[True] = True
    g8_passed: Literal[True] = True
    all_gates_passed: Literal[True] = True
    exact_mcnemar_supplementary_two_sided_p: Literal["0.0009765625"] = "0.0009765625"
    saved_gate_evaluation_exact_match: Literal[True] = True
    gate_compensation_used: Literal[False] = False
    capability_estimate: None = None
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> IndependentGateReconstruction:
        if self.gate_reconstruction_id != identity(
            self,
            "gate_reconstruction_id",
            "finance_v26_205_independent_online_gate_reconstruction:",
        ):
            raise ValueError("v26.205 independent Gate Reconstruction identity differs")
        return self


class NegativeControlResult(FrozenModel):
    result_id: str = Field(min_length=1)
    control_name: Literal[
        "changed_raw_response_bytes",
        "cross_arm_parent_binding",
        "missing_job",
        "duplicate_job",
        "revise_selector_posthoc_adaptation",
    ]
    expected_rejection_reason: str = Field(min_length=1)
    observed_rejection_reason: str = Field(min_length=1)
    rejected: Literal[True] = True
    accepted: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> NegativeControlResult:
        if self.result_id != identity(
            self,
            "result_id",
            "finance_v26_205_negative_control_result:",
        ):
            raise ValueError("v26.205 negative Control Result identity differs")
        return self


class NegativeControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    catalog_id: str = Field(min_length=1)
    controls: tuple[NegativeControlResult, ...] = Field(min_length=5, max_length=5)
    control_count: Literal[5] = 5
    rejected_control_count: Literal[5] = 5
    accepted_control_count: Literal[0] = 0
    response_byte_change_rejected: Literal[True] = True
    cross_arm_parent_rejected: Literal[True] = True
    missing_or_duplicate_job_rejected_count: Literal[2] = 2
    posthoc_adaptation_rejected: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> NegativeControlAudit:
        if len({item.control_name for item in self.controls}) != 5:
            raise ValueError("v26.205 negative Control set differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_205_postrun_negative_control_audit:",
        ):
            raise ValueError("v26.205 negative Control Audit identity differs")
        return self


class PostrunIndependentAuditDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    byte_reconstruction_audit_id: str = Field(min_length=1)
    request_identity_audit_id: str = Field(min_length=1)
    observation_catalog_id: str = Field(min_length=1)
    independent_evaluation_id: str = Field(min_length=1)
    gate_reconstruction_id: str = Field(min_length=1)
    negative_control_audit_id: str = Field(min_length=1)
    decision: Literal[
        "v26_204_paired_online_calibration_complete_auditable_and_scientific_result_accepted_as_scoped"
    ]
    v204_actual_artifact_authority: Literal["independently_reconstructed"]
    v204_scientific_result: Literal["accepted_as_scoped"]
    first_response_interface_gate: Literal["empirically_passed_on_exact_calibration_surface"]
    composite_repair_effect_supported: Literal[True] = True
    individual_submechanism_effect_identified: Literal[False] = False
    full_program_capability_instantiated: Literal[False] = False
    historical_v200_estimates_modified: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    full_repaired_192_job_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> PostrunIndependentAuditDecision:
        if self.decision_id != identity(
            self,
            "decision_id",
            "finance_v26_205_postrun_independent_audit_decision:",
        ):
            raise ValueError("v26.205 postrun Audit Decision identity differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    next_stage: Literal[
        "fresh_repaired_action_interface_full_condition_integration_and_identity_preflight_only"
    ] = NEXT_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    fresh_identity_chain_required: Literal[True] = True
    full_repaired_192_job_execution_authorized: Literal[False] = False
    additional_interface_calibration_authorized: Literal[False] = False
    parser_relaxation_authorized: Literal[False] = False
    historical_response_adaptation_authorized: Literal[False] = False
    interface_factor_decomposition_authorized: Literal[False] = False
    qa_mapper_state_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_205_transition:",
        ):
            raise ValueError("v26.205 prospective Transition identity differs")
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
        if (
            tuple(item.relative_path for item in self.members)
            != tuple(sorted(item.relative_path for item in self.members))
            or len({item.relative_path for item in self.members}) != len(self.members)
            or self.file_count != len(self.members)
            or self.total_byte_count != sum(item.byte_count for item in self.members)
        ):
            raise ValueError("v26.205 Artifact Manifest geometry differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_205_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("v26.205 Artifact Root differs")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "finance_v26_205_artifact_manifest:",
        ):
            raise ValueError("v26.205 Artifact Manifest identity differs")
        return self


def artifact_manifest(*, run_id: str, members: tuple[ArtifactMember, ...]) -> ArtifactManifest:
    root = canonical_hash(
        tuple(item.model_dump(mode="json") for item in members),
        prefix="finance_v26_205_artifact_root:",
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
            prefix="finance_v26_205_artifact_manifest:",
        ),
    )
