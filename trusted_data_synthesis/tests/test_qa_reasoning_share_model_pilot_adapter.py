"""Isolated adapter seams only: every HTTP operation is mocked, no complete sessions."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import adapter, models
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol import models as core
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol import public_view

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = "SYNTHETIC_PRIVATE_REASONING_CANARY_DO_NOT_RECORD"
VALID = canonical_json_bytes(
    {
        "kind": "action",
        "state_id": "unit-state",
        "operation": "share_ratio",
        "inputs": [],
        "parameters": {},
        "public_basis": {
            "relation": "requires",
            "evidence_refs": [],
            "claim_refs": [],
            "intended_metric": "unit_metric",
        },
    }
).decode("utf-8")


@pytest.fixture(scope="module")
def public_request() -> dict[str, Any]:
    # Read historical source facts, but do not execute source building or a kernel/session.
    directory = ROOT / core.PARENT
    source = json.loads((directory / "source_binding.json").read_bytes())
    contract = json.loads((directory / "contract.json").read_bytes())
    context = public_view.public_context(source, contract)
    protocol = models.protocol_contract(core.protocol_contract(context), models.model_config())
    state = public_view.make_state(context, protocol, core.initial_dynamic())
    return public_view.request_for(state, protocol)


@pytest.fixture
def request_record(public_request: dict[str, Any]) -> dict[str, Any]:
    return adapter.render_http_request(
        public_request,
        models.model_config(),
        session_id="unit-session",
        turn_index=0,
        call_id="unit-call",
    )


def envelope(content: Any = VALID, **changes: Any) -> bytes:
    value = {
        "id": "unit-provider-response",
        "model": "deepseek-v4-pro",
        "object": "chat.completion",
        "system_fingerprint": "unit-fingerprint",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": content,
                    "reasoning_content": PRIVATE,
                },
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 40,
            "total_tokens": 140,
            "completion_tokens_details": {"reasoning_tokens": 0},
        },
        **changes,
    }
    return canonical_json_bytes(value)


def observe(request: dict[str, Any], body: bytes) -> dict[str, Any]:
    subject = adapter.DeepSeekAdapter(
        models.model_config(),
        transport=adapter.MockTransport(lambda _: {"http_status": 200, "body": body}),
    )
    return subject.perform(request, reserve=lambda _: {"id": "unit-reservation"})


def test_wire_body_is_deterministic_exact_public_request_without_second_schema(
    public_request: dict[str, Any],
    request_record: dict[str, Any],
) -> None:
    assert request_record == adapter.render_http_request(
        public_request,
        models.model_config(),
        session_id="unit-session",
        turn_index=0,
        call_id="unit-call",
    )
    wire = json.loads(request_record["body_json"])
    assert len(wire["messages"]) == 2
    assert wire["messages"][0] == {"role": "system", "content": adapter.SYSTEM_MESSAGE}
    assert wire["messages"][1] == {
        "role": "user",
        "content": canonical_json_bytes(public_request).decode("utf-8"),
    }
    assert (
        json.loads(wire["messages"][1]["content"])["response_schema"]
        == (public_request["response_schema"])
    )
    assert set(wire) == {
        "model",
        "messages",
        "thinking",
        "temperature",
        "top_p",
        "max_tokens",
        "response_format",
        "stream",
    }
    assert wire["thinking"] == {"type": "disabled"}
    raw = request_record["body_json"].encode("utf-8")
    assert request_record["body_sha256"] == models.sha(raw)
    assert request_record["body_byte_count"] == len(raw)
    assert request_record["input_token_upper_bound"] == len(raw) + 1024
    assert "unit-session" not in wire["messages"][1]["content"]


def test_public_content_and_metadata_are_selected_without_private_envelope_hash(
    request_record: dict[str, Any],
) -> None:
    raw_envelope = envelope()
    result = observe(request_record, raw_envelope)
    response = result["response"]
    assert result["public_content"] == VALID.encode("utf-8")
    assert response["parser_status"] == "valid"
    assert response["parser_code"] == "schema.valid"
    assert response["evidence_level"] == "public_submission_replayable"
    assert response["generator_origin"] == "adapter_mock"
    assert response["received_model"] == "deepseek-v4-pro"
    assert response["system_fingerprint"] == "unit-fingerprint"
    assert response["response_id"] == "unit-provider-response"
    assert response["attempt_id"] == "unit-reservation"
    for key in ("session_id", "turn_index", "call_id", "public_request_id", "state_id", "phase"):
        assert response[key] == request_record[key]
    persisted = canonical_json_bytes(response)
    assert PRIVATE.encode() not in persisted
    assert models.sha(PRIVATE.encode()).encode() not in persisted
    assert models.sha(raw_envelope).encode() not in persisted


@pytest.mark.parametrize(
    "content", ["", "not JSON", "```json\n" + VALID + "\n```", '{"kind":"update"}']
)
def test_invalid_public_text_is_never_repaired_or_persisted(
    request_record: dict[str, Any],
    content: str,
) -> None:
    result = observe(request_record, envelope(content))
    response = result["response"]
    assert result["public_content"] == content.encode()
    assert response["status"] == "received"
    assert response["parser_status"] == "invalid"
    assert response["evidence_level"] == "receiver_diagnosis_only"
    assert response["public_content_sha256"] == models.sha(content.encode())
    assert response["public_content_bytes"] == len(content.encode())
    assert "raw_public_json" not in response and "content" not in response
    assert PRIVATE not in json.dumps(response)


@pytest.mark.parametrize("model", [None, "deepseek-wrong-model"])
def test_missing_or_unregistered_actual_model_is_terminal_without_expected_name_fill(
    request_record: dict[str, Any],
    model: str | None,
) -> None:
    result = observe(request_record, envelope(model=model))
    assert result["public_content"] is None
    assert result["response"]["code"] == "provider.model_identity_mismatch"
    assert result["response"]["received_model"] == model
    assert result["response"]["public_content_sha256"] is None


def test_usage_absence_stays_unknown_and_usage_cap_is_terminal(
    request_record: dict[str, Any],
) -> None:
    missing = observe(request_record, envelope(usage=None))["response"]["usage"]
    assert missing == dict.fromkeys(adapter.USAGE_KEYS)
    for key, cap in (
        ("prompt_tokens", 66560),
        ("completion_tokens", 8192),
        ("total_tokens", 74752),
    ):
        result = observe(request_record, envelope(usage={key: cap + 1}))
        assert result["public_content"] is None
        assert result["response"]["code"] == "provider.actual_token_cap"
        assert result["response"]["usage"][key] == cap + 1


def test_no_public_content_and_http_failure_have_no_synthetic_submission(
    request_record: dict[str, Any],
) -> None:
    missing = observe(request_record, envelope(None))
    assert missing["public_content"] is None
    assert missing["response"]["code"] == "provider.public_content_unavailable"
    assert missing["response"]["public_content_bytes"] is None
    subject = adapter.DeepSeekAdapter(
        models.model_config(),
        transport=adapter.MockTransport(
            lambda _: {"http_status": 429, "body": PRIVATE.encode()},
        ),
    )
    failed = subject.perform(request_record, reserve=lambda _: {"id": "attempt"})
    assert failed["response"]["code"] == "transport.http_error"
    assert failed["response"]["parser_status"] == "not_available"
    assert failed["public_content"] is None
    assert PRIVATE not in json.dumps(failed["response"])


def test_reservation_precedes_single_timeout_attempt_and_exception_is_discarded(
    request_record: dict[str, Any],
) -> None:
    events: list[str] = []

    def reserve(request: dict[str, Any]) -> dict[str, Any]:
        assert request == request_record
        events.append("durably_reserved")
        return {"id": "attempt-before-timeout"}

    def timeout(request: dict[str, Any]) -> dict[str, Any]:
        assert events == ["durably_reserved"]
        events.append("one_send")
        raise adapter.TransportFailure("transport.timeout")

    subject = adapter.DeepSeekAdapter(
        models.model_config(), transport=adapter.MockTransport(timeout)
    )
    result = subject.perform(request_record, reserve=reserve)
    assert events == ["durably_reserved", "one_send"]
    assert result["response"]["attempt_id"] == "attempt-before-timeout"
    assert result["response"]["code"] == "transport.timeout"
    assert result["public_content"] is None

    def private_exception(_: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(PRIVATE)

    failed = adapter.DeepSeekAdapter(
        models.model_config(),
        transport=adapter.MockTransport(private_exception),
    ).perform(request_record, reserve=lambda _: {"id": "other-attempt"})
    assert failed["response"]["code"] == "transport.unclassified_failure"
    assert PRIVATE not in json.dumps(failed["response"])
    assert models.sha(PRIVATE.encode()) not in json.dumps(failed["response"])


@pytest.mark.parametrize("timeout", [False, True])
def test_real_transport_code_uses_exact_stdin_credential_pipe_and_total_timeout_with_mocked_process(
    request_record: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    timeout: bool,
) -> None:
    events: list[str] = []
    seen: dict[str, Any] = {}
    key = "synthetic-unit-credential"

    class FakeProcess:
        returncode = 0

        def __init__(self, args: list[str], **kwargs: Any) -> None:
            assert events == ["reserved"]
            events.append("popen")
            seen["args"] = args
            assert key not in json.dumps(args)
            assert "env" not in kwargs
            assert kwargs["close_fds"] is True
            seen["header"] = os.read(kwargs["pass_fds"][0], 4096)
            self.calls = 0

        def communicate(self, data: bytes | None = None, **kwargs: Any) -> tuple[bytes, bytes]:
            self.calls += 1
            if self.calls == 1:
                seen["stdin"] = data
                assert kwargs["timeout"] == 180
                if timeout:
                    raise subprocess.TimeoutExpired("synthetic", 180, stderr=PRIVATE.encode())
            return envelope() + b"\n200", PRIVATE.encode()

        def kill(self) -> None:
            events.append("kill")

    monkeypatch.setattr(adapter.subprocess, "Popen", FakeProcess)

    def reserve(_: dict[str, Any]) -> dict[str, Any]:
        events.append("reserved")
        return {"id": "curl-unit-reservation"}

    subject = adapter.DeepSeekAdapter(models.model_config())
    result = subject.perform(request_record, api_key=key, reserve=reserve)
    assert seen["stdin"] == request_record["body_json"].encode()
    assert seen["header"] == (
        f"Authorization: Bearer {key}\nContent-Type: application/json\n".encode()
    )
    args = seen["args"]
    assert args[:2] == ["curl", "--disable"]
    for flag, value in (
        ("--retry", "0"),
        ("--max-redirs", "0"),
        ("--connect-timeout", "30"),
        ("--max-time", "180"),
        ("--data-binary", "@-"),
    ):
        assert args[args.index(flag) + 1] == value
    assert "--location" not in args and "-L" not in args
    assert events == (["reserved", "popen", "kill"] if timeout else ["reserved", "popen"])
    assert result["response"]["code"] == ("transport.timeout" if timeout else None)
    assert key not in json.dumps(result["response"])
    assert PRIVATE not in json.dumps(result["response"])


def test_unregistered_send_is_rejected_before_reservation(request_record: dict[str, Any]) -> None:
    subject = adapter.DeepSeekAdapter(
        models.model_config(),
        transport=adapter.MockTransport(
            lambda _: {"http_status": 200, "body": envelope()},
        ),
    )

    def forbidden_reserve(_: dict[str, Any]) -> dict[str, Any]:
        pytest.fail("a caller supplied send must be rejected before attempt reservation")

    with pytest.raises(core.ProtocolError, match="adapter.registered_transport_callable"):
        subject.perform(request_record, reserve=forbidden_reserve, send=lambda _: {})


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("id", None, "provider.response_identity"),
        ("object", "not.chat.completion", "provider.response_identity"),
        ("index", 1, "provider.choice_index"),
        ("finish_reason", "unregistered_reason", "provider.finish_reason"),
    ],
)
def test_envelope_identity_and_choice_bounds_fail_before_public_parser(
    request_record: dict[str, Any],
    field: str,
    value: Any,
    code: str,
) -> None:
    supplied = json.loads(envelope())
    target = supplied["choices"][0] if field in {"index", "finish_reason"} else supplied
    target[field] = value
    result = observe(request_record, canonical_json_bytes(supplied))
    assert result["public_content"] is None
    assert result["response"]["code"] == code
    assert result["response"]["parser_status"] == "not_available"


def test_present_but_inconsistent_usage_is_typed_failure(request_record: dict[str, Any]) -> None:
    result = observe(
        request_record,
        envelope(
            usage={
                "prompt_tokens": 100,
                "completion_tokens": 40,
                "total_tokens": 141,
            }
        ),
    )
    assert result["public_content"] is None
    assert result["response"]["code"] == "provider.usage_inconsistent"


def test_deep_public_json_is_a_receiver_parser_diagnosis_not_a_crashed_attempt(
    request_record: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def depth_limited_parser(_: bytes) -> dict[str, Any]:
        raise RecursionError(PRIVATE)

    # Different Python builds have different C/Python JSON recursion limits. Inject
    # exactly the parser exception rather than changing a process-global limit.
    monkeypatch.setattr(adapter, "parse_submission", depth_limited_parser)
    content = "[" * 5000 + "0" + "]" * 5000
    result = observe(request_record, envelope(content))
    assert result["public_content"] == content.encode()
    assert result["response"]["parser_status"] == "invalid"
    assert result["response"]["parser_code"] == "schema.public_submission"
    assert result["response"]["public_content_sha256"] == models.sha(content.encode())
    assert result["response"]["public_content_bytes"] == len(content.encode())
    assert result["response"]["evidence_level"] == "receiver_diagnosis_only"
