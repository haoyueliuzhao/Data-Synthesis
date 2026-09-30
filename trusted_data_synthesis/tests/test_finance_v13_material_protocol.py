"""Finite typed material controls; synthetic public originals only, no dispatch."""

import copy
import json

import pytest
from test_finance_v10_process_review import fixture

from trusted_synthesis.finance_research import v11_process_review as original
from trusted_synthesis.finance_research import v13_material_protocol as protocol
from trusted_synthesis.finance_research.contracts import digest


def view(label="one"):
    episode, old, _ = fixture()
    return original.prepare_review_request(
        episode,
        slot_id="v10gen:" + digest(label),
        role="A",
        native_result=old["native_result"],
        integrity=old["integrity"],
    )["trajectory"]


def rebound(v):
    v["view_id"] = "public_trajectory:" + digest({k: x for k, x in v.items() if k != "view_id"})
    return v


def bindings(views):
    return dict(
        task_slot_ids=[v["slot_id"] for v in views],
        source_seal_id="synthetic-seal",
        private_marker="NOT_FOR_MODEL",
    )


def request(v=None):
    v = v or view()
    return protocol.prepare_projection(
        v, protocol_id="synthetic-protocol", source_bindings=bindings([v])
    )


def artifact(body, finish="tool_calls"):
    return dict(
        review_text=json.dumps(body),
        finish_reason=finish,
        review_format_error=None,
        usage={"completion_tokens": 123},
    )


def projection_body(req):
    return dict(
        status="complete",
        positive_reason_ids=list(req["domains"][0]["reason_ids"]),
        partial_positive_reason=[],
        positive_action_ids=list(req["domains"][0]["successful_action_ids"]),
    )


def test_typed_domains_preserve_all_text_and_exclude_empty_wrong_targets_and_failed_actions():
    v = view()
    req = request(v)
    d = req["domains"][0]
    units = {u["unit_id"]: u for u in d["catalog"]["units"]}
    assert all(units[i]["text"] and units[i]["kind"] == "public_content" for i in d["reason_ids"])
    payload = json.loads(req["messages"][1]["content"])
    assert payload["packages"][0]["units"] == {i: u["text"] for i, u in units.items()}
    assert "NOT_FOR_MODEL" not in json.dumps(req["messages"])
    assert "native_result" not in json.dumps(req["messages"])
    body = protocol.request_body(req)
    assert body["model"] == "deepseek-flash" and body["thinking"] == {"type": "disabled"}
    assert body["tool_choice"]["function"]["name"] == "submit_material"
    assert req["max_output_tokens"] in protocol.CAPS
    v["events"][0]["is_error"] = True
    failed = protocol.typed_domains(rebound(v))
    assert v["events"][0]["action_id"] not in failed["successful_action_ids"]
    assert v["events"][0]["event_id"] in failed["evidence_ids"]


def test_projection_success_reason_zero_and_exact_source_ranges():
    req = request()
    body = projection_body(req)
    result = protocol.inspect_projection(req, artifact(body))
    assert result["usable"] and result["projection"]["positive_actions"]
    assert result["reason_projection"]["positive_public_characters"] > 0
    assert not result["actual_model_call_receipt_verified"] and not result["production_admitted"]
    assert protocol.validate_inspection(result, req, artifact(body)) == result
    body["positive_reason_ids"] = []
    result = protocol.inspect_projection(req, artifact(body))
    assert result["usable"] and result["reason_projection"]["positive_public_characters"] == 0


@pytest.mark.parametrize(
    "fault", ["wrong_kind", "invented_action", "null_quote", "duplicate", "length", "bad_json"]
)
def test_invalid_projection_never_filters_or_rejudges_process(fault):
    req = request()
    body = projection_body(req)
    if fault == "wrong_kind":
        body["positive_reason_ids"] = [
            next(
                u["unit_id"]
                for u in req["domains"][0]["catalog"]["units"]
                if u["kind"] == "tool_observation"
            )
        ]
    elif fault == "invented_action":
        body["positive_action_ids"] = ["invented-action"]
    elif fault == "null_quote":
        body["partial_positive_reason"] = [dict(id=body["positive_reason_ids"][0], quote=None)]
    elif fault == "duplicate":
        body["positive_reason_ids"] *= 2
    art = artifact(body, "length" if fault == "length" else "tool_calls")
    if fault == "bad_json":
        art["review_text"] += "}"
    result = protocol.inspect_projection(req, art)
    assert (
        not result["usable"] and result["reason_projection"]["positive_public_characters"] is None
    )
    assert (
        result["raw_review"] == art["review_text"]
        and result["original_process_judgments_unchanged"]
    )
    assert not result["JSON_repaired"]


