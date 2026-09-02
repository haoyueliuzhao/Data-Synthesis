# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from trusted_synthesis.core.task.all_typed_rejection_public_feedback import (
    PublicCorrectionBoundTerminal,
)
from trusted_synthesis.core.task.state_local_presentation_hardening import StepRuntimeResult
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)
from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_repaired_observation_derived_terminal.v1"
CONSUMED_STAGE: Final = (
    "fresh_repaired_full_condition_observation_derived_terminal_"
    "single_consumer_path_repair_preflight_only"
)
NEXT_STAGE: Final = (
    "fresh_repaired_full_condition_observation_derived_terminal_single_consumer_"
    "path_repair_preflight_independent_audit_only"
)
DECISION: Final = (
    "fresh_repaired_observation_derived_terminal_single_consumer_path_preflight_"
    "passed_independent_audit_required_online_execution_blocked"
)
TERMINAL_KINDS: Final = (
    "completed_qualified",
    "completed_invalid",
    "first_response_abi_invalid",
    "correction_response_abi_invalid",
    "first_action_reference_invalid",
    "correction_action_reference_invalid",
    "correction_attempt_typed_invalid",
    "final_response_abi_invalid",
    "provider_failure_no_payload",
    "provider_transport_failure",
    "privacy_rejection",
    "resource_budget_exhausted",
    "instrument_failure",
    "provider_identity_failure",
    "thinking_integrity_failure",
    "usage_integrity_failure",
)
EVIDENCE_KINDS: Final = (
    "completed_runner",
    "parser_rejection",
    "final_parser_rejection",
    "action_reference_failure",
    "correction_bound_failure",
    "provider_no_payload_exception",
    "transport_exception",
    "privacy_exception",
    "resource_exception",
    "instrument_exception",
    "provider_identity_exception",
    "thinking_integrity_exception",
    "usage_integrity_exception",
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


class ExternalRevisionAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: Literal["941b3137f2d0823ef1ec681c4364ee6d6aca242d9edc9d35b1b3dfdbea8396a9"]
    review_byte_count: Literal[16582] = 16_582
    audit_result: Literal["VALID_SCOPED_DURABLE_INGRESS_AND_PERSISTENCE_MECHANICS_PREFLIGHT"] = (
        "VALID_SCOPED_DURABLE_INGRESS_AND_PERSISTENCE_MECHANICS_PREFLIGHT"
    )
    failed_at: Literal["AUTHORITATIVE_TERMINAL_PROVENANCE_AND_HANDOFF"] = (
        "AUTHORITATIVE_TERMINAL_PROVENANCE_AND_HANDOFF"
    )
    operator_directive: Literal["参照审计报告继续实验修订"] = "参照审计报告继续实验修订"
    operator_directive_sha256: Literal[
        "dc2b598ec3667bd0e26354d1dac1ca447fa87acea50bd30a5fc245a9c35374e9"
    ]
    operator_directive_byte_count: Literal[36] = 36
    consumed_stage: Literal[
        "fresh_repaired_full_condition_observation_derived_terminal_single_consumer_path_repair_preflight_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalRevisionAuthorization:
        directive = self.operator_directive.encode("utf-8")
        if (
            len(directive) != self.operator_directive_byte_count
            or hashlib.sha256(directive).hexdigest() != self.operator_directive_sha256
            or self.authorization_id
            != identity(
                self,
                "authorization_id",
                "finance_v26_213_external_revision_authorization:",
            )
        ):
            raise ValueError("v26.213 external authorization differs")
        return self


class V212Freeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v212_report_id: str = Field(min_length=1)
    v212_decision_id: str = Field(min_length=1)
    v212_transition_id: str = Field(min_length=1)
    v212_consumer_binding_id: str = Field(min_length=1)
    v212_composition_contract_id: str = Field(min_length=1)
    v212_artifact_manifest_id: str = Field(min_length=1)
    v212_artifact_root: str = Field(min_length=1)
    v212_source_commit: Literal["9173b16cc1340449fa18b4030b8d2c7686fa3b5f"]
    v212_source_tree: Literal["2b3562714d70b587c4ef1424e15885e5f1e92880"]
    formal_file_count: Literal[1067] = 1_067
    formal_total_byte_count: Literal[2239071] = 2_239_071
    manifest_member_count: Literal[1066] = 1_066
    manifest_member_byte_count: Literal[2017584] = 2_017_584
    durable_ingress_retained: Literal[True] = True
    runner_replay_retained: Literal[True] = True
    persistence_mechanics_retained: Literal[True] = True
    terminal_label_controls_diagnostic_only: Literal[True] = True
    first_blocker: Literal[
        "caller_supplied_terminal_kind_replaces_observation_derived_terminal_dispatch"
    ] = "caller_supplied_terminal_kind_replaces_observation_derived_terminal_dispatch"
    v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V212Freeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_213_v212_freeze:"):
            raise ValueError("v26.213 v26.212 Freeze identity differs")
        return self


class SourceBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v212_freeze_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    files: tuple[SourceBinding, ...] = Field(min_length=4)
    symbols: tuple[SourceBinding, ...] = Field(min_length=6)
    dispatcher_terminal_kind_parameter_count: Literal[0] = 0
    provider_network_symbols: Literal[0] = 0
    credential_environment_symbols: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ImplementationBinding:
        if (
            tuple(item.relative_path for item in self.files)
            != tuple(sorted({item.relative_path for item in self.files}))
            or len({item.symbol for item in self.symbols}) != len(self.symbols)
            or self.binding_id
            != identity(
                self,
                "binding_id",
                "fresh_repaired_observation_derived_terminal_implementation_binding:",
            )
        ):
            raise ValueError("v26.213 Implementation Binding differs")
        return self


class CompletedRunnerEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    evidence_kind: Literal["completed_runner"] = "completed_runner"
    job_id: str = Field(min_length=1)
    invocation_records: tuple[dict[str, Any], ...] = Field(min_length=2, max_length=10)
    final_public_payload: dict[str, Any]
    final_result: dict[str, Any]
    final_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_result_id: str = Field(min_length=1)
    task_report_id: str = Field(min_length=1)
    mechanism_report_id: str = Field(min_length=1)
    qualified_report_id: str = Field(min_length=1)
    base_valid: bool
    mechanism_valid: bool
    qualified_valid: bool
    source_runner_completed: Literal[True] = True
    terminal_label_input: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evidence(self) -> CompletedRunnerEvidence:
        records = tuple(
            v209_models.ExecutableInvocationRecord.model_validate(item)
            for item in self.invocation_records
        )
        final = records[-1]
        strict_result = StepRuntimeResult.model_validate(self.final_result)
        task = strict_result.task_validity
        mechanism = strict_result.mechanism_qualification
        qualified = strict_result.qualified_validity
        if (
            any(item.job_id != self.job_id for item in records)
            or final.phase != "final"
            or final.typed_terminal is not None
            or not final.exact_response_parsed
            or not final.current_state_and_candidate_or_final_envelope_valid
            or not final.runtime_step_or_finalize_completed
            or final.public_response_sha256 != canonical_sha256(self.final_public_payload)
            or self.final_result_sha256 != canonical_sha256(self.final_result)
            or self.final_result_id != strict_result.result_id
            or self.task_report_id != task.report_id
            or self.mechanism_report_id != mechanism.report_id
            or self.qualified_report_id != qualified.report_id
            or self.base_valid != task.base_valid
            or self.mechanism_valid != mechanism.mechanism_semantically_qualified
            or self.qualified_valid != qualified.qualified_valid
            or self.qualified_valid != (self.base_valid and self.mechanism_valid)
            or self.evidence_id
            != identity(self, "evidence_id", "fresh_repaired_completed_runner_evidence:")
        ):
            raise ValueError("completed Runner evidence differs from actual Final factors")
        return self


ParserPhase = Literal["first_action", "correction"]


class ParserRejectionEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    evidence_kind: Literal["parser_rejection"] = "parser_rejection"
    job_id: str = Field(min_length=1)
    phase: ParserPhase
    invocation_record: dict[str, Any]
    public_payload: dict[str, Any]
    parser_exception_type: Literal["SemanticActionResponseRejection"] = (
        "SemanticActionResponseRejection"
    )
    parser_rejected: Literal[True] = True
    terminal_label_input: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evidence(self) -> ParserRejectionEvidence:
        record = v209_models.ExecutableInvocationRecord.model_validate(self.invocation_record)
        if (
            record.job_id != self.job_id
            or record.phase != self.phase
            or record.exact_response_parsed
            or record.current_state_and_candidate_or_final_envelope_valid
            or record.runtime_step_or_finalize_completed
            or record.public_response_sha256 != canonical_sha256(self.public_payload)
            or self.evidence_id
            != identity(self, "evidence_id", "fresh_repaired_parser_rejection_evidence:")
        ):
            raise ValueError("parser rejection evidence differs")
        return self


class FinalParserRejectionEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    evidence_kind: Literal["final_parser_rejection"] = "final_parser_rejection"
    job_id: str = Field(min_length=1)
    invocation_record: dict[str, Any]
    public_payload: dict[str, Any]
    parser_exception_type: Literal["ValidationError"] = "ValidationError"
    parser_rejected: Literal[True] = True
    terminal_label_input: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evidence(self) -> FinalParserRejectionEvidence:
        record = v209_models.ExecutableInvocationRecord.model_validate(self.invocation_record)
        if (
            record.job_id != self.job_id
            or record.phase != "final"
            or record.exact_response_parsed
            or record.current_state_and_candidate_or_final_envelope_valid
            or record.runtime_step_or_finalize_completed
            or record.public_response_sha256 != canonical_sha256(self.public_payload)
            or self.evidence_id
            != identity(
                self,
                "evidence_id",
                "fresh_repaired_final_parser_rejection_evidence:",
            )
        ):
            raise ValueError("Final parser rejection evidence differs")
        return self


class ActionReferenceFailureEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    evidence_kind: Literal["action_reference_failure"] = "action_reference_failure"
    job_id: str = Field(min_length=1)
    phase: Literal["first_action", "correction"]
    invocation_record: dict[str, Any]
    public_payload: dict[str, Any]
    current_state_id: str = Field(min_length=1)
    current_candidate_action_ids: tuple[str, ...] = Field(min_length=1)
    observed_action_id: str = Field(min_length=1)
    parser_accepted: Literal[True] = True
    current_reference_valid: Literal[False] = False
    terminal_label_input: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evidence(self) -> ActionReferenceFailureEvidence:
        record = v209_models.ExecutableInvocationRecord.model_validate(self.invocation_record)
        if (
            record.job_id != self.job_id
            or record.phase != self.phase
            or not record.exact_response_parsed
            or record.current_state_and_candidate_or_final_envelope_valid
            or record.runtime_step_or_finalize_completed
            or record.current_state_id != self.current_state_id
            or record.candidate_action_ids != self.current_candidate_action_ids
            or record.selected_action_id != self.observed_action_id
            or self.observed_action_id in self.current_candidate_action_ids
            or record.public_response_sha256 != canonical_sha256(self.public_payload)
            or self.evidence_id
            != identity(
                self,
                "evidence_id",
                "fresh_repaired_action_reference_failure_evidence:",
            )
        ):
            raise ValueError("Action reference evidence differs")
        return self


class CorrectionBoundFailureEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    evidence_kind: Literal["correction_bound_failure"] = "correction_bound_failure"
    job_id: str = Field(min_length=1)
    invocation_record: dict[str, Any]
    public_payload: dict[str, Any]
    correction_terminal: dict[str, Any]
    correction_attempt_index: Literal[2] = 2
    correction_attempt_bound: Literal[1] = 1
    parser_accepted: Literal[True] = True
    current_reference_valid: Literal[True] = True
    terminal_label_input: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evidence(self) -> CorrectionBoundFailureEvidence:
        record = v209_models.ExecutableInvocationRecord.model_validate(self.invocation_record)
        terminal = PublicCorrectionBoundTerminal.model_validate(self.correction_terminal)
        if (
            record.job_id != self.job_id
            or record.phase != "correction"
            or not record.exact_response_parsed
            or not record.current_state_and_candidate_or_final_envelope_valid
            or not record.runtime_step_or_finalize_completed
            or record.action_accepted
            or record.public_response_sha256 != canonical_sha256(self.public_payload)
            or terminal.terminal_reason != "correction_attempt_typed_invalid"
            or terminal.correction_attempt_bound != self.correction_attempt_bound
            or terminal.second_response_class
            not in {
                "same_current_invalid",
                "different_current_invalid",
                "stale_action_id",
                "foreign_or_unbound_action_id",
                "malformed_action_reference",
            }
            or self.evidence_id
            != identity(
                self,
                "evidence_id",
                "fresh_repaired_correction_bound_failure_evidence:",
            )
        ):
            raise ValueError("Correction-bound evidence differs")
        return self


class TypedExceptionEvidenceBase(FrozenModel):
    evidence_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    invocation_record: dict[str, Any]
    exception_type: str = Field(min_length=1)
    exception_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exception_observed: Literal[True] = True
    terminal_label_input: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_outer_evidence(self) -> TypedExceptionEvidenceBase:
        record = v209_models.ExecutableInvocationRecord.model_validate(self.invocation_record)
        if (
            record.job_id != self.job_id
            or record.public_response_sha256 is not None
            or record.exact_response_parsed
            or record.runtime_step_or_finalize_completed
            or self.evidence_id
            != identity(self, "evidence_id", "fresh_repaired_typed_exception_evidence:")
        ):
            raise ValueError("typed exception evidence differs")
        return self


class ProviderNoPayloadEvidence(TypedExceptionEvidenceBase):
    evidence_kind: Literal["provider_no_payload_exception"] = "provider_no_payload_exception"
    exception_type: Literal["ProviderNoPayloadError"] = "ProviderNoPayloadError"


class TransportFailureEvidence(TypedExceptionEvidenceBase):
    evidence_kind: Literal["transport_exception"] = "transport_exception"
    exception_type: Literal["ProviderTransportError"] = "ProviderTransportError"


class PrivacyFailureEvidence(TypedExceptionEvidenceBase):
    evidence_kind: Literal["privacy_exception"] = "privacy_exception"
    exception_type: Literal["PrivacyEvidenceError"] = "PrivacyEvidenceError"


class ResourceFailureEvidence(TypedExceptionEvidenceBase):
    evidence_kind: Literal["resource_exception"] = "resource_exception"
    exception_type: Literal["ResourceBudgetError"] = "ResourceBudgetError"


class InstrumentFailureEvidence(TypedExceptionEvidenceBase):
    evidence_kind: Literal["instrument_exception"] = "instrument_exception"
    exception_type: Literal["InstrumentEvidenceError"] = "InstrumentEvidenceError"


class ProviderIdentityFailureEvidence(TypedExceptionEvidenceBase):
    evidence_kind: Literal["provider_identity_exception"] = "provider_identity_exception"
    exception_type: Literal["ProviderIdentityError"] = "ProviderIdentityError"


class ThinkingIntegrityFailureEvidence(TypedExceptionEvidenceBase):
    evidence_kind: Literal["thinking_integrity_exception"] = "thinking_integrity_exception"
    exception_type: Literal["ThinkingIntegrityError"] = "ThinkingIntegrityError"


class UsageIntegrityFailureEvidence(TypedExceptionEvidenceBase):
    evidence_kind: Literal["usage_integrity_exception"] = "usage_integrity_exception"
    exception_type: Literal["UsageIntegrityError"] = "UsageIntegrityError"


ObservedEvidence = Annotated[
    CompletedRunnerEvidence
    | ParserRejectionEvidence
    | FinalParserRejectionEvidence
    | ActionReferenceFailureEvidence
    | CorrectionBoundFailureEvidence
    | ProviderNoPayloadEvidence
    | TransportFailureEvidence
    | PrivacyFailureEvidence
    | ResourceFailureEvidence
    | InstrumentFailureEvidence
    | ProviderIdentityFailureEvidence
    | ThinkingIntegrityFailureEvidence
    | UsageIntegrityFailureEvidence,
    Field(discriminator="evidence_kind"),
]
OBSERVED_EVIDENCE_ADAPTER: Final = TypeAdapter(ObservedEvidence)


class ObservationDerivedDispatcherBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    source_v195_terminal_registry_id: str = Field(min_length=1)
    exact_v209_runner_id: str = Field(min_length=1)
    dispatcher_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_kinds: tuple[str, ...] = EVIDENCE_KINDS
    terminal_kinds: tuple[str, ...] = TERMINAL_KINDS
    terminal_policy_ids: tuple[str, ...] = Field(min_length=16, max_length=16)
    dispatcher_input: Literal["ObservedEvidence"] = "ObservedEvidence"
    terminal_kind_input_allowed: Literal[False] = False
    expected_terminal_input_allowed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ObservationDerivedDispatcherBinding:
        if (
            self.evidence_kinds != EVIDENCE_KINDS
            or self.terminal_kinds != TERMINAL_KINDS
            or len(set(self.terminal_policy_ids)) != 16
            or self.binding_id
            != identity(
                self,
                "binding_id",
                "fresh_repaired_observation_derived_terminal_dispatcher_binding:",
            )
        ):
            raise ValueError("observation-derived Dispatcher Binding differs")
        return self


class ObservationBoundPersistenceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    source_v212_raw_result_writer_binding_id: str = Field(min_length=1)
    source_v212_trace_outcome_checkpoint_binding_id: str = Field(min_length=1)
    persistence_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_dispatch_rederivation_required: Literal[True] = True
    observed_evidence_embedded_in_raw: Literal[True] = True
    raw_before_result_required: Literal[True] = True
    durable_no_replace_required: Literal[True] = True
    terminal_argument_allowed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ObservationBoundPersistenceBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_observation_bound_persistence_binding:",
        ):
            raise ValueError("observation-bound persistence Binding differs")
        return self


class SingleConsumerImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    exact_v211_authorization_id: str = Field(min_length=1)
    exact_v209_implementation_id: str = Field(min_length=1)
    exact_v209_manifest_id: str = Field(min_length=1)
    exact_v209_runner_id: str = Field(min_length=1)
    exact_v209_execution_contract_id: str = Field(min_length=1)
    source_v212_consumption_contract_id: str = Field(min_length=1)
    source_v212_run_start_contract_id: str = Field(min_length=1)
    source_v212_provider_transport_binding_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    persistence_binding_id: str = Field(min_length=1)
    execute_preflight_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    one_entry_function: Literal["RepairedOnlineExecutionConsumer.execute_preflight"] = (
        "RepairedOnlineExecutionConsumer.execute_preflight"
    )
    runner_terminal_persistence_single_call_chain: Literal[True] = True
    terminal_label_input_allowed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> SingleConsumerImplementationBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_single_online_consumer_implementation_binding:",
        ):
            raise ValueError("single consumer Binding differs")
        return self


class SingleConsumerCompositionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    v212_freeze_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    persistence_binding_id: str = Field(min_length=1)
    exact_sequence: tuple[str, ...] = (
        "authorization_guard",
        "durable_preflight_consumption_receipt",
        "durable_run_start_receipt",
        "credential_and_factory_gate",
        "actual_current_state_runner",
        "collect_actual_result_or_typed_evidence",
        "derive_authoritative_terminal",
        "persist_raw_result_trace_outcome_checkpoint",
    )
    build_level_runner_terminal_join_forbidden: Literal[True] = True
    caller_terminal_forbidden: Literal[True] = True
    current_v211_authorization_consumed: Literal[False] = False
    new_online_authorization_created: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> SingleConsumerCompositionContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_repaired_observation_derived_single_consumer_composition_contract:",
        ):
            raise ValueError("single consumer Composition differs")
        return self


class DerivedTerminalDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    job_id: str = Field(min_length=1)
    terminal_kind: str = Field(min_length=1)
    terminal_policy_id: str = Field(min_length=1)
    derivation_rule: str = Field(min_length=1)
    terminal_label_was_input: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> DerivedTerminalDecision:
        if self.terminal_kind not in TERMINAL_KINDS or self.decision_id != identity(
            self, "decision_id", "fresh_repaired_derived_terminal_decision:"
        ):
            raise ValueError("derived terminal Decision differs")
        return self


