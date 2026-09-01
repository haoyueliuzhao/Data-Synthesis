from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task import fresh_artifact_backed_outcome_authority as authority
from trusted_synthesis.experiments.vtdo_experiment import (
    json_explicit_authoritative_execution_kernel as execution_kernel,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_models as kernel_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_explicit_prompt_contract_preflight as v192,
)
from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_artifact_backed_terminal_to_outcome_integration.v1"
AUTHORIZED_STAGE: Final = (
    "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_only"
)

ReachableTerminalKind = Literal[
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
]
ControlPhase = Literal["primary_action", "correction_action", "final"]
ObservedExceptionType = Literal[
    "ProviderNoPayloadError",
    "ProviderTransportError",
    "PrivacyProjectionRejected",
    "ResourceBudgetError",
    "InstrumentIntegrityError",
    "ProviderIdentityIntegrityError",
    "ThinkingIntegrityError",
    "UsageIntegrityError",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


def _make(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: _identity(provisional, field, prefix)}, **values)


def _canonical_bytes(value: BaseModel) -> bytes:
    return json.dumps(
        value.model_dump(mode="json", warnings=False),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class ExternalTerminalOutcomeRepairAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    audit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_byte_count: int = Field(gt=0)
    audit_decision: Literal[
        "v26_196_negative_audit_accepted_terminal_to_outcome_integration_repair_only"
    ]
    consumed_stage: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_only"
    ] = AUTHORIZED_STAGE
    source_transition_id: str = Field(min_length=1)
    provider_calls_authorized: Literal[False] = False
    online_execution_authorized: Literal[False] = False
    source_task_or_manifest_change_authorized: Literal[False] = False
    six_outcome_contract_semantic_change_authorized: Literal[False] = False
    qa_change_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalTerminalOutcomeRepairAuthorization:
        if self.authorization_id != _identity(
            self,
            "authorization_id",
            "finance_v26_197_external_repair_authorization:",
        ):
            raise ValueError("terminal integration external authorization identity differs")
        return self


class AuthorizationAdmission(FrozenModel):
    admission_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    audit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    consumed_stage: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_only"
    ] = AUTHORIZED_STAGE
    provider_execution_requested: Literal[False] = False
    credential_lookup_permitted: Literal[False] = False
    admitted_before_client_construction: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_admission(self) -> AuthorizationAdmission:
        if self.admission_id != _identity(
            self,
            "admission_id",
            "terminal_outcome_precredential_authorization_admission:",
        ):
            raise ValueError("terminal integration authorization admission identity differs")
        return self


class PrecredentialAuthorizationGuard:
    """Exact external-parent admission that runs before any client construction."""

    def admit(
        self,
        *,
        authorization: object | None,
        authorization_bytes: bytes | None,
        provider_execution_requested: bool,
    ) -> AuthorizationAdmission:
        if type(authorization) is not ExternalTerminalOutcomeRepairAuthorization:
            raise ValueError("external authorization parent type differs")
        assert isinstance(authorization, ExternalTerminalOutcomeRepairAuthorization)
        strict = ExternalTerminalOutcomeRepairAuthorization.model_validate(
            authorization.model_dump(mode="python", warnings=False)
        )
        if authorization_bytes is None:
            raise ValueError("external authorization bytes are missing")
        if (
            len(authorization_bytes) != strict.audit_byte_count
            or _sha256(authorization_bytes) != strict.audit_sha256
        ):
            raise ValueError("external authorization bytes differ")
        if provider_execution_requested:
            raise ValueError("repair-preflight authorization forbids Provider execution")
        return cast(
            AuthorizationAdmission,
            _make(
                AuthorizationAdmission,
                {
                    "authorization_id": strict.authorization_id,
                    "audit_sha256": strict.audit_sha256,
                },
                field="admission_id",
                prefix="terminal_outcome_precredential_authorization_admission:",
            ),
        )


class TerminalOutcomeIntegrationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    predecessor_execution_contract_id: str = Field(min_length=1)
    predecessor_runner_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    raw_descriptor_contract_id: str = Field(min_length=1)
    result_descriptor_contract_id: str = Field(min_length=1)
    attempt_trace_contract_id: str = Field(min_length=1)
    outcome_row_contract_id: str = Field(min_length=1)
    evaluator_contract_id: str = Field(min_length=1)
    reachable_terminal_count: Literal[16] = 16
    excluded_terminal_count: Literal[2] = 2
    kernel_owned_dispatcher_required: Literal[True] = True
    caller_supplied_terminal_forbidden: Literal[True] = True
    fresh_writer_required: Literal[True] = True
    raw_before_result_required: Literal[True] = True
    fixture_complete_forbidden: Literal[True] = True
    external_authorization_before_client_required: Literal[True] = True
    predecessor_execution_identity_reused: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> TerminalOutcomeIntegrationContract:
        six = (
            self.terminal_registry_id,
            self.raw_descriptor_contract_id,
            self.result_descriptor_contract_id,
            self.attempt_trace_contract_id,
            self.outcome_row_contract_id,
            self.evaluator_contract_id,
        )
        if len(set(six)) != 6:
            raise ValueError("six fresh authority identities are not distinct")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "fresh_terminal_to_outcome_integration_contract:",
        ):
            raise ValueError("terminal integration Contract identity differs")
        return self


