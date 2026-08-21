from __future__ import annotations

import json
import urllib.request
from typing import Any

import pytest

from trusted_synthesis.runtime.agent.client import LLMClientError
from trusted_synthesis.runtime.agent.prospective_thinking_client import (
    ProspectiveThinkingJsonClient,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    capture_redacted_provider_response_envelope,
    make_prospective_thinking_completion_protocol,
    make_prospective_thinking_failure_artifact,
    project_model_completion,
    render_primary_completion_prompt,
    render_rescue_completion_prompt,
    serialize_validated_failure_artifact,
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


def _config(*, thinking_type: str = "enabled") -> AgentModelConfig:
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
        contract_repair_attempts=0,
        auto_discover_models=False,
        require_requested_model=True,
        input_cache_hit_cost_per_million=0.0028,
        input_cache_miss_cost_per_million=0.14,
        output_cost_per_million=0.28,
        request_body_overrides={"thinking": {"type": thinking_type}},
        interaction_protocol="host_instrumented",
    )


def _provider_response(
    *,
    content: str,
    finish_reason: str = "stop",
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {
                    "content": content,
                    "reasoning_content": "do-not-persist-private-reasoning",
                    "tool_calls": tool_calls or [],
                },
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 4096 if finish_reason == "length" else 80,
            "total_tokens": 4196 if finish_reason == "length" else 180,
            "completion_tokens_details": {
                "reasoning_tokens": 4096 if finish_reason == "length" else 64
            },
        },
    }


def _decision_source_prompt() -> str:
    payload = {
        "public_context": {
            "prompt_protocol": "compact.v1",
            "task": {
                "instruction": "Resolve the public Finance operation.",
                "answer_schema": {"value": "number"},
                "mechanism_requirement_fields": ["evidence"],
                "retrieval": {"query_fields": ["metric"]},
            },
            "public_operation": {
                "variables": [{"symbol": "evidence_a"}],
                "nodes": [{"node_id": "leaf", "semantic_role": "retrieve"}],
            },
            "repair": {"identical_retry_forbidden": True},
            "stop": {"terminal_node_id": "leaf"},
            "terminal_verification": {"tool_id": "cross_check_evidence"},
            "tools": [{"tool_id": "query_structured_fact"}],
            "action_binding_fields_exposed": False,
        },
        "public_path_condition": "structured_direct",
        "progress": {
            "ready_nodes": [{"node_id": "leaf", "semantic_role": "retrieve"}],
            "terminal_node_completed": False,
        },
        "history": {
            "selected_evidence_ids": [],
            "acquisitions": [],
            "pending_search": None,
            "operations": [{"large_replayed_operation": "x" * 500}],
            "failed_actions": [],
        },
        "response_contract": {"rationale_summary_required": True},
    }
    return "Historical decision header\n" + json.dumps(payload, sort_keys=True)


def test_completion_protocol_round_trips_with_fixed_authority_and_budget() -> None:
    protocol = make_prospective_thinking_completion_protocol()
    reparsed = type(protocol).model_validate_json(protocol.model_dump_json())

    assert reparsed == protocol
    assert protocol.contract_id.startswith("prospective_thinking_completion_protocol:")
    assert protocol.model_plan_request_count == 0
    assert protocol.maximum_rescue_calls_per_job == 1
    assert protocol.minimum_rescue_prompt_reduction_basis_points == 1000
    assert protocol.rescue_is_independent_public_decision_terminal_phase
    assert not protocol.rescue_requests_repeated_planning_or_deliberation
    assert protocol.model_tool_choice_preserved
    assert protocol.model_argument_choice_preserved
    assert protocol.model_answer_choice_preserved


def test_primary_preserves_public_authority_and_rescue_is_shorter() -> None:
    source = _decision_source_prompt()
    primary = render_primary_completion_prompt("decision", source)
    rescue = render_rescue_completion_prompt(
        "decision",
        source,
        "reasoning_only_length_truncation",
    )
    primary_payload = json.loads(primary.partition("\n")[2])
    rescue_payload = json.loads(rescue.partition("\n")[2])

    assert primary_payload["public_context"]["public_operation"]
    assert primary_payload["public_context"]["tools"]
    assert primary_payload["response_contract"]["fields"] == [
        "action",
        "arguments",
        "tool_id",
    ]
    assert "rationale_summary" not in primary_payload["response_contract"]["fields"]
    assert rescue_payload["operation"] == primary_payload["public_context"]["public_operation"]
    assert rescue_payload["tools"] == primary_payload["public_context"]["tools"]
    assert "operations" not in rescue_payload["history"]
    assert rescue_payload["rescue"]["repeat_planning_or_deliberation"] is False
    assert len(rescue.encode("utf-8")) < len(primary.encode("utf-8")) * 0.9


def test_completion_projection_preserves_model_choices_and_rejects_host_fields() -> None:
    decision = project_model_completion(
        "decision",
        {
            "action": "call_tool",
            "arguments": {"evidence_id": "evidence:public"},
            "tool_id": "query_structured_fact",
            "rationale_summary": "discarded public summary",
        },
    )
    final = project_model_completion("final_answer", {"answer": {"value": 12.0}})

    assert decision.tool_id == "query_structured_fact"
    assert decision.arguments == {"evidence_id": "evidence:public"}
    assert decision.dropped_non_authority_fields == ("rationale_summary",)
    assert final.answer == {"value": 12.0}
    with pytest.raises(ValueError, match="forbidden public Completion field"):
        project_model_completion(
            "decision",
            {
                "action": "call_tool",
                "arguments": {},
                "tool_id": "query_structured_fact",
                "oracle": {"tool_id": "hidden"},
            },
        )


