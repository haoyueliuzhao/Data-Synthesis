"""One fresh V16 call: exact bytes, official usage, explicit proxy, zero retries."""

import copy
import hashlib
import json
import weakref

import httpx

from .contracts import ProviderCallError, digest, invocation_identity
from .probe_budget import V6_PURPOSE, ProbeBudget, _request_record_digest
from .providers import _json
from .qwen_protocol import strict_json_decoder
from .v16_adjudication_protocol import (
    ENDPOINT,
    MODEL,
    bound,
    checked_request,
    inspect_paid_annotation,
    request_body,
    require,
)
from .v16_budget import NETWORK_REASON, continue_reserved, read_matrix_permit

_CLIENTS = weakref.WeakSet()


def annotation_client(*, timeout=1200.0, proxy=None):
    require(
        isinstance(timeout, (int, float)) and timeout >= 900,
        "read timeout must cover the documented server queue window",
    )
    limits = httpx.Limits(max_connections=16, max_keepalive_connections=16)
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=30.0, pool=60.0),
        trust_env=False,
        verify=True,
        transport=httpx.AsyncHTTPTransport(
            retries=0,
            trust_env=False,
            verify=True,
            proxy=proxy,
            limits=limits,
        ),
    )
    _CLIENTS.add(client)
    return client


def _binding(request):
    return dict(
        wire_protocol=request["wire_protocol"],
        protocol_id=request["protocol_id"],
        policy_id=request["policy_id"],
        role=request["role"],
        purpose=request["purpose"],
        production_request_id=request["id"],
        semantic_review_request_sha256=digest(request),
        endpoint=ENDPOINT,
    )


def _material_payload(message, finish, request):
    result = dict(
        review_text=None,
        review_payload_source=None,
        review_tool_call_id=None,
        review_format_error=None,
    )
    calls = message.get("tool_calls")
    name = request["strict_tool"]["function"]["name"]
    if not isinstance(calls, list) or len(calls) != 1:
        result["review_format_error"] = "expected_exactly_one_material_tool_call"
        return result
    call = calls[0]
    if (
        not isinstance(call, dict)
        or call.get("type") != "function"
        or not isinstance(call.get("id"), str)
        or not call["id"].strip()
        or not isinstance(call.get("function"), dict)
        or call["function"].get("name") != name
        or not isinstance(call["function"].get("arguments"), str)
    ):
        result["review_format_error"] = "invalid_material_tool_name_id_or_argument_string"
        return result
    result.update(
        review_text=call["function"]["arguments"],
        review_payload_source="tool_call.function.arguments",
        review_tool_call_id=call["id"],
        review_format_error=None if finish == "tool_calls" else "strict_finish_not_tool_calls",
    )
    return result


def _response(value, request):
    require(
        isinstance(value, dict) and value.get("model") == MODEL,
        "response model is not deepseek-flash",
    )
    usage = value.get("usage", {})
    keys = (
        "prompt_tokens",
        "completion_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "total_tokens",
    )
    require(
        all(type(usage.get(k)) is int and usage[k] >= 0 for k in keys)
        and usage["prompt_tokens"]
        == usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"]
        and usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
        and usage["completion_tokens"] <= request["max_output_tokens"]
        and usage["prompt_tokens"] <= 1048576,
        "usage missing/inconsistent",
    )
    choices = value.get("choices")
    require(
        isinstance(value.get("id"), str)
        and value["id"]
        and isinstance(choices, list)
        and len(choices) == 1,
        "one real response required",
    )
    finish, message = choices[0].get("finish_reason"), choices[0].get("message")
    require(
        finish in {"tool_calls", "stop", "length", "content_filter"} and isinstance(message, dict),
        "invalid/interrupted response envelope",
    )
    require(
        message.get("reasoning_content") in (None, "")
        and (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) == 0,
        "private thinking outside registered call",
    )
    require(
        message.get("content") is None or isinstance(message["content"], str),
        "original response content must be text/null",
    )
    return message, finish


def restore_settled(row, request):
    """Read only, no reserve/send and no repair of the original annotation string."""
    body = request_body(request)
    wire = _json(body).encode()
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
        "only real settled model response may be restored",
    )
    coords = json.loads(row["coordinates_json"])
    expected = invocation_identity(
        dict(run_id=coords["run_id"], episode_id=request["episode_id"], attempt_index=1),
        turn_index=0,
    )
    require(
        coords == expected
        and row["invocation_id"] == coords["invocation_id"]
        and row["request_body"] == wire
        and row["request_sha256"] == digest(body),
        "settled request identity/bytes changed",
    )
    raw = row["response_body"]
    require(
        isinstance(raw, bytes) and hashlib.sha256(raw).hexdigest() == row["response_sha256"],
        "original response missing/changed",
    )
    value = strict_json_decoder().decode(raw.decode("utf-8"))
    message, finish = _response(value, request)
    evidence = json.loads(row["evidence_json"])
    require(
        all(evidence.get(k) == v for k, v in _binding(request).items())
        and evidence.get("response_id") == value["id"]
        and evidence.get("finish_reason") == finish
        and json.loads(row["usage_json"]) == value["usage"]
        and evidence.get("automatic_retry") is False
        and isinstance(evidence.get("price_sheet_id"), str),
        "settled evidence/usage changed",
    )
    return bound(
        dict(
            schema="v16_settled_material_artifact.v1",
            **_binding(request),
            budget_invocation_id=row["invocation_id"],
            budget_coordinates=coords,
            public_request=body,
            request_sha256=digest(body),
            public_request_body_sha256=hashlib.sha256(wire).hexdigest(),
            api_response_raw=raw.decode("utf-8"),
            raw_api_response_sha256=row["response_sha256"],
            api_response=value,
            usage=copy.deepcopy(value["usage"]),
            http_status=row["http_status"],
            peak_tariff_upper_bound_microcny=row["settled_microcny"],
            budget_reserved_microcny=row["reserved_microcny"],
            price_sheet_id=evidence["price_sheet_id"],
            content=message.get("content"),
            finish_reason=finish,
            **_material_payload(message, finish, request),
            actual_model_calls=1,
            retries=0,
            content_repair_performed=False,
            ledger_record_sha256=_request_record_digest(row),
        )
    )


