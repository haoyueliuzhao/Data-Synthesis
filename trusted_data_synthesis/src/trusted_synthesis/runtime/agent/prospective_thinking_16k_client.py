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

EXACT_16K_REQUEST_BINDING_VERSION: Final = "exact_16k_request_binding_certificate.v1"
EXACT_16K_PROFILE_PATH: Final = "config/deepseek_v4_flash_agent_thinking_16k_v1.json"
EXACT_16K_PROFILE_SHA256: Final = "f820ec425d1763c74f6a93c4511d8f4ebf37761555a1e2a50c2b032f293b5ee6"
EXACT_16K_MODEL_CONFIG_ID: Final = (
    "agent_model_config:380395940dabe1a71eb175431b5c176b90e03b9c55a0c1a22a1de6cf46c1d437"
)
EXACT_16K_THINKING_BINDING_ID: Final = (
    "prospective_thinking_model_binding:"
    "4041c2b462023c7957e4d24e7b02b9d2968f2b686e9fef7f98799507ae87eae2"
)
EXACT_16K_MODEL_ID: Final = "deepseek-v4-flash"
EXACT_16K_MAX_TOKENS: Final = 16384


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Exact16KRequestBindingCertificate(FrozenModel):
    certificate_id: str = Field(min_length=1)
    profile_relative_path: Literal["config/deepseek_v4_flash_agent_thinking_16k_v1.json"] = (
        EXACT_16K_PROFILE_PATH
    )
    profile_sha256: str = Field(min_length=64, max_length=64)
    model_config_id: str = EXACT_16K_MODEL_CONFIG_ID
    thinking_binding_id: str = EXACT_16K_THINKING_BINDING_ID
    provider: Literal["deepseek"] = "deepseek"
    endpoint: Literal["https://api.deepseek.com/v1/chat/completions"] = (
        "https://api.deepseek.com/v1/chat/completions"
    )
    request_model: Literal["deepseek-v4-flash"] = EXACT_16K_MODEL_ID
    request_max_tokens: Literal[16384] = EXACT_16K_MAX_TOKENS
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
    schema_version: Literal["exact_16k_request_binding_certificate.v1"] = (
        EXACT_16K_REQUEST_BINDING_VERSION
    )

    @model_validator(mode="after")
    def validate_certificate(self) -> Exact16KRequestBindingCertificate:
        if (
            self.profile_sha256 != EXACT_16K_PROFILE_SHA256
            or self.model_config_id != EXACT_16K_MODEL_CONFIG_ID
            or self.thinking_binding_id != EXACT_16K_THINKING_BINDING_ID
        ):
            raise ValueError("exact 16K request certificate changed profile identity")
        if self.request_body_fields != tuple(sorted(self.request_body_fields)):
            raise ValueError("exact 16K request body fields are not canonical")
        if self.certificate_id != exact_16k_request_binding_certificate_id(self):
            raise ValueError("exact 16K request certificate identity mismatch")
        return self


def exact_16k_request_binding_certificate_id(
    value: Exact16KRequestBindingCertificate,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"certificate_id"}),
        prefix="exact_16k_request_binding_certificate:",
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


def require_exact_16k_model_config(config: AgentModelConfig) -> AgentModelConfig:
    binding = bind_prospective_thinking(config)
    if (
        config.public_manifest_hash != EXACT_16K_MODEL_CONFIG_ID
        or binding.binding_id != EXACT_16K_THINKING_BINDING_ID
        or config.provider != "deepseek"
        or config.endpoint != "https://api.deepseek.com/v1/chat/completions"
        or config.model != EXACT_16K_MODEL_ID
        or config.max_output_tokens != EXACT_16K_MAX_TOKENS
        or config.maximum_model_attempts != 1
        or config.fallback_models
        or not config.require_requested_model
        or config.interaction_protocol != "host_instrumented"
    ):
        raise ValueError("model config is not the persisted exact 16K route")
    return config


def make_exact_16k_request_body(
    config: AgentModelConfig,
    prompt: str,
) -> dict[str, Any]:
    require_exact_16k_model_config(config)
    if not prompt:
        raise ValueError("exact 16K Provider request requires a public Prompt")
    body = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config.temperature,
        "max_tokens": config.max_output_tokens,
        "response_format": {"type": "json_object"},
        **config.request_body_overrides,
    }
    if (
        body.get("model") != EXACT_16K_MODEL_ID
        or body.get("max_tokens") != EXACT_16K_MAX_TOKENS
        or body.get("thinking") != {"type": "enabled"}
        or body.get("response_format") != {"type": "json_object"}
    ):
        raise ValueError("actual Provider request body is not exact 16K Thinking JSON")
    return body


