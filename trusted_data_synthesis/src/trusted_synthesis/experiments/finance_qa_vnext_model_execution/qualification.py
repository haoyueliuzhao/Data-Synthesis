"""Independent provenance and outcome checks for the registered online QA cohort.

The domain validator owns public Action/Observation/Update semantics.  This
module binds that saved execution to the actual HTTP exchange and distinguishes
an observed unsuccessful run from missing evidence.  It never calls a callback,
transport, task executor, model, or tokenizer.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.measurement import audit_session, compare_sessions
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError, contract

from .models import identity, record


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ProtocolError(code)


def _equal(left: Any, right: Any) -> bool:
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            _require(key not in result, "online.json_duplicate_key")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise ProtocolError("online.json_non_finite")

    return json.loads(data, object_pairs_hook=pairs, parse_constant=reject_constant)


def _identity(value: dict[str, Any]) -> None:
    identity = value.get("id")
    _require(isinstance(identity, str) and ":" in identity, "online.record_identity_missing")
    assert isinstance(identity, str)
    prefix = identity.split(":", 1)[0] + ":"
    body = {key: item for key, item in value.items() if key != "id"}
    _require(identity == strict_canonical_hash(body, prefix=prefix), "online.record_identity")


class _Artifacts:
    """Validate exact file membership and hashes before interpreting parent links."""

    def __init__(self, directory: Path):
        _require(directory.is_dir() and not directory.is_symlink(), "online.transport_directory")
        self.directory = directory.resolve()
        self.files: dict[str, bytes] = {}
        manifest_file = self.directory / "manifest.json"
        _require(not manifest_file.is_symlink(), "online.manifest_symlink")
        self.manifest = _json(manifest_file.read_bytes())
        _identity(self.manifest)
        _require(self.manifest.get("self_excluding") is True, "online.manifest_self_exclusion")
        for member in self.manifest["members"]:
            name = member["path"]
            relative = Path(name)
            _require(
                not relative.is_absolute()
                and ".." not in relative.parts
                and relative.as_posix() == name
                and name != "manifest.json"
                and name not in self.files,
                "online.member_path",
            )
            target = self.directory / relative
            _require(
                not target.is_symlink() and target.resolve().is_relative_to(self.directory),
                "online.member_escape",
            )
            data = target.read_bytes()
            _require(
                _sha(data) == member["sha256"] and len(data) == member["bytes"],
                "online.member_bytes:" + name,
            )
            self.files[name] = data
        actual = {
            path.relative_to(self.directory).as_posix()
            for path in self.directory.rglob("*")
            if path.is_file() and path != manifest_file
        }
        _require(actual == set(self.files), "online.member_set")

    def raw(self, name: str) -> bytes:
        _require(name in self.files, "online.missing_member:" + name)
        return self.files[name]

    def json(self, name: str, *, identified: bool = True) -> dict[str, Any]:
        value = _json(self.raw(name))
        _require(isinstance(value, dict), "online.record_object:" + name)
        if identified:
            _identity(value)
        return value


def compare_qualified_sessions(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Require independently verified online origin before domain finite comparison."""
    for item in (left, right):
        _identity(item)
        _require(
            item.get("qualified") is True
            and item.get("model_origin_verified") is True
            and item.get("evidence_complete") is True,
            "online.comparison_qualification",
        )
    return compare_sessions(left["domain_audit"], right["domain_audit"])


def _registration(adapter: Any, registration: dict[str, Any]) -> None:
    identity(registration, "session_registration")
    _require(registration["protocol_id"] == contract()["id"], "online.protocol_baseline")
    _require(
        registration["context_id"] == adapter.context["id"]
        and registration["task_id"] == adapter.context["task_id"]
        and registration["task_type"] == adapter.context["task_type"]
        and registration["registry_hash"] == strict_canonical_hash(adapter.registry.manifest()),
        "online.registered_task_context_registry",
    )
    _require(
        registration["replacement_allowed"] is False
        and registration["reference_route"] is None
        and registration["independent_initial_state"] is True,
        "online.registered_sampling_condition",
    )
    _require(
        1 <= registration["maximum_actions"] <= 12
        and registration["maximum_actions"] <= registration["maximum_submissions"] <= 32
        and 1 <= registration["maximum_provider_attempts"] <= 32,
        "online.registered_bounds",
    )


def _start(registration: dict[str, Any], start: dict[str, Any] | None, expected: str) -> None:
    _require(start is not None, "online.start_record_missing")
    assert start is not None
    identity(start, "session_start")
    _require(
        start["status"] == expected
        and start["session_id"] == registration["session_id"]
        and start["registered_id"] == registration["id"],
        "online.start_parent",
    )


