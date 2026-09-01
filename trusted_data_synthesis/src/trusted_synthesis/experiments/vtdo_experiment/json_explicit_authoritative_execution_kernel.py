from __future__ import annotations

import hashlib
import inspect
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_explicit_prompt_contract_preflight as v192,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    StageOneProspectiveThinkingJsonClient,
    StageOneRequestBindingCertificate,
    certify_stage_one_request_pre_call,
    make_stage_one_request_body,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

PromptKind = Literal["action", "correction", "final"]
RequestKind = Literal["semantic_proposal", "final_answer"]
PublicAttemptPhase = Literal["primary", "semantic_recovery"]
KernelEvent = Literal[
    "render",
    "request_body",
    "request_certificate",
    "resource_certificate",
    "dynamic_certificate",
    "certified_client",
    "privacy_envelope_journal",
    "privacy_projection_journal",
    "semantic_parse",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


class KernelResourceCertificate(FrozenModel):
    certificate_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0, le=22)
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_utf8_bytes: int = Field(gt=0, le=60000)
    provider_calls_before: int = Field(ge=0, le=22)
    transport_invocations_before: int = Field(ge=0, le=23)
    maximum_provider_calls: Literal[23] = 23
    maximum_transport_invocations: Literal[24] = 24
    maximum_rollout_tokens: Literal[1120000] = 1120000
    maximum_prompt_utf8_bytes: Literal[60000] = 60000
    provider_call_permitted: Literal[True] = True

    @model_validator(mode="after")
    def validate_certificate(self) -> KernelResourceCertificate:
        if self.certificate_id != _identity(
            self, "certificate_id", "authoritative_kernel_resource_certificate:"
        ):
            raise ValueError("kernel resource certificate identity differs")
        return self


class KernelDynamicRequestCertificate(FrozenModel):
    certificate_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0, le=22)
    prompt_kind: PromptKind
    request_kind: RequestKind
    public_attempt_phase: PublicAttemptPhase
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_binding_certificate_id: str = Field(min_length=1)
    resource_certificate_id: str = Field(min_length=1)
    invocation_authorized: Literal[True] = True

    @model_validator(mode="after")
    def validate_certificate(self) -> KernelDynamicRequestCertificate:
        if self.certificate_id != _identity(
            self, "certificate_id", "authoritative_kernel_dynamic_request_certificate:"
        ):
            raise ValueError("kernel dynamic request certificate identity differs")
        return self


class PreparedKernelRequest(FrozenModel):
    preparation_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0, le=22)
    prompt_kind: PromptKind
    rendered_prompt: str = Field(min_length=1)
    canonical_request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_binding_certificate: StageOneRequestBindingCertificate
    resource_certificate: KernelResourceCertificate
    dynamic_certificate: KernelDynamicRequestCertificate

    @model_validator(mode="after")
    def validate_request(self) -> PreparedKernelRequest:
        prompt_sha = _sha256(self.rendered_prompt.encode("utf-8"))
        if (
            self.request_binding_certificate.prompt_sha256 != prompt_sha
            or self.resource_certificate.prompt_sha256 != prompt_sha
            or self.dynamic_certificate.prompt_sha256 != prompt_sha
            or self.dynamic_certificate.request_binding_certificate_id
            != self.request_binding_certificate.certificate_id
            or self.dynamic_certificate.resource_certificate_id
            != self.resource_certificate.certificate_id
            or self.dynamic_certificate.request_body_sha256 != self.canonical_request_body_sha256
        ):
            raise ValueError("prepared kernel request crosses a certificate parent")
        if self.preparation_id != _identity(
            self, "preparation_id", "authoritative_kernel_prepared_request:"
        ):
            raise ValueError("prepared kernel request identity differs")
        return self


class CertifiedClientResponse(FrozenModel):
    response_id: str = Field(min_length=1)
    payload: dict[str, Any]
    telemetry: ModelCallTelemetry
    consumed_request_binding_certificate_id: str = Field(min_length=1)
    transmitted_request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_call_made: bool

    @model_validator(mode="after")
    def validate_response(self) -> CertifiedClientResponse:
        if self.response_id != _identity(
            self, "response_id", "authoritative_kernel_certified_client_response:"
        ):
            raise ValueError("certified client response identity differs")
        return self