class DispatchControlPayload(FrozenModel):
    payload_id: str = Field(min_length=1)
    phase: ControlPhase
    response_abi_valid: bool | None = None
    action_reference_valid: bool | None = None
    state_precondition_valid: bool | None = None
    action_accepted: bool | None = None
    correction_invoked: bool = False
    correction_response_abi_valid: bool | None = None
    correction_action_reference_valid: bool | None = None
    correction_state_precondition_valid: bool | None = None
    correction_accepted: bool | None = None
    task_completion: bool | None = None
    task_verifier_invoked: bool = False
    final_response_abi_valid: bool | None = None
    final_result_id: str | None = None
    final_base_valid: bool | None = None
    final_mechanism_qualified: bool | None = None
    final_qualified_valid: bool | None = None
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_payload(self) -> DispatchControlPayload:
        if self.phase == "final":
            if self.task_completion is not True or self.final_response_abi_valid is None:
                raise ValueError("final control payload lacks completion and ABI evidence")
            factors = (
                self.final_result_id,
                self.final_base_valid,
                self.final_mechanism_qualified,
                self.final_qualified_valid,
            )
            if self.final_response_abi_valid:
                if not self.task_verifier_invoked or any(item is None for item in factors):
                    raise ValueError("valid Final control lacks factorized Verifier evidence")
                if self.final_qualified_valid != bool(
                    self.final_base_valid and self.final_mechanism_qualified
                ):
                    raise ValueError("Final control Qualified value is not its conjunction")
            elif self.task_verifier_invoked or any(item is not None for item in factors):
                raise ValueError("invalid Final control carries Verifier factors")
        elif self.phase == "primary_action":
            if self.response_abi_valid is None:
                raise ValueError("primary control lacks response ABI evidence")
            if not self.response_abi_valid and any(
                item is not None
                for item in (
                    self.action_reference_valid,
                    self.state_precondition_valid,
                    self.action_accepted,
                )
            ):
                raise ValueError("ABI-invalid primary control carries downstream evidence")
            if self.response_abi_valid and self.action_reference_valid is None:
                raise ValueError("ABI-valid primary control lacks Action-reference evidence")
        else:
            if (
                self.response_abi_valid is not True
                or self.action_reference_valid is not True
                or self.state_precondition_valid is not False
                or self.action_accepted is not False
                or not self.correction_invoked
                or self.correction_response_abi_valid is None
            ):
                raise ValueError("correction control lacks exact first-rejection evidence")
            if self.correction_response_abi_valid and (
                self.correction_action_reference_valid is None
            ):
                raise ValueError("ABI-valid correction lacks Action-reference evidence")
        if self.payload_id != _identity(
            self,
            "payload_id",
            "terminal_dispatch_control_payload:",
        ):
            raise ValueError("terminal dispatch control payload identity differs")
        return self


class TerminalExecutionEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    authorization_admission_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    component_index: int = Field(ge=0, le=3)
    component_key: str = Field(min_length=1)
    invocation_receipt_ids: tuple[str, ...] = Field(max_length=1)
    public_payload: DispatchControlPayload | None = None
    public_payload_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    exception_type: ObservedExceptionType | None = None
    exception_reason_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evidence(self) -> TerminalExecutionEvidence:
        if (self.public_payload is None) == (self.exception_type is None):
            raise ValueError("terminal evidence must contain exactly one observed source")
        if self.public_payload is not None:
            expected_sha = _sha256(_canonical_bytes(self.public_payload))
            if self.public_payload_sha256 != expected_sha or self.exception_reason_sha256:
                raise ValueError("terminal public-payload evidence differs")
        elif self.public_payload_sha256 or self.exception_reason_sha256 is None:
            raise ValueError("terminal exception evidence differs")
        if self.evidence_id != _identity(
            self,
            "evidence_id",
            "production_terminal_execution_evidence:",
        ):
            raise ValueError("terminal execution evidence identity differs")
        return self


class TerminalDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    terminal_policy_id: str = Field(min_length=1)
    execution_evidence_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    terminal_kind: ReachableTerminalKind
    terminal_projection_count: Literal[1] = 1
    caller_supplied_terminal: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> TerminalDecision:
        if self.decision_id != _identity(
            self,
            "decision_id",
            "authoritative_terminal_dispatch_decision:",
        ):
            raise ValueError("terminal dispatch decision identity differs")
        return self


class ProviderNoPayloadError(RuntimeError):
    pass


class ProviderTransportError(RuntimeError):
    pass


class ResourceBudgetError(RuntimeError):
    pass


class InstrumentIntegrityError(RuntimeError):
    pass


class ProviderIdentityIntegrityError(RuntimeError):
    pass


class ThinkingIntegrityError(RuntimeError):
    pass


class UsageIntegrityError(RuntimeError):
    pass


_OBSERVED_EXCEPTIONS: Final = (
    ProviderNoPayloadError,
    ProviderTransportError,
    ResourceBudgetError,
    InstrumentIntegrityError,
    ProviderIdentityIntegrityError,
    ThinkingIntegrityError,
    UsageIntegrityError,
)


