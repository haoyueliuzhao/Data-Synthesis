"""Synthetic mechanical/semantic controls, not observed model pass rates."""

import copy
import hashlib
import json

import pytest
from test_finance_semantic_review import fixture_bundle, fixture_review

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.semantic_review import ReviewError
from trusted_synthesis.finance_research.v6_slot_review import (
    capacity_features,
    inspect_slot_review,
    slot_review_request,
    validate_slot_review,
)


def encoded_fixture(request, review):
    spans = request["compact_catalog"]["spans"]
    by_evidence = {digest(v): k for k, v in spans.items()}
    by_document = {}
    for eid, value in spans.items():
        by_document.setdefault(value["doc_id"], eid)
    slot = copy.deepcopy(next(s for s in review["slots"] if s["slot_id"] == request["slot_id"]))
    slot.pop("slot_id")
    slot["terms"] = copy.deepcopy(review["terms"])

    def encode(value):
        if isinstance(value, dict):
            if {"doc_id", "start", "end", "quote"} <= set(value):
                return by_evidence[
                    digest({k: value[k] for k in ("doc_id", "start", "end", "quote")})
                ]
            return {k: encode(v) for k, v in value.items()}
        if isinstance(value, list):
            return [encode(v) for v in value]
        if isinstance(value, str):
            return by_document.get(value, value)
        return value

    actions = {
        by_document[a["action_doc_id"]]: encode(
            {k: v for k, v in a.items() if k != "action_doc_id"}
        )
        for a in slot.pop("actions")
    }
    masks = {
        by_evidence[digest({k: m[k] for k in ("doc_id", "start", "end", "quote")})]: {
            k: m[k] for k in ("label", "proposition_ids")
        }
        for m in slot.pop("mask")
    }
    return encode(slot) | dict(actions=actions, mask=masks)


def setup(reviewer=0):
    bundle = fixture_bundle()
    request = slot_review_request(bundle, "s0", {"program": "add(120, 0)", "answer": 120}, reviewer)
    return request, encoded_fixture(request, fixture_review(bundle, reviewer))


def test_single_slot_roundtrip_has_original_semantics_but_no_training_admission():
    request, review = setup()
    raw = json.dumps(review)
    result = validate_slot_review(raw, request)
    assert result["interface_admitted"] and result["semantic_consistent"]
    assert result["v_trace"] == result["reported_v_trace"] == "valid"
    assert result["slot_id"] == "s0" and result["reviewer"] == 0
    assert set(result["parsed"]) == {"terms", "slot"}
    assert result["parsed"]["slot"]["slot_id"] == "s0"
    assert result["parsed"]["slot"]["mask"][0]["quote"] in {
        "Revenue is 120.",
        '{"program":"add(120, 0)"}',
    }
    assert result["derived"]["chi"] == 0
    assert result["raw_review_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert result["raw_review_sha256"] != result["expanded_review_sha256"]
    assert result["requires_second_review_and_task_alignment"]
    assert result["encoding_manifest"] is None
    assert not result["human_reviewed"] and not result["mathematical_proof"]
    assert not result["semantic_repair_performed"]


def test_no_other_slot_trajectory_or_other_reviewer_visible():
    bundle = fixture_bundle()
    bundle["slots"][7]["trajectory"]["segments"][1]["text"] = "OTHER_SLOT_SECRET"
    bundle["slots"][7]["trajectory"]["segments"][1]["end"] = len("OTHER_SLOT_SECRET")
    a = slot_review_request(bundle, "s0", {}, 0)
    b = slot_review_request(bundle, "s0", {}, 1)
    payload = json.loads(a["messages"][1]["content"])
    assert "OTHER_SLOT_SECRET" not in a["messages"][1]["content"]
    assert "slots" not in payload and "output_schema" not in payload
    assert {d["slot_id"] for d in a["document_index"].values()} == {None, "s0"}
    assert not a["other_reviewer_output_visible"] and not a["other_slot_trajectories_visible"]
    assert a["document_catalog"] == b["document_catalog"]
    assert a["messages"] != b["messages"]
    assert a["task_bundle_sha256"] == digest(bundle)


def test_fixed_action_mask_schema_and_supported_keywords():
    request, _ = setup()
    parameters = request["strict_tool"]["function"]["parameters"]
    catalog = request["document_catalog"]
    for field, kinds in (
        ("actions", {"action_arguments"}),
        ("mask", {"public_content", "action_arguments"}),
    ):
        expected = {e for e, d in catalog.items() if d["kind"] in kinds}
        schema = parameters["properties"][field]
        assert set(schema["properties"]) == set(schema["required"]) == expected
        assert not schema["additionalProperties"]
        for item in schema["properties"].values():
            assert "component" not in item["properties"]
            assert "action_doc_id" not in item["properties"]
            assert "span_id" not in item["properties"]
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

    def check(node):
        assert set(node) <= allowed
        if node.get("type") == "object":
            assert set(node["required"]) == set(node["properties"])
            assert node["additionalProperties"] is False
            for child in node["properties"].values():
                check(child)
        if "items" in node:
            check(node["items"])
        assert node.get("enum") != []

    check(parameters)
    assert "slots" not in parameters["properties"] and "relations" not in parameters["properties"]
    assert capacity_features(request)["action_count"] == 1
    assert capacity_features(request)["target_fragment_count"] == 2


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_mask",
        "extra_source_mask",
        "missing_action",
        "unknown_evidence",
        "source_as_text",
        "wrong_term_source",
        "catalog",
        "request_other_slot",
        "bad_json",
    ],
)
def test_mechanical_failures_are_interface_failures(mutation):
    request, review = setup()
    if mutation == "missing_mask":
        review["mask"].pop(next(iter(review["mask"])))
    elif mutation == "extra_source_mask":
        source = review["propositions"][0]["support"][0]
        review["mask"][source] = dict(label="approved", proposition_ids=["p"])
    elif mutation == "missing_action":
        review["actions"] = {}
    elif mutation == "unknown_evidence":
        review["propositions"][0]["support"] = ["e99999"]
    elif mutation == "source_as_text":
        review["propositions"][0]["text"] = review["propositions"][0]["support"]
    elif mutation == "wrong_term_source":
        review["terms"][0]["source_doc_ids"] = list(review["actions"])
    elif mutation == "catalog":
        request["document_catalog"]["e0"]["text"] += " invented"
    elif mutation == "request_other_slot":
        request["slot_id"] = "s7"
    raw = "{" if mutation == "bad_json" else json.dumps(review)
    with pytest.raises(ReviewError):
        validate_slot_review(raw, request)
    check = inspect_slot_review(raw, request)
    assert not check["interface_admitted"] and check["error_kind"] == "mechanical_interface"
    assert check["v_trace"] == "unknown" and check["validation"] is None