def paid_record(request, artifact, row):
    require(restore_settled(row, request) == artifact, "paid receipt is not exact settled replay")
    inspected = inspect_paid_annotation(request, artifact)
    return bound(
        dict(
            schema="v16_paid_material_annotation.v1",
            request=copy.deepcopy(request),
            artifact=copy.deepcopy(artifact),
            inspection=inspected,
            actual_model_call_receipt_verified=True,
            role=request["role"],
            purpose=request["purpose"],
            slot_id=request.get("slot_id"),
            slot_ids=[view["slot_id"] for view in request["views"]],
            task_id=request["task_id"],
            protocol_id=request["protocol_id"],
        )
    )


async def request_once(*, ledger, api_key, request, client, timeout=1200.0, resume_reserved=False):
    checked_request(request)
    require(
        isinstance(ledger, ProbeBudget)
        and ledger.purpose == V6_PURPOSE
        and ledger.price_sheet.model == MODEL
        and isinstance(api_key, str)
        and api_key,
        "same original flash wallet and in-memory key required",
    )
    require(
        client is not None and (not isinstance(client, httpx.AsyncClient) or client in _CLIENTS),
        "explicit registered TLS/proxy client required; no environment fallback",
    )
    require(
        isinstance(timeout, (int, float)) and timeout >= 900,
        "registered read timeout >=900 required",
    )
    with ledger._transaction() as db:
        permit = read_matrix_permit(db, ledger.config)
        require(
            permit is not None and permit["protocol_id"] == request["protocol_id"],
            "request must bind registered V16 protocol",
        )
    body = request_body(request)
    wire = _json(body).encode()
    require(api_key.encode() not in wire, "key cannot enter retained model input")
    coords = invocation_identity(
        dict(run_id=ledger.run_id, episode_id=request["episode_id"], attempt_index=1), turn_index=0
    )
    iid = coords["invocation_id"]
    local = {**_binding(request), "price_sheet_id": ledger.price_sheet.id}
    if resume_reserved:
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

    try:
        response = await client.post(
            ENDPOINT,
            content=wire,
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            timeout=httpx.Timeout(timeout, connect=30.0, pool=60.0),
        )
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
        require(type(status) is int and isinstance(raw, bytes), "auditable status/bytes missing")
    except Exception as failure:
        raise unknown(
            "v16 unauditable transport response", extra=dict(exception_type=type(failure).__name__)
        ) from failure
    if api_key.encode() in raw:
        raise unknown(
            "v16 response echoed credential",
            raw=raw.replace(api_key.encode(), b"<REDACTED_API_KEY>"),
            status=status,
            extra=dict(
                credential_redacted=True, original_response_sha256=hashlib.sha256(raw).hexdigest()
            ),
        )
    try:
        value = strict_json_decoder().decode(raw.decode("utf-8"))
        require(isinstance(value, dict), "API envelope must be an object")
        ledger.price_sheet.usage(value.get("usage"), output_limit=request["max_output_tokens"])
        if 200 <= status < 300:
            require(value.get("model") == MODEL, "response model changed")
    except (ValueError, TypeError, KeyError) as failure:
        raise unknown(
            "v16 returned usage/model contract unknown",
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
            if ledger.request_record(iid)["state"] == "DISPATCHED":
                raise unknown(
                    "v16 tariff settlement failed",
                    raw=raw,
                    status=status,
                    extra=dict(exception_type=type(failure).__name__),
                ) from failure
            raise

    if not 200 <= status < 300:
        amount = settle("service_failure", dict(http_status=status))
        raise ProviderCallError(
            f"V16 HTTP {status}; no retry",
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
            "V16 invalid/interrupted response",
            settlement="unknown",
            actual_model_calls=1,
            evidence=dict(
                budget_invocation_id=iid,
                billing_usage_known=True,
                peak_tariff_upper_bound_microcny=amount,
            ),
        ) from failure
    settle("model_response", dict(response_id=value["id"], finish_reason=finish))
    return restore_settled(ledger.request_record(iid), request)
