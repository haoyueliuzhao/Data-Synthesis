# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as frozen_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_actual_typed_failure_source_totality_runtime as v215_runtime,
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
    phase1_v26_fresh_repaired_typed_failure_exit_provenance_models as models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import AgentModelConfig


def _encoded(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _identified(values: dict[str, Any], *, field: str, prefix: str) -> dict[str, Any]:
    result = dict(values)
    result[field] = canonical_hash(values, prefix=prefix)
    return result


def _exception_type_id(error: BaseException) -> str:
    value = type(error)
    return f"{value.__module__}:{value.__qualname__}"


def _reason_sha(error: v209.TypedTransportFailure) -> str:
    return hashlib.sha256(error.reason.encode("utf-8")).hexdigest()


def _dispatch_parent(dispatch: v209.TransportDispatch) -> str:
    return canonical_hash(
        {
            "request_body": dict(dispatch.request_body),
            "certificate_id": dispatch.certificate.certificate_id,
            "receipt_id": dispatch.receipt.receipt_id,
        },
        prefix="fresh_repaired_v209_typed_failure_dispatch_parent:",
    )


def _response_parent(response: Any) -> str:
    return canonical_hash(
        {"public_response_candidate": response},
        prefix="fresh_repaired_v209_typed_failure_response_parent:",
    )


class UpstreamFailureAuthority:
    """No-replace ledger binding an exact exception object to a producer observation."""

    def __init__(self) -> None:
        self._by_object: dict[int, models.UpstreamFailureObservation] = {}
        self._by_identity: dict[str, models.UpstreamFailureObservation] = {}

    def record_from_producer(
        self,
        error: v209.TypedTransportFailure,
        observation: models.UpstreamFailureObservation,
    ) -> None:
        strict = models.UpstreamFailureObservation.model_validate(
            observation.model_dump(mode="python", warnings=False)
        )
        if (
            type(error) is not v209.TypedTransportFailure
            or strict.exception_type_id != _exception_type_id(error)
            or strict.terminal_kind != error.terminal
            or strict.exception_reason_sha256 != _reason_sha(error)
            or id(error) in self._by_object
            or strict.observation_id in self._by_identity
        ):
            raise ValueError("upstream failure producer observation differs")
        self._by_object[id(error)] = strict
        self._by_identity[strict.observation_id] = strict

    def require_error(self, error: v209.TypedTransportFailure) -> models.UpstreamFailureObservation:
        observation = self._by_object.get(id(error))
        if observation is None:
            raise ValueError("queued typed failure has no upstream source authority")
        if (
            observation.exception_type_id != _exception_type_id(error)
            or observation.terminal_kind != error.terminal
            or observation.exception_reason_sha256 != _reason_sha(error)
        ):
            raise ValueError("queued typed failure differs from upstream source authority")
        return observation

    def require_identity(self, observation_id: str) -> models.UpstreamFailureObservation:
        try:
            return self._by_identity[observation_id]
        except KeyError as error:
            raise ValueError("upstream failure observation identity is absent") from error

    @property
    def count(self) -> int:
        return len(self._by_identity)


class AuthoritativeUpstreamFailureProducer:
    def __init__(
        self,
        *,
        binding: models.UpstreamFailureProducerBinding,
        authority: UpstreamFailureAuthority,
    ) -> None:
        self._binding = binding
        self._authority = authority
        self._policy_by_terminal = dict(binding.terminal_policy_items)

    def create_failure(
        self,
        *,
        terminal_kind: str,
        reason: str,
        source_event_id: str,
    ) -> v209.TypedTransportFailure:
        terminal_policy_id = self._policy_by_terminal.get(terminal_kind)
        if terminal_policy_id is None:
            raise ValueError("upstream typed failure terminal is outside the v26.195 Registry")
        error = v209.TypedTransportFailure(terminal_kind, reason)
        observation = cast(
            models.UpstreamFailureObservation,
            models.make_identity(
                models.UpstreamFailureObservation,
                {
                    "producer_binding_id": self._binding.binding_id,
                    "source_event_id": source_event_id,
                    "exception_type_id": _exception_type_id(error),
                    "terminal_kind": terminal_kind,
                    "exception_reason_sha256": _reason_sha(error),
                    "terminal_policy_id": terminal_policy_id,
                },
                field="observation_id",
                prefix="fresh_repaired_upstream_typed_failure_observation:",
            ),
        )
        self._authority.record_from_producer(error, observation)
        return error


class SourceExitProofAuthority:
    """Authenticates exact v26.209 direct exits and authority-backed rethrows."""

    def __init__(
        self,
        *,
        contract: models.TypedFailureExitSurfaceContract,
        upstream_authority: UpstreamFailureAuthority,
    ) -> None:
        self._contract = contract
        self._upstream = upstream_authority
        self._declaration_by_code: dict[str, models.SourceExitDeclaration] = {
            item.exit_code: item for item in contract.exits
        }
        self._by_object: dict[int, models.SourceExitProof] = {}

    def _record(
        self,
        *,
        error: v209.TypedTransportFailure,
        exit_code: str,
        parent_id: str,
        upstream_observation: models.UpstreamFailureObservation | None,
    ) -> models.SourceExitProof:
        try:
            declaration = self._declaration_by_code[exit_code]
        except KeyError as missing:
            raise ValueError("typed failure source exit is outside the AST Contract") from missing
        if type(error) is not v209.TypedTransportFailure:
            raise ValueError("typed failure exact class differs from source exit Contract")
        reason_sha = _reason_sha(error)
        if declaration.source_exit_kind == "direct_constructor":
            if (
                upstream_observation is not None
                or declaration.direct_terminal_kind != error.terminal
                or declaration.direct_reason_sha256 != reason_sha
            ):
                raise ValueError("direct typed failure differs from exact constructor exit")
        else:
            if upstream_observation is None:
                raise ValueError("queued typed failure rethrow lacks upstream authority")
            if (
                upstream_observation.exception_type_id != _exception_type_id(error)
                or upstream_observation.terminal_kind != error.terminal
                or upstream_observation.exception_reason_sha256 != reason_sha
            ):
                raise ValueError("authenticated rethrow differs from upstream observation")
        proof = cast(
            models.SourceExitProof,
            models.make_identity(
                models.SourceExitProof,
                {
                    "source_contract_id": self._contract.contract_id,
                    "source_symbol_id": declaration.source_symbol_id,
                    "source_exit_id": declaration.source_exit_id,
                    "exit_code": declaration.exit_code,
                    "source_exit_kind": declaration.source_exit_kind,
                    "failure_origin": declaration.failure_origin,
                    "exception_type_id": _exception_type_id(error),
                    "terminal_kind": error.terminal,
                    "exception_reason_sha256": reason_sha,
                    "dispatch_or_response_parent_id": parent_id,
                    "upstream_failure_observation_id": (
                        upstream_observation.observation_id
                        if upstream_observation is not None
                        else None
                    ),
                },
                field="proof_id",
                prefix="fresh_repaired_v209_typed_failure_source_exit_proof:",
            ),
        )
        if id(error) in self._by_object:
            raise ValueError("typed failure source exit proof already exists")
        self._by_object[id(error)] = proof
        return proof

    def record_transport_exit(
        self,
        *,
        error: v209.TypedTransportFailure,
        exit_code: str,
        dispatch: v209.TransportDispatch,
    ) -> models.SourceExitProof:
        if type(error) is not v209.TypedTransportFailure:
            raise ValueError("typed failure exact class differs before rethrow authority lookup")
        upstream = (
            self._upstream.require_error(error) if exit_code == "E2_authenticated_rethrow" else None
        )
        return self._record(
            error=error,
            exit_code=exit_code,
            parent_id=_dispatch_parent(dispatch),
            upstream_observation=upstream,
        )

    def record_projection_exit(
        self, *, error: v209.TypedTransportFailure, response: Any
    ) -> models.SourceExitProof:
        reason_sha = _reason_sha(error)
        reasoning = self._declaration_by_code["E3_reasoning_key"]
        non_object = self._declaration_by_code["E4_non_object"]
        if (
            error.terminal == reasoning.direct_terminal_kind
            and reason_sha == reasoning.direct_reason_sha256
            and _contains_reasoning_key(response)
        ):
            exit_code = reasoning.exit_code
        elif (
            error.terminal == non_object.direct_terminal_kind
            and reason_sha == non_object.direct_reason_sha256
            and not isinstance(json.loads(models.canonical_bytes(response)), dict)
        ):
            exit_code = non_object.exit_code
        else:
            raise ValueError("public projection failure does not match an exact source exit")
        return self._record(
            error=error,
            exit_code=exit_code,
            parent_id=_response_parent(response),
            upstream_observation=None,
        )

    def require_for_runner(self, error: v209.TypedTransportFailure) -> models.SourceExitProof:
        proof = self._by_object.get(id(error))
        if proof is None:
            raise ValueError("Runner catch has no exact source exit proof")
        return models.SourceExitProof.model_validate(
            proof.model_dump(mode="python", warnings=False)
        )


def _contains_reasoning_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            "reasoning" in str(key).casefold() or _contains_reasoning_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_reasoning_key(item) for item in value)
    return False


