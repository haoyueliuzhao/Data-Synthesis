"""Fresh whole-matrix review wire; compact IDs, exact host projection, no old relabeling."""

from __future__ import annotations

import copy
import json

from . import v11_process_review as candidate
from .contracts import Episode, digest
from .qwen_protocol import strict_json_decoder
from .v11_process_review import DIMENSIONS
from .v12_review_capacity import capacity_for

MODEL = "deepseek-flash"
ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
BATCH_ID = "finqa-v12-20260930-rereview-01"
WIRE = "v12_compact_unit_AB_production.v1"


def require(value, message):
    if not value:
        raise ValueError(message)


def bound(value):
    return {**value, "id": digest(value)}


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def review_episode_id(protocol_id, slot_id, role):
    require(
        role in {"A", "B"} and slot_id.startswith("v10gen:"),
        "same original V10 slot and A/B role required",
    )
    return "v12review:" + digest(dict(protocol_id=protocol_id, slot_id=slot_id, role=role))


def policy_definition():
    return bound(
        dict(
            schema="v12_rereview_policy.v1",
            model=MODEL,
            wire_protocol=WIRE,
            source_batch="same complete original V10 cohort; no new generation",
            candidate_policy_id=candidate.policy_definition()["id"],
            fixed_original_tasks=1000,
            fixed_original_slots=8000,
            fixed_native_correct_packages=5719,
            fixed_new_review_calls=11438,
            old_verdicts_reused=False,
            failed_only_sampling=False,
            favorable_result_selection=False,
            original_history_and_UNKNOWN_holds_preserved=True,
            A="four critical checks plus unique positive unit/action supervision",
            B="independent four critical checks only; no A judgment or mask",
            whole_evidence=(
                "provided short unit IDs or actual action/event IDs; "
                "host supplies original coordinates"
            ),
            partial_evidence=(
                "nonempty exact quote uniquely matched in original segment; no fuzzy repair"
            ),
            optional_behavior_and_context_only_not_requested=True,
            raw_wire_preserved=True,
            deterministic_wire_materialization_not_model_text=True,
            no_summary_or_evidence_count_semantic_maximum=True,
            output_capacity=(
                "per-original serialized response-planning scenario; estimate not guarantee"
            ),
            output_limit_is_real_terminal=True,
            JSON_repair=False,
            logical_process_and_projection_independent=True,
            missing_A_supervision_is_projection_failure_only=True,
            unrequested_top_level_fields_are_logged_not_critical_evidence=True,
            projection_failed_joint_candidates_retained=True,
            no_individual_reason0_exclusion=True,
            no_mapping_or_training_in_this_stage=True,
            API_calls_per_side=1,
            automatic_retry=False,
        )
    )


def _object(properties):
    return dict(
        type="object", properties=properties, required=list(properties), additionalProperties=False
    )


def _array(items):
    return dict(type="array", items=items)


def strict_tool(role):
    require(role in {"A", "B"}, "A/B only")
    string = {"type": "string"}
    partial = _object(dict(id=string, quote=string))
    assessment = _object(
        dict(
            status=dict(
                type="string", enum=["supported", "critical_error", "unknown", "not_applicable"]
            ),
            summary=string,
            evidence_ids=_array(string),
            partial_evidence=_array(partial),
        )
    )
    properties = dict(process=_object({name: copy.deepcopy(assessment) for name in DIMENSIONS}))
    if role == "A":
        properties["supervision"] = _object(
            dict(
                status=dict(type="string", enum=["complete", "unknown"]),
                positive_units=_array(string),
                partial_positive_content=_array(partial),
                positive_actions=_array(string),
            )
        )
    return dict(
        type="function",
        function=dict(
            name="submit_review",
            strict=True,
            description=(
                "Return the requested compact review once "
                "as a single JSON function argument object."
            ),
            parameters=_object(properties),
        ),
    )


