"""Explicit V3 wire compatibility; only temporary ledgers and mocked HTTP."""

import json

import pytest
from test_finance_research_probe_provider import Client
from test_finance_v6_strict_review_provider import (
    call,
    ledger_fixture,
    request_fixture,
    response_fixture,
)

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.v6_review_provider import (
    STRICT_ENDPOINT,
    STRICT_WIRE_PROTOCOLS,
)


def rewired_request(wire):
    request = request_fixture()
    payload = json.loads(request["messages"][1]["content"])
    payload["wire_protocol"] = wire
    request["wire_protocol"] = wire
    request["messages"][1]["content"] = json.dumps(payload)
    request["messages_model_sha256"] = digest(
        dict(model=request["model"], messages=request["messages"])
    )
    return request


@pytest.mark.parametrize(
    "wire", ["v6_strict_review.v2", "v6_slot_review.v3", "v6_alignment_review.v3"]
)
def test_only_explicit_registered_strict_wires_preserve_their_actual_identity(tmp_path, wire):
    assert STRICT_WIRE_PROTOCOLS == {
        "v6_strict_review.v2",
        "v6_slot_review.v3",
        "v6_slot_review.v4",
        "v6_slot_review.v5",
        "v6_slot_review.v6",
        "v6_alignment_review.v3",
        "v8_single_target_review.v1",
        "v8_alignment_review.v1",
    }
    ledger, request = ledger_fixture(tmp_path), rewired_request(wire)
    client = Client(response_fixture(' {"raw":"unchanged"} '))
    artifact = call(ledger, client, request)
    body = json.loads(client.calls[0][1]["content"])
    assert artifact["wire_protocol"] == wire
    assert client.calls[0][0] == artifact["endpoint"] == STRICT_ENDPOINT
    assert artifact["review_text"] == ' {"raw":"unchanged"} ' and artifact["content"] is None
    assert artifact["review_format_error"] is None
    assert body["tool_choice"] == {"type": "function", "function": {"name": "submit_review"}}
    assert body["tools"] == [request["strict_tool"]] and "response_format" not in body
    assert body["model"] == "deepseek-flash" and body["thinking"] == {"type": "disabled"}
    assert body["temperature"] == 0 and body["top_p"] == 1 and body["max_tokens"] == 32768
    assert ledger.snapshot()["halt"] is None


@pytest.mark.parametrize("wire", ["v6_slot_review.v7", "v6_alignment_review.v2", "unregistered"])
def test_unregistered_wire_never_reserves_or_sends(tmp_path, wire):
    ledger, client = ledger_fixture(tmp_path), Client(response_fixture())
    before = ledger.snapshot()
    with pytest.raises(ValueError):
        call(ledger, client, rewired_request(wire))
    assert not client.calls and ledger.snapshot() == before


def test_payload_and_metadata_must_bind_same_explicit_stage_before_dispatch(tmp_path):
    ledger, client = ledger_fixture(tmp_path), Client(response_fixture())
    request = rewired_request("v6_slot_review.v3")
    request["wire_protocol"] = "v6_alignment_review.v3"
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="strict"):
        call(ledger, client, request)
    assert not client.calls and ledger.snapshot() == before


@pytest.mark.parametrize("wire", ["v6_slot_review.v3", "v6_alignment_review.v3"])
def test_v3_does_not_relax_unique_tool_or_output_limits(tmp_path, wire):
    ledger, request = ledger_fixture(tmp_path), rewired_request(wire)
    invalid = response_fixture()
    invalid["choices"][0]["message"]["tool_calls"][0]["id"] = ""
    artifact = call(ledger, Client(invalid), request)
    assert artifact["wire_protocol"] == wire
    assert artifact["review_text"] is None and artifact["review_format_error"]
    request["max_output_tokens"] = 65535
    before, client = ledger.snapshot(), Client(response_fixture())
    with pytest.raises(ValueError, match="capacity"):
        call(ledger, client, request, episode_id="must-not-send")
    assert not client.calls and ledger.snapshot() == before


def test_actual_single_slot_request_factory_uses_the_unchanged_strict_transport(tmp_path):
    from test_finance_semantic_review import fixture_bundle

    from trusted_synthesis.finance_research.v6_slot_review import slot_review_request

    request = slot_review_request(
        fixture_bundle(), "s0", {"program": "add(120, 0)", "answer": 120}, 1
    )
    request.update(max_output_tokens=16384, capacity_policy_id="registered-v3-capacity")
    ledger, client = ledger_fixture(tmp_path), Client(response_fixture('{"raw":"single slot"}'))
    artifact = call(ledger, client, request, episode_id="v3-slot/s0/reviewer1")
    assert artifact["wire_protocol"] == "v6_slot_review.v3" and artifact["reviewer"] == 1
    assert artifact["review_text"] == '{"raw":"single slot"}'
    assert artifact["public_request"]["tools"] == [request["strict_tool"]]
    assert artifact["public_request"]["max_tokens"] == 16384
    assert client.calls[0][0] == STRICT_ENDPOINT


def test_actual_alignment_factory_with_own_eight_unknown_judgments_uses_strict_transport(tmp_path):
    from test_finance_semantic_review import fixture_bundle, mechanical

    from trusted_synthesis.finance_research.v6_state_alignment import alignment_request

    bundle = fixture_bundle()
    judgments = {
        slot["slot_id"]: dict(
            reviewer=0,
            slot_id=slot["slot_id"],
            task_id=bundle["task_id"],
            task_bundle_sha256=digest(bundle),
            v_trace="unknown",
            semantic_validation_error="synthetic unresolved semantic fixture",
        )
        for slot in bundle["slots"]
    }
    request = alignment_request(dict(bundle=bundle, mechanical=mechanical()), judgments, 0)
    request.update(max_output_tokens=16384, capacity_policy_id="registered-v3-capacity")
    ledger, client = ledger_fixture(tmp_path), Client(response_fixture('{"pairs":{}}'))
    artifact = call(ledger, client, request, episode_id="v3-alignment/task/reviewer0")
    assert artifact["wire_protocol"] == "v6_alignment_review.v3"
    assert artifact["review_text"] == '{"pairs":{}}'
    assert artifact["public_request"]["tools"] == [request["strict_tool"]]
    assert request["other_reviewer_output_visible"] is False
    assert request["private_reference_in_alignment"] is False
    assert len(json.loads(request["messages"][1]["content"])["own_slot_judgments"]) == 8
    assert client.calls[0][0] == STRICT_ENDPOINT