class AuthoritativeTerminalDispatcher:
    def __init__(
        self,
        *,
        integration_contract: TerminalOutcomeIntegrationContract,
        terminal_registry: authority.FreshTerminalRegistry,
    ) -> None:
        self._integration_contract = integration_contract
        self._registry = terminal_registry
        if terminal_registry.registry_id != integration_contract.terminal_registry_id:
            raise ValueError("dispatcher crosses its exact terminal Registry")
        self._policies = {item.terminal_kind: item for item in terminal_registry.policies}

    def _decision(
        self,
        evidence: TerminalExecutionEvidence,
        value: ReachableTerminalKind,
    ) -> TerminalDecision:
        policy = self._policies[value]
        if policy.registration_status != "reachable":
            raise ValueError("dispatcher selected a non-reachable terminal policy")
        return cast(
            TerminalDecision,
            _make(
                TerminalDecision,
                {
                    "integration_contract_id": self._integration_contract.contract_id,
                    "terminal_registry_id": self._registry.registry_id,
                    "terminal_policy_id": policy.policy_id,
                    "execution_evidence_id": evidence.evidence_id,
                    "job_id": evidence.job_id,
                    "terminal_kind": value,
                },
                field="decision_id",
                prefix="authoritative_terminal_dispatch_decision:",
            ),
        )

    def dispatch(self, evidence: TerminalExecutionEvidence) -> TerminalDecision:
        if evidence.integration_contract_id != self._integration_contract.contract_id:
            raise ValueError("dispatcher evidence crosses its integration Contract")
        if evidence.exception_type == "ProviderNoPayloadError":
            return self._decision(evidence, "provider_failure_no_payload")
        if evidence.exception_type == "ProviderTransportError":
            return self._decision(evidence, "provider_transport_failure")
        if evidence.exception_type == "PrivacyProjectionRejected":
            return self._decision(evidence, "privacy_rejection")
        if evidence.exception_type == "ResourceBudgetError":
            return self._decision(evidence, "resource_budget_exhausted")
        if evidence.exception_type == "InstrumentIntegrityError":
            return self._decision(evidence, "instrument_failure")
        if evidence.exception_type == "ProviderIdentityIntegrityError":
            return self._decision(evidence, "provider_identity_failure")
        if evidence.exception_type == "ThinkingIntegrityError":
            return self._decision(evidence, "thinking_integrity_failure")
        if evidence.exception_type == "UsageIntegrityError":
            return self._decision(evidence, "usage_integrity_failure")
        payload = evidence.public_payload
        if payload is None:
            raise ValueError("dispatcher lacks a public payload or typed exception")
        if payload.phase == "primary_action":
            if payload.response_abi_valid is False:
                return self._decision(evidence, "first_response_abi_invalid")
            if payload.action_reference_valid is False:
                return self._decision(evidence, "first_action_reference_invalid")
        elif payload.phase == "correction_action":
            if payload.correction_response_abi_valid is False:
                return self._decision(evidence, "correction_response_abi_invalid")
            if payload.correction_action_reference_valid is False:
                return self._decision(evidence, "correction_action_reference_invalid")
            if payload.correction_state_precondition_valid is False:
                return self._decision(evidence, "correction_attempt_typed_invalid")
        elif payload.final_response_abi_valid is False:
            return self._decision(evidence, "final_response_abi_invalid")
        elif payload.final_qualified_valid is True:
            return self._decision(evidence, "completed_qualified")
        elif payload.task_verifier_invoked:
            return self._decision(evidence, "completed_invalid")
        raise ValueError("execution evidence does not determine one registered terminal")


class IntegratedComponentAttemptEvidence(FrozenModel):
    attempt_id: str = Field(min_length=1)
    component_index: int = Field(ge=0, le=3)
    component_key: str = Field(min_length=1)
    reached_state_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    response_source: Literal["zero_provider_dispatch_control"] = "zero_provider_dispatch_control"
    first_response_abi_valid: bool | None
    first_action_reference_valid: bool | None
    first_action_state_precondition_valid: bool | None
    first_action_accepted: bool | None
    correction_invoked: bool
    correction_response_abi_valid: bool | None
    correction_action_reference_valid: bool | None
    correction_state_precondition_valid: bool | None
    correction_accepted: bool | None
    committed: bool
    terminal: bool
    invocation_receipt_ids: tuple[str, ...] = Field(max_length=1)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_attempt(self) -> IntegratedComponentAttemptEvidence:
        if self.correction_invoked != (self.correction_response_abi_valid is not None):
            raise ValueError("integrated correction evidence differs")
        if self.committed and self.terminal:
            raise ValueError("integrated attempt cannot commit and terminalize together")
        if self.attempt_id != _identity(
            self,
            "attempt_id",
            "fresh_kernel_component_attempt:",
        ):
            raise ValueError("integrated Component attempt identity differs")
        return self


class IntegratedFreshRawExecutionPayload(FrozenModel):
    payload_id: str = Field(min_length=1)
    evidence_kind: Literal["scripted_preflight_control"] = "scripted_preflight_control"
    job_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    authorization_admission_id: str = Field(min_length=1)
    terminal_kind: ReachableTerminalKind
    component_attempts: tuple[IntegratedComponentAttemptEvidence, ...] = Field(
        min_length=1,
        max_length=4,
    )
    terminal_evidence: TerminalExecutionEvidence
    terminal_decision: TerminalDecision
    terminal_evidence_id: str = Field(min_length=1)
    provider_artifact_ids: tuple[str, ...] = ()
    transport_artifact_ids: tuple[str, ...] = ()
    model_response_present: Literal[False] = False
    token_usage: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_payload(self) -> IntegratedFreshRawExecutionPayload:
        if tuple(item.component_index for item in self.component_attempts) != tuple(
            range(len(self.component_attempts))
        ):
            raise ValueError("integrated Raw attempts are not contiguous")
        if (
            self.terminal_evidence_id != self.terminal_evidence.evidence_id
            or self.terminal_decision.execution_evidence_id != self.terminal_evidence.evidence_id
            or self.terminal_decision.terminal_kind != self.terminal_kind
            or self.terminal_decision.integration_contract_id != self.integration_contract_id
            or self.terminal_evidence.integration_contract_id != self.integration_contract_id
            or self.terminal_evidence.authorization_admission_id != self.authorization_admission_id
            or self.terminal_evidence.job_id != self.job_id
            or self.terminal_decision.job_id != self.job_id
        ):
            raise ValueError("integrated Raw crosses terminal evidence or decision")
        if self.payload_id != _identity(
            self,
            "payload_id",
            "fresh_kernel_raw_execution_payload:",
        ):
            raise ValueError("integrated Raw payload identity differs")
        return self