def test_redacted_envelope_and_failure_artifact_never_serialize_reasoning() -> None:
    response = _provider_response(content="{not-json")
    envelope = capture_redacted_provider_response_envelope(response)
    artifact = make_prospective_thinking_failure_artifact(
        failure_type="invalid_json",
        request_hash="a" * 64,
        response_envelope=envelope,
    )
    serialized = serialize_validated_failure_artifact(artifact)

    assert envelope.response_model == "deepseek-v4-flash"
    assert envelope.reasoning_content_present
    assert envelope.reasoning_content_length == len("do-not-persist-private-reasoning")
    assert b"do-not-persist-private-reasoning" not in serialized
    assert b'"reasoning_content"' not in serialized


def test_prospective_client_captures_envelope_before_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_ONLY_DEEPSEEK_KEY", "test-secret")
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeHttpResponse(_provider_response(content="{not-json")),
    )
    client = ProspectiveThinkingJsonClient(_config())

    with pytest.raises(LLMClientError) as caught:
        client.complete_json("Return JSON.")

    telemetry = caught.value.telemetry[0]
    failure_artifact = caught.value.failure_artifact
    assert telemetry.http_success
    assert telemetry.response_model == "deepseek-v4-flash"
    assert telemetry.error_type == "JSONDecodeError"
    assert telemetry.response_shape["response_envelope_captured_before_content_parse"] is True
    assert telemetry.response_shape["provider_native_tool_call_observed"] is False
    assert "do-not-persist-private-reasoning" not in telemetry.model_dump_json()
    assert failure_artifact is not None
    assert failure_artifact.failure_type == "invalid_json"
    assert "do-not-persist-private-reasoning" not in failure_artifact.model_dump_json()


def test_prospective_client_returns_success_with_redacted_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_ONLY_DEEPSEEK_KEY", "test-secret")
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeHttpResponse(_provider_response(content='{"ok":true}')),
    )

    payload, telemetry = ProspectiveThinkingJsonClient(_config()).complete_json("Return JSON.")

    assert payload == {"ok": True}
    assert telemetry.response_model == "deepseek-v4-flash"
    assert telemetry.json_contract_success
    assert telemetry.response_shape["response_envelope_captured_before_content_parse"] is True
    assert "do-not-persist-private-reasoning" not in telemetry.model_dump_json()


def test_prospective_client_types_an_invalid_response_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_ONLY_DEEPSEEK_KEY", "test-secret")
    malformed = _provider_response(content='{"ok":true}')
    malformed.pop("model")
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeHttpResponse(malformed),
    )

    with pytest.raises(LLMClientError) as caught:
        ProspectiveThinkingJsonClient(_config()).complete_json("Return JSON.")

    telemetry = caught.value.telemetry[0]
    failure_artifact = caught.value.failure_artifact
    assert telemetry.http_success
    assert telemetry.response_model is None
    assert failure_artifact is not None
    assert failure_artifact.failure_type == "response_envelope_invalid"
    assert failure_artifact.response_envelope is None


def test_prospective_client_retains_known_identity_when_usage_is_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_ONLY_DEEPSEEK_KEY", "test-secret")
    malformed = _provider_response(content='{"ok":true}')
    malformed.pop("usage")
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeHttpResponse(malformed),
    )

    with pytest.raises(LLMClientError) as caught:
        ProspectiveThinkingJsonClient(_config()).complete_json("Return JSON.")

    telemetry = caught.value.telemetry[0]
    assert telemetry.http_success
    assert telemetry.response_model == "deepseek-v4-flash"
    assert telemetry.response_shape["provider_native_tool_call_observed"] is False
    assert telemetry.response_shape["response_envelope_captured_before_content_parse"] is True
    assert telemetry.response_shape["response_envelope_schema_valid"] is False


def test_prospective_client_retains_reasoning_only_and_native_tool_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_ONLY_DEEPSEEK_KEY", "test-secret")
    responses = iter(
        (
            _provider_response(content="", finish_reason="length"),
            _provider_response(
                content='{"action":"call_tool"}',
                tool_calls=[{"id": "forbidden"}],
            ),
        )
    )
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeHttpResponse(next(responses)),
    )

    for expected_error, native_tool in (
        ("ReasoningBudgetExhaustedError", False),
        ("ProviderNativeToolCallError", True),
    ):
        with pytest.raises(LLMClientError) as caught:
            ProspectiveThinkingJsonClient(_config()).complete_json("Return JSON.")
        telemetry = caught.value.telemetry[0]
        failure_artifact = caught.value.failure_artifact
        assert telemetry.response_model == "deepseek-v4-flash"
        assert telemetry.error_type == expected_error
        assert telemetry.response_shape["provider_native_tool_call_observed"] is native_tool
        assert "do-not-persist-private-reasoning" not in telemetry.model_dump_json()
        assert failure_artifact is not None
        assert failure_artifact.failure_type == (
            "provider_native_tool_call" if native_tool else "reasoning_only_length_truncation"
        )


def test_prospective_client_rejects_disabled_thinking_before_credential_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_ONLY_DEEPSEEK_KEY", raising=False)
    with pytest.raises(ValueError, match="thinking=\\{'type': 'enabled'\\}"):
        ProspectiveThinkingJsonClient(_config(thinking_type="disabled"))
