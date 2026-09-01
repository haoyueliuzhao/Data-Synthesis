from __future__ import annotations

import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_artifact_backed_terminal_to_outcome_online_authorization.v1"
CONSUMED_STAGE: Final = (
    "fresh_artifact_backed_terminal_to_outcome_integration_repair_"
    "online_execution_authorization_only"
)
NEXT_STAGE: Final = (
    "fresh_artifact_backed_terminal_to_outcome_integration_repair_"
    "exact_192_job_online_execution_only"
)


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


def canonical_bytes(value: BaseModel) -> bytes:
    return (
        json.dumps(
            value.model_dump(mode="json", warnings=False),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ExternalOnlineAuthorizationDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    audit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_byte_count: int = Field(gt=0)
    audit_decision: Literal["v26_198_accepted_online_authorization_only"]
    consumed_stage: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_"
        "online_execution_authorization_only"
    ] = CONSUMED_STAGE
    v198_report_id: str = Field(min_length=1)
    v198_decision_id: str = Field(min_length=1)
    v198_transition_id: str = Field(min_length=1)
    issue_narrow_online_authorization: Literal[True] = True
    provider_execution_during_authorization: Literal[False] = False
    source_manifest_or_authority_change_authorized: Literal[False] = False
    qa_integration_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> ExternalOnlineAuthorizationDecision:
        if self.decision_id != identity(
            self,
            "decision_id",
            "finance_v26_199_external_online_authorization_decision:",
        ):
            raise ValueError("v26.199 external authorization decision identity differs")
        return self


class V198AuthorityFreeze(FrozenModel):
    audit_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v198_report_id: str = Field(min_length=1)
    v198_decision_id: str = Field(min_length=1)
    v198_transition_id: str = Field(min_length=1)
    v198_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    v198_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    v198_sealed_artifact_root: str = Field(min_length=1)
    v198_distribution_artifact_root: str = Field(min_length=1)
    formal_file_count: Literal[48] = 48
    formal_file_match_count: Literal[48] = 48
    formal_total_byte_count: Literal[275894] = 275_894
    sealed_member_count: Literal[45] = 45
    distribution_member_count: Literal[47] = 47
    all_v198_gates_passed: Literal[True] = True
    online_execution_authorized_before_v199: Literal[False] = False
    predecessor_mutation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V198AuthorityFreeze:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_199_v198_authority_freeze_audit:",
        ):
            raise ValueError("v26.199 v26.198 Freeze identity differs")
        return self


class FrozenExecutionConditionBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v198_freeze_audit_id: str = Field(min_length=1)
    v194_report_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    runtime_semantic_contract_id: str = Field(min_length=1)
    kernel_resource_persistence_contract_id: str = Field(min_length=1)
    generation_profile_id: str = Field(min_length=1)
    prompt_contract_id: str = Field(min_length=1)
    prompt_schema_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    thinking_policy_id: str = Field(min_length=1)
    action_grammar_id: str = Field(min_length=1)
    final_grammar_id: str = Field(min_length=1)
    bounded_generation_policy_id: str = Field(min_length=1)
    generation_resource_contract_id: str = Field(min_length=1)
    exact_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    exact_job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_files: tuple[FileBinding, ...] = Field(min_length=9, max_length=9)
    exact_package_count: Literal[32] = 32
    exact_replica_count: Literal[6] = 6
    exact_job_count: Literal[192] = 192
    exact_registered_invocation_count: Literal[792] = 792
    unique_raw_namespace_count: Literal[192] = 192
    unique_result_namespace_count: Literal[192] = 192
    condition_changed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> FrozenExecutionConditionBinding:
        if self.exact_job_ids != tuple(sorted(set(self.exact_job_ids))):
            raise ValueError("v26.199 exact Job set differs")
        if len({item.relative_path for item in self.parent_files}) != 9:
            raise ValueError("v26.199 frozen parent file set differs")
        if self.binding_id != identity(
            self,
            "binding_id",
            "finance_v26_199_frozen_execution_condition_binding:",
        ):
            raise ValueError("v26.199 frozen execution condition identity differs")
        return self


class SuccessorIntegrationAuthorityBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    v198_freeze_audit_id: str = Field(min_length=1)
    frozen_condition_binding_id: str = Field(min_length=1)
    v197_report_id: str = Field(min_length=1)
    v198_report_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    integration_implementation_binding_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    raw_descriptor_contract_id: str = Field(min_length=1)
    result_descriptor_contract_id: str = Field(min_length=1)
    attempt_trace_contract_id: str = Field(min_length=1)
    outcome_row_contract_id: str = Field(min_length=1)
    evaluator_contract_id: str = Field(min_length=1)
    successor_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    successor_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    successor_files: tuple[FileBinding, ...] = Field(min_length=4, max_length=4)
    reachable_terminal_count: Literal[16] = 16
    excluded_terminal_count: Literal[2] = 2
    old_complete_job_fallback_forbidden: Literal[True] = True
    fresh_writer_required: Literal[True] = True
    raw_before_result_required: Literal[True] = True
    caller_terminal_forbidden: Literal[True] = True
    authority_semantics_changed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> SuccessorIntegrationAuthorityBinding:
        six = (
            self.terminal_registry_id,
            self.raw_descriptor_contract_id,
            self.result_descriptor_contract_id,
            self.attempt_trace_contract_id,
            self.outcome_row_contract_id,
            self.evaluator_contract_id,
        )
        if len(set(six)) != 6:
            raise ValueError("v26.199 six Outcome authority identities differ")
        if self.binding_id != identity(
            self,
            "binding_id",
            "finance_v26_199_successor_integration_authority_binding:",
        ):
            raise ValueError("v26.199 successor integration binding identity differs")
        return self


class ExactOnlineExecutionAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v198_freeze_audit_id: str = Field(min_length=1)
    frozen_condition_binding_id: str = Field(min_length=1)
    successor_integration_binding_id: str = Field(min_length=1)
    v198_report_id: str = Field(min_length=1)
    v198_decision_id: str = Field(min_length=1)
    v198_transition_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    integration_implementation_binding_id: str = Field(min_length=1)
    generation_profile_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    thinking_policy_id: str = Field(min_length=1)
    action_grammar_id: str = Field(min_length=1)
    final_grammar_id: str = Field(min_length=1)
    bounded_generation_policy_id: str = Field(min_length=1)
    generation_resource_contract_id: str = Field(min_length=1)
    kernel_resource_persistence_contract_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    raw_descriptor_contract_id: str = Field(min_length=1)
    result_descriptor_contract_id: str = Field(min_length=1)
    attempt_trace_contract_id: str = Field(min_length=1)
    outcome_row_contract_id: str = Field(min_length=1)
    evaluator_contract_id: str = Field(min_length=1)
    exact_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    exact_job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorized_stage: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_"
        "exact_192_job_online_execution_only"
    ] = NEXT_STAGE
    exact_package_count: Literal[32] = 32
    exact_job_count: Literal[192] = 192
    maximum_manifest_executions: Literal[1] = 1
    online_execution_authorized: Literal[True] = True
    provider_calls_authorized: Literal[True] = True
    exact_192_job_execution_authorized: Literal[True] = True
    precredential_validation_required: Literal[True] = True
    fresh_outcome_writer_required: Literal[True] = True
    old_complete_job_fallback_forbidden: Literal[True] = True
    authorization_reuse_authorized: Literal[False] = False
    replacement_rerun_authorized: Literal[False] = False
    recovery_execution_authorized: Literal[False] = False
    source_or_manifest_change_authorized: Literal[False] = False
    model_thinking_grammar_policy_resource_change_authorized: Literal[False] = False
    authority_semantic_change_authorized: Literal[False] = False
    qa_integration_authorized: Literal[False] = False
    mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    provider_calls_during_authorization: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExactOnlineExecutionAuthorization:
        if self.exact_job_ids != tuple(sorted(set(self.exact_job_ids))):
            raise ValueError("v26.199 Authorization Job denominator differs")
        six = (
            self.terminal_registry_id,
            self.raw_descriptor_contract_id,
            self.result_descriptor_contract_id,
            self.attempt_trace_contract_id,
            self.outcome_row_contract_id,
            self.evaluator_contract_id,
        )
        if len(set(six)) != 6:
            raise ValueError("v26.199 Authorization authority identities differ")
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "fresh_terminal_to_outcome_exact_online_execution_authorization:",
        ):
            raise ValueError("v26.199 online Authorization identity differs")
        return self


