from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_semantic_action_rematerialization import (  # noqa: E501
    PROSPECTIVE_EXECUTION_RUN_ID,
    PROSPECTIVE_RUNNER_RUN_ID,
    SemanticActionJob,
    SemanticActionResourceContract,
    SemanticActionStaticInputs,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    CanonicalActionCommit,
    CanonicalActionProposal,
    PublicSemanticRejectionObservation,
    SemanticActionState,
    build_semantic_action_state,
    evaluate_canonical_action_proposal,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    RESPONSE_PROTOCOL_VERSION,
    SemanticActionResponseRejection,
    parse_exact_canonical_action_payload,
    render_exact_canonical_action_abi_rescue_prompt,
    render_exact_canonical_action_prompt,
    render_exact_canonical_action_semantic_recovery_prompt,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    CompletionProjection,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_semantic_proposal import (
    ModelResultRejection,
    parse_final_answer_payload,
)
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
RUNNER_RUN_ID: Final = PROSPECTIVE_RUNNER_RUN_ID
EXECUTION_RUN_ID: Final = PROSPECTIVE_EXECUTION_RUN_ID


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SemanticActionRunnerContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_static_contract_id: str = Field(min_length=1)
    predecessor_manifest_id: str = Field(min_length=1)
    semantic_action_protocol_id: str = Field(min_length=1)
    response_grammar_id: str = Field(min_length=1)
    candidate_space_authority_audit_id: str = Field(min_length=1)
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    exact_job_denominator: Literal[32] = 32
    runner_run_id: str = RUNNER_RUN_ID
    execution_run_id: str = EXECUTION_RUN_ID
    model_response_fields: tuple[str, str, str, str] = (
        "state_id",
        "action_id",
        "decision_kind",
        "protocol",
    )
    exact_request_completion_bound_tokens: Literal[16384] = 16384
    provider_accounting_margin_tokens: Literal[1] = 1
    rollout_upper_bound_tokens: int = Field(gt=260000)
    maximum_primary_stage_one_requests: Literal[11] = 11
    maximum_stage_one_provider_calls: Literal[12] = 12
    maximum_abi_rescue_calls: Literal[1] = 1
    maximum_semantic_recovery_calls: Literal[1] = 1
    abi_and_semantic_recovery_counters_separate: Literal[True] = True
    first_choice_failure_retained_after_recovery: Literal[True] = True
    stage_two_provider_call_upper_bound: Literal[0] = 0
    stage_two_reverses_same_action_id: Literal[True] = True
    raw_provider_persisted_before_projection: Literal[True] = True
    raw_only_recovery: Literal[True] = True
    orphan_provider_artifact_fails_closed: Literal[True] = True
    private_reasoning_persistence_allowed: Literal[False] = False
    runner_implemented: Literal[True] = True
    empirical_execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_semantic_action_runner_contract.v1"] = (
        "finance_v26_semantic_action_runner_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> SemanticActionRunnerContract:
        if (
            self.maximum_stage_one_provider_calls
            != self.maximum_primary_stage_one_requests + self.maximum_abi_rescue_calls
        ):
            raise ValueError("semantic action Runner call bound changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_semantic_action_runner_contract:"
        ):
            raise ValueError("semantic action Runner Contract identity changed")
        return self


class DynamicActionRequestCertificate(FrozenModel):
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
    prompt_utf8_bytes: int = Field(gt=0, le=60000)
    abi_rescue_count_before: int = Field(ge=0, le=1)
    semantic_recovery_count_before: int = Field(ge=0, le=1)
    prompt_rendered_before_certificate: Literal[True] = True
    candidate_order_bound_before_provider: Literal[True] = True
    provider_calls_before_certificate: Literal[0] = 0
    stage_two_provider_calls_before_certificate: Literal[0] = 0
    schema_version: Literal["finance_v26_dynamic_action_request_certificate.v1"] = (
        "finance_v26_dynamic_action_request_certificate.v1"
    )

    @model_validator(mode="after")
    def validate_certificate(self) -> DynamicActionRequestCertificate:
        if self.public_attempt_phase == "abi_rescue":
            if self.provider_attempt_phase != "rescue":
                raise ValueError("ABI Rescue did not bind Provider rescue phase")
        elif self.provider_attempt_phase != "primary":
            raise ValueError("primary or Semantic Recovery bound a Provider rescue phase")
        if self.certificate_id != _identity(
            self, "certificate_id", "finance_v26_dynamic_action_request_certificate:"
        ):
            raise ValueError("dynamic action-request certificate identity changed")
        return self


class ActionResourceCertificate(FrozenModel):
    certificate_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    request_index: int = Field(ge=0)
    request_kind: legacy.StageOneRequestKind
    public_attempt_phase: PublicAttemptPhase
    request_prompt_sha256: str = Field(min_length=64, max_length=64)
    prompt_utf8_bytes: int = Field(gt=0)
    prompt_token_upper_bound: int = Field(gt=0)
    completion_token_upper_bound: Literal[16385] = 16385
    request_token_upper_bound: int = Field(gt=0)
    cumulative_provider_tokens_before: int = Field(ge=0)
    abi_rescue_reserve_tokens: int = Field(ge=0)
    semantic_recovery_reserve_tokens: int = Field(ge=0)
    final_answer_reserve_tokens: int = Field(ge=0)
    required_reserve_tokens: int = Field(ge=0)
    projected_upper_total: int = Field(gt=0)
    rollout_upper_bound_tokens: int = Field(gt=260000)
    decision: Literal["allowed", "denied_no_call"]
    denial_reason: (
        Literal[
            "oversized_prompt",
            "request_bound_exceeds_remaining_budget",
            "required_reserve_not_available",
            "stage_one_request_count_exhausted",
        ]
        | None
    ) = None
    provider_call_permitted: bool
    schema_version: Literal["finance_v26_action_resource_certificate.v1"] = (
        "finance_v26_action_resource_certificate.v1"
    )

    @model_validator(mode="after")
    def validate_certificate(self) -> ActionResourceCertificate:
        if (
            self.prompt_token_upper_bound != self.prompt_utf8_bytes + 256
            or self.request_token_upper_bound
            != self.prompt_token_upper_bound + self.completion_token_upper_bound
            or self.required_reserve_tokens
            != self.abi_rescue_reserve_tokens
            + self.semantic_recovery_reserve_tokens
            + self.final_answer_reserve_tokens
            or self.projected_upper_total
            != self.cumulative_provider_tokens_before
            + self.request_token_upper_bound
            + self.required_reserve_tokens
            or self.provider_call_permitted != (self.decision == "allowed")
            or (self.denial_reason is None) != self.provider_call_permitted
        ):
            raise ValueError("dynamic semantic-action resource arithmetic changed")
        if self.certificate_id != _identity(
            self, "certificate_id", "finance_v26_action_resource_certificate:"
        ):
            raise ValueError("semantic action resource-certificate identity changed")
        return self


class PreparedActionRequest(FrozenModel):
    preparation_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    request_kind: legacy.StageOneRequestKind
    public_attempt_phase: PublicAttemptPhase
    primary_prompt: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    public_state_id: str | None = None
    dynamic_certificate: DynamicActionRequestCertificate | None
    request_binding_certificate: legacy.StageOneRequestBindingCertificate
    resource_certificate: ActionResourceCertificate
    provider_invocation_authorized: bool
    provider_calls_before_preparation: Literal[0] = 0

    @model_validator(mode="after")
    def validate_preparation(self) -> PreparedActionRequest:
        digest = legacy.sha256_text(self.prompt)
        if (
            self.request_binding_certificate.prompt_sha256 != digest
            or self.resource_certificate.request_prompt_sha256 != digest
            or (
                self.dynamic_certificate is not None
                and self.dynamic_certificate.request_prompt_sha256 != digest
            )
        ):
            raise ValueError("prepared semantic-action Prompt binding changed")
        if self.provider_invocation_authorized != bool(
            self.dynamic_certificate is not None
            and self.resource_certificate.provider_call_permitted
        ):
            raise ValueError("prepared semantic-action invocation authorization changed")
        if self.preparation_id != _identity(
            self, "preparation_id", "finance_v26_prepared_action_request:"
        ):
            raise ValueError("prepared semantic-action request identity changed")
        return self


class RawActionProviderCall(FrozenModel):
    artifact_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    provider_call_index: int = Field(ge=0)
    request_kind: legacy.StageOneRequestKind
    public_attempt_phase: PublicAttemptPhase
    prompt_sha256: str = Field(min_length=64, max_length=64)
    dynamic_certificate: DynamicActionRequestCertificate
    request_binding_certificate: legacy.StageOneRequestBindingCertificate
    resource_certificate_id: str = Field(min_length=1)
    response_payload: dict[str, Any] | None = None
    provider_telemetry: legacy.ModelCallTelemetry
    failure_artifact: legacy.ProspectiveThinkingFailureArtifact | None = None
    captured_before_response_projection: Literal[True] = True
    stage_two_provider_call_count: Literal[0] = 0
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    raw_request_body_persisted: Literal[False] = False
    schema_version: Literal["finance_v26_raw_action_provider_call.v1"] = (
        "finance_v26_raw_action_provider_call.v1"
    )

    @model_validator(mode="after")
    def validate_artifact(self) -> RawActionProviderCall:
        if (
            self.provider_telemetry.request_hash != self.prompt_sha256
            or self.dynamic_certificate.request_prompt_sha256 != self.prompt_sha256
            or self.request_binding_certificate.prompt_sha256 != self.prompt_sha256
            or legacy.contains_private_reasoning(self.response_payload)
        ):
            raise ValueError("Raw semantic-action Provider binding or privacy changed")
        if self.artifact_id != _identity(
            self, "artifact_id", "finance_v26_raw_action_provider_call:"
        ):
            raise ValueError("Raw semantic-action Provider identity changed")
        return self


class SemanticActionAttempt(FrozenModel):
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
    provider_call_made: bool
    response_payload_present: bool
    exact_four_field_payload: bool = False
    failure_family: str | None = None
    failure_subtype: str | None = None
    completion_failure_type: str | None = None
    disposition: AttemptDisposition
    error: str | None = None
    previous_response_content_reused: Literal[False] = False
    private_reasoning_reused: Literal[False] = False
    host_semantic_action_inserted: Literal[False] = False
    schema_version: Literal["finance_v26_semantic_action_attempt.v1"] = (
        "finance_v26_semantic_action_attempt.v1"
    )

    @model_validator(mode="after")
    def validate_attempt(self) -> SemanticActionAttempt:
        if self.provider_call_made != (self.provider_call_index is not None):
            raise ValueError("semantic action Provider-call accounting changed")
        if self.provider_call_made and not all(
            (
                self.dynamic_certificate_id,
                self.request_binding_certificate_id,
                self.resource_certificate_id,
            )
        ):
            raise ValueError("semantic action Provider call preceded a certificate")
        if self.attempt_id != _identity(self, "attempt_id", "finance_v26_semantic_action_attempt:"):
            raise ValueError("semantic action attempt identity changed")
        return self


class SemanticChoiceRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    public_attempt_phase: Literal["primary", "semantic_recovery"]
    state_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    selected_action_id: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    visible_action_id_match: bool
    decision_kind_match: bool
    semantic_accepted: bool
    rejection_id: str | None = None
    commit_id: str | None = None
    different_action_after_rejection: bool | None = None
    observation_status: Literal["succeeded", "failed"] | None = None
    public_progress_after_commit: bool | None = None
    first_choice_failure_retained: Literal[True] = True
    schema_version: Literal["finance_v26_semantic_choice_record.v1"] = (
        "finance_v26_semantic_choice_record.v1"
    )

    @model_validator(mode="after")
    def validate_record(self) -> SemanticChoiceRecord:
        if self.semantic_accepted != (self.commit_id is not None):
            raise ValueError("semantic choice acceptance and Commit diverged")
        if self.semantic_accepted == (self.rejection_id is not None):
            raise ValueError("semantic choice has neither or both Commit and rejection")
        if self.record_id != _identity(self, "record_id", "finance_v26_semantic_choice_record:"):
            raise ValueError("semantic choice-record identity changed")
        return self


class SemanticActionCommitRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    public_state_id: str = Field(min_length=1)
    proposal: CanonicalActionProposal
    commit: CanonicalActionCommit
    stage_two_profile_id: str = Field(min_length=1)
    provider_calls_before_commit: int = Field(ge=1)
    stage_two_provider_calls: Literal[0] = 0
    semantic_choice_inserted_by_host: Literal[False] = False
    reversible_same_action_id_passed: Literal[True] = True
    schema_version: Literal["finance_v26_semantic_action_commit_record.v1"] = (
        "finance_v26_semantic_action_commit_record.v1"
    )

    @model_validator(mode="after")
    def validate_record(self) -> SemanticActionCommitRecord:
        if (
            self.proposal.state_id != self.public_state_id
            or self.commit.state_id != self.public_state_id
            or self.commit.proposal_id != self.proposal.proposal_id
            or self.commit.action_id != self.proposal.action_id
        ):
            raise ValueError("semantic action Commit parent or reverse binding changed")
        if self.record_id != _identity(
            self, "record_id", "finance_v26_semantic_action_commit_record:"
        ):
            raise ValueError("semantic action Commit-record identity changed")
        return self


class SemanticActionCompletedResult(FrozenModel):
    result_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    answer: dict[str, Any] = Field(min_length=1)
    cited_evidence_ids: tuple[str, ...] = Field(min_length=1)
    final_attempt_id: str = Field(min_length=1)
    schema_version: Literal["finance_v26_semantic_action_completed_result.v1"] = (
        "finance_v26_semantic_action_completed_result.v1"
    )

    @model_validator(mode="after")
    def validate_result(self) -> SemanticActionCompletedResult:
        if self.cited_evidence_ids != tuple(sorted(set(self.cited_evidence_ids))):
            raise ValueError("semantic action cited Evidence is not canonical")
        if self.result_id != _identity(
            self, "result_id", "finance_v26_semantic_action_completed_result:"
        ):
            raise ValueError("semantic action completed-result identity changed")
        return self


class SemanticActionRawExecution(FrozenModel):
    artifact_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    job: SemanticActionJob
    operational_record_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    path_audit_id: str = Field(min_length=1)
    provider_call_artifacts: tuple[legacy.RawFileDescriptor, ...]
    provider_telemetry: tuple[legacy.ModelCallTelemetry, ...]
    attempts: tuple[SemanticActionAttempt, ...] = Field(min_length=1)
    semantic_choices: tuple[SemanticChoiceRecord, ...]
    commits: tuple[SemanticActionCommitRecord, ...]
    semantic_rejections: tuple[PublicSemanticRejectionObservation, ...]
    observations: tuple[AgentToolObservation, ...]
    completed_result: SemanticActionCompletedResult | None = None
    terminal_disposition: TerminalDisposition
    terminal_failure_type: str | None = None
    execution_error: str | None = None
    cumulative_provider_tokens: int = Field(ge=0)
    stage_one_provider_call_count: int = Field(ge=0, le=12)
    stage_two_provider_call_count: Literal[0] = 0
    abi_rescue_attempt_count: int = Field(ge=0, le=1)
    semantic_recovery_attempt_count: int = Field(ge=0, le=1)
    first_choice_semantic_rejection_count: int = Field(ge=0, le=1)
    model_discovery_call_count: Literal[0] = 0
    captured_before_verifier_scoring: Literal[True] = True
    private_reasoning_content_persisted: Literal[False] = False
    schema_version: Literal["finance_v26_semantic_action_raw_execution.v1"] = (
        "finance_v26_semantic_action_raw_execution.v1"
    )

    @model_validator(mode="after")
    def validate_execution(self) -> SemanticActionRawExecution:
        if (
            self.stage_one_provider_call_count != len(self.provider_telemetry)
            or len(self.provider_call_artifacts) != self.stage_one_provider_call_count
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
            raise ValueError("semantic action Raw denominator changed")
        if self.artifact_id != _identity(
            self, "artifact_id", "finance_v26_semantic_action_raw_execution:"
        ):
            raise ValueError("semantic action Raw identity changed")
        return self


class StageOneClient(Protocol):
    config: legacy.AgentModelConfig

    def complete_json_certified(
        self,
        prompt: str,
        certificate: legacy.StageOneRequestBindingCertificate,
    ) -> tuple[dict[str, Any], legacy.ModelCallTelemetry]: ...


class InstrumentContractError(RuntimeError):
    pass


class BudgetNoCallError(RuntimeError):
    pass


class _AttemptOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    attempt: SemanticActionAttempt
    payload: dict[str, Any] | None = None
    proposal: CanonicalActionProposal | None = None
    answer: dict[str, Any] | None = None


def make_semantic_action_runner_contract(
    static: SemanticActionStaticInputs,
) -> SemanticActionRunnerContract:
    values = {
        "predecessor_static_contract_id": static.contract.contract_id,
        "predecessor_manifest_id": static.manifest.manifest_id,
        "semantic_action_protocol_id": static.contract.semantic_action_protocol_id,
        "response_grammar_id": static.grammar.grammar_id,
        "candidate_space_authority_audit_id": (static.contract.candidate_space_authority_audit_id),
        "stage_one_profile_id": static.stage_one.profile_id,
        "stage_two_profile_id": static.stage_two.profile_id,
        "resource_contract_id": static.resource.contract_id,
        "rollout_upper_bound_tokens": static.resource.rollout_upper_bound_tokens,
    }
    provisional = SemanticActionRunnerContract.model_construct(contract_id="pending", **values)
    return SemanticActionRunnerContract(
        contract_id=_identity(
            provisional, "contract_id", "finance_v26_semantic_action_runner_contract:"
        ),
        **values,
    )


def semantic_action_runtime_binding(
    static: SemanticActionStaticInputs,
    job: SemanticActionJob,
) -> legacy.RuntimeBinding:
    old_jobs = {item.job_id: item for item in static.historical.manifest.jobs}
    old_job = old_jobs[job.predecessor_job_id]
    binding = legacy.two_stage_runtime_binding(static.historical, old_job)
    task = next(item for item in static.tasks if item.task_package_id == job.task_package_id)
    path = next(item for item in static.paths if item.path_audit_id == job.path_audit_id)
    if (
        task.predecessor_task_package_id != old_job.task_package_id
        or path.predecessor_path_audit_id != old_job.path_audit_id
        or task.operational_record_id != binding.record.record_id
        or path.compiler_trajectory_id != binding.compiler_trajectory.trajectory_id
        or job.path_strategy_id != binding.source_registered_path.path_strategy_id
    ):
        raise ValueError("semantic action Runtime binding changed")
    return binding


def raw_execution_path(output_dir: Path, job: SemanticActionJob) -> Path:
    return output_dir / "raw_execution" / f"{job.job_id.rsplit(':', 1)[-1]}.json"


def raw_provider_path(output_dir: Path, job: SemanticActionJob, call_index: int) -> Path:
    return (
        output_dir
        / "raw_provider_calls"
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


class JournaledSemanticActionClient:
    def __init__(
        self,
        delegate: StageOneClient,
        *,
        runner_contract: SemanticActionRunnerContract,
        resource_contract: SemanticActionResourceContract,
        job: SemanticActionJob,
        output_dir: Path,
    ) -> None:
        legacy.require_stage_one_model_config(delegate.config)
        if (
            job.resource_contract_id != resource_contract.contract_id
            or runner_contract.resource_contract_id != resource_contract.contract_id
            or job.stage_one_profile_id != runner_contract.stage_one_profile_id
            or job.stage_two_profile_id != runner_contract.stage_two_profile_id
        ):
            raise ValueError("semantic action journal client differs from frozen Job route")
        self._delegate = delegate
        self._runner_contract = runner_contract
        self._resource = resource_contract
        self._job = job
        self._output_dir = output_dir
        self._resource_certificates: list[ActionResourceCertificate] = []
        self._telemetry: list[legacy.ModelCallTelemetry] = []
        self._descriptors: list[legacy.RawFileDescriptor] = []
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
    def descriptors(self) -> tuple[legacy.RawFileDescriptor, ...]:
        return tuple(self._descriptors)

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
    ) -> ActionResourceCertificate:
        prompt_bytes = len(prompt.encode("utf-8"))
        prompt_upper = prompt_bytes + self._resource.chat_envelope_tokens
        request_upper = prompt_upper + self._resource.accounted_completion_bound_tokens
        abi = (
            self._request_bound(self._resource.qualified_maximum_abi_rescue_prompt_utf8_bytes)
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
            self._request_bound(self._resource.qualified_maximum_final_answer_prompt_utf8_bytes)
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
        provisional = ActionResourceCertificate.model_construct(certificate_id="pending", **values)
        return ActionResourceCertificate(
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
        abi_rescue_count_before: int,
        semantic_recovery_count_before: int,
    ) -> PreparedActionRequest:
        if self._instrument_failures:
            raise InstrumentContractError(
                "cannot prepare after a semantic action Instrument failure"
            )
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
        dynamic: DynamicActionRequestCertificate | None = None
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
                "prompt_utf8_bytes": len(prompt.encode("utf-8")),
                "abi_rescue_count_before": abi_rescue_count_before,
                "semantic_recovery_count_before": semantic_recovery_count_before,
            }
            provisional = DynamicActionRequestCertificate.model_construct(
                certificate_id="pending", **values
            )
            dynamic = DynamicActionRequestCertificate(
                certificate_id=_identity(
                    provisional,
                    "certificate_id",
                    "finance_v26_dynamic_action_request_certificate:",
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
            "dynamic_certificate": dynamic,
            "request_binding_certificate": request_binding,
            "resource_certificate": resource,
            "provider_invocation_authorized": bool(
                dynamic is not None and resource.provider_call_permitted
            ),
        }
        provisional_request = PreparedActionRequest.model_construct(
            preparation_id="pending", **values
        )
        return PreparedActionRequest(
            preparation_id=_identity(
                provisional_request,
                "preparation_id",
                "finance_v26_prepared_action_request:",
            ),
            **values,
        )

    def _persist(
        self,
        *,
        prepared: PreparedActionRequest,
        payload: dict[str, Any] | None,
        telemetry: legacy.ModelCallTelemetry,
        failure_artifact: legacy.ProspectiveThinkingFailureArtifact | None,
    ) -> None:
        if prepared.dynamic_certificate is None:
            raise ValueError("cannot persist an uncertified semantic action Provider call")
        values = {
            "runner_contract_id": self._runner_contract.contract_id,
            "job_id": self._job.job_id,
            "logical_request_index": prepared.logical_request_index,
            "provider_call_index": len(self._telemetry),
            "request_kind": prepared.request_kind,
            "public_attempt_phase": prepared.public_attempt_phase,
            "prompt_sha256": legacy.sha256_text(prepared.prompt),
            "dynamic_certificate": prepared.dynamic_certificate,
            "request_binding_certificate": prepared.request_binding_certificate,
            "resource_certificate_id": prepared.resource_certificate.certificate_id,
            "response_payload": payload,
            "provider_telemetry": telemetry,
            "failure_artifact": failure_artifact,
        }
        provisional = RawActionProviderCall.model_construct(artifact_id="pending", **values)
        artifact = RawActionProviderCall(
            artifact_id=_identity(
                provisional,
                "artifact_id",
                "finance_v26_raw_action_provider_call:",
            ),
            **values,
        )
        path = raw_provider_path(self._output_dir, self._job, len(self._telemetry))
        write_json_atomic(path, artifact.model_dump(mode="json"))
        self._telemetry.append(telemetry)
        self._descriptors.append(_descriptor(path, self._output_dir))

    def _charge(
        self, prepared: PreparedActionRequest, telemetry: legacy.ModelCallTelemetry
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
        self, prepared: PreparedActionRequest
    ) -> tuple[dict[str, Any], legacy.ModelCallTelemetry]:
        if prepared.preparation_id in self._used_preparations:
            raise InstrumentContractError("prepared semantic action request was reused")
        self._used_preparations.add(prepared.preparation_id)
        if not prepared.resource_certificate.provider_call_permitted:
            raise BudgetNoCallError(str(prepared.resource_certificate.denial_reason))
        if not prepared.provider_invocation_authorized or prepared.dynamic_certificate is None:
            raise InstrumentContractError(
                "semantic action invocation lacks all pre-call certificates"
            )
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
                self._persist(
                    prepared=prepared,
                    payload=None,
                    telemetry=telemetry,
                    failure_artifact=failure,
                )
                self._charge(prepared, telemetry)
            if self._instrument_failures:
                raise InstrumentContractError(";".join(self.instrument_failures)) from exc
            raise
        self._persist(
            prepared=prepared,
            payload=payload,
            telemetry=telemetry,
            failure_artifact=None,
        )
        self._charge(prepared, telemetry)
        if self._instrument_failures:
            raise InstrumentContractError(";".join(self.instrument_failures))
        return payload, telemetry


def _make_attempt(
    *,
    prepared: PreparedActionRequest,
    provider_call_index: int | None,
    disposition: AttemptDisposition,
    response_payload_present: bool,
    exact_four_field_payload: bool = False,
    failure_family: str | None = None,
    failure_subtype: str | None = None,
    completion_failure_type: str | None = None,
    error: str | None = None,
) -> SemanticActionAttempt:
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
        "provider_call_made": provider_call_index is not None,
        "response_payload_present": response_payload_present,
        "exact_four_field_payload": exact_four_field_payload,
        "failure_family": failure_family,
        "failure_subtype": failure_subtype,
        "completion_failure_type": completion_failure_type,
        "disposition": disposition,
        "error": error,
    }
    provisional = SemanticActionAttempt.model_construct(attempt_id="pending", **values)
    return SemanticActionAttempt(
        attempt_id=_identity(provisional, "attempt_id", "finance_v26_semantic_action_attempt:"),
        **values,
    )


def _invoke_attempt(
    ledger: JournaledSemanticActionClient,
    *,
    logical_request_index: int,
    request_kind: legacy.StageOneRequestKind,
    public_attempt_phase: PublicAttemptPhase,
    primary_prompt: str,
    prompt: str,
    state: SemanticActionState | None,
    abi_rescue_count: int,
    semantic_recovery_count: int,
) -> _AttemptOutcome:
    prepared = ledger.prepare(
        logical_request_index=logical_request_index,
        request_kind=request_kind,
        public_attempt_phase=public_attempt_phase,
        primary_prompt=primary_prompt,
        prompt=prompt,
        public_state_id=state.state_id if state is not None else None,
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
    except InstrumentContractError as exc:
        index = before if ledger.provider_call_count > before else None
        return _AttemptOutcome(
            attempt=_make_attempt(
                prepared=prepared,
                provider_call_index=index,
                disposition="instrument_failure",
                response_payload_present=False,
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
                    exact_four_field_payload=True,
                ),
                payload=payload,
                proposal=proposal,
            )
        answer = parse_final_answer_payload(payload)
        return _AttemptOutcome(
            attempt=_make_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="usable",
                response_payload_present=True,
            ),
            payload=payload,
            answer=answer,
        )
    except SemanticActionResponseRejection as exc:
        return _AttemptOutcome(
            attempt=_make_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="model_result_failure",
                response_payload_present=True,
                failure_family=exc.family,
                failure_subtype=exc.subtype,
                error=str(exc),
            ),
            payload=payload,
        )
    except ModelResultRejection as exc:
        return _AttemptOutcome(
            attempt=_make_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="model_result_failure",
                response_payload_present=True,
                failure_family=exc.classification.family,
                failure_subtype=exc.classification.subtype,
                error=str(exc),
            ),
            payload=payload,
        )


