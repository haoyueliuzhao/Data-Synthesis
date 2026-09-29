"""One budgeted V10 annotation call, direct verified TLS and exact settled replay.

The transport has no financial rubric, no gold flag and no 16384-token minimum.
Ordinary invalid annotation strings remain exact settled originals, never repaired.
"""

from __future__ import annotations

import copy
import hashlib
import json
import weakref

import httpx

from .contracts import ProviderCallError, digest, invocation_identity
from .probe_budget import V6_PURPOSE, ProbeBudget, _request_record_digest
from .providers import _json
from .qwen_protocol import strict_json_decoder
from .v6_review_provider import _strict_review_payload
from .v10_process_review import bound, require
from .v10_review_protocol import checked_request

MODEL = "deepseek-flash"
ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
NETWORK_REASON = "v10 transport response or usage unknown"
_DIRECT_CLIENTS = weakref.WeakSet()


def direct_client(*, timeout=120.0):
    client = httpx.AsyncClient(
        timeout=timeout,
        trust_env=False,
        verify=True,
        transport=httpx.AsyncHTTPTransport(retries=0, trust_env=False, verify=True),
    )
    _DIRECT_CLIENTS.add(client)
    return client


def request_body(request):
    checked_request(request)
    body = dict(
        model=MODEL,
        messages=copy.deepcopy(request["messages"]),
        tools=[copy.deepcopy(request["strict_tool"])],
        tool_choice={"type": "function", "function": {"name": "submit_review"}},
        temperature=0,
        top_p=1,
        max_tokens=request["max_output_tokens"],
        thinking={"type": "disabled"},
        stream=False,
    )
    require(
        len(_json(body).encode()) + request["max_output_tokens"] < 1048576,
        "full visible request/output envelope too large; no truncation",
    )
    return body


def _binding(request):
    return dict(
        wire_protocol=request["wire_protocol"],
        protocol_id=request["protocol_id"],
        policy_id=request["policy_id"],
        role=request["role"],
        production_request_id=request["id"],
        semantic_review_request_sha256=digest(request),
        endpoint=ENDPOINT,
    )


def _response(value, request):
    require(
        isinstance(value, dict) and value.get("model") == MODEL,
        "response model is not deepseek-flash",
    )
    usage = value.get("usage", {})
    required = (
        "prompt_tokens",
        "completion_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "total_tokens",
    )
    require(
        all(type(usage.get(k)) is int and usage[k] >= 0 for k in required)
        and usage["prompt_tokens"]
        == usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"]
        and usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
        and usage["completion_tokens"] <= request["max_output_tokens"]
        and usage["prompt_tokens"] <= 1048576,
        "original usage is absent or inconsistent",
    )
    choices = value.get("choices")
    require(
        isinstance(value.get("id"), str)
        and value["id"]
        and isinstance(choices, list)
        and len(choices) == 1,
        "one real response choice required",
    )
    choice = choices[0]
    finish, message = choice.get("finish_reason"), choice.get("message")
    require(
        finish in {"tool_calls", "stop", "length", "content_filter"} and isinstance(message, dict),
        "interrupted/invalid response envelope",
    )
    require(
        message.get("reasoning_content") in (None, "")
        and (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) == 0,
        "private reasoning/thinking tokens are outside the frozen call",
    )
    require(
        message.get("content") is None or isinstance(message.get("content"), str),
        "response content must be original text or null",
    )
    return message, finish


