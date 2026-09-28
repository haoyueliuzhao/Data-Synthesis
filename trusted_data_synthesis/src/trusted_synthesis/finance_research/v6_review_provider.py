"""One paid V6 semantic-review request, bound to the shared generation/review ledger.

This transport does not parse, repair, validate or accept the review's content JSON.
It preserves the real response for the separate semantic rubric. No retry/fallback.
"""

from __future__ import annotations

import copy
import hashlib

from .contracts import ProviderCallError, digest, invocation_identity
from .probe_budget import V6_PURPOSE, ProbeBudget
from .probe_provider import ENDPOINT, INFRA_FINISH_REASONS, MODEL
from .providers import _json
from .qwen_protocol import strict_json_decoder

OUTPUT_LIMIT = 16384
STRICT_WIRE_PROTOCOL = "v6_strict_review.v2"
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"


def _strict_tool(request, payload):
    tool = request.get("strict_tool")
    if (
        not isinstance(tool, dict)
        or set(tool) != {"type", "function"}
        or tool["type"] != "function"
        or not isinstance(tool["function"], dict)
    ):
        raise ValueError("strict review requires one explicit function schema")
    function = tool["function"]
    parameters = function.get("parameters")
    if (
        set(function) - {"name", "description", "strict", "parameters"}
        or function.get("name") != "submit_review"
        or function.get("strict") is not True
        or not isinstance(parameters, dict)
        or parameters.get("type") != "object"
        or "output_schema" in payload
        or "strict_tool" in payload
        or payload.get("wire_protocol") != STRICT_WIRE_PROTOCOL
        or request.get("strict_tool_sha256") != digest(tool)
    ):
        raise ValueError("strict submit_review schema belongs only in the bound tool declaration")

    def inline(value):
        if isinstance(value, dict):
            if "$ref" in value or "$defs" in value or "definitions" in value:
                raise ValueError("strict review schema must be inline, not unresolved references")
            for child in value.values():
                inline(child)
        elif isinstance(value, list):
            for child in value:
                inline(child)

    inline(parameters)
    return copy.deepcopy(tool)


def _strict_review_payload(message, finish):
    """Extract a real function-argument string only; never interpret or repair its JSON."""
    result = dict(
        review_text=None,
        review_payload_source=None,
        review_tool_call_id=None,
        review_format_error=None,
    )
    calls = message.get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1:
        result["review_format_error"] = "expected_exactly_one_submit_review_tool_call"
        return result
    call = calls[0]
    if (
        not isinstance(call, dict)
        or call.get("type") != "function"
        or not isinstance(call.get("id"), str)
        or not call["id"].strip()
        or not isinstance(call.get("function"), dict)
        or call["function"].get("name") != "submit_review"
        or not isinstance(call["function"].get("arguments"), str)
    ):
        result["review_format_error"] = "invalid_submit_review_name_id_or_argument_string"
        return result
    result.update(
        review_text=call["function"]["arguments"],
        review_payload_source="tool_call.function.arguments",
        review_tool_call_id=call["id"],
        review_format_error=None if finish == "tool_calls" else "strict_finish_not_tool_calls",
    )
    return result


def _request_body(ledger, request):
    if not isinstance(ledger, ProbeBudget) or ledger.purpose != V6_PURPOSE:
        raise ValueError("V6 reviews require the same dedicated joint budget purpose")
    if request.get("model") != MODEL or ledger.price_sheet.model != MODEL:
        raise ValueError("review model must be exactly deepseek-flash")
    messages = request.get("messages")
    if (
        not isinstance(messages, list)
        or len(messages) != 2
        or [message.get("role") for message in messages] != ["system", "user"]
        or any(not isinstance(message.get("content"), str) for message in messages)
    ):
        raise ValueError("review requires the complete fixed system/user request")
    if (
        type(request.get("reviewer")) is not int
        or request["reviewer"] not in (0, 1)
        or request.get("private_reference_for_review_only") is not True
        or request.get("other_reviewer_output_visible") is not False
        or request.get("messages_model_sha256") != digest({"model": MODEL, "messages": messages})
        or request.get("rubric_sha256") != digest(messages[0]["content"])
    ):
        raise ValueError("semantic review metadata/request binding differs")
    payload = strict_json_decoder().decode(messages[1]["content"])
    strict = request.get("wire_protocol") == STRICT_WIRE_PROTOCOL
    compact = request.get("wire_protocol") in {"v6_compact_review.v1", STRICT_WIRE_PROTOCOL}
    if (
        not isinstance(payload, dict)
        or payload.get("task_bundle_sha256") != request.get("task_bundle_sha256")
        or type(payload.get("reviewer")) is not int
        or payload["reviewer"] not in (0, 1)
        or request["reviewer"] != payload["reviewer"]
    ):
        raise ValueError("review task bundle/reviewer/documents differ from sent payload")
    if compact:
        if (
            not ledger.config.get("amendment_id")
            or payload.get("document_catalog") != request.get("document_catalog")
            or request.get("catalog_sha256") != digest(request.get("document_catalog"))
            or not request.get("capacity_policy_id")
            or type(request.get("max_output_tokens")) is not int
            or request["max_output_tokens"] not in ledger.allowed_output_limits
            or request["max_output_tokens"] < OUTPUT_LIMIT
        ):
            raise ValueError("compact review requires its amended joint budget and bound capacity")
        output_limit = request["max_output_tokens"]
    else:
        if request.get("wire_protocol") is not None or payload.get("document_index") != request.get(
            "document_index"
        ):
            raise ValueError("review document index or wire protocol differs")
        output_limit = OUTPUT_LIMIT
    body = dict(
        model=MODEL,
        messages=copy.deepcopy(messages),
        temperature=0,
        top_p=1,
        max_tokens=output_limit,
        thinking={"type": "disabled"},
        stream=False,
    )
    if strict:
        body.update(
            tools=[_strict_tool(request, payload)],
            tool_choice={"type": "function", "function": {"name": "submit_review"}},
        )
    else:
        body["response_format"] = {"type": "json_object"}
    return body, payload["reviewer"]


