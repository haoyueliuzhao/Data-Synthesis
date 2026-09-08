"""Exact new-session original HTTP/response bindings; no old population reuse."""

import json

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.experiments.finance_qa_vnext_finqa_quotient.source import sha


def read(path):
    return json.loads(path.read_bytes())


def bind_turn(directory, index, registration, *, model_required=True):
    """Exact same-interaction joins, without schema repair or requalification."""
    turn, attempt = f"runtime/turns/{index:03d}", f"transport/attempts/{index:03d}"
    names = {
        "request": turn + "_request.json",
        "raw_response": turn + "_response.raw",
        "transition": turn + "_transition.json",
        "http_request": attempt + "_http_request.body",
        "http_response": attempt + "_http_response.body",
        "outcome": attempt + "_outcome.json",
        "request_metadata": attempt + "_http_request.json",
        "response_metadata": attempt + "_http_response.json",
        "public_content": attempt + "_public_content.txt",
        "public_request": attempt + "_public_request.json",
    }
    contents = {key: (directory / name).read_bytes() for key, name in names.items()}
    request, event, http, response, outcome, req_meta, resp_meta = (
        json.loads(contents[k])
        for k in (
            "request",
            "transition",
            "http_request",
            "http_response",
            "outcome",
            "request_metadata",
            "response_metadata",
        )
    )
    raw = contents["raw_response"]
    require(event["submission_count"] == index + 1, "materialize.submission_index")
    require(
        event["request_id"]
        == request["id"]
        == outcome["public_request_id"]
        == req_meta["public_request_id"]
        == resp_meta["public_request_id"],
        "materialize.request_join",
    )
    require(
        event["before_state_id"]
        == request["state"]["id"]
        == outcome["public_runtime_state_id"]
        == req_meta["public_runtime_state_id"]
        == resp_meta["public_runtime_state_id"],
        "materialize.state_join",
    )
    for item in (outcome, req_meta, resp_meta):
        require(
            item["session_id"] == registration["id"]
            and item["task_id"] == registration["task_id"]
            and item["turn_index"] == item["attempt_index"] == index,
            "materialize.attempt_join",
        )
    require(
        outcome["http_request_id"] == req_meta["id"] == resp_meta["http_request_id"]
        and outcome["http_response_id"] == resp_meta["id"],
        "materialize.http_join",
    )
    require(
        sha(contents["http_request"]) == req_meta["body_sha256"]
        and len(contents["http_request"]) == req_meta["body_byte_count"]
        and http == req_meta["body"],
        "materialize.http_request_bytes",
    )
    require(
        sha(contents["http_response"]) == resp_meta["body_sha256"]
        and len(contents["http_response"]) == resp_meta["body_byte_count"],
        "materialize.http_response_bytes",
    )
    require(
        outcome["transport_kind"] == ("live_http" if model_required else "adapter_mock")
        and outcome["status"] == "public_content"
        and outcome["public_content_returned_to_runtime"]
        and outcome["host_repairs"] == []
        and outcome["condition_flags"] == []
        and outcome["automatic_retries"] == 0,
        "materialize.original_live_content",
    )
    require(
        len(response["choices"]) == 1 and response["choices"][0]["message"]["role"] == "assistant",
        "materialize.one_original_response",
    )
    require(response["id"] == outcome["provider_response_id"], "materialize.provider_response_id")
    require(
        raw == response["choices"][0]["message"]["content"].encode() == contents["public_content"],
        "materialize.raw_response_bytes",
    )
    require(
        sha(raw) == event["raw_sha256"] == outcome["public_content_sha256"]
        and len(raw) == outcome["public_content_byte_count"],
        "materialize.raw_hash",
    )
    if event["model_submission"] is not None:
        require(json.loads(raw) == event["model_submission"], "materialize.no_rewriting")
    else:
        require(not event["admitted"], "materialize.unparsed_not_admitted")
    messages = http["messages"]
    require(
        len(messages) == 2 and [m["role"] for m in messages] == ["system", "user"],
        "materialize.original_messages",
    )
    require(
        messages[1]["content"].encode()
        == contents["request"]
        == contents["public_request"]
        == canonical_json_bytes(request),
        "materialize.original_request_bytes",
    )
    require(
        ("accepted_result_bindings" in request) == (registration["view_condition"] == "V1"),
        "materialize.original_view",
    )
    require(
        event["system_binding"]["raw_response_rewritten"] is False
        and event["system_binding"]["semantic_fields_filled"] is False,
        "materialize.host_not_target",
    )
    binding = record(
        "finqa_original_interaction",
        label=registration["label"],
        index=index,
        public_request_id=request["id"],
        transition_id=event["id"],
        outcome_id=outcome["id"],
        admitted=event["admitted"],
        error=event["error"],
        files={
            k: {"path": names[k], "sha256": sha(v), "bytes": len(v)} for k, v in contents.items()
        },
    )
    return {
        "binding": binding,
        "request": request,
        "event": event,
        "http": http,
        "raw": raw,
        "contents": contents,
        "outcome": outcome,
    }
