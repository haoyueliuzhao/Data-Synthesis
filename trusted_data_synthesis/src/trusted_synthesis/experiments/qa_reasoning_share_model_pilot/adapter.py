"""One-request public-JSON adapter; no repair, retry, private-reasoning artifact or fallback.

Only ``message.content`` can become a public submission. The HTTP envelope exists
transiently in memory and is never persisted or hashed. A response record contains
selected provider metadata and a hash of *public content only*, never the envelope.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.engine import verify_callback
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.models import (
    ProtocolError,
    parse_submission,
    require,
)

from .models import model_config, record, sha, source_binding

SYSTEM_MESSAGE = (
    "Follow the public protocol in the user message. The user message is the complete current "
    "public request, including its State, instructions and exact allowed response_schema. "
    "Return exactly one JSON object matching one allowed submission schema. Make all semantic "
    "choices yourself from the public information. Do not output Markdown or private reasoning."
)
USAGE_KEYS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "reasoning_tokens",
)


def render_http_request(
    public_request: dict[str, Any],
    config: dict[str, Any],
    *,
    session_id: str,
    turn_index: int,
    call_id: str,
) -> dict[str, Any]:
    """Persistable exact body, with unchanged canonical public request as the user message."""
    require(config == model_config(), "adapter.frozen_configuration")
    body = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": canonical_json_bytes(public_request).decode("utf-8")},
        ],
        **{
            key: copy.deepcopy(config[key])
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
    require(len(raw) <= config["maximum_serialized_request_bytes"], "adapter.request_byte_cap")
    require(len(raw) + 1024 <= config["maximum_input_tokens"], "adapter.input_token_cap")
    return record(
        "provider_request",
        session_id=session_id,
        turn_index=turn_index,
        call_id=call_id,
        model_configuration_id=config["id"],
        public_request_id=public_request["id"],
        state_id=public_request["state_id"],
        phase=public_request["state"]["phase"],
        endpoint=config["endpoint"],
        requested_model=config["model"],
        body_json=raw.decode("utf-8"),
        body_sha256=sha(raw),
        body_byte_count=len(raw),
        input_token_upper_bound=len(raw) + 1024,
        reserved_tokens=config["maximum_request_reserved_tokens"],
    )


class TransportFailure(Exception):
    """Typed code only. Never preserve an underlying exception string or body."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class CurlTransport:
    """A single POST with total/connect deadlines and no redirects, retries or curlrc.

    Credentials travel through an inherited anonymous pipe, not argv, environment,
    an on-disk header file, request artifacts, or exception text.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        require(config == model_config(), "adapter.frozen_configuration")
        self.config = copy.deepcopy(config)

    def send(self, request: dict[str, Any], *, api_key: str | None) -> dict[str, Any]:
        config = self.config
        if (
            not isinstance(api_key, str)
            or not 0 < len(api_key) <= 2048
            or any(char in api_key for char in "\r\n\x00")
        ):
            raise TransportFailure("transport.invalid_credential")
        raw = request["body_json"].encode("utf-8")
        require(sha(raw) == request["body_sha256"], "transport.request_bytes")
        require(request["endpoint"] == config["endpoint"], "transport.endpoint")
        read_fd, write_fd = os.pipe()
        try:
            try:
                os.write(
                    write_fd,
                    (
                        "Authorization: Bearer " + api_key + "\nContent-Type: application/json\n"
                    ).encode("utf-8"),
                )
            finally:
                os.close(write_fd)
            args = [
                "curl",
                "--disable",
                "--silent",
                "--show-error",
                "--request",
                "POST",
                "--proto",
                "=https",
                "--retry",
                "0",
                "--max-redirs",
                "0",
                "--connect-timeout",
                str(config["connect_timeout_seconds"]),
                "--max-time",
                str(config["timeout_seconds"]),
                "--max-filesize",
                str(config["maximum_http_response_bytes"]),
                "--header",
                f"@/dev/fd/{read_fd}",
                "--data-binary",
                "@-",
                "--write-out",
                "\n%{http_code}",
                request["endpoint"],
            ]
            try:
                process = subprocess.Popen(
                    args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    pass_fds=(read_fd,),
                    close_fds=True,
                )
            except OSError:
                raise TransportFailure("transport.process_start") from None
        finally:
            os.close(read_fd)
        try:
            stdout, _stderr = process.communicate(raw, timeout=config["timeout_seconds"])
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise TransportFailure("transport.timeout") from None
        except OSError:
            process.kill()
            process.communicate()
            raise TransportFailure("transport.process_io") from None
        if process.returncode == 28:
            raise TransportFailure("transport.timeout")
        if process.returncode == 63:
            raise TransportFailure("transport.http_response_byte_cap")
        if process.returncode != 0:
            raise TransportFailure("transport.curl_failure")
        body, separator, status = stdout.rpartition(b"\n")
        if not separator or len(status) != 3 or not status.isdigit():
            raise TransportFailure("transport.http_status_unavailable")
        if len(body) > config["maximum_http_response_bytes"]:
            raise TransportFailure("transport.http_response_byte_cap")
        return {"http_status": int(status), "body": body}


class MockTransport:
    """Explicit local adapter mock; cannot be registered as model-origin evidence."""

    def __init__(self, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self.handler = handler

    def send(self, request: dict[str, Any], *, api_key: str | None) -> dict[str, Any]:
        # The mock handler receives only the exact public HTTP request, never credentials.
        return self.handler(copy.deepcopy(request))


def _metadata_string(value: Any) -> str | None:
    # Control characters and unbounded metadata must not become an artifact channel.
    if not isinstance(value, str) or len(value) > 512:
        return None
    if any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        return None
    return value


def _usage(envelope: dict[str, Any]) -> dict[str, int | None]:
    supplied = envelope.get("usage")
    supplied = supplied if isinstance(supplied, dict) else {}
    details = supplied.get("completion_tokens_details")
    details = details if isinstance(details, dict) else {}
    result: dict[str, int | None] = {}
    for key in USAGE_KEYS:
        value = supplied.get(key) if key != "reasoning_tokens" else details.get(key)
        result[key] = value if type(value) is int and value >= 0 else None
    return result


def _unique_envelope_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate envelope key")
        result[key] = value
    return result


class DeepSeekAdapter:
    """Source-bound request/attempt/response bridge with separate mock provenance."""

    def __init__(
        self,
        config: dict[str, Any],
        *,
        transport: CurlTransport | MockTransport | None = None,
    ) -> None:
        require(config == model_config(), "adapter.frozen_configuration")
        self.config = copy.deepcopy(config)
        self.transport = transport if transport is not None else CurlTransport(config)
        require(type(self.transport) in {CurlTransport, MockTransport}, "adapter.transport_class")
        origin = "model" if type(self.transport) is CurlTransport else "adapter_mock"
        path = Path(__file__).resolve()
        transport_binding = record(
            "transport_binding",
            **source_binding(__name__, type(self.transport).__name__, "send", path),
            origin=origin,
            kind=origin,
        )
        self.binding = record(
            "adapter_binding",
            origin=origin,
            kind=origin,
            model_configuration_id=config["id"],
            adapter_callback=source_binding(__name__, type(self).__name__, "perform", path),
            transport_binding=transport_binding,
        )

    def perform(
        self,
        request: dict[str, Any],
        *,
        api_key: str | None = None,
        reserve: Callable[[dict[str, Any]], dict[str, Any]],
        send: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        config = self.config
        require(config == model_config(), "adapter.frozen_configuration")
        transport_binding = self.binding["transport_binding"]
        admitted: Any = verify_callback(self.transport, transport_binding)
        require(send is None or send == admitted, "adapter.registered_transport_callable")
        supplied = json.loads(request["body_json"])
        public_request = json.loads(supplied["messages"][1]["content"])
        require(
            request
            == render_http_request(
                public_request,
                config,
                session_id=request["session_id"],
                turn_index=request["turn_index"],
                call_id=request["call_id"],
            ),
            "adapter.request_exact",
        )
        # The caller must durably write and read back this reservation before returning it.
        # Any send outcome below consumes this attempt, including timeout and missing content.
        reservation = reserve(copy.deepcopy(request))
        metadata: dict[str, Any] = {
            "http_status": None,
            "received_model": None,
            "response_id": None,
            "system_fingerprint": None,
            "finish_reason": None,
            "usage": dict.fromkeys(USAGE_KEYS),
        }
        public: bytes | None = None
        status = "transport_failure"
        code: str | None = "transport.unclassified_failure"
        try:
            received = admitted(copy.deepcopy(request), api_key=api_key)
        except TransportFailure as error:
            # Only codes raised by this module are admitted; foreign exception text is dropped.
            known = {
                "transport.invalid_credential",
                "transport.process_start",
                "transport.timeout",
                "transport.process_io",
                "transport.http_response_byte_cap",
                "transport.curl_failure",
                "transport.http_status_unavailable",
            }
            code = error.code if error.code in known else "transport.unclassified_failure"
        except Exception:
            # No exception object, chained message, response body or stderr is persisted.
            pass
        else:
            status, code, public = self._extract(received, metadata)
        parser_status = "not_available"
        parser_code: str | None = None
        if public is not None:
            try:
                parse_submission(public)
            except ProtocolError as error:
                parser_status, parser_code = "invalid", error.stage
            except RecursionError:
                parser_status, parser_code = "invalid", "schema.public_submission"
            else:
                parser_status, parser_code = "valid", "schema.valid"
        evidence = {
            "valid": "public_submission_replayable",
            "invalid": "receiver_diagnosis_only",
        }.get(
            parser_status,
            "typed_transport_observation"
            if status == "transport_failure"
            else "receiver_envelope_diagnosis_only",
        )
        response = record(
            "provider_response",
            request_id=request["id"],
            attempt_id=reservation["id"],
            **{
                key: request[key]
                for key in (
                    "session_id",
                    "turn_index",
                    "call_id",
                    "public_request_id",
                    "state_id",
                    "phase",
                    "model_configuration_id",
                )
            },
            transport_binding_id=transport_binding["id"],
            generator_origin=self.binding["origin"],
            status=status,
            code=code,
            **metadata,
            public_content_sha256=sha(public) if public is not None else None,
            public_content_bytes=len(public) if public is not None else None,
            parser_status=parser_status,
            parser_code=parser_code,
            evidence_level=evidence,
        )
        return {
            "request": copy.deepcopy(request),
            "reservation": reservation,
            "response": response,
            "public_content": public,
        }

    def _extract(
        self, received: Any, metadata: dict[str, Any]
    ) -> tuple[str, str | None, bytes | None]:
        """Select content and allowlisted metadata without recording the full envelope."""
        if not isinstance(received, dict):
            return "transport_failure", "transport.invalid_result", None
        http_status = received.get("http_status")
        if type(http_status) is not int or not 100 <= http_status <= 599:
            return "transport_failure", "transport.http_status_unavailable", None
        metadata["http_status"] = http_status
        if not 200 <= http_status <= 299:
            return "transport_failure", "transport.http_error", None
        body = received.get("body")
        if not isinstance(body, bytes):
            return "envelope_failure", "provider.invalid_body_type", None
        if len(body) > self.config["maximum_http_response_bytes"]:
            return "transport_failure", "transport.http_response_byte_cap", None
        try:
            envelope = json.loads(body, object_pairs_hook=_unique_envelope_pairs)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
            return "envelope_failure", "provider.invalid_json_envelope", None
        if not isinstance(envelope, dict):
            return "envelope_failure", "provider.invalid_envelope", None
        metadata.update(
            received_model=_metadata_string(envelope.get("model")),
            response_id=_metadata_string(envelope.get("id")),
            system_fingerprint=_metadata_string(envelope.get("system_fingerprint")),
            usage=_usage(envelope),
        )
        if envelope.get("object") != "chat.completion" or not metadata["response_id"]:
            return "envelope_failure", "provider.response_identity", None
        if metadata["received_model"] not in self.config["allowed_response_models"]:
            return "envelope_failure", "provider.model_identity_mismatch", None
        for key, cap in (
            ("prompt_tokens", "maximum_input_tokens"),
            ("completion_tokens", "max_tokens"),
            ("total_tokens", "maximum_request_reserved_tokens"),
        ):
            value = metadata["usage"][key]
            if value is not None and value > self.config[cap]:
                return "envelope_failure", "provider.actual_token_cap", None
        usage = metadata["usage"]
        if all(
            usage[key] is not None for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        ):
            if usage["prompt_tokens"] + usage["completion_tokens"] != usage["total_tokens"]:
                return "envelope_failure", "provider.usage_inconsistent", None
        choices = envelope.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            return "envelope_failure", "provider.invalid_choices", None
        choice = choices[0]
        metadata["finish_reason"] = _metadata_string(choice.get("finish_reason"))
        if type(choice.get("index")) is not int or choice["index"] != 0:
            return "envelope_failure", "provider.choice_index", None
        if metadata["finish_reason"] not in {
            "stop",
            "length",
            "content_filter",
            "tool_calls",
            "insufficient_system_resource",
        }:
            return "envelope_failure", "provider.finish_reason", None
        if metadata["finish_reason"] == "tool_calls":
            return "envelope_failure", "provider.native_tool_call_forbidden", None
        if metadata["finish_reason"] == "insufficient_system_resource":
            return "transport_failure", "provider.insufficient_system_resource", None
        message = choice.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            return "envelope_failure", "provider.invalid_message", None
        if message.get("tool_calls") or message.get("function_call"):
            return "envelope_failure", "provider.native_tool_call_forbidden", None
        content = message.get("content")
        if not isinstance(content, str):
            return "envelope_failure", "provider.public_content_unavailable", None
        try:
            public = content.encode("utf-8")
        except UnicodeEncodeError:
            return "envelope_failure", "provider.public_content_encoding", None
        return "received", None, public
