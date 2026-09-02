# ruff: noqa: E501
from __future__ import annotations

import hashlib
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_observation_derived_terminal_models as v213_models,
)
from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_repaired_outer_typed_exception_authenticity.v1"
CONSUMED_STAGE: Final = (
    "fresh_repaired_outer_typed_exception_observation_authenticity_"
    "and_single_consumer_failure_terminalization_preflight_only"
)
NEXT_STAGE: Final = (
    "fresh_repaired_outer_typed_exception_observation_authenticity_and_single_consumer_"
    "failure_terminalization_preflight_independent_audit_only"
)
DECISION: Final = (
    "fresh_repaired_outer_typed_exception_observation_authenticity_and_single_consumer_"
    "failure_terminalization_preflight_passed_independent_audit_required_online_execution_blocked"
)
EXACT_V209_RUNNER_ID: Final = (
    "fresh_repaired_final_continuity_executable_full_condition_runner:"
    "e58b8318667568b9becbb1fa946f1ac079937c9c744b6a2c4877661abebf0266"
)
OUTER_TERMINAL_KINDS: Final = (
    "provider_failure_no_payload",
    "provider_transport_failure",
    "privacy_rejection",
    "resource_budget_exhausted",
    "instrument_failure",
    "provider_identity_failure",
    "thinking_integrity_failure",
    "usage_integrity_failure",
)
EXCEPTION_TERMINAL_ITEMS: Final = (
    ("ProviderNoPayloadError", "provider_failure_no_payload"),
    ("ProviderTransportError", "provider_transport_failure"),
    ("PrivacyEvidenceError", "privacy_rejection"),
    ("ResourceBudgetError", "resource_budget_exhausted"),
    ("InstrumentEvidenceError", "instrument_failure"),
    ("ProviderIdentityError", "provider_identity_failure"),
    ("ThinkingIntegrityError", "thinking_integrity_failure"),
    ("UsageIntegrityError", "usage_integrity_failure"),
)
EXCEPTION_TO_TERMINAL: Final = dict(EXCEPTION_TERMINAL_ITEMS)

canonical_bytes = v213_models.canonical_bytes
canonical_sha256 = v213_models.canonical_sha256
identity = v213_models.identity
make_identity = v213_models.make_identity


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExternalRevisionAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_byte_count: Literal[14653] = 14653
    operator_directive: Literal["参照审计继续实验修订"] = "参照审计继续实验修订"
    operator_directive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    operator_directive_byte_count: int = Field(gt=0)
    audit_result: Literal["VALID_SCOPED_COMPLETED_AND_PARSER_TERMINAL_PREFLIGHT"] = (
        "VALID_SCOPED_COMPLETED_AND_PARSER_TERMINAL_PREFLIGHT"
    )
    failed_at: Literal["OUTER_TYPED_EXCEPTION_EVIDENCE_AUTHENTICITY"] = (
        "OUTER_TYPED_EXCEPTION_EVIDENCE_AUTHENTICITY"
    )
    consumed_stage: Literal[
        "fresh_repaired_outer_typed_exception_observation_authenticity_"
        "and_single_consumer_failure_terminalization_preflight_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalRevisionAuthorization:
        if self.authorization_id != identity(
            self, "authorization_id", "finance_v26_214_external_revision_authorization:"
        ):
            raise ValueError("v26.214 external authorization identity differs")
        return self


class V213Freeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v213_report_id: str = Field(min_length=1)
    v213_decision_id: str = Field(min_length=1)
    v213_transition_id: str = Field(min_length=1)
    v213_artifact_manifest_id: str = Field(min_length=1)
    v213_artifact_root: str = Field(min_length=1)
    v213_source_commit: Literal["904577d81bcd83183d3aae0bab4e9f53c9907f0d"] = (
        "904577d81bcd83183d3aae0bab4e9f53c9907f0d"
    )
    v213_source_tree: Literal["c2f2e7629b29f7dfbcc27153539a1aa5be1cdf23"] = (
        "c2f2e7629b29f7dfbcc27153539a1aa5be1cdf23"
    )
    formal_file_count: Literal[1058] = 1058
    formal_total_byte_count: Literal[58565824] = 58565824
    manifest_member_count: Literal[1057] = 1057
    manifest_member_byte_count: Literal[58336116] = 58336116
    completed_main_path_retained: Literal[True] = True
    parser_reference_bound_paths_retained: Literal[True] = True
    five_layer_persistence_retained: Literal[True] = True
    outer_typed_exception_authenticity_failed: Literal[True] = True
    first_blocker: Literal[
        "evidence_subclass_not_bound_to_invocation_terminal_and_actual_exception_identity"
    ] = "evidence_subclass_not_bound_to_invocation_terminal_and_actual_exception_identity"
    v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V213Freeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_214_v213_freeze:"):
            raise ValueError("v26.214 v26.213 Freeze identity differs")
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
            self, "source_identity_id", "finance_v26_214_source_identity:"
        ):
            raise ValueError("v26.214 source identity differs")
        return self


class ImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v213_freeze_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    files: tuple[SourceBinding, ...] = Field(min_length=4, max_length=4)
    symbols: tuple[SourceBinding, ...] = Field(min_length=6)
    direct_network_routes: Literal[0] = 0
    credential_environment_routes: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ImplementationBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_outer_typed_exception_authenticity_implementation_binding:",
        ):
            raise ValueError("v26.214 implementation Binding differs")
        return self


class RunnerObservationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    exact_v209_runner_id: Literal[
        "fresh_repaired_final_continuity_executable_full_condition_runner:"
        "e58b8318667568b9becbb1fa946f1ac079937c9c744b6a2c4877661abebf0266"
    ] = EXACT_V209_RUNNER_ID
    exact_v209_request_implementation_id: str = Field(min_length=1)
    runner_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_authority_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    caught_exception_class_to_terminal: tuple[tuple[str, str], ...] = EXCEPTION_TERMINAL_ITEMS
    observation_constructed_inside_runner_catch: Literal[True] = True
    caller_evidence_subtype_allowed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> RunnerObservationBinding:
        if (
            self.caught_exception_class_to_terminal != EXCEPTION_TERMINAL_ITEMS
            or self.binding_id
            != identity(
                self,
                "binding_id",
                "fresh_repaired_runner_owned_typed_failure_observation_binding:",
            )
        ):
            raise ValueError("v26.214 Runner observation Binding differs")
        return self


class TypedFailureObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    runner_binding_id: str = Field(min_length=1)
    source_runner_id: Literal[
        "fresh_repaired_final_continuity_executable_full_condition_runner:"
        "e58b8318667568b9becbb1fa946f1ac079937c9c744b6a2c4877661abebf0266"
    ] = EXACT_V209_RUNNER_ID
    job_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    certificate_id: str = Field(min_length=1)
    pre_transport_receipt_id: str = Field(min_length=1)
    injected_transport_seam_id: str = Field(min_length=1)
    caught_exception_class: str = Field(min_length=1)
    caught_terminal_kind: str = Field(min_length=1)
    exception_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    invocation_record: dict[str, Any]
    runner_owned: Literal[True] = True
    constructed_inside_runner_catch: Literal[True] = True
    terminal_label_input: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> TypedFailureObservation:
        record = v209_models.ExecutableInvocationRecord.model_validate(self.invocation_record)
        expected_terminal = EXCEPTION_TO_TERMINAL.get(self.caught_exception_class)
        if (
            expected_terminal is None
            or expected_terminal != self.caught_terminal_kind
            or record.typed_terminal != self.caught_terminal_kind
            or record.job_id != self.job_id
            or record.invocation_id != self.invocation_id
            or record.request_id != self.request_id
            or record.certificate_id != self.certificate_id
            or record.pre_transport_receipt_id != self.pre_transport_receipt_id
            or record.injected_transport_seam_id != self.injected_transport_seam_id
            or record.public_response_sha256 is not None
            or record.exact_response_parsed
            or record.runtime_step_or_finalize_completed
            or not record.event_sequence
            or record.event_sequence[-1] != "terminal_dispatch"
            or self.observation_id
            != identity(
                self,
                "observation_id",
                "fresh_repaired_runner_owned_typed_failure_observation:",
            )
        ):
            raise ValueError("Runner-owned typed failure observation differs")
        return self


class AuthenticatedTypedFailureEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    evidence_kind: Literal["runner_owned_typed_failure"] = "runner_owned_typed_failure"
    job_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    failure_observation: TypedFailureObservation
    expected_terminal_input: Literal[False] = False
    caller_selected_evidence_subtype: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evidence(self) -> AuthenticatedTypedFailureEvidence:
        if (
            self.job_id != self.failure_observation.job_id
            or self.invocation_id != self.failure_observation.invocation_id
            or self.evidence_id
            != identity(
                self,
                "evidence_id",
                "fresh_repaired_authenticated_typed_failure_evidence:",
            )
        ):
            raise ValueError("authenticated typed failure evidence differs")
        return self


class AuthenticDispatcherBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    runner_observation_binding_id: str = Field(min_length=1)
    source_v195_terminal_registry_id: str = Field(min_length=1)
    dispatcher_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_kinds: tuple[str, ...] = OUTER_TERMINAL_KINDS
    terminal_policy_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    dispatcher_input: Literal["AuthenticatedTypedFailureEvidence"] = (
        "AuthenticatedTypedFailureEvidence"
    )
    authority_ledger_match_required: Literal[True] = True
    terminal_from_observation_not_subtype: Literal[True] = True
    terminal_kind_input_allowed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> AuthenticDispatcherBinding:
        if (
            self.terminal_kinds != OUTER_TERMINAL_KINDS
            or len(set(self.terminal_policy_ids)) != 8
            or self.binding_id
            != identity(
                self,
                "binding_id",
                "fresh_repaired_authentic_typed_failure_dispatcher_binding:",
            )
        ):
            raise ValueError("v26.214 authentic Dispatcher Binding differs")
        return self


class PersistenceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    source_v213_persistence_binding_id: str = Field(min_length=1)
    persistence_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_dispatch_rederivation_required: Literal[True] = True
    authority_ledger_revalidation_required: Literal[True] = True
    observation_embedded_in_raw: Literal[True] = True
    raw_before_result_required: Literal[True] = True
    durable_no_replace_required: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> PersistenceBinding:
        if self.binding_id != identity(
            self, "binding_id", "fresh_repaired_authentic_typed_failure_persistence_binding:"
        ):
            raise ValueError("v26.214 persistence Binding differs")
        return self


class ConsumerBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    exact_v211_authorization_id: str = Field(min_length=1)
    exact_v209_manifest_id: str = Field(min_length=1)
    source_v212_consumption_contract_id: str = Field(min_length=1)
    source_v212_run_start_contract_id: str = Field(min_length=1)
    runner_observation_binding_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    persistence_binding_id: str = Field(min_length=1)
    execute_preflight_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    one_entry_function: Literal["FailureTerminalizingConsumer.execute_preflight"] = (
        "FailureTerminalizingConsumer.execute_preflight"
    )
    invocation_terminal_branch_persisted_in_consumer: Literal[True] = True
    caller_evidence_subtype_allowed: Literal[False] = False
    current_v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ConsumerBinding:
        if self.binding_id != identity(
            self, "binding_id", "fresh_repaired_typed_failure_terminalizing_consumer_binding:"
        ):
            raise ValueError("v26.214 consumer Binding differs")
        return self


class CompositionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    v213_freeze_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    runner_observation_binding_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    persistence_binding_id: str = Field(min_length=1)
    exact_sequence: tuple[str, ...] = (
        "authorization_guard",
        "durable_preflight_consumption_receipt",
        "durable_run_start_receipt",
        "credential_and_factory_gate",
        "actual_runner_invocation",
        "runner_catches_typed_exception",
        "runner_constructs_failure_observation",
        "consumer_terminal_branch",
        "dispatcher_verifies_authority_and_record",
        "persist_raw_result_trace_outcome_checkpoint",
    )
    build_level_failure_join_forbidden: Literal[True] = True
    caller_terminal_forbidden: Literal[True] = True
    caller_evidence_subtype_forbidden: Literal[True] = True
    current_v211_authorization_consumed: Literal[False] = False
    new_online_authorization_created: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CompositionContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_repaired_typed_failure_single_consumer_composition_contract:",
        ):
            raise ValueError("v26.214 Composition Contract differs")
        return self


class DerivedTerminalDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    terminal_kind: str = Field(min_length=1)
    terminal_policy_id: str = Field(min_length=1)
    caught_exception_class: str = Field(min_length=1)
    exception_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivation_rule: Literal[
        "authority_bound_exception_class_and_invocation_terminal_agreement"
    ] = "authority_bound_exception_class_and_invocation_terminal_agreement"
    terminal_label_was_input: Literal[False] = False
    evidence_subtype_selected_terminal: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> DerivedTerminalDecision:
        if self.terminal_kind not in OUTER_TERMINAL_KINDS or self.decision_id != identity(
            self, "decision_id", "fresh_repaired_authentic_typed_failure_terminal_decision:"
        ):
            raise ValueError("v26.214 derived terminal Decision differs")
        return self


class PersistedEvidenceDescriptor(FrozenModel):
    descriptor_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
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
            self.terminal_kind not in OUTER_TERMINAL_KINDS
            or self.persistence_sequence != ("raw", "result", "trace", "outcome", "checkpoint")
            or len(
                {self.raw_id, self.result_id, self.trace_id, self.outcome_id, self.checkpoint_id}
            )
            != 5
            or self.descriptor_id
            != identity(
                self,
                "descriptor_id",
                "finance_v26_214_persisted_typed_failure_descriptor:",
            )
        ):
            raise ValueError("v26.214 persisted Descriptor differs")
        return self


class FailureTerminalControl(FrozenModel):
    control_id: str = Field(min_length=1)
    expected_terminal: str = Field(min_length=1)
    failure_observation: TypedFailureObservation
    evidence: AuthenticatedTypedFailureEvidence
    decision: DerivedTerminalDecision
    persistence: PersistedEvidenceDescriptor
    expected_terminal_used_only_after_dispatch: Literal[True] = True
    expected_terminal_passed_to_runner: Literal[False] = False
    expected_terminal_passed_to_dispatcher: Literal[False] = False
    expected_terminal_passed_to_writer: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> FailureTerminalControl:
        if (
            self.expected_terminal not in OUTER_TERMINAL_KINDS
            or self.failure_observation.observation_id
            != self.evidence.failure_observation.observation_id
            or self.evidence.evidence_id != self.decision.evidence_id
            or self.decision.terminal_kind != self.expected_terminal
            or self.persistence.decision_id != self.decision.decision_id
            or self.control_id
            != identity(self, "control_id", "finance_v26_214_typed_failure_terminal_control:")
        ):
            raise ValueError("v26.214 typed failure control differs")
        return self


class FailureExecutionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    consumption_receipt_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    controls: tuple[FailureTerminalControl, ...] = Field(min_length=8, max_length=8)
    actual_runner_invocation_count: Literal[8] = 8
    runner_catch_observation_count: Literal[8] = 8
    terminal_branch_count: Literal[8] = 8
    exact_terminal_match_count: Literal[8] = 8
    persisted_layer_count: Literal[40] = 40
    distinct_exception_class_count: Literal[8] = 8
    distinct_terminal_count: Literal[8] = 8
    caller_selected_evidence_subtype_count: Literal[0] = 0
    build_level_failure_join_count: Literal[0] = 0
    exception_escape_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FailureExecutionAudit:
        if (
            tuple(item.expected_terminal for item in self.controls) != OUTER_TERMINAL_KINDS
            or len({item.failure_observation.invocation_id for item in self.controls}) != 8
            or len({item.failure_observation.caught_exception_class for item in self.controls}) != 8
            or self.audit_id
            != identity(
                self, "audit_id", "finance_v26_214_single_consumer_failure_execution_audit:"
            )
        ):
            raise ValueError("v26.214 failure execution Audit differs")
        return self


class NegativeControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    rejected: Literal[True] = True
    rejected_before_raw_write: Literal[True] = True
    fully_rehashed: Literal[True] = True
    fully_rehashed_downstream_layer_ids: tuple[str, ...] = Field(min_length=5, max_length=5)
    rejection_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> NegativeControl:
        if len(set(self.fully_rehashed_downstream_layer_ids)) != 5 or self.control_id != identity(
            self, "control_id", "finance_v26_214_typed_failure_provenance_control:"
        ):
            raise ValueError("v26.214 provenance control differs")
        return self


class NegativeControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    controls: tuple[NegativeControl, ...] = Field(min_length=4, max_length=4)
    rejected_count: Literal[4] = 4
    accepted_count: Literal[0] = 0
    fully_rehashed_attack_count: Literal[4] = 4
    fully_rehashed_downstream_layer_identity_count: Literal[20] = 20
    raw_write_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> NegativeControlAudit:
        expected = {
            "instrument_record_as_provider_identity",
            "provider_identity_record_as_transport",
            "exception_reason_hash_replaced",
            "cross_job_failure_observation_substituted",
        }
        if {item.control_name for item in self.controls} != expected or self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_214_typed_failure_provenance_negative_control_audit:",
        ):
            raise ValueError("v26.214 negative-control Audit differs")
        return self


class ScopeBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v213_freeze_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
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
        if self.audit_id != identity(self, "audit_id", "finance_v26_214_scope_boundary_audit:"):
            raise ValueError("v26.214 scope boundary Audit differs")
        return self


class GateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> GateResult:
        if self.gate_id != identity(self, "gate_id", "finance_v26_214_gate:"):
            raise ValueError("v26.214 Gate identity differs")
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
            self, "evaluation_id", "finance_v26_214_gate_evaluation:"
        ):
            raise ValueError("v26.214 Gate Evaluation differs")
        return self


class Decision(FrozenModel):
    decision_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_outer_typed_exception_observation_authenticity_and_single_consumer_"
        "failure_terminalization_preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    external_authorization_id: str = Field(min_length=1)
    v213_freeze_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    execution_audit_id: str = Field(min_length=1)
    negative_control_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> Decision:
        if self.decision_id != identity(
            self, "decision_id", "finance_v26_214_typed_failure_authenticity_decision:"
        ):
            raise ValueError("v26.214 Decision differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    status: Literal["PASSED_PREFLIGHT_ONLINE_EXECUTION_BLOCKED"] = (
        "PASSED_PREFLIGHT_ONLINE_EXECUTION_BLOCKED"
    )
    next_stage: Literal[
        "fresh_repaired_outer_typed_exception_observation_authenticity_and_single_consumer_"
        "failure_terminalization_preflight_independent_audit_only"
    ] = NEXT_STAGE
    provider_execution_authorized: Literal[False] = False
    new_online_authorization_required_after_independent_audit: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> Transition:
        if self.transition_id != identity(self, "transition_id", "finance_v26_214_transition:"):
            raise ValueError("v26.214 Transition differs")
        return self


class Report(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v213_freeze_id: str = Field(min_length=1)
    runner_observation_binding_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    execution_audit_id: str = Field(min_length=1)
    negative_control_audit_id: str = Field(min_length=1)
    scope_boundary_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_outer_typed_exception_observation_authenticity_and_single_consumer_"
        "failure_terminalization_preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    current_v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> Report:
        if self.report_id != identity(
            self, "report_id", "finance_v26_214_typed_failure_authenticity_report:"
        ):
            raise ValueError("v26.214 Report differs")
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
            raise ValueError("v26.214 Artifact Manifest geometry differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_214_artifact_root:",
        )
        if self.artifact_root != expected_root or self.manifest_id != identity(
            self, "manifest_id", "finance_v26_214_artifact_manifest:"
        ):
            raise ValueError("v26.214 Artifact Root or Manifest differs")
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
        prefix="finance_v26_214_artifact_root:",
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
            prefix="finance_v26_214_artifact_manifest:",
        ),
    )
