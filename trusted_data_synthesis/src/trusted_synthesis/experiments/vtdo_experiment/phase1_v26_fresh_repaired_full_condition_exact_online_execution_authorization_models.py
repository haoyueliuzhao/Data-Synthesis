# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_repaired_full_condition_exact_online_execution_authorization.v1"
CONSUMED_STAGE: Final = (
    "fresh_repaired_full_condition_exact_192_job_online_execution_authorization_only"
)
NEXT_STAGE: Final = "fresh_repaired_full_condition_exact_192_job_online_execution_only"
DECISION: Final = "exact_repaired_192_job_online_execution_authorization_issued_not_consumed"
EXECUTION_SEQUENCE: Final = (
    "validate_exact_authorization_bytes",
    "precredential_guard",
    "consume_authorization_exactly_once",
    "persist_durable_run_start_receipt",
    "credential_lookup",
    "construct_provider_transport",
    "invoke_exact_v26_209_runner_current_state_loop",
    "typed_terminal_dispatch",
    "persist_raw_before_result",
    "reconstruct_trace_and_outcome",
    "persist_checkpoint",
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


class ExternalOnlineAuthorizationDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    review_sha256: Literal["6f620c16c86a10098691156500af98cd014810d63fe2fe4915b67ab850138b82"]
    review_byte_count: Literal[12940] = 12_940
    review_audit_result: Literal["PASSED_AS_SCOPED"] = "PASSED_AS_SCOPED"
    review_mandatory_revision: Literal["NONE"] = "NONE"
    review_observed_blocking_defect: Literal["NONE"] = "NONE"
    review_first_unclosed_gate: Literal["exact_precredential_online_execution_authorization"] = (
        "exact_precredential_online_execution_authorization"
    )
    operator_directive: Literal["参照审计，继续实验"] = "参照审计，继续实验"
    operator_directive_sha256: Literal[
        "dbaf736d9a857237a3c762625b0b5368fb31f6863b3f0b02690314912e25650d"
    ]
    operator_directive_byte_count: Literal[27] = 27
    explicit_operator_authorization_after_review: Literal[True] = True
    only_authorized_stage: Literal[
        "fresh_repaired_full_condition_exact_192_job_online_execution_authorization_only"
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
        ):
            raise ValueError("v26.211 operator directive bytes differ")
        if self.decision_id != identity(
            self,
            "decision_id",
            "finance_v26_211_external_online_authorization_decision:",
        ):
            raise ValueError("v26.211 external decision identity differs")
        return self


class V210AuthorityFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v210_report_id: str = Field(min_length=1)
    v210_decision_id: str = Field(min_length=1)
    v210_gate_id: str = Field(min_length=1)
    v210_transition_id: str = Field(min_length=1)
    v210_artifact_manifest_id: str = Field(min_length=1)
    v210_artifact_root: str = Field(min_length=1)
    v210_source_commit: Literal["56238892be483da4bab0d188dcc1fe69287174bf"]
    v210_source_tree: Literal["b0e329e53318f17b2d1930023c3bd872660bea64"]
    v210_formal_file_count: Literal[15] = 15
    v210_formal_total_byte_count: Literal[1344368] = 1_344_368
    v210_manifest_member_count: Literal[14] = 14
    v210_manifest_member_total_byte_count: Literal[1341853] = 1_341_853
    v210_decision: Literal["v26_209_final_request_continuity_repair_independent_audit_passed"]
    v210_all_gates_passed: Literal[True] = True
    v210_provider_calls: Literal[0] = 0
    v210_credential_lookups: Literal[0] = 0
    v210_empirical_rows: Literal[0] = 0
    historical_artifact_mutation_count: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V210AuthorityFreeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_211_v210_authority_freeze:"):
            raise ValueError("v26.211 v26.210 Freeze identity differs")
        return self


class FrozenExecutionConditionBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    v210_freeze_id: str = Field(min_length=1)
    v209_source_commit: Literal["5809e9782515e55ee797b43730584d5d860aaa5c"]
    v209_source_tree: Literal["b2272bc1766a2d9b8c6562cb0b9f2f47151ad7cf"]
    implementation_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    estimand_contract_id: str = Field(min_length=1)
    typed_failure_control_audit_id: str = Field(min_length=1)
    generation_profile_id: str = Field(min_length=1)
    prompt_contract_id: str = Field(min_length=1)
    prompt_schema_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    model_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    thinking_policy_id: str = Field(min_length=1)
    action_grammar_id: str = Field(min_length=1)
    final_grammar_id: str = Field(min_length=1)
    bounded_generation_policy_id: str = Field(min_length=1)
    generation_resource_contract_id: str = Field(min_length=1)
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
    task_component_candidate_schedule_change_count: Literal[0] = 0
    presentation_runtime_change_count: Literal[0] = 0
    model_thinking_sampling_change_count: Literal[0] = 0
    grammar_policy_resource_change_count: Literal[0] = 0
    correction_validity_denominator_threshold_terminal_change_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> FrozenExecutionConditionBinding:
        if (
            self.exact_package_ids != tuple(sorted(set(self.exact_package_ids)))
            or self.exact_job_ids != tuple(sorted(set(self.exact_job_ids)))
            or canonical_sha256(self.exact_package_ids) != self.exact_package_set_sha256
            or canonical_sha256(self.exact_job_ids) != self.exact_job_set_sha256
        ):
            raise ValueError("v26.211 exact Package/Job set differs")
        if self.binding_id != identity(
            self,
            "binding_id",
            "finance_v26_211_frozen_execution_condition_binding:",
        ):
            raise ValueError("v26.211 frozen condition identity differs")
        return self


class OnlineExecutionCompositionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    condition_binding_id: str = Field(min_length=1)
    exact_v26_209_runner_id: str = Field(min_length=1)
    exact_v26_209_implementation_id: str = Field(min_length=1)
    event_sequence: tuple[str, ...] = EXECUTION_SEQUENCE
    exact_authorization_bytes_required: Literal[True] = True
    precredential_guard_required: Literal[True] = True
    consume_exactly_once_before_credential_lookup: Literal[True] = True
    durable_run_start_receipt_required: Literal[True] = True
    exact_runner_current_state_loop_required: Literal[True] = True
    credentialed_provider_transport_required: Literal[True] = True
    typed_terminal_dispatch_required: Literal[True] = True
    raw_before_result_persistence_required: Literal[True] = True
    trace_outcome_checkpoint_required: Literal[True] = True
    caller_terminal_forbidden: Literal[True] = True
    historical_response_input_forbidden: Literal[True] = True
    reference_choice_vector_input_forbidden: Literal[True] = True
    prebuilt_final_input_forbidden: Literal[True] = True
    one_current_state_prompt_at_a_time: Literal[True] = True
    provider_failure_typed_terminal_required: Literal[True] = True
    transport_failure_typed_terminal_required: Literal[True] = True
    thinking_failure_typed_terminal_required: Literal[True] = True
    usage_failure_typed_terminal_required: Literal[True] = True
    model_failure_typed_terminal_required: Literal[True] = True
    failure_reopens_authorization: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> OnlineExecutionCompositionContract:
        if self.event_sequence != EXECUTION_SEQUENCE:
            raise ValueError("v26.211 online execution sequence differs")
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_repaired_full_condition_online_execution_composition_contract:",
        ):
            raise ValueError("v26.211 composition Contract identity differs")
        return self


class ExactOnlineExecutionAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v210_freeze_id: str = Field(min_length=1)
    condition_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    implementation_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    estimand_contract_id: str = Field(min_length=1)
    terminal_policy_parent_id: str = Field(min_length=1)
    generation_profile_id: str = Field(min_length=1)
    prompt_contract_id: str = Field(min_length=1)
    prompt_schema_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    thinking_policy_id: str = Field(min_length=1)
    action_grammar_id: str = Field(min_length=1)
    final_grammar_id: str = Field(min_length=1)
    bounded_generation_policy_id: str = Field(min_length=1)
    generation_resource_contract_id: str = Field(min_length=1)
    kernel_resource_contract_id: str = Field(min_length=1)
    exact_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    exact_job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_coordinate_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    trace_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome_namespace_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorized_stage: Literal[
        "fresh_repaired_full_condition_exact_192_job_online_execution_only"
    ] = NEXT_STAGE
    exact_package_count: Literal[32] = 32
    exact_job_count: Literal[192] = 192
    exact_registered_coordinate_count: Literal[792] = 792
    maximum_authorization_consumptions: Literal[1] = 1
    online_execution_authorized: Literal[True] = True
    provider_execution_authorized: Literal[True] = True
    exact_192_job_execution_authorized: Literal[True] = True
    consume_before_credential_lookup: Literal[True] = True
    durable_run_start_receipt_required: Literal[True] = True
    authorization_reuse_authorized: Literal[False] = False
    replacement_run_authorized: Literal[False] = False
    failed_job_rerun_authorized: Literal[False] = False
    recovery_run_authorized: Literal[False] = False
    historical_reuse_authorized: Literal[False] = False
    source_manifest_condition_change_authorized: Literal[False] = False
    qa_integration_authorized: Literal[False] = False
    mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    provider_calls_during_authorization: Literal[0] = 0
    credential_lookups_during_authorization: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExactOnlineExecutionAuthorization:
        if (
            self.exact_job_ids != tuple(sorted(set(self.exact_job_ids)))
            or canonical_sha256(self.exact_job_ids) != self.exact_job_set_sha256
        ):
            raise ValueError("v26.211 Authorization Job set differs")
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "fresh_repaired_full_condition_exact_online_execution_authorization:",
        ):
            raise ValueError("v26.211 online Authorization identity differs")
        return self


