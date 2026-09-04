# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_models as v231,
)
from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_exact_v209_recovery_online_authorization_manifest_byte_repair.v1"
RUN_ID: Final = "finance_v26_232_fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_predecessor_manifest_actual_byte_authority_repair_v1_20260904"
CONSUMED_STAGE: Final = (
    "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_"
    "authorization_predecessor_manifest_actual_byte_authority_repair_only"
)
NEXT_STAGE: Final = (
    "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_only"
)
DECISION_VALUE: Final = (
    "fresh_exact_v209_recovery_online_authorization_predecessor_manifest_actual_byte_"
    "authority_repaired_new_authorization_issued_not_consumed"
)
EXTERNAL_REVIEW_SHA256: Final = "04a5e36142abc3ecde5706c19f9277ee1315beb6f2b5e023863aad0ab963b5bc"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 10_544
DIRECTIVE: Final = "参照审计修订问题"
DIRECTIVE_SHA256: Final = "a5eccdee792d12977caf76a67107c721878efb7ae02598d987e2e86b83fcc0d8"
DIRECTIVE_BYTE_COUNT: Final = 24

V229_MANIFEST_BYTES: Final = 16_952
V229_MANIFEST_SHA256: Final = "3c74bf72426c33400338e9f234a82bc342f368910a40c84d360ac3bd61b8fa72"
V230_MANIFEST_BYTES: Final = 3_150
V230_MANIFEST_SHA256: Final = "70ad2b0afa9fac2917512e4e2d7d85cf2f42abb99e8a6a058b751f627f8605b1"
V231_MANIFEST_BYTES: Final = 2_889
V231_MANIFEST_SHA256: Final = "147ac88a48a5f04321cd242fd5031d0e334abccb502eccf02cbc64fa1730039f"

V231_RUN_ID: Final = v231.RUN_ID
V231_MANIFEST_ID: Final = "finance_v26_231_artifact_manifest:92c0f3baaeaeb278e9037ebf4dd85c3e86b760bd1d624681379857700f134308"
V231_ARTIFACT_ROOT: Final = (
    "finance_v26_231_artifact_root:a9d1d137adcdb3552fcfc5eaf8c979a6f0ab2906b7165a690144c53adb1c24d1"
)
V231_REPORT_ID: Final = "finance_v26_231_online_authorization_report:09e2894fbc945ccb28d53f1e60ba84769ed60fad75b59f562f8fadbe56aa48ed"
V231_GATE_ID: Final = "finance_v26_231_gate_evaluation:713932e60414c905a5e602013372d13522d9b90ed76431ddbec452e0d7e03527"
V231_DECISION_ID: Final = "finance_v26_231_online_authorization_decision:9be1b0912f6bb4f6d5cfee7af5d4185d593ae54e482edd7517e3e6d0e48c47d3"
V231_TRANSITION_ID: Final = (
    "finance_v26_231_transition:bfd9754ad862373eaf427f445e3e8760920a506cd60b6df399abdecef4ff64da"
)
V231_AUTHORIZATION_ID: Final = (
    "fresh_v26_231_exact_recovery_online_execution_authorization:"
    "d54c68b13db02db4582f7e587973b61af431efa714f1ba3d6473939f4b12c06d"
)
V231_PARENT_BINDING_ID: Final = (
    "fresh_v26_231_exact_recovery_parent_binding:"
    "9a67201347027bd2dc147bebf39ec2825616c6a3ead1acc6db7c8b038df95665"
)
V231_EXECUTION_CONTRACT_ID: Final = (
    "fresh_v26_231_recovery_execution_contract:"
    "48705123b548e499afb2f3553d10ee454d15975e54b8a275ce3b732f107f70e0"
)
V231_COMPOSITION_ID: Final = (
    "fresh_v26_231_recovery_online_execution_composition:"
    "cf18a6134e0dea327460a28deae4ecb4e314d3aef655074b2ed97ae6fa6561a7"
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
        allow_nan=False,
    ).encode("utf-8")


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha(canonical_bytes(value))


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False), prefix=prefix
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


