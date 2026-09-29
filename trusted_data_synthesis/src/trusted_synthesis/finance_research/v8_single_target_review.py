"""V8 one-authority target judgment, finite semantics, consensus and CPU encoding.

All projections below are mechanical and prospective. The reviewer decides every
target label once; tool success never supplies approval. No API calls here.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from types import SimpleNamespace
from typing import Literal

from pydantic import Field

from . import v6_state_alignment as alignment_base
from .contracts import digest
from .semantic_review import (
    SOURCE_KINDS,
    TARGET_KINDS,
    NonassertiveSlotReview,
    ReviewError,
    Term,
    _meaning_terms,
    _Record,
    _strict_json,
    _validate_slot,
    document_index,
)
from .v6_compact_review import CompactEdge, CompactNode, CompactProposition, CompactUpdate
from .v6_compact_review import fragment_ranges as old_ranges
from .v6_encoding import encode_reviewed_probe_for_student as encode_base
from .v6_slot_review import slot_rubric as old_rubric
from .v6_task import public_trajectory_view
from .v7_review_coherence import COHERENCE_APPENDIX
from .v8_review_policy import (
    ACTION_FIELDS,
    ALIGNMENT_WIRE,
    NONASSERTIVE_POLICY,
    REVIEW_WIRE,
    nonassertive_fragment_kind,
    policy_definition,
)

ENCODING_POLICY = "v8_single_authoritative_targets.v1"


class AnchoredTerm(Term):
    source_doc_ids: list[str] = Field(alias="public_source_anchor_ids")


class Claim(CompactProposition):
    text: list[str] = Field(alias="model_claim_ids")
    support: list[str] = Field(alias="support_evidence_ids")
    retraction: list[str] = Field(alias="retraction_model_ids")


class Node(CompactNode):
    source_doc_ids: list[str] = Field(alias="public_source_anchor_ids")


class TargetJudgment(_Record):
    label: Literal["approved", "retracted", "unknown", "nonassertive_context"]
    proposition_ids: list[str]
    evidence: list[str]


class SingleTargetOutput(_Record):
    terms: list[AnchoredTerm]
    nodes: list[Node]
    edges: list[CompactEdge]
    v_trace: Literal["valid", "invalid", "unknown"]
    reason_codes: list[str]
    coverage_complete: bool
    propositions: list[Claim]
    updates: list[CompactUpdate]
    targets: dict[str, TargetJudgment]


def require(condition, message):
    if not condition:
        raise ReviewError(message)


def fragment_ranges(text, kind):
    if kind == "action_arguments":
        return [(0, len(text))] if text else []
    if kind != "public_content":
        return old_ranges(text)
    boundaries = [m.end() for m in re.finditer(r";[ \t]*|\n+|[.!?][\"')\]]*\s+", text)]
    boundaries.append(len(text))
    result, start = [], 0
    for end in sorted(set(boundaries)):
        result.extend((start + left, start + right) for left, right in old_ranges(text[start:end]))
        start = end
    return result


def _action_contract(doc):
    try:
        value = _strict_json(doc["text"])
    except (ValueError, ReviewError):
        return False
    fields = ACTION_FIELDS.get(doc.get("action_name"))
    return (
        fields is not None
        and isinstance(value, dict)
        and set(value) == set(fields)
        and all(isinstance(value[k], str) for k in fields)
    )


def catalog(docs, *, typed=True):
    public, spans, first, counts = {}, {}, {}, Counter()
    prefixes = dict(
        question="src",
        source_text="src",
        source_table_cell="src",
        public_content="text",
        action_arguments="action",
        tool_observation="obs",
        unparsed_tool_call="raw",
    )
    for doc_id in sorted(docs):
        doc = docs[doc_id]
        for start, end in fragment_ranges(doc["text"], doc["kind"]):
            prefix = prefixes[doc["kind"]]
            eid = f"{prefix}_{counts[prefix]}" if typed else f"e{len(spans)}"
            counts[prefix] += 1
            first.setdefault(doc_id, eid)
            spans[eid] = dict(doc_id=doc_id, start=start, end=end, quote=doc["text"][start:end])
            item = dict(text=doc["text"][start:end], kind=doc["kind"], slot_id=doc["slot_id"])
            for name in (
                "source_id",
                "turn_index",
                "event_index",
                "action_name",
                "is_error",
                "actual_event_present",
                "actual_event_success",
            ):
                if name in doc:
                    item[name] = doc[name]
            if doc["kind"] == "action_arguments":
                item["registered_action_fields_only"] = _action_contract(doc)
            public[eid] = item
    for eid, span in spans.items():
        doc = docs[span["doc_id"]]
        if "observes_action_doc_id" in doc:
            require(doc["observes_action_doc_id"] in first, "observation lost its original action")
            public[eid]["observes_action_id"] = first[doc["observes_action_doc_id"]]
    return public, dict(spans=spans)


def strict_tool(public):
    schema = SingleTargetOutput.model_json_schema()
    definitions = schema.get("$defs", {})
    sources = [e for e, d in public.items() if d["kind"] in SOURCE_KINDS]
    targets = [e for e, d in public.items() if d["kind"] in TARGET_KINDS]
    groups = dict(
        public_source_anchor_ids=sources,
        model_claim_ids=targets,
        retraction_model_ids=targets,
        support_evidence_ids=list(public),
        evidence=list(public),
        nonredundancy_evidence=list(public),
        action_doc_id=[e for e, d in public.items() if d["kind"] == "action_arguments"],
        observation_doc_id=[e for e, d in public.items() if d["kind"] == "tool_observation"],
    )

    def inline(value, name=None):
        if "$ref" in value:
            return inline(definitions[value["$ref"].removeprefix("#/$defs/")], name)
        result = {
            key: copy.deepcopy(value[key]) for key in ("type", "enum", "pattern") if key in value
        }
        if value.get("type") == "object":
            props = {key: inline(child, key) for key, child in value.get("properties", {}).items()}
            result.update(properties=props, required=list(props), additionalProperties=False)
        if value.get("type") == "array":
            result["items"] = inline(value["items"])
            if groups.get(name):
                result["items"] = dict(type="string", enum=groups[name])
        if value.get("type") == "string" and groups.get(name):
            result["enum"] = groups[name]
        return result

    parameters = inline(schema)
    target_template = inline(schema["properties"]["targets"]["additionalProperties"])
    target_properties = {}
    for eid in targets:
        item = copy.deepcopy(target_template)
        if public[eid]["kind"] == "action_arguments":
            item["properties"]["label"]["enum"] = ["approved", "retracted", "unknown"]
        target_properties[eid] = item
    parameters["properties"]["targets"] = dict(
        type="object", properties=target_properties, required=targets, additionalProperties=False
    )
    return dict(
        type="function", function=dict(name="submit_review", strict=True, parameters=parameters)
    )


def rubric(reviewer):
    base = old_rubric(reviewer)
    # The prior substantive paragraphs remain, but the old redundant output and
    # narrow Q-only mask contract are explicitly replaced by this frozen policy.
    base = base[: base.index("\nLOCATORS:")]
    return (
        base
        + """
