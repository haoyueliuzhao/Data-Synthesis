"""Bind new valid open sessions to exact public request/response/event bytes.

No Provider, tool executor or old trajectory is called here. Invalid or unknown
registrations remain in the original online tree and are referenced by the
materializer without pretending that absent public messages were received.
"""

from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    request_body,
    strict_json,
)

from .plan import BASELINE, MODEL, OUTPUT, SYSTEM, encode, read_json, record, require, sha

POSITIVE_TOOL_NAMES = frozenset({"calculate", "read_source", "notebook"})


def content_identity(value, code):
    """Check a content-addressed record without imposing the worker's namespace."""
    require(isinstance(value, dict) and isinstance(value.get("id"), str), code)
    kind, separator, digest = value["id"].partition(":")
    require(
        bool(kind)
        and separator == ":"
        and len(digest) == 64
        and value["id"] == kind + ":" + sha(encode({k: v for k, v in value.items() if k != "id"})),
        code,
    )


def _new_identity(value, code):
    content_identity(value, code)
    kind = value["id"].partition(":")[0]
    require(
        value
        == record(kind, **{k: v for k, v in value.items() if k not in {"id", "schema_version"}}),
        code,
    )


def _event_target(event, raw, final_content):
    """Validate the actual worker decision, preserving first-Final precedence."""
    require(event["raw_sha256"] == sha(raw), "new_source.event_raw_identity")
    call = event["tool_call"]
    if event["protocol_error"] is not None:
        require(call is None and event["final"] is False, "new_source.error_not_execution")
        return None
    parsed = strict_json(raw)
    require(isinstance(parsed, dict), "new_source.legal_response_object")
    if event["final"]:
        require(
            "final" in parsed and parsed["final"] == final_content and call is None,
            "new_source.original_Final",
        )
    elif call is not None:
        require(
            "final" not in parsed
            and parsed.get("tool") == call["name"]
            and parsed.get("arguments", {}) == call["arguments"],
            "new_source.original_tool_arguments",
        )
        require(
            call["output"]["call_id"] == call["id"]
            and call["output"]["tool"] == call["name"]
            and call["output"]["status"] in {"ok", "error"},
            "new_source.tool_output_identity",
        )
    else:
        require("final" not in parsed and "tool" not in parsed, "new_source.message_only_event")
    return parsed


