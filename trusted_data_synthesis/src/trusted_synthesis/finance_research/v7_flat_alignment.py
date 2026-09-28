"""Prospective alignment of one side's eight fresh flat-v6 slot judgments.

This version does not masquerade as v5, mix earlier successes, call a model, or
admit training. Unknown slot returns keep their original registered coordinates.
"""

from __future__ import annotations

import copy
import hashlib
import json

from . import v6_state_alignment as baseline
from . import v7_flat_review as flat
from .contracts import digest
from .semantic_review import ReviewError

WIRE_PROTOCOL = "v6_alignment_review.v5"
SLOT_PROTOCOL = flat.WIRE_PROTOCOL


def _require(condition, message):
    if not condition:
        raise ReviewError(message)


def slot_review_record(request, artifact):
    """Keep actual v6 artifacts, including malformed returns, in all eight slots."""
    flat._checked_request(request)
    _require(
        artifact.get("wire_protocol") == SLOT_PROTOCOL
        and artifact.get("semantic_review_request_sha256") == digest(request),
        "slot artifact is not bound to the actual flat-v6 request",
    )
    raw = artifact.get("review_text")
    format_error = artifact.get("review_format_error")
    if artifact.get("finish_reason") != "tool_calls" or format_error:
        inspection = dict(
            interface_admitted=False,
            semantic_consistent=False,
            validation=None,
            error=format_error or "non-normal original strict finish",
            error_kind="mechanical_interface",
        )
    else:
        inspection = flat.inspect_slot_review(raw, request)
    if inspection["validation"] is not None:
        result = copy.deepcopy(inspection["validation"])
        result.update(
            original_slot_artifact_sha256=digest(artifact), slot_request_sha256=digest(request)
        )
        return result
    return dict(
        wire_protocol=SLOT_PROTOCOL,
        schema=SLOT_PROTOCOL,
        reviewer=request["reviewer"],
        task_id=request["task_id"],
        slot_id=request["slot_id"],
        task_bundle_sha256=request["task_bundle_sha256"],
        v_trace="unknown",
        reported_v_trace=None,
        interface_admitted=False,
        semantic_consistent=False,
        parsed=None,
        terms=None,
        derived=None,
        document_index=request["document_index"],
        semantic_validation_error=None,
        mechanical_validation_error=inspection["error"],
        raw_review_sha256=hashlib.sha256(raw.encode()).hexdigest()
        if isinstance(raw, str)
        else None,
        original_slot_artifact_sha256=digest(artifact),
        slot_request_sha256=digest(request),
        failed_slot_request=copy.deepcopy(request),
        failed_slot_artifact=copy.deepcopy(artifact),
        positive_target_mask=None,
        encoding_manifest=None,
        mask_complete=False,
        original_coordinate_retained=True,
        old_reviews_reclassified=False,
    )


def _records(reviews):
    for item in reviews.values():
        _require(
            item.get("wire_protocol") == SLOT_PROTOCOL,
            "flat alignment accepts only actual flat-v6 slot records",
        )
        if item.get("interface_admitted") is False:
            _require(
                isinstance(item.get("failed_slot_request"), dict)
                and isinstance(item.get("failed_slot_artifact"), dict),
                "unknown flat slot needs its bound original request and artifact",
            )
            _require(
                slot_review_record(item["failed_slot_request"], item["failed_slot_artifact"])
                == item,
                "failed flat slot was changed or reclassified",
            )
        if item.get("v_trace") == "valid":
            _require(
                item.get("interface_admitted") is True and item.get("semantic_consistent") is True,
                "effective valid flat record lacks its finite validation",
            )


def _request(base):
    baseline._checked_request(base, allow_nonassertive_context=True)
    _records(base["own_slot_reviews"])
    payload = json.loads(base["messages"][1]["content"])
    payload.update(wire_protocol=WIRE_PROTOCOL, slot_review_protocol=SLOT_PROTOCOL)
    rubric = base["messages"][0]["content"] + (
        "\nPROSPECTIVE FLAT-v6 CONTEXT: these are only your own eight newly sealed flat-wire "
        "slot reviews. Their finite semantic rules and zero-loss empty-Q policy are unchanged. "
        "Do not reinterpret failed or unknown slots, use the other reviewer's output, count "
        "empty Q context as a state distinction, or reuse an older trial's review. "
        "No free-form graph-string equality or native-answer-only shortcut defines equivalence."
    )
    messages = [
        dict(role="system", content=rubric),
        dict(role="user", content=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
    ]
    result = copy.deepcopy(base)
    result.update(
        wire_protocol=WIRE_PROTOCOL,
        slot_review_protocol=SLOT_PROTOCOL,
        messages=messages,
        rubric_sha256=digest(rubric),
        messages_model_sha256=digest(dict(model="deepseek-flash", messages=messages)),
        alignment_semantic_baseline_request=copy.deepcopy(base),
        alignment_semantic_baseline_request_sha256=digest(base),
        previous_trial_outputs_visible=False,
    )
    return result


def alignment_request(prepared, reviews, reviewer=0):
    _records(reviews)
    return _request(
        baseline.alignment_request(prepared, reviews, reviewer, allow_nonassertive_context=True)
    )


def validate_alignment(raw, request):
    try:
        _require(request.get("wire_protocol") == WIRE_PROTOCOL, "wrong flat alignment version")
        base = request["alignment_semantic_baseline_request"]
        _require(
            digest(base) == request["alignment_semantic_baseline_request_sha256"],
            "flat alignment baseline binding changed",
        )
        expected = _request(base)
        _require(
            all(request.get(k) == v for k, v in expected.items()),
            "flat alignment request binding changed",
        )
        value = baseline.validate_alignment(raw, base, allow_nonassertive_context=True)
    except ReviewError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise ReviewError(f"flat alignment interface {type(error).__name__}: {error}") from error
    value.update(
        schema="v7_flat_state_alignment.v1",
        wire_protocol=WIRE_PROTOCOL,
        slot_review_protocol=SLOT_PROTOCOL,
        alignment_request_sha256=digest(request),
        alignment_semantic_baseline_request_sha256=digest(base),
        previous_trial_outputs_reused=False,
        semantic_repair_performed=False,
    )
    return value


def inspect_alignment(raw, request):
    try:
        value = validate_alignment(raw, request)
    except ReviewError as error:
        return dict(
            interface_admitted=False,
            semantic_consistent=False,
            validation=None,
            error=str(error),
            error_kind="mechanical_interface",
            wire_protocol=WIRE_PROTOCOL,
            reviewer=request.get("reviewer"),
            task_id=request.get("task_id"),
            task_bundle_sha256=request.get("task_bundle_sha256"),
            slot_review_bindings=request.get("slot_review_bindings"),
            pairs=None,
            raw_review_sha256=hashlib.sha256(raw.encode()).hexdigest()
            if isinstance(raw, str)
            else None,
        )
    errors = [
        p["semantic_validation_error"]
        for p in value["pairs"].values()
        if p["semantic_validation_error"]
    ]
    return dict(
        interface_admitted=True,
        semantic_consistent=value["semantic_consistent"],
        validation=value,
        error=errors or None,
        error_kind="semantic_inconsistency" if errors else None,
        wire_protocol=WIRE_PROTOCOL,
    )
