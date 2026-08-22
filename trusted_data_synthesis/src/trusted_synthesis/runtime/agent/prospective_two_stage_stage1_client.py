from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.client import (
    EmptyFinalContentError,
    LLMClientError,
    ReasoningBudgetExhaustedError,
    _estimate_cost,
    _optional_int,
    _strip_json_fence,
)
from trusted_synthesis.runtime.agent.prospective_thinking import bind_prospective_thinking
from trusted_synthesis.runtime.agent.prospective_thinking_client import (
    ProspectiveThinkingJsonClient,
    ProviderNativeToolCallError,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    ProspectiveThinkingFailureArtifact,
    RedactedProviderResponseEnvelope,
    RedactedProviderResponseFields,
    capture_redacted_provider_response_fields,
    require_admitted_response_envelope,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

STAGE_ONE_REQUEST_BINDING_VERSION: Final = "two_stage_stage_one_request_certificate.v1"
STAGE_ONE_PROFILE_PATH: Final = (
    "config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
)
STAGE_ONE_PROFILE_SHA256: Final = "2043fac92b0ef286c368091eb2ec424489dd94e5b6bdf5954810ecdca403615f"
STAGE_ONE_MODEL_CONFIG_ID: Final = (
    "agent_model_config:05eb110b4269f3a569d24918f356cb905d871aace45b9024c4575295b05a1015"
)
STAGE_ONE_THINKING_BINDING_ID: Final = (
    "prospective_thinking_model_binding:"
    "5afdd81c4318c89d5c31f9398e77b28822eb338578c2bc3533ed77d6291d33c8"
)
STAGE_ONE_PROFILE_ID: Final = (
    "finance_v26_stage_one_thinking_profile:"
    "9d89a504a3fee25a60ae392e10cab063b0604f36fb0672e19bc8f1ec45bb3045"
)
STAGE_TWO_PROFILE_ID: Final = (
    "finance_v26_stage_two_commit_profile:"
    "024f2543b11f26ebc40000c7342d6ff6b4067d78b3dc11be466514fc765734a5"
)
ACTION_PROTOCOL_ID: Final = (
    "prospective_action_constructibility_protocol:"
    "a5e293c0445f174813895f17888b3df4ab2e8223e9e4739440524892c8325565"
)
STAGE_ONE_MODEL_ID: Final = "deepseek-v4-flash"
STAGE_ONE_MAX_TOKENS: Final = 16384

StageOneRequestKind = Literal["semantic_proposal", "final_answer"]
StageOneAttemptPhase = Literal["primary", "rescue"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StageOneRequestBindingCertificate(FrozenModel):
    certificate_id: str = Field(min_length=1)
    stage_one_profile_id: str = STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = STAGE_TWO_PROFILE_ID
    action_constructibility_protocol_id: str = ACTION_PROTOCOL_ID
    profile_relative_path: str = STAGE_ONE_PROFILE_PATH
    profile_sha256: str = Field(min_length=64, max_length=64)
    model_config_id: str = STAGE_ONE_MODEL_CONFIG_ID
    thinking_binding_id: str = STAGE_ONE_THINKING_BINDING_ID
    request_kind: StageOneRequestKind
    phase: StageOneAttemptPhase
    provider: Literal["deepseek"] = "deepseek"
    endpoint: Literal["https://api.deepseek.com/v1/chat/completions"] = (
        "https://api.deepseek.com/v1/chat/completions"
    )
    request_model: Literal["deepseek-v4-flash"] = STAGE_ONE_MODEL_ID
    request_max_tokens: Literal[16384] = STAGE_ONE_MAX_TOKENS
    thinking_type: Literal["enabled"] = "enabled"
    response_format_type: Literal["json_object"] = "json_object"
    prompt_sha256: str = Field(min_length=64, max_length=64)
    canonical_request_body_sha256: str = Field(min_length=64, max_length=64)
    canonical_request_body_bytes: int = Field(gt=0)
    request_body_fields: tuple[str, ...]
    exact_model_route: Literal[True] = True
    fallback_forbidden: Literal[True] = True
    model_discovery_call_required: Literal[False] = False
    provider_calls_for_request_before_certificate: Literal[0] = 0
    provider_invocation_authorized_after_certificate: Literal[True] = True
    raw_request_body_persisted: Literal[False] = False
    schema_version: Literal["two_stage_stage_one_request_certificate.v1"] = (
        STAGE_ONE_REQUEST_BINDING_VERSION
    )

    @model_validator(mode="after")
    def validate_certificate(self) -> StageOneRequestBindingCertificate:
        if (
            self.profile_sha256 != STAGE_ONE_PROFILE_SHA256
            or self.model_config_id != STAGE_ONE_MODEL_CONFIG_ID
            or self.thinking_binding_id != STAGE_ONE_THINKING_BINDING_ID
        ):
            raise ValueError("Stage 1 request certificate changed the exact profile identity")
        if self.request_body_fields != tuple(sorted(self.request_body_fields)):
            raise ValueError("Stage 1 request body fields are not canonical")
        if self.certificate_id != stage_one_request_binding_certificate_id(self):
            raise ValueError("Stage 1 request certificate identity changed")
        return self


def stage_one_request_binding_certificate_id(
    value: StageOneRequestBindingCertificate,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"certificate_id"}),
        prefix="two_stage_stage_one_request_certificate:",
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_body_bytes(body: Mapping[str, Any]) -> bytes:
    return json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def require_stage_one_model_config(config: AgentModelConfig) -> AgentModelConfig:
    binding = bind_prospective_thinking(config)
    if (
        config.public_manifest_hash != STAGE_ONE_MODEL_CONFIG_ID
        or binding.binding_id != STAGE_ONE_THINKING_BINDING_ID
        or config.provider != "deepseek"
        or config.endpoint != "https://api.deepseek.com/v1/chat/completions"
        or config.model != STAGE_ONE_MODEL_ID
        or config.max_output_tokens != STAGE_ONE_MAX_TOKENS
        or config.maximum_model_attempts != 1
        or config.contract_repair_attempts != 0
        or config.auto_discover_models
        or config.fallback_models
        or not config.require_requested_model
        or config.interaction_protocol != "host_instrumented"
    ):
        raise ValueError("model config is not the persisted two-stage Stage 1 route")
    return config


def make_stage_one_request_body(
    config: AgentModelConfig,
    prompt: str,
) -> dict[str, Any]:
    require_stage_one_model_config(config)
    if not prompt:
        raise ValueError("Stage 1 Provider request requires a public Prompt")
    body = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config.temperature,
        "max_tokens": config.max_output_tokens,
        "response_format": {"type": "json_object"},
        **config.request_body_overrides,
    }
    if (
        body.get("model") != STAGE_ONE_MODEL_ID
        or body.get("max_tokens") != STAGE_ONE_MAX_TOKENS
        or body.get("thinking") != {"type": "enabled"}
        or body.get("response_format") != {"type": "json_object"}
    ):
        raise ValueError("actual Provider request body is not exact Stage 1 Thinking JSON")
    return body