def certify_exact_16k_request_pre_call(
    *,
    config: AgentModelConfig,
    prompt: str,
    profile_sha256: str,
) -> Exact16KRequestBindingCertificate:
    body = make_exact_16k_request_body(config, prompt)
    body_bytes = _canonical_body_bytes(body)
    values = {
        "profile_sha256": profile_sha256,
        "prompt_sha256": _sha256_text(prompt),
        "canonical_request_body_sha256": hashlib.sha256(body_bytes).hexdigest(),
        "canonical_request_body_bytes": len(body_bytes),
        "request_body_fields": tuple(sorted(body)),
    }
    provisional = Exact16KRequestBindingCertificate.model_construct(
        certificate_id="pending",
        **values,
    )
    return Exact16KRequestBindingCertificate(
        certificate_id=exact_16k_request_binding_certificate_id(provisional),
        **values,
    )


class Exact16KProspectiveThinkingJsonClient(ProspectiveThinkingJsonClient):
    """Exact-route client that accepts only a matching pre-call request certificate."""

    def __init__(self, config: AgentModelConfig) -> None:
        require_exact_16k_model_config(config)
        super().__init__(config)

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        raise LLMClientError("exact 16K calls require a pre-call request binding certificate")

    def complete_json_certified(
        self,
        prompt: str,
        certificate: Exact16KRequestBindingCertificate,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        expected = certify_exact_16k_request_pre_call(
            config=self.config,
            prompt=prompt,
            profile_sha256=EXACT_16K_PROFILE_SHA256,
        )
        if certificate != expected:
            raise LLMClientError("exact 16K request certificate differs from actual request body")
        return self._complete_once_certified(prompt, certificate)

    def _complete_once_certified(
        self,
        prompt: str,
        certificate: Exact16KRequestBindingCertificate,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        config = self.config
        request_hash = _sha256_text(prompt)
        body = make_exact_16k_request_body(config, prompt)
        body_bytes = _canonical_body_bytes(body)
        if (
            request_hash != certificate.prompt_sha256
            or hashlib.sha256(body_bytes).hexdigest() != certificate.canonical_request_body_sha256
        ):
            raise LLMClientError("certified exact 16K request bytes changed before invocation")
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
        prompt_cache_hit_tokens: int | None = None
        prompt_cache_miss_tokens: int | None = None
        total_tokens: int | None = None
        estimated_cost: float | None = None
        cost_estimation_method: str | None = None
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
            prompt_cache_hit_tokens = _optional_int(usage.get("prompt_cache_hit_tokens"))
            prompt_cache_miss_tokens = _optional_int(usage.get("prompt_cache_miss_tokens"))
            total_tokens = _optional_int(usage.get("total_tokens"))
            if (
                total_tokens is None
                and prompt_tokens is not None
                and envelope.completion_tokens is not None
            ):
                total_tokens = prompt_tokens + envelope.completion_tokens
            estimated_cost, cost_estimation_method = _estimate_cost(
                config,
                prompt_tokens,
                envelope.completion_tokens,
                prompt_cache_hit_tokens=prompt_cache_hit_tokens,
                prompt_cache_miss_tokens=prompt_cache_miss_tokens,
            )
            if envelope.provider_native_tool_call_observed:
                raise ProviderNativeToolCallError(
                    "Provider-native tool calls are forbidden by the Host protocol"
                )
            require_admitted_response_envelope(envelope, expected_model=EXACT_16K_MODEL_ID)

            choices = response_body["choices"]
            choice = choices[0]
            message = choice["message"]
            raw_content = message.get("content")
            content = "" if raw_content is None else str(raw_content)
            if not content.strip():
                if envelope.finish_reason == "length" and envelope.reasoning_content_present:
                    raise ReasoningBudgetExhaustedError(
                        "model exhausted the output budget in reasoning before final content"
                    )
                raise EmptyFinalContentError("model returned an empty final content field")
            parsed = json.loads(_strip_json_fence(content))
            if not isinstance(parsed, dict):
                raise TypeError("model response must be a JSON object")
            return parsed, self._telemetry(
                request_hash=request_hash,
                model=EXACT_16K_MODEL_ID,
                status=status,
                envelope=envelope,
                redacted_fields=redacted_fields,
                prompt_tokens=prompt_tokens,
                prompt_cache_hit_tokens=prompt_cache_hit_tokens,
                prompt_cache_miss_tokens=prompt_cache_miss_tokens,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                cost_estimation_method=cost_estimation_method,
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
                model=EXACT_16K_MODEL_ID,
                status=status,
                envelope=envelope,
                redacted_fields=redacted_fields,
                prompt_tokens=prompt_tokens,
                prompt_cache_hit_tokens=prompt_cache_hit_tokens,
                prompt_cache_miss_tokens=prompt_cache_miss_tokens,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                cost_estimation_method=cost_estimation_method,
                discovery_attempted=False,
                discovered_count=0,
                started=started,
                json_contract_success=False,
                error=exc,
            )
            failure_artifact: ProspectiveThinkingFailureArtifact | None = self._failure_artifact(
                error=exc,
                request_hash=request_hash,
                status=status,
                envelope=envelope,
            )
            raise LLMClientError(
                str(exc),
                (telemetry,),
                failure_artifact=failure_artifact,
            ) from exc
