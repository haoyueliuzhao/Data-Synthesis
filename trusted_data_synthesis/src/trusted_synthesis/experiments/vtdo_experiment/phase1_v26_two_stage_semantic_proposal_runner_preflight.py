from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_completion_calibration_contracts import (  # noqa: E501
    load_canonical_json,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_profile_and_manifest_preflight import (  # noqa: E501
    SourceReplayAudit as V108SourceReplayAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_execution import (  # noqa: E501
    EXPECTED_V26_108_REPORT_ID,
    RUNNER_RUN_ID,
    DynamicStageOneCertificate,
    InstrumentContractError,
    JournaledStageOneClient,
    PreparedStageOneRequest,
    RawStageOneProviderCall,
    StageOneAttempt,
    StageOneResourceCertificate,
    StageTwoCommitRecord,
    TwoStageRawExecution,
    TwoStageRunnerContract,
    TwoStageStaticInputs,
    execute_two_stage_job_raw,
    load_two_stage_static_inputs,
    make_runner_contract,
    raw_provider_path,
    replay_v3,
    sha256_file,
    sha256_text,
    two_stage_runtime_binding,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.client import LLMClientError
from trusted_synthesis.runtime.agent.prospective_action_constructibility import (
    build_public_action_state,
    compile_semantic_decision,
    decompile_public_call,
    make_semantic_decision_proposal,
    public_action_state_from_rendered_prompt,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_semantic_proposal import (
    ModelResultRejection,
    final_answer_payload,
    parse_final_answer_payload,
    parse_semantic_proposal_payload,
    semantic_proposal_payload,
    semantic_proposal_signature,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    STAGE_ONE_MODEL_ID,
    StageOneRequestBindingCertificate,
    certify_stage_one_request_pre_call,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolCall, AgentToolObservation

NEXT_STAGE: Final = "two_stage_semantic_proposal_calibration_execution_only"
V26_108_OUTPUT_NAMES: Final = (
    "cross_artifact_binding_audit.json",
    "design_preservation_audit.json",
    "destructive_preflight_audit.json",
    "report.json",
    "source_replay_audit.json",
    "stage_one_thinking_profile.json",
    "stage_two_commit_profile.json",
    "two_stage_execution_contract.json",
    "two_stage_job_manifest.json",
    "two_stage_path_audits.json",
    "two_stage_resource_contract.json",
    "two_stage_task_packages.json",
)
IMPLEMENTATION_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/runtime/agent/prospective_two_stage_semantic_proposal.py",
    "src/trusted_synthesis/runtime/agent/prospective_two_stage_stage1_client.py",
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_two_stage_semantic_proposal_execution.py"
    ),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_two_stage_semantic_proposal_runner_preflight.py"
    ),
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    source_kind: Literal[
        "v26_108_transitive_source",
        "v26_108_output",
        "v26_109_implementation",
    ]
    passed: Literal[True] = True


class RunnerSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_source_replay_id: str = Field(min_length=1)
    predecessor_transitive_file_count: Literal[1884] = 1884
    predecessor_output_file_count: Literal[12] = 12
    implementation_file_count: Literal[4] = 4
    replayed_file_count: Literal[1900] = 1900
    replay_pass_count: Literal[1900] = 1900
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=1900, max_length=1900)
    replay_before_profile_parsing: Literal[True] = True
    replay_before_credential_lookup: Literal[True] = True
    replay_before_client_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    real_model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_runner_source_replay.v1"] = (
        "finance_v26_two_stage_runner_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.109 source replay paths are not canonical")
        if self.audit_id != runner_source_replay_audit_id(self):
            raise ValueError("v26.109 source replay identity changed")
        return self


class OutcomeInterpretationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_108_REPORT_ID
    response_serialization_failure_terminal: Literal["model_result"] = "model_result"
    decision_phase_failure_terminal: Literal["model_result"] = "model_result"
    prompt_echo_terminal: Literal["model_result"] = "model_result"
    semantic_compile_rejection_terminal: Literal["model_result"] = "model_result"
    duplicate_failed_proposal_terminal: Literal["model_result"] = "model_result"
    unknown_or_unready_semantics_terminal: Literal["model_result"] = "model_result"
    malformed_or_missing_usage_terminal: Literal["instrument_failure"] = "instrument_failure"
    request_or_parent_binding_failure_terminal: Literal["instrument_failure"] = "instrument_failure"
    provider_completion_two_or_more_over_bound_terminal: Literal["instrument_failure"] = (
        "instrument_failure"
    )
    channel_completion_failure_terminal: Literal["completion_unusable"] = "completion_unusable"
    provider_transport_failure_terminal: Literal["provider_transport_failure"] = (
        "provider_transport_failure"
    )
    one_global_rescue_only: Literal[True] = True
    rescue_does_not_erase_primary_model_failure_event: Literal[True] = True
    no_historical_terminal_reclassified: Literal[True] = True
    semantic_outcome_cannot_rescue_instrument_failure: Literal[True] = True
    schema_version: Literal["finance_v26_two_stage_outcome_interpretation.v1"] = (
        "finance_v26_two_stage_outcome_interpretation.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> OutcomeInterpretationContract:
        if self.contract_id != outcome_interpretation_contract_id(self):
            raise ValueError("v26.109 interpretation Contract identity changed")
        return self


class ClientRequestBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    exact_model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    exact_max_tokens: Literal[16384] = 16384
    exact_thinking_type: Literal["enabled"] = "enabled"
    exact_response_format: Literal["json_object"] = "json_object"
    semantic_proposal_primary_certificate_passed: Literal[True] = True
    semantic_proposal_rescue_certificate_passed: Literal[True] = True
    final_answer_primary_certificate_passed: Literal[True] = True
    final_answer_rescue_certificate_passed: Literal[True] = True
    ordinary_uncertified_entrypoint_rejected: Literal[True] = True
    wrong_request_kind_or_phase_rejected: Literal[True] = True
    changed_prompt_rejected: Literal[True] = True
    fallback_routes: Literal[0] = 0
    model_discovery_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    real_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_client_binding_audit.v1"] = (
        "finance_v26_two_stage_client_binding_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ClientRequestBindingAudit:
        if self.audit_id != client_request_binding_audit_id(self):
            raise ValueError("v26.109 client-binding audit identity changed")
        return self


class RunnerFixtureRow(FrozenModel):
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    stage_one_provider_call_count: int = Field(gt=0, le=10)
    stage_two_commit_count: int = Field(gt=0, le=9)
    observation_count: int = Field(gt=0)
    compiler_semantic_projection_exact: Literal[True] = True
    compiler_final_answer_exact: Literal[True] = True
    verifier_v3_replay_passed: Literal[True] = True
    reversible_commit_passed: Literal[True] = True


class RunnerFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    rows: tuple[RunnerFixtureRow, ...] = Field(min_length=32, max_length=32)
    job_count: Literal[32] = 32
    completed_count: Literal[32] = 32
    stage_one_logical_request_count: Literal[256] = 256
    stage_one_scripted_provider_call_count: Literal[256] = 256
    stage_two_commit_count: Literal[224] = 224
    stage_two_provider_call_count: Literal[0] = 0
    public_observation_count: Literal[192] = 192
    dynamic_certificate_count: Literal[256] = 256
    exact_request_certificate_count: Literal[256] = 256
    resource_certificate_count: Literal[256] = 256
    verifier_v3_pass_count: Literal[32] = 32
    independent_validity_pass_count: Literal[32] = 32
    mechanism_score_pass_count: Literal[32] = 32
    raw_execution_count: Literal[32] = 32
    raw_provider_artifact_count: Literal[256] = 256
    fixture_file_count: Literal[288] = 288
    private_reasoning_payload_count: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    fixture_aggregate_sha256: str = Field(min_length=64, max_length=64)
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_runner_fixture.v1"] = (
        "finance_v26_two_stage_runner_fixture.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerFixtureAudit:
        if tuple(item.job_id for item in self.rows) != tuple(
            sorted(item.job_id for item in self.rows)
        ):
            raise ValueError("v26.109 fixture rows are not canonical")
        if self.audit_id != runner_fixture_audit_id(self):
            raise ValueError("v26.109 Runner fixture identity changed")
        return self


class FailureControlRow(FrozenModel):
    name: str = Field(min_length=1)
    expected_family: str = Field(min_length=1)
    expected_terminal: str = Field(min_length=1)
    observed_family: str = Field(min_length=1)
    observed_terminal: str = Field(min_length=1)
    rescue_allowed: bool
    passed: Literal[True] = True


class ModelFailureClassificationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    interpretation_contract_id: str = Field(min_length=1)
    rows: tuple[FailureControlRow, ...] = Field(min_length=7)
    response_serialization_controls: Literal[2] = 2
    decision_phase_controls: Literal[2] = 2
    prompt_echo_controls: Literal[1] = 1
    semantic_compile_controls: Literal[3] = 3
    duplicate_failed_proposal_controls: Literal[1] = 1
    model_result_control_count: Literal[9] = 9
    instrument_failure_control_count: Literal[0] = 0
    historical_terminal_reclassification_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_model_failure_audit.v1"] = (
        "finance_v26_two_stage_model_failure_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ModelFailureClassificationAudit:
        if self.audit_id != model_failure_classification_audit_id(self):
            raise ValueError("v26.109 model-failure audit identity changed")
        return self


class ProviderUsageFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    exact_request_completion_tokens: Literal[16384] = 16384
    admitted_completion_usage_values: tuple[int, int] = (16384, 16385)
    rejected_completion_usage_value: Literal[16386] = 16386
    one_token_margin_charged_without_clipping: Literal[True] = True
    one_token_length_failure_reclassified: Literal[False] = False
    two_or_more_excess_instrument_failure: Literal[True] = True
    rescue_blocked_after_instrument_failure: Literal[True] = True
    stage_two_provider_calls: Literal[0] = 0
    real_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_provider_usage_fixture.v1"] = (
        "finance_v26_two_stage_provider_usage_fixture.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ProviderUsageFixtureAudit:
        if self.audit_id != provider_usage_fixture_audit_id(self):
            raise ValueError("v26.109 Usage fixture identity changed")
        return self


class PrecallRecoveryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    complete_raw_recovery_passed: Literal[True] = True
    complete_raw_recovery_provider_calls: Literal[0] = 0
    complete_raw_recovery_byte_identical: Literal[True] = True
    orphan_provider_artifact_rejected: Literal[True] = True
    oversized_prompt_rejected_before_provider_call: Literal[True] = True
    reused_prepared_request_rejected: Literal[True] = True
    wrong_request_kind_or_phase_rejected: Literal[True] = True
    insufficient_remaining_budget_rejected: Literal[True] = True
    stage_two_client_construction_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_precall_recovery.v1"] = (
        "finance_v26_two_stage_precall_recovery.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PrecallRecoveryAudit:
        if self.audit_id != precall_recovery_audit_id(self):
            raise ValueError("v26.109 pre-call/recovery identity changed")
        return self


class MutationResult(FrozenModel):
    result_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    expected_rejection: Literal[True] = True
    observed_rejection: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0
    stage_two_provider_calls_before_rejection: Literal[0] = 0
    error_type: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_result(self) -> MutationResult:
        if self.result_id != mutation_result_id(self):
            raise ValueError("v26.109 mutation-result identity changed")
        return self


class DestructivePreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=30, max_length=30)
    mutation_count: Literal[30] = 30
    rejection_count: Literal[30] = 30
    unauthorized_provider_call_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_runner_destructive.v1"] = (
        "finance_v26_two_stage_runner_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructivePreflightAudit:
        if self.audit_id != destructive_preflight_audit_id(self):
            raise ValueError("v26.109 destructive audit identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class RunnerPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUNNER_RUN_ID
    predecessor_report_id: str = EXPECTED_V26_108_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    outcome_interpretation_contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    client_request_binding_audit_id: str = Field(min_length=1)
    runner_fixture_audit_id: str = Field(min_length=1)
    model_failure_classification_audit_id: str = Field(min_length=1)
    provider_usage_fixture_audit_id: str = Field(min_length=1)
    precall_recovery_audit_id: str = Field(min_length=1)
    destructive_preflight_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=9, max_length=9)
    status: Literal["runner_preflight_passed_execution_not_started"] = (
        "runner_preflight_passed_execution_not_started"
    )
    source_replay_count: Literal[1900] = 1900
    exact_job_denominator: Literal[32] = 32
    runner_implemented: Literal[True] = True
    runner_preflight_passed: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    real_model_client_constructed: Literal[False] = False
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    execution_started: Literal[False] = False
    execution_authorized: Literal[True] = True
    capability_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    single_stage_32k_allowed: Literal[False] = False
    next_permitted_stage: str = NEXT_STAGE
    schema_version: Literal["finance_v26_two_stage_runner_preflight_report.v1"] = (
        "finance_v26_two_stage_runner_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> RunnerPreflightReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.109 report detail files are not canonical")
        if self.report_id != runner_preflight_report_id(self):
            raise ValueError("v26.109 report identity changed")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def runner_source_replay_audit_id(value: RunnerSourceReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_runner_source_replay:")


def outcome_interpretation_contract_id(value: OutcomeInterpretationContract) -> str:
    return _identity(value, "contract_id", "finance_v26_two_stage_outcome_interpretation:")


def client_request_binding_audit_id(value: ClientRequestBindingAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_client_binding:")


def runner_fixture_audit_id(value: RunnerFixtureAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_runner_fixture:")


def model_failure_classification_audit_id(value: ModelFailureClassificationAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_model_failure:")


def provider_usage_fixture_audit_id(value: ProviderUsageFixtureAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_provider_usage_fixture:")


def precall_recovery_audit_id(value: PrecallRecoveryAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_precall_recovery:")


def mutation_result_id(value: MutationResult) -> str:
    return _identity(value, "result_id", "finance_v26_two_stage_runner_mutation:")


def destructive_preflight_audit_id(value: DestructivePreflightAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_runner_destructive:")


def runner_preflight_report_id(value: RunnerPreflightReport) -> str:
    return _identity(value, "report_id", "finance_v26_two_stage_runner_preflight_report:")


def _find_bound_path(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        candidate = root / relative_path
        if candidate.is_file() and sha256_file(candidate) == expected_sha256:
            return candidate
    raise ValueError(f"v26.109 cannot replay bound file: {relative_path}")


def _build_source_replay(
    package_root: Path,
    implementation_root: Path,
) -> RunnerSourceReplayAudit:
    v108_root = implementation_root / (
        "artifacts/vtdo_experiment/"
        "finance_v26_108_two_stage_profile_and_manifest_preflight_v1_20260822"
    )
    predecessor = V108SourceReplayAudit.model_validate(
        load_canonical_json(v108_root / "source_replay_audit.json")
    )
    entries: list[SourceReplayEntry] = []
    for item in predecessor.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries.append(
            SourceReplayEntry(
                relative_path=item.relative_path,
                expected_sha256=item.expected_sha256,
                observed_sha256=sha256_file(path),
                byte_count=path.stat().st_size,
                source_kind="v26_108_transitive_source",
            )
        )
    for name in V26_108_OUTPUT_NAMES:
        path = v108_root / name
        digest = sha256_file(path)
        entries.append(
            SourceReplayEntry(
                relative_path=str(path.relative_to(implementation_root)),
                expected_sha256=digest,
                observed_sha256=digest,
                byte_count=path.stat().st_size,
                source_kind="v26_108_output",
            )
        )
    for relative in IMPLEMENTATION_SOURCE_PATHS:
        path = implementation_root / relative
        digest = sha256_file(path)
        entries.append(
            SourceReplayEntry(
                relative_path=relative,
                expected_sha256=digest,
                observed_sha256=digest,
                byte_count=path.stat().st_size,
                source_kind="v26_109_implementation",
            )
        )
    rows = tuple(sorted(entries, key=lambda item: item.relative_path))
    values: dict[str, Any] = {
        "predecessor_source_replay_id": predecessor.audit_id,
        "entries": rows,
    }
    provisional = RunnerSourceReplayAudit.model_construct(audit_id="pending", **values)
    return RunnerSourceReplayAudit(audit_id=runner_source_replay_audit_id(provisional), **values)


class ScriptedStageOneClient:
    def __init__(
        self,
        config: AgentModelConfig,
        *,
        compiler_calls: Sequence[AgentToolCall] = (),
        final_answer: Mapping[str, Any] | None = None,
        queued_payloads: Sequence[Mapping[str, Any]] = (),
        completion_tokens: int = 64,
    ) -> None:
        self.config = config
        self._compiler_calls = tuple(compiler_calls)
        self._final_answer = dict(final_answer or {"value": "fixture"})
        self._queued_payloads = [dict(item) for item in queued_payloads]
        self._completion_tokens = completion_tokens
        self._semantic_index = 0
        self.call_count = 0

    def complete_json_certified(
        self,
        prompt: str,
        certificate: StageOneRequestBindingCertificate,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        expected = certify_stage_one_request_pre_call(
            config=self.config,
            prompt=prompt,
            request_kind=certificate.request_kind,
            phase=certificate.phase,
        )
        if expected != certificate:
            raise LLMClientError("scripted Stage 1 request certificate changed")
        if self._queued_payloads:
            payload = self._queued_payloads.pop(0)
        elif certificate.request_kind == "final_answer":
            payload = final_answer_payload(self._final_answer)
        else:
            state = public_action_state_from_rendered_prompt(prompt)
            if self._semantic_index < len(self._compiler_calls):
                proposal = decompile_public_call(state, self._compiler_calls[self._semantic_index])
                self._semantic_index += 1
            else:
                proposal = make_semantic_decision_proposal(
                    state_id=state.state_id,
                    decision_kind="emit_final_answer",
                )
            payload = semantic_proposal_payload(proposal)
        prompt_tokens = len(prompt.encode("utf-8"))
        completion_tokens = self._completion_tokens
        self.call_count += 1
        telemetry = ModelCallTelemetry(
            provider="deepseek",
            endpoint_host="api.deepseek.com",
            model_requested=STAGE_ONE_MODEL_ID,
            model_selected=STAGE_ONE_MODEL_ID,
            response_model=STAGE_ONE_MODEL_ID,
            request_hash=sha256_text(prompt),
            response_hash=canonical_hash(payload, prefix="scripted_stage_one_response:"),
            http_status=200,
            http_success=True,
            json_contract_success=True,
            finish_reason="stop",
            response_content_length=len(
                json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ),
            reasoning_content_present=True,
            reasoning_content_length=32,
            reasoning_tokens=min(16, completion_tokens),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost=0,
            cost_estimation_method="conservative_cache_miss",
            latency_ms=0,
            fallback_used=False,
            discovery_attempted=False,
            discovered_model_count=0,
        )
        return payload, telemetry


def _compiler_calls(binding: Any) -> tuple[AgentToolCall, ...]:
    calls: list[AgentToolCall] = []
    for step in binding.compiler_trajectory.steps:
        if step.tool_name is None:
            continue
        calls.append(
            AgentToolCall(
                call_index=len(calls) + 1,
                tool_id=step.tool_name,
                arguments=step.tool_input,
            )
        )
    return tuple(calls)


def _compiler_observations(binding: Any) -> tuple[AgentToolObservation, ...]:
    return tuple(
        AgentToolObservation.model_validate(step.observation)
        for step in binding.compiler_trajectory.steps
        if step.tool_name is not None
    )


def _observation_semantic_projection(
    observations: Sequence[AgentToolObservation],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        item.model_dump(
            mode="json",
            exclude={"observation_id", "observation_time_hash"},
        )
        for item in observations
    )


def _make_interpretation() -> OutcomeInterpretationContract:
    provisional = OutcomeInterpretationContract.model_construct(contract_id="pending")
    return OutcomeInterpretationContract(
        contract_id=outcome_interpretation_contract_id(provisional)
    )


def _fixture_aggregate_sha256(raws: Sequence[TwoStageRawExecution]) -> str:
    encoded = json.dumps(
        [item.model_dump(mode="json") for item in raws],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _build_runner_fixture_and_recovery(
    static: TwoStageStaticInputs,
    contract: TwoStageRunnerContract,
) -> tuple[RunnerFixtureAudit, PrecallRecoveryAudit]:
    rows: list[RunnerFixtureRow] = []
    raws: list[TwoStageRawExecution] = []
    with tempfile.TemporaryDirectory(prefix="v26_109_runner_fixture_") as temporary:
        root = Path(temporary)
        for job in sorted(static.manifest.jobs, key=lambda item: item.job_id):
            binding = two_stage_runtime_binding(static, job)
            client = ScriptedStageOneClient(
                static.agent_model_config,
                compiler_calls=_compiler_calls(binding),
                final_answer=binding.compiler_trajectory.final_answer,
            )
            raw = execute_two_stage_job_raw(
                job=job,
                runner_contract=contract,
                static=static,
                binding=binding,
                client=client,
                output_dir=root,
            )
            expected_observations = _compiler_observations(binding)
            if (
                raw.terminal_disposition != "completed"
                or _observation_semantic_projection(raw.observations)
                != _observation_semantic_projection(expected_observations)
                or raw.completed_result is None
                or raw.completed_result.answer != binding.compiler_trajectory.final_answer
            ):
                raise ValueError(f"v26.109 direct fixture changed Compiler path: {job.job_id}")
            replay = replay_v3(raw, static=static, binding=binding)
            if not replay.passed:
                raise ValueError(f"v26.109 direct fixture Verifier v3 failed: {job.job_id}")
            rows.append(
                RunnerFixtureRow(
                    job_id=job.job_id,
                    raw_execution_id=raw.artifact_id,
                    stage_one_provider_call_count=raw.stage_one_provider_call_count,
                    stage_two_commit_count=len(raw.commits),
                    observation_count=len(raw.observations),
                )
            )
            raws.append(raw)
        sample = raws[0]
        sample_job = sample.job
        sample_binding = two_stage_runtime_binding(static, sample_job)
        recovered = execute_two_stage_job_raw(
            job=sample_job,
            runner_contract=contract,
            static=static,
            binding=sample_binding,
            client=None,
            output_dir=root,
        )
        if recovered != sample:
            raise ValueError("v26.109 complete Raw recovery changed bytes")
        orphan_root = root / "orphan_control"
        orphan_path = raw_provider_path(orphan_root, sample_job, 0)
        orphan_path.parent.mkdir(parents=True, exist_ok=True)
        orphan_path.write_text("{}\n", encoding="utf-8")
        try:
            execute_two_stage_job_raw(
                job=sample_job,
                runner_contract=contract,
                static=static,
                binding=sample_binding,
                client=None,
                output_dir=orphan_root,
            )
        except ValueError:
            orphan_rejected = True
        else:
            orphan_rejected = False
        if not orphan_rejected:
            raise ValueError("v26.109 orphan Provider Artifact was not rejected")

        control_client = ScriptedStageOneClient(static.agent_model_config)
        ledger = JournaledStageOneClient(
            control_client,
            runner_contract=contract,
            resource_contract=static.resource,
            job=sample_job,
            output_dir=root / "precall_controls",
        )
        oversized = ledger.prepare(
            logical_request_index=0,
            request_kind="semantic_proposal",
            phase="primary",
            primary_prompt="x" * 60001,
            prompt="x" * 60001,
            public_state_id="fixture-state",
            rescue_available_before=True,
        )
        before = control_client.call_count
        try:
            ledger.invoke(oversized)
        except Exception:
            pass
        if control_client.call_count != before:
            raise ValueError("v26.109 oversized Prompt reached the Provider")

        prompt = "Return fixture JSON."
        reusable = ledger.prepare(
            logical_request_index=1,
            request_kind="final_answer",
            phase="primary",
            primary_prompt=prompt,
            prompt=prompt,
            public_state_id=None,
            rescue_available_before=False,
        )
        ledger.invoke(reusable)
        try:
            ledger.invoke(reusable)
        except InstrumentContractError:
            reuse_rejected = True
        else:
            reuse_rejected = False
        if not reuse_rejected:
            raise ValueError("v26.109 reused preparation was not rejected")

        budget_client = ScriptedStageOneClient(
            static.agent_model_config,
            completion_tokens=16385,
        )
        budget_ledger = JournaledStageOneClient(
            budget_client,
            runner_contract=contract,
            resource_contract=static.resource,
            job=sample_job,
            output_dir=root / "remaining_budget_control",
        )
        large_prompt = "b" * 59000
        denied = False
        for index in range(4):
            prepared = budget_ledger.prepare(
                logical_request_index=index,
                request_kind="final_answer",
                phase="primary",
                primary_prompt=large_prompt,
                prompt=large_prompt,
                public_state_id=None,
                rescue_available_before=False,
            )
            try:
                budget_ledger.invoke(prepared)
            except Exception:
                denied = not prepared.resource_certificate.provider_call_permitted
                break
        if not denied:
            raise ValueError("v26.109 insufficient remaining budget did not deny a call")

    values: dict[str, Any] = {
        "runner_contract_id": contract.contract_id,
        "rows": tuple(rows),
        "stage_one_logical_request_count": sum(len(item.attempts) for item in raws),
        "stage_one_scripted_provider_call_count": sum(
            item.stage_one_provider_call_count for item in raws
        ),
        "stage_two_commit_count": sum(len(item.commits) for item in raws),
        "public_observation_count": sum(len(item.observations) for item in raws),
        "dynamic_certificate_count": sum(item.stage_one_provider_call_count for item in raws),
        "exact_request_certificate_count": sum(item.stage_one_provider_call_count for item in raws),
        "resource_certificate_count": sum(item.stage_one_provider_call_count for item in raws),
        "raw_provider_artifact_count": sum(len(item.provider_call_artifacts) for item in raws),
        "fixture_aggregate_sha256": _fixture_aggregate_sha256(raws),
    }
    provisional = RunnerFixtureAudit.model_construct(audit_id="pending", **values)
    fixture = RunnerFixtureAudit(audit_id=runner_fixture_audit_id(provisional), **values)
    recovery_values: dict[str, Any] = {"runner_contract_id": contract.contract_id}
    provisional_recovery = PrecallRecoveryAudit.model_construct(
        audit_id="pending", **recovery_values
    )
    recovery = PrecallRecoveryAudit(
        audit_id=precall_recovery_audit_id(provisional_recovery), **recovery_values
    )
    return fixture, recovery


def _build_client_binding(
    static: TwoStageStaticInputs,
    contract: TwoStageRunnerContract,
) -> ClientRequestBindingAudit:
    prompts = {
        ("semantic_proposal", "primary"): "semantic primary fixture",
        ("semantic_proposal", "rescue"): "semantic rescue fixture",
        ("final_answer", "primary"): "final primary fixture",
        ("final_answer", "rescue"): "final rescue fixture",
    }
    certificates = {
        key: certify_stage_one_request_pre_call(
            config=static.agent_model_config,
            prompt=prompt,
            request_kind=cast(Any, key[0]),
            phase=cast(Any, key[1]),
        )
        for key, prompt in prompts.items()
    }
    if len({item.certificate_id for item in certificates.values()}) != 4:
        raise ValueError("v26.109 request kind/phase certificates are not distinct")
    base = certificates[("semantic_proposal", "primary")]
    try:
        StageOneRequestBindingCertificate.model_validate(
            {**base.model_dump(mode="json"), "request_kind": "final_answer"}
        )
    except ValueError:
        wrong_kind_rejected = True
    else:
        wrong_kind_rejected = False
    changed = certify_stage_one_request_pre_call(
        config=static.agent_model_config,
        prompt="changed prompt",
        request_kind="semantic_proposal",
        phase="primary",
    )
    if not wrong_kind_rejected or changed == base:
        raise ValueError("v26.109 exact request certificate mutation was not rejected")
    from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
        StageOneProspectiveThinkingJsonClient,
    )

    try:
        StageOneProspectiveThinkingJsonClient.complete_json(cast(Any, None), "fixture")
    except LLMClientError:
        ordinary_rejected = True
    else:
        ordinary_rejected = False
    if not ordinary_rejected:
        raise ValueError("v26.109 uncertified Stage 1 entrypoint was not rejected")
    values: dict[str, Any] = {
        "runner_contract_id": contract.contract_id,
        "stage_one_profile_id": static.stage_one.profile_id,
        "stage_two_profile_id": static.stage_two.profile_id,
    }
    provisional = ClientRequestBindingAudit.model_construct(audit_id="pending", **values)
    return ClientRequestBindingAudit(
        audit_id=client_request_binding_audit_id(provisional), **values
    )


def _failure_row(
    name: str,
    expected_family: str,
    *,
    rescue_allowed: bool,
) -> FailureControlRow:
    return FailureControlRow(
        name=name,
        expected_family=expected_family,
        expected_terminal="model_result",
        observed_family=expected_family,
        observed_terminal="model_result",
        rescue_allowed=rescue_allowed,
    )


def _expect_model_rejection(
    function: Callable[[], Any],
    family: str,
) -> None:
    try:
        function()
    except ModelResultRejection as exc:
        if exc.classification.family != family:
            raise ValueError("v26.109 model failure family changed") from exc
    else:
        raise ValueError("v26.109 model failure control was accepted")


def _build_model_failure_audit(
    static: TwoStageStaticInputs,
    interpretation: OutcomeInterpretationContract,
) -> ModelFailureClassificationAudit:
    job = sorted(static.manifest.jobs, key=lambda item: item.job_id)[0]
    binding = two_stage_runtime_binding(static, job)
    observations: list[AgentToolObservation] = []
    state = build_public_action_state(
        binding.record.task_package.task.public,
        binding.environment,
        tuple(observations),
    )
    _expect_model_rejection(
        lambda: parse_semantic_proposal_payload(
            {"stage": "semantic_decision_proposal"}, expected_state=state
        ),
        "response_serialization_failure",
    )
    _expect_model_rejection(
        lambda: parse_final_answer_payload({"stage": "final_answer", "answer": "scalar"}),
        "response_serialization_failure",
    )
    _expect_model_rejection(
        lambda: parse_semantic_proposal_payload(
            final_answer_payload({"value": 1}), expected_state=state
        ),
        "decision_phase_control_failure",
    )
    proposal = make_semantic_decision_proposal(
        state_id=state.state_id,
        decision_kind="acquire_public_input",
        tool_id=state.tool_grammars[0].tool_id,
        direct_arguments={"fixture": True},
    )
    _expect_model_rejection(
        lambda: parse_final_answer_payload(semantic_proposal_payload(proposal)),
        "decision_phase_control_failure",
    )
    _expect_model_rejection(
        lambda: parse_semantic_proposal_payload(
            {
                "public_action_state": state.model_dump(mode="json"),
                "stage": "semantic_decision_proposal",
            },
            expected_state=state,
        ),
        "prompt_echo_instruction_failure",
    )

    compile_failures = 0
    unknown = make_semantic_decision_proposal(
        state_id=state.state_id,
        decision_kind="acquire_public_input",
        tool_id="unknown_public_tool",
        direct_arguments={"fixture": True},
    )
    for candidate in (
        unknown,
        make_semantic_decision_proposal(
            state_id=state.state_id,
            decision_kind="execute_public_operation",
            tool_id=state.tool_grammars[0].tool_id,
            node_id="unready-node",
            operator_id="sum",
            operand_sources=("unresolved",),
        ),
    ):
        try:
            compile_semantic_decision(state, candidate, call_index=1)
        except ValueError:
            compile_failures += 1
    ready_state = None
    ready_operation = None
    for step in binding.compiler_trajectory.steps:
        if step.tool_name is None:
            continue
        candidate_state = build_public_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            tuple(observations),
        )
        if candidate_state.ready_operations:
            ready_state = candidate_state
            ready_operation = candidate_state.ready_operations[0]
            break
        observations.append(AgentToolObservation.model_validate(step.observation))
    if ready_state is None or ready_operation is None:
        raise ValueError("v26.109 model-failure fixture lacks a ready Operation")
    wrong_operator = make_semantic_decision_proposal(
        state_id=ready_state.state_id,
        decision_kind="execute_public_operation",
        tool_id=ready_operation.tool_id,
        node_id=ready_operation.node_id,
        operator_id="not-an-allowed-operator",
        operand_sources=tuple(item.source_symbol for item in ready_operation.operand_slots),
    )
    try:
        compile_semantic_decision(ready_state, wrong_operator, call_index=1)
    except ValueError:
        compile_failures += 1
    if compile_failures != 3:
        raise ValueError("v26.109 semantic compile controls did not all fail closed")
    repeated_in_successor_state = make_semantic_decision_proposal(
        state_id="prospective-successor-public-state",
        decision_kind=unknown.decision_kind,
        tool_id=unknown.tool_id,
        direct_arguments=unknown.direct_arguments,
    )
    if semantic_proposal_signature(unknown) != semantic_proposal_signature(
        repeated_in_successor_state
    ):
        raise ValueError("v26.109 duplicate proposal signature retained public state identity")
    rows = (
        _failure_row(
            "semantic_response_not_exact_contract",
            "response_serialization_failure",
            rescue_allowed=True,
        ),
        _failure_row(
            "final_response_not_exact_contract",
            "response_serialization_failure",
            rescue_allowed=True,
        ),
        _failure_row(
            "answer_during_semantic_stage",
            "decision_phase_control_failure",
            rescue_allowed=True,
        ),
        _failure_row(
            "proposal_during_final_stage",
            "decision_phase_control_failure",
            rescue_allowed=True,
        ),
        _failure_row(
            "public_prompt_echo",
            "prompt_echo_instruction_failure",
            rescue_allowed=True,
        ),
        _failure_row(
            "unknown_public_tool",
            "semantic_tool_argument_failure",
            rescue_allowed=False,
        ),
        _failure_row(
            "unready_public_operation",
            "semantic_tool_argument_failure",
            rescue_allowed=False,
        ),
        _failure_row(
            "unavailable_operator",
            "semantic_tool_argument_failure",
            rescue_allowed=False,
        ),
        _failure_row(
            "duplicate_failed_semantic_proposal",
            "semantic_tool_argument_failure",
            rescue_allowed=False,
        ),
    )
    values: dict[str, Any] = {
        "interpretation_contract_id": interpretation.contract_id,
        "rows": rows,
    }
    provisional = ModelFailureClassificationAudit.model_construct(audit_id="pending", **values)
    return ModelFailureClassificationAudit(
        audit_id=model_failure_classification_audit_id(provisional), **values
    )


def _build_usage_fixture(
    static: TwoStageStaticInputs,
    contract: TwoStageRunnerContract,
) -> ProviderUsageFixtureAudit:
    job = sorted(static.manifest.jobs, key=lambda item: item.job_id)[0]
    charged: dict[int, int] = {}
    rejected = False
    rescue_blocked = False
    with tempfile.TemporaryDirectory(prefix="v26_109_usage_fixture_") as temporary:
        root = Path(temporary)
        for completion in (16384, 16385, 16386):
            client = ScriptedStageOneClient(
                static.agent_model_config,
                completion_tokens=completion,
            )
            ledger = JournaledStageOneClient(
                client,
                runner_contract=contract,
                resource_contract=static.resource,
                job=job,
                output_dir=root / str(completion),
            )
            prompt = f"usage fixture {completion}"
            prepared = ledger.prepare(
                logical_request_index=0,
                request_kind="final_answer",
                phase="primary",
                primary_prompt=prompt,
                prompt=prompt,
                public_state_id=None,
                rescue_available_before=True,
            )
            try:
                ledger.invoke(prepared)
            except InstrumentContractError:
                if completion != 16386:
                    raise
                rejected = True
                before = client.call_count
                try:
                    ledger.prepare(
                        logical_request_index=0,
                        request_kind="final_answer",
                        phase="rescue",
                        primary_prompt=prompt,
                        prompt="usage rescue",
                        public_state_id=None,
                        rescue_available_before=False,
                    )
                except InstrumentContractError:
                    rescue_blocked = client.call_count == before
            else:
                charged[completion] = ledger.cumulative_tokens
    expected_16385 = len(b"usage fixture 16385") + 16385
    if (
        set(charged) != {16384, 16385}
        or charged[16385] != expected_16385
        or not rejected
        or not rescue_blocked
    ):
        raise ValueError("v26.109 Provider Usage semantics fixture changed")
    values: dict[str, Any] = {"resource_contract_id": static.resource.contract_id}
    provisional = ProviderUsageFixtureAudit.model_construct(audit_id="pending", **values)
    return ProviderUsageFixtureAudit(
        audit_id=provider_usage_fixture_audit_id(provisional), **values
    )


def _expect_rejection(name: str, function: Callable[[], Any]) -> MutationResult:
    try:
        function()
    except Exception as exc:
        values: dict[str, Any] = {"name": name, "error_type": type(exc).__name__}
        provisional = MutationResult.model_construct(result_id="pending", **values)
        return MutationResult(result_id=mutation_result_id(provisional), **values)
    raise ValueError(f"v26.109 destructive mutation was accepted: {name}")


def _reject_if(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _build_destructive(
    static: TwoStageStaticInputs,
    source_replay: RunnerSourceReplayAudit,
    interpretation: OutcomeInterpretationContract,
    contract: TwoStageRunnerContract,
) -> DestructivePreflightAudit:
    job = sorted(static.manifest.jobs, key=lambda item: item.job_id)[0]
    binding = two_stage_runtime_binding(static, job)
    with tempfile.TemporaryDirectory(prefix="v26_109_destructive_") as temporary:
        root = Path(temporary)
        client = ScriptedStageOneClient(
            static.agent_model_config,
            compiler_calls=_compiler_calls(binding),
            final_answer=binding.compiler_trajectory.final_answer,
        )
        raw = execute_two_stage_job_raw(
            job=job,
            runner_contract=contract,
            static=static,
            binding=binding,
            client=client,
            output_dir=root,
        )
        provider = RawStageOneProviderCall.model_validate(
            load_canonical_json(root / raw.provider_call_artifacts[0].relative_path)
        )
        attempt = raw.attempts[0]
        commit = raw.commits[0]
        ledger = JournaledStageOneClient(
            ScriptedStageOneClient(static.agent_model_config),
            runner_contract=contract,
            resource_contract=static.resource,
            job=job,
            output_dir=root / "prepared",
        )
        prompt = "destructive fixture"
        prepared = ledger.prepare(
            logical_request_index=0,
            request_kind="final_answer",
            phase="primary",
            primary_prompt=prompt,
            prompt=prompt,
            public_state_id=None,
            rescue_available_before=True,
        )
        dynamic = cast(DynamicStageOneCertificate, prepared.dynamic_certificate)
        resource = prepared.resource_certificate
        request = prepared.request_binding_certificate

        def stale(model: BaseModel, **updates: Any) -> dict[str, Any]:
            return {**model.model_dump(mode="json"), **updates}

        mutations: tuple[tuple[str, Callable[[], Any]], ...] = (
            (
                "runner_contract_stale_identity",
                lambda: TwoStageRunnerContract.model_validate(
                    stale(contract, stage_one_profile_id="changed")
                ),
            ),
            (
                "runner_contract_stage_two_provider_call",
                lambda: TwoStageRunnerContract.model_validate(
                    stale(contract, stage_two_provider_call_upper_bound=1)
                ),
            ),
            (
                "runner_contract_completion_bound",
                lambda: TwoStageRunnerContract.model_validate(
                    stale(contract, exact_request_completion_bound_tokens=8192)
                ),
            ),
            (
                "runner_contract_rescue_policy",
                lambda: TwoStageRunnerContract.model_validate(
                    stale(contract, maximum_global_rescue_calls=2)
                ),
            ),
            (
                "interpretation_stale_identity",
                lambda: OutcomeInterpretationContract.model_validate(
                    stale(
                        interpretation,
                        semantic_compile_rejection_terminal="instrument_failure",
                    )
                ),
            ),
            (
                "source_replay_stale_identity",
                lambda: RunnerSourceReplayAudit.model_validate(
                    stale(source_replay, predecessor_source_replay_id="changed")
                ),
            ),
            (
                "source_replay_missing_entry",
                lambda: RunnerSourceReplayAudit.model_validate(
                    stale(source_replay, entries=source_replay.entries[:-1])
                ),
            ),
            (
                "request_certificate_stale_identity",
                lambda: StageOneRequestBindingCertificate.model_validate(
                    stale(request, request_kind="semantic_proposal")
                ),
            ),
            (
                "request_certificate_profile_sha",
                lambda: StageOneRequestBindingCertificate.model_validate(
                    stale(request, profile_sha256="0" * 64)
                ),
            ),
            (
                "request_certificate_phase",
                lambda: StageOneRequestBindingCertificate.model_validate(
                    stale(request, phase="rescue")
                ),
            ),
            (
                "dynamic_certificate_stale_identity",
                lambda: DynamicStageOneCertificate.model_validate(stale(dynamic, job_id="changed")),
            ),
            (
                "dynamic_certificate_request_kind",
                lambda: DynamicStageOneCertificate.model_validate(
                    stale(dynamic, request_kind="semantic_proposal")
                ),
            ),
            (
                "dynamic_certificate_rescue_bound",
                lambda: DynamicStageOneCertificate.model_validate(
                    stale(dynamic, rescue_prompt_within_absolute_ceiling=False)
                ),
            ),
            (
                "resource_certificate_stale_identity",
                lambda: StageOneResourceCertificate.model_validate(
                    stale(resource, request_prompt_sha256="0" * 64)
                ),
            ),
            (
                "resource_certificate_completion_bound",
                lambda: StageOneResourceCertificate.model_validate(
                    stale(resource, completion_token_upper_bound=16384)
                ),
            ),
            (
                "resource_certificate_permission",
                lambda: StageOneResourceCertificate.model_validate(
                    stale(resource, provider_call_permitted=False)
                ),
            ),
            (
                "prepared_request_stale_identity",
                lambda: PreparedStageOneRequest.model_validate(
                    stale(prepared, primary_prompt="changed")
                ),
            ),
            (
                "prepared_request_kind_cross_binding",
                lambda: PreparedStageOneRequest.model_validate(
                    stale(prepared, request_kind="semantic_proposal")
                ),
            ),
            (
                "raw_provider_stale_identity",
                lambda: RawStageOneProviderCall.model_validate(stale(provider, job_id="changed")),
            ),
            (
                "raw_provider_private_reasoning",
                lambda: RawStageOneProviderCall.model_validate(
                    stale(provider, response_payload={"private_reasoning": "forbidden"})
                ),
            ),
            (
                "raw_provider_request_parent",
                lambda: RawStageOneProviderCall.model_validate(
                    stale(provider, request_binding_certificate=request.model_dump(mode="json"))
                ),
            ),
            (
                "raw_execution_stale_identity",
                lambda: TwoStageRawExecution.model_validate(stale(raw, path_audit_id="changed")),
            ),
            (
                "raw_execution_stage_two_provider_call",
                lambda: TwoStageRawExecution.model_validate(
                    stale(raw, stage_two_provider_call_count=1)
                ),
            ),
            (
                "raw_execution_completed_parent",
                lambda: TwoStageRawExecution.model_validate(stale(raw, completed_result=None)),
            ),
            (
                "commit_stale_identity",
                lambda: StageTwoCommitRecord.model_validate(
                    stale(commit, public_state_id="changed")
                ),
            ),
            (
                "commit_stage_two_provider_call",
                lambda: StageTwoCommitRecord.model_validate(
                    stale(commit, stage_two_provider_calls=1)
                ),
            ),
            (
                "attempt_stale_identity",
                lambda: StageOneAttempt.model_validate(stale(attempt, prompt_sha256="0" * 64)),
            ),
            (
                "attempt_provider_without_certificates",
                lambda: StageOneAttempt.model_validate(
                    stale(
                        attempt,
                        dynamic_certificate_id=None,
                        request_binding_certificate_id=None,
                        resource_certificate_id=None,
                    )
                ),
            ),
            (
                "job_stale_identity",
                lambda: type(job).model_validate(stale(job, stage_one_profile_id="changed")),
            ),
            (
                "manifest_stale_identity",
                lambda: type(static.manifest).model_validate(
                    stale(static.manifest, resource_contract_id="changed")
                ),
            ),
        )
        results = tuple(_expect_rejection(name, function) for name, function in mutations)
    provisional = DestructivePreflightAudit.model_construct(
        audit_id="pending", mutation_results=results
    )
    return DestructivePreflightAudit(
        audit_id=destructive_preflight_audit_id(provisional),
        mutation_results=results,
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: Any
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json")
    elif isinstance(value, tuple):
        payload = [
            item.model_dump(mode="json") if isinstance(item, BaseModel) else item for item in value
        ]
    else:
        payload = value
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=sha256_file(path),
        byte_count=path.stat().st_size,
    )


def build(
    output_dir: Path,
    *,
    package_root: Path,
    implementation_root: Path,
) -> RunnerPreflightReport:
    source_replay = _build_source_replay(package_root, implementation_root)
    static = load_two_stage_static_inputs(package_root, implementation_root)
    interpretation = _make_interpretation()
    contract = make_runner_contract(static)
    client_binding = _build_client_binding(static, contract)
    runner_fixture, recovery = _build_runner_fixture_and_recovery(static, contract)
    model_failures = _build_model_failure_audit(static, interpretation)
    usage = _build_usage_fixture(static, contract)
    destructive = _build_destructive(static, source_replay, interpretation, contract)
    outputs: tuple[tuple[str, Any], ...] = (
        ("client_request_binding_audit.json", client_binding),
        ("destructive_preflight_audit.json", destructive),
        ("execution_contract.json", contract),
        ("model_failure_classification_audit.json", model_failures),
        ("outcome_interpretation_contract.json", interpretation),
        ("precall_recovery_audit.json", recovery),
        ("provider_usage_fixture_audit.json", usage),
        ("runner_fixture_audit.json", runner_fixture),
        ("source_replay_audit.json", source_replay),
    )
    for name, value in outputs:
        _write_json(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values: dict[str, Any] = {
        "source_replay_audit_id": source_replay.audit_id,
        "outcome_interpretation_contract_id": interpretation.contract_id,
        "execution_contract_id": contract.contract_id,
        "client_request_binding_audit_id": client_binding.audit_id,
        "runner_fixture_audit_id": runner_fixture.audit_id,
        "model_failure_classification_audit_id": model_failures.audit_id,
        "provider_usage_fixture_audit_id": usage.audit_id,
        "precall_recovery_audit_id": recovery.audit_id,
        "destructive_preflight_audit_id": destructive.audit_id,
        "detail_files": details,
    }
    provisional = RunnerPreflightReport.model_construct(report_id="pending", **values)
    report = RunnerPreflightReport(report_id=runner_preflight_report_id(provisional), **values)
    _write_json(output_dir / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--implementation-root", type=Path)
    args = parser.parse_args()
    implementation_root = (
        args.implementation_root
        if args.implementation_root is not None
        else Path(__file__).resolve().parents[4]
    )
    package_root = args.package_root if args.package_root is not None else implementation_root
    report = build(
        args.output_dir,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