def certify_stage_one_request_pre_call(
    *,
    config: AgentModelConfig,
    prompt: str,
    request_kind: StageOneRequestKind,
    phase: StageOneAttemptPhase,
) -> StageOneRequestBindingCertificate:
    body = make_stage_one_request_body(config, prompt)
    body_bytes = _canonical_body_bytes(body)
    values: dict[str, Any] = {
        "profile_sha256": STAGE_ONE_PROFILE_SHA256,
        "request_kind": request_kind,
        "phase": phase,
        "prompt_sha256": _sha256_text(prompt),
        "canonical_request_body_sha256": hashlib.sha256(body_bytes).hexdigest(),
        "canonical_request_body_bytes": len(body_bytes),
        "request_body_fields": tuple(sorted(body)),
    }
    provisional = StageOneRequestBindingCertificate.model_construct(
        certificate_id="pending",
        **values,
    )
    return StageOneRequestBindingCertificate(
        certificate_id=stage_one_request_binding_certificate_id(provisional),
        **values,
    )


class StageOneProspectiveThinkingJsonClient(ProspectiveThinkingJsonClient):
    """Exact Stage 1 route; every call requires a single-use external authorization."""

    def __init__(self, config: AgentModelConfig) -> None:
        require_stage_one_model_config(config)
        super().__init__(config)

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        raise LLMClientError("Stage 1 calls require a pre-call request binding certificate")

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
        if certificate != expected:
            raise LLMClientError("Stage 1 request certificate differs from actual request body")
        return self._complete_once_certified(prompt, certificate)

    def _complete_once_certified(
        self,
        prompt: str,
        certificate: StageOneRequestBindingCertificate,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        config = self.config
        request_hash = _sha256_text(prompt)
        body_bytes = _canonical_body_bytes(make_stage_one_request_body(config, prompt))
        if (
            request_hash != certificate.prompt_sha256
            or hashlib.sha256(body_bytes).hexdigest() != certificate.canonical_request_body_sha256
        ):
            raise LLMClientError("certified Stage 1 request bytes changed before invocation")
        request = urllib.request.Request(
            config.endpoint,
            data=body_bytes,
            headers=self._headers(json_content=True),
            method="POST",
        )
        started = time.perf_counter()
        status: int | None = None
        envelope: RedactedProviderResponseEnvelope | None = None
        redacted_fields: RedactedProviderResponseFields | None = None
        prompt_tokens: int | None = None
        cache_hit: int | None = None
        cache_miss: int | None = None
        total_tokens: int | None = None
        estimated_cost: float | None = None
        cost_method: str | None = None
        try:
            with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
                status = int(getattr(response, "status", 200))
                response_body = json.loads(response.read().decode("utf-8"))
            if not isinstance(response_body, Mapping):
                raise TypeError("HTTP-success response body must be a JSON object")
            redacted_fields = capture_redacted_provider_response_fields(response_body)
            envelope = RedactedProviderResponseEnvelope.model_validate(redacted_fields)
            usage = response_body.get("usage")
            if not isinstance(usage, Mapping):
                raise ValueError("HTTP-success response lacks Usage")
            prompt_tokens = _optional_int(usage.get("prompt_tokens", usage.get("input_tokens")))
            cache_hit = _optional_int(usage.get("prompt_cache_hit_tokens"))
            cache_miss = _optional_int(usage.get("prompt_cache_miss_tokens"))
            total_tokens = _optional_int(usage.get("total_tokens"))
            if total_tokens is None and prompt_tokens is not None and envelope.completion_tokens:
                total_tokens = prompt_tokens + envelope.completion_tokens
            estimated_cost, cost_method = _estimate_cost(
                config,
                prompt_tokens,
                envelope.completion_tokens,
                prompt_cache_hit_tokens=cache_hit,
                prompt_cache_miss_tokens=cache_miss,
            )
            if envelope.provider_native_tool_call_observed:
                raise ProviderNativeToolCallError(
                    "Provider-native tool calls are forbidden by the Host protocol"
                )
            require_admitted_response_envelope(envelope, expected_model=STAGE_ONE_MODEL_ID)
            message = response_body["choices"][0]["message"]
            raw_content = message.get("content")
            content = "" if raw_content is None else str(raw_content)
            if not content.strip():
                if envelope.finish_reason == "length" and envelope.reasoning_content_present:
                    raise ReasoningBudgetExhaustedError(
                        "model exhausted the Stage 1 output budget in reasoning"
                    )
                raise EmptyFinalContentError("model returned an empty Stage 1 content field")
            parsed = json.loads(_strip_json_fence(content))
            if not isinstance(parsed, dict):
                raise TypeError("Stage 1 response must be a JSON object")
            return parsed, self._telemetry(
                request_hash=request_hash,
                model=STAGE_ONE_MODEL_ID,
                status=status,
                envelope=envelope,
                redacted_fields=redacted_fields,
                prompt_tokens=prompt_tokens,
                prompt_cache_hit_tokens=cache_hit,
                prompt_cache_miss_tokens=cache_miss,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                cost_estimation_method=cost_method,
                discovery_attempted=False,
                discovered_count=0,
                started=started,
                json_contract_success=True,
            )
        except Exception as exc:
            if isinstance(exc, urllib.error.HTTPError):
                status = int(exc.code)
            telemetry = self._telemetry(
                request_hash=request_hash,
                model=STAGE_ONE_MODEL_ID,
                status=status,
                envelope=envelope,
                redacted_fields=redacted_fields,
                prompt_tokens=prompt_tokens,
                prompt_cache_hit_tokens=cache_hit,
                prompt_cache_miss_tokens=cache_miss,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                cost_estimation_method=cost_method,
                discovery_attempted=False,
                discovered_count=0,
                started=started,
                json_contract_success=False,
                error=exc,
            )
            failure: ProspectiveThinkingFailureArtifact | None = self._failure_artifact(
                error=exc,
                request_hash=request_hash,
                status=status,
                envelope=envelope,
            )
            raise LLMClientError(
                str(exc),
                (telemetry,),
                failure_artifact=failure,
            ) from exc
