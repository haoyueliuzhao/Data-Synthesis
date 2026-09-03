# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = (
    "fresh_repaired_upstream_terminal_domain_exact_registry_complement_independent_audit.v1"
)
CONSUMED_STAGE: Final = (
    "fresh_repaired_upstream_terminal_domain_exact_registry_complement_binding_"
    "preflight_independent_audit_only"
)
NEXT_STAGE: Final = (
    "fresh_repaired_upstream_terminal_domain_exact_registry_complement_bound_"
    "online_execution_authorization_only"
)
DECISION: Final = (
    "v26_218_upstream_terminal_domain_exact_registry_complement_binding_"
    "preflight_independent_audit_passed"
)
V218_DECISION: Final = (
    "fresh_repaired_upstream_terminal_domain_exact_registry_complement_binding_"
    "preflight_passed_independent_audit_required_online_execution_blocked"
)
V218_COMMIT: Final = "6171fcc27a4a88693cb9daa1485b0d658b11a5a1"
V218_TREE: Final = "1de85c4ee2f69a360bc7b7c13704186042648064"
REGISTRY_ID: Final = (
    "fresh_kernel_terminal_registry:"
    "a9d3089011f34b114b4b8264c09eb6b4c5875dd6978de0a2c3fe316577203152"
)
V217_EVENT_SOURCE_BINDING_ID: Final = (
    "fresh_repaired_upstream_failure_event_source_binding:"
    "16427f8aa014cc406c469e17519afd488b32a8af52f378d455b94bf35d384f68"
)
V217_SOURCE_CONTRACT_ID: Final = (
    "fresh_repaired_actual_v209_typed_failure_exit_surface_contract:"
    "ed3f99ef045982412db30a21d3d8b5bd4e03e8039908a6176a4c0637bd331742"
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


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False), prefix=prefix
    )


def make_identity(
    model: type[BaseModel], values: dict[str, Any], *, field: str, prefix: str
) -> BaseModel:
    provisional = model.model_construct(**{field: "pending"}, **values)
    return model.model_validate({field: identity(provisional, field, prefix), **values})


class ExternalIndependentAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: Literal["a631683b8532ff22cc015317fb31116a6d72179f682fcba0a94f93cd2d1ae56e"]
    review_byte_count: Literal[9045] = 9_045
    audit_result: Literal["PASSED_AS_SCOPED"] = "PASSED_AS_SCOPED"
    blocking_defect: Literal["NONE_FOUND"] = "NONE_FOUND"
    mandatory_revision: Literal["NONE"] = "NONE"
    operator_directive: Literal["参照审计报告继续实验"] = "参照审计报告继续实验"
    operator_directive_sha256: Literal[
        "2310d8996483f5f0d431940d98cbfc56a53e23aca61b59306de2d9bf61b9ec1a"
    ]
    operator_directive_byte_count: Literal[30] = 30
    only_authorized_stage: Literal[
        "fresh_repaired_upstream_terminal_domain_exact_registry_complement_binding_"
        "preflight_independent_audit_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    online_authorization_creation_authorized: Literal[False] = False
    online_execution_authorized: Literal[False] = False
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
                "finance_v26_219_external_independent_audit_authorization:",
            )
        ):
            raise ValueError("v26.219 external independent-audit authorization differs")
        return self


class V218Freeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v218_report_id: str = Field(min_length=1)
    v218_decision_id: str = Field(min_length=1)
    v218_transition_id: str = Field(min_length=1)
    v218_complement_binding_id: str = Field(min_length=1)
    v218_composition_contract_id: str = Field(min_length=1)
    v218_artifact_manifest_id: str = Field(min_length=1)
    v218_artifact_root: str = Field(min_length=1)
    v218_source_commit: Literal["6171fcc27a4a88693cb9daa1485b0d658b11a5a1"] = V218_COMMIT
    v218_source_tree: Literal["1de85c4ee2f69a360bc7b7c13704186042648064"] = V218_TREE
    v218_formal_file_count: Literal[51] = 51
    v218_formal_total_byte_count: Literal[1054511] = 1_054_511
    v218_manifest_member_count: Literal[50] = 50
    v218_manifest_member_byte_count: Literal[1044590] = 1_044_590
    v218_decision: Literal[
        "fresh_repaired_upstream_terminal_domain_exact_registry_complement_binding_"
        "preflight_passed_independent_audit_required_online_execution_blocked"
    ] = V218_DECISION
    historical_artifact_mutations: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V218Freeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_219_v218_freeze:"):
            raise ValueError("v26.219 v26.218 Freeze identity differs")
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
        if self.source_identity_id != identity(
            self, "source_identity_id", "finance_v26_219_source_identity:"
        ):
            raise ValueError("v26.219 source identity differs")
        return self


class ImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    files: tuple[SourceBinding, ...] = Field(min_length=3, max_length=3)
    symbols: tuple[SourceBinding, ...] = Field(min_length=6)
    candidate_v218_helper_calls: Literal[0] = 0
    direct_network_routes: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ImplementationBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_registry_complement_independent_audit_implementation_binding:",
        ):
            raise ValueError("v26.219 implementation Binding differs")
        return self


class DetachedRebuildAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    exact_source_commit: Literal["6171fcc27a4a88693cb9daa1485b0d658b11a5a1"] = V218_COMMIT
    exact_source_tree: Literal["1de85c4ee2f69a360bc7b7c13704186042648064"] = V218_TREE
    archived_source_file_count: int = Field(gt=0)
    credential_like_environment_variable_count: Literal[0] = 0
    rebuilt_file_count: Literal[51] = 51
    saved_file_count: Literal[51] = 51
    path_match_count: Literal[51] = 51
    sha256_match_count: Literal[51] = 51
    byte_count_match_count: Literal[51] = 51
    actual_byte_equality_count: Literal[51] = 51
    rebuilt_total_byte_count: Literal[1054511] = 1_054_511
    saved_total_byte_count: Literal[1054511] = 1_054_511
    manifest_member_revalidation_count: Literal[50] = 50
    candidate_report_used_as_outcome_oracle: Literal[False] = False
    candidate_gate_used_as_outcome_oracle: Literal[False] = False
    candidate_complement_audit_used_as_outcome_oracle: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DetachedRebuildAudit:
        if self.audit_id != identity(self, "audit_id", "finance_v26_219_detached_rebuild_audit:"):
            raise ValueError("v26.219 detached rebuild Audit differs")
        return self


class IndependentRegistryComplementAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    exact_v195_registry_id: Literal[
        "fresh_kernel_terminal_registry:"
        "a9d3089011f34b114b4b8264c09eb6b4c5875dd6978de0a2c3fe316577203152"
    ] = REGISTRY_ID
    exact_v195_registry_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    v217_event_source_binding_id: Literal[
        "fresh_repaired_upstream_failure_event_source_binding:"
        "16427f8aa014cc406c469e17519afd488b32a8af52f378d455b94bf35d384f68"
    ] = V217_EVENT_SOURCE_BINDING_ID
    candidate_binding_id: str = Field(min_length=1)
    reachable_terminal_policy_items: tuple[tuple[str, str], ...] = Field(
        min_length=16, max_length=16
    )
    admitted_event_terminal_policy_items: tuple[tuple[str, str, str], ...] = Field(
        min_length=1, max_length=1
    )
    admitted_terminal_kinds: tuple[str, ...] = Field(min_length=1, max_length=1)
    forbidden_terminal_kinds: tuple[str, ...] = Field(min_length=15, max_length=15)
    reachable_count: Literal[16] = 16
    admitted_count: Literal[1] = 1
    forbidden_count: Literal[15] = 15
    union_equals_reachable: Literal[True] = True
    intersection_is_empty: Literal[True] = True
    correct_registry_names_present: Literal[2] = 2
    old_misspellings_present: Literal[0] = 0
    admitted_mapping_derived_from_v217_source_binding: Literal[True] = True
    candidate_admitted_mapping_match: Literal[True] = True
    candidate_binding_actual_byte_match: Literal[True] = True
    candidate_helper_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentRegistryComplementAudit:
        reachable = tuple(item[0] for item in self.reachable_terminal_policy_items)
        admitted = tuple(self.admitted_terminal_kinds)
        forbidden = tuple(self.forbidden_terminal_kinds)
        if (
            reachable != tuple(sorted(reachable))
            or len(set(reachable)) != 16
            or admitted != ("instrument_failure",)
            or forbidden != tuple(sorted(set(reachable) - set(admitted)))
            or set(admitted) | set(forbidden) != set(reachable)
            or set(admitted) & set(forbidden)
            or "provider_failure_no_payload" not in forbidden
            or "resource_budget_exhausted" not in forbidden
            or "provider_no_payload_failure" in forbidden
            or "resource_failure" in forbidden
            or self.audit_id
            != identity(
                self,
                "audit_id",
                "finance_v26_219_independent_registry_complement_audit:",
            )
        ):
            raise ValueError("v26.219 independent Registry complement Audit differs")
        return self


class IndependentRetainedRuntimeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    detached_rebuild_audit_id: str = Field(min_length=1)
    runtime_relative_paths_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    retained_runtime_file_count: Literal[35] = 35
    v218_to_v217_path_match_count: Literal[35] = 35
    v218_to_v217_sha256_match_count: Literal[35] = 35
    v218_to_v217_actual_byte_match_count: Literal[35] = 35
    detached_to_v218_actual_byte_match_count: Literal[35] = 35
    ingress_receipt_count: Literal[2] = 2
    five_layer_file_count: Literal[25] = 25
    upstream_artifact_file_count: Literal[8] = 8
    v217_execution_object_actual_byte_match: Literal[True] = True
    candidate_retained_audit_used_as_outcome_oracle: Literal[False] = False
    provider_calls: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentRetainedRuntimeAudit:
        if self.audit_id != identity(
            self, "audit_id", "finance_v26_219_independent_retained_runtime_audit:"
        ):
            raise ValueError("v26.219 independent retained-runtime Audit differs")
        return self


class IndependentSourceExitChainRow(FrozenModel):
    row_id: str = Field(min_length=1)
    exit_code: Literal[
        "E0_invalid_dispatch_chain",
        "E1_empty_queue",
        "E2_authenticated_rethrow",
        "E3_reasoning_key",
        "E4_non_object",
    ]
    terminal_kind: Literal["instrument_failure", "privacy_rejection"]
    job_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    source_exit_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    raw_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    outcome_id: str = Field(min_length=1)
    checkpoint_id: str = Field(min_length=1)
    raw_result_trace_outcome_checkpoint_bytes_match_v217: Literal[5] = 5
    detached_layer_bytes_match: Literal[5] = 5
    content_identity_match_count: Literal[5] = 5
    source_contract_match: Literal[True] = True
    terminal_and_parent_chain_match: Literal[True] = True
    e2_upstream_artifact_chain_present: bool
    formal_empirical_row: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> IndependentSourceExitChainRow:
        expected = {
            "E0_invalid_dispatch_chain": "instrument_failure",
            "E1_empty_queue": "instrument_failure",
            "E2_authenticated_rethrow": "instrument_failure",
            "E3_reasoning_key": "privacy_rejection",
            "E4_non_object": "instrument_failure",
        }
        if (
            expected[self.exit_code] != self.terminal_kind
            or self.e2_upstream_artifact_chain_present
            != (self.exit_code == "E2_authenticated_rethrow")
            or self.row_id
            != identity(self, "row_id", "finance_v26_219_independent_source_exit_chain_row:")
        ):
            raise ValueError("v26.219 source-exit chain row differs")
        return self


class IndependentSourceExitPersistenceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    exact_source_contract_id: Literal[
        "fresh_repaired_actual_v209_typed_failure_exit_surface_contract:"
        "ed3f99ef045982412db30a21d3d8b5bd4e03e8039908a6176a4c0637bd331742"
    ] = V217_SOURCE_CONTRACT_ID
    rows: tuple[IndependentSourceExitChainRow, ...] = Field(min_length=5, max_length=5)
    source_exit_count: Literal[5] = 5
    distinct_source_exit_count: Literal[5] = 5
    instrument_terminal_count: Literal[4] = 4
    privacy_terminal_count: Literal[1] = 1
    five_layer_file_count: Literal[25] = 25
    v217_layer_actual_byte_match_count: Literal[25] = 25
    detached_layer_actual_byte_match_count: Literal[25] = 25
    content_identity_match_count: Literal[25] = 25
    source_contract_exit_count: Literal[5] = 5
    source_contract_row_match_count: Literal[5] = 5
    e2_upstream_chain_count: Literal[1] = 1
    e2_upstream_artifact_file_integrity_count: Literal[4] = 4
    exception_escape_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    candidate_execution_helper_calls: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentSourceExitPersistenceAudit:
        codes = tuple(row.exit_code for row in self.rows)
        if codes != (
            "E0_invalid_dispatch_chain",
            "E1_empty_queue",
            "E2_authenticated_rethrow",
            "E3_reasoning_key",
            "E4_non_object",
        ) or self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_219_independent_source_exit_persistence_audit:",
        ):
            raise ValueError("v26.219 source-exit persistence Audit differs")
        return self


class IndependentFullRehashAttackAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    registry_complement_audit_id: str = Field(min_length=1)
    candidate_binding_id: str = Field(min_length=1)
    candidate_composition_id: str = Field(min_length=1)
    candidate_gate_id: str = Field(min_length=1)
    candidate_report_id: str = Field(min_length=1)
    saved_negative_control_id: str = Field(min_length=1)
    expected_missing_terminal_kinds: tuple[str, str] = (
        "provider_failure_no_payload",
        "resource_budget_exhausted",
    )
    injected_non_registry_terminal_kinds: tuple[str, str] = (
        "provider_no_payload_failure",
        "resource_failure",
    )
    candidate_forbidden_count: Literal[15] = 15
    independently_rehashed_object_count: Literal[4] = 4
    saved_candidate_identity_match_count: Literal[4] = 4
    rejected: Literal[True] = True
    rejection_stage: Literal["independent_registry_complement_admission"] = (
        "independent_registry_complement_admission"
    )
    rejection_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    attack_output_writes: Literal[0] = 0
    candidate_attack_helper_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentFullRehashAttackAudit:
        if self.audit_id != identity(
            self, "audit_id", "finance_v26_219_independent_full_rehash_attack_audit:"
        ):
            raise ValueError("v26.219 independent full-rehash attack Audit differs")
        return self


class ScopeBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    current_v211_authorization_consumed: Literal[False] = False
    new_online_authorizations: Literal[0] = 0
    provider_calls: Literal[0] = 0
    provider_client_constructions: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    qa_reads: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ScopeBoundaryAudit:
        if self.audit_id != identity(self, "audit_id", "finance_v26_219_scope_boundary_audit:"):
            raise ValueError("v26.219 scope boundary Audit differs")
        return self


class GateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> GateResult:
        if self.gate_id != identity(self, "gate_id", "finance_v26_219_gate:"):
            raise ValueError("v26.219 Gate identity differs")
        return self


class GateEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    gates: tuple[GateResult, ...] = Field(min_length=7, max_length=7)
    passed_count: Literal[7] = 7
    failed_count: Literal[0] = 0
    all_gates_passed: Literal[True] = True
    provider_calls: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> GateEvaluation:
        if len({gate.gate_name for gate in self.gates}) != 7 or self.evaluation_id != identity(
            self, "evaluation_id", "finance_v26_219_gate_evaluation:"
        ):
            raise ValueError("v26.219 Gate Evaluation differs")
        return self


class Decision(FrozenModel):
    decision_id: str = Field(min_length=1)
    decision: Literal[
        "v26_218_upstream_terminal_domain_exact_registry_complement_binding_"
        "preflight_independent_audit_passed"
    ] = DECISION
    authorization_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    detached_rebuild_audit_id: str = Field(min_length=1)
    registry_complement_audit_id: str = Field(min_length=1)
    retained_runtime_audit_id: str = Field(min_length=1)
    source_exit_persistence_audit_id: str = Field(min_length=1)
    full_rehash_attack_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    mandatory_revision: Literal["NONE"] = "NONE"
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> Decision:
        if self.decision_id != identity(
            self, "decision_id", "finance_v26_219_independent_audit_decision:"
        ):
            raise ValueError("v26.219 Decision differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    status: Literal["PASSED_INDEPENDENT_AUDIT_ONLINE_EXECUTION_BLOCKED"] = (
        "PASSED_INDEPENDENT_AUDIT_ONLINE_EXECUTION_BLOCKED"
    )
    next_stage: Literal[
        "fresh_repaired_upstream_terminal_domain_exact_registry_complement_bound_"
        "online_execution_authorization_only"
    ] = NEXT_STAGE
    next_stage_authorized: Literal[False] = False
    separate_external_decision_required: Literal[True] = True
    online_authorization_created: Literal[False] = False
    provider_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> Transition:
        if self.transition_id != identity(self, "transition_id", "finance_v26_219_transition:"):
            raise ValueError("v26.219 Transition differs")
        return self


class Report(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    detached_rebuild_audit_id: str = Field(min_length=1)
    registry_complement_audit_id: str = Field(min_length=1)
    retained_runtime_audit_id: str = Field(min_length=1)
    source_exit_persistence_audit_id: str = Field(min_length=1)
    full_rehash_attack_audit_id: str = Field(min_length=1)
    scope_boundary_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    decision: Literal[
        "v26_218_upstream_terminal_domain_exact_registry_complement_binding_"
        "preflight_independent_audit_passed"
    ] = DECISION
    current_v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> Report:
        if self.report_id != identity(
            self, "report_id", "finance_v26_219_independent_audit_report:"
        ):
            raise ValueError("v26.219 Report differs")
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
            self.file_count != len(self.members)
            or self.total_byte_count != sum(item.byte_count for item in self.members)
            or tuple(item.relative_path for item in self.members)
            != tuple(sorted({item.relative_path for item in self.members}))
        ):
            raise ValueError("v26.219 Artifact Manifest geometry differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_219_artifact_root:",
        )
        if self.artifact_root != expected_root or self.manifest_id != identity(
            self, "manifest_id", "finance_v26_219_artifact_manifest:"
        ):
            raise ValueError("v26.219 Artifact Root or Manifest differs")
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
        prefix="finance_v26_219_artifact_root:",
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
            prefix="finance_v26_219_artifact_manifest:",
        ),
    )