class Identified(FrozenModel):
    @classmethod
    def prefix(cls) -> str:
        raise NotImplementedError

    def check_id(self, field: str) -> None:
        if getattr(self, field) != identity(self, field, self.prefix()):
            raise ValueError(f"{type(self).__name__} identity differs")


class ExternalRepairDecision(Identified):
    decision_id: str
    review_sha256: Literal["04a5e36142abc3ecde5706c19f9277ee1315beb6f2b5e023863aad0ab963b5bc"] = (
        EXTERNAL_REVIEW_SHA256
    )
    review_byte_count: Literal[10544] = EXTERNAL_REVIEW_BYTE_COUNT
    audit_decision: Literal["FAIL_NARROWLY_AT_G0"] = "FAIL_NARROWLY_AT_G0"
    blocking_defect: Literal[
        "PREDECESSOR_SELF_EXCLUDING_MANIFEST_ACTUAL_BYTE_AUTHORITY_NOT_CLOSED"
    ] = "PREDECESSOR_SELF_EXCLUDING_MANIFEST_ACTUAL_BYTE_AUTHORITY_NOT_CLOSED"
    first_failed_gate: Literal["G0_EXACT_V26_230_FREEZE"] = "G0_EXACT_V26_230_FREEZE"
    mandatory_revision: Literal["NARROW"] = "NARROW"
    recovery_population_authority: Literal["RETAINED"] = "RETAINED"
    authorization_construction: Literal["LOCALLY_CONSTRUCTED"] = "LOCALLY_CONSTRUCTED"
    authorization_consumability: Literal["NOT_AUTHORIZED"] = "NOT_AUTHORIZED"
    operator_directive: Literal["参照审计修订问题"] = DIRECTIVE
    operator_directive_sha256: Literal[
        "a5eccdee792d12977caf76a67107c721878efb7ae02598d987e2e86b83fcc0d8"
    ] = DIRECTIVE_SHA256
    operator_directive_byte_count: Literal[24] = DIRECTIVE_BYTE_COUNT
    only_authorized_stage: Literal[
        "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_predecessor_manifest_actual_byte_authority_repair_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized_during_stage: Literal[0] = 0
    recovery_executions_authorized_during_stage: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_external_manifest_byte_repair_decision:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        directive = self.operator_directive.encode("utf-8")
        if (
            len(directive) != self.operator_directive_byte_count
            or sha(directive) != self.operator_directive_sha256
        ):
            raise ValueError("operator directive bytes differ")
        self.check_id("decision_id")
        return self


class ManifestByteAuthority(Identified):
    authority_id: str
    predecessor_version: Literal["v26.229", "v26.230", "v26.231"]
    run_id: str
    manifest_relative_path: Literal["artifact_manifest.json"] = "artifact_manifest.json"
    expected_byte_count: int = Field(gt=0)
    actual_byte_count: int = Field(gt=0)
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_id: str
    artifact_root: str
    manifest_member_count: int = Field(gt=0)
    manifest_member_bytes: int = Field(gt=0)
    formal_file_count: int = Field(gt=0)
    formal_total_bytes: int = Field(gt=0)
    manifest_actual_bytes_match: Literal[True] = True
    all_member_actual_bytes_match: Literal[True] = True
    exact_path_set_match: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_predecessor_manifest_actual_byte_authority:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            self.expected_byte_count != self.actual_byte_count
            or self.expected_sha256 != self.actual_sha256
            or self.formal_file_count != self.manifest_member_count + 1
            or self.formal_total_bytes != self.manifest_member_bytes + self.actual_byte_count
        ):
            raise ValueError("predecessor Manifest actual-byte authority differs")
        self.check_id("authority_id")
        return self


