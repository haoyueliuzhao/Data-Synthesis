# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_exact_v209_unbound_provider_failure_recovery_online_authorization.v1"
RUN_ID: Final = "finance_v26_231_fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_v1_20260904"
CONSUMED_STAGE: Final = "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_only"
NEXT_STAGE: Final = (
    "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_only"
)
DECISION_VALUE: Final = "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_issued_not_consumed"


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


class ExternalDecision(Identified):
    decision_id: str
    review_sha256: Literal["a7a93482dbd8a7944f105b670ca9eb35a042fcc87f790940ca4c8910c3a6b5e4"]
    review_byte_count: Literal[12817] = 12_817
    audit_decision: Literal["PASS_AS_SCOPED"] = "PASS_AS_SCOPED"
    blocking_defect: Literal["NONE_FOUND"] = "NONE_FOUND"
    mandatory_revision: Literal["NONE"] = "NONE"
    next_unclosed_gate: Literal["RECOVERY_ONLINE_AUTHORIZATION"] = "RECOVERY_ONLINE_AUTHORIZATION"
    recovery_population_authority: Literal["CLOSED"] = "CLOSED"
    recovery_execution_result: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    v26_226_empirical_set: Literal["STILL_INCOMPLETE"] = "STILL_INCOMPLETE"
    operator_directive: Literal["参照审计报告继续实验"] = "参照审计报告继续实验"
    operator_directive_sha256: Literal[
        "2310d8996483f5f0d431940d98cbfc56a53e23aca61b59306de2d9bf61b9ec1a"
    ]
    operator_directive_byte_count: Literal[30] = 30
    only_authorized_stage: Literal[
        "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized_during_stage: Literal[0] = 0
    recovery_executions_authorized_during_stage: Literal[0] = 0
    credential_lookups_authorized_during_stage: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_231_external_online_authorization_decision:"

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


class V230Freeze(Identified):
    freeze_id: str
    external_decision_id: str
    source_commit: Literal["bb056e0def4a7ceec4f07797b5e559ff7067f848"]
    source_tree: Literal["413c52ab220393d6ff63855ce9735b248915c6b6"]
    formal_file_count: Literal[20] = 20
    formal_total_byte_count: Literal[308132] = 308_132
    manifest_member_count: Literal[19] = 19
    manifest_member_byte_count: Literal[304982] = 304_982
    manifest_id: Literal[
        "finance_v26_230_artifact_manifest:8a48e037f821085a2a90934b2cac68dd739c0eefd110291f8cf03a910fd8cdf5"
    ]
    artifact_root: Literal[
        "finance_v26_230_artifact_root:3144ae72addc83cfcf2924a3ff5a70032a5e7aec07b48e2a897f6f30ad76cd64"
    ]
    report_id: Literal[
        "finance_v26_230_independent_audit_report:1af2d30e05746d1058ed05c982f309988f44a9c41f518146e4a186caa931d7fc"
    ]
    gate_id: Literal[
        "finance_v26_230_gate_evaluation:bc8db7576be5ea67c0ceadda83c1210282e0ca2e467131a7d0397413501592a4"
    ]
    decision_id: Literal[
        "finance_v26_230_independent_audit_decision:eafa69e8a27b05955b115ea93f895b6c9d27d7c509a4946843ab93828cf252c7"
    ]
    transition_id: Literal[
        "finance_v26_230_transition:79aab330f2ef4d17481262a7663d56d6ee2c00513660fd3c7a60f5c390c44fdb"
    ]
    component_audit_ids: tuple[str, ...] = Field(min_length=10, max_length=10)
    passed_gate_count: Literal[8] = 8
    failed_gate_count: Literal[0] = 0
    exact_source_count: Literal[33] = 33
    successful_prefix_calls: Literal[55] = 55
    captured_failed_requests: Literal[33] = 33
    reasoning_budget_count: Literal[31] = 31
    json_decode_count: Literal[2] = 2
    online_authorizations: Literal[0] = 0
    recovery_executions: Literal[0] = 0
    provider_calls: Literal[0] = 0
    prospective_next_stage: Literal[
        "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_only"
    ] = CONSUMED_STAGE
    next_stage_authorized: Literal[False] = False
    actual_byte_matches: Literal[20] = 20
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_231_v230_independent_audit_freeze:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if self.component_audit_ids != tuple(sorted(set(self.component_audit_ids))):
            raise ValueError("v26.230 component Audit set differs")
        self.check_id("freeze_id")
        return self


FailurePhase = Literal["first_action", "subsequent_action", "final"]


class RecoveryBudgetRow(FrozenModel):
    job_ordinal: int = Field(ge=0, le=191)
    recovery_job_id: str
    recovery_candidate_id: str
    historical_job_id: str
    source_row_id: str
    failed_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    failed_request_byte_count: int = Field(gt=0)
    failed_phase: FailurePhase
    successful_prefix_call_count: int = Field(ge=0, le=3)
    successful_prefix_usage_tokens: int = Field(ge=0)
    remaining_primary_request_limit: int = Field(ge=18, le=21)
    remaining_provider_call_limit: int = Field(ge=20, le=23)
    remaining_transport_invocation_limit: int = Field(ge=21, le=24)
    remaining_rollout_token_limit: int = Field(gt=0, le=1_120_000)
    exact_failed_request_max_tokens: Literal[16384] = 16_384
    failed_request_reissue_count: Literal[1] = 1
    successful_prefix_provider_reissue_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            self.remaining_primary_request_limit != 21 - self.successful_prefix_call_count
            or self.remaining_provider_call_limit != 23 - self.successful_prefix_call_count
            or self.remaining_transport_invocation_limit != 24 - self.successful_prefix_call_count
            or self.remaining_rollout_token_limit != 1_120_000 - self.successful_prefix_usage_tokens
        ):
            raise ValueError("Recovery residual budget differs")
        return self


