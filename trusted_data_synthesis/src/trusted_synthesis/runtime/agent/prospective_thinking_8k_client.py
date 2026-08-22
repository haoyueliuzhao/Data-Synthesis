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

EXACT_8K_REQUEST_BINDING_VERSION: Final = "exact_8k_request_binding_certificate.v1"
EXACT_8K_PROFILE_PATH: Final = "config/deepseek_v4_flash_agent_thinking_8k_v1.json"
EXACT_8K_PROFILE_SHA256: Final = "efef0545f4a5467956ecdbcc3442341af1b4f158558d41f0b8e607859ef7d256"
EXACT_8K_MODEL_CONFIG_ID: Final = (
    "agent_model_config:c07d13207cba89d1e1cc3790151e2b5a32b7bf06f0ee6974f8e761fce5562b2e"
)
EXACT_8K_THINKING_BINDING_ID: Final = (
    "prospective_thinking_model_binding:"
    "9ed92eb9c7326eaf8b083633cda2e10cbfdb454322bcffffcd0d2f5e1329ac57"
)
EXACT_8K_MODEL_ID: Final = "deepseek-v4-flash"
EXACT_8K_MAX_TOKENS: Final = 8192


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Exact8KRequestBindingCertificate(FrozenModel):
    certificate_id: str = Field(min_length=1)
    profile_relative_path: Literal["config/deepseek_v4_flash_agent_thinking_8k_v1.json"] = (
        EXACT_8K_PROFILE_PATH
    )
    profile_sha256: str = Field(min_length=64, max_length=64)
    model_config_id: str = EXACT_8K_MODEL_CONFIG_ID
    thinking_binding_id: str = EXACT_8K_THINKING_BINDING_ID
    provider: Literal["deepseek"] = "deepseek"
    endpoint: Literal["https://api.deepseek.com/v1/chat/completions"] = (
        "https://api.deepseek.com/v1/chat/completions"
    )
    request_model: Literal["deepseek-v4-flash"] = EXACT_8K_MODEL_ID
    request_max_tokens: Literal[8192] = EXACT_8K_MAX_TOKENS
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
    schema_version: Literal["exact_8k_request_binding_certificate.v1"] = (
        EXACT_8K_REQUEST_BINDING_VERSION
    )

    @model_validator(mode="after")
    def validate_certificate(self) -> Exact8KRequestBindingCertificate:
        if (
            self.profile_sha256 != EXACT_8K_PROFILE_SHA256
            or self.model_config_id != EXACT_8K_MODEL_CONFIG_ID
            or self.thinking_binding_id != EXACT_8K_THINKING_BINDING_ID
        ):
            raise ValueError("exact 8K request certificate changed profile identity")
        if self.request_body_fields != tuple(sorted(self.request_body_fields)):
            raise ValueError("exact 8K request body fields are not canonical")
        if self.certificate_id != exact_8k_request_binding_certificate_id(self):
            raise ValueError("exact 8K request certificate identity mismatch")
        return self


def exact_8k_request_binding_certificate_id(
    value: Exact8KRequestBindingCertificate,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"certificate_id"}),
        prefix="exact_8k_request_binding_certificate:",
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


def require_exact_8k_model_config(config: AgentModelConfig) -> AgentModelConfig:
    binding = bind_prospective_thinking(config)
    if (
        config.public_manifest_hash != EXACT_8K_MODEL_CONFIG_ID
        or binding.binding_id != EXACT_8K_THINKING_BINDING_ID
        or config.provider != "deepseek"
        or config.endpoint != "https://api.deepseek.com/v1/chat/completions"
        or config.model != EXACT_8K_MODEL_ID
        or config.max_output_tokens != EXACT_8K_MAX_TOKENS
        or config.maximum_model_attempts != 1
        or config.fallback_models
        or not config.require_requested_model
        or config.interaction_protocol != "host_instrumented"
    ):
        raise ValueError("model config is not the persisted exact 8K route")
    return config


def make_exact_8k_request_body(
    config: AgentModelConfig,
    prompt: str,
) -> dict[str, Any]:
    require_exact_8k_model_config(config)
    if not prompt:
        raise ValueError("exact 8K Provider request requires a public Prompt")
    body = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config.temperature,
        "max_tokens": config.max_output_tokens,
        "response_format": {"type": "json_object"},
        **config.request_body_overrides,
    }
    if (
        body.get("model") != EXACT_8K_MODEL_ID
        or body.get("max_tokens") != EXACT_8K_MAX_TOKENS
        or body.get("thinking") != {"type": "enabled"}
        or body.get("response_format") != {"type": "json_object"}
    ):
        raise ValueError("actual Provider request body is not exact 8K Thinking JSON")
    return body


def certify_exact_8k_request_pre_call(
    *,
    config: AgentModelConfig,
    prompt: str,
    profile_sha256: str,
) -> Exact8KRequestBindingCertificate:
    body = make_exact_8k_request_body(config, prompt)
    body_bytes = _canonical_body_bytes(body)
    values = {
        "profile_sha256": profile_sha256,
        "prompt_sha256": _sha256_text(prompt),
        "canonical_request_body_sha256": hashlib.sha256(body_bytes).hexdigest(),
        "canonical_request_body_bytes": len(body_bytes),
        "request_body_fields": tuple(sorted(body)),
    }
    provisional = Exact8KRequestBindingCertificate.model_construct(
        certificate_id="pending",
        **values,
    )
    return Exact8KRequestBindingCertificate(
        certificate_id=exact_8k_request_binding_certificate_id(provisional),
        **values,
    )


class Exact8KProspectiveThinkingJsonClient(ProspectiveThinkingJsonClient):
    """Exact-route client that accepts only a matching pre-call request certificate."""

    def __init__(self, config: AgentModelConfig) -> None:
        require_exact_8k_model_config(config)
        super().__init__(config)

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        raise LLMClientError("exact 8K calls require a pre-call request binding certificate")

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
            raise LLMClientError("exact 8K request certificate differs from actual request body")
        return self._complete_once_certified(prompt, certificate)

    def _complete_once_certified(
        self,
        prompt: str,
        certificate: Exact8KRequestBindingCertificate,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        config = self.config
        request_hash = _sha256_text(prompt)
        body = make_exact_8k_request_body(config, prompt)
        body_bytes = _canonical_body_bytes(body)
        if (
            request_hash != certificate.prompt_sha256
            or hashlib.sha256(body_bytes).hexdigest() != certificate.canonical_request_body_sha256
        ):
            raise LLMClientError("certified exact 8K request bytes changed before invocation")
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
            require_admitted_response_envelope(envelope, expected_model=EXACT_8K_MODEL_ID)

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
                model=EXACT_8K_MODEL_ID,
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
                model=EXACT_8K_MODEL_ID,
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
