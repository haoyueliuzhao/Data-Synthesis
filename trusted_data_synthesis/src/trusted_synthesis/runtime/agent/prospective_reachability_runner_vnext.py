from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.core.measurement.support import (
    BaselineActionSetResolution,
    MeasurementSupportDecision,
    classify_measurement_support,
    make_measurement_support_event,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_execution as privacy_runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_privacy_safe_prompt_runner_preflight as prompt_runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_representation_qualification_preflight as s1_runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_execution as action_execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_measurement_support import (
    classify_non_observation_support,
    classify_public_observation_support,
    public_progress_vector_id,
    resolve_public_baseline_action_set,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalHostEnvelope,
    QualifiedFinalResponseGrammar,
    QualifiedFinalResponsePayload,
    make_qualified_final_host_envelope,
    parse_qualified_final_response,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    CanonicalActionCommit,
    PublicSemanticRejectionObservation,
    SemanticActionState,
    build_semantic_action_state,
    evaluate_canonical_action_proposal,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    SemanticActionResponseRejection,
    parse_exact_canonical_action_payload,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import CompletionProjection
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest, AgentToolObservation


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _descriptor(path: Path, output_dir: Path) -> legacy.RawFileDescriptor:
    return legacy.RawFileDescriptor(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def render_qualified_final_primary_prompt(
    compact_public_context: str,
    *,
    grammar: QualifiedFinalResponseGrammar,
) -> str:
    payload = {
        "instruction": "Return exactly one JSON object matching response_grammar.",
        "public_context": compact_public_context,
        "response_grammar": {
            "outer_fields": list(grammar.outer_field_order),
            "answer_fields": list(grammar.answer_field_order),
            "citation_fields": list(grammar.citation_field_order),
            "exact_field_sets": True,
            "minimum_citations": 1,
            "response_protocol": grammar.response_protocol,
            "model_owns": ["answer.result", "answer.citations", "rationale_summary"],
            "hidden_model_content": "must_not_be_included_or_reused",
        },
    }
    return "Return exactly one JSON object.\n" + json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _qualified_final_prompt_payload(prompt: str) -> dict[str, Any]:
    prefix, separator, body = prompt.partition("\n")
    if prefix != "Return exactly one JSON object." or separator != "\n":
        raise ValueError("qualified Final Prompt envelope changed")
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError("qualified Final Prompt payload is not an object")
    return value


def render_qualified_final_rescue_prompt(
    primary_prompt: str,
    *,
    failure_family: str,
    failure_subtype: str,
) -> str:
    primary = _qualified_final_prompt_payload(primary_prompt)
    payload = {
        "instruction": "Return exactly one corrected JSON object matching response_grammar.",
        "public_context": primary["public_context"],
        "response_grammar": primary["response_grammar"],
        "typed_failure": {"family": failure_family, "subtype": failure_subtype},
    }
    return "Return exactly one JSON object.\n" + json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class PreparedQualifiedRequest(privacy_runner.PreparedPrivacyFirstRequest):
    final_response_host_envelope: QualifiedFinalHostEnvelope | None = None


class QualifiedCompletedResult(FrozenModel):
    result_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    final_payload: QualifiedFinalResponsePayload
    final_attempt_id: str = Field(min_length=1)
    final_response_host_envelope: QualifiedFinalHostEnvelope
    schema_version: Literal["finance_v26_qualified_reachability_completed_result.v1"] = (
        "finance_v26_qualified_reachability_completed_result.v1"
    )

    @model_validator(mode="after")
    def validate_result(self) -> QualifiedCompletedResult:
        if self.result_id != _identity(
            self,
            "result_id",
            "finance_v26_qualified_reachability_completed_result:",
        ):
            raise ValueError("qualified Reachability completed-result identity changed")
        return self


RunnerTerminal = Literal[
    "completed_model_endpoint",
    "model_result_failure",
    "measurement_support_exit",
    "typed_semantic_rejection",
    "typed_budget_no_call",
    "provider_transport_failure",
    "instrument_failure",
    "privacy_rejection",
]


class FreshReachabilityRawExecution(FrozenModel):
    artifact_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    job_payload: dict[str, Any]
    task_package_id: str = Field(min_length=1)
    operational_record_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    provider_envelope_artifacts: tuple[legacy.RawFileDescriptor, ...]
    public_payload_projection_artifacts: tuple[legacy.RawFileDescriptor, ...]
    transport_invocation_artifacts: tuple[legacy.RawFileDescriptor, ...]
    provider_telemetry: tuple[legacy.ModelCallTelemetry, ...]
    attempts: tuple[privacy_runner.PrivacyFirstAttempt, ...]
    semantic_choices: tuple[action_execution.SemanticChoiceRecord, ...]
    commits: tuple[action_execution.SemanticActionCommitRecord, ...]
    semantic_rejections: tuple[PublicSemanticRejectionObservation, ...]
    observations: tuple[AgentToolObservation, ...]
    measurement_support_decisions: tuple[MeasurementSupportDecision, ...]
    completed_result: QualifiedCompletedResult | None = None
    terminal_disposition: RunnerTerminal
    terminal_failure_type: str | None = None
    execution_error: str | None = None
    measurement_support_available: bool
    model_endpoint_observed: bool
    instrument_integrity: bool
    privacy_compliant: bool
    cumulative_provider_tokens: int = Field(ge=0, le=1_120_000)
    stage_one_provider_call_count: int = Field(ge=0, le=23)
    transport_inclusive_invocation_count: int = Field(ge=0, le=24)
    abi_rescue_attempt_count: int = Field(ge=0, le=1)
    semantic_recovery_attempt_count: int = Field(ge=0, le=1)
    transport_replacement_attempt_count: int = Field(ge=0, le=1)
    ordinary_detour_count: int = Field(ge=0, le=2)
    privacy_rejected_payload_count: int = Field(ge=0)
    exact_four_field_action_payload_count: int = Field(ge=0)
    exact_qualified_final_payload_count: int = Field(ge=0, le=1)
    first_action_interface_qualified: bool
    later_provider_calls_after_support_exit: Literal[0] = 0
    task_verifier_invocation_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    state_mapping_row_count: Literal[0] = 0
    schema_version: Literal["finance_v26_fresh_reachability_raw_execution.v1"] = (
        "finance_v26_fresh_reachability_raw_execution.v1"
    )

    @model_validator(mode="after")
    def validate_raw(self) -> FreshReachabilityRawExecution:
        if (
            self.job_payload.get("job_id") != self.job_id
            or self.job_payload.get("task_package_id") != self.task_package_id
            or len(self.provider_envelope_artifacts) != self.stage_one_provider_call_count
            or len(self.public_payload_projection_artifacts) != self.stage_one_provider_call_count
            or len(self.provider_telemetry) != self.stage_one_provider_call_count
            or len(self.transport_invocation_artifacts) != self.transport_inclusive_invocation_count
            or self.transport_replacement_attempt_count
            != self.transport_inclusive_invocation_count - self.stage_one_provider_call_count
            or self.measurement_support_available
            != (self.terminal_disposition != "measurement_support_exit")
            or self.instrument_integrity != (self.terminal_disposition != "instrument_failure")
            or self.privacy_compliant != (self.terminal_disposition != "privacy_rejection")
        ):
            raise ValueError("fresh Reachability Raw denominator changed")
        if self.model_endpoint_observed and not (
            self.measurement_support_available
            and self.instrument_integrity
            and self.privacy_compliant
        ):
            raise ValueError("ineligible Fresh Reachability Raw claims a model endpoint")
        if (
            self.terminal_disposition == "completed_model_endpoint"
            and self.completed_result is None
        ):
            raise ValueError("completed model endpoint lacks its qualified Final payload")
        if self.artifact_id != _identity(
            self,
            "artifact_id",
            "finance_v26_fresh_reachability_raw_execution:",
        ):
            raise ValueError("fresh Reachability Raw identity changed")
        return self


@dataclass(frozen=True)
class FreshReachabilityRuntimeBinding:
    package: Any
    record: Any
    environment: AgentToolEnvironmentManifest
    prompt_contract: Any
    source_selection_id: str
    path_strategy_id: str
    public_path_condition: str | None


class _QualifiedJournal(s1_runner._S1Journal):  # noqa: SLF001
    def prepare(
        self,
        *,
        logical_request_index: int,
        request_kind: legacy.StageOneRequestKind,
        public_attempt_phase: privacy_runner.PublicAttemptPhase,
        primary_prompt: str,
        prompt: str,
        public_state_id: str | None,
        final_response_host_envelope: QualifiedFinalHostEnvelope | None,
        abi_rescue_count_before: int,
        semantic_recovery_count_before: int,
    ) -> PreparedQualifiedRequest:
        if self._instrument_failures:  # noqa: SLF001
            raise privacy_runner.InstrumentContractError(
                "cannot prepare after an Instrument failure"
            )
        provider_phase: legacy.StageOneAttemptPhase = (
            "rescue" if public_attempt_phase == "abi_rescue" else "primary"
        )
        request_binding = legacy.certify_stage_one_request_pre_call(
            config=self._delegate.config,  # noqa: SLF001
            prompt=prompt,
            request_kind=request_kind,
            phase=provider_phase,
        )
        resource = self._resource_certificate(  # noqa: SLF001
            prompt,
            request_kind=request_kind,
            public_attempt_phase=public_attempt_phase,
            abi_rescue_available_before=abi_rescue_count_before == 0,
            semantic_recovery_available_before=semantic_recovery_count_before == 0,
        )
        self._resource_certificates.append(resource)  # noqa: SLF001
        dynamic: privacy_runner.PrivacyFirstDynamicRequestCertificate | None = None
        if resource.provider_call_permitted:
            values = {
                "runner_contract_id": self._runner_contract.contract_id,  # noqa: SLF001
                "job_id": self._job.job_id,  # noqa: SLF001
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
            provisional = privacy_runner.PrivacyFirstDynamicRequestCertificate.model_construct(
                certificate_id="pending", **values
            )
            dynamic = privacy_runner.PrivacyFirstDynamicRequestCertificate(
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
        provisional_request = PreparedQualifiedRequest.model_construct(
            preparation_id="pending", **values
        )
        return PreparedQualifiedRequest(
            preparation_id=_identity(
                provisional_request,
                "preparation_id",
                "finance_v26_prepared_privacy_first_request:",
            ),
            **values,
        )


@dataclass(frozen=True)
class _CallOutcome:
    attempt: privacy_runner.PrivacyFirstAttempt
    payload: dict[str, Any] | None = None
    proposal: Any | None = None
    final_payload: QualifiedFinalResponsePayload | None = None


def _attempt(
    *,
    prepared: PreparedQualifiedRequest,
    provider_call_index: int | None,
    disposition: Any,
    response_payload_present: bool,
    payload_projection_status: Any = None,
    exact_four_field_action_payload: bool = False,
    exact_qualified_final_payload: bool = False,
    failure_family: str | None = None,
    failure_subtype: str | None = None,
    completion_failure_type: str | None = None,
    error: str | None = None,
) -> privacy_runner.PrivacyFirstAttempt:
    return privacy_runner._make_attempt(  # noqa: SLF001
        prepared=cast(Any, prepared),
        provider_call_index=provider_call_index,
        disposition=disposition,
        response_payload_present=response_payload_present,
        payload_projection_status=payload_projection_status,
        exact_four_field_action_payload=exact_four_field_action_payload,
        exact_two_field_final_payload=exact_qualified_final_payload,
        failure_family=failure_family,
        failure_subtype=failure_subtype,
        completion_failure_type=completion_failure_type,
        error=error,
    )


def _invoke_once(
    ledger: _QualifiedJournal,
    *,
    logical_request_index: int,
    request_kind: legacy.StageOneRequestKind,
    public_attempt_phase: privacy_runner.PublicAttemptPhase,
    primary_prompt: str,
    prompt: str,
    state: SemanticActionState | None,
    final_response_host_envelope: QualifiedFinalHostEnvelope | None,
    static: Any,
    qualified_grammar: QualifiedFinalResponseGrammar,
    abi_rescue_count: int,
    semantic_recovery_count: int,
) -> _CallOutcome:
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
        payload, _ = ledger.invoke(cast(Any, prepared))
    except privacy_runner.BudgetNoCallError as exc:
        return _CallOutcome(
            attempt=_attempt(
                prepared=prepared,
                provider_call_index=None,
                disposition="typed_budget_no_call",
                response_payload_present=False,
                error=str(exc),
            )
        )
    except privacy_runner.PayloadPrivacyProjectionError as exc:
        return _CallOutcome(
            attempt=_attempt(
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
    except s1_runner._TransportReplacementExhausted as exc:  # noqa: SLF001
        return _CallOutcome(
            attempt=_attempt(
                prepared=prepared,
                provider_call_index=None,
                disposition="provider_transport_failure",
                response_payload_present=False,
                error=str(exc),
            )
        )
    except s1_runner._TransportInvocationLimit as exc:  # noqa: SLF001
        return _CallOutcome(
            attempt=_attempt(
                prepared=prepared,
                provider_call_index=None,
                disposition="typed_budget_no_call",
                response_payload_present=False,
                error=str(exc),
            )
        )
    except privacy_runner.InstrumentContractError as exc:
        index = before if ledger.provider_call_count > before else None
        status = ledger.projection_statuses[-1] if index is not None else None
        return _CallOutcome(
            attempt=_attempt(
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
        disposition = (
            "completion_failure"
            if exc.telemetry and all(item.http_success for item in exc.telemetry)
            else "provider_transport_failure"
        )
        return _CallOutcome(
            attempt=_attempt(
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
            return _CallOutcome(
                attempt=_attempt(
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
            raise ValueError("qualified Final Parser lacks Host Envelope")
        final_payload = parse_qualified_final_response(
            payload,
            grammar=qualified_grammar,
            envelope=final_response_host_envelope,
        )
        return _CallOutcome(
            attempt=_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="usable",
                response_payload_present=True,
                payload_projection_status="validated_public_payload",
                exact_qualified_final_payload=True,
            ),
            payload=payload,
            final_payload=final_payload,
        )
    except (SemanticActionResponseRejection, ValidationError, ValueError) as exc:
        return _CallOutcome(
            attempt=_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="model_result_failure",
                response_payload_present=True,
                payload_projection_status="validated_public_payload",
                failure_family="response_serialization_failure",
                failure_subtype="response_not_exact_qualified_grammar",
                error=str(exc),
            ),
            payload=payload,
        )


def _active_call(
    ledger: _QualifiedJournal,
    *,
    attempts: list[privacy_runner.PrivacyFirstAttempt],
    logical_request_index: int,
    request_kind: legacy.StageOneRequestKind,
    public_attempt_phase: Literal["primary", "semantic_recovery"],
    primary_prompt: str,
    state: SemanticActionState | None,
    presentation_salt: str | None,
    instruction: str | None,
    condition: str | None,
    final_response_host_envelope: QualifiedFinalHostEnvelope | None,
    static: Any,
    qualified_grammar: QualifiedFinalResponseGrammar,
    abi_rescue_count: int,
    semantic_recovery_count: int,
) -> tuple[_CallOutcome, int]:
    primary = _invoke_once(
        ledger,
        logical_request_index=logical_request_index,
        request_kind=request_kind,
        public_attempt_phase=public_attempt_phase,
        primary_prompt=primary_prompt,
        prompt=primary_prompt,
        state=state,
        final_response_host_envelope=final_response_host_envelope,
        static=static,
        qualified_grammar=qualified_grammar,
        abi_rescue_count=abi_rescue_count,
        semantic_recovery_count=semantic_recovery_count,
    )
    attempts.append(primary.attempt)
    if abi_rescue_count == 0 and s1_runner._abi_rescue_allowed(primary.attempt):  # noqa: SLF001
        abi_rescue_count = 1
        family = primary.attempt.failure_family or "channel_parse_failure"
        subtype = (
            primary.attempt.failure_subtype
            or primary.attempt.completion_failure_type
            or "completion_failure"
        )
        if request_kind == "semantic_proposal":
            if state is None or presentation_salt is None or instruction is None:
                raise ValueError("Action ABI Rescue lacks privacy-safe S1 state")
            rescue_prompt = prompt_runner.render_privacy_safe_s1_action_prompt(
                phase="abi_rescue",
                instruction=instruction,
                state=state,
                public_path_condition=condition,
                presentation_salt=presentation_salt,
                typed_failure={"family": family, "subtype": subtype},
                grammar=static.action_grammar,
            )
        else:
            rescue_prompt = render_qualified_final_rescue_prompt(
                primary_prompt,
                failure_family=family,
                failure_subtype=subtype,
            )
        rescue = _invoke_once(
            ledger,
            logical_request_index=logical_request_index,
            request_kind=request_kind,
            public_attempt_phase="abi_rescue",
            primary_prompt=primary_prompt,
            prompt=rescue_prompt,
            state=state,
            final_response_host_envelope=final_response_host_envelope,
            static=static,
            qualified_grammar=qualified_grammar,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        attempts.append(rescue.attempt)
        return rescue, abi_rescue_count
    return primary, abi_rescue_count


def _presentation_salt(
    *,
    binding: FreshReachabilityRuntimeBinding,
    state: SemanticActionState,
    logical_index: int,
) -> str:
    return canonical_hash(
        {
            "source_selection_id": binding.source_selection_id,
            "task_package_id": binding.package.task_package_id,
            "state_id": state.state_id,
            "logical_index": logical_index,
            "path_strategy_id": binding.path_strategy_id,
        },
        prefix="finance_v26_fresh_reachability_candidate_presentation:",
    )


def _unavailable_support(
    *,
    before: SemanticActionState,
    selected_action_id: str,
    observation_status: Literal["succeeded", "failed"],
) -> MeasurementSupportDecision:
    progress = public_progress_vector_id(before)
    event = make_measurement_support_event(
        event_kind="public_observation",
        public_state_id_before=before.state_id,
        public_state_id_after=canonical_hash(
            {
                "state_id_before": before.state_id,
                "selected_action_id": selected_action_id,
                "observation_status": observation_status,
            },
            prefix="prospective_unavailable_public_successor:",
        ),
        progress_vector_id_before=progress,
        progress_vector_id_after=progress,
        selected_action_id=selected_action_id,
        observation_status=observation_status,
        successor_public_state_available=False,
    )
    return classify_measurement_support(
        event,
        baseline_resolver=lambda: cast(
            BaselineActionSetResolution,
            resolve_public_baseline_action_set(before),
        ),
    )


def _raw_path(output_dir: Path, job: Any) -> Path:
    return output_dir / "raw_execution" / f"{job.job_id.rsplit(':', 1)[-1]}.json"


def execute_fresh_reachability_job_raw(
    *,
    job: Any,
    runner_contract: Any,
    resource_contract: Any,
    static: Any,
    qualified_grammar: QualifiedFinalResponseGrammar,
    binding: FreshReachabilityRuntimeBinding,
    client: Any | None,
    output_dir: Path,
) -> FreshReachabilityRawExecution:
    raw_path = _raw_path(output_dir, job)
    if raw_path.exists():
        raw = FreshReachabilityRawExecution.model_validate_json(
            raw_path.read_text(encoding="utf-8")
        )
        if (
            raw.runner_contract_id != runner_contract.contract_id
            or raw.job_payload != job.model_dump(mode="json")
        ):
            raise ValueError("fresh Reachability Raw recovery crosses identities")
        for descriptor in (
            *raw.provider_envelope_artifacts,
            *raw.public_payload_projection_artifacts,
            *raw.transport_invocation_artifacts,
        ):
            path = output_dir / descriptor.relative_path
            if (
                not path.is_file()
                or _sha256(path) != descriptor.sha256
                or path.stat().st_size != descriptor.byte_count
            ):
                raise ValueError("fresh Reachability Raw recovery bytes changed")
        return raw
    envelope_dir = privacy_runner.provider_envelope_path(output_dir, cast(Any, job), 0).parent
    projection_dir = privacy_runner.payload_projection_path(output_dir, cast(Any, job), 0).parent
    invocation_dir = s1_runner._invocation_path(output_dir, cast(Any, job), 0).parent  # noqa: SLF001
    if any(
        directory.exists() and any(directory.iterdir())
        for directory in (envelope_dir, projection_dir, invocation_dir)
    ):
        raise ValueError("orphan Provider or invocation artifact forbids retry")
    if client is None:
        raise ValueError("pending fresh Reachability Job has no Stage 1 client")
    ledger = _QualifiedJournal(
        client,
        runner_contract=cast(Any, runner_contract),
        resource_contract=cast(Any, resource_contract),
        job=cast(Any, job),
        output_dir=output_dir,
    )
    runtime = legacy._runtime(binding.record, binding.environment)  # noqa: SLF001
    observations: list[AgentToolObservation] = []
    attempts: list[privacy_runner.PrivacyFirstAttempt] = []
    choices: list[action_execution.SemanticChoiceRecord] = []
    commits: list[action_execution.SemanticActionCommitRecord] = []
    semantic_rejections: list[PublicSemanticRejectionObservation] = []
    support_decisions: list[MeasurementSupportDecision] = []
    abi_rescue_count = 0
    semantic_recovery_count = 0
    ordinary_detour_count = 0
    pending_semantic_recovery = False
    prior_rejected_action_id: str | None = None
    terminal: RunnerTerminal = "model_result_failure"
    failure_type: str | None = None
    error: str | None = None
    completed: QualifiedCompletedResult | None = None
    final_state: SemanticActionState | None = None
    final_commit: CanonicalActionCommit | None = None
    logical_index = 0
    condition = binding.public_path_condition
    for _ in range(resource_contract.maximum_primary_stage_one_requests - 1):
        state = build_semantic_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            tuple(observations),
            semantic_rejections=tuple(semantic_rejections),
        )
        presentation_salt = _presentation_salt(
            binding=binding,
            state=state,
            logical_index=logical_index,
        )
        phase: Literal["primary", "semantic_recovery"] = (
            "semantic_recovery" if pending_semantic_recovery else "primary"
        )
        typed_failure = None
        if pending_semantic_recovery:
            rejection = semantic_rejections[-1]
            typed_failure = {
                "family": "semantic_action_rejection",
                "subtype": rejection.error_category,
                "rejection_id": rejection.rejection_id,
            }
        prompt = prompt_runner.render_privacy_safe_s1_action_prompt(
            phase=phase,
            instruction=binding.record.task_package.task.public.instruction,
            state=state,
            public_path_condition=condition,
            presentation_salt=presentation_salt,
            typed_failure=typed_failure,
            grammar=static.action_grammar,
        )
        decoded_state, _ = (
            s1_runner.predecessor.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001
                prompt,
                presentation_salt=presentation_salt,
            )
        )
        if decoded_state != state or prompt_runner._sensitive_key_paths(  # noqa: SLF001
            prompt_runner._privacy_safe_prompt_payload(prompt).model_dump(mode="json")  # noqa: SLF001
        ):
            raise ValueError("fresh Reachability Prompt changed state or safe Key surface")
        ledger.ordinary_detour_count = ordinary_detour_count
        outcome, abi_rescue_count = _active_call(
            ledger,
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="semantic_proposal",
            public_attempt_phase=phase,
            primary_prompt=prompt,
            state=state,
            presentation_salt=presentation_salt,
            instruction=binding.record.task_package.task.public.instruction,
            condition=condition,
            final_response_host_envelope=None,
            static=static,
            qualified_grammar=qualified_grammar,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        current_index = logical_index
        logical_index += 1
        if outcome.attempt.disposition != "usable" or outcome.proposal is None:
            terminal = cast(RunnerTerminal, s1_runner._terminal_from_attempt(outcome.attempt))  # noqa: SLF001
            if outcome.attempt.payload_projection_status == "privacy_rejected":
                terminal = "privacy_rejection"
            failure_type = (
                outcome.attempt.failure_subtype
                or outcome.attempt.completion_failure_type
                or outcome.attempt.disposition
            )
            error = outcome.attempt.error
            break
        proposal = outcome.proposal
        selected = evaluate_canonical_action_proposal(
            state,
            proposal,
            call_index=len(observations) + 1,
        )
        if selected.rejection is not None:
            choices.append(
                action_execution._choice_record(  # noqa: SLF001
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
            terminal = "typed_semantic_rejection"
            failure_type = "semantic_recovery_exhausted"
            error = selected.rejection.error_category
            break
        commit = selected.commit
        if commit is None:
            raise ValueError("accepted fresh Reachability action lacks a Commit")
        commits.append(
            s1_runner._semantic_commit_record(  # noqa: SLF001
                logical_request_index=current_index,
                state=state,
                proposal=proposal,
                commit=commit,
                stage_two_profile_id=static.stage_two.profile_id,
                provider_calls_before_commit=ledger.provider_call_count,
            )
        )
        pending_semantic_recovery = False
        observation: AgentToolObservation | None = None
        progress: bool | None = None
        if commit.call is not None:
            observation = legacy._execute_observation(  # noqa: SLF001
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
            try:
                after: SemanticActionState | None = build_semantic_action_state(
                    binding.record.task_package.task.public,
                    binding.environment,
                    tuple(observations),
                    semantic_rejections=tuple(semantic_rejections),
                )
            except ValueError as exc:
                if str(exc) != "semantic action state has no selectable public action":
                    raise
                after = None
            status = cast(Literal["succeeded", "failed"], observation.status)
            if after is None:
                support = _unavailable_support(
                    before=state,
                    selected_action_id=proposal.action_id,
                    observation_status=status,
                )
            elif proposal.decision_kind == "verify_terminal_operation":
                support = classify_non_observation_support(
                    event_kind="terminal_verification",
                    state=state,
                    state_after=after,
                    selected_action_id=proposal.action_id,
                )
            else:
                support = classify_public_observation_support(
                    state_before=state,
                    state_after=after,
                    selected_action_id=proposal.action_id,
                    observation_status=status,
                )
            support_decisions.append(support)
            progress = bool(after is not None and support.reason_code == "public_progress")
            ordinary_detour_count += int(support.ordinary_detour_observed)
            ledger.ordinary_detour_count = ordinary_detour_count
            if support.status == "unavailable":
                terminal = "measurement_support_exit"
                failure_type = support.reason_code
                error = "trajectory left the pre-registered Measurement Support"
            elif ordinary_detour_count > 1:
                terminal = "measurement_support_exit"
                failure_type = "ordinary_detour_allowance_exhausted"
                error = "trajectory left the pre-registered T_dyn^(1) support"
        else:
            support = classify_non_observation_support(
                event_kind="final_commit" if commit.action == "emit_final" else "non_public_commit",
                state=state,
                selected_action_id=proposal.action_id,
            )
            support_decisions.append(support)
        choices.append(
            action_execution._choice_record(  # noqa: SLF001
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
        if terminal == "measurement_support_exit":
            break
        if commit.action == "emit_final":
            final_state = state
            final_commit = commit
            break
    else:
        terminal = "model_result_failure"
        failure_type = "semantic_action_primary_request_limit_exhausted"
        error = "model did not reach Final within the frozen request limit"
    if (
        final_state is not None
        and final_commit is not None
        and terminal == "model_result_failure"
        and failure_type is None
    ):
        compact_source = render_compact_final_prompt(
            binding.prompt_contract.public_context,
            binding.record.task_package.task.public,
            tuple(observations),
            public_path_condition=condition,
        )
        final_prompt = render_qualified_final_primary_prompt(
            compact_source,
            grammar=qualified_grammar,
        )
        host_envelope = make_qualified_final_host_envelope(
            terminal_state_id=final_state.state_id,
            terminal_commit_id=final_commit.commit_id,
            grammar=qualified_grammar,
        )
        ledger.ordinary_detour_count = ordinary_detour_count
        outcome, abi_rescue_count = _active_call(
            ledger,
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="final_answer",
            public_attempt_phase="primary",
            primary_prompt=final_prompt,
            state=None,
            presentation_salt=None,
            instruction=None,
            condition=condition,
            final_response_host_envelope=host_envelope,
            static=static,
            qualified_grammar=qualified_grammar,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        if outcome.attempt.disposition == "usable" and outcome.final_payload is not None:
            values = {
                "job_id": job.job_id,
                "final_payload": outcome.final_payload,
                "final_attempt_id": outcome.attempt.attempt_id,
                "final_response_host_envelope": host_envelope,
            }
            provisional = QualifiedCompletedResult.model_construct(result_id="pending", **values)
            completed = QualifiedCompletedResult(
                result_id=_identity(
                    provisional,
                    "result_id",
                    "finance_v26_qualified_reachability_completed_result:",
                ),
                **values,
            )
            terminal = "completed_model_endpoint"
        else:
            terminal = cast(RunnerTerminal, s1_runner._terminal_from_attempt(outcome.attempt))  # noqa: SLF001
            if outcome.attempt.payload_projection_status == "privacy_rejected":
                terminal = "privacy_rejection"
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
    first_choice = choices[0] if choices else None
    first_interface = bool(
        first_choice is not None
        and first_choice.visible_action_id_match
        and first_choice.decision_kind_match
        and first_choice.semantic_accepted
        and first_choice.commit_id is not None
    )
    measurement_support_available = terminal != "measurement_support_exit"
    instrument_integrity = terminal != "instrument_failure"
    privacy_compliant = terminal != "privacy_rejection"
    model_endpoint_observed = bool(
        measurement_support_available and instrument_integrity and privacy_compliant
    )
    raw_values = {
        "runner_contract_id": runner_contract.contract_id,
        "job_id": job.job_id,
        "job_payload": job.model_dump(mode="json"),
        "task_package_id": job.task_package_id,
        "operational_record_id": binding.record.record_id,
        "environment_manifest_id": binding.environment.manifest_id,
        "provider_envelope_artifacts": ledger.envelope_descriptors,
        "public_payload_projection_artifacts": ledger.projection_descriptors,
        "transport_invocation_artifacts": ledger.transport_invocation_descriptors,
        "provider_telemetry": ledger.telemetry,
        "attempts": tuple(attempts),
        "semantic_choices": tuple(choices),
        "commits": tuple(commits),
        "semantic_rejections": tuple(semantic_rejections),
        "observations": tuple(observations),
        "measurement_support_decisions": tuple(support_decisions),
        "completed_result": completed,
        "terminal_disposition": terminal,
        "terminal_failure_type": failure_type,
        "execution_error": error,
        "measurement_support_available": measurement_support_available,
        "model_endpoint_observed": model_endpoint_observed,
        "instrument_integrity": instrument_integrity,
        "privacy_compliant": privacy_compliant,
        "cumulative_provider_tokens": ledger.cumulative_tokens,
        "stage_one_provider_call_count": ledger.provider_call_count,
        "transport_inclusive_invocation_count": ledger.transport_invocation_count,
        "abi_rescue_attempt_count": sum(
            item.public_attempt_phase == "abi_rescue" for item in attempts
        ),
        "semantic_recovery_attempt_count": sum(
            item.public_attempt_phase == "semantic_recovery" for item in choices
        ),
        "transport_replacement_attempt_count": ledger.transport_replacement_count,
        "ordinary_detour_count": ordinary_detour_count,
        "privacy_rejected_payload_count": sum(
            item == "privacy_rejected" for item in ledger.projection_statuses
        ),
        "exact_four_field_action_payload_count": sum(
            item.exact_four_field_action_payload for item in attempts
        ),
        "exact_qualified_final_payload_count": sum(
            item.exact_two_field_final_payload for item in attempts
        ),
        "first_action_interface_qualified": first_interface,
    }
    provisional_raw = FreshReachabilityRawExecution.model_construct(
        artifact_id="pending", **raw_values
    )
    raw = FreshReachabilityRawExecution(
        artifact_id=_identity(
            provisional_raw,
            "artifact_id",
            "finance_v26_fresh_reachability_raw_execution:",
        ),
        **raw_values,
    )
    _write_json_atomic(raw_path, raw)
    persisted = FreshReachabilityRawExecution.model_validate_json(
        raw_path.read_text(encoding="utf-8")
    )
    if persisted.artifact_id != raw.artifact_id:
        raise ValueError("fresh Reachability Raw persistence changed its identity")
    return persisted


def qualified_reference_final_answer(
    *,
    legacy_answer: Mapping[str, Any],
    observations: Sequence[AgentToolObservation],
) -> dict[str, Any]:
    evidence_ids = legacy._selected_evidence_ids(observations)  # noqa: SLF001
    if not evidence_ids:
        raise ValueError("qualified reference Final fixture lacks selected Evidence")
    return {
        "result": json.loads(json.dumps(dict(legacy_answer))),
        "citations": [{"evidence_id": item} for item in evidence_ids],
    }
