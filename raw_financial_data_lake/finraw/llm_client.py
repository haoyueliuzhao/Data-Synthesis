from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse


_MODEL_DISCOVERY_CACHE: dict[str, tuple[float, list[str]]] = {}
_MODEL_SUCCESS_CACHE: dict[str, str] = {}


@dataclass(frozen=True)
class JsonCompletion:
    payload: dict[str, Any]
    telemetry: dict[str, Any]


class LLMClientError(RuntimeError):
    def __init__(self, message: str, telemetry: dict[str, Any]):
        super().__init__(message)
        self.telemetry = telemetry


class OpenAICompatibleJsonClient:
    """JSON-only client with model discovery/fallback and redacted telemetry."""

    def __init__(self, config: dict[str, Any]):
        self.endpoint = str(config.get("endpoint") or "").strip()
        self.model = str(config.get("model") or "").strip()
        self.provider = str(config.get("provider") or "openai_compatible")
        self.key_env = str(config.get("api_key_env") or "DASHSCOPE_API_KEY")
        self.api_key = os.environ.get(self.key_env, "")
        self.timeout = float(config.get("timeout_seconds", 30))
        self.max_output_tokens = max(int(config.get("max_output_tokens", 2048)), 1)
        self.reasoning_effort = str(config.get("reasoning_effort") or "").strip()
        thinking = config.get("thinking")
        if isinstance(thinking, str):
            thinking = {"type": thinking}
        self.thinking = dict(thinking) if isinstance(thinking, dict) else None
        if self.thinking is not None and self.thinking.get("type") not in {
            "enabled",
            "disabled",
        }:
            raise ValueError("thinking.type must be enabled or disabled")
        self.store = bool(config["store"]) if "store" in config else None
        self.http_headers = {
            str(key): str(value)
            for key, value in dict(config.get("http_headers") or {}).items()
        }
        self.input_cost_per_million = float(config.get("input_cost_per_million") or 0)
        self.output_cost_per_million = float(config.get("output_cost_per_million") or 0)
        self.auto_select_model = bool(config.get("auto_select_model", False))
        self.models_endpoint = str(config.get("models_endpoint") or "").strip()
        self.fallback_models = tuple(
            str(item).strip()
            for item in config.get("fallback_models") or []
            if str(item).strip()
        )
        self.preferred_model_patterns = tuple(
            str(item).strip()
            for item in config.get("preferred_model_patterns")
            or ["qwen-plus", "qwen-turbo", "qwen-max", "qwen3"]
            if str(item).strip()
        )
        self.maximum_model_attempts = max(
            int(config.get("maximum_model_attempts", 3)), 1
        )
        self.model_discovery_cache_seconds = max(
            float(config.get("model_discovery_cache_seconds", 3600)), 0
        )
        self.fallback_http_statuses = {
            int(item)
            for item in config.get("fallback_http_statuses") or [400, 403, 404, 429]
        }
        if not self.endpoint or not self.model or not self.api_key:
            raise ValueError(
                "LLM endpoint, model, and API key environment variable are required"
            )

    def discover_models(self) -> tuple[list[str], dict[str, Any]]:
        endpoint = self.models_endpoint or _derive_models_endpoint(self.endpoint)
        cache_key = self._cache_key(endpoint)
        cached = _MODEL_DISCOVERY_CACHE.get(cache_key)
        if cached and time.time() - cached[0] <= self.model_discovery_cache_seconds:
            return list(cached[1]), {
                "model_discovery_attempted": False,
                "model_discovery_success": True,
                "model_discovery_cache_hit": True,
                "models_endpoint_host": urlparse(endpoint).netloc,
                "discovered_model_count": len(cached[1]),
                "error_type": None,
            }
        telemetry = {
            "model_discovery_attempted": True,
            "model_discovery_success": False,
            "model_discovery_cache_hit": False,
            "models_endpoint_host": urlparse(endpoint).netloc,
            "discovered_model_count": 0,
            "error_type": None,
        }
        request = urllib.request.Request(
            endpoint,
            headers=self._request_headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            models = sorted(
                {
                    str(item.get("id")).strip()
                    for item in payload.get("data") or []
                    if isinstance(item, dict) and str(item.get("id") or "").strip()
                }
            )
            _MODEL_DISCOVERY_CACHE[cache_key] = (time.time(), list(models))
            return models, {
                **telemetry,
                "model_discovery_success": True,
                "discovered_model_count": len(models),
            }
        except Exception as exc:
            return [], {**telemetry, "error_type": type(exc).__name__}

    def complete_json(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
    ) -> JsonCompletion:
        request_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        discovered_models: list[str] = []
        discovery_telemetry = {
            "model_discovery_attempted": False,
            "model_discovery_success": False,
            "discovered_model_count": 0,
            "error_type": None,
        }
        if self.auto_select_model:
            discovered_models, discovery_telemetry = self.discover_models()
        candidates = self._model_candidates(discovered_models)
        attempts: list[dict[str, Any]] = []
        last_error: Exception | None = None
        for model in candidates[: self.maximum_model_attempts]:
            try:
                completion = self._complete_once(
                    prompt,
                    model=model,
                    temperature=temperature,
                    request_hash=request_hash,
                )
                _MODEL_SUCCESS_CACHE[self._cache_key(self.endpoint)] = model
                return JsonCompletion(
                    completion.payload,
                    {
                        **completion.telemetry,
                        "model_attempt_count": len(attempts) + 1,
                        "attempted_models": [
                            *[item["model"] for item in attempts],
                            model,
                        ],
                        "model_fallback_used": model != self.model,
                        "model_discovery": discovery_telemetry,
                    },
                )
            except LLMClientError as exc:
                last_error = exc
                status = exc.telemetry.get("http_status")
                attempts.append(
                    {
                        "model": model,
                        "http_status": status,
                        "error_type": exc.telemetry.get("error_type"),
                        "http_success": bool(
                            exc.telemetry.get("http_success")
                        ),
                    }
                )
                if status not in self.fallback_http_statuses:
                    break
        telemetry = {
            "provider": self.provider,
            "endpoint_host": urlparse(self.endpoint).netloc,
            "model_requested": self.model,
            "request_hash": request_hash,
            "request_count": len(attempts),
            "http_success": any(
                bool(item.get("http_success")) for item in attempts
            ),
            "json_valid": False,
            "http_status": attempts[-1]["http_status"] if attempts else None,
            "latency_ms": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "estimated_cost": None,
            "cost_estimation_configured": bool(
                self.input_cost_per_million or self.output_cost_per_million
            ),
            "response_id": None,
            "response_model": None,
            "response_hash": None,
            "error_type": (
                attempts[-1]["error_type"]
                if attempts
                else type(last_error).__name__
                if last_error
                else "NoModelCandidate"
            ),
            "model_attempt_count": len(attempts),
            "attempted_models": [item["model"] for item in attempts],
            "model_fallback_used": False,
            "model_discovery": discovery_telemetry,
        }
        raise LLMClientError(
            "All configured LLM models failed", telemetry
        ) from last_error

    def _model_candidates(self, discovered_models: list[str]) -> list[str]:
        output: list[str] = []

        def add(model: str) -> None:
            if model and model not in output and _chat_model_candidate(model):
                output.append(model)

        # A cached success is only a routing hint when fallback/discovery is enabled.
        # Strict model trials must never inherit another client's endpoint cache.
        if self.auto_select_model or self.fallback_models:
            add(_MODEL_SUCCESS_CACHE.get(self._cache_key(self.endpoint), ""))
        add(self.model)
        for model in self.fallback_models:
            add(model)
        ranked = sorted(
            discovered_models,
            key=lambda model: (
                _model_preference(model, self.preferred_model_patterns),
                model,
            ),
        )
        for model in ranked:
            add(model)
        return output or [self.model]

    def _cache_key(self, endpoint: str) -> str:
        credential_fingerprint = hashlib.sha256(
            self.api_key.encode("utf-8")
        ).hexdigest()
        return hashlib.sha256(
            f"{self.provider}|{endpoint}|{credential_fingerprint}".encode("utf-8")
        ).hexdigest()

    def _request_headers(self, *, json_content: bool = False) -> dict[str, str]:
        headers = {
            **self.http_headers,
            "Authorization": f"Bearer {self.api_key}",
        }
        if json_content:
            headers["Content-Type"] = "application/json"
        return headers

    def _complete_once(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float,
        request_hash: str,
    ) -> JsonCompletion:
        base = {
            "provider": self.provider,
            "endpoint_host": urlparse(self.endpoint).netloc,
            "model_requested": self.model,
            "model_selected": model,
            "request_hash": request_hash,
            "request_count": 1,
            "http_success": False,
            "json_valid": False,
            "http_status": None,
            "latency_ms": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "estimated_cost": None,
            "cost_estimation_configured": bool(
                self.input_cost_per_million or self.output_cost_per_million
            ),
            "response_id": None,
            "response_model": None,
            "response_hash": None,
            "error_type": None,
        }
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": self.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        if self.thinking is not None:
            body["thinking"] = self.thinking
        if self.reasoning_effort and (
            self.thinking is None or self.thinking.get("type") != "disabled"
        ):
            body["reasoning_effort"] = self.reasoning_effort
        if self.store is not None:
            body["store"] = self.store
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=self._request_headers(json_content=True),
            method="POST",
        )
        started = time.perf_counter()
        response_status: int | None = None
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response_status = int(getattr(response, "status", 200))
                raw = response.read().decode("utf-8")
                elapsed = round((time.perf_counter() - started) * 1000, 3)
                response_body = json.loads(raw)
                content = str(response_body["choices"][0]["message"]["content"])
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    raise TypeError("LLM JSON response must be an object")
                usage = dict(response_body.get("usage") or {})
                prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
                completion_tokens = usage.get(
                    "completion_tokens", usage.get("output_tokens")
                )
                total_tokens = usage.get("total_tokens")
                if (
                    total_tokens is None
                    and prompt_tokens is not None
                    and completion_tokens is not None
                ):
                    total_tokens = int(prompt_tokens) + int(completion_tokens)
                estimated_cost = None
                if (
                    prompt_tokens is not None
                    and completion_tokens is not None
                    and (self.input_cost_per_million or self.output_cost_per_million)
                ):
                    estimated_cost = (
                        float(prompt_tokens) * self.input_cost_per_million
                        + float(completion_tokens) * self.output_cost_per_million
                    ) / 1_000_000
                telemetry = {
                    **base,
                    "http_success": True,
                    "json_valid": True,
                    "http_status": int(getattr(response, "status", 200)),
                    "latency_ms": elapsed,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "estimated_cost": estimated_cost,
                    "response_id": response_body.get("id"),
                    "response_model": response_body.get("model"),
                    "response_hash": hashlib.sha256(
                        content.encode("utf-8")
                    ).hexdigest(),
                }
                return JsonCompletion(parsed, telemetry)
        except Exception as exc:
            elapsed = round((time.perf_counter() - started) * 1000, 3)
            status = (
                exc.code
                if isinstance(exc, urllib.error.HTTPError)
                else response_status
            )
            telemetry = {
                **base,
                "latency_ms": elapsed,
                "http_status": status,
                "http_success": status is not None and 200 <= int(status) < 300,
                "error_type": type(exc).__name__,
            }
            raise LLMClientError(str(exc), telemetry) from exc


def _derive_models_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    path = re.sub(r"/(?:chat/completions|responses)/?$", "/models", parsed.path)
    if path == parsed.path:
        path = parsed.path.rstrip("/") + "/models"
    return urlunparse(parsed._replace(path=path, query="", fragment=""))


def _chat_model_candidate(model: str) -> bool:
    lowered = model.casefold()
    excluded = (
        "embedding",
        "rerank",
        "image",
        "audio",
        "speech",
        "tts",
        "whisper",
        "video",
        "wan",
    )
    return not any(token in lowered for token in excluded)


def _model_preference(model: str, patterns: tuple[str, ...]) -> tuple[int, int]:
    lowered = model.casefold()
    for index, pattern in enumerate(patterns):
        if pattern.casefold() in lowered:
            return index, len(model)
    return len(patterns), len(model)
