from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_final_grammar_privacy_rematerialization as static_stage,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_execution as predecessor,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_exact_final_response_grammar import (
    ExactFinalResponsePayload,
    ExactFinalResponseRejection,
    FinalResponseHostEnvelope,
    make_final_response_host_envelope,
    parse_exact_final_response_payload,
    render_exact_final_primary_prompt,
    render_exact_final_rescue_prompt,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    CanonicalActionCommit,
    CanonicalActionProposal,
    PublicSemanticRejectionObservation,
    SemanticActionState,
    build_semantic_action_state,
    evaluate_canonical_action_proposal,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    SemanticActionResponseRejection,
    parse_exact_canonical_action_payload,
    render_exact_canonical_action_abi_rescue_prompt,
    render_exact_canonical_action_prompt,
    render_exact_canonical_action_semantic_recovery_prompt,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import CompletionProjection
from trusted_synthesis.runtime.tools import AgentToolObservation

PublicAttemptPhase = Literal["primary", "abi_rescue", "semantic_recovery"]
AttemptDisposition = Literal[
    "usable",
    "model_result_failure",
    "completion_failure",
    "provider_transport_failure",
    "typed_budget_no_call",
    "instrument_failure",
]
TerminalDisposition = Literal[
    "completed",
    "model_result",
    "completion_unusable",
    "provider_transport_failure",
    "typed_budget_no_call",
    "instrument_failure",
]
PayloadProjectionStatus = Literal[
    "validated_public_payload",
    "privacy_rejected",
    "provider_failure_no_payload",
]
RUNNER_RUN_ID: Final = static_stage.PROSPECTIVE_RUNNER_RUN_ID
EXECUTION_RUN_ID: Final = static_stage.PROSPECTIVE_EXECUTION_RUN_ID


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class PrivacyFirstRunnerContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_static_contract_id: str = Field(min_length=1)
    predecessor_manifest_id: str = Field(min_length=1)
    semantic_action_protocol_id: str = static_stage.EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_response_grammar_id: str = static_stage.EXPECTED_ACTION_GRAMMAR_ID
    exact_final_response_grammar_id: str = Field(min_length=1)
    final_response_protocol: Literal["prospective_exact_final_response.v1"] = (
        "prospective_exact_final_response.v1"
    )
    candidate_space_authority_audit_id: str = static_stage.EXPECTED_CANDIDATE_AUDIT_ID
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    exact_job_denominator: Literal[32] = 32
    runner_run_id: str = RUNNER_RUN_ID
    execution_run_id: str = EXECUTION_RUN_ID
    action_response_fields: tuple[str, str, str, str] = (
        "state_id",
        "action_id",
        "decision_kind",
        "protocol",
    )
    final_response_fields: tuple[str, str] = ("answer", "rationale_summary")
    exact_request_completion_bound_tokens: Literal[16384] = 16384
    provider_accounting_margin_tokens: Literal[1] = 1
    rollout_upper_bound_tokens: Literal[400000] = 400000
    maximum_primary_stage_one_requests: Literal[11] = 11
    maximum_stage_one_provider_calls: Literal[12] = 12
    maximum_abi_rescue_calls: Literal[1] = 1
    maximum_semantic_recovery_calls: Literal[1] = 1
    abi_and_semantic_recovery_counters_separate: Literal[True] = True
    first_choice_failure_retained_after_recovery: Literal[True] = True
    stage_two_provider_call_upper_bound: Literal[0] = 0
    stage_two_reverses_same_action_id: Literal[True] = True
    privacy_redacted_envelope_persisted_before_payload_validation: Literal[True] = True
    public_payload_projection_is_separate_artifact: Literal[True] = True
    invalid_payload_content_persisted: Literal[False] = False
    invalid_payload_key_persisted: Literal[False] = False
    raw_only_recovery: Literal[True] = True
    orphan_provider_artifact_fails_closed: Literal[True] = True
    private_reasoning_persistence_allowed: Literal[False] = False
    runner_implemented: Literal[True] = True
    empirical_execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_first_runner_contract.v1"] = (
        "finance_v26_privacy_first_runner_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> PrivacyFirstRunnerContract:
        if (
            self.maximum_stage_one_provider_calls
            != self.maximum_primary_stage_one_requests + self.maximum_abi_rescue_calls
        ):
            raise ValueError("v26.123 Runner call bound changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_privacy_first_runner_contract:"
        ):
            raise ValueError("v26.123 Runner Contract identity changed")
        return self


class PrivacyFirstDynamicRequestCertificate(FrozenModel):
    certificate_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    request_kind: legacy.StageOneRequestKind
    public_attempt_phase: PublicAttemptPhase
    provider_attempt_phase: legacy.StageOneAttemptPhase
    primary_prompt_sha256: str = Field(min_length=64, max_length=64)
    request_prompt_sha256: str = Field(min_length=64, max_length=64)
    public_state_id: str | None = None
    final_response_host_envelope_id: str | None = None
    prompt_utf8_bytes: int = Field(gt=0, le=60000)
    abi_rescue_count_before: int = Field(ge=0, le=1)
    semantic_recovery_count_before: int = Field(ge=0, le=1)
    prompt_rendered_before_certificate: Literal[True] = True
    candidate_order_bound_before_provider: Literal[True] = True
    final_host_envelope_bound_before_provider: Literal[True] = True
    provider_calls_before_certificate: Literal[0] = 0
    stage_two_provider_calls_before_certificate: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_first_dynamic_request_certificate.v1"] = (
        "finance_v26_privacy_first_dynamic_request_certificate.v1"
    )

    @model_validator(mode="after")
    def validate_certificate(self) -> PrivacyFirstDynamicRequestCertificate:
        if self.public_attempt_phase == "abi_rescue":
            if self.provider_attempt_phase != "rescue":
                raise ValueError("v26.123 ABI Rescue did not bind Provider rescue phase")
        elif self.provider_attempt_phase != "primary":
            raise ValueError("v26.123 primary or Semantic Recovery bound rescue phase")
        if self.public_state_id is None:
            raise ValueError("v26.123 request certificate lacks its public state")
        final = self.request_kind == "final_answer"
        if final != (self.final_response_host_envelope_id is not None):
            raise ValueError("v26.123 Final request and Host Envelope binding diverged")
        if final and self.public_state_id is None:
            raise ValueError("v26.123 Final request does not bind its terminal public state")
        if self.certificate_id != _identity(
            self,
            "certificate_id",
            "finance_v26_privacy_first_dynamic_request_certificate:",
        ):
            raise ValueError("v26.123 dynamic request-certificate identity changed")
        return self