def _abi_rescue_allowed(attempt: SemanticActionAttempt) -> bool:
    return attempt.disposition == "completion_failure" or (
        attempt.disposition == "model_result_failure"
        and attempt.failure_family in {"response_serialization_failure", "channel_parse_failure"}
    )


def _active_outcome(
    ledger: JournaledSemanticActionClient,
    *,
    attempts: list[SemanticActionAttempt],
    logical_request_index: int,
    request_kind: legacy.StageOneRequestKind,
    public_attempt_phase: Literal["primary", "semantic_recovery"],
    primary_prompt: str,
    state: SemanticActionState | None,
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
            else legacy.render_semantically_sufficient_final_rescue_prompt(
                primary_prompt, failure_type=subtype
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
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        attempts.append(rescue.attempt)
        return rescue, abi_rescue_count
    return primary, abi_rescue_count


def _terminal_from_attempt(attempt: SemanticActionAttempt) -> TerminalDisposition:
    if attempt.disposition == "completion_failure":
        return "completion_unusable"
    if attempt.disposition == "provider_transport_failure":
        return "provider_transport_failure"
    if attempt.disposition == "typed_budget_no_call":
        return "typed_budget_no_call"
    if attempt.disposition == "instrument_failure":
        return "instrument_failure"
    return "model_result"


def _choice_record(
    *,
    logical_request_index: int,
    phase: Literal["primary", "semantic_recovery"],
    state: SemanticActionState,
    proposal: CanonicalActionProposal,
    commit: CanonicalActionCommit | None,
    rejection: PublicSemanticRejectionObservation | None,
    prior_rejected_action_id: str | None,
    observation: AgentToolObservation | None,
    progress: bool | None,
) -> SemanticChoiceRecord:
    candidates = {item.action_id: item for item in state.action_candidates}
    candidate = candidates.get(proposal.action_id)
    values = {
        "logical_request_index": logical_request_index,
        "public_attempt_phase": phase,
        "state_id": state.state_id,
        "proposal_id": proposal.proposal_id,
        "selected_action_id": proposal.action_id,
        "decision_kind": proposal.decision_kind,
        "visible_action_id_match": candidate is not None,
        "decision_kind_match": bool(
            candidate is not None and candidate.decision_kind == proposal.decision_kind
        ),
        "semantic_accepted": commit is not None,
        "rejection_id": rejection.rejection_id if rejection is not None else None,
        "commit_id": commit.commit_id if commit is not None else None,
        "different_action_after_rejection": (
            proposal.action_id != prior_rejected_action_id
            if phase == "semantic_recovery" and prior_rejected_action_id is not None
            else None
        ),
        "observation_status": observation.status if observation is not None else None,
        "public_progress_after_commit": progress,
    }
    provisional = SemanticChoiceRecord.model_construct(record_id="pending", **values)
    return SemanticChoiceRecord(
        record_id=_identity(provisional, "record_id", "finance_v26_semantic_choice_record:"),
        **values,
    )


def _public_progress(
    before: SemanticActionState,
    after: SemanticActionState,
    observation: AgentToolObservation,
) -> bool:
    return bool(
        observation.status == "succeeded"
        and (
            len(after.unresolved_symbols) < len(before.unresolved_symbols)
            or len(after.source_references) > len(before.source_references)
            or after.terminal_operation_ref != before.terminal_operation_ref
            or after.terminal_verification_completed != before.terminal_verification_completed
        )
    )


def _finish_raw(
    *,
    runner_contract: SemanticActionRunnerContract,
    job: SemanticActionJob,
    binding: legacy.RuntimeBinding,
    ledger: JournaledSemanticActionClient,
    attempts: Sequence[SemanticActionAttempt],
    choices: Sequence[SemanticChoiceRecord],
    commits: Sequence[SemanticActionCommitRecord],
    semantic_rejections: Sequence[PublicSemanticRejectionObservation],
    observations: Sequence[AgentToolObservation],
    completed: SemanticActionCompletedResult | None,
    terminal: TerminalDisposition,
    failure_type: str | None,
    error: str | None,
    output_dir: Path,
) -> SemanticActionRawExecution:
    values = {
        "runner_contract_id": runner_contract.contract_id,
        "job": job,
        "operational_record_id": binding.record.record_id,
        "environment_manifest_id": binding.environment.manifest_id,
        "path_audit_id": job.path_audit_id,
        "provider_call_artifacts": ledger.descriptors,
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
    provisional = SemanticActionRawExecution.model_construct(artifact_id="pending", **values)
    raw = SemanticActionRawExecution(
        artifact_id=_identity(
            provisional, "artifact_id", "finance_v26_semantic_action_raw_execution:"
        ),
        **values,
    )
    write_json_atomic(raw_execution_path(output_dir, job), raw.model_dump(mode="json"))
    return raw


def execute_semantic_action_job_raw(
    *,
    job: SemanticActionJob,
    runner_contract: SemanticActionRunnerContract,
    static: SemanticActionStaticInputs,
    binding: legacy.RuntimeBinding,
    client: StageOneClient | None,
    output_dir: Path,
) -> SemanticActionRawExecution:
    raw_path = raw_execution_path(output_dir, job)
    if raw_path.exists():
        raw = SemanticActionRawExecution.model_validate(legacy.load_canonical_json(raw_path))
        if raw.runner_contract_id != runner_contract.contract_id or raw.job != job:
            raise ValueError("semantic action Raw recovery crosses frozen identities")
        for descriptor in raw.provider_call_artifacts:
            path = output_dir / descriptor.relative_path
            if not path.is_file() or legacy.sha256_file(path) != descriptor.sha256:
                raise ValueError("semantic action Raw recovery Provider bytes changed")
            RawActionProviderCall.model_validate(legacy.load_canonical_json(path))
        return raw
    provider_dir = raw_provider_path(output_dir, job, 0).parent
    if provider_dir.exists() and any(provider_dir.glob("call_*.json")):
        raise ValueError("orphan semantic action Provider artifacts forbid retry")
    if client is None:
        raise ValueError("pending semantic action Job has no Stage 1 client")
    if (
        job.contract_id != static.contract.contract_id
        or job.task_package_id not in {item.task_package_id for item in static.tasks}
        or job.path_audit_id not in {item.path_audit_id for item in static.paths}
    ):
        raise ValueError("semantic action Job differs from its static identity chain")
    ledger = JournaledSemanticActionClient(
        client,
        runner_contract=runner_contract,
        resource_contract=static.resource,
        job=job,
        output_dir=output_dir,
    )
    runtime = legacy._runtime(binding.record, binding.environment)
    observations: list[AgentToolObservation] = []
    attempts: list[SemanticActionAttempt] = []
    choices: list[SemanticChoiceRecord] = []
    commits: list[SemanticActionCommitRecord] = []
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
    completed: SemanticActionCompletedResult | None = None
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
                grammar=static.grammar,
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
                _choice_record(
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
            raise ValueError("accepted semantic action lacks a Commit")
        commit_values = {
            "logical_request_index": current_index,
            "public_state_id": state.state_id,
            "proposal": proposal,
            "commit": commit,
            "stage_two_profile_id": static.stage_two.profile_id,
            "provider_calls_before_commit": ledger.provider_call_count,
        }
        provisional_commit = SemanticActionCommitRecord.model_construct(
            record_id="pending", **commit_values
        )
        commits.append(
            SemanticActionCommitRecord(
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
            progress = _public_progress(state, after, observation)
        choices.append(
            _choice_record(
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
            break
    else:
        terminal = "model_result"
        failure_type = "semantic_action_primary_request_limit_exhausted"
        error = "model did not reach final Commit within the frozen request limit"
    if (
        commits
        and commits[-1].commit.action == "emit_final"
        and terminal == "model_result"
        and failure_type is None
    ):
        final_prompt = render_compact_final_prompt(
            binding.prompt_contract.public_context,
            binding.record.task_package.task.public,
            tuple(observations),
            public_path_condition=condition,
        )
        outcome, abi_rescue_count = _active_outcome(
            ledger,
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="final_answer",
            public_attempt_phase="primary",
            primary_prompt=final_prompt,
            state=None,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        if outcome.attempt.disposition == "usable" and outcome.answer is not None:
            citations = legacy._selected_evidence_ids(observations)
            if not citations:
                terminal = "model_result"
                failure_type = "final_answer_without_public_evidence"
                error = "final answer has no selected public Evidence"
            else:
                values = {
                    "job_id": job.job_id,
                    "answer": outcome.answer,
                    "cited_evidence_ids": citations,
                    "final_attempt_id": outcome.attempt.attempt_id,
                }
                provisional = SemanticActionCompletedResult.model_construct(
                    result_id="pending", **values
                )
                completed = SemanticActionCompletedResult(
                    result_id=_identity(
                        provisional,
                        "result_id",
                        "finance_v26_semantic_action_completed_result:",
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


def response_protocol() -> str:
    return RESPONSE_PROTOCOL_VERSION
