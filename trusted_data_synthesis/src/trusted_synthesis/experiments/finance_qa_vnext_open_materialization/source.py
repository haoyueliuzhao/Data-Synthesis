"""Read-only joins to existing open interactions; no Action/Update or old State fiction."""

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    encode,
    request_body,
    strict_json,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import SYSTEMS

from .plan import BASELINE, SOURCE, read_json, record, require, sha


def bind_session(root, row):
    parent = root / SOURCE
    directory = parent / "online/sessions" / row["label"]
    session_manifest = manifest(directory)
    result = read_json(directory / "result.json")
    public_path = parent / f"preparation/public/{row['task_key']}.json"
    public = read_json(public_path)
    require(result["origin"] == "live_http", "source.real_model_origin")
    require(result["requested_model"] == "deepseek-v4-flash", "source.fixed_flash")
    require(result["terminal"] == row["terminal"], "source.terminal_join")
    require(
        not result["history_truncated"] and not result["online_answer_feedback"],
        "source.open_history",
    )
    expected = [
        {"role": "system", "content": SYSTEMS[row["arm"]]},
        {"role": "user", "content": encode({"task": public}).decode()},
    ]
    events = {event["response_index"]: event for event in result["events"]}
    turns = []
    for index, outcome in enumerate(result["attempts"]):
        prefix = directory / f"turns/{index:03d}"

        def file(suffix, *, turn_prefix=prefix):
            return turn_prefix.with_name(turn_prefix.name + suffix)

        request_bytes = file("_http_request.body").read_bytes()
        projection_bytes = file("_response_projection.json").read_bytes()
        raw = file("_assistant.raw").read_bytes()
        projection = strict_json(projection_bytes)
        require(request_bytes == encode(request_body(expected)), "source.same_exact_full_request")
        require(sha(request_bytes) == outcome["request_sha256"], "source.request_sha")
        require(
            sha(projection_bytes) == outcome["response_projection_sha256"], "source.projection_sha"
        )
        require(
            projection["is_original_http_response"] is False, "source.projection_not_HTTP_original"
        )
        require(
            outcome["origin"] == "live_http" and outcome["public_content_returned"],
            "source.received_public_content",
        )
        message = projection["choices"][0]["message"]
        require(
            "reasoning_content" not in message and message["content"].encode() == raw,
            "source.public_content_exact",
        )
        event = events[index]
        require(event == read_json(file("_event.json")), "source.event_join")
        require(sha(raw) == event["raw_sha256"], "source.response_sha")
        request = read_json(file("_http_request.body"))
        require(request["messages"] == expected, "source.message_identity")
        call = event["tool_call"]
        if call:
            require(call["output"] == read_json(file("_tool.json")), "source.actual_tool_output")
        if event["protocol_error"]:
            require(call is None and not event["final"], "source.error_was_not_execution")
            parsed = None
        else:
            parsed = strict_json(raw)
            if event["final"]:
                require(index == len(result["attempts"]) - 1, "source.first_Final_stops")
                require(parsed["final"] == result["final"], "source.original_Final")
            elif call:
                require(
                    parsed["tool"] == call["name"]
                    and parsed.get("arguments", {}) == call["arguments"],
                    "source.original_arguments",
                )
        binding = record(
            "open_interaction_binding",
            source_commit=BASELINE,
            population=row["arm"],
            task_key=row["task_key"],
            task_id=public["task_id"],
            source_document_id=public["id"],
            source_document_sha256=sha(public_path.read_bytes()),
            session_label=row["label"],
            session_result_id=result["id"],
            session_manifest_id=session_manifest["id"],
            source_closeout_id=row["id"],
            response_index=index,
            provider_response_id=outcome["provider_response_id"],
            request_sha256=sha(request_bytes),
            response_projection_sha256=sha(projection_bytes),
            raw_response_sha256=sha(raw),
            response_projection_is_not_original_HTTP=True,
            actual_tool_call_id=call["id"] if call else None,
            original_response_not_rewritten=True,
        )
        turns.append(
            {
                "binding": binding,
                "request_bytes": request_bytes,
                "projection_bytes": projection_bytes,
                "raw": raw,
                "input_messages": request["messages"],
                "event": event,
                "parsed": parsed,
                "prefix": prefix,
            }
        )
        expected.append({"role": "assistant", "content": raw.decode()})
        if event["protocol_error"]:
            expected.append(
                {
                    "role": "user",
                    "content": encode({"interface_error": event["protocol_error"]}).decode(),
                }
            )
        elif event["final"]:
            pass
        elif call:
            expected.append(
                {"role": "user", "content": encode({"tool_result": call["output"]}).decode()}
            )
        else:
            expected.append(
                {"role": "user", "content": encode({"receipt": "model_message_recorded"}).decode()}
            )
    require(expected == read_json(directory / "messages.json"), "source.complete_stored_history")
    require(len(turns) == result["model_requests"], "source.every_attempt_bound")
    return {
        "row": row,
        "result": result,
        "public": public,
        "turns": turns,
        "directory": directory,
        "session_manifest_id": session_manifest["id"],
    }