def bind_session(root, row):
    """Bind only a joint-valid new session; missing/unknown sessions are not read as valid."""
    root = Path(root)
    require(row["formula_driven_trace_verified"] is True, "new_source.original_valid_only")
    content_identity(row, "new_source.closeout_identity")
    require(
        row["arm"] == "T" and row["label"].startswith("T_" + row["task_key"] + "_"),
        "new_source.fixed_condition_and_task",
    )
    directory = root / OUTPUT / "online/sessions" / row["label"]
    require(directory.is_dir() and not directory.is_symlink(), "new_source.session_directory")
    session_manifest = manifest(directory)
    result_path = directory / "result.json"
    result_raw = result_path.read_bytes()
    result = read_json(result_path)
    content_identity(result, "new_source.result_identity")
    require(session_manifest["result_id"] == result["id"], "new_source.manifest_result_join")
    public_path = root / OUTPUT / f"preparation/public/{row['task_key']}.json"
    public_raw = public_path.read_bytes()
    public = read_json(public_path)
    content_identity(public, "new_source.public_document_identity")
    require(
        result["origin"] == "live_http"
        and result["requested_model"] == MODEL
        and result["terminal"] == "model_final"
        and row.get("terminal", result["terminal"]) == result["terminal"],
        "new_source.real_valid_Final_session",
    )
    require(
        result["source_document_sha256"] == sha(encode(public))
        and not result["history_truncated"]
        and not result["online_answer_feedback"]
        and not result["hidden_evaluator_loaded"]
        and result["first_final_stops"] is True,
        "new_source.complete_ungraded_source_history",
    )
    attempts, events = result["attempts"], result["events"]
    require(
        len(attempts) == len(events) == result["model_requests"]
        and len(attempts) > 0
        and result["provider_attempts"] == len(attempts)
        and [event["response_index"] for event in events] == list(range(len(events)))
        and [attempt["index"] for attempt in attempts] == list(range(len(attempts))),
        "new_source.valid_complete_attempt_set",
    )
    expected = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": encode({"task": public}).decode()},
    ]
    turns, call_ids = [], []
    for index, (outcome, event) in enumerate(zip(attempts, events, strict=True)):
        prefix = directory / f"turns/{index:03d}"

        def file(suffix, *, turn_prefix=prefix):
            return turn_prefix.with_name(turn_prefix.name + suffix)

        request_bytes = file("_http_request.body").read_bytes()
        projection_bytes = file("_response_projection.json").read_bytes()
        event_bytes = file("_event.json").read_bytes()
        raw = file("_assistant.raw").read_bytes()
        reservation = read_json(file("_reservation.json"))
        content_identity(reservation, "new_source.reservation_identity")
        require(outcome == read_json(file("_outcome.json")), "new_source.original_outcome")
        require(event == strict_json(event_bytes), "new_source.original_event")
        require(event["oracle_feedback"] is False, "new_source.no_oracle_event")
        require(request_bytes == encode(request_body(expected, MODEL)), "new_source.full_request")
        require(
            sha(request_bytes) == outcome["request_sha256"] == reservation["request_sha256"]
            and len(request_bytes) == reservation["request_bytes"]
            and reservation["id"] == outcome["reservation_id"]
            and reservation["index"] == index
            and reservation["requested_model"] == MODEL
            and reservation["provider_call"] is True
            and reservation["prefix_messages"] == len(expected),
            "new_source.original_request_reservation",
        )
        projection = strict_json(projection_bytes)
        require(
            sha(projection_bytes) == outcome["response_projection_sha256"]
            and projection["is_original_http_response"] is False
            and projection["parse_error"] is None
            and outcome["response_is_projection"] is True
            and outcome["origin"] == "live_http"
            and outcome["http_status"] == 200
            and outcome["error"] is None
            and outcome["public_content_received"] is True
            and outcome["public_content_returned"] is True,
            "new_source.received_original_public_projection",
        )
        require(
            projection["id"] == outcome["provider_response_id"]
            and projection["object"] == "chat.completion"
            and projection["model"] == outcome["model"]
            and projection["model"] in {MODEL, MODEL + "-0731"}
            and len(projection["choices"]) == 1
            and projection["usage"] == outcome["usage"]
            and projection["reasoning_telemetry"] == outcome["reasoning_telemetry"],
            "new_source.provider_response_join",
        )
        choice = projection["choices"][0]
        message = choice["message"]
        require(
            choice["index"] == 0
            and choice["finish_reason"] == outcome["finish_reason"] == "stop"
            and message["role"] == "assistant"
            and message["native_tool_calls_present"] is False
            and "reasoning_content" not in message
            and isinstance(message["content"], str)
            and message["content"].encode() == raw,
            "new_source.exact_public_assistant",
        )
        parsed = _event_target(event, raw, result["final"])
        call = event["tool_call"]
        if call is not None:
            require(
                call["output"] == read_json(file("_tool.json")), "new_source.actual_tool_output"
            )
            call_ids.append(call["id"])
            require(call["id"] == "tool:" + str(len(call_ids)), "new_source.actual_tool_order")
        if event["final"]:
            require(index == len(attempts) - 1, "new_source.first_Final_stops")
        binding = record(
            "new_support_interaction_binding",
            historical_implementation_baseline=BASELINE,
            population="T",
            task_key=row["task_key"],
            task_id=public["task_id"],
            source_document_id=public["id"],
            source_document_sha256=sha(public_raw),
            session_label=row["label"],
            session_result_id=result["id"],
            session_result_file_sha256=sha(result_raw),
            session_manifest_id=session_manifest["id"],
            source_closeout_id=row["id"],
            response_index=index,
            provider_response_id=outcome["provider_response_id"],
            request_sha256=sha(request_bytes),
            response_projection_sha256=sha(projection_bytes),
            raw_response_sha256=sha(raw),
            event_sha256=sha(event_bytes),
            reservation_id=reservation["id"],
            response_projection_is_not_original_HTTP=True,
            actual_tool_call_id=call["id"] if call else None,
            original_response_not_rewritten=True,
        )
        turns.append(
            {
                "binding": binding,
                "request_bytes": request_bytes,
                "projection_bytes": projection_bytes,
                "event_bytes": event_bytes,
                "raw": raw,
                "input_messages": strict_json(request_bytes)["messages"],
                "event": event,
                "parsed": parsed,
                "prefix": prefix,
            }
        )
        expected.append({"role": "assistant", "content": raw.decode()})
        if event["protocol_error"] is not None:
            expected.append(
                {
                    "role": "user",
                    "content": encode({"interface_error": event["protocol_error"]}).decode(),
                }
            )
        elif call is not None:
            expected.append(
                {"role": "user", "content": encode({"tool_result": call["output"]}).decode()}
            )
        elif not event["final"]:
            expected.append(
                {"role": "user", "content": encode({"receipt": "model_message_recorded"}).decode()}
            )
    require(
        events[-1]["final"] and sum(event["final"] for event in events) == 1,
        "new_source.one_terminal_Final",
    )
    require(len(call_ids) == result["tool_calls"], "new_source.complete_tool_set")
    require(
        expected == read_json(directory / "messages.json"), "new_source.complete_stored_history"
    )
    require(
        result_path.read_bytes() == result_raw and public_path.read_bytes() == public_raw,
        "new_source.inputs_unchanged",
    )
    return {
        "row": row,
        "result": result,
        "result_bytes": result_raw,
        "public": public,
        "turns": turns,
        "directory": directory,
        "session_manifest_id": session_manifest["id"],
    }