V8 NEW SINGLE-AUTHORITY TARGET POLICY:
Return one object with root terms,nodes,edges,v_trace,reason_codes,coverage_complete,
propositions,updates,targets. There is NO actions table, mask table, or semantic_graph
wrapper. targets has EVERY prelisted original target key exactly once. Each record
has label,proposition_ids,evidence. Judge that exact target's positive-supervision
eligibility ONCE; the host derives action judgment and mask from that same record.
Successful execution is necessary for a positive action but never automatically
approves it. Approving an action never approves another R/U/content target.

Typed IDs src_* are original public sources, text_* the model's actual public text,
action_* atomic original tool arguments, obs_* actual observations, raw_* unparsed
original calls. Source-anchor fields accept src_* only. A read_source observation
is still obs_*; derived terms anchor their original source inputs, not a claim that
their computed result appeared verbatim there. Cite actual calculations in evidence.
Terms/nodes use public_source_anchor_ids. Propositions use model_claim_ids,
support_evidence_ids,retraction_model_ids. Edges name NODE IDs, not TERM IDs.

All public content is partitioned at original sentence/newline/semicolon positions;
no character or history is removed. Judge each fragment, including mixed fragments.
Action arguments are atomic ONLY under their registered fields; extra reason or
rationale fields cannot hide unreviewed reasoning inside an approved action.
targets includes the entire original public content and every original action.
Approved targets require actual reviewed supported proposition binding and evidence.
Retracted/unknown critical claims are never positive; an unsupported key claim makes
v_trace unknown, and an unretracted critical contradiction invalid.

