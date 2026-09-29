"""Bounded original8000 record/projection audit; no semantic qualification.

Read each original Episode once. Do not rescore, execute tools, open the wallet,
call a model, derive positive masks, or rewrite original history. Full durable
event and real-tokenizer roundtrip checks are limited to prospectively selected
first examples, not repeated across the whole historical archive.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

from .calibration import ROOT, now, publish
from .contracts import Episode, digest
from .encoding import _native_response, _student_messages
from .harness import episode_tool_specs, public_initial_messages
from .probe_collection import slot_directory
from .providers import _api_messages, canonical_assistant_message, tokenizer_binding
from .settlement import episode_is_complete
from .storage import encode, load_public_snapshot
from .v6_collection import STUDY, bound, require
from .v6_task import public_trajectory_view

PARENT = STUDY / "new_full_probe_v8_launch_01"
OUTPUT = STUDY / "process_review_v10_01/record_audit_01"
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/bb028b82-e470-4493-bbab-d859fd09c401/已粘贴的文本.txt"
)
CATEGORIES = (
    "direct_submission",
    "execute_then_submit",
    "error_then_changed_action_candidate",
    "normal_model_failure",
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_bound(path):
    raw = Path(path).read_bytes()
    value = json.loads(raw)
    require(
        value["id"] == digest({k: v for k, v in value.items() if k != "id"}),
        "bound input record changed",
    )
    return value, dict(path=str(Path(path).resolve()), sha256=sha(raw), id=value["id"])


def behavior_candidates(episode, q_native):
    """Observable event pattern only, never a financial-reasoning label."""
    events = episode.tool_events
    submitted = bool(events and events[-1].name == "submit_program" and not events[-1].is_error)
    changed = any(
        event.is_error
        and any(
            (later.name, later.raw_arguments) != (event.name, event.raw_arguments)
            for later in events[index + 1 :]
        )
        for index, event in enumerate(events)
    )
    return dict(
        direct_submission=submitted and len(events) == 1,
        execute_then_submit=submitted and any(e.name == "run_program" for e in events[:-1]),
        error_then_changed_action_candidate=changed,
        normal_model_failure=episode_is_complete(episode) and q_native is False,
    )


def inspect_episode(episode, task, slot, *, q_native, tokenizer=None, capture=False):
    """Compare actual saved fields, canonical request chain, view and rendered text."""
    issues, counts = [], Counter()
    checks = {
        "complete_settled_episode": episode_is_complete(episode),
        "registered_slot_task": episode.task_id == slot["task_id"],
        "actual_API_turn_count": episode.actual_model_calls
        == episode.provider_attempts
        == len(episode.turns),
        "initial_public_input_exact": list(episode.messages[:2])
        == public_initial_messages(task, episode.config),
        "request_history_chain_exact": True,
        "API_public_content_exact": True,
        "API_parsed_tool_calls_exact": True,
        "saved_action_event_links_exact": True,
        "final_program_matches_actual_submit": True,
        "public_view_exact": None,
        "Student_text_rendering_checked": tokenizer is not None,
        "Student_public_body_preserved": None if tokenizer is None else True,
        "Student_history_contents_present": None if tokenizer is None else True,
    }
    history = copy.deepcopy(list(episode.messages[:2]))
    event_index, by_turn, details = 0, {}, []
    requests = []
    for index, turn in enumerate(episode.turns):
        counts["turns"] += 1
        counts["public_content_nonempty_turns"] += bool(turn.raw_text.strip())
        counts["public_content_characters"] += len(turn.raw_text)
        metadata = turn.provider_metadata
        request, response = metadata.get("public_request"), metadata.get("api_response")
        counts["actual_request_objects_present"] += isinstance(request, dict)
        counts["raw_API_response_strings_present"] += isinstance(
            metadata.get("api_response_raw"), str
        )
        if not isinstance(request, dict) or not isinstance(response, dict):
            issues.append(
                dict(layer="record", turn=index, reason="missing_actual_request_or_response")
            )
            checks["request_history_chain_exact"] = False
            continue
        requests.append(request)
        checks["request_history_chain_exact"] &= (
            request.get("messages") == _api_messages(history)
            and request.get("tools") == episode_tool_specs(episode.config)
            and request.get("model") == "deepseek-flash"
            and request.get("thinking") == {"type": "disabled"}
        )
        choices = response.get("choices", [])
        message = choices[0].get("message", {}) if len(choices) == 1 else {}
        checks["API_public_content_exact"] &= (message.get("content") or "") == turn.raw_text
        counts["nonempty_separate_reasoning_content"] += bool(message.get("reasoning_content"))
        raw_calls = message.get("tool_calls") or []
        counts["raw_API_tool_call_entries"] += len(raw_calls) if isinstance(raw_calls, list) else 1
        counts["parsed_tool_calls"] += len(turn.tool_calls)
        unparsed = bool(raw_calls and not turn.tool_calls)
        counts["turns_with_unparsed_API_tool_calls"] += unparsed
        counts["unparsed_API_call_entries"] += (
            len(raw_calls) if unparsed and isinstance(raw_calls, list) else int(unparsed)
        )
        if turn.tool_calls:
            checks["API_parsed_tool_calls_exact"] &= (
                isinstance(raw_calls, list)
                and len(raw_calls) == len(turn.tool_calls)
                and all(
                    original.get("id") == call.call_id
                    and original.get("function", {}).get("name") == call.name
                    and original.get("function", {}).get("arguments") == call.raw_arguments
                    for original, call in zip(raw_calls, turn.tool_calls, strict=False)
                )
            )
        history.append(canonical_assistant_message(turn))
        actual_event = None
        if len(turn.tool_calls) == 1:
            if event_index >= len(episode.tool_events):
                checks["saved_action_event_links_exact"] = False
            else:
                call, actual_event = turn.tool_calls[0], episode.tool_events[event_index]
                checks["saved_action_event_links_exact"] &= (
                    call.call_id,
                    call.name,
                    call.raw_arguments,
                ) == (actual_event.call_id, actual_event.name, actual_event.raw_arguments)
                by_turn[index] = actual_event
                event_index += 1
                history.append(
                    dict(
                        role="tool", tool_call_id=call.call_id, content=actual_event.visible_output
                    )
                )
                counts["saved_tool_events"] += 1
                counts["saved_tool_errors"] += actual_event.is_error
                counts["observations_with_next_model_request"] += index + 1 < len(episode.turns)
                counts["terminal_observations_without_next_request"] += index + 1 == len(
                    episode.turns
                )
        elif index != len(episode.turns) - 1:
            checks["saved_action_event_links_exact"] = False
        rendered = None
        if tokenizer is not None:
            try:
                prompt = tokenizer.apply_chat_template(
                    _student_messages(request["messages"]),
                    tools=request["tools"],
                    tokenize=False,
                    add_generation_prompt=True,
                )
                rendered_response = _native_response(turn)
                checks["Student_public_body_preserved"] &= rendered_response.startswith(
                    turn.raw_text
                )
                content_messages = [
                    m
                    for m in request["messages"]
                    if isinstance(m.get("content"), str) and m["content"]
                ]
                checks["Student_history_contents_present"] &= all(
                    m["content"] in prompt for m in content_messages
                )
                counts["Student_text_rendered_turns"] += 1
                counts["Student_rendered_original_body_characters"] += len(turn.raw_text)
                counts["Student_rendered_parsed_tool_arguments"] += len(turn.tool_calls)
                counts["Student_unparsed_API_calls_not_in_structured_response"] += (
                    len(raw_calls) if unparsed and isinstance(raw_calls, list) else int(unparsed)
                )
                if capture:
                    rendered = dict(rendered_prompt=prompt, rendered_response=rendered_response)
            except (ValueError, TypeError, KeyError, AttributeError) as failure:
                issues.append(
                    dict(
                        layer="Student_text",
                        turn=index,
                        reason=type(failure).__name__,
                        detail=str(failure),
                    )
                )
                checks["Student_public_body_preserved"] = False
        if capture:
            details.append(
                dict(
                    turn_index=index,
                    original_API_response_raw=metadata.get("api_response_raw"),
                    original_API_public_content=turn.raw_text,
                    original_API_tool_calls=raw_calls,
                    parsed_tool_calls=[c.model_dump(mode="json") for c in turn.tool_calls],
                    actual_request=request,
                    actual_next_request=(
                        episode.turns[index + 1].provider_metadata.get("public_request")
                        if index + 1 < len(episode.turns)
                        else None
                    ),
                    actual_tool_event=actual_event.model_dump(mode="json")
                    if actual_event
                    else None,
                    Student_text=rendered,
                    unparsed_calls_are_raw_evidence_not_invented_actions=unparsed,
                )
            )
    checks["saved_action_event_links_exact"] &= event_index == len(episode.tool_events)
    checks["request_history_chain_exact"] &= history == list(episode.messages)
    if episode.stop_reason == "final_answer":
        submitted = episode.tool_events[-1] if episode.tool_events else None
        checks["final_program_matches_actual_submit"] = bool(
            submitted
            and submitted.name == "submit_program"
            and not submitted.is_error
            and submitted.raw_output.get("program") == episode.final_program
        )
    view = None
    try:
        view = public_trajectory_view(episode, slot_id=slot["slot_id"])
        docs = {row["segment_id"]: row for row in view["segments"]}
        content_ok = len(view["turns"]) == len(episode.turns) and all(
            docs[p["public_content_segment_id"]]["text"] == turn.raw_text
            for p, turn in zip(view["turns"], episode.turns, strict=True)
        )
        argument_ok = all(
            docs[action["arguments_segment_id"]]["text"] == call.raw_arguments
            for p, turn in zip(view["turns"], episode.turns, strict=True)
            for action, call in zip(p["actions"], turn.tool_calls, strict=True)
        )
        observation_ok = len(view["events"]) == len(episode.tool_events) and all(
            docs[p["observation_segment_id"]]["text"] == event.visible_output
            for p, event in zip(view["events"], episode.tool_events, strict=True)
        )
        unparsed_count = sum(s["kind"] == "unparsed_tool_call" for s in view["segments"])
        checks["public_view_exact"] = (
            content_ok
            and argument_ok
            and observation_ok
            and unparsed_count == counts["unparsed_API_call_entries"]
        )
        counts["view_public_content_segments"] = sum(
            s["kind"] == "public_content" for s in view["segments"]
        )
        counts["view_action_argument_segments"] = sum(
            s["kind"] == "action_arguments" for s in view["segments"]
        )
        counts["view_observation_segments"] = sum(
            s["kind"] == "tool_observation" for s in view["segments"]
        )
        counts["view_unparsed_call_segments"] = sum(
            s["kind"] == "unparsed_tool_call" for s in view["segments"]
        )
    except (ValueError, TypeError, KeyError, AttributeError) as failure:
        checks["public_view_exact"] = False
        issues.append(dict(layer="view", reason=type(failure).__name__, detail=str(failure)))
    for name, value in checks.items():
        if value is False and name != "Student_text_rendering_checked":
            issues.append(dict(layer="mechanical", reason=name))
    row = dict(
        slot=slot,
        Q_native_reused=q_native,
        stop_reason=episode.stop_reason,
        counts=dict(counts),
        checks=checks,
        issues=issues,
        case_candidates=behavior_candidates(episode, q_native),
        public_content_present=counts["public_content_nonempty_turns"] > 0,
        has_observation_fed_to_later_request=counts["observations_with_next_model_request"] > 0,
        has_saved_tool_error=counts["saved_tool_errors"] > 0,
        public_view_id=view["view_id"] if view else None,
        canonical_episode_sha256=view["episode_sha256"] if view else None,
        substantive_reasoning="not_measured",
        financial_process_correctness="not_measured",
        semantic_observation_update="not_measured",
        semantic_revision="not_measured",
        positive_mask=None,
        material_admission=False,
    )
    detail = (
        dict(
            task_id=episode.task_id,
            slot_id=slot["slot_id"],
            original_messages=list(episode.messages),
            original_final_program=episode.final_program,
            original_stop_reason=episode.stop_reason,
            original_tool_events=[e.model_dump(mode="json") for e in episode.tool_events],
            turns=details,
            public_view=view,
            no_rewritten_model_content=True,
            private_reference_loaded=False,
            semantic_quality_assessed=False,
        )
        if capture
        else None
    )
    return row, detail


def inspect_case_events(directory, episode):
    """Inspect only selected cases' original durable chronology, not all archive logs."""
    paths = sorted((Path(directory) / "events").glob("*/event.json"))
    saved = []
    for path in paths:
        raw = path.read_bytes()
        saved.append((json.loads(raw), dict(path=str(path), sha256=sha(raw))))
    issues, positions = [], {}
    for index, (event, _) in enumerate(saved):
        positions.setdefault((event["kind"], event["step"]), []).append(index)
    actual_events = iter(episode.tool_events)
    for step, turn in enumerate(episode.turns):
        actual_event = next(actual_events, None) if len(turn.tool_calls) == 1 else None
        intents = positions.get(("model_call_intent", step), [])
        returns = positions.get(("model_call_returned", step), [])
        if len(intents) != 1 or len(returns) != 1 or intents[0] >= returns[0]:
            issues.append(f"model_intent_return_order:{step}")
            continue
        intent, response = saved[intents[0]][0]["payload"], saved[returns[0]][0]["payload"]
        if _api_messages(intent["messages"]) != turn.provider_metadata["public_request"][
            "messages"
        ] or response != turn.model_dump(mode="json"):
            issues.append(f"model_original_payload:{step}")
        if len(turn.tool_calls) == 1:
            ti = positions.get(("tool_call_intent", step), [])
            tr = positions.get(("tool_call_returned", step), [])
            if len(ti) != 1 or len(tr) != 1 or not returns[0] < ti[0] < tr[0]:
                issues.append(f"actual_tool_order:{step}")
            else:
                intended = saved[ti[0]][0]["payload"]
                observed = saved[tr[0]][0]["payload"]
                if (
                    actual_event is None
                    or observed != actual_event.model_dump(mode="json")
                    or any(
                        intended.get(k) != v
                        for k, v in turn.tool_calls[0].model_dump(mode="json").items()
                    )
                ):
                    issues.append(f"original_tool_intent_observation:{step}")
                following = positions.get(("model_call_intent", step + 1), [])
                if step + 1 < len(episode.turns) and (not following or tr[0] >= following[0]):
                    issues.append(f"observation_before_next_request:{step}")
    if (
        not saved
        or saved[-1][0]["kind"] != "episode_completed"
        or saved[-1][0]["payload"] != episode.model_dump(mode="json")
    ):
        issues.append("final_durable_episode_payload")
    return dict(
        checked=True,
        original_event_files=len(saved),
        chronological_order_exact=not issues,
        issues=issues,
        events=[
            dict(sequence=i, kind=e["kind"], step=e["step"], **ref)
            for i, (e, ref) in enumerate(saved)
        ],
        order_not_claim_of_faithful_hidden_reasoning=True,
    )


