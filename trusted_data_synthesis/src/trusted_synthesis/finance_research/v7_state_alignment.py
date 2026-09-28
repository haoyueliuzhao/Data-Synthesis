"""Prospective v5-mask alignment/encoding support; no model calls or training.

Only v5-sealed per-slot judgments enter this explicit alignment version. The
nonassertive_context label is retained through consensus and is always zero-loss.
Older alignment defaults keep rejecting the new label. This is not retrospective
admission of an earlier technical cohort or permission to drop unmapped material.
"""

from __future__ import annotations

import copy
import hashlib
import json

from . import v6_state_alignment as baseline
from . import v7_mask_review as slot_v5
from .contracts import digest
from .semantic_review import ReviewError, is_nonassertive_context_fragment
from .v6_encoding import encode_reviewed_probe_for_student as encode_base
from .v6_task import public_trajectory_view

WIRE_PROTOCOL = "v6_alignment_review.v4"
SLOT_PROTOCOL = "v6_slot_review.v5"
MASK_POLICY = "explicit_empty_Q_nonassertive_zero_loss.v1"
ENCODING_POLICY = "v7_v5_mask_consensus_nonassertive_context_zero_loss.v1"


def _require(condition, message):
    if not condition:
        raise ReviewError(message)


def _versioned_slots(reviews):
    for item in reviews.values():
        _require(
            item.get("wire_protocol") == SLOT_PROTOCOL
            and item.get("mask_amendment") == MASK_POLICY,
            "prospective alignment requires explicitly bound v5 slot judgments",
        )
        if item.get("interface_admitted") is False:
            request = item.get("failed_review_request")
            _require(
                isinstance(request, dict), "unknown v5 slot lacks its original versioned request"
            )
            expected = slot_review_record(request, item.get("failed_review_arguments"))
            _require(
                item == expected, "mechanically failed slot is not its bound v5 unknown record"
            )
        if item.get("v_trace") == "valid":
            _require(
                item.get("interface_admitted") is True and item.get("semantic_consistent") is True,
                "effective valid v5 judgment lacks its finite validation",
            )


def slot_review_record(request, raw_arguments):
    """Bind actual v5 arguments, retaining a mechanical failure in its original slot.

    Unknown candidates are not eligible, but never block alignment merely because
    another genuinely eligible candidate exists. No older failure gains a v5 label.
    """
    _require(
        request.get("wire_protocol") == SLOT_PROTOCOL
        and request.get("mask_amendment") == MASK_POLICY,
        "failed-slot adapter requires an actual v5 request",
    )
    base = request["typed_baseline_request"]
    _require(digest(base) == request["typed_baseline_request_sha256"], "v5 slot baseline changed")
    expected_request = slot_v5._request(base)
    _require(
        all(request.get(key) == value for key, value in expected_request.items()),
        "failed-slot adapter request binding differs",
    )
    inspection = slot_v5.inspect_slot_review(raw_arguments, request)
    if inspection["validation"] is not None:
        return inspection["validation"]
    return dict(
        wire_protocol=SLOT_PROTOCOL,
        schema=SLOT_PROTOCOL,
        mask_amendment=MASK_POLICY,
        reviewer=request["reviewer"],
        task_id=request["task_id"],
        slot_id=request["slot_id"],
        task_bundle_sha256=request["task_bundle_sha256"],
        v_trace="unknown",
        reported_v_trace=None,
        interface_admitted=False,
        semantic_consistent=False,
        semantic_validation_error=None,
        mechanical_validation_error=inspection["error"],
        parsed=None,
        terms=None,
        derived=None,
        document_index=request["document_index"],
        original_document_index_sha256=digest(request["document_index"]),
        raw_review_sha256=hashlib.sha256(raw_arguments.encode()).hexdigest()
        if isinstance(raw_arguments, str)
        else None,
        review_request_sha256=digest(request),
        failed_review_request=copy.deepcopy(request),
        failed_review_arguments=raw_arguments,
        inspection=inspection,
        positive_target_mask=None,
        mask_complete=False,
        encoding_manifest=None,
        original_coordinate_retained=True,
        host_semantic_repair=False,
        old_reviews_reclassified=False,
    )


