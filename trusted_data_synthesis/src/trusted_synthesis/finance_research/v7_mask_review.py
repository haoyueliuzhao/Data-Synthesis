"""Prospective v5: explicitly reviewed empty optional fields are zero-loss context.

Old v3/v4 requests and decisions are never upgraded or repaired by this module.
"""

from __future__ import annotations

import copy
import hashlib
import json

from . import v6_slot_review as baseline
from . import v7_slot_review as typed
from .contracts import digest
from .semantic_review import ReviewError
from .v6_compact_review import _require

WIRE_PROTOCOL = "v6_slot_review.v5"
AMENDMENT = """
PROSPECTIVE EMPTY-OPTIONAL-FIELD MASK AMENDMENT:
Every approved mask fragment must name at least one actually reviewed, supported
proposition; never invent a financial proposition for an empty optional Q field.
The new nonassertive_context mask label is allowed ONLY for a whole public-content
fragment that consists of Q: None or Q: N/A (case-insensitive, optional final period,
and surrounding whitespace). It must have proposition_ids: []. This fragment stays
in the original input/history but has ZERO target loss. The host verifies this
narrow lexical domain; it never changes the model's chosen label. It is not a
financial assertion, evidence of correctness, state node, or substantive update.
Any financial statement, uncertainty, contradiction, action arguments, source,
observation, or claim of verification is outside this exception. Do not put these
into nonassertive_context. An unknown substantive claim remains unknown/invalid;
an unresolved critical claim forbids v_trace=valid. Both reviewers must independently
agree on the complete mask before any future positive training use.
Graph IDs must stay in their own namespaces: edge endpoints name existing NODE
IDs, never TERM IDs. Every node must bind existing semantic terms, including a
decision/result node. Every derived term retains its original public-input source
anchors; observations are evidence, not substitutes for those anchors. Do not
approve a mask fragment bound to an unknown or retracted proposition. No automatic
repair, omitted source, or supplied answer is permitted by this amendment.
"""


def _request(base):
    typed._checked_request(base)
    result = copy.deepcopy(base)
    tool = result["strict_tool"]
    for name, item in tool["function"]["parameters"]["properties"]["mask"]["properties"].items():
        if result["document_catalog"][name]["kind"] == "public_content":
            item["properties"]["label"]["enum"].append("nonassertive_context")
    payload = json.loads(base["messages"][1]["content"])
    payload["wire_protocol"] = WIRE_PROTOCOL
    rubric = base["messages"][0]["content"] + AMENDMENT
    messages = [
        dict(role="system", content=rubric),
        dict(role="user", content=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
    ]
    result.update(
        wire_protocol=WIRE_PROTOCOL,
        messages=messages,
        strict_tool_sha256=digest(tool),
        rubric_sha256=digest(rubric),
        messages_model_sha256=digest(dict(model="deepseek-flash", messages=messages)),
        typed_baseline_request=copy.deepcopy(base),
        typed_baseline_request_sha256=digest(base),
        mask_amendment="explicit_empty_Q_nonassertive_zero_loss.v1",
    )
    return result


def slot_review_request(prepared, slot_id, reference, reviewer=0):
    return _request(typed.slot_review_request(prepared, slot_id, reference, reviewer))


def validate_slot_review(raw_arguments, request):
    try:
        _require(request.get("wire_protocol") == WIRE_PROTOCOL, "wrong v5 mask wire")
        base = request["typed_baseline_request"]
        _require(digest(base) == request["typed_baseline_request_sha256"], "v5 baseline changed")
        expected = _request(base)
        _require(
            all(request.get(k) == v for k, v in expected.items()), "v5 request binding differs"
        )
        mapped = typed._mapped_arguments(raw_arguments, base["typed_to_baseline_locators"])
        result = baseline.validate_slot_review(
            mapped, base["semantic_baseline_request"], allow_nonassertive_context=True
        )
    except ReviewError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise ReviewError(f"v5 interface {type(error).__name__}: {error}") from error
    result.update(
        schema=WIRE_PROTOCOL,
        wire_protocol=WIRE_PROTOCOL,
        raw_review_sha256=hashlib.sha256(raw_arguments.encode()).hexdigest(),
        locator_mapped_review_sha256=hashlib.sha256(mapped.encode()).hexdigest(),
        mask_amendment=request["mask_amendment"],
        original_review_reclassified=False,
        host_mask_repair=False,
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
            v_trace="unknown",
            derived=None,
            error=str(failure),
            error_kind="mechanical_interface",
        )
    return dict(
        interface_admitted=True,
        semantic_consistent=result["semantic_consistent"],
        validation=result,
        error=result["semantic_validation_error"],
        error_kind=None if result["semantic_consistent"] else "semantic_inconsistency",
    )