class ExitTracingScriptedTransport(v209.ScriptedTransport):
    """Calls the exact v26.209 send and authenticates every typed-failure exit."""

    def __init__(
        self,
        *,
        source_exit_authority: SourceExitProofAuthority,
        invalid_dispatch_chain: bool = False,
    ) -> None:
        super().__init__()
        self._source_exit_authority = source_exit_authority
        self._invalid_dispatch_chain = invalid_dispatch_chain
        self.last_response: Any = None

    def send(self, dispatch: v209.TransportDispatch) -> Any:
        effective = dispatch
        if self._invalid_dispatch_chain:
            changed = dict(dispatch.request_body)
            changed["v26_216_invalid_dispatch_chain"] = True
            effective = v209.TransportDispatch(
                request_body=changed,
                certificate=dispatch.certificate,
                receipt=dispatch.receipt,
            )
            exit_code = "E0_invalid_dispatch_chain"
        elif not self._queue:
            exit_code = "E1_empty_queue"
        elif isinstance(self._queue[0], v209.TypedTransportFailure):
            exit_code = "E2_authenticated_rethrow"
        else:
            exit_code = ""
        try:
            response = super().send(effective)
        except v209.TypedTransportFailure as error:
            if not exit_code:
                raise ValueError("unexpected v26.209 typed-failure exit") from error
            self._source_exit_authority.record_transport_exit(
                error=error, exit_code=exit_code, dispatch=effective
            )
            raise
        self.last_response = response
        return response


