"""One durably reserved HTTP attempt per public callback; no repair or fallback.

The HTTP response envelope is retained as received. Only the original nonempty
``choices[0].message.content`` string can be returned to PublicQARuntime. This
module never constructs a public Submission, admission Receipt, or model answer.
"""

from __future__ import annotations

import asyncio
import copy
import importlib.metadata
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore

from .models import read_json, record, require, sha

SYSTEM_PROMPT = (
    "Follow the public QA protocol in the user message. It contains the complete current "
    "task, State, legal action candidates and strict response schemas. Choose among the "
    "supplied legal alternatives and return exactly one JSON object matching an allowed "
    "Action, Update, or Final schema for this State. Use only this request. Do not output "
    "Markdown, private reasoning, or native tool calls. Do not invent evidence or change "
    "the public contract."
)
SOURCE_RELATIVE_PATH = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "finance_qa_vnext_model_execution/transport.py"
)


class TransportConfig(BaseModel):
    """The preregistered condition, including byte-based admission, not measured tokens."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    endpoint: Literal["https://api.deepseek.com/chat/completions"] = (
        "https://api.deepseek.com/chat/completions"
    )
    model: Literal["deepseek-v4-pro"] = "deepseek-v4-pro"
    temperature: float = Field(default=0.7, ge=0.7, le=0.7)
    top_p: float = Field(default=1.0, ge=1.0, le=1.0)
    max_tokens: Literal[8192] = 8192
    timeout_seconds: Literal[180] = 180
    connect_timeout_seconds: Literal[30] = 30
    maximum_serialized_request_bytes: Literal[98304] = 98304
    maximum_input_tokens: Literal[99328] = 99328
    input_overhead_allowance: Literal[1024] = 1024
    maximum_http_response_bytes: Literal[2097152] = 2097152
    maximum_public_response_bytes: Literal[1048576] = 1048576
    attempts_per_session: int = Field(default=32, ge=1, le=32)
    maximum_pilot_attempts: int = Field(default=384, ge=1, le=384)
    system_prompt: str = SYSTEM_PROMPT

    def as_record(self) -> dict[str, Any]:
        return record(
            "transport_config",
            **self.model_dump(mode="json"),
            allowed_response_models=["deepseek-v4-pro", "deepseek-v4-pro-0813"],
            thinking={"type": "disabled"},
            response_format={"type": "json_object"},
            stream=False,
            native_tool_calls=False,
            automatic_retries=0,
            model_fallbacks=0,
            redirects=0,
            trust_env=False,
            maximum_request_reserved_tokens=107520,
            maximum_session_reserved_tokens=self.attempts_per_session * 107520,
            maximum_pilot_reserved_tokens=self.maximum_pilot_attempts * 107520,
            messages_policy="neutral system plus canonical current public request; stateless",
            input_token_admission_rule=(
                "actual serialized HTTP body UTF-8 bytes plus 1024 allowance"
            ),
            exact_offline_model_tokenization_claimed=False,
            actual_tokens_authority="observed Provider usage; missing values remain unknown",
            immutable_model_snapshot_claimed=False,
            timeout_semantics="asyncio hard total deadline; separate HTTP connect deadline",
        )


@dataclass(frozen=True)
class HTTPResponse:
    status_code: int
    body: bytes
    headers: tuple[tuple[str, str], ...] = ()
    complete: bool = True
    elapsed_ns: int | None = None


class HTTPSendError(Exception):
    """An observed transport failure, optionally with a bounded partial HTTP response."""

    def __init__(self, code: str, response: HTTPResponse | None = None):
        self.code, self.response = code, response
        super().__init__(code)


class OnlineTransportError(Exception):
    """Root records this typed termination; no empty Runtime Submission is fabricated."""

    def __init__(self, code: str, evidence_id: str):
        self.code, self.evidence_id = code, evidence_id
        super().__init__(code)


class Sender(Protocol):
    def send(self, request: dict[str, Any], *, api_key: str | None) -> HTTPResponse: ...


class HttpxSender:
    """Fresh, single-attempt HTTPS client; no environment proxies or implicit retries."""

    def __init__(self, config: TransportConfig):
        self.config = config

    def send(self, request: dict[str, Any], *, api_key: str | None) -> HTTPResponse:
        if (
            not isinstance(api_key, str)
            or not 0 < len(api_key) <= 2048
            or any(character in api_key for character in "\r\n\x00")
        ):
            raise HTTPSendError("transport.credential_unavailable")
        require(request["endpoint"] == self.config.endpoint, "transport.endpoint")
        body = request["body_json"].encode("utf-8")
        require(sha(body) == request["body_sha256"], "transport.exact_request_body")
        return asyncio.run(self._send(request["endpoint"], body, api_key))

    async def _send(self, endpoint: str, body: bytes, api_key: str) -> HTTPResponse:
        started = time.monotonic_ns()
        status: int | None = None
        headers: tuple[tuple[str, str], ...] = ()
        received = bytearray()

        def partial() -> HTTPResponse | None:
            return (
                HTTPResponse(status, bytes(received), headers, False, time.monotonic_ns() - started)
                if status is not None
                else None
            )

        try:
            async with asyncio.timeout(self.config.timeout_seconds):
                async with httpx.AsyncClient(
                    transport=httpx.AsyncHTTPTransport(retries=0, trust_env=False),
                    trust_env=False,
                    follow_redirects=False,
                    timeout=httpx.Timeout(
                        self.config.timeout_seconds, connect=self.config.connect_timeout_seconds
                    ),
                ) as client:
                    async with client.stream(
                        "POST",
                        endpoint,
                        content=body,
                        headers={
                            "Authorization": "Bearer " + api_key,
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "Accept-Encoding": "identity",
                        },
                    ) as response:
                        status = response.status_code
                        headers = tuple(
                            (key.decode("latin-1"), value.decode("latin-1"))
                            for key, value in response.headers.raw
                        )
                        async for chunk in response.aiter_raw():
                            remaining = self.config.maximum_http_response_bytes - len(received)
                            received.extend(chunk[:remaining])
                            if len(chunk) > remaining:
                                raise HTTPSendError("transport.response_byte_cap", partial())
            assert status is not None
            return HTTPResponse(
                status, bytes(received), headers, True, time.monotonic_ns() - started
            )
        except (TimeoutError, httpx.TimeoutException):
            raise HTTPSendError("transport.timeout", partial()) from None
        except httpx.HTTPError:
            raise HTTPSendError("transport.http_io", partial()) from None


def render_http_request(
    public_request: dict[str, Any],
    config: TransportConfig,
    *,
    session_id: str,
    attempt_index: int,
) -> dict[str, Any]:
    """Render the full actual request even when it must be denied for resource limits."""
    state, context = public_request["state"], public_request["context"]
    require(
        state["context_id"] == context["id"]
        and state["protocol_id"] == public_request["protocol_id"],
        "transport.public_parent_binding",
    )
    frozen = config.as_record()
    messages = [
        {"role": "system", "content": config.system_prompt},
        {"role": "user", "content": canonical_json_bytes(public_request).decode("utf-8")},
    ]
    body = {
        "model": frozen["model"],
        "messages": messages,
        **{
            key: frozen[key]
            for key in (
                "thinking",
                "temperature",
                "top_p",
                "max_tokens",
                "response_format",
                "stream",
            )
        },
    }
    raw = canonical_json_bytes(body)
    return record(
        "http_request",
        session_id=session_id,
        attempt_index=attempt_index,
        turn_index=state["submission_count"],
        public_request_id=public_request["id"],
        public_runtime_state_id=state["id"],
        context_id=context["id"],
        task_id=context["task_id"],
        protocol_id=public_request["protocol_id"],
        model_configuration_id=frozen["id"],
        endpoint=config.endpoint,
        body=body,
        messages=messages,
        body_json=raw.decode("utf-8"),
        body_sha256=sha(raw),
        body_byte_count=len(raw),
        input_admission_upper_bound=len(raw) + config.input_overhead_allowance,
        input_allowance=config.maximum_input_tokens,
        reserved_tokens=frozen["maximum_request_reserved_tokens"],
    )


def _usage(envelope: dict[str, Any]) -> tuple[dict[str, int | None], list[str]]:
    raw = envelope.get("usage")
    raw = raw if isinstance(raw, dict) else {}
    details = raw.get("completion_tokens_details")
    details = details if isinstance(details, dict) else {}
    keys = (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "reasoning_tokens",
    )
    values = {**raw, "reasoning_tokens": details.get("reasoning_tokens")}
    usage: dict[str, int | None] = {}
    for key in keys:
        supplied = values.get(key)
        usage[key] = supplied if type(supplied) is int and supplied >= 0 else None
    flags = []
    if any(key in values and values[key] is not None and usage[key] is None for key in keys):
        flags.append("provider.invalid_usage")
    prompt, completion, total = (
        usage["prompt_tokens"],
        usage["completion_tokens"],
        usage["total_tokens"],
    )
    if prompt is not None and completion is not None and total is not None:
        if prompt + completion != total:
            flags.append("provider.usage_sum_mismatch")
    for key, bound in (
        ("prompt_tokens", 99328),
        ("completion_tokens", 8192),
        ("total_tokens", 107520),
    ):
        actual = usage[key]
        if actual is not None and actual > bound:
            flags.append("provider.usage_exceeds_allowance." + key)
    if usage["reasoning_tokens"] not in (None, 0):
        flags.append("provider.unexpected_reasoning_tokens")
    return usage, flags


def _extract(response: HTTPResponse, config: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "provider_failure",
        "code": None,
        "observed_model": None,
        "provider_response_id": None,
        "system_fingerprint": None,
        "finish_reason": None,
        "usage": _usage({})[0],
        "condition_flags": [],
        "public_content": None,
        "return_content": False,
    }
    if not response.complete:
        result["code"] = "provider.incomplete_http_response"
        return result
    try:
        envelope = read_json(response.body)
        require(isinstance(envelope, dict), "provider.envelope_object")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        result["code"] = "provider.invalid_envelope"
        return result
    result.update(
        observed_model=envelope.get("model") if isinstance(envelope.get("model"), str) else None,
        provider_response_id=envelope.get("id") if isinstance(envelope.get("id"), str) else None,
        system_fingerprint=envelope.get("system_fingerprint")
        if isinstance(envelope.get("system_fingerprint"), str)
        else None,
    )
    result["usage"], result["condition_flags"] = _usage(envelope)
    choices = envelope.get("choices")
    choice = choices[0] if isinstance(choices, list) and len(choices) == 1 else None
    message = choice.get("message") if isinstance(choice, dict) else None
    if isinstance(choice, dict):
        result["finish_reason"] = choice.get("finish_reason")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            try:
                result["public_content"] = content.encode("utf-8")
            except UnicodeError:
                result["code"] = "provider.public_content_encoding"
        if message.get("reasoning_content"):
            result["condition_flags"].append("provider.unexpected_reasoning_content")
        if message.get("tool_calls") or message.get("function_call"):
            result["condition_flags"].append("provider.unexpected_native_tool_calls")
    if result["finish_reason"] == "tool_calls":
        result["condition_flags"].append("provider.unexpected_native_tool_calls")
    if not 200 <= response.status_code < 300:
        result["code"] = "provider.http_error"
    elif result["observed_model"] not in config["allowed_response_models"]:
        result["code"] = "provider.model_identity_mismatch"
    elif envelope.get("object") != "chat.completion" or not result["provider_response_id"]:
        result["code"] = "provider.response_identity"
    elif (
        not isinstance(choice, dict)
        or type(choice.get("index")) is not int
        or choice["index"] != 0
        or not isinstance(message, dict)
        or message.get("role") != "assistant"
    ):
        result["code"] = "provider.response_shape"
    elif result["code"] is None and not result["public_content"]:
        result["code"] = "provider.no_public_content"
    if (
        result["public_content"] is not None
        and len(result["public_content"]) > config["maximum_public_response_bytes"]
    ):
        result["condition_flags"].append("provider.public_content_exceeds_runtime_cap")
    if result["code"] is None:
        result.update(status="public_content", return_content=True)
    result["condition_flags"] = sorted(set(result["condition_flags"]))
    return result


class OnlineModelCallback:
    """Stable callback binding plus independently inspectable per-attempt evidence."""

    def __init__(
        self,
        config: TransportConfig,
        *,
        session_id: str,
        evidence_directory: Path,
        api_key: str | None = None,
        sender: Sender | None = None,
    ):
        require(bool(session_id), "transport.session_id")
        self.config = config
        self.configuration = config.as_record()
        self.session_id = session_id
        self._api_key = api_key
        self.sender = sender if sender is not None else HttpxSender(config)
        self._send = self.sender.send
        self.store = DurableStore(evidence_directory)
        source = Path(__file__).read_bytes()
        live = type(self.sender) is HttpxSender
        if live:
            assert isinstance(self.sender, HttpxSender)
            require(self.sender.config.as_record() == self.configuration, "transport.sender_config")
        self.binding = record(
            "callback_binding",
            session_id=session_id,
            model_configuration_id=self.configuration["id"],
            origin="model" if live else "adapter_mock",
            transport_kind="live_http" if live else "adapter_mock",
            implementation={
                "module": __name__,
                "class": type(self).__name__,
                "method": "generate",
                "source_relative_path": SOURCE_RELATIVE_PATH,
                "source_sha256": sha(source),
                "source_byte_count": len(source),
            },
            sender_implementation={
                "module": type(self.sender).__module__,
                "class": type(self.sender).__qualname__,
                "method": "send",
                "httpx_version": importlib.metadata.version("httpx") if live else None,
            },
            model_origin_requires_attempt_response_evidence=True,
            host_semantic_field_fill=False,
            automatic_retries=0,
            model_fallbacks=0,
        )
        self._binding_bytes = canonical_json_bytes(self.binding)
        self._attempts: list[dict[str, Any]] = []
        self._stops: list[dict[str, Any]] = []
        self._last_outcome: dict[str, Any] | None = None
        self._closed = False
        self._finalized: dict[str, Any] | None = None
        self._lock = threading.Lock()
        self.store.json("config.json", self.configuration)
        self.store.json("binding.json", self.binding)

    @property
    def attempt_count(self) -> int:
        return len(self._attempts)

    @property
    def last_outcome(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._last_outcome)

    def generate(self, request: dict[str, Any]) -> bytes:
        with self._lock:
            if self._closed:
                assert self._last_outcome is not None
                raise OnlineTransportError("transport.session_closed", self._last_outcome["id"])
            require(
                canonical_json_bytes(self.binding) == self._binding_bytes,
                "transport.binding_changed",
            )
            require(
                self.config.as_record() == self.configuration, "transport.configuration_changed"
            )
            if type(self.sender) is HttpxSender:
                require(
                    self.sender.config.as_record() == self.configuration,
                    "transport.sender_config_changed",
                )
            http_request = render_http_request(
                request, self.config, session_id=self.session_id, attempt_index=self.attempt_count
            )
            denial = (
                "resource.attempt_budget"
                if self.attempt_count >= self.config.attempts_per_session
                else "resource.input_budget"
                if (
                    http_request["body_byte_count"] > self.config.maximum_serialized_request_bytes
                    or http_request["input_admission_upper_bound"]
                    > self.config.maximum_input_tokens
                )
                else None
            )
            prefix = (
                f"stops/{len(self._stops):03d}" if denial else f"attempts/{self.attempt_count:03d}"
            )
            paths: dict[str, str | None] = {
                "public_request": prefix + "_public_request.json",
                "http_request": prefix + "_http_request.json",
                "http_request_body": prefix + "_http_request.body",
                "reservation": None,
                "http_response": None,
                "http_response_body": None,
                "public_content": None,
                "outcome": prefix + "_outcome.json",
            }
            self.store.json(str(paths["public_request"]), request)
            self.store.json(str(paths["http_request"]), http_request)
            self.store.write(
                str(paths["http_request_body"]), http_request["body_json"].encode("utf-8")
            )
            if denial:
                outcome = self._outcome(
                    http_request,
                    None,
                    None,
                    {
                        **_extract(HTTPResponse(0, b"", complete=False), self.configuration),
                        "status": "resource_termination",
                        "code": denial,
                    },
                )
                self._persist_outcome(outcome, paths, self._stops)
                self._closed = True
                raise OnlineTransportError(denial, outcome["id"])

            index = self.attempt_count
            reservation = record(
                "attempt_reservation",
                **self._parents(http_request),
                http_request_id=http_request["id"],
                reserved_tokens=self.configuration["maximum_request_reserved_tokens"],
                session_reserved_tokens_after=(index + 1)
                * self.configuration["maximum_request_reserved_tokens"],
                attempt_consumed=True,
                reserved_before_send=True,
                reserved_at_utc=datetime.now(timezone.utc).isoformat(),
            )
            paths["reservation"] = prefix + "_reservation.json"
            self.store.json(str(paths["reservation"]), reservation)
            require(
                (self.store.root / str(paths["reservation"])).read_bytes()
                == canonical_json_bytes(reservation)
                and (self.store.root / str(paths["http_request_body"])).read_bytes()
                == http_request["body_json"].encode("utf-8"),
                "transport.reservation_readback",
            )
            row = {"attempt_index": index, "turn_index": http_request["turn_index"], "paths": paths}
            self._attempts.append(row)
            self.store.events.append(
                {
                    "kind": "reservation_readback",
                    "attempt_index": index,
                    "reservation_path": paths["reservation"],
                    "http_request_body_path": paths["http_request_body"],
                }
            )
            self.store.events.append(
                {
                    "kind": "send",
                    "attempt_index": index,
                    "http_request_id": http_request["id"],
                    "reservation_id": reservation["id"],
                }
            )
            transport_code = None
            response: HTTPResponse | None
            try:
                response = self._send(copy.deepcopy(http_request), api_key=self._api_key)
                require(isinstance(response, HTTPResponse), "transport.sender_response_type")
                require(
                    type(response.status_code) is int and 100 <= response.status_code <= 599,
                    "transport.status_code",
                )
                require(type(response.body) is bytes, "transport.response_bytes")
            except HTTPSendError as error:
                response = error.response
                transport_code = (
                    error.code
                    if error.code
                    in {
                        "transport.credential_unavailable",
                        "transport.timeout",
                        "transport.http_io",
                        "transport.response_byte_cap",
                    }
                    else "transport.unclassified_failure"
                )
            except (TimeoutError, httpx.TimeoutException):
                response, transport_code = None, "transport.timeout"
            except Exception:
                response, transport_code = None, "transport.unclassified_failure"
            response_record = None
            if response is not None:
                self.store.events.append(
                    {
                        "kind": "receive",
                        "attempt_index": index,
                        "status_code": response.status_code,
                        "body_byte_count": len(response.body),
                    }
                )
                paths["http_response_body"] = prefix + "_http_response.body"
                paths["http_response"] = prefix + "_http_response.json"
                self.store.write(str(paths["http_response_body"]), response.body)
                response_record = record(
                    "http_response",
                    **self._parents(http_request),
                    http_request_id=http_request["id"],
                    reservation_id=reservation["id"],
                    status_code=response.status_code,
                    headers=response.headers,
                    body_sha256=sha(response.body),
                    body_byte_count=len(response.body),
                    complete=response.complete,
                    elapsed_ns=response.elapsed_ns,
                )
                self.store.json(str(paths["http_response"]), response_record)
                extracted = _extract(response, self.configuration)
            else:
                extracted = _extract(HTTPResponse(0, b"", complete=False), self.configuration)
            if transport_code:
                self.store.events.append(
                    {"kind": "send_failed", "attempt_index": index, "code": transport_code}
                )
                extracted.update(
                    status="transport_failure", code=transport_code, return_content=False
                )
            outcome = self._outcome(http_request, reservation, response_record, extracted)
            content = extracted["public_content"]
            if content is not None:
                paths["public_content"] = prefix + "_public_content.txt"
                self.store.write(str(paths["public_content"]), content)
            self._persist_outcome(outcome, paths)
            row["outcome_id"] = outcome["id"]
            if not extracted["return_content"]:
                self._closed = True
                raise OnlineTransportError(outcome["code"], outcome["id"])
            assert isinstance(content, bytes) and content
            return content

    def _parents(self, request: dict[str, Any]) -> dict[str, Any]:
        return {
            **{
                key: request[key]
                for key in (
                    "session_id",
                    "attempt_index",
                    "turn_index",
                    "public_request_id",
                    "public_runtime_state_id",
                    "context_id",
                    "task_id",
                    "protocol_id",
                    "model_configuration_id",
                )
            },
            "callback_binding_id": self.binding["id"],
        }

    def _outcome(self, request, reservation, response, extracted) -> dict[str, Any]:
        content = extracted["public_content"]
        return record(
            "provider_outcome",
            **self._parents(request),
            http_request_id=request["id"],
            reservation_id=reservation["id"] if reservation else None,
            http_response_id=response["id"] if response else None,
            transport_kind=self.binding["transport_kind"],
            **{
                key: extracted[key]
                for key in (
                    "status",
                    "code",
                    "observed_model",
                    "provider_response_id",
                    "system_fingerprint",
                    "finish_reason",
                    "usage",
                    "condition_flags",
                )
            },
            public_content_present=content is not None,
            public_content_sha256=sha(content) if content is not None else None,
            public_content_byte_count=len(content) if content is not None else None,
            public_content_returned_to_runtime=extracted["return_content"],
            provider_attempt_consumed=reservation is not None,
            automatic_retries=0,
            host_repairs=[],
        )

    def _persist_outcome(self, outcome, paths, rows=None) -> None:
        self.store.json(str(paths["outcome"]), outcome)
        self.store.events.append(
            {
                "kind": "outcome_persisted",
                "attempt_index": outcome["attempt_index"],
                "outcome_path": paths["outcome"],
                "outcome_id": outcome["id"],
            }
        )
        self._last_outcome = outcome
        if rows is not None:
            rows.append(
                {"outcome_id": outcome["id"], "turn_index": outcome["turn_index"], "paths": paths}
            )

    def finalize(self) -> dict[str, Any]:
        """Called once after Runtime termination; manifest covers all evidence, not itself."""
        with self._lock:
            if self._finalized is not None:
                return copy.deepcopy(self._finalized)
            ledger = record(
                "transport_ledger",
                session_id=self.session_id,
                model_configuration_id=self.configuration["id"],
                callback_binding_id=self.binding["id"],
                transport_kind=self.binding["transport_kind"],
                attempts=self._attempts,
                stops=self._stops,
                provider_attempt_count=self.attempt_count,
                reserved_tokens=self.attempt_count
                * self.configuration["maximum_request_reserved_tokens"],
                write_events=self.store.events,
            )
            self.store.json("ledger.json", ledger)
            members = [
                {
                    "path": str(path.relative_to(self.store.root)),
                    "sha256": sha(path.read_bytes()),
                    "bytes": path.stat().st_size,
                }
                for path in sorted(self.store.root.rglob("*"))
                if path.is_file()
            ]
            self.store.json(
                "manifest.json",
                record(
                    "transport_manifest",
                    session_id=self.session_id,
                    ledger_id=ledger["id"],
                    members=members,
                    self_excluding=True,
                    write_events=self.store.events,
                ),
            )
            self._closed, self._finalized = True, ledger
            return copy.deepcopy(ledger)
