"""Strict-tool V6 review wire v2, using one flat public evidence ID namespace.

Strict JSON constrains shape/locators, not truth. All substantive validation is
still delegated to the unchanged original semantic validator. No API calls here.
"""

from __future__ import annotations

import hashlib
import json

from .contracts import digest
from .semantic_review import (
    SOURCE_KINDS,
    TARGET_KINDS,
    _strict_json,
    document_index,
    validate_review,
)
from .v6_compact_review import CompactTaskReview, _require, compact_rubric, fragment_ranges

WIRE_PROTOCOL = "v6_strict_review.v2"
TOOL_NAME = "submit_review"


def _catalog(docs):
    original_slots = sorted({d["slot_id"] for d in docs.values() if d["slot_id"] is not None})
    _require(len(original_slots) == 8, "strict review requires eight original candidates")
    slots = {f"s{i}": sid for i, sid in enumerate(original_slots)}
    reverse_slots = {v: k for k, v in slots.items()}
    public, spans, first = {}, {}, {}
    for doc_id in sorted(docs):
        doc = docs[doc_id]
        for start, end in fragment_ranges(doc["text"], atomic=doc["kind"] == "action_arguments"):
            eid = f"e{len(spans)}"
            first.setdefault(doc_id, eid)
            spans[eid] = dict(doc_id=doc_id, start=start, end=end, quote=doc["text"][start:end])
            value = dict(
                text=doc["text"][start:end],
                kind=doc["kind"],
                slot_id=reverse_slots.get(doc["slot_id"]),
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
            public[eid] = value
    for eid, span in spans.items():
        doc = docs[span["doc_id"]]
        if "observes_action_doc_id" in doc:
            action_id = doc["observes_action_doc_id"]
            _require(action_id in first, "actual observation has no nonempty atomic action")
            public[eid]["observes_action_id"] = first[action_id]
    return public, dict(slot_aliases=slots, spans=spans)


def strict_parameters(document_catalog):
    """Inline local Pydantic schema into the documented beta-strict subset.

    Array cardinality/semantic checks remain local: no unsupported minItems,
    maxItems, $ref, $defs, titles or descriptions are sent to the server.
    """
    original = CompactTaskReview.model_json_schema()
    definitions = original.get("$defs", {})
    all_ids = list(document_catalog)
    groups = {
        "source_doc_ids": [k for k, d in document_catalog.items() if d["kind"] in SOURCE_KINDS],
        "action_doc_id": [
            k for k, d in document_catalog.items() if d["kind"] == "action_arguments"
        ],
        "observation_doc_id": [
            k for k, d in document_catalog.items() if d["kind"] == "tool_observation"
        ],
        "span_id": [k for k, d in document_catalog.items() if d["kind"] in TARGET_KINDS],
        "text": [k for k, d in document_catalog.items() if d["kind"] in TARGET_KINDS],
        "retraction": [k for k, d in document_catalog.items() if d["kind"] in TARGET_KINDS],
    }
    for name in ("evidence", "support", "nonredundancy_evidence"):
        groups[name] = all_ids
    for name in ("slot_id", "left", "right"):
        groups[name] = [f"s{i}" for i in range(8)]

    def inline(node, name=None):
        if "$ref" in node:
            _require(node["$ref"].startswith("#/$defs/"), "nonlocal strict schema reference")
            return inline(definitions[node["$ref"].removeprefix("#/$defs/")], name)
        result = {k: node[k] for k in ("type", "enum", "pattern") if k in node}
        if "const" in node:
            result["enum"] = [node["const"]]
        if "anyOf" in node:
            result["anyOf"] = [inline(x, name) for x in node["anyOf"]]
        if node.get("type") == "object":
            props = {k: inline(v, k) for k, v in node.get("properties", {}).items()}
            result.update(properties=props, required=list(props), additionalProperties=False)
        elif node.get("type") == "array":
            result["items"] = inline(node["items"])
            if name in groups:
                result["items"] = dict(type="string", enum=groups[name])
        elif node.get("type") == "string" and name in groups:
            result["enum"] = groups[name]
        return result

    return inline(original)


def strict_tool(document_catalog):
    return dict(
        type="function",
        function=dict(name=TOOL_NAME, strict=True, parameters=strict_parameters(document_catalog)),
    )


def strict_rubric(reviewer):
    # Retain the prior substantive qualification rubric; replace ONLY the locator
    # vocabulary and response transport directives, not any semantic criterion.
    text = compact_rubric(reviewer)
    text = text.replace(
        "Return exactly the supplied strict JSON schema, without Markdown, duplicate keys, NaN,\n"
        "or commentary.",
        "Call submit_review exactly once with arguments conforming to its supplied strict "
        "schema. Do not return prose, Markdown, duplicate keys, NaN, or other tool calls.",
    )
    marker = "\nCOMPACT FORMAT:"
    _require(marker in text, "substantive rubric locator appendix changed")
    text = text.split(marker, 1)[0]
    return text + (
        "\nFLAT EVIDENCE LOCATORS: document_catalog is one flat map e0,e1,... to immutable "
        "original public-text fragments. ALL source_doc_ids, action_doc_id, observation_doc_id, "
        "evidence, text, support, retraction, nonredundancy_evidence, and mask.span_id fields "
        "use these SAME e IDs. There is no separate document/fragment naming system. "
        "In fields named source_doc_ids/action_doc_id/observation_doc_id choose an e ID of "
        "the required kind; the host only restores its original parent document locator. "
        "In evidence/text/support/retraction fields the e ID selects that exact original "
        "fragment. Never return quotes, offsets, invented IDs or fabricated content. "
        "Action arguments are atomic. A tool observation's observes_action_id identifies its "
        "actual atomic action e ID. Every target e ID receives exactly one mask entry in its "
        "own slot; source/observation e IDs are never targets. Source fragments that share a "
        "source_id belong to the original public source; IDs are only locators, never "
        "semantic identities. Slot aliases s0,...,s7 are likewise locators only. "
        "Arguments contain ONLY terms, slots and relations. Keep all eight slots and all "
        "28 unordered pairs in ascending slot order. Strict JSON is not semantic correctness; "
        "use unknown when original evidence is insufficient. "
        f"Independent review context index: {reviewer}; no other review is provided."
    )


def strict_review_request(bundle, reference, reviewer=0):
    bundle = bundle.get("bundle", bundle)
    docs = document_index(bundle)
    public, local = _catalog(docs)
    reference = reference.model_dump(mode="json") if hasattr(reference, "model_dump") else reference
    _require(isinstance(reference, dict), "explicit private offline reference required")
    rubric = strict_rubric(reviewer)
    tool = strict_tool(public)
    bundle_hash = digest(bundle)
    payload = dict(
        wire_protocol=WIRE_PROTOCOL,
        task_id=bundle["task_id"],
        task_bundle_sha256=bundle_hash,
        reviewer=reviewer,
        slot_ids=list(local["slot_aliases"]),
        document_catalog=public,
        review_only_private_reference=reference,
    )
    messages = [
        dict(role="system", content=rubric),
        dict(role="user", content=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
    ]
    return dict(
        wire_protocol=WIRE_PROTOCOL,
        model="deepseek-flash",
        reviewer=reviewer,
        messages=messages,
        document_index=docs,
        document_catalog=public,
        compact_catalog=local,
        catalog_sha256=digest(public),
        compact_catalog_sha256=digest(local),
        strict_tool=tool,
        strict_tool_sha256=digest(tool),
        task_bundle_sha256=bundle_hash,
        rubric_sha256=digest(rubric),
        messages_model_sha256=digest(dict(model="deepseek-flash", messages=messages)),
        private_reference_for_review_only=True,
        other_reviewer_output_visible=False,
    )


def capacity_features(request):
    docs = request["document_index"]
    targets = {k: d for k, d in docs.items() if d["kind"] in TARGET_KINDS}
    return dict(
        document_count=len(docs),
        original_document_chars=sum(len(d["text"]) for d in docs.values()),
        public_content_chars=sum(
            len(d["text"]) for d in docs.values() if d["kind"] == "public_content"
        ),
        target_chars=sum(len(d["text"]) for d in targets.values()),
        target_document_count=sum(bool(d["text"]) for d in targets.values()),
        target_fragment_count=sum(
            s["doc_id"] in targets for s in request["compact_catalog"]["spans"].values()
        ),
        action_count=sum(d["kind"] == "action_arguments" for d in docs.values()),
        source_chars=sum(len(d["text"]) for d in docs.values() if d["slot_id"] is None),
        fragment_count=len(request["compact_catalog"]["spans"]),
        request_content_chars=sum(len(m["content"]) for m in request["messages"]),
        strict_tool_chars=len(
            json.dumps(request["strict_tool"], ensure_ascii=False, separators=(",", ":"))
        ),
        exact_api_token_count_known=False,
    )


def _checked_catalog(request):
    _require(request.get("wire_protocol") == WIRE_PROTOCOL, "wrong strict wire protocol")
    _require(request.get("model") == "deepseek-flash", "strict review model must be deepseek-flash")
    public, local = _catalog(request["document_index"])
    _require(
        public == request["document_catalog"]
        and local == request["compact_catalog"]
        and digest(public) == request["catalog_sha256"]
        and digest(local) == request["compact_catalog_sha256"],
        "strict evidence catalog does not exhaustively bind the original documents",
    )
    expected_tool = strict_tool(public)
    _require(
        request["strict_tool"] == expected_tool
        and request["strict_tool_sha256"] == digest(expected_tool),
        "strict function schema/locator binding differs",
    )
    messages = request["messages"]
    _require(
        digest(dict(model="deepseek-flash", messages=messages)) == request["messages_model_sha256"]
        and messages[0]["content"] == strict_rubric(request["reviewer"])
        and digest(messages[0]["content"]) == request["rubric_sha256"],
        "strict request/rubric binding differs",
    )
    payload = _strict_json(messages[1]["content"])
    _require(
        payload["document_catalog"] == public
        and payload["reviewer"] == request["reviewer"]
        and payload["task_bundle_sha256"] == request["task_bundle_sha256"]
        and payload["wire_protocol"] == WIRE_PROTOCOL
        and "output_schema" not in payload,
        "strict wire document/coordinate binding differs",
    )
    return local


def validate_strict_review(raw_arguments, request):
    local = _checked_catalog(request)
    value = CompactTaskReview.model_validate(_strict_json(raw_arguments)).model_dump()

    def span(eid):
        _require(eid in local["spans"], f"unknown flat evidence ID: {eid}")
        return dict(local["spans"][eid])

    def evidence(ids):
        return [span(eid) for eid in ids]

    def doc(eid, kinds):
        result = span(eid)["doc_id"]
        _require(
            request["document_index"][result]["kind"] in kinds, "wrong evidence kind for field"
        )
        return result

    def slot(alias):
        _require(alias in local["slot_aliases"], "unknown strict slot alias")
        return local["slot_aliases"][alias]

    for term in value["terms"]:
        term["source_doc_ids"] = [doc(x, SOURCE_KINDS) for x in term["source_doc_ids"]]
    for item in value["slots"]:
        item["slot_id"] = slot(item["slot_id"])
        for prop in item["propositions"]:
            for name in ("text", "support", "retraction"):
                prop[name] = evidence(prop[name])
        for action in item["actions"]:
            action["action_doc_id"] = doc(action["action_doc_id"], {"action_arguments"})
            action["evidence"] = evidence(action["evidence"])
        for update in item["updates"]:
            update["action_doc_id"] = doc(update["action_doc_id"], {"action_arguments"})
            update["observation_doc_id"] = doc(update["observation_doc_id"], {"tool_observation"})
            for name in ("evidence", "nonredundancy_evidence"):
                update[name] = evidence(update[name])
        item["mask"] = [span(m.pop("span_id")) | m for m in item["mask"]]
        for node in item["semantic_graph"]["nodes"]:
            node["source_doc_ids"] = [doc(x, SOURCE_KINDS) for x in node["source_doc_ids"]]
            node["evidence"] = evidence(node["evidence"])
        for edge in item["semantic_graph"]["edges"]:
            edge["evidence"] = evidence(edge["evidence"])
    for relation in value["relations"]:
        relation["left"], relation["right"] = slot(relation["left"]), slot(relation["right"])
        relation["evidence"] = evidence(relation["evidence"])
    expanded = dict(
        schema_version="v6_semantic_review.v1",
        reviewer=request["reviewer"],
        task_bundle_sha256=request["task_bundle_sha256"],
        **value,
    )
    result = validate_review(
        json.dumps(expanded, ensure_ascii=False, separators=(",", ":")),
        request["document_index"],
        expected_reviewer=request["reviewer"],
        expected_bundle_sha256=request["task_bundle_sha256"],
    )
    result["expanded_review_sha256"] = result["raw_review_sha256"]
    result["raw_review_sha256"] = hashlib.sha256(raw_arguments.encode()).hexdigest()
    result.update(
        wire_protocol=WIRE_PROTOCOL,
        catalog_sha256=request["catalog_sha256"],
        compact_catalog_sha256=request["compact_catalog_sha256"],
        strict_tool_sha256=request["strict_tool_sha256"],
        evidence_expansion="mechanical flat original-fragment lookup only",
        semantic_repair_performed=False,
        strict_format_is_semantic_correctness=False,
    )
    return result