class PreparedPrivacyFirstRequest(FrozenModel):
    preparation_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    request_kind: legacy.StageOneRequestKind
    public_attempt_phase: PublicAttemptPhase
    primary_prompt: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    public_state_id: str | None = None
    final_response_host_envelope: FinalResponseHostEnvelope | None = None
    dynamic_certificate: PrivacyFirstDynamicRequestCertificate | None
    request_binding_certificate: legacy.StageOneRequestBindingCertificate
    resource_certificate: predecessor.ActionResourceCertificate
    provider_invocation_authorized: bool
    provider_calls_before_preparation: Literal[0] = 0

    @model_validator(mode="after")
    def validate_preparation(self) -> PreparedPrivacyFirstRequest:
        digest = legacy.sha256_text(self.prompt)
        provider_phase: legacy.StageOneAttemptPhase = (
            "rescue" if self.public_attempt_phase == "abi_rescue" else "primary"
        )
        if (
            self.request_binding_certificate.prompt_sha256 != digest
            or self.resource_certificate.request_prompt_sha256 != digest
            or (
                self.dynamic_certificate is not None
                and self.dynamic_certificate.request_prompt_sha256 != digest
            )
        ):
            raise ValueError("v26.123 prepared Prompt binding changed")
        if (
            self.request_binding_certificate.request_kind != self.request_kind
            or self.request_binding_certificate.phase != provider_phase
            or self.resource_certificate.request_kind != self.request_kind
            or self.resource_certificate.public_attempt_phase != self.public_attempt_phase
        ):
            raise ValueError("v26.123 prepared request kind or phase binding changed")
        if self.dynamic_certificate is not None:
            dynamic = self.dynamic_certificate
            expected_envelope_id = (
                self.final_response_host_envelope.envelope_id
                if self.final_response_host_envelope is not None
                else None
            )
            if (
                dynamic.logical_request_index != self.logical_request_index
                or dynamic.request_kind != self.request_kind
                or dynamic.public_attempt_phase != self.public_attempt_phase
                or dynamic.provider_attempt_phase != provider_phase
                or dynamic.primary_prompt_sha256 != legacy.sha256_text(self.primary_prompt)
                or dynamic.public_state_id != self.public_state_id
                or dynamic.final_response_host_envelope_id != expected_envelope_id
            ):
                raise ValueError("v26.123 prepared dynamic-certificate binding changed")
        if self.request_kind == "final_answer":
            if (
                self.final_response_host_envelope is None
                or self.public_state_id != self.final_response_host_envelope.terminal_state_id
            ):
                raise ValueError("v26.123 prepared Final request lacks its Host Envelope")
        elif self.final_response_host_envelope is not None:
            raise ValueError("v26.123 semantic request carries a Final Host Envelope")
        if self.provider_invocation_authorized != bool(
            self.dynamic_certificate is not None
            and self.resource_certificate.provider_call_permitted
        ):
            raise ValueError("v26.123 invocation authorization changed")
        if self.preparation_id != _identity(
            self, "preparation_id", "finance_v26_prepared_privacy_first_request:"
        ):
            raise ValueError("v26.123 prepared request identity changed")
        return self


class PrivacyFirstProviderEnvelope(FrozenModel):
    envelope_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    provider_call_index: int = Field(ge=0)
    request_kind: legacy.StageOneRequestKind
    public_attempt_phase: PublicAttemptPhase
    prompt_sha256: str = Field(min_length=64, max_length=64)
    dynamic_certificate: PrivacyFirstDynamicRequestCertificate
    request_binding_certificate: legacy.StageOneRequestBindingCertificate
    resource_certificate_id: str = Field(min_length=1)
    final_response_host_envelope_id: str | None = None
    provider_telemetry: legacy.ModelCallTelemetry
    failure_artifact: legacy.ProspectiveThinkingFailureArtifact | None = None
    public_content_hash: str | None = None
    public_content_length: int | None = Field(default=None, ge=0)
    payload_content_persisted: Literal[False] = False
    persisted_before_payload_validation: Literal[True] = True
    payload_validation_required_for_persistence: Literal[False] = False
    stage_two_provider_call_count: Literal[0] = 0
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    raw_request_body_persisted: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_first_provider_envelope.v1"] = (
        "finance_v26_privacy_first_provider_envelope.v1"
    )

    @model_validator(mode="after")
    def validate_envelope(self) -> PrivacyFirstProviderEnvelope:
        if (
            self.provider_telemetry.request_hash != self.prompt_sha256
            or self.dynamic_certificate.request_prompt_sha256 != self.prompt_sha256
            or self.request_binding_certificate.prompt_sha256 != self.prompt_sha256
            or self.public_content_hash != self.provider_telemetry.response_hash
            or self.public_content_length != self.provider_telemetry.response_content_length
            or self.final_response_host_envelope_id
            != self.dynamic_certificate.final_response_host_envelope_id
        ):
            raise ValueError("v26.123 privacy-first Provider Envelope binding changed")
        if (
            self.dynamic_certificate.runner_contract_id != self.runner_contract_id
            or self.dynamic_certificate.job_id != self.job_id
            or self.dynamic_certificate.logical_request_index != self.logical_request_index
            or self.dynamic_certificate.request_kind != self.request_kind
            or self.dynamic_certificate.public_attempt_phase != self.public_attempt_phase
            or self.request_binding_certificate.request_kind != self.request_kind
            or self.request_binding_certificate.phase
            != self.dynamic_certificate.provider_attempt_phase
        ):
            raise ValueError("v26.123 Provider Envelope parent binding changed")
        if self.envelope_id != _identity(
            self, "envelope_id", "finance_v26_privacy_first_provider_envelope:"
        ):
            raise ValueError("v26.123 privacy-first Provider Envelope identity changed")
        return self


class PublicPayloadProjection(FrozenModel):
    projection_id: str = Field(min_length=1)
    provider_envelope_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    provider_call_index: int = Field(ge=0)
    request_kind: legacy.StageOneRequestKind
    projection_status: PayloadProjectionStatus
    response_payload: dict[str, Any] | None = None
    failure_family: str | None = None
    failure_subtype: str | None = None
    validation_performed_after_envelope_persistence: Literal[True] = True
    invalid_payload_content_persisted: Literal[False] = False
    invalid_payload_key_persisted: Literal[False] = False
    private_reasoning_content_persisted: Literal[False] = False
    schema_version: Literal["finance_v26_public_payload_projection.v1"] = (
        "finance_v26_public_payload_projection.v1"
    )

    @model_validator(mode="after")
    def validate_projection(self) -> PublicPayloadProjection:
        if self.projection_status == "validated_public_payload":
            if (
                self.response_payload is None
                or self.failure_family is not None
                or self.failure_subtype is not None
                or legacy.contains_private_reasoning(self.response_payload)
            ):
                raise ValueError("v26.123 validated public Projection is not public")
        elif self.response_payload is not None:
            raise ValueError("v26.123 rejected or absent Payload content was persisted")
        if self.projection_status == "privacy_rejected":
            if (
                self.failure_family != "payload_privacy_failure"
                or self.failure_subtype != "public_payload_omitted_after_privacy_rejection"
            ):
                raise ValueError("v26.123 privacy Projection exposes non-neutral detail")
        elif self.projection_status == "provider_failure_no_payload":
            if self.failure_family != "provider_or_completion_failure":
                raise ValueError("v26.123 no-Payload Projection classification changed")
        if self.projection_id != _identity(
            self, "projection_id", "finance_v26_public_payload_projection:"
        ):
            raise ValueError("v26.123 public Payload Projection identity changed")
        return self


def validate_provider_artifact_pair(
    envelope: PrivacyFirstProviderEnvelope,
    projection: PublicPayloadProjection,
) -> None:
    if (
        projection.provider_envelope_id != envelope.envelope_id
        or projection.job_id != envelope.job_id
        or projection.provider_call_index != envelope.provider_call_index
        or projection.request_kind != envelope.request_kind
    ):
        raise ValueError("v26.123 Envelope/Projection parent binding changed")


class PrivacyFirstAttempt(FrozenModel):
    attempt_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    provider_call_index: int | None = Field(default=None, ge=0)
    request_kind: legacy.StageOneRequestKind
    public_attempt_phase: PublicAttemptPhase
    prompt_sha256: str = Field(min_length=64, max_length=64)
    prompt_utf8_bytes: int = Field(gt=0)
    dynamic_certificate_id: str | None = None
    request_binding_certificate_id: str | None = None
    resource_certificate_id: str | None = None
    final_response_host_envelope_id: str | None = None
    provider_call_made: bool
    response_payload_present: bool
    payload_projection_status: PayloadProjectionStatus | None = None
    exact_four_field_action_payload: bool = False
    exact_two_field_final_payload: bool = False
    failure_family: str | None = None
    failure_subtype: str | None = None
    completion_failure_type: str | None = None
    disposition: AttemptDisposition
    error: str | None = None
    previous_response_content_reused: Literal[False] = False
    private_reasoning_reused: Literal[False] = False
    host_semantic_action_answer_or_rationale_inserted: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_first_attempt.v1"] = (
        "finance_v26_privacy_first_attempt.v1"
    )

    @model_validator(mode="after")
    def validate_attempt(self) -> PrivacyFirstAttempt:
        if self.provider_call_made != (self.provider_call_index is not None):
            raise ValueError("v26.123 Provider-call accounting changed")
        if self.provider_call_made and not all(
            (
                self.dynamic_certificate_id,
                self.request_binding_certificate_id,
                self.resource_certificate_id,
                self.payload_projection_status,
            )
        ):
            raise ValueError("v26.123 Provider call lacks a certificate or Projection")
        if (self.request_kind == "final_answer") != (
            self.final_response_host_envelope_id is not None
        ):
            raise ValueError("v26.123 Final attempt Host Envelope binding changed")
        if self.attempt_id != _identity(self, "attempt_id", "finance_v26_privacy_first_attempt:"):
            raise ValueError("v26.123 attempt identity changed")
        return self


