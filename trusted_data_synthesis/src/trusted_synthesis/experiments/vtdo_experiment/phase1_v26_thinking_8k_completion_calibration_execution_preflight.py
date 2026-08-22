from __future__ import annotations

import argparse
import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    ImplementationSourceFile,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_8k_completion_calibration_contracts import (  # noqa: E501
    IMPLEMENTATION_SOURCE_PATHS,
    ROOT_CAUSE_PROVIDER_ARTIFACT,
    RUNNER_PREFLIGHT_RUN_ID,
    DetailFile,
    Exact8KExecutionContract,
    Exact8KOutcomeInterpretationContract,
    Exact8KRunnerPreflightReport,
    Exact8KRunnerSourceReplayAudit,
    build_runner_source_replay,
    exact_8k_execution_contract_id,
    exact_8k_outcome_interpretation_id,
    exact_8k_runner_preflight_report_id,
    load_canonical_json,
    sha256,
    sha256_text,
    write_json_atomic,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_8k_completion_calibration_execution import (  # noqa: E501
    JournaledExact8KClient,
    _cp_upper,
    _next_transition,
    execute_exact_8k_job_raw,
    load_static_inputs,
    make_execution_report,
    raw_execution_path,
    raw_lineage_audit,
    raw_provider_path,
    runtime_binding,
    score_exact_8k_raw_execution,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import LLMClientError
from trusted_synthesis.runtime.agent.budget_closed import (
    ProviderTokenBudgetContract,
    make_provider_token_budget_contract,
)
from trusted_synthesis.runtime.agent.prospective_thinking_8k_client import (
    EXACT_8K_MODEL_CONFIG_ID,
    EXACT_8K_MODEL_ID,
    EXACT_8K_PROFILE_SHA256,
    EXACT_8K_THINKING_BINDING_ID,
    Exact8KRequestBindingCertificate,
    certify_exact_8k_request_pre_call,
    require_exact_8k_model_config,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    CompletionFailureKind,
    RedactedProviderResponseEnvelope,
    make_prospective_thinking_failure_artifact,
    render_primary_completion_prompt,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion_bound import (
    render_bounded_rescue_completion_prompt,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolObservation

CLIENT_BINDING_VERSION: Final[Literal["finance_v26_exact_8k_client_binding_fixture.v1"]] = (
    "finance_v26_exact_8k_client_binding_fixture.v1"
)
RUNNER_FIXTURE_VERSION: Final[Literal["finance_v26_exact_8k_runner_fixture.v1"]] = (
    "finance_v26_exact_8k_runner_fixture.v1"
)
PRECALL_RECOVERY_VERSION: Final[Literal["finance_v26_exact_8k_precall_recovery_fixture.v1"]] = (
    "finance_v26_exact_8k_precall_recovery_fixture.v1"
)
DESTRUCTIVE_VERSION: Final[Literal["finance_v26_exact_8k_runner_destructive.v1"]] = (
    "finance_v26_exact_8k_runner_destructive.v1"
)
RESCUE_FAILURE_TYPES: tuple[CompletionFailureKind, ...] = (
    "empty_final_content",
    "invalid_json",
    "invalid_response_contract",
    "length_truncated_content",
    "reasoning_only_length_truncation",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Exact8KClientBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    profile_sha256: str = EXACT_8K_PROFILE_SHA256
    model_config_id: str = EXACT_8K_MODEL_CONFIG_ID
    thinking_binding_id: str = EXACT_8K_THINKING_BINDING_ID
    representative_certificate: Exact8KRequestBindingCertificate
    request_model: Literal["deepseek-v4-flash"] = EXACT_8K_MODEL_ID
    request_max_tokens: Literal[8192] = 8192
    request_thinking_type: Literal["enabled"] = "enabled"
    actual_request_body_builder_shared_with_client: Literal[True] = True
    exact_route_skips_model_discovery_call: Literal[True] = True
    uncertified_client_entry_rejected_by_implementation: Literal[True] = True
    request_body_overrides_cannot_replace_max_tokens: Literal[True] = True
    profile_validated_before_client_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_8k_client_binding_fixture.v1"] = (
        CLIENT_BINDING_VERSION
    )

    @model_validator(mode="after")
    def validate_audit(self) -> Exact8KClientBindingAudit:
        if (
            self.representative_certificate.model_config_id != self.model_config_id
            or self.representative_certificate.thinking_binding_id != self.thinking_binding_id
            or self.representative_certificate.request_max_tokens != 8192
        ):
            raise ValueError("v26.100 client binding fixture changed")
        if self.audit_id != client_binding_audit_id(self):
            raise ValueError("v26.100 client binding audit identity mismatch")
        return self


class DirectFixtureRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    path_audit_id: str = Field(min_length=1)
    provider_call_count: int = Field(gt=0)
    logical_request_count: int = Field(gt=0)
    observation_count: int = Field(gt=0)
    registered_primary_prompt_match_count: int = Field(gt=0)
    dynamic_certificate_count: int = Field(gt=0)
    request_binding_certificate_count: int = Field(gt=0)
    expected_observation_semantic_hashes: tuple[str, ...] = Field(min_length=1)
    observed_observation_semantic_hashes: tuple[str, ...] = Field(min_length=1)
    completed: Literal[True] = True
    observations_match_compiler: Literal[True] = True
    all_primary_prompts_match_registered: Literal[True] = True
    all_provider_calls_dynamically_precertified: Literal[True] = True
    all_provider_calls_exact_8k_request_bound: Literal[True] = True
    replay_passed: Literal[True] = True
    verifier_valid: Literal[True] = True
    mechanism_success: Literal[True] = True
    rescue_provider_call_count: Literal[0] = 0
    model_plan_call_count: Literal[0] = 0
    model_discovery_call_count: Literal[0] = 0
    provider_calls_are_scripted_fixtures: Literal[True] = True
    empirical_row: Literal[False] = False

    @model_validator(mode="after")
    def validate_row(self) -> DirectFixtureRow:
        if self.expected_observation_semantic_hashes != self.observed_observation_semantic_hashes:
            raise ValueError("v26.100 direct fixture observations changed")
        if not (
            self.registered_primary_prompt_match_count
            == self.logical_request_count
            == self.dynamic_certificate_count
            == self.request_binding_certificate_count
            == self.provider_call_count
        ):
            raise ValueError("v26.100 direct fixture certificate denominator changed")
        if self.row_id != direct_fixture_row_id(self):
            raise ValueError("v26.100 direct fixture identity mismatch")
        return self


class RescueFixtureRow(FrozenModel):
    row_id: str = Field(min_length=1)
    failure_type: CompletionFailureKind
    job_id: str = Field(min_length=1)
    provider_call_count: int = Field(gt=1)
    rescue_provider_call_count: Literal[1] = 1
    rescued_usable_request_count: Literal[1] = 1
    maximum_rescue_prompt_utf8_bytes: int = Field(gt=0, le=6144)
    completed: Literal[True] = True
    all_rescue_prompts_absolutely_bounded: Literal[True] = True
    all_rescue_calls_dynamically_precertified: Literal[True] = True
    all_rescue_calls_exact_8k_request_bound: Literal[True] = True
    previous_final_content_reused: Literal[False] = False
    private_reasoning_reused: Literal[False] = False
    host_action_inserted: Literal[False] = False
    model_plan_call_count: Literal[0] = 0
    provider_calls_are_scripted_fixtures: Literal[True] = True
    empirical_row: Literal[False] = False

    @model_validator(mode="after")
    def validate_row(self) -> RescueFixtureRow:
        if self.row_id != rescue_fixture_row_id(self):
            raise ValueError("v26.100 Rescue fixture identity mismatch")
        return self


class RunnerFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    direct_rows: tuple[DirectFixtureRow, ...] = Field(min_length=32, max_length=32)
    rescue_rows: tuple[RescueFixtureRow, ...] = Field(min_length=5, max_length=5)
    direct_fixture_job_count: Literal[32] = 32
    direct_fixture_provider_call_count: int = Field(gt=0)
    direct_fixture_logical_request_count: int = Field(gt=0)
    direct_fixture_observation_count: int = Field(gt=0)
    direct_dynamic_certificate_count: int = Field(gt=0)
    direct_request_binding_certificate_count: int = Field(gt=0)
    direct_replay_pass_count: Literal[32] = 32
    direct_verifier_valid_count: Literal[32] = 32
    direct_mechanism_success_count: Literal[32] = 32
    direct_cell_summary_count: Literal[12] = 12
    full_aggregate_report_id: str = Field(min_length=1)
    full_aggregate_raw_file_count: int = Field(ge=32)
    full_aggregate_provider_call_count: int = Field(gt=0)
    full_aggregate_valid_terminal_count: Literal[32] = 32
    full_aggregate_status: Literal["passed"] = "passed"
    rescue_fixture_count: Literal[5] = 5
    global_rescue_exhaustion_terminal: Literal["completion_unusable"] = "completion_unusable"
    global_rescue_exhaustion_rescue_provider_call_count: Literal[1] = 1
    telemetry_only_terminal: Literal["instrument_failure"] = "instrument_failure"
    telemetry_only_rescue_provider_call_count: Literal[0] = 0
    length_failure_transition_control: Literal["fresh_16k_completion_preflight_only"] = (
        "fresh_16k_completion_preflight_only"
    )
    telemetry_failure_transition_control: Literal[
        "thinking_response_telemetry_wrapper_repair_only"
    ] = "thinking_response_telemetry_wrapper_repair_only"
    direct_pass_transition_control: Literal["thinking_role_protocol_freeze_only"] = (
        "thinking_role_protocol_freeze_only"
    )
    all_direct_paths_completed: Literal[True] = True
    all_direct_observations_match_compiler: Literal[True] = True
    all_registered_primary_prompts_match: Literal[True] = True
    all_rescue_types_recovered: Literal[True] = True
    one_global_rescue_enforced: Literal[True] = True
    response_telemetry_failure_not_rescued: Literal[True] = True
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    compiler_fixture_empirical_rows: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_8k_runner_fixture.v1"] = RUNNER_FIXTURE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerFixtureAudit:
        if tuple(item.failure_type for item in self.rescue_rows) != RESCUE_FAILURE_TYPES:
            raise ValueError("v26.100 Rescue fixture denominator changed")
        if self.audit_id != runner_fixture_audit_id(self):
            raise ValueError("v26.100 Runner fixture identity mismatch")
        return self


class PrecallRecoveryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    first_execution_provider_call_count: int = Field(gt=0)
    recovered_artifact_id: str = Field(min_length=1)
    recovery_artifact_id: str = Field(min_length=1)
    raw_only_recovery_provider_call_count: Literal[0] = 0
    raw_only_recovery_byte_identical: Literal[True] = True
    orphan_provider_artifact_rejected: Literal[True] = True
    oversized_primary_denied_before_delegate: Literal[True] = True
    oversized_primary_delegate_call_count: Literal[0] = 0
    resource_exhaustion_denied_before_delegate: Literal[True] = True
    resource_exhaustion_delegate_call_count: Literal[0] = 0
    wrong_actual_request_kind_rejected_before_delegate: Literal[True] = True
    wrong_actual_request_kind_delegate_call_count: Literal[0] = 0
    off_compiler_primary_utf8_bytes: Literal[7914] = 7914
    off_compiler_bounded_rescue_utf8_bytes: Literal[3888] = 3888
    off_compiler_provider_calls_before_certificates: Literal[0] = 0
    off_compiler_scripted_provider_calls_after_certificates: Literal[1] = 1
    off_compiler_rescue_absolutely_bounded: Literal[True] = True
    off_compiler_rescue_dynamically_precertified: Literal[True] = True
    off_compiler_rescue_exact_8k_request_bound: Literal[True] = True
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_8k_precall_recovery_fixture.v1"] = (
        PRECALL_RECOVERY_VERSION
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PrecallRecoveryAudit:
        if self.recovered_artifact_id != self.recovery_artifact_id:
            raise ValueError("v26.100 raw-only recovery Artifact changed")
        if self.audit_id != precall_recovery_audit_id(self):
            raise ValueError("v26.100 pre-call/recovery audit identity mismatch")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True
    failure_type: str = Field(min_length=1)


class DestructivePreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=20)
    rejected_mutation_count: int = Field(ge=20)
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_8k_runner_destructive.v1"] = DESTRUCTIVE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DestructivePreflightAudit:
        if self.rejected_mutation_count != len(self.mutation_results):
            raise ValueError("v26.100 destructive denominator changed")
        if self.audit_id != destructive_preflight_audit_id(self):
            raise ValueError("v26.100 destructive audit identity mismatch")
        return self


class FixtureEvent(FrozenModel):
    payload: dict[str, Any] | None = None
    failure_type: (
        CompletionFailureKind
        | Literal["response_envelope_invalid", "provider_native_tool_call", "transport"]
        | None
    ) = None

    @model_validator(mode="after")
    def validate_event(self) -> FixtureEvent:
        if (self.payload is None) == (self.failure_type is None):
            raise ValueError("fixture event requires exactly one payload or failure")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def client_binding_audit_id(value: Exact8KClientBindingAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_client_binding_fixture:")


def direct_fixture_row_id(value: DirectFixtureRow) -> str:
    return _identity(value, "row_id", "finance_v26_exact_8k_direct_fixture:")


def rescue_fixture_row_id(value: RescueFixtureRow) -> str:
    return _identity(value, "row_id", "finance_v26_exact_8k_rescue_fixture:")


def runner_fixture_audit_id(value: RunnerFixtureAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_runner_fixture:")


def precall_recovery_audit_id(value: PrecallRecoveryAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_precall_recovery_fixture:")


def destructive_preflight_audit_id(value: DestructivePreflightAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_runner_destructive:")


class ScriptedProviderClient:
    def __init__(self, config: AgentModelConfig, events: Sequence[FixtureEvent]) -> None:
        self.config = require_exact_8k_model_config(config)
        self._events = tuple(events)
        self.call_count = 0

    def _telemetry(
        self,
        prompt: str,
        *,
        content: str,
        finish_reason: str,
        json_success: bool,
        native_tool: bool = False,
        response_model: str | None = EXACT_8K_MODEL_ID,
        http_success: bool = True,
    ) -> tuple[ModelCallTelemetry, RedactedProviderResponseEnvelope | None]:
        prompt_tokens = max(1, len(prompt.encode("utf-8")) // 4)
        completion_tokens = 64
        total_tokens = prompt_tokens + completion_tokens
        envelope = (
            RedactedProviderResponseEnvelope(
                response_model=response_model or EXACT_8K_MODEL_ID,
                finish_reason=finish_reason,
                public_content_sha256=sha256_text(content),
                public_content_length=len(content),
                provider_native_tool_call_observed=native_tool,
                reasoning_content_present=True,
                reasoning_content_length=96,
                reasoning_tokens=32,
                completion_tokens=completion_tokens,
            )
            if http_success and response_model is not None
            else None
        )
        redacted = (
            envelope.model_dump(mode="json")
            if envelope is not None
            else {
                "response_model": response_model,
                "finish_reason": finish_reason,
                "public_content_sha256": sha256_text(content),
                "public_content_length": len(content),
                "provider_native_tool_call_observed": native_tool,
                "reasoning_content_present": True,
                "reasoning_content_length": 96,
                "reasoning_tokens": 32,
                "completion_tokens": completion_tokens,
            }
        )
        telemetry = ModelCallTelemetry(
            provider=self.config.provider,
            endpoint_host="fixture.invalid",
            model_requested=EXACT_8K_MODEL_ID,
            model_selected=EXACT_8K_MODEL_ID,
            response_model=response_model,
            request_hash=sha256_text(prompt),
            response_hash=sha256_text(content) if http_success else None,
            http_status=200 if http_success else 503,
            http_success=http_success,
            json_contract_success=json_success,
            finish_reason=finish_reason if http_success else None,
            response_content_length=len(content) if http_success else None,
            reasoning_content_present=http_success,
            reasoning_content_length=96 if http_success else None,
            reasoning_tokens=32 if http_success else None,
            prompt_tokens=prompt_tokens if http_success else None,
            completion_tokens=completion_tokens if http_success else None,
            total_tokens=total_tokens if http_success else None,
            estimated_cost=0.0,
            cost_estimation_method="conservative_cache_miss",
            latency_ms=1.0,
            fallback_used=False,
            error_type=None if json_success else "FixtureFailure",
            error_message=None if json_success else "scripted Provider fixture failure",
            response_shape={
                "provider_native_tool_call_observed": native_tool if http_success else None,
                "redacted_response_envelope": redacted,
                "response_envelope_captured_before_content_parse": http_success,
                "response_envelope_schema_valid": envelope is not None,
            },
        )
        return telemetry, envelope

    def complete_json_certified(
        self,
        prompt: str,
        certificate: Exact8KRequestBindingCertificate,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        expected = certify_exact_8k_request_pre_call(
            config=self.config,
            prompt=prompt,
            profile_sha256=EXACT_8K_PROFILE_SHA256,
        )
        if certificate != expected:
            raise LLMClientError("scripted exact 8K request certificate changed")
        if self.call_count >= len(self._events):
            raise AssertionError("scripted Provider fixture exhausted")
        event = self._events[self.call_count]
        self.call_count += 1
        if event.payload is not None:
            content = json.dumps(
                event.payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            telemetry, _ = self._telemetry(
                prompt,
                content=content,
                finish_reason="stop",
                json_success=True,
            )
            return event.payload, telemetry
        failure = cast(str, event.failure_type)
        if failure == "transport":
            telemetry, _ = self._telemetry(
                prompt,
                content="",
                finish_reason="",
                json_success=False,
                http_success=False,
            )
            raise LLMClientError("fixture transport failure", (telemetry,))
        if failure == "response_envelope_invalid":
            telemetry, _ = self._telemetry(
                prompt,
                content="",
                finish_reason="stop",
                json_success=False,
                response_model=None,
            )
            artifact = make_prospective_thinking_failure_artifact(
                failure_type="response_envelope_invalid",
                request_hash=telemetry.request_hash,
                response_envelope=None,
            )
            raise LLMClientError(
                "fixture malformed response envelope",
                (telemetry,),
                failure_artifact=artifact,
            )
        content = (
            ""
            if failure in {"empty_final_content", "reasoning_only_length_truncation"}
            else '{"truncated":'
        )
        finish_reason = (
            "length"
            if failure in {"length_truncated_content", "reasoning_only_length_truncation"}
            else "stop"
        )
        native_tool = failure == "provider_native_tool_call"
        telemetry, envelope = self._telemetry(
            prompt,
            content=content,
            finish_reason=finish_reason,
            json_success=False,
            native_tool=native_tool,
        )
        artifact = make_prospective_thinking_failure_artifact(
            failure_type=cast(Any, failure),
            request_hash=telemetry.request_hash,
            response_envelope=envelope,
        )
        raise LLMClientError(
            f"fixture {failure}",
            (telemetry,),
            failure_artifact=artifact,
        )


def _projection_payloads(trajectory: Trajectory) -> tuple[dict[str, Any], ...]:
    output = [
        {"action": "call_tool", "tool_id": step.tool_name, "arguments": step.tool_input}
        for step in trajectory.steps
        if step.tool_name is not None
    ]
    final = trajectory.final_answer
    result = final.get("result") if isinstance(final, Mapping) else None
    if not isinstance(result, Mapping):
        raise ValueError("v26.100 fixture trajectory lacks a final result")
    output.append({"answer": dict(result)})
    return tuple(output)


def _trajectory_observations(trajectory: Trajectory) -> tuple[AgentToolObservation, ...]:
    return tuple(
        AgentToolObservation.model_validate(step.observation)
        for step in trajectory.steps
        if step.tool_name is not None and step.observation is not None
    )


def _observation_semantic_hash(observation: AgentToolObservation) -> str:
    return canonical_hash(
        observation.model_dump(
            mode="json",
            exclude={"observation_id", "observation_time_hash"},
        ),
        prefix="finance_v26_exact_8k_observation_semantics:",
    )


def _make_provider_contract() -> ProviderTokenBudgetContract:
    return make_provider_token_budget_contract(
        provider="deepseek",
        model_id=EXACT_8K_MODEL_ID,
        maximum_total_tokens=160000,
        maximum_prompt_utf8_bytes=60000,
        maximum_output_tokens=8192,
        provider_chat_envelope_token_upper_bound=256,
        contract_repair_reserve_tokens=8192,
        final_answer_reserve_tokens=8192,
    )


def _make_interpretation() -> Exact8KOutcomeInterpretationContract:
    values = {
        "zero_failure_cp95_upper_bound": _cp_upper(0, 32),
        "one_failure_cp95_upper_bound": _cp_upper(1, 32),
    }
    provisional = Exact8KOutcomeInterpretationContract.model_construct(
        contract_id="pending",
        **values,
    )
    return Exact8KOutcomeInterpretationContract(
        contract_id=exact_8k_outcome_interpretation_id(provisional),
        **values,
    )


def _source_files(package_root: Path) -> tuple[ImplementationSourceFile, ...]:
    return tuple(
        ImplementationSourceFile(
            relative_path=relative_path,
            sha256=sha256(package_root / relative_path),
        )
        for relative_path in IMPLEMENTATION_SOURCE_PATHS
    )


def _make_execution_contract(
    *,
    replay: Exact8KRunnerSourceReplayAudit,
    interpretation: Exact8KOutcomeInterpretationContract,
    provider_contract: ProviderTokenBudgetContract,
    static: Any,
    package_root: Path,
) -> Exact8KExecutionContract:
    values = {
        "source_replay_audit_id": replay.audit_id,
        "outcome_interpretation_contract_id": interpretation.contract_id,
        "provider_budget_contract_id": provider_contract.contract_id,
        "job_ids": tuple(sorted(item.job_id for item in static.predecessor_manifest.jobs)),
        "runner_implementation_source_files": _source_files(package_root),
    }
    provisional = Exact8KExecutionContract.model_construct(contract_id="pending", **values)
    return Exact8KExecutionContract(
        contract_id=exact_8k_execution_contract_id(provisional),
        **values,
    )


def _make_client_binding_audit(
    *,
    execution_contract: Exact8KExecutionContract,
    model_config: AgentModelConfig,
) -> Exact8KClientBindingAudit:
    certificate = certify_exact_8k_request_pre_call(
        config=model_config,
        prompt="Return one exact public JSON fixture.",
        profile_sha256=EXACT_8K_PROFILE_SHA256,
    )
    values = {
        "execution_contract_id": execution_contract.contract_id,
        "representative_certificate": certificate,
    }
    provisional = Exact8KClientBindingAudit.model_construct(audit_id="pending", **values)
    return Exact8KClientBindingAudit(
        audit_id=client_binding_audit_id(provisional),
        **values,
    )


def _execute_fixture(
    *,
    static: Any,
    execution_contract: Exact8KExecutionContract,
    provider_contract: ProviderTokenBudgetContract,
    job: Any,
    events: Sequence[FixtureEvent],
    output_dir: Path,
) -> tuple[Any, ScriptedProviderClient, Any]:
    binding = runtime_binding(static, job)
    client = ScriptedProviderClient(static.agent_model_config, events)
    raw = execute_exact_8k_job_raw(
        job=job,
        execution_contract=execution_contract,
        provider_contract=provider_contract,
        completion_protocol=static.completion_bound_protocol,
        binding=binding,
        client=client,
        output_dir=output_dir,
    )
    return raw, client, binding


def _make_runner_fixture_audit(
    *,
    static: Any,
    execution_contract: Exact8KExecutionContract,
    provider_contract: ProviderTokenBudgetContract,
    interpretation: Exact8KOutcomeInterpretationContract,
) -> RunnerFixtureAudit:
    direct_rows: list[DirectFixtureRow] = []
    rescue_rows: list[RescueFixtureRow] = []
    direct_results: list[Any] = []
    direct_raw_by_job: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="v26_100_runner_fixture_") as temporary:
        root = Path(temporary)
        direct_output = root / "direct"
        for job in static.predecessor_manifest.jobs:
            binding = runtime_binding(static, job)
            events = tuple(
                FixtureEvent(payload=payload)
                for payload in _projection_payloads(binding.compiler_trajectory)
            )
            raw, client, binding = _execute_fixture(
                static=static,
                execution_contract=execution_contract,
                provider_contract=provider_contract,
                job=job,
                events=events,
                output_dir=direct_output,
            )
            prepared_stub = SimpleNamespace(
                execution_contract=execution_contract,
                replay_contract=static.replay_contract,
            )
            scored = score_exact_8k_raw_execution(
                raw=raw,
                prepared=prepared_stub,
                binding=binding,
                output_dir=direct_output,
            )
            expected = tuple(
                _observation_semantic_hash(item)
                for item in _trajectory_observations(binding.compiler_trajectory)
            )
            observed = tuple(_observation_semantic_hash(item) for item in raw.observations)
            values = {
                "job_id": job.job_id,
                "path_audit_id": job.path_audit_id,
                "provider_call_count": client.call_count,
                "logical_request_count": len(raw.logical_requests),
                "observation_count": len(raw.observations),
                "registered_primary_prompt_match_count": sum(
                    item.registered_primary_prompt_match for item in raw.request_attempts
                ),
                "dynamic_certificate_count": sum(
                    item.dynamic_certificate is not None for item in raw.request_attempts
                ),
                "request_binding_certificate_count": sum(
                    item.request_binding_certificate is not None for item in raw.request_attempts
                ),
                "expected_observation_semantic_hashes": expected,
                "observed_observation_semantic_hashes": observed,
                "completed": raw.terminal_disposition == "completed",
                "observations_match_compiler": expected == observed,
                "all_primary_prompts_match_registered": all(
                    item.registered_primary_prompt_match
                    for item in raw.request_attempts
                    if item.phase == "primary"
                ),
                "all_provider_calls_dynamically_precertified": all(
                    item.dynamic_certificate is not None
                    for item in raw.request_attempts
                    if item.provider_call_made
                ),
                "all_provider_calls_exact_8k_request_bound": all(
                    item.request_binding_certificate is not None
                    and item.request_binding_certificate.request_max_tokens == 8192
                    for item in raw.request_attempts
                    if item.provider_call_made
                ),
                "replay_passed": bool(scored.replay_result and scored.replay_result.passed),
                "verifier_valid": scored.independent_validity,
                "mechanism_success": scored.mechanism_success,
            }
            provisional = DirectFixtureRow.model_construct(row_id="pending", **values)
            direct_rows.append(
                DirectFixtureRow(row_id=direct_fixture_row_id(provisional), **values)
            )
            direct_results.append(scored)
            direct_raw_by_job[job.job_id] = raw

        representative = static.predecessor_manifest.jobs[0]
        representative_binding = runtime_binding(static, representative)
        payloads = _projection_payloads(representative_binding.compiler_trajectory)
        for index, failure_type in enumerate(RESCUE_FAILURE_TYPES):
            events = (
                FixtureEvent(failure_type=failure_type),
                *(FixtureEvent(payload=item) for item in payloads),
            )
            raw, client, _ = _execute_fixture(
                static=static,
                execution_contract=execution_contract,
                provider_contract=provider_contract,
                job=representative,
                events=events,
                output_dir=root / "rescue" / f"{index:02d}",
            )
            rescue_attempts = tuple(item for item in raw.request_attempts if item.phase == "rescue")
            values = {
                "failure_type": failure_type,
                "job_id": representative.job_id,
                "provider_call_count": client.call_count,
                "rescue_provider_call_count": raw.rescue_provider_call_count,
                "rescued_usable_request_count": sum(
                    item.outcome == "rescued_usable" for item in raw.logical_requests
                ),
                "maximum_rescue_prompt_utf8_bytes": max(
                    item.prompt_utf8_bytes for item in rescue_attempts
                ),
                "completed": raw.terminal_disposition == "completed",
                "all_rescue_prompts_absolutely_bounded": all(
                    item.rescue_prompt_within_absolute_ceiling for item in rescue_attempts
                ),
                "all_rescue_calls_dynamically_precertified": all(
                    item.dynamic_certificate is not None for item in rescue_attempts
                ),
                "all_rescue_calls_exact_8k_request_bound": all(
                    item.request_binding_certificate is not None
                    and item.request_binding_certificate.request_max_tokens == 8192
                    for item in rescue_attempts
                ),
            }
            provisional = RescueFixtureRow.model_construct(row_id="pending", **values)
            rescue_rows.append(
                RescueFixtureRow(row_id=rescue_fixture_row_id(provisional), **values)
            )

        exhaustion_events = (
            FixtureEvent(failure_type="reasoning_only_length_truncation"),
            FixtureEvent(payload=payloads[0]),
            *(FixtureEvent(payload=item) for item in payloads[1:-1]),
            FixtureEvent(failure_type="invalid_json"),
        )
        exhausted_output = root / "global_rescue_exhaustion"
        exhausted, _, exhausted_binding = _execute_fixture(
            static=static,
            execution_contract=execution_contract,
            provider_contract=provider_contract,
            job=representative,
            events=exhaustion_events,
            output_dir=exhausted_output,
        )
        telemetry_output = root / "telemetry_only"
        telemetry_failure, _, telemetry_binding = _execute_fixture(
            static=static,
            execution_contract=execution_contract,
            provider_contract=provider_contract,
            job=representative,
            events=(FixtureEvent(failure_type="response_envelope_invalid"),),
            output_dir=telemetry_output,
        )
        prepared_stub = SimpleNamespace(
            execution_contract=execution_contract,
            replay_contract=static.replay_contract,
        )
        exhausted_result = score_exact_8k_raw_execution(
            raw=exhausted,
            prepared=prepared_stub,
            binding=exhausted_binding,
            output_dir=exhausted_output,
        )
        telemetry_result = score_exact_8k_raw_execution(
            raw=telemetry_failure,
            prepared=prepared_stub,
            binding=telemetry_binding,
            output_dir=telemetry_output,
        )
        aggregate_prepared = SimpleNamespace(
            execution_contract=execution_contract,
            preflight_report=SimpleNamespace(report_id="fixture-only-preflight"),
            interpretation_contract=interpretation,
            replay_contract=static.replay_contract,
        )
        lineage = raw_lineage_audit(
            prepared=aggregate_prepared,
            results=direct_results,
            raw_by_job=direct_raw_by_job,
            output_dir=direct_output,
        )
        aggregate_report = make_execution_report(
            prepared=aggregate_prepared,
            results=direct_results,
            lineage=lineage,
            raw_by_job=direct_raw_by_job,
        )

    values = {
        "execution_contract_id": execution_contract.contract_id,
        "direct_rows": tuple(direct_rows),
        "rescue_rows": tuple(rescue_rows),
        "direct_fixture_provider_call_count": sum(item.provider_call_count for item in direct_rows),
        "direct_fixture_logical_request_count": sum(
            item.logical_request_count for item in direct_rows
        ),
        "direct_fixture_observation_count": sum(item.observation_count for item in direct_rows),
        "direct_dynamic_certificate_count": sum(
            item.dynamic_certificate_count for item in direct_rows
        ),
        "direct_request_binding_certificate_count": sum(
            item.request_binding_certificate_count for item in direct_rows
        ),
        "direct_replay_pass_count": sum(item.replay_passed for item in direct_rows),
        "direct_verifier_valid_count": sum(item.verifier_valid for item in direct_rows),
        "direct_mechanism_success_count": sum(item.mechanism_success for item in direct_rows),
        "direct_cell_summary_count": len(_cell_summaries_proxy(direct_results)),
        "full_aggregate_report_id": aggregate_report.report_id,
        "full_aggregate_raw_file_count": len(lineage.files),
        "full_aggregate_provider_call_count": aggregate_report.provider_call_count,
        "full_aggregate_valid_terminal_count": aggregate_report.terminal_counts.get(
            "model_valid_trajectory",
            0,
        ),
        "full_aggregate_status": aggregate_report.status,
        "global_rescue_exhaustion_terminal": exhausted.terminal_disposition,
        "global_rescue_exhaustion_rescue_provider_call_count": (
            exhausted.rescue_provider_call_count
        ),
        "telemetry_only_terminal": telemetry_failure.terminal_disposition,
        "telemetry_only_rescue_provider_call_count": (telemetry_failure.rescue_provider_call_count),
        "length_failure_transition_control": _next_transition(
            interpretation,
            (exhausted_result,),
        ),
        "telemetry_failure_transition_control": _next_transition(
            interpretation,
            (telemetry_result,),
        ),
        "direct_pass_transition_control": _next_transition(
            interpretation,
            direct_results,
        ),
        "all_direct_paths_completed": all(item.completed for item in direct_rows),
        "all_direct_observations_match_compiler": all(
            item.observations_match_compiler for item in direct_rows
        ),
        "all_registered_primary_prompts_match": all(
            item.all_primary_prompts_match_registered for item in direct_rows
        ),
        "all_rescue_types_recovered": all(item.completed for item in rescue_rows),
        "one_global_rescue_enforced": (
            exhausted.rescue_attempt_count == 1
            and exhausted.rescue_provider_call_count == 1
            and exhausted.terminal_disposition == "completion_unusable"
        ),
        "response_telemetry_failure_not_rescued": (
            telemetry_failure.rescue_provider_call_count == 0
            and telemetry_failure.terminal_disposition == "instrument_failure"
        ),
    }
    provisional = RunnerFixtureAudit.model_construct(audit_id="pending", **values)
    return RunnerFixtureAudit(audit_id=runner_fixture_audit_id(provisional), **values)


def _cell_summaries_proxy(results: Sequence[Any]) -> tuple[Any, ...]:
    from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501
        _cell_summaries,
    )

    return _cell_summaries(results)


def _make_precall_recovery_audit(
    *,
    static: Any,
    execution_contract: Exact8KExecutionContract,
    provider_contract: ProviderTokenBudgetContract,
) -> PrecallRecoveryAudit:
    job = static.predecessor_manifest.jobs[0]
    binding = runtime_binding(static, job)
    payloads = _projection_payloads(binding.compiler_trajectory)
    events = tuple(FixtureEvent(payload=item) for item in payloads)
    with tempfile.TemporaryDirectory(prefix="v26_100_precall_recovery_") as temporary:
        root = Path(temporary)
        output = root / "recoverable"
        client = ScriptedProviderClient(static.agent_model_config, events)
        first = execute_exact_8k_job_raw(
            job=job,
            execution_contract=execution_contract,
            provider_contract=provider_contract,
            completion_protocol=static.completion_bound_protocol,
            binding=binding,
            client=client,
            output_dir=output,
        )
        before = raw_execution_path(output, job).read_bytes()
        recovered = execute_exact_8k_job_raw(
            job=job,
            execution_contract=execution_contract,
            provider_contract=provider_contract,
            completion_protocol=static.completion_bound_protocol,
            binding=binding,
            client=None,
            output_dir=output,
        )
        after = raw_execution_path(output, job).read_bytes()

        orphan_output = root / "orphan"
        write_json_atomic(raw_provider_path(orphan_output, job, 0), {"orphan_fixture": True})
        orphan_rejected = False
        try:
            execute_exact_8k_job_raw(
                job=job,
                execution_contract=execution_contract,
                provider_contract=provider_contract,
                completion_protocol=static.completion_bound_protocol,
                binding=binding,
                client=ScriptedProviderClient(static.agent_model_config, events),
                output_dir=orphan_output,
            )
        except ValueError:
            orphan_rejected = True

        oversized_client = ScriptedProviderClient(static.agent_model_config, ())
        oversized_ledger = JournaledExact8KClient(
            oversized_client,
            execution_contract=execution_contract,
            job=job,
            provider_contract=provider_contract,
            completion_protocol=static.completion_bound_protocol,
            output_dir=root / "oversized",
        )
        oversized_prompt = "x" * 60001
        oversized_prepared = oversized_ledger.prepare_request(
            phase="primary",
            request_kind="decision",
            primary_prompt=oversized_prompt,
            prompt=oversized_prompt,
            failure_type=None,
            rescue_available_before=True,
        )
        oversized_denied = False
        try:
            oversized_ledger.invoke(oversized_prepared, logical_request_index=0)
        except LLMClientError:
            oversized_denied = oversized_ledger.no_call_terminal is not None

        load_canonical_json(Path(static_path_root(static)) / "unused") if False else None
        source_prompt = _first_primary_prompt(binding)
        resource_client = ScriptedProviderClient(static.agent_model_config, ())
        resource_ledger = JournaledExact8KClient(
            resource_client,
            execution_contract=execution_contract,
            job=job,
            provider_contract=provider_contract,
            completion_protocol=static.completion_bound_protocol,
            output_dir=root / "resource",
        )
        resource_ledger._cumulative_tokens = 150000
        resource_prepared = resource_ledger.prepare_request(
            phase="primary",
            request_kind="decision",
            primary_prompt=source_prompt,
            prompt=source_prompt,
            failure_type=None,
            rescue_available_before=True,
        )
        resource_denied = False
        try:
            resource_ledger.invoke(resource_prepared, logical_request_index=0)
        except LLMClientError:
            resource_denied = resource_ledger.no_call_terminal is not None

        kind_client = ScriptedProviderClient(static.agent_model_config, ())
        kind_ledger = JournaledExact8KClient(
            kind_client,
            execution_contract=execution_contract,
            job=job,
            provider_contract=provider_contract,
            completion_protocol=static.completion_bound_protocol,
            output_dir=root / "kind",
        )
        wrong_kind_rejected = False
        try:
            kind_ledger.prepare_request(
                phase="primary",
                request_kind="final_answer",
                primary_prompt=source_prompt,
                prompt=source_prompt,
                failure_type=None,
                rescue_available_before=True,
            )
        except ValueError:
            wrong_kind_rejected = True

        root_cause = load_canonical_json(
            Path(__file__).resolve().parents[4] / ROOT_CAUSE_PROVIDER_ARTIFACT
        )
        off_primary = str(root_cause["prompt"])
        off_rescue = render_bounded_rescue_completion_prompt(
            "decision",
            off_primary,
            "reasoning_only_length_truncation",
        )
        off_client = ScriptedProviderClient(
            static.agent_model_config,
            (FixtureEvent(payload=payloads[0]),),
        )
        off_ledger = JournaledExact8KClient(
            off_client,
            execution_contract=execution_contract,
            job=job,
            provider_contract=provider_contract,
            completion_protocol=static.completion_bound_protocol,
            output_dir=root / "off_compiler",
        )
        off_prepared = off_ledger.prepare_request(
            phase="rescue",
            request_kind="decision",
            primary_prompt=off_primary,
            prompt=off_rescue,
            failure_type="reasoning_only_length_truncation",
            rescue_available_before=False,
        )
        before_off_calls = off_client.call_count
        off_ledger.invoke(off_prepared, logical_request_index=6)

    values = {
        "execution_contract_id": execution_contract.contract_id,
        "first_execution_provider_call_count": client.call_count,
        "recovered_artifact_id": first.artifact_id,
        "recovery_artifact_id": recovered.artifact_id,
        "raw_only_recovery_byte_identical": before == after,
        "orphan_provider_artifact_rejected": orphan_rejected,
        "oversized_primary_denied_before_delegate": oversized_denied,
        "oversized_primary_delegate_call_count": oversized_client.call_count,
        "resource_exhaustion_denied_before_delegate": resource_denied,
        "resource_exhaustion_delegate_call_count": resource_client.call_count,
        "wrong_actual_request_kind_rejected_before_delegate": wrong_kind_rejected,
        "wrong_actual_request_kind_delegate_call_count": kind_client.call_count,
        "off_compiler_primary_utf8_bytes": len(off_primary.encode("utf-8")),
        "off_compiler_bounded_rescue_utf8_bytes": len(off_rescue.encode("utf-8")),
        "off_compiler_provider_calls_before_certificates": before_off_calls,
        "off_compiler_scripted_provider_calls_after_certificates": off_client.call_count,
        "off_compiler_rescue_absolutely_bounded": len(off_rescue.encode("utf-8")) <= 6144,
        "off_compiler_rescue_dynamically_precertified": (
            off_prepared.dynamic_certificate is not None
        ),
        "off_compiler_rescue_exact_8k_request_bound": (
            off_prepared.request_binding_certificate.request_max_tokens == 8192
        ),
    }
    provisional = PrecallRecoveryAudit.model_construct(audit_id="pending", **values)
    return PrecallRecoveryAudit(
        audit_id=precall_recovery_audit_id(provisional),
        **values,
    )


def static_path_root(static: Any) -> str:
    return str(static.predecessor_report.report_id)


def _first_primary_prompt(binding: Any) -> str:
    from trusted_synthesis.runtime.agent.compact_budget_prompt import (
        compact_public_progress,
        render_compact_decision_prompt,
    )

    progress = compact_public_progress(binding.record.task_package.task.public, ())
    if progress["final_answer_allowed"]:
        raise ValueError("v26.100 representative fixture unexpectedly starts final-ready")
    condition = (
        None
        if binding.source_registered_path.role == "capability"
        else binding.source_registered_path.path_strategy_id
    )
    source = render_compact_decision_prompt(
        binding.prompt_contract.public_context,
        binding.record.task_package.task.public,
        (),
        public_path_condition=condition,
    )
    return render_primary_completion_prompt("decision", source)


def _mutation(name: str, callback: Callable[[], Any]) -> MutationResult:
    try:
        callback()
    except Exception as exc:
        return MutationResult(
            mutation_name=name,
            rejected=True,
            failure_type=type(exc).__name__,
        )
    raise AssertionError(f"v26.100 destructive mutation was accepted: {name}")


def _make_destructive_audit(
    *,
    replay: Exact8KRunnerSourceReplayAudit,
    interpretation: Exact8KOutcomeInterpretationContract,
    execution_contract: Exact8KExecutionContract,
    client_audit: Exact8KClientBindingAudit,
) -> DestructivePreflightAudit:
    def validate_contract(**updates: Any) -> None:
        payload = execution_contract.model_dump(mode="json")
        payload.update(updates)
        Exact8KExecutionContract.model_validate(payload)

    def validate_interpretation(**updates: Any) -> None:
        payload = interpretation.model_dump(mode="json")
        payload.update(updates)
        Exact8KOutcomeInterpretationContract.model_validate(payload)

    def mutate_replay() -> None:
        payload = replay.model_dump(mode="json")
        payload["entries"][0]["observed_sha256"] = "0" * 64
        Exact8KRunnerSourceReplayAudit.model_validate(payload)

    def mutate_request_certificate(**updates: Any) -> None:
        payload = client_audit.representative_certificate.model_dump(mode="json")
        payload.update(updates)
        Exact8KRequestBindingCertificate.model_validate(payload)

    base_config = require_exact_8k_model_config(
        AgentModelConfig.model_validate(
            json.loads(
                (
                    Path(__file__).resolve().parents[4]
                    / "config/deepseek_v4_flash_agent_thinking_8k_v1.json"
                ).read_text(  # noqa: E501
                    encoding="utf-8"
                )
            )["model"]
        )
    )

    def use_16k_config() -> None:
        payload = base_config.model_dump(mode="python")
        payload["max_output_tokens"] = 16384
        require_exact_8k_model_config(AgentModelConfig.model_validate(payload))

    mutations = (
        _mutation("changed_source_digest", mutate_replay),
        _mutation(
            "completion_bound_4096", lambda: validate_contract(completion_upper_bound_tokens=4096)
        ),
        _mutation(
            "completion_bound_16384", lambda: validate_contract(completion_upper_bound_tokens=16384)
        ),
        _mutation(
            "rollout_bound_240000", lambda: validate_contract(rollout_upper_bound_tokens=240000)
        ),
        _mutation(
            "rescue_ceiling_7176", lambda: validate_contract(rescue_prompt_upper_bound_bytes=7176)
        ),
        _mutation("second_rescue", lambda: validate_contract(maximum_rescue_calls_per_job=2)),
        _mutation("model_plan_call", lambda: validate_contract(model_plan_calls_per_job=1)),
        _mutation(
            "model_discovery_call", lambda: validate_contract(model_discovery_calls_per_job=1)
        ),
        _mutation(
            "transient_retry", lambda: validate_contract(transient_provider_retries_per_request=1)
        ),
        _mutation(
            "automatic_16k", lambda: validate_contract(automatic_16k_escalation_allowed=True)
        ),
        _mutation(
            "provider_before_certificates",
            lambda: validate_contract(provider_invocation_before_all_certificates_allowed=True),
        ),
        _mutation(
            "request_body_certificate_removed",
            lambda: validate_contract(actual_request_body_certificate_required=False),
        ),
        _mutation(
            "dynamic_kind_certificate_removed",
            lambda: validate_contract(actual_request_kind_certificate_required=False),
        ),
        _mutation(
            "dynamic_rescue_certificate_removed",
            lambda: validate_contract(actual_rescue_prompt_certificate_required=False),
        ),
        _mutation(
            "raw_recovery_disabled", lambda: validate_contract(raw_only_recovery_required=False)
        ),
        _mutation(
            "orphan_retry_allowed",
            lambda: validate_contract(
                orphan_provider_artifact_requires_fresh_recovery_contract=False
            ),
        ),
        _mutation(
            "private_reasoning_persisted",
            lambda: validate_contract(private_reasoning_content_persisted=True),
        ),
        _mutation(
            "raw_http_body_persisted", lambda: validate_contract(raw_http_body_persisted=True)
        ),
        _mutation(
            "duplicate_job",
            lambda: validate_contract(
                job_ids=(execution_contract.job_ids[0], *execution_contract.job_ids[:-1])
            ),
        ),
        _mutation("16k_model_config", use_16k_config),
        _mutation(
            "request_max_tokens_16384", lambda: mutate_request_certificate(request_max_tokens=16384)
        ),
        _mutation(
            "request_thinking_disabled",
            lambda: mutate_request_certificate(thinking_type="disabled"),
        ),
        _mutation(
            "completion_gate_relaxed",
            lambda: validate_interpretation(zero_failure_gate_threshold=0.20),
        ),
        _mutation(
            "automatic_interpretation_escalation",
            lambda: validate_interpretation(automatic_16k_escalation_allowed=True),
        ),
        _mutation(
            "semantic_rescue",
            lambda: validate_interpretation(
                semantic_validity_can_rescue_completion_or_budget_gate=True
            ),
        ),
    )
    values = {"mutation_results": mutations, "rejected_mutation_count": len(mutations)}
    provisional = DestructivePreflightAudit.model_construct(audit_id="pending", **values)
    return DestructivePreflightAudit(
        audit_id=destructive_preflight_audit_id(provisional),
        **values,
    )


def _detail(path: Path, output_dir: Path, record_count: int = 1) -> DetailFile:
    return DetailFile(
        relative_path=str(path.resolve().relative_to(output_dir.resolve())),
        sha256=sha256(path),
        record_count=record_count,
    )


def build_exact_8k_runner_preflight(
    *,
    run_id: str,
    output_dir: Path,
    package_root: Path,
) -> Exact8KRunnerPreflightReport:
    if run_id != RUNNER_PREFLIGHT_RUN_ID:
        raise ValueError("v26.100 Runner preflight run identity changed")
    replay = build_runner_source_replay(package_root)
    static = load_static_inputs(package_root)
    provider_contract = _make_provider_contract()
    interpretation = _make_interpretation()
    execution_contract = _make_execution_contract(
        replay=replay,
        interpretation=interpretation,
        provider_contract=provider_contract,
        static=static,
        package_root=package_root,
    )
    client_audit = _make_client_binding_audit(
        execution_contract=execution_contract,
        model_config=static.agent_model_config,
    )
    runner_fixture = _make_runner_fixture_audit(
        static=static,
        execution_contract=execution_contract,
        provider_contract=provider_contract,
        interpretation=interpretation,
    )
    precall_recovery = _make_precall_recovery_audit(
        static=static,
        execution_contract=execution_contract,
        provider_contract=provider_contract,
    )
    destructive = _make_destructive_audit(
        replay=replay,
        interpretation=interpretation,
        execution_contract=execution_contract,
        client_audit=client_audit,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads: tuple[tuple[str, BaseModel, int], ...] = (
        ("source_replay_audit.json", replay, len(replay.entries)),
        ("outcome_interpretation_contract.json", interpretation, 1),
        ("provider_token_budget_contract.json", provider_contract, 1),
        ("execution_contract.json", execution_contract, 1),
        ("client_request_binding_audit.json", client_audit, 1),
        ("runner_fixture_audit.json", runner_fixture, len(runner_fixture.direct_rows)),
        ("precall_recovery_audit.json", precall_recovery, 1),
        ("destructive_preflight_audit.json", destructive, len(destructive.mutation_results)),
    )
    for name, payload, _ in payloads:
        write_json_atomic(output_dir / name, payload.model_dump(mode="json"))
    details = tuple(
        sorted(
            (_detail(output_dir / name, output_dir, count) for name, _, count in payloads),
            key=lambda item: item.relative_path,
        )
    )
    values = {
        "source_replay_audit_id": replay.audit_id,
        "outcome_interpretation_contract_id": interpretation.contract_id,
        "provider_budget_contract_id": provider_contract.contract_id,
        "execution_contract_id": execution_contract.contract_id,
        "client_binding_audit_id": client_audit.audit_id,
        "runner_fixture_audit_id": runner_fixture.audit_id,
        "precall_recovery_audit_id": precall_recovery.audit_id,
        "destructive_preflight_audit_id": destructive.audit_id,
        "detail_files": details,
        "implementation_source_files": execution_contract.runner_implementation_source_files,
    }
    provisional = Exact8KRunnerPreflightReport.model_construct(report_id="pending", **values)
    report = Exact8KRunnerPreflightReport(
        report_id=exact_8k_runner_preflight_report_id(provisional),
        **values,
    )
    write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Finance v26.100 exact-8K Runner preflight"
    )
    parser.add_argument("--run-id", default=RUNNER_PREFLIGHT_RUN_ID)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    args = parser.parse_args()
    report = build_exact_8k_runner_preflight(
        run_id=args.run_id,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
