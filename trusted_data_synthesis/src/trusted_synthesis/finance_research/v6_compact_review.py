"""Capacity-revised V6 review wire format; only source locators are compressed.

The host creates immutable, exhaustive public-text fragments BEFORE requesting a
review. A model selects their IDs, never computes character offsets or recopies
source text. Expansion is a mechanical lookup, not a semantic repair. The original
semantic validator and two-review resolver remain the qualification authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import Field

from .contracts import digest
from .semantic_review import (
    RUBRIC,
    ActionJudgment,
    Edge,
    Node,
    Proposition,
    Relation,
    ReviewError,
    Term,
    Update,
    _Record,
    _strict_json,
    document_index,
    validate_review,
)

WIRE_PROTOCOL = "v6_compact_review.v1"
FRAGMENT_TARGET = 200


class CompactProposition(Proposition):
    text: list[str]
    support: list[str]
    retraction: list[str]


class CompactNode(Node):
    evidence: list[str]


class CompactEdge(Edge):
    evidence: list[str]


class CompactGraph(_Record):
    nodes: list[CompactNode]
    edges: list[CompactEdge]


class CompactAction(ActionJudgment):
    evidence: list[str]


class CompactUpdate(Update):
    evidence: list[str]
    nonredundancy_evidence: list[str]


class CompactMask(_Record):
    span_id: str
    label: Literal["approved", "retracted", "unknown"]
    component: Literal["reason", "update", "action", "final"]
    proposition_ids: list[str]


class CompactSlot(_Record):
    slot_id: str
    v_trace: Literal["valid", "invalid", "unknown"]
    reason_codes: list[str]
    coverage_complete: bool
    propositions: list[CompactProposition]
    actions: list[CompactAction]
    updates: list[CompactUpdate]
    mask: list[CompactMask]
    semantic_graph: CompactGraph


class CompactRelation(Relation):
    evidence: list[str]


class CompactTaskReview(_Record):
    terms: list[Term]
    slots: list[CompactSlot] = Field(min_length=8, max_length=8)
    relations: list[CompactRelation] = Field(min_length=28, max_length=28)


def _require(condition, message):
    if not condition:
        raise ReviewError(message)


def fragment_ranges(text, *, atomic=False):
    """Partition without deleting punctuation/whitespace or judging propositions.

    Prefer sentence/newline boundaries, then whitespace near 200 codepoints.
    An individual unbroken token is never cut merely to meet the size target.
    Tool arguments stay atomic, preserving whole-action approval semantics.
    """
    if not text:
        return []
    if atomic:
        return [(0, len(text))]
    sentence_ends = [m.end() for m in re.finditer(r"[.!?][\"')\]]*\s+|\n+", text)]
    sentence_ends.append(len(text))
    ranges, cursor = [], 0
    for end in sorted(set(sentence_ends)):
        while end - cursor > FRAGMENT_TARGET:
            boundaries = [m.end() + cursor for m in re.finditer(r"\s+", text[cursor:end])]
            before = [i for i in boundaries if i <= cursor + FRAGMENT_TARGET]
            boundary = (
                max(before)
                if before
                else next((i for i in boundaries if i > cursor + FRAGMENT_TARGET), end)
            )
            ranges.append((cursor, boundary))
            cursor = boundary
        if end > cursor:
            ranges.append((cursor, end))
            cursor = end
    return ranges


def _catalog(docs):
    slots = sorted({doc["slot_id"] for doc in docs.values() if doc["slot_id"] is not None})
    _require(len(slots) == 8, "compact review requires all eight original slots")
    slot_aliases = {f"s{i}": sid for i, sid in enumerate(slots)}
    reverse_slots = {v: k for k, v in slot_aliases.items()}
    doc_aliases = {f"d{i}": name for i, name in enumerate(sorted(docs))}
    reverse_docs = {v: k for k, v in doc_aliases.items()}
    public, spans = {}, {}
    for alias, name in doc_aliases.items():
        doc = docs[name]
        parts = []
        for i, (start, end) in enumerate(
            fragment_ranges(doc["text"], atomic=doc["kind"] == "action_arguments")
        ):
            span_id = f"{alias}p{i}"
            quote = doc["text"][start:end]
            parts.append(dict(span_id=span_id, text=quote))
            spans[span_id] = dict(doc_id=name, start=start, end=end, quote=quote)
        value = dict(
            kind=doc["kind"],
            slot_id=reverse_slots.get(doc["slot_id"]),
            fragments=parts,
        )
        for key in (
            "source_id",
            "turn_index",
            "event_index",
            "action_name",
            "is_error",
            "actual_event_present",
            "actual_event_success",
        ):
            if key in doc:
                value[key] = doc[key]
        if "observes_action_doc_id" in doc:
            value["observes_action_doc_id"] = reverse_docs[doc["observes_action_doc_id"]]
        public[alias] = value
    local = dict(slot_aliases=slot_aliases, document_aliases=doc_aliases, spans=spans)
    return public, local


_OFFSET_PARAGRAPH = """Offsets are zero-based half-open Unicode codepoint offsets in
document_index[doc_id].text. quote must
equal that original substring."""
_MASK_PARAGRAPH = (
    "Partition EVERY character of each nonempty public_content and action_arguments document into\n"
    "nonoverlapping approved/retracted/unknown mask spans. "
    "Include original punctuation/whitespace in an\n"
    "adjacent span; never manufacture target text."
)


def compact_rubric(reviewer):
    _require(type(reviewer) is int and reviewer in (0, 1), "invalid reviewer coordinate")
    rubric = RUBRIC.replace(
        _OFFSET_PARAGRAPH,
        "Evidence is a list of original fragment IDs from document_catalog. Return ONLY those "
        "IDs, never quotes or character offsets. Each ID names an immutable exact public-text "
        "fragment. The host performs lookup only; it never supplies a missing semantic judgment.",
    ).replace(
        _MASK_PARAGRAPH,
        "Return exactly one mask entry for EVERY fragment of every nonempty public_content "
        "and action_arguments document of that slot. Do not omit, duplicate or merge IDs. "
        "Fragments are a mechanical text partition, not asserted propositions. If a fragment "
        "mixes supported and unsupported/retracted critical content, label the whole fragment "
        "unknown unless it is wholly justified as retracted; never approve an unsupported part. "
        "Do not mask source, observation or private-reference fragments. Never manufacture text.",
    )
    return rubric + (
        "\nCOMPACT FORMAT: document aliases d0,d1,... and slot aliases s0,...,s7 are only "
        "locators, not semantic identities. Use aliases in all doc/slot fields and fragment IDs "
        "in all evidence/text/support/retraction lists. Model output contains ONLY terms, slots, "
        "relations; request coordinates are bound by the host, not recopied by you. "
        "Keep all substantive judgment, proposition, graph, action and 28-pair fields. "
        f"Independent review context index: {reviewer}; no other review is provided."
    )


def compact_review_request(prepared_or_bundle, reference, reviewer=0):
    bundle = prepared_or_bundle.get("bundle", prepared_or_bundle)
    docs = document_index(bundle)
    document_catalog, compact_catalog = _catalog(docs)
    reference = reference.model_dump(mode="json") if hasattr(reference, "model_dump") else reference
    _require(isinstance(reference, dict), "explicit private offline reference required")
    rubric = compact_rubric(reviewer)
    bundle_hash = digest(bundle)
    payload = dict(
        wire_protocol=WIRE_PROTOCOL,
        task_id=bundle["task_id"],
        task_bundle_sha256=bundle_hash,
        reviewer=reviewer,
        slot_ids=list(compact_catalog["slot_aliases"]),
        document_catalog=document_catalog,
        review_only_private_reference=reference,
        output_schema=CompactTaskReview.model_json_schema(),
    )
    messages = [
        dict(role="system", content=rubric),
        dict(role="user", content=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
    ]
    return dict(
        wire_protocol=WIRE_PROTOCOL,
        model="deepseek-flash",
        messages=messages,
        reviewer=reviewer,
        document_index=docs,
        document_catalog=document_catalog,
        compact_catalog=compact_catalog,
        catalog_sha256=digest(document_catalog),
        compact_catalog_sha256=digest(compact_catalog),
        task_bundle_sha256=bundle_hash,
        rubric_sha256=digest(rubric),
        messages_model_sha256=digest(dict(model="deepseek-flash", messages=messages)),
        private_reference_for_review_only=True,
        other_reviewer_output_visible=False,
    )


def capacity_features(request):
    """Exact local sizes, not an assertion of DeepSeek tokenizer counts."""
    docs = request["document_index"]
    spans = request["compact_catalog"]["spans"]
    target_docs = {
        k: v for k, v in docs.items() if v["kind"] in {"public_content", "action_arguments"}
    }
    return dict(
        document_count=len(docs),
        original_document_chars=sum(len(d["text"]) for d in docs.values()),
        public_content_chars=sum(
            len(d["text"]) for d in docs.values() if d["kind"] == "public_content"
        ),
        target_chars=sum(len(d["text"]) for d in target_docs.values()),
        target_document_count=sum(bool(d["text"]) for d in target_docs.values()),
        target_fragment_count=sum(s["doc_id"] in target_docs for s in spans.values()),
        action_count=sum(d["kind"] == "action_arguments" for d in docs.values()),
        source_chars=sum(len(d["text"]) for d in docs.values() if d["slot_id"] is None),
        fragment_count=len(spans),
        request_content_chars=sum(len(m["content"]) for m in request["messages"]),
        exact_api_token_count_known=False,
    )


def _checked_catalog(request):
    _require(request.get("wire_protocol") == WIRE_PROTOCOL, "wrong compact wire protocol")
    _require(request.get("model") == "deepseek-flash", "review model must be deepseek-flash")
    docs = request["document_index"]
    public, local = _catalog(docs)
    _require(
        public == request["document_catalog"]
        and local == request["compact_catalog"]
        and digest(public) == request["catalog_sha256"]
        and digest(local) == request["compact_catalog_sha256"],
        "compact catalog does not exhaustively bind the original documents",
    )
    messages = request["messages"]
    _require(
        digest(dict(model="deepseek-flash", messages=messages)) == request["messages_model_sha256"]
        and messages[0]["content"] == compact_rubric(request["reviewer"])
        and digest(messages[0]["content"]) == request["rubric_sha256"],
        "compact request/rubric binding differs",
    )
    payload = _strict_json(messages[1]["content"])
    _require(
        payload["document_catalog"] == public
        and payload["reviewer"] == request["reviewer"]
        and payload["task_bundle_sha256"] == request["task_bundle_sha256"]
        and payload["wire_protocol"] == WIRE_PROTOCOL,
        "compact wire document/coordinate binding differs",
    )
    return local


def validate_compact_review(raw, request):
    """Expand literal locators, then run unchanged qualification checks.

    No missing key, evidence, mask label, semantic term, graph or verdict is fixed.
    Invalid output remains an error/unknown under the outer controller policy.
    """
    local = _checked_catalog(request)
    model = CompactTaskReview.model_validate(_strict_json(raw))
    compact = model.model_dump()

    def lookup(mapping, value, name):
        _require(value in mapping, f"unknown compact {name}: {value}")
        return mapping[value]

    def evidence(ids):
        return [dict(lookup(local["spans"], sid, "fragment")) for sid in ids]

    def doc(alias):
        return lookup(local["document_aliases"], alias, "document")

    def slot(alias):
        return lookup(local["slot_aliases"], alias, "slot")

    for term in compact["terms"]:
        term["source_doc_ids"] = [doc(x) for x in term["source_doc_ids"]]
    for item in compact["slots"]:
        item["slot_id"] = slot(item["slot_id"])
        for prop in item["propositions"]:
            for name in ("text", "support", "retraction"):
                prop[name] = evidence(prop[name])
        for action in item["actions"]:
            action["action_doc_id"] = doc(action["action_doc_id"])
            action["evidence"] = evidence(action["evidence"])
        for update in item["updates"]:
            for name in ("action_doc_id", "observation_doc_id"):
                update[name] = doc(update[name])
            for name in ("evidence", "nonredundancy_evidence"):
                update[name] = evidence(update[name])
        masks = []
        for mask in item["mask"]:
            span_id = mask.pop("span_id")
            masks.append(dict(lookup(local["spans"], span_id, "mask fragment")) | mask)
        item["mask"] = masks
        for node in item["semantic_graph"]["nodes"]:
            node["source_doc_ids"] = [doc(x) for x in node["source_doc_ids"]]
            node["evidence"] = evidence(node["evidence"])
        for edge in item["semantic_graph"]["edges"]:
            edge["evidence"] = evidence(edge["evidence"])
    for relation in compact["relations"]:
        relation["left"], relation["right"] = slot(relation["left"]), slot(relation["right"])
        relation["evidence"] = evidence(relation["evidence"])
    expanded = dict(
        schema_version="v6_semantic_review.v1",
        reviewer=request["reviewer"],
        task_bundle_sha256=request["task_bundle_sha256"],
        **compact,
    )
    result = validate_review(
        json.dumps(expanded, ensure_ascii=False, separators=(",", ":")),
        request["document_index"],
        expected_reviewer=request["reviewer"],
        expected_bundle_sha256=request["task_bundle_sha256"],
    )
    result["expanded_review_sha256"] = result["raw_review_sha256"]
    result["raw_review_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
    result.update(
        wire_protocol=WIRE_PROTOCOL,
        compact_catalog_sha256=request["compact_catalog_sha256"],
        catalog_sha256=request["catalog_sha256"],
        evidence_expansion="mechanical fixed original-fragment lookup only",
        semantic_repair_performed=False,
    )
    return result