def _joined_turn(session, turn):
    row, result, binding, event = session["row"], session["result"], turn["binding"], turn["event"]
    require(row["formula_driven_trace_verified"] is True, "new_export.valid_session_only")
    content_identity(row, "new_export.closeout_identity")
    content_identity(result, "new_export.result_identity")
    _new_identity(binding, "new_export.binding_identity")
    require(
        binding["session_label"] == row["label"]
        and binding["population"] == row["arm"] == "T"
        and binding["task_key"] == row["task_key"]
        and binding["task_id"] == session["public"]["task_id"]
        and binding["source_document_id"] == session["public"]["id"]
        and binding["source_closeout_id"] == row["id"]
        and binding["session_result_id"] == result["id"]
        and binding["session_manifest_id"] == session["session_manifest_id"],
        "new_export.same_session_task_and_condition",
    )
    require(
        sha(turn["request_bytes"]) == binding["request_sha256"]
        and sha(turn["projection_bytes"]) == binding["response_projection_sha256"]
        and sha(turn["raw"]) == binding["raw_response_sha256"]
        and sha(turn["event_bytes"]) == binding["event_sha256"]
        and strict_json(turn["event_bytes"]) == event
        and strict_json(turn["request_bytes"])["messages"] == turn["input_messages"],
        "new_export.same_interaction_bytes",
    )
    index = binding["response_index"]
    require(
        type(index) is int
        and 0 <= index < len(session["turns"])
        and event["response_index"] == index
        and event == result["events"][index]
        and binding == session["turns"][index]["binding"]
        and all(
            turn[key] == session["turns"][index][key]
            for key in (
                "request_bytes",
                "projection_bytes",
                "event_bytes",
                "raw",
                "input_messages",
                "event",
            )
        ),
        "new_export.original_registered_turn",
    )
    prefix = session["directory"] / f"turns/{index:03d}"
    require(turn["prefix"] == prefix, "new_export.original_turn_path")
    for key, suffix in (
        ("request_bytes", "_http_request.body"),
        ("projection_bytes", "_response_projection.json"),
        ("event_bytes", "_event.json"),
        ("raw", "_assistant.raw"),
    ):
        path = prefix.with_name(prefix.name + suffix)
        require(
            path.is_file() and not path.is_symlink() and path.read_bytes() == turn[key],
            "new_export.persisted_turn_bytes",
        )
    require(
        session["result_bytes"] == (session["directory"] / "result.json").read_bytes()
        and sha(session["result_bytes"]) == binding["session_result_file_sha256"]
        and strict_json(session["result_bytes"]) == result,
        "new_export.persisted_result_identity",
    )
    require(
        binding["actual_tool_call_id"] == (event["tool_call"]["id"] if event["tool_call"] else None)
        and strict_json(turn["projection_bytes"])["choices"][0]["message"]["content"].encode()
        == turn["raw"],
        "new_export.original_projection_and_call",
    )
    parsed = _event_target(event, turn["raw"], result["final"])
    require(parsed == turn["parsed"], "new_export.original_parsed_target")
    return parsed


def positive_candidate(session, turn):
    """Keep legal public explanation turns and successful tools, without target repair."""
    parsed = _joined_turn(session, turn)
    event, binding, row = turn["event"], turn["binding"], session["row"]
    if event["protocol_error"] is not None:
        return None
    call = event["tool_call"]
    if call is not None and (
        call["name"] not in POSITIVE_TOOL_NAMES or call["output"]["status"] != "ok"
    ):
        return None
    response_kind = "Final" if event["final"] else call["name"] if call is not None else "message"
    require(isinstance(parsed, dict), "new_export.legal_positive_object")
    return record(
        "new_support_original_candidate",
        population="T",
        task_key=row["task_key"],
        task_id=session["public"]["task_id"],
        session_label=row["label"],
        response_index=binding["response_index"],
        response_kind=response_kind,
        source_closeout_id=row["id"],
        interaction_binding_id=binding["id"],
        request_sha256=binding["request_sha256"],
        response_projection_sha256=binding["response_projection_sha256"],
        raw_response_sha256=binding["raw_response_sha256"],
        input_messages=turn["input_messages"],
        target_response=turn["raw"].decode(),
        original_system_preserved=True,
        target_only_original_public_model_content=True,
        public_messages_not_merged_into_tool_or_Final=True,
        offline_annotation_inserted_in_target=False,
        source_is_received_projection_not_original_HTTP=True,
        no_training_weight_assigned=True,
    )