class V231CandidateFreeze(Identified):
    freeze_id: str
    external_decision_id: str
    manifest_byte_authority_id: str
    source_commit: Literal["d74406041cabb1ea61df22b99f8a96affdae2ea0"]
    source_tree: Literal["3cdbb7cbdbc79ec01726ba262b8833d4e013d058"]
    formal_file_count: Literal[18] = 18
    formal_total_bytes: Literal[103759] = 103_759
    manifest_id: Literal[
        "finance_v26_231_artifact_manifest:92c0f3baaeaeb278e9037ebf4dd85c3e86b760bd1d624681379857700f134308"
    ] = V231_MANIFEST_ID
    artifact_root: Literal[
        "finance_v26_231_artifact_root:a9d1d137adcdb3552fcfc5eaf8c979a6f0ab2906b7165a690144c53adb1c24d1"
    ] = V231_ARTIFACT_ROOT
    report_id: Literal[
        "finance_v26_231_online_authorization_report:09e2894fbc945ccb28d53f1e60ba84769ed60fad75b59f562f8fadbe56aa48ed"
    ] = V231_REPORT_ID
    gate_id: Literal[
        "finance_v26_231_gate_evaluation:713932e60414c905a5e602013372d13522d9b90ed76431ddbec452e0d7e03527"
    ] = V231_GATE_ID
    decision_id: Literal[
        "finance_v26_231_online_authorization_decision:9be1b0912f6bb4f6d5cfee7af5d4185d593ae54e482edd7517e3e6d0e48c47d3"
    ] = V231_DECISION_ID
    transition_id: Literal[
        "finance_v26_231_transition:bfd9754ad862373eaf427f445e3e8760920a506cd60b6df399abdecef4ff64da"
    ] = V231_TRANSITION_ID
    authorization_id: Literal[
        "fresh_v26_231_exact_recovery_online_execution_authorization:d54c68b13db02db4582f7e587973b61af431efa714f1ba3d6473939f4b12c06d"
    ] = V231_AUTHORIZATION_ID
    external_audit_decision: Literal["FAIL_NARROWLY_AT_G0"] = "FAIL_NARROWLY_AT_G0"
    first_failed_gate: Literal["G0_EXACT_V26_230_FREEZE"] = "G0_EXACT_V26_230_FREEZE"
    authorization_consumable: Literal[False] = False
    formal_bytes_modified: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_v231_candidate_freeze:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("freeze_id")
        return self


class V230Freeze(v231.V230Freeze):
    external_decision_id: str
    v231_candidate_freeze_id: str
    v230_manifest_byte_authority_id: str
    v230_manifest_byte_count: Literal[3150] = V230_MANIFEST_BYTES
    v230_manifest_sha256: Literal[
        "70ad2b0afa9fac2917512e4e2d7d85cf2f42abb99e8a6a058b751f627f8605b1"
    ] = V230_MANIFEST_SHA256
    old_v231_freeze_id: str
    old_v231_freeze_retained_projection_match: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_v230_manifest_actual_byte_freeze:"


class RecoveryParentBinding(v231.RecoveryParentBinding):
    v229_manifest_byte_authority_id: str
    v230_manifest_byte_authority_id: str
    v229_manifest_byte_count: Literal[16952] = V229_MANIFEST_BYTES
    v229_manifest_sha256: Literal[
        "3c74bf72426c33400338e9f234a82bc342f368910a40c84d360ac3bd61b8fa72"
    ] = V229_MANIFEST_SHA256
    v230_manifest_byte_count: Literal[3150] = V230_MANIFEST_BYTES
    v230_manifest_sha256: Literal[
        "70ad2b0afa9fac2917512e4e2d7d85cf2f42abb99e8a6a058b751f627f8605b1"
    ] = V230_MANIFEST_SHA256
    retained_v231_parent_binding_id: Literal[
        "fresh_v26_231_exact_recovery_parent_binding:9a67201347027bd2dc147bebf39ec2825616c6a3ead1acc6db7c8b038df95665"
    ] = V231_PARENT_BINDING_ID
    retained_v231_parent_actual_byte_match: Literal[True] = True
    recovery_semantic_projection_unchanged: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "fresh_v26_232_exact_manifest_byte_bound_recovery_parent_binding:"


class RecoveryExecutionContract(v231.RecoveryExecutionContract):
    retained_v231_contract_id: Literal[
        "fresh_v26_231_recovery_execution_contract:48705123b548e499afb2f3553d10ee454d15975e54b8a275ce3b732f107f70e0"
    ] = V231_EXECUTION_CONTRACT_ID
    retained_contract_projection_match: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "fresh_v26_232_manifest_byte_bound_recovery_execution_contract:"


