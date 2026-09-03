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
    phase1_v26_fresh_repaired_typed_failure_exit_provenance_runtime as v216_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_models as models,
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


def _descriptor_file_relative(descriptor: models.UpstreamArtifactDescriptor) -> str:
    directory = (
        "upstream_event_descriptors"
        if descriptor.artifact_kind == "upstream_failure_event"
        else "upstream_observation_descriptors"
    )
    safe = hashlib.sha256(descriptor.descriptor_id.encode("utf-8")).hexdigest()
    return f"{directory}/{safe}.json"


class UpstreamEventArtifactAuthority:
    """No-replace event ledger whose authority includes actual persisted bytes."""

    def __init__(self, *, root: Path, binding: models.UpstreamEventSourceBinding) -> None:
        self._root = root
        self._binding = binding
        self._by_identity: dict[
            str, tuple[models.AuthenticatedUpstreamFailureEvent, models.UpstreamArtifactDescriptor]
        ] = {}

    def record_instrument_failure(
        self, *, source_job_id: str, source_invocation_request_parent_id: str
    ) -> models.AuthenticatedUpstreamFailureEvent:
        """Constructs the sole admitted event; no complete event or label is accepted."""
        strict = cast(
            models.AuthenticatedUpstreamFailureEvent,
            models.make_identity(
                models.AuthenticatedUpstreamFailureEvent,
                {
                    "event_source_binding_id": self._binding.binding_id,
                    "source_job_id": source_job_id,
                    "source_invocation_request_parent_id": source_invocation_request_parent_id,
                },
                field="event_id",
                prefix="fresh_repaired_authenticated_upstream_failure_event:",
            ),
        )
        if strict.event_id in self._by_identity:
            raise ValueError("upstream event already exists in bound source authority")
        safe = hashlib.sha256(strict.event_id.encode("utf-8")).hexdigest()
        relative = f"upstream_events/{safe}.json"
        payload = _encoded(strict)
        v212_runtime._durable_write_no_replace(self._root / relative, payload)
        descriptor = cast(
            models.UpstreamArtifactDescriptor,
            models.make_identity(
                models.UpstreamArtifactDescriptor,
                {
                    "artifact_kind": "upstream_failure_event",
                    "object_id": strict.event_id,
                    "relative_path": relative,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "byte_count": len(payload),
                    "parent_descriptor_id": None,
                },
                field="descriptor_id",
                prefix="fresh_repaired_upstream_artifact_descriptor:",
            ),
        )
        descriptor_path = self._root / _descriptor_file_relative(descriptor)
        v212_runtime._durable_write_no_replace(descriptor_path, _encoded(descriptor))
        self._by_identity[strict.event_id] = (strict, descriptor)
        self.require_event(strict)
        return strict

    def require_event(
        self, event: models.AuthenticatedUpstreamFailureEvent
    ) -> tuple[models.AuthenticatedUpstreamFailureEvent, models.UpstreamArtifactDescriptor]:
        strict = models.AuthenticatedUpstreamFailureEvent.model_validate(
            event.model_dump(mode="python", warnings=False)
        )
        saved = self._by_identity.get(strict.event_id)
        if saved is None or models.canonical_bytes(saved[0]) != models.canonical_bytes(strict):
            raise ValueError("upstream event is absent from source authority")
        actual_event, descriptor = saved
        event_path = self._root / descriptor.relative_path
        descriptor_path = self._root / _descriptor_file_relative(descriptor)
        if (
            not event_path.is_file()
            or event_path.read_bytes() != _encoded(actual_event)
            or hashlib.sha256(event_path.read_bytes()).hexdigest() != descriptor.sha256
            or event_path.stat().st_size != descriptor.byte_count
            or not descriptor_path.is_file()
            or descriptor_path.read_bytes() != _encoded(descriptor)
        ):
            raise ValueError("upstream event artifact bytes are absent or differ")
        return actual_event, descriptor


class BoundUpstreamInstrumentEventSource:
    def __init__(
        self,
        *,
        binding: models.UpstreamEventSourceBinding,
        authority: UpstreamEventArtifactAuthority,
    ) -> None:
        self._binding = binding
        self._authority = authority

    def emit_instrument_failure(
        self, *, source_job_id: str, source_invocation_request_parent_id: str
    ) -> models.AuthenticatedUpstreamFailureEvent:
        return self._authority.record_instrument_failure(
            source_job_id=source_job_id,
            source_invocation_request_parent_id=source_invocation_request_parent_id,
        )


