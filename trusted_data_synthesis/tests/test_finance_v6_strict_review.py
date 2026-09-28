"""Synthetic fixture controls, not paid model semantic-validation results."""

import copy
import hashlib
import json

import pytest
from test_finance_semantic_review import fixture_bundle, fixture_review, mechanical

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.semantic_review import ReviewError, resolve_pair
from trusted_synthesis.finance_research.v6_strict_review import (
    capacity_features,
    strict_review_request,
    validate_strict_review,
)


def encoded_fixture(request, review):
    local = request["compact_catalog"]
    by_document = {}
    for eid, span in local["spans"].items():
        by_document.setdefault(span["doc_id"], eid)
    by_evidence = {digest(span): eid for eid, span in local["spans"].items()}
    slots = {v: k for k, v in local["slot_aliases"].items()}

    def encode(value):
        if isinstance(value, dict):
            if {"doc_id", "start", "end", "quote"} <= set(value):
                ev = {k: value[k] for k in ("doc_id", "start", "end", "quote")}
                eid = by_evidence[digest(ev)]
                if "label" in value:
                    return dict(
                        span_id=eid,
                        **{k: value[k] for k in ("label", "component", "proposition_ids")},
                    )
                return eid
            return {k: encode(v) for k, v in value.items()}
        if isinstance(value, list):
            return [encode(v) for v in value]
        if isinstance(value, str):
            return by_document.get(value, slots.get(value, value))
        return value

    return encode({k: v for k, v in review.items() if k in {"terms", "slots", "relations"}})


def setup(reviewer=0):
    bundle = fixture_bundle()
    request = strict_review_request(bundle, {"program": "add(120, 0)", "answer": 120}, reviewer)
    return request, encoded_fixture(request, fixture_review(bundle, reviewer))


def test_roundtrip_retains_original_semantics_and_actual_raw_arguments_hash():
    a, aa = setup(0)
    b, bb = setup(1)
    raw_a = json.dumps(aa)
    checked_a = validate_strict_review(raw_a, a)
    checked_b = validate_strict_review(json.dumps(bb), b)
    checks = mechanical()
    checks["s0"]["native_correct"] = False
    result = resolve_pair(checked_a, checked_b, checks)
    assert len(result["process_valid_slots_retained"]) == 8
    assert len(result["valid_slots_retained"]) == 7
    assert result["slots"]["s0"]["v_trace"] == "valid"
    assert result["slots"]["s0"]["q_native"] is False
    assert result["task_mapping"] == "complete"
    assert len({result["slots"][sid]["state_id"] for sid in result["valid_slots_retained"]}) == 1
    assert checked_a["raw_review_sha256"] == hashlib.sha256(raw_a.encode()).hexdigest()
    assert checked_a["expanded_review_sha256"] != checked_a["raw_review_sha256"]
    assert not checked_a["semantic_repair_performed"]
    assert not checked_a["strict_format_is_semantic_correctness"]
    assert a["document_catalog"] == b["document_catalog"]
    assert a["messages"] != b["messages"]
    assert not a["other_reviewer_output_visible"]


def test_strict_schema_has_only_supported_keywords_required_properties_and_flat_enums():
    request, _ = setup()
    schema = request["strict_tool"]["function"]["parameters"]
    allowed = {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "anyOf",
        "pattern",
    }
    catalog = request["document_catalog"]

    def check(node, name=None):
        assert set(node) <= allowed
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
            for key, value in node["properties"].items():
                check(value, key)
        if "items" in node:
            check(node["items"])
        if name in {
            "source_doc_ids",
            "evidence",
            "text",
            "support",
            "retraction",
            "nonredundancy_evidence",
        }:
            assert set(node["items"]["enum"]) <= set(catalog)
            if name == "source_doc_ids":
                assert all(
                    catalog[x]["kind"] in {"question", "source_text", "source_table_cell"}
                    for x in node["items"]["enum"]
                )
        if name in {"action_doc_id", "observation_doc_id", "span_id"}:
            assert set(node["enum"]) <= set(catalog)
        if name in {"slot_id", "left", "right"}:
            assert node["enum"] == [f"s{i}" for i in range(8)]

    check(schema)
    assert request["strict_tool"]["function"]["name"] == "submit_review"
    assert request["strict_tool"]["function"]["strict"] is True
    payload = json.loads(request["messages"][1]["content"])
    assert "output_schema" not in payload
    assert payload["document_catalog"] == catalog
    assert all(key == f"e{i}" for i, key in enumerate(catalog))
    assert "d0,d1" not in request["messages"][0]["content"]
    assert "Call submit_review exactly once" in request["messages"][0]["content"]
    assert capacity_features(request)["strict_tool_chars"] > 0
    assert capacity_features(request)["target_fragment_count"] == 16


