"""Read-only, same-interaction source joins for the two explicitly separate batches."""

from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.model_contract import (
    response_model_matches,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.source import (
    _event_target,
    content_identity,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    request_body,
    strict_json,
)

from .plan import (
    LABELS,
    MODEL,
    OLD,
    OLD_LABELS,
    OUTPUT,
    SYSTEM,
    encode,
    read_json,
    record,
    require,
    sha,
)


def batch_path(label):
    require(label in (*OLD_LABELS, *LABELS), "source.registered_candidate_only")
    return OLD if label in OLD_LABELS else OUTPUT


def bind(root, row):
    """Bind available admitted events; this alone does not certify a positive package."""
    root = Path(root)
    label = row["label"]
    base = root / batch_path(label)
    directory = base / "online/sessions" / label
    public = read_json(base / "preparation/public/X2.json")
    result_path = directory / "result.json"
    result_raw = result_path.read_bytes() if result_path.exists() else None
    result = strict_json(result_raw) if result_raw is not None else None
    sealed = manifest(directory) if (directory / "manifest.json").exists() else None
    if result is not None:
        content_identity(result, "source.content_identity")
        require(sealed and sealed["result_id"] == result["id"], "source.worker_manifest_result")
        require(
            result["origin"] == "live_http"
            and result["requested_model"] == MODEL
            and result["source_document_sha256"] == sha(encode(public))
            and result["first_final_stops"]
            and not result["history_truncated"]
            and not result["online_answer_feedback"]
            and not result["hidden_evaluator_loaded"],
            "source.frozen_public_only_condition",
        )
    expected = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": encode({"task": public}).decode()},
    ]
    turns = []
    tool_count = 0
    for index, path in enumerate(sorted((directory / "turns").glob("*_event.json"))):
        require(path.name == f"{index:03d}_event.json", "source.contiguous_events")
        prefix = directory / f"turns/{index:03d}"

        def file(suffix, prefix=prefix):
            return prefix.with_name(prefix.name + suffix)

        event_bytes = path.read_bytes()
        event = strict_json(event_bytes)
        raw = file("_assistant.raw").read_bytes()
        request = file("_http_request.body").read_bytes()
        reservation = read_json(file("_reservation.json"))
        outcome = read_json(file("_outcome.json"))
        projection_raw = file("_response_projection.json").read_bytes()
        projection = strict_json(projection_raw)
        content_identity(reservation, "source.reservation_identity")
        require(
            event["response_index"] == index
            and event["raw_sha256"] == sha(raw)
            and not event["oracle_feedback"]
            and request == encode(request_body(expected, MODEL))
            and sha(request) == reservation["request_sha256"] == outcome["request_sha256"]
            and len(request) == reservation["request_bytes"]
            and reservation["index"] == index
            and reservation["provider_call"]
            and reservation["requested_model"] == MODEL
            and reservation["prefix_messages"] == len(expected)
            and outcome["reservation_id"] == reservation["id"]
            and sha(projection_raw) == outcome["response_projection_sha256"]
            and outcome["origin"] == "live_http"
            and outcome["http_status"] == 200
            and outcome["error"] is None
            and outcome["public_content_returned"]
            and projection["is_original_http_response"] is False
            and projection["parse_error"] is None
            and projection["id"] == outcome["provider_response_id"]
            and projection["model"] == outcome["model"]
            and response_model_matches(MODEL, outcome["model"])
            and projection["usage"] == outcome["usage"]
            and len(projection["choices"]) == 1,
            "source.actual_public_request_response_join",
        )
        choice = projection["choices"][0]
        message = choice["message"]
        require(
            choice["index"] == 0
            and choice["finish_reason"] == outcome["finish_reason"] == "stop"
            and message["role"] == "assistant"
            and not message["native_tool_calls_present"]
            and "reasoning_content" not in message
            and message["content"].encode() == raw,
            "source.exact_admitted_public_content",
        )
        if result is not None:
            require(
                result["events"][index] == event and result["attempts"][index] == outcome,
                "source.result_event_outcome_join",
            )
        final = (
            result["final"]
            if result is not None
            else (strict_json(raw).get("final") if event["final"] else None)
        )
        parsed = _event_target(event, raw, final)
        call = event["tool_call"]
        if call:
            tool_count += 1
            require(
                call["id"] == f"tool:{tool_count}"
                and call["output"] == read_json(file("_tool.json")),
                "source.actual_ordered_tool_record",
            )
        binding = record(
            "DR_original_interaction",
            session_label=label,
            population="E",
            task_key="X2",
            response_index=index,
            source_document_id=public["id"],
            source_closeout_id=row["id"],
            request_sha256=sha(request),
            raw_response_sha256=sha(raw),
            response_projection_sha256=sha(projection_raw),
            event_sha256=sha(event_bytes),
            source_batch="historical_8" if label in OLD_LABELS else "new_32",
            original_qualification_not_overwritten=True,
        )
        turns.append(
            {
                "binding": binding,
                "event": event,
                "raw": raw,
                "request_bytes": request,
                "projection_bytes": projection_raw,
                "event_bytes": event_bytes,
                "input_messages": strict_json(request)["messages"],
                "parsed": parsed,
                "prefix": prefix,
            }
        )
        expected.append({"role": "assistant", "content": raw.decode()})
        if event["final"]:
            require(
                result is not None and index == len(result["events"]) - 1,
                "source.actual_terminal_Final",
            )
            break
        if event["protocol_error"] is not None:
            feedback = {"interface_error": event["protocol_error"]}
        elif call:
            feedback = {"tool_result": call["output"]}
        else:
            feedback = {"receipt": "model_message_recorded"}
        expected.append({"role": "user", "content": encode(feedback).decode()})
    if result is not None:
        require(
            expected == read_json(directory / "messages.json"), "source.entire_admitted_history"
        )
        require(tool_count == result["tool_calls"], "source.all_actual_tools")
    return {
        "row": row,
        "result": result,
        "result_bytes": result_raw,
        "public": public,
        "turns": turns,
        "directory": directory,
        "session_manifest_id": sealed["id"] if sealed else None,
    }