class ArtifactBackedUpstreamFailureAuthority:
    def __init__(
        self,
        *,
        root: Path,
        event_authority: UpstreamEventArtifactAuthority,
    ) -> None:
        self._root = root
        self._events = event_authority
        self._by_object: dict[int, models.UpstreamArtifactChain] = {}
        self._by_identity: dict[str, models.UpstreamArtifactChain] = {}

    def record_observation(
        self,
        *,
        error: v209.TypedTransportFailure,
        chain: models.UpstreamArtifactChain,
    ) -> None:
        strict = models.UpstreamArtifactChain.model_validate(
            chain.model_dump(mode="python", warnings=False)
        )
        self._events.require_event(strict.event)
        observation = strict.observation
        if (
            type(error) is not v209.TypedTransportFailure
            or observation.exception_type_id != _exception_type_id(error)
            or observation.terminal_kind != error.terminal
            or observation.exception_reason_sha256 != _reason_sha(error)
            or id(error) in self._by_object
            or observation.observation_id in self._by_identity
        ):
            raise ValueError("artifact-backed upstream failure observation differs")
        self._by_object[id(error)] = strict
        self._by_identity[observation.observation_id] = strict
        self.require_error(error)

    def _require_artifacts(self, chain: models.UpstreamArtifactChain) -> None:
        self._events.require_event(chain.event)
        observation = chain.observation
        descriptor = chain.observation_descriptor
        observation_path = self._root / descriptor.relative_path
        descriptor_path = self._root / _descriptor_file_relative(descriptor)
        if (
            not observation_path.is_file()
            or observation_path.read_bytes() != _encoded(observation)
            or hashlib.sha256(observation_path.read_bytes()).hexdigest() != descriptor.sha256
            or observation_path.stat().st_size != descriptor.byte_count
            or not descriptor_path.is_file()
            or descriptor_path.read_bytes() != _encoded(descriptor)
        ):
            raise ValueError("upstream observation artifact bytes are absent or differ")

    def require_error(self, error: v209.TypedTransportFailure) -> models.UpstreamArtifactChain:
        chain = self._by_object.get(id(error))
        if chain is None:
            raise ValueError("queued typed failure has no artifact-backed upstream authority")
        observation = chain.observation
        if (
            type(error) is not v209.TypedTransportFailure
            or observation.exception_type_id != _exception_type_id(error)
            or observation.terminal_kind != error.terminal
            or observation.exception_reason_sha256 != _reason_sha(error)
        ):
            raise ValueError("queued typed failure differs from upstream artifact chain")
        self._require_artifacts(chain)
        return chain

    def require_identity(self, observation_id: str) -> models.UpstreamArtifactChain:
        chain = self._by_identity.get(observation_id)
        if chain is None:
            raise ValueError("upstream observation identity is absent")
        self._require_artifacts(chain)
        return chain

    def require_candidate_chain(self, chain: models.UpstreamArtifactChain) -> None:
        strict = models.UpstreamArtifactChain.model_validate(
            chain.model_dump(mode="python", warnings=False)
        )
        saved = self._by_identity.get(strict.observation.observation_id)
        if saved is None or models.canonical_bytes(saved) != models.canonical_bytes(strict):
            raise ValueError("candidate upstream artifact chain is outside source authority")
        self._require_artifacts(strict)

    @property
    def count(self) -> int:
        return len(self._by_identity)


