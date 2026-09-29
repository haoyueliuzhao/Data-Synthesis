"""Budgeted real DeepSeek Flash Probe, with explicit disabled thinking and no retry.

The exact public request object is serialized once and those bytes are sent and
stored. Authorization is held only in memory and never included in evidence.
"""

from __future__ import annotations

import copy
import hashlib

from .contracts import ModelIdentity, ModelTurn, ProviderCallError, digest, invocation_identity
from .probe_budget import V6_PURPOSE, InvalidUsage, ProbeBudget
from .providers import _api_messages, _json, parse_tool_calls, validate_structured_context
from .qwen_protocol import strict_json_decoder

ENDPOINT = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-flash"
INFRA_FINISH_REASONS = {"insufficient_system_resource", "aborted"}
V6_HARNESS_PROFILE_PAIR = ("bigfinance-derived-vtdo-v6", "finqa-public-reasoning-v1")
V7_HARNESS_PROFILE_PAIR = ("bigfinance-derived-vtdo-v7", "finqa-public-reasoning-v2")
PROBE_HARNESS_PROFILE_PAIRS = {
    ("bigfinance-derived-vtdo-v3", "finqa_program_v2"),
    ("bigfinance-derived-vtdo-v4", "finqa_program_v3_structured"),
    V6_HARNESS_PROFILE_PAIR,
    V7_HARNESS_PROFILE_PAIR,
}


