from __future__ import annotations

import json
import urllib.request
from typing import Any

import pytest

from trusted_synthesis.runtime.agent.prospective_thinking import (
    PROSPECTIVE_THINKING_MODE_POLICY,
    ProspectiveThinkingModePolicy,
    ThinkingRequiredOpenAICompatibleJsonClient,
    bind_prospective_thinking,
    enable_prospective_thinking,
    require_prospective_thinking,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.status = 200
        self._payload = payload

    def __enter__(self) -> _FakeHttpResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _config(request_body_overrides: dict[str, Any]) -> AgentModelConfig:
    return AgentModelConfig(
        provider="deepseek",
        endpoint="https://api.deepseek.com/v1/chat/completions",
        models_endpoint="https://api.deepseek.com/models",
        model="deepseek-v4-flash",
        api_key_env="TEST_ONLY_DEEPSEEK_KEY",
        timeout_seconds=180,
        max_output_tokens=4096,
        temperature=0.6,
        maximum_model_attempts=1,
        contract_repair_attempts=1,
        auto_discover_models=False,
        require_requested_model=True,
        input_cache_hit_cost_per_million=0.0028,
        input_cache_miss_cost_per_million=0.14,
        output_cost_per_million=0.28,
        request_body_overrides=request_body_overrides,
        interaction_protocol="host_instrumented",
    )


def test_prospective_thinking_policy_round_trips_with_stable_identity() -> None:
    policy = ProspectiveThinkingModePolicy.model_validate_json(
        PROSPECTIVE_THINKING_MODE_POLICY.model_dump_json()
    )

    assert policy == PROSPECTIVE_THINKING_MODE_POLICY
    assert policy.policy_id.startswith("prospective_thinking_mode_policy:")
    assert policy.required_request_body_fragment == {"thinking": {"type": "enabled"}}
    assert policy.historical_provider_calls_in_scope is False
    assert policy.reasoning_tokens_count_toward_completion_usage is True


def test_enable_prospective_thinking_creates_a_new_config_and_binding() -> None:
    historical = _config({"thinking": {"type": "disabled"}, "top_p": 0.9})

    enabled = enable_prospective_thinking(historical)
    binding = bind_prospective_thinking(enabled)

    assert historical.request_body_overrides["thinking"] == {"type": "disabled"}
    assert enabled.request_body_overrides == {
        "thinking": {"type": "enabled"},
        "top_p": 0.9,
    }
    assert enabled.public_manifest_hash != historical.public_manifest_hash
    assert binding.model_config_id == enabled.public_manifest_hash
    assert binding.policy_id == PROSPECTIVE_THINKING_MODE_POLICY.policy_id
    assert binding.thinking_type == "enabled"


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"thinking": {"type": "disabled"}},
        {"thinking": "enabled"},
        {"thinking": {"type": "enabled", "budget": 4096}},
        {"Thinking": {"type": "enabled"}},
    ],
)
def test_prospective_thinking_rejects_missing_or_nonexact_config(
    overrides: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match="prospective model calls require"):
        require_prospective_thinking(_config(overrides))


def test_thinking_client_rejects_before_credential_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_ONLY_DEEPSEEK_KEY", raising=False)

    with pytest.raises(ValueError, match="thinking=\\{'type': 'enabled'\\}"):
        ThinkingRequiredOpenAICompatibleJsonClient(_config({"thinking": {"type": "disabled"}}))


def test_thinking_client_sends_enabled_request_and_retains_redacted_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_ONLY_DEEPSEEK_KEY", "test-secret")
    observed: dict[str, Any] = {}

    def fake_urlopen(request: urllib.request.Request, *, timeout: float):
        assert timeout == 180
        request_data = request.data
        assert isinstance(request_data, bytes)
        observed.update(json.loads(request_data))
        return _FakeHttpResponse(
            {
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": '{"ok": true}',
                            "reasoning_content": "private reasoning omitted",
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 40,
                    "total_tokens": 140,
                    "completion_tokens_details": {"reasoning_tokens": 32},
                },
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = ThinkingRequiredOpenAICompatibleJsonClient(
        _config({"thinking": {"type": "enabled"}, "top_p": 0.9})
    )

    payload, telemetry = client.complete_json("Return JSON.")

    assert payload == {"ok": True}
    assert observed["thinking"] == {"type": "enabled"}
    assert observed["max_tokens"] == 4096
    assert telemetry.reasoning_content_present is True
    assert telemetry.reasoning_tokens == 32
    assert telemetry.completion_tokens == 40
    assert client.thinking_mode_binding.model_config_id == client.config.public_manifest_hash
