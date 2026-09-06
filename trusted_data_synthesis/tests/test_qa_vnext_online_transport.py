"""Local HTTP mocks only: no credentials, real Provider calls, GPU or Student work."""

from __future__ import annotations

import asyncio
import copy
import json
import socket
from pathlib import Path
from typing import Any

import httpx
import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.callbacks import PublicFixtureCallback
from trusted_synthesis.domains.finance.qa_vnext.catalog import FinanceQACatalog
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import contract
from trusted_synthesis.domains.finance.qa_vnext.protocol import record as public_record
from trusted_synthesis.domains.finance.qa_vnext.runner import build_catalog
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import transport
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import identity, sha

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("transport unit tests must never open a real socket")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def request(index: int = 0, **context_fields: Any) -> dict[str, Any]:
    rules = contract()
    context = public_record("context", task_id="transport-test-task", **context_fields)
    state = public_record(
        "state",
        context_id=context["id"],
        protocol_id=rules["id"],
        submission_count=index,
        phase="action",
        accepted_claims=[],
        pending_observation=None,
        last_feedback=None,
    )
    return public_record(
        "request",
        context=context,
        state=state,
        protocol_id=rules["id"],
        available_actions=[],
        final_claim_ids=[],
        update_transition_options={},
        response_schemas=rules["submission_schemas"],
    )


def envelope(content: Any = "not JSON", **updates: Any) -> bytes:
    return canonical_json_bytes(
        {
            "id": "mock-provider-response",
            "object": "chat.completion",
            "model": "deepseek-v4-pro",
            "system_fingerprint": "mock-fingerprint",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": content,
                    },
                }
            ],
            "usage": {"prompt_tokens": 200, "completion_tokens": 10, "total_tokens": 210},
            **updates,
        }
    )


class MockSender:
    def __init__(self, handler):
        self.handler = handler
        self.requests: list[dict[str, Any]] = []

    def send(self, value: dict[str, Any], *, api_key: str | None) -> transport.HTTPResponse:
        self.requests.append(copy.deepcopy(value))
        return self.handler(value)


def callback(tmp_path: Path, sender: MockSender) -> transport.OnlineModelCallback:
    return transport.OnlineModelCallback(
        transport.TransportConfig(),
        session_id="opaque-preregistered-session",
        evidence_directory=tmp_path / "transport",
        sender=sender,
    )


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes())


def test_config_and_actual_http_bytes_freeze_the_current_full_public_request() -> None:
    config = transport.TransportConfig()
    frozen = config.as_record()
    identity(frozen, "transport_config")
    public = request(7)
    rendered = transport.render_http_request(
        public, config, session_id="registered", attempt_index=7
    )
    raw = rendered["body_json"].encode("utf-8")
    assert raw == canonical_json_bytes(rendered["body"])
    assert rendered["body_sha256"] == sha(raw)
    assert rendered["body_byte_count"] == len(raw)
    assert rendered["input_admission_upper_bound"] == len(raw) + 1024
    assert rendered["input_allowance"] == 99328
    assert rendered["reserved_tokens"] == 107520
    assert frozen["maximum_session_reserved_tokens"] == 32 * 107520
    assert frozen["maximum_pilot_reserved_tokens"] == 384 * 107520
    assert rendered["model_configuration_id"] == frozen["id"]
    assert rendered["public_runtime_state_id"] == public["state"]["id"]
    assert rendered["messages"] == [
        {"role": "system", "content": frozen["system_prompt"]},
        {"role": "user", "content": canonical_json_bytes(public).decode("utf-8")},
    ]
    assert set(rendered["body"]) == {
        "model",
        "messages",
        "thinking",
        "temperature",
        "top_p",
        "max_tokens",
        "response_format",
        "stream",
    }
    assert rendered["body"]["thinking"] == {"type": "disabled"}
    assert rendered["body"]["response_format"] == {"type": "json_object"}
    assert "disclosed_total" not in frozen["system_prompt"]
    assert "reconstructed_total" not in frozen["system_prompt"]


