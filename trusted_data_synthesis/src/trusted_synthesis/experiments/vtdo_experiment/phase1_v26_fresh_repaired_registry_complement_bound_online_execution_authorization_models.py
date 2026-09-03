# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_repaired_registry_complement_bound_online_execution_authorization.v1"
CONSUMED_STAGE: Final = (
    "fresh_repaired_upstream_terminal_domain_exact_registry_complement_bound_"
    "online_execution_authorization_only"
)
NEXT_STAGE: Final = (
    "fresh_repaired_upstream_terminal_domain_exact_registry_complement_bound_"
    "exact_192_job_online_execution_only"
)
DECISION: Final = (
    "fresh_repaired_registry_complement_bound_exact_192_job_online_execution_"
    "authorization_issued_not_consumed"
)
OLD_V211_AUTHORIZATION_ID: Final = (
    "fresh_repaired_full_condition_exact_online_execution_authorization:"
    "aa52ba5fffbdb7236953d3a20dbf29ba739ce7e385123051ededc21454499bbe"
)
REGISTRY_ID: Final = (
    "fresh_kernel_terminal_registry:"
    "a9d3089011f34b114b4b8264c09eb6b4c5875dd6978de0a2c3fe316577203152"
)
EVENT_SEQUENCE: Final = (
    "validate_exact_fresh_authorization_bytes",
    "precredential_parent_and_scope_guard",
    "consume_fresh_authorization_exactly_once",
    "persist_durable_consumption_receipt",
    "persist_durable_run_start_receipt",
    "credential_lookup",
    "construct_provider_transport_and_writers",
    "invoke_exact_v26_209_current_state_runner",
    "derive_main_observation_terminal_or_v26_218_source_bound_failure_terminal",
    "admit_exact_v195_registry_policy",
    "persist_raw_before_result",
    "reconstruct_trace_outcome_and_checkpoint",
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


class ExternalOnlineAuthorizationDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    review_sha256: Literal["8a8ac1155fee931a4da4ae6c5ecbeab57fafdd4132d3a0626e42b471ba8fe459"]
    review_byte_count: Literal[13007] = 13_007
    audit_result: Literal["PASSED_AS_SCOPED"] = "PASSED_AS_SCOPED"
    blocking_defect: Literal["NONE_FOUND"] = "NONE_FOUND"
    mandatory_revision: Literal["NONE"] = "NONE"
    scope_limitation: Literal["PROCESS-ISOLATED / LOCAL-DETERMINISTIC ONLY"] = (
        "PROCESS-ISOLATED / LOCAL-DETERMINISTIC ONLY"
    )
    overall_gate: Literal["PASS"] = "PASS"
    reviewed_online_execution_authorized: Literal[False] = False
    operator_directive: Literal["参照审计继续实验"] = "参照审计继续实验"
    operator_directive_sha256: Literal[
        "b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb"
    ]
    operator_directive_byte_count: Literal[24] = 24
    only_authorized_stage: Literal[
        "fresh_repaired_upstream_terminal_domain_exact_registry_complement_bound_"
        "online_execution_authorization_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized_during_decision: Literal[0] = 0
    credential_lookups_authorized_during_decision: Literal[0] = 0
    online_execution_during_decision_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> ExternalOnlineAuthorizationDecision:
        directive = self.operator_directive.encode("utf-8")
        if (
            len(directive) != self.operator_directive_byte_count
            or hashlib.sha256(directive).hexdigest() != self.operator_directive_sha256
            or self.decision_id
            != identity(
                self,
                "decision_id",
                "finance_v26_220_external_online_authorization_decision:",
            )
        ):
            raise ValueError("v26.220 external online authorization decision differs")
        return self


class V219IndependentAuditFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v219_source_commit: Literal["40a7f6aa6fe5dac3a0b2f0865418bc384d4e6252"]
    v219_source_tree: Literal["3cc72c2d7721d4212dc68787ccf19c29e8f36c19"]
    v219_formal_file_count: Literal[17] = 17
    v219_formal_total_byte_count: Literal[46670] = 46_670
    v219_manifest_member_count: Literal[16] = 16
    v219_manifest_member_byte_count: Literal[43862] = 43_862
    v219_artifact_manifest_id: str = Field(min_length=1)
    v219_artifact_root: str = Field(min_length=1)
    v219_report_id: str = Field(min_length=1)
    v219_gate_evaluation_id: str = Field(min_length=1)
    v219_decision_id: str = Field(min_length=1)
    v219_transition_id: str = Field(min_length=1)
    v219_component_audit_ids: tuple[str, ...] = Field(min_length=6, max_length=6)
    v219_decision: Literal[
        "v26_218_upstream_terminal_domain_exact_registry_complement_binding_"
        "preflight_independent_audit_passed"
    ]
    v219_all_seven_gates_passed: Literal[True] = True
    v219_mandatory_revision: Literal["NONE"] = "NONE"
    v219_process_isolated_adjacent_pass_count: Literal[89] = 89
    v219_provider_calls: Literal[0] = 0
    v219_current_v211_authorization_consumed: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V219IndependentAuditFreeze:
        if self.freeze_id != identity(
            self, "freeze_id", "finance_v26_220_v219_independent_audit_freeze:"
        ):
            raise ValueError("v26.220 v26.219 Freeze differs")
        return self


class V218RepairedParentSetBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    v219_freeze_id: str = Field(min_length=1)
    v218_source_commit: Literal["6171fcc27a4a88693cb9daa1485b0d658b11a5a1"]
    v218_source_tree: Literal["1de85c4ee2f69a360bc7b7c13704186042648064"]
    v218_artifact_manifest_id: str = Field(min_length=1)
    v218_artifact_root: str = Field(min_length=1)
    v218_report_id: str = Field(min_length=1)
    v218_gate_id: str = Field(min_length=1)
    v218_decision_id: str = Field(min_length=1)
    v218_transition_id: str = Field(min_length=1)
    exact_v195_registry_id: Literal[
        "fresh_kernel_terminal_registry:"
        "a9d3089011f34b114b4b8264c09eb6b4c5875dd6978de0a2c3fe316577203152"
    ] = REGISTRY_ID
    complement_binding_id: str = Field(min_length=1)
    v218_composition_contract_id: str = Field(min_length=1)
    exact_parent_ids: tuple[str, ...] = Field(min_length=19)
    exact_parent_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_parent_count: int = Field(ge=19)
    registry_reachable_count: Literal[16] = 16
    admitted_terminal_count: Literal[1] = 1
    forbidden_terminal_count: Literal[15] = 15
    admitted_event_terminal_policy_items: tuple[tuple[str, str, str], ...] = Field(
        min_length=1, max_length=1
    )
    forbidden_terminal_kinds: tuple[str, ...] = Field(min_length=15, max_length=15)
    exact_partition_closed: Literal[True] = True
    old_misspelling_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> V218RepairedParentSetBinding:
        if (
            self.exact_parent_ids != tuple(sorted(set(self.exact_parent_ids)))
            or len(self.exact_parent_ids) != self.exact_parent_count
            or canonical_sha256(self.exact_parent_ids) != self.exact_parent_set_sha256
            or self.admitted_event_terminal_policy_items[0][1] != "instrument_failure"
            or "provider_failure_no_payload" not in self.forbidden_terminal_kinds
            or "resource_budget_exhausted" not in self.forbidden_terminal_kinds
            or "provider_no_payload_failure" in self.forbidden_terminal_kinds
            or "resource_failure" in self.forbidden_terminal_kinds
            or self.binding_id
            != identity(
                self,
                "binding_id",
                "fresh_repaired_v218_complete_parent_set_binding:",
            )
        ):
            raise ValueError("v26.220 v26.218 repaired parent set differs")
        return self


class ExactExecutionConditionBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    v219_freeze_id: str = Field(min_length=1)
    v209_source_commit: Literal["5809e9782515e55ee797b43730584d5d860aaa5c"]
    v209_source_tree: Literal["b2272bc1766a2d9b8c6562cb0b9f2f47151ad7cf"]
    v209_implementation_id: str = Field(min_length=1)
    v209_package_catalog_id: str = Field(min_length=1)
    v209_manifest_id: str = Field(min_length=1)
    v209_runner_id: str = Field(min_length=1)
    v209_execution_contract_id: str = Field(min_length=1)
    v209_invocation_census_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    kernel_resource_contract_id: str = Field(min_length=1)
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
    exact_replica_count: Literal[6] = 6
    exact_job_count: Literal[192] = 192
    exact_registered_coordinate_count: Literal[792] = 792
    first_action_count: Literal[192] = 192
    subsequent_action_count: Literal[288] = 288
    correction_side_branch_count: Literal[120] = 120
    final_count: Literal[192] = 192
    maximum_prompt_utf8_bytes: Literal[60000] = 60_000
    maximum_primary_requests: Literal[21] = 21
    maximum_provider_calls: Literal[23] = 23
    maximum_transport_invocations: Literal[24] = 24
    maximum_rollout_tokens: Literal[1120000] = 1_120_000
    old_v211_authorization_id: Literal[
        "fresh_repaired_full_condition_exact_online_execution_authorization:"
        "aa52ba5fffbdb7236953d3a20dbf29ba739ce7e385123051ededc21454499bbe"
    ] = OLD_V211_AUTHORIZATION_ID
    old_v211_authorization_is_authority: Literal[False] = False
    source_condition_change_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ExactExecutionConditionBinding:
        if (
            self.exact_package_ids != tuple(sorted(set(self.exact_package_ids)))
            or self.exact_job_ids != tuple(sorted(set(self.exact_job_ids)))
            or canonical_sha256(self.exact_package_ids) != self.exact_package_set_sha256
            or canonical_sha256(self.exact_job_ids) != self.exact_job_set_sha256
            or self.binding_id
            != identity(
                self,
                "binding_id",
                "fresh_repaired_registry_complement_bound_execution_condition:",
            )
        ):
            raise ValueError("v26.220 exact execution condition differs")
        return self


class OnlineExecutionCompositionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    v219_freeze_id: str = Field(min_length=1)
    v218_parent_set_binding_id: str = Field(min_length=1)
    condition_binding_id: str = Field(min_length=1)
    exact_v213_main_consumer_binding_id: str = Field(min_length=1)
    exact_v213_main_dispatcher_binding_id: str = Field(min_length=1)
    exact_v213_main_persistence_binding_id: str = Field(min_length=1)
    exact_v213_main_composition_contract_id: str = Field(min_length=1)
    exact_v218_failure_complement_binding_id: str = Field(min_length=1)
    exact_v218_failure_composition_contract_id: str = Field(min_length=1)
    exact_v218_failure_source_contract_id: str = Field(min_length=1)
    event_sequence: tuple[str, ...] = EVENT_SEQUENCE
    main_observation_terminal_kinds: tuple[str, ...] = Field(min_length=8, max_length=8)
    source_bound_failure_terminal_kinds: tuple[str, ...] = Field(min_length=2, max_length=2)
    caller_terminal_forbidden: Literal[True] = True
    old_v211_authorization_forbidden: Literal[True] = True
    unbound_terminal_source_fails_closed: Literal[True] = True
    exact_authorization_bytes_required: Literal[True] = True
    consumption_and_run_start_before_credentials: Literal[True] = True
    raw_before_result_required: Literal[True] = True
    complete_trace_outcome_checkpoint_required: Literal[True] = True
    historical_response_forbidden: Literal[True] = True
    reference_choice_vector_forbidden: Literal[True] = True
    prebuilt_final_forbidden: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> OnlineExecutionCompositionContract:
        if (
            self.event_sequence != EVENT_SEQUENCE
            or self.main_observation_terminal_kinds
            != tuple(sorted(set(self.main_observation_terminal_kinds)))
            or self.source_bound_failure_terminal_kinds
            != ("instrument_failure", "privacy_rejection")
            or self.contract_id
            != identity(
                self,
                "contract_id",
                "fresh_repaired_registry_complement_bound_online_execution_composition_contract:",
            )
        ):
            raise ValueError("v26.220 online execution composition differs")
        return self


class ExactOnlineExecutionAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v219_freeze_id: str = Field(min_length=1)
    v218_parent_set_binding_id: str = Field(min_length=1)
    condition_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    exact_v218_parent_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    v209_manifest_id: str = Field(min_length=1)
    v209_runner_id: str = Field(min_length=1)
    v209_execution_contract_id: str = Field(min_length=1)
    exact_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    exact_job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_coordinate_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    trace_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorized_stage: Literal[
        "fresh_repaired_upstream_terminal_domain_exact_registry_complement_bound_"
        "exact_192_job_online_execution_only"
    ] = NEXT_STAGE
    exact_job_count: Literal[192] = 192
    exact_registered_coordinate_count: Literal[792] = 792
    maximum_authorization_consumptions: Literal[1] = 1
    authorization_issued: Literal[True] = True
    authorization_consumed: Literal[False] = False
    provider_execution_authorized_in_successor: Literal[True] = True
    provider_execution_during_authorization: Literal[False] = False
    old_v211_authorization_accepted: Literal[False] = False
    replacement_run_authorized: Literal[False] = False
    failed_job_rerun_authorized: Literal[False] = False
    recovery_run_authorized: Literal[False] = False
    condition_change_authorized: Literal[False] = False
    qa_mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    postrun_independent_audit_required: Literal[True] = True
    provider_calls_during_authorization: Literal[0] = 0
    credential_lookups_during_authorization: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExactOnlineExecutionAuthorization:
        if (
            self.exact_job_ids != tuple(sorted(set(self.exact_job_ids)))
            or canonical_sha256(self.exact_job_ids) != self.exact_job_set_sha256
            or self.authorization_id
            != identity(
                self,
                "authorization_id",
                "fresh_repaired_registry_complement_bound_exact_online_execution_authorization:",
            )
        ):
            raise ValueError("v26.220 exact online execution Authorization differs")
        return self


class OnlineAuthorizationAdmission(FrozenModel):
    admission_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authorized_stage: str = Field(min_length=1)
    v218_parent_set_binding_id: str = Field(min_length=1)
    condition_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    exact_job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    diagnostic_nonconsuming_probe: Literal[True] = True
    authorization_consumed: Literal[False] = False
    post_guard_probe_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_admission(self) -> OnlineAuthorizationAdmission:
        if self.admission_id != identity(
            self,
            "admission_id",
            "fresh_repaired_registry_complement_bound_online_authorization_admission:",
        ):
            raise ValueError("v26.220 online authorization admission differs")
        return self


class PrecredentialAuthorizationGuard:
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
            raise ValueError("expected v26.220 authorization bytes differ")
        self._expected = strict
        self._expected_bytes = expected_authorization_bytes

    def admit(
        self,
        *,
        authorization: object | None,
        authorization_bytes: bytes | None,
        requested_stage: str,
        requested_v218_parent_set_binding_id: str,
        requested_condition_binding_id: str,
        requested_composition_contract_id: str,
        requested_manifest_id: str,
        requested_runner_id: str,
        requested_execution_contract_id: str,
        requested_job_ids: tuple[str, ...],
        requested_coordinate_set_sha256: str,
        provider_execution_requested: bool,
        old_v211_authorization_presented: bool = False,
        replacement_run_requested: bool = False,
        failed_job_rerun_requested: bool = False,
        recovery_run_requested: bool = False,
        condition_change_requested: bool = False,
        qa_integration_requested: bool = False,
        caller_terminal_provided: bool = False,
        historical_response_provided: bool = False,
        reference_choice_vector_provided: bool = False,
        prebuilt_final_provided: bool = False,
    ) -> OnlineAuthorizationAdmission:
        if type(authorization) is not ExactOnlineExecutionAuthorization:
            raise ValueError("fresh online authorization parent type differs")
        assert isinstance(authorization, ExactOnlineExecutionAuthorization)
        strict = ExactOnlineExecutionAuthorization.model_validate(
            authorization.model_dump(mode="python", warnings=False)
        )
        if (
            authorization_bytes != self._expected_bytes
            or strict.authorization_id != self._expected.authorization_id
        ):
            raise ValueError("fresh online authorization bytes or identity differ")
        pairs = (
            (requested_stage, strict.authorized_stage),
            (requested_v218_parent_set_binding_id, strict.v218_parent_set_binding_id),
            (requested_condition_binding_id, strict.condition_binding_id),
            (requested_composition_contract_id, strict.composition_contract_id),
            (requested_manifest_id, strict.v209_manifest_id),
            (requested_runner_id, strict.v209_runner_id),
            (requested_execution_contract_id, strict.v209_execution_contract_id),
            (requested_coordinate_set_sha256, strict.exact_coordinate_set_sha256),
        )
        if any(actual != expected for actual, expected in pairs):
            raise ValueError("requested v26.220 execution parent differs")
        if requested_job_ids != strict.exact_job_ids:
            raise ValueError("requested v26.220 Job set differs")
        if not provider_execution_requested:
            raise ValueError("exact Provider execution request is required")
        if any(
            (
                old_v211_authorization_presented,
                replacement_run_requested,
                failed_job_rerun_requested,
                recovery_run_requested,
                condition_change_requested,
                qa_integration_requested,
                caller_terminal_provided,
                historical_response_provided,
                reference_choice_vector_provided,
                prebuilt_final_provided,
            )
        ):
            raise ValueError("requested v26.220 execution contains a forbidden expansion")
        return cast(
            OnlineAuthorizationAdmission,
            make_identity(
                OnlineAuthorizationAdmission,
                {
                    "authorization_id": strict.authorization_id,
                    "authorized_stage": strict.authorized_stage,
                    "v218_parent_set_binding_id": strict.v218_parent_set_binding_id,
                    "condition_binding_id": strict.condition_binding_id,
                    "composition_contract_id": strict.composition_contract_id,
                    "exact_job_set_sha256": strict.exact_job_set_sha256,
                },
                field="admission_id",
                prefix="fresh_repaired_registry_complement_bound_online_authorization_admission:",
            ),
        )


class AdmissionControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    admitted: bool
    rejected: bool
    rejection_reason_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    post_guard_probe_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> AdmissionControl:
        if (
            self.admitted == self.rejected
            or (self.admitted and self.rejection_reason_sha256 is not None)
            or (self.rejected and self.rejection_reason_sha256 is None)
            or self.control_id
            != identity(
                self,
                "control_id",
                "finance_v26_220_precredential_admission_control:",
            )
        ):
            raise ValueError("v26.220 admission control differs")
        return self


class PrecredentialAdmissionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    admission_id: str = Field(min_length=1)
    controls: tuple[AdmissionControl, ...] = Field(min_length=16)
    legal_control_count: Literal[1] = 1
    invalid_control_count: int = Field(ge=15)
    invalid_post_guard_probe_count: Literal[0] = 0
    old_v211_authorization_rejected: Literal[True] = True
    authorization_consumed_by_probe: Literal[False] = False
    run_start_receipts: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PrecredentialAdmissionAudit:
        if (
            len(self.controls) != self.invalid_control_count + 1
            or sum(item.admitted for item in self.controls) != 1
            or sum(item.rejected for item in self.controls) != self.invalid_control_count
            or len({item.control_name for item in self.controls}) != len(self.controls)
            or self.audit_id
            != identity(
                self,
                "audit_id",
                "finance_v26_220_precredential_admission_audit:",
            )
        ):
            raise ValueError("v26.220 precredential admission Audit differs")
        return self


class ParentAttack(FrozenModel):
    attack_id: str = Field(min_length=1)
    attack_name: str = Field(min_length=1)
    mutated_authorization_id: str = Field(min_length=1)
    mutated_composition_id: str = Field(min_length=1)
    fully_rehashed_object_count: Literal[2] = 2
    rejected_by_exact_guard: Literal[True] = True
    rejection_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    post_guard_probe_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_attack(self) -> ParentAttack:
        if self.attack_id != identity(
            self, "attack_id", "finance_v26_220_fully_rehashed_parent_attack:"
        ):
            raise ValueError("v26.220 parent attack differs")
        return self


class ParentAttackAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    attacks: tuple[ParentAttack, ...] = Field(min_length=12)
    attack_count: int = Field(ge=12)
    fully_rehashed_object_count: int = Field(ge=24)
    rejected_attack_count: int = Field(ge=12)
    accepted_attack_count: Literal[0] = 0
    post_guard_probe_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ParentAttackAudit:
        if (
            len(self.attacks) != self.attack_count
            or self.fully_rehashed_object_count != 2 * self.attack_count
            or self.rejected_attack_count != self.attack_count
            or len({item.attack_name for item in self.attacks}) != self.attack_count
            or self.audit_id != identity(self, "audit_id", "finance_v26_220_parent_attack_audit:")
        ):
            raise ValueError("v26.220 parent attack Audit differs")
        return self


class ScopeBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    fresh_online_authorizations_issued: Literal[1] = 1
    fresh_online_authorizations_consumed: Literal[0] = 0
    old_v211_authorization_consumed: Literal[False] = False
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
        if self.audit_id != identity(self, "audit_id", "finance_v26_220_scope_boundary_audit:"):
            raise ValueError("v26.220 scope boundary Audit differs")
        return self


class GateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> GateResult:
        if self.gate_id != identity(self, "gate_id", "finance_v26_220_gate:"):
            raise ValueError("v26.220 Gate differs")
        return self


class GateEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    gates: tuple[GateResult, ...] = Field(min_length=8, max_length=8)
    passed_count: Literal[8] = 8
    failed_count: Literal[0] = 0
    all_gates_passed: Literal[True] = True
    authorization_issued: Literal[True] = True
    authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> GateEvaluation:
        if len({item.gate_name for item in self.gates}) != 8 or self.evaluation_id != identity(
            self, "evaluation_id", "finance_v26_220_gate_evaluation:"
        ):
            raise ValueError("v26.220 Gate Evaluation differs")
        return self


class OnlineAuthorizationDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v219_freeze_id: str = Field(min_length=1)
    v218_parent_set_binding_id: str = Field(min_length=1)
    condition_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    admission_audit_id: str = Field(min_length=1)
    parent_attack_audit_id: str = Field(min_length=1)
    scope_boundary_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_registry_complement_bound_exact_192_job_online_execution_"
        "authorization_issued_not_consumed"
    ] = DECISION
    online_authorization_issued: Literal[True] = True
    online_authorization_consumed: Literal[False] = False
    old_v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> OnlineAuthorizationDecision:
        if self.decision_id != identity(
            self, "decision_id", "finance_v26_220_online_authorization_decision:"
        ):
            raise ValueError("v26.220 online authorization Decision differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    status: Literal["AUTHORIZED_NOT_CONSUMED"] = "AUTHORIZED_NOT_CONSUMED"
    next_stage: Literal[
        "fresh_repaired_upstream_terminal_domain_exact_registry_complement_bound_"
        "exact_192_job_online_execution_only"
    ] = NEXT_STAGE
    exact_fresh_authorization_required: Literal[True] = True
    consume_exactly_once_before_credentials: Literal[True] = True
    old_v211_authorization_forbidden: Literal[True] = True
    replacement_rerun_recovery_forbidden: Literal[True] = True
    postrun_independent_audit_required: Literal[True] = True
    provider_execution_authorized_only_in_successor: Literal[True] = True
    provider_execution_performed_here: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.transition_id != identity(self, "transition_id", "finance_v26_220_transition:"):
            raise ValueError("v26.220 Transition differs")
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
            self, "source_identity_id", "finance_v26_220_source_identity:"
        ):
            raise ValueError("v26.220 source identity differs")
        return self


class ImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v219_freeze_id: str = Field(min_length=1)
    files: tuple[SourceFile, ...] = Field(min_length=3, max_length=3)
    guard_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    build_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
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
            "fresh_repaired_registry_complement_bound_online_authorization_implementation_binding:",
        ):
            raise ValueError("v26.220 implementation Binding differs")
        return self