class PrivacyFirstCompletedResult(FrozenModel):
    result_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    answer: dict[str, Any] = Field(min_length=1)
    rationale_summary: str = Field(min_length=1)
    cited_evidence_ids: tuple[str, ...] = Field(min_length=1)
    final_attempt_id: str = Field(min_length=1)
    final_response_host_envelope: FinalResponseHostEnvelope
    host_answer_or_rationale_inserted: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_first_completed_result.v1"] = (
        "finance_v26_privacy_first_completed_result.v1"
    )

    @model_validator(mode="after")
    def validate_result(self) -> PrivacyFirstCompletedResult:
        if self.cited_evidence_ids != tuple(sorted(set(self.cited_evidence_ids))):
            raise ValueError("v26.123 cited Evidence is not canonical")
        if self.result_id != _identity(
            self, "result_id", "finance_v26_privacy_first_completed_result:"
        ):
            raise ValueError("v26.123 completed-result identity changed")
        return self


class PrivacyFirstRawExecution(FrozenModel):
    artifact_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    job: static_stage.FinalGrammarJob
    operational_record_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    path_audit_id: str = Field(min_length=1)
    provider_envelope_artifacts: tuple[legacy.RawFileDescriptor, ...]
    public_payload_projection_artifacts: tuple[legacy.RawFileDescriptor, ...]
    provider_telemetry: tuple[legacy.ModelCallTelemetry, ...]
    attempts: tuple[PrivacyFirstAttempt, ...] = Field(min_length=1)
    semantic_choices: tuple[predecessor.SemanticChoiceRecord, ...]
    commits: tuple[predecessor.SemanticActionCommitRecord, ...]
    semantic_rejections: tuple[PublicSemanticRejectionObservation, ...]
    observations: tuple[AgentToolObservation, ...]
    completed_result: PrivacyFirstCompletedResult | None = None
    terminal_disposition: TerminalDisposition
    terminal_failure_type: str | None = None
    execution_error: str | None = None
    cumulative_provider_tokens: int = Field(ge=0)
    stage_one_provider_call_count: int = Field(ge=0, le=12)
    public_payload_projection_count: int = Field(ge=0, le=12)
    privacy_rejected_payload_count: int = Field(ge=0, le=12)
    stage_two_provider_call_count: Literal[0] = 0
    abi_rescue_attempt_count: int = Field(ge=0, le=1)
    semantic_recovery_attempt_count: int = Field(ge=0, le=1)
    first_choice_semantic_rejection_count: int = Field(ge=0, le=1)
    model_discovery_call_count: Literal[0] = 0
    telemetry_envelopes_persisted_before_payload_validation: Literal[True] = True
    captured_before_verifier_scoring: Literal[True] = True
    private_reasoning_content_persisted: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_first_raw_execution.v1"] = (
        "finance_v26_privacy_first_raw_execution.v1"
    )

    @model_validator(mode="after")
    def validate_execution(self) -> PrivacyFirstRawExecution:
        if (
            self.stage_one_provider_call_count != len(self.provider_telemetry)
            or len(self.provider_envelope_artifacts) != self.stage_one_provider_call_count
            or len(self.public_payload_projection_artifacts) != self.stage_one_provider_call_count
            or self.public_payload_projection_count != self.stage_one_provider_call_count
            or self.abi_rescue_attempt_count
            != sum(item.public_attempt_phase == "abi_rescue" for item in self.attempts)
            or self.semantic_recovery_attempt_count
            != sum(
                item.public_attempt_phase == "semantic_recovery" for item in self.semantic_choices
            )
            or self.first_choice_semantic_rejection_count
            != sum(
                item.public_attempt_phase == "primary" and not item.semantic_accepted
                for item in self.semantic_choices
            )
            or (self.completed_result is not None) != (self.terminal_disposition == "completed")
        ):
            raise ValueError("v26.123 Raw denominator changed")
        if self.artifact_id != _identity(
            self, "artifact_id", "finance_v26_privacy_first_raw_execution:"
        ):
            raise ValueError("v26.123 Raw identity changed")
        return self


class InstrumentContractError(RuntimeError):
    pass


class BudgetNoCallError(RuntimeError):
    pass


class PayloadPrivacyProjectionError(ValueError):
    family: str = "payload_privacy_failure"
    subtype: str = "public_payload_omitted_after_privacy_rejection"


class _AttemptOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    attempt: PrivacyFirstAttempt
    payload: dict[str, Any] | None = None
    proposal: CanonicalActionProposal | None = None
    final_payload: ExactFinalResponsePayload | None = None


def make_privacy_first_runner_contract(
    static: static_stage.FinalGrammarStaticInputs,
) -> PrivacyFirstRunnerContract:
    values = {
        "predecessor_static_contract_id": static.contract.contract_id,
        "predecessor_manifest_id": static.manifest.manifest_id,
        "exact_final_response_grammar_id": static.final_grammar.grammar_id,
        "stage_one_profile_id": static.stage_one.profile_id,
        "stage_two_profile_id": static.stage_two.profile_id,
        "resource_contract_id": static.resource.contract_id,
    }
    provisional = PrivacyFirstRunnerContract.model_construct(contract_id="pending", **values)
    return PrivacyFirstRunnerContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_privacy_first_runner_contract:",
        ),
        **values,
    )


def privacy_first_runtime_binding(
    static: static_stage.FinalGrammarStaticInputs,
    job: static_stage.FinalGrammarJob,
) -> legacy.RuntimeBinding:
    old_jobs = {item.job_id: item for item in static.predecessor.manifest.jobs}
    old_job = old_jobs[job.predecessor_job_id]
    binding = predecessor.semantic_action_runtime_binding(static.predecessor, old_job)
    task = next(item for item in static.tasks if item.task_package_id == job.task_package_id)
    path = next(item for item in static.paths if item.path_audit_id == job.path_audit_id)
    if (
        task.predecessor_task_package_id != old_job.task_package_id
        or path.predecessor_path_audit_id != old_job.path_audit_id
        or task.operational_record_id != binding.record.record_id
        or path.compiler_trajectory_id != binding.compiler_trajectory.trajectory_id
        or job.path_strategy_id != binding.source_registered_path.path_strategy_id
    ):
        raise ValueError("v26.123 Runtime binding changed")
    return binding


def raw_execution_path(output_dir: Path, job: static_stage.FinalGrammarJob) -> Path:
    return output_dir / "raw_execution" / f"{job.job_id.rsplit(':', 1)[-1]}.json"


def provider_envelope_path(
    output_dir: Path,
    job: static_stage.FinalGrammarJob,
    call_index: int,
) -> Path:
    return (
        output_dir
        / "raw_provider_envelopes"
        / job.job_id.rsplit(":", 1)[-1]
        / f"call_{call_index:03d}.json"
    )


def payload_projection_path(
    output_dir: Path,
    job: static_stage.FinalGrammarJob,
    call_index: int,
) -> Path:
    return (
        output_dir
        / "public_payload_projections"
        / job.job_id.rsplit(":", 1)[-1]
        / f"call_{call_index:03d}.json"
    )


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded)
    temporary.replace(path)


def _descriptor(path: Path, output_dir: Path) -> legacy.RawFileDescriptor:
    return legacy.RawFileDescriptor(
        relative_path=str(path.resolve().relative_to(output_dir.resolve())),
        sha256=legacy.sha256_file(path),
        byte_count=path.stat().st_size,
    )