class KernelInvocationReceipt(FrozenModel):
    receipt_id: str = Field(min_length=1)
    preparation_id: str = Field(min_length=1)
    certified_response_id: str = Field(min_length=1)
    envelope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    projection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_sequence: tuple[KernelEvent, ...]
    provider_call_made: bool

    @model_validator(mode="after")
    def validate_receipt(self) -> KernelInvocationReceipt:
        expected = (
            "render",
            "request_body",
            "request_certificate",
            "resource_certificate",
            "dynamic_certificate",
            "certified_client",
            "privacy_envelope_journal",
            "privacy_projection_journal",
            "semantic_parse",
        )
        if self.event_sequence != expected:
            raise ValueError("kernel invocation sequence differs")
        if self.receipt_id != _identity(
            self, "receipt_id", "authoritative_kernel_invocation_receipt:"
        ):
            raise ValueError("kernel invocation receipt identity differs")
        return self


class CertifiedKernelClient(Protocol):
    config: AgentModelConfig

    def complete_json_certified(
        self,
        prompt: str,
        certificate: StageOneRequestBindingCertificate,
    ) -> CertifiedClientResponse: ...


class KernelJournalWriter(Protocol):
    def write_envelope(
        self, *, job_id: str, logical_request_index: int, payload: dict[str, Any]
    ) -> str: ...

    def write_projection(
        self, *, job_id: str, logical_request_index: int, payload: dict[str, Any]
    ) -> str: ...

    def write_raw(self, *, job_id: str, payload: dict[str, Any]) -> str: ...

    def write_result(self, *, job_id: str, payload: dict[str, Any]) -> str: ...

    def assert_no_orphans(self) -> None: ...


def _write_no_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


class NoReplaceKernelJournalWriter:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._envelopes: set[tuple[str, int]] = set()
        self._projections: set[tuple[str, int]] = set()
        self._raw: set[str] = set()
        self._result: set[str] = set()

    def _write(self, relative: Path, payload: dict[str, Any]) -> str:
        encoded = _canonical_bytes(payload)
        _write_no_replace(self._root / relative, encoded)
        return _sha256(encoded)

    def write_envelope(
        self, *, job_id: str, logical_request_index: int, payload: dict[str, Any]
    ) -> str:
        key = (job_id, logical_request_index)
        if key in self._envelopes:
            raise ValueError("duplicate privacy envelope")
        value = self._write(
            Path("envelopes") / _safe(job_id) / f"{logical_request_index:03d}.json", payload
        )
        self._envelopes.add(key)
        return value

    def write_projection(
        self, *, job_id: str, logical_request_index: int, payload: dict[str, Any]
    ) -> str:
        key = (job_id, logical_request_index)
        if key not in self._envelopes:
            raise ValueError("privacy projection precedes its envelope")
        if key in self._projections:
            raise ValueError("duplicate privacy projection")
        value = self._write(
            Path("projections") / _safe(job_id) / f"{logical_request_index:03d}.json", payload
        )
        self._projections.add(key)
        return value

    def write_raw(self, *, job_id: str, payload: dict[str, Any]) -> str:
        if job_id in self._raw:
            raise ValueError("duplicate Raw write")
        value = self._write(Path("raw") / f"{_safe(job_id)}.json", payload)
        self._raw.add(job_id)
        return value

    def write_result(self, *, job_id: str, payload: dict[str, Any]) -> str:
        if job_id not in self._raw:
            raise ValueError("Result write bypasses Raw")
        if job_id in self._result:
            raise ValueError("duplicate Result write")
        value = self._write(Path("result") / f"{_safe(job_id)}.json", payload)
        self._result.add(job_id)
        return value

    def assert_no_orphans(self) -> None:
        if self._envelopes != self._projections:
            raise ValueError("orphan Provider artifact blocks execution")
        if self._raw != self._result:
            raise ValueError("orphan Raw/Result artifact blocks execution")


def _safe(identifier: str) -> str:
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()


class ProductionStageOneClientAdapter:
    """Narrow adapter around the exact certified client; no alternate request-body seam."""

    def __init__(self, client: StageOneProspectiveThinkingJsonClient) -> None:
        self._client = client
        self.config = client.config

    def complete_json_certified(
        self,
        prompt: str,
        certificate: StageOneRequestBindingCertificate,
    ) -> CertifiedClientResponse:
        payload, telemetry = self._client.complete_json_certified(prompt, certificate)
        body_sha = _sha256(_canonical_bytes(make_stage_one_request_body(self.config, prompt)))
        values = {
            "payload": payload,
            "telemetry": telemetry,
            "consumed_request_binding_certificate_id": certificate.certificate_id,
            "transmitted_request_body_sha256": body_sha,
            "actual_prompt_sha256": _sha256(prompt.encode("utf-8")),
            "provider_call_made": True,
        }
        provisional = CertifiedClientResponse.model_construct(response_id="pending", **values)
        return CertifiedClientResponse(
            response_id=_identity(
                provisional,
                "response_id",
                "authoritative_kernel_certified_client_response:",
            ),
            **values,
        )


