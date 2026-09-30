"""Synthetic fixed-source adjudication controls; no API or Student input."""

import copy
import json
from unittest.mock import patch

import pytest
from test_finance_v13_material_protocol import artifact, bindings, view

from trusted_synthesis.finance_research import v11_process_review as public
from trusted_synthesis.finance_research import v15_mapping_protocol as previous
from trusted_synthesis.finance_research import v16_adjudication_protocol as protocol
from trusted_synthesis.finance_research.contracts import digest


def failed_record(views=None):
    views = views or [view("one"), view("two")]
    req = previous.prepare_mapping(
        views, protocol_id="synthetic-v15", source_bindings=bindings(views)
    )
    art = artifact(dict(mapping_status="complete", states=[], ambiguity_notes=[]))
    return protocol.bound(
        dict(
            schema="v15_paid_material_annotation.v1",
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


def request(views=None):
    old = failed_record(views)
    return protocol.prepare_mapping(
        old["request"]["views"],
        latest_record=old,
        protocol_id="synthetic-v16",
        source_bindings=bindings(old["request"]["views"]),
    )


def body(req):
    return dict(
        states=[
            dict(
                members=list(req["aliases"]["packages"]),
                basis="Same evidence and subtraction; wording differs, no consequential change.",
                chi=0,
                evidence=[
                    f"p{i}:"
                    + next(
                        u["unit_id"] for u in d["catalog"]["units"] if u["kind"] == "public_content"
                    )
                    for i, d in enumerate(req["domains"])
                ],
                changes=[],
            )
        ],
        resolution="Prior members were missing. Full original histories establish this partition.",
        unresolved="",
    )


def test_concise_request_preserves_complete_units_table_locations_and_failed_source():
    req = request()
    payload = json.loads(req["messages"][1]["content"])
    for index, (package, local, original) in enumerate(
        zip(payload["packages"], req["domains"], req["views"], strict=True)
    ):
        assert [u["text"] for u in package["units"]] == [
            u["text"] for u in local["catalog"]["units"]
        ]
        docs = {d["segment_id"]: d for d in original["segments"]}
        for selected, source in zip(package["units"], local["catalog"]["units"], strict=True):
            doc = docs[source["segment_id"]]
            assert selected["id"] == f"p{index}:" + source["unit_id"]
            assert (selected["row"], selected["column"], selected["source"]) == (
                doc.get("row"),
                doc.get("column"),
                doc.get("source_id"),
            )
    assert (
        payload["latest_failed_annotation"]["original_raw_arguments"]
        == req["latest_record"]["artifact"]["review_text"]
    )
    assert "NOT_FOR_MODEL" not in json.dumps(req["messages"])
    assert req["episode_id"].startswith("v16mapping:")
    wire = protocol.request_body(req)
    assert wire["model"] == "deepseek-flash" and wire["thinking"] == {"type": "disabled"}
    properties = req["strict_tool"]["function"]["parameters"]["properties"]
    assert set(properties) == {"states", "resolution", "unresolved"}
    state_keys = set(properties["states"]["items"]["properties"])
    assert state_keys == {"members", "basis", "chi", "evidence", "changes"}


def test_complete_partition_has_separate_semantic_and_mechanical_authorities():
    req = request()
    before = copy.deepcopy(req["latest_record"])
    value = body(req)
    inspected = protocol.inspect_reply(req, artifact(value))
    assert inspected["mapping_admitted"] and inspected["mapping_status"] == "complete"
    assert inspected["state_by_slot"] == {s: "z0000" for s in req["slot_ids"]}
    assert inspected["chi_by_state"] == {"z0000": 0}
    assert inspected["states"][0]["semantic_summary"] is None
    assert inspected["states"][0]["basis"] == value["states"][0]["basis"]
    assert inspected["semantic_source"]["kind"] == "new_model_adjudication"
    assert inspected["mechanical_source"]["semantic_labels_filled"] is False
    assert (
        not inspected["actual_model_call_receipt_verified"]
        and not inspected["semantic_truth_proved"]
    )
    assert req["latest_record"] == before
    assert protocol.validate_inspection(inspected, req, artifact(value)) == inspected


@pytest.mark.parametrize(
    "fault",
    [
        "members_missing",
        "members_omitted",
        "members_duplicate",
        "unknown_member",
        "basis_empty",
        "evidence_missing",
        "chi_default",
        "chi_one_without_change",
        "resolution_missing",
        "old_extra_schema",
        "duplicate_json_key",
        "length",
    ],
)
def test_failures_never_get_default_members_chi_or_automatic_repair(fault):
    req = request()
    value = body(req)
    state = value["states"][0]
    if fault == "members_missing":
        del state["members"]
    elif fault == "members_omitted":
        state["members"] = state["members"][:1]
    elif fault == "members_duplicate":
        state["members"] *= 2
    elif fault == "unknown_member":
        state["members"].append("p9")
    elif fault == "basis_empty":
        state["basis"] = " "
    elif fault == "evidence_missing":
        state["evidence"] = state["evidence"][:1]
    elif fault == "chi_default":
        del state["chi"]
    elif fault == "chi_one_without_change":
        state["chi"] = 1
    elif fault == "resolution_missing":
        value["resolution"] = ""
    elif fault == "old_extra_schema":
        state["partial_evidence"] = []
    art = artifact(value, "length" if fault == "length" else "tool_calls")
    if fault == "duplicate_json_key":
        art["review_text"] = art["review_text"][:-1] + ',"unresolved":""}'
    result = protocol.inspect_reply(req, art)
    assert (
        not result["mapping_admitted"] and result["state_by_slot"] == result["chi_by_state"] == {}
    )
    assert result["raw_review"] == art["review_text"] and not result["JSON_repaired"]


def test_unresolved_semantics_cannot_hide_behind_a_complete_partition():
    req = request()
    value = body(req)
    value["unresolved"] = (
        "Cannot decide whether the apparent check changes the acceptance rationale."
    )
    inspected = protocol.inspect_reply(req, artifact(value))
    assert inspected["annotation_status"] == "annotation_succeeded"
    assert not inspected["mapping_admitted"] and inspected["mapping_status"] == "unknown"
    assert inspected["unresolved"] == value["unresolved"]
    value["unresolved"] = ""
    value["resolution"] = (
        "The old nonempty note was a consistent explanation, not an unresolved alternative."
    )
    assert protocol.inspect_reply(req, artifact(value))["mapping_admitted"]


def revised_views():
    from test_finance_public_reasoning import call, mocked_episode
    from test_finance_research_datasets import finqa_record

    from trusted_synthesis.finance_research.datasets import adapt_finqa

    task = adapt_finqa([finqa_record()], split="train", revision="v16-synthetic")[0]
    # The fixture tests temporal source binding, not the separate native executor.
    with patch(
        "trusted_synthesis.finance_research.v6_task.execute_public_program",
        return_value={"program": "add(8, 2)", "result": 10.0, "synthetic_only": True},
    ):
        episode, _ = mocked_episode(
            task,
            [
                ("I initially choose addition.", [call("run_program", {"program": "add(8, 2)"})]),
                (
                    "The observation exposes my wrong operation. The question needs subtraction.",
                    [call("submit_program", {"program": "subtract(8, 2)"})],
                ),
            ],
        )
    return [
        public.prepare_review_request(
            episode,
            slot_id="v10gen:" + digest(label),
            role="A",
            native_result={},
            integrity={k: True for k in public.INTEGRITY_CHECKS},
        )["trajectory"]
        for label in ("revised-one", "revised-two")
    ]


def revised_body(req):
    value = body(req)
    state = value["states"][0]
    state["chi"] = 1
    state["basis"] = (
        "Both change their planned addition to subtraction after observing the wrong program."
    )
    for index, local in enumerate(req["domains"]):
        units = local["catalog"]["units"]
        view = req["views"][index]
        docs = {d["segment_id"]: d for d in view["segments"]}
        consequence = next(
            u
            for u in units
            if u["kind"] == "action_arguments" and docs[u["segment_id"]]["turn_index"] == 1
        )
        state["changes"].append(
            dict(
                kind="revision",
                action=f"p{index}:a0",
                consequence=f"p{index}:" + consequence["unit_id"],
                effect="The model changes the operation, not just repeats the tool output.",
            )
        )
    return value


def test_host_pairs_causal_action_to_its_actual_observation_and_preserves_model_effect():
    req = request(revised_views())
    value = revised_body(req)
    inspected = protocol.inspect_reply(req, artifact(value))
    assert inspected["mapping_admitted"]
    for index, event in enumerate(inspected["states"][0]["interventions"]):
        assert (
            event["observation_segment_id"]
            == req["views"][index]["events"][0]["observation_segment_id"]
        )
        assert event["effect"] == value["states"][0]["changes"][index]["effect"]
        assert event["observation_pair_source"] == "host_exact_original_action_event"


@pytest.mark.parametrize(
    "fault",
    [
        "tool_consequence",
        "same_turn",
        "foreign_consequence",
        "wrong_action",
        "missing_member_change",
        "empty_effect",
        "chi_zero_with_changes",
    ],
)
def test_real_result_or_wrong_temporal_pair_does_not_stand_in_for_later_model_behavior(fault):
    req = request(revised_views())
    value = revised_body(req)
    state = value["states"][0]
    change = state["changes"][0]
    if fault == "tool_consequence":
        change["consequence"] = next(
            i for i in req["mapping_domains"]["observation_ids"] if i.startswith("p0:")
        )
    elif fault == "same_turn":
        change["consequence"] = state["evidence"][0]
    elif fault == "foreign_consequence":
        change["consequence"] = state["changes"][1]["consequence"]
    elif fault == "wrong_action":
        change["action"] = "p0:a1"
    elif fault == "missing_member_change":
        state["changes"] = state["changes"][:1]
    elif fault == "empty_effect":
        change["effect"] = " "
    else:
        state["chi"] = 0
    result = protocol.inspect_reply(req, artifact(value))
    assert not result["mapping_admitted"] and result["chi_by_state"] == {}


def test_request_source_or_model_cannot_be_changed_and_accepted_authority_cannot_be_replaced():
    req = request()
    req["model"] = "other-model"
    with pytest.raises(ValueError, match="deepseek-flash"):
        protocol.request_body(req)
    req = request()
    req["latest_record"]["artifact"]["review_text"] += " "
    with pytest.raises(ValueError, match="actual unresolved"):
        protocol.checked_request(req)
    old = failed_record()
    old["inspection"]["mapping_admitted"] = True
    old = protocol.bound({k: v for k, v in old.items() if k != "id"})
    with pytest.raises(ValueError, match="accepted authorities"):
        protocol.prepare_mapping(
            old["request"]["views"],
            latest_record=old,
            protocol_id="wrong",
            source_bindings=old["request"]["source_bindings"],
        )