class PrivacyFirstJournaledClient:
    def __init__(
        self,
        delegate: predecessor.StageOneClient,
        *,
        runner_contract: PrivacyFirstRunnerContract,
        resource_contract: static_stage.FinalGrammarResourceContract,
        job: static_stage.FinalGrammarJob,
        output_dir: Path,
    ) -> None:
        legacy.require_stage_one_model_config(delegate.config)
        if (
            job.resource_contract_id != resource_contract.contract_id
            or runner_contract.resource_contract_id != resource_contract.contract_id
            or job.stage_one_profile_id != runner_contract.stage_one_profile_id
            or job.stage_two_profile_id != runner_contract.stage_two_profile_id
            or job.exact_final_response_grammar_id
            != runner_contract.exact_final_response_grammar_id
        ):
            raise ValueError("v26.123 journal client differs from frozen Job route")
        self._delegate = delegate
        self._runner_contract = runner_contract
        self._resource = resource_contract
        self._job = job
        self._output_dir = output_dir
        self._resource_certificates: list[predecessor.ActionResourceCertificate] = []
        self._telemetry: list[legacy.ModelCallTelemetry] = []
        self._envelope_descriptors: list[legacy.RawFileDescriptor] = []
        self._projection_descriptors: list[legacy.RawFileDescriptor] = []
        self._projection_statuses: list[PayloadProjectionStatus] = []
        self._used_preparations: set[str] = set()
        self._cumulative_tokens = 0
        self._instrument_failures: set[str] = set()

    @property
    def provider_call_count(self) -> int:
        return len(self._telemetry)

    @property
    def cumulative_tokens(self) -> int:
        return self._cumulative_tokens

    @property
    def telemetry(self) -> tuple[legacy.ModelCallTelemetry, ...]:
        return tuple(self._telemetry)

    @property
    def envelope_descriptors(self) -> tuple[legacy.RawFileDescriptor, ...]:
        return tuple(self._envelope_descriptors)

    @property
    def projection_descriptors(self) -> tuple[legacy.RawFileDescriptor, ...]:
        return tuple(self._projection_descriptors)

    @property
    def projection_statuses(self) -> tuple[PayloadProjectionStatus, ...]:
        return tuple(self._projection_statuses)

    @property
    def instrument_failures(self) -> tuple[str, ...]:
        return tuple(sorted(self._instrument_failures))

    def _request_bound(self, prompt_bytes: int) -> int:
        return (
            prompt_bytes
            + self._resource.chat_envelope_tokens
            + self._resource.accounted_completion_bound_tokens
        )

    def _resource_certificate(
        self,
        prompt: str,
        *,
        request_kind: legacy.StageOneRequestKind,
        public_attempt_phase: PublicAttemptPhase,
        abi_rescue_available_before: bool,
        semantic_recovery_available_before: bool,
    ) -> predecessor.ActionResourceCertificate:
        prompt_bytes = len(prompt.encode("utf-8"))
        prompt_upper = prompt_bytes + self._resource.chat_envelope_tokens
        request_upper = prompt_upper + self._resource.accounted_completion_bound_tokens
        abi_prompt_bound = max(
            self._resource.qualified_maximum_action_abi_rescue_prompt_utf8_bytes,
            self._resource.qualified_maximum_final_rescue_prompt_utf8_bytes,
        )
        abi = (
            self._request_bound(abi_prompt_bound)
            if abi_rescue_available_before and public_attempt_phase != "abi_rescue"
            else 0
        )
        semantic = (
            self._request_bound(
                self._resource.qualified_maximum_semantic_recovery_prompt_utf8_bytes
            )
            if request_kind == "semantic_proposal"
            and semantic_recovery_available_before
            and public_attempt_phase != "semantic_recovery"
            else 0
        )
        final = (
            self._request_bound(self._resource.qualified_maximum_final_primary_prompt_utf8_bytes)
            if request_kind == "semantic_proposal"
            else 0
        )
        projected = self._cumulative_tokens + request_upper + abi + semantic + final
        denial: str | None = None
        if self.provider_call_count >= self._resource.maximum_stage_one_provider_calls:
            denial = "stage_one_request_count_exhausted"
        elif prompt_bytes > self._resource.prompt_upper_bound_bytes:
            denial = "oversized_prompt"
        elif self._cumulative_tokens + request_upper > self._resource.rollout_upper_bound_tokens:
            denial = "request_bound_exceeds_remaining_budget"
        elif projected > self._resource.rollout_upper_bound_tokens:
            denial = "required_reserve_not_available"
        values = {
            "resource_contract_id": self._resource.contract_id,
            "request_index": len(self._resource_certificates),
            "request_kind": request_kind,
            "public_attempt_phase": public_attempt_phase,
            "request_prompt_sha256": legacy.sha256_text(prompt),
            "prompt_utf8_bytes": prompt_bytes,
            "prompt_token_upper_bound": prompt_upper,
            "request_token_upper_bound": request_upper,
            "cumulative_provider_tokens_before": self._cumulative_tokens,
            "abi_rescue_reserve_tokens": abi,
            "semantic_recovery_reserve_tokens": semantic,
            "final_answer_reserve_tokens": final,
            "required_reserve_tokens": abi + semantic + final,
            "projected_upper_total": projected,
            "rollout_upper_bound_tokens": self._resource.rollout_upper_bound_tokens,
            "decision": "denied_no_call" if denial else "allowed",
            "denial_reason": denial,
            "provider_call_permitted": denial is None,
        }
        provisional = predecessor.ActionResourceCertificate.model_construct(
            certificate_id="pending", **values
        )
        return predecessor.ActionResourceCertificate(
            certificate_id=_identity(
                provisional,
                "certificate_id",
                "finance_v26_action_resource_certificate:",
            ),
            **values,
        )

    def prepare(
        self,
        *,
        logical_request_index: int,
        request_kind: legacy.StageOneRequestKind,
        public_attempt_phase: PublicAttemptPhase,
        primary_prompt: str,
        prompt: str,
        public_state_id: str | None,
        final_response_host_envelope: FinalResponseHostEnvelope | None,
        abi_rescue_count_before: int,
        semantic_recovery_count_before: int,
    ) -> PreparedPrivacyFirstRequest:
        if self._instrument_failures:
            raise InstrumentContractError("cannot prepare after an Instrument failure")
        provider_phase: legacy.StageOneAttemptPhase = (
            "rescue" if public_attempt_phase == "abi_rescue" else "primary"
        )
        request_binding = legacy.certify_stage_one_request_pre_call(
            config=self._delegate.config,
            prompt=prompt,
            request_kind=request_kind,
            phase=provider_phase,
        )
        resource = self._resource_certificate(
            prompt,
            request_kind=request_kind,
            public_attempt_phase=public_attempt_phase,
            abi_rescue_available_before=abi_rescue_count_before == 0,
            semantic_recovery_available_before=semantic_recovery_count_before == 0,
        )
        self._resource_certificates.append(resource)
        dynamic: PrivacyFirstDynamicRequestCertificate | None = None
        if resource.provider_call_permitted:
            values = {
                "runner_contract_id": self._runner_contract.contract_id,
                "job_id": self._job.job_id,
                "logical_request_index": logical_request_index,
                "request_kind": request_kind,
                "public_attempt_phase": public_attempt_phase,
                "provider_attempt_phase": provider_phase,
                "primary_prompt_sha256": legacy.sha256_text(primary_prompt),
                "request_prompt_sha256": legacy.sha256_text(prompt),
                "public_state_id": public_state_id,
                "final_response_host_envelope_id": (
                    final_response_host_envelope.envelope_id
                    if final_response_host_envelope is not None
                    else None
                ),
                "prompt_utf8_bytes": len(prompt.encode("utf-8")),
                "abi_rescue_count_before": abi_rescue_count_before,
                "semantic_recovery_count_before": semantic_recovery_count_before,
            }
            provisional = PrivacyFirstDynamicRequestCertificate.model_construct(
                certificate_id="pending", **values
            )
            dynamic = PrivacyFirstDynamicRequestCertificate(
                certificate_id=_identity(
                    provisional,
                    "certificate_id",
                    "finance_v26_privacy_first_dynamic_request_certificate:",
                ),
                **values,
            )
        values = {
            "logical_request_index": logical_request_index,
            "request_kind": request_kind,
            "public_attempt_phase": public_attempt_phase,
            "primary_prompt": primary_prompt,
            "prompt": prompt,
            "public_state_id": public_state_id,
            "final_response_host_envelope": final_response_host_envelope,
            "dynamic_certificate": dynamic,
            "request_binding_certificate": request_binding,
            "resource_certificate": resource,
            "provider_invocation_authorized": bool(
                dynamic is not None and resource.provider_call_permitted
            ),
        }
        provisional_request = PreparedPrivacyFirstRequest.model_construct(
            preparation_id="pending", **values
        )
        return PreparedPrivacyFirstRequest(
            preparation_id=_identity(
                provisional_request,
                "preparation_id",
                "finance_v26_prepared_privacy_first_request:",
            ),
            **values,
        )

    def _persist_envelope(
        self,
        *,
        prepared: PreparedPrivacyFirstRequest,
        telemetry: legacy.ModelCallTelemetry,
        failure_artifact: legacy.ProspectiveThinkingFailureArtifact | None,
    ) -> PrivacyFirstProviderEnvelope:
        if prepared.dynamic_certificate is None:
            raise ValueError("cannot persist an uncertified Provider call")
        call_index = len(self._telemetry)
        values = {
            "runner_contract_id": self._runner_contract.contract_id,
            "job_id": self._job.job_id,
            "logical_request_index": prepared.logical_request_index,
            "provider_call_index": call_index,
            "request_kind": prepared.request_kind,
            "public_attempt_phase": prepared.public_attempt_phase,
            "prompt_sha256": legacy.sha256_text(prepared.prompt),
            "dynamic_certificate": prepared.dynamic_certificate,
            "request_binding_certificate": prepared.request_binding_certificate,
            "resource_certificate_id": prepared.resource_certificate.certificate_id,
            "final_response_host_envelope_id": (
                prepared.final_response_host_envelope.envelope_id
                if prepared.final_response_host_envelope is not None
                else None
            ),
            "provider_telemetry": telemetry,
            "failure_artifact": failure_artifact,
            "public_content_hash": telemetry.response_hash,
            "public_content_length": telemetry.response_content_length,
        }
        provisional = PrivacyFirstProviderEnvelope.model_construct(envelope_id="pending", **values)
        envelope = PrivacyFirstProviderEnvelope(
            envelope_id=_identity(
                provisional,
                "envelope_id",
                "finance_v26_privacy_first_provider_envelope:",
            ),
            **values,
        )
        path = provider_envelope_path(self._output_dir, self._job, call_index)
        write_json_atomic(path, envelope.model_dump(mode="json"))
        self._telemetry.append(telemetry)
        self._envelope_descriptors.append(_descriptor(path, self._output_dir))
        return envelope

    def _persist_projection(
        self,
        *,
        envelope: PrivacyFirstProviderEnvelope,
        status: PayloadProjectionStatus,
        payload: dict[str, Any] | None,
    ) -> PublicPayloadProjection:
        failure_family: str | None = None
        failure_subtype: str | None = None
        if status == "privacy_rejected":
            failure_family = "payload_privacy_failure"
            failure_subtype = "public_payload_omitted_after_privacy_rejection"
        elif status == "provider_failure_no_payload":
            failure_family = "provider_or_completion_failure"
            failure_subtype = "no_public_payload_returned"
        values = {
            "provider_envelope_id": envelope.envelope_id,
            "job_id": self._job.job_id,
            "provider_call_index": envelope.provider_call_index,
            "request_kind": envelope.request_kind,
            "projection_status": status,
            "response_payload": payload,
            "failure_family": failure_family,
            "failure_subtype": failure_subtype,
        }
        provisional = PublicPayloadProjection.model_construct(projection_id="pending", **values)
        projection = PublicPayloadProjection(
            projection_id=_identity(
                provisional,
                "projection_id",
                "finance_v26_public_payload_projection:",
            ),
            **values,
        )
        path = payload_projection_path(self._output_dir, self._job, envelope.provider_call_index)
        write_json_atomic(path, projection.model_dump(mode="json"))
        self._projection_descriptors.append(_descriptor(path, self._output_dir))
        self._projection_statuses.append(status)
        return projection

    def _charge(
        self,
        prepared: PreparedPrivacyFirstRequest,
        telemetry: legacy.ModelCallTelemetry,
    ) -> None:
        certificate = prepared.resource_certificate
        failures = []
        if telemetry.request_hash != certificate.request_prompt_sha256:
            failures.append("request_hash_mismatch")
        if (
            telemetry.model_requested != legacy.STAGE_ONE_MODEL_ID
            or telemetry.model_selected != legacy.STAGE_ONE_MODEL_ID
            or telemetry.response_model != legacy.STAGE_ONE_MODEL_ID
        ):
            failures.append("exact_model_mismatch_or_missing")
        if telemetry.fallback_used or telemetry.discovery_attempted:
            failures.append("fallback_or_discovery_observed")
        counted = 0
        if telemetry.http_success:
            if telemetry.response_hash is None or telemetry.response_content_length is None:
                failures.append("successful_public_content_hash_or_length_missing")
            prompt_tokens = telemetry.prompt_tokens
            completion_tokens = telemetry.completion_tokens
            total_tokens = telemetry.total_tokens
            if prompt_tokens is None or completion_tokens is None or total_tokens is None:
                failures.append("successful_usage_missing")
            else:
                counted = total_tokens
                if prompt_tokens + completion_tokens != total_tokens:
                    failures.append("prompt_completion_sum_mismatch")
                if prompt_tokens > certificate.prompt_token_upper_bound:
                    failures.append("prompt_upper_bound_exceeded")
                if completion_tokens >= 16386:
                    failures.append("two_or_more_completion_tokens_over_exact_request")
                if total_tokens > certificate.request_token_upper_bound:
                    failures.append("request_upper_bound_exceeded")
                if (
                    self._cumulative_tokens + total_tokens
                    > self._resource.rollout_upper_bound_tokens
                ):
                    failures.append("rollout_upper_bound_exceeded")
        self._cumulative_tokens += counted
        self._instrument_failures.update(failures)

    def invoke(
        self, prepared: PreparedPrivacyFirstRequest
    ) -> tuple[dict[str, Any], legacy.ModelCallTelemetry]:
        if prepared.preparation_id in self._used_preparations:
            raise InstrumentContractError("prepared request was reused")
        self._used_preparations.add(prepared.preparation_id)
        if not prepared.resource_certificate.provider_call_permitted:
            raise BudgetNoCallError(str(prepared.resource_certificate.denial_reason))
        if not prepared.provider_invocation_authorized or prepared.dynamic_certificate is None:
            raise InstrumentContractError("Provider invocation lacks all certificates")
        try:
            payload, telemetry = self._delegate.complete_json_certified(
                prepared.prompt, prepared.request_binding_certificate
            )
        except legacy.LLMClientError as exc:
            failure = (
                exc.failure_artifact
                if isinstance(exc.failure_artifact, legacy.ProspectiveThinkingFailureArtifact)
                else None
            )
            if len(exc.telemetry) != 1:
                self._instrument_failures.add("multiple_or_missing_model_attempt_telemetry")
            for telemetry in exc.telemetry:
                envelope = self._persist_envelope(
                    prepared=prepared,
                    telemetry=telemetry,
                    failure_artifact=failure,
                )
                self._charge(prepared, telemetry)
                projection = self._persist_projection(
                    envelope=envelope,
                    status="provider_failure_no_payload",
                    payload=None,
                )
                validate_provider_artifact_pair(envelope, projection)
            if self._instrument_failures:
                raise InstrumentContractError(";".join(self.instrument_failures)) from exc
            raise
        envelope = self._persist_envelope(
            prepared=prepared,
            telemetry=telemetry,
            failure_artifact=None,
        )
        self._charge(prepared, telemetry)
        if legacy.contains_private_reasoning(payload):
            projection = self._persist_projection(
                envelope=envelope,
                status="privacy_rejected",
                payload=None,
            )
            validate_provider_artifact_pair(envelope, projection)
            if self._instrument_failures:
                raise InstrumentContractError(";".join(self.instrument_failures))
            raise PayloadPrivacyProjectionError
        projection = self._persist_projection(
            envelope=envelope,
            status="validated_public_payload",
            payload=payload,
        )
        validate_provider_artifact_pair(envelope, projection)
        if self._instrument_failures:
            raise InstrumentContractError(";".join(self.instrument_failures))
        return payload, telemetry


