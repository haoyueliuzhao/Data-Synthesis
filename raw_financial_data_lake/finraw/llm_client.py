from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class JsonCompletion:
    payload: dict[str, Any]
    telemetry: dict[str, Any]


class LLMClientError(RuntimeError):
    def __init__(self, message: str, telemetry: dict[str, Any]):
        super().__init__(message)
        self.telemetry = telemetry


class OpenAICompatibleJsonClient:
    """Small JSON-only client that never records prompts, responses, or credentials."""

    def __init__(self, config: dict[str, Any]):
        self.endpoint = str(config.get("endpoint") or "").strip()
        self.model = str(config.get("model") or "").strip()
        self.provider = str(config.get("provider") or "openai_compatible")
        self.key_env = str(config.get("api_key_env") or "OPENAI_API_KEY")
        self.api_key = os.environ.get(self.key_env, "")
        self.timeout = float(config.get("timeout_seconds", 30))
        self.input_cost_per_million = float(config.get("input_cost_per_million") or 0)
        self.output_cost_per_million = float(config.get("output_cost_per_million") or 0)
        if not self.endpoint or not self.model or not self.api_key:
            raise ValueError(
                "LLM endpoint, model, and API key environment variable are required"
            )

    def complete_json(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
    ) -> JsonCompletion:
        request_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        base = {
            "provider": self.provider,
            "endpoint_host": urlparse(self.endpoint).netloc,
            "model_requested": self.model,
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
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
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
            status = exc.code if isinstance(exc, urllib.error.HTTPError) else None
            telemetry = {
                **base,
                "latency_ms": elapsed,
                "http_status": status,
                "http_success": status is not None and 200 <= int(status) < 300,
                "error_type": type(exc).__name__,
            }
            raise LLMClientError(str(exc), telemetry) from exc