def _request(base):
    baseline._checked_request(base, allow_nonassertive_context=True)
    _versioned_slots(base["own_slot_reviews"])
    payload = json.loads(base["messages"][1]["content"])
    payload["wire_protocol"] = WIRE_PROTOCOL
    payload["slot_review_protocol"] = SLOT_PROTOCOL
    payload["mask_policy"] = MASK_POLICY
    rubric = base["messages"][0]["content"] + (
        "\nPROSPECTIVE v5 MASK SUPPORT: slot judgments used the registered empty-Q "
        "nonassertive_context policy. Those lexical empty optional fields remain history "
        "but carry no positive target loss. They do not establish a financial proposition, "
        "verification, revision, semantic difference, chi, or state. Do not rejudge or "
        "change any slot mask. All previous semantic and accepted-answer-path criteria "
        "remain unchanged."
    )
    messages = [
        dict(role="system", content=rubric),
        dict(role="user", content=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
    ]
    result = copy.deepcopy(base)
    result.update(
        wire_protocol=WIRE_PROTOCOL,
        messages=messages,
        rubric_sha256=digest(rubric),
        messages_model_sha256=digest(dict(model="deepseek-flash", messages=messages)),
        slot_review_protocol=SLOT_PROTOCOL,
        mask_policy=MASK_POLICY,
        semantic_alignment_baseline_request=copy.deepcopy(base),
        semantic_alignment_baseline_request_sha256=digest(base),
    )
    return result


def alignment_request(prepared, slot_reviews_for_one_reviewer, reviewer=0):
    _versioned_slots(slot_reviews_for_one_reviewer)
    return _request(
        baseline.alignment_request(
            prepared, slot_reviews_for_one_reviewer, reviewer, allow_nonassertive_context=True
        )
    )


def validate_alignment(raw, request):
    try:
        _require(request.get("wire_protocol") == WIRE_PROTOCOL, "wrong prospective alignment wire")
        base = request["semantic_alignment_baseline_request"]
        _require(
            digest(base) == request["semantic_alignment_baseline_request_sha256"],
            "prospective alignment baseline changed",
        )
        expected = _request(base)
        _require(
            all(request.get(key) == value for key, value in expected.items()),
            "prospective alignment request binding differs",
        )
        result = baseline.validate_alignment(raw, base, allow_nonassertive_context=True)
    except ReviewError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise ReviewError(
            f"prospective alignment interface {type(error).__name__}: {error}"
        ) from error
    result.update(
        schema="v7_state_alignment.v1",
        wire_protocol=WIRE_PROTOCOL,
        alignment_request_sha256=digest(request),
        semantic_alignment_baseline_request_sha256=digest(base),
        slot_review_protocol=SLOT_PROTOCOL,
        mask_policy=MASK_POLICY,
        old_reviews_reclassified=False,
    )
    return result


def inspect_alignment(raw, request):
    try:
        result = validate_alignment(raw, request)
    except ReviewError as error:
        return dict(
            interface_admitted=False,
            semantic_consistent=False,
            validation=None,
            error=str(error),
            error_kind="mechanical_interface",
            reviewer=request.get("reviewer"),
            task_id=request.get("task_id"),
            task_bundle_sha256=request.get("task_bundle_sha256"),
            slot_review_bindings=request.get("slot_review_bindings"),
            raw_review_sha256=hashlib.sha256(raw.encode()).hexdigest()
            if isinstance(raw, str)
            else None,
            pairs=None,
            wire_protocol=WIRE_PROTOCOL,
        )
    errors = [
        p["semantic_validation_error"]
        for p in result["pairs"].values()
        if p["semantic_validation_error"]
    ]
    return dict(
        interface_admitted=True,
        semantic_consistent=result["semantic_consistent"],
        validation=result,
        error=errors or None,
        error_kind="semantic_inconsistency" if errors else None,
    )


def resolve_decomposed_pair(prepared, slot_reviews0, slot_reviews1, alignment0, alignment1):
    for side in (slot_reviews0, slot_reviews1):
        _versioned_slots(side)
    for alignment in (alignment0, alignment1):
        if alignment is not None:
            _require(
                alignment.get("wire_protocol") == WIRE_PROTOCOL,
                "prospective resolver cannot mix historical alignment protocols",
            )
    result = baseline.resolve_decomposed_pair(
        prepared,
        slot_reviews0,
        slot_reviews1,
        alignment0,
        alignment1,
        allow_nonassertive_context=True,
    )
    for sid, item in result["slots"].items():
        manifest = item["encoding_manifest"]
        if manifest is None:
            continue
        # Preserve original per-fragment granularity rather than canonical merged
        # masks: two adjacent empty Q fragments remain two independently checked
        # zero-target fragments. No model label is rewritten or supplied here.
        zero = []
        own = slot_reviews0[sid]
        for span in own["parsed"]["slot"]["mask"]:
            if span["label"] != "nonassertive_context":
                continue
            doc = own["document_index"][span["doc_id"]]
            zero.append(
                {key: span[key] for key in ("doc_id", "start", "end", "quote")}
                | dict(
                    original_segment_id=doc["original_segment_id"],
                    layer="context",
                    label="nonassertive_context",
                    proposition_ids=[],
                )
            )
        manifest.update(
            slot_review_protocol=SLOT_PROTOCOL,
            alignment_protocol=WIRE_PROTOCOL,
            semantic_mask_policy=MASK_POLICY,
            nonassertive_context_spans=zero,
            nonassertive_context_target_loss=0,
        )
    unencodable = [
        sid
        for sid in result["valid_slots_retained"]
        if result["slots"][sid]["encoding_manifest"] is None
    ]
    result.update(
        schema="v7_decomposed_pair_resolution.v1",
        slot_review_protocol=SLOT_PROTOCOL,
        alignment_protocol=WIRE_PROTOCOL,
        mask_policy=MASK_POLICY,
        unencodable_jointly_qualified_slots=unencodable,
        common_kernel_material_ready=result["task_mapping"] == "complete" and not unencodable,
        no_partial_valid_subset_substitution=True,
        actual_training_performed=False,
        old_reviews_reclassified=False,
    )
    return result


def encode_reviewed_probe_for_student(episode, resolved_mask, tokenizer, **kwargs):
    """Version-bound facade over the unchanged original-positive-span encoder."""
    _require(
        resolved_mask.get("slot_review_protocol") == SLOT_PROTOCOL
        and resolved_mask.get("alignment_protocol") == WIRE_PROTOCOL
        and resolved_mask.get("semantic_mask_policy") == MASK_POLICY
        and resolved_mask.get("nonassertive_context_target_loss") == 0,
        "prospective encoding requires this explicit mask/alignment version",
    )
    view = public_trajectory_view(episode, slot_id=resolved_mask.get("slot_id"))
    documents = {doc["segment_id"]: doc for doc in view["segments"]}
    for zero in resolved_mask["nonassertive_context_spans"]:
        document = documents.get(zero["original_segment_id"])
        _require(
            zero["label"] == "nonassertive_context"
            and not zero["proposition_ids"]
            and zero["layer"] == "context"
            and is_nonassertive_context_fragment(zero["quote"]),
            "invalid registered zero-context fragment",
        )
        _require(
            document is not None
            and document["kind"] == "public_content"
            and type(zero["start"]) is int
            and type(zero["end"]) is int
            and 0 <= zero["start"] < zero["end"] <= len(document["text"])
            and document["text"][zero["start"] : zero["end"]] == zero["quote"],
            "zero-context evidence is not an exact original public-content span",
        )
        for positive in resolved_mask["positive_content_spans"]:
            _require(
                zero["original_segment_id"] != positive["original_segment_id"]
                or zero["end"] <= positive["start"]
                or positive["end"] <= zero["start"],
                "nonassertive context overlaps a positive Student target",
            )
    encoded = encode_base(episode, resolved_mask, tokenizer, **kwargs)
    result = dict(encoded)
    result.pop("encoding_id")
    result.update(
        schema="v7_student_encoding.v1",
        encoding_policy=ENCODING_POLICY,
        underlying_encoding_id=encoded["encoding_id"],
        slot_review_protocol=SLOT_PROTOCOL,
        alignment_protocol=WIRE_PROTOCOL,
        semantic_mask_policy=MASK_POLICY,
        nonassertive_context_target_loss=0,
        actual_model_or_training_calls=0,
    )
    return result | {"encoding_id": "v7_student_encoding:" + digest(result)}