def _make_attempt(
    *,
    prepared: PreparedPrivacyFirstRequest,
    provider_call_index: int | None,
    disposition: AttemptDisposition,
    response_payload_present: bool,
    payload_projection_status: PayloadProjectionStatus | None = None,
    exact_four_field_action_payload: bool = False,
    exact_two_field_final_payload: bool = False,
    failure_family: str | None = None,
    failure_subtype: str | None = None,
    completion_failure_type: str | None = None,
    error: str | None = None,
) -> PrivacyFirstAttempt:
    values = {
        "logical_request_index": prepared.logical_request_index,
        "provider_call_index": provider_call_index,
        "request_kind": prepared.request_kind,
        "public_attempt_phase": prepared.public_attempt_phase,
        "prompt_sha256": legacy.sha256_text(prepared.prompt),
        "prompt_utf8_bytes": len(prepared.prompt.encode("utf-8")),
        "dynamic_certificate_id": (
            prepared.dynamic_certificate.certificate_id
            if prepared.dynamic_certificate is not None
            else None
        ),
        "request_binding_certificate_id": (prepared.request_binding_certificate.certificate_id),
        "resource_certificate_id": prepared.resource_certificate.certificate_id,
        "final_response_host_envelope_id": (
            prepared.final_response_host_envelope.envelope_id
            if prepared.final_response_host_envelope is not None
            else None
        ),
        "provider_call_made": provider_call_index is not None,
        "response_payload_present": response_payload_present,
        "payload_projection_status": payload_projection_status,
        "exact_four_field_action_payload": exact_four_field_action_payload,
        "exact_two_field_final_payload": exact_two_field_final_payload,
        "failure_family": failure_family,
        "failure_subtype": failure_subtype,
        "completion_failure_type": completion_failure_type,
        "disposition": disposition,
        "error": error,
    }
    provisional = PrivacyFirstAttempt.model_construct(attempt_id="pending", **values)
    return PrivacyFirstAttempt(
        attempt_id=_identity(provisional, "attempt_id", "finance_v26_privacy_first_attempt:"),
        **values,
    )