class IntegratedFreshJobBoundAttemptTrace(FrozenModel):
    trace_id: str = Field(min_length=1)
    trace_contract_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    authorization_admission_id: str = Field(min_length=1)
    evidence_kind: Literal["scripted_preflight_control"] = "scripted_preflight_control"
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    terminal_kind: ReachableTerminalKind
    terminal_evidence_id: str = Field(min_length=1)
    terminal_decision_id: str = Field(min_length=1)
    component_attempts: tuple[IntegratedComponentAttemptEvidence, ...] = Field(
        min_length=1,
        max_length=4,
    )
    failure_loci: tuple[authority.FreshFailureLocus, ...] = ()
    correction_count: int = Field(ge=0, le=4)
    terminal_projection_count: Literal[1] = 1
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_trace(self) -> IntegratedFreshJobBoundAttemptTrace:
        if self.correction_count != sum(
            int(item.correction_invoked) for item in self.component_attempts
        ):
            raise ValueError("integrated AttemptTrace correction count differs")
        if self.trace_id != _identity(
            self,
            "trace_id",
            "fresh_kernel_job_bound_attempt_trace:",
        ):
            raise ValueError("integrated AttemptTrace identity differs")
        return self


class IntegratedFreshEvidenceBundle(FrozenModel):
    raw: authority.FreshRawExecutionDescriptor
    result: authority.FreshJobResultDescriptor
    trace: IntegratedFreshJobBoundAttemptTrace
    row: authority.FreshOutcomeRow


class OutcomeArtifactWriter(Protocol):
    def write_raw(self, *, job_id: str, payload: Any) -> tuple[str, int]: ...

    def write_result(self, *, job_id: str, payload: Any) -> tuple[str, int]: ...

    def assert_closed(self) -> None: ...


def _attempt_from_evidence(
    evidence: TerminalExecutionEvidence,
    decision: TerminalDecision,
) -> IntegratedComponentAttemptEvidence:
    payload = evidence.public_payload
    values: dict[str, Any] = {
        "component_index": evidence.component_index,
        "component_key": evidence.component_key,
        "reached_state_token": canonical_hash(
            {
                "job_id": evidence.job_id,
                "component_index": evidence.component_index,
                "component_key": evidence.component_key,
                "integration_contract_id": evidence.integration_contract_id,
            },
            prefix="integrated_terminal_control_state:",
        ).split(":", 1)[1][:24],
        "first_response_abi_valid": None,
        "first_action_reference_valid": None,
        "first_action_state_precondition_valid": None,
        "first_action_accepted": None,
        "correction_invoked": False,
        "correction_response_abi_valid": None,
        "correction_action_reference_valid": None,
        "correction_state_precondition_valid": None,
        "correction_accepted": None,
        "committed": False,
        "terminal": True,
        "invocation_receipt_ids": evidence.invocation_receipt_ids,
    }
    if payload is not None and payload.phase in {"primary_action", "correction_action"}:
        values.update(
            {
                "first_response_abi_valid": payload.response_abi_valid,
                "first_action_reference_valid": payload.action_reference_valid,
                "first_action_state_precondition_valid": payload.state_precondition_valid,
                "first_action_accepted": payload.action_accepted,
                "correction_invoked": payload.correction_invoked,
                "correction_response_abi_valid": payload.correction_response_abi_valid,
                "correction_action_reference_valid": payload.correction_action_reference_valid,
                "correction_state_precondition_valid": (
                    payload.correction_state_precondition_valid
                ),
                "correction_accepted": payload.correction_accepted,
            }
        )
    elif payload is not None and payload.phase == "final":
        values.update(
            {
                "first_response_abi_valid": True,
                "first_action_reference_valid": True,
                "first_action_state_precondition_valid": True,
                "first_action_accepted": True,
                "committed": True,
                "terminal": False,
            }
        )
    if decision.terminal_kind in {"completed_qualified", "completed_invalid"}:
        values["committed"] = True
        values["terminal"] = False
    return cast(
        IntegratedComponentAttemptEvidence,
        _make(
            IntegratedComponentAttemptEvidence,
            values,
            field="attempt_id",
            prefix="fresh_kernel_component_attempt:",
        ),
    )


def _terminal_validity(
    evidence: TerminalExecutionEvidence,
    decision: TerminalDecision,
) -> authority.FreshTerminalValidity:
    payload = evidence.public_payload
    values: dict[str, Any] = {
        "terminal_kind": decision.terminal_kind,
        "task_completion": None,
        "task_verifier_invoked": False,
        "final_response_abi_valid": None,
        "final_result_id": None,
        "final_base_valid": None,
        "final_mechanism_qualified": None,
        "final_qualified_valid": None,
    }
    if payload is not None and payload.phase == "final":
        values.update(
            {
                "task_completion": payload.task_completion,
                "task_verifier_invoked": payload.task_verifier_invoked,
                "final_response_abi_valid": payload.final_response_abi_valid,
                "final_result_id": payload.final_result_id,
                "final_base_valid": payload.final_base_valid,
                "final_mechanism_qualified": payload.final_mechanism_qualified,
                "final_qualified_valid": payload.final_qualified_valid,
            }
        )
    return cast(
        authority.FreshTerminalValidity,
        authority.make_identity_model(
            authority.FreshTerminalValidity,
            values,
            field="validity_id",
            prefix="fresh_kernel_terminal_validity:",
        ),
    )


