"""Typed-locator wire v4; the original V6 qualification semantics are unchanged.

This is a bijective wire-label adaptation, not a source/evidence repair. A model's
obs_* source anchor remains an observation and fails the original source-kind
check. The actual v4 arguments, mechanical mapping, and expanded semantic record
have separate hashes. No API calls are made here.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter

from . import v6_slot_review as baseline
from .contracts import digest
from .semantic_review import ReviewError, _strict_json
from .v6_compact_review import _require

WIRE_PROTOCOL = "v6_slot_review.v4"
FIELD_NAMES = {
    "source_doc_ids": "public_source_anchor_ids",
    "text": "model_claim_ids",
    "support": "support_evidence_ids",
    "retraction": "retraction_model_ids",
}
KIND_PREFIX = {
    "question": "src",
    "source_text": "src",
    "source_table_cell": "src",
    "public_content": "text",
    "action_arguments": "action",
    "tool_observation": "obs",
    "unparsed_tool_call": "raw",
}


def slot_rubric(reviewer):
    rubric = baseline.slot_rubric(reviewer)
    start, end = rubric.index("\nLOCATORS:"), rubric.index("\nFIXED TARGETS:")
    locator = (
        "\nTYPED LOCATORS: document_catalog is a single-level map. src_* names only the "
        "original question or original public source text/table cell; text_* names the "
        "model's public content; action_* names an actual atomic tool argument; obs_* names "
        "an actual tool observation. raw_* retains an unparsed original call, if present, "
        "and is never a positive action/target. Each ID selects one exact original fragment; "
        "there is no second document-ID system. Never calculate offsets, copy quotes or "
        "invent IDs. An observation names its real action in observes_action_id.\n"
        "SOURCE ANCHOR IS NOT OBSERVATION EVIDENCE: terms.public_source_anchor_ids and "
        "nodes.public_source_anchor_ids may contain ONLY src_* IDs. A derived term anchors "
        "the original public inputs from which it is derived; this does NOT claim the "
        "computed result appears literally in those sources. Its actual calculation or "
        "submission observation belongs in node.evidence or proposition.support_evidence_ids, "
        "not in public_source_anchor_ids. A read_source response is still an obs_* "
        "observation; cite the corresponding original src_* for the public-source anchor. "
        "The reviewer, never the host, must select and justify those original anchors. "
        "The host will not substitute a source for an observation. Locator-role example "
        "only: public_source_anchor_ids:[src_1] and evidence:[obs_2] have DIFFERENT roles, "
        "and these illustrative IDs must not be used unless present and relevant.\n"
        "PROPOSITION FIELDS: model_claim_ids locates the model's actual claim and "
        "retraction_model_ids locates its explicit retraction; use only text_* or action_* "
        "IDs, never a question/source/observation as invented model text. "
        "support_evidence_ids cites the actual available supporting evidence. "
        "All other evidence lists also cite available IDs of the appropriate role. "
        "action_doc_id accepts only action_*; observation_doc_id accepts only obs_*."
    )
    rubric = rubric[:start] + locator + rubric[end:]
    # These two occurrences refer to catalog locators, not model proposition IDs.
    rubric = rubric.replace("actual action e ID", "actual action_* ID")
    rubric = rubric.replace("public_content/action_arguments e ID", "text_*/action_* ID")
    return rubric


def _typed_request(base):
    baseline._checked_catalog(base)
    # Disk records use sort_keys=True, which reorders e0,e1,e2 into e0,e1,e10.
    # ID assignment must follow the original numeric coordinates, never the
    # deserialized mapping's insertion order. The hash-bound wire JSON also
    # preserves inner catalog field order for exact message-byte reconstruction.
    payload = _strict_json(base["messages"][1]["content"])
    wire_catalog = payload["document_catalog"]
    ordered_ids = sorted(wire_catalog, key=lambda eid: int(eid.removeprefix("e")))
    counters, forward = Counter(), {}
    for eid in ordered_ids:
        item = wire_catalog[eid]
        prefix = KIND_PREFIX[item["kind"]]
        forward[eid] = f"{prefix}_{counters[prefix]}"
        counters[prefix] += 1
    reverse = {typed: old for old, typed in forward.items()}
    _require(len(reverse) == len(forward), "typed locators must be bijective")
    catalog = {}
    for eid in ordered_ids:
        item = wire_catalog[eid]
        value = copy.deepcopy(item)
        if "observes_action_id" in value:
            value["observes_action_id"] = forward[value["observes_action_id"]]
        catalog[forward[eid]] = value
    local = dict(
        slot_id=base["slot_id"],
        spans={
            forward[eid]: copy.deepcopy(span)
            for eid, span in base["compact_catalog"]["spans"].items()
        },
    )

    def schema(node):
        result = {}
        for key, value in node.items():
            if key == "properties":
                result[key] = {
                    forward.get(name, FIELD_NAMES.get(name, name)): schema(child)
                    for name, child in value.items()
                }
            elif key == "required":
                result[key] = [forward.get(name, FIELD_NAMES.get(name, name)) for name in value]
            elif key == "enum":
                result[key] = [
                    forward.get(item, item) if isinstance(item, str) else item for item in value
                ]
            elif isinstance(value, dict):
                result[key] = schema(value)
            elif key == "anyOf":
                result[key] = [schema(child) for child in value]
            else:
                result[key] = copy.deepcopy(value)
        return result

    tool = copy.deepcopy(base["strict_tool"])
    tool["function"]["parameters"] = schema(tool["function"]["parameters"])
    rubric = slot_rubric(base["reviewer"])
    payload.update(wire_protocol=WIRE_PROTOCOL, document_catalog=catalog)
    messages = [
        dict(role="system", content=rubric),
        dict(role="user", content=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
    ]
    result = copy.deepcopy(base)
    result.update(
        wire_protocol=WIRE_PROTOCOL,
        messages=messages,
        document_catalog=catalog,
        compact_catalog=local,
        catalog_sha256=digest(catalog),
        compact_catalog_sha256=digest(local),
        strict_tool=tool,
        strict_tool_sha256=digest(tool),
        rubric_sha256=digest(rubric),
        messages_model_sha256=digest(dict(model="deepseek-flash", messages=messages)),
        semantic_baseline_request=copy.deepcopy(base),
        semantic_baseline_request_sha256=digest(base),
        typed_to_baseline_locators=reverse,
        wire_adaptation="bijective locator and field-label rename only; no semantic repair",
    )
    return result


def slot_review_request(prepared, slot_id, reference, reviewer=0):
    return _typed_request(baseline.slot_review_request(prepared, slot_id, reference, reviewer))


def capacity_features(request):
    return baseline.capacity_features(request)


def _checked_request(request):
    _require(request.get("wire_protocol") == WIRE_PROTOCOL, "wrong typed slot wire protocol")
    base = request["semantic_baseline_request"]
    _require(
        digest(base) == request["semantic_baseline_request_sha256"],
        "typed slot semantic baseline binding differs",
    )
    expected = _typed_request(base)
    # Capacity/runtime fields may be appended by the registered controller; every
    # factory field must still equal the original derivation from the baseline.
    _require(
        all(request.get(key) == value for key, value in expected.items()),
        "typed slot catalog/schema/rubric/request binding differs",
    )
    return base, request["typed_to_baseline_locators"]


def _mapped_arguments(raw_arguments, aliases):
    value = _strict_json(raw_arguments)
    _require(isinstance(value, dict), "typed slot arguments must be an object")

    def locator(name):
        _require(isinstance(name, str) and name in aliases, f"unknown typed locator: {name}")
        return aliases[name]

    def refs(items):
        _require(isinstance(items, list), "typed evidence references must be lists")
        return [locator(item) for item in items]

    def renamed(obj, old):
        new = FIELD_NAMES[old]
        _require(
            old not in obj and new in obj, f"required typed field {new}; legacy {old} forbidden"
        )
        obj[old] = refs(obj.pop(new))

    for term in value["terms"]:
        renamed(term, "source_doc_ids")
    for prop in value["propositions"]:
        for old in ("text", "support", "retraction"):
            renamed(prop, old)
    actions = {}
    for eid, action in value["actions"].items():
        action["evidence"] = refs(action["evidence"])
        actions[locator(eid)] = action
    value["actions"] = actions
    value["mask"] = {locator(eid): mask for eid, mask in value["mask"].items()}
    for update in value["updates"]:
        for name in ("action_doc_id", "observation_doc_id"):
            update[name] = locator(update[name])
        for name in ("evidence", "nonredundancy_evidence"):
            update[name] = refs(update[name])
    for node in value["semantic_graph"]["nodes"]:
        renamed(node, "source_doc_ids")
        node["evidence"] = refs(node["evidence"])
    for edge in value["semantic_graph"]["edges"]:
        edge["evidence"] = refs(edge["evidence"])
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def validate_slot_review(raw_arguments, request):
    try:
        base, aliases = _checked_request(request)
        mapped = _mapped_arguments(raw_arguments, aliases)
        result = baseline.validate_slot_review(mapped, base)
    except ReviewError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError) as failure:
        raise ReviewError(f"typed slot interface {type(failure).__name__}: {failure}") from failure
    result.update(
        schema=WIRE_PROTOCOL,
        wire_protocol=WIRE_PROTOCOL,
        raw_review_sha256=hashlib.sha256(raw_arguments.encode()).hexdigest(),
        locator_mapped_review_sha256=hashlib.sha256(mapped.encode()).hexdigest(),
        catalog_sha256=request["catalog_sha256"],
        compact_catalog_sha256=request["compact_catalog_sha256"],
        strict_tool_sha256=request["strict_tool_sha256"],
        semantic_baseline_request_sha256=request["semantic_baseline_request_sha256"],
        locator_mapping_is_another_model_response=False,
        wire_adaptation=request["wire_adaptation"],
    )
    return result


def inspect_slot_review(raw_arguments, request):
    try:
        result = validate_slot_review(raw_arguments, request)
    except ReviewError as failure:
        return dict(
            interface_admitted=False,
            semantic_consistent=False,
            validation=None,
            error=str(failure),
            error_kind="mechanical_interface",
            reviewer=request.get("reviewer"),
            task_id=request.get("task_id"),
            slot_id=request.get("slot_id"),
            task_bundle_sha256=request.get("task_bundle_sha256"),
            raw_review_sha256=hashlib.sha256(raw_arguments.encode()).hexdigest()
            if isinstance(raw_arguments, str)
            else None,
            v_trace="unknown",
            parsed=None,
            derived=None,
        )
    return dict(
        interface_admitted=True,
        semantic_consistent=result["semantic_consistent"],
        validation=result,
        error=result["semantic_validation_error"],
        error_kind=None if result["semantic_consistent"] else "semantic_inconsistency",
    )
