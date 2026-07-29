from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Protocol
from urllib.parse import urlparse, urlunparse

from trusted_synthesis.runtime.agent.schema import (
    AgentModelConfig,
    HostInteractionProgress,
    ModelCallTelemetry,
)

_CODE_FENCE = chr(96) * 3


class JsonCompletionClient(Protocol):
    @property
    def config(self) -> AgentModelConfig: ...

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]: ...


class LLMClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        telemetry: tuple[ModelCallTelemetry, ...] = (),
        *,
        failure_artifact: Any | None = None,
        interaction_progress: HostInteractionProgress | None = None,
    ) -> None:
        super().__init__(message)
        self.telemetry = telemetry
        self.failure_artifact = failure_artifact
        self.interaction_progress = interaction_progress


class OpenAICompatibleJsonClient:
    """JSON-only client with explicit model discovery and redacted telemetry."""

    def __init__(self, config: AgentModelConfig) -> None:
        self._config = config
        self._discovered_models: tuple[str, ...] | None = None
        self._discovery_lock = threading.Lock()
        self._api_key = os.environ.get(config.api_key_env, "")
        if not self._api_key:
            raise ValueError(f"missing model credential environment variable: {config.api_key_env}")

    @property
    def config(self) -> AgentModelConfig:
        return self._config

    def discover_models(self) -> tuple[str, ...]:
        if self._discovered_models is not None:
            return self._discovered_models
        with self._discovery_lock:
            if self._discovered_models is not None:
                return self._discovered_models
            endpoint = self._config.models_endpoint or _derive_models_endpoint(
                self._config.endpoint
            )
            request = urllib.request.Request(
                endpoint,
                headers=self._headers(),
                method="GET",
            )
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self._config.timeout_seconds,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except Exception as exc:
                raise LLMClientError(f"model discovery failed: {type(exc).__name__}") from exc
            self._discovered_models = tuple(
                sorted(
                    {
                        str(item.get("id")).strip()
                        for item in payload.get("data") or ()
                        if isinstance(item, dict) and str(item.get("id") or "").strip()
                    }
                )
            )
        return self._discovered_models

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        discovered: tuple[str, ...] = ()
        discovery_attempted = False
        if self._config.auto_discover_models:
            discovery_attempted = True
            try:
                discovered = self.discover_models()
            except LLMClientError:
                discovered = ()
        candidates = self._model_candidates(discovered)
        attempts: list[ModelCallTelemetry] = []
        for model in candidates[: self._config.maximum_model_attempts]:
            try:
                return self._complete_once(
                    prompt,
                    model=model,
                    discovery_attempted=discovery_attempted,
                    discovered_count=len(discovered),
                )
            except LLMClientError as exc:
                attempts.extend(exc.telemetry)
        raise LLMClientError("all configured model attempts failed", tuple(attempts))

    def _model_candidates(self, discovered: tuple[str, ...]) -> tuple[str, ...]:
        available = set(discovered)
        requested_available = not discovered or self._config.model in available
        if self._config.require_requested_model and not requested_available:
            raise LLMClientError(f"requested model is not listed by provider: {self._config.model}")
        ordered: list[str] = []

        def add(model: str) -> None:
            if model and model not in ordered and (not discovered or model in available):
                ordered.append(model)

        add(self._config.model)
        if not self._config.require_requested_model:
            for model in self._config.fallback_models:
                add(model)
            for pattern in self._config.preferred_model_patterns:
                for model in discovered:
                    if pattern.casefold() in model.casefold():
                        add(model)
        if not ordered:
            add(self._config.model)
        return tuple(ordered)

    def _complete_once(
        self,
        prompt: str,
        *,
        model: str,
        discovery_attempted: bool,
        discovered_count: int,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        request_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            self._config.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=self._headers(json_content=True),
            method="POST",
        )
        started = time.perf_counter()
        status: int | None = None
        content: str | None = None
        try:
            with urllib.request.urlopen(request, timeout=self._config.timeout_seconds) as response:
                status = int(getattr(response, "status", 200))
                response_body = json.loads(response.read().decode("utf-8"))
            content = str(response_body["choices"][0]["message"]["content"])
            parsed = json.loads(_strip_json_fence(content))
            if not isinstance(parsed, dict):
                raise TypeError("model response must be a JSON object")
            usage = dict(response_body.get("usage") or {})
            prompt_tokens = _optional_int(usage.get("prompt_tokens", usage.get("input_tokens")))
            completion_tokens = _optional_int(
                usage.get("completion_tokens", usage.get("output_tokens"))
            )
            total_tokens = _optional_int(usage.get("total_tokens"))
            if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
                total_tokens = prompt_tokens + completion_tokens
            telemetry = ModelCallTelemetry(
                provider=self._config.provider,
                endpoint_host=urlparse(self._config.endpoint).netloc,
                model_requested=self._config.model,
                model_selected=model,
                response_model=response_body.get("model"),
                request_hash=request_hash,
                response_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                http_status=status,
                http_success=True,
                json_contract_success=True,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost=_estimate_cost(
                    self._config,
                    prompt_tokens,
                    completion_tokens,
                ),
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                fallback_used=model != self._config.model,
                discovery_attempted=discovery_attempted,
                discovered_model_count=discovered_count,
            )
            return parsed, telemetry
        except Exception as exc:
            if isinstance(exc, urllib.error.HTTPError):
                status = int(exc.code)
            telemetry = ModelCallTelemetry(
                provider=self._config.provider,
                endpoint_host=urlparse(self._config.endpoint).netloc,
                model_requested=self._config.model,
                model_selected=model,
                request_hash=request_hash,
                response_hash=(
                    hashlib.sha256(content.encode("utf-8")).hexdigest()
                    if content is not None
                    else None
                ),
                http_status=status,
                http_success=False,
                json_contract_success=False,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                fallback_used=model != self._config.model,
                discovery_attempted=discovery_attempted,
                discovered_model_count=discovered_count,
                error_type=type(exc).__name__,
                error_message=_safe_error_message(exc),
            )
            raise LLMClientError(str(exc), (telemetry,)) from exc

    def _headers(self, *, json_content: bool = False) -> dict[str, str]:
        output = {
            **self._config.extra_headers,
            "Authorization": f"Bearer {self._api_key}",
        }
        if json_content:
            output["Content-Type"] = "application/json"
        return output


def _derive_models_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    path = re.sub(r"/(?:chat/completions|responses)/?$", "/models", parsed.path)
    if path == parsed.path:
        path = parsed.path.rstrip("/") + "/models"
    return urlunparse(parsed._replace(path=path, query="", fragment=""))


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith(_CODE_FENCE):
        stripped = stripped[len(_CODE_FENCE) :].lstrip()
        if stripped.casefold().startswith("json"):
            stripped = stripped[4:].lstrip()
        if stripped.endswith(_CODE_FENCE):
            stripped = stripped[: -len(_CODE_FENCE)].rstrip()
    return stripped


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _estimate_cost(
    config: AgentModelConfig,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> float | None:
    if prompt_tokens is None or completion_tokens is None:
        return None
    if not config.input_cost_per_million and not config.output_cost_per_million:
        return None
    return (
        prompt_tokens * config.input_cost_per_million
        + completion_tokens * config.output_cost_per_million
    ) / 1_000_000


def _safe_error_message(exc: Exception) -> str:
    return " ".join(f"{type(exc).__name__}: {exc}".split())[:500]
