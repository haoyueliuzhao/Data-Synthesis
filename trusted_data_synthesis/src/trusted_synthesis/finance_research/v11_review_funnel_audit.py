"""Read-only V10 final A/B funnel diagnosis, never new qualification or replayed API.

Final terminals are selected exclusively by the sealed logical matrix, including
the previously authorized attempt2 replacements. No wallet is opened. Raw model
claims, machine annotation success and the saved process verdict stay distinct.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pydantic

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

from .contracts import digest, invocation_identity
from .qwen_protocol import strict_json_decoder
from .v10_process_review import CriticalProcess, ProcessReviewOutput
from .v10_review_protocol import BOutput, review_policy_definition

PAIR_COUNT = 5719
SIDE_COUNT = 11438
ORIGINAL_SLOT_COUNT = 8000
CATEGORIES = ("valid", "invalid", "unknown", "annotation_failed")
DIMENSIONS = (
    "evidence_and_operations",
    "observation_interpretation",
    "unwithdrawn_critical_contradictions",
    "actual_revisions",
)
STATUSES = {"supported", "critical_error", "unknown", "not_applicable"}
VALIDATOR_FILES = (
    "v10_process_review.py",
    "v10_review_protocol.py",
    "contracts.py",
    "qwen_protocol.py",
)
DEFAULT_FROZEN = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/.codex-worktrees/finqa-v10-proxy-frozen-20260930"
)
_STATE = None


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def bound(value):
    return {**value, "id": digest(value)}


def check_bound(value, schema=None):
    require(
        isinstance(value, dict)
        and value.get("id") == digest({k: v for k, v in value.items() if k != "id"})
        and (schema is None or value.get("schema") == schema),
        "audit input content identity/schema mismatch",
    )
    return value


def read_record(path, *, ref=None, expected_path=None, root=None, schema=None):
    path = Path(path).resolve()
    require(
        expected_path is None or path == Path(expected_path).resolve(), "redirected audit artifact"
    )
    require(root is None or Path(root).resolve() in path.parents, "artifact escaped original root")
    raw = path.read_bytes()
    value = check_bound(strict_json_decoder().decode(raw.decode()), schema)
    if ref is not None:
        require(
            ref["sha256"] == sha_bytes(raw) and ref["id"] == value["id"],
            "sealed artifact byte SHA/content identity mismatch",
        )
    return value, dict(path=str(path), id=value["id"], sha256=sha_bytes(raw))


def read_ref(ref, **kwargs):
    return read_record(ref["path"], ref=ref, **kwargs)[0]


def _raw_statuses(value):
    process = value.get("process") if isinstance(value, dict) else None
    return {
        name: process[name].get("status")
        if isinstance(process, dict) and isinstance(process.get(name), dict)
        else None
        for name in DIMENSIONS
    }


def raw_status_claim(statuses):
    if any(type(v) is not str or v not in STATUSES for v in statuses.values()):
        return "incomplete_or_invalid_statuses"
    if any(statuses[k] == "not_applicable" for k in (DIMENSIONS[0], DIMENSIONS[2])):
        return "inadmissible_critical_NA"
    if "critical_error" in statuses.values():
        return "invalid"
    if "unknown" in statuses.values():
        return "unknown"
    return "valid"


def locator_diagnostic(location, documents, *, context, path, dimension=None, decision=None):
    """Classify exact text only inside the explicitly referenced segment; no repair."""
    if not isinstance(location, dict):
        location = {}
    sid, start, end, quote = (location.get(k) for k in ("segment_id", "start", "end", "quote"))
    doc = documents.get(sid) if isinstance(sid, str) else None
    detail = dict(
        context=context,
        path=path,
        process_dimension=dimension,
        supervision_decision=decision,
        segment_id=sid,
        start=start,
        end=end,
        quote_sha256=sha_bytes(quote.encode()) if isinstance(quote, str) else None,
        quote_characters=len(quote) if isinstance(quote, str) else None,
        quote_preview=quote[:160] if isinstance(quote, str) else None,
        segment_kind=doc.get("kind") if doc else None,
    )
    if doc is None:
        return {**detail, "problem": "missing_segment", "exact_quote_occurrences": None}
    text = doc["text"]
    detail["segment_characters"] = len(text)
    valid_types = type(start) is int and type(end) is int and isinstance(quote, str)
    if valid_types and 0 <= start < end <= len(text) and text[start:end] == quote:
        return None
    offsets = []
    occurrences = 0
    if isinstance(quote, str) and quote:
        position = text.find(quote)
        while position >= 0:
            occurrences += 1
            if len(offsets) < 2:
                offsets.append([position, position + len(quote)])
            position = text.find(quote, position + 1)
    problem = (
        "malformed_locator_fields"
        if not valid_types
        else "quote_absent_from_referenced_segment"
        if occurrences == 0
        else "unique_exact_quote_wrong_offsets"
        if occurrences == 1
        else "multiple_exact_quotes_unresolved_offsets"
    )
    return {
        **detail,
        "problem": problem,
        "exact_quote_occurrences": occurrences,
        "first_two_exact_occurrence_spans": offsets,
        "original_slice_preview": text[start:end][:160]
        if type(start) is int and type(end) is int
        else None,
        "not_a_semantic_verdict_or_normalized_locator": True,
    }


def _locations(value):
    if not isinstance(value, dict):
        return
    process = value.get("process")
    if isinstance(process, dict):
        for name in DIMENSIONS:
            assessment = process.get(name)
            if isinstance(assessment, dict) and isinstance(assessment.get("evidence"), list):
                for index, location in enumerate(assessment["evidence"]):
                    yield (
                        location,
                        dict(
                            context="critical_process",
                            path=f"process.{name}.evidence[{index}]",
                            dimension=name,
                            decision=None,
                        ),
                        assessment.get("status"),
                    )
    behavior = value.get("behavior")
    if isinstance(behavior, dict) and isinstance(behavior.get("evidence"), list):
        for index, location in enumerate(behavior["evidence"]):
            yield location, dict(context="behavior", path=f"behavior.evidence[{index}]"), None
    if isinstance(value.get("supervision"), list):
        for index, location in enumerate(value["supervision"]):
            yield (
                location,
                dict(
                    context="supervision",
                    path=f"supervision[{index}]",
                    decision=location.get("decision") if isinstance(location, dict) else None,
                ),
                None,
            )


def _process_failure(checks, docs, role):
    for name in DIMENSIONS:
        item = checks[name]
        if name in (DIMENSIONS[0], DIMENSIONS[2]) and item["status"] == "not_applicable":
            return dict(stage="process", path=f"process.{name}", reason="critical_dimension_NA")
        needs = (
            item["status"] == "critical_error"
            or name == DIMENSIONS[0]
            and item["status"] == "supported"
        )
        if needs and not item["evidence"]:
            return dict(
                stage="process", path=f"process.{name}", reason="required_critical_evidence_absent"
            )
        for i, location in enumerate(item["evidence"]):
            path = f"process.{name}.evidence[{i}]"
            issue = locator_diagnostic(
                location, docs, context="critical_process", path=path, dimension=name
            )
            if issue:
                return dict(stage="process", path=path, reason=issue["problem"])
    return None


def first_failure(raw, view, role, *, normal=True):
    """Replay only the frozen local annotation order; never generate a new label."""
    docs = {d["segment_id"]: d for d in view["segments"]}
    if not normal:
        return dict(
            stage="JSON", path="$", reason="non_normal_envelope_passed_empty_string_to_inspector"
        )
    try:
        value = strict_json_decoder().decode(raw)
    except (ValueError, TypeError) as exc:
        return dict(stage="JSON", path="$", reason=type(exc).__name__ + ": " + str(exc))
    try:
        value = (
            (ProcessReviewOutput if role == "A" else BOutput)
            .model_validate(value)
            .model_dump(mode="json")
        )
    except (ValueError, TypeError) as exc:
        paths = (
            [list(e["loc"]) for e in exc.errors(include_url=False)]
            if isinstance(exc, pydantic.ValidationError)
            else []
        )
        return dict(
            stage="schema",
            path=paths[0] if paths else "$",
            schema_error_paths=paths,
            reason=type(exc).__name__ + ": " + str(exc),
        )
    failed = _process_failure(value["process"], docs, role)
    if failed or role == "B":
        return failed
    for i, location in enumerate(value["behavior"]["evidence"]):
        path = f"behavior.evidence[{i}]"
        issue = locator_diagnostic(location, docs, context="behavior", path=path)
        if issue:
            return dict(stage="behavior", path=path, reason=issue["problem"])
    actions = {a["arguments_segment_id"]: a for t in view["turns"] for a in t["actions"]}
    events = {e["event_id"]: e for e in view["events"]}
    intervals = defaultdict(list)
    for i, location in enumerate(value["supervision"]):
        path = f"supervision[{i}]"
        issue = locator_diagnostic(
            location, docs, context="supervision", path=path, decision=location["decision"]
        )
        if issue:
            return dict(stage="supervision", path=path, reason=issue["problem"])
        doc = docs[location["segment_id"]]
        if doc["kind"] not in {"public_content", "action_arguments"}:
            return dict(stage="supervision", path=path, reason="source_or_observation_input_only")
        for start, end in intervals[location["segment_id"]]:
            if not (location["end"] <= start or end <= location["start"]):
                return dict(stage="supervision", path=path, reason="overlapping_decisions")
        intervals[location["segment_id"]].append((location["start"], location["end"]))
        if doc["kind"] == "action_arguments" and location["decision"] == "positive":
            action = actions.get(location["segment_id"])
            event = events.get(action["event_id"]) if action else None
            if not (
                location["start"] == 0
                and location["end"] == len(doc["text"])
                and event is not None
                and not event["is_error"]
            ):
                return dict(
                    stage="action", path=path, reason="positive_action_not_whole_actual_success"
                )
    return None


def diagnose_side(record, role):
    """Pure diagnosis for a side already structurally bound by the input reader."""
    require(role in {"A", "B"} and record["role"] == role, "side role changed")
    inspection, artifact, request = record["inspection"], record["artifact"], record["request"]
    view = request["candidate_request"]["trajectory"]
    docs = {d["segment_id"]: d for d in view["segments"]}
    raw = artifact["review_text"]
    normal = artifact["finish_reason"] == "tool_calls" and not artifact["review_format_error"]
    try:
        raw_value = strict_json_decoder().decode(raw)
        raw_json_error = None
    except (ValueError, TypeError) as exc:
        raw_value = None
        raw_json_error = type(exc).__name__ + ": " + str(exc)
    statuses = _raw_statuses(raw_value)
    claim = raw_status_claim(statuses)
    locators, examined = [], 0
    for location, context, status in _locations(raw_value):
        examined += 1
        issue = locator_diagnostic(location, docs, **context)
        if issue:
            locators.append({**issue, "raw_assessment_status": status})
    failed = first_failure(raw, view, role, normal=normal)
    observed = (
        "annotation_failed"
        if record["review_status"] == "annotation_failed"
        else record["process_validity"]
    )
    require(observed in CATEGORIES, "unrecognized saved review category")
    require(
        (failed is not None) == (observed == "annotation_failed"),
        "saved inspection and diagnostic failure path disagree",
    )
    if failed is None:
        require(claim == observed, "saved successful process label differs from its raw statuses")
    try:
        critical = CriticalProcess.model_validate(raw_value["process"]).model_dump(mode="json")
        critical_failure = _process_failure(critical, docs, role)
    except (ValueError, TypeError, KeyError) as exc:
        critical_failure = dict(stage="schema", reason=type(exc).__name__ + ": " + str(exc))
    completion = artifact.get("usage", {}).get("completion_tokens")
    maximum = request["max_output_tokens"]
    auxiliary_first = failed is not None and (
        failed["stage"] in {"behavior", "supervision", "action"}
        or failed["stage"] == "schema"
        and failed.get("schema_error_paths")
        and all(p and p[0] in {"behavior", "supervision"} for p in failed["schema_error_paths"])
    )
    return dict(
        role=role,
        slot_id=record["slot_id"],
        task_id=record["task_id"],
        saved_review_status=record["review_status"],
        saved_process_validity=record["process_validity"],
        saved_category=observed,
        saved_inspection_statuses=_raw_statuses(inspection.get("parsed")),
        original_annotation_error=inspection.get(
            "annotation_failure_reason", inspection.get("error")
        ),
        raw_process_statuses=statuses,
        raw_status_claim=claim,
        raw_JSON_error=raw_json_error,
        first_failure=failed,
        raw_critical_local_binding_failure=critical_failure,
        raw_critical_local_binding_passed=critical_failure is None,
        descriptive_auxiliary_failure_after_bound_raw_process=bool(
            auxiliary_first and critical_failure is None
        ),
        raw_claim_and_local_binding_are_not_new_qualification=True,
        finish_reason=artifact["finish_reason"],
        review_format_error=artifact["review_format_error"],
        normal_annotation_envelope=normal,
        validator_was_given_empty_string=not normal,
        max_output_tokens=maximum,
        completion_tokens=completion,
        completion_reached_cap=type(completion) is int and completion >= maximum,
        locator_count_examined=examined,
        locator_problems=locators,
        all_locator_problems_are_diagnostics_including_after_first_failure=True,
        raw_return_repaired=False,
        saved_judgment_changed=False,
    )


def _prepare(source_root, expected_review_seal_id=None):
    root = Path(source_root).resolve()
    anchors = {}

    def load(relative, schema=None):
        value, ref = read_record(root / relative, root=root, schema=schema)
        anchors[relative] = ref
        return value

    plan = load("registration/protocol.json", "v10_new8000_generation_protocol.v1")
    phase = load("review_registration/record.json", "v10_process_review_registration.v1")
    seal = load("review_seal/record.json", "v10_complete_process_review_seal.v1")
    require(
        expected_review_seal_id is None or seal["id"] == expected_review_seal_id,
        "unexpected review seal; do not audit another or rewritten result",
    )
    generation = read_ref(
        phase["generation_seal"], expected_path=root / "generation_seal/record.json", root=root
    )
    native = read_ref(
        phase["native_support"], expected_path=root / "native_support/record.json", root=root
    )
    anchors.update(generation_seal=phase["generation_seal"], native_support=phase["native_support"])
    require(
        plan["id"]
        == phase["protocol_id"]
        == seal["protocol_id"]
        == generation["protocol_id"]
        == native["protocol_id"]
        and plan["batch_id"] == phase["batch_id"] == seal["batch_id"]
        and plan["review_policy_id"] == phase["policy_id"] == review_policy_definition()["id"]
        and seal["generation_seal_id"] == native["generation_seal_id"] == generation["id"]
        and seal["native_support_id"] == native["id"],
        "original protocol/native/review barriers disagree",
    )
    require(
        len(plan["slots"]) == len(generation["slots"]) == len(native["rows"]) == ORIGINAL_SLOT_COUNT
        and generation["denominator"] == native["slot_denominator"] == ORIGINAL_SLOT_COUNT
        and [r["slot"] for r in generation["slots"]]
        == [r["slot"] for r in native["rows"]]
        == plan["slots"],
        "original 8000 denominator/roster changed",
    )
    eligible = [r["slot"] for r in native["rows"] if r["Q_native"] is True]
    expected = [(s["slot_id"], role) for s in eligible for role in ("A", "B")]
    require(
        len(eligible)
        == len({s["slot_id"] for s in eligible})
        == phase["M"]
        == seal["M"]
        == PAIR_COUNT
        and phase["eligible_slots"] == eligible
        and phase["maximum_calls"] == seal["expected_reviews"] == len(expected) == SIDE_COUNT
        and [(j["slot_id"], j["role"]) for j in phase["jobs"]] == expected
        and [(t["slot_id"], t["role"]) for t in seal["terminals"]] == expected
        and len({j["episode_id"] for j in phase["jobs"]}) == SIDE_COUNT
        and [j["episode_id"] for j in phase["jobs"]] == [t["episode_id"] for t in seal["terminals"]]
        and set(seal["joint_records"]) == {s["slot_id"] for s in eligible}
        and seal["all_registered_jobs_terminal"] is True
        and seal["returned"] == SIDE_COUNT
        and seal["network_unknowns"] == 0
        and all(t["terminal_kind"] == "paid_model_return" for t in seal["terminals"]),
        "complete final 5719 pairs / 11438 actual returned sides required",
    )
    replacements = {}
    if seal.get("network_retry_resolution") is not None:
        resolution = read_ref(
            seal["network_retry_resolution"],
            root=root,
            expected_path=root / "network_retry_01/resolution/record.json",
        )
        activation = read_ref(
            resolution["activation"],
            root=root,
            expected_path=root / "network_retry_01/activation/record.json",
        )
        permit = read_ref(
            resolution["authorization"],
            root=root,
            expected_path=root / "network_retry_01/authorization/record.json",
        )
        primary = read_ref(
            resolution["primary_matrix"],
            root=root,
            expected_path=root / "network_retry_01/complete_primary_matrix/record.json",
        )
        require(
            resolution["schema"] == "v10_network_retry_resolution.v1"
            and resolution["protocol_id"] == plan["id"]
            and activation["permit_id"] == permit["id"]
            and activation["primary_completion"] == resolution["primary_matrix"]
            and primary["protocol_id"] == plan["id"]
            and primary["phase_id"] == phase["id"]
            and primary["all_registered_jobs_terminal"] is True
            and activation["all_primary_attempt1_terminal"] is True
            and resolution["fixed_logical_review_denominator"]
            == activation["expected_reviews"]
            == primary["expected_reviews"]
            == SIDE_COUNT
            and [t["episode_id"] for t in primary["terminals"]]
            == [j["episode_id"] for j in phase["jobs"]]
            and resolution["only_supplementary_result_decides_final_sides"] is True
            and resolution["favorable_result_selection"] is False
            and resolution["attempt3_authorized"] is False,
            "the final replacement is not the registered whole-matrix once-only group",
        )
        targets = {t["episode_id"]: t for t in activation["targets"]}
        replacements = {r["episode_id"]: r for r in resolution["replacements"]}
        require(
            list(replacements)
            == list(targets)
            == [j["episode_id"] for j in activation["jobs"]]
            == [
                t["episode_id"]
                for t in primary["terminals"]
                if t["terminal_kind"] == "acknowledged_connection_unknown"
            ]
            and len(replacements)
            == len(resolution["replacements"])
            == len(activation["targets"])
            == activation["target_count"]
            == resolution["supplementary_attempts"]
            and resolution["physical_attempts"] == SIDE_COUNT + len(replacements),
            "attempt2 roster incomplete, duplicated, or selected by results",
        )
        for old, final in zip(primary["terminals"], seal["terminals"], strict=True):
            eid = final["episode_id"]
            if eid in replacements:
                r, target = replacements[eid], targets[eid]
                require(
                    r["final_terminal"] == final["record"]
                    and r["original_terminal"] == old["record"] == final["original_terminal"]
                    and r["origin_invocation_id"] == target["origin_invocation_id"]
                    and r["retry_invocation_id"] == target["retry_invocation_id"]
                    and final["physical_attempt_index"] == 2
                    and final["network_retry_resolution"] == seal["network_retry_resolution"]
                    and final["authorization"] == resolution["authorization"],
                    "final side changed its authorized physical attempt",
                )
            else:
                require(
                    old["record"] == final["record"]
                    and final.get("physical_attempt_index", 1) == 1,
                    "non-target original was replaced",
                )
        anchors["network_retry_resolution"] = seal["network_retry_resolution"]
        anchors.update(
            network_retry_activation=resolution["activation"],
            network_retry_authorization=resolution["authorization"],
            complete_primary_matrix=resolution["primary_matrix"],
        )
    else:
        require(
            all(t.get("physical_attempt_index", 1) == 1 for t in seal["terminals"]),
            "unbound supplementary final side",
        )
    outcomes = {r["slot"]["slot_id"]: r for r in generation["slots"]}
    jobs = [
        dict(
            index=index,
            slot=slot,
            A=seal["terminals"][2 * index],
            B=seal["terminals"][2 * index + 1],
            joint=seal["joint_records"][slot["slot_id"]],
            outcome=outcomes[slot["slot_id"]],
        )
        for index, slot in enumerate(eligible)
    ]
    return dict(
        root=str(root),
        plan=plan,
        phase=phase,
        seal=seal,
        replacements=replacements,
        anchors=anchors,
        jobs=jobs,
    )


def _verify_side(job, role, state):
    from .v6_review_provider import _strict_review_payload

    root, plan = Path(state["root"]), state["plan"]
    terminal, slot = job[role], job["slot"]
    sid, eid = slot["slot_id"], terminal["episode_id"]
    replacement = state["replacements"].get(eid)
    primary_dir = root / "reviews" / sid.split(":", 1)[1] / role
    directory = (
        root / "network_retry_01/slots" / eid.split(":", 1)[1] if replacement else primary_dir
    )
    record = read_ref(
        terminal["record"],
        root=root,
        expected_path=directory / "record/record.json",
        schema="v10_paid_process_review.v1",
    )
    request, artifact, inspection = record["request"], record["artifact"], record["inspection"]
    check_bound(request)
    check_bound(artifact)
    check_bound(inspection)
    saved_request = read_record(directory / "request/record.json", root=root)[0]
    saved_artifact = read_record(directory / "artifact/record.json", root=root)[0]
    require(
        saved_request == request and saved_artifact == artifact,
        "independent original request/artifact differs",
    )
    if replacement:
        original = read_ref(
            replacement["original_terminal"],
            root=root,
            expected_path=primary_dir / "record/record.json",
        )
        require(
            original["schema"] == "v10_network_unknown_review.v1"
            and original["invocation_id"] == replacement["origin_invocation_id"]
            and original["actual_model_call_receipt_verified"] is False
            and read_record(primary_dir / "request/record.json", root=root)[0] == request,
            "supplementary result did not preserve its actual original UNKNOWN/request",
        )
    candidate = check_bound(request["candidate_request"])
    view = candidate["trajectory"]
    require(
        record["protocol_id"] == request["protocol_id"] == plan["batch_id"]
        and record["policy_id"] == request["policy_id"] == plan["review_policy_id"]
        and record["role"] == request["role"] == role
        and record["task_id"] == request["task_id"] == slot["task_id"]
        and record["slot_id"]
        == request["slot_id"]
        == candidate["slot_id"]
        == view["slot_id"]
        == sid
        and request["episode_id"] == eid
        and record["episode_sha256"]
        == request["episode_sha256"]
        == candidate["episode_sha256"]
        == view["episode_sha256"]
        == job["outcome"]["episode_sha256"]
        and record["view_id"]
        == request["view_id"]
        == candidate["view_id"]
        == view["view_id"]
        == "public_trajectory:" + digest({k: v for k, v in view.items() if k != "view_id"})
        and record["actual_model_call_receipt_verified"] is True
        and inspection["review_status"] == record["review_status"]
        and inspection["process_validity"] == record["process_validity"],
        "original side / visible trajectory / saved inspection identity differs",
    )
    coordinates = invocation_identity(
        dict(
            run_id=plan["budget_config"]["run_id"],
            episode_id=eid,
            attempt_index=2 if replacement else 1,
        ),
        turn_index=0,
    )
    binding = record["ledger_binding"]
    raw_response = artifact["api_response_raw"].encode()
    response = strict_json_decoder().decode(raw_response.decode())
    public_request = artifact["public_request"]
    require(
        artifact["budget_coordinates"] == binding["coordinates"] == coordinates
        and artifact["budget_invocation_id"]
        == binding["invocation_id"]
        == coordinates["invocation_id"]
        and (not replacement or replacement["retry_invocation_id"] == coordinates["invocation_id"])
        and artifact["raw_api_response_sha256"]
        == sha_bytes(raw_response)
        == binding["original_response_sha256"]
        and response == artifact["api_response"]
        and response["model"] == public_request["model"] == "deepseek-flash"
        and public_request["messages"] == request["messages"]
        and public_request["tools"] == [request["strict_tool"]]
        and public_request["max_tokens"] == request["max_output_tokens"]
        and artifact["request_sha256"]
        == digest(public_request)
        == binding["original_request_sha256"]
        and artifact["public_request_body_sha256"]
        == sha_bytes(canonical(public_request))
        == binding["original_request_body_sha256"]
        and response["usage"] == artifact["usage"]
        and digest(artifact["usage"]) == binding["usage_sha256"]
        and artifact["ledger_record_sha256"] == binding["original_ledger_record_sha256"]
        and binding["state"] == "SETTLED"
        and binding["actual_response_and_usage_bound"] is True,
        "retained paid-return/HTTP/usage receipt is internally inconsistent (wallet not reopened)",
    )
    choice = response["choices"][0]
    require(
        choice["finish_reason"] == artifact["finish_reason"]
        and all(
            artifact.get(k) == v
            for k, v in _strict_review_payload(choice["message"], choice["finish_reason"]).items()
        ),
        "diagnosed annotation text differs from the exact original model envelope",
    )
    if role == "A":
        normal = artifact["finish_reason"] == "tool_calls" and not artifact["review_format_error"]
        require(
            inspection["request"] == candidate
            and inspection["raw_review"] == (artifact["review_text"] if normal else ""),
            "A inspection did not consume the retained original response",
        )
        manifest = check_bound(record["supervision_manifest"])
        require(
            manifest["authority_record"] == inspection
            and manifest["supervision_source_record_id"] == inspection["id"],
            "A supervision authority changed",
        )
    else:
        require(record["supervision_manifest"] is None, "B cannot become supervision authority")
    diagnostic = diagnose_side(record, role)
    diagnostic.update(
        pair_index=job["index"],
        record=terminal["record"],
        record_id=record["id"],
        physical_attempt_index=coordinates["attempt_index"],
        invocation_id=coordinates["invocation_id"],
        episode_id=eid,
        request_id=request["id"],
        original_ledger_record_sha256=binding["original_ledger_record_sha256"],
        record_integrity_verified_from_sealed_files=True,
        wallet_or_financial_state_reverified=False,
    )
    return record, diagnostic


def _audit_pair(job):
    state = _STATE
    root = Path(state["root"])
    sid = job["slot"]["slot_id"]
    outcome = check_bound(job["outcome"], "v10_generation_slot_outcome.v1")
    episode_path = root / "slots" / sid.split(":", 1)[1] / "episode/episode.json"
    require(
        outcome["status"] == "COMPLETE"
        and Path(outcome["episode_path"]).resolve() == episode_path.resolve()
        and sha_bytes(episode_path.read_bytes()) == outcome["episode_file_sha256"],
        "original canonical Episode is absent/changed; no native rescoring is permitted",
    )
    a, a_diag = _verify_side(job, "A", state)
    b, b_diag = _verify_side(job, "B", state)
    joint = read_ref(
        job["joint"],
        root=root,
        expected_path=root / "joint" / sid.split(":", 1)[1] / "record.json",
        schema="v10_joint_process_review.v1",
    )
    valid = a_diag["saved_category"] == b_diag["saved_category"] == "valid"
    require(
        joint["slot_id"] == sid
        and joint["task_id"] == job["slot"]["task_id"]
        and joint["protocol_id"] == state["plan"]["batch_id"]
        and joint["policy_id"] == state["plan"]["review_policy_id"]
        and joint["q_native"] is True
        and joint["joint_valid"] is valid
        and joint["A_record_id"] == a["id"]
        and joint["B_record_id"] == b["id"]
        and joint["A"] == a
        and joint["B"] == b
        and joint["A_manifest"] == a["supervision_manifest"]
        and joint["supervision_authority"] == "A"
        and a["request"]["candidate_request"]["trajectory"]
        == b["request"]["candidate_request"]["trajectory"],
        "joint must bind exactly the sealed final A/B, never a more favorable attempt",
    )
    pair = dict(
        pair_index=job["index"],
        slot_id=sid,
        task_id=job["slot"]["task_id"],
        Q_native_as_sealed=True,
        joint_valid_as_sealed=joint["joint_valid"],
        joint=job["joint"],
        A_record=a_diag["record"],
        B_record=b_diag["record"],
        A_category=a_diag["saved_category"],
        B_category=b_diag["saved_category"],
        A_raw_status_claim=a_diag["raw_status_claim"],
        B_raw_status_claim=b_diag["raw_status_claim"],
        diagnostic_does_not_change_joint=True,
    )
    return pair, [a_diag, b_diag]


def _source_binding(frozen_source_root):
    current = Path(__file__).resolve().parent
    frozen = (
        Path(frozen_source_root).resolve()
        / "trusted_data_synthesis/src/trusted_synthesis/finance_research"
    )
    result = {}
    for name in VALIDATOR_FILES:
        here, original = (
            sha_bytes((current / name).read_bytes()),
            sha_bytes((frozen / name).read_bytes()),
        )
        require(here == original, "diagnostic imports differ from frozen V10 source: " + name)
        result[name] = dict(
            sha256=here, imported_path=str(current / name), frozen_path=str(frozen / name)
        )
    return dict(
        scanner=dict(
            path=str(Path(__file__).resolve()), sha256=sha_bytes(Path(__file__).read_bytes())
        ),
        unchanged_V10_validator_sources=result,
        python=sys.version,
        pydantic=pydantic.__version__,
    )


def _summarize(results, state, source_binding, registration=None, *, progress=False):
    cross = {a: {b: 0 for b in CATEGORIES} for a in CATEGORIES}
    totals = {r: Counter() for r in ("A", "B")}
    claims = {r: defaultdict(Counter) for r in ("A", "B")}
    dimensions = {r: {d: defaultdict(Counter) for d in DIMENSIONS} for r in ("A", "B")}
    first = {r: Counter() for r in ("A", "B")}
    envelope = {r: Counter() for r in ("A", "B")}
    auxiliary_loss = {r: Counter() for r in ("A", "B")}
    locator_issues, locator_sides = Counter(), Counter()
    locator_examined = Counter()
    cases = defaultdict(list)
    sides_bytes, pairs_bytes, valid_slots, task_order, joint_by_task = [], [], [], [], {}
    attempts = Counter()

    def case(key, side, issue=None):
        if len(cases[key]) >= 2:
            return
        cases[key].append(
            dict(
                pair_index=side["pair_index"],
                role=side["role"],
                task_id=side["task_id"],
                slot_id=side["slot_id"],
                record=side["record"],
                physical_attempt_index=side["physical_attempt_index"],
                first_failure=side["first_failure"],
                locator=issue,
            )
        )

    processed = 0
    for pair, sides in results:
        require(
            pair["pair_index"] == processed, "diagnostic order must be the registered pair order"
        )
        processed += 1
        cross[pair["A_category"]][pair["B_category"]] += 1
        if pair["joint_valid_as_sealed"]:
            valid_slots.append(pair["slot_id"])
            joint_by_task.setdefault(pair["task_id"], []).append(pair["slot_id"])
        task_order.append(pair["task_id"])
        pairs_bytes.append(canonical(pair) + b"\n")
        for side in sides:
            role, saved = side["role"], side["saved_category"]
            totals[role][saved] += 1
            claims[role][side["raw_status_claim"]][saved] += 1
            for name, status in side["raw_process_statuses"].items():
                dimensions[role][name][str(status)][saved] += 1
            stage = side["first_failure"]["stage"] if side["first_failure"] else "none"
            first[role][stage] += 1
            envelope[role]["finish:" + str(side["finish_reason"])] += 1
            if side["completion_reached_cap"]:
                envelope[role]["completion_reached_cap"] += 1
            if side["validator_was_given_empty_string"]:
                envelope[role]["inspector_empty_string_envelope_wrapper"] += 1
            if side["descriptive_auxiliary_failure_after_bound_raw_process"]:
                auxiliary_loss[role][side["raw_status_claim"]] += 1
                case(f"{role}/auxiliary_failure/raw_claim_{side['raw_status_claim']}", side)
            attempts[str(side["physical_attempt_index"])] += 1
            case(f"{role}/saved/{saved}", side)
            if stage != "none":
                case(f"{role}/first_failure/{stage}", side)
            if side["finish_reason"] == "length":
                case(f"{role}/envelope/length", side)
            locator_examined[role] += side["locator_count_examined"]
            distinct = set()
            for issue in side["locator_problems"]:
                context = issue["context"]
                if context == "supervision":
                    context += ":" + str(issue["supervision_decision"])
                elif context == "critical_process":
                    context += (
                        ":"
                        + str(issue["process_dimension"])
                        + ":"
                        + str(issue["raw_assessment_status"])
                    )
                key = f"{role}/{context}/{issue['problem']}"
                locator_issues[key] += 1
                distinct.add(key)
                case("locator/" + key, side, issue)
            locator_sides.update(distinct)
            sides_bytes.append(canonical(side) + b"\n")
        if progress and processed % 128 == 0:
            print(
                json.dumps(
                    dict(
                        stage="read_only_funnel_audit",
                        verified_pairs=processed,
                        denominator=PAIR_COUNT,
                    )
                ),
                flush=True,
            )
    seal = state["seal"]
    require(
        processed == PAIR_COUNT
        and len(sides_bytes) == SIDE_COUNT
        and valid_slots == seal["joint_slot_ids"]
        and joint_by_task == seal["joint_by_task"]
        and len(joint_by_task) == seal["N"]
        and sum(sum(row.values()) for row in cross.values()) == PAIR_COUNT,
        "whole audit or saved joint intersection incomplete/inconsistent",
    )
    summary = bound(
        dict(
            schema="v11_frozen_review_funnel_diagnosis.v1",
            completed_at=datetime.now(timezone.utc).isoformat(),
            complete=True,
            source_root=state["root"],
            source_review_seal_id=seal["id"],
            optional_V11_registration=registration,
            source_binding=source_binding,
            input_anchors=state["anchors"],
            pair_denominator=PAIR_COUNT,
            logical_side_denominator=SIDE_COUNT,
            original_generation_denominator=ORIGINAL_SLOT_COUNT,
            selected_final_physical_attempt_counts=dict(attempts),
            saved_joint_valid_count=len(valid_slots),
            saved_joint_task_count=len(joint_by_task),
            excluded_by_saved_joint_rule=PAIR_COUNT - len(valid_slots),
            saved_annotation_intersection_fraction=len(valid_slots) / PAIR_COUNT,
            AB_saved_category_cross_table=cross,
            side_saved_category_counts=totals,
            raw_status_claim_by_saved_category=claims,
            raw_dimension_status_by_saved_category=dimensions,
            first_failure_stage_counts=first,
            first_failure_agrees_with_every_saved_inspection=True,
            annotation_envelope_counts=envelope,
            auxiliary_failure_after_bound_raw_process_counts_by_raw_claim=auxiliary_loss,
            auxiliary_counts_are_descriptive_not_requalified_valid_or_invalid=True,
            locator_occurrence_counts=locator_issues,
            distinct_side_counts_for_locator_categories=locator_sides,
            locator_count_examined=locator_examined,
            cases_per_category_limit=2,
            case_selection="first two in original registered pair order, A then B",
            cases_reference="cases.json",
            side_rows_reference="sides.jsonl",
            pair_rows_reference="pairs.jsonl",
            native_reexecuted=False,
            financial_semantics_rejudged=False,
            model_calls=0,
            wallet_opened=False,
            GPU_used=False,
            original_files_written=False,
            saved_labels_or_masks_changed=False,
            new_qualification_created=False,
            original_HTTP_usage_receipts_internally_bound=True,
            wallet_billing_reverified=False,
            interpretation=(
                "Saved A/B annotation categories and exact text diagnostics only. "
                "Raw supported/critical_error claims are not established financial truth. "
                "Exact quote search is restricted to its named original segment; no fuzzy "
                "matching, normalization, new review, selection or training admission."
            ),
        )
    )
    case_record = bound(
        dict(
            schema="v11_review_funnel_case_index.v1",
            source_review_seal_id=seal["id"],
            fixed_maximum_per_category=2,
            ordering="registered pairs then A/B",
            cases=dict(cases),
        )
    )
    return summary, {
        "summary.json": canonical(summary) + b"\n",
        "sides.jsonl": b"".join(sides_bytes),
        "pairs.jsonl": b"".join(pairs_bytes),
        "cases.json": canonical(case_record) + b"\n",
    }


def audit_review_funnel(
    source_root,
    output,
    *,
    workers=8,
    expected_review_seal_id=None,
    frozen_source_root=DEFAULT_FROZEN,
    registration_path=None,
    progress=True,
):
    global _STATE
    root, target = Path(source_root).resolve(), Path(output).resolve()
    require(
        root != target and root not in target.parents,
        "audit output cannot modify the original root",
    )
    require(not target.exists(), "audit output must be a new immutable directory")
    require(type(workers) is int and 1 <= workers <= 8, "use one to eight read-only CPU workers")
    started = time.monotonic()
    sources = _source_binding(frozen_source_root)
    state = _prepare(root, expected_review_seal_id)
    registration = read_record(registration_path)[1] if registration_path else None
    _STATE = state
    try:
        if workers == 1:
            summary, payloads = _summarize(
                map(_audit_pair, state["jobs"]), state, sources, registration, progress=progress
            )
        else:
            with multiprocessing.get_context("fork").Pool(workers) as pool:
                summary, payloads = _summarize(
                    pool.imap(_audit_pair, state["jobs"], chunksize=1),
                    state,
                    sources,
                    registration,
                    progress=progress,
                )
        require(
            _source_binding(frozen_source_root) == sources, "diagnostic source changed during scan"
        )
        manifest = bound(
            dict(
                schema="v11_review_funnel_artifact_manifest.v1",
                summary_id=summary["id"],
                source_binding=sources,
                source_review_seal_id=state["seal"]["id"],
                files={
                    name: dict(sha256=sha_bytes(raw), bytes=len(raw))
                    for name, raw in payloads.items()
                },
                elapsed_seconds=time.monotonic() - started,
                workers=workers,
                complete=True,
                diagnostic_only=True,
                new_qualification_created=False,
            )
        )
        payloads["manifest.json"] = canonical(manifest) + b"\n"
        write_immutable_artifact_directory(target, payloads)
        return summary
    finally:
        _STATE = None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--expected-review-seal-id")
    parser.add_argument("--frozen-source-root", type=Path, default=DEFAULT_FROZEN)
    parser.add_argument("--registration", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    summary = audit_review_funnel(
        args.root,
        args.out,
        workers=args.workers,
        expected_review_seal_id=args.expected_review_seal_id,
        frozen_source_root=args.frozen_source_root,
        registration_path=args.registration,
        progress=not args.quiet,
    )
    print(
        json.dumps(
            dict(complete=True, summary_id=summary["id"], output=str(args.out)), ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