def rubric(role):
    base = """Review the actual full public solving history below, not a reconstructed proof.
Return one submit_review object, no second JSON object, duplicate key, Markdown or prose outside it.
Keep each summary concise; cite IDs instead of copying whole source passages.
The four process checks are evidence_and_operations, observation_interpretation,
unwithdrawn_critical_contradictions, actual_revisions. supported, critical_error,
unknown and not_applicable are reviewer claims, not host-proved financial truth.
evidence_and_operations and unwithdrawn_critical_contradictions cannot be N/A.
Supported evidence_and_operations and each critical_error require actual evidence.
Initial public sources were already visible. No mandatory read_source/check/revision,
reference program match, proposition graph or author-style proof is required.
Tool success alone does not establish correct reasoning. Retain earlier mistakes and
withdrawals as context; assess whether a critical error remains unwithdrawn.

All original text is present once in units, indexed by short u IDs. Source and history
groups preserve its location and chronology. evidence_ids chooses whole units (or
provided actual action/event IDs). Do not output start/end or repeat full arguments.
Use partial_evidence only when whole units are unsuitable; {id,quote} must contain a
nonempty contiguous exact quote unique in its original segment, retaining qualifiers.
Do not normalize numbers, fuzzy-match text, invent IDs or infer missing evidence.
Use empty arrays when no partial quote is needed. Choosing an ID proves neither
financial correctness nor semantic completeness; resolve the actual substantive issue.
"""
    if role == "B":
        return (
            base
            + "\nReturn only process; do not supply another reviewer's judgment or supervision."
        )
    return (
        base
        + """
Also provide supervision with status complete or unknown. positive_units approves only
original public-content units. partial_positive_content approves exact unique subspans
when needed. positive_actions selects actual successful action IDs; host derives full
original argument ranges. Sources and tool observations are inputs, never targets.
Do not overlap positive selections. Unlisted content/actions remain unreviewed with zero
positive target; do not enumerate context-only narration or add behavior descriptions.
No minimum positive-reason quota per original is imposed. If projection is unresolved,
say unknown; this does not erase independently readable process judgments.
"""
    )


def public_payload(view, catalog, role):
    """Lossless public strings/order; remove repeated long metadata IDs, never text."""
    units = catalog["units"]
    by_segment = {}
    for unit in units:
        by_segment.setdefault(unit["segment_id"], []).append(unit["unit_id"])
    docs = {s["segment_id"]: s for s in view["segments"]}
    for sid, doc in docs.items():
        require(
            "".join(u["text"] for u in units if u["segment_id"] == sid) == doc["text"],
            "public unit text lost",
        )
    covered = []
    question = []
    for doc in view["segments"]:
        if doc["kind"] == "question":
            question.extend(by_segment[doc["segment_id"]])
            covered.append(doc["segment_id"])
    sources = []
    for source in view["sources"]:
        parts = []
        for sid in source["segment_ids"]:
            doc = docs[sid]
            parts.append(
                {
                    **{k: doc[k] for k in ("kind", "row", "column") if k in doc},
                    "units": by_segment[sid],
                }
            )
            covered.append(sid)
        sources.append(
            dict(
                source_id=source["source_id"],
                kind=source["kind"],
                locator=source["locator"],
                parts=parts,
            )
        )
    history = []
    for turn in view["turns"]:
        sid = turn["public_content_segment_id"]
        covered.append(sid)
        actions = []
        for action in turn["actions"]:
            args = action["arguments_segment_id"]
            covered.append(args)
            actions.append(
                dict(
                    action_id=action["action_id"],
                    name=action["name"],
                    argument_units=by_segment[args],
                    event_id=action["event_id"],
                )
            )
        unparsed = []
        for sid2 in turn["unparsed_tool_call_segment_ids"]:
            covered.append(sid2)
            unparsed.extend(by_segment[sid2])
        history.append(
            dict(
                turn_index=turn["turn_index"],
                public_content=by_segment[sid],
                actions=actions,
                unparsed_tool_calls=unparsed,
            )
        )
    events = []
    for event in view["events"]:
        sid = event["observation_segment_id"]
        covered.append(sid)
        events.append(
            dict(
                event_id=event["event_id"],
                event_index=event["event_index"],
                action_id=event["action_id"],
                name=event["name"],
                is_error=event["is_error"],
                observation_units=by_segment[sid],
                result_handle=event["result_handle"],
            )
        )
    require(
        len(covered) == len(set(covered)) == len(docs) and set(covered) == set(docs),
        "every original public segment exactly once",
    )
    return dict(
        wire_protocol=WIRE,
        role=role,
        task_id=view["task_id"],
        question_units=question,
        sources=sources,
        history=history,
        events=events,
        units={u["unit_id"]: u["text"] for u in units},
        stop_reason=view["stop_reason"],
        final_program=view["final_program"],
    )


