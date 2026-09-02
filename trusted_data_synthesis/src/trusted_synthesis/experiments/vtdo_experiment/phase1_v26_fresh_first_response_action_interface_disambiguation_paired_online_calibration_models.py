# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_calibration_preflight_models as v203_models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry

SCHEMA_VERSION: Final = (
    "fresh_first_response_action_interface_disambiguation_paired_online_calibration.v1"
)
CONSUMED_STAGE: Final = (
    "fresh_first_response_action_interface_disambiguation_paired_24_call_online_calibration_only"
)
NEXT_STAGE: Final = (
    "fresh_first_response_action_interface_disambiguation_paired_24_call_"
    "online_calibration_postrun_independent_audit_only"
)

ExecutionStatus = Literal["completed", "failed", "interrupted"]


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


class ExternalOnlineAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    audit_sha256: Literal["58ddefdbe073456a6bd462b50f59f7b3a1083bb6797dbca806dbbb9ed39ce7e8"]
    audit_byte_count: Literal[14139] = 14_139
    audited_experiment: Literal["Finance v26.203"] = "Finance v26.203"
    audit_decision: Literal["PASS_AS_SCOPED"] = "PASS_AS_SCOPED"
    report_revision_required: Literal[False] = False
    v203_decision_id: str = Field(min_length=1)
    v203_transition_id: str = Field(min_length=1)
    v203_manifest_id: str = Field(min_length=1)
    v203_action_contract_id: str = Field(min_length=1)
    v203_gate_contract_id: str = Field(min_length=1)
    only_authorized_successor: Literal[
        "fresh_first_response_action_interface_disambiguation_paired_24_call_"
        "online_calibration_only"
    ] = CONSUMED_STAGE
    exact_provider_call_limit: Literal[24] = 24
    calls_per_job: Literal[1] = 1
    stage_two_call_limit: Literal[0] = 0
    retry_limit: Literal[0] = 0
    recovery_call_limit: Literal[0] = 0
    correction_call_limit: Literal[0] = 0
    final_call_limit: Literal[0] = 0
    manifest_order_required: Literal[True] = True
    precredential_single_consumption_required: Literal[True] = True
    durable_run_start_required: Literal[True] = True
    fixed_denominator_including_outer_terminals: Literal[24] = 24
    postrun_independent_audit_only: Literal[True] = True
    full_192_job_execution_authorized: Literal[False] = False
    qa_mapper_state_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalOnlineAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_204_external_online_authorization:",
        ):
            raise ValueError("v26.204 external online Authorization identity differs")
        return self


class V203Freeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_commit: Literal["511b9603fe9cdced1b8ea49f5753515318c827e8"]
    source_tree: Literal["2ba56b284f3b7119cce41bff33d70c9bf231b86b"]
    artifact_manifest_id: Literal[
        "finance_v26_203_artifact_manifest:"
        "d6a2c5a261758ac46343955d9f26206f8fb3e3565d5fd8aae4474c7707655c6a"
    ]
    artifact_root: Literal[
        "finance_v26_203_artifact_root:"
        "a9c21c4ed2a3276496ebb14c54d26dd3b3cb3700a93eee5aee630419564315b3"
    ]
    decision_id: Literal[
        "finance_v26_203_decision:94439fc523b8956d53f682dbe836c41416008aa7eb1c675d68f5b99829a79132"
    ]
    transition_id: Literal[
        "finance_v26_203_transition:"
        "6b2d408d70101e1da407084003574358e6276f2f67a2d13eee2de8874c9149d3"
    ]
    population_id: Literal[
        "fresh_first_response_stratified_calibration_population:"
        "fd6ec4188bf67da6d80f7e186e10cf56b05f9713c3141a443e60f67a96804f0b"
    ]
    manifest_id: Literal[
        "fresh_first_response_calibration_manifest:"
        "bfcc54e24f8abb48304b7f98a9265a085b545393c12b391d08b4259f063b145c"
    ]
    action_contract_id: Literal[
        "fresh_first_response_exact_action_interface_contract:"
        "a95252bf3ce3d3c510636034f151eb5c8f219ee42c6e09f0fd8848f58bd0ffc1"
    ]
    evidence_schema_audit_id: Literal[
        "finance_v26_203_calibration_evidence_schema_audit:"
        "087cd064739be84827d3983ee6be67c592992fd12cb747d76d609a070b64d518"
    ]
    gate_contract_id: Literal[
        "fresh_first_response_online_calibration_gate_contract:"
        "a997e5617585e79951524bdff3dbb6fb25d0e87f8203c7a25814e31bbe55c9e8"
    ]
    formal_file_count: Literal[15] = 15
    formal_total_byte_count: Literal[582364] = 582_364
    actual_path_match_count: Literal[15] = 15
    actual_sha256_match_count: Literal[15] = 15
    actual_byte_count_match_count: Literal[15] = 15
    historical_response_adaptation: Literal[False] = False
    parser_relaxation: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V203Freeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_204_v203_freeze:"):
            raise ValueError("v26.204 v26.203 Freeze identity differs")
        return self