class RecoveryParentBinding(Identified):
    binding_id: str
    v230_freeze_id: str
    v229_manifest_id: Literal[
        "finance_v26_229_artifact_manifest:968a9b5adee2a0c5011c753ec777de8bc91a768745f09943ea676cd2e9e2f863"
    ]
    v229_artifact_root: Literal[
        "finance_v26_229_artifact_root:0e99bbf37aff7faeb3f5adef51eeccd086d3cc760c09de6ecf236de914b6abe1"
    ]
    v229_report_id: Literal[
        "finance_v26_229_preflight_report:bec3dbbf526d38dd566c57cb10c14235d21c21636b4c81fd8f1dd2a088d83ecc"
    ]
    v229_decision_id: Literal[
        "finance_v26_229_decision:a81ff8a964d8c58bd7b444c71fc4c910c02938d0f0ce7d07f7c85bc297650e23"
    ]
    v229_transition_id: Literal[
        "finance_v26_229_transition:2e2160e5568d140141aad37da5133d8904395de5c4ff284666500cba289eae80"
    ]
    recovery_contract_id: Literal[
        "finance_v26_229_recovery_contract:5313f77c0284420e5ee8a23d34f418a52b517ffb8fcf24d1efb49608dda81202"
    ]
    recovery_population_id: Literal[
        "finance_v26_229_recovery_population:f7b9e21a46abd8efbace595d10ef4d479973eb5631542ee80f5a191e48979821"
    ]
    v230_recovery_population_audit_id: Literal[
        "finance_v26_230_independent_recovery_population_audit:6ba5d20162af1eb6fb7f91367d94e963d7b14c3af49f8e948383a7f42919c9cb"
    ]
    v230_replay_audit_id: Literal[
        "finance_v26_230_independent_request_replay_audit:9289bd1525f5391f8666031924afc8c1692fe4e528b08afdeac39114ef7428cd"
    ]
    recovery_candidate_ids: tuple[str, ...] = Field(min_length=33, max_length=33)
    recovery_job_ids: tuple[str, ...] = Field(min_length=33, max_length=33)
    source_row_ids: tuple[str, ...] = Field(min_length=33, max_length=33)
    failed_request_sha256s: tuple[str, ...] = Field(min_length=33, max_length=33)
    budget_rows: tuple[RecoveryBudgetRow, ...] = Field(min_length=33, max_length=33)
    candidate_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_row_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    failed_request_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_job_count: Literal[33] = 33
    successful_prefix_call_count: Literal[55] = 55
    successful_prefix_usage_tokens: Literal[665598] = 665_598
    first_action_failure_count: Literal[3] = 3
    subsequent_action_failure_count: Literal[25] = 25
    final_failure_count: Literal[5] = 5
    reasoning_budget_count: Literal[31] = 31
    json_decode_count: Literal[2] = 2
    candidate_actual_byte_matches: Literal[33] = 33
    recovery_job_actual_byte_matches: Literal[33] = 33
    contract_actual_byte_match: Literal[True] = True
    population_actual_byte_match: Literal[True] = True
    historical_job_identity_overlap_count: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "fresh_v26_231_exact_recovery_parent_binding:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        vectors = (
            (self.recovery_candidate_ids, self.candidate_set_sha256),
            (self.recovery_job_ids, self.job_set_sha256),
            (self.source_row_ids, self.source_row_set_sha256),
            (self.failed_request_sha256s, self.failed_request_set_sha256),
        )
        if any(
            values != tuple(sorted(set(values))) or canonical_sha256(values) != digest
            for values, digest in vectors
        ):
            raise ValueError("Recovery parent set differs")
        if tuple(row.job_ordinal for row in self.budget_rows) != tuple(
            sorted(row.job_ordinal for row in self.budget_rows)
        ):
            raise ValueError("Recovery budget rows differ")
        if (
            sum(row.successful_prefix_call_count for row in self.budget_rows)
            != self.successful_prefix_call_count
        ):
            raise ValueError("Recovery prefix count differs")
        if (
            sum(row.successful_prefix_usage_tokens for row in self.budget_rows)
            != self.successful_prefix_usage_tokens
        ):
            raise ValueError("Recovery prefix Usage differs")
        phases = [row.failed_phase for row in self.budget_rows]
        if (
            phases.count("first_action") != 3
            or phases.count("subsequent_action") != 25
            or phases.count("final") != 5
        ):
            raise ValueError("Recovery phase partition differs")
        self.check_id("binding_id")
        return self