def prepare_request(episode: Episode, *, slot_id, role, native_result, integrity, protocol_id):
    base = candidate.prepare_review_request(
        episode, slot_id=slot_id, role=role, native_result=native_result, integrity=integrity
    )
    view, catalog = base["trajectory"], base["catalog"]
    capacity = capacity_for(view, catalog, role)
    messages = [
        dict(role="system", content=rubric(role)),
        dict(role="user", content=canonical(public_payload(view, catalog, role)).decode()),
    ]
    request = bound(
        dict(
            schema="v12_review_request.v1",
            wire_protocol=WIRE,
            model=MODEL,
            batch_id=BATCH_ID,
            protocol_id=protocol_id,
            policy_id=policy_definition()["id"],
            episode_id=review_episode_id(protocol_id, slot_id, role),
            role=role,
            task_id=episode.task_id,
            slot_id=slot_id,
            source_episode_sha256=digest(episode),
            candidate_request=base,
            messages=messages,
            messages_sha256=digest(messages),
            strict_tool=strict_tool(role),
            capacity=capacity,
            max_output_tokens=capacity["max_output_tokens"],
            original_public_text_preserved=True,
            no_native_or_private_reference_in_messages=True,
        )
    )
    body = _body(request)
    require(
        len(canonical(body)) + request["max_output_tokens"] < 1048576,
        "full original request/output envelope too large; no truncation",
    )
    return request


def _body(request):
    return dict(
        model=MODEL,
        messages=copy.deepcopy(request["messages"]),
        tools=[copy.deepcopy(request["strict_tool"])],
        tool_choice=dict(type="function", function=dict(name="submit_review")),
        temperature=0,
        top_p=1,
        max_tokens=request["max_output_tokens"],
        thinking={"type": "disabled"},
        stream=False,
    )


def checked_request(request):
    require(
        request.get("id") == digest({k: v for k, v in request.items() if k != "id"})
        and request.get("schema") == "v12_review_request.v1"
        and request.get("model") == MODEL
        and request.get("wire_protocol") == WIRE
        and request.get("batch_id") == BATCH_ID
        and request.get("policy_id") == policy_definition()["id"],
        "wrong registered V12 request/model/policy",
    )
    view, catalog = candidate._checked_request(request["candidate_request"])
    role = request["role"]
    require(
        role == request["candidate_request"]["role"]
        and request["slot_id"] == view["slot_id"]
        and request["task_id"] == view["task_id"]
        and request["source_episode_sha256"] == view["episode_sha256"]
        and request["episode_id"]
        == review_episode_id(request["protocol_id"], request["slot_id"], role),
        "new side must bind the same original role/slot",
    )
    messages = [
        dict(role="system", content=rubric(role)),
        dict(role="user", content=canonical(public_payload(view, catalog, role)).decode()),
    ]
    require(
        request["messages"] == messages
        and request["messages_sha256"] == digest(messages)
        and request["strict_tool"] == strict_tool(role)
        and request["capacity"] == capacity_for(view, catalog, role)
        and request["max_output_tokens"] == request["capacity"]["max_output_tokens"],
        "wire/capacity/original public input changed",
    )
    return request


def request_body(request):
    checked_request(request)
    body = _body(request)
    require(
        len(canonical(body)) + request["max_output_tokens"] < 1048576,
        "full request/output envelope exceeds registered context; no clipping",
    )
    return body