def test_empty_domains_fail_offline_and_future_typed_AB_cannot_dispatch():
    v = view()
    for d in v["segments"]:
        if d["kind"] == "public_content":
            d["text"] = ""
    with pytest.raises(ValueError, match="empty selectable domain"):
        request(rebound(v))
    v = view()
    for e in v["events"]:
        e["is_error"] = True
    with pytest.raises(ValueError, match="empty selectable domain"):
        request(rebound(v))
    tool = protocol.typed_ab_tool(view(), "B")
    checks = tool["function"]["parameters"]["properties"]["process"]["properties"]
    for name, check in checks.items():
        enum = check["properties"]["status"]["enum"]
        assert ("not_applicable" not in enum) is (name in protocol.CRITICAL)
    encoded = json.dumps(tool)
    assert not any(k in encoded for k in ["minItems", "maxItems", "minLength", "maxLength"])
    req = request()
    req["purpose"] = "A"
    with pytest.raises(ValueError, match="no A/B dispatch"):
        protocol.request_body(req)


def mapping_request():
    vv = [view("one"), view("two")]
    return protocol.prepare_mapping(
        vv, protocol_id="synthetic-protocol", source_bindings=bindings(vv)
    )


def mapping_body(req):
    return dict(
        mapping_status="complete",
        states=[
            dict(
                state_id="same-evidence-and-derivation",
                slot_ids=req["slot_ids"],
                semantic_summary="Same original evidence and derivation.",
                evidence_ids=[req["mapping_domains"]["evidence_ids"][0]],
                partial_evidence=[],
                chi=0,
                chi_reason="No consequential original revision established.",
                interventions=[],
            )
        ],
        ambiguities=[],
    )


def test_whole_task_mapping_uses_complete_views_and_host_locators_not_supervision():
    req = mapping_request()
    body = mapping_body(req)
    result = protocol.inspect_mapping(req, artifact(body))
    assert result["mapping_status"] == "complete" and set(result["state_by_slot"]) == set(
        req["slot_ids"]
    )
    assert result["raw_wire_annotation"] == body
    assert "start" not in json.dumps(req["strict_tool"])
    assert "start" in result["deterministic_materialized_annotation"]["states"][0]["evidence"][0]
    assert "NOT_FOR_MODEL" not in json.dumps(req["messages"])
    assert not result["production_admitted"]
    incomplete = copy.deepcopy(body)
    incomplete["states"][0]["slot_ids"].pop()
    blocked = protocol.inspect_mapping(req, artifact(incomplete))
    assert blocked["mapping_status"] == "unknown" and not blocked["state_by_slot"]
    false_chi = copy.deepcopy(body)
    false_chi["states"][0]["chi"] = 1
    assert protocol.inspect_mapping(req, artifact(false_chi))["mapping_status"] == "unknown"


def test_genuine_singleton_retains_unknown_chi_but_multislot_subset_cannot_be_singleton():
    v = view()
    record = protocol.singleton(v, protocol_id="synthetic-protocol", source_bindings=bindings([v]))
    assert record["deterministic_singleton"] and record["actual_model_calls"] == 0
    assert set(record["chi_by_state"].values()) == {None}
    assert record["chi_status"] == "not_required_for_weighting"
    assert (
        set(record["pi"].values()) == {1} and record["centered_gradient"] == record["novelty"] == 0
    )
    with pytest.raises(ValueError, match="exactly one registered"):
        protocol.singleton(
            v, protocol_id="synthetic-protocol", source_bindings=bindings([v, view("two")])
        )
    with pytest.raises(ValueError, match="complete registered task kernel"):
        protocol.prepare_mapping(
            [v, view("two")],
            protocol_id="synthetic-protocol",
            source_bindings=bindings([v, view("two"), view("three")]),
        )


def test_request_binding_and_output_capacity_reject_mutation_and_overflow():
    req = request()
    req["model"] = "different-model"
    with pytest.raises(ValueError, match="deepseek-flash"):
        protocol.request_body(req)
    req = request()
    req["messages"][0]["content"] += " altered"
    with pytest.raises(ValueError, match="binding changed"):
        protocol.request_body(req)
    v = view()
    next(d for d in v["segments"] if d["kind"] == "public_content")["text"] = "x" * 200000
    with pytest.raises(ValueError, match="output estimate exceeds"):
        request(rebound(v))


@pytest.mark.parametrize("purpose", ["projection", "mapping"])
def test_settled_missing_or_wrong_tool_is_terminal_without_fabricated_argument_text(purpose):
    req = request() if purpose == "projection" else mapping_request()
    art = dict(
        review_text=None,
        finish_reason="tool_calls",
        review_format_error="wrong_tool_name",
        usage={"completion_tokens": 123},
    )
    result = protocol.inspect_paid_annotation(req, art)
    assert result["raw_review"] is None and result["raw_wire_annotation"] is None
    assert "missing_material_argument_text" in result["errors"]
    assert not result["JSON_repaired"]
    if purpose == "projection":
        assert not result["usable"]
    else:
        assert result["mapping_status"] == "unknown"