class ExitProvenanceTransportFactory(v212_runtime.ProviderTransportFactory):
    def __init__(
        self,
        *,
        source_exit_authority: SourceExitProofAuthority,
        producer: AuthoritativeUpstreamFailureProducer,
        policy_by_terminal: dict[str, str],
    ) -> None:
        super().__init__()
        self._source_exit_authority = source_exit_authority
        self._producer = producer
        self._policy_by_terminal = policy_by_terminal

    def _new(self, *, invalid: bool = False) -> ExitTracingScriptedTransport:
        self.construction_count += 1
        return ExitTracingScriptedTransport(
            source_exit_authority=self._source_exit_authority,
            invalid_dispatch_chain=invalid,
        )

    def create_for_control(self, control_name: str) -> ExitTracingScriptedTransport:
        if control_name == "transport_invalid_dispatch_chain":
            return self._new(invalid=True)
        transport = self._new()
        if control_name == "projection_reasoning_key":
            transport.queue({"reasoning_content": "must remain private"})
        elif control_name == "projection_non_object":
            transport.queue(cast(Any, ("not", "a", "json", "object")))
        elif control_name == "transport_authenticated_rethrow":
            source_event_id = canonical_hash(
                {"control": control_name},
                prefix="finance_v26_216_upstream_failure_source_event:",
            )
            error = self._producer.create_failure(
                terminal_kind="instrument_failure",
                reason="authenticated upstream instrument failure",
                source_event_id=source_event_id,
            )
            transport.queue(error)
        elif control_name != "transport_empty_queue":
            raise ValueError(f"unknown exit-surface control:{control_name}")
        return transport

    def create_untrusted(self, error: v209.TypedTransportFailure) -> ExitTracingScriptedTransport:
        transport = self._new()
        transport.queue(error)
        return transport


class RunnerFailureObservationAuthority:
    def __init__(self) -> None:
        self._by_invocation: dict[str, models.TypedFailureObservation] = {}

    def record_from_runner(self, observation: models.TypedFailureObservation) -> None:
        strict = models.TypedFailureObservation.model_validate(
            observation.model_dump(mode="python", warnings=False)
        )
        if strict.invocation_id in self._by_invocation:
            raise ValueError("Runner observation invocation already exists")
        self._by_invocation[strict.invocation_id] = strict

    def require_exact(
        self, observation: models.TypedFailureObservation
    ) -> models.TypedFailureObservation:
        strict = models.TypedFailureObservation.model_validate(
            observation.model_dump(mode="python", warnings=False)
        )
        actual = self._by_invocation.get(strict.invocation_id)
        if actual is None or models.canonical_bytes(actual) != models.canonical_bytes(strict):
            raise ValueError("candidate observation differs from Runner-owned authority")
        return actual

    def get(self, invocation_id: str) -> models.TypedFailureObservation:
        try:
            return self._by_invocation[invocation_id]
        except KeyError as error:
            raise ValueError("Runner-owned observation is absent") from error

    @property
    def count(self) -> int:
        return len(self._by_invocation)


