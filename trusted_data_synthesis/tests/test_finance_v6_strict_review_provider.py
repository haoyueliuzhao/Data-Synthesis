"""Strict-review HTTP mock controls; no real network, ledger, GPU, or credentials."""

import asyncio
import copy
import hashlib
import json

import pytest
from test_finance_research_probe_provider import Client, value
from test_finance_semantic_review import fixture_bundle
from test_finance_v6_budget_amendment import amendment, paused_budget, reopen
from test_finance_v6_compact_review import setup

from trusted_synthesis.finance_research.contracts import ProviderCallError, digest
from trusted_synthesis.finance_research.probe_budget import DuplicateInvocation
from trusted_synthesis.finance_research.probe_provider import ENDPOINT
from trusted_synthesis.finance_research.semantic_review import review_request
from trusted_synthesis.finance_research.v6_review_provider import (
    STRICT_ENDPOINT,
    STRICT_WIRE_PROTOCOL,
    request_review,
)

KEY = "strict-review-cpu-mock-secret-123456789"


def request_fixture():
    request, _ = setup()
    payload = json.loads(request["messages"][1]["content"])
    payload["wire_protocol"] = STRICT_WIRE_PROTOCOL
    del payload["output_schema"]
    request["messages"][1]["content"] = json.dumps(payload)
    request.update(
        wire_protocol=STRICT_WIRE_PROTOCOL,
        max_output_tokens=32768,
        capacity_policy_id="registered-capacity-control",
        strict_tool=dict(
            type="function",
            function=dict(
                name="submit_review",
                strict=True,
                parameters=dict(
                    type="object",
                    properties={"result": {"type": "string"}},
                    required=["result"],
                    additionalProperties=False,
                ),
            ),
        ),
    )
    request["messages_model_sha256"] = digest(
        dict(model=request["model"], messages=request["messages"])
    )
    request["strict_tool_sha256"] = digest(request["strict_tool"])
    return request


def ledger_fixture(tmp_path):
    ledger, _ = paused_budget(tmp_path / "joint.sqlite3")
    amendment(ledger)
    return reopen(ledger.path)


def response_fixture(arguments=' {"result":"original"} \n', *, content=None, finish="tool_calls"):
    response = value()
    response["choices"] = [
        dict(
            finish_reason=finish,
            message=dict(
                role="assistant",
                content=content,
                tool_calls=[
                    dict(
                        id="actual-review-call-0",
                        type="function",
                        function=dict(name="submit_review", arguments=arguments),
                    )
                ],
            ),
        )
    ]
    return response


def call(ledger, client, request=None, *, episode_id="strict-review/0"):
    return asyncio.run(
        request_review(
            ledger=ledger,
            api_key=KEY,
            episode_id=episode_id,
            request=request_fixture() if request is None else request,
            client=client,
        )
    )


def test_exact_beta_forced_strict_tool_body_and_raw_argument_receipt(tmp_path):
    ledger, request = ledger_fixture(tmp_path), request_fixture()
    client = Client(response_fixture())
    before = ledger.snapshot()["settled_tariff_microcny"]
    artifact = call(ledger, client, request)
    url, sent = client.calls[0]
    body = json.loads(sent["content"])
    assert (
        url
        == artifact["endpoint"]
        == STRICT_ENDPOINT
        == "https://api.deepseek.com/beta/chat/completions"
    )
    assert body == dict(
        model="deepseek-flash",
        messages=request["messages"],
        temperature=0,
        top_p=1,
        max_tokens=32768,
        thinking={"type": "disabled"},
        stream=False,
        tools=[request["strict_tool"]],
        tool_choice={"type": "function", "function": {"name": "submit_review"}},
    )
    assert "response_format" not in body
    assert "output_schema" not in json.loads(body["messages"][1]["content"])
    assert artifact["content"] is None
    assert artifact["review_text"] == ' {"result":"original"} \n'
    assert artifact["review_payload_source"] == "tool_call.function.arguments"
    assert artifact["review_tool_call_id"] == "actual-review-call-0"
    assert artifact["review_format_error"] is None
    assert artifact["finish_reason"] == "tool_calls"
    assert artifact["request_sha256"] == digest(body) == hashlib.sha256(sent["content"]).hexdigest()
    assert artifact["strict_tool_sha256"] == digest(request["strict_tool"])
    assert artifact["semantic_review_request_sha256"] == digest(request)
    assert artifact["api_response"] == client.response
    saved = ledger.request_record(artifact["budget_invocation_id"])
    assert saved["response_body"].decode() == artifact["api_response_raw"]
    assert saved["state"] == "SETTLED" and not ledger.unsettled()
    assert ledger.snapshot()["settled_tariff_microcny"] == before + 280
    assert ledger.snapshot()["halt"] is None
    assert KEY.encode() not in saved["request_body"] + saved["response_body"]