async def request_review(*, ledger, api_key, episode_id, request, client=None, timeout=120.0):
    """Send exactly once; unknown cost/execution halts the entire shared budget.

    ``episode_id`` is the controller's fixed task/reviewer identity. Attempt is 1,
    turn is 0; calling again with that identity is refused by the persistent ledger.
    No semantic content failure is treated as a transport/billing failure.
    """
    if not isinstance(api_key, str) or not api_key:
        raise ValueError("caller must supply an in-memory API key")
    body, reviewer = _request_body(ledger, request)
    strict = request.get("wire_protocol") == STRICT_WIRE_PROTOCOL
    endpoint = STRICT_ENDPOINT if strict else ENDPOINT
    output_limit = body["max_tokens"]
    wire = _json(body).encode("utf-8")
    if api_key.encode() in wire:
        raise ValueError("credential must not appear in a retained public request")
    coordinates = invocation_identity(
        {"run_id": ledger.run_id, "episode_id": episode_id, "attempt_index": 1}, turn_index=0
    )
    invocation_id = coordinates["invocation_id"]
    metadata_hash = digest(request)
    local_binding = dict(
        reviewer=reviewer,
        task_bundle_sha256=request["task_bundle_sha256"],
        rubric_sha256=request["rubric_sha256"],
        review_request_metadata_sha256=metadata_hash,
        semantic_review_request_sha256=digest(request),
    )
    if strict:
        local_binding.update(
            wire_protocol=STRICT_WIRE_PROTOCOL,
            endpoint=endpoint,
            strict_tool_sha256=digest(body["tools"][0]),
        )
    reserved = ledger.reserve(
        invocation_id, coordinates=coordinates, request=body, request_body=wire
    )
    ledger.mark_dispatched(invocation_id)
    actual_calls = 0

    def unknown(reason, *, raw=None, status=None, classification="unknown", evidence=None):
        retained = dict(
            request_sha256=digest(body),
            budget_invocation_id=invocation_id,
            budget_coordinates=coordinates,
            billing_usage_known=False,
            reservation_retained=True,
            automatic_retry=False,
            **local_binding,
            **(evidence or {}),
        )
        ledger.unknown(
            invocation_id,
            reason=reason,
            http_status=status,
            response_classification=classification,
            response_body=raw,
            evidence=retained,
        )
        return ProviderCallError(
            reason, settlement="unknown", actual_model_calls=actual_calls, evidence=retained
        )

    headers = {"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}
    try:
        if client is None:
            import httpx

            async with httpx.AsyncClient(
                timeout=timeout, transport=httpx.AsyncHTTPTransport(retries=0)
            ) as actual:
                actual_calls += 1
                response = await actual.post(endpoint, content=wire, headers=headers)
        else:
            actual_calls += 1
            response = await client.post(endpoint, content=wire, headers=headers, timeout=timeout)
    except BaseException as failure:
        error = unknown(
            "review transport response or usage unknown",
            evidence={"exception_type": type(failure).__name__, "service_response_received": False},
        )
        if not isinstance(failure, Exception):
            raise
        raise error from failure
    try:
        status, raw = response.status_code, response.content
        if type(status) is not int or not isinstance(raw, bytes):
            raise ValueError("review response status/body type differs")
    except Exception as failure:
        raise unknown(
            "review transport did not return auditable response bytes",
            evidence={"exception_type": type(failure).__name__},
        ) from failure
    classification = "model_response" if 200 <= status < 300 else "service_failure"
    if api_key.encode() in raw:
        redacted = raw.replace(api_key.encode(), b"<REDACTED_API_KEY>")
        raise unknown(
            "review response echoed credential material",
            raw=redacted,
            status=status,
            classification=classification,
            evidence={
                "credential_redacted": True,
                "raw_response_original_sha256": hashlib.sha256(raw).hexdigest(),
            },
        )
    try:
        raw_text = raw.decode("utf-8")
        value = strict_json_decoder().decode(raw_text)
        if not isinstance(value, dict):
            raise ValueError("review service envelope must be a JSON object")
        ledger.price_sheet.usage(value.get("usage"), output_limit=output_limit)
        if 200 <= status < 300 and value.get("model") != MODEL:
            raise ValueError("review returned another model")
        if 200 <= status < 300:
            for choice in value.get("choices", []):
                if choice.get("message", {}).get("reasoning_content") not in (None, ""):
                    raise ValueError("review returned private reasoning despite disabled thinking")
            if (value["usage"].get("completion_tokens_details") or {}).get(
                "reasoning_tokens", 0
            ) != 0:
                raise ValueError("review returned reasoning usage despite disabled thinking")
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as failure:
        raise unknown(
            "review model/thinking/usage contract is unknown or inconsistent",
            raw=raw,
            status=status,
            classification=classification,
            evidence={"exception_type": type(failure).__name__, "service_response_received": True},
        ) from failure

    def settle(response_class, extra=None):
        try:
            return ledger.settle(
                invocation_id,
                usage=value["usage"],
                http_status=status,
                response_classification=response_class,
                response_body=raw,
                evidence={**local_binding, "automatic_retry": False, **(extra or {})},
            )
        except Exception as failure:
            # Invalid usage or interrupted durable settlement must never become a
            # successful review. If the DB is unavailable, pending state remains.
            row = ledger.request_record(invocation_id)
            if row and row["state"] == "DISPATCHED":
                raise unknown(
                    "review tariff settlement failed",
                    raw=raw,
                    status=status,
                    classification=response_class,
                    evidence={"exception_type": type(failure).__name__},
                ) from failure
            raise

    if classification == "service_failure":
        amount = settle(classification, {"http_status": status})
        raise ProviderCallError(
            f"review API returned HTTP {status}; no retry",
            settlement="service_failure",
            actual_model_calls=1,
            evidence={
                **local_binding,
                "budget_invocation_id": invocation_id,
                "billing_usage_known": True,
                "peak_tariff_upper_bound_microcny": amount,
            },
        )
    try:
        choices = value.get("choices")
        if (
            not isinstance(value.get("id"), str)
            or not value["id"]
            or not isinstance(choices, list)
            or len(choices) != 1
        ):
            raise ValueError("review lacks one actual service response")
        choice = choices[0]
        finish = choice.get("finish_reason")
        if finish in INFRA_FINISH_REASONS or finish not in {
            "stop",
            "length",
            "content_filter",
            "tool_calls",
        }:
            raise ValueError("review lacks a normal completed finish reason")
        message = choice["message"]
        if (
            not isinstance(message, dict)
            or message.get("content") is not None
            and not isinstance(message["content"], str)
        ):
            raise ValueError("review content is not text/null")
        # Deliberately do not parse this string, strip fences, or replace null.
        content = message.get("content")
    except (ValueError, TypeError, KeyError, AttributeError, IndexError) as failure:
        amount = settle(
            "invalid_or_interrupted_response", {"exception_type": type(failure).__name__}
        )
        raise ProviderCallError(
            "review service envelope violates the execution contract",
            settlement="unknown",
            actual_model_calls=1,
            evidence={
                **local_binding,
                "budget_invocation_id": invocation_id,
                "billing_usage_known": True,
                "peak_tariff_upper_bound_microcny": amount,
            },
        ) from failure
    amount = settle("model_response", {"response_id": value["id"], "finish_reason": finish})
    return dict(
        budget_invocation_id=invocation_id,
        budget_coordinates=coordinates,
        public_request=body,
        request_sha256=digest(body),
        public_request_body_sha256=hashlib.sha256(wire).hexdigest(),
        api_response_raw=raw_text,
        raw_api_response_sha256=hashlib.sha256(raw).hexdigest(),
        api_response=value,
        usage=copy.deepcopy(value["usage"]),
        peak_tariff_upper_bound_microcny=amount,
        budget_reserved_microcny=reserved,
        price_sheet_id=ledger.price_sheet.id,
        content=content,
        finish_reason=finish,
        actual_model_calls=1,
        retries=0,
        content_repair_performed=False,
        **(_strict_review_payload(message, finish) if strict else {}),
        **local_binding,
    )