class ExecutionOrderEntry(FrozenModel):
    ordinal: int = Field(ge=0, le=23)
    source_cell_ordinal: int = Field(ge=0, le=11)
    job_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    pair_id: str = Field(min_length=1)
    source_cell_id: str = Field(min_length=1)
    arm: v203_models.Arm
    execution_order_within_pair: Literal[0, 1]


class OnlineExecutionPreparation(FrozenModel):
    preparation_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v203_freeze_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    action_contract_id: str = Field(min_length=1)
    evidence_schema_audit_id: str = Field(min_length=1)
    gate_contract_id: str = Field(min_length=1)
    interface_profile_ids: tuple[str, str]
    execution_order: tuple[ExecutionOrderEntry, ...] = Field(min_length=24, max_length=24)
    exact_job_count: Literal[24] = 24
    exact_request_count: Literal[24] = 24
    exact_source_cell_count: Literal[12] = 12
    control_first_pair_count: Literal[6] = 6
    repair_first_pair_count: Literal[6] = 6
    v203_formal_file_revalidation_count: Literal[15] = 15
    request_body_hash_revalidation_count: Literal[24] = 24
    credential_lookup_attempted: Literal[False] = False
    provider_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_preparation(self) -> OnlineExecutionPreparation:
        if tuple(item.ordinal for item in self.execution_order) != tuple(range(24)):
            raise ValueError("v26.204 execution ordinals differ")
        if (
            len({item.job_id for item in self.execution_order}) != 24
            or len({item.request_id for item in self.execution_order}) != 24
        ):
            raise ValueError("v26.204 execution order denominator differs")
        if self.preparation_id != identity(
            self,
            "preparation_id",
            "finance_v26_204_online_execution_preparation:",
        ):
            raise ValueError("v26.204 online Preparation identity differs")
        return self


class OnlineAuthorizationAdmission(FrozenModel):
    admission_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    preparation_id: str = Field(min_length=1)
    canonical_authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    consumed_stage: Literal[
        "fresh_first_response_action_interface_disambiguation_paired_24_call_"
        "online_calibration_only"
    ] = CONSUMED_STAGE
    authorization_consumed: Literal[True] = True
    execution_ordinal: Literal[1] = 1
    admitted_before_output_directory_creation: Literal[True] = True
    admitted_before_credential_lookup: Literal[True] = True
    admitted_before_provider_client_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    provider_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_admission(self) -> OnlineAuthorizationAdmission:
        if self.admission_id != identity(
            self,
            "admission_id",
            "finance_v26_204_online_authorization_admission:",
        ):
            raise ValueError("v26.204 online Admission identity differs")
        return self


class RunStartReceipt(FrozenModel):
    receipt_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    admission_id: str = Field(min_length=1)
    preparation_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    exact_execution_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    execution_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    started_at_utc: str = Field(min_length=1)
    authorization_consumed: Literal[True] = True
    manifest_execution_ordinal: Literal[1] = 1
    durable_before_credential_lookup: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    provider_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_receipt(self) -> RunStartReceipt:
        if self.receipt_id != identity(
            self,
            "receipt_id",
            "finance_v26_204_online_run_start_receipt:",
        ):
            raise ValueError("v26.204 Run Start Receipt identity differs")
        return self


class PublicProviderCallRaw(FrozenModel):
    raw_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    ordinal: int = Field(ge=0, le=23)
    job_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    source_cell_id: str = Field(min_length=1)
    arm: v203_models.Arm
    raw_namespace: str = Field(min_length=1)
    canonical_request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_response_object: dict[str, Any] | None
    typed_outer_terminal: str | None
    exception_type: str | None
    exception_reason_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    telemetry: ModelCallTelemetry
    provider_call_count: Literal[1] = 1
    stage_two_call_count: Literal[0] = 0
    retry_count: Literal[0] = 0
    recovery_call_count: Literal[0] = 0
    correction_call_count: Literal[0] = 0
    final_call_count: Literal[0] = 0
    private_reasoning_content_persisted: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_raw(self) -> PublicProviderCallRaw:
        if (self.public_response_object is None) == (self.typed_outer_terminal is None):
            raise ValueError("v26.204 Raw must contain one public response or one outer terminal")
        if self.public_response_object is not None and self.exception_type is not None:
            raise ValueError("v26.204 successful Raw carries an exception")
        if self.raw_id != identity(
            self,
            "raw_id",
            "fresh_first_response_calibration_public_provider_raw:",
        ):
            raise ValueError("v26.204 public Provider Raw identity differs")
        return self