class RecoveryExecutionContract(Identified):
    contract_id: str
    parent_binding_id: str
    v209_execution_contract_id: Literal[
        "fresh_repaired_final_continuity_executable_full_condition_execution_contract:fc10dce5cdb2a3f677c93ad0780b5aa2b2e22eb44d6a1bf3c1d43d11ac6540d4"
    ]
    v209_runner_id: Literal[
        "fresh_repaired_final_continuity_executable_full_condition_runner:e58b8318667568b9becbb1fa946f1ac079937c9c744b6a2c4877661abebf0266"
    ]
    v209_resource_contract_id: Literal[
        "authoritative_kernel_resource_persistence_contract:ba6fb7967c3429d05184cc7a3ddc619187bf28ea438cc1b46bd66ce6a21055b4"
    ]
    v209_repair_profile_id: Literal[
        "fresh_repaired_action_interface_full_condition_profile:b0be8d7e8166f0fd5dfce43edc0ab4150e02f4f59cd97b4310e6cd49df94ab52"
    ]
    model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    thinking_type: Literal["enabled"] = "enabled"
    response_format_type: Literal["json_object"] = "json_object"
    request_max_tokens: Literal[16384] = 16_384
    source_request_max_tokens: Literal[16384] = 16_384
    max_tokens_changed_from_v26_226: Literal[False] = False
    failed_request_body_change_allowed: Literal[False] = False
    first_online_request_exact_failed_request_bytes_required: Literal[True] = True
    successful_prefix_mode: Literal["local_persisted_public_projection_replay_only"] = (
        "local_persisted_public_projection_replay_only"
    )
    recovery_mode: Literal["continue_from_exact_failed_request_to_fresh_terminal"] = (
        "continue_from_exact_failed_request_to_fresh_terminal"
    )
    exact_job_count: Literal[33] = 33
    historical_successful_prefix_provider_calls: Literal[0] = 0
    exact_failed_request_online_calls: Literal[33] = 33
    maximum_online_primary_requests: Literal[638] = 638
    maximum_online_provider_calls: Literal[704] = 704
    maximum_online_transport_invocations: Literal[737] = 737
    maximum_online_rollout_tokens: Literal[36294402] = 36_294_402
    per_job_combined_primary_request_limit: Literal[21] = 21
    per_job_combined_provider_call_limit: Literal[23] = 23
    per_job_combined_transport_invocation_limit: Literal[24] = 24
    per_job_combined_rollout_token_limit: Literal[1120000] = 1_120_000
    maximum_prompt_utf8_bytes: Literal[60000] = 60_000
    original_failed_call_usage_imputation_allowed: Literal[False] = False
    fresh_usage_accounting_starts_at_zero: Literal[True] = True
    trajectory_accounting_starts_at_successful_prefix_usage: Literal[True] = True
    replacement_failure_retry_allowed: Literal[False] = False
    current_state_runner_semantics_required: Literal[True] = True
    continue_after_successful_reissue_until_terminal: Literal[True] = True
    fresh_recovery_terminal_or_failure_record_required: Literal[True] = True
    historical_v26_226_terminal_backfill_allowed: Literal[False] = False
    historical_job_rerun_allowed: Literal[False] = False
    new_completion_budget_condition: Literal[False] = False
    provider_calls_authorized_during_contract_stage: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "fresh_v26_231_recovery_execution_contract:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if self.maximum_online_primary_requests != 33 * 21 - 55:
            raise ValueError("aggregate Primary request limit differs")
        if self.maximum_online_provider_calls != 33 * 23 - 55:
            raise ValueError("aggregate Provider call limit differs")
        if self.maximum_online_transport_invocations != 33 * 24 - 55:
            raise ValueError("aggregate transport invocation limit differs")
        if self.maximum_online_rollout_tokens != 33 * 1_120_000 - 665_598:
            raise ValueError("aggregate rollout token limit differs")
        self.check_id("contract_id")
        return self