@pytest.mark.parametrize(
    "mutation",
    ["unsupported_critical", "missing_action_evidence", "duplicate_term", "unbound_graph_term"],
)
def test_semantic_inconsistency_is_unknown_not_interface_failure_or_repair(mutation):
    request, review = setup()
    if mutation == "unsupported_critical":
        review["propositions"][0]["judgment"] = "unknown"
    elif mutation == "missing_action_evidence":
        next(iter(review["actions"].values()))["evidence"] = []
    elif mutation == "duplicate_term":
        review["terms"].append(copy.deepcopy(review["terms"][0]))
    elif mutation == "unbound_graph_term":
        review["semantic_graph"]["nodes"][0]["term_ids"] = ["unbound"]
    raw = json.dumps(review)
    inspected = inspect_slot_review(raw, request)
    assert inspected["interface_admitted"] and not inspected["semantic_consistent"]
    assert inspected["error_kind"] == "semantic_inconsistency"
    result = inspected["validation"]
    assert result["reported_v_trace"] == result["parsed"]["slot"]["v_trace"] == "valid"
    assert result["v_trace"] == "unknown" and result["derived"] is None
    assert result["semantic_validation_error"]
    assert result["positive_target_mask"] is None and result["encoding_manifest"] is None
    assert not result["semantic_repair_performed"]
    if mutation == "unsupported_critical":
        assert result["parsed"]["slot"]["propositions"][0]["judgment"] == "unknown"


def test_empty_action_observation_groups_have_no_empty_enum_and_no_fake_ids():
    bundle = fixture_bundle()
    view = bundle["slots"][0]["trajectory"]
    view["segments"] = [
        s for s in view["segments"] if s["kind"] not in {"action_arguments", "tool_observation"}
    ]
    view["turns"][0]["actions"] = []
    view["events"] = []
    request = slot_review_request(bundle, "s0", {}, 0)
    schema = request["strict_tool"]["function"]["parameters"]
    assert schema["properties"]["actions"]["properties"] == {}
    updates = schema["properties"]["updates"]["items"]["properties"]
    assert updates["action_doc_id"] == {"type": "string"}
    assert updates["observation_doc_id"] == {"type": "string"}
    assert '"enum": []' not in json.dumps(schema)
    review = dict(
        terms=[],
        v_trace="unknown",
        reason_codes=[],
        coverage_complete=False,
        propositions=[],
        actions={},
        updates=[],
        mask={
            e: dict(label="unknown", proposition_ids=[])
            for e, d in request["document_catalog"].items()
            if d["kind"] == "public_content"
        },
        semantic_graph=dict(nodes=[], edges=[]),
    )
    checked = inspect_slot_review(json.dumps(review), request)
    assert checked["interface_admitted"] and checked["validation"]["v_trace"] == "unknown"
    review["updates"] = [
        dict(
            kind="verification",
            prior_proposition="p",
            posterior_proposition="p",
            action_doc_id="fake",
            observation_doc_id="fake",
            decision_change="none",
            substantive=False,
            evidence=[],
            nonredundancy_evidence=[],
        )
    ]
    assert not inspect_slot_review(json.dumps(review), request)["interface_admitted"]