_FAILURE_STAGE: Final[dict[ReachableTerminalKind, authority.FailureStage]] = {
    "completed_invalid": "base_answer",
    "first_response_abi_invalid": "action_abi",
    "correction_response_abi_invalid": "action_abi",
    "first_action_reference_invalid": "action_reference",
    "correction_action_reference_invalid": "action_reference",
    "correction_attempt_typed_invalid": "state_precondition",
    "final_response_abi_invalid": "final_abi",
    "provider_failure_no_payload": "provider",
    "provider_transport_failure": "transport",
    "privacy_rejection": "privacy",
    "resource_budget_exhausted": "resource",
    "instrument_failure": "instrument",
    "provider_identity_failure": "model_identity",
    "thinking_integrity_failure": "thinking",
    "usage_integrity_failure": "usage",
}


def _failure_loci(
    *,
    decision: TerminalDecision,
    evidence: TerminalExecutionEvidence,
    source_descriptor_id: str,
) -> tuple[authority.FreshFailureLocus, ...]:
    if decision.terminal_kind == "completed_qualified":
        return ()
    values = {
        "stage": _FAILURE_STAGE[decision.terminal_kind],
        "component_key": evidence.component_key,
        "attempt_index": 1
        if decision.terminal_kind.startswith("correction_")
        or decision.terminal_kind == "correction_attempt_typed_invalid"
        else 0,
        "reason_code": decision.terminal_kind,
        "source_descriptor_id": source_descriptor_id,
    }
    return (
        cast(
            authority.FreshFailureLocus,
            authority.make_identity_model(
                authority.FreshFailureLocus,
                values,
                field="locus_id",
                prefix="fresh_kernel_failure_locus:",
            ),
        ),
    )