def load_population(root):
    parent = root / SOURCE
    manifests = {
        name: manifest(parent / name)["id"]
        for name in ("preparation", "online", "assessment", "closeout")
    }
    report = read_json(parent / "closeout/report.json")
    require(report["registered"] == 24, "source.fixed_population")
    require(report["by_condition"]["T"]["formula_driven_verified"] == 10, "source.fixed_T_validity")
    require(report["by_condition"]["A"]["formula_driven_verified"] == 2, "source.fixed_A_validity")
    require(len({r["label"] for r in report["rows"]}) == 24, "source.unique_sessions")
    sessions = {row["label"]: bind_session(root, row) for row in report["rows"]}
    valid = {
        label: session
        for label, session in sessions.items()
        if session["row"]["formula_driven_trace_verified"]
    }
    return report, manifests, sessions, valid


def positive_candidate(session, turn):
    row, event, binding = session["row"], turn["event"], turn["binding"]
    require(row["formula_driven_trace_verified"], "materialize.source_joint_valid_only")
    require(
        binding["session_label"] == row["label"]
        and binding["population"] == row["arm"]
        and binding["task_key"] == row["task_key"]
        and binding["source_closeout_id"] == row["id"]
        and binding["session_result_id"] == session["result"]["id"],
        "materialize.same_session_and_condition",
    )
    require(
        sha(turn["request_bytes"]) == binding["request_sha256"]
        and sha(turn["projection_bytes"]) == binding["response_projection_sha256"]
        and sha(turn["raw"]) == binding["raw_response_sha256"]
        and strict_json(turn["request_bytes"])["messages"] == turn["input_messages"],
        "materialize.same_interaction_bytes",
    )
    index = binding["response_index"]
    require(
        type(index) is int
        and 0 <= index < len(session["turns"])
        and event["response_index"] == index
        and event["raw_sha256"] == binding["raw_response_sha256"]
        and session["turns"][index]["binding"] == binding
        and session["turns"][index]["event"] == event
        and session["turns"][index]["request_bytes"] == turn["request_bytes"]
        and session["turns"][index]["raw"] == turn["raw"],
        "materialize.same_registered_turn",
    )
    require(
        event
        == next((e for e in session["result"]["events"] if e["response_index"] == index), None)
        and binding["actual_tool_call_id"]
        == (event["tool_call"]["id"] if event["tool_call"] else None),
        "materialize.original_qualification_event",
    )
    call = event["tool_call"]
    eligible = event["protocol_error"] is None and (
        event["final"]
        or (call is not None and call["name"] == "calculate" and call["output"]["status"] == "ok")
    )
    if not eligible:
        return None
    parsed = strict_json(turn["raw"])
    require(
        (event["final"] and parsed.get("final") == session["result"]["final"])
        or (
            not event["final"]
            and parsed.get("tool") == call["name"]
            and parsed.get("arguments", {}) == call["arguments"]
        ),
        "materialize.original_target_event_join",
    )
    return record(
        "open_original_candidate",
        population=row["arm"],
        task_key=row["task_key"],
        task_id=session["public"]["task_id"],
        session_label=row["label"],
        response_index=binding["response_index"],
        response_kind="Final" if event["final"] else "calculate",
        source_closeout_id=row["id"],
        interaction_binding_id=binding["id"],
        request_sha256=binding["request_sha256"],
        response_projection_sha256=binding["response_projection_sha256"],
        raw_response_sha256=binding["raw_response_sha256"],
        input_messages=turn["input_messages"],
        target_response=turn["raw"].decode(),
        original_system_preserved=True,
        target_only_original_public_model_content=True,
        offline_annotation_inserted_in_target=False,
        source_is_received_projection_not_original_HTTP=True,
        no_training_weight_assigned=True,
    )
