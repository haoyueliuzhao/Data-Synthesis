from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_action_constructibility_two_stage_preflight import (  # noqa: E501
    make_authority_preserving_replay_v3_contract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_completion_calibration_contracts import (  # noqa: E501
    RawFileDescriptor,
    load_canonical_json,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_completion_calibration_execution import (  # noqa: E501
    RuntimeBinding,
    _runtime,
    load_static_inputs,
    runtime_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501
    _execute_observation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_profile_and_manifest_preflight import (  # noqa: E501
    StageOneThinkingProfile,
    StageTwoCommitProfile,
    TwoStageExecutionContract,
    TwoStageJob,
    TwoStageManifest,
    TwoStagePathAudit,
    TwoStageResourceContract,
    TwoStageStaticPreflightReport,
    TwoStageTaskPackage,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.client import LLMClientError
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_action_constructibility import (
    DecisionCommitCompilation,
    ProspectiveFailureClassification,
    PublicActionState,
    SemanticDecisionProposal,
    build_public_action_state,
    compile_semantic_decision,
    render_action_constructible_decision_prompt,
    render_semantically_sufficient_final_rescue_prompt,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    ProspectiveThinkingFailureArtifact,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_semantic_proposal import (
    ModelResultRejection,
    parse_final_answer_payload,
    parse_semantic_proposal_payload,
    render_semantic_proposal_rescue_prompt,
    semantic_proposal_signature,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    STAGE_ONE_MODEL_ID,
    StageOneAttemptPhase,
    StageOneRequestBindingCertificate,
    StageOneRequestKind,
    certify_stage_one_request_pre_call,
    require_stage_one_model_config,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolObservation

V26_108_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_108_two_stage_profile_and_manifest_preflight_v1_20260822"
)
EXPECTED_V26_108_REPORT_ID: Final = (
    "finance_v26_two_stage_static_preflight_report:"
    "5ec8e8c6b22463f7a77fc75cb46b3d13139e6b43c5494fb81fcf106579230c7a"
)
EXPECTED_V26_108_CONTRACT_ID: Final = (
    "finance_v26_two_stage_execution_contract:"
    "52b63ce8293d9cbfe82f9cc54512b72706edd77ecc135e20e8f9cfce7cc8888b"
)
EXPECTED_V26_108_MANIFEST_ID: Final = (
    "finance_v26_two_stage_manifest:"
    "c11af7e8a4bc20e7d136b68c564b98abd884f9310e153d009ef14b80d75d8dd2"
)
EXPECTED_V26_108_RESOURCE_ID: Final = (
    "finance_v26_two_stage_resource_contract:"
    "a54be4f1c8344fc0f35eaef1a73f04136bec872cb4817273b8fb8c7e2b57a0ca"
)
STAGE_ONE_PROFILE_PATH: Final = (
    "config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
)
RUNNER_RUN_ID: Final = "finance_v26_109_two_stage_semantic_proposal_runner_preflight_v1_20260822"
EXECUTION_RUN_ID: Final = "finance_v26_110_two_stage_semantic_proposal_calibration_v1"

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


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TwoStageRunnerContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_static_contract_id: str = EXPECTED_V26_108_CONTRACT_ID
    predecessor_manifest_id: str = EXPECTED_V26_108_MANIFEST_ID
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    resource_contract_id: str = EXPECTED_V26_108_RESOURCE_ID
    exact_job_denominator: Literal[32] = 32
    runner_run_id: str = RUNNER_RUN_ID
    execution_run_id: str = EXECUTION_RUN_ID
    stage_one_request_kinds: tuple[str, str] = ("semantic_proposal", "final_answer")
    stage_two_request_kind: Literal["deterministic_commit"] = "deterministic_commit"
    stage_two_provider_call_upper_bound: Literal[0] = 0
    exact_request_completion_bound_tokens: Literal[16384] = 16384
    provider_accounting_margin_tokens: Literal[1] = 1
    rollout_upper_bound_tokens: Literal[260000] = 260000
    maximum_primary_stage_one_requests: Literal[10] = 10
    maximum_global_rescue_calls: Literal[1] = 1
    semantic_compile_rejection_is_model_result: Literal[True] = True
    response_serialization_failure_is_model_result: Literal[True] = True
    decision_phase_failure_is_model_result: Literal[True] = True
    prompt_echo_is_model_result: Literal[True] = True
    duplicate_failed_proposal_is_model_result: Literal[True] = True
    channel_completion_failure_may_use_one_rescue: Literal[True] = True
    serialization_phase_or_echo_may_use_one_rescue: Literal[True] = True
    semantic_compile_rejection_may_use_rescue: Literal[False] = False
    raw_provider_persisted_before_projection: Literal[True] = True
    raw_only_recovery: Literal[True] = True
    orphan_provider_artifact_fails_closed: Literal[True] = True
    private_reasoning_persistence_allowed: Literal[False] = False
    runner_implemented: Literal[True] = True
    empirical_execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_two_stage_runner_contract.v1"] = (
        "finance_v26_two_stage_runner_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> TwoStageRunnerContract:
        if self.contract_id != two_stage_runner_contract_id(self):
            raise ValueError("v26.109 Runner Contract identity changed")
        return self


class DynamicStageOneCertificate(FrozenModel):
    certificate_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    request_kind: StageOneRequestKind
    phase: StageOneAttemptPhase
    primary_prompt_sha256: str = Field(min_length=64, max_length=64)
    request_prompt_sha256: str = Field(min_length=64, max_length=64)
    public_state_id: str | None = None
    prompt_utf8_bytes: int = Field(gt=0, le=60000)
    rescue_prompt_within_absolute_ceiling: bool | None = None
    request_kind_inferred_from_actual_public_state: Literal[True] = True
    primary_prompt_rendered_before_certificate: Literal[True] = True
    rescue_rendered_before_certificate: Literal[True] | None = None
    stage_two_provider_calls_before_certificate: Literal[0] = 0
    provider_calls_before_certificate: Literal[0] = 0
    schema_version: Literal["finance_v26_dynamic_stage_one_certificate.v1"] = (
        "finance_v26_dynamic_stage_one_certificate.v1"
    )

    @model_validator(mode="after")
    def validate_certificate(self) -> DynamicStageOneCertificate:
        if self.phase == "rescue":
            if self.rescue_prompt_within_absolute_ceiling is not True:
                raise ValueError("v26.109 Rescue certificate is not absolutely bounded")
            if self.rescue_rendered_before_certificate is not True:
                raise ValueError("v26.109 Rescue was not rendered before certification")
        elif self.rescue_prompt_within_absolute_ceiling is not None:
            raise ValueError("v26.109 Primary certificate carries Rescue state")
        if self.certificate_id != dynamic_stage_one_certificate_id(self):
            raise ValueError("v26.109 dynamic certificate identity changed")
        return self


class StageOneResourceCertificate(FrozenModel):
    certificate_id: str = Field(min_length=1)
    resource_contract_id: str = EXPECTED_V26_108_RESOURCE_ID
    request_index: int = Field(ge=0)
    request_kind: StageOneRequestKind
    phase: StageOneAttemptPhase
    request_prompt_sha256: str = Field(min_length=64, max_length=64)
    prompt_utf8_bytes: int = Field(gt=0)
    prompt_token_upper_bound: int = Field(gt=0)
    completion_token_upper_bound: Literal[16385] = 16385
    request_token_upper_bound: int = Field(gt=0)
    cumulative_provider_tokens_before: int = Field(ge=0)
    rescue_reserve_tokens: int = Field(ge=0, le=16385)
    final_answer_reserve_tokens: int = Field(ge=0, le=16385)
    required_reserve_tokens: int = Field(ge=0, le=32770)
    projected_upper_total: int = Field(gt=0)
    rollout_upper_bound_tokens: Literal[260000] = 260000
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
    schema_version: Literal["finance_v26_stage_one_resource_certificate.v1"] = (
        "finance_v26_stage_one_resource_certificate.v1"
    )

    @model_validator(mode="after")
    def validate_certificate(self) -> StageOneResourceCertificate:
        if self.prompt_token_upper_bound != self.prompt_utf8_bytes + 256:
            raise ValueError("v26.109 Prompt upper-bound arithmetic changed")
        if self.request_token_upper_bound != self.prompt_token_upper_bound + 16385:
            raise ValueError("v26.109 request upper-bound arithmetic changed")
        if self.required_reserve_tokens != (
            self.rescue_reserve_tokens + self.final_answer_reserve_tokens
        ):
            raise ValueError("v26.109 required reserve arithmetic changed")
        if self.provider_call_permitted != (self.decision == "allowed"):
            raise ValueError("v26.109 Provider permission differs from resource decision")
        if (self.denial_reason is None) != self.provider_call_permitted:
            raise ValueError("v26.109 denial reason accounting changed")
        if self.certificate_id != stage_one_resource_certificate_id(self):
            raise ValueError("v26.109 resource certificate identity changed")
        return self


class PreparedStageOneRequest(FrozenModel):
    preparation_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    request_kind: StageOneRequestKind
    phase: StageOneAttemptPhase
    primary_prompt: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    public_state_id: str | None = None
    dynamic_certificate: DynamicStageOneCertificate | None = None
    request_binding_certificate: StageOneRequestBindingCertificate
    resource_certificate: StageOneResourceCertificate
    provider_invocation_authorized: bool
    provider_calls_before_preparation: Literal[0] = 0

    @model_validator(mode="after")
    def validate_preparation(self) -> PreparedStageOneRequest:
        prompt_hash = sha256_text(self.prompt)
        if (
            self.request_binding_certificate.prompt_sha256 != prompt_hash
            or self.resource_certificate.request_prompt_sha256 != prompt_hash
        ):
            raise ValueError("v26.109 prepared Prompt binding changed")
        if (
            self.request_binding_certificate.request_kind != self.request_kind
            or self.request_binding_certificate.phase != self.phase
            or self.resource_certificate.request_kind != self.request_kind
            or self.resource_certificate.phase != self.phase
            or (
                self.dynamic_certificate is not None
                and (
                    self.dynamic_certificate.request_kind != self.request_kind
                    or self.dynamic_certificate.phase != self.phase
                )
            )
        ):
            raise ValueError("v26.109 prepared request kind or phase binding changed")
        complete = self.dynamic_certificate is not None
        if self.provider_invocation_authorized != bool(
            complete and self.resource_certificate.provider_call_permitted
        ):
            raise ValueError("v26.109 invocation authorization changed")
        if self.preparation_id != prepared_stage_one_request_id(self):
            raise ValueError("v26.109 prepared request identity changed")
        return self


class RawStageOneProviderCall(FrozenModel):
    artifact_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    provider_call_index: int = Field(ge=0)
    request_kind: StageOneRequestKind
    phase: StageOneAttemptPhase
    prompt_sha256: str = Field(min_length=64, max_length=64)
    dynamic_certificate: DynamicStageOneCertificate
    request_binding_certificate: StageOneRequestBindingCertificate
    resource_certificate_id: str = Field(min_length=1)
    response_payload: dict[str, Any] | None = None
    provider_telemetry: ModelCallTelemetry
    failure_artifact: ProspectiveThinkingFailureArtifact | None = None
    captured_before_response_projection: Literal[True] = True
    stage_two_provider_call_count: Literal[0] = 0
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    raw_request_body_persisted: Literal[False] = False
    schema_version: Literal["finance_v26_raw_stage_one_provider_call.v1"] = (
        "finance_v26_raw_stage_one_provider_call.v1"
    )

    @model_validator(mode="after")
    def validate_artifact(self) -> RawStageOneProviderCall:
        if (
            self.provider_telemetry.request_hash != self.prompt_sha256
            or self.dynamic_certificate.request_prompt_sha256 != self.prompt_sha256
            or self.request_binding_certificate.prompt_sha256 != self.prompt_sha256
        ):
            raise ValueError("v26.109 Raw Provider Prompt binding changed")
        if contains_private_reasoning(self.response_payload):
            raise ValueError("v26.109 public payload contains private reasoning")
        if self.artifact_id != raw_stage_one_provider_call_id(self):
            raise ValueError("v26.109 Raw Provider identity changed")
        return self


class StageOneAttempt(FrozenModel):
    attempt_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    provider_call_index: int | None = Field(default=None, ge=0)
    request_kind: StageOneRequestKind
    phase: StageOneAttemptPhase
    prompt_sha256: str = Field(min_length=64, max_length=64)
    prompt_utf8_bytes: int = Field(gt=0)
    dynamic_certificate_id: str | None = None
    request_binding_certificate_id: str | None = None
    resource_certificate_id: str | None = None
    provider_call_made: bool
    response_payload_present: bool
    model_failure_classification: ProspectiveFailureClassification | None = None
    completion_failure_type: str | None = None
    disposition: AttemptDisposition
    error: str | None = None
    previous_response_content_reused: Literal[False] = False
    private_reasoning_reused: Literal[False] = False
    host_semantic_action_inserted: Literal[False] = False
    schema_version: Literal["finance_v26_stage_one_attempt.v1"] = "finance_v26_stage_one_attempt.v1"

    @model_validator(mode="after")
    def validate_attempt(self) -> StageOneAttempt:
        certificates = (
            self.dynamic_certificate_id,
            self.request_binding_certificate_id,
            self.resource_certificate_id,
        )
        if self.provider_call_made != (self.provider_call_index is not None):
            raise ValueError("v26.109 Provider call index accounting changed")
        if self.provider_call_made and not all(certificates):
            raise ValueError("v26.109 Provider call preceded a certificate")
        if self.attempt_id != stage_one_attempt_id(self):
            raise ValueError("v26.109 Stage 1 attempt identity changed")
        return self


class StageTwoCommitRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    public_state_id: str = Field(min_length=1)
    proposal: SemanticDecisionProposal
    commit: DecisionCommitCompilation
    stage_two_profile_id: str = Field(min_length=1)
    provider_calls_before_commit: int = Field(ge=1)
    stage_two_provider_calls: Literal[0] = 0
    semantic_choice_inserted_by_host: Literal[False] = False
    reversible_mapping_passed: Literal[True] = True
    schema_version: Literal["finance_v26_stage_two_commit_record.v1"] = (
        "finance_v26_stage_two_commit_record.v1"
    )

    @model_validator(mode="after")
    def validate_record(self) -> StageTwoCommitRecord:
        if (
            self.proposal.state_id != self.public_state_id
            or self.commit.state_id != self.public_state_id
            or self.commit.proposal_id != self.proposal.proposal_id
        ):
            raise ValueError("v26.109 Commit record parent binding changed")
        if self.record_id != stage_two_commit_record_id(self):
            raise ValueError("v26.109 Commit record identity changed")
        return self


class TwoStageCompletedResult(FrozenModel):
    result_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    answer: dict[str, Any] = Field(min_length=1)
    cited_evidence_ids: tuple[str, ...] = Field(min_length=1)
    final_attempt_id: str = Field(min_length=1)
    schema_version: Literal["finance_v26_two_stage_completed_result.v1"] = (
        "finance_v26_two_stage_completed_result.v1"
    )

    @model_validator(mode="after")
    def validate_result(self) -> TwoStageCompletedResult:
        if self.cited_evidence_ids != tuple(sorted(set(self.cited_evidence_ids))):
            raise ValueError("v26.109 cited Evidence is not canonical")
        if self.result_id != two_stage_completed_result_id(self):
            raise ValueError("v26.109 completed-result identity changed")
        return self


class TwoStageRawExecution(FrozenModel):
    artifact_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    job: TwoStageJob
    operational_record_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    path_audit_id: str = Field(min_length=1)
    provider_call_artifacts: tuple[RawFileDescriptor, ...]
    provider_telemetry: tuple[ModelCallTelemetry, ...]
    attempts: tuple[StageOneAttempt, ...] = Field(min_length=1)
    commits: tuple[StageTwoCommitRecord, ...]
    observations: tuple[AgentToolObservation, ...]
    completed_result: TwoStageCompletedResult | None = None
    terminal_disposition: TerminalDisposition
    terminal_failure_type: str | None = None
    execution_error: str | None = None
    cumulative_provider_tokens: int = Field(ge=0)
    stage_one_provider_call_count: int = Field(ge=0, le=11)
    stage_two_provider_call_count: Literal[0] = 0
    rescue_attempt_count: int = Field(ge=0, le=1)
    model_discovery_call_count: Literal[0] = 0
    captured_before_verifier_scoring: Literal[True] = True
    private_reasoning_content_persisted: Literal[False] = False
    schema_version: Literal["finance_v26_two_stage_raw_execution.v1"] = (
        "finance_v26_two_stage_raw_execution.v1"
    )

    @model_validator(mode="after")
    def validate_execution(self) -> TwoStageRawExecution:
        if self.stage_one_provider_call_count != len(self.provider_telemetry):
            raise ValueError("v26.109 Stage 1 Provider denominator changed")
        if len(self.provider_call_artifacts) != self.stage_one_provider_call_count:
            raise ValueError("v26.109 Provider artifact denominator changed")
        if self.rescue_attempt_count != sum(item.phase == "rescue" for item in self.attempts):
            raise ValueError("v26.109 Rescue attempt denominator changed")
        if (self.completed_result is not None) != (self.terminal_disposition == "completed"):
            raise ValueError("v26.109 completed-result terminal changed")
        if self.artifact_id != two_stage_raw_execution_id(self):
            raise ValueError("v26.109 Raw Execution identity changed")
        return self


class TwoStageStaticInputs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    report: TwoStageStaticPreflightReport
    predecessor_contract: TwoStageExecutionContract
    manifest: TwoStageManifest
    resource: TwoStageResourceContract
    stage_one: StageOneThinkingProfile
    stage_two: StageTwoCommitProfile
    tasks: tuple[TwoStageTaskPackage, ...]
    paths: tuple[TwoStagePathAudit, ...]
    agent_model_config: AgentModelConfig
    historical: Any


class StageOneClient(Protocol):
    config: AgentModelConfig

    def complete_json_certified(
        self,
        prompt: str,
        certificate: StageOneRequestBindingCertificate,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]: ...


class InstrumentContractError(RuntimeError):
    pass


class BudgetNoCallError(RuntimeError):
    pass


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def two_stage_runner_contract_id(value: TwoStageRunnerContract) -> str:
    return _identity(value, "contract_id", "finance_v26_two_stage_runner_contract:")


def dynamic_stage_one_certificate_id(value: DynamicStageOneCertificate) -> str:
    return _identity(value, "certificate_id", "finance_v26_dynamic_stage_one_certificate:")


def stage_one_resource_certificate_id(value: StageOneResourceCertificate) -> str:
    return _identity(value, "certificate_id", "finance_v26_stage_one_resource_certificate:")


def prepared_stage_one_request_id(value: PreparedStageOneRequest) -> str:
    return _identity(value, "preparation_id", "finance_v26_prepared_stage_one_request:")


def raw_stage_one_provider_call_id(value: RawStageOneProviderCall) -> str:
    return _identity(value, "artifact_id", "finance_v26_raw_stage_one_provider_call:")


def stage_one_attempt_id(value: StageOneAttempt) -> str:
    return _identity(value, "attempt_id", "finance_v26_stage_one_attempt:")


def stage_two_commit_record_id(value: StageTwoCommitRecord) -> str:
    return _identity(value, "record_id", "finance_v26_stage_two_commit_record:")


def two_stage_completed_result_id(value: TwoStageCompletedResult) -> str:
    return _identity(value, "result_id", "finance_v26_two_stage_completed_result:")


def two_stage_raw_execution_id(value: TwoStageRawExecution) -> str:
    return _identity(value, "artifact_id", "finance_v26_two_stage_raw_execution:")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contains_private_reasoning(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).casefold()
            if "reasoning" in normalized and normalized not in {
                "reasoning_content_present",
                "reasoning_content_length",
                "reasoning_tokens",
            }:
                return True
            if contains_private_reasoning(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(contains_private_reasoning(item) for item in value)
    return False


def _load_models(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    payload = load_canonical_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"expected canonical array: {path}")
    return tuple(model.model_validate(item) for item in payload)


def load_two_stage_static_inputs(
    package_root: Path,
    implementation_root: Path,
) -> TwoStageStaticInputs:
    root = implementation_root / V26_108_DIR
    report = TwoStageStaticPreflightReport.model_validate(load_canonical_json(root / "report.json"))
    contract = TwoStageExecutionContract.model_validate(
        load_canonical_json(root / "two_stage_execution_contract.json")
    )
    manifest = TwoStageManifest.model_validate(
        load_canonical_json(root / "two_stage_job_manifest.json")
    )
    resource = TwoStageResourceContract.model_validate(
        load_canonical_json(root / "two_stage_resource_contract.json")
    )
    stage_one = StageOneThinkingProfile.model_validate(
        load_canonical_json(root / "stage_one_thinking_profile.json")
    )
    stage_two = StageTwoCommitProfile.model_validate(
        load_canonical_json(root / "stage_two_commit_profile.json")
    )
    tasks = cast(
        tuple[TwoStageTaskPackage, ...],
        _load_models(root / "two_stage_task_packages.json", TwoStageTaskPackage),
    )
    paths = cast(
        tuple[TwoStagePathAudit, ...],
        _load_models(root / "two_stage_path_audits.json", TwoStagePathAudit),
    )
    profile_payload = json.loads(
        (implementation_root / STAGE_ONE_PROFILE_PATH).read_text(encoding="utf-8")
    )
    if not isinstance(profile_payload, Mapping):
        raise ValueError("v26.109 Stage 1 profile is not an object")
    model_config = require_stage_one_model_config(
        AgentModelConfig.model_validate(profile_payload["model"])
    )
    if (
        report.report_id != EXPECTED_V26_108_REPORT_ID
        or contract.contract_id != EXPECTED_V26_108_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_V26_108_MANIFEST_ID
        or resource.contract_id != EXPECTED_V26_108_RESOURCE_ID
        or manifest.contract_id != contract.contract_id
        or report.runner_implemented
        or report.execution_authorized
        or stage_two.provider_call_upper_bound != 0
    ):
        raise ValueError("v26.109 static predecessor binding changed")
    historical = load_static_inputs(package_root)
    predecessor_jobs = {item.job_id: item for item in historical.predecessor_manifest.jobs}
    for job in manifest.jobs:
        runtime_binding(historical, predecessor_jobs[job.predecessor_job_id])
    return TwoStageStaticInputs(
        report=report,
        predecessor_contract=contract,
        manifest=manifest,
        resource=resource,
        stage_one=stage_one,
        stage_two=stage_two,
        tasks=tasks,
        paths=paths,
        agent_model_config=model_config,
        historical=historical,
    )


def two_stage_runtime_binding(
    inputs: TwoStageStaticInputs,
    job: TwoStageJob,
) -> RuntimeBinding:
    predecessor_jobs = {item.job_id: item for item in inputs.historical.predecessor_manifest.jobs}
    predecessor = predecessor_jobs[job.predecessor_job_id]
    binding = runtime_binding(inputs.historical, predecessor)
    task = next(item for item in inputs.tasks if item.task_package_id == job.task_package_id)
    path = next(item for item in inputs.paths if item.path_audit_id == job.path_audit_id)
    if (
        task.predecessor_task_package_id != predecessor.task_package_id
        or path.predecessor_path_audit_id != predecessor.path_audit_id
        or task.operational_record_id != binding.record.record_id
        or path.compiler_trajectory_id != binding.compiler_trajectory.trajectory_id
        or job.path_strategy_id != binding.source_registered_path.path_strategy_id
    ):
        raise ValueError("v26.109 fresh Job does not preserve its frozen runtime binding")
    return binding


def raw_execution_path(output_dir: Path, job: TwoStageJob) -> Path:
    return output_dir / "raw_execution" / f"{job.job_id.rsplit(':', 1)[-1]}.json"


def raw_provider_path(output_dir: Path, job: TwoStageJob, call_index: int) -> Path:
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


def _descriptor(path: Path, output_dir: Path) -> RawFileDescriptor:
    return RawFileDescriptor(
        relative_path=str(path.resolve().relative_to(output_dir.resolve())),
        sha256=sha256_file(path),
        byte_count=path.stat().st_size,
    )


class JournaledStageOneClient:
    def __init__(
        self,
        delegate: StageOneClient,
        *,
        runner_contract: TwoStageRunnerContract,
        resource_contract: TwoStageResourceContract,
        job: TwoStageJob,
        output_dir: Path,
    ) -> None:
        require_stage_one_model_config(delegate.config)
        if (
            job.resource_contract_id != resource_contract.contract_id
            or runner_contract.resource_contract_id != resource_contract.contract_id
            or job.stage_one_profile_id != runner_contract.stage_one_profile_id
            or job.stage_two_profile_id != runner_contract.stage_two_profile_id
        ):
            raise ValueError("v26.109 journal client differs from the frozen Job route")
        self._delegate = delegate
        self._runner_contract = runner_contract
        self._resource_contract = resource_contract
        self._job = job
        self._output_dir = output_dir
        self._resource_certificates: list[StageOneResourceCertificate] = []
        self._telemetry: list[ModelCallTelemetry] = []
        self._descriptors: list[RawFileDescriptor] = []
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
    def telemetry(self) -> tuple[ModelCallTelemetry, ...]:
        return tuple(self._telemetry)

    @property
    def descriptors(self) -> tuple[RawFileDescriptor, ...]:
        return tuple(self._descriptors)

    @property
    def instrument_failures(self) -> tuple[str, ...]:
        return tuple(sorted(self._instrument_failures))

    def _resource_certificate(
        self,
        prompt: str,
        *,
        request_kind: StageOneRequestKind,
        phase: StageOneAttemptPhase,
        rescue_available_before: bool,
    ) -> StageOneResourceCertificate:
        prompt_bytes = len(prompt.encode("utf-8"))
        prompt_upper = prompt_bytes + self._resource_contract.chat_envelope_tokens
        request_upper = prompt_upper + self._resource_contract.accounted_completion_bound_tokens
        rescue = (
            self._resource_contract.accounted_completion_bound_tokens
            if phase == "primary" and rescue_available_before
            else 0
        )
        final = (
            self._resource_contract.accounted_completion_bound_tokens
            if request_kind == "semantic_proposal"
            else 0
        )
        projected = self._cumulative_tokens + request_upper + rescue + final
        denial: str | None = None
        if (
            len(self._resource_certificates)
            >= self._resource_contract.maximum_stage_one_provider_calls
        ):
            denial = "stage_one_request_count_exhausted"
        elif prompt_bytes > self._resource_contract.prompt_upper_bound_bytes:
            denial = "oversized_prompt"
        elif (
            self._cumulative_tokens + request_upper
            > self._resource_contract.rollout_upper_bound_tokens
        ):
            denial = "request_bound_exceeds_remaining_budget"
        elif projected > self._resource_contract.rollout_upper_bound_tokens:
            denial = "required_reserve_not_available"
        values: dict[str, Any] = {
            "request_index": len(self._resource_certificates),
            "request_kind": request_kind,
            "phase": phase,
            "request_prompt_sha256": sha256_text(prompt),
            "prompt_utf8_bytes": prompt_bytes,
            "prompt_token_upper_bound": prompt_upper,
            "request_token_upper_bound": request_upper,
            "cumulative_provider_tokens_before": self._cumulative_tokens,
            "rescue_reserve_tokens": rescue,
            "final_answer_reserve_tokens": final,
            "required_reserve_tokens": rescue + final,
            "projected_upper_total": projected,
            "decision": "denied_no_call" if denial else "allowed",
            "denial_reason": denial,
            "provider_call_permitted": denial is None,
        }
        provisional = StageOneResourceCertificate.model_construct(
            certificate_id="pending", **values
        )
        return StageOneResourceCertificate(
            certificate_id=stage_one_resource_certificate_id(provisional),
            **values,
        )

    def prepare(
        self,
        *,
        logical_request_index: int,
        request_kind: StageOneRequestKind,
        phase: StageOneAttemptPhase,
        primary_prompt: str,
        prompt: str,
        public_state_id: str | None,
        rescue_available_before: bool,
    ) -> PreparedStageOneRequest:
        if self._instrument_failures:
            raise InstrumentContractError(
                "v26.109 cannot prepare after an Instrument contract failure"
            )
        request_binding = certify_stage_one_request_pre_call(
            config=self._delegate.config,
            prompt=prompt,
            request_kind=request_kind,
            phase=phase,
        )
        resource = self._resource_certificate(
            prompt,
            request_kind=request_kind,
            phase=phase,
            rescue_available_before=rescue_available_before,
        )
        self._resource_certificates.append(resource)
        dynamic: DynamicStageOneCertificate | None = None
        if resource.provider_call_permitted:
            dynamic_values: dict[str, Any] = {
                "runner_contract_id": self._runner_contract.contract_id,
                "job_id": self._job.job_id,
                "logical_request_index": logical_request_index,
                "request_kind": request_kind,
                "phase": phase,
                "primary_prompt_sha256": sha256_text(primary_prompt),
                "request_prompt_sha256": sha256_text(prompt),
                "public_state_id": public_state_id,
                "prompt_utf8_bytes": len(prompt.encode("utf-8")),
                "rescue_prompt_within_absolute_ceiling": (
                    len(prompt.encode("utf-8")) <= 6144 if phase == "rescue" else None
                ),
                "rescue_rendered_before_certificate": True if phase == "rescue" else None,
            }
            dynamic_provisional = DynamicStageOneCertificate.model_construct(
                certificate_id="pending", **dynamic_values
            )
            dynamic = DynamicStageOneCertificate(
                certificate_id=dynamic_stage_one_certificate_id(dynamic_provisional),
                **dynamic_values,
            )
        request_values: dict[str, Any] = {
            "logical_request_index": logical_request_index,
            "request_kind": request_kind,
            "phase": phase,
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
        provisional = PreparedStageOneRequest.model_construct(
            preparation_id="pending", **request_values
        )
        return PreparedStageOneRequest(
            preparation_id=prepared_stage_one_request_id(provisional), **request_values
        )

    def _persist(
        self,
        *,
        prepared: PreparedStageOneRequest,
        payload: dict[str, Any] | None,
        telemetry: ModelCallTelemetry,
        failure_artifact: ProspectiveThinkingFailureArtifact | None,
    ) -> None:
        if prepared.dynamic_certificate is None:
            raise ValueError("v26.109 cannot persist an uncertified Provider call")
        values: dict[str, Any] = {
            "runner_contract_id": self._runner_contract.contract_id,
            "job_id": self._job.job_id,
            "logical_request_index": prepared.logical_request_index,
            "provider_call_index": len(self._telemetry),
            "request_kind": prepared.request_kind,
            "phase": prepared.phase,
            "prompt_sha256": sha256_text(prepared.prompt),
            "dynamic_certificate": prepared.dynamic_certificate,
            "request_binding_certificate": prepared.request_binding_certificate,
            "resource_certificate_id": prepared.resource_certificate.certificate_id,
            "response_payload": payload,
            "provider_telemetry": telemetry,
            "failure_artifact": failure_artifact,
        }
        provisional = RawStageOneProviderCall.model_construct(artifact_id="pending", **values)
        artifact = RawStageOneProviderCall(
            artifact_id=raw_stage_one_provider_call_id(provisional), **values
        )
        path = raw_provider_path(self._output_dir, self._job, len(self._telemetry))
        write_json_atomic(path, artifact.model_dump(mode="json"))
        self._telemetry.append(telemetry)
        self._descriptors.append(_descriptor(path, self._output_dir))

    def _charge(self, prepared: PreparedStageOneRequest, telemetry: ModelCallTelemetry) -> None:
        certificate = prepared.resource_certificate
        failures: list[str] = []
        if telemetry.request_hash != certificate.request_prompt_sha256:
            failures.append("request_hash_mismatch")
        if (
            telemetry.model_requested != STAGE_ONE_MODEL_ID
            or telemetry.model_selected != STAGE_ONE_MODEL_ID
            or telemetry.response_model != STAGE_ONE_MODEL_ID
        ):
            failures.append("exact_model_mismatch_or_missing")
        if telemetry.fallback_used or telemetry.discovery_attempted:
            failures.append("fallback_or_discovery_observed")
        counted = 0
        if telemetry.http_success:
            prompt = telemetry.prompt_tokens
            completion = telemetry.completion_tokens
            total = telemetry.total_tokens
            if prompt is None or completion is None or total is None:
                failures.append("successful_usage_missing")
            else:
                counted = total
                if prompt + completion != total:
                    failures.append("prompt_completion_sum_mismatch")
                if prompt > certificate.prompt_token_upper_bound:
                    failures.append("prompt_upper_bound_exceeded")
                if completion >= 16386:
                    failures.append("two_or_more_completion_tokens_over_exact_request")
                if total > certificate.request_token_upper_bound:
                    failures.append("request_upper_bound_exceeded")
                if self._cumulative_tokens + total > 260000:
                    failures.append("rollout_upper_bound_exceeded")
        self._cumulative_tokens += counted
        self._instrument_failures.update(failures)

    def invoke(
        self, prepared: PreparedStageOneRequest
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        if prepared.preparation_id in self._used_preparations:
            raise InstrumentContractError("v26.109 prepared request was reused")
        self._used_preparations.add(prepared.preparation_id)
        if not prepared.resource_certificate.provider_call_permitted:
            raise BudgetNoCallError(str(prepared.resource_certificate.denial_reason))
        if not prepared.provider_invocation_authorized or prepared.dynamic_certificate is None:
            raise InstrumentContractError("v26.109 invocation lacks all pre-call certificates")
        try:
            payload, telemetry = self._delegate.complete_json_certified(
                prepared.prompt, prepared.request_binding_certificate
            )
        except LLMClientError as exc:
            failure = (
                exc.failure_artifact
                if isinstance(exc.failure_artifact, ProspectiveThinkingFailureArtifact)
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


class _AttemptOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    attempt: StageOneAttempt
    payload: dict[str, Any] | None = None
    proposal: SemanticDecisionProposal | None = None
    answer: dict[str, Any] | None = None


def _make_attempt(
    *,
    prepared: PreparedStageOneRequest,
    provider_call_index: int | None,
    disposition: AttemptDisposition,
    response_payload_present: bool,
    classification: ProspectiveFailureClassification | None = None,
    completion_failure_type: str | None = None,
    error: str | None = None,
) -> StageOneAttempt:
    values: dict[str, Any] = {
        "logical_request_index": prepared.logical_request_index,
        "provider_call_index": provider_call_index,
        "request_kind": prepared.request_kind,
        "phase": prepared.phase,
        "prompt_sha256": sha256_text(prepared.prompt),
        "prompt_utf8_bytes": len(prepared.prompt.encode("utf-8")),
        "dynamic_certificate_id": (
            prepared.dynamic_certificate.certificate_id
            if prepared.dynamic_certificate is not None
            else None
        ),
        "request_binding_certificate_id": prepared.request_binding_certificate.certificate_id,
        "resource_certificate_id": prepared.resource_certificate.certificate_id,
        "provider_call_made": provider_call_index is not None,
        "response_payload_present": response_payload_present,
        "model_failure_classification": classification,
        "completion_failure_type": completion_failure_type,
        "disposition": disposition,
        "error": error,
    }
    provisional = StageOneAttempt.model_construct(attempt_id="pending", **values)
    return StageOneAttempt(attempt_id=stage_one_attempt_id(provisional), **values)


def _invoke_attempt(
    ledger: JournaledStageOneClient,
    *,
    logical_request_index: int,
    request_kind: StageOneRequestKind,
    phase: StageOneAttemptPhase,
    primary_prompt: str,
    prompt: str,
    state: PublicActionState | None,
    rescue_available_before: bool,
) -> _AttemptOutcome:
    prepared = ledger.prepare(
        logical_request_index=logical_request_index,
        request_kind=request_kind,
        phase=phase,
        primary_prompt=primary_prompt,
        prompt=prompt,
        public_state_id=state.state_id if state is not None else None,
        rescue_available_before=rescue_available_before,
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
    except LLMClientError as exc:
        index = before if ledger.provider_call_count > before else None
        failure_type = (
            exc.failure_artifact.failure_type
            if isinstance(exc.failure_artifact, ProspectiveThinkingFailureArtifact)
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
            if state is None:
                raise ValueError("semantic Proposal parsing lacks a public state")
            proposal = parse_semantic_proposal_payload(payload, expected_state=state)
            attempt = _make_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="usable",
                response_payload_present=True,
            )
            return _AttemptOutcome(attempt=attempt, payload=payload, proposal=proposal)
        answer = parse_final_answer_payload(payload)
        attempt = _make_attempt(
            prepared=prepared,
            provider_call_index=before,
            disposition="usable",
            response_payload_present=True,
        )
        return _AttemptOutcome(attempt=attempt, payload=payload, answer=answer)
    except ModelResultRejection as exc:
        return _AttemptOutcome(
            attempt=_make_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="model_result_failure",
                response_payload_present=True,
                classification=exc.classification,
                error=str(exc),
            ),
            payload=payload,
        )


def _rescue_allowed(attempt: StageOneAttempt) -> bool:
    if attempt.disposition == "completion_failure":
        return True
    classification = attempt.model_failure_classification
    return bool(
        attempt.disposition == "model_result_failure"
        and classification is not None
        and classification.family
        in {
            "response_serialization_failure",
            "decision_phase_control_failure",
            "prompt_echo_instruction_failure",
        }
    )


def _terminal_from_attempt(attempt: StageOneAttempt) -> TerminalDisposition:
    mapping: dict[AttemptDisposition, TerminalDisposition] = {
        "model_result_failure": "model_result",
        "completion_failure": "completion_unusable",
        "provider_transport_failure": "provider_transport_failure",
        "typed_budget_no_call": "typed_budget_no_call",
        "instrument_failure": "instrument_failure",
        "usable": "instrument_failure",
    }
    return mapping[attempt.disposition]


def _selected_evidence_ids(observations: Sequence[AgentToolObservation]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                evidence_id
                for observation in observations
                if observation.status == "succeeded"
                for evidence_id in observation.evidence_ids
            }
        )
    )


def _active_outcome(
    ledger: JournaledStageOneClient,
    *,
    attempts: list[StageOneAttempt],
    logical_request_index: int,
    request_kind: StageOneRequestKind,
    primary_prompt: str,
    state: PublicActionState | None,
    rescue_used: bool,
) -> tuple[_AttemptOutcome, bool]:
    primary = _invoke_attempt(
        ledger,
        logical_request_index=logical_request_index,
        request_kind=request_kind,
        phase="primary",
        primary_prompt=primary_prompt,
        prompt=primary_prompt,
        state=state,
        rescue_available_before=not rescue_used,
    )
    attempts.append(primary.attempt)
    if not rescue_used and _rescue_allowed(primary.attempt):
        rescue_used = True
        family = (
            primary.attempt.model_failure_classification.family
            if primary.attempt.model_failure_classification is not None
            else "channel_parse_failure"
        )
        subtype = (
            primary.attempt.model_failure_classification.subtype
            if primary.attempt.model_failure_classification is not None
            else str(primary.attempt.completion_failure_type or "completion_failure")
        )
        if request_kind == "semantic_proposal":
            rescue_prompt = render_semantic_proposal_rescue_prompt(
                primary_prompt,
                failure_family=family,
                failure_subtype=subtype,
            )
        else:
            rescue_prompt = render_semantically_sufficient_final_rescue_prompt(
                primary_prompt,
                failure_type=subtype,
            )
        rescue = _invoke_attempt(
            ledger,
            logical_request_index=logical_request_index,
            request_kind=request_kind,
            phase="rescue",
            primary_prompt=primary_prompt,
            prompt=rescue_prompt,
            state=state,
            rescue_available_before=False,
        )
        attempts.append(rescue.attempt)
        return rescue, rescue_used
    return primary, rescue_used


def _finish_raw(
    *,
    runner_contract: TwoStageRunnerContract,
    job: TwoStageJob,
    binding: RuntimeBinding,
    ledger: JournaledStageOneClient,
    attempts: Sequence[StageOneAttempt],
    commits: Sequence[StageTwoCommitRecord],
    observations: Sequence[AgentToolObservation],
    completed: TwoStageCompletedResult | None,
    terminal: TerminalDisposition,
    failure_type: str | None,
    error: str | None,
    output_dir: Path,
) -> TwoStageRawExecution:
    values: dict[str, Any] = {
        "runner_contract_id": runner_contract.contract_id,
        "job": job,
        "operational_record_id": binding.record.record_id,
        "environment_manifest_id": binding.environment.manifest_id,
        "path_audit_id": job.path_audit_id,
        "provider_call_artifacts": ledger.descriptors,
        "provider_telemetry": ledger.telemetry,
        "attempts": tuple(attempts),
        "commits": tuple(commits),
        "observations": tuple(observations),
        "completed_result": completed,
        "terminal_disposition": terminal,
        "terminal_failure_type": failure_type,
        "execution_error": error,
        "cumulative_provider_tokens": ledger.cumulative_tokens,
        "stage_one_provider_call_count": ledger.provider_call_count,
        "rescue_attempt_count": sum(item.phase == "rescue" for item in attempts),
    }
    provisional = TwoStageRawExecution.model_construct(artifact_id="pending", **values)
    raw = TwoStageRawExecution(artifact_id=two_stage_raw_execution_id(provisional), **values)
    write_json_atomic(raw_execution_path(output_dir, job), raw.model_dump(mode="json"))
    return raw


def execute_two_stage_job_raw(
    *,
    job: TwoStageJob,
    runner_contract: TwoStageRunnerContract,
    static: TwoStageStaticInputs,
    binding: RuntimeBinding,
    client: StageOneClient | None,
    output_dir: Path,
) -> TwoStageRawExecution:
    raw_path = raw_execution_path(output_dir, job)
    if raw_path.exists():
        raw = TwoStageRawExecution.model_validate(load_canonical_json(raw_path))
        if raw.runner_contract_id != runner_contract.contract_id or raw.job != job:
            raise ValueError("v26.109 Raw recovery crosses frozen identities")
        for descriptor in raw.provider_call_artifacts:
            path = output_dir / descriptor.relative_path
            if not path.is_file() or sha256_file(path) != descriptor.sha256:
                raise ValueError("v26.109 Raw recovery Provider bytes changed")
            RawStageOneProviderCall.model_validate(load_canonical_json(path))
        return raw
    provider_dir = raw_provider_path(output_dir, job, 0).parent
    if provider_dir.exists() and any(provider_dir.glob("call_*.json")):
        raise ValueError(
            "orphan v26.109 Provider Artifacts exist without a Raw Execution; retry forbidden"
        )
    if client is None:
        raise ValueError("pending v26.109 fixture Job has no Stage 1 client")
    if (
        job.contract_id != static.predecessor_contract.contract_id
        or job.task_package_id not in {item.task_package_id for item in static.tasks}
        or job.path_audit_id not in {item.path_audit_id for item in static.paths}
    ):
        raise ValueError("v26.109 Job differs from its static identity chain")
    ledger = JournaledStageOneClient(
        client,
        runner_contract=runner_contract,
        resource_contract=static.resource,
        job=job,
        output_dir=output_dir,
    )
    runtime = _runtime(binding.record, binding.environment)
    observations: list[AgentToolObservation] = []
    attempts: list[StageOneAttempt] = []
    commits: list[StageTwoCommitRecord] = []
    failed_signatures: set[str] = set()
    rescue_used = False
    condition = (
        None
        if binding.source_registered_path.role == "capability"
        else binding.source_registered_path.path_strategy_id
    )
    terminal: TerminalDisposition = "model_result"
    failure_type: str | None = None
    error: str | None = None
    completed: TwoStageCompletedResult | None = None
    logical_index = 0
    for _ in range(static.resource.maximum_primary_stage_one_requests - 1):
        state = build_public_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            tuple(observations),
        )
        prompt = render_action_constructible_decision_prompt(
            instruction=binding.record.task_package.task.public.instruction,
            state=state,
            public_path_condition=condition,
        )
        outcome, rescue_used = _active_outcome(
            ledger,
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="semantic_proposal",
            primary_prompt=prompt,
            state=state,
            rescue_used=rescue_used,
        )
        logical_index += 1
        if outcome.attempt.disposition != "usable" or outcome.proposal is None:
            terminal = _terminal_from_attempt(outcome.attempt)
            classification = outcome.attempt.model_failure_classification
            failure_type = (
                classification.subtype
                if classification is not None
                else outcome.attempt.completion_failure_type or outcome.attempt.disposition
            )
            error = outcome.attempt.error
            break
        proposal = outcome.proposal
        signature = semantic_proposal_signature(proposal)
        if signature in failed_signatures:
            terminal = "model_result"
            failure_type = "duplicate_failed_semantic_proposal"
            error = "model repeated a semantic proposal that already produced a typed failure"
            break
        try:
            commit = compile_semantic_decision(state, proposal, call_index=len(observations) + 1)
        except ValueError as exc:
            terminal = "model_result"
            failure_type = "semantic_compile_rejection"
            error = str(exc)
            break
        commit_values: dict[str, Any] = {
            "logical_request_index": logical_index - 1,
            "public_state_id": state.state_id,
            "proposal": proposal,
            "commit": commit,
            "stage_two_profile_id": static.stage_two.profile_id,
            "provider_calls_before_commit": ledger.provider_call_count,
        }
        provisional_commit = StageTwoCommitRecord.model_construct(
            record_id="pending", **commit_values
        )
        commits.append(
            StageTwoCommitRecord(
                record_id=stage_two_commit_record_id(provisional_commit), **commit_values
            )
        )
        if commit.action == "emit_final":
            break
        if commit.call is None:
            raise ValueError("v26.109 tool Commit unexpectedly lacks its public call")
        from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
            CompletionProjection,
        )

        observation = _execute_observation(
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
        if observation.status == "failed":
            failed_signatures.add(signature)
    else:
        terminal = "model_result"
        failure_type = "stage_one_primary_request_limit_exhausted"
        error = "model did not reach deterministic final Commit within the frozen request limit"

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
        outcome, rescue_used = _active_outcome(
            ledger,
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="final_answer",
            primary_prompt=final_prompt,
            state=None,
            rescue_used=rescue_used,
        )
        if outcome.attempt.disposition == "usable" and outcome.answer is not None:
            citations = _selected_evidence_ids(observations)
            if not citations:
                terminal = "model_result"
                failure_type = "final_answer_without_public_evidence"
                error = "final answer has no successfully selected public Evidence"
            else:
                values: dict[str, Any] = {
                    "job_id": job.job_id,
                    "answer": outcome.answer,
                    "cited_evidence_ids": citations,
                    "final_attempt_id": outcome.attempt.attempt_id,
                }
                provisional = TwoStageCompletedResult.model_construct(result_id="pending", **values)
                completed = TwoStageCompletedResult(
                    result_id=two_stage_completed_result_id(provisional), **values
                )
                terminal = "completed"
        else:
            terminal = _terminal_from_attempt(outcome.attempt)
            classification = outcome.attempt.model_failure_classification
            failure_type = (
                classification.subtype
                if classification is not None
                else outcome.attempt.completion_failure_type or outcome.attempt.disposition
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
        commits=commits,
        observations=observations,
        completed=completed,
        terminal=terminal,
        failure_type=failure_type,
        error=error,
        output_dir=output_dir,
    )


def make_runner_contract(static: TwoStageStaticInputs) -> TwoStageRunnerContract:
    values: dict[str, Any] = {
        "stage_one_profile_id": static.stage_one.profile_id,
        "stage_two_profile_id": static.stage_two.profile_id,
    }
    provisional = TwoStageRunnerContract.model_construct(contract_id="pending", **values)
    return TwoStageRunnerContract(contract_id=two_stage_runner_contract_id(provisional), **values)


def replay_v3(
    raw: TwoStageRawExecution,
    *,
    static: TwoStageStaticInputs,
    binding: RuntimeBinding,
) -> Any:
    from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay_v3 import (  # noqa: E501
        replay_authority_preserving_observations_v3,
    )

    return replay_authority_preserving_observations_v3(
        make_authority_preserving_replay_v3_contract(static.historical.replay_contract),
        static.historical.replay_contract,
        binding.record,
        binding.environment,
        raw.observations,
    )