def case_token_roundtrip(detail, tokenizer):
    if tokenizer is None:
        return dict(checked=False, reason="local_tokenizer_unavailable")
    rows = []
    for turn in detail["turns"]:
        rendered = turn["Student_text"]
        if rendered is None:
            rows.append(dict(turn_index=turn["turn_index"], checked=False))
            continue
        text = rendered["rendered_prompt"] + rendered["rendered_response"]
        ids = tokenizer(text, add_special_tokens=False, truncation=False, padding=False)[
            "input_ids"
        ]
        rows.append(
            dict(
                turn_index=turn["turn_index"],
                checked=True,
                decode_exact=tokenizer.decode(
                    ids, skip_special_tokens=False, clean_up_tokenization_spaces=False
                )
                == text,
                sequence_tokens_before_Student_EOS=len(ids),
                sequence_tokens_with_one_Student_EOS=len(ids) + 1,
                exceeds_registered24576=len(ids) + 1 > 24576,
                input_ids_without_appended_EOS=ids,
                Student_EOS_id=tokenizer.eos_token_id,
                target_positions=None,
                API_sampling_receipt=False,
            )
        )
    return dict(checked=True, rows=rows, context_truncated=False, supervision_decided=False)


def run(parent=PARENT, output=OUTPUT, *, workers=8):
    parent, output = Path(parent), Path(output)
    require(not output.exists(), "new immutable audit directory required; no overwrite/relabel")
    require(type(workers) is int and 1 <= workers <= 16, "bounded CPU worker count1..16")
    protocol, protocol_ref = read_bound(parent / "registration/protocol.json")
    seal, seal_ref = read_bound(parent / "generation_seal/record.json")
    native, native_ref = read_bound(parent / "native_support/record.json")
    slots = protocol["slots"]
    require(
        len(slots) == len({s["slot_id"] for s in slots}) == 8000
        and len(protocol["task_ids"]) == 1000
        and seal["protocol_id"] == native["protocol_id"] == protocol["id"]
        and native["generation_seal_id"] == seal["id"]
        and [r["slot"] for r in seal["slots"]] == slots
        and [r["slot"] for r in native["rows"]] == slots,
        "full original fixed1000x8 parent/seal/native roster required",
    )
    source_dir = Path(__file__).parent
    sources = {
        name: sha((source_dir / name).read_bytes())
        for name in (
            "v10_record_audit.py",
            "v6_task.py",
            "encoding.py",
            "v6_encoding.py",
            "providers.py",
            "harness.py",
            "profiles.py",
            "contracts.py",
            "storage.py",
        )
    }
    registration = bound(
        dict(
            schema="v10_record_audit_registration.v1",
            at=now(),
            parent_protocol=protocol_ref,
            parent_generation_seal=seal_ref,
            reused_native_record=native_ref,
            original_tasks=1000,
            original_slots=8000,
            slot_order_sha256=digest(slots),
            source_commit=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            source_bindings=sources,
            audit_attachment_sha256=sha(AUDIT.read_bytes()),
            case_order="first matching protocol.slots ordinal; no success/richness preference",
            case_rules={
                "direct_submission": "only one actual successful submit_program event",
                "execute_then_submit": "run_program before successful submit_program",
                "error_then_changed_action_candidate": (
                    "error followed by different name/raw_arguments; NOT semantic revision"
                ),
                "normal_model_failure": "complete settled episode; reused Q_native=False",
            },
            cases_may_overlap=True,
            maximum_distinct_cases=4,
            full_population_scope="original records, request chain, view, Student text",
            selected_cases_only="durable event file sequence and real Student token roundtrip",
            semantic_substance_not_measured=True,
            label_or_length_not_semantic_proxy=True,
            tools_reexecuted=False,
            native_rescored=False,
            models_called=0,
            GPU_used=False,
            wallet_opened=False,
            original_files_modified=False,
            workers=workers,
        )
    )
    publish(output / "registration", registration)
    manifest, public, _ = load_public_snapshot(protocol["snapshot"])
    require(manifest["id"] == protocol["snapshot_id"], "original public snapshot differs")
    tasks = {
        t.task_id: t
        for t in public
        if t.dataset == "finqa" and t.task_id in set(protocol["task_ids"])
    }
    require(set(tasks) == set(protocol["task_ids"]), "original public1000 required")
    tokenizer, tokenizer_info = None, {}
    try:
        from .v6_review_revision import original_protocol
        from .v7_base_evaluation import load_tokenizer

        tokenizer = load_tokenizer(original_protocol()["assets"])
        codec, template = tokenizer_binding(tokenizer)
        tokenizer_info = dict(
            available=True,
            tokenizer_digest=codec,
            chat_template_digest=template,
            local_files_only=True,
            model_weights_loaded=False,
        )
    except (OSError, ValueError, ImportError) as failure:
        tokenizer_info = dict(
            available=False,
            reason=type(failure).__name__,
            detail=str(failure),
            local_files_only=True,
            download_attempted=False,
        )
    rows, selected, case_bodies = [], {}, {}
    start = time.monotonic()

    def one(index, wanted):
        slot, expected, scored = slots[index], seal["slots"][index], native["rows"][index]
        directory = slot_directory(parent, slot)
        path = directory / "episode/episode.json"
        try:
            raw = path.read_bytes()
            file_sha = sha(raw)  # Exactly one original file read/hash in this population pass.
            episode = Episode.model_validate_json(raw)
            capture = any(
                v and k in wanted
                for k, v in behavior_candidates(episode, scored["Q_native"]).items()
            )
            row, detail = inspect_episode(
                episode,
                tasks[slot["task_id"]],
                slot,
                q_native=scored["Q_native"],
                tokenizer=tokenizer,
                capture=capture,
            )
            byte_bound = file_sha == expected["episode_file_sha256"]
            row["checks"]["original_episode_byte_binding"] = byte_bound
            row["checks"]["registered_episode_config"] = (
                episode.config.model_dump(mode="json")
                == protocol["configs_by_task"][slot["task_id"]]
            )
            row["checks"]["canonical_episode_binding"] = (
                row["canonical_episode_sha256"] == expected["episode_sha256"]
                if row["canonical_episode_sha256"] is not None
                else None
            )
            if not byte_bound:
                row["issues"].append(dict(layer="record", reason="original_episode_byte_binding"))
            for check in ("registered_episode_config", "canonical_episode_binding"):
                if row["checks"][check] is False:
                    row["issues"].append(dict(layer="record", reason=check))
            row.update(
                original_ordinal=index,
                original_episode=dict(path=str(path), sha256=file_sha),
                existing_native_status=scored["native"]["status"],
            )
            if detail is not None:
                detail.update(
                    original_episode=row["original_episode"], Q_native_reused=scored["Q_native"]
                )
            return row, detail, episode if capture else None, directory
        except Exception as failure:
            return (
                dict(
                    original_ordinal=index,
                    slot=slot,
                    Q_native_reused=scored["Q_native"],
                    counts={},
                    checks={},
                    issues=[
                        dict(
                            layer="record_load", reason=type(failure).__name__, detail=str(failure)
                        )
                    ],
                    case_candidates={},
                    substantive_reasoning="not_measured",
                    material_admission=False,
                ),
                None,
                None,
                directory,
            )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for offset in range(0, 8000, 32):
            wanted = set(CATEGORIES) - set(selected)
            for row, detail, episode, directory in executor.map(
                lambda i, wanted=wanted: one(i, wanted), range(offset, min(offset + 32, 8000))
            ):
                rows.append(row)
                picks = [
                    c for c in CATEGORIES if c not in selected and row["case_candidates"].get(c)
                ]
                if picks:
                    name = f"original_{row['original_ordinal']:04d}"
                    for category in picks:
                        selected[category] = name
                    require(
                        detail is not None and episode is not None,
                        "selected original detail missing",
                    )
                    detail.update(
                        original_ordinal=row["original_ordinal"],
                        selected_categories=picks,
                        durable_events=inspect_case_events(directory, episode),
                        Student_token_roundtrip=case_token_roundtrip(detail, tokenizer),
                        mechanical_row=row,
                    )
                    case_bodies[name] = detail
            if offset % 256 == 0 or len(rows) == 8000:
                print(
                    json.dumps(
                        dict(
                            processed=len(rows),
                            denominator=8000,
                            elapsed_seconds=round(time.monotonic() - start, 2),
                            selected_cases=selected,
                        )
                    ),
                    flush=True,
                )
    totals, check_totals, issues, candidates, stops = Counter(), {}, Counter(), Counter(), Counter()
    for row in rows:
        totals.update(row["counts"])
        for name, value in row["checks"].items():
            counts = check_totals.setdefault(name, Counter())
            counts["not_checked" if value is None else "passed" if value else "failed"] += 1
        for issue in row["issues"]:
            issues[issue["layer"] + ":" + issue["reason"]] += 1
        candidates.update({k: int(v) for k, v in row["case_candidates"].items()})
        stops[row.get("stop_reason", "record_unreadable")] += 1
    report = bound(
        dict(
            schema="v10_original8000_record_audit.v1",
            at=now(),
            registration_id=registration["id"],
            original_tasks=1000,
            denominator=8000,
            processed_originals=len(rows),
            original_files_read_once_in_full_pass=True,
            totals=dict(totals),
            episodes_with_nonempty_public_content=sum(
                r.get("public_content_present", False) for r in rows
            ),
            episodes_with_later_observation_input=sum(
                r.get("has_observation_fed_to_later_request", False) for r in rows
            ),
            episodes_with_saved_tool_error=sum(r.get("has_saved_tool_error", False) for r in rows),
            check_totals={k: dict(v) for k, v in check_totals.items()},
            issue_counts=dict(issues),
            episodes_with_mechanical_issues=sum(bool(r["issues"]) for r in rows),
            stop_reason_counts=dict(stops),
            existing_native_counts=dict(Counter(str(r["Q_native_reused"]) for r in rows)),
            candidate_pattern_counts=dict(candidates),
            cases={
                c: dict(
                    status="selected" if c in selected else "not_observed",
                    artifact=f"cases/{selected[c]}/record.json" if c in selected else None,
                )
                for c in CATEGORIES
            },
            distinct_cases=len(case_bodies),
            tokenizer=tokenizer_info,
            selected_case_durable_event_checks=len(case_bodies),
            full_archive_durable_event_scan_performed=False,
            full_population_token_roundtrip_performed=False,
            actual_sampling_tokens_or_hidden_reasoning_claimed=False,
            financial_process_correctness="not_measured",
            task_relevant_substantive_reasoning="not_measured",
            semantic_observation_updates="not_measured",
            semantic_error_revision="not_measured",
            positive_supervision_masks_generated=False,
            material_admission=False,
            native_rescored=False,
            tools_reexecuted=False,
            models_called=0,
            GPU_used=False,
            wallet_opened=False,
            elapsed_seconds=round(time.monotonic() - start, 2),
        )
    )
    members = {
        "report.json": encode(report),
        "rows.jsonl": b"".join(
            (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode() for row in rows
        ),
        "audit_source.py": Path(__file__).read_bytes(),
    }
    for name, detail in case_bodies.items():
        members[f"cases/{name}/record.json"] = encode(bound(detail))
    write_immutable_artifact_directory(output / "results", members)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, default=PARENT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    result = run(args.parent, args.output, workers=args.workers)
    print(
        json.dumps(
            dict(
                id=result["id"],
                processed=result["processed_originals"],
                mechanical_issue_episodes=result["episodes_with_mechanical_issues"],
            )
        )
    )


if __name__ == "__main__":
    main()