class ExitProvenanceRunner(v215_runtime.ActualSourceAuthenticRunner):
    """Inherits the separated catches and requires an exact source-exit proof."""

    def __init__(
        self,
        *,
        source_exit_authority: SourceExitProofAuthority,
        observation_authority: RunnerFailureObservationAuthority,
        runner_binding_id: str,
        source_contract_id: str,
        **kwargs: Any,
    ) -> None:
        v209.FinalContinuityRepairedFullConditionRunner.__init__(self, **kwargs)
        self._source_exit_authority = source_exit_authority
        self._observation_authority = observation_authority
        self._runner_binding_id = runner_binding_id
        self._source_contract_id = source_contract_id

    def _terminalize_actual_failure(
        self,
        *,
        error: v209.TypedTransportFailure,
        failure_origin: str,
        events: list[str],
        job: v209_models.ExecutableDevelopmentJob,
        invocation_index: int,
        phase: v209_models.PromptPhase,
        component_key: str | None,
        current_state_id: str,
        candidates: tuple[str, ...],
        prompt_id: str,
        request_id: str,
        certificate: v209_models.ValidatedRequestCertificate,
        receipt: v209_models.PreTransportReceipt,
        messages: tuple[dict[str, str], ...],
        request_body: dict[str, Any],
    ) -> v209.InvocationOutcome:
        if failure_origin == "public_projection":
            if not isinstance(self._transport, ExitTracingScriptedTransport):
                raise ValueError("projection failure transport does not expose response parent")
            self._source_exit_authority.record_projection_exit(
                error=error, response=self._transport.last_response
            )
        proof = self._source_exit_authority.require_for_runner(error)
        if proof.failure_origin != failure_origin:
            raise ValueError("Runner catch origin differs from source exit proof")
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
                    "source_contract_id": self._source_contract_id,
                    "job_id": job.job_id,
                    "invocation_id": record.invocation_id,
                    "request_id": record.request_id,
                    "certificate_id": record.certificate_id,
                    "pre_transport_receipt_id": record.pre_transport_receipt_id,
                    "injected_transport_seam_id": record.injected_transport_seam_id,
                    "source_exit_proof": proof,
                    "exception_type_id": _exception_type_id(error),
                    "caught_terminal_kind": error.terminal,
                    "exception_reason_sha256": _reason_sha(error),
                    "invocation_record": record.model_dump(mode="json", warnings=False),
                },
                field="observation_id",
                prefix="fresh_repaired_exit_provenance_typed_failure_observation:",
            ),
        )
        self._observation_authority.record_from_runner(observation)
        return v209.InvocationOutcome(record=record, terminal=error.terminal)