def restore_artifact(ledger_row, request):
    """Read-only reconstruction of exactly one SETTLED original; no reserve/send.

    A response with malformed review JSON is still reconstructed without parsing
    or repair. Service/billing/transport failures never become successful receipts.
    """
    body = request_body(request)
    row = ledger_row
    require(
        isinstance(row, dict)
        and row.get("state") == "SETTLED"
        and row.get("response_classification") == "model_response"
        and type(row.get("http_status")) is int
        and 200 <= row["http_status"] < 300
        and row.get("dispatched_at") is not None
        and row.get("settled_at") is not None
        and type(row.get("settled_microcny")) is int
        and row["settled_microcny"] >= 0,
        "only an actual settled model response can be restored",
    )
    coords = json.loads(row["coordinates_json"])
    attempt_index = coords.get("attempt_index")
    if attempt_index != 1:
        from .v10_network_retry import validate_retry_row_evidence

        validate_retry_row_evidence(row, _json(body).encode())
    expected = invocation_identity(
        dict(
            run_id=coords["run_id"], episode_id=request["episode_id"], attempt_index=attempt_index
        ),
        turn_index=0,
    )
    require(
        coords == expected
        and row["invocation_id"] == coords["invocation_id"]
        and row["request_body"] == _json(body).encode()
        and row["request_sha256"] == digest(body),
        "settled request identity/HTTP bytes changed",
    )
    raw = row["response_body"]
    require(
        isinstance(raw, bytes) and hashlib.sha256(raw).hexdigest() == row["response_sha256"],
        "original response bytes are missing or changed",
    )
    text = raw.decode("utf-8")
    value = strict_json_decoder().decode(text)
    message, finish = _response(value, request)
    evidence = json.loads(row["evidence_json"])
    require(
        all(evidence.get(k) == v for k, v in _binding(request).items())
        and evidence.get("response_id") == value["id"]
        and evidence.get("finish_reason") == finish
        and json.loads(row["usage_json"]) == value["usage"]
        and evidence.get("automatic_retry") is False
        and isinstance(evidence.get("price_sheet_id"), str),
        "settled metadata/usage binding changed",
    )
    return bound(
        dict(
            schema="v10_settled_annotation_artifact.v1",
            **_binding(request),
            budget_invocation_id=row["invocation_id"],
            budget_coordinates=coords,
            public_request=body,
            request_sha256=digest(body),
            public_request_body_sha256=hashlib.sha256(row["request_body"]).hexdigest(),
            api_response_raw=text,
            raw_api_response_sha256=row["response_sha256"],
            api_response=value,
            usage=copy.deepcopy(value["usage"]),
            http_status=row["http_status"],
            peak_tariff_upper_bound_microcny=row["settled_microcny"],
            budget_reserved_microcny=row["reserved_microcny"],
            price_sheet_id=evidence["price_sheet_id"],
            content=message.get("content"),
            finish_reason=finish,
            **_strict_review_payload(message, finish),
            actual_model_calls=1,
            retries=0,
            content_repair_performed=False,
            ledger_record_sha256=_request_record_digest(row),
        )
    )


def validate_paid_artifact(request, artifact, ledger_record):
    restored = restore_artifact(ledger_record, request)
    require(
        restored == artifact, "production annotation must be the exact original settled response"
    )
    return dict(
        invocation_id=artifact["budget_invocation_id"],
        coordinates=artifact["budget_coordinates"],
        original_request_sha256=artifact["request_sha256"],
        original_request_body_sha256=artifact["public_request_body_sha256"],
        original_response_sha256=artifact["raw_api_response_sha256"],
        original_ledger_record_sha256=artifact["ledger_record_sha256"],
        usage_sha256=digest(artifact["usage"]),
        settled_microcny=artifact["peak_tariff_upper_bound_microcny"],
        state="SETTLED",
        actual_response_and_usage_bound=True,
    )