class OnlineAuthorizationAdmission(FrozenModel):
    admission_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authorized_stage: Literal[
        "fresh_repaired_full_condition_exact_192_job_online_execution_only"
    ] = NEXT_STAGE
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    exact_job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_coordinate_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_execution_requested: Literal[True] = True
    admitted_before_authorization_consumption: Literal[True] = True
    admitted_before_run_start_receipt: Literal[True] = True
    admitted_before_credential_lookup: Literal[True] = True
    admitted_before_transport_and_writer_construction: Literal[True] = True
    credential_lookup_permitted_only_after_durable_consumption: Literal[True] = True
    diagnostic_probe_only: Literal[True] = True
    authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_admission(self) -> OnlineAuthorizationAdmission:
        if self.admission_id != identity(
            self,
            "admission_id",
            "fresh_repaired_full_condition_online_authorization_admission:",
        ):
            raise ValueError("v26.211 online admission identity differs")
        return self


class PrecredentialOnlineAuthorizationGuard:
    """Exact-byte guard for the future one-shot v26.212 execution entry."""

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
        requested_composition_contract_id: str,
        requested_coordinate_set_sha256: str,
        requested_generation_profile_id: str,
        requested_model_config_id: str,
        requested_thinking_policy_id: str,
        requested_action_grammar_id: str,
        requested_final_grammar_id: str,
        requested_policy_id: str,
        requested_generation_resource_contract_id: str,
        requested_kernel_resource_contract_id: str,
        provider_execution_requested: bool,
        replacement_run_requested: bool,
        failed_job_rerun_requested: bool,
        recovery_run_requested: bool,
        historical_reuse_requested: bool,
        qa_integration_requested: bool,
        caller_terminal_provided: bool,
        historical_response_provided: bool,
        reference_choice_vector_provided: bool,
        prebuilt_final_provided: bool,
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
        pairs = (
            (requested_stage, strict.authorized_stage),
            (requested_manifest_id, strict.manifest_id),
            (requested_runner_id, strict.runner_id),
            (requested_execution_contract_id, strict.execution_contract_id),
            (requested_composition_contract_id, strict.composition_contract_id),
            (requested_coordinate_set_sha256, strict.exact_coordinate_set_sha256),
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
            (requested_kernel_resource_contract_id, strict.kernel_resource_contract_id),
        )
        if any(actual != expected for actual, expected in pairs):
            raise ValueError("requested online execution parent differs")
        if requested_job_ids != strict.exact_job_ids:
            raise ValueError("requested online Job set differs")
        if not provider_execution_requested:
            raise ValueError("exact Provider execution request is required")
        forbidden = (
            replacement_run_requested,
            failed_job_rerun_requested,
            recovery_run_requested,
            historical_reuse_requested,
            qa_integration_requested,
            caller_terminal_provided,
            historical_response_provided,
            reference_choice_vector_provided,
            prebuilt_final_provided,
        )
        if any(forbidden):
            raise ValueError("requested execution contains a forbidden expansion or injected input")
        return cast(
            OnlineAuthorizationAdmission,
            make_identity(
                OnlineAuthorizationAdmission,
                {
                    "authorization_id": strict.authorization_id,
                    "manifest_id": strict.manifest_id,
                    "runner_id": strict.runner_id,
                    "composition_contract_id": strict.composition_contract_id,
                    "exact_job_set_sha256": strict.exact_job_set_sha256,
                    "exact_coordinate_set_sha256": strict.exact_coordinate_set_sha256,
                },
                field="admission_id",
                prefix="fresh_repaired_full_condition_online_authorization_admission:",
            ),
        )


class AdmissionControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    admitted: bool
    rejected: bool
    rejection_reason_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    credential_probe_count: int = Field(ge=0, le=1)
    transport_factory_count: int = Field(ge=0, le=1)
    raw_writer_factory_count: int = Field(ge=0, le=1)
    result_writer_factory_count: int = Field(ge=0, le=1)
    outcome_writer_factory_count: int = Field(ge=0, le=1)
    checkpoint_writer_factory_count: int = Field(ge=0, le=1)
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> AdmissionControl:
        counts = (
            self.credential_probe_count,
            self.transport_factory_count,
            self.raw_writer_factory_count,
            self.result_writer_factory_count,
            self.outcome_writer_factory_count,
            self.checkpoint_writer_factory_count,
        )
        if self.admitted == self.rejected:
            raise ValueError("v26.211 admission disposition differs")
        if self.admitted:
            if self.rejection_reason_sha256 is not None or counts != (1, 1, 1, 1, 1, 1):
                raise ValueError("v26.211 legal diagnostic admission differs")
        elif self.rejection_reason_sha256 is None or any(counts):
            raise ValueError("v26.211 invalid admission reached a post-guard probe")
        if self.control_id != identity(
            self, "control_id", "finance_v26_211_precredential_admission_control:"
        ):
            raise ValueError("v26.211 admission control identity differs")
        return self


class PrecredentialAdmissionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    admission_id: str = Field(min_length=1)
    controls: tuple[AdmissionControl, ...] = Field(min_length=20)
    legal_control_count: Literal[1] = 1
    invalid_control_count: int = Field(ge=19)
    invalid_control_post_guard_probe_count: Literal[0] = 0
    guard_precedes_all_post_guard_probes: Literal[True] = True
    authorization_consumed_by_diagnostic_probe: Literal[False] = False
    durable_run_start_receipt_created: Literal[False] = False
    credential_lookups: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PrecredentialAdmissionAudit:
        if (
            sum(item.admitted for item in self.controls) != 1
            or sum(item.rejected for item in self.controls) != self.invalid_control_count
            or len(self.controls) != self.invalid_control_count + 1
            or len({item.control_name for item in self.controls}) != len(self.controls)
        ):
            raise ValueError("v26.211 admission control denominator differs")
        if self.audit_id != identity(
            self, "audit_id", "finance_v26_211_precredential_admission_audit:"
        ):
            raise ValueError("v26.211 admission Audit identity differs")
        return self


class DestructiveControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    mutated_authorization_id: str = Field(min_length=1)
    fully_rehashed: Literal[True] = True
    rejected_by_exact_guard: Literal[True] = True
    post_guard_probe_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> DestructiveControl:
        if self.control_id != identity(
            self, "control_id", "finance_v26_211_authorization_destructive_control:"
        ):
            raise ValueError("v26.211 destructive control identity differs")
        return self


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    controls: tuple[DestructiveControl, ...] = Field(min_length=12)
    attack_count: int = Field(ge=12)
    fully_rehashed_attack_count: int = Field(ge=12)
    rejected_attack_count: int = Field(ge=12)
    accepted_attack_count: Literal[0] = 0
    post_guard_probe_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if (
            len(self.controls) != self.attack_count
            or self.fully_rehashed_attack_count != self.attack_count
            or self.rejected_attack_count != self.attack_count
            or len({item.control_name for item in self.controls}) != self.attack_count
        ):
            raise ValueError("v26.211 destructive denominator differs")
        if self.audit_id != identity(
            self, "audit_id", "finance_v26_211_authorization_destructive_audit:"
        ):
            raise ValueError("v26.211 destructive Audit identity differs")
        return self


class ScopeBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    exact_job_count: Literal[192] = 192
    authorization_issued: Literal[True] = True
    authorization_consumed: Literal[False] = False
    durable_run_start_receipts: Literal[0] = 0
    manifest_job_executions: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    raw_files_written: Literal[0] = 0
    result_files_written: Literal[0] = 0
    trace_rows: Literal[0] = 0
    outcome_rows: Literal[0] = 0
    checkpoint_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    qa_population_reads: Literal[0] = 0
    qa_change_count: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ScopeBoundaryAudit:
        if self.audit_id != identity(self, "audit_id", "finance_v26_211_scope_boundary_audit:"):
            raise ValueError("v26.211 scope boundary identity differs")
        return self


class GateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> GateResult:
        if self.gate_id != identity(self, "gate_id", "finance_v26_211_online_authorization_gate:"):
            raise ValueError("v26.211 Gate identity differs")
        return self


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[GateResult, ...] = Field(min_length=20)
    passed_gate_count: int = Field(ge=20)
    failed_gate_count: Literal[0] = 0
    all_gates_passed: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if self.passed_gate_count != len(self.gates) or len(
            {item.gate_name for item in self.gates}
        ) != len(self.gates):
            raise ValueError("v26.211 static Gate denominator differs")
        if self.audit_id != identity(
            self, "audit_id", "finance_v26_211_online_authorization_static_audit:"
        ):
            raise ValueError("v26.211 static Audit identity differs")
        return self


class OnlineAuthorizationDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v210_freeze_id: str = Field(min_length=1)
    condition_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    admission_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    scope_boundary_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    decision: Literal[
        "exact_repaired_192_job_online_execution_authorization_issued_not_consumed"
    ] = DECISION
    online_authorization_issued: Literal[True] = True
    online_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> OnlineAuthorizationDecision:
        if self.decision_id != identity(
            self, "decision_id", "finance_v26_211_online_authorization_decision:"
        ):
            raise ValueError("v26.211 Decision identity differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    status: Literal["AUTHORIZED_NOT_CONSUMED"] = "AUTHORIZED_NOT_CONSUMED"
    next_stage: Literal["fresh_repaired_full_condition_exact_192_job_online_execution_only"] = (
        NEXT_STAGE
    )
    exact_authorization_required: Literal[True] = True
    consume_exactly_once_before_credentials: Literal[True] = True
    replacement_rerun_recovery_forbidden: Literal[True] = True
    postrun_independent_audit_required: Literal[True] = True
    source_manifest_condition_change_authorized: Literal[False] = False
    qa_mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    provider_calls_in_this_stage: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.transition_id != identity(self, "transition_id", "finance_v26_211_transition:"):
            raise ValueError("v26.211 Transition identity differs")
        return self


class SourceIdentity(FrozenModel):
    source_identity_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    implementation_files: tuple[str, ...] = Field(min_length=3)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_source(self) -> SourceIdentity:
        if self.implementation_files != tuple(sorted(set(self.implementation_files))):
            raise ValueError("v26.211 implementation file set differs")
        if self.source_identity_id != identity(
            self, "source_identity_id", "finance_v26_211_source_identity:"
        ):
            raise ValueError("v26.211 source identity differs")
        return self


class OnlineAuthorizationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v210_freeze_id: str = Field(min_length=1)
    condition_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    admission_id: str = Field(min_length=1)
    admission_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    scope_boundary_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    decision: Literal[
        "exact_repaired_192_job_online_execution_authorization_issued_not_consumed"
    ] = DECISION
    exact_package_count: Literal[32] = 32
    exact_job_count: Literal[192] = 192
    exact_coordinate_count: Literal[792] = 792
    authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> OnlineAuthorizationReport:
        if self.report_id != identity(
            self, "report_id", "finance_v26_211_online_authorization_report:"
        ):
            raise ValueError("v26.211 report identity differs")
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
            raise ValueError("v26.211 artifact Manifest geometry differs")
        expected_root = canonical_hash(
            tuple(
                {
                    "relative_path": item.relative_path,
                    "sha256": item.sha256,
                    "byte_count": item.byte_count,
                }
                for item in self.members
            ),
            prefix="finance_v26_211_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("v26.211 Artifact Root differs")
        if self.manifest_id != identity(self, "manifest_id", "finance_v26_211_artifact_manifest:"):
            raise ValueError("v26.211 Artifact Manifest identity differs")
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
        tuple(
            {
                "relative_path": item.relative_path,
                "sha256": item.sha256,
                "byte_count": item.byte_count,
            }
            for item in members
        ),
        prefix="finance_v26_211_artifact_root:",
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
            prefix="finance_v26_211_artifact_manifest:",
        ),
    )