def materialize_wire(value, request):
    """Normative ID-list encoding, never repair an invalid JSON or guess a quote."""
    failures = []
    role = request["role"]
    base = request["candidate_request"]
    offered = {u["unit_id"] for u in base["catalog"]["units"]}
    offered.update(a["action_id"] for a in base["catalog"]["actions"])
    offered.update(e["event_id"] for e in base["catalog"]["events"])

    def error(scope, path, reason):
        failures.append(dict(scope=scope, path=path, reason=reason))

    def object_shape(item, fields, scope, path):
        if not isinstance(item, dict) or set(item) != set(fields):
            error(scope, path, "missing_or_extra_wire_fields")
            return item if isinstance(item, dict) else {}
        return item

    def references(whole, partial, scope, path):
        result = []
        if not isinstance(whole, list):
            error(scope, path + ".ids", "ID_array_required")
        else:
            for i, identifier in enumerate(whole):
                if not isinstance(identifier, str) or identifier not in offered:
                    error(scope, f"{path}.ids[{i}]", "provided_original_ID_required")
                result.append(dict(id=identifier, quote=None))
        if not isinstance(partial, list):
            error(scope, path + ".partial", "partial_array_required")
        else:
            for i, ref in enumerate(partial):
                obj = object_shape(ref, ["id", "quote"], scope, f"{path}.partial[{i}]")
                if (
                    not isinstance(obj.get("id"), str)
                    or obj.get("id") not in offered
                    or not isinstance(obj.get("quote"), str)
                    or not obj.get("quote")
                ):
                    error(
                        scope,
                        f"{path}.partial[{i}]",
                        "provided_ID_and_nonempty_exact_quote_required",
                    )
                result.append(copy.deepcopy(obj))
        return result

    # The transport/JSON envelope is not the auxiliary A supervision contract.
    # A missing or malformed auxiliary field must never invalidate a complete core.
    if not isinstance(value, dict):
        error("envelope", "$", "wire_object_required")
        value = {}
    else:
        expected = {"process", "supervision"} if role == "A" else {"process"}
        for extra in sorted(set(value) - expected):
            error("auxiliary", f"$.{extra}", "unrequested_top_level_field")
    process = object_shape(value.get("process"), DIMENSIONS, "process", "process")
    derived = {"process": {}}
    for name in DIMENSIONS:
        check = object_shape(
            process.get(name),
            ["status", "summary", "evidence_ids", "partial_evidence"],
            "process",
            "process." + name,
        )
        derived["process"][name] = dict(
            status=check.get("status"),
            summary=check.get("summary"),
            evidence=references(
                check.get("evidence_ids"),
                check.get("partial_evidence"),
                "process",
                "process." + name,
            ),
        )
    if role == "A":
        sup = object_shape(
            value.get("supervision"),
            ["status", "positive_units", "partial_positive_content", "positive_actions"],
            "projection",
            "supervision",
        )
        derived["supervision"] = dict(
            status=sup.get("status"),
            positive_content=references(
                sup.get("positive_units"),
                sup.get("partial_positive_content"),
                "projection",
                "supervision",
            ),
            positive_actions=copy.deepcopy(sup.get("positive_actions")),
        )
    return derived, failures


def inspect_paid_annotation(request, artifact):
    checked_request(request)
    raw = artifact["review_text"]
    require(isinstance(raw, str), "preserve original returned annotation text")
    normal = artifact["finish_reason"] == "tool_calls" and not artifact["review_format_error"]
    decoded, parse_error, wire_errors = None, None, []
    try:
        decoded = strict_json_decoder().decode(raw)
    except (ValueError, TypeError) as exc:
        parse_error = f"{type(exc).__name__}: {exc}"
    if parse_error is None:
        derived, wire_errors = materialize_wire(decoded, request)
        inspection_text = canonical(derived).decode()
    else:
        derived, inspection_text = None, raw
    inspection = candidate.inspect_review(inspection_text, request["candidate_request"])
    process = inspection["process_evidence_binding"]
    projection = inspection["auxiliary"]["supervision"]
    process_wire_ok = not any(e["scope"] in {"process", "envelope"} for e in wire_errors)
    process_usable = normal and parse_error is None and process_wire_ok
    validity = process["validated_process_outcome"] if process_usable else "unknown"
    projection_usable = (
        None
        if request["role"] == "B"
        else (
            normal
            and parse_error is None
            and projection["usable"]
            and not any(e["scope"] in {"projection", "envelope"} for e in wire_errors)
        )
    )
    codes = []
    if artifact["finish_reason"] == "length":
        codes.append("OUTPUT_LIMIT_REACHED")
    elif not normal:
        codes.append("ANNOTATION_ENVELOPE_FAILED")
    if parse_error is not None:
        codes.append("RAW_JSON_PARSE_FAILED")
    if wire_errors:
        codes.append("WIRE_SCHEMA_FAILED")
    if not process["all_critical_evidence_bound"]:
        codes.append("LOCATOR_OR_CRITICAL_SCHEMA_UNRESOLVED")
    if request["role"] == "A" and not projection_usable:
        codes.append("SUPERVISION_REPRESENTATION_FAILED")
    return dict(
        inspection=inspection,
        new_pipeline_outcomes=dict(
            envelope_complete=bool(normal),
            raw_JSON_complete=parse_error is None,
            raw_JSON_error=parse_error,
            raw_wire_annotation=decoded,
            deterministic_materialized_annotation=derived,
            materialization_is_not_raw_model_text=True,
            wire_schema_failures=wire_errors,
            process_validity=validity,
            process_candidate_usable=bool(process_usable and validity == "valid"),
            projection_usable=projection_usable,
            failure_codes=codes,
            finish_reason=artifact["finish_reason"],
            max_output_tokens=request["max_output_tokens"],
            completion_tokens=artifact["usage"]["completion_tokens"],
            historical_verdicts_changed=False,
            JSON_repaired=False,
        ),
    )