class PersistedEvidenceDescriptor(FrozenModel):
    descriptor_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    terminal_kind: str = Field(min_length=1)
    raw_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    outcome_id: str = Field(min_length=1)
    checkpoint_id: str = Field(min_length=1)
    raw_relative_path: str = Field(min_length=1)
    result_relative_path: str = Field(min_length=1)
    trace_relative_path: str = Field(min_length=1)
    outcome_relative_path: str = Field(min_length=1)
    checkpoint_relative_path: str = Field(min_length=1)
    persistence_sequence: tuple[str, ...]
    actual_byte_match_count: Literal[5] = 5
    formal_empirical_row: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> PersistedEvidenceDescriptor:
        if (
            self.terminal_kind not in TERMINAL_KINDS
            or self.persistence_sequence != ("raw", "result", "trace", "outcome", "checkpoint")
            or len(
                {
                    self.raw_id,
                    self.result_id,
                    self.trace_id,
                    self.outcome_id,
                    self.checkpoint_id,
                }
            )
            != 5
            or self.descriptor_id
            != identity(
                self,
                "descriptor_id",
                "finance_v26_213_persisted_evidence_descriptor:",
            )
        ):
            raise ValueError("persisted evidence Descriptor differs")
        return self


class SingleConsumerExecutionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    consumption_receipt_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    v209_invocation_census_id: str = Field(min_length=1)
    v209_execution_control_audit_id: str = Field(min_length=1)
    descriptors: tuple[PersistedEvidenceDescriptor, ...] = Field(min_length=192, max_length=192)
    exact_job_count: Literal[192] = 192
    actual_runner_invocation_count: Literal[792] = 792
    injected_transport_dispatch_count: Literal[792] = 792
    completed_runner_evidence_count: Literal[192] = 192
    observation_derived_completed_qualified_count: Literal[192] = 192
    raw_result_trace_outcome_checkpoint_count: Literal[960] = 960
    build_level_terminal_join_count: Literal[0] = 0
    caller_terminal_argument_count: Literal[0] = 0
    exception_escape_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SingleConsumerExecutionAudit:
        if (
            len({item.job_id for item in self.descriptors}) != 192
            or any(item.terminal_kind != "completed_qualified" for item in self.descriptors)
            or self.audit_id
            != identity(
                self,
                "audit_id",
                "finance_v26_213_single_consumer_execution_audit:",
            )
        ):
            raise ValueError("single consumer execution Audit differs")
        return self