@pytest.mark.parametrize(
    "arguments,content",
    [("{bad JSON", None), ("", "actual accompanying prose"), ('{"duplicate":1,"duplicate":2}', "")],
)
def test_arguments_and_public_content_are_never_repaired_or_replaced(tmp_path, arguments, content):
    ledger = ledger_fixture(tmp_path)
    artifact = call(ledger, Client(response_fixture(arguments, content=content)))
    assert artifact["review_text"] == arguments and artifact["content"] == content
    assert artifact["content_repair_performed"] is False
    assert ledger.snapshot()["halt"] is None and not ledger.unsettled()


@pytest.mark.parametrize("finish", ["length", "stop", "content_filter"])
def test_non_tool_finish_is_paid_format_unknown_with_original_partial_arguments(tmp_path, finish):
    ledger = ledger_fixture(tmp_path)
    client = Client(response_fixture('{"partial":', finish=finish))
    artifact = call(ledger, client)
    assert artifact["finish_reason"] == finish and artifact["review_text"] == '{"partial":'
    assert artifact["review_format_error"] == "strict_finish_not_tool_calls"
    assert len(client.calls) == 1 and not ledger.unsettled() and ledger.snapshot()["halt"] is None


@pytest.mark.parametrize(
    "mutation", ["missing", "multiple", "wrong_name", "empty_id", "type", "arguments_type"]
)
def test_invalid_tool_delivery_is_settled_without_inventing_review_or_falling_back_to_content(
    tmp_path, mutation
):
    ledger, returned = (
        ledger_fixture(tmp_path),
        response_fixture(content='{"fallback":"must not use"}'),
    )
    message = returned["choices"][0]["message"]
    if mutation == "missing":
        del message["tool_calls"]
    elif mutation == "multiple":
        message["tool_calls"].append(copy.deepcopy(message["tool_calls"][0]))
    elif mutation == "wrong_name":
        message["tool_calls"][0]["function"]["name"] = "other_tool"
    elif mutation == "empty_id":
        message["tool_calls"][0]["id"] = "  "
    elif mutation == "type":
        message["tool_calls"][0]["type"] = "not_function"
    else:
        message["tool_calls"][0]["function"]["arguments"] = {"not": "a raw string"}
    client = Client(returned)
    artifact = call(ledger, client)
    assert artifact["review_text"] is None and artifact["review_payload_source"] is None
    assert artifact["review_format_error"]
    assert artifact["content"] == '{"fallback":"must not use"}'
    assert artifact["api_response"] == returned
    assert len(client.calls) == 1 and not ledger.unsettled() and ledger.snapshot()["halt"] is None


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_tool",
        "wrong_name",
        "not_strict",
        "ref",
        "payload_schema",
        "catalog",
        "model",
        "cap",
    ],
)
def test_bad_strict_request_is_rejected_before_reserving_or_dispatching(tmp_path, mutation):
    ledger, request = ledger_fixture(tmp_path), request_fixture()
    if mutation == "missing_tool":
        del request["strict_tool"]
    elif mutation == "wrong_name":
        request["strict_tool"]["function"]["name"] = "another_tool"
    elif mutation == "not_strict":
        request["strict_tool"]["function"]["strict"] = False
    elif mutation == "ref":
        request["strict_tool"]["function"]["parameters"]["properties"]["result"] = {
            "$ref": "#/missing"
        }
    elif mutation == "payload_schema":
        payload = json.loads(request["messages"][1]["content"])
        payload["output_schema"] = {"type": "object"}
        request["messages"][1]["content"] = json.dumps(payload)
        request["messages_model_sha256"] = digest(
            dict(model=request["model"], messages=request["messages"])
        )
    elif mutation == "catalog":
        request["catalog_sha256"] = "0" * 64
    elif mutation == "model":
        request["model"] = "another-model"
    else:
        request["max_output_tokens"] = 65535
    client, before = Client(response_fixture()), ledger.snapshot()
    with pytest.raises(ValueError):
        call(ledger, client, request)
    assert client.calls == [] and ledger.snapshot() == before


