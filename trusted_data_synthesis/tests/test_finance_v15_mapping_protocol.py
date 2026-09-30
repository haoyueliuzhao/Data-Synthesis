"""Synthetic exact-unit and declared-basis controls, no paid or Student work."""

import copy
import hashlib
import json

import pytest
from test_finance_v13_material_protocol import artifact, bindings, rebound, view

from trusted_synthesis.finance_research import v14_material_protocol as old
from trusted_synthesis.finance_research import v15_mapping_protocol as protocol


def original_request(views=None):
    views = views or [view("one"), view("two")]
    return old.prepare_mapping(
        views, protocol_id="synthetic-original", source_bindings=bindings(views)
    )


def original_body(req):
    return dict(
        mapping_status="complete",
        ambiguity_notes=[],
        states=[
            dict(
                members=list(req["aliases"]["packages"]),
                semantic_summary="Recorded original equivalence.",
                evidence_ids=[
                    next(e for e in req["mapping_domains"]["evidence_ids"] if e.startswith(p + ":"))
                    for p in req["aliases"]["packages"]
                ],
                partial_evidence=[],
                chi=0,
                chi_reason=(
                    "The original author explicitly gives shared evidence and derivation; "
                    "no consequential intervention separates members."
                ),
                interventions=[],
            )
        ],
    )


def paid(req, body, raw=None):
    art = artifact(body)
    if raw is not None:
        art["review_text"] = raw
    record = old.bound(
        dict(
            schema="v14_paid_material_annotation.v1",
            purpose="mapping",
            role="mapping",
            task_id=req["task_id"],
            slot_id=None,
            slot_ids=req["slot_ids"],
            request=req,
            artifact=art,
            inspection=old.inspect_reply(req, art),
            actual_model_call_receipt_verified=True,
        )
    )
    ref = dict(
        path="synthetic-only-not-a-paid-artifact",
        id=record["id"],
        sha256=hashlib.sha256(old.canonical(record)).hexdigest(),
    )
    return record, ref


def approval(record, ref):
    state = record["inspection"]["raw_wire_annotation"]["states"][0]
    return {
        record["task_id"]: dict(
            task_id=record["task_id"],
            candidate_id="synthetic-candidate",
            source_record_ref=ref,
            raw_review_sha256=hashlib.sha256(
                record["artifact"]["review_text"].encode()
            ).hexdigest(),
            basis_source_path="raw_wire_annotation.states[0].chi_reason",
            original_basis_text_sha256=hashlib.sha256(state["chi_reason"].encode()).hexdigest(),
            members=state["members"],
            approved_existing_basis=True,
        )
    }


def test_missing_summary_needs_exact_declared_interpretation_and_stays_none():
    req = original_request()
    body = original_body(req)
    del body["states"][0]["semantic_summary"]
    record, ref = paid(req, body)
    before = copy.deepcopy(record)
    assert not protocol.derive_mapping(record, ref)["usable"]
    result = protocol.derive_mapping(record, ref, approvals=approval(record, ref))
    assert result["usable"] and result["inspection"]["states"][0]["semantic_summary"] is None
    assert result["inspection"]["states"][0]["chi"] == 0
    assert (
        result["inspection"]["classification_basis_sources"][0]["text"]
        == body["states"][0]["chi_reason"]
    )
    assert record == before and result["actual_model_calls"] == 0
    assert not result["supervision_and_encodings_changed"]


def test_approval_cannot_be_reused_for_changed_basis_or_chi_one():
    req = original_request()
    body = original_body(req)
    del body["states"][0]["semantic_summary"]
    record, ref = paid(req, body)
    approved = approval(record, ref)
    approved[record["task_id"]]["original_basis_text_sha256"] = "changed"
    assert not protocol.derive_mapping(record, ref, approvals=approved)["usable"]
    body["states"][0]["chi"] = 1
    record, ref = paid(req, body)
    assert not protocol.derive_mapping(record, ref, approvals=approval(record, ref))["usable"]