def _configuration(config: dict[str, Any], registration: dict[str, Any]) -> None:
    identity(config, "transport_config")
    _require(config["id"] == registration["model_configuration_id"], "online.configuration_parent")
    _require(
        config["attempts_per_session"] == registration["maximum_provider_attempts"],
        "online.provider_attempt_bound",
    )
    _require(
        config["thinking"] == {"type": "disabled"}
        and config["native_tool_calls"] is False
        and config["automatic_retries"] == config["model_fallbacks"] == config["redirects"] == 0
        and config["stream"] is False,
        "online.configuration_semantics",
    )
    _require(
        config["maximum_request_reserved_tokens"]
        == config["maximum_input_tokens"] + config["max_tokens"]
        and config["maximum_session_reserved_tokens"]
        == config["attempts_per_session"] * config["maximum_request_reserved_tokens"],
        "online.configuration_allowance",
    )


def _http_request(
    files: _Artifacts,
    paths: dict[str, str],
    registration: dict[str, Any],
    config: dict[str, Any],
    turn: int,
    attempt: int | None,
    *,
    resource_stop: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    public = files.json(paths["public_request"])
    request = files.json(paths["http_request"])
    identity(request, "http_request")
    raw = files.raw(paths["http_request_body"])
    body = _json(raw)
    messages = [
        {"role": "system", "content": config["system_prompt"]},
        {"role": "user", "content": canonical_json_bytes(public).decode("utf-8")},
    ]
    expected_body = {
        "model": config["model"],
        "thinking": config["thinking"],
        "temperature": config["temperature"],
        "top_p": config["top_p"],
        "max_tokens": config["max_tokens"],
        "response_format": config["response_format"],
        "stream": config["stream"],
        "messages": messages,
    }
    _require(
        _equal(body, expected_body)
        and raw == canonical_json_bytes(body)
        and request["body_json"] == raw.decode("utf-8")
        and _equal(request["body"], body)
        and _equal(request["messages"], messages),
        "online.actual_http_messages_or_configuration",
    )
    _require(
        public["protocol_id"] == registration["protocol_id"]
        and public["state"]["protocol_id"] == registration["protocol_id"]
        and public["context"]["id"] == registration["context_id"]
        and public["context"]["task_id"] == registration["task_id"]
        and public["state"]["context_id"] == registration["context_id"]
        and public["state"]["submission_count"] == turn,
        "online.actual_public_state",
    )
    expected = {
        "session_id": registration["session_id"],
        "turn_index": turn,
        "attempt_index": attempt,
        "public_request_id": public["id"],
        "public_runtime_state_id": public["state"]["id"],
        "context_id": registration["context_id"],
        "task_id": registration["task_id"],
        "protocol_id": registration["protocol_id"],
        "model_configuration_id": config["id"],
        "endpoint": config["endpoint"],
        "body_sha256": _sha(raw),
        "body_byte_count": len(raw),
        "input_admission_upper_bound": len(raw) + config["input_overhead_allowance"],
        "input_allowance": config["maximum_input_tokens"],
        "reserved_tokens": config["maximum_request_reserved_tokens"],
    }
    _require(
        all(_equal(request[key], value) for key, value in expected.items()),
        "online.http_request_parent_or_budget",
    )
    if not resource_stop:
        _require(
            len(raw) <= config["maximum_serialized_request_bytes"]
            and request["input_admission_upper_bound"] <= config["maximum_input_tokens"],
            "online.sent_request_resource_limit",
        )
    return public, request, raw


def _position(journal: list[dict[str, Any]], kind: str, **fields: Any) -> int:
    found = [
        index
        for index, entry in enumerate(journal)
        if entry.get("kind") == kind
        and all(entry.get(key) == value for key, value in fields.items())
    ]
    _require(len(found) == 1, "online.unique_journal_event:" + kind)
    return found[0]


def _reservation_order(
    journal: list[dict[str, Any]],
    paths: dict[str, str],
    request: dict[str, Any],
    reservation: dict[str, Any],
) -> None:
    index = request["attempt_index"]
    readback = _position(journal, "reservation_readback", attempt_index=index)
    send = _position(journal, "send", attempt_index=index)
    _require(
        journal[readback]["reservation_path"] == paths["reservation"]
        and journal[readback]["http_request_body_path"] == paths["http_request_body"]
        and journal[send]["http_request_id"] == request["id"]
        and journal[send]["reservation_id"] == reservation["id"]
        and readback < send,
        "online.reservation_before_send",
    )
    for key in ("public_request", "http_request_body", "http_request", "reservation"):
        file_sync = _position(journal, "file_fsync", path=paths[key])
        directory_sync = _position(journal, "directory_fsync", path=paths[key])
        _require(file_sync < directory_sync < readback, "online.pre_send_durability")


def _observed_usage(
    envelope: dict[str, Any], config: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    raw = envelope.get("usage")
    raw = raw if isinstance(raw, dict) else {}
    nested = raw.get("completion_tokens_details")
    values = {
        **raw,
        "reasoning_tokens": nested.get("reasoning_tokens") if isinstance(nested, dict) else None,
    }
    fields = (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "reasoning_tokens",
    )
    usage: dict[str, Any] = {
        field: values.get(field) if type(values.get(field)) is int and values[field] >= 0 else None
        for field in fields
    }
    flags = []
    if any(
        field in values and values[field] is not None and usage[field] is None for field in fields
    ):
        flags.append("provider.invalid_usage")
    if all(usage[field] is not None for field in fields[:3]):
        if usage["prompt_tokens"] + usage["completion_tokens"] != usage["total_tokens"]:
            flags.append("provider.usage_sum_mismatch")
    limits = {
        "prompt_tokens": config["maximum_input_tokens"],
        "completion_tokens": config["max_tokens"],
        "total_tokens": config["maximum_request_reserved_tokens"],
    }
    for field, limit in limits.items():
        if usage[field] is not None and usage[field] > limit:
            flags.append("provider.usage_exceeds_allowance." + field)
    if usage["reasoning_tokens"] not in (None, 0):
        flags.append("provider.unexpected_reasoning_tokens")
    return usage, flags


def _response(
    files: _Artifacts,
    paths: dict[str, str],
    request: dict[str, Any],
    reservation: dict[str, Any],
    outcome: dict[str, Any],
    config: dict[str, Any],
    journal: list[dict[str, Any]],
) -> tuple[bytes | None, dict[str, bool], str | None]:
    """Decode the observed HTTP bytes independently of the transport's parser flags."""
    attempt = request["attempt_index"]
    sent = _position(journal, "send", attempt_index=attempt)
    persisted = _position(journal, "outcome_persisted", attempt_index=attempt)
    _require(
        journal[persisted]["outcome_id"] == outcome["id"]
        and journal[persisted]["outcome_path"] == paths["outcome"],
        "online.outcome_journal_parent",
    )
    outcome_sync = _position(journal, "directory_fsync", path=paths["outcome"])
    _require(sent < outcome_sync < persisted, "online.outcome_after_send")

    def no_decoded_envelope() -> None:
        empty_usage, _ = _observed_usage({}, config)
        _require(
            all(
                outcome[key] is None
                for key in (
                    "observed_model",
                    "provider_response_id",
                    "system_fingerprint",
                    "finish_reason",
                    "public_content_sha256",
                    "public_content_byte_count",
                )
            )
            and outcome["public_content_present"] is False
            and _equal(outcome["usage"], empty_usage)
            and outcome["condition_flags"] == []
            and "public_content" not in paths,
            "online.no_envelope_no_invented_observation",
        )

    failure_markers = [
        entry
        for entry in journal
        if entry.get("kind") == "send_failed" and entry.get("attempt_index") == attempt
    ]
    transport_failure = outcome["status"] == "transport_failure"
    if transport_failure:
        _require(
            len(failure_markers) == 1
            and failure_markers[0]["code"] == outcome["code"]
            and outcome["code"]
            in {
                "transport.timeout",
                "transport.http_io",
                "transport.response_byte_cap",
                "transport.credential_unavailable",
                "transport.unclassified_failure",
            },
            "online.transport_failure_evidence",
        )
        failure = _position(journal, "send_failed", attempt_index=attempt)
        _require(sent < failure < outcome_sync, "online.failed_send_evidence")
    else:
        _require(not failure_markers, "online.unreported_transport_failure")
    if "http_response" not in paths:
        _require(
            "http_response_body" not in paths
            and outcome["http_response_id"] is None
            and outcome["public_content_returned_to_runtime"] is False
            and transport_failure,
            "online.absent_response_outcome",
        )
        _require(
            outcome["observed_model"] is None
            and outcome["provider_response_id"] is None
            and outcome["public_content_present"] is False
            and outcome["public_content_sha256"] is None
            and "public_content" not in paths,
            "online.absent_response_no_fabricated_content",
        )
        no_decoded_envelope()
        return None, {}, None
    response = files.json(paths["http_response"])
    identity(response, "http_response")
    raw = files.raw(paths["http_response_body"])
    _require(
        response["id"] == outcome["http_response_id"]
        and response["http_request_id"] == request["id"]
        and response["reservation_id"] == reservation["id"]
        and response["body_sha256"] == _sha(raw)
        and response["body_byte_count"] == len(raw),
        "online.observed_http_response_parent",
    )
    received = _position(journal, "receive", attempt_index=attempt)
    _require(
        sent < received < outcome_sync
        and journal[received]["status_code"] == response["status_code"]
        and journal[received]["body_byte_count"] == len(raw),
        "online.receive_evidence",
    )
    if response["complete"] is not True:
        _require(
            (transport_failure or outcome["code"] == "provider.incomplete_http_response")
            and outcome["public_content_returned_to_runtime"] is False
            and outcome["public_content_present"] is False
            and "public_content" not in paths,
            "online.partial_response_outcome",
        )
        no_decoded_envelope()
        return None, {}, None
    try:
        envelope = _json(raw)
        _require(isinstance(envelope, dict), "online.provider_envelope_object")
    except (ValueError, UnicodeError):
        _require(
            (transport_failure or outcome["code"] == "provider.invalid_envelope")
            and outcome["public_content_returned_to_runtime"] is False,
            "online.invalid_envelope_outcome",
        )
        no_decoded_envelope()
        return None, {}, None
    usage, flags = _observed_usage(envelope, config)
    choices = envelope.get("choices")
    choice = (
        choices[0]
        if isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict)
        else {}
    )
    candidate_message = choice.get("message")
    message: dict[str, Any] = candidate_message if isinstance(candidate_message, dict) else {}
    content = message.get("content")
    encoding_error = False
    try:
        public = content.encode("utf-8") if isinstance(content, str) else None
    except UnicodeError:
        public, encoding_error = None, True
    if message.get("reasoning_content"):
        flags.append("provider.unexpected_reasoning_content")
    if (
        message.get("tool_calls")
        or message.get("function_call")
        or choice.get("finish_reason") == "tool_calls"
    ):
        flags.append("provider.unexpected_native_tool_calls")
    if public is not None and len(public) > config["maximum_public_response_bytes"]:
        flags.append("provider.public_content_exceeds_runtime_cap")
    observed_model = envelope.get("model") if isinstance(envelope.get("model"), str) else None
    response_id = envelope.get("id") if isinstance(envelope.get("id"), str) else None
    fingerprint = (
        envelope.get("system_fingerprint")
        if isinstance(envelope.get("system_fingerprint"), str)
        else None
    )
    expected = {
        "observed_model": observed_model,
        "provider_response_id": response_id,
        "system_fingerprint": fingerprint,
        "finish_reason": choice.get("finish_reason"),
        "usage": usage,
        "condition_flags": sorted(set(flags)),
        "public_content_present": public is not None,
        "public_content_sha256": _sha(public) if public is not None else None,
        "public_content_byte_count": len(public) if public is not None else None,
    }
    _require(
        all(_equal(outcome[key], value) for key, value in expected.items()),
        "online.raw_envelope_attribution",
    )
    if public is not None:
        _require(
            files.raw(paths["public_content"]) == public, "online.retained_public_content_bytes"
        )
    else:
        _require("public_content" not in paths, "online.absent_content_no_text_file")
    code = "provider.public_content_encoding" if encoding_error else None
    if not 200 <= response["status_code"] < 300:
        code = "provider.http_error"
    elif observed_model not in config["allowed_response_models"]:
        code = "provider.model_identity_mismatch"
    elif envelope.get("object") != "chat.completion" or not response_id:
        code = "provider.response_identity"
    elif (
        not choice
        or type(choice.get("index")) is not int
        or choice["index"] != 0
        or message.get("role") != "assistant"
    ):
        code = "provider.response_shape"
    elif code is None and not public:
        code = "provider.no_public_content"
    checks = {
        "no_observed_condition_deviation": not flags,
        "observed_model_allowed": observed_model in config["allowed_response_models"],
    }
    if transport_failure or code is not None:
        _require(
            (transport_failure or outcome["code"] == code)
            and outcome["public_content_returned_to_runtime"] is False,
            "online.observed_failure_classification",
        )
        return None, checks, observed_model
    assert public is not None
    _require(
        outcome["status"] == "public_content"
        and outcome["public_content_present"] is True
        and outcome["public_content_returned_to_runtime"] is True
        and outcome["public_content_sha256"] == _sha(public)
        and outcome["public_content_byte_count"] == len(public)
        and outcome["code"] is None,
        "online.exact_public_content",
    )
    return public, checks, observed_model


def _verified_turn(
    files: _Artifacts,
    paths: dict[str, str],
    event: dict[str, Any],
    public_request: dict[str, Any],
    request: dict[str, Any],
    reservation: dict[str, Any],
    outcome: dict[str, Any],
    content: bytes,
    runtime_directory: Path,
) -> dict[str, Any]:
    turn = event["sequence"]
    _require(_equal(event["request"], public_request), "online.runtime_request_disagreement")
    actual = (runtime_directory / f"turns/{turn:03d}_response.txt").read_bytes()
    _require(
        actual == content
        and event["submission"]["raw_sha256"] == _sha(content)
        and event["submission"]["raw_bytes"] == len(content),
        "online.runtime_content_disagreement",
    )
    _require(
        event["submission"]["request_id"] == public_request["id"]
        and event["receipt"]["submission_id"] == event["submission"]["id"]
        and event["receipt"]["request_id"] == public_request["id"],
        "online.runtime_submission_receipt_parent",
    )
    return {
        "turn_index": turn,
        "public_request_id": public_request["id"],
        "public_runtime_state_id": public_request["state"]["id"],
        "provider_attempt_id": reservation["id"],
        "request_id": request["id"],
        "response_id": outcome["http_response_id"],
        "provider_response_id": outcome["provider_response_id"],
        "submission_id": event["submission"]["id"],
        "receipt_id": event["receipt"]["id"],
        "model_origin_evidence_id": outcome["id"],
        "public_request_path": paths["public_request"],
        "public_request_sha256": _sha(files.raw(paths["public_request"])),
        "request_path": paths["http_request_body"],
        "request_sha256": _sha(files.raw(paths["http_request_body"])),
        "response_path": paths["http_response_body"],
        "response_sha256": _sha(files.raw(paths["http_response_body"])),
        "raw_public_content_path": paths["public_content"],
        "raw_public_content_sha256": _sha(content),
        "admitted": event["receipt"]["admitted"],
    }


def _callback_stop(
    session: dict[str, Any],
    outcome: dict[str, Any],
    public: dict[str, Any],
    runtime_directory: Path,
) -> None:
    stop = session.get("callback_stop")
    _require(isinstance(stop, dict), "online.callback_stop_missing")
    assert isinstance(stop, dict)
    _identity(stop)
    turn = len(session["events"])
    _require(
        stop["sequence"] == turn
        and stop["request_id"] == public["id"]
        and stop["state_id"] == public["state"]["id"]
        and stop["external_evidence_id"] == outcome["id"]
        and stop["reason"] == outcome["code"],
        "online.callback_stop_parent",
    )
    _require(
        (runtime_directory / f"turns/{turn:03d}_request.json").read_bytes()
        == canonical_json_bytes(public),
        "online.stopping_actual_request",
    )
    for suffix in ("response.txt", "submission.json", "receipt.json"):
        _require(
            not (runtime_directory / f"turns/{turn:03d}_{suffix}").exists(),
            "online.stop_fabricated_submission",
        )


def _whole_journal(files: _Artifacts, ledger: dict[str, Any]) -> None:
    journal = ledger["write_events"]
    attempts, stops = ledger["attempts"], ledger["stops"]
    allowed = {
        "file_fsync",
        "directory_fsync",
        "reservation_readback",
        "send",
        "receive",
        "send_failed",
        "outcome_persisted",
    }
    _require(all(item.get("kind") in allowed for item in journal), "online.unknown_journal_effect")
    for kind in ("send", "reservation_readback"):
        _require(
            [item["attempt_index"] for item in journal if item["kind"] == kind]
            == list(range(len(attempts))),
            "online.journal_attempt_count",
        )
    _require(
        [item["outcome_id"] for item in journal if item["kind"] == "outcome_persisted"]
        == [row["outcome_id"] for row in attempts + stops],
        "online.journal_outcome_count",
    )
    _require(
        [item["attempt_index"] for item in journal if item["kind"] == "receive"]
        == [
            row["attempt_index"]
            for row in attempts
            if row["paths"].get("http_response") is not None
        ],
        "online.journal_receive_count",
    )
    failures = [
        row["attempt_index"]
        for row in attempts
        if files.json(row["paths"]["outcome"])["status"] == "transport_failure"
    ]
    _require(
        [item["attempt_index"] for item in journal if item["kind"] == "send_failed"] == failures,
        "online.journal_failure_count",
    )
    for kind in ("file_fsync", "directory_fsync"):
        paths = [item["path"] for item in journal if item["kind"] == kind]
        _require(
            len(paths) == len(set(paths)) and set(paths) == set(files.files) - {"ledger.json"},
            "online.journal_file_set",
        )
    for path in set(files.files) - {"ledger.json"}:
        _require(
            _position(journal, "file_fsync", path=path)
            < _position(journal, "directory_fsync", path=path),
            "online.journal_file_directory_order",
        )


def _chain(
    adapter: Any,
    registration: dict[str, Any],
    session: dict[str, Any],
    runtime_directory: Path,
    transport_directory: Path,
) -> dict[str, Any]:
    domain_audit = audit_session(adapter, session, runtime_directory)
    _require(domain_audit["validation_passed"] is True, "online.domain_validation_failed")
    _require(
        session["bounds"]
        == {
            "actions": registration["maximum_actions"],
            "submissions": registration["maximum_submissions"],
        },
        "online.runtime_registered_bounds",
    )
    files = _Artifacts(transport_directory)
    config, binding, ledger = (
        files.json(name) for name in ("config.json", "binding.json", "ledger.json")
    )
    identity(binding, "callback_binding")
    identity(ledger, "transport_ledger")
    identity(files.manifest, "transport_manifest")
    _configuration(config, registration)
    _require(
        binding["session_id"] == registration["session_id"]
        and binding["model_configuration_id"] == config["id"]
        and _equal(session["callback_binding"], binding),
        "online.callback_binding_parent",
    )
    _require(
        binding["host_semantic_field_fill"] is False
        and binding["automatic_retries"] == binding["model_fallbacks"] == 0
        and binding["model_origin_requires_attempt_response_evidence"] is True,
        "online.callback_no_repair_or_fallback",
    )
    implementation = binding["implementation"]
    source = Path(__file__).with_name("transport.py").read_bytes()
    module = "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
    _require(
        implementation["module"] == module
        and implementation["class"] == "OnlineModelCallback"
        and implementation["method"] == "generate"
        and implementation["source_relative_path"]
        == (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/"
            "finance_qa_vnext_model_execution/transport.py"
        )
        and implementation["source_sha256"] == _sha(source)
        and implementation["source_byte_count"] == len(source),
        "online.transport_source_binding",
    )
    _require(binding["transport_kind"] in {"live_http", "adapter_mock"}, "online.transport_kind")
    if binding["transport_kind"] == "live_http":
        sender = binding["sender_implementation"]
        _require(
            sender["module"] == module
            and sender["class"] == "HttpxSender"
            and sender["method"] == "send"
            and sender["httpx_version"] == importlib.metadata.version("httpx"),
            "online.live_sender_source_binding",
        )
    _require(
        files.manifest["session_id"] == registration["session_id"]
        and files.manifest["ledger_id"] == ledger["id"],
        "online.manifest_ledger_parent",
    )
    _require(
        ledger["session_id"] == registration["session_id"]
        and ledger["model_configuration_id"] == config["id"]
        and ledger["callback_binding_id"] == binding["id"]
        and ledger["transport_kind"] == binding["transport_kind"],
        "online.ledger_condition_parent",
    )
    journal = ledger["write_events"]
    expected_journal = journal + [
        {"kind": "file_fsync", "path": "ledger.json"},
        {"kind": "directory_fsync", "path": "ledger.json"},
    ]
    _require(
        _equal(files.manifest["write_events"], expected_journal), "online.ledger_journal_binding"
    )
    rows, stops = ledger["attempts"], ledger["stops"]
    _require(
        len(rows) == ledger["provider_attempt_count"] <= registration["maximum_provider_attempts"]
        and len(stops) <= 1,
        "online.attempt_denominator",
    )
    expected_paths = {"config.json", "binding.json", "ledger.json"}
    verified: list[dict[str, Any]] = []
    observed_models: list[str] = []
    condition_rows: list[dict[str, Any]] = []
    terminal_outcome = None
    for index, row in enumerate(rows):
        _require(
            terminal_outcome is None
            and row["attempt_index"] == index
            and row["turn_index"] == index,
            "online.no_hidden_retry_or_replacement",
        )
        paths = {key: value for key, value in row["paths"].items() if value is not None}
        _require(not (expected_paths & set(paths.values())), "online.reused_artifact_path")
        expected_paths.update(paths.values())
        public, request, _ = _http_request(files, paths, registration, config, index, index)
        reservation = files.json(paths["reservation"])
        identity(reservation, "attempt_reservation")
        expected = {
            "session_id": registration["session_id"],
            "turn_index": index,
            "attempt_index": index,
            "public_request_id": public["id"],
            "public_runtime_state_id": public["state"]["id"],
            "http_request_id": request["id"],
            "callback_binding_id": binding["id"],
            "model_configuration_id": config["id"],
            "reserved_tokens": config["maximum_request_reserved_tokens"],
            "session_reserved_tokens_after": (index + 1)
            * config["maximum_request_reserved_tokens"],
            "attempt_consumed": True,
            "reserved_before_send": True,
        }
        _require(
            all(_equal(reservation[key], value) for key, value in expected.items()),
            "online.reservation_parent",
        )
        _reservation_order(journal, paths, request, reservation)
        outcome = files.json(paths["outcome"])
        identity(outcome, "provider_outcome")
        _require(row["outcome_id"] == outcome["id"], "online.outcome_ledger_parent")
        parents = {
            key: value
            for key, value in expected.items()
            if key
            not in {
                "reserved_tokens",
                "session_reserved_tokens_after",
                "attempt_consumed",
                "reserved_before_send",
            }
        }
        parents.update(reservation_id=reservation["id"], transport_kind=binding["transport_kind"])
        parents.update(provider_attempt_consumed=True, automatic_retries=0, host_repairs=[])
        _require(
            all(_equal(outcome[key], value) for key, value in parents.items()),
            "online.outcome_parent",
        )
        content, checks, observed_model = _response(
            files, paths, request, reservation, outcome, config, journal
        )
        condition_rows.append({"outcome_id": outcome["id"], "checks": checks})
        if observed_model is not None:
            observed_models.append(observed_model)
        if content is not None:
            _require(index < len(session["events"]), "online.response_without_runtime_submission")
            verified.append(
                _verified_turn(
                    files,
                    paths,
                    session["events"][index],
                    public,
                    request,
                    reservation,
                    outcome,
                    content,
                    runtime_directory,
                )
            )
        else:
            _require(index == len(session["events"]), "online.failure_turn_boundary")
            _callback_stop(session, outcome, public, runtime_directory)
            terminal_outcome = outcome
    for stop_row in stops:
        _require(
            terminal_outcome is None and len(verified) == len(session["events"]),
            "online.resource_stop_boundary",
        )
        paths = {key: value for key, value in stop_row["paths"].items() if value is not None}
        _require(not (expected_paths & set(paths.values())), "online.reused_artifact_path")
        expected_paths.update(paths.values())
        public, request, raw = _http_request(
            files, paths, registration, config, len(rows), len(rows), resource_stop=True
        )
        outcome = files.json(paths["outcome"])
        identity(outcome, "provider_outcome")
        _require(
            outcome["id"] == stop_row["outcome_id"]
            and outcome["status"] == "resource_termination"
            and outcome["reservation_id"] is None
            and outcome["attempt_index"] == len(rows)
            and outcome["provider_attempt_consumed"] is False
            and outcome["http_request_id"] == request["id"]
            and outcome["public_request_id"] == public["id"]
            and outcome["public_runtime_state_id"] == public["state"]["id"]
            and outcome["session_id"] == registration["session_id"],
            "online.resource_stop_parent",
        )
        _require(
            len(rows) >= config["attempts_per_session"]
            or len(raw) > config["maximum_serialized_request_bytes"]
            or len(raw) + config["input_overhead_allowance"] > config["maximum_input_tokens"],
            "online.resource_stop_observed_limit",
        )
        expected_code = (
            "resource.attempt_budget"
            if len(rows) >= config["attempts_per_session"]
            else "resource.input_budget"
        )
        _require(
            outcome["code"] == expected_code
            and "reservation" not in paths
            and "http_response" not in paths
            and "public_content" not in paths
            and outcome["public_content_returned_to_runtime"] is False,
            "online.resource_stop_no_phantom_attempt",
        )
        persisted = _position(journal, "outcome_persisted", attempt_index=len(rows))
        _require(
            journal[persisted]["outcome_id"] == outcome["id"]
            and journal[persisted]["outcome_path"] == paths["outcome"]
            and _position(journal, "directory_fsync", path=paths["outcome"]) < persisted,
            "online.resource_stop_durable_outcome",
        )
        _require(
            not any(
                item.get("kind") == "send" and item.get("attempt_index") == len(rows)
                for item in journal
            ),
            "online.resource_stop_sent_request",
        )
        _callback_stop(session, outcome, public, runtime_directory)
        terminal_outcome = outcome
    _require(expected_paths == set(files.files), "online.unindexed_transport_evidence")
    _whole_journal(files, ledger)
    _require(len(verified) == len(session["events"]), "online.runtime_response_coverage")
    _require(
        ledger["reserved_tokens"]
        == len(rows) * config["maximum_request_reserved_tokens"]
        <= config["maximum_session_reserved_tokens"],
        "online.reservation_total",
    )
    if session.get("callback_stop") is not None:
        _require(terminal_outcome is not None, "online.stop_outcome_missing")
    elif session["final"] is None:
        _require(
            session["terminal_state"]["last_feedback"]["code"] == "submission_budget_exhausted"
            and len(session["events"]) == registration["maximum_submissions"],
            "online.unknown_terminal_condition",
        )
    condition_valid = all(all(row["checks"].values()) for row in condition_rows)
    model_origin = (
        binding["transport_kind"] == "live_http"
        and bool(verified)
        and all(model in config["allowed_response_models"] for model in observed_models)
    )
    qa_valid = domain_audit["qa_valid"] if session["final"] is not None else None
    qualified = model_origin and condition_valid and domain_audit["qualified"] is True
    reason = (
        None
        if qualified
        else (
            "generation_condition_failed"
            if not condition_valid
            else terminal_outcome["code"]
            if terminal_outcome
            else "submission_budget_exhausted"
            if session["final"] is None
            else "model_origin_not_verified"
        )
    )
    return {
        "status": "success" if qualified else "known_failure",
        "reason": reason,
        "execution_started": True,
        "terminated": session["terminal_state"]["terminal"],
        "evidence_complete": True,
        "model_origin_verified": model_origin,
        "condition_valid": condition_valid,
        "condition_checks": condition_rows,
        "qa_valid": qa_valid,
        "trajectory_valid": domain_audit["trajectory_valid"],
        "qualified": qualified,
        "end_to_end_success": qualified,
        "export_eligible": qualified,
        "projection_status": "supported"
        if qualified and domain_audit["projection_supported"]
        else "undetermined",
        "quotient_assignment_id": None,
        "domain_audit": domain_audit,
        "domain_audit_id": domain_audit["id"],
        "depth_metrics": domain_audit["depth_metrics"],
        "depth_scope": "complete_session" if session["final"] is not None else "reached_prefix",
        "verified_turns": verified,
        "provider_attempt_count": len(rows),
        "runtime_submission_count": len(session["events"]),
        "actual_response_models": sorted(set(observed_models)),
        "transport_manifest_id": files.manifest["id"],
        "transport_manifest_sha256": _sha((transport_directory / "manifest.json").read_bytes()),
        "transport_ledger_id": ledger["id"],
        "transport_binding_id": binding["id"],
        "terminal_outcome_id": terminal_outcome["id"] if terminal_outcome else None,
        "control_evidence": binding["transport_kind"] != "live_http",
        "errors": [],
    }


def qualify_session(
    adapter: Any,
    registration: dict[str, Any],
    session_or_none: dict[str, Any] | None,
    runtime_directory: str | Path,
    transport_directory: str | Path,
    *,
    start_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Qualify one fixed registration; missing evidence never becomes Y=0."""
    details: dict[str, Any] = {
        "status": "unknown",
        "reason": "evidence_incomplete",
        "execution_started": None,
        "terminated": None,
        "evidence_complete": False,
        "model_origin_verified": False,
        "condition_valid": None,
        "condition_checks": [],
        "qa_valid": None,
        "trajectory_valid": None,
        "qualified": None,
        "end_to_end_success": None,
        "export_eligible": False,
        "projection_status": "undetermined",
        "quotient_assignment_id": None,
        "domain_audit": None,
        "domain_audit_id": None,
        "depth_metrics": None,
        "depth_scope": None,
        "verified_turns": [],
        "provider_attempt_count": None,
        "runtime_submission_count": None,
        "actual_response_models": [],
        "transport_manifest_id": None,
        "transport_manifest_sha256": None,
        "transport_ledger_id": None,
        "transport_binding_id": None,
        "terminal_outcome_id": None,
        "control_evidence": None,
        "errors": [],
    }
    try:
        _registration(adapter, registration)
        if (
            session_or_none is None
            and isinstance(start_record, dict)
            and start_record.get("status") == "started"
        ):
            _start(registration, start_record, "started")
            details.update(execution_started=True, reason="started_session_evidence_missing")
        elif session_or_none is None:
            _start(registration, start_record, "not_started")
            assert start_record is not None
            runtime = Path(runtime_directory)
            transport = Path(transport_directory)
            _require(
                not (runtime / "session.json").exists()
                and not any(transport.glob("attempts/*"))
                and not any(transport.glob("stops/*"))
                and not any(runtime.glob("turns/*")),
                "online.not_started_conflicting_evidence",
            )
            details.update(
                status="not_started",
                reason=start_record.get("reason"),
                execution_started=False,
                terminated=False,
                evidence_complete=True,
                provider_attempt_count=0,
                runtime_submission_count=0,
            )
        else:
            _start(registration, start_record, "started")
            details = _chain(
                adapter,
                registration,
                session_or_none,
                Path(runtime_directory),
                Path(transport_directory),
            )
    except (OSError, ValueError, TypeError, KeyError, IndexError, ArithmeticError) as error:
        details["errors"] = [{"code": str(error), "type": type(error).__name__}]
    return record(
        "qualification",
        registration_id=registration.get("id"),
        registered_session_id=registration.get("session_id"),
        session_id=session_or_none.get("id") if session_or_none else None,
        context_id=registration.get("context_id"),
        task_id=registration.get("task_id"),
        task_type=registration.get("task_type"),
        task_group=registration.get("task_group"),
        protocol_id=registration.get("protocol_id"),
        registry_hash=registration.get("registry_hash"),
        model_configuration_id=registration.get("model_configuration_id"),
        start_record_id=start_record.get("id") if start_record else None,
        registered_denominator_preserved=True,
        provider_calls_by_qualification=0,
        runtime_executions_by_qualification=0,
        historical_protocol_data_reused=False,
        **details,
    )
