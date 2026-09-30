"""No API: exact temporal-pair domains, authentic-schema lineage and missing chi."""

import copy
import json

import pytest
from test_finance_v13_material_protocol import artifact, bindings
from test_finance_v16_adjudication import body as old_body
from test_finance_v16_adjudication import request as old_request
from test_finance_v16_adjudication import revised_views

from trusted_synthesis.finance_research import v16_adjudication_protocol as previous
from trusted_synthesis.finance_research import v17_adjudication_protocol as protocol


def failed_source():
    req = old_request(revised_views())
    value = old_body(req)
    del value["states"][0]["chi"]
    art = artifact(value)
    return protocol.bound(
        dict(
            schema="v16_paid_material_annotation.v1",
            purpose="mapping",
            role="mapping",
            task_id=req["task_id"],
            slot_id=None,
            slot_ids=req["slot_ids"],
            request=req,
            artifact=art,
            inspection=previous.inspect_reply(req, art),
            actual_model_call_receipt_verified=True,
        )
    )


def request():
    rec = failed_source()
    return protocol.prepare_mapping(
        rec["request"]["views"],
        latest_record=rec,
        protocol_id="synthetic-v17",
        source_bindings=bindings(rec["request"]["views"]),
    )


def body(req, chi=0):
    state = dict(
        members=list(req["aliases"]["packages"]),
        basis="A new explicit semantic judgment, never supplied by temporal eligibility alone.",
        chi=chi,
        evidence=[
            f"p{i}:"
            + next(u["unit_id"] for u in d["catalog"]["units"] if u["kind"] == "public_content")
            for i, d in enumerate(req["domains"])
        ],
        changes=[],
    )
    if chi:
        state["changes"] = [
            dict(
                pair_id=next(k for k, p in req["temporal_pairs"].items() if p["package"] == member),
                effect="The original later model behavior changes its operation.",
            )
            for member in state["members"]
        ]
    return dict(
        states=[state],
        resolution="The missing chi has been independently adjudicated explicitly.",
        unresolved="",
    )


def test_request_keeps_original_schemas_all_public_text_and_names_mechanical_facts():
    req = request()
    assert req["latest_record"]["schema"] == "v16_paid_material_annotation.v1"
    assert (
        req["latest_record"]["request"]["latest_record"]["schema"]
        == "v15_paid_material_annotation.v1"
    )
    assert req["historical_failed_record_ids"] == [
        req["latest_record"]["request"]["latest_record_id"],
        req["latest_record_id"],
    ]
    payload = json.loads(req["messages"][1]["content"])
    assert [r["schema"] for r in payload["historical_failed_annotations"]] == [
        "v15_paid_material_annotation.v1",
        "v16_paid_material_annotation.v1",
    ]
    for p, d in zip(payload["packages"], req["domains"], strict=True):
        assert [u["text"] for u in p["units"]] == [u["text"] for u in d["catalog"]["units"]]
    diag = payload["mechanical_source_diagnostics"]
    assert diag["actor"] == "Host_original_public_bytes_v17"
    assert diag["no_membership_or_chi_suggestion"]
    assert diag["latest_wire_field_and_pair_diagnostics"][0]["absent_required_fields"] == ["chi"]
    assert "NOT_FOR_MODEL" not in json.dumps(req["messages"])
    wire = protocol.request_body(req)
    assert wire["model"] == "deepseek-flash" and wire["max_tokens"] == 8192
    assert req["episode_id"].startswith("v17mapping:")


def test_pair_catalog_contains_only_exact_same_package_strictly_later_model_units():
    req = request()
    assert req["temporal_pairs"]
    for key, pair in req["temporal_pairs"].items():
        assert key == pair["pair_id"]
        assert pair["consequence_turn"] > pair["action_turn"]
        assert pair["consequence_kind"] in {"public_content", "action_arguments"}
        assert pair["package"] == pair["action"].split(":")[0] == pair["consequence"].split(":")[0]
        view = next(v for v in req["views"] if v["slot_id"] == pair["slot_id"])
        event = next(e for e in view["events"] if e["action_id"] == pair["action_id"])
        assert pair["observation_segment_id"] == event["observation_segment_id"]
    state_schema = req["strict_tool"]["function"]["parameters"]["properties"]["states"]["items"]
    assert "chi" in state_schema["required"]
    change_schema = state_schema["properties"]["changes"]["items"]
    assert set(change_schema["properties"]) == {"pair_id", "effect"}
    assert change_schema["properties"]["pair_id"]["enum"] == list(req["temporal_pairs"])
    assert state_schema["properties"]["members"]["items"]["enum"] == list(
        req["aliases"]["packages"]
    )


