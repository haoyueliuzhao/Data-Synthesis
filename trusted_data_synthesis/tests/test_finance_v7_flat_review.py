"""Flat wire controls, synthetic judgments and one mocked paid transport only."""

import copy
import hashlib
import json

import pytest
from test_finance_research_probe_provider import Client
from test_finance_semantic_review import fixture_bundle
from test_finance_v6_strict_review_provider import call, ledger_fixture, response_fixture
from test_finance_v7_slot_review import setup as typed_setup

from trusted_synthesis.finance_research import v7_flat_review as flat
from trusted_synthesis.finance_research import v7_mask_review as baseline
from trusted_synthesis.finance_research.v6_review_provider import STRICT_ENDPOINT


def setup():
    typed, value = typed_setup()
    v5 = baseline._request(typed)
    v5.update(max_output_tokens=16384, capacity_policy_id="registered-v6-fixture")
    request = flat.flat_request(v5)
    graph = value.pop("semantic_graph")
    value.update(nodes=graph["nodes"], edges=graph["edges"])
    value["actions"] = [dict(action_id=k, **v) for k, v in value["actions"].items()]
    value["mask"] = [dict(target_id=k, **v) for k, v in value["mask"].items()]
    return request, value


def test_bijective_projection_preserves_semantics_without_faking_another_response():
    request, value = setup()
    raw = json.dumps(value)
    result = flat.validate_slot_review(raw, request)
    expected = baseline.validate_slot_review(
        flat._mapped_arguments(raw, request["flat_baseline_request"]),
        request["flat_baseline_request"],
    )
    assert result["interface_admitted"] and result["semantic_consistent"]
    assert result["v_trace"] == "valid" and result["derived"]["chi"] == 0
    assert result["parsed"] == expected["parsed"]
    assert result["wire_protocol"] == result["schema"] == "v6_slot_review.v6"
    assert result["raw_review_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert result["raw_review_sha256"] != result["flat_mapped_review_sha256"]
    assert not result["original_review_reclassified"] and not result["host_semantic_repair"]
    assert request["max_output_tokens"] == 16384
    assert request["capacity_policy_id"] == "registered-v6-fixture"


def test_sorted_disk_roundtrip_and_actual_factory_are_stable():
    request, value = setup()
    restored = json.loads(json.dumps(request, sort_keys=True))
    assert flat.validate_slot_review(json.dumps(value), restored)["semantic_consistent"]
    recreated = flat.flat_request(restored["flat_baseline_request"])
    assert recreated == request
    real = flat.slot_review_request(
        fixture_bundle(), "s0", {"program": "add(120, 0)", "answer": 120}
    )
    assert real["wire_protocol"] == flat.WIRE_PROTOCOL
    schema = request["strict_tool"]["function"]["parameters"]
    assert "semantic_graph" not in schema["properties"]
    assert {"terms", "nodes", "edges"} <= set(schema["properties"])
    assert set(schema["required"]) == set(schema["properties"])
    for field in ("actions", "mask"):
        assert schema["properties"][field]["type"] == "array"
    assert "PROSPECTIVE UPDATE-COHERENCE" in request["messages"][0]["content"]
    payload = json.loads(request["messages"][1]["content"])
    assert payload["wire_protocol"] == flat.WIRE_PROTOCOL
    assert "flat_baseline_request" not in payload and "strict_tool" not in payload


@pytest.mark.parametrize(
    "where",
    [
        "duplicate_mask",
        "missing_mask",
        "duplicate_action",
        "missing_action",
        "wrong_kind_action",
        "unknown_target",
        "extra_root",
        "extra_record",
        "missing_terms",
        "old_graph",
        "extra_node",
        "wrong_source",
        "action_nonassertive",
    ],
)
def test_no_missing_extra_duplicate_or_wrong_kind_is_repaired(where):
    request, value = setup()
    if where == "duplicate_mask":
        value["mask"].append(copy.deepcopy(value["mask"][0]))
    elif where == "missing_mask":
        value["mask"].pop()
    elif where == "duplicate_action":
        value["actions"].append(copy.deepcopy(value["actions"][0]))
    elif where == "missing_action":
        value["actions"].clear()
    elif where == "wrong_kind_action":
        value["actions"][0]["action_id"] = "obs_0"
    elif where == "unknown_target":
        value["mask"][0]["target_id"] = "text_999999"
    elif where == "extra_root":
        value["edges_note"] = "n/a"
    elif where == "extra_record":
        value["mask"][0]["note"] = "n/a"
    elif where == "missing_terms":
        value.pop("terms")
    elif where == "old_graph":
        value["semantic_graph"] = {"nodes": [], "edges": []}
    elif where == "extra_node":
        value["nodes"][0]["note"] = "n/a"
    elif where == "wrong_source":
        value["terms"][0]["public_source_anchor_ids"] = ["obs_0"]
    else:
        next(row for row in value["mask"] if row["target_id"].startswith("action_"))["label"] = (
            "nonassertive_context"
        )
    result = flat.inspect_slot_review(json.dumps(value), request)
    assert not result["interface_admitted"] and result["v_trace"] == "unknown"
    assert result["validation"] is None


@pytest.mark.parametrize("suffix", [" {}", ', "v_trace":"valid"}', " trailing"])
def test_multiple_json_or_trailing_data_remains_failure(suffix):
    request, value = setup()
    assert not flat.inspect_slot_review(json.dumps(value) + suffix, request)["interface_admitted"]


def test_semantic_unknown_and_old_shape_failures_not_reclassified():
    request, value = setup()
    value["propositions"][0]["judgment"] = "unknown"
    result = flat.inspect_slot_review(json.dumps(value), request)
    assert result["interface_admitted"] and not result["semantic_consistent"]
    assert result["validation"]["v_trace"] == "unknown"
    assert result["validation"]["reported_v_trace"] == "valid"
    assert result["validation"]["positive_target_mask"] is None
    old = json.loads(flat._mapped_arguments(json.dumps(value), request["flat_baseline_request"]))
    old["semantic_graph"]["terms"] = old.pop("terms")
    assert not baseline.inspect_slot_review(json.dumps(old), request["flat_baseline_request"])[
        "interface_admitted"
    ]
    assert not flat.inspect_slot_review(json.dumps(old), request)["interface_admitted"]


def test_bound_schema_or_baseline_tampering_is_not_admitted():
    request, value = setup()
    request["strict_tool"]["function"]["parameters"]["required"].remove("terms")
    assert not flat.inspect_slot_review(json.dumps(value), request)["interface_admitted"]


def test_actual_new_factory_reaches_only_existing_strict_flash_transport(tmp_path):
    request, value = setup()
    raw = json.dumps(value)
    ledger, client = ledger_fixture(tmp_path), Client(response_fixture(raw))
    artifact = call(ledger, client, request, episode_id="v7flat6/synthetic/reviewer0")
    assert len(client.calls) == 1 and client.calls[0][0] == STRICT_ENDPOINT
    body = json.loads(client.calls[0][1]["content"])
    assert artifact["wire_protocol"] == flat.WIRE_PROTOCOL
    assert artifact["review_text"] == raw
    assert body["tools"] == [request["strict_tool"]]
    assert body["tool_choice"] == dict(type="function", function=dict(name="submit_review"))
    assert body["model"] == "deepseek-flash" and body["thinking"] == {"type": "disabled"}
    assert body["max_tokens"] == 16384 and body["temperature"] == 0
    assert "response_format" not in body
    assert ledger.snapshot()["held_microcny"] == 0