class ExitProvenanceDispatcher:
    def __init__(
        self,
        *,
        binding: models.DispatcherBinding,
        source_contract: models.TypedFailureExitSurfaceContract,
        runner_authority: RunnerFailureObservationAuthority,
        upstream_authority: UpstreamFailureAuthority,
    ) -> None:
        self._binding = binding
        self._contract = source_contract
        self._runner_authority = runner_authority
        self._upstream_authority = upstream_authority
        self._declaration_by_id = {item.source_exit_id: item for item in source_contract.exits}
        self._policy_by_terminal = dict(binding.terminal_policy_items)

    def dispatch(
        self, evidence: models.AuthenticatedTypedFailureEvidence
    ) -> models.DerivedTerminalDecision:
        strict = models.AuthenticatedTypedFailureEvidence.model_validate(
            evidence.model_dump(mode="python", warnings=False)
        )
        observation = self._runner_authority.require_exact(strict.failure_observation)
        proof = models.SourceExitProof.model_validate(
            observation.source_exit_proof.model_dump(mode="python", warnings=False)
        )
        declaration = self._declaration_by_id.get(proof.source_exit_id)
        if declaration is None or declaration.source_symbol_id != proof.source_symbol_id:
            raise ValueError("source exit proof is outside the exact AST Contract")
        if declaration.source_exit_kind == "direct_constructor":
            if (
                proof.upstream_failure_observation_id is not None
                or declaration.direct_terminal_kind != proof.terminal_kind
                or declaration.direct_reason_sha256 != proof.exception_reason_sha256
            ):
                raise ValueError("direct source exit proof differs from declaration")
        else:
            if proof.upstream_failure_observation_id is None:
                raise ValueError("rethrow source exit proof lacks upstream authority")
            upstream = self._upstream_authority.require_identity(
                proof.upstream_failure_observation_id
            )
            if (
                upstream.exception_type_id != proof.exception_type_id
                or upstream.terminal_kind != proof.terminal_kind
                or upstream.exception_reason_sha256 != proof.exception_reason_sha256
                or upstream.terminal_policy_id != self._policy_by_terminal.get(proof.terminal_kind)
            ):
                raise ValueError("rethrow source exit proof differs from upstream observation")
        if proof.terminal_kind not in self._policy_by_terminal:
            raise ValueError("source exit terminal is outside the v26.195 Registry")
        return cast(
            models.DerivedTerminalDecision,
            models.make_identity(
                models.DerivedTerminalDecision,
                {
                    "dispatcher_binding_id": self._binding.binding_id,
                    "source_contract_id": self._contract.contract_id,
                    "evidence_id": strict.evidence_id,
                    "observation_id": observation.observation_id,
                    "source_exit_id": proof.source_exit_id,
                    "source_exit_kind": proof.source_exit_kind,
                    "upstream_failure_observation_id": proof.upstream_failure_observation_id,
                    "invocation_id": observation.invocation_id,
                    "job_id": observation.job_id,
                    "terminal_kind": proof.terminal_kind,
                    "terminal_policy_id": self._policy_by_terminal[proof.terminal_kind],
                    "exception_reason_sha256": proof.exception_reason_sha256,
                },
                field="decision_id",
                prefix="fresh_repaired_exit_provenance_terminal_decision:",
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
        "source_exit_id": evidence.failure_observation.source_exit_proof.source_exit_id,
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
        prefix="fresh_repaired_exit_provenance_raw:",
    )
    result = _identified(
        {**shared, "raw_id": raw["raw_id"]},
        field="result_id",
        prefix="fresh_repaired_exit_provenance_result:",
    )
    trace = _identified(
        {**shared, "raw_id": raw["raw_id"], "result_id": result["result_id"]},
        field="trace_id",
        prefix="fresh_repaired_exit_provenance_trace:",
    )
    outcome = _identified(
        {
            **shared,
            "raw_id": raw["raw_id"],
            "result_id": result["result_id"],
            "trace_id": trace["trace_id"],
        },
        field="outcome_id",
        prefix="fresh_repaired_exit_provenance_outcome:",
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
        prefix="fresh_repaired_exit_provenance_checkpoint:",
    )
    return (
        ("raw", raw),
        ("result", result),
        ("trace", trace),
        ("outcome", outcome),
        ("checkpoint", checkpoint),
    )


class ExitProvenancePersistencePipeline:
    def __init__(
        self,
        *,
        root: Path,
        binding: models.PersistenceBinding,
        dispatcher: ExitProvenanceDispatcher,
    ) -> None:
        self._root = root
        self._binding = binding
        self._dispatcher = dispatcher
        self._persisted: set[str] = set()

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
            or strict.evidence_id in self._persisted
        ):
            raise ValueError("exit-provenance terminal decision differs before Raw")
        values = _layer_values(binding=self._binding, evidence=strict, decision=expected)
        safe = hashlib.sha256(strict.evidence_id.encode("utf-8")).hexdigest()
        paths: dict[str, Path] = {}
        for layer, value in values:
            path = self._root / namespace / layer / f"{safe}.json"
            v212_runtime._durable_write_no_replace(path, _encoded(value))
            if path.read_bytes() != _encoded(value):
                raise ValueError("exit-provenance persisted bytes differ")
            paths[layer] = path
        self._persisted.add(strict.evidence_id)
        by_layer = dict(values)
        return cast(
            models.PersistedEvidenceDescriptor,
            models.make_identity(
                models.PersistedEvidenceDescriptor,
                {
                    "job_id": strict.job_id,
                    "invocation_id": strict.invocation_id,
                    "observation_id": strict.failure_observation.observation_id,
                    "source_exit_id": strict.failure_observation.source_exit_proof.source_exit_id,
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
                prefix="finance_v26_216_exit_provenance_persisted_descriptor:",
            ),
        )


class ConsumerParentGuard:
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
            raise ValueError("exit-provenance consumer parent type differs")
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
            raise ValueError("exit-provenance consumer parent bytes differ")


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
            prefix="fresh_repaired_exit_provenance_authenticated_typed_failure_evidence:",
        ),
    )


def _forged_observation(
    source: models.TypedFailureObservation, **updates: Any
) -> models.TypedFailureObservation:
    values = source.model_dump(mode="python", exclude={"observation_id"}, warnings=False)
    values["source_exit_proof"] = models.SourceExitProof.model_validate(values["source_exit_proof"])
    values.update(updates)
    observation_id = canonical_hash(
        values, prefix="fresh_repaired_exit_provenance_typed_failure_observation:"
    )
    return models.TypedFailureObservation.model_construct(observation_id=observation_id, **values)


def _forged_evidence(
    observation: models.TypedFailureObservation, *, job_id: str | None = None
) -> models.AuthenticatedTypedFailureEvidence:
    values = {
        "evidence_kind": "runner_owned_source_exit_typed_failure",
        "job_id": job_id or observation.job_id,
        "invocation_id": observation.invocation_id,
        "failure_observation": observation,
        "expected_terminal_input": False,
        "caller_selected_source_exit": False,
        "provider_calls": 0,
        "schema_version": models.SCHEMA_VERSION,
    }
    evidence_id = canonical_hash(
        values,
        prefix="fresh_repaired_exit_provenance_authenticated_typed_failure_evidence:",
    )
    return models.AuthenticatedTypedFailureEvidence.model_construct(
        evidence_id=evidence_id, **values
    )