@pytest.mark.parametrize("content", ["not JSON", "  \n", "```json\n{}\n```", '{ "x": 1.00 }\n'])
def test_reservation_durability_and_raw_return_without_host_repair(
    tmp_path: Path,
    content: str,
) -> None:
    raw_response = envelope(content)
    observations = []

    def send(value):
        prefix = tmp_path / "transport/attempts/000"
        reserved = load(prefix.with_name(prefix.name + "_reservation.json"))
        body = prefix.with_name(prefix.name + "_http_request.body").read_bytes()
        assert reserved["http_request_id"] == value["id"]
        assert reserved["reserved_before_send"]
        assert body == value["body_json"].encode("utf-8")
        observations.extend(copy.deepcopy(subject.store.events))
        return transport.HTTPResponse(200, raw_response, (("x-request-id", "mock-http-id"),))

    sender = MockSender(send)
    subject = callback(tmp_path, sender)
    original_binding = copy.deepcopy(subject.binding)
    assert subject.generate(request()) == content.encode("utf-8")
    assert subject.binding == original_binding
    ledger = subject.finalize()
    assert ledger["provider_attempt_count"] == 1
    assert ledger["reserved_tokens"] == 107520
    assert ledger["transport_kind"] == "adapter_mock"
    paths = ledger["attempts"][0]["paths"]
    root = subject.store.root
    assert (root / paths["http_response_body"]).read_bytes() == raw_response
    assert (root / paths["public_content"]).read_bytes() == content.encode("utf-8")
    outcome = load(root / paths["outcome"])
    identity(outcome, "provider_outcome")
    assert outcome["public_content_returned_to_runtime"]
    assert outcome["observed_model"] == "deepseek-v4-pro"
    assert outcome["host_repairs"] == []
    assert outcome["public_runtime_state_id"] == request()["state"]["id"]
    markers = [row["kind"] for row in observations]
    assert markers[-2:] == ["reservation_readback", "send"]
    reserved_path = paths["reservation"]
    file_sync = next(
        i
        for i, row in enumerate(observations)
        if row == {"kind": "file_fsync", "path": reserved_path}
    )
    dir_sync = next(
        i
        for i, row in enumerate(observations)
        if row == {"kind": "directory_fsync", "path": reserved_path}
    )
    assert file_sync < dir_sync < markers.index("reservation_readback") < markers.index("send")
    manifest = load(root / "manifest.json")
    identity(manifest, "transport_manifest")
    files = {
        str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }
    assert set(files) - {"manifest.json"} == {row["path"] for row in manifest["members"]}
    for row in manifest["members"]:
        assert sha(files[row["path"]]) == row["sha256"]
        assert len(files[row["path"]]) == row["bytes"]
    assert not any("submission" in path or "receipt" in path for path in files)
    assert subject.finalize() == ledger


@pytest.mark.parametrize("content", [None, ""])
def test_no_public_string_consumes_one_attempt_and_never_fabricates_submission(
    tmp_path: Path,
    content: str | None,
) -> None:
    sender = MockSender(lambda _: transport.HTTPResponse(200, envelope(content)))
    subject = callback(tmp_path, sender)
    with pytest.raises(transport.OnlineTransportError) as raised:
        subject.generate(request())
    assert raised.value.code == "provider.no_public_content"
    assert raised.value.evidence_id == subject.last_outcome["id"]
    with pytest.raises(transport.OnlineTransportError, match="transport.session_closed"):
        subject.generate(request())
    assert len(sender.requests) == subject.attempt_count == 1
    ledger = subject.finalize()
    outcome = load(subject.store.root / ledger["attempts"][0]["paths"]["outcome"])
    assert not outcome["public_content_returned_to_runtime"]
    assert not any(
        "submission" in path.name or "receipt" in path.name
        for path in subject.store.root.rglob("*")
    )


@pytest.mark.parametrize("model", [None, "unregistered-model"])
def test_identity_mismatch_preserves_raw_response_without_public_submission(
    tmp_path: Path,
    model: str | None,
) -> None:
    original = envelope('{"kind":"action"}', model=model)
    sender = MockSender(lambda _: transport.HTTPResponse(200, original))
    subject = callback(tmp_path, sender)
    with pytest.raises(transport.OnlineTransportError) as raised:
        subject.generate(request())
    assert raised.value.code == "provider.model_identity_mismatch"
    assert subject.attempt_count == 1
    assert subject.last_outcome["observed_model"] == model
    assert not subject.last_outcome["public_content_returned_to_runtime"]
    ledger = subject.finalize()
    paths = ledger["attempts"][0]["paths"]
    assert (subject.store.root / paths["http_response_body"]).read_bytes() == original


def test_timeout_is_observed_once_without_retry_response_or_exception_secret(
    tmp_path: Path,
) -> None:
    def timeout(_):
        raise TimeoutError("DO_NOT_PERSIST_CREDENTIAL_CANARY")

    sender = MockSender(timeout)
    subject = callback(tmp_path, sender)
    with pytest.raises(transport.OnlineTransportError) as raised:
        subject.generate(request())
    assert raised.value.code == "transport.timeout"
    assert raised.value.evidence_id == subject.last_outcome["id"]
    ledger = subject.finalize()
    assert len(sender.requests) == ledger["provider_attempt_count"] == 1
    assert ledger["attempts"][0]["paths"]["http_response_body"] is None
    assert ledger["attempts"][0]["paths"]["public_content"] is None
    assert all(
        b"DO_NOT_PERSIST_CREDENTIAL_CANARY" not in path.read_bytes()
        for path in subject.store.root.rglob("*")
        if path.is_file()
    )