@dataclass
class _JobLedger:
    provider_calls: int = 0
    transport_invocations: int = 0
    cumulative_tokens: int = 0


class AuthoritativeJsonExplicitExecutionKernel:
    """Production-shaped certified seam shared by Action, Correction, and Final."""

    def __init__(
        self,
        *,
        execution_contract_id: str,
        runner_id: str,
        manifest_id: str,
        prompt_contract: v192.JsonExplicitPromptContract,
        prompt_schema: v192.JsonExplicitPromptSchema,
        client: CertifiedKernelClient,
        writer: KernelJournalWriter,
    ) -> None:
        if "fixture_response" in inspect.signature(self.invoke).parameters:
            raise ValueError("fixture_response entered production Runner input")
        self._execution_contract_id = execution_contract_id
        self._runner_id = runner_id
        self._manifest_id = manifest_id
        self._prompt_contract = prompt_contract
        self._prompt_schema = prompt_schema
        self._client = client
        self._writer = writer
        self._ledgers: dict[str, _JobLedger] = {}
        self._receipts: dict[str, list[KernelInvocationReceipt]] = {}

    @property
    def receipts(self) -> tuple[KernelInvocationReceipt, ...]:
        return tuple(item for job in sorted(self._receipts) for item in self._receipts[job])

    def invoke(
        self,
        *,
        job_id: str,
        logical_request_index: int,
        prompt_kind: PromptKind,
        public_attempt_phase: PublicAttemptPhase,
        core: dict[str, Any] | str,
    ) -> dict[str, Any]:
        events: list[KernelEvent] = []
        prompt = v192._render_prompt(  # noqa: SLF001
            prompt_kind=prompt_kind,
            core=core,
            contract=self._prompt_contract,
            schema=self._prompt_schema,
        )
        events.append("render")
        body = make_stage_one_request_body(self._client.config, prompt)
        body_sha = _sha256(_canonical_bytes(body))
        events.append("request_body")
        request_kind: RequestKind = (
            "final_answer" if prompt_kind == "final" else "semantic_proposal"
        )
        provider_phase: Literal["primary", "rescue"] = (
            "rescue" if public_attempt_phase == "semantic_recovery" else "primary"
        )
        request_certificate = certify_stage_one_request_pre_call(
            config=self._client.config,
            prompt=prompt,
            request_kind=request_kind,
            phase=provider_phase,
        )
        if request_certificate.canonical_request_body_sha256 != body_sha:
            raise ValueError("request builder differs from request certificate")
        events.append("request_certificate")
        ledger = self._ledgers.setdefault(job_id, _JobLedger())
        if logical_request_index != len(self._receipts.setdefault(job_id, [])):
            raise ValueError("logical request index is not contiguous")
        resource_values = {
            "execution_contract_id": self._execution_contract_id,
            "job_id": job_id,
            "logical_request_index": logical_request_index,
            "prompt_sha256": request_certificate.prompt_sha256,
            "prompt_utf8_bytes": len(prompt.encode("utf-8")),
            "provider_calls_before": ledger.provider_calls,
            "transport_invocations_before": ledger.transport_invocations,
        }
        provisional_resource = KernelResourceCertificate.model_construct(
            certificate_id="pending", **resource_values
        )
        resource = KernelResourceCertificate(
            certificate_id=_identity(
                provisional_resource,
                "certificate_id",
                "authoritative_kernel_resource_certificate:",
            ),
            **resource_values,
        )
        events.append("resource_certificate")
        dynamic_values = {
            "execution_contract_id": self._execution_contract_id,
            "runner_id": self._runner_id,
            "manifest_id": self._manifest_id,
            "job_id": job_id,
            "logical_request_index": logical_request_index,
            "prompt_kind": prompt_kind,
            "request_kind": request_kind,
            "public_attempt_phase": public_attempt_phase,
            "prompt_sha256": request_certificate.prompt_sha256,
            "request_body_sha256": body_sha,
            "request_binding_certificate_id": request_certificate.certificate_id,
            "resource_certificate_id": resource.certificate_id,
        }
        provisional_dynamic = KernelDynamicRequestCertificate.model_construct(
            certificate_id="pending", **dynamic_values
        )
        dynamic = KernelDynamicRequestCertificate(
            certificate_id=_identity(
                provisional_dynamic,
                "certificate_id",
                "authoritative_kernel_dynamic_request_certificate:",
            ),
            **dynamic_values,
        )
        events.append("dynamic_certificate")
        prepared_values = {
            "job_id": job_id,
            "logical_request_index": logical_request_index,
            "prompt_kind": prompt_kind,
            "rendered_prompt": prompt,
            "canonical_request_body_sha256": body_sha,
            "request_binding_certificate": request_certificate,
            "resource_certificate": resource,
            "dynamic_certificate": dynamic,
        }
        provisional_prepared = PreparedKernelRequest.model_construct(
            preparation_id="pending", **prepared_values
        )
        prepared = PreparedKernelRequest(
            preparation_id=_identity(
                provisional_prepared,
                "preparation_id",
                "authoritative_kernel_prepared_request:",
            ),
            **prepared_values,
        )
        response = self._client.complete_json_certified(prompt, request_certificate)
        events.append("certified_client")
        if response.consumed_request_binding_certificate_id != request_certificate.certificate_id:
            raise ValueError("certified client consumed a missing or crossed request certificate")
        if response.transmitted_request_body_sha256 != body_sha:
            raise ValueError("transport mutated or ignored the certified request body")
        if response.actual_prompt_sha256 != request_certificate.prompt_sha256:
            raise ValueError("certified client bypassed the JSON-explicit renderer")
        envelope = {
            "preparation_id": prepared.preparation_id,
            "dynamic_certificate_id": dynamic.certificate_id,
            "response_id": response.response_id,
            "telemetry": response.telemetry.model_dump(mode="json"),
        }
        envelope_sha = self._writer.write_envelope(
            job_id=job_id,
            logical_request_index=logical_request_index,
            payload=envelope,
        )
        events.append("privacy_envelope_journal")
        if legacy.contains_private_reasoning(response.payload):
            projection_payload: dict[str, Any] = {
                "response_id": response.response_id,
                "status": "privacy_rejected",
                "payload": None,
            }
            projection_sha = self._writer.write_projection(
                job_id=job_id,
                logical_request_index=logical_request_index,
                payload=projection_payload,
            )
            events.append("privacy_projection_journal")
            raise ValueError(f"privacy response rejected:{projection_sha}")
        projection_payload = {
            "response_id": response.response_id,
            "status": "validated_public_payload",
            "payload": response.payload,
        }
        projection_sha = self._writer.write_projection(
            job_id=job_id,
            logical_request_index=logical_request_index,
            payload=projection_payload,
        )
        events.append("privacy_projection_journal")
        _canonical_bytes(response.payload)
        events.append("semantic_parse")
        receipt_values = {
            "preparation_id": prepared.preparation_id,
            "certified_response_id": response.response_id,
            "envelope_sha256": envelope_sha,
            "projection_sha256": projection_sha,
            "event_sequence": tuple(events),
            "provider_call_made": response.provider_call_made,
        }
        provisional_receipt = KernelInvocationReceipt.model_construct(
            receipt_id="pending", **receipt_values
        )
        receipt = KernelInvocationReceipt(
            receipt_id=_identity(
                provisional_receipt,
                "receipt_id",
                "authoritative_kernel_invocation_receipt:",
            ),
            **receipt_values,
        )
        self._receipts[job_id].append(receipt)
        ledger.transport_invocations += 1
        ledger.provider_calls += int(response.provider_call_made)
        ledger.cumulative_tokens += response.telemetry.total_tokens or 0
        return response.payload

    def complete_job(self, *, job_id: str) -> tuple[str, str]:
        receipts = tuple(item.receipt_id for item in self._receipts.get(job_id, ()))
        if not receipts:
            raise ValueError("completed Job lacks an invocation trace")
        raw_sha = self._writer.write_raw(
            job_id=job_id,
            payload={"job_id": job_id, "invocation_receipt_ids": receipts},
        )
        result_sha = self._writer.write_result(
            job_id=job_id,
            payload={"job_id": job_id, "raw_sha256": raw_sha, "terminal": "fixture_complete"},
        )
        return raw_sha, result_sha

    def assert_closed(self) -> None:
        self._writer.assert_no_orphans()


__all__ = [
    "AuthoritativeJsonExplicitExecutionKernel",
    "CertifiedClientResponse",
    "CertifiedKernelClient",
    "KernelDynamicRequestCertificate",
    "KernelInvocationReceipt",
    "KernelJournalWriter",
    "KernelResourceCertificate",
    "NoReplaceKernelJournalWriter",
    "PreparedKernelRequest",
    "ProductionStageOneClientAdapter",
]
