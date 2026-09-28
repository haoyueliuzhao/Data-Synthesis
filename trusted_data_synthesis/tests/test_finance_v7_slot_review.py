"""Synthetic v4 locator controls; no new observed-model pass rate is implied."""

import copy
import hashlib
import json

import pytest
from test_finance_semantic_review import fixture_bundle, fixture_review
from test_finance_v6_slot_review import encoded_fixture

from trusted_synthesis.finance_research.v7_slot_review import (
    capacity_features,
    inspect_slot_review,
    slot_review_request,
    validate_slot_review,
)


def typed_fixture(request, review):
    old = encoded_fixture(request["semantic_baseline_request"], review)
    aliases = {v: k for k, v in request["typed_to_baseline_locators"].items()}

    def refs(items):
        return [aliases[e] for e in items]

    for term in old["terms"]:
        term["public_source_anchor_ids"] = refs(term.pop("source_doc_ids"))
    for prop in old["propositions"]:
        for before, after in (
            ("text", "model_claim_ids"),
            ("support", "support_evidence_ids"),
            ("retraction", "retraction_model_ids"),
        ):
            prop[after] = refs(prop.pop(before))
    actions = {}
    for eid, action in old["actions"].items():
        action["evidence"] = refs(action["evidence"])
        actions[aliases[eid]] = action
    old["actions"] = actions
    old["mask"] = {aliases[eid]: item for eid, item in old["mask"].items()}
    for update in old["updates"]:
        for key in ("action_doc_id", "observation_doc_id"):
            update[key] = aliases[update[key]]
        for key in ("evidence", "nonredundancy_evidence"):
            update[key] = refs(update[key])
    for node in old["semantic_graph"]["nodes"]:
        node["public_source_anchor_ids"] = refs(node.pop("source_doc_ids"))
        node["evidence"] = refs(node["evidence"])
    for edge in old["semantic_graph"]["edges"]:
        edge["evidence"] = refs(edge["evidence"])
    return old


def setup(reviewer=0):
    bundle = fixture_bundle()
    req = slot_review_request(bundle, "s0", {"program": "add(120, 0)", "answer": 120}, reviewer)
    return req, typed_fixture(req, fixture_review(bundle, reviewer))


def test_typed_roundtrip_preserves_semantics_and_separately_hashes_actual_response():
    req, review = setup()
    raw = json.dumps(review)
    result = validate_slot_review(raw, req)
    assert result["wire_protocol"] == "v6_slot_review.v4"
    assert result["interface_admitted"] and result["semantic_consistent"]
    assert result["reported_v_trace"] == result["v_trace"] == "valid"
    assert result["derived"]["chi"] == 0
    assert result["raw_review_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert (
        len(
            {
                result[k]
                for k in (
                    "raw_review_sha256",
                    "locator_mapped_review_sha256",
                    "expanded_review_sha256",
                )
            }
        )
        == 3
    )
    assert not result["locator_mapping_is_another_model_response"]
    assert not result["semantic_repair_performed"]
    assert result["parsed"]["terms"][0]["source_doc_ids"] == ["shared/source"]
    assert result["parsed"]["slot"]["propositions"][0]["text"][0]["quote"] == "Revenue is 120."
    assert result["encoding_manifest"] is None


def test_typed_schema_and_catalog_have_clear_roles_and_no_legacy_wire_fields():
    req, _ = setup()
    catalog = req["document_catalog"]
    prefixes = {
        "source_text": "src_",
        "public_content": "text_",
        "action_arguments": "action_",
        "tool_observation": "obs_",
    }
    assert all(name.startswith(prefixes[item["kind"]]) for name, item in catalog.items())
    for item in catalog.values():
        if "observes_action_id" in item:
            assert item["observes_action_id"].startswith("action_")
    schema = req["strict_tool"]["function"]["parameters"]
    terms = schema["properties"]["terms"]["items"]["properties"]
    assert "source_doc_ids" not in terms
    assert all(e.startswith("src_") for e in terms["public_source_anchor_ids"]["items"]["enum"])
    props = schema["properties"]["propositions"]["items"]["properties"]
    assert {"model_claim_ids", "support_evidence_ids", "retraction_model_ids"} <= set(props)
    assert not {"text", "support", "retraction"} & set(props)
    assert all(
        e.startswith(("text_", "action_")) for e in props["model_claim_ids"]["items"]["enum"]
    )
    assert set(schema["properties"]["actions"]["properties"]) == {"action_0"}
    assert set(schema["properties"]["mask"]["properties"]) == {"text_0", "action_0"}
    payload = json.loads(req["messages"][1]["content"])
    assert payload["document_catalog"] == catalog
    assert "semantic_baseline_request" not in payload and "output_schema" not in payload
    assert "SOURCE ANCHOR IS NOT OBSERVATION EVIDENCE" in req["messages"][0]["content"]
    assert "source_doc_ids" not in req["messages"][0]["content"]
    assert capacity_features(req)["target_fragment_count"] == 2