def test_input_cap_saves_actual_untruncated_request_without_consuming_attempt(
    tmp_path: Path,
) -> None:
    sender = MockSender(lambda _: pytest.fail("over-budget request reached HTTP"))
    subject = callback(tmp_path, sender)
    public = request(evidence_text='"' * 100000)
    with pytest.raises(transport.OnlineTransportError) as raised:
        subject.generate(public)
    assert raised.value.code == "resource.input_budget"
    ledger = subject.finalize()
    assert ledger["provider_attempt_count"] == ledger["reserved_tokens"] == 0
    assert ledger["attempts"] == []
    paths = ledger["stops"][0]["paths"]
    assert paths["reservation"] is None
    assert load(subject.store.root / paths["public_request"]) == public
    body = (subject.store.root / paths["http_request_body"]).read_bytes()
    assert len(body) > 98304
    assert json.loads(json.loads(body)["messages"][1]["content"]) == public


def test_attempt_33_has_resource_outcome_not_a_send_or_replacement(tmp_path: Path) -> None:
    sender = MockSender(lambda _: transport.HTTPResponse(200, envelope()))
    subject = callback(tmp_path, sender)
    for index in range(32):
        assert subject.generate(request(index)) == b"not JSON"
    with pytest.raises(transport.OnlineTransportError) as raised:
        subject.generate(request(32))
    assert raised.value.code == "resource.attempt_budget"
    ledger = subject.finalize()
    assert len(sender.requests) == ledger["provider_attempt_count"] == 32
    assert ledger["reserved_tokens"] == 3440640
    assert len(ledger["stops"]) == 1
    assert ledger["stops"][0]["paths"]["reservation"] is None


def test_unexpected_conditions_do_not_rewrite_or_drop_available_public_content(
    tmp_path: Path,
) -> None:
    value = json.loads(envelope("raw public content"))
    value["choices"][0]["message"].update(reasoning_content="unexpected reasoning", tool_calls=[{}])
    value["usage"]["completion_tokens"] = 8193
    raw = canonical_json_bytes(value)
    sender = MockSender(lambda _: transport.HTTPResponse(200, raw))
    subject = callback(tmp_path, sender)
    assert subject.generate(request()) == b"raw public content"
    assert set(subject.last_outcome["condition_flags"]) >= {
        "provider.unexpected_reasoning_content",
        "provider.unexpected_native_tool_calls",
        "provider.usage_exceeds_allowance.completion_tokens",
        "provider.usage_sum_mismatch",
    }
    ledger = subject.finalize()
    assert (
        subject.store.root / ledger["attempts"][0]["paths"]["http_response_body"]
    ).read_bytes() == raw


@pytest.fixture(scope="module")
def source_cases() -> tuple[FinanceQACatalog, dict[str, Any]]:
    catalog = build_catalog(REPO_ROOT)
    cases, _ = catalog.frozen_source_cases(
        REPO_ROOT,
        task_types=("registered_cross_metric_comparison", "derived_growth_absolute_spread"),
    )
    return catalog, {case.task_type: case for case in cases}


@pytest.mark.parametrize("correct_first", [True, False])
def test_same_runtime_accepts_17_step_branch_or_new_callback_correction(
    tmp_path: Path,
    source_cases: tuple[FinanceQACatalog, dict[str, Any]],
    correct_first: bool,
) -> None:
    catalog, cases = source_cases
    family = (
        "derived_growth_absolute_spread" if correct_first else "registered_cross_metric_comparison"
    )
    adapter = ProgramTaskAdapter(cases[family], catalog.registry)
    fixture = PublicFixtureCallback()
    sent_public = []

    def send(value):
        public = json.loads(value["body"]["messages"][1]["content"])
        sent_public.append(public)
        text = (
            b'{"kind":"old_protocol_action"}'
            if not correct_first and len(sent_public) == 1
            else fixture.generate(public)
        )
        return transport.HTTPResponse(
            200, envelope(text.decode("utf-8"), id=f"mock-{len(sent_public)}")
        )

    sender = MockSender(send)
    subject = callback(tmp_path, sender)
    session = PublicQARuntime(
        adapter, subject, tmp_path / "runtime", max_submissions=32, max_actions=12
    ).run()
    ledger = subject.finalize()
    assert session["final"] is not None
    assert session["final"]["qa_validation"]["qa_valid"]
    assert (
        len(session["events"]) == ledger["provider_attempt_count"] == (17 if correct_first else 4)
    )
    for event, row in zip(session["events"], ledger["attempts"], strict=True):
        assert canonical_json_bytes(event["request"]) == canonical_json_bytes(
            sent_public[event["sequence"]]
        )
        raw = (subject.store.root / row["paths"]["public_content"]).read_bytes()
        assert sha(raw) == event["submission"]["raw_sha256"]
    if not correct_first:
        assert not session["events"][0]["receipt"]["admitted"]
        assert session["events"][1]["receipt"]["admitted"]
        assert sent_public[1]["state"]["last_feedback"]["admitted"] is False
        assert sent_public[0]["state"]["id"] != sent_public[1]["state"]["id"]
        assert (
            subject.store.root / ledger["attempts"][0]["paths"]["public_content"]
        ).read_bytes() == b'{"kind":"old_protocol_action"}'


