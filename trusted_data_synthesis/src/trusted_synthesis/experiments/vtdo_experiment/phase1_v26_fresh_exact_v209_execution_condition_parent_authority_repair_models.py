# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_exact_v209_execution_condition_parent_authority_repair.v1"
CONSUMED_STAGE: Final = (
    "fresh_exact_v209_execution_condition_authoritative_parent_binding_repair_preflight_only"
)
NEXT_STAGE: Final = (
    "fresh_exact_v209_execution_condition_authoritative_parent_binding_"
    "repair_preflight_independent_audit_only"
)
DECISION: Final = (
    "fresh_exact_v209_execution_condition_authoritative_parent_binding_repair_"
    "preflight_passed_independent_audit_required_online_authorization_blocked"
)
V220_AUTHORIZATION_ID: Final = (
    "fresh_repaired_registry_complement_bound_exact_online_execution_authorization:"
    "ea1c906e3f9f8302bb2624defbf258f2601edd91e6256ae4ddec48be32517b5a"
)
V209_MANIFEST_ID: Final = (
    "finance_v26_209_artifact_manifest:"
    "1ec5df9edc0fb7b89921bbe3c154856e72e362cbbaee58a191bf9f275fc0bcf9"
)
V209_ARTIFACT_ROOT: Final = (
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


class ExternalRepairAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: Literal["fbf49cf53f7612b260c1e1b2ec6f66747c5335c168ac133bcef510ea628ac605"]
    review_byte_count: Literal[13510] = 13_510
    audit_result: Literal["FAIL"] = "FAIL"
    retained_scope: Literal["VALID_SCOPED_AUTHORIZATION_OBJECT_CONSTRUCTION"] = (
        "VALID_SCOPED_AUTHORIZATION_OBJECT_CONSTRUCTION"
    )
    blocking_defect: Literal["EXACT_V209_EXECUTION_CONDITION_PARENT_AUTHORITY_NOT_CLOSED"] = (
        "EXACT_V209_EXECUTION_CONDITION_PARENT_AUTHORITY_NOT_CLOSED"
    )
    first_failed_gate: Literal["G2_EXACT_V209_192_JOB_CONDITION"] = (
        "G2_EXACT_V209_192_JOB_CONDITION"
    )
    mandatory_revision: Literal["REQUIRED"] = "REQUIRED"
    current_authorization_must_remain_unconsumed: Literal[True] = True
    reviewed_online_execution_authorized: Literal[False] = False
    operator_directive: Literal["参照审计报告继续实验修订"] = "参照审计报告继续实验修订"
    operator_directive_sha256: Literal[
        "dc2b598ec3667bd0e26354d1dac1ca447fa87acea50bd30a5fc245a9c35374e9"
    ]
    operator_directive_byte_count: Literal[36] = 36
    only_authorized_stage: Literal[
        "fresh_exact_v209_execution_condition_authoritative_parent_binding_repair_preflight_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    online_authorization_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalRepairAuthorization:
        directive = self.operator_directive.encode("utf-8")
        if (
            len(directive) != self.operator_directive_byte_count
            or hashlib.sha256(directive).hexdigest() != self.operator_directive_sha256
            or self.authorization_id
            != identity(
                self,
                "authorization_id",
                "finance_v26_221_external_repair_authorization:",
            )
        ):
            raise ValueError("v26.221 external repair authorization differs")
        return self


class V220Freeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v220_source_commit: Literal["4276d29f39a77f933f470fafd590020698fe9931"]
    v220_source_tree: Literal["9f9cfab48ad7de93b7eec8b58382fc780d5b15fd"]
    v220_formal_file_count: Literal[18] = 18
    v220_formal_total_byte_count: Literal[126513] = 126_513
    v220_manifest_member_count: Literal[17] = 17
    v220_manifest_member_byte_count: Literal[123577] = 123_577
    v220_artifact_manifest_id: str = Field(min_length=1)
    v220_artifact_root: str = Field(min_length=1)
    v220_report_id: str = Field(min_length=1)
    v220_gate_id: str = Field(min_length=1)
    v220_decision_id: str = Field(min_length=1)
    v220_transition_id: str = Field(min_length=1)
    v220_condition_binding_id: str = Field(min_length=1)
    v220_composition_contract_id: str = Field(min_length=1)
    v220_authorization_id: Literal[
        "fresh_repaired_registry_complement_bound_exact_online_execution_authorization:"
        "ea1c906e3f9f8302bb2624defbf258f2601edd91e6256ae4ddec48be32517b5a"
    ] = V220_AUTHORIZATION_ID
    historical_v220_decision: str = Field(min_length=1)
    current_scoped_classification: Literal[
        "v26_220_materializes_an_unconsumed_fresh_authorization_object_but_"
        "does_not_authoritatively_bind_the_exact_v26_209_execution_condition"
    ]
    first_failed_gate: Literal["G2_EXACT_V209_192_JOB_CONDITION"] = (
        "G2_EXACT_V209_192_JOB_CONDITION"
    )
    authorization_object_construction_retained: Literal[True] = True
    exact_v209_condition_authority_retained: Literal[False] = False
    v220_authorization_consumed: Literal[False] = False
    v220_authorization_reusable: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V220Freeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_221_v220_freeze:"):
            raise ValueError("v26.221 v26.220 Freeze differs")
        return self


class FormalMember(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class V209FormalAuthorityFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    v220_freeze_id: str = Field(min_length=1)
    v209_source_commit: Literal["5809e9782515e55ee797b43730584d5d860aaa5c"]
    v209_source_tree: Literal["b2272bc1766a2d9b8c6562cb0b9f2f47151ad7cf"]
    exact_artifact_manifest_id: Literal[
        "finance_v26_209_artifact_manifest:"
        "1ec5df9edc0fb7b89921bbe3c154856e72e362cbbaee58a191bf9f275fc0bcf9"
    ] = V209_MANIFEST_ID
    exact_artifact_root: Literal[
        "finance_v26_209_artifact_root:"
        "76ef4cdb9cc0703f6bee2fd76c9c8ea7cbce5277337ff882ffcb44f8085e4770"
    ] = V209_ARTIFACT_ROOT
    formal_file_count: Literal[21] = 21
    formal_total_byte_count: Literal[44916386] = 44_916_386
    manifest_member_count: Literal[20] = 20
    manifest_member_byte_count: Literal[44912918] = 44_912_918
    members: tuple[FormalMember, ...] = Field(min_length=20, max_length=20)
    formal_member_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    path_match_count: Literal[20] = 20
    sha256_match_count: Literal[20] = 20
    byte_count_match_count: Literal[20] = 20
    actual_byte_match_count: Literal[20] = 20
    strict_object_identity_revalidation_count: Literal[1024] = 1_024
    source_file_commit_match_count: Literal[3] = 3
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V209FormalAuthorityFreeze:
        projection = tuple(item.model_dump(mode="json", warnings=False) for item in self.members)
        if (
            tuple(item.relative_path for item in self.members)
            != tuple(sorted({item.relative_path for item in self.members}))
            or canonical_sha256(projection) != self.formal_member_set_sha256
            or self.freeze_id
            != identity(self, "freeze_id", "finance_v26_221_v209_formal_authority_freeze:")
        ):
            raise ValueError("v26.221 v26.209 formal authority Freeze differs")
        return self


class RelationClosureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    formal_freeze_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    invocation_census_id: str = Field(min_length=1)
    implementation_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
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
    runner_contract_census_parent_match_count: Literal[12] = 12
    expected_job_set_match: Literal[True] = True
    all_relations_closed: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RelationClosureAudit:
        if (
            self.exact_package_ids != tuple(sorted(set(self.exact_package_ids)))
            or self.exact_job_ids != tuple(sorted(set(self.exact_job_ids)))
            or canonical_sha256(self.exact_package_ids) != self.exact_package_set_sha256
            or canonical_sha256(self.exact_job_ids) != self.exact_job_set_sha256
            or self.audit_id
            != identity(self, "audit_id", "finance_v26_221_v209_relation_closure_audit:")
        ):
            raise ValueError("v26.221 v26.209 relation closure Audit differs")
        return self


class AuthoritativeExecutionConditionBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    v220_freeze_id: str = Field(min_length=1)
    v209_formal_freeze_id: str = Field(min_length=1)
    relation_closure_audit_id: str = Field(min_length=1)
    exact_v209_artifact_manifest_id: Literal[
        "finance_v26_209_artifact_manifest:"
        "1ec5df9edc0fb7b89921bbe3c154856e72e362cbbaee58a191bf9f275fc0bcf9"
    ] = V209_MANIFEST_ID
    exact_v209_artifact_root: Literal[
        "finance_v26_209_artifact_root:"
        "76ef4cdb9cc0703f6bee2fd76c9c8ea7cbce5277337ff882ffcb44f8085e4770"
    ] = V209_ARTIFACT_ROOT
    formal_member_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_catalog_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    invocation_census_id: str = Field(min_length=1)
    implementation_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    exact_package_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
    exact_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    exact_package_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_coordinate_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    trace_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_package_count: Literal[32] = 32
    exact_job_count: Literal[192] = 192
    exact_coordinate_count: Literal[792] = 792
    previous_v220_condition_binding_id: str = Field(min_length=1)
    previous_v220_condition_authority_superseded: Literal[True] = True
    current_v220_authorization_consumed: Literal[False] = False
    current_v220_authorization_reusable: Literal[False] = False
    new_online_authorization_created: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> AuthoritativeExecutionConditionBinding:
        if (
            self.exact_package_ids != tuple(sorted(set(self.exact_package_ids)))
            or self.exact_job_ids != tuple(sorted(set(self.exact_job_ids)))
            or canonical_sha256(self.exact_package_ids) != self.exact_package_set_sha256
            or canonical_sha256(self.exact_job_ids) != self.exact_job_set_sha256
            or self.binding_id
            != identity(
                self,
                "binding_id",
                "fresh_exact_v209_execution_condition_authoritative_parent_binding:",
            )
        ):
            raise ValueError("v26.221 authoritative execution condition differs")
        return self


class RepairedCompositionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    v220_freeze_id: str = Field(min_length=1)
    authoritative_condition_binding_id: str = Field(min_length=1)
    v218_parent_set_binding_id: str = Field(min_length=1)
    retained_v220_composition_contract_id: str = Field(min_length=1)
    exact_v209_artifact_manifest_id: str = Field(min_length=1)
    exact_v209_artifact_root: str = Field(min_length=1)
    exact_v209_formal_member_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    relation_closure_required_before_authorization: Literal[True] = True
    v209_formal_admission_required_before_condition_construction: Literal[True] = True
    current_v220_authorization_forbidden: Literal[True] = True
    fresh_authorization_required_after_independent_audit: Literal[True] = True
    caller_terminal_forbidden: Literal[True] = True
    unbound_terminal_source_fails_closed: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> RepairedCompositionContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_exact_v209_parent_authority_repaired_composition_contract:",
        ):
            raise ValueError("v26.221 repaired Composition differs")
        return self


class UpstreamTamperControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    mutated_relative_path: Literal["executable_development_manifest.json"] = (
        "executable_development_manifest.json"
    )
    mutation_kind: Literal["job_id", "raw_namespace"]
    candidate_artifact_manifest_rehashed: bool
    candidate_artifact_manifest_id: str = Field(min_length=1)
    candidate_artifact_root: str = Field(min_length=1)
    prospective_condition_id: str = Field(min_length=1)
    prospective_composition_id: str = Field(min_length=1)
    prospective_authorization_id: str = Field(min_length=1)
    prospective_downstream_rehashed_object_count: Literal[3] = 3
    candidate_job_count: Literal[192] = 192
    candidate_unique_job_count: Literal[192] = 192
    candidate_namespace_count: Literal[192] = 192
    candidate_unique_namespace_count: Literal[192] = 192
    cardinality_preserved: Literal[True] = True
    rejected_before_condition_construction: Literal[True] = True
    authoritative_condition_created: Literal[False] = False
    online_authorization_created: Literal[False] = False
    rejection_stage: Literal["exact_v209_member_admission", "exact_v209_manifest_root_admission"]
    rejection_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    attack_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> UpstreamTamperControl:
        expected_stage = (
            "exact_v209_manifest_root_admission"
            if self.candidate_artifact_manifest_rehashed
            else "exact_v209_member_admission"
        )
        if self.rejection_stage != expected_stage or self.control_id != identity(
            self,
            "control_id",
            "finance_v26_221_upstream_tamper_control:",
        ):
            raise ValueError("v26.221 upstream tamper control differs")
        return self


class UpstreamTamperAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    formal_freeze_id: str = Field(min_length=1)
    controls: tuple[UpstreamTamperControl, ...] = Field(min_length=4, max_length=4)
    attack_count: Literal[4] = 4
    job_id_attack_count: Literal[2] = 2
    namespace_attack_count: Literal[2] = 2
    formal_manifest_rehash_attack_count: Literal[2] = 2
    prospective_downstream_rehashed_object_count: Literal[12] = 12
    rejected_before_condition_count: Literal[4] = 4
    accepted_attack_count: Literal[0] = 0
    authoritative_condition_created_count: Literal[0] = 0
    online_authorization_created_count: Literal[0] = 0
    attack_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> UpstreamTamperAudit:
        if (
            len({item.control_name for item in self.controls}) != 4
            or sum(item.mutation_kind == "job_id" for item in self.controls) != 2
            or sum(item.mutation_kind == "raw_namespace" for item in self.controls) != 2
            or sum(item.candidate_artifact_manifest_rehashed for item in self.controls) != 2
            or self.audit_id != identity(self, "audit_id", "finance_v26_221_upstream_tamper_audit:")
        ):
            raise ValueError("v26.221 upstream tamper Audit differs")
        return self


class ScopeBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    v220_authorization_id: str = Field(min_length=1)
    v220_authorization_consumed: Literal[False] = False
    v220_authorization_reused: Literal[False] = False
    new_online_authorizations: Literal[0] = 0
    durable_consumption_receipts: Literal[0] = 0
    durable_run_start_receipts: Literal[0] = 0
    manifest_job_executions: Literal[0] = 0
    provider_calls: Literal[0] = 0
    provider_client_constructions: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    raw_result_trace_outcome_checkpoint_rows: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    qa_reads: Literal[0] = 0
    mapper_state_frequency_contribution_vtdo_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ScopeBoundaryAudit:
        if self.audit_id != identity(self, "audit_id", "finance_v26_221_scope_boundary_audit:"):
            raise ValueError("v26.221 scope boundary Audit differs")
        return self


class GateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> GateResult:
        if self.gate_id != identity(self, "gate_id", "finance_v26_221_gate:"):
            raise ValueError("v26.221 Gate differs")
        return self


class GateEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    gates: tuple[GateResult, ...] = Field(min_length=8, max_length=8)
    passed_count: Literal[8] = 8
    failed_count: Literal[0] = 0
    all_gates_passed: Literal[True] = True
    online_authorization_issued: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> GateEvaluation:
        if len({item.gate_name for item in self.gates}) != 8 or self.evaluation_id != identity(
            self, "evaluation_id", "finance_v26_221_gate_evaluation:"
        ):
            raise ValueError("v26.221 Gate Evaluation differs")
        return self


class Decision(FrozenModel):
    decision_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v220_freeze_id: str = Field(min_length=1)
    v209_formal_freeze_id: str = Field(min_length=1)
    relation_closure_audit_id: str = Field(min_length=1)
    authoritative_condition_binding_id: str = Field(min_length=1)
    repaired_composition_contract_id: str = Field(min_length=1)
    upstream_tamper_audit_id: str = Field(min_length=1)
    scope_boundary_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_exact_v209_execution_condition_authoritative_parent_binding_repair_"
        "preflight_passed_independent_audit_required_online_authorization_blocked"
    ] = DECISION
    v220_authorization_consumed: Literal[False] = False
    v220_authorization_reusable: Literal[False] = False
    new_online_authorization_issued: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> Decision:
        if self.decision_id != identity(
            self, "decision_id", "finance_v26_221_parent_authority_decision:"
        ):
            raise ValueError("v26.221 Decision differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    status: Literal["PASSED_REPAIR_PREFLIGHT_ONLINE_AUTHORIZATION_BLOCKED"] = (
        "PASSED_REPAIR_PREFLIGHT_ONLINE_AUTHORIZATION_BLOCKED"
    )
    next_stage: Literal[
        "fresh_exact_v209_execution_condition_authoritative_parent_binding_"
        "repair_preflight_independent_audit_only"
    ] = NEXT_STAGE
    next_stage_authorized: Literal[False] = False
    separate_external_audit_decision_required: Literal[True] = True
    fresh_online_authorization_required_after_audit: Literal[True] = True
    v220_authorization_forbidden: Literal[True] = True
    provider_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> Transition:
        if self.transition_id != identity(self, "transition_id", "finance_v26_221_transition:"):
            raise ValueError("v26.221 Transition differs")
        return self


class SourceFile(FrozenModel):
    relative_path: str = Field(min_length=1)
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
            self, "source_identity_id", "finance_v26_221_source_identity:"
        ):
            raise ValueError("v26.221 source identity differs")
        return self


class ImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v220_freeze_id: str = Field(min_length=1)
    files: tuple[SourceFile, ...] = Field(min_length=3, max_length=3)
    formal_admission_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    relation_closure_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    attack_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_or_network_call_count: Literal[0] = 0
    credential_lookup_symbol_count: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ImplementationBinding:
        if tuple(item.relative_path for item in self.files) != tuple(
            sorted({item.relative_path for item in self.files})
        ) or self.binding_id != identity(
            self,
            "binding_id",
            "fresh_exact_v209_parent_authority_repair_implementation_binding:",
        ):
            raise ValueError("v26.221 implementation Binding differs")
        return self


class Report(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v220_freeze_id: str = Field(min_length=1)
    v209_formal_freeze_id: str = Field(min_length=1)
    relation_closure_audit_id: str = Field(min_length=1)
    authoritative_condition_binding_id: str = Field(min_length=1)
    repaired_composition_contract_id: str = Field(min_length=1)
    upstream_tamper_audit_id: str = Field(min_length=1)
    scope_boundary_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_exact_v209_execution_condition_authoritative_parent_binding_repair_"
        "preflight_passed_independent_audit_required_online_authorization_blocked"
    ] = DECISION
    v220_authorization_consumed: Literal[False] = False
    v220_authorization_reusable: Literal[False] = False
    new_online_authorizations: Literal[0] = 0
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> Report:
        if self.report_id != identity(
            self, "report_id", "finance_v26_221_parent_authority_report:"
        ):
            raise ValueError("v26.221 Report differs")
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
            prefix="finance_v26_221_artifact_root:",
        )
        if (
            self.file_count != len(self.members)
            or self.total_byte_count != sum(item.byte_count for item in self.members)
            or tuple(item.relative_path for item in self.members)
            != tuple(sorted({item.relative_path for item in self.members}))
            or self.artifact_root != root
            or self.manifest_id
            != identity(self, "manifest_id", "finance_v26_221_artifact_manifest:")
        ):
            raise ValueError("v26.221 Artifact Manifest differs")
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
        prefix="finance_v26_221_artifact_root:",
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
            prefix="finance_v26_221_artifact_manifest:",
        ),
    )