EVENT_SEQUENCE: Final = (
    "validate_exact_fresh_authorization_bytes",
    "precredential_parent_scope_and_budget_guard",
    "consume_authorization_exactly_once",
    "persist_durable_consumption_receipt",
    "persist_durable_recovery_run_start_receipt",
    "credential_lookup_and_provider_construction",
    "locally_replay_55_historical_successful_public_projections",
    "dispatch_each_exact_captured_failed_request_once",
    "continue_exact_v26_209_current_state_runner_to_fresh_terminal",
    "persist_fresh_recovery_terminal_or_source_bound_failure",
    "persist_raw_before_result_trace_outcome_and_checkpoint",
)


class RecoveryComposition(Identified):
    composition_id: str
    v230_freeze_id: str
    parent_binding_id: str
    execution_contract_id: str
    event_sequence: tuple[str, ...] = Field(min_length=11, max_length=11)
    exact_recovery_job_count: Literal[33] = 33
    historical_prefix_provider_calls: Literal[0] = 0
    historical_success_response_reuse_as_provider_response: Literal[False] = False
    exact_failed_request_reissue_once: Literal[True] = True
    continuation_to_terminal_required: Literal[True] = True
    exact_authorization_consumption_before_credential: Literal[True] = True
    durable_consumption_receipt_before_credential: Literal[True] = True
    durable_run_start_receipt_before_credential: Literal[True] = True
    raw_before_result: Literal[True] = True
    result_before_trace: Literal[True] = True
    trace_before_outcome: Literal[True] = True
    outcome_before_checkpoint: Literal[True] = True
    historical_mutation_or_backfill_allowed: Literal[False] = False
    replacement_192_job_run_allowed: Literal[False] = False
    empirical_estimation_during_execution_allowed: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "fresh_v26_231_recovery_online_execution_composition:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if self.event_sequence != EVENT_SEQUENCE:
            raise ValueError("Recovery execution order differs")
        self.check_id("composition_id")
        return self