class FreshOutcomeIntegratedExecutionKernel:
    """Successor Kernel: frozen invoke, evidence dispatch, then typed fresh persistence."""

    def __init__(
        self,
        *,
        authorization: object | None,
        authorization_bytes: bytes | None,
        integration_contract: TerminalOutcomeIntegrationContract,
        terminal_registry: authority.FreshTerminalRegistry,
        catalog: kernel_models.AuthoritativeRunnerPackageCatalog,
        manifest: kernel_models.AuthoritativeDevelopmentManifest,
        runner: kernel_models.AuthoritativeRunnerContract,
        execution: kernel_models.AuthoritativeExecutionContract,
        raw_contract: authority.FreshRawExecutionDescriptorContract,
        result_contract: authority.FreshJobResultDescriptorContract,
        trace_contract: authority.FreshJobBoundAttemptTraceContract,
        outcome_contract: authority.FreshOutcomeRowContract,
        evaluator_contract: authority.FreshExactEvidenceSetEvaluatorContract,
        prompt_contract: v192.JsonExplicitPromptContract,
        prompt_schema: v192.JsonExplicitPromptSchema,
        client_factory: Callable[[], execution_kernel.CertifiedKernelClient],
        kernel_writer_factory: Callable[[], execution_kernel.KernelJournalWriter],
        outcome_writer_factory: Callable[[], OutcomeArtifactWriter],
        provider_execution_requested: bool = False,
    ) -> None:
        admission = PrecredentialAuthorizationGuard().admit(
            authorization=authorization,
            authorization_bytes=authorization_bytes,
            provider_execution_requested=provider_execution_requested,
        )
        client = client_factory()
        kernel_writer = kernel_writer_factory()
        outcome_writer = outcome_writer_factory()
        if (
            integration_contract.authorization_id != admission.authorization_id
            or integration_contract.predecessor_execution_contract_id != execution.contract_id
            or integration_contract.predecessor_runner_id != runner.runner_id
            or integration_contract.manifest_id != manifest.manifest_id
            or integration_contract.package_catalog_id != catalog.catalog_id
            or integration_contract.terminal_registry_id != terminal_registry.registry_id
            or integration_contract.raw_descriptor_contract_id != raw_contract.contract_id
            or integration_contract.result_descriptor_contract_id != result_contract.contract_id
            or integration_contract.attempt_trace_contract_id != trace_contract.contract_id
            or integration_contract.outcome_row_contract_id != outcome_contract.contract_id
            or integration_contract.evaluator_contract_id != evaluator_contract.contract_id
        ):
            raise ValueError("integrated Kernel crosses frozen execution or Outcome parents")
        self._admission = admission
        self._integration_contract = integration_contract
        self._registry = terminal_registry
        self._catalog = catalog
        self._manifest = manifest
        self._runner = runner
        self._execution = execution
        self._raw_contract = raw_contract
        self._result_contract = result_contract
        self._trace_contract = trace_contract
        self._outcome_contract = outcome_contract
        self._outcome_writer = outcome_writer
        self._kernel = execution_kernel.AuthoritativeJsonExplicitExecutionKernel(
            execution_contract_id=execution.contract_id,
            runner_id=runner.runner_id,
            manifest_id=manifest.manifest_id,
            prompt_contract=prompt_contract,
            prompt_schema=prompt_schema,
            client=client,
            writer=kernel_writer,
        )
        self._dispatcher = AuthoritativeTerminalDispatcher(
            integration_contract=integration_contract,
            terminal_registry=terminal_registry,
        )
        self._jobs = {item.job_id: item for item in manifest.jobs}
        self._packages = {item.package_id: item for item in catalog.packages}
        self._evidence: dict[str, TerminalExecutionEvidence] = {}
        self._decisions: dict[str, TerminalDecision] = {}
        self._bundles: dict[str, IntegratedFreshEvidenceBundle] = {}

    @property
    def authorization_admission(self) -> AuthorizationAdmission:
        return self._admission

    @property
    def decisions(self) -> tuple[TerminalDecision, ...]:
        return tuple(self._decisions[key] for key in sorted(self._decisions))

    def _evidence_from_exception(
        self,
        *,
        job_id: str,
        component_index: int,
        component_key: str,
        exception_type: ObservedExceptionType,
        reason: str,
        receipt_ids: tuple[str, ...],
    ) -> TerminalExecutionEvidence:
        return cast(
            TerminalExecutionEvidence,
            _make(
                TerminalExecutionEvidence,
                {
                    "integration_contract_id": self._integration_contract.contract_id,
                    "authorization_admission_id": self._admission.admission_id,
                    "job_id": job_id,
                    "component_index": component_index,
                    "component_key": component_key,
                    "invocation_receipt_ids": receipt_ids,
                    "exception_type": exception_type,
                    "exception_reason_sha256": _sha256(reason.encode("utf-8")),
                },
                field="evidence_id",
                prefix="production_terminal_execution_evidence:",
            ),
        )

    def invoke(
        self,
        *,
        job_id: str,
        logical_request_index: int,
        prompt_kind: execution_kernel.PromptKind,
        public_attempt_phase: execution_kernel.PublicAttemptPhase,
        core: dict[str, Any] | str,
    ) -> TerminalDecision:
        if job_id in self._evidence:
            raise ValueError("integrated Job already has terminal execution evidence")
        job = self._jobs.get(job_id)
        if job is None:
            raise ValueError("integrated invoke Job is absent from exact Manifest")
        package = self._packages[job.package_id]
        component_index = 0
        component_key = package.topological_component_keys[component_index]
        receipts_before = len(self._kernel.receipts)
        payload: dict[str, Any] | None = None
        caught: Exception | None = None
        try:
            payload = self._kernel.invoke(
                job_id=job_id,
                logical_request_index=logical_request_index,
                prompt_kind=prompt_kind,
                public_attempt_phase=public_attempt_phase,
                core=core,
            )
        except _OBSERVED_EXCEPTIONS as error:
            caught = error
        except ValueError as error:
            if str(error).startswith("privacy response rejected:"):
                caught = error
            else:
                raise
        receipts_after = self._kernel.receipts
        receipt_ids = tuple(item.receipt_id for item in receipts_after[receipts_before:])
        if caught is not None:
            observed_type: ObservedExceptionType
            if isinstance(caught, ProviderNoPayloadError):
                observed_type = "ProviderNoPayloadError"
            elif isinstance(caught, ProviderTransportError):
                observed_type = "ProviderTransportError"
            elif isinstance(caught, ResourceBudgetError):
                observed_type = "ResourceBudgetError"
            elif isinstance(caught, InstrumentIntegrityError):
                observed_type = "InstrumentIntegrityError"
            elif isinstance(caught, ProviderIdentityIntegrityError):
                observed_type = "ProviderIdentityIntegrityError"
            elif isinstance(caught, ThinkingIntegrityError):
                observed_type = "ThinkingIntegrityError"
            elif isinstance(caught, UsageIntegrityError):
                observed_type = "UsageIntegrityError"
            else:
                observed_type = "PrivacyProjectionRejected"
            evidence = self._evidence_from_exception(
                job_id=job_id,
                component_index=component_index,
                component_key=component_key,
                exception_type=observed_type,
                reason=str(caught),
                receipt_ids=receipt_ids,
            )
        else:
            assert payload is not None
            public_payload = DispatchControlPayload.model_validate(payload)
            evidence = cast(
                TerminalExecutionEvidence,
                _make(
                    TerminalExecutionEvidence,
                    {
                        "integration_contract_id": self._integration_contract.contract_id,
                        "authorization_admission_id": self._admission.admission_id,
                        "job_id": job_id,
                        "component_index": component_index,
                        "component_key": component_key,
                        "invocation_receipt_ids": receipt_ids,
                        "public_payload": public_payload,
                        "public_payload_sha256": _sha256(_canonical_bytes(public_payload)),
                    },
                    field="evidence_id",
                    prefix="production_terminal_execution_evidence:",
                ),
            )
        decision = self._dispatcher.dispatch(evidence)
        self._evidence[job_id] = evidence
        self._decisions[job_id] = decision
        return decision

    def complete_job(self, *, job_id: str) -> IntegratedFreshEvidenceBundle:
        if job_id in self._bundles:
            raise ValueError("integrated Job already completed")
        evidence = self._evidence.get(job_id)
        decision = self._decisions.get(job_id)
        job = self._jobs.get(job_id)
        if evidence is None or decision is None or job is None:
            raise ValueError("integrated completion lacks dispatched execution evidence")
        attempt = _attempt_from_evidence(evidence, decision)
        raw_payload = cast(
            IntegratedFreshRawExecutionPayload,
            _make(
                IntegratedFreshRawExecutionPayload,
                {
                    "job_id": job_id,
                    "execution_contract_id": self._execution.contract_id,
                    "terminal_registry_id": self._registry.registry_id,
                    "integration_contract_id": self._integration_contract.contract_id,
                    "authorization_admission_id": self._admission.admission_id,
                    "terminal_kind": decision.terminal_kind,
                    "component_attempts": (attempt,),
                    "terminal_evidence": evidence,
                    "terminal_decision": decision,
                    "terminal_evidence_id": evidence.evidence_id,
                },
                field="payload_id",
                prefix="fresh_kernel_raw_execution_payload:",
            ),
        )
        raw_sha, raw_bytes = self._outcome_writer.write_raw(
            job_id=job_id,
            payload=raw_payload,
        )
        raw = cast(
            authority.FreshRawExecutionDescriptor,
            authority.make_identity_model(
                authority.FreshRawExecutionDescriptor,
                {
                    "descriptor_contract_id": self._raw_contract.contract_id,
                    "evidence_kind": "scripted_preflight_control",
                    "job_id": job_id,
                    "manifest_id": self._manifest.manifest_id,
                    "runner_id": self._runner.runner_id,
                    "execution_contract_id": self._execution.contract_id,
                    "package_id": job.package_id,
                    "replica_index": job.replica_index,
                    "raw_namespace": job.raw_namespace,
                    "artifact_relative_path": authority.expected_raw_artifact_filename(job),
                    "artifact_sha256": raw_sha,
                    "artifact_byte_count": raw_bytes,
                    "payload_id": raw_payload.payload_id,
                },
                field="raw_execution_id",
                prefix="fresh_kernel_raw_execution_descriptor:",
            ),
        )
        validity = _terminal_validity(evidence, decision)
        result_payload = cast(
            authority.FreshJobResultPayload,
            authority.make_identity_model(
                authority.FreshJobResultPayload,
                {
                    "evidence_kind": "scripted_preflight_control",
                    "job_id": job_id,
                    "raw_execution_id": raw.raw_execution_id,
                    "execution_contract_id": self._execution.contract_id,
                    "terminal_registry_id": self._registry.registry_id,
                    "terminal_kind": decision.terminal_kind,
                    "validity": validity,
                },
                field="payload_id",
                prefix="fresh_kernel_job_result_payload:",
            ),
        )
        result_sha, result_bytes = self._outcome_writer.write_result(
            job_id=job_id,
            payload=result_payload,
        )
        result = cast(
            authority.FreshJobResultDescriptor,
            authority.make_identity_model(
                authority.FreshJobResultDescriptor,
                {
                    "descriptor_contract_id": self._result_contract.contract_id,
                    "evidence_kind": "scripted_preflight_control",
                    "job_id": job_id,
                    "raw_execution_id": raw.raw_execution_id,
                    "execution_contract_id": self._execution.contract_id,
                    "result_namespace": job.result_namespace,
                    "artifact_relative_path": authority.expected_result_artifact_filename(job),
                    "artifact_sha256": result_sha,
                    "artifact_byte_count": result_bytes,
                    "payload_id": result_payload.payload_id,
                },
                field="result_id",
                prefix="fresh_kernel_job_result_descriptor:",
            ),
        )
        loci = _failure_loci(
            decision=decision,
            evidence=evidence,
            source_descriptor_id=raw.raw_execution_id,
        )
        trace = cast(
            IntegratedFreshJobBoundAttemptTrace,
            _make(
                IntegratedFreshJobBoundAttemptTrace,
                {
                    "trace_contract_id": self._trace_contract.contract_id,
                    "integration_contract_id": self._integration_contract.contract_id,
                    "authorization_admission_id": self._admission.admission_id,
                    "job_id": job_id,
                    "raw_execution_id": raw.raw_execution_id,
                    "result_id": result.result_id,
                    "terminal_kind": decision.terminal_kind,
                    "terminal_evidence_id": evidence.evidence_id,
                    "terminal_decision_id": decision.decision_id,
                    "component_attempts": (attempt,),
                    "failure_loci": loci,
                    "correction_count": int(attempt.correction_invoked),
                },
                field="trace_id",
                prefix="fresh_kernel_job_bound_attempt_trace:",
            ),
        )
        row = cast(
            authority.FreshOutcomeRow,
            authority.make_identity_model(
                authority.FreshOutcomeRow,
                {
                    "outcome_contract_id": self._outcome_contract.contract_id,
                    "evidence_kind": "scripted_preflight_control",
                    "job_id": job_id,
                    "manifest_id": self._manifest.manifest_id,
                    "runner_id": self._runner.runner_id,
                    "execution_contract_id": self._execution.contract_id,
                    "package_id": job.package_id,
                    "replica_index": job.replica_index,
                    "raw_execution_id": raw.raw_execution_id,
                    "result_id": result.result_id,
                    "trace_id": trace.trace_id,
                    "terminal_registry_id": self._registry.registry_id,
                    "terminal_kind": decision.terminal_kind,
                    "correction_count": trace.correction_count,
                    "task_completion": validity.task_completion,
                    "task_verifier_invoked": validity.task_verifier_invoked,
                    "final_result_id": validity.final_result_id,
                    "final_base_valid": validity.final_base_valid,
                    "final_mechanism_qualified": validity.final_mechanism_qualified,
                    "final_qualified_valid": validity.final_qualified_valid,
                    "failure_locus_ids": tuple(item.locus_id for item in loci),
                    "formal_empirical_row": False,
                },
                field="row_id",
                prefix="fresh_kernel_outcome_row:",
            ),
        )
        bundle = IntegratedFreshEvidenceBundle(raw=raw, result=result, trace=trace, row=row)
        self._bundles[job_id] = bundle
        return bundle

    def assert_closed(self) -> None:
        self._kernel.assert_closed()
        self._outcome_writer.assert_closed()
        if set(self._evidence) != set(self._bundles):
            raise ValueError("integrated terminal evidence has an orphan Job")