class AsyncBytes(httpx.AsyncByteStream):
    def __init__(self, content: bytes):
        self.content = content

    async def __aiter__(self):
        yield self.content


def test_httpx_sender_uses_exact_bytes_single_post_and_safe_client_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_client = httpx.AsyncClient
    configurations, requests = [], []
    raw_response = envelope("from HTTP mock")

    def handle(value):
        requests.append(value)
        return httpx.Response(200, stream=AsyncBytes(raw_response))

    def client(**kwargs):
        configurations.append(kwargs.copy())
        kwargs["transport"] = httpx.MockTransport(handle)
        return original_client(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    config = transport.TransportConfig()
    wire = transport.render_http_request(request(), config, session_id="s", attempt_index=0)
    response = transport.HttpxSender(config).send(wire, api_key="local-test-key")
    assert response.body == raw_response
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].content == wire["body_json"].encode("utf-8")
    assert requests[0].headers["accept-encoding"] == "identity"
    assert configurations[0]["trust_env"] is False
    assert configurations[0]["follow_redirects"] is False
    assert configurations[0]["timeout"].connect == 30
    assert configurations[0]["timeout"].read == 180
    assert configurations[0]["transport"]._pool._retries == 0


def test_httpx_total_deadline_has_no_automatic_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    original_client, original_timeout = httpx.AsyncClient, asyncio.timeout
    calls, deadlines = [], []

    async def handle(value):
        calls.append(value)
        await asyncio.sleep(1)
        return httpx.Response(200, stream=AsyncBytes(envelope()))

    def client(**kwargs):
        kwargs["transport"] = httpx.MockTransport(handle)
        return original_client(**kwargs)

    def short_timeout(seconds):
        deadlines.append(seconds)
        return original_timeout(0.01)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    monkeypatch.setattr(asyncio, "timeout", short_timeout)
    config = transport.TransportConfig()
    wire = transport.render_http_request(request(), config, session_id="s", attempt_index=0)
    with pytest.raises(transport.HTTPSendError, match="transport.timeout"):
        transport.HttpxSender(config).send(wire, api_key="local-test-key")
    assert deadlines == [180]
    assert len(calls) == 1


def test_allowed_observed_alias_and_absent_usage_are_retained_without_filling(
    tmp_path: Path,
) -> None:
    sender = MockSender(
        lambda _: transport.HTTPResponse(
            200,
            envelope(
                "alias response", model="deepseek-v4-pro-0813", usage=None, system_fingerprint=None
            ),
        )
    )
    subject = callback(tmp_path, sender)
    assert subject.generate(request()) == b"alias response"
    observed = subject.last_outcome
    assert observed["observed_model"] == "deepseek-v4-pro-0813"
    assert observed["system_fingerprint"] is None
    assert all(value is None for value in observed["usage"].values())
    assert observed["condition_flags"] == []
    subject.finalize()


def test_public_string_over_runtime_byte_cap_is_not_truncated_by_transport(tmp_path: Path) -> None:
    text = "x" * (1048576 + 1)
    sender = MockSender(lambda _: transport.HTTPResponse(200, envelope(text)))
    subject = callback(tmp_path, sender)
    assert subject.generate(request()) == text.encode()
    assert subject.last_outcome["public_content_byte_count"] == 1048577
    assert subject.last_outcome["condition_flags"] == [
        "provider.public_content_exceeds_runtime_cap"
    ]
    subject.finalize()


def test_httpx_response_byte_bound_returns_only_observed_partial_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_client = httpx.AsyncClient
    calls = []

    def handle(value):
        calls.append(value)
        return httpx.Response(200, stream=AsyncBytes(b"x" * (2097152 + 1)))

    def client(**kwargs):
        kwargs["transport"] = httpx.MockTransport(handle)
        return original_client(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    config = transport.TransportConfig()
    wire = transport.render_http_request(request(), config, session_id="s", attempt_index=0)
    with pytest.raises(transport.HTTPSendError) as raised:
        transport.HttpxSender(config).send(wire, api_key="local-test-key")
    assert raised.value.code == "transport.response_byte_cap"
    assert raised.value.response is not None
    assert raised.value.response.complete is False
    assert raised.value.response.body == b"x" * 2097152
    assert len(calls) == 1