class ExactOnlineAuthorization(Identified):
    authorization_id: str
    external_decision_id: str
    v230_freeze_id: str
    parent_binding_id: str
    execution_contract_id: str
    composition_id: str
    recovery_job_ids: tuple[str, ...] = Field(min_length=33, max_length=33)
    recovery_job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorized_stage: Literal[
        "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_only"
    ] = NEXT_STAGE
    exact_recovery_job_count: Literal[33] = 33
    maximum_authorization_consumptions: Literal[1] = 1
    authorization_issued: Literal[True] = True
    authorization_consumed: Literal[False] = False
    provider_execution_authorized_in_successor: Literal[True] = True
    provider_execution_during_authorization: Literal[False] = False
    same_stage_consumption_forbidden: Literal[True] = True
    recovery_execution_authorized_in_successor: Literal[True] = True
    successful_prefix_provider_reissue_authorized: Literal[False] = False
    historical_v26_226_mutation_authorized: Literal[False] = False
    historical_terminal_backfill_authorized: Literal[False] = False
    replacement_run_authorized: Literal[False] = False
    additional_recovery_population_authorized: Literal[False] = False
    empirical_estimation_authorized: Literal[False] = False
    qa_mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    postrun_independent_audit_required: Literal[True] = True
    provider_calls_during_authorization: Literal[0] = 0
    credential_lookups_during_authorization: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "fresh_v26_231_exact_recovery_online_execution_authorization:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            self.recovery_job_ids != tuple(sorted(set(self.recovery_job_ids)))
            or canonical_sha256(self.recovery_job_ids) != self.recovery_job_set_sha256
        ):
            raise ValueError("authorized Recovery Job set differs")
        self.check_id("authorization_id")
        return self


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
        return "fresh_v26_231_recovery_online_authorization_admission:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("admission_id")
        return self


class PrecredentialGuard:
    def __init__(self, expected: ExactOnlineAuthorization, expected_bytes: bytes) -> None:
        strict = ExactOnlineAuthorization.model_validate(expected.model_dump(mode="python"))
        if canonical_bytes(strict) != expected_bytes:
            raise ValueError("expected authorization bytes differ")
        self._expected = strict
        self._bytes = expected_bytes

    def admit(
        self,
        *,
        authorization: object | None,
        authorization_bytes: bytes | None,
        requested_stage: str,
        requested_v230_freeze_id: str,
        requested_parent_binding_id: str,
        requested_execution_contract_id: str,
        requested_composition_id: str,
        requested_recovery_job_ids: tuple[str, ...],
        provider_execution_requested: bool,
        continuation_to_terminal_requested: bool,
        successful_prefix_provider_reissue_requested: bool = False,
        historical_mutation_requested: bool = False,
        historical_terminal_backfill_requested: bool = False,
        replacement_run_requested: bool = False,
        extra_recovery_job_requested: bool = False,
        max_tokens_change_requested: bool = False,
        empirical_estimation_requested: bool = False,
        qa_integration_requested: bool = False,
    ) -> Admission:
        if type(authorization) is not ExactOnlineAuthorization:
            raise ValueError("authorization parent type differs")
        assert isinstance(authorization, ExactOnlineAuthorization)
        strict = ExactOnlineAuthorization.model_validate(authorization.model_dump(mode="python"))
        if (
            authorization_bytes != self._bytes
            or strict.authorization_id != self._expected.authorization_id
        ):
            raise ValueError("authorization bytes or identity differ")
        actual = (
            requested_stage,
            requested_v230_freeze_id,
            requested_parent_binding_id,
            requested_execution_contract_id,
            requested_composition_id,
            requested_recovery_job_ids,
        )
        expected = (
            strict.authorized_stage,
            strict.v230_freeze_id,
            strict.parent_binding_id,
            strict.execution_contract_id,
            strict.composition_id,
            strict.recovery_job_ids,
        )
        if actual != expected:
            raise ValueError("requested Recovery execution parent differs")
        if not provider_execution_requested or not continuation_to_terminal_requested:
            raise ValueError("exact Recovery execution intent is required")
        if any(
            (
                successful_prefix_provider_reissue_requested,
                historical_mutation_requested,
                historical_terminal_backfill_requested,
                replacement_run_requested,
                extra_recovery_job_requested,
                max_tokens_change_requested,
                empirical_estimation_requested,
                qa_integration_requested,
            )
        ):
            raise ValueError("requested Recovery execution contains a forbidden expansion")
        return cast(
            Admission,
            make_identity(
                Admission,
                {
                    "authorization_id": strict.authorization_id,
                    "authorized_stage": strict.authorized_stage,
                    "v230_freeze_id": strict.v230_freeze_id,
                    "parent_binding_id": strict.parent_binding_id,
                    "execution_contract_id": strict.execution_contract_id,
                    "composition_id": strict.composition_id,
                    "recovery_job_set_sha256": strict.recovery_job_set_sha256,
                },
                field="admission_id",
                prefix=Admission.prefix(),
            ),
        )