def _forged_decision(
    *,
    binding: models.DispatcherBinding,
    contract: models.TypedFailureExitSurfaceContract,
    evidence: models.AuthenticatedTypedFailureEvidence,
    terminal: str,
) -> models.DerivedTerminalDecision:
    observation = evidence.failure_observation
    proof = observation.source_exit_proof
    policy_by_terminal = dict(binding.terminal_policy_items)
    values = {
        "dispatcher_binding_id": binding.binding_id,
        "source_contract_id": contract.contract_id,
        "evidence_id": evidence.evidence_id,
        "observation_id": observation.observation_id,
        "source_exit_id": proof.source_exit_id,
        "source_exit_kind": proof.source_exit_kind,
        "upstream_failure_observation_id": proof.upstream_failure_observation_id,
        "invocation_id": observation.invocation_id,
        "job_id": evidence.job_id,
        "terminal_kind": terminal,
        "terminal_policy_id": policy_by_terminal.get(
            terminal, canonical_hash(terminal, prefix="forged_terminal_policy:")
        ),
        "exception_reason_sha256": observation.exception_reason_sha256,
        "derivation_rule": "source_exit_proof_upstream_authority_record_and_registry_agreement",
        "terminal_label_was_input": False,
        "provider_calls": 0,
        "schema_version": models.SCHEMA_VERSION,
    }
    decision_id = canonical_hash(values, prefix="fresh_repaired_exit_provenance_terminal_decision:")
    return models.DerivedTerminalDecision.model_construct(decision_id=decision_id, **values)


def _negative_control(
    *,
    name: str,
    stage: str,
    reason: str,
    layer_ids: tuple[str, ...] = (),
) -> models.NegativeControl:
    return cast(
        models.NegativeControl,
        models.make_identity(
            models.NegativeControl,
            {
                "control_name": name,
                "rejection_stage": stage,
                "rejected_before_runner_authority_append": stage == "source_exit_admission",
                "fully_rehashed": bool(layer_ids),
                "fully_rehashed_downstream_layer_ids": layer_ids,
                "rejection_reason_sha256": hashlib.sha256(reason.encode("utf-8")).hexdigest(),
            },
            field="control_id",
            prefix="finance_v26_216_exit_provenance_negative_control:",
        ),
    )


def _retained_authority_attacks(
    *,
    root: Path,
    binding: models.PersistenceBinding,
    dispatcher_binding: models.DispatcherBinding,
    contract: models.TypedFailureExitSurfaceContract,
    dispatcher: ExitProvenanceDispatcher,
    controls: tuple[models.ExitSurfaceControl, ...],
) -> tuple[models.NegativeControl, ...]:
    by_name = {item.control_name: item for item in controls}
    instrument = by_name["transport_empty_queue"].failure_observation
    privacy = by_name["projection_reasoning_key"].failure_observation
    cases: list[
        tuple[str, models.AuthenticatedTypedFailureEvidence, models.DerivedTerminalDecision]
    ] = []
    instrument_changed = _forged_observation(
        instrument, caught_terminal_kind="provider_identity_failure"
    )
    evidence_one = _forged_evidence(instrument_changed)
    cases.append(
        (
            "instrument_observation_reclassified_as_provider_identity",
            evidence_one,
            _forged_decision(
                binding=dispatcher_binding,
                contract=contract,
                evidence=evidence_one,
                terminal="provider_identity_failure",
            ),
        )
    )
    privacy_changed = _forged_observation(
        privacy, caught_terminal_kind="provider_transport_failure"
    )
    evidence_two = _forged_evidence(privacy_changed)
    cases.append(
        (
            "privacy_observation_reclassified_as_transport",
            evidence_two,
            _forged_decision(
                binding=dispatcher_binding,
                contract=contract,
                evidence=evidence_two,
                terminal="provider_transport_failure",
            ),
        )
    )
    reason_changed = _forged_observation(
        privacy,
        exception_reason_sha256=hashlib.sha256(b"fully rehashed false reason").hexdigest(),
    )
    evidence_three = _forged_evidence(reason_changed)
    cases.append(
        (
            "exception_reason_hash_replaced",
            evidence_three,
            _forged_decision(
                binding=dispatcher_binding,
                contract=contract,
                evidence=evidence_three,
                terminal="privacy_rejection",
            ),
        )
    )
    target_job = controls[0].failure_observation.job_id
    cross_job = _forged_observation(privacy, job_id=target_job)
    evidence_four = _forged_evidence(cross_job, job_id=target_job)
    cases.append(
        (
            "cross_job_failure_observation_substituted",
            evidence_four,
            _forged_decision(
                binding=dispatcher_binding,
                contract=contract,
                evidence=evidence_four,
                terminal="privacy_rejection",
            ),
        )
    )
    attack_root = root / "negative_controls"
    pipeline = ExitProvenancePersistencePipeline(
        root=attack_root, binding=binding, dispatcher=dispatcher
    )
    results: list[models.NegativeControl] = []
    for name, evidence, decision in cases:
        layer_ids = tuple(
            cast(str, value[f"{layer}_id"])
            for layer, value in _layer_values(binding=binding, evidence=evidence, decision=decision)
        )
        try:
            pipeline.persist(namespace=name, evidence=evidence, decision=decision)
        except ValueError as error:
            results.append(
                _negative_control(
                    name=name,
                    stage="persistence_pre_raw",
                    reason=str(error),
                    layer_ids=layer_ids,
                )
            )
        else:
            raise ValueError(f"retained authority attack was admitted:{name}")
    if attack_root.exists() and any(path.is_file() for path in attack_root.rglob("*")):
        raise ValueError("retained authority attack wrote Raw evidence")
    return tuple(results)