class RecoveryComposition(v231.RecoveryComposition):
    retained_v231_composition_id: Literal[
        "fresh_v26_231_recovery_online_execution_composition:cf18a6134e0dea327460a28deae4ecb4e314d3aef655074b2ed97ae6fa6561a7"
    ] = V231_COMPOSITION_ID
    retained_event_sequence_match: Literal[True] = True
    predecessor_manifest_actual_byte_guard_before_authorization: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "fresh_v26_232_manifest_byte_bound_recovery_online_execution_composition:"


class ExactOnlineAuthorization(v231.ExactOnlineAuthorization):
    v231_candidate_freeze_id: str
    v229_manifest_byte_authority_id: str
    v230_manifest_byte_authority_id: str
    superseded_v231_authorization_id: Literal[
        "fresh_v26_231_exact_recovery_online_execution_authorization:d54c68b13db02db4582f7e587973b61af431efa714f1ba3d6473939f4b12c06d"
    ] = V231_AUTHORIZATION_ID
    superseded_v231_authorization_consumable: Literal[False] = False
    exact_predecessor_manifest_actual_bytes_bound: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "fresh_v26_232_exact_manifest_byte_bound_recovery_online_execution_authorization:"


class Admission(Identified):
    admission_id: str
    authorization_id: str
    authorized_stage: str
    v230_freeze_id: str
    parent_binding_id: str
    execution_contract_id: str
    composition_id: str
    recovery_job_set_sha256: str
    diagnostic_nonconsuming_probe: Literal[True] = True
    authorization_consumed: Literal[False] = False
    post_guard_probe_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "fresh_v26_232_recovery_online_authorization_admission:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("admission_id")
        return self


class AdmissionControl(Identified):
    control_id: str
    control_name: str
    admitted: bool
    rejected: bool
    rejection_reason_sha256: str | None = None
    precredential_rejection: Literal[True] = True
    post_guard_probe_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_precredential_admission_control:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if self.admitted == self.rejected or (
            self.admitted != (self.rejection_reason_sha256 is None)
        ):
            raise ValueError("admission control partition differs")
        self.check_id("control_id")
        return self


class AdmissionAudit(Identified):
    audit_id: str
    authorization_id: str
    admission_id: str
    controls: tuple[AdmissionControl, ...] = Field(min_length=20, max_length=20)
    legal_control_count: Literal[1] = 1
    invalid_control_count: Literal[19] = 19
    invalid_post_guard_probe_count: Literal[0] = 0
    authorization_consumptions: Literal[0] = 0
    run_start_receipts: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_precredential_admission_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            sum(row.admitted for row in self.controls) != 1
            or sum(row.rejected for row in self.controls) != 19
        ):
            raise ValueError("admission Audit partition differs")
        self.check_id("audit_id")
        return self


class ParentAttack(Identified):
    attack_id: str
    attack_name: str
    mutated_authorization_id: str
    rejected_by_exact_guard: Literal[True] = True
    rejection_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fully_rehashed_object_count: Literal[1] = 1
    post_guard_probe_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_fully_rehashed_parent_attack:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("attack_id")
        return self


class ParentAttackAudit(Identified):
    audit_id: str
    authorization_id: str
    attacks: tuple[ParentAttack, ...] = Field(min_length=10, max_length=10)
    attack_count: Literal[10] = 10
    rejected_attack_count: Literal[10] = 10
    accepted_attack_count: Literal[0] = 0
    fully_rehashed_object_count: Literal[10] = 10
    post_guard_probe_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_parent_attack_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if len({row.attack_name for row in self.attacks}) != 10:
            raise ValueError("parent attack domain differs")
        self.check_id("audit_id")
        return self


class ManifestAttack(Identified):
    attack_id: str
    attack_name: Literal[
        "v26_230_manifest_same_length_key_reordering",
        "v26_229_manifest_same_length_key_reordering",
    ]
    predecessor_version: Literal["v26.229", "v26.230"]
    original_byte_count: int = Field(gt=0)
    candidate_byte_count: int = Field(gt=0)
    original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parsed_json_equal: Literal[True] = True
    candidate_byte_count_equal: Literal[True] = True
    candidate_sha256_changed: Literal[True] = True
    rejected: Literal[True] = True
    rejection_stage: Literal["freeze.manifest_bytes"] = "freeze.manifest_bytes"
    exception_type: Literal["V232Error"] = "V232Error"
    reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_manifest_byte_attack:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            self.original_byte_count != self.candidate_byte_count
            or self.original_sha256 == self.candidate_sha256
        ):
            raise ValueError("Manifest attack geometry differs")
        self.check_id("attack_id")
        return self