@pytest.mark.parametrize("chi", [0, 1])
def test_explicit_judgment_maps_to_normalized_source_bound_inspection(chi):
    req = request()
    original = copy.deepcopy(req["latest_record"])
    value = body(req, chi)
    inspected = protocol.inspect_reply(req, artifact(value))
    assert inspected["mapping_admitted"]
    assert inspected["state_by_slot"] == {s: "z0000" for s in req["slot_ids"]}
    assert inspected["chi_by_state"] == {"z0000": chi}
    assert inspected["mechanical_source"]["semantic_labels_filled"] is False
    assert inspected["semantic_truth_proved"] is False
    assert inspected["actual_model_call_receipt_verified"] is False
    assert req["latest_record"] == original
    assert protocol.validate_inspection(inspected, req, artifact(value)) == inspected
    for change in inspected["states"][0]["interventions"]:
        pair = req["temporal_pairs"][change["pair_id"]]
        assert change["action_id"] == pair["action_id"]
        assert change["observation_segment_id"] == pair["observation_segment_id"]
        assert "kind" not in change


@pytest.mark.parametrize(
    "fault",
    [
        "missing_chi",
        "bool_chi",
        "null_chi",
        "missing_members",
        "missing_member_evidence",
        "foreign_member",
        "unknown_pair",
        "old_action_fields",
        "missing_member_change",
        "empty_effect",
        "duplicate_pair",
        "chi_zero_with_change",
        "duplicate_json",
        "length",
    ],
)
def test_no_missing_label_fill_no_illegal_pair_and_no_automatic_repair(fault):
    req = request()
    value = body(req, 1)
    state = value["states"][0]
    if fault == "missing_chi":
        del state["chi"]
        state["basis"] = "chi=1 is stated here but must NEVER fill a missing field."
    elif fault == "bool_chi":
        state["chi"] = True
    elif fault == "null_chi":
        state["chi"] = None
    elif fault == "missing_members":
        del state["members"]
    elif fault == "missing_member_evidence":
        state["evidence"] = state["evidence"][:1]
    elif fault == "foreign_member":
        state["members"] = ["p99"]
    elif fault == "unknown_pair":
        state["changes"][0]["pair_id"] = "p0:q999"
    elif fault == "old_action_fields":
        state["changes"][0]["action"] = "p0:a0"
    elif fault == "missing_member_change":
        state["changes"] = state["changes"][:1]
    elif fault == "empty_effect":
        state["changes"][0]["effect"] = " "
    elif fault == "duplicate_pair":
        state["changes"].append(copy.deepcopy(state["changes"][0]))
    elif fault == "chi_zero_with_change":
        state["chi"] = 0
    art = artifact(value, "length" if fault == "length" else "tool_calls")
    if fault == "duplicate_json":
        art["review_text"] = art["review_text"][:-1] + ',"unresolved":""}'
    result = protocol.inspect_reply(req, art)
    assert not result["mapping_admitted"]
    assert result["state_by_slot"] == result["chi_by_state"] == {}
    assert result["raw_review"] == art["review_text"] and not result["JSON_repaired"]


def test_temporally_valid_pair_is_not_allowed_for_another_states_member():
    req = request()
    value = body(req, 1)
    first = value["states"][0]
    second = copy.deepcopy(first)
    first.update(members=["p0"], evidence=first["evidence"][:1], changes=[first["changes"][1]])
    second.update(members=["p1"], evidence=second["evidence"][1:], changes=[second["changes"][0]])
    value["states"] = [first, second]
    assert not protocol.inspect_reply(req, artifact(value))["mapping_admitted"]


def test_unresolved_semantics_stay_unknown_even_with_mechanically_complete_output():
    req = request()
    value = body(req)
    value["unresolved"] = "The pair is temporally legal, but its substantive effect is unresolved."
    result = protocol.inspect_reply(req, artifact(value))
    assert result["annotation_status"] == "annotation_succeeded"
    assert result["mapping_status"] == "unknown" and not result["mapping_admitted"]


def test_model_pair_or_historical_schema_change_is_rejected_before_transport():
    req = request()
    req["model"] = "other-model"
    with pytest.raises(ValueError, match="deepseek-flash"):
        protocol.request_body(req)
    req = request()
    pair = next(iter(req["temporal_pairs"].values()))
    pair["consequence_turn"] = pair["action_turn"]
    with pytest.raises(ValueError, match="temporal pairs changed"):
        protocol.request_body(req)
    rec = failed_source()
    rec["schema"] = "v15_paid_material_annotation.v1"
    rec = protocol.bound({k: v for k, v in rec.items() if k != "id"})
    with pytest.raises(ValueError, match="historical schemas"):
        protocol.prepare_mapping(
            rec["request"]["views"],
            latest_record=rec,
            protocol_id="bad",
            source_bindings=bindings(rec["request"]["views"]),
        )


def test_policy_is_only_three_once_calls_and_preserves_741_authorities():
    policy = protocol.policy_definition()
    assert policy["fixed_target_tasks"] == policy["maximum_new_calls"] == 3
    assert policy["fixed_target_packages"] == 13
    assert policy["unchanged_prior_tasks"] == 741
    assert policy["calls_per_task"] == 1 and policy["automatic_retries"] == 0
    assert not policy["model_fallback"] and not policy["Student_information_visible"]