@pytest.mark.parametrize("mutation", ["model", "usage", "thinking"])
def test_strict_response_unknown_model_usage_or_private_thinking_halts_with_reservation(
    tmp_path, mutation
):
    ledger, returned = ledger_fixture(tmp_path), response_fixture()
    if mutation == "model":
        returned["model"] = "unrequested-model"
    elif mutation == "usage":
        del returned["usage"]
    else:
        returned["choices"][0]["message"]["reasoning_content"] = "unrequested private text"
    client, before = Client(returned), ledger.snapshot()
    with pytest.raises(ProviderCallError) as caught:
        call(ledger, client)
    assert caught.value.settlement == "unknown"
    assert len(client.calls) == 1 and ledger.snapshot()["halt"]
    assert ledger.snapshot()["held_microcny"] > 0
    assert ledger.snapshot()["settled_tariff_microcny"] == before["settled_tariff_microcny"]


def test_exact_strict_invocation_is_not_reissued_and_legacy_v1_endpoint_is_unchanged(tmp_path):
    ledger = ledger_fixture(tmp_path)
    client = Client(response_fixture())
    call(ledger, client)
    with pytest.raises(DuplicateInvocation):
        call(ledger, client)
    assert len(client.calls) == 1
    plain = review_request(fixture_bundle(), {"answer": 120}, 0)
    returned = value()
    returned["choices"] = [
        dict(finish_reason="stop", message=dict(role="assistant", content=" {v1 raw} "))
    ]
    old_client = Client(returned)
    original = call(ledger, old_client, plain, episode_id="legacy-full-v1")
    body = json.loads(old_client.calls[0][1]["content"])
    assert old_client.calls[0][0] == ENDPOINT and "tools" not in body
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] == 16384 and original["content"] == " {v1 raw} "
    assert "review_text" not in original and "endpoint" not in original


def test_actual_strict_schema_request_and_original_arguments_semantics_roundtrip(tmp_path):
    from test_finance_v6_strict_review import setup as strict_setup

    from trusted_synthesis.finance_research.v6_strict_review import validate_strict_review

    request, semantic_answer = strict_setup()
    request.update(max_output_tokens=32768, capacity_policy_id="registered-capacity-control")
    raw_arguments = json.dumps(semantic_answer, ensure_ascii=False)
    ledger = ledger_fixture(tmp_path)
    artifact = call(ledger, Client(response_fixture(raw_arguments)), request)
    validated = validate_strict_review(artifact["review_text"], request)
    assert artifact["review_format_error"] is None
    assert validated["raw_review_sha256"] == hashlib.sha256(raw_arguments.encode()).hexdigest()
    assert validated["wire_protocol"] == STRICT_WIRE_PROTOCOL
    assert not validated["semantic_repair_performed"]