class TerminalEvidenceControl(FrozenModel):
    control_id: str = Field(min_length=1)
    expected_terminal: str = Field(min_length=1)
    observed_evidence: ObservedEvidence
    derived_decision: DerivedTerminalDecision
    persistence: PersistedEvidenceDescriptor
    expected_terminal_used_only_after_dispatch: Literal[True] = True
    expected_terminal_passed_to_runner: Literal[False] = False
    expected_terminal_passed_to_dispatcher: Literal[False] = False
    expected_terminal_passed_to_writer: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> TerminalEvidenceControl:
        if (
            self.expected_terminal not in TERMINAL_KINDS
            or self.derived_decision.terminal_kind != self.expected_terminal
            or self.observed_evidence.evidence_id != self.derived_decision.evidence_id
            or self.persistence.decision_id != self.derived_decision.decision_id
            or self.control_id
            != identity(self, "control_id", "finance_v26_213_terminal_evidence_control:")
        ):
            raise ValueError("terminal evidence Control differs")
        return self


class TerminalEvidenceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    controls: tuple[TerminalEvidenceControl, ...] = Field(min_length=16, max_length=16)
    exact_reachable_terminal_count: Literal[16] = 16
    actual_evidence_control_count: Literal[16] = 16
    exact_derived_terminal_match_count: Literal[16] = 16
    persisted_layer_reference_count: Literal[80] = 80
    label_only_control_count: Literal[0] = 0
    caller_terminal_argument_count: Literal[0] = 0
    exception_escape_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> TerminalEvidenceAudit:
        if tuple(
            item.expected_terminal for item in self.controls
        ) != TERMINAL_KINDS or self.audit_id != identity(
            self, "audit_id", "finance_v26_213_terminal_evidence_audit:"
        ):
            raise ValueError("terminal evidence Audit differs")
        return self


class NegativeControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    fully_rehashed: Literal[True] = True
    rejected: Literal[True] = True
    rejected_before_raw_write: Literal[True] = True
    rejection_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fully_rehashed_downstream_layer_ids: tuple[str, ...] = Field(max_length=5)
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> NegativeControl:
        requires_layers = self.control_name in {
            "qualified_runner_evidence_relabel",
            "cross_job_terminal_decision_substitution",
        }
        if (
            (requires_layers and len(set(self.fully_rehashed_downstream_layer_ids)) != 5)
            or (not requires_layers and self.fully_rehashed_downstream_layer_ids)
            or self.control_id
            != identity(
                self,
                "control_id",
                "finance_v26_213_terminal_provenance_negative_control:",
            )
        ):
            raise ValueError("terminal provenance negative Control differs")
        return self


class NegativeControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    controls: tuple[NegativeControl, ...] = Field(min_length=4, max_length=4)
    caller_terminal_api_absent_count: Literal[1] = 1
    qualified_relabel_rejected_count: Literal[1] = 1
    cross_job_substitution_rejected_count: Literal[1] = 1
    invalid_factorization_rejected_count: Literal[1] = 1
    fully_rehashed_downstream_attack_count: Literal[2] = 2
    fully_rehashed_downstream_layer_identity_count: Literal[10] = 10
    rejected_count: Literal[4] = 4
    accepted_count: Literal[0] = 0
    raw_write_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> NegativeControlAudit:
        if len({item.control_name for item in self.controls}) != 4 or self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_213_terminal_provenance_negative_control_audit:",
        ):
            raise ValueError("terminal provenance negative Audit differs")
        return self


class ScopeBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v212_freeze_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    current_v211_authorization_consumed: Literal[False] = False
    isolated_preflight_lease_count: Literal[1] = 1
    preflight_run_start_receipt_count: Literal[1] = 1
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    provider_client_constructions: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    new_online_authorizations: Literal[0] = 0
    qa_reads: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ScopeBoundaryAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_213_scope_boundary_audit:",
        ):
            raise ValueError("v26.213 scope boundary differs")
        return self


class GateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> GateResult:
        if self.gate_id != identity(
            self,
            "gate_id",
            "finance_v26_213_observation_terminal_gate:",
        ):
            raise ValueError("v26.213 Gate differs")
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
            self,
            "evaluation_id",
            "finance_v26_213_observation_terminal_gate_evaluation:",
        ):
            raise ValueError("v26.213 Gate Evaluation differs")
        return self


class Decision(FrozenModel):
    decision_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v212_freeze_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    execution_audit_id: str = Field(min_length=1)
    terminal_evidence_audit_id: str = Field(min_length=1)
    negative_control_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_observation_derived_terminal_single_consumer_path_preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> Decision:
        if self.decision_id != identity(
            self,
            "decision_id",
            "finance_v26_213_observation_terminal_decision:",
        ):
            raise ValueError("v26.213 Decision differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    status: Literal["PASSED_PREFLIGHT_ONLINE_EXECUTION_BLOCKED"] = (
        "PASSED_PREFLIGHT_ONLINE_EXECUTION_BLOCKED"
    )
    next_stage: Literal[
        "fresh_repaired_full_condition_observation_derived_terminal_single_consumer_path_repair_preflight_independent_audit_only"
    ] = NEXT_STAGE
    new_online_authorization_required_after_independent_audit: Literal[True] = True
    provider_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> Transition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_213_transition:",
        ):
            raise ValueError("v26.213 Transition differs")
        return self