class ArtifactBackedUpstreamFailureObserver:
    def __init__(
        self,
        *,
        binding: models.UpstreamObservationBinding,
        source_binding: models.UpstreamEventSourceBinding,
        event_authority: UpstreamEventArtifactAuthority,
        failure_authority: ArtifactBackedUpstreamFailureAuthority,
        root: Path,
    ) -> None:
        self._binding = binding
        self._source_binding = source_binding
        self._events = event_authority
        self._failures = failure_authority
        self._root = root

    def observe_failure(
        self, event: models.AuthenticatedUpstreamFailureEvent
    ) -> v209.TypedTransportFailure:
        strict_event, event_descriptor = self._events.require_event(event)
        event_kind, terminal_kind, terminal_policy_id = (
            self._source_binding.admitted_event_terminal_policy_items[0]
        )
        if strict_event.event_kind != event_kind:
            raise ValueError("upstream event kind is outside the source-derived terminal domain")
        error = v209.TypedTransportFailure(terminal_kind, strict_event.reason)
        observation = cast(
            models.ArtifactBackedUpstreamFailureObservation,
            models.make_identity(
                models.ArtifactBackedUpstreamFailureObservation,
                {
                    "observation_binding_id": self._binding.binding_id,
                    "event_id": strict_event.event_id,
                    "event_descriptor_id": event_descriptor.descriptor_id,
                    "source_job_id": strict_event.source_job_id,
                    "exception_type_id": _exception_type_id(error),
                    "terminal_kind": terminal_kind,
                    "exception_reason_sha256": _reason_sha(error),
                    "terminal_policy_id": terminal_policy_id,
                },
                field="observation_id",
                prefix="fresh_repaired_artifact_backed_upstream_failure_observation:",
            ),
        )
        safe = hashlib.sha256(observation.observation_id.encode("utf-8")).hexdigest()
        observation_relative = f"upstream_observations/{safe}.json"
        observation_payload = _encoded(observation)
        v212_runtime._durable_write_no_replace(
            self._root / observation_relative, observation_payload
        )
        observation_descriptor = cast(
            models.UpstreamArtifactDescriptor,
            models.make_identity(
                models.UpstreamArtifactDescriptor,
                {
                    "artifact_kind": "upstream_failure_observation",
                    "object_id": observation.observation_id,
                    "relative_path": observation_relative,
                    "sha256": hashlib.sha256(observation_payload).hexdigest(),
                    "byte_count": len(observation_payload),
                    "parent_descriptor_id": event_descriptor.descriptor_id,
                },
                field="descriptor_id",
                prefix="fresh_repaired_upstream_artifact_descriptor:",
            ),
        )
        v212_runtime._durable_write_no_replace(
            self._root / _descriptor_file_relative(observation_descriptor),
            _encoded(observation_descriptor),
        )
        chain = cast(
            models.UpstreamArtifactChain,
            models.make_identity(
                models.UpstreamArtifactChain,
                {
                    "event": strict_event,
                    "event_descriptor": event_descriptor,
                    "observation": observation,
                    "observation_descriptor": observation_descriptor,
                },
                field="chain_id",
                prefix="fresh_repaired_upstream_failure_artifact_chain:",
            ),
        )
        self._failures.record_observation(error=error, chain=chain)
        return error


class SourceExitProofAuthority:
    """Authenticates exact v26.209 direct exits and authority-backed rethrows."""

    def __init__(
        self,
        *,
        contract: models.TypedFailureExitSurfaceContract,
        upstream_authority: ArtifactBackedUpstreamFailureAuthority,
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
        upstream_chain: models.UpstreamArtifactChain | None,
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
                upstream_chain is not None
                or declaration.direct_terminal_kind != error.terminal
                or declaration.direct_reason_sha256 != reason_sha
            ):
                raise ValueError("direct typed failure differs from exact constructor exit")
        else:
            if upstream_chain is None:
                raise ValueError("queued typed failure rethrow lacks artifact-backed authority")
            upstream_observation = upstream_chain.observation
            if (
                upstream_observation.exception_type_id != _exception_type_id(error)
                or upstream_observation.terminal_kind != error.terminal
                or upstream_observation.exception_reason_sha256 != reason_sha
            ):
                raise ValueError("authenticated rethrow differs from upstream artifact chain")
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
                        upstream_chain.observation.observation_id
                        if upstream_chain is not None
                        else None
                    ),
                    "upstream_artifact_chain": upstream_chain,
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
            upstream_chain=upstream,
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
            upstream_chain=None,
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
    """Calls exact v26.209 send; E2 is born inside its actual dispatch."""

    def __init__(
        self,
        *,
        source_exit_authority: SourceExitProofAuthority,
        invalid_dispatch_chain: bool = False,
        authenticated_rethrow: bool = False,
        source_job_id: str | None = None,
        event_source: BoundUpstreamInstrumentEventSource | None = None,
        observer: ArtifactBackedUpstreamFailureObserver | None = None,
    ) -> None:
        super().__init__()
        self._source_exit_authority = source_exit_authority
        self._invalid_dispatch_chain = invalid_dispatch_chain
        self._authenticated_rethrow = authenticated_rethrow
        self._source_job_id = source_job_id
        self._event_source = event_source
        self._observer = observer
        self.authenticated_error: v209.TypedTransportFailure | None = None
        self.last_response: Any = None

    def send(self, dispatch: v209.TransportDispatch) -> Any:
        effective = dispatch
        if self._invalid_dispatch_chain:
            changed = dict(dispatch.request_body)
            changed["v26_217_invalid_dispatch_chain"] = True
            effective = v209.TransportDispatch(
                request_body=changed,
                certificate=dispatch.certificate,
                receipt=dispatch.receipt,
            )
            exit_code = "E0_invalid_dispatch_chain"
        else:
            if self._authenticated_rethrow:
                if (
                    self._queue
                    or self._source_job_id is None
                    or self._event_source is None
                    or self._observer is None
                    or self.authenticated_error is not None
                ):
                    raise ValueError("authenticated E2 transport source configuration differs")
                event = self._event_source.emit_instrument_failure(
                    source_job_id=self._source_job_id,
                    source_invocation_request_parent_id=_dispatch_parent(effective),
                )
                self.authenticated_error = self._observer.observe_failure(event)
                self.queue(self.authenticated_error)
            if not self._queue:
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