class OnlineAuthorizationAdmission(FrozenModel):
    admission_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authorized_stage: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_"
        "exact_192_job_online_execution_only"
    ] = NEXT_STAGE
    manifest_id: str = Field(min_length=1)
    exact_job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_execution_requested: Literal[True] = True
    qa_integration_requested: Literal[False] = False
    admitted_before_client_construction: Literal[True] = True
    admitted_before_writer_construction: Literal[True] = True
    admitted_before_credential_lookup: Literal[True] = True
    credential_lookup_permitted_after_admission: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_admission(self) -> OnlineAuthorizationAdmission:
        if self.admission_id != identity(
            self,
            "admission_id",
            "fresh_terminal_to_outcome_online_authorization_admission:",
        ):
            raise ValueError("v26.199 online admission identity differs")
        return self


class PrecredentialOnlineAuthorizationGuard:
    """Exact one-authorization guard for the future v26.200 execution entry."""

    def __init__(
        self,
        *,
        expected_authorization: ExactOnlineExecutionAuthorization,
        expected_authorization_bytes: bytes,
    ) -> None:
        strict = ExactOnlineExecutionAuthorization.model_validate(
            expected_authorization.model_dump(mode="python", warnings=False)
        )
        if expected_authorization_bytes != canonical_bytes(strict):
            raise ValueError("expected online authorization bytes differ")
        self._expected = strict
        self._expected_bytes = expected_authorization_bytes

    def admit(
        self,
        *,
        authorization: object | None,
        authorization_bytes: bytes | None,
        requested_stage: str,
        requested_manifest_id: str,
        requested_job_ids: tuple[str, ...],
        requested_runner_id: str,
        requested_execution_contract_id: str,
        requested_integration_contract_id: str,
        requested_generation_profile_id: str,
        requested_model_config_id: str,
        requested_thinking_policy_id: str,
        requested_action_grammar_id: str,
        requested_final_grammar_id: str,
        requested_policy_id: str,
        requested_generation_resource_contract_id: str,
        requested_kernel_resource_contract_id: str,
        provider_execution_requested: bool,
        qa_integration_requested: bool,
    ) -> OnlineAuthorizationAdmission:
        if type(authorization) is not ExactOnlineExecutionAuthorization:
            raise ValueError("online authorization parent type differs")
        assert isinstance(authorization, ExactOnlineExecutionAuthorization)
        strict = ExactOnlineExecutionAuthorization.model_validate(
            authorization.model_dump(mode="python", warnings=False)
        )
        if (
            authorization_bytes is None
            or authorization_bytes != self._expected_bytes
            or strict.authorization_id != self._expected.authorization_id
        ):
            raise ValueError("online authorization bytes or identity differ")
        expected_pairs = (
            (requested_stage, strict.authorized_stage),
            (requested_manifest_id, strict.manifest_id),
            (requested_runner_id, strict.runner_id),
            (requested_execution_contract_id, strict.execution_contract_id),
            (requested_integration_contract_id, strict.integration_contract_id),
            (requested_generation_profile_id, strict.generation_profile_id),
            (requested_model_config_id, strict.model_config_id),
            (requested_thinking_policy_id, strict.thinking_policy_id),
            (requested_action_grammar_id, strict.action_grammar_id),
            (requested_final_grammar_id, strict.final_grammar_id),
            (requested_policy_id, strict.bounded_generation_policy_id),
            (
                requested_generation_resource_contract_id,
                strict.generation_resource_contract_id,
            ),
            (
                requested_kernel_resource_contract_id,
                strict.kernel_resource_persistence_contract_id,
            ),
        )
        if any(actual != expected for actual, expected in expected_pairs):
            raise ValueError("requested online execution parent differs")
        if requested_job_ids != strict.exact_job_ids:
            raise ValueError("requested online Job set differs")
        if not provider_execution_requested:
            raise ValueError("online authorization requires the exact Provider execution request")
        if qa_integration_requested:
            raise ValueError("online authorization forbids QA integration")
        return cast(
            OnlineAuthorizationAdmission,
            make_identity(
                OnlineAuthorizationAdmission,
                {
                    "authorization_id": strict.authorization_id,
                    "manifest_id": strict.manifest_id,
                    "exact_job_set_sha256": strict.exact_job_set_sha256,
                },
                field="admission_id",
                prefix="fresh_terminal_to_outcome_online_authorization_admission:",
            ),
        )


class AdmissionControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    admitted: bool
    rejected: bool
    rejection_reason_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    client_factory_count: int = Field(ge=0, le=1)
    kernel_writer_factory_count: int = Field(ge=0, le=1)
    outcome_writer_factory_count: int = Field(ge=0, le=1)
    credential_lookup_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> AdmissionControl:
        if self.admitted == self.rejected:
            raise ValueError("v26.199 admission disposition differs")
        if self.admitted:
            if self.rejection_reason_sha256 is not None or (
                self.client_factory_count,
                self.kernel_writer_factory_count,
                self.outcome_writer_factory_count,
            ) != (1, 1, 1):
                raise ValueError("v26.199 legal admission probe differs")
        elif self.rejection_reason_sha256 is None or any(
            (
                self.client_factory_count,
                self.kernel_writer_factory_count,
                self.outcome_writer_factory_count,
            )
        ):
            raise ValueError("v26.199 invalid admission reached a factory")
        if self.control_id != identity(
            self,
            "control_id",
            "finance_v26_199_precredential_admission_control:",
        ):
            raise ValueError("v26.199 admission control identity differs")
        return self


class PrecredentialAdmissionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    admission_id: str = Field(min_length=1)
    controls: tuple[AdmissionControl, ...] = Field(min_length=10, max_length=10)
    legal_control_count: Literal[1] = 1
    invalid_control_count: Literal[9] = 9
    invalid_control_factory_call_count: Literal[0] = 0
    credential_lookup_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PrecredentialAdmissionAudit:
        if (
            sum(item.admitted for item in self.controls) != 1
            or sum(item.rejected for item in self.controls) != 9
            or len({item.control_name for item in self.controls}) != 10
        ):
            raise ValueError("v26.199 admission control denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_199_precredential_admission_audit:",
        ):
            raise ValueError("v26.199 admission audit identity differs")
        return self


class ScopeExclusionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    exact_job_count: Literal[192] = 192
    online_execution_consumed: Literal[False] = False
    manifest_job_execution_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    raw_files_written: Literal[0] = 0
    result_files_written: Literal[0] = 0
    development_outcomes: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    qa_population_reads: Literal[0] = 0
    qa_change_count: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    old_complete_job_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ScopeExclusionAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_199_scope_exclusion_audit:",
        ):
            raise ValueError("v26.199 scope exclusion identity differs")
        return self


