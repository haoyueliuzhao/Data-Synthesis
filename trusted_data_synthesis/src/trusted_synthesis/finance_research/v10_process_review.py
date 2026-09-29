"""Prospective compact process annotation; no provider, wallet or training entry.

Record integrity, benchmark outcomes, critical process judgment and annotation
success are separate. No V8/V9 result is reclassified by this candidate contract.
"""

from __future__ import annotations

import copy
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import Episode, digest
from .qwen_protocol import strict_json_decoder
from .v6_task import public_trajectory_view

WIRE = "v10_compact_process_review.v1"
MANIFEST_SCHEMA = "v10_source_span_supervision.v1"
INTEGRITY_CHECKS = (
    "sealed",
    "calls_settled",
    "history_complete",
    "actions_observations_bound",
    "private_reference_isolated",
)


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Locator(Record):
    segment_id: str
    start: int
    end: int
    quote: str


class Assessment(Record):
    status: Literal["supported", "critical_error", "unknown", "not_applicable"]
    summary: str = Field(min_length=1)
    evidence: list[Locator]


class CriticalProcess(Record):
    evidence_and_operations: Assessment
    observation_interpretation: Assessment
    unwithdrawn_critical_contradictions: Assessment
    actual_revisions: Assessment


class Behavior(Record):
    description: str = Field(min_length=1)
    evidence: list[Locator] = Field(min_length=1)


class Supervision(Locator):
    decision: Literal["positive", "context_only", "unreviewed"]
    reason: str = Field(min_length=1)


class ProcessReviewOutput(Record):
    process: CriticalProcess
    behavior: Behavior
    supervision: list[Supervision]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bound(value):
    return {**value, "id": digest(value)}


def policy_definition():
    return bound(
        dict(
            schema="v10_compact_process_policy.v1",
            status="prospective_offline_candidate",
            model="deepseek-flash",
            annotation_strategy="requires_separate_prospective_registration",
            minimum_reviewers_mathematically_required=None,
            native_execution_and_program_accuracy_separate=True,
            public_initial_sources_are_available_without_read_source=True,
            no_narration_regex=True,
            no_proposition_graph=True,
            no_answer_reachability_gate=True,
            exploration_not_automatically_invalid=True,
            omitted_spans="unreviewed_zero_target_context",
            positive_actions="explicit_full_original_arguments_of_actual_successful_action_only",
            supervision_authority="one_validated_annotation_record",
            raw_history_SFT_mask_and_feedback_TokenReceipt_are_distinct=True,
            previous_review_results_reclassified=False,
            production_authorized=False,
        )
    )


def rubric():
    return """Review the actual public FinQA solving process, not a reconstructed proof.
The complete immutable trajectory contains initial public question/table/text,
chronological public explanations, actual action arguments and real observations.
Initial sources are already visible: do not demand a read_source call. A submit_program
is the current final contract; do not demand answer/scale/result_id, a reference DAG,
endpoint/movement routes, or equivalence to a unique author program. Native execution
and program metrics are handled separately and are not supplied as an oracle here.

Return one compact process record via submit_review. Assess four critical dimensions:
* evidence_and_operations: supported only when the key evidence and operations fit
  the task; cite necessary exact original locations. This dimension is never N/A.
* observation_interpretation: whether actual observations were understood accurately;
  not_applicable is allowed when no prior observation needed interpreting.
* unwithdrawn_critical_contradictions: supported means checked and NO critical
  unwithdrawn contradiction; critical_error means one exists; unknown means unclear.
  This dimension is never N/A. Corrected/withdrawn earlier mistakes are not automatically
  an unwithdrawn contradiction. Do not erase their original history.
* actual_revisions: supported when a claimed material revision was actually expressed
  and reflected in subsequent behavior; not_applicable when no revision is observed
  or needed. Do not force U/Q, checking, mistakes or revisions into a direct solution.

critical_error requires an actual critical problem with original evidence, not an
annotation difficulty. Any unresolved critical ambiguity, including a mixed claim
that cannot be judged, is unknown. Tool success proves execution, not sound reasoning.
Use concise summaries and necessary locators, not per-sentence propositions, terms,
nodes, edges or an all-nodes-to-answer proof. Exploration or a rejected alternative
need not lie on a final support chain and does not alone invalidate the process.
Describe actual semantic behavior (evidence choice, derivation, checking, revision and
consequences) with necessary original pointers. Do not classify by hashes, temporary
IDs, length, wording style or tool-call counts. Mere 'R' labels and narration are not
proof of substantive reasoning. Ordinary procedural intentions need no financial
proposition or finite English regex; factual assertions still need semantic review.

Provide ONE source-span supervision decision. Positive spans are explicitly reviewed
learnable public reasoning/recovery or actions; context_only preserves procedural,
wrong/withdrawn or otherwise non-target history; unreviewed is never positive. Omitted
text is unreviewed zero-target context, not silently correct. If omitted/mixed unknown
content is critical, the corresponding process assessment must remain unknown.
Public-content spans may be coarse contiguous intervals. Action-argument positivity
requires the WHOLE exact original argument string and an actual non-error tool event;
partial arguments must not approve the full action. Sources and observations remain
inputs, never SFT targets. Reasoning must not be discarded merely to ease annotation;
all-masked reasoning will be reported. Retain every original character regardless of
mask. This SFT decision is NOT a local feedback TokenReceipt or sampled-token mask.
"""