class ArtifactBackedTransportFactory(v212_runtime.ProviderTransportFactory):
    def __init__(
        self,
        *,
        source_exit_authority: SourceExitProofAuthority,
        event_source: BoundUpstreamInstrumentEventSource,
        observer: ArtifactBackedUpstreamFailureObserver,
    ) -> None:
        super().__init__()
        self._source_exit_authority = source_exit_authority
        self._event_source = event_source
        self._observer = observer
        self._e2_transport: ExitTracingScriptedTransport | None = None

    def _new(
        self,
        *,
        invalid: bool = False,
        authenticated_rethrow: bool = False,
        source_job_id: str | None = None,
    ) -> ExitTracingScriptedTransport:
        self.construction_count += 1
        return ExitTracingScriptedTransport(
            source_exit_authority=self._source_exit_authority,
            invalid_dispatch_chain=invalid,
            authenticated_rethrow=authenticated_rethrow,
            source_job_id=source_job_id,
            event_source=self._event_source if authenticated_rethrow else None,
            observer=self._observer if authenticated_rethrow else None,
        )

    @property
    def positive_e2_error(self) -> v209.TypedTransportFailure | None:
        if self._e2_transport is None:
            return None
        return self._e2_transport.authenticated_error

    def create_for_control(
        self, *, control_name: str, source_job_id: str
    ) -> ExitTracingScriptedTransport:
        if control_name == "transport_invalid_dispatch_chain":
            return self._new(invalid=True)
        if control_name == "transport_authenticated_rethrow":
            transport = self._new(authenticated_rethrow=True, source_job_id=source_job_id)
            self._e2_transport = transport
            return transport
        transport = self._new()
        if control_name == "projection_reasoning_key":
            transport.queue({"reasoning_content": "must remain private"})
        elif control_name == "projection_non_object":
            transport.queue(cast(Any, ("not", "a", "json", "object")))
        elif control_name != "transport_empty_queue":
            raise ValueError(f"unknown exit-surface control:{control_name}")
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


class ArtifactBackedExitProvenanceRunner(v216_runtime.ExitProvenanceRunner):
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
                prefix="fresh_repaired_upstream_event_authority_typed_failure_observation:",
            ),
        )
        self._observation_authority.record_from_runner(observation)
        return v209.InvocationOutcome(record=record, terminal=error.terminal)


