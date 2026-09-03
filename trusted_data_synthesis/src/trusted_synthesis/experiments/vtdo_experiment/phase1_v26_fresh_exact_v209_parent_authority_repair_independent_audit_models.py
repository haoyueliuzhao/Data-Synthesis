# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_exact_v209_parent_authority_repair_independent_audit.v1"
CONSUMED_STAGE: Final = (
    "fresh_exact_v209_execution_condition_authoritative_parent_binding_"
    "repair_preflight_independent_audit_only"
)
NEXT_STAGE: Final = (
    "fresh_exact_v209_execution_condition_authoritative_parent_bound_"
    "online_execution_authorization_only"
)
DECISION: Final = (
    "v26_221_exact_v209_execution_condition_parent_authority_repair_"
    "preflight_independent_audit_passed"
)
V221_COMMIT: Final = "dbd9d15b6d44577725ef8d8a6c1fcca730120d5d"
V221_TREE: Final = "06f23ef0847e39b03fae9b19155cb3e7b22fbdf7"
V209_MANIFEST_ID: Final = (
    "finance_v26_209_artifact_manifest:"
    "1ec5df9edc0fb7b89921bbe3c154856e72e362cbbaee58a191bf9f275fc0bcf9"
)
V209_ROOT: Final = (
    "finance_v26_209_artifact_root:76ef4cdb9cc0703f6bee2fd76c9c8ea7cbce5277337ff882ffcb44f8085e4770"
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


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


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


class ExternalIndependentAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: Literal["3c687f46977a555a3f71d6759e6cd1c1de1117b7ea9e99e3d22e52e7afa1e318"]
    review_byte_count: Literal[14613] = 14_613
    audit_result: Literal["PASSED_AS_SCOPED"] = "PASSED_AS_SCOPED"
    blocking_defect: Literal["NONE_FOUND"] = "NONE_FOUND"
    first_failed_gate: Literal["NONE"] = "NONE"
    mandatory_revision: Literal["NONE"] = "NONE"
    repaired_object: Literal["EXACT_V209_EXECUTION_CONDITION_PARENT_AUTHORITY"] = (
        "EXACT_V209_EXECUTION_CONDITION_PARENT_AUTHORITY"
    )
    v220_authorization_unconsumed: Literal[True] = True
    v220_authorization_forbidden_as_future_authority: Literal[True] = True
    new_online_authorization_created: Literal[False] = False
    online_execution_blocked: Literal[True] = True
    operator_directive: Literal["参照审计报告继续实验修订"] = "参照审计报告继续实验修订"
    operator_directive_sha256: Literal[
        "dc2b598ec3667bd0e26354d1dac1ca447fa87acea50bd30a5fc245a9c35374e9"
    ]
    operator_directive_byte_count: Literal[36] = 36
    only_authorized_stage: Literal[
        "fresh_exact_v209_execution_condition_authoritative_parent_binding_"
        "repair_preflight_independent_audit_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    online_authorization_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalIndependentAuditAuthorization:
        directive = self.operator_directive.encode("utf-8")
        if (
            len(directive) != self.operator_directive_byte_count
            or hashlib.sha256(directive).hexdigest() != self.operator_directive_sha256
            or self.authorization_id
            != identity(
                self,
                "authorization_id",
                "finance_v26_222_external_independent_audit_authorization:",
            )
        ):
            raise ValueError("v26.222 external independent-audit authorization differs")
        return self


class V221Freeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v221_source_commit: Literal["dbd9d15b6d44577725ef8d8a6c1fcca730120d5d"] = V221_COMMIT
    v221_source_tree: Literal["06f23ef0847e39b03fae9b19155cb3e7b22fbdf7"] = V221_TREE
    v221_formal_file_count: Literal[17] = 17
    v221_formal_total_byte_count: Literal[112607] = 112_607
    v221_manifest_member_count: Literal[16] = 16
    v221_manifest_member_byte_count: Literal[109876] = 109_876
    v221_artifact_manifest_id: str = Field(min_length=1)
    v221_artifact_root: str = Field(min_length=1)
    v221_report_id: str = Field(min_length=1)
    v221_gate_id: str = Field(min_length=1)
    v221_decision_id: str = Field(min_length=1)
    v221_transition_id: str = Field(min_length=1)
    v221_formal_freeze_id: str = Field(min_length=1)
    v221_relation_audit_id: str = Field(min_length=1)
    v221_condition_binding_id: str = Field(min_length=1)
    v221_composition_contract_id: str = Field(min_length=1)
    v221_tamper_audit_id: str = Field(min_length=1)
    v221_decision: str = Field(min_length=1)
    v220_authorization_consumed: Literal[False] = False
    v220_authorization_forbidden_as_successor_authority: Literal[True] = True
    v221_online_authorization_count: Literal[0] = 0
    v221_provider_calls: Literal[0] = 0
    candidate_report_used_as_outcome_oracle: Literal[False] = False
    candidate_gate_used_as_outcome_oracle: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V221Freeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_222_v221_freeze:"):
            raise ValueError("v26.222 v26.221 Freeze differs")
        return self


class DetachedRebuildAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    archived_source_file_count: int = Field(gt=0)
    saved_file_count: Literal[17] = 17
    rebuilt_file_count: Literal[17] = 17
    saved_total_byte_count: Literal[112607] = 112_607
    rebuilt_total_byte_count: Literal[112607] = 112_607
    path_match_count: Literal[17] = 17
    sha256_match_count: Literal[17] = 17
    byte_count_match_count: Literal[17] = 17
    actual_byte_match_count: Literal[17] = 17
    manifest_member_revalidation_count: Literal[16] = 16
    credential_like_environment_key_count: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    provider_calls: Literal[0] = 0
    candidate_report_used_as_outcome_oracle: Literal[False] = False
    candidate_gate_used_as_outcome_oracle: Literal[False] = False
    candidate_formal_freeze_used_as_outcome_oracle: Literal[False] = False
    candidate_relation_audit_used_as_outcome_oracle: Literal[False] = False
    candidate_tamper_audit_used_as_outcome_oracle: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DetachedRebuildAudit:
        if self.audit_id != identity(self, "audit_id", "finance_v26_222_detached_rebuild_audit:"):
            raise ValueError("v26.222 detached rebuild Audit differs")
        return self


class IndependentV209AuthorityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    exact_v209_manifest_id: Literal[
        "finance_v26_209_artifact_manifest:"
        "1ec5df9edc0fb7b89921bbe3c154856e72e362cbbaee58a191bf9f275fc0bcf9"
    ] = V209_MANIFEST_ID
    exact_v209_artifact_root: Literal[
        "finance_v26_209_artifact_root:"
        "76ef4cdb9cc0703f6bee2fd76c9c8ea7cbce5277337ff882ffcb44f8085e4770"
    ] = V209_ROOT
    formal_file_count: Literal[21] = 21
    formal_total_byte_count: Literal[44916386] = 44_916_386
    member_count: Literal[20] = 20
    member_byte_count: Literal[44912918] = 44_912_918
    path_match_count: Literal[20] = 20
    sha256_match_count: Literal[20] = 20
    byte_count_match_count: Literal[20] = 20
    actual_byte_match_count: Literal[20] = 20
    independent_identity_match_count: Literal[1024] = 1_024
    source_commit_tree_match: Literal[True] = True
    source_file_commit_match_count: Literal[3] = 3
    package_catalog_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    invocation_census_id: str = Field(min_length=1)
    implementation_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    candidate_condition_projection_match_count: Literal[17] = 17
    candidate_condition_projection_field_count: Literal[17] = 17
    candidate_formal_freeze_used_as_outcome_oracle: Literal[False] = False
    candidate_condition_used_as_outcome_oracle: Literal[False] = False
    candidate_helper_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentV209AuthorityAudit:
        if self.audit_id != identity(
            self, "audit_id", "finance_v26_222_independent_v209_authority_audit:"
        ):
            raise ValueError("v26.222 independent v26.209 authority Audit differs")
        return self


class IndependentRelationClosureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    v209_authority_audit_id: str = Field(min_length=1)
    exact_package_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
    exact_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    exact_package_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_coordinate_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    trace_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_job_count: Literal[192] = 192
    census_distinct_job_count: Literal[192] = 192
    census_job_set_matches_manifest: Literal[True] = True
    census_row_job_membership_match_count: Literal[792] = 792
    job_package_membership_match_count: Literal[192] = 192
    package_replica_cell_match_count: Literal[192] = 192
    namespace_owner_match_count: Literal[768] = 768
    namespace_unique_count_each: Literal[192] = 192
    parent_match_count: Literal[12] = 12
    expected_job_set_match: Literal[True] = True
    unique_coordinate_count: Literal[792] = 792
    candidate_relation_projection_match_count: Literal[16] = 16
    candidate_relation_projection_field_count: Literal[16] = 16
    candidate_relation_helper_calls: Literal[0] = 0
    candidate_relation_audit_used_as_outcome_oracle: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentRelationClosureAudit:
        if (
            self.exact_package_ids != tuple(sorted(set(self.exact_package_ids)))
            or self.exact_job_ids != tuple(sorted(set(self.exact_job_ids)))
            or canonical_sha256(self.exact_package_ids) != self.exact_package_set_sha256
            or canonical_sha256(self.exact_job_ids) != self.exact_job_set_sha256
            or self.audit_id
            != identity(self, "audit_id", "finance_v26_222_independent_relation_closure_audit:")
        ):
            raise ValueError("v26.222 independent relation closure Audit differs")
        return self


class IndependentAttackControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    mutation_kind: Literal["job_id", "raw_namespace"]
    candidate_artifact_manifest_rehashed: bool
    candidate_artifact_manifest_id: str = Field(min_length=1)
    candidate_artifact_root: str = Field(min_length=1)
    prospective_condition_id: str = Field(min_length=1)
    prospective_composition_id: str = Field(min_length=1)
    prospective_authorization_id: str = Field(min_length=1)
    candidate_job_count: Literal[192] = 192
    candidate_unique_job_count: Literal[192] = 192
    candidate_namespace_count: Literal[192] = 192
    candidate_unique_namespace_count: Literal[192] = 192
    rejected_before_condition: Literal[True] = True
    rejection_stage: Literal[
        "independent_exact_v209_member_admission",
        "independent_exact_v209_manifest_root_admission",
    ]
    candidate_control_projection_match: Literal[True] = True
    condition_objects_created: Literal[0] = 0
    online_authorizations_created: Literal[0] = 0
    attack_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> IndependentAttackControl:
        stage = (
            "independent_exact_v209_manifest_root_admission"
            if self.candidate_artifact_manifest_rehashed
            else "independent_exact_v209_member_admission"
        )
        if self.rejection_stage != stage or self.control_id != identity(
            self,
            "control_id",
            "finance_v26_222_independent_upstream_attack_control:",
        ):
            raise ValueError("v26.222 independent attack control differs")
        return self


class IndependentAttackAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    v209_authority_audit_id: str = Field(min_length=1)
    controls: tuple[IndependentAttackControl, ...] = Field(min_length=4, max_length=4)
    attack_count: Literal[4] = 4
    rejected_count: Literal[4] = 4
    accepted_count: Literal[0] = 0
    candidate_control_projection_match_count: Literal[4] = 4
    candidate_attack_helper_calls: Literal[0] = 0
    candidate_tamper_audit_used_as_outcome_oracle: Literal[False] = False
    condition_objects_created: Literal[0] = 0
    online_authorizations_created: Literal[0] = 0
    attack_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentAttackAudit:
        if len({item.control_name for item in self.controls}) != 4 or self.audit_id != identity(
            self, "audit_id", "finance_v26_222_independent_upstream_attack_audit:"
        ):
            raise ValueError("v26.222 independent attack Audit differs")
        return self


class ScopeBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    v220_authorization_consumptions: Literal[0] = 0
    new_online_authorizations: Literal[0] = 0
    manifest_job_executions: Literal[0] = 0
    provider_calls: Literal[0] = 0
    provider_client_constructions: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    qa_reads: Literal[0] = 0
    mapper_state_frequency_contribution_vtdo_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ScopeBoundaryAudit:
        if self.audit_id != identity(self, "audit_id", "finance_v26_222_scope_boundary_audit:"):
            raise ValueError("v26.222 scope boundary Audit differs")
        return self


class GateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> GateResult:
        if self.gate_id != identity(self, "gate_id", "finance_v26_222_gate:"):
            raise ValueError("v26.222 Gate differs")
        return self


class GateEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    gates: tuple[GateResult, ...] = Field(min_length=6, max_length=6)
    passed_count: Literal[6] = 6
    failed_count: Literal[0] = 0
    all_gates_passed: Literal[True] = True
    online_authorization_issued: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> GateEvaluation:
        if len({item.gate_name for item in self.gates}) != 6 or self.evaluation_id != identity(
            self, "evaluation_id", "finance_v26_222_gate_evaluation:"
        ):
            raise ValueError("v26.222 Gate Evaluation differs")
        return self


class Decision(FrozenModel):
    decision_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    detached_rebuild_audit_id: str = Field(min_length=1)
    v209_authority_audit_id: str = Field(min_length=1)
    relation_closure_audit_id: str = Field(min_length=1)
    attack_audit_id: str = Field(min_length=1)
    scope_boundary_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision: Literal[
        "v26_221_exact_v209_execution_condition_parent_authority_repair_"
        "preflight_independent_audit_passed"
    ] = DECISION
    blocking_defect: Literal["NONE_FOUND"] = "NONE_FOUND"
    mandatory_revision: Literal["NONE"] = "NONE"
    v220_authorization_consumed: Literal[False] = False
    new_online_authorization_issued: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> Decision:
        if self.decision_id != identity(
            self, "decision_id", "finance_v26_222_independent_audit_decision:"
        ):
            raise ValueError("v26.222 Decision differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    status: Literal["PASSED_INDEPENDENT_AUDIT_ONLINE_AUTHORIZATION_BLOCKED"] = (
        "PASSED_INDEPENDENT_AUDIT_ONLINE_AUTHORIZATION_BLOCKED"
    )
    next_stage: Literal[
        "fresh_exact_v209_execution_condition_authoritative_parent_bound_"
        "online_execution_authorization_only"
    ] = NEXT_STAGE
    next_stage_authorized: Literal[False] = False
    separate_external_decision_required: Literal[True] = True
    online_authorization_created: Literal[False] = False
    provider_execution_authorized: Literal[False] = False
    v220_authorization_forbidden: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> Transition:
        if self.transition_id != identity(self, "transition_id", "finance_v26_222_transition:"):
            raise ValueError("v26.222 Transition differs")
        return self


class SourceBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class SourceIdentity(FrozenModel):
    source_identity_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    implementation_files: tuple[str, ...] = Field(min_length=3, max_length=3)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_source(self) -> SourceIdentity:
        if self.implementation_files != tuple(
            sorted(set(self.implementation_files))
        ) or self.source_identity_id != identity(
            self, "source_identity_id", "finance_v26_222_source_identity:"
        ):
            raise ValueError("v26.222 source identity differs")
        return self


class ImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    files: tuple[SourceBinding, ...] = Field(min_length=3, max_length=3)
    symbols: tuple[SourceBinding, ...] = Field(min_length=4)
    candidate_helper_calls: Literal[0] = 0
    network_import_count: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ImplementationBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_exact_v209_parent_authority_independent_audit_implementation_binding:",
        ):
            raise ValueError("v26.222 implementation Binding differs")
        return self


class Report(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    detached_rebuild_audit_id: str = Field(min_length=1)
    v209_authority_audit_id: str = Field(min_length=1)
    relation_closure_audit_id: str = Field(min_length=1)
    attack_audit_id: str = Field(min_length=1)
    scope_boundary_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    decision: Literal[
        "v26_221_exact_v209_execution_condition_parent_authority_repair_"
        "preflight_independent_audit_passed"
    ] = DECISION
    v220_authorization_consumed: Literal[False] = False
    new_online_authorizations: Literal[0] = 0
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> Report:
        if self.report_id != identity(
            self, "report_id", "finance_v26_222_independent_audit_report:"
        ):
            raise ValueError("v26.222 Report differs")
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
        root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_222_artifact_root:",
        )
        if (
            self.file_count != len(self.members)
            or self.total_byte_count != sum(item.byte_count for item in self.members)
            or tuple(item.relative_path for item in self.members)
            != tuple(sorted({item.relative_path for item in self.members}))
            or self.artifact_root != root
            or self.manifest_id
            != identity(self, "manifest_id", "finance_v26_222_artifact_manifest:")
        ):
            raise ValueError("v26.222 Artifact Manifest differs")
        return self


def artifact_manifest(run_id: str, payloads: dict[str, bytes]) -> ArtifactManifest:
    members = tuple(
        ArtifactMember(
            relative_path=name,
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
        )
        for name, payload in sorted(payloads.items())
    )
    root = canonical_hash(
        tuple(item.model_dump(mode="json") for item in members),
        prefix="finance_v26_222_artifact_root:",
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
            prefix="finance_v26_222_artifact_manifest:",
        ),
    )