class AdmissionControl(Identified):
    control_id: str
    control_name: str
    admitted: bool
    rejected: bool
    rejection_reason_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    post_guard_probe_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_231_precredential_admission_control:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            self.admitted == self.rejected
            or (self.admitted and self.rejection_reason_sha256 is not None)
            or (self.rejected and self.rejection_reason_sha256 is None)
        ):
            raise ValueError("admission control result differs")
        self.check_id("control_id")
        return self


class AdmissionAudit(Identified):
    audit_id: str
    authorization_id: str
    admission_id: str
    controls: tuple[AdmissionControl, ...] = Field(min_length=16)
    legal_control_count: Literal[1] = 1
    invalid_control_count: int = Field(ge=15)
    invalid_post_guard_probe_count: Literal[0] = 0
    authorization_consumptions: Literal[0] = 0
    run_start_receipts: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_231_precredential_admission_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            len(self.controls) != self.invalid_control_count + 1
            or sum(row.admitted for row in self.controls) != 1
            or sum(row.rejected for row in self.controls) != self.invalid_control_count
            or len({row.control_name for row in self.controls}) != len(self.controls)
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
        return "finance_v26_231_fully_rehashed_parent_attack:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("attack_id")
        return self


class ParentAttackAudit(Identified):
    audit_id: str
    authorization_id: str
    attacks: tuple[ParentAttack, ...] = Field(min_length=10)
    attack_count: int = Field(ge=10)
    rejected_attack_count: int = Field(ge=10)
    accepted_attack_count: Literal[0] = 0
    fully_rehashed_object_count: int = Field(ge=10)
    post_guard_probe_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_231_parent_attack_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            self.attack_count != len(self.attacks)
            or self.rejected_attack_count != len(self.attacks)
            or self.fully_rehashed_object_count != len(self.attacks)
            or len({row.attack_name for row in self.attacks}) != len(self.attacks)
        ):
            raise ValueError("parent attack Audit differs")
        self.check_id("audit_id")
        return self


class ScopeAudit(Identified):
    audit_id: str
    authorization_id: str
    online_authorizations_issued: Literal[1] = 1
    online_authorizations_consumed: Literal[0] = 0
    authorization_consumption_receipts: Literal[0] = 0
    run_start_receipts: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    model_client_constructions: Literal[0] = 0
    recovery_executions: Literal[0] = 0
    historical_prefix_provider_calls: Literal[0] = 0
    failed_job_reruns: Literal[0] = 0
    historical_v26_226_writes: Literal[0] = 0
    historical_terminal_backfills: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    qa_reads: Literal[0] = 0
    mapper_state_frequency_contribution_vtdo_rows: Literal[0] = 0
    training_release_production_rows: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_231_scope_boundary_audit:"

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
        return "finance_v26_231_gate_evaluation:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if len({row.name for row in self.gates}) != 8:
            raise ValueError("Gate partition differs")
        self.check_id("evaluation_id")
        return self


