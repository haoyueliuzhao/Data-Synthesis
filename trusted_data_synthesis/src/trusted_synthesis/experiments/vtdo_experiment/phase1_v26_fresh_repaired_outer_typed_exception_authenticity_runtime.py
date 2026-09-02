# ruff: noqa: E501
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as frozen_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_exact_online_execution_authorization_models as v211_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight as v209,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_models as v212_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_runtime as v212_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_outer_typed_exception_authenticity_models as models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import AgentModelConfig


def _encoded(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _identified(values: dict[str, Any], *, field: str, prefix: str) -> dict[str, Any]:
    result = dict(values)
    result[field] = canonical_hash(values, prefix=prefix)
    return result


class ProviderNoPayloadError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("provider_failure_no_payload", "provider returned no public payload")


class ProviderTransportError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("provider_transport_failure", "typed transport failure")


class PrivacyEvidenceError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("privacy_rejection", "public payload failed privacy projection")


class ResourceBudgetError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("resource_budget_exhausted", "resource budget exhausted")


class InstrumentEvidenceError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("instrument_failure", "instrument evidence failure")


class ProviderIdentityError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("provider_identity_failure", "provider identity differs")


class ThinkingIntegrityError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("thinking_integrity_failure", "Thinking telemetry differs")


class UsageIntegrityError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("usage_integrity_failure", "Usage telemetry differs")


OUTER_ERROR_TYPES: tuple[type[v209.TypedTransportFailure], ...] = (
    ProviderNoPayloadError,
    ProviderTransportError,
    PrivacyEvidenceError,
    ResourceBudgetError,
    InstrumentEvidenceError,
    ProviderIdentityError,
    ThinkingIntegrityError,
    UsageIntegrityError,
)


class RunnerFailureObservationAuthority:
    """Append-only in-memory authority populated only by the Runner catch path."""

    def __init__(self) -> None:
        self._by_invocation: dict[str, models.TypedFailureObservation] = {}

    def record_from_runner(self, observation: models.TypedFailureObservation) -> None:
        strict = models.TypedFailureObservation.model_validate(
            observation.model_dump(mode="python", warnings=False)
        )
        if strict.invocation_id in self._by_invocation:
            raise ValueError("Runner failure observation invocation already exists")
        self._by_invocation[strict.invocation_id] = strict

    def require_exact(
        self, observation: models.TypedFailureObservation
    ) -> models.TypedFailureObservation:
        strict = models.TypedFailureObservation.model_validate(
            observation.model_dump(mode="python", warnings=False)
        )
        actual = self._by_invocation.get(strict.invocation_id)
        if actual is None or models.canonical_bytes(actual) != models.canonical_bytes(strict):
            raise ValueError("typed failure observation differs from Runner-owned authority")
        return actual

    def get(self, invocation_id: str) -> models.TypedFailureObservation:
        try:
            return self._by_invocation[invocation_id]
        except KeyError as error:
            raise ValueError("Runner failure observation is absent") from error

    @property
    def count(self) -> int:
        return len(self._by_invocation)


class ObservationAuthenticFullConditionRunner(v209.FinalContinuityRepairedFullConditionRunner):
    """The v26.209 Runner route with an observation emitted inside its typed-failure catch."""

    def __init__(
        self,
        *,
        observation_authority: RunnerFailureObservationAuthority,
        runner_binding_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._observation_authority = observation_authority
        self._runner_binding_id = runner_binding_id

    def _invoke_current_state(
        self,
        *,
        job: v209_models.ExecutableDevelopmentJob,
        invocation_index: int,
        phase: v209_models.PromptPhase,
        state: Any,
        context: Any,
    ) -> v209.InvocationOutcome:
        events: list[str] = ["read_current_runtime_state"]
        preview_result = None
        final_envelope = None
        if phase == "final":
            if context is None or state.current_index != len(state.ordered_components):
                v209._fail(
                    "runner.final_state", "Final invoked before the actual terminal Runtime State"
                )
            preview_result = step_runtime.finalize(copy.deepcopy(state))
            prompt_core, final_envelope = v209.v188.render_final_prompt(
                context=context,
                result=preview_result,
                grammar=self._prepared.final_grammar,
            )
            current_state_id = preview_result.result_id
            candidates: tuple[str, ...] = ()
            component_key = None
            prompt_kind = "final"
        else:
            if state.current_index >= len(state.ordered_components):
                v209._fail("runner.action_state", "Action invoked after terminal Runtime State")
            public_prompt = step_runtime.render_next_prompt(state)
            prompt_core = v209.v193._action_core(public_prompt, self._prepared)
            current_state_id = public_prompt.state.state_token
            candidates = tuple(item.action_id for item in public_prompt.candidates)
            component_key = state.ordered_components[state.current_index].component_key
            prompt_kind = "correction" if phase == "correction" else "action"
        messages = v209._compile_authoritative_messages(
            phase=phase,
            prompt_core=prompt_core,
            prompt_kind=prompt_kind,
            profile=self._profile,
            prompt_contract=self._prompt_contract,
            prompt_schema=self._prompt_schema,
        )
        events.append("compile_authoritative_messages")
        request_body = v209._build_canonical_request_body(self._config, messages)
        events.append("build_canonical_request")
        messages_sha = v209_models.canonical_sha256(messages)
        body_sha = v209_models.canonical_sha256(request_body)
        prompt_id = canonical_hash(
            {
                "job_id": job.job_id,
                "invocation_index": invocation_index,
                "phase": phase,
                "current_state_id": current_state_id,
                "canonical_messages_sha256": messages_sha,
                "implementation_id": self._implementation_id,
            },
            prefix="fresh_repaired_final_continuity_executable_dynamic_prompt:",
        )
        request_id = canonical_hash(
            {
                "job_id": job.job_id,
                "invocation_index": invocation_index,
                "prompt_id": prompt_id,
                "canonical_request_body_sha256": body_sha,
            },
            prefix="fresh_repaired_final_continuity_executable_dynamic_request:",
        )
        certificate = v209._validate_request_and_certificate(
            job=job,
            invocation_index=invocation_index,
            phase=phase,
            current_state_id=current_state_id,
            candidate_action_ids=candidates,
            messages=messages,
            request_body=request_body,
            prompt_id=prompt_id,
            request_id=request_id,
            config=self._config,
            profile=self._profile,
            final_grammar_id=self._prepared.final_grammar.grammar_id,
        )
        events.append("validate_request_and_certificate")
        receipt = v209._pre_transport_receipt(certificate=certificate)
        events.append("emit_pre_transport_receipt")
        try:
            response = self._transport.send(
                v209.TransportDispatch(
                    request_body=request_body,
                    certificate=certificate,
                    receipt=receipt,
                )
            )
            events.append("injected_transport_dispatch")
            public = v209._project_public_payload(response)
            events.append("project_public_payload")
        except v209.TypedTransportFailure as error:
            if events[-1] != "injected_transport_dispatch":
                events.append("injected_transport_dispatch")
            events.append("terminal_dispatch")
            record = v209._invocation_record(
                job=job,
                invocation_index=invocation_index,
                phase=phase,
                component_key=component_key,
                current_state_id=current_state_id,
                candidate_action_ids=candidates,
                selected_action_id=None,
                prompt_id=prompt_id,
                request_id=request_id,
                certificate=certificate,
                receipt=receipt,
                messages=messages,
                request_body=request_body,
                response=None,
                exact_response_parsed=False,
                state_or_envelope_valid=False,
                runtime_completed=False,
                action_accepted=None,
                typed_terminal=error.terminal,
                event_sequence=tuple(events),
            )
            observation = cast(
                models.TypedFailureObservation,
                models.make_identity(
                    models.TypedFailureObservation,
                    {
                        "runner_binding_id": self._runner_binding_id,
                        "job_id": job.job_id,
                        "invocation_id": record.invocation_id,
                        "request_id": record.request_id,
                        "certificate_id": record.certificate_id,
                        "pre_transport_receipt_id": record.pre_transport_receipt_id,
                        "injected_transport_seam_id": record.injected_transport_seam_id,
                        "caught_exception_class": type(error).__name__,
                        "caught_terminal_kind": error.terminal,
                        "exception_reason_sha256": hashlib.sha256(
                            error.reason.encode("utf-8")
                        ).hexdigest(),
                        "invocation_record": record.model_dump(mode="json", warnings=False),
                    },
                    field="observation_id",
                    prefix="fresh_repaired_runner_owned_typed_failure_observation:",
                ),
            )
            self._observation_authority.record_from_runner(observation)
            return v209.InvocationOutcome(record=record, terminal=error.terminal)

        if phase == "final":
            try:
                v209.parse_qualified_final_response(
                    public,
                    grammar=self._prepared.final_grammar,
                    envelope=final_envelope,
                )
            except (ValidationError, ValueError):
                events.extend(("parse_exact_response", "terminal_dispatch"))
                terminal = "final_response_abi_invalid"
                record = v209._invocation_record(
                    job=job,
                    invocation_index=invocation_index,
                    phase=phase,
                    component_key=None,
                    current_state_id=current_state_id,
                    candidate_action_ids=(),
                    selected_action_id=None,
                    prompt_id=prompt_id,
                    request_id=request_id,
                    certificate=certificate,
                    receipt=receipt,
                    messages=messages,
                    request_body=request_body,
                    response=public,
                    exact_response_parsed=False,
                    state_or_envelope_valid=False,
                    runtime_completed=False,
                    action_accepted=None,
                    typed_terminal=terminal,
                    event_sequence=tuple(events),
                )
                return v209.InvocationOutcome(record=record, terminal=terminal)
            events.append("parse_exact_response")
            events.append("validate_current_state_and_candidate_or_final_envelope")
            actual_result = step_runtime.finalize(state)
            if preview_result is None or actual_result.result_id != preview_result.result_id:
                v209._fail("runner.finalize", "Final preview and actual Runtime result differ")
            events.extend(("runtime_step_or_finalize", "terminal_dispatch"))
            record = v209._invocation_record(
                job=job,
                invocation_index=invocation_index,
                phase=phase,
                component_key=None,
                current_state_id=current_state_id,
                candidate_action_ids=(),
                selected_action_id=None,
                prompt_id=prompt_id,
                request_id=request_id,
                certificate=certificate,
                receipt=receipt,
                messages=messages,
                request_body=request_body,
                response=public,
                exact_response_parsed=True,
                state_or_envelope_valid=True,
                runtime_completed=True,
                action_accepted=None,
                typed_terminal=None,
                event_sequence=tuple(events),
            )
            return v209.InvocationOutcome(record=record, final_result=actual_result)

        try:
            proposal = v209.parse_exact_canonical_action_payload(public)
        except v209.SemanticActionResponseRejection:
            events.extend(("parse_exact_response", "terminal_dispatch"))
            terminal = (
                "correction_response_abi_invalid"
                if phase == "correction"
                else "first_response_abi_invalid"
            )
            record = v209._invocation_record(
                job=job,
                invocation_index=invocation_index,
                phase=phase,
                component_key=component_key,
                current_state_id=current_state_id,
                candidate_action_ids=candidates,
                selected_action_id=None,
                prompt_id=prompt_id,
                request_id=request_id,
                certificate=certificate,
                receipt=receipt,
                messages=messages,
                request_body=request_body,
                response=public,
                exact_response_parsed=False,
                state_or_envelope_valid=False,
                runtime_completed=False,
                action_accepted=None,
                typed_terminal=terminal,
                event_sequence=tuple(events),
            )
            return v209.InvocationOutcome(record=record, terminal=terminal)
        events.append("parse_exact_response")
        if proposal.state_id != current_state_id or proposal.action_id not in candidates:
            events.extend(
                ("validate_current_state_and_candidate_or_final_envelope", "terminal_dispatch")
            )
            terminal = (
                "correction_action_reference_invalid"
                if phase == "correction"
                else "first_action_reference_invalid"
            )
            record = v209._invocation_record(
                job=job,
                invocation_index=invocation_index,
                phase=phase,
                component_key=component_key,
                current_state_id=current_state_id,
                candidate_action_ids=candidates,
                selected_action_id=proposal.action_id,
                prompt_id=prompt_id,
                request_id=request_id,
                certificate=certificate,
                receipt=receipt,
                messages=messages,
                request_body=request_body,
                response=public,
                exact_response_parsed=True,
                state_or_envelope_valid=False,
                runtime_completed=False,
                action_accepted=None,
                typed_terminal=terminal,
                event_sequence=tuple(events),
            )
            return v209.InvocationOutcome(record=record, terminal=terminal)
        events.append("validate_current_state_and_candidate_or_final_envelope")
        runtime_output = step_runtime.step(state, proposal.action_id)
        accepted = bool(getattr(runtime_output, "action_accepted", False))
        events.extend(("runtime_step_or_finalize", "terminal_dispatch"))
        record = v209._invocation_record(
            job=job,
            invocation_index=invocation_index,
            phase=phase,
            component_key=component_key,
            current_state_id=current_state_id,
            candidate_action_ids=candidates,
            selected_action_id=proposal.action_id,
            prompt_id=prompt_id,
            request_id=request_id,
            certificate=certificate,
            receipt=receipt,
            messages=messages,
            request_body=request_body,
            response=public,
            exact_response_parsed=True,
            state_or_envelope_valid=True,
            runtime_completed=True,
            action_accepted=accepted,
            typed_terminal=None,
            event_sequence=tuple(events),
        )
        return v209.InvocationOutcome(record=record, runtime_output=runtime_output)


class AuthenticatedFailureTransportFactory(v212_runtime.ProviderTransportFactory):
    """Gate-compatible zero-Provider factory for actual typed transport failures."""

    def __init__(self) -> None:
        super().__init__()
        self.failure_transports: list[v209.ScriptedTransport] = []

    def create_failure(self, error: v209.TypedTransportFailure) -> v209.ScriptedTransport:
        self.construction_count += 1
        transport = v209.ScriptedTransport()
        transport.queue(error)
        self.failure_transports.append(transport)
        return transport


class AuthenticTypedFailureDispatcher:
    """Derive the terminal from a Runner-owned observation, never from an evidence subtype."""

    def __init__(
        self,
        binding: models.AuthenticDispatcherBinding,
        authority: RunnerFailureObservationAuthority,
    ) -> None:
        self._binding = binding
        self._authority = authority
        self._policy_by_terminal = dict(
            zip(binding.terminal_kinds, binding.terminal_policy_ids, strict=True)
        )

    def dispatch(
        self, evidence: models.AuthenticatedTypedFailureEvidence
    ) -> models.DerivedTerminalDecision:
        strict = models.AuthenticatedTypedFailureEvidence.model_validate(
            evidence.model_dump(mode="python", warnings=False)
        )
        observation = self._authority.require_exact(strict.failure_observation)
        terminal = models.EXCEPTION_TO_TERMINAL.get(observation.caught_exception_class)
        record = v209_models.ExecutableInvocationRecord.model_validate(
            observation.invocation_record
        )
        if (
            terminal is None
            or terminal != observation.caught_terminal_kind
            or terminal != record.typed_terminal
            or record.job_id != strict.job_id
            or record.invocation_id != strict.invocation_id
        ):
            raise ValueError("Runner failure observation terminal provenance differs")
        return cast(
            models.DerivedTerminalDecision,
            models.make_identity(
                models.DerivedTerminalDecision,
                {
                    "dispatcher_binding_id": self._binding.binding_id,
                    "evidence_id": strict.evidence_id,
                    "observation_id": observation.observation_id,
                    "invocation_id": observation.invocation_id,
                    "job_id": observation.job_id,
                    "terminal_kind": terminal,
                    "terminal_policy_id": self._policy_by_terminal[terminal],
                    "caught_exception_class": observation.caught_exception_class,
                    "exception_reason_sha256": observation.exception_reason_sha256,
                },
                field="decision_id",
                prefix="fresh_repaired_authentic_typed_failure_terminal_decision:",
            ),
        )


def _layer_values(
    *,
    binding: models.PersistenceBinding,
    evidence: models.AuthenticatedTypedFailureEvidence,
    decision: models.DerivedTerminalDecision,
) -> tuple[tuple[str, dict[str, Any]], ...]:
    shared = {
        "persistence_binding_id": binding.binding_id,
        "job_id": evidence.job_id,
        "invocation_id": evidence.invocation_id,
        "observation_id": evidence.failure_observation.observation_id,
        "evidence_id": evidence.evidence_id,
        "decision_id": decision.decision_id,
        "terminal_kind": decision.terminal_kind,
        "formal_empirical_row": False,
        "provider_calls": 0,
        "schema_version": models.SCHEMA_VERSION,
    }
    raw = _identified(
        {
            **shared,
            "failure_observation": evidence.failure_observation.model_dump(
                mode="json", warnings=False
            ),
            "authenticated_evidence": evidence.model_dump(mode="json", warnings=False),
            "derived_terminal_decision": decision.model_dump(mode="json", warnings=False),
        },
        field="raw_id",
        prefix="fresh_repaired_authentic_typed_failure_raw:",
    )
    result = _identified(
        {**shared, "raw_id": raw["raw_id"]},
        field="result_id",
        prefix="fresh_repaired_authentic_typed_failure_result:",
    )
    trace = _identified(
        {**shared, "raw_id": raw["raw_id"], "result_id": result["result_id"]},
        field="trace_id",
        prefix="fresh_repaired_authentic_typed_failure_trace:",
    )
    outcome = _identified(
        {
            **shared,
            "raw_id": raw["raw_id"],
            "result_id": result["result_id"],
            "trace_id": trace["trace_id"],
        },
        field="outcome_id",
        prefix="fresh_repaired_authentic_typed_failure_outcome:",
    )
    checkpoint = _identified(
        {
            **shared,
            "raw_id": raw["raw_id"],
            "result_id": result["result_id"],
            "trace_id": trace["trace_id"],
            "outcome_id": outcome["outcome_id"],
        },
        field="checkpoint_id",
        prefix="fresh_repaired_authentic_typed_failure_checkpoint:",
    )
    return (
        ("raw", raw),
        ("result", result),
        ("trace", trace),
        ("outcome", outcome),
        ("checkpoint", checkpoint),
    )


class AuthenticFailurePersistencePipeline:
    """Revalidate authority and rederive the terminal before the first Raw write."""

    def __init__(
        self,
        *,
        root: Path,
        binding: models.PersistenceBinding,
        dispatcher: AuthenticTypedFailureDispatcher,
    ) -> None:
        self._root = root
        self._binding = binding
        self._dispatcher = dispatcher
        self._persisted_evidence_ids: set[str] = set()

    def persist(
        self,
        *,
        namespace: str,
        evidence: models.AuthenticatedTypedFailureEvidence,
        decision: models.DerivedTerminalDecision,
    ) -> models.PersistedEvidenceDescriptor:
        strict = models.AuthenticatedTypedFailureEvidence.model_validate(
            evidence.model_dump(mode="python", warnings=False)
        )
        expected = self._dispatcher.dispatch(strict)
        if (
            models.canonical_bytes(expected) != models.canonical_bytes(decision)
            or strict.evidence_id in self._persisted_evidence_ids
        ):
            raise ValueError("terminal decision is not derived from authentic failure observation")
        values = _layer_values(binding=self._binding, evidence=strict, decision=expected)
        safe = hashlib.sha256(strict.evidence_id.encode("utf-8")).hexdigest()
        paths: dict[str, Path] = {}
        for layer, value in values:
            path = self._root / namespace / layer / f"{safe}.json"
            v212_runtime._durable_write_no_replace(path, _encoded(value))
            if path.read_bytes() != _encoded(value):
                raise ValueError("persisted typed failure evidence bytes differ")
            paths[layer] = path
        self._persisted_evidence_ids.add(strict.evidence_id)
        by_layer = dict(values)
        return cast(
            models.PersistedEvidenceDescriptor,
            models.make_identity(
                models.PersistedEvidenceDescriptor,
                {
                    "job_id": strict.job_id,
                    "invocation_id": strict.invocation_id,
                    "observation_id": strict.failure_observation.observation_id,
                    "evidence_id": strict.evidence_id,
                    "decision_id": expected.decision_id,
                    "terminal_kind": expected.terminal_kind,
                    "raw_id": by_layer["raw"]["raw_id"],
                    "result_id": by_layer["result"]["result_id"],
                    "trace_id": by_layer["trace"]["trace_id"],
                    "outcome_id": by_layer["outcome"]["outcome_id"],
                    "checkpoint_id": by_layer["checkpoint"]["checkpoint_id"],
                    "raw_relative_path": paths["raw"].relative_to(self._root).as_posix(),
                    "result_relative_path": paths["result"].relative_to(self._root).as_posix(),
                    "trace_relative_path": paths["trace"].relative_to(self._root).as_posix(),
                    "outcome_relative_path": paths["outcome"].relative_to(self._root).as_posix(),
                    "checkpoint_relative_path": paths["checkpoint"]
                    .relative_to(self._root)
                    .as_posix(),
                    "persistence_sequence": tuple(layer for layer, _value in values),
                },
                field="descriptor_id",
                prefix="finance_v26_214_persisted_typed_failure_descriptor:",
            ),
        )


class FailureConsumerParentGuard:
    def __init__(
        self,
        *,
        consumer: models.ConsumerBinding,
        composition: models.CompositionContract,
    ) -> None:
        self._consumer = consumer
        self._composition = composition

    def admit(self, consumer: object, composition: object) -> None:
        if (
            type(consumer) is not models.ConsumerBinding
            or type(composition) is not models.CompositionContract
        ):
            raise ValueError("typed failure consumer parent type differs")
        assert isinstance(consumer, models.ConsumerBinding)
        assert isinstance(composition, models.CompositionContract)
        strict_consumer = models.ConsumerBinding.model_validate(
            consumer.model_dump(mode="python", warnings=False)
        )
        strict_composition = models.CompositionContract.model_validate(
            composition.model_dump(mode="python", warnings=False)
        )
        if (
            models.canonical_bytes(strict_consumer) != models.canonical_bytes(self._consumer)
            or models.canonical_bytes(strict_composition)
            != models.canonical_bytes(self._composition)
            or strict_composition.consumer_binding_id != strict_consumer.binding_id
            or strict_composition.runner_observation_binding_id
            != strict_consumer.runner_observation_binding_id
            or strict_composition.dispatcher_binding_id != strict_consumer.dispatcher_binding_id
            or strict_composition.persistence_binding_id != strict_consumer.persistence_binding_id
        ):
            raise ValueError("typed failure consumer parent bytes differ")


def _evidence(
    observation: models.TypedFailureObservation,
) -> models.AuthenticatedTypedFailureEvidence:
    return cast(
        models.AuthenticatedTypedFailureEvidence,
        models.make_identity(
            models.AuthenticatedTypedFailureEvidence,
            {
                "job_id": observation.job_id,
                "invocation_id": observation.invocation_id,
                "failure_observation": observation,
            },
            field="evidence_id",
            prefix="fresh_repaired_authenticated_typed_failure_evidence:",
        ),
    )


def _forged_observation(
    source: models.TypedFailureObservation,
    **updates: Any,
) -> models.TypedFailureObservation:
    values = source.model_dump(mode="python", exclude={"observation_id"}, warnings=False)
    values.update(updates)
    observation_id = canonical_hash(
        values, prefix="fresh_repaired_runner_owned_typed_failure_observation:"
    )
    return models.TypedFailureObservation.model_construct(observation_id=observation_id, **values)


def _forged_evidence(
    observation: models.TypedFailureObservation,
    *,
    job_id: str | None = None,
) -> models.AuthenticatedTypedFailureEvidence:
    values = {
        "evidence_kind": "runner_owned_typed_failure",
        "job_id": job_id or observation.job_id,
        "invocation_id": observation.invocation_id,
        "failure_observation": observation,
        "expected_terminal_input": False,
        "caller_selected_evidence_subtype": False,
        "provider_calls": 0,
        "schema_version": models.SCHEMA_VERSION,
    }
    evidence_id = canonical_hash(
        values, prefix="fresh_repaired_authenticated_typed_failure_evidence:"
    )
    return models.AuthenticatedTypedFailureEvidence.model_construct(
        evidence_id=evidence_id, **values
    )


def _forged_decision(
    *,
    binding: models.AuthenticDispatcherBinding,
    evidence: models.AuthenticatedTypedFailureEvidence,
    terminal: str,
) -> models.DerivedTerminalDecision:
    observation = evidence.failure_observation
    values = {
        "dispatcher_binding_id": binding.binding_id,
        "evidence_id": evidence.evidence_id,
        "observation_id": observation.observation_id,
        "invocation_id": observation.invocation_id,
        "job_id": evidence.job_id,
        "terminal_kind": terminal,
        "terminal_policy_id": binding.terminal_policy_ids[binding.terminal_kinds.index(terminal)],
        "caught_exception_class": observation.caught_exception_class,
        "exception_reason_sha256": observation.exception_reason_sha256,
        "derivation_rule": "authority_bound_exception_class_and_invocation_terminal_agreement",
        "terminal_label_was_input": False,
        "evidence_subtype_selected_terminal": False,
        "provider_calls": 0,
        "schema_version": models.SCHEMA_VERSION,
    }
    decision_id = canonical_hash(
        values, prefix="fresh_repaired_authentic_typed_failure_terminal_decision:"
    )
    return models.DerivedTerminalDecision.model_construct(decision_id=decision_id, **values)


def _negative_control(
    name: str,
    reason: str,
    layer_ids: tuple[str, ...],
) -> models.NegativeControl:
    return cast(
        models.NegativeControl,
        models.make_identity(
            models.NegativeControl,
            {
                "control_name": name,
                "fully_rehashed_downstream_layer_ids": layer_ids,
                "rejection_reason_sha256": hashlib.sha256(reason.encode("utf-8")).hexdigest(),
            },
            field="control_id",
            prefix="finance_v26_214_typed_failure_provenance_control:",
        ),
    )


def _run_negative_controls(
    *,
    root: Path,
    binding: models.PersistenceBinding,
    dispatcher_binding: models.AuthenticDispatcherBinding,
    dispatcher: AuthenticTypedFailureDispatcher,
    controls: tuple[models.FailureTerminalControl, ...],
) -> models.NegativeControlAudit:
    by_terminal = {item.expected_terminal: item for item in controls}
    instrument = by_terminal["instrument_failure"].failure_observation
    provider_identity = by_terminal["provider_identity_failure"].failure_observation
    provider_transport = by_terminal["provider_transport_failure"].failure_observation
    cases: list[
        tuple[str, models.AuthenticatedTypedFailureEvidence, models.DerivedTerminalDecision]
    ] = []

    instrument_as_identity = _forged_observation(
        instrument,
        caught_exception_class="ProviderIdentityError",
        caught_terminal_kind="provider_identity_failure",
    )
    first_evidence = _forged_evidence(instrument_as_identity)
    cases.append(
        (
            "instrument_record_as_provider_identity",
            first_evidence,
            _forged_decision(
                binding=dispatcher_binding,
                evidence=first_evidence,
                terminal="provider_identity_failure",
            ),
        )
    )

    identity_as_transport = _forged_observation(
        provider_identity,
        caught_exception_class="ProviderTransportError",
        caught_terminal_kind="provider_transport_failure",
    )
    second_evidence = _forged_evidence(identity_as_transport)
    cases.append(
        (
            "provider_identity_record_as_transport",
            second_evidence,
            _forged_decision(
                binding=dispatcher_binding,
                evidence=second_evidence,
                terminal="provider_transport_failure",
            ),
        )
    )

    reason_replaced = _forged_observation(
        provider_transport,
        exception_reason_sha256=hashlib.sha256(b"fully rehashed forged reason").hexdigest(),
    )
    third_evidence = _forged_evidence(reason_replaced)
    cases.append(
        (
            "exception_reason_hash_replaced",
            third_evidence,
            _forged_decision(
                binding=dispatcher_binding,
                evidence=third_evidence,
                terminal="provider_transport_failure",
            ),
        )
    )

    target_job = controls[0].failure_observation.job_id
    cross_job = _forged_observation(provider_transport, job_id=target_job)
    fourth_evidence = _forged_evidence(cross_job, job_id=target_job)
    cases.append(
        (
            "cross_job_failure_observation_substituted",
            fourth_evidence,
            _forged_decision(
                binding=dispatcher_binding,
                evidence=fourth_evidence,
                terminal="provider_transport_failure",
            ),
        )
    )

    attack_root = root / "negative_controls"
    pipeline = AuthenticFailurePersistencePipeline(
        root=attack_root, binding=binding, dispatcher=dispatcher
    )
    results: list[models.NegativeControl] = []
    for name, evidence, decision in cases:
        layer_ids = tuple(
            cast(str, value[f"{layer}_id"])
            for layer, value in _layer_values(binding=binding, evidence=evidence, decision=decision)
        )
        try:
            pipeline.persist(
                namespace=name,
                evidence=evidence,
                decision=decision,
            )
        except ValueError as error:
            results.append(_negative_control(name, str(error), layer_ids))
        else:
            raise ValueError(f"typed failure provenance attack was admitted:{name}")
    if attack_root.exists() and any(path.is_file() for path in attack_root.rglob("*")):
        raise ValueError("typed failure provenance attack wrote Raw evidence")
    return cast(
        models.NegativeControlAudit,
        models.make_identity(
            models.NegativeControlAudit,
            {"controls": tuple(results)},
            field="audit_id",
            prefix="finance_v26_214_typed_failure_provenance_negative_control_audit:",
        ),
    )


@dataclass(frozen=True)
class PreflightExecution:
    consumption_receipt: v212_models.PreflightConsumptionReceipt
    run_start_receipt: v212_models.PreflightRunStartReceipt
    execution_audit: models.FailureExecutionAudit
    negative_audit: models.NegativeControlAudit


class FailureTerminalizingConsumer:
    """One entry that catches, authenticates, dispatches, and persists actual failures."""

    def __init__(
        self,
        *,
        binding: models.ConsumerBinding,
        composition: models.CompositionContract,
        runner_binding: models.RunnerObservationBinding,
        dispatcher_binding: models.AuthenticDispatcherBinding,
        persistence_binding: models.PersistenceBinding,
        consumption_contract: v212_models.AuthorizationConsumptionReceiptContract,
        run_start_contract: v212_models.RunStartReceiptContract,
        authorization: v211_models.ExactOnlineExecutionAuthorization,
        authorization_bytes: bytes,
    ) -> None:
        self._binding = binding
        self._composition = composition
        self._runner_binding = runner_binding
        self._dispatcher_binding = dispatcher_binding
        self._persistence_binding = persistence_binding
        self._consumption_contract = consumption_contract
        self._run_start_contract = run_start_contract
        self._authorization = authorization
        self._authorization_bytes = authorization_bytes
        self._guard = FailureConsumerParentGuard(consumer=binding, composition=composition)

    def execute_preflight(
        self,
        *,
        root: Path,
        manifest: v209_models.ExecutableDevelopmentManifest,
        implementation: v209_models.ImplementationBinding,
        parents: Any,
        prepared: Any,
        config: AgentModelConfig,
    ) -> PreflightExecution:
        self._guard.admit(self._binding, self._composition)
        durable_consumer = v212_runtime.DurableAuthorizationConsumer(
            contract=self._consumption_contract,
            consumer_binding_id=self._binding.binding_id,
            expected_authorization=self._authorization,
            expected_authorization_file_bytes=self._authorization_bytes,
        )
        consumption = durable_consumer.consume_preflight_lease(root / "consumer_ingress")
        run_writer = v212_runtime.DurableRunStartReceiptWriter(
            contract=self._run_start_contract,
            consumer_binding_id=self._binding.binding_id,
            manifest_id=manifest.manifest_id,
            exact_job_set_sha256=models.canonical_sha256(manifest.expected_job_ids),
        )
        run_start = run_writer.write(root / "consumer_ingress", consumption)
        boundary_count = 0

        def boundary_probe() -> None:
            nonlocal boundary_count
            boundary_count += 1

        authority = RunnerFailureObservationAuthority()
        dispatcher = AuthenticTypedFailureDispatcher(self._dispatcher_binding, authority)

        def writer_builder() -> AuthenticFailurePersistencePipeline:
            return AuthenticFailurePersistencePipeline(
                root=root,
                binding=self._persistence_binding,
                dispatcher=dispatcher,
            )

        products = v212_runtime.CredentialBoundFactoryGate().open(
            root=root / "consumer_ingress",
            consumption=consumption,
            run_start=run_start,
            credential_boundary_probe=boundary_probe,
            transport_factory_builder=AuthenticatedFailureTransportFactory,
            writer_factory_builder=writer_builder,
        )
        factory = cast(AuthenticatedFailureTransportFactory, products.transport_factory)
        pipeline = cast(AuthenticFailurePersistencePipeline, products.writer_factory_marker)
        if boundary_count != 1 or not isinstance(pipeline, AuthenticFailurePersistencePipeline):
            raise ValueError("typed failure consumer factory order differs")

        terminal_controls: list[models.FailureTerminalControl] = []
        jobs = tuple(sorted(manifest.jobs, key=lambda item: item.job_id)[:8])
        for job, error_type, expected in zip(
            jobs, OUTER_ERROR_TYPES, models.OUTER_TERMINAL_KINDS, strict=True
        ):
            context = v209._context_for_job(job=job, parents=parents, prepared=prepared)
            state = frozen_runtime._initialize(context)
            error = error_type()
            transport = factory.create_failure(error)
            runner = ObservationAuthenticFullConditionRunner(
                observation_authority=authority,
                runner_binding_id=self._runner_binding.binding_id,
                transport=transport,
                config=config,
                profile=parents.profile,
                prepared=prepared,
                implementation_id=implementation.implementation_id,
                prompt_contract=parents.prompt_contract,
                prompt_schema=parents.prompt_schema,
            )
            outcome = runner.invoke_action(job=job, invocation_index=0, state=state)
            if outcome.terminal is None:
                raise ValueError("actual Runner typed failure did not enter terminal branch")
            observation = authority.get(outcome.record.invocation_id)
            evidence = _evidence(observation)
            decision = dispatcher.dispatch(evidence)
            descriptor = pipeline.persist(
                namespace="typed_failure_controls",
                evidence=evidence,
                decision=decision,
            )
            if decision.terminal_kind != expected or outcome.terminal != expected:
                raise ValueError("actual Runner failure terminal differs")
            terminal_controls.append(
                cast(
                    models.FailureTerminalControl,
                    models.make_identity(
                        models.FailureTerminalControl,
                        {
                            "expected_terminal": expected,
                            "failure_observation": observation,
                            "evidence": evidence,
                            "decision": decision,
                            "persistence": descriptor,
                        },
                        field="control_id",
                        prefix="finance_v26_214_typed_failure_terminal_control:",
                    ),
                )
            )
        controls = tuple(terminal_controls)
        if (
            authority.count != 8
            or factory.construction_count != 8
            or len(factory.failure_transports) != 8
            or sum(len(item.dispatches) for item in factory.failure_transports) != 8
        ):
            raise ValueError("typed failure single-consumer execution geometry differs")
        execution_audit = cast(
            models.FailureExecutionAudit,
            models.make_identity(
                models.FailureExecutionAudit,
                {
                    "consumer_binding_id": self._binding.binding_id,
                    "composition_contract_id": self._composition.contract_id,
                    "consumption_receipt_id": consumption.receipt_id,
                    "run_start_receipt_id": run_start.receipt_id,
                    "controls": controls,
                },
                field="audit_id",
                prefix="finance_v26_214_single_consumer_failure_execution_audit:",
            ),
        )
        negative_audit = _run_negative_controls(
            root=root,
            binding=self._persistence_binding,
            dispatcher_binding=self._dispatcher_binding,
            dispatcher=dispatcher,
            controls=controls,
        )
        return PreflightExecution(
            consumption_receipt=consumption,
            run_start_receipt=run_start,
            execution_audit=execution_audit,
            negative_audit=negative_audit,
        )