class ArtifactBackedExitDispatcher:
    def __init__(
        self,
        *,
        binding: models.DispatcherBinding,
        source_contract: models.TypedFailureExitSurfaceContract,
        runner_authority: RunnerFailureObservationAuthority,
        upstream_authority: ArtifactBackedUpstreamFailureAuthority,
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
            if (
                proof.upstream_failure_observation_id is None
                or proof.upstream_artifact_chain is None
            ):
                raise ValueError("rethrow source exit proof lacks artifact-backed authority")
            chain = self._upstream_authority.require_identity(proof.upstream_failure_observation_id)
            if models.canonical_bytes(chain) != models.canonical_bytes(
                proof.upstream_artifact_chain
            ):
                raise ValueError("rethrow source exit proof crosses upstream artifact chain")
            upstream = chain.observation
            if (
                upstream.exception_type_id != proof.exception_type_id
                or upstream.terminal_kind != proof.terminal_kind
                or upstream.exception_reason_sha256 != proof.exception_reason_sha256
                or upstream.terminal_policy_id != self._policy_by_terminal.get(proof.terminal_kind)
            ):
                raise ValueError("rethrow proof differs from artifact-backed observation")
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
                prefix="fresh_repaired_upstream_event_authority_terminal_decision:",
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
        prefix="fresh_repaired_upstream_event_authority_raw:",
    )
    result = _identified(
        {**shared, "raw_id": raw["raw_id"]},
        field="result_id",
        prefix="fresh_repaired_upstream_event_authority_result:",
    )
    trace = _identified(
        {**shared, "raw_id": raw["raw_id"], "result_id": result["result_id"]},
        field="trace_id",
        prefix="fresh_repaired_upstream_event_authority_trace:",
    )
    outcome = _identified(
        {
            **shared,
            "raw_id": raw["raw_id"],
            "result_id": result["result_id"],
            "trace_id": trace["trace_id"],
        },
        field="outcome_id",
        prefix="fresh_repaired_upstream_event_authority_outcome:",
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
        prefix="fresh_repaired_upstream_event_authority_checkpoint:",
    )
    return (
        ("raw", raw),
        ("result", result),
        ("trace", trace),
        ("outcome", outcome),
        ("checkpoint", checkpoint),
    )


class ArtifactBackedExitPersistencePipeline:
    def __init__(
        self,
        *,
        root: Path,
        binding: models.PersistenceBinding,
        dispatcher: ArtifactBackedExitDispatcher,
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
                prefix="finance_v26_217_upstream_event_authority_persisted_descriptor:",
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
            or strict_composition.upstream_event_source_binding_id
            != strict_consumer.upstream_event_source_binding_id
            or strict_composition.upstream_observation_binding_id
            != strict_consumer.upstream_observation_binding_id
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
            prefix="fresh_repaired_upstream_event_authority_authenticated_typed_failure_evidence:",
        ),
    )


def _forged_observation(
    source: models.TypedFailureObservation, **updates: Any
) -> models.TypedFailureObservation:
    values = source.model_dump(mode="python", exclude={"observation_id"}, warnings=False)
    values["source_exit_proof"] = models.SourceExitProof.model_validate(values["source_exit_proof"])
    values.update(updates)
    observation_id = canonical_hash(
        values, prefix="fresh_repaired_upstream_event_authority_typed_failure_observation:"
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
        prefix="fresh_repaired_upstream_event_authority_authenticated_typed_failure_evidence:",
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
        "derivation_rule": "source_exit_proof_artifact_backed_event_observation_and_registry_agreement",
        "terminal_label_was_input": False,
        "provider_calls": 0,
        "schema_version": models.SCHEMA_VERSION,
    }
    decision_id = canonical_hash(
        values, prefix="fresh_repaired_upstream_event_authority_terminal_decision:"
    )
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
                "rejected_before_runner_authority_append": True,
                "fully_rehashed": bool(layer_ids),
                "fully_rehashed_downstream_layer_ids": layer_ids,
                "rejection_reason_sha256": hashlib.sha256(reason.encode("utf-8")).hexdigest(),
            },
            field="control_id",
            prefix="finance_v26_217_upstream_event_authority_negative_control:",
        ),
    )


