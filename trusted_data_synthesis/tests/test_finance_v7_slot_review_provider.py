"""Typed locator v4 factory transport controls; only mock HTTP/temp ledger."""

import json

import pytest
from test_finance_research_probe_provider import Client
from test_finance_semantic_review import fixture_bundle
from test_finance_v6_strict_review_provider import call, ledger_fixture, response_fixture

from trusted_synthesis.finance_research.v6_review_provider import STRICT_ENDPOINT
from trusted_synthesis.finance_research.v7_slot_review import slot_review_request


def request_fixture():
    request = slot_review_request(
        fixture_bundle(), "s0", {"program": "add(120, 0)", "answer": 120}, 1
    )
    request.update(max_output_tokens=16384, capacity_policy_id="registered-typed-locator-control")
    return request


def test_real_typed_locator_factory_retains_v4_identity_and_original_tool_arguments(tmp_path):
    ledger, request = ledger_fixture(tmp_path), request_fixture()
    client = Client(response_fixture(' {"typed":"unaltered actual arguments"} \n'))
    artifact = call(ledger, client, request, episode_id="v4-slot/s0/reviewer1")
    assert artifact["wire_protocol"] == "v6_slot_review.v4"
    assert artifact["reviewer"] == 1 and artifact["review_format_error"] is None
    assert artifact["content"] is None
    assert artifact["review_text"] == ' {"typed":"unaltered actual arguments"} \n'
    assert client.calls[0][0] == artifact["endpoint"] == STRICT_ENDPOINT
    body = json.loads(client.calls[0][1]["content"])
    assert body["tools"] == [request["strict_tool"]]
    assert body["tools"][0]["function"]["name"] == "submit_review"
    assert body["tools"][0]["function"]["strict"] is True
    assert body["thinking"] == {"type": "disabled"} and body["model"] == "deepseek-flash"
    assert body["temperature"] == 0 and body["max_tokens"] == 16384
    assert "response_format" not in body
    assert json.loads(body["messages"][1]["content"])["wire_protocol"] == "v6_slot_review.v4"


def test_typed_v4_cannot_mislabel_stage_or_bypass_existing_catalog_binding(tmp_path):
    ledger, client = ledger_fixture(tmp_path), Client(response_fixture())
    request, before = request_fixture(), ledger.snapshot()
    request["wire_protocol"] = "v6_slot_review.v3"
    with pytest.raises(ValueError, match="strict"):
        call(ledger, client, request)
    request = request_fixture()
    request["catalog_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="compact"):
        call(ledger, client, request)
    assert client.calls == [] and ledger.snapshot() == before
