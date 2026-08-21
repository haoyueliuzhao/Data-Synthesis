from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any, Literal
from urllib.parse import urlparse

from trusted_synthesis.runtime.agent.client import (
    EmptyFinalContentError,
    LLMClientError,
    ReasoningBudgetExhaustedError,
    _estimate_cost,
    _optional_int,
    _safe_error_message,
    _strip_json_fence,
)
from trusted_synthesis.runtime.agent.prospective_thinking import (
    ThinkingRequiredOpenAICompatibleJsonClient,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    REDACTED_RESPONSE_ENVELOPE_VERSION,
    CompletionFailureKind,
    ProspectiveThinkingFailureArtifact,
    RedactedProviderResponseEnvelope,
    RedactedProviderResponseFields,
    capture_redacted_provider_response_fields,
    make_prospective_thinking_failure_artifact,
    require_admitted_response_envelope,
    serialize_validated_failure_artifact,
)
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry


class ProviderNativeToolCallError(ValueError):
    """A future Host-instrumented call observed a forbidden Provider-native tool call."""


class ProspectiveThinkingJsonClient(ThinkingRequiredOpenAICompatibleJsonClient):
    """Future-only client that freezes public response telemetry before content parsing."""

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        discovered: tuple[str, ...] = ()
        discovery_attempted = False
        if self.config.auto_discover_models:
            discovery_attempted = True
            try:
                discovered = self.discover_models()
            except LLMClientError:
                discovered = ()
        candidates = self._model_candidates(discovered)
        attempts: list[ModelCallTelemetry] = []
        failure_artifact: ProspectiveThinkingFailureArtifact | None = None
        for model in candidates[: self.config.maximum_model_attempts]:
            try:
                return self._complete_once(
                    prompt,
                    model=model,
                    discovery_attempted=discovery_attempted,
                    discovered_count=len(discovered),
                )
            except LLMClientError as exc:
                attempts.extend(exc.telemetry)
                if isinstance(exc.failure_artifact, ProspectiveThinkingFailureArtifact):
                    failure_artifact = exc.failure_artifact
        raise LLMClientError(
            "all configured model attempts failed",
            tuple(attempts),
            failure_artifact=failure_artifact,
        )

    def _complete_once(
        self,
        prompt: str,
        *,
        model: str,
        discovery_attempted: bool,
        discovered_count: int,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        config = self.config
        request_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config.temperature,
            "max_tokens": config.max_output_tokens,
            "response_format": {"type": "json_object"},
            **config.request_body_overrides,
        }
        request = urllib.request.Request(
            config.endpoint,
            data=json.dumps(body).encode("utf-8"),
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

            # Capture only allowed public fields before strict validation or content parsing.
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
            require_admitted_response_envelope(envelope, expected_model=model)

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
                model=model,
                status=status,
                envelope=envelope,
                redacted_fields=redacted_fields,
                prompt_tokens=prompt_tokens,
                prompt_cache_hit_tokens=prompt_cache_hit_tokens,
                prompt_cache_miss_tokens=prompt_cache_miss_tokens,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                cost_estimation_method=cost_estimation_method,
                discovery_attempted=discovery_attempted,
                discovered_count=discovered_count,
                started=started,
                json_contract_success=True,
            )
        except Exception as exc:
            if isinstance(exc, urllib.error.HTTPError):
                status = int(exc.code)
            telemetry = self._telemetry(
                request_hash=request_hash,
                model=model,
                status=status,
                envelope=envelope,
                redacted_fields=redacted_fields,
                prompt_tokens=prompt_tokens,
                prompt_cache_hit_tokens=prompt_cache_hit_tokens,
                prompt_cache_miss_tokens=prompt_cache_miss_tokens,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                cost_estimation_method=cost_estimation_method,
                discovery_attempted=discovery_attempted,
                discovered_count=discovered_count,
                started=started,
                json_contract_success=False,
                error=exc,
            )
            failure_artifact = self._failure_artifact(
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

    @staticmethod
    def _failure_artifact(
        *,
        error: Exception,
        request_hash: str,
        status: int | None,
        envelope: RedactedProviderResponseEnvelope | None,
    ) -> ProspectiveThinkingFailureArtifact | None:
        if status is None or not 200 <= status < 300:
            return None
        failure_type: (
            CompletionFailureKind
            | Literal["provider_native_tool_call", "response_envelope_invalid"]
        )
        if isinstance(error, ProviderNativeToolCallError):
            failure_type = "provider_native_tool_call"
        elif envelope is None:
            failure_type = "response_envelope_invalid"
        elif isinstance(error, ReasoningBudgetExhaustedError):
            failure_type = "reasoning_only_length_truncation"
        elif isinstance(error, EmptyFinalContentError):
            failure_type = "empty_final_content"
        elif isinstance(error, json.JSONDecodeError):
            failure_type = (
                "length_truncated_content" if envelope.finish_reason == "length" else "invalid_json"
            )
        elif isinstance(error, TypeError):
            failure_type = "invalid_response_contract"
        else:
            failure_type = "response_envelope_invalid"
        artifact = make_prospective_thinking_failure_artifact(
            failure_type=failure_type,
            request_hash=request_hash,
            response_envelope=envelope,
        )
        serialize_validated_failure_artifact(artifact)
        return artifact

    def _telemetry(
        self,
        *,
        request_hash: str,
        model: str,
        status: int | None,
        envelope: RedactedProviderResponseEnvelope | None,
        redacted_fields: RedactedProviderResponseFields | None,
        prompt_tokens: int | None,
        prompt_cache_hit_tokens: int | None,
        prompt_cache_miss_tokens: int | None,
        total_tokens: int | None,
        estimated_cost: float | None,
        cost_estimation_method: str | None,
        discovery_attempted: bool,
        discovered_count: int,
        started: float,
        json_contract_success: bool,
        error: Exception | None = None,
    ) -> ModelCallTelemetry:
        config = self.config
        envelope_payload = (
            envelope.model_dump(mode="json")
            if envelope is not None
            else dict(redacted_fields)
            if redacted_fields is not None
            else None
        )
        captured_response_model = (
            envelope.response_model
            if envelope is not None
            else redacted_fields["response_model"]
            if redacted_fields is not None
            else None
        )
        captured_finish_reason = (
            envelope.finish_reason
            if envelope is not None
            else redacted_fields["finish_reason"]
            if redacted_fields is not None
            else None
        )
        captured_content_sha256 = (
            envelope.public_content_sha256
            if envelope is not None
            else redacted_fields["public_content_sha256"]
            if redacted_fields is not None
            else None
        )
        captured_content_length = (
            envelope.public_content_length
            if envelope is not None
            else redacted_fields["public_content_length"]
            if redacted_fields is not None
            else None
        )
        captured_native_tool = (
            envelope.provider_native_tool_call_observed
            if envelope is not None
            else (
                redacted_fields["provider_native_tool_call_observed"]
                if redacted_fields is not None
                else None
            )
        )
        captured_reasoning_present = (
            envelope.reasoning_content_present
            if envelope is not None
            else redacted_fields["reasoning_content_present"]
            if redacted_fields is not None
            else None
        )
        captured_reasoning_length = (
            envelope.reasoning_content_length
            if envelope is not None
            else redacted_fields["reasoning_content_length"]
            if redacted_fields is not None
            else None
        )
        captured_reasoning_tokens = (
            envelope.reasoning_tokens
            if envelope is not None
            else redacted_fields["reasoning_tokens"]
            if redacted_fields is not None
            else None
        )
        captured_completion_tokens = (
            envelope.completion_tokens
            if envelope is not None
            else redacted_fields["completion_tokens"]
            if redacted_fields is not None
            else None
        )
        response_shape = {
            "provider_native_tool_call_observed": captured_native_tool,
            "redacted_response_envelope": envelope_payload,
            "response_envelope_captured_before_content_parse": redacted_fields is not None,
            "response_envelope_schema": (
                REDACTED_RESPONSE_ENVELOPE_VERSION if redacted_fields is not None else None
            ),
            "response_envelope_schema_valid": envelope is not None,
        }
        return ModelCallTelemetry(
            provider=config.provider,
            endpoint_host=urlparse(config.endpoint).netloc,
            model_requested=config.model,
            model_selected=model,
            response_model=captured_response_model,
            request_hash=request_hash,
            response_hash=captured_content_sha256,
            http_status=status,
            http_success=bool(status is not None and 200 <= status < 300),
            json_contract_success=json_contract_success,
            finish_reason=captured_finish_reason,
            response_content_length=captured_content_length,
            reasoning_content_present=bool(captured_reasoning_present),
            reasoning_content_length=captured_reasoning_length,
            reasoning_tokens=captured_reasoning_tokens,
            prompt_tokens=prompt_tokens,
            prompt_cache_hit_tokens=prompt_cache_hit_tokens,
            prompt_cache_miss_tokens=prompt_cache_miss_tokens,
            completion_tokens=captured_completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            cost_estimation_method=cost_estimation_method,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            fallback_used=model != config.model,
            discovery_attempted=discovery_attempted,
            discovered_model_count=discovered_count,
            error_type=(type(error).__name__ if error is not None else None),
            error_message=(_safe_error_message(error) if error is not None else None),
            response_shape=response_shape,
        )