def _invoke_attempt(
    ledger: PrivacyFirstJournaledClient,
    *,
    logical_request_index: int,
    request_kind: legacy.StageOneRequestKind,
    public_attempt_phase: PublicAttemptPhase,
    primary_prompt: str,
    prompt: str,
    state: SemanticActionState | None,
    final_response_host_envelope: FinalResponseHostEnvelope | None,
    static: static_stage.FinalGrammarStaticInputs,
    abi_rescue_count: int,
    semantic_recovery_count: int,
) -> _AttemptOutcome:
    public_state_id = (
        state.state_id
        if state is not None
        else (
            final_response_host_envelope.terminal_state_id
            if final_response_host_envelope is not None
            else None
        )
    )
    prepared = ledger.prepare(
        logical_request_index=logical_request_index,
        request_kind=request_kind,
        public_attempt_phase=public_attempt_phase,
        primary_prompt=primary_prompt,
        prompt=prompt,
        public_state_id=public_state_id,
        final_response_host_envelope=final_response_host_envelope,
        abi_rescue_count_before=abi_rescue_count,
        semantic_recovery_count_before=semantic_recovery_count,
    )
    before = ledger.provider_call_count
    try:
        payload, _ = ledger.invoke(prepared)
    except BudgetNoCallError as exc:
        return _AttemptOutcome(
            attempt=_make_attempt(
                prepared=prepared,
                provider_call_index=None,
                disposition="typed_budget_no_call",
                response_payload_present=False,
                error=str(exc),
            )
        )
    except PayloadPrivacyProjectionError as exc:
        return _AttemptOutcome(
            attempt=_make_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="model_result_failure",
                response_payload_present=False,
                payload_projection_status="privacy_rejected",
                failure_family=exc.family,
                failure_subtype=exc.subtype,
                error=str(exc),
            )
        )
    except InstrumentContractError as exc:
        index = before if ledger.provider_call_count > before else None
        status = (
            ledger.projection_statuses[-1]
            if index is not None and ledger.projection_statuses
            else None
        )
        return _AttemptOutcome(
            attempt=_make_attempt(
                prepared=prepared,
                provider_call_index=index,
                disposition="instrument_failure",
                response_payload_present=False,
                payload_projection_status=status,
                error=str(exc),
            )
        )
    except legacy.LLMClientError as exc:
        index = before if ledger.provider_call_count > before else None
        failure_type = (
            exc.failure_artifact.failure_type
            if isinstance(exc.failure_artifact, legacy.ProspectiveThinkingFailureArtifact)
            else type(exc).__name__
        )
        disposition: AttemptDisposition = (
            "completion_failure"
            if exc.telemetry and all(item.http_success for item in exc.telemetry)
            else "provider_transport_failure"
        )
        return _AttemptOutcome(
            attempt=_make_attempt(
                prepared=prepared,
                provider_call_index=index,
                disposition=disposition,
                response_payload_present=False,
                payload_projection_status=(
                    "provider_failure_no_payload" if index is not None else None
                ),
                completion_failure_type=failure_type,
                error=str(exc),
            )
        )
    try:
        if request_kind == "semantic_proposal":
            proposal = parse_exact_canonical_action_payload(payload)
            return _AttemptOutcome(
                attempt=_make_attempt(
                    prepared=prepared,
                    provider_call_index=before,
                    disposition="usable",
                    response_payload_present=True,
                    payload_projection_status="validated_public_payload",
                    exact_four_field_action_payload=True,
                ),
                payload=payload,
                proposal=proposal,
            )
        if final_response_host_envelope is None:
            raise ValueError("v26.123 Final Parser lacks its Host Envelope")
        final_payload = parse_exact_final_response_payload(
            payload,
            grammar=static.final_grammar,
            envelope=final_response_host_envelope,
        )
        return _AttemptOutcome(
            attempt=_make_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="usable",
                response_payload_present=True,
                payload_projection_status="validated_public_payload",
                exact_two_field_final_payload=True,
            ),
            payload=payload,
            final_payload=final_payload,
        )
    except SemanticActionResponseRejection as exc:
        return _AttemptOutcome(
            attempt=_make_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="model_result_failure",
                response_payload_present=True,
                payload_projection_status="validated_public_payload",
                failure_family=exc.family,
                failure_subtype=exc.subtype,
                error=str(exc),
            ),
            payload=payload,
        )
    except ExactFinalResponseRejection as exc:
        return _AttemptOutcome(
            attempt=_make_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="model_result_failure",
                response_payload_present=True,
                payload_projection_status="validated_public_payload",
                failure_family=exc.family,
                failure_subtype=exc.subtype,
                error=str(exc),
            ),
            payload=payload,
        )


def _abi_rescue_allowed(attempt: PrivacyFirstAttempt) -> bool:
    return attempt.disposition == "completion_failure" or (
        attempt.disposition == "model_result_failure"
        and attempt.failure_family in {"response_serialization_failure", "channel_parse_failure"}
    )