def _forged_artifact_chain(
    source: models.UpstreamArtifactChain,
    *,
    source_job_id: str,
    request_parent: str,
) -> models.UpstreamArtifactChain:
    event = cast(
        models.AuthenticatedUpstreamFailureEvent,
        models.make_identity(
            models.AuthenticatedUpstreamFailureEvent,
            {
                "event_source_binding_id": source.event.event_source_binding_id,
                "source_job_id": source_job_id,
                "source_invocation_request_parent_id": request_parent,
            },
            field="event_id",
            prefix="fresh_repaired_authenticated_upstream_failure_event:",
        ),
    )
    event_payload = _encoded(event)
    event_descriptor = cast(
        models.UpstreamArtifactDescriptor,
        models.make_identity(
            models.UpstreamArtifactDescriptor,
            {
                "artifact_kind": "upstream_failure_event",
                "object_id": event.event_id,
                "relative_path": f"upstream_events/forged-{hashlib.sha256(event.event_id.encode()).hexdigest()}.json",
                "sha256": hashlib.sha256(event_payload).hexdigest(),
                "byte_count": len(event_payload),
                "parent_descriptor_id": None,
            },
            field="descriptor_id",
            prefix="fresh_repaired_upstream_artifact_descriptor:",
        ),
    )
    observation = cast(
        models.ArtifactBackedUpstreamFailureObservation,
        models.make_identity(
            models.ArtifactBackedUpstreamFailureObservation,
            {
                "observation_binding_id": source.observation.observation_binding_id,
                "event_id": event.event_id,
                "event_descriptor_id": event_descriptor.descriptor_id,
                "source_job_id": event.source_job_id,
                "exception_type_id": source.observation.exception_type_id,
                "terminal_kind": source.observation.terminal_kind,
                "exception_reason_sha256": source.observation.exception_reason_sha256,
                "terminal_policy_id": source.observation.terminal_policy_id,
            },
            field="observation_id",
            prefix="fresh_repaired_artifact_backed_upstream_failure_observation:",
        ),
    )
    observation_payload = _encoded(observation)
    observation_descriptor = cast(
        models.UpstreamArtifactDescriptor,
        models.make_identity(
            models.UpstreamArtifactDescriptor,
            {
                "artifact_kind": "upstream_failure_observation",
                "object_id": observation.observation_id,
                "relative_path": f"upstream_observations/forged-{hashlib.sha256(observation.observation_id.encode()).hexdigest()}.json",
                "sha256": hashlib.sha256(observation_payload).hexdigest(),
                "byte_count": len(observation_payload),
                "parent_descriptor_id": event_descriptor.descriptor_id,
            },
            field="descriptor_id",
            prefix="fresh_repaired_upstream_artifact_descriptor:",
        ),
    )
    return cast(
        models.UpstreamArtifactChain,
        models.make_identity(
            models.UpstreamArtifactChain,
            {
                "event": event,
                "event_descriptor": event_descriptor,
                "observation": observation,
                "observation_descriptor": observation_descriptor,
            },
            field="chain_id",
            prefix="fresh_repaired_upstream_failure_artifact_chain:",
        ),
    )


def _proof_with_chain(
    source: models.SourceExitProof, chain: models.UpstreamArtifactChain
) -> models.SourceExitProof:
    values = source.model_dump(mode="python", exclude={"proof_id"}, warnings=False)
    values["dispatch_or_response_parent_id"] = chain.event.source_invocation_request_parent_id
    values["upstream_failure_observation_id"] = chain.observation.observation_id
    values["upstream_artifact_chain"] = chain
    return cast(
        models.SourceExitProof,
        models.make_identity(
            models.SourceExitProof,
            values,
            field="proof_id",
            prefix="fresh_repaired_v209_typed_failure_source_exit_proof:",
        ),
    )


def _downstream_for_proof(
    *,
    source: models.TypedFailureObservation,
    proof: models.SourceExitProof,
    binding: models.PersistenceBinding,
    dispatcher_binding: models.DispatcherBinding,
    contract: models.TypedFailureExitSurfaceContract,
) -> tuple[
    models.AuthenticatedTypedFailureEvidence,
    models.DerivedTerminalDecision,
    tuple[str, ...],
]:
    forged = _forged_observation(source, source_exit_proof=proof)
    evidence = _forged_evidence(forged)
    decision = _forged_decision(
        binding=dispatcher_binding,
        contract=contract,
        evidence=evidence,
        terminal=proof.terminal_kind,
    )
    layer_ids = tuple(
        cast(str, value[f"{layer}_id"])
        for layer, value in _layer_values(binding=binding, evidence=evidence, decision=decision)
    )
    return evidence, decision, layer_ids