class Decision(Identified):
    decision_id: str
    external_decision_id: str
    gate_evaluation_id: str
    authorization_id: str
    decision: Literal[
        "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_issued_not_consumed"
    ] = DECISION_VALUE
    exact_recovery_job_count: Literal[33] = 33
    authorization_issued_count: Literal[1] = 1
    authorization_consumed_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    recovery_executions: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_231_online_authorization_decision:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("decision_id")
        return self


class Transition(Identified):
    transition_id: str
    decision_id: str
    authorization_id: str
    consumed_stage: Literal[
        "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_only"
    ] = CONSUMED_STAGE
    next_stage: Literal[
        "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_only"
    ] = NEXT_STAGE
    next_stage_authorized: Literal[True] = True
    authorization_issued: Literal[True] = True
    authorization_consumed: Literal[False] = False
    provider_calls_authorized_during_current_stage: Literal[False] = False
    provider_calls_authorized_only_after_successor_consumption: Literal[True] = True
    historical_prefix_provider_reissue_authorized: Literal[False] = False
    recovery_population_change_authorized: Literal[False] = False
    historical_v26_226_mutation_authorized: Literal[False] = False
    empirical_estimation_authorized: Literal[False] = False
    independent_postrun_audit_required: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_231_transition:"

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
    members: tuple[SourceMember, ...] = Field(min_length=2, max_length=2)
    member_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_231_source_identity:"

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
    v230_freeze_id: str
    required_symbols: tuple[str, ...] = Field(min_length=8)
    network_symbols_present: Literal[False] = False
    credential_environment_symbols_present: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "fresh_v26_231_recovery_online_authorization_implementation_binding:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if self.required_symbols != tuple(sorted(set(self.required_symbols))):
            raise ValueError("implementation symbol set differs")
        self.check_id("binding_id")
        return self


class Report(Identified):
    report_id: str
    run_id: Literal[
        "finance_v26_231_fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_v1_20260904"
    ] = RUN_ID
    source_identity_id: str
    implementation_binding_id: str
    external_decision_id: str
    v230_freeze_id: str
    parent_binding_id: str
    execution_contract_id: str
    composition_id: str
    authorization_id: str
    admission_audit_id: str
    parent_attack_audit_id: str
    scope_audit_id: str
    gate_evaluation_id: str
    decision_id: str
    transition_id: str
    decision: Literal[
        "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_issued_not_consumed"
    ] = DECISION_VALUE
    exact_recovery_job_count: Literal[33] = 33
    historical_successful_prefix_calls: Literal[55] = 55
    historical_successful_prefix_provider_reissues: Literal[0] = 0
    exact_failed_requests_bound: Literal[33] = 33
    maximum_online_provider_calls: Literal[704] = 704
    request_max_tokens: Literal[16384] = 16_384
    online_authorizations_issued: Literal[1] = 1
    online_authorizations_consumed: Literal[0] = 0
    provider_calls: Literal[0] = 0
    recovery_executions: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    historical_mutations: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_231_online_authorization_report:"

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
    run_id: Literal[
        "finance_v26_231_fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_v1_20260904"
    ] = RUN_ID
    members: tuple[ArtifactMember, ...]
    file_count: int = Field(ge=1)
    total_member_bytes: int = Field(gt=0)
    self_excluding: Literal[True] = True
    manifest_relative_path: Literal["artifact_manifest.json"] = "artifact_manifest.json"
    artifact_root: str
    provider_calls: Literal[0] = 0

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_231_artifact_manifest:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        paths = tuple(row.relative_path for row in self.members)
        expected_root = canonical_hash(
            tuple(row.model_dump(mode="json") for row in self.members),
            prefix="finance_v26_231_artifact_root:",
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
            prefix="finance_v26_231_artifact_root:",
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