def candidates(session):
    row, result = session["row"], session["result"]
    require(
        row["formula_driven_trace_verified"] and result is not None,
        "candidate.complete_qualified_session",
    )
    require(
        result["terminal"] == "model_final" and session["turns"][-1]["event"]["final"],
        "candidate.real_first_Final",
    )
    require(
        len(session["turns"]) == len(result["attempts"]) == result["provider_attempts"],
        "candidate.all_original_attempts",
    )
    positives, excluded = [], []
    for turn in session["turns"]:
        event, binding = turn["event"], turn["binding"]
        call = event["tool_call"]
        if event["protocol_error"] is not None or (call and call["output"]["status"] != "ok"):
            excluded.append(
                {
                    "response_index": event["response_index"],
                    "raw_sha256": sha(turn["raw"]),
                    "reason": "original_failed_request_only_kept_in_history",
                }
            )
            continue
        kind = "Final" if event["final"] else call["name"] if call else "message"
        require(
            kind in {"message", "calculate", "read_source", "notebook", "Final"},
            "candidate.legal_original_kind",
        )
        candidate = record(
            "DR_original_positive_candidate",
            population="E",
            task_key="X2",
            task_id=session["public"]["task_id"],
            session_label=row["label"],
            response_index=event["response_index"],
            response_kind=kind,
            source_closeout_id=row["id"],
            interaction_binding_id=binding["id"],
            **{
                k: binding[k]
                for k in ("request_sha256", "response_projection_sha256", "raw_response_sha256")
            },
            input_messages=turn["input_messages"],
            target_response=turn["raw"].decode(),
            original_system_preserved=True,
            target_only_original_public_model_content=True,
            original_json_errors_retained_in_subsequent_history=True,
            source_is_received_projection_not_original_HTTP=True,
            offline_annotation_inserted_in_target=False,
            no_training_weight_assigned=True,
        )
        positives.append((candidate, turn["raw"]))
    require(
        positives and positives[-1][0]["response_kind"] == "Final",
        "candidate.complete_positive_package",
    )
    return positives, excluded