def strict_tool(view):
    schema = ProcessReviewOutput.model_json_schema()
    definitions = schema.get("$defs", {})
    segments = [d["segment_id"] for d in view["segments"]]

    def inline(value, name=None):
        if "$ref" in value:
            return inline(definitions[value["$ref"].removeprefix("#/$defs/")], name)
        result = {k: copy.deepcopy(value[k]) for k in ("type", "enum") if k in value}
        if value.get("type") == "object":
            props = {k: inline(v, k) for k, v in value["properties"].items()}
            result.update(properties=props, required=list(props), additionalProperties=False)
        elif value.get("type") == "array":
            result["items"] = inline(value["items"])
        elif name == "segment_id":
            result["enum"] = segments
        return result

    return dict(
        type="function", function=dict(name="submit_review", strict=True, parameters=inline(schema))
    )


def prepare_process_request(
    episode: Episode, *, slot_id, native_result, integrity, reviewer=0, policy=None
):
    require(type(reviewer) is int and reviewer >= 0, "reviewer is a registered strategy coordinate")
    require(isinstance(slot_id, str) and bool(slot_id), "original slot identity required")
    require(isinstance(native_result, dict), "retain the separate original native outcome")
    require(
        isinstance(integrity, dict)
        and all(
            k in integrity and (type(integrity[k]) is bool or integrity[k] is None)
            for k in INTEGRITY_CHECKS
        ),
        "external mechanical checks must explicitly retain unknown values",
    )
    policy = policy_definition() if policy is None else policy
    require(
        policy == policy_definition(), "register changed policy separately; no implicit variant"
    )
    view = public_trajectory_view(episode, slot_id=slot_id)
    payload = dict(wire_protocol=WIRE, policy=policy, reviewer=reviewer, trajectory=view)
    messages = [
        dict(role="system", content=rubric()),
        dict(role="user", content=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
    ]
    tool = strict_tool(view)
    return bound(
        dict(
            schema="v10_process_review_request.v1",
            wire_protocol=WIRE,
            model="deepseek-flash",
            policy=policy,
            policy_id=policy["id"],
            reviewer=reviewer,
            slot_id=slot_id,
            episode_sha256=digest(episode),
            view_id=view["view_id"],
            trajectory=view,
            native_result=copy.deepcopy(native_result),
            integrity=copy.deepcopy(integrity),
            external_integrity_evidence_verified_here=False,
            messages=messages,
            strict_tool=tool,
            messages_sha256=digest(messages),
            strict_tool_sha256=digest(tool),
            native_and_private_reference_visible_to_reviewer=False,
            actual_model_call_receipt_verified=False,
            production_authorized=False,
        )
    )


def _checked_request(request):
    require(
        request.get("id") == digest({k: v for k, v in request.items() if k != "id"}),
        "request record changed",
    )
    require(
        request.get("schema") == "v10_process_review_request.v1"
        and request.get("wire_protocol") == WIRE
        and request.get("model") == "deepseek-flash"
        and request.get("policy") == policy_definition()
        and request.get("policy_id") == policy_definition()["id"],
        "not the prospective compact policy; do not reinterpret older reviews",
    )
    view = request["trajectory"]
    require(
        view["view_id"]
        == "public_trajectory:" + digest({k: v for k, v in view.items() if k != "view_id"})
        and view["view_id"] == request["view_id"]
        and view["episode_sha256"] == request["episode_sha256"]
        and view["slot_id"] == request["slot_id"],
        "original public view binding changed",
    )
    payload = dict(
        wire_protocol=WIRE, policy=request["policy"], reviewer=request["reviewer"], trajectory=view
    )
    expected_messages = [
        dict(role="system", content=rubric()),
        dict(role="user", content=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
    ]
    require(
        request["messages"] == expected_messages
        and request["messages_sha256"] == digest(expected_messages)
        and request["strict_tool"] == strict_tool(view)
        and request["strict_tool_sha256"] == digest(request["strict_tool"]),
        "original process request/strict schema changed",
    )
    return view


def _locator(location, documents):
    doc = documents.get(location.segment_id)
    require(
        doc is not None
        and 0 <= location.start < location.end <= len(doc["text"])
        and doc["text"][location.start : location.end] == location.quote,
        "locator is not exact original text",
    )
    return doc


def _validate_annotation(value, view):
    documents = {d["segment_id"]: d for d in view["segments"]}
    checks = value.process.model_dump()
    for name, check in checks.items():
        if name in {"evidence_and_operations", "unwithdrawn_critical_contradictions"}:
            require(
                check["status"] != "not_applicable", "critical dimension cannot be unassessed N/A"
            )
        if (name == "evidence_and_operations" and check["status"] == "supported") or check[
            "status"
        ] == "critical_error":
            require(
                bool(check["evidence"]), "key supported evidence/error requires original locators"
            )
        for evidence in getattr(value.process, name).evidence:
            _locator(evidence, documents)
    for evidence in value.behavior.evidence:
        _locator(evidence, documents)
    actions = {a["arguments_segment_id"]: a for t in view["turns"] for a in t["actions"]}
    events = {e["event_id"]: e for e in view["events"]}
    intervals = {}
    for decision in value.supervision:
        doc = _locator(decision, documents)
        require(
            doc["kind"] in {"public_content", "action_arguments"},
            "sources/observations are input-only, not a supervision target",
        )
        for start, end in intervals.get(decision.segment_id, []):
            require(
                decision.end <= start or end <= decision.start,
                "one authority cannot assign overlapping source-span decisions",
            )
        intervals.setdefault(decision.segment_id, []).append((decision.start, decision.end))
        if doc["kind"] == "action_arguments" and decision.decision == "positive":
            action = actions[decision.segment_id]
            event = events.get(action["event_id"])
            require(
                decision.start == 0
                and decision.end == len(doc["text"])
                and event is not None
                and not event["is_error"],
                "positive action requires whole original arguments and actual success",
            )
    statuses = {c["status"] for c in checks.values()}
    return (
        "invalid"
        if "critical_error" in statuses
        else "unknown"
        if "unknown" in statuses
        else "valid"
    )


def inspect_process_review(raw: str, request):
    view = _checked_request(request)
    require(isinstance(raw, str), "preserve the original annotation text, not an invented dict")
    error, parsed, validity = None, None, "unknown"
    try:
        value = ProcessReviewOutput.model_validate(strict_json_decoder().decode(raw))
        validity = _validate_annotation(value, view)
        parsed = value.model_dump(mode="json")
    except (ValueError, TypeError, KeyError) as failure:
        error = f"{type(failure).__name__}: {failure}"
    checks = request["integrity"]
    integrity_status = (
        "verified_by_external_checks"
        if all(checks[k] is True for k in INTEGRITY_CHECKS)
        else "failed_external_checks"
        if any(checks[k] is False for k in INTEGRITY_CHECKS)
        else "unknown_external_checks"
    )
    return bound(
        dict(
            schema="v10_process_review_inspection.v1",
            policy_id=request["policy_id"],
            episode_sha256=request["episode_sha256"],
            view_id=view["view_id"],
            slot_id=request["slot_id"],
            request_id=request["id"],
            request=copy.deepcopy(request),
            raw_review=raw,
            review_status="annotation_succeeded" if error is None else "annotation_failed",
            annotation_failure_reason=error,
            process_validity=validity,
            parsed=parsed,
            record_integrity_status=integrity_status,
            native_result=request["native_result"],
            semantic_truth_proved=False,
            actual_model_call_receipt_verified=False,
            external_integrity_evidence_verified_here=False,
            annotation_origin="offline_candidate_contract_not_production_evidence",
            training_material_admitted=False,
            historical_judgments_reclassified=False,
        )
    )


def supervision_manifest(inspection):
    require(
        inspection.get("schema") == "v10_process_review_inspection.v1"
        and inspection.get("id") == digest({k: v for k, v in inspection.items() if k != "id"}),
        "one original validated annotation authority is required",
    )
    rebuilt = inspect_process_review(inspection["raw_review"], inspection["request"])
    require(rebuilt == inspection, "authority must reproduce from original request and annotation")
    view = inspection["request"]["trajectory"]
    documents = {d["segment_id"]: d for d in view["segments"]}
    actions = {a["arguments_segment_id"]: a for t in view["turns"] for a in t["actions"]}
    content, positive_actions = [], []
    gate = (
        inspection["review_status"] == "annotation_succeeded"
        and inspection["process_validity"] == "valid"
        and inspection["record_integrity_status"] == "verified_by_external_checks"
    )
    decisions = inspection["parsed"]["supervision"] if inspection["parsed"] else []
    for index, decision in enumerate(decisions):
        if not gate or decision["decision"] != "positive":
            continue
        if documents[decision["segment_id"]]["kind"] == "public_content":
            content.append(
                dict(
                    original_segment_id=decision["segment_id"],
                    start=decision["start"],
                    end=decision["end"],
                    quote=decision["quote"],
                    layer="reason",
                    authority_decision_index=index,
                )
            )
        else:
            positive_actions.append(actions[decision["segment_id"]]["action_id"])
    original_reason_chars = sum(
        len(d["text"]) for d in documents.values() if d["kind"] == "public_content"
    )
    positive_reason_chars = sum(s["end"] - s["start"] for s in content)
    return bound(
        dict(
            schema=MANIFEST_SCHEMA,
            version=1,
            policy_id=inspection["policy_id"],
            review_policy_id=inspection["policy_id"],
            episode_sha256=inspection["episode_sha256"],
            view_id=inspection["view_id"],
            slot_id=inspection["slot_id"],
            review_status=inspection["review_status"],
            process_validity=inspection["process_validity"],
            record_integrity_status=inspection["record_integrity_status"],
            native_result=inspection["native_result"],
            supervision_source_record_id=inspection["id"],
            supervision_source_record_ids=[inspection["id"]],
            authority_record=copy.deepcopy(inspection),
            positive_content_spans=content,
            positive_action_ids=positive_actions,
            positive_action_decision_indices={
                actions[d["segment_id"]]["action_id"]: i
                for i, d in enumerate(decisions)
                if gate and d["decision"] == "positive" and d["segment_id"] in actions
            },
            omitted_spans_are_unreviewed=True,
            raw_history_unchanged=True,
            original_public_content_characters=original_reason_chars,
            positive_public_content_characters=positive_reason_chars,
            public_reasoning_all_masked=original_reason_chars > 0 and positive_reason_chars == 0,
            arbitrary_minimum_reason_tokens_required=False,
            not_a_TokenReceipt=True,
            actual_model_call_receipt_verified=False,
            external_integrity_evidence_verified_here=False,
            annotation_origin=inspection["annotation_origin"],
            production_authorized=False,
            training_material_admitted=False,
        )
    )


def validate_manifest(episode: Episode, manifest):
    require(
        manifest.get("schema") == MANIFEST_SCHEMA
        and manifest.get("id") == digest({k: v for k, v in manifest.items() if k != "id"}),
        "not a bound prospective source-span manifest",
    )
    view = public_trajectory_view(episode, slot_id=manifest.get("slot_id"))
    require(
        manifest.get("episode_sha256") == digest(episode)
        and manifest.get("view_id") == view["view_id"]
        and manifest.get("authority_record", {}).get("request", {}).get("trajectory") == view,
        "manifest/authority differs from the actual original Episode",
    )
    require(
        supervision_manifest(manifest["authority_record"]) == manifest,
        "manifest targets must derive exactly from their unique source-span authority",
    )
    return manifest
