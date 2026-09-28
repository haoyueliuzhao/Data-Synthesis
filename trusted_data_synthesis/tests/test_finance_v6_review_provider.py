"""Mock HTTP only: review artifacts, joint tariff accounting, and fail-stop recovery."""

import asyncio
import copy
import hashlib
import json

import pytest
from test_finance_research_probe_budget import budget, usage
from test_finance_research_probe_provider import Client, value
from test_finance_semantic_review import fixture_bundle
from test_finance_v6_probe_budget import reserve, v6_budget

from trusted_synthesis.finance_research.contracts import ProviderCallError, digest
from trusted_synthesis.finance_research.probe_budget import BudgetUnavailable, DuplicateInvocation
from trusted_synthesis.finance_research.semantic_review import review_request
from trusted_synthesis.finance_research.v6_review_provider import request_review

KEY = "fixture-review-secret-123456789"


def request(reviewer=0):
    return review_request(fixture_bundle(), {"program": "add(120, 0)", "answer": 120}, reviewer)


def response(content=' {"not_the_rubric_schema":true} \n', finish="stop", **changes):
    result = value(**changes)
    result["choices"] = [
        {"finish_reason": finish, "message": {"role": "assistant", "content": content}}
    ]
    return result


def call(ledger, client, req=None, episode="review/task/reviewer0"):
    return asyncio.run(
        request_review(
            ledger=ledger,
            api_key=KEY,
            episode_id=episode,
            request=request() if req is None else req,
            client=client,
        )
    )


def test_actual_wire_and_all_artifact_bindings_match_joint_ledger(tmp_path):
    ledger = v6_budget(tmp_path)
    client = Client(response(usage=usage(output=10000)))
    req = request()
    artifact = call(ledger, client, req)
    wire = client.calls[0][1]["content"]
    body = json.loads(wire)
    assert body == artifact["public_request"]
    assert body == {
        "model": "deepseek-flash",
        "messages": req["messages"],
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 16384,
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "stream": False,
    }
    assert "reviewer" not in body and "document_index" not in body
    assert artifact["request_sha256"] == digest(body)
    assert artifact["public_request_body_sha256"] == hashlib.sha256(wire).hexdigest()
    assert artifact["semantic_review_request_sha256"] == digest(req)
    assert artifact["review_request_metadata_sha256"] == digest(req)
    assert artifact["reviewer"] == json.loads(req["messages"][1]["content"])["reviewer"] == 0
    for field in ("task_bundle_sha256", "rubric_sha256"):
        assert artifact[field] == req[field]
    saved = ledger.request_record(artifact["budget_invocation_id"])
    assert saved["state"] == "SETTLED" and saved["request_body"] == wire
    assert saved["response_body"].decode() == artifact["api_response_raw"]
    assert saved["response_sha256"] == artifact["raw_api_response_sha256"]
    assert artifact["api_response"] == client.response
    assert artifact["budget_reserved_microcny"] == 2_228_224
    assert (
        artifact["peak_tariff_upper_bound_microcny"]
        == ledger.snapshot()["settled_tariff_microcny"]
        == 80_120
    )
    assert artifact["actual_model_calls"] == 1 and artifact["retries"] == 0
    assert KEY.encode() not in saved["request_body"] + saved["response_body"]


@pytest.mark.parametrize(
    "content,finish",
    [("```json\n{not JSON}\n```", "stop"), (None, "stop"), (" {truncated", "length")],
)
def test_bad_semantic_content_is_preserved_and_paid_not_transport_failure(
    tmp_path, content, finish
):
    ledger = v6_budget(tmp_path)
    artifact = call(ledger, Client(response(content, finish)))
    assert artifact["content"] == content and artifact["finish_reason"] == finish
    assert artifact["content_repair_performed"] is False
    assert ledger.snapshot()["settled_tariff_microcny"] == 280
    assert ledger.snapshot()["halt"] is None
    assert not ledger.unsettled()