class ManifestAttackAudit(Identified):
    audit_id: str
    attacks: tuple[ManifestAttack, ...] = Field(min_length=2, max_length=2)
    attempted_count: Literal[2] = 2
    rejected_count: Literal[2] = 2
    accepted_count: Literal[0] = 0
    rejection_stage: Literal["freeze.manifest_bytes"] = "freeze.manifest_bytes"
    attack_output_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_manifest_byte_negative_control_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        expected = (
            "v26_230_manifest_same_length_key_reordering",
            "v26_229_manifest_same_length_key_reordering",
        )
        if tuple(row.attack_name for row in self.attacks) != expected:
            raise ValueError("Manifest attack domain differs")
        self.check_id("audit_id")
        return self


class ScopeAudit(Identified):
    audit_id: str
    authorization_id: str
    online_authorizations_issued: Literal[1] = 1
    online_authorizations_consumed: Literal[0] = 0
    superseded_v231_authorizations_consumed: Literal[0] = 0
    authorization_consumption_receipts: Literal[0] = 0
    run_start_receipts: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    model_client_constructions: Literal[0] = 0
    recovery_executions: Literal[0] = 0
    historical_prefix_provider_calls: Literal[0] = 0
    failed_job_reruns: Literal[0] = 0
    historical_v26_226_writes: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    qa_reads: Literal[0] = 0
    mapper_state_frequency_contribution_vtdo_rows: Literal[0] = 0
    training_release_production_rows: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_scope_boundary_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("audit_id")
        return self


class Gate(FrozenModel):
    name: str
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    passed: Literal[True] = True


class GateEvaluation(Identified):
    evaluation_id: str
    gates: tuple[Gate, ...] = Field(min_length=8, max_length=8)
    passed_count: Literal[8] = 8
    failed_count: Literal[0] = 0
    noncompensatory: Literal[True] = True
    decision: Literal["PASS"] = "PASS"
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_gate_evaluation:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if len({row.name for row in self.gates}) != 8:
            raise ValueError("Gate domain differs")
        self.check_id("evaluation_id")
        return self


class Decision(Identified):
    decision_id: str
    external_decision_id: str
    gate_evaluation_id: str
    authorization_id: str
    decision: Literal[
        "fresh_exact_v209_recovery_online_authorization_predecessor_manifest_actual_byte_authority_repaired_new_authorization_issued_not_consumed"
    ] = DECISION_VALUE
    exact_recovery_job_count: Literal[33] = 33
    authorization_issued_count: Literal[1] = 1
    authorization_consumed_count: Literal[0] = 0
    superseded_v231_authorization_consumable: Literal[False] = False
    provider_calls: Literal[0] = 0
    recovery_executions: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_online_authorization_decision:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("decision_id")
        return self


class Transition(Identified):
    transition_id: str
    decision_id: str
    authorization_id: str
    consumed_stage: str = CONSUMED_STAGE
    next_stage: str = NEXT_STAGE
    next_stage_authorized: Literal[True] = True
    authorization_issued: Literal[True] = True
    authorization_consumed: Literal[False] = False
    superseded_v231_authorization_reusable: Literal[False] = False
    provider_calls_authorized_during_current_stage: Literal[False] = False
    provider_calls_authorized_only_after_successor_consumption: Literal[True] = True
    recovery_population_change_authorized: Literal[False] = False
    historical_v26_226_mutation_authorized: Literal[False] = False
    empirical_estimation_authorized: Literal[False] = False
    independent_postrun_audit_required: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_transition:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("transition_id")
        return self


