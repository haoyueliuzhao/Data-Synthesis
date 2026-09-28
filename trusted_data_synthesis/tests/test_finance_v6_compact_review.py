"""Mechanical fixture controls only: these are NOT model review observations."""

import copy
import hashlib
import json

import pytest
from test_finance_semantic_review import fixture_bundle, fixture_review, mechanical

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.semantic_review import ReviewError, resolve_pair
from trusted_synthesis.finance_research.v6_compact_review import (
    capacity_features,
    compact_review_request,
    fragment_ranges,
    validate_compact_review,
)


def encoded_fixture(request, review):
    """Encode an already-authored synthetic test fixture, never a real response."""
    local = request["compact_catalog"]
    docs = {v: k for k, v in local["document_aliases"].items()}
    slots = {v: k for k, v in local["slot_aliases"].items()}
    spans = {digest(v): k for k, v in local["spans"].items()}

    def convert(value):
        if isinstance(value, dict):
            if {"doc_id", "start", "end", "quote"} <= set(value):
                evidence = {k: value[k] for k in ("doc_id", "start", "end", "quote")}
                sid = spans[digest(evidence)]
                if "label" in value:
                    return dict(
                        span_id=sid,
                        **{k: value[k] for k in ("label", "component", "proposition_ids")},
                    )
                return sid
            return {k: convert(v) for k, v in value.items()}
        if isinstance(value, list):
            return [convert(v) for v in value]
        if isinstance(value, str):
            return docs.get(value, slots.get(value, value))
        return value

    return convert({k: v for k, v in review.items() if k in {"terms", "slots", "relations"}})


def setup(reviewer=0):
    bundle = fixture_bundle()
    request = compact_review_request(bundle, {"program": "add(120, 0)", "answer": 120}, reviewer)
    return request, encoded_fixture(request, fixture_review(bundle, reviewer))


def test_compact_roundtrip_preserves_q_v_mapper_and_masks():
    a, aa = setup(0)
    b, bb = setup(1)
    raw_a, raw_b = json.dumps(aa), json.dumps(bb)
    checked_a, checked_b = validate_compact_review(raw_a, a), validate_compact_review(raw_b, b)
    checks = mechanical()
    checks["s0"]["native_correct"] = False
    result = resolve_pair(checked_a, checked_b, checks)
    assert result["task_mapping"] == "complete"
    assert len(result["process_valid_slots_retained"]) == 8
    assert len(result["valid_slots_retained"]) == 7
    assert result["slots"]["s0"]["v_trace"] == "valid"
    assert result["slots"]["s0"]["q_native"] is False
    assert len({result["slots"][sid]["state_id"] for sid in result["valid_slots_retained"]}) == 1
    assert (
        result["slots"]["s1"]["encoding_manifest"]["positive_content_spans"][0]["quote"]
        == "Revenue is 120."
    )
    assert checked_a["raw_review_sha256"] == hashlib.sha256(raw_a.encode()).hexdigest()
    assert checked_a["expanded_review_sha256"] != checked_a["raw_review_sha256"]
    assert not checked_a["semantic_repair_performed"]
    assert not result["human_reviewed"] and not result["mathematical_proof"]
    assert a["document_catalog"] == b["document_catalog"]
    assert a["messages"] != b["messages"]
    assert not a["other_reviewer_output_visible"]


def test_wire_catalog_contains_no_long_ids_or_offsets_or_duplicate_raw_docs():
    request, _ = setup()
    payload = json.loads(request["messages"][1]["content"])
    assert "document_index" not in payload and "compact_catalog" not in payload
    assert "quote" not in payload["output_schema"]["$defs"]
    for name, doc in payload["document_catalog"].items():
        assert name.startswith("d")
        assert "episode_sha256" not in doc and "original_segment_id" not in doc
        for fragment in doc["fragments"]:
            assert set(fragment) == {"span_id", "text"}
    assert "zero-based half-open Unicode" not in request["messages"][0]["content"]
    features = capacity_features(request)
    assert features["action_count"] == 8
    assert features["target_fragment_count"] == 16
    assert not features["exact_api_token_count_known"]


@pytest.mark.parametrize(
    "text",
    ["", "a", "Revenue 120.\n\nNow 140.  ", "a " * 600, "x" * 2500, "中文。\n现金 12.5%！\n "],
)
def test_fragment_partition_preserves_every_character(text):
    ranges = fragment_ranges(text)
    assert "".join(text[a:b] for a, b in ranges) == text
    assert all(0 <= a < b <= len(text) for a, b in ranges)
    assert all(left[1] == right[0] for left, right in zip(ranges, ranges[1:], strict=False))
    if text:
        assert fragment_ranges(text, atomic=True) == [(0, len(text))]


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_fragment",
        "missing_mask",
        "duplicate_mask",
        "source_mask",
        "cross_slot_mask",
        "changed_catalog",
        "model",
        "missing_pair",
    ],
)
def test_invalid_locators_masks_and_bindings_never_repaired(mutation):
    request, review = setup()
    if mutation == "unknown_fragment":
        review["slots"][0]["propositions"][0]["text"] = ["absent"]
    elif mutation == "missing_mask":
        review["slots"][0]["mask"].pop()
    elif mutation == "duplicate_mask":
        review["slots"][0]["mask"].append(copy.deepcopy(review["slots"][0]["mask"][0]))
    elif mutation == "source_mask":
        source = review["slots"][0]["propositions"][0]["support"][0]
        review["slots"][0]["mask"][0]["span_id"] = source
    elif mutation == "cross_slot_mask":
        review["slots"][0]["mask"][0]["span_id"] = review["slots"][1]["mask"][0]["span_id"]
    elif mutation == "changed_catalog":
        request["document_catalog"]["d0"]["fragments"][0]["text"] += " invented"
    elif mutation == "model":
        request["model"] = "another-model"
    elif mutation == "missing_pair":
        review["relations"].pop()
    with pytest.raises(ValueError):
        validate_compact_review(json.dumps(review), request)


def test_disagreement_preserves_all_valid_packages_and_unknown_mapper():
    a, aa = setup(0)
    b, bb = setup(1)
    bb["relations"][0].update(relation="unknown", basis="unresolved")
    result = resolve_pair(
        validate_compact_review(json.dumps(aa), a),
        validate_compact_review(json.dumps(bb), b),
        mechanical(),
    )
    assert result["task_mapping"] == "incomplete"
    assert len(result["valid_slots_retained"]) == 8
    assert all(
        v["v_trace"] == "valid" and v["mapper"] == "unknown" for v in result["slots"].values()
    )


def test_duplicate_json_keys_are_not_accepted():
    request, _ = setup()
    with pytest.raises(ReviewError, match="duplicate"):
        validate_compact_review('{"terms":[],"terms":[]}', request)
