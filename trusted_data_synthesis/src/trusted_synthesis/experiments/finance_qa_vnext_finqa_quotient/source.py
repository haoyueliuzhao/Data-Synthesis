"""Read existing verdicts and bind actual HTTP bytes; never replay a Runtime."""

import hashlib
import json

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require

from .rules import PARENT, VALID


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def snapshot(directory):
    rows = []
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            require(not path.is_symlink(), "source.no_symlinks")
            data = path.read_bytes()
            rows.append(
                {
                    "path": path.relative_to(directory).as_posix(),
                    "bytes": len(data),
                    "sha256": sha(data),
                }
            )
    return record("finqa_existing_source_snapshot", parent=PARENT, members=rows)


def population(root):
    parent = root / PARENT
    registrations = read(parent / "preparation/registrations.json")
    summary = read(parent / "online/summary.json")
    report = read(parent / "closeout/report.json")
    require(len(registrations) == len(summary["sessions"]) == 8, "source.eight_registrations")
    by_label = {r["label"]: r for r in summary["sessions"]}
    require(len(by_label) == 8, "source.unique_labels")
    rows = []
    for reg in registrations:
        directory = parent / "online/sessions" / reg["label"]
        audit = read(directory / "audit.json")
        require(audit == by_label[reg["label"]], "source.saved_audit_summary")
        require(read(directory / "registration.json") == reg, "source.registration")
        require(
            audit["view_condition"] == reg["view_condition"]
            and audit["task_key"] == reg["task_key"],
            "source.condition",
        )
        rows.append(
            {
                "label": reg["label"],
                "registration": reg,
                "audit_id": audit["id"],
                "complete_valid": audit["complete_valid"],
                "status": audit["status"],
                "submissions": audit["submissions"],
                "provider_attempts": audit["provider_attempts"],
                "view_condition": reg["view_condition"],
                "task_key": reg["task_key"],
                "source_directory": directory.relative_to(root).as_posix(),
                "success_distribution_eligible": audit["complete_valid"],
                "failure_promoted": False,
            }
        )
    require({r["label"] for r in rows if r["complete_valid"]} == set(VALID), "source.valid_set")
    require(sum(r["submissions"] for r in rows) == 212, "source.original_denominator")
    require(report["registered_sessions"] == 8, "source.closeout_population")
    return record(
        "finqa_existing_population",
        rows=rows,
        summary_id=summary["id"],
        closeout_id=report["id"],
        original_task_weights={"V0": {"E1": "1/2", "J2": "1/2"}, "V1": {"E1": "1/2", "J2": "1/2"}},
        original_all_submissions=212,
        new_submissions=0,
        qualifications_recomputed=0,
    )


def bind_turn(directory, index, registration):
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
        outcome["transport_kind"] == "live_http"
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
    require(json.loads(raw) == event["model_submission"], "materialize.no_rewriting")
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


def load_session(root, row):
    directory = root / row["source_directory"]
    require(row["complete_valid"] and row["label"] in VALID, "materialize.success_only")
    audit = read(directory / "audit.json")
    require(
        audit["model_origin_verified"]
        and audit["transition_replay_verified"]
        and audit["independent_arithmetic_verified"],
        "source.existing_validity_authority",
    )
    paths = sorted((directory / "runtime/turns").glob("*_transition.json"))
    require(
        len(paths) == row["submissions"] == row["provider_attempts"], "source.complete_turn_set"
    )
    turns = [bind_turn(directory, i, row["registration"]) for i in range(len(paths))]
    require(
        turns[-1]["event"]["terminal"]
        and turns[-1]["event"]["admitted"]
        and turns[-1]["event"]["model_submission"]["kind"] == "final",
        "source.original_terminal",
    )
    return {"row": row, "audit": audit, "turns": turns}


def candidate(session, turn):
    require(turn["event"]["admitted"], "materialize.admitted_only")
    row, request, event = session["row"], turn["request"], turn["event"]
    return record(
        "finqa_original_candidate",
        label=row["label"],
        task_id=request["context"]["task_id"],
        session_id=row["registration"]["id"],
        task_key="J2",
        view_condition=row["view_condition"],
        generation_registration_id=row["registration"]["id"],
        protocol_id=request["protocol_id"],
        qualification_id=session["audit"]["id"],
        public_runtime_state_id=request["state"]["id"],
        public_request_id=request["id"],
        interaction_id=turn["binding"]["id"],
        transition_id=event["id"],
        submission=event["submission_count"],
        submission_kind=event["model_submission"]["kind"],
        disposition=event["model_submission"].get("disposition"),
        actual_http_body_sha256=sha(turn["contents"]["http_request"]),
        actual_http_body=turn["http"],
        messages=turn["http"]["messages"],
        target_text=turn["raw"].decode(),
        target_raw_sha256=sha(turn["raw"]),
        admitted=True,
        complete_session_valid=True,
        host_display_is_target=False,
        raw_trace_keeps_unadmitted=True,
        class_weights_assigned=False,
    )