async def request_review(
    *, ledger, api_key, request, client=None, timeout=120.0, resume_reserved=False, attempt_index=1
):
    require(
        isinstance(ledger, ProbeBudget)
        and ledger.purpose == V6_PURPOSE
        and ledger.price_sheet.model == MODEL,
        "same dedicated flash wallet required",
    )
    require(isinstance(api_key, str) and api_key, "in-memory API credential required")
    require(
        ledger.snapshot().get("v10_partition", {}).get("batch_id") == request["protocol_id"],
        "V10 production requires this batch's existing-wallet purpose registration",
    )
    # Real shared clients must be constructed by the fixed direct/TLS factory.
    # Non-httpx injected clients are only CPU mock transports used by unit tests.
    require(
        not isinstance(client, httpx.AsyncClient) or client in _DIRECT_CLIENTS,
        "shared HTTP client must use direct_client: no proxy/TLS/retry variant",
    )
    body = request_body(request)
    wire = _json(body).encode()
    require(api_key.encode() not in wire, "credential cannot enter retained model input")
    require(
        type(attempt_index) is int and attempt_index in (1, 2),
        "only original or expressly permitted second attempt",
    )
    coords = invocation_identity(
        dict(run_id=ledger.run_id, episode_id=request["episode_id"], attempt_index=attempt_index),
        turn_index=0,
    )
    iid = coords["invocation_id"]
    local = {**_binding(request), "price_sheet_id": ledger.price_sheet.id}
    if attempt_index != 1:
        require(type(attempt_index) is int and attempt_index == 2, "no automatic or third attempt")
        from .v10_network_retry import provider_retry_binding

        local.update(provider_retry_binding(ledger, request, wire))
    if resume_reserved:
        from .v10_budget import continue_reserved

        continue_reserved(ledger, iid, coordinates=coords, request=body, request_body=wire)
    else:
        ledger.reserve(iid, coordinates=coords, request=body, request_body=wire)
    ledger.mark_dispatched(iid)

    def unknown(reason, *, raw=None, status=None, extra=None):
        evidence = dict(
            **local,
            request_sha256=digest(body),
            budget_invocation_id=iid,
            budget_coordinates=coords,
            billing_usage_known=False,
            reservation_retained=True,
            automatic_retry=False,
            **(extra or {}),
        )
        ledger.unknown(iid, reason=reason, response_body=raw, http_status=status, evidence=evidence)
        return ProviderCallError(
            reason, settlement="unknown", actual_model_calls=1, evidence=evidence
        )

    headers = {"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}
    try:
        if client is None:
            async with direct_client(timeout=timeout) as actual:
                response = await actual.post(ENDPOINT, content=wire, headers=headers)
        else:
            response = await client.post(ENDPOINT, content=wire, headers=headers, timeout=timeout)
    except BaseException as failure:
        error = unknown(
            NETWORK_REASON,
            extra=dict(exception_type=type(failure).__name__, service_response_received=False),
        )
        if not isinstance(failure, Exception):
            raise
        raise error from failure
    try:
        status, raw = response.status_code, response.content
        require(
            type(status) is int and isinstance(raw, bytes),
            "auditable status/response bytes missing",
        )
    except Exception as failure:
        raise unknown(
            "v10 unauditable transport response", extra=dict(exception_type=type(failure).__name__)
        ) from failure
    if api_key.encode() in raw:
        raise unknown(
            "v10 response echoed credential",
            raw=raw.replace(api_key.encode(), b"<REDACTED_API_KEY>"),
            status=status,
            extra=dict(
                credential_redacted=True, original_response_sha256=hashlib.sha256(raw).hexdigest()
            ),
        )
    try:
        value = strict_json_decoder().decode(raw.decode("utf-8"))
        require(isinstance(value, dict), "original API envelope is not an object")
        ledger.price_sheet.usage(value.get("usage"), output_limit=request["max_output_tokens"])
        if 200 <= status < 300:
            require(value.get("model") == MODEL, "response model changed")
    except (ValueError, TypeError, KeyError) as failure:
        raise unknown(
            "v10 returned usage/model contract unknown",
            raw=raw,
            status=status,
            extra=dict(exception_type=type(failure).__name__, service_response_received=True),
        ) from failure

    def settle(classification, extra):
        try:
            return ledger.settle(
                iid,
                usage=value["usage"],
                http_status=status,
                response_classification=classification,
                response_body=raw,
                evidence={**local, "automatic_retry": False, **extra},
            )
        except Exception as failure:
            row = ledger.request_record(iid)
            if row and row["state"] == "DISPATCHED":
                raise unknown(
                    "v10 tariff settlement failed",
                    raw=raw,
                    status=status,
                    extra=dict(exception_type=type(failure).__name__),
                ) from failure
            raise

    if not 200 <= status < 300:
        amount = settle("service_failure", dict(http_status=status))
        raise ProviderCallError(
            f"V10 annotation HTTP {status}; no retry",
            settlement="service_failure",
            actual_model_calls=1,
            evidence=dict(
                budget_invocation_id=iid,
                billing_usage_known=True,
                peak_tariff_upper_bound_microcny=amount,
            ),
        )
    try:
        _, finish = _response(value, request)
    except (ValueError, TypeError, KeyError, AttributeError) as failure:
        amount = settle(
            "invalid_or_interrupted_response", dict(exception_type=type(failure).__name__)
        )
        raise ProviderCallError(
            "V10 annotation envelope interrupted/invalid",
            settlement="unknown",
            actual_model_calls=1,
            evidence=dict(
                budget_invocation_id=iid,
                billing_usage_known=True,
                peak_tariff_upper_bound_microcny=amount,
            ),
        ) from failure
    settle("model_response", dict(response_id=value["id"], finish_reason=finish))
    return restore_artifact(ledger.request_record(iid), request)