@pytest.mark.parametrize(
    "case", ["model", "thinking", "reasoning_usage", "over_limit", "missing_usage"]
)
def test_model_thinking_or_unknown_usage_preserves_full_hold_and_stops_both_purposes(
    tmp_path, case
):
    returned = response()
    if case == "model":
        returned["model"] = "other-model"
    elif case == "thinking":
        returned["choices"][0]["message"]["reasoning_content"] = "not requested"
    elif case == "reasoning_usage":
        returned["usage"]["completion_tokens_details"] = {"reasoning_tokens": 1}
    elif case == "over_limit":
        returned["usage"] = usage(output=16385)
    else:
        del returned["usage"]
    ledger, client = v6_budget(tmp_path), Client(returned)
    with pytest.raises(ProviderCallError) as caught:
        call(ledger, client)
    assert caught.value.settlement == "unknown" and caught.value.actual_model_calls == 1
    assert len(client.calls) == 1 and ledger.snapshot()["unknown_requests"] == 1
    assert ledger.snapshot()["held_microcny"] == 2_228_224
    assert ledger.snapshot()["settled_tariff_microcny"] == 0
    for cap in (2048, 16384):
        with pytest.raises(BudgetUnavailable):
            reserve(ledger, f"blocked-{cap}", cap)


@pytest.mark.parametrize("failure", [TimeoutError("mock timeout"), asyncio.CancelledError()])
def test_transport_failure_and_cancellation_never_retry_or_release_unknown(tmp_path, failure):
    ledger, client = v6_budget(tmp_path), Client(failure=failure)
    expected = (
        asyncio.CancelledError if isinstance(failure, asyncio.CancelledError) else ProviderCallError
    )
    with pytest.raises(expected):
        call(ledger, client)
    assert len(client.calls) == 1
    assert ledger.snapshot()["unknown_requests"] == 1
    assert ledger.snapshot()["held_microcny"] == 2_228_224


def test_http_failure_known_usage_is_charged_but_stops(tmp_path):
    ledger, client = (
        v6_budget(tmp_path),
        Client({"error": "mock unavailable", "usage": usage()}, status=503),
    )
    with pytest.raises(ProviderCallError) as caught:
        call(ledger, client)
    assert caught.value.settlement == "service_failure"
    assert caught.value.evidence["billing_usage_known"] is True
    assert ledger.snapshot()["settled_tariff_microcny"] == 280
    assert ledger.snapshot()["held_microcny"] == 0 and ledger.snapshot()["halt"]


def test_credential_echo_is_redacted_before_durable_storage(tmp_path):
    ledger = v6_budget(tmp_path)
    with pytest.raises(ProviderCallError):
        call(ledger, Client(response("echo " + KEY)))
    saved = ledger.request_record(ledger.unsettled()[0]["invocation_id"])
    assert (
        KEY.encode() not in saved["response_body"]
        and b"<REDACTED_API_KEY>" in saved["response_body"]
    )
    assert json.loads(saved["evidence_json"])["credential_redacted"] is True
    assert ledger.snapshot()["held_microcny"] == 2_228_224


def test_exact_invocation_never_reissued_and_metadata_tamper_or_legacy_fail_before_send(tmp_path):
    ledger, client = v6_budget(tmp_path), Client(response())
    call(ledger, client)
    with pytest.raises(DuplicateInvocation):
        call(ledger, client)
    assert len(client.calls) == 1
    original = request()
    for field, replacement in (
        ("reviewer", 1),
        ("rubric_sha256", "0" * 64),
        ("task_bundle_sha256", "0" * 64),
        ("messages_model_sha256", "0" * 64),
    ):
        changed = copy.deepcopy(original)
        changed[field] = replacement
        with pytest.raises(ValueError):
            call(ledger, client, changed, episode="other-identity")
    assert len(client.calls) == 1 and ledger.snapshot()["requests_reserved"] == 1
    legacy_client = Client(response())
    with pytest.raises(ValueError, match="joint budget"):
        call(budget(tmp_path / "legacy"), legacy_client)
    assert not legacy_client.calls