def validate_integrated_bundle(
    *,
    artifact_root: Path,
    bundle: IntegratedFreshEvidenceBundle,
    integration_contract: TerminalOutcomeIntegrationContract,
    admission: AuthorizationAdmission,
    registry: authority.FreshTerminalRegistry,
    job: kernel_models.AuthoritativeDevelopmentJob,
    manifest: kernel_models.AuthoritativeDevelopmentManifest,
    runner: kernel_models.AuthoritativeRunnerContract,
    execution: kernel_models.AuthoritativeExecutionContract,
    raw_contract: authority.FreshRawExecutionDescriptorContract,
    result_contract: authority.FreshJobResultDescriptorContract,
    trace_contract: authority.FreshJobBoundAttemptTraceContract,
    outcome_contract: authority.FreshOutcomeRowContract,
) -> None:
    bundle = IntegratedFreshEvidenceBundle.model_validate(
        bundle.model_dump(mode="python", warnings=False)
    )
    raw_path = artifact_root / bundle.raw.artifact_relative_path
    result_path = artifact_root / bundle.result.artifact_relative_path
    raw_bytes = raw_path.read_bytes()
    result_bytes = result_path.read_bytes()
    if (
        len(raw_bytes) != bundle.raw.artifact_byte_count
        or _sha256(raw_bytes) != bundle.raw.artifact_sha256
        or len(result_bytes) != bundle.result.artifact_byte_count
        or _sha256(result_bytes) != bundle.result.artifact_sha256
    ):
        raise ValueError("integrated descriptor does not bind actual Raw/Result bytes")
    raw_payload = IntegratedFreshRawExecutionPayload.model_validate(json.loads(raw_bytes))
    result_payload = authority.FreshJobResultPayload.model_validate(json.loads(result_bytes))
    if raw_bytes != _canonical_bytes(raw_payload) or result_bytes != _canonical_bytes(
        result_payload
    ):
        raise ValueError("integrated Raw/Result bytes are not canonical typed payloads")
    if (
        bundle.raw.descriptor_contract_id != raw_contract.contract_id
        or bundle.result.descriptor_contract_id != result_contract.contract_id
        or bundle.trace.trace_contract_id != trace_contract.contract_id
        or bundle.trace.integration_contract_id != integration_contract.contract_id
        or bundle.trace.authorization_admission_id != admission.admission_id
        or bundle.row.outcome_contract_id != outcome_contract.contract_id
        or bundle.raw.job_id != job.job_id
        or bundle.result.job_id != job.job_id
        or bundle.trace.job_id != job.job_id
        or bundle.row.job_id != job.job_id
        or bundle.raw.manifest_id != manifest.manifest_id
        or bundle.raw.runner_id != runner.runner_id
        or bundle.raw.execution_contract_id != execution.contract_id
        or bundle.result.raw_execution_id != bundle.raw.raw_execution_id
        or bundle.trace.raw_execution_id != bundle.raw.raw_execution_id
        or bundle.trace.result_id != bundle.result.result_id
        or bundle.row.trace_id != bundle.trace.trace_id
        or raw_payload.payload_id != bundle.raw.payload_id
        or result_payload.payload_id != bundle.result.payload_id
        or raw_payload.integration_contract_id != integration_contract.contract_id
        or raw_payload.authorization_admission_id != admission.admission_id
    ):
        raise ValueError("integrated evidence DAG crosses an exact parent")
    dispatcher = AuthoritativeTerminalDispatcher(
        integration_contract=integration_contract,
        terminal_registry=registry,
    )
    reconstructed_decision = dispatcher.dispatch(raw_payload.terminal_evidence)
    if reconstructed_decision != raw_payload.terminal_decision:
        raise ValueError("integrated terminal decision is not reconstructed from Raw evidence")
    expected_attempt = _attempt_from_evidence(
        raw_payload.terminal_evidence,
        reconstructed_decision,
    )
    expected_validity = _terminal_validity(
        raw_payload.terminal_evidence,
        reconstructed_decision,
    )
    expected_loci = _failure_loci(
        decision=reconstructed_decision,
        evidence=raw_payload.terminal_evidence,
        source_descriptor_id=bundle.raw.raw_execution_id,
    )
    if (
        raw_payload.component_attempts != (expected_attempt,)
        or result_payload.validity != expected_validity
        or bundle.trace.component_attempts != (expected_attempt,)
        or bundle.trace.failure_loci != expected_loci
        or bundle.row.failure_locus_ids != tuple(item.locus_id for item in expected_loci)
        or bundle.row.terminal_kind != reconstructed_decision.terminal_kind
        or bundle.row.formal_empirical_row
    ):
        raise ValueError("integrated Trace or Outcome is not reconstructed from artifacts")


__all__ = [
    "AuthorizationAdmission",
    "AuthoritativeTerminalDispatcher",
    "DispatchControlPayload",
    "ExternalTerminalOutcomeRepairAuthorization",
    "FreshOutcomeIntegratedExecutionKernel",
    "InstrumentIntegrityError",
    "IntegratedComponentAttemptEvidence",
    "IntegratedFreshEvidenceBundle",
    "IntegratedFreshJobBoundAttemptTrace",
    "IntegratedFreshRawExecutionPayload",
    "PrecredentialAuthorizationGuard",
    "ProviderIdentityIntegrityError",
    "ProviderNoPayloadError",
    "ProviderTransportError",
    "ReachableTerminalKind",
    "ResourceBudgetError",
    "TerminalDecision",
    "TerminalExecutionEvidence",
    "TerminalOutcomeIntegrationContract",
    "ThinkingIntegrityError",
    "UsageIntegrityError",
    "validate_integrated_bundle",
]