class DestructiveControl(FrozenModel):
    control_id: str = Field(min_length=1)
    attack_name: str = Field(min_length=1)
    changed_authorization_id: str = Field(min_length=1)
    downstream_rehash_completed: Literal[True] = True
    rejected_before_client_factory: Literal[True] = True
    credential_lookup_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> DestructiveControl:
        if self.control_id != identity(
            self,
            "control_id",
            "finance_v26_199_online_authorization_destructive_control:",
        ):
            raise ValueError("v26.199 destructive control identity differs")
        return self


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    controls: tuple[DestructiveControl, ...] = Field(min_length=20, max_length=20)
    control_count: Literal[20] = 20
    rejected_count: Literal[20] = 20
    accepted_count: Literal[0] = 0
    credential_lookup_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if len({item.attack_name for item in self.controls}) != 20:
            raise ValueError("v26.199 destructive denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_199_online_authorization_destructive_audit:",
        ):
            raise ValueError("v26.199 destructive audit identity differs")
        return self


class StaticGate(FrozenModel):
    name: str = Field(min_length=1)
    passed: Literal[True] = True
    evidence_ids: tuple[str, ...] = Field(min_length=1)


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=28, max_length=28)
    gate_count: Literal[28] = 28
    passed_count: Literal[28] = 28
    failed_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if len({item.name for item in self.gates}) != 28:
            raise ValueError("v26.199 static Gate denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_199_static_audit:",
        ):
            raise ValueError("v26.199 static audit identity differs")
        return self


class OnlineAuthorizationDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v198_freeze_audit_id: str = Field(min_length=1)
    frozen_condition_binding_id: str = Field(min_length=1)
    successor_integration_binding_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    precredential_admission_audit_id: str = Field(min_length=1)
    scope_exclusion_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    decision: Literal["exact_frozen_192_job_online_execution_authorization_issued_not_consumed"]
    first_failed_gate: None = None
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> OnlineAuthorizationDecision:
        if self.decision_id != identity(
            self,
            "decision_id",
            "finance_v26_199_online_authorization_decision:",
        ):
            raise ValueError("v26.199 decision identity differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    next_stage: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_"
        "exact_192_job_online_execution_only"
    ] = NEXT_STAGE
    exact_192_job_execution_authorized: Literal[True] = True
    provider_calls_authorized_for_exact_manifest_only: Literal[True] = True
    authorization_consumed: Literal[False] = False
    provider_calls_executed: Literal[0] = 0
    source_or_manifest_change_authorized: Literal[False] = False
    qa_integration_authorized: Literal[False] = False
    mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_199_transition:",
        ):
            raise ValueError("v26.199 transition identity differs")
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
    scope: Literal["sealed_evidence", "distribution"]
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ArtifactManifest:
        paths = tuple(item.relative_path for item in self.members)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.199 artifact member set differs")
        if self.file_count != len(self.members) or self.total_byte_count != sum(
            item.byte_count for item in self.members
        ):
            raise ValueError("v26.199 artifact aggregate differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix=f"finance_v26_199_{self.scope}_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("v26.199 artifact Root differs")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            f"finance_v26_199_{self.scope}_artifact_manifest:",
        ):
            raise ValueError("v26.199 artifact Manifest identity differs")
        return self


class OnlineAuthorizationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    external_decision_id: str = Field(min_length=1)
    v198_freeze_audit_id: str = Field(min_length=1)
    frozen_condition_binding_id: str = Field(min_length=1)
    successor_integration_binding_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    admission_id: str = Field(min_length=1)
    precredential_admission_audit_id: str = Field(min_length=1)
    scope_exclusion_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    sealed_manifest_id: str = Field(min_length=1)
    sealed_artifact_root: str = Field(min_length=1)
    decision: Literal["exact_frozen_192_job_online_execution_authorization_issued_not_consumed"]
    v198_formal_file_match_count: Literal[48] = 48
    exact_package_count: Literal[32] = 32
    exact_job_count: Literal[192] = 192
    exact_registered_invocation_count: Literal[792] = 792
    destructive_rejection_count: Literal[20] = 20
    static_gate_pass_count: Literal[28] = 28
    online_authorization_issued: Literal[True] = True
    online_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    development_outcomes: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    qa_change_count: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> OnlineAuthorizationReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_199_terminal_outcome_online_authorization_report:",
        ):
            raise ValueError("v26.199 Report identity differs")
        return self