SpoofedTypedTransportFailure = type(
    "TypedTransportFailure",
    (v209.TypedTransportFailure,),
    {"__module__": __name__},
)


@dataclass(frozen=True)
class PreflightExecution:
    consumption_receipt: v212_models.PreflightConsumptionReceipt
    run_start_receipt: v212_models.PreflightRunStartReceipt
    execution_audit: models.ExitSurfaceExecutionAudit
    negative_audit: models.NegativeControlAudit


class ExitProvenanceFailureConsumer:
    def __init__(
        self,
        *,
        binding: models.ConsumerBinding,
        composition: models.CompositionContract,
        source_contract: models.TypedFailureExitSurfaceContract,
        producer_binding: models.UpstreamFailureProducerBinding,
        runner_binding: models.RunnerObservationBinding,
        dispatcher_binding: models.DispatcherBinding,
        persistence_binding: models.PersistenceBinding,
        consumption_contract: v212_models.AuthorizationConsumptionReceiptContract,
        run_start_contract: v212_models.RunStartReceiptContract,
        authorization: v211_models.ExactOnlineExecutionAuthorization,
        authorization_bytes: bytes,
    ) -> None:
        self._binding = binding
        self._composition = composition
        self._source_contract = source_contract
        self._producer_binding = producer_binding
        self._runner_binding = runner_binding
        self._dispatcher_binding = dispatcher_binding
        self._persistence_binding = persistence_binding
        self._consumption_contract = consumption_contract
        self._run_start_contract = run_start_contract
        self._authorization = authorization
        self._authorization_bytes = authorization_bytes
        self._guard = ConsumerParentGuard(consumer=binding, composition=composition)

    def _runner(
        self,
        *,
        transport: ExitTracingScriptedTransport,
        source_exit_authority: SourceExitProofAuthority,
        runner_authority: RunnerFailureObservationAuthority,
        implementation: v209_models.ImplementationBinding,
        parents: Any,
        prepared: Any,
        config: AgentModelConfig,
    ) -> ExitProvenanceRunner:
        return ExitProvenanceRunner(
            source_exit_authority=source_exit_authority,
            observation_authority=runner_authority,
            runner_binding_id=self._runner_binding.binding_id,
            source_contract_id=self._source_contract.contract_id,
            transport=transport,
            config=config,
            profile=parents.profile,
            prepared=prepared,
            implementation_id=implementation.implementation_id,
            prompt_contract=parents.prompt_contract,
            prompt_schema=parents.prompt_schema,
        )

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

        upstream_authority = UpstreamFailureAuthority()
        producer = AuthoritativeUpstreamFailureProducer(
            binding=self._producer_binding, authority=upstream_authority
        )
        source_exit_authority = SourceExitProofAuthority(
            contract=self._source_contract, upstream_authority=upstream_authority
        )
        runner_authority = RunnerFailureObservationAuthority()
        dispatcher = ExitProvenanceDispatcher(
            binding=self._dispatcher_binding,
            source_contract=self._source_contract,
            runner_authority=runner_authority,
            upstream_authority=upstream_authority,
        )
        policy_by_terminal = dict(self._dispatcher_binding.terminal_policy_items)

        def transport_builder() -> ExitProvenanceTransportFactory:
            return ExitProvenanceTransportFactory(
                source_exit_authority=source_exit_authority,
                producer=producer,
                policy_by_terminal=policy_by_terminal,
            )

        def writer_builder() -> ExitProvenancePersistencePipeline:
            return ExitProvenancePersistencePipeline(
                root=root, binding=self._persistence_binding, dispatcher=dispatcher
            )

        products = v212_runtime.CredentialBoundFactoryGate().open(
            root=root / "consumer_ingress",
            consumption=consumption,
            run_start=run_start,
            credential_boundary_probe=boundary_probe,
            transport_factory_builder=transport_builder,
            writer_factory_builder=writer_builder,
        )
        factory = cast(ExitProvenanceTransportFactory, products.transport_factory)
        pipeline = cast(ExitProvenancePersistencePipeline, products.writer_factory_marker)
        if boundary_count != 1:
            raise ValueError("exit-provenance consumer factory order differs")

        jobs = tuple(sorted(manifest.jobs, key=lambda item: item.job_id))
        controls: list[models.ExitSurfaceControl] = []
        for job, (name, exit_code, expected_terminal) in zip(
            jobs[:5], models.EXIT_CONTROL_ITEMS, strict=True
        ):
            context = v209._context_for_job(job=job, parents=parents, prepared=prepared)
            transport = factory.create_for_control(name)
            outcome = self._runner(
                transport=transport,
                source_exit_authority=source_exit_authority,
                runner_authority=runner_authority,
                implementation=implementation,
                parents=parents,
                prepared=prepared,
                config=config,
            ).invoke_action(
                job=job,
                invocation_index=0,
                state=frozen_runtime._initialize(context),
            )
            if outcome.terminal is None:
                raise ValueError("actual v26.209 source exit did not terminalize")
            observation = runner_authority.get(outcome.record.invocation_id)
            evidence = _evidence(observation)
            decision = dispatcher.dispatch(evidence)
            descriptor = pipeline.persist(
                namespace="exit_surface_controls", evidence=evidence, decision=decision
            )
            if (
                outcome.terminal != expected_terminal
                or decision.terminal_kind != expected_terminal
                or observation.source_exit_proof.exit_code != exit_code
            ):
                raise ValueError("actual v26.209 source exit control differs")
            controls.append(
                cast(
                    models.ExitSurfaceControl,
                    models.make_identity(
                        models.ExitSurfaceControl,
                        {
                            "control_name": name,
                            "expected_exit_code": exit_code,
                            "expected_terminal": expected_terminal,
                            "source_exit_proof": observation.source_exit_proof,
                            "failure_observation": observation,
                            "evidence": evidence,
                            "decision": decision,
                            "persistence": descriptor,
                        },
                        field="control_id",
                        prefix="finance_v26_216_typed_failure_exit_control:",
                    ),
                )
            )
        strict_controls = tuple(controls)
        if runner_authority.count != 5 or upstream_authority.count != 1:
            raise ValueError("positive exit authority counts differ")

        negative_controls: list[models.NegativeControl] = []
        source_attacks = (
            (
                "registered_terminal_rethrow_without_upstream_authority",
                v209.TypedTransportFailure(
                    "instrument_failure", "arbitrary but registered-terminal reason"
                ),
            ),
            (
                "unregistered_terminal_rethrow",
                v209.TypedTransportFailure("unregistered_terminal", "unregistered queued failure"),
            ),
            (
                "nonregistered_exact_class_spoof",
                SpoofedTypedTransportFailure(
                    "instrument_failure", "same bare name but different exact class"
                ),
            ),
        )
        before_negative = runner_authority.count
        for job, (name, error) in zip(jobs[5:8], source_attacks, strict=True):
            context = v209._context_for_job(job=job, parents=parents, prepared=prepared)
            try:
                self._runner(
                    transport=factory.create_untrusted(error),
                    source_exit_authority=source_exit_authority,
                    runner_authority=runner_authority,
                    implementation=implementation,
                    parents=parents,
                    prepared=prepared,
                    config=config,
                ).invoke_action(
                    job=job,
                    invocation_index=0,
                    state=frozen_runtime._initialize(context),
                )
            except ValueError as rejected:
                negative_controls.append(
                    _negative_control(
                        name=name,
                        stage="source_exit_admission",
                        reason=str(rejected),
                    )
                )
            else:
                raise ValueError(f"unauthenticated queued rethrow was admitted:{name}")
        if runner_authority.count != before_negative:
            raise ValueError("source admission attack reached Runner authority")

        retained = _retained_authority_attacks(
            root=root,
            binding=self._persistence_binding,
            dispatcher_binding=self._dispatcher_binding,
            contract=self._source_contract,
            dispatcher=dispatcher,
            controls=strict_controls,
        )
        negative = cast(
            models.NegativeControlAudit,
            models.make_identity(
                models.NegativeControlAudit,
                {"controls": tuple(negative_controls) + retained},
                field="audit_id",
                prefix="finance_v26_216_exit_provenance_negative_control_audit:",
            ),
        )
        execution = cast(
            models.ExitSurfaceExecutionAudit,
            models.make_identity(
                models.ExitSurfaceExecutionAudit,
                {
                    "source_contract_id": self._source_contract.contract_id,
                    "consumer_binding_id": self._binding.binding_id,
                    "composition_contract_id": self._composition.contract_id,
                    "consumption_receipt_id": consumption.receipt_id,
                    "run_start_receipt_id": run_start.receipt_id,
                    "controls": strict_controls,
                },
                field="audit_id",
                prefix="finance_v26_216_exit_surface_execution_audit:",
            ),
        )
        return PreflightExecution(
            consumption_receipt=consumption,
            run_start_receipt=run_start,
            execution_audit=execution,
            negative_audit=negative,
        )