def _active_outcome(
    ledger: PrivacyFirstJournaledClient,
    *,
    attempts: list[PrivacyFirstAttempt],
    logical_request_index: int,
    request_kind: legacy.StageOneRequestKind,
    public_attempt_phase: Literal["primary", "semantic_recovery"],
    primary_prompt: str,
    state: SemanticActionState | None,
    final_response_host_envelope: FinalResponseHostEnvelope | None,
    static: static_stage.FinalGrammarStaticInputs,
    abi_rescue_count: int,
    semantic_recovery_count: int,
) -> tuple[_AttemptOutcome, int]:
    primary = _invoke_attempt(
        ledger,
        logical_request_index=logical_request_index,
        request_kind=request_kind,
        public_attempt_phase=public_attempt_phase,
        primary_prompt=primary_prompt,
        prompt=primary_prompt,
        state=state,
        final_response_host_envelope=final_response_host_envelope,
        static=static,
        abi_rescue_count=abi_rescue_count,
        semantic_recovery_count=semantic_recovery_count,
    )
    attempts.append(primary.attempt)
    if abi_rescue_count == 0 and _abi_rescue_allowed(primary.attempt):
        abi_rescue_count = 1
        family = primary.attempt.failure_family or "channel_parse_failure"
        subtype = (
            primary.attempt.failure_subtype
            or primary.attempt.completion_failure_type
            or "completion_failure"
        )
        rescue_prompt = (
            render_exact_canonical_action_abi_rescue_prompt(
                primary_prompt,
                failure_family=family,
                failure_subtype=subtype,
            )
            if request_kind == "semantic_proposal"
            else render_exact_final_rescue_prompt(
                primary_prompt,
                failure_family=family,
                failure_subtype=subtype,
            )
        )
        rescue = _invoke_attempt(
            ledger,
            logical_request_index=logical_request_index,
            request_kind=request_kind,
            public_attempt_phase="abi_rescue",
            primary_prompt=primary_prompt,
            prompt=rescue_prompt,
            state=state,
            final_response_host_envelope=final_response_host_envelope,
            static=static,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        attempts.append(rescue.attempt)
        return rescue, abi_rescue_count
    return primary, abi_rescue_count


def _terminal_from_attempt(attempt: PrivacyFirstAttempt) -> TerminalDisposition:
    if attempt.disposition == "completion_failure":
        return "completion_unusable"
    if attempt.disposition == "provider_transport_failure":
        return "provider_transport_failure"
    if attempt.disposition == "typed_budget_no_call":
        return "typed_budget_no_call"
    if attempt.disposition == "instrument_failure":
        return "instrument_failure"
    return "model_result"


def _finish_raw(
    *,
    runner_contract: PrivacyFirstRunnerContract,
    job: static_stage.FinalGrammarJob,
    binding: legacy.RuntimeBinding,
    ledger: PrivacyFirstJournaledClient,
    attempts: Sequence[PrivacyFirstAttempt],
    choices: Sequence[predecessor.SemanticChoiceRecord],
    commits: Sequence[predecessor.SemanticActionCommitRecord],
    semantic_rejections: Sequence[PublicSemanticRejectionObservation],
    observations: Sequence[AgentToolObservation],
    completed: PrivacyFirstCompletedResult | None,
    terminal: TerminalDisposition,
    failure_type: str | None,
    error: str | None,
    output_dir: Path,
) -> PrivacyFirstRawExecution:
    values = {
        "runner_contract_id": runner_contract.contract_id,
        "job": job,
        "operational_record_id": binding.record.record_id,
        "environment_manifest_id": binding.environment.manifest_id,
        "path_audit_id": job.path_audit_id,
        "provider_envelope_artifacts": ledger.envelope_descriptors,
        "public_payload_projection_artifacts": ledger.projection_descriptors,
        "provider_telemetry": ledger.telemetry,
        "attempts": tuple(attempts),
        "semantic_choices": tuple(choices),
        "commits": tuple(commits),
        "semantic_rejections": tuple(semantic_rejections),
        "observations": tuple(observations),
        "completed_result": completed,
        "terminal_disposition": terminal,
        "terminal_failure_type": failure_type,
        "execution_error": error,
        "cumulative_provider_tokens": ledger.cumulative_tokens,
        "stage_one_provider_call_count": ledger.provider_call_count,
        "public_payload_projection_count": len(ledger.projection_descriptors),
        "privacy_rejected_payload_count": sum(
            item == "privacy_rejected" for item in ledger.projection_statuses
        ),
        "abi_rescue_attempt_count": sum(
            item.public_attempt_phase == "abi_rescue" for item in attempts
        ),
        "semantic_recovery_attempt_count": sum(
            item.public_attempt_phase == "semantic_recovery" for item in choices
        ),
        "first_choice_semantic_rejection_count": sum(
            item.public_attempt_phase == "primary" and not item.semantic_accepted
            for item in choices
        ),
    }
    provisional = PrivacyFirstRawExecution.model_construct(artifact_id="pending", **values)
    raw = PrivacyFirstRawExecution(
        artifact_id=_identity(
            provisional,
            "artifact_id",
            "finance_v26_privacy_first_raw_execution:",
        ),
        **values,
    )
    write_json_atomic(raw_execution_path(output_dir, job), raw.model_dump(mode="json"))
    return raw


def execute_privacy_first_job_raw(
    *,
    job: static_stage.FinalGrammarJob,
    runner_contract: PrivacyFirstRunnerContract,
    static: static_stage.FinalGrammarStaticInputs,
    binding: legacy.RuntimeBinding,
    client: predecessor.StageOneClient | None,
    output_dir: Path,
) -> PrivacyFirstRawExecution:
    raw_path = raw_execution_path(output_dir, job)
    if raw_path.exists():
        raw = PrivacyFirstRawExecution.model_validate(legacy.load_canonical_json(raw_path))
        if raw.runner_contract_id != runner_contract.contract_id or raw.job != job:
            raise ValueError("v26.123 Raw recovery crosses frozen identities")
        envelopes: list[PrivacyFirstProviderEnvelope] = []
        for descriptor in raw.provider_envelope_artifacts:
            path = output_dir / descriptor.relative_path
            if not path.is_file() or legacy.sha256_file(path) != descriptor.sha256:
                raise ValueError("v26.123 Raw recovery Envelope bytes changed")
            envelopes.append(
                PrivacyFirstProviderEnvelope.model_validate(legacy.load_canonical_json(path))
            )
        projections: list[PublicPayloadProjection] = []
        for descriptor in raw.public_payload_projection_artifacts:
            path = output_dir / descriptor.relative_path
            if not path.is_file() or legacy.sha256_file(path) != descriptor.sha256:
                raise ValueError("v26.123 Raw recovery Projection bytes changed")
            projections.append(
                PublicPayloadProjection.model_validate(legacy.load_canonical_json(path))
            )
        expected_indices = list(range(raw.stage_one_provider_call_count))
        if (
            [item.provider_call_index for item in envelopes] != expected_indices
            or [item.provider_call_index for item in projections] != expected_indices
            or [item.provider_telemetry for item in envelopes] != list(raw.provider_telemetry)
        ):
            raise ValueError("v26.123 Raw recovery Provider ordering changed")
        for envelope, projection in zip(envelopes, projections, strict=True):
            if (
                envelope.runner_contract_id != raw.runner_contract_id
                or envelope.job_id != raw.job.job_id
            ):
                raise ValueError("v26.123 Raw recovery Provider parent changed")
            validate_provider_artifact_pair(envelope, projection)
        return raw
    envelope_dir = provider_envelope_path(output_dir, job, 0).parent
    projection_dir = payload_projection_path(output_dir, job, 0).parent
    if (envelope_dir.exists() and any(envelope_dir.glob("call_*.json"))) or (
        projection_dir.exists() and any(projection_dir.glob("call_*.json"))
    ):
        raise ValueError("v26.123 orphan Provider artifacts forbid retry")
    if client is None:
        raise ValueError("pending v26.123 Job has no Stage 1 client")
    if (
        job.contract_id != static.contract.contract_id
        or job.task_package_id not in {item.task_package_id for item in static.tasks}
        or job.path_audit_id not in {item.path_audit_id for item in static.paths}
    ):
        raise ValueError("v26.123 Job differs from its static identity chain")
    ledger = PrivacyFirstJournaledClient(
        client,
        runner_contract=runner_contract,
        resource_contract=static.resource,
        job=job,
        output_dir=output_dir,
    )
    runtime = legacy._runtime(binding.record, binding.environment)
    observations: list[AgentToolObservation] = []
    attempts: list[PrivacyFirstAttempt] = []
    choices: list[predecessor.SemanticChoiceRecord] = []
    commits: list[predecessor.SemanticActionCommitRecord] = []
    semantic_rejections: list[PublicSemanticRejectionObservation] = []
    abi_rescue_count = 0
    semantic_recovery_count = 0
    pending_semantic_recovery = False
    prior_rejected_action_id: str | None = None
    condition = (
        None
        if binding.source_registered_path.role == "capability"
        else binding.source_registered_path.path_strategy_id
    )
    terminal: TerminalDisposition = "model_result"
    failure_type: str | None = None
    error: str | None = None
    completed: PrivacyFirstCompletedResult | None = None
    final_state: SemanticActionState | None = None
    final_commit: CanonicalActionCommit | None = None
    logical_index = 0
    for _ in range(static.resource.maximum_primary_stage_one_requests - 1):
        state = build_semantic_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            tuple(observations),
            semantic_rejections=tuple(semantic_rejections),
        )
        presentation_salt = canonical_hash(
            {
                "job_id": job.job_id,
                "logical_request_index": logical_index,
                "state_id": state.state_id,
                "semantic_recovery_count": semantic_recovery_count,
            },
            prefix="finance_v26_runner_candidate_presentation:",
        )
        phase: Literal["primary", "semantic_recovery"] = (
            "semantic_recovery" if pending_semantic_recovery else "primary"
        )
        prompt = (
            render_exact_canonical_action_semantic_recovery_prompt(
                instruction=binding.record.task_package.task.public.instruction,
                state=state,
                public_path_condition=condition,
                presentation_salt=presentation_salt,
            )
            if pending_semantic_recovery
            else render_exact_canonical_action_prompt(
                instruction=binding.record.task_package.task.public.instruction,
                state=state,
                public_path_condition=condition,
                presentation_salt=presentation_salt,
                grammar=static.action_grammar,
            )
        )
        outcome, abi_rescue_count = _active_outcome(
            ledger,
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="semantic_proposal",
            public_attempt_phase=phase,
            primary_prompt=prompt,
            state=state,
            final_response_host_envelope=None,
            static=static,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        current_index = logical_index
        logical_index += 1
        if outcome.attempt.disposition != "usable" or outcome.proposal is None:
            terminal = _terminal_from_attempt(outcome.attempt)
            failure_type = (
                outcome.attempt.failure_subtype
                or outcome.attempt.completion_failure_type
                or outcome.attempt.disposition
            )
            error = outcome.attempt.error
            break
        proposal = outcome.proposal
        selected = evaluate_canonical_action_proposal(
            state, proposal, call_index=len(observations) + 1
        )
        if selected.rejection is not None:
            choices.append(
                predecessor._choice_record(
                    logical_request_index=current_index,
                    phase=phase,
                    state=state,
                    proposal=proposal,
                    commit=None,
                    rejection=selected.rejection,
                    prior_rejected_action_id=prior_rejected_action_id,
                    observation=None,
                    progress=None,
                )
            )
            if semantic_recovery_count == 0 and selected.rejection.semantic_recovery_available:
                semantic_recovery_count = 1
                semantic_rejections.append(selected.rejection)
                prior_rejected_action_id = proposal.action_id
                pending_semantic_recovery = True
                continue
            terminal = "model_result"
            failure_type = "semantic_recovery_exhausted"
            error = selected.rejection.error_category
            break
        commit = selected.commit
        if commit is None:
            raise ValueError("accepted v26.123 action lacks a Commit")
        commit_values = {
            "logical_request_index": current_index,
            "public_state_id": state.state_id,
            "proposal": proposal,
            "commit": commit,
            "stage_two_profile_id": static.stage_two.profile_id,
            "provider_calls_before_commit": ledger.provider_call_count,
        }
        provisional_commit = predecessor.SemanticActionCommitRecord.model_construct(
            record_id="pending", **commit_values
        )
        commits.append(
            predecessor.SemanticActionCommitRecord(
                record_id=_identity(
                    provisional_commit,
                    "record_id",
                    "finance_v26_semantic_action_commit_record:",
                ),
                **commit_values,
            )
        )
        pending_semantic_recovery = False
        observation: AgentToolObservation | None = None
        progress: bool | None = None
        if commit.call is not None:
            observation = legacy._execute_observation(
                record=binding.record,
                environment=binding.environment,
                runtime=runtime,
                observations=tuple(observations),
                projection=CompletionProjection(
                    request_kind="decision",
                    action="call_tool",
                    tool_id=commit.call.tool_id,
                    arguments=commit.call.arguments,
                ),
            )
            observations.append(observation)
            after = build_semantic_action_state(
                binding.record.task_package.task.public,
                binding.environment,
                tuple(observations),
                semantic_rejections=tuple(semantic_rejections),
            )
            progress = predecessor._public_progress(state, after, observation)
        choices.append(
            predecessor._choice_record(
                logical_request_index=current_index,
                phase=phase,
                state=state,
                proposal=proposal,
                commit=commit,
                rejection=None,
                prior_rejected_action_id=prior_rejected_action_id,
                observation=observation,
                progress=progress,
            )
        )
        if commit.action == "emit_final":
            final_state = state
            final_commit = commit
            break
    else:
        terminal = "model_result"
        failure_type = "semantic_action_primary_request_limit_exhausted"
        error = "model did not reach Final within the frozen request limit"
    if (
        final_state is not None
        and final_commit is not None
        and terminal == "model_result"
        and failure_type is None
    ):
        compact_source = render_compact_final_prompt(
            binding.prompt_contract.public_context,
            binding.record.task_package.task.public,
            tuple(observations),
            public_path_condition=condition,
        )
        final_prompt = render_exact_final_primary_prompt(
            compact_source,
            grammar=static.final_grammar,
        )
        host_envelope = make_final_response_host_envelope(
            terminal_state_id=final_state.state_id,
            terminal_commit_id=final_commit.commit_id,
            grammar=static.final_grammar,
        )
        outcome, abi_rescue_count = _active_outcome(
            ledger,
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="final_answer",
            public_attempt_phase="primary",
            primary_prompt=final_prompt,
            state=None,
            final_response_host_envelope=host_envelope,
            static=static,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        if outcome.attempt.disposition == "usable" and outcome.final_payload is not None:
            citations = legacy._selected_evidence_ids(observations)
            if not citations:
                terminal = "model_result"
                failure_type = "final_answer_without_public_evidence"
                error = "Final answer has no selected public Evidence"
            else:
                values = {
                    "job_id": job.job_id,
                    "answer": outcome.final_payload.answer,
                    "rationale_summary": outcome.final_payload.rationale_summary,
                    "cited_evidence_ids": citations,
                    "final_attempt_id": outcome.attempt.attempt_id,
                    "final_response_host_envelope": host_envelope,
                }
                provisional = PrivacyFirstCompletedResult.model_construct(
                    result_id="pending", **values
                )
                completed = PrivacyFirstCompletedResult(
                    result_id=_identity(
                        provisional,
                        "result_id",
                        "finance_v26_privacy_first_completed_result:",
                    ),
                    **values,
                )
                terminal = "completed"
        else:
            terminal = _terminal_from_attempt(outcome.attempt)
            failure_type = (
                outcome.attempt.failure_subtype
                or outcome.attempt.completion_failure_type
                or outcome.attempt.disposition
            )
            error = outcome.attempt.error
    if ledger.instrument_failures:
        terminal = "instrument_failure"
        failure_type = "provider_usage_or_binding_contract_failure"
        error = ";".join(ledger.instrument_failures)
        completed = None
    return _finish_raw(
        runner_contract=runner_contract,
        job=job,
        binding=binding,
        ledger=ledger,
        attempts=attempts,
        choices=choices,
        commits=commits,
        semantic_rejections=semantic_rejections,
        observations=observations,
        completed=completed,
        terminal=terminal,
        failure_type=failure_type,
        error=error,
        output_dir=output_dir,
    )