def quote_request(first="alpha needle\nbeta needle\n"):
    views = [view("one"), view("two")]
    next(s for s in views[0]["segments"] if s["kind"] == "public_content")["text"] = first
    rebound(views[0])
    req = original_request(views)
    unit = next(u for u in req["domains"][0]["catalog"]["units"] if u["kind"] == "public_content")
    body = original_body(req)
    body["states"][0]["partial_evidence"] = [dict(id="p0:" + unit["unit_id"], quote="needle")]
    return req, body, unit


def test_exact_selected_unit_disambiguates_repetition_elsewhere_without_text_change():
    req, body, unit = quote_request()
    record, ref = paid(req, body)
    assert not record["inspection"]["mapping_admitted"]
    result = protocol.derive_mapping(record, ref)
    assert result["usable"]
    ev = result["inspection"]["states"][0]["evidence"][-1]
    assert ev["quote"] == "needle" and ev["start"] == unit["start"] + 6
    assert ev["end"] <= unit["end"]
    assert (
        result["inspection"]["original_unit_resolution_receipts"][-1]["rule"]
        == "original_selected_unit_unique_exact"
    )


@pytest.mark.parametrize(
    "text,quote",
    [
        ("needle needle\nother\n", "needle"),
        ("first unit\nneedle\n", "needle"),
        ("needle\n", "Needle"),
        ("needle\n", ""),
    ],
)
def test_ambiguous_absent_neighbor_case_changed_or_empty_quote_is_not_repaired(text, quote):
    req, body, _ = quote_request(text)
    body["states"][0]["partial_evidence"][0]["quote"] = quote
    record, ref = paid(req, body)
    result = protocol.derive_mapping(record, ref)
    assert not result["usable"] and not result["inspection"]["JSON_repaired"]
    assert result["inspection"]["raw_review"] == record["artifact"]["review_text"]


def test_duplicate_JSON_key_and_missing_members_cannot_use_optional_summary():
    req = original_request()
    body = original_body(req)
    raw = json.dumps(body)[:-1] + ',"mapping_status":"complete"}'
    assert not protocol.derive_mapping(*paid(req, body, raw))["usable"]
    del body["states"][0]["members"]
    assert not protocol.derive_mapping(*paid(req, body))["usable"]


def test_new_wire_one_original_basis_not_fabricated_semantic_summary():
    req0 = original_request()
    req = protocol.prepare_mapping(
        req0["views"], protocol_id="new-synthetic", source_bindings=req0["source_bindings"]
    )
    body = original_body(req0)
    state = body["states"][0]
    state.pop("semantic_summary")
    state["basis"] = state.pop("chi_reason")
    result = protocol.inspect_reply(req, artifact(body))
    assert result["mapping_admitted"] and result["states"][0]["semantic_summary"] is None
    assert result["classification_basis_sources"][0]["text"] == state["basis"]
    assert result["classification_basis_sources"][0]["not_an_original_semantic_summary"]
    schema = req["strict_tool"]["function"]["parameters"]["properties"]["states"]["items"]
    assert "basis" in schema["properties"] and "semantic_summary" not in schema["properties"]
    assert "chi_reason" not in schema["properties"]
    assert req["episode_id"].startswith("v15mapping:")
    assert protocol.request_body(req)["model"] == "deepseek-flash"
    assert "NOT_FOR_MODEL" not in json.dumps(req["messages"])
    body["states"][0]["basis"] = ""
    assert not protocol.inspect_reply(req, artifact(body))["mapping_admitted"]
    missing = artifact(body)
    missing["review_text"] = None
    missing["review_format_error"] = "missing_tool"
    assert protocol.inspect_reply(req, missing)["raw_review"] is None


def test_new_basis_does_not_override_member_evidence_or_chi_constraints():
    req0 = original_request()
    req = protocol.prepare_mapping(
        req0["views"], protocol_id="new-synthetic", source_bindings=req0["source_bindings"]
    )
    body = original_body(req0)
    state = body["states"][0]
    state.pop("semantic_summary")
    state["basis"] = state.pop("chi_reason")
    state["chi"] = 1
    assert not protocol.inspect_reply(req, artifact(body))["mapping_admitted"]
    state["chi"] = 0
    state["members"] = ["p0"]
    assert not protocol.inspect_reply(req, artifact(body))["mapping_admitted"]