def test_flat_catalog_preserves_all_bytes_and_actual_observation_links():
    request, _ = setup()
    docs = request["document_index"]
    spans = request["compact_catalog"]["spans"]
    for doc_id, doc in docs.items():
        ordered = sorted(
            (v for v in spans.values() if v["doc_id"] == doc_id), key=lambda v: v["start"]
        )
        assert "".join(s["quote"] for s in ordered) == doc["text"]
        if doc["kind"] == "action_arguments":
            assert len(ordered) == 1
    catalog = request["document_catalog"]
    for value in catalog.values():
        if value["kind"] == "tool_observation":
            action = catalog[value["observes_action_id"]]
            assert action["kind"] == "action_arguments"
            assert action["slot_id"] == value["slot_id"]


@pytest.mark.parametrize(
    "mutation",
    [
        "doc_fragment_namespace",
        "wrong_action_kind",
        "wrong_source_kind",
        "missing_mask",
        "duplicate_mask",
        "cross_slot",
        "catalog",
        "schema",
        "missing_pair",
        "unknown_semantics",
    ],
)
def test_strict_shape_does_not_bypass_local_semantic_or_provenance_checks(mutation):
    request, review = setup()
    if mutation == "doc_fragment_namespace":
        review["slots"][0]["propositions"][0]["text"] = ["d0p0"]
    elif mutation == "wrong_action_kind":
        review["slots"][0]["actions"][0]["action_doc_id"] = review["slots"][0]["propositions"][0][
            "support"
        ][0]
    elif mutation == "wrong_source_kind":
        review["terms"][0]["source_doc_ids"] = [review["slots"][0]["actions"][0]["action_doc_id"]]
    elif mutation == "missing_mask":
        review["slots"][0]["mask"].pop()
    elif mutation == "duplicate_mask":
        review["slots"][0]["mask"].append(copy.deepcopy(review["slots"][0]["mask"][0]))
    elif mutation == "cross_slot":
        review["slots"][0]["mask"][0]["span_id"] = review["slots"][1]["mask"][0]["span_id"]
    elif mutation == "catalog":
        request["document_catalog"]["e0"]["text"] += " invented"
    elif mutation == "schema":
        request["strict_tool"]["function"]["parameters"]["additionalProperties"] = True
    elif mutation == "missing_pair":
        review["relations"].pop()
    elif mutation == "unknown_semantics":
        review["slots"][0]["propositions"][0]["judgment"] = "unknown"
    with pytest.raises(ValueError):
        validate_strict_review(json.dumps(review), request)


def test_semantic_disagreement_retains_all_common_valid_candidates():
    a, aa = setup(0)
    b, bb = setup(1)
    bb["relations"][0].update(relation="unknown", basis="unresolved")
    result = resolve_pair(
        validate_strict_review(json.dumps(aa), a),
        validate_strict_review(json.dumps(bb), b),
        mechanical(),
    )
    assert result["task_mapping"] == "incomplete"
    assert len(result["valid_slots_retained"]) == 8
    assert all(
        v["v_trace"] == "valid" and v["mapper"] == "unknown" for v in result["slots"].values()
    )


def test_duplicate_argument_keys_remain_invalid():
    request, _ = setup()
    with pytest.raises(ReviewError, match="duplicate"):
        validate_strict_review('{"terms":[],"terms":[]}', request)