class CalibrationJobResult(FrozenModel):
    result_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    ordinal: int = Field(ge=0, le=23)
    job_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    source_cell_id: str = Field(min_length=1)
    arm: v203_models.Arm
    raw_id: str = Field(min_length=1)
    result_namespace: str = Field(min_length=1)
    response: v203_models.FirstResponseDescriptor
    provider_call_count: Literal[1] = 1
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> CalibrationJobResult:
        if (
            self.response.job_id != self.job_id
            or self.response.request_id != self.request_id
            or self.response.source_cell_id != self.source_cell_id
            or self.response.arm != self.arm
            or self.response.evidence_kind != "empirical_calibration"
            or self.response.provider_call_count != 1
        ):
            raise ValueError("v26.204 Result-to-Response parent differs")
        if self.result_id != identity(
            self,
            "result_id",
            "fresh_first_response_calibration_job_result:",
        ):
            raise ValueError("v26.204 Calibration Job Result identity differs")
        return self


class ObservationRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    ordinal: int = Field(ge=0, le=23)
    job_id: str = Field(min_length=1)
    raw_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    observation_namespace: str = Field(min_length=1)
    observation: v203_models.FirstActionInterfaceObservation
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> ObservationRecord:
        if self.observation.job_id != self.job_id:
            raise ValueError("v26.204 Observation Record Job parent differs")
        if self.record_id != identity(
            self,
            "record_id",
            "fresh_first_response_calibration_observation_record:",
        ):
            raise ValueError("v26.204 Observation Record identity differs")
        return self


class OnlineGateEvaluation(FrozenModel):
    gate_evaluation_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    gate_contract_id: str = Field(min_length=1)
    paired_evaluation_id: str = Field(min_length=1)
    g0_actual_complete_evidence_count: int = Field(ge=0, le=24)
    g1_actual_paired_semantic_parent_mismatch_count: int = Field(ge=0)
    g2_actual_parser_grammar_candidate_change_count: int = Field(ge=0)
    g3_actual_repair_exact_action_abi_count: int = Field(ge=0, le=12)
    g4_actual_repair_reference_state_valid_count: int = Field(ge=0, le=12)
    g5_actual_paired_repair_only_abi_success_count: int = Field(ge=0, le=12)
    g6_actual_paired_control_only_abi_success_count: int = Field(ge=0, le=12)
    g7_actual_adaptation_relaxation_retry_count: int = Field(ge=0)
    g8_actual_qa_mapper_state_contribution_vtdo_count: int = Field(ge=0)
    g0_passed: bool
    g1_passed: bool
    g2_passed: bool
    g3_passed: bool
    g4_passed: bool
    g5_passed: bool
    g6_passed: bool
    g7_passed: bool
    g8_passed: bool
    all_gates_passed: bool
    gate_compensation_used: Literal[False] = False
    exact_mcnemar_supplementary_two_sided_p: str | None
    capability_estimate: None = None
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate_evaluation(self) -> OnlineGateEvaluation:
        passes = (
            self.g0_passed,
            self.g1_passed,
            self.g2_passed,
            self.g3_passed,
            self.g4_passed,
            self.g5_passed,
            self.g6_passed,
            self.g7_passed,
            self.g8_passed,
        )
        if self.all_gates_passed != all(passes):
            raise ValueError("v26.204 noncompensatory Gate conjunction differs")
        if self.gate_evaluation_id != identity(
            self,
            "gate_evaluation_id",
            "finance_v26_204_online_gate_evaluation:",
        ):
            raise ValueError("v26.204 online Gate Evaluation identity differs")
        return self


class ExecutionCheckpoint(FrozenModel):
    checkpoint_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    ordinal: int = Field(ge=0, le=23)
    job_id: str = Field(min_length=1)
    raw_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    observation_record_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_checkpoint(self) -> ExecutionCheckpoint:
        if self.checkpoint_id != identity(
            self,
            "checkpoint_id",
            "finance_v26_204_online_execution_checkpoint:",
        ):
            raise ValueError("v26.204 Checkpoint identity differs")
        return self


class OnlineExecutionSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    paired_evaluation_id: str | None
    gate_evaluation_id: str | None
    execution_status: ExecutionStatus
    attempted_job_count: int = Field(ge=0, le=24)
    raw_count: int = Field(ge=0, le=24)
    result_count: int = Field(ge=0, le=24)
    observation_count: int = Field(ge=0, le=24)
    provider_calls: int = Field(ge=0, le=24)
    stage_two_calls: Literal[0] = 0
    retry_count: Literal[0] = 0
    recovery_call_count: Literal[0] = 0
    correction_call_count: Literal[0] = 0
    final_call_count: Literal[0] = 0
    typed_outer_terminal_partition: dict[str, int]
    total_usage_tokens: int = Field(ge=0)
    estimated_cost_usd: str
    all_online_gates_passed: bool | None
    full_192_job_execution_authorized: Literal[False] = False
    next_stage: Literal[
        "fresh_first_response_action_interface_disambiguation_paired_24_call_"
        "online_calibration_postrun_independent_audit_only"
    ] = NEXT_STAGE
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> OnlineExecutionSummary:
        if self.execution_status == "completed" and (
            self.attempted_job_count,
            self.raw_count,
            self.result_count,
            self.observation_count,
            self.provider_calls,
        ) != (24, 24, 24, 24, 24):
            raise ValueError("v26.204 completed Summary denominator differs")
        if self.summary_id != identity(
            self,
            "summary_id",
            "finance_v26_204_online_execution_summary:",
        ):
            raise ValueError("v26.204 online Summary identity differs")
        return self


class ArtifactMember(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ExecutionArtifactManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    members: tuple[ArtifactMember, ...] = Field(min_length=1)
    file_count: int = Field(gt=0)
    total_byte_count: int = Field(gt=0)
    artifact_root: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ExecutionArtifactManifest:
        paths = tuple(item.relative_path for item in self.members)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.204 artifact member set differs")
        if self.file_count != len(self.members) or self.total_byte_count != sum(
            item.byte_count for item in self.members
        ):
            raise ValueError("v26.204 artifact aggregate differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_204_execution_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("v26.204 artifact Root differs")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "finance_v26_204_execution_artifact_manifest:",
        ):
            raise ValueError("v26.204 artifact Manifest identity differs")
        return self


def make_paired_evaluation(
    *,
    manifest_id: str,
    observations: tuple[v203_models.FirstActionInterfaceObservation, ...],
) -> v203_models.ExactPairedCalibrationEvaluation:
    by_cell: dict[str, dict[str, v203_models.FirstActionInterfaceObservation]] = {}
    for item in observations:
        by_cell.setdefault(item.source_cell_id, {})[item.arm] = item
    if len(by_cell) != 12 or any(set(rows) != {"C", "R"} for rows in by_cell.values()):
        raise ValueError("v26.204 paired Observation denominator differs")
    repair_abi = sum(rows["R"].exact_four_field_abi_valid for rows in by_cell.values())
    repair_bound = sum(
        rows["R"].exact_four_field_abi_valid
        and rows["R"].action_reference_valid is True
        and rows["R"].state_binding_valid is True
        for rows in by_cell.values()
    )
    repair_only = sum(
        rows["R"].exact_four_field_abi_valid and not rows["C"].exact_four_field_abi_valid
        for rows in by_cell.values()
    )
    control_only = sum(
        rows["C"].exact_four_field_abi_valid and not rows["R"].exact_four_field_abi_valid
        for rows in by_cell.values()
    )
    all_gates = repair_abi >= 9 and repair_bound >= 8 and repair_only >= 7 and control_only <= 1
    return cast(
        v203_models.ExactPairedCalibrationEvaluation,
        v203_models.make_identity(
            v203_models.ExactPairedCalibrationEvaluation,
            {
                "manifest_id": manifest_id,
                "observation_ids": tuple(sorted(item.observation_id for item in observations)),
                "exact_job_ids": tuple(sorted(item.job_id for item in observations)),
                "repair_abi_success_count": repair_abi,
                "repair_reference_state_valid_count": repair_bound,
                "paired_repair_only_abi_success_count": repair_only,
                "paired_control_only_abi_success_count": control_only,
                "delta_abi_numerator": repair_only - control_only,
                "all_gates_passed": all_gates,
            },
            field="evaluation_id",
            prefix="fresh_first_response_exact_paired_calibration_evaluation:",
        ),
    )