def _upstream_authority_attacks(
    *,
    root: Path,
    binding: models.PersistenceBinding,
    dispatcher_binding: models.DispatcherBinding,
    contract: models.TypedFailureExitSurfaceContract,
    dispatcher: ArtifactBackedExitDispatcher,
    controls: tuple[models.ExitSurfaceControl, ...],
    failure_authority: ArtifactBackedUpstreamFailureAuthority,
    event_source: BoundUpstreamInstrumentEventSource,
    observer: ArtifactBackedUpstreamFailureObserver,
    positive_e2_error: v209.TypedTransportFailure,
    cross_job_id: str,
) -> tuple[models.NegativeControl, ...]:
    positive = next(
        item for item in controls if item.expected_exit_code == "E2_authenticated_rethrow"
    )
    positive_chain = failure_authority.require_error(positive_e2_error)
    results: list[models.NegativeControl] = []

    try:
        cast(Any, observer).observe_failure(
            positive_chain.event, terminal_kind="completed_qualified"
        )
    except TypeError as error:
        results.append(
            _negative_control(
                name="completed_qualified_producer_mint_attempt",
                stage="event_schema_admission",
                reason=str(error),
            )
        )
    else:
        raise ValueError("completed terminal mint entered upstream observer")

    impossible_values = positive_chain.observation.model_dump(
        mode="python", exclude={"observation_id"}, warnings=False
    )
    impossible_values["terminal_kind"] = "provider_transport_failure"
    impossible_id = canonical_hash(
        impossible_values,
        prefix="fresh_repaired_artifact_backed_upstream_failure_observation:",
    )
    try:
        models.ArtifactBackedUpstreamFailureObservation.model_validate(
            {"observation_id": impossible_id, **impossible_values}
        )
    except ValueError as error:
        results.append(
            _negative_control(
                name="registered_event_incompatible_outer_terminal",
                stage="event_schema_admission",
                reason=str(error),
            )
        )
    else:
        raise ValueError("event-incompatible registered terminal was admitted")

    forged_chain = _forged_artifact_chain(
        positive_chain,
        source_job_id=positive_chain.event.source_job_id,
        request_parent=canonical_hash(
            {"caller": "forged-source-event-id"},
            prefix="finance_v26_217_forged_upstream_event_parent:",
        ),
    )
    forged_proof = _proof_with_chain(positive.source_exit_proof, forged_chain)
    _forged_evidence_value, _forged_decision_value, forged_layer_ids = _downstream_for_proof(
        source=positive.failure_observation,
        proof=forged_proof,
        binding=binding,
        dispatcher_binding=dispatcher_binding,
        contract=contract,
    )
    try:
        failure_authority.require_candidate_chain(forged_chain)
    except ValueError as error:
        results.append(
            _negative_control(
                name="caller_forged_source_event_id_full_rehash",
                stage="upstream_artifact_admission",
                reason=str(error),
                layer_ids=forged_layer_ids,
            )
        )
    else:
        raise ValueError("fully rehashed forged upstream event was admitted")

    cross_event = event_source.emit_instrument_failure(
        source_job_id=cross_job_id,
        source_invocation_request_parent_id=canonical_hash(
            {"cross_job_id": cross_job_id},
            prefix="finance_v26_217_cross_event_request_parent:",
        ),
    )
    cross_error = observer.observe_failure(cross_event)
    cross_chain = failure_authority.require_error(cross_error)
    event_path = root / cross_chain.event_descriptor.relative_path
    absent_path = event_path.with_suffix(".temporarily_absent")
    event_path.rename(absent_path)
    try:
        try:
            failure_authority.require_candidate_chain(cross_chain)
        except ValueError as error:
            results.append(
                _negative_control(
                    name="missing_upstream_event_artifact",
                    stage="upstream_artifact_admission",
                    reason=str(error),
                )
            )
        else:
            raise ValueError("missing upstream event artifact was admitted")
    finally:
        absent_path.rename(event_path)
    failure_authority.require_candidate_chain(cross_chain)

    cross_proof = _proof_with_chain(positive.source_exit_proof, cross_chain)
    cross_evidence, cross_decision, cross_layer_ids = _downstream_for_proof(
        source=positive.failure_observation,
        proof=cross_proof,
        binding=binding,
        dispatcher_binding=dispatcher_binding,
        contract=contract,
    )
    attack_root = root / "negative_controls"
    pipeline = ArtifactBackedExitPersistencePipeline(
        root=attack_root, binding=binding, dispatcher=dispatcher
    )
    try:
        pipeline.persist(
            namespace="cross_event_cross_job_observation_substitution",
            evidence=cross_evidence,
            decision=cross_decision,
        )
    except ValueError as error:
        results.append(
            _negative_control(
                name="cross_event_cross_job_observation_substitution",
                stage="persistence_pre_raw",
                reason=str(error),
                layer_ids=cross_layer_ids,
            )
        )
    else:
        raise ValueError("cross-event/cross-Job observation was admitted")
    if attack_root.exists() and any(path.is_file() for path in attack_root.rglob("*")):
        raise ValueError("upstream authority attack wrote Raw evidence")
    return tuple(results)


@dataclass(frozen=True)
class PreflightExecution:
    consumption_receipt: v212_models.PreflightConsumptionReceipt
    run_start_receipt: v212_models.PreflightRunStartReceipt
    execution_audit: models.ExitSurfaceExecutionAudit
    negative_audit: models.NegativeControlAudit