You may explicitly label a whole text_* fragment nonassertive_context only for an
empty Q/U None or N/A optional field, or ordinary procedural intention such as
"submitting the predicted program." Such context has empty proposition_ids and
ZERO target loss. It stays in the history and creates no state or chi. Do not invent
a financial proposition for it. The frozen whole-fragment domain is supplied in
review_policy.nonassertive; unrecognized or mixed text is unknown. Amounts, periods,
formulas, source judgments, "verified", "correct result" and ambiguous mixtures
are NOT exempt. No action_* or observation is nonassertive_context.
An empty Q clause before a semicolon and a separate procedural clause are separate
original fragments, not an edited/truncated original response.

All critical reasoning, explicit withdrawals, genuine action/observation updates,
accepted semantic graphs and consequential chi conditions remain in force. Neither
more tools nor length creates a state. Do not force an error or verification.
There is no host repair, missing-target completion, cross-review mask intersection
or deletion of a hard-to-map jointly qualified package. Two isolated same-model
reviews are not independent experts or mathematical proof.
"""
        + COHERENCE_APPENDIX
    )


def slot_review_request(prepared, slot_id, reference, reviewer=0):
    bundle = prepared.get("bundle", prepared)
    require(type(reviewer) is int and reviewer in (0, 1), "two registered reviewer contexts only")
    require(slot_id in {s["slot_id"] for s in bundle["slots"]}, "unregistered original slot")
    docs = {k: d for k, d in document_index(bundle).items() if d["slot_id"] in (None, slot_id)}
    public, local = catalog(docs)
    policy = policy_definition()
    reference = reference.model_dump(mode="json") if hasattr(reference, "model_dump") else reference
    require(isinstance(reference, dict), "offline author reference required, never a public source")
    payload = dict(
        wire_protocol=REVIEW_WIRE,
        task_id=bundle["task_id"],
        slot_id=slot_id,
        reviewer=reviewer,
        task_bundle_sha256=digest(bundle),
        document_catalog=public,
        review_policy=policy,
        review_only_private_reference=reference,
    )
    messages = [
        dict(role="system", content=rubric(reviewer)),
        dict(role="user", content=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
    ]
    tool = strict_tool(public)
    return dict(
        wire_protocol=REVIEW_WIRE,
        model="deepseek-flash",
        reviewer=reviewer,
        task_id=bundle["task_id"],
        slot_id=slot_id,
        task_bundle_sha256=digest(bundle),
        document_index=docs,
        document_catalog=public,
        compact_catalog=local,
        catalog_sha256=digest(public),
        compact_catalog_sha256=digest(local),
        review_policy_id=policy["id"],
        messages=messages,
        strict_tool=tool,
        strict_tool_sha256=digest(tool),
        rubric_sha256=digest(messages[0]["content"]),
        messages_model_sha256=digest(dict(model="deepseek-flash", messages=messages)),
        private_reference_for_review_only=True,
        other_reviewer_output_visible=False,
        other_slot_trajectories_visible=False,
    )


def capacity_features(request):
    public = request["document_catalog"]
    return dict(
        target_fragment_count=sum(d["kind"] in TARGET_KINDS for d in public.values()),
        action_count=sum(d["kind"] == "action_arguments" for d in public.values()),
        target_chars=sum(len(d["text"]) for d in public.values() if d["kind"] in TARGET_KINDS),
        public_content_chars=sum(
            len(d["text"]) for d in public.values() if d["kind"] == "public_content"
        ),
        request_content_chars=sum(len(m["content"]) for m in request["messages"]),
        strict_tool_chars=len(json.dumps(request["strict_tool"])),
        exact_api_tokens_known=False,
    )


def _checked_request(request):
    require(
        request.get("wire_protocol") == REVIEW_WIRE and request.get("model") == "deepseek-flash",
        "wrong v8 review protocol/model",
    )
    require(
        request.get("review_policy_id") == policy_definition()["id"], "v8 frozen policy changed"
    )
    docs = request["document_index"]
    require(
        all(d["slot_id"] in (None, request["slot_id"]) for d in docs.values()), "other slot leaked"
    )
    public, local = catalog(docs)
    messages = request["messages"]
    payload = _strict_json(messages[1]["content"])
    require(
        public == request["document_catalog"] == payload["document_catalog"]
        and local == request["compact_catalog"]
        and digest(public) == request["catalog_sha256"]
        and digest(local) == request["compact_catalog_sha256"]
        and payload["review_policy"] == policy_definition()
        and payload["slot_id"] == request["slot_id"]
        and payload["reviewer"] == request["reviewer"]
        and payload["task_bundle_sha256"] == request["task_bundle_sha256"]
        and payload["wire_protocol"] == REVIEW_WIRE,
        "v8 exact source/target/coordinate binding differs",
    )
    require(
        messages[0]["content"] == rubric(request["reviewer"])
        and digest(messages[0]["content"]) == request["rubric_sha256"]
        and digest(dict(model="deepseek-flash", messages=messages))
        == request["messages_model_sha256"]
        and strict_tool(public) == request["strict_tool"]
        and digest(request["strict_tool"]) == request["strict_tool_sha256"],
        "v8 wire/rubric/schema changed",
    )
    return docs, local


def validate_slot_review(raw, request):
    try:
        docs, local = _checked_request(request)
        value = SingleTargetOutput.model_validate(_strict_json(raw)).model_dump()
        expected = {e for e, d in request["document_catalog"].items() if d["kind"] in TARGET_KINDS}
        require(
            set(value["targets"]) == expected, "single authoritative targets missing or invented"
        )

        def evidence(ids):
            require(all(e in local["spans"] for e in ids), "unknown original evidence ID")
            return [copy.deepcopy(local["spans"][e]) for e in ids]

        def doc(eid, kinds):
            span = evidence([eid])[0]
            require(docs[span["doc_id"]]["kind"] in kinds, "wrong original evidence kind")
            return span["doc_id"]

        terms = value.pop("terms")
        for term in terms:
            term["source_doc_ids"] = [doc(e, SOURCE_KINDS) for e in term["source_doc_ids"]]
        for prop in value["propositions"]:
            for field in ("text", "retraction"):
                for eid in prop[field]:
                    doc(eid, TARGET_KINDS)
            for field in ("text", "support", "retraction"):
                prop[field] = evidence(prop[field])
        for update in value["updates"]:
            update["action_doc_id"] = doc(update["action_doc_id"], {"action_arguments"})
            update["observation_doc_id"] = doc(update["observation_doc_id"], {"tool_observation"})
            require(
                docs[update["observation_doc_id"]].get("observes_action_doc_id")
                == update["action_doc_id"],
                "update observation is not from its original action",
            )
            for field in ("evidence", "nonredundancy_evidence"):
                update[field] = evidence(update[field])
        for node in value["nodes"]:
            node["source_doc_ids"] = [doc(e, SOURCE_KINDS) for e in node["source_doc_ids"]]
            node["evidence"] = evidence(node["evidence"])
        for edge in value["edges"]:
            edge["evidence"] = evidence(edge["evidence"])
        targets = value.pop("targets")
        actions, masks, policy_errors = [], [], []
        for eid, target in targets.items():
            span = evidence([eid])[0]
            original = docs[span["doc_id"]]
            support = evidence(target["evidence"])
            if target["label"] == "approved" and not support:
                policy_errors.append("approved_target_requires_reviewed_evidence")
            if original["kind"] == "action_arguments":
                require(
                    target["label"] != "nonassertive_context",
                    "action is not a zero-context prose field",
                )
                if target["label"] == "approved" and not _action_contract(original):
                    policy_errors.append(
                        "extra_or_unregistered_action_fields_cannot_be_atomically_approved"
                    )
                actions.append(
                    dict(
                        action_doc_id=span["doc_id"],
                        label=target["label"],
                        proposition_ids=target["proposition_ids"],
                        evidence=support,
                    )
                )
                component = "final" if original.get("action_name") == "submit_program" else "action"
            else:
                component = "reason"
            masks.append(
                span
                | dict(
                    label=target["label"],
                    component=component,
                    proposition_ids=target["proposition_ids"],
                )
            )
        value.update(
            slot_id=request["slot_id"],
            actions=actions,
            mask=masks,
            semantic_graph=dict(nodes=value.pop("nodes"), edges=value.pop("edges")),
        )
        slot = NonassertiveSlotReview.model_validate(value)
        parsed = dict(terms=terms, slot=slot.model_dump(), target_judgments=targets)
        derived, meanings, error = None, None, None
        try:
            require(not policy_errors, ";".join(policy_errors))
            meanings = _meaning_terms(
                SimpleNamespace(terms=[Term.model_validate(t) for t in terms]), docs
            )
            derived = _validate_slot(
                slot,
                docs,
                meanings,
                allow_nonassertive_context=True,
                nonassertive_policy=NONASSERTIVE_POLICY,
            )
        except ReviewError as failure:
            error = str(failure)
    except ReviewError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError) as failure:
        raise ReviewError(f"v8 interface {type(failure).__name__}: {failure}") from failure
    return dict(
        schema=REVIEW_WIRE,
        wire_protocol=REVIEW_WIRE,
        review_policy_id=request["review_policy_id"],
        reviewer=request["reviewer"],
        task_id=request["task_id"],
        slot_id=request["slot_id"],
        task_bundle_sha256=request["task_bundle_sha256"],
        interface_admitted=True,
        semantic_consistent=error is None,
        semantic_validation_error=error,
        reported_v_trace=slot.v_trace,
        v_trace=slot.v_trace if error is None else "unknown",
        parsed=parsed,
        derived=derived,
        terms=meanings,
        document_index=docs,
        raw_review_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        expanded_review_sha256=digest(parsed),
        review_request_sha256=digest(request),
        host_semantic_repair=False,
        action_and_mask_from_single_model_target=True,
        tool_success_automatically_approved=False,
        encoding_manifest=None,
        not_a_training_admission=True,
    )


def inspect_slot_review(raw, request):
    try:
        result = validate_slot_review(raw, request)
    except ReviewError as failure:
        return dict(
            interface_admitted=False,
            semantic_consistent=False,
            validation=None,
            error=str(failure),
            error_kind="mechanical_interface",
            wire_protocol=REVIEW_WIRE,
        )
    return dict(
        interface_admitted=True,
        semantic_consistent=result["semantic_consistent"],
        validation=result,
        error=result["semantic_validation_error"],
        error_kind=None if result["semantic_consistent"] else "semantic_inconsistency",
    )


def slot_review_record(request, artifact):
    _checked_request(request)
    require(
        artifact.get("wire_protocol") == REVIEW_WIRE
        and artifact.get("semantic_review_request_sha256") == digest(request),
        "unbound actual v8 artifact",
    )
    raw = artifact.get("review_text")
    assessment = (
        inspect_slot_review(raw, request)
        if artifact.get("finish_reason") == "tool_calls" and not artifact.get("review_format_error")
        else dict(
            interface_admitted=False,
            semantic_consistent=False,
            validation=None,
            error="non-normal strict response",
        )
    )
    if assessment["validation"] is not None:
        return assessment["validation"] | dict(actual_artifact_sha256=digest(artifact))
    return dict(
        wire_protocol=REVIEW_WIRE,
        review_policy_id=request["review_policy_id"],
        reviewer=request["reviewer"],
        task_id=request["task_id"],
        slot_id=request["slot_id"],
        task_bundle_sha256=request["task_bundle_sha256"],
        interface_admitted=False,
        semantic_consistent=False,
        v_trace="unknown",
        reported_v_trace=None,
        parsed=None,
        derived=None,
        document_index=request["document_index"],
        mechanical_validation_error=assessment["error"],
        raw_review_sha256=hashlib.sha256(raw.encode()).hexdigest()
        if isinstance(raw, str)
        else None,
        failed_request=copy.deepcopy(request),
        failed_artifact=copy.deepcopy(artifact),
        actual_artifact_sha256=digest(artifact),
        original_coordinate_retained=True,
    )


def _versioned_records(reviews):
    for item in reviews.values():
        require(
            item.get("wire_protocol") == REVIEW_WIRE
            and item.get("review_policy_id") == policy_definition()["id"],
            "mixed review policy/version",
        )
        if item.get("interface_admitted") is False:
            require(
                slot_review_record(item["failed_request"], item["failed_artifact"]) == item,
                "failed original review record changed",
            )
        if item["v_trace"] == "valid":
            require(
                item.get("semantic_consistent") is True and item.get("derived") is not None,
                "effective valid record lacks finite validation",
            )


def _alignment_baseline(prepared, reviews, reviewer):
    slots = alignment_base._slot_inputs(
        prepared, reviews, reviewer, allow_nonassertive_context=True
    )
    docs = document_index(prepared["bundle"])
    public, local = catalog(docs, typed=False)
    aliases = {f"s{i}": sid for i, sid in enumerate(slots)}
    reverse = {sid: alias for alias, sid in aliases.items()}
    for item in public.values():
        if item["slot_id"] is not None:
            item["slot_id"] = reverse[item["slot_id"]]
    local["slot_aliases"] = aliases
    own = alignment_base._own_eligible(prepared, reviews, slots)
    payload = dict(
        wire_protocol=alignment_base.WIRE_PROTOCOL,
        task_id=prepared["bundle"]["task_id"],
        reviewer=reviewer,
        task_bundle_sha256=digest(prepared["bundle"]),
        document_catalog=public,
        own_slot_judgments={
            reverse[sid]: alignment_base._summary(reviews[sid], local) for sid in slots
        },
        own_eligible_ids=[reverse[sid] for sid in own],
        pair_keys=list(alignment_base.PAIR_KEYS),
    )
    messages = [
        dict(role="system", content=alignment_base.alignment_rubric(reviewer)),
        dict(role="user", content=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
    ]
    tool = alignment_base._strict_tool(public)
    return dict(
        wire_protocol=alignment_base.WIRE_PROTOCOL,
        model="deepseek-flash",
        task_id=prepared["bundle"]["task_id"],
        reviewer=reviewer,
        messages=messages,
        task_bundle_sha256=digest(prepared["bundle"]),
        document_index=docs,
        document_catalog=public,
        compact_catalog=local,
        catalog_sha256=digest(public),
        compact_catalog_sha256=digest(local),
        strict_tool=tool,
        strict_tool_sha256=digest(tool),
        rubric_sha256=digest(messages[0]["content"]),
        messages_model_sha256=digest(dict(model="deepseek-flash", messages=messages)),
        private_reference_for_review_only=True,
        private_reference_in_alignment=False,
        other_reviewer_output_visible=False,
        own_eligible_slot_ids=own,
        slot_review_bindings={sid: digest(reviews[sid]) for sid in slots},
        own_slot_reviews=copy.deepcopy(reviews),
    )


def _alignment_request(base):
    alignment_base._checked_request(base, allow_nonassertive_context=True)
    _versioned_records(base["own_slot_reviews"])
    payload = _strict_json(base["messages"][1]["content"])
    payload.update(wire_protocol=ALIGNMENT_WIRE, review_policy_id=policy_definition()["id"])
    instruction = base["messages"][0]["content"] + (
        "\nV8: the only target judgments came from each original target exactly once. "
        "Model-labelled empty optional or ordinary procedural context is zero-supervision "
        "history, not a financial proposition or state/chi difference. Do not rejudge masks, "
        "drop a difficult jointly qualified package, demand identical temporary proposition "
        "IDs, or see the other reviewer's output. Original finer fragments remain unchanged."
    )
    messages = [
        dict(role="system", content=instruction),
        dict(role="user", content=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
    ]
    value = copy.deepcopy(base)
    value.update(
        wire_protocol=ALIGNMENT_WIRE,
        review_policy_id=policy_definition()["id"],
        messages=messages,
        rubric_sha256=digest(instruction),
        messages_model_sha256=digest(dict(model="deepseek-flash", messages=messages)),
        semantic_alignment_baseline=copy.deepcopy(base),
        semantic_alignment_baseline_sha256=digest(base),
    )
    return value


def alignment_request(prepared, reviews, reviewer=0):
    _versioned_records(reviews)
    return _alignment_request(_alignment_baseline(prepared, reviews, reviewer))


def validate_alignment(raw, request):
    require(request.get("wire_protocol") == ALIGNMENT_WIRE, "wrong v8 alignment wire")
    base = request["semantic_alignment_baseline"]
    require(
        digest(base) == request["semantic_alignment_baseline_sha256"], "v8 alignment base changed"
    )
    require(
        all(request.get(k) == v for k, v in _alignment_request(base).items()),
        "v8 alignment binding differs",
    )
    value = alignment_base.validate_alignment(raw, base, allow_nonassertive_context=True)
    value.update(
        schema=ALIGNMENT_WIRE,
        wire_protocol=ALIGNMENT_WIRE,
        review_policy_id=request["review_policy_id"],
        alignment_request_sha256=digest(request),
    )
    return value


def inspect_alignment(raw, request):
    try:
        value = validate_alignment(raw, request)
    except (ValueError, TypeError, KeyError, AttributeError) as failure:
        return dict(
            interface_admitted=False,
            semantic_consistent=False,
            validation=None,
            error=str(failure),
            error_kind="mechanical_interface",
            reviewer=request["reviewer"],
            task_bundle_sha256=request["task_bundle_sha256"],
            slot_review_bindings=request["slot_review_bindings"],
            pairs=None,
            raw_review_sha256=hashlib.sha256(raw.encode()).hexdigest()
            if isinstance(raw, str)
            else None,
        )
    return dict(
        interface_admitted=True,
        semantic_consistent=value["semantic_consistent"],
        validation=value,
        error=[
            p["semantic_validation_error"]
            for p in value["pairs"].values()
            if p["semantic_validation_error"]
        ]
        or None,
    )


def resolve_pair(prepared, side0, side1, alignment0, alignment1):
    for side in (side0, side1):
        _versioned_records(side)
    for alignment in (alignment0, alignment1):
        if alignment is not None and alignment.get("interface_admitted"):
            require(
                alignment.get("wire_protocol") == ALIGNMENT_WIRE
                and alignment.get("review_policy_id") == policy_definition()["id"],
                "mixed alignment policy",
            )
    value = alignment_base.resolve_decomposed_pair(
        prepared, side0, side1, alignment0, alignment1, allow_nonassertive_context=True
    )
    for sid, slot in value["slots"].items():
        manifest = slot["encoding_manifest"]
        if manifest is None:
            continue
        zero = []
        for span in side0[sid]["parsed"]["slot"]["mask"]:
            if span["label"] == "nonassertive_context":
                doc = side0[sid]["document_index"][span["doc_id"]]
                zero.append(
                    {k: span[k] for k in ("doc_id", "start", "end", "quote")}
                    | dict(
                        original_segment_id=doc["original_segment_id"],
                        label=span["label"],
                        layer="context",
                        proposition_ids=[],
                    )
                )
        manifest.update(
            review_policy_id=policy_definition()["id"],
            review_wire=REVIEW_WIRE,
            alignment_wire=ALIGNMENT_WIRE,
            encoding_policy=ENCODING_POLICY,
            nonassertive_context_spans=zero,
            nonassertive_context_target_loss=0,
        )
    unencoded = [
        sid
        for sid in value["valid_slots_retained"]
        if value["slots"][sid]["encoding_manifest"] is None
    ]
    value.update(
        schema="v8_common_material_resolution.v1",
        review_policy_id=policy_definition()["id"],
        review_wire=REVIEW_WIRE,
        alignment_wire=ALIGNMENT_WIRE,
        unencodable_jointly_qualified_slots=unencoded,
        common_kernel_material_ready=value["task_mapping"] == "complete" and not unencoded,
        no_mask_intersection=True,
        no_hard_case_deletion=True,
        actual_training=False,
    )
    return value


def encode_reviewed_probe_for_student(episode, manifest, tokenizer, **kwargs):
    require(
        manifest.get("review_policy_id") == policy_definition()["id"]
        and manifest.get("encoding_policy") == ENCODING_POLICY,
        "v8 encoder requires the complete policy-bound consensus manifest",
    )
    view = public_trajectory_view(episode, slot_id=manifest.get("slot_id"))
    docs = {d["segment_id"]: d for d in view["segments"]}
    for span in manifest["nonassertive_context_spans"]:
        original = docs.get(span["original_segment_id"])
        require(
            original is not None
            and original["kind"] == "public_content"
            and 0 <= span["start"] < span["end"] <= len(original["text"])
            and original["text"][span["start"] : span["end"]] == span["quote"]
            and nonassertive_fragment_kind(span["quote"]) is not None
            and span["label"] == "nonassertive_context"
            and not span["proposition_ids"],
            "zero-context label not bound to exact eligible original text",
        )
        for positive in manifest["positive_content_spans"]:
            require(
                span["original_segment_id"] != positive["original_segment_id"]
                or span["end"] <= positive["start"]
                or positive["end"] <= span["start"],
                "zero-context fragment overlaps positive supervision",
            )
    value = encode_base(episode, manifest, tokenizer, **kwargs)
    original_id = value.pop("encoding_id")
    value.update(
        schema="v8_student_encoding.v1",
        encoding_policy=ENCODING_POLICY,
        review_policy_id=policy_definition()["id"],
        underlying_encoding_id=original_id,
        nonassertive_context_target_loss=0,
        actual_model_calls=0,
    )
    return value | dict(encoding_id="v8_student_encoding:" + digest(value))