class BudgetedDeepSeekFlashProvider:
    """One fixed inventory episode; the caller supplies the matching harness scope."""

    def __init__(
        self,
        *,
        ledger: ProbeBudget,
        api_key: str,
        episode_id: str,
        attempt_index: int = 1,
        client=None,
        timeout=120.0,
        model=MODEL,
    ):
        if model != MODEL or ledger.price_sheet.model != MODEL:
            raise ValueError("Probe requests must use exactly deepseek-flash; no fallback")
        if not isinstance(api_key, str) or not api_key:
            raise ValueError("the caller must supply an in-memory API key")
        self.ledger, self._key, self._client, self.timeout = ledger, api_key, client, timeout
        self.scope = {
            "run_id": ledger.run_id,
            "episode_id": episode_id,
            "attempt_index": attempt_index,
        }
        invocation_identity(self.scope, turn_index=0)
        self.identity = ModelIdentity(backend="deepseek_api", model_id=MODEL)
        self.actual_model_calls, self._turn_index = 0, 0

    def _unknown(
        self,
        invocation_id,
        *,
        body,
        reason,
        response_body=None,
        http_status=None,
        response_classification="unknown",
        evidence=None,
        actual_model_calls=1,
    ):
        evidence = {
            "request_sha256": digest(body),
            "public_request": body,
            "budget_invocation_id": invocation_id,
            "billing_usage_known": False,
            "reservation_retained": True,
            "automatic_retry": False,
            **(evidence or {}),
        }
        self.ledger.unknown(
            invocation_id,
            reason=reason,
            http_status=http_status,
            response_classification=response_classification,
            response_body=response_body,
            evidence=evidence,
        )
        return ProviderCallError(
            reason, settlement="unknown", actual_model_calls=actual_model_calls, evidence=evidence
        )

    async def chat(self, messages, tools, config):
        pair = (config.harness_id, config.submission_profile)
        # This is a prospective V7 generation allowance, not an enlargement of
        # V6 or either earlier frozen generation protocol. The monetary ledger
        # remains the same joint run, with each request's own cap/usage receipt.
        output_limits = (
            (2048, 16384)
            if pair == V7_HARNESS_PROFILE_PAIR
            else (2048,)
            if pair == V6_HARNESS_PROFILE_PAIR
            else (2048, 4096)
        )
        if not (
            self.identity.model_id == MODEL
            and config.api_model == MODEL
            and config.tier == "EVAL_NATIVE"
            and config.role == "sft"
            and pair in PROBE_HARNESS_PROFILE_PAIRS
            and (
                (pair in {V6_HARNESS_PROFILE_PAIR, V7_HARNESS_PROFILE_PAIR})
                == (self.ledger.purpose == V6_PURPOSE)
            )
            and config.local_tool_protocol == "qwen2.5-native-tool-call-v1"
            and (config.temperature, config.top_p, config.top_k) == (1.0, 1.0, 0)
            and config.max_new_tokens in self.ledger.allowed_output_limits
            and config.max_new_tokens in output_limits
            and config.context_limit == self.ledger.price_sheet.context_input_token_ceiling
            and config.max_steps == 32
        ):
            raise ValueError("Probe differs from the frozen SFT/H1-R Flash T=1 output contract")
        validate_structured_context(messages, tools, config)
        coordinates = invocation_identity(self.scope, turn_index=self._turn_index)
        invocation_id = coordinates["invocation_id"]
        body = {
            "model": MODEL,
            "messages": _api_messages(messages),
            "temperature": 1.0,
            "top_p": 1.0,
            "max_tokens": config.max_new_tokens,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        if tools:
            body["tools"] = copy.deepcopy(tools)
        request_body = _json(body).encode("utf-8")
        reserved = self.ledger.reserve(
            invocation_id, coordinates=coordinates, request=body, request_body=request_body
        )
        # Commit DISPATCHED before making the network attempt. A crash in between
        # remains conservatively held until an explicit disposition, never retried.
        self.ledger.mark_dispatched(invocation_id)
        self._turn_index += 1
        headers = {"Authorization": "Bearer " + self._key, "Content-Type": "application/json"}
        before_http = self.actual_model_calls
        try:
            if self._client is None:
                import httpx

                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    trust_env=False,
                    transport=httpx.AsyncHTTPTransport(retries=0, trust_env=False),
                ) as client:
                    self.actual_model_calls += 1
                    response = await client.post(ENDPOINT, content=request_body, headers=headers)
            else:
                self.actual_model_calls += 1
                response = await self._client.post(
                    ENDPOINT, content=request_body, headers=headers, timeout=self.timeout
                )
        except BaseException as failure:
            unknown = self._unknown(
                invocation_id,
                body=body,
                reason="transport response or billing usage unknown",
                actual_model_calls=self.actual_model_calls - before_http,
                evidence={
                    "exception_type": type(failure).__name__,
                    "service_response_received": False,
                },
            )
            if not isinstance(failure, Exception):
                raise  # Cancellation/interrupt preserves the durable unknown hold.
            raise unknown from failure
        status = response.status_code
        response_body = response.content
        if not isinstance(response_body, bytes):
            response_body = bytes(response_body)
        response_class = "service_failure" if not 200 <= status < 300 else "model_response"
        if self._key.encode() in response_body:
            # Never persist a credential echoed by a broken service response.
            original_sha = hashlib.sha256(response_body).hexdigest()
            redacted = response_body.replace(self._key.encode(), b"<REDACTED_API_KEY>")
            raise self._unknown(
                invocation_id,
                body=body,
                reason="service response echoed credential material",
                http_status=status,
                response_body=redacted,
                response_classification=response_class,
                evidence={
                    "raw_response_original_sha256": original_sha,
                    "credential_redacted": True,
                },
            )
        try:
            raw_response = response_body.decode("utf-8")
            value = strict_json_decoder().decode(raw_response)
            if not isinstance(value, dict):
                raise ValueError("API response is not a JSON object")
            if 200 <= status < 300 and value.get("model") != MODEL:
                raise ValueError("API response model differs from the requested frozen model")
            self.ledger.price_sheet.usage(value.get("usage"), output_limit=config.max_new_tokens)
        except (ValueError, TypeError, UnicodeError, InvalidUsage, RecursionError) as failure:
            raise self._unknown(
                invocation_id,
                body=body,
                reason="returned response has unknown or inconsistent tariff usage",
                response_body=response_body,
                http_status=status,
                response_classification=response_class,
                evidence={
                    "exception_type": type(failure).__name__,
                    "response_classification": response_class,
                    "http_status": status,
                    "service_response_received": True,
                },
            ) from failure
        usage = value["usage"]
        if not 200 <= status < 300:
            amount = self.ledger.settle(
                invocation_id,
                usage=usage,
                http_status=status,
                response_classification="service_failure",
                response_body=response_body,
                evidence={"http_status": status, "automatic_retry": False},
            )
            raise ProviderCallError(
                f"API returned HTTP {status}; no retry",
                settlement="service_failure",
                actual_model_calls=1,
                evidence={
                    "public_request": body,
                    "api_response": value,
                    "request_sha256": digest(body),
                    "budget_invocation_id": invocation_id,
                    "billing_usage_known": True,
                    "peak_tariff_upper_bound_microcny": amount,
                },
            )
        try:
            if not isinstance(value.get("id"), str) or not value["id"]:
                raise ValueError("API response lacks its actual response ID")
            choices = value.get("choices")
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("API response must have exactly one completed choice")
            choice = choices[0]
            finish = choice.get("finish_reason")
            if finish in INFRA_FINISH_REASONS:
                raise ValueError("API explicitly interrupted the response: " + finish)
            if finish not in {"stop", "length", "tool_calls", "content_filter"}:
                raise ValueError("API response lacks a registered completed finish reason")
            message = choice["message"]
            if not isinstance(message, dict) or not ({"content", "tool_calls"} & set(message)):
                raise ValueError("API response has no actual assistant content or tool fields")
            if (
                message.get("reasoning_content") not in (None, "")
                or (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) != 0
            ):
                raise ValueError("API returned reasoning despite explicitly disabled thinking")
            raw = message.get("content") or ""
            if not isinstance(raw, str):
                raise ValueError("API assistant content is not text")
            raw_calls = message.get("tool_calls") or []
            try:
                calls = parse_tool_calls(_json({"tool_calls": raw_calls}), call_prefix=value["id"])
            except (ValueError, TypeError, IndexError, RecursionError):
                calls = ()
            parse_error = (
                "malformed_native_tool_calls_no_repair" if raw_calls and not calls else None
            )
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as failure:
            amount = self.ledger.settle(
                invocation_id,
                usage=usage,
                http_status=status,
                response_classification="invalid_or_interrupted_response",
                response_body=response_body,
                evidence={"exception_type": type(failure).__name__, "reason": str(failure)},
            )
            raise ProviderCallError(
                "returned API response violates the frozen execution contract",
                settlement="unknown",
                actual_model_calls=1,
                evidence={
                    "public_request": body,
                    "api_response": value,
                    "request_sha256": digest(body),
                    "budget_invocation_id": invocation_id,
                    "billing_usage_known": True,
                    "execution_response_valid": False,
                    "peak_tariff_upper_bound_microcny": amount,
                    "reason": str(failure),
                },
            ) from failure
        amount = self.ledger.settle(
            invocation_id,
            usage=usage,
            http_status=status,
            response_classification="model_response",
            response_body=response_body,
            evidence={"response_id": value["id"], "finish_reason": finish},
        )
        return ModelTurn(
            raw_text=raw,
            tool_calls=calls,
            finish_reason=finish,
            usage={key: item for key, item in usage.items() if type(item) is int},
            provider_metadata={
                "public_request": body,
                "request_sha256": digest(body),
                "public_request_body_sha256": hashlib.sha256(request_body).hexdigest(),
                "api_response": value,
                "api_response_raw": raw_response,
                "raw_api_response_sha256": hashlib.sha256(response_body).hexdigest(),
                "tool_protocol": "deepseek-native-tool-calls-v1",
                "parse_error": parse_error,
                "model_tool_format_failure": parse_error is not None,
                "local_token_receipt_available": False,
                "API_and_local_token_budget_equivalence_claimed": False,
                "context_limit_locally_verified": False,
                "requested_context_limit_not_an_API_token_fact": config.context_limit,
                "official_input_reservation_token_ceiling": (
                    self.ledger.price_sheet.context_input_token_ceiling
                ),
                "thinking_contract": {"type": "disabled"},
                "retries": 0,
                "budget_invocation_id": invocation_id,
                "budget_coordinates": coordinates,
                "price_sheet_id": self.ledger.price_sheet.id,
                "budget_reserved_microcny": reserved,
                "peak_tariff_upper_bound_microcny": amount,
                "cost_is_provider_invoice": False,
            },
        )