class SourceIdentity(FrozenModel):
    source_identity_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    implementation_files: tuple[str, ...] = Field(min_length=4)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_source(self) -> SourceIdentity:
        if self.implementation_files != tuple(
            sorted(set(self.implementation_files))
        ) or self.source_identity_id != identity(
            self, "source_identity_id", "finance_v26_213_source_identity:"
        ):
            raise ValueError("v26.213 source identity differs")
        return self


class Report(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v212_freeze_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    execution_audit_id: str = Field(min_length=1)
    terminal_evidence_audit_id: str = Field(min_length=1)
    negative_control_audit_id: str = Field(min_length=1)
    scope_boundary_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_observation_derived_terminal_single_consumer_path_preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    exact_job_count: Literal[192] = 192
    actual_runner_invocation_count: Literal[792] = 792
    observation_derived_terminal_count: Literal[192] = 192
    terminal_evidence_control_count: Literal[16] = 16
    current_v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> Report:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_213_observation_terminal_report:",
        ):
            raise ValueError("v26.213 report differs")
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
            raise ValueError("v26.213 Artifact Manifest geometry differs")
        expected = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_213_artifact_root:",
        )
        if self.artifact_root != expected or self.manifest_id != identity(
            self, "manifest_id", "finance_v26_213_artifact_manifest:"
        ):
            raise ValueError("v26.213 Artifact Root or Manifest differs")
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
        prefix="finance_v26_213_artifact_root:",
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
            prefix="finance_v26_213_artifact_manifest:",
        ),
    )