class Report(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v219_freeze_id: str = Field(min_length=1)
    v218_parent_set_binding_id: str = Field(min_length=1)
    condition_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    admission_audit_id: str = Field(min_length=1)
    parent_attack_audit_id: str = Field(min_length=1)
    scope_boundary_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_registry_complement_bound_exact_192_job_online_execution_"
        "authorization_issued_not_consumed"
    ] = DECISION
    authorization_issued: Literal[True] = True
    authorization_consumed: Literal[False] = False
    old_v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> Report:
        if self.report_id != identity(
            self, "report_id", "finance_v26_220_online_authorization_report:"
        ):
            raise ValueError("v26.220 Report differs")
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
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_220_artifact_root:",
        )
        if (
            self.file_count != len(self.members)
            or self.total_byte_count != sum(item.byte_count for item in self.members)
            or tuple(item.relative_path for item in self.members)
            != tuple(sorted({item.relative_path for item in self.members}))
            or self.artifact_root != expected_root
            or self.manifest_id
            != identity(self, "manifest_id", "finance_v26_220_artifact_manifest:")
        ):
            raise ValueError("v26.220 Artifact Manifest differs")
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
        prefix="finance_v26_220_artifact_root:",
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
            prefix="finance_v26_220_artifact_manifest:",
        ),
    )