@pytest.mark.parametrize(
    "where",
    ["term", "node", "claim", "legacy_term", "missing_mask", "legacy_eid", "wrong_action_key"],
)
def test_wrong_typed_roles_remain_interface_errors_never_substituted(where):
    req, review = setup()
    if where == "term":
        review["terms"][0]["public_source_anchor_ids"] = ["obs_0"]
    elif where == "node":
        review["semantic_graph"]["nodes"][0]["public_source_anchor_ids"] = ["obs_0"]
    elif where == "claim":
        review["propositions"][0]["model_claim_ids"] = ["src_0"]
    elif where == "legacy_term":
        review["terms"][0]["source_doc_ids"] = review["terms"][0].pop("public_source_anchor_ids")
    elif where == "missing_mask":
        review["mask"].pop("text_0")
    elif where == "legacy_eid":
        review["propositions"][0]["model_claim_ids"] = ["e2"]
    elif where == "wrong_action_key":
        review["actions"]["obs_0"] = review["actions"].pop("action_0")
    result = inspect_slot_review(json.dumps(review), req)
    assert not result["interface_admitted"]
    assert result["validation"] is None and result["v_trace"] == "unknown"


def test_actual_observation_can_be_evidence_but_never_becomes_a_source_anchor():
    req, review = setup()
    review["propositions"][0]["support_evidence_ids"].append("obs_0")
    review["semantic_graph"]["nodes"][0]["evidence"].append("obs_0")
    result = validate_slot_review(json.dumps(review), req)
    assert result["interface_admitted"]
    assert result["parsed"]["terms"][0]["source_doc_ids"] == ["shared/source"]
    evidence = result["parsed"]["slot"]["semantic_graph"]["nodes"][0]["evidence"]
    assert any(e["doc_id"] == "slot/s0/observation" for e in evidence)


def test_semantic_failure_remains_unknown_with_original_reported_judgment():
    req, review = setup()
    review["propositions"][0]["judgment"] = "unknown"
    result = inspect_slot_review(json.dumps(review), req)
    assert result["interface_admitted"] and not result["semantic_consistent"]
    value = result["validation"]
    assert value["reported_v_trace"] == value["parsed"]["slot"]["v_trace"] == "valid"
    assert value["v_trace"] == "unknown" and value["derived"] is None
    assert value["positive_target_mask"] is None


def test_capacity_fields_do_not_change_binding_and_local_baseline_is_not_on_wire():
    req, review = setup()
    req.update(max_output_tokens=16384, capacity_policy_id="registered-fixture")
    assert validate_slot_review(json.dumps(review), req)["interface_admitted"]
    bad = copy.deepcopy(req)
    bad["typed_to_baseline_locators"]["src_0"] = bad["typed_to_baseline_locators"]["obs_0"]
    assert not inspect_slot_review(json.dumps(review), bad)["interface_admitted"]
    assert {d["slot_id"] for d in req["document_index"].values()} == {None, "s0"}
    assert not req["other_reviewer_output_visible"] and not req["other_slot_trajectories_visible"]


def test_empty_action_observation_domains_do_not_create_fake_locators_or_empty_enum():
    bundle = fixture_bundle()
    view = bundle["slots"][0]["trajectory"]
    view["segments"] = [
        s for s in view["segments"] if s["kind"] not in {"action_arguments", "tool_observation"}
    ]
    view["turns"][0]["actions"] = []
    view["events"] = []
    req = slot_review_request(bundle, "s0", {}, 0)
    assert not any(e.startswith(("action_", "obs_")) for e in req["document_catalog"])
    assert '"enum": []' not in json.dumps(req["strict_tool"])


@pytest.mark.parametrize("extra_shared_sources", [0, 20])
def test_sort_keys_disk_roundtrip_preserves_original_typed_ids_and_wire_bytes(extra_shared_sources):
    bundle = fixture_bundle()
    for slot in bundle["slots"]:
        for i in range(extra_shared_sources):
            text = f"Synthetic unchanged catalog entry {i}."
            slot["trajectory"]["segments"].append(
                dict(
                    segment_id=f"extra_source_{i:02}",
                    kind="source_text",
                    text=text,
                    start=0,
                    end=len(text),
                )
            )
    request = slot_review_request(bundle, "s0", {}, 0)
    review = typed_fixture(request, fixture_review(bundle))
    raw_arguments = json.dumps(review)
    before = validate_slot_review(raw_arguments, request)
    loaded = json.loads(json.dumps(request, ensure_ascii=False, sort_keys=True))
    if extra_shared_sources:
        assert list(loaded["semantic_baseline_request"]["document_catalog"])[:3] == [
            "e0",
            "e1",
            "e10",
        ]
    assert loaded["messages"] == request["messages"]
    assert loaded["typed_to_baseline_locators"] == request["typed_to_baseline_locators"]
    assert validate_slot_review(raw_arguments, loaded) == before
