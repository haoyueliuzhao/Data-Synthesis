# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_models as v217_models,
)
from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_repaired_upstream_terminal_domain_exact_registry_complement.v1"
CONSUMED_STAGE: Final = (
    "fresh_repaired_upstream_terminal_domain_exact_registry_complement_binding_preflight_only"
)
NEXT_STAGE: Final = (
    "fresh_repaired_upstream_terminal_domain_exact_registry_complement_binding_"
    "preflight_independent_audit_only"
)
DECISION: Final = (
    "fresh_repaired_upstream_terminal_domain_exact_registry_complement_binding_"
    "preflight_passed_independent_audit_required_online_execution_blocked"
)
EXACT_V195_REGISTRY_ID: Final = (
    "fresh_kernel_terminal_registry:"
    "a9d3089011f34b114b4b8264c09eb6b4c5875dd6978de0a2c3fe316577203152"
)
ADMITTED_EVENT_KIND: Final = "transport_instrument_failure"
ADMITTED_TERMINAL_KIND: Final = "instrument_failure"


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
    model: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> BaseModel:
    provisional = model.model_construct(**{field: "pending"}, **values)
    return model.model_validate({field: identity(provisional, field, prefix), **values})


class ExternalRevisionAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: Literal["4af91cc69d550143fc21f8c8afd0adb61ac3377d6dc51fe0994db3dda397b21f"]
    review_byte_count: Literal[14305] = 14_305
    operator_directive: Literal["参照审计报告继续实验修订"] = "参照审计报告继续实验修订"
    operator_directive_sha256: Literal[
        "dc2b598ec3667bd0e26354d1dac1ca447fa87acea50bd30a5fc245a9c35374e9"
    ]
    operator_directive_byte_count: Literal[36] = 36
    audit_result: Literal["VALID_SCOPED_CALLER_LABEL_REMOVAL_AND_ARTIFACT_BACKED_E2_CHAIN"] = (
        "VALID_SCOPED_CALLER_LABEL_REMOVAL_AND_ARTIFACT_BACKED_E2_CHAIN"
    )
    failed_at: Literal["EXACT_V195_REACHABLE_TERMINAL_COMPLEMENT_BINDING"] = (
        "EXACT_V195_REACHABLE_TERMINAL_COMPLEMENT_BINDING"
    )
    consumed_stage: Literal[
        "fresh_repaired_upstream_terminal_domain_exact_registry_complement_binding_preflight_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalRevisionAuthorization:
        if self.authorization_id != identity(
            self, "authorization_id", "finance_v26_218_external_revision_authorization:"
        ):
            raise ValueError("v26.218 external authorization identity differs")
        return self


class V217Freeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v217_report_id: str = Field(min_length=1)
    v217_decision_id: str = Field(min_length=1)
    v217_transition_id: str = Field(min_length=1)
    v217_artifact_manifest_id: str = Field(min_length=1)
    v217_artifact_root: str = Field(min_length=1)
    v217_source_commit: Literal["650911314b8a65d7c7480ae405f983ca6083e114"] = (
        "650911314b8a65d7c7480ae405f983ca6083e114"
    )
    v217_source_tree: Literal["57fb9b657378174651c3e841d942314c8d1bdb83"] = (
        "57fb9b657378174651c3e841d942314c8d1bdb83"
    )
    formal_file_count: Literal[59] = 59
    formal_total_byte_count: Literal[1075394] = 1_075_394
    manifest_member_count: Literal[58] = 58
    manifest_member_byte_count: Literal[1064349] = 1_064_349
    caller_label_removal_retained: Literal[True] = True
    artifact_backed_e2_chain_retained: Literal[True] = True
    singleton_runtime_derivation_retained: Literal[True] = True
    exact_registry_complement_failed: Literal[True] = True
    first_blocker: Literal["forbidden_terminal_kinds_is_not_exact_v195_reachable_complement"] = (
        "forbidden_terminal_kinds_is_not_exact_v195_reachable_complement"
    )
    v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V217Freeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_218_v217_freeze:"):
            raise ValueError("v26.218 v26.217 Freeze identity differs")
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
    implementation_files: tuple[str, ...] = Field(min_length=4, max_length=4)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_source(self) -> SourceIdentity:
        if self.source_identity_id != identity(
            self, "source_identity_id", "finance_v26_218_source_identity:"
        ):
            raise ValueError("v26.218 source identity differs")
        return self


class ImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v217_freeze_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    files: tuple[SourceBinding, ...] = Field(min_length=4, max_length=4)
    symbols: tuple[SourceBinding, ...] = Field(min_length=4)
    direct_network_routes: Literal[0] = 0
    credential_environment_routes: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ImplementationBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_upstream_terminal_domain_implementation_binding:",
        ):
            raise ValueError("v26.218 implementation Binding differs")
        return self


class ExactRegistryComplementBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    v217_event_source_binding_id: str = Field(min_length=1)
    exact_v195_terminal_registry_id: Literal[
        "fresh_kernel_terminal_registry:"
        "a9d3089011f34b114b4b8264c09eb6b4c5875dd6978de0a2c3fe316577203152"
    ] = EXACT_V195_REGISTRY_ID
    reachable_terminal_policy_items: tuple[tuple[str, str], ...] = Field(
        min_length=16, max_length=16
    )
    admitted_event_terminal_policy_items: tuple[tuple[str, str, str], ...] = Field(
        min_length=1, max_length=1
    )
    admitted_terminal_kinds: tuple[str, ...] = Field(min_length=1, max_length=1)
    forbidden_terminal_kinds: tuple[str, ...] = Field(min_length=15, max_length=15)
    registry_reachable_count: Literal[16] = 16
    admitted_terminal_count: Literal[1] = 1
    forbidden_terminal_count: Literal[15] = 15
    union_equals_reachable: Literal[True] = True
    intersection_is_empty: Literal[True] = True
    forbidden_derived_from_registry: Literal[True] = True
    handwritten_forbidden_set_is_authority: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ExactRegistryComplementBinding:
        reachable = tuple(item[0] for item in self.reachable_terminal_policy_items)
        policies = tuple(item[1] for item in self.reachable_terminal_policy_items)
        admitted = tuple(self.admitted_terminal_kinds)
        forbidden = tuple(self.forbidden_terminal_kinds)
        event_kind, event_terminal, event_policy = self.admitted_event_terminal_policy_items[0]
        policy_by_terminal = dict(self.reachable_terminal_policy_items)
        expected_forbidden = tuple(sorted(set(reachable) - set(admitted)))
        if (
            reachable != tuple(sorted(reachable))
            or len(set(reachable)) != 16
            or len(set(policies)) != 16
            or admitted != (ADMITTED_TERMINAL_KIND,)
            or event_kind != ADMITTED_EVENT_KIND
            or event_terminal != ADMITTED_TERMINAL_KIND
            or event_policy != policy_by_terminal.get(ADMITTED_TERMINAL_KIND)
            or forbidden != expected_forbidden
            or set(admitted) | set(forbidden) != set(reachable)
            or set(admitted) & set(forbidden)
            or "provider_failure_no_payload" not in forbidden
            or "resource_budget_exhausted" not in forbidden
            or "provider_no_payload_failure" in forbidden
            or "resource_failure" in forbidden
            or self.binding_id
            != identity(
                self,
                "binding_id",
                "fresh_repaired_exact_v195_registry_complement_binding:",
            )
        ):
            raise ValueError("v26.218 exact Registry-complement Binding differs")
        return self


class CompositionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    v217_freeze_id: str = Field(min_length=1)
    complement_binding_id: str = Field(min_length=1)
    v217_source_contract_id: str = Field(min_length=1)
    v217_event_source_binding_id: str = Field(min_length=1)
    v217_observation_binding_id: str = Field(min_length=1)
    v217_runner_binding_id: str = Field(min_length=1)
    v217_dispatcher_binding_id: str = Field(min_length=1)
    v217_persistence_binding_id: str = Field(min_length=1)
    v217_consumer_binding_id: str = Field(min_length=1)
    v217_composition_contract_id: str = Field(min_length=1)
    exact_sequence: tuple[str, ...] = (
        "exact_v195_registry_load",
        "reachable_terminal_policy_derivation",
        "admitted_singleton_derivation",
        "exact_forbidden_complement_derivation",
        "noncompensatory_partition_admission",
        "retained_v217_single_consumer_execution",
    )
    current_v211_authorization_consumed: Literal[False] = False
    new_online_authorization_created: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CompositionContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_repaired_exact_registry_complement_composition_contract:",
        ):
            raise ValueError("v26.218 Composition Contract differs")
        return self


class RetainedExecutionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    complement_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    v217_execution: v217_models.ExitSurfaceExecutionAudit
    exact_v217_execution_object_match: Literal[True] = True
    retained_runtime_file_byte_match_count: Literal[35] = 35
    retained_source_exit_controls: Literal[5] = 5
    retained_persisted_layers: Literal[25] = 25
    retained_upstream_artifact_files: Literal[8] = 8
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RetainedExecutionAudit:
        if (
            self.v217_execution.typed_failure_exit_count != 5
            or self.v217_execution.persisted_layer_count != 25
            or self.v217_execution.provider_calls != 0
            or self.audit_id
            != identity(
                self,
                "audit_id",
                "finance_v26_218_retained_execution_audit:",
            )
        ):
            raise ValueError("v26.218 retained execution Audit differs")
        return self


class ComplementNegativeControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: Literal["same_length_misspelled_registry_complement_full_rehash"] = (
        "same_length_misspelled_registry_complement_full_rehash"
    )
    candidate_binding_id: str = Field(min_length=1)
    candidate_composition_id: str = Field(min_length=1)
    candidate_gate_id: str = Field(min_length=1)
    candidate_report_id: str = Field(min_length=1)
    expected_missing_terminal_kinds: tuple[str, str] = (
        "provider_failure_no_payload",
        "resource_budget_exhausted",
    )
    injected_non_registry_terminal_kinds: tuple[str, str] = (
        "provider_no_payload_failure",
        "resource_failure",
    )
    candidate_forbidden_count: Literal[15] = 15
    fully_rehashed_object_count: Literal[4] = 4
    rejected: Literal[True] = True
    rejection_stage: Literal["registry_complement_admission"] = "registry_complement_admission"
    rejection_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> ComplementNegativeControl:
        if self.control_id != identity(
            self,
            "control_id",
            "finance_v26_218_registry_complement_negative_control:",
        ):
            raise ValueError("v26.218 complement negative control differs")
        return self


class NegativeControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    complement_binding_id: str = Field(min_length=1)
    control: ComplementNegativeControl
    rejected_count: Literal[1] = 1
    accepted_count: Literal[0] = 0
    fully_rehashed_object_count: Literal[4] = 4
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> NegativeControlAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_218_registry_complement_negative_control_audit:",
        ):
            raise ValueError("v26.218 negative-control Audit differs")
        return self


class ScopeBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v217_freeze_id: str = Field(min_length=1)
    complement_binding_id: str = Field(min_length=1)
    isolated_preflight_lease_count: Literal[1] = 1
    preflight_run_start_receipt_count: Literal[1] = 1
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
        if self.audit_id != identity(self, "audit_id", "finance_v26_218_scope_boundary_audit:"):
            raise ValueError("v26.218 scope boundary Audit differs")
        return self


class GateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> GateResult:
        if self.gate_id != identity(self, "gate_id", "finance_v26_218_gate:"):
            raise ValueError("v26.218 Gate identity differs")
        return self


class GateEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    gates: tuple[GateResult, ...] = Field(min_length=8, max_length=8)
    passed_count: Literal[8] = 8
    failed_count: Literal[0] = 0
    all_gates_passed: Literal[True] = True
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> GateEvaluation:
        if len({item.gate_name for item in self.gates}) != 8 or self.evaluation_id != identity(
            self, "evaluation_id", "finance_v26_218_gate_evaluation:"
        ):
            raise ValueError("v26.218 Gate Evaluation differs")
        return self


class Decision(FrozenModel):
    decision_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_upstream_terminal_domain_exact_registry_complement_binding_"
        "preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    external_authorization_id: str = Field(min_length=1)
    v217_freeze_id: str = Field(min_length=1)
    complement_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    retained_execution_audit_id: str = Field(min_length=1)
    negative_control_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> Decision:
        if self.decision_id != identity(
            self, "decision_id", "finance_v26_218_registry_complement_decision:"
        ):
            raise ValueError("v26.218 Decision differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    status: Literal["PASSED_PREFLIGHT_ONLINE_EXECUTION_BLOCKED"] = (
        "PASSED_PREFLIGHT_ONLINE_EXECUTION_BLOCKED"
    )
    next_stage: Literal[
        "fresh_repaired_upstream_terminal_domain_exact_registry_complement_binding_"
        "preflight_independent_audit_only"
    ] = NEXT_STAGE
    provider_execution_authorized: Literal[False] = False
    new_online_authorization_required_after_independent_audit: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> Transition:
        if self.transition_id != identity(self, "transition_id", "finance_v26_218_transition:"):
            raise ValueError("v26.218 Transition differs")
        return self


class Report(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v217_freeze_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    complement_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    retained_execution_audit_id: str = Field(min_length=1)
    negative_control_audit_id: str = Field(min_length=1)
    scope_boundary_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_upstream_terminal_domain_exact_registry_complement_binding_"
        "preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    current_v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> Report:
        if self.report_id != identity(
            self, "report_id", "finance_v26_218_registry_complement_report:"
        ):
            raise ValueError("v26.218 Report differs")
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
            raise ValueError("v26.218 Artifact Manifest geometry differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_218_artifact_root:",
        )
        if self.artifact_root != expected_root or self.manifest_id != identity(
            self, "manifest_id", "finance_v26_218_artifact_manifest:"
        ):
            raise ValueError("v26.218 Artifact Root or Manifest differs")
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
        prefix="finance_v26_218_artifact_root:",
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
            prefix="finance_v26_218_artifact_manifest:",
        ),
    )