class ArtifactBackedFailureConsumer:
    def __init__(
        self,
        *,
        binding: models.ConsumerBinding,
        composition: models.CompositionContract,
        source_contract: models.TypedFailureExitSurfaceContract,
        event_source_binding: models.UpstreamEventSourceBinding,
        observation_binding: models.UpstreamObservationBinding,
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
        self._event_source_binding = event_source_binding
        self._observation_binding = observation_binding
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
    ) -> ArtifactBackedExitProvenanceRunner:
        return ArtifactBackedExitProvenanceRunner(
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

        event_authority = UpstreamEventArtifactAuthority(
            root=root, binding=self._event_source_binding
        )
        failure_authority = ArtifactBackedUpstreamFailureAuthority(
            root=root, event_authority=event_authority
        )
        event_source = BoundUpstreamInstrumentEventSource(
            binding=self._event_source_binding, authority=event_authority
        )
        observer = ArtifactBackedUpstreamFailureObserver(
            binding=self._observation_binding,
            source_binding=self._event_source_binding,
            event_authority=event_authority,
            failure_authority=failure_authority,
            root=root,
        )
        source_exit_authority = SourceExitProofAuthority(
            contract=self._source_contract, upstream_authority=failure_authority
        )
        runner_authority = RunnerFailureObservationAuthority()
        dispatcher = ArtifactBackedExitDispatcher(
            binding=self._dispatcher_binding,
            source_contract=self._source_contract,
            runner_authority=runner_authority,
            upstream_authority=failure_authority,
        )

        def transport_builder() -> ArtifactBackedTransportFactory:
            return ArtifactBackedTransportFactory(
                source_exit_authority=source_exit_authority,
                event_source=event_source,
                observer=observer,
            )

        def writer_builder() -> ArtifactBackedExitPersistencePipeline:
            return ArtifactBackedExitPersistencePipeline(
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
        factory = cast(ArtifactBackedTransportFactory, products.transport_factory)
        pipeline = cast(ArtifactBackedExitPersistencePipeline, products.writer_factory_marker)
        if boundary_count != 1:
            raise ValueError("artifact-backed consumer factory order differs")

        jobs = tuple(sorted(manifest.jobs, key=lambda item: item.job_id))
        controls: list[models.ExitSurfaceControl] = []
        for job, (name, exit_code, expected_terminal) in zip(
            jobs[:5], models.EXIT_CONTROL_ITEMS, strict=True
        ):
            context = v209._context_for_job(job=job, parents=parents, prepared=prepared)
            transport = factory.create_for_control(control_name=name, source_job_id=job.job_id)
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
                        prefix="finance_v26_217_typed_failure_exit_control:",
                    ),
                )
            )
        strict_controls = tuple(controls)
        if (
            runner_authority.count != 5
            or failure_authority.count != 1
            or factory.positive_e2_error is None
        ):
            raise ValueError("positive exit authority counts differ")
        e2_chain = failure_authority.require_error(factory.positive_e2_error)
        e2_control = next(
            item
            for item in strict_controls
            if item.expected_exit_code == "E2_authenticated_rethrow"
        )
        if e2_control.source_exit_proof.upstream_artifact_chain is None or models.canonical_bytes(
            e2_control.source_exit_proof.upstream_artifact_chain
        ) != models.canonical_bytes(e2_chain):
            raise ValueError("positive E2 proof does not embed exact artifact chain")

        before_negative = runner_authority.count
        negative_controls = _upstream_authority_attacks(
            root=root,
            binding=self._persistence_binding,
            dispatcher_binding=self._dispatcher_binding,
            contract=self._source_contract,
            dispatcher=dispatcher,
            controls=strict_controls,
            failure_authority=failure_authority,
            event_source=event_source,
            observer=observer,
            positive_e2_error=factory.positive_e2_error,
            cross_job_id=jobs[5].job_id,
        )
        if runner_authority.count != before_negative:
            raise ValueError("upstream authority attack reached Runner authority")
        negative = cast(
            models.NegativeControlAudit,
            models.make_identity(
                models.NegativeControlAudit,
                {"controls": negative_controls},
                field="audit_id",
                prefix="finance_v26_217_upstream_event_authority_negative_control_audit:",
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
                prefix="finance_v26_217_exit_surface_execution_audit:",
            ),
        )
        return PreflightExecution(
            consumption_receipt=consumption,
            run_start_receipt=run_start,
            execution_audit=execution,
            negative_audit=negative,
        )