class SourceMember(FrozenModel):
    relative_path: str
    git_blob_oid: str = Field(pattern=r"^[0-9a-f]{40}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)
    committed_current_bytes_match: Literal[True] = True


class SourceIdentity(Identified):
    source_identity_id: str
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    commit_tree_relation: Literal[True] = True
    members: tuple[SourceMember, ...] = Field(min_length=4, max_length=4)
    member_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_source_identity:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        paths = tuple(row.relative_path for row in self.members)
        if (
            paths != tuple(sorted(set(paths)))
            or canonical_sha256(tuple(row.model_dump(mode="json") for row in self.members))
            != self.member_set_sha256
        ):
            raise ValueError("source member set differs")
        self.check_id("source_identity_id")
        return self


class ImplementationBinding(Identified):
    binding_id: str
    source_identity_id: str
    external_decision_id: str
    v231_candidate_freeze_id: str
    required_symbols: tuple[str, ...] = Field(min_length=8)
    manifest_actual_byte_checks: Literal[3] = 3
    manifest_same_length_attack_controls: Literal[2] = 2
    network_symbols_present: Literal[False] = False
    credential_environment_symbols_present: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "fresh_v26_232_manifest_byte_repair_implementation_binding:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if self.required_symbols != tuple(sorted(set(self.required_symbols))):
            raise ValueError("implementation symbol set differs")
        self.check_id("binding_id")
        return self


class Report(Identified):
    report_id: str
    run_id: str = RUN_ID
    source_identity_id: str
    implementation_binding_id: str
    external_decision_id: str
    v231_candidate_freeze_id: str
    v229_manifest_byte_authority_id: str
    v230_manifest_byte_authority_id: str
    v230_freeze_id: str
    parent_binding_id: str
    execution_contract_id: str
    composition_id: str
    authorization_id: str
    admission_audit_id: str
    parent_attack_audit_id: str
    manifest_attack_audit_id: str
    scope_audit_id: str
    gate_evaluation_id: str
    decision_id: str
    transition_id: str
    decision: str = DECISION_VALUE
    exact_recovery_job_count: Literal[33] = 33
    historical_successful_prefix_calls: Literal[55] = 55
    exact_failed_requests_bound: Literal[33] = 33
    maximum_online_provider_calls: Literal[704] = 704
    request_max_tokens: Literal[16384] = 16_384
    predecessor_manifest_actual_byte_matches: Literal[2] = 2
    same_length_manifest_attacks_rejected: Literal[2] = 2
    online_authorizations_issued: Literal[1] = 1
    online_authorizations_consumed: Literal[0] = 0
    provider_calls: Literal[0] = 0
    recovery_executions: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    historical_mutations: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_manifest_byte_repair_report:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("report_id")
        return self


class ArtifactMember(FrozenModel):
    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ArtifactManifest(Identified):
    manifest_id: str
    run_id: str = RUN_ID
    members: tuple[ArtifactMember, ...]
    file_count: int = Field(ge=1)
    total_member_bytes: int = Field(gt=0)
    self_excluding: Literal[True] = True
    manifest_relative_path: Literal["artifact_manifest.json"] = "artifact_manifest.json"
    artifact_root: str
    provider_calls: Literal[0] = 0

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_232_artifact_manifest:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        paths = tuple(row.relative_path for row in self.members)
        expected_root = canonical_hash(
            tuple(row.model_dump(mode="json") for row in self.members),
            prefix="finance_v26_232_artifact_root:",
        )
        if (
            paths != tuple(sorted(set(paths)))
            or self.file_count != len(self.members)
            or self.total_member_bytes != sum(row.byte_count for row in self.members)
            or self.artifact_root != expected_root
        ):
            raise ValueError("artifact Manifest differs")
        self.check_id("manifest_id")
        return self


def artifact_manifest(payloads: dict[str, bytes]) -> ArtifactManifest:
    members = tuple(
        ArtifactMember(relative_path=path, sha256=sha(payload), byte_count=len(payload))
        for path, payload in sorted(payloads.items())
    )
    values = {
        "members": members,
        "file_count": len(members),
        "total_member_bytes": sum(row.byte_count for row in members),
        "artifact_root": canonical_hash(
            tuple(row.model_dump(mode="json") for row in members),
            prefix="finance_v26_232_artifact_root:",
        ),
    }
    return cast(
        ArtifactManifest,
        make_identity(
            ArtifactManifest,
            values,
            field="manifest_id",
            prefix=ArtifactManifest.prefix(),
        ),
    )
