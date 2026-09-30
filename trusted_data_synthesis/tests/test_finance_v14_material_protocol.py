"""Synthetic V14 interpretation/short-wire controls; no model or tokenizer."""

import copy
import hashlib
import json

import pytest
from test_finance_v13_material_protocol import (
    artifact,
    bindings,
    mapping_body,
    mapping_request,
    projection_body,
    request,
    view,
)

from trusted_synthesis.finance_research import v13_material_protocol as old
from trusted_synthesis.finance_research import v14_material_protocol as protocol


def paid(req, body, *, raw=None):
    art = artifact(body)
    if raw is not None:
        art["review_text"] = raw
    record = old.bound(
        dict(
            schema="v13_paid_material_annotation.v1",
            purpose=req["purpose"],
            role=req["role"],
            task_id=req["task_id"],
            slot_id=req["slot_id"],
            request=req,
            artifact=art,
            inspection=old.inspect_paid_annotation(req, art),
            actual_model_call_receipt_verified=True,
        )
    )
    ref = dict(
        path="synthetic-only-original",
        id=record["id"],
        sha256=hashlib.sha256(old.canonical(record)).hexdigest(),
    )
    return record, ref


def test_uniform_old_success_keeps_entire_partition_evidence_and_chi_exactly():
    req = mapping_request()
    original, ref = paid(req, mapping_body(req))
    before = copy.deepcopy(original)
    derived = protocol.derive_mapping(original, ref)
    assert derived["usable"] and derived["original_success"]
    assert derived["core_unchanged_from_original_success"]
    assert derived["original_semantic_sha256"] == derived["derived_semantic_sha256"]
    for field in (
        "states",
        "state_by_slot",
        "chi_by_state",
        "deterministic_materialized_annotation",
    ):
        assert derived["inspection"][field] == original["inspection"][field]
    assert original == before and derived["actual_model_calls"] == 0


def test_only_mechanically_redundant_extras_can_be_sidecar_not_missing_core():
    req = mapping_request()
    body = mapping_body(req)
    body.update(
        slot_ids=list(req["slot_ids"]),
        partial_evidence=[],
        semantic_summary=body["states"][0]["semantic_summary"],
    )
    original, ref = paid(req, body)
    derived = protocol.derive_mapping(original, ref)
    assert not original["inspection"]["mapping_admitted"] and derived["usable"]
    assert derived["auxiliary_sidecar"] == {
        k: body[k] for k in ("slot_ids", "partial_evidence", "semantic_summary")
    }
    assert all(p["accepted"] for p in derived["auxiliary_proofs"])
    del body["states"][0]["semantic_summary"]
    rejected = protocol.derive_mapping(*paid(req, body))
    assert not rejected["usable"]  # top summary is not moved to repair the core


@pytest.mark.parametrize(
    "extra",
    [
        {"semantic_summary": "These two members may not belong to the same state."},
        {"slot_ids": ["invented"]},
        {"partial_evidence": [dict(id="p0:u00000", quote="new evidence not in core")]},
        {"other_annotation": "unrequested"},
    ],
)
def test_unproved_or_decision_bearing_extra_remains_pending(extra):
    req = mapping_request()
    body = mapping_body(req)
    body.update(extra)
    result = protocol.derive_mapping(*paid(req, body))
    assert not result["usable"] and result["auxiliary_sidecar"] == extra
    assert any(not p["accepted"] for p in result["auxiliary_proofs"])


def test_redundancy_does_not_hide_core_membership_or_chi_errors():
    req = mapping_request()
    body = mapping_body(req)
    second = copy.deepcopy(body["states"][0])
    second["state_id"] = "second"
    body["states"].append(second)
    body["slot_ids"] = list(req["slot_ids"])
    result = protocol.derive_mapping(*paid(req, body))
    assert not result["usable"] and "two states" in result["errors"][0]
    body["states"] = [body["states"][0]]
    body["states"][0]["chi"] = 1
    assert not protocol.derive_mapping(*paid(req, body))["usable"]


@pytest.mark.parametrize("duplicate", [False, True])
def test_broken_or_duplicate_key_JSON_is_not_repaired(duplicate):
    req = mapping_request()
    body = mapping_body(req)
    raw = json.dumps(body)
    raw = raw[:-1] + ',"mapping_status":"complete"}' if duplicate else raw + "}"
    result = protocol.derive_mapping(*paid(req, body, raw=raw))
    assert not result["usable"] and not result["raw_JSON_repaired"]
    assert result["raw_review_sha256"] == hashlib.sha256(raw.encode()).hexdigest()


def test_same_authority_overlap_preserves_each_original_span_not_character_merge():
    req = request()
    body = projection_body(req)
    unit = next(
        u
        for u in req["domains"][0]["catalog"]["units"]
        if u["unit_id"] == body["positive_reason_ids"][0]
    )
    body["partial_positive_reason"] = [dict(id=unit["unit_id"], quote=unit["text"])]
    original, ref = paid(req, body)
    assert original["inspection"]["errors"] == ["overlapping_projection_decisions"]
    derived = protocol.derive_projection(original, ref)
    assert derived["usable"] and not derived["character_spans_merged"]
    spans = derived["projection"]["positive_content"]
    assert len(spans) == len(body["positive_reason_ids"]) + 1
    assert spans[0] == spans[-1]
    assert derived["token_selection"] == "union_of_individually_bounded_original_spans"
    body["positive_action_ids"][0] = body["positive_action_ids"][0][:-1]
    assert not protocol.derive_projection(*paid(req, body))["usable"]


def new_mapping():
    views = [view("one"), view("two")]
    return protocol.prepare_mapping(
        views, protocol_id="new-synthetic-only", source_bindings=bindings(views)
    )


def compact_mapping_body(req):
    return dict(
        mapping_status="complete",
        ambiguity_notes=[],
        states=[
            dict(
                members=[alias],
                semantic_summary="Synthetic semantic state asserted by test fixture.",
                evidence_ids=[
                    next(
                        e
                        for e in req["mapping_domains"]["evidence_ids"]
                        if e.startswith(alias + ":")
                    )
                ],
                partial_evidence=[],
                chi=0,
                chi_reason="No consequential intervention asserted.",
                interventions=[],
            )
            for alias in ("p1", "p0")
        ],
    )


def test_compact_mapping_has_one_membership_field_and_canonical_host_state_ids():
    req = new_mapping()
    body = compact_mapping_body(req)
    result = protocol.inspect_reply(req, artifact(body))
    assert result["mapping_admitted"] and result["state_IDs_generated_by_host"]
    assert result["state_by_slot"][req["aliases"]["packages"]["p0"]] == "z0000"
    assert result["state_by_slot"][req["aliases"]["packages"]["p1"]] == "z0001"
    body["states"].reverse()
    assert protocol.inspect_reply(req, artifact(body))["states"] == result["states"]
    schema = json.dumps(req["strict_tool"])
    assert '"state_id"' not in schema and '"slot_ids"' not in schema
    assert all(k not in schema for k in ("minItems", "maxItems", "minLength", "maxLength"))
    body["states"][1]["members"] = ["p0"]
    failed = protocol.inspect_reply(req, artifact(body))
    assert not failed["mapping_admitted"] and not failed["state_by_slot"]
    assert failed["raw_wire_annotation"] == body


def test_compact_projection_short_actions_exactly_expand_to_originals():
    original = request()
    req = protocol.prepare_projection(
        original["views"][0],
        protocol_id="new-synthetic-only",
        source_bindings=original["source_bindings"],
    )
    body = dict(
        status="complete",
        positive_reason_ids=req["domains"][0]["reason_ids"],
        partial_positive_reason=[],
        positive_action_ids=list(req["aliases"]["actions"]),
    )
    result = protocol.inspect_reply(req, artifact(body))
    assert result["usable"]
    assert [p["action_id"] for p in result["projection"]["positive_actions"]] == req["domains"][0][
        "successful_action_ids"
    ]
    assert req["episode_id"].startswith("v14projection:")
    assert protocol.request_body(req)["model"] == "deepseek-flash"
    assert protocol.request_body(req)["thinking"] == {"type": "disabled"}
    body["positive_action_ids"] = ["a999"]
    assert not protocol.inspect_reply(req, artifact(body))["usable"]


def test_missing_tool_and_complete_with_ambiguity_do_not_become_success():
    req = new_mapping()
    missing = artifact({})
    missing["review_text"] = None
    missing["review_format_error"] = "wrong_tool"
    assert not protocol.inspect_reply(req, missing)["mapping_admitted"]
    body = compact_mapping_body(req)
    body["ambiguity_notes"] = [
        dict(description="Unresolved member relationship.", evidence_ids=[], partial_evidence=[])
    ]
    assert not protocol.inspect_reply(req, artifact(body))["mapping_admitted"]
    body["mapping_status"] = "unknown"
    result = protocol.inspect_reply(req, artifact(body))
    assert result["mapping_status"] == "unknown" and not result["errors"]
    assert not result["production_admitted"]


def test_review_summary_with_existing_children_reuses_them_without_overwrite(tmp_path, monkeypatch):
    """Storage/control fixture, not financial/paid measurements or training material."""
    source, output = tmp_path / "synthetic-source", tmp_path / "synthetic-output"
    memory = {}

    def remember(path, value):
        path = str(path)
        value = protocol.bound(value)
        ref = dict(
            path=path, id=value["id"], sha256=hashlib.sha256(protocol.canonical(value)).hexdigest()
        )
        memory[path] = value, ref
        return value, ref

    original_read = protocol._read

    def source_read(path, ref=None):
        if str(path) in memory:
            value, own = memory[str(path)]
            assert ref is None or ref == own
            return copy.deepcopy(value), copy.deepcopy(own)
        return original_read(path, ref)

    def derive_map(record, ref):
        i = record["index"]
        return protocol.bound(
            dict(
                task_id=f"task{i}",
                slot_ids=[f"map-slot{i}"],
                usable=i < 337,
                original_success=i < 325,
                synthetic_storage_fixture=True,
            )
        )

    def derive_projection(record, ref):
        return protocol.bound(
            dict(
                task_id=record["task_id"],
                slot_id=record["slot_id"],
                usable=record["index"] < 2,
                synthetic_storage_fixture=True,
            )
        )

    monkeypatch.setattr(protocol, "_read", source_read)
    monkeypatch.setattr(protocol, "derive_mapping", derive_map)
    monkeypatch.setattr(protocol, "derive_projection", derive_projection)
    terminals = []
    for i in range(645):
        record, ref = remember(
            source / f"mapping{i}.json",
            dict(
                index=i,
                purpose="mapping",
                task_id=f"task{i}",
                actual_model_call_receipt_verified=i < 633,
                invocation_id=f"synthetic-network-{i}",
                original_ledger_record_sha256="synthetic",
            ),
        )
        _, terminal_ref = remember(source / f"mapping-terminal{i}.json", dict(record=ref))
        terminals.append(terminal_ref)
    for i in range(671):
        _, ref = remember(
            source / f"projection{i}.json",
            dict(
                index=i - 668,
                purpose="projection",
                task_id=f"projection-task{i}",
                slot_id=f"projection-slot{i}",
                actual_model_call_receipt_verified=True,
                inspection=dict(usable=i < 668),
            ),
        )
        _, terminal_ref = remember(source / f"projection-terminal{i}.json", dict(record=ref))
        terminals.append(terminal_ref)
    definition, _ = remember(
        source / "definition/record.json",
        dict(
            pairs=[
                dict(
                    slot_id=f"inherited{i}",
                    task_id=f"inherited-task{i}",
                    projection_authority="V12_A_original",
                    A_record=dict(id=f"synthetic{i}"),
                )
                for i in range(1797)
            ]
        ),
    )
    plan, _ = remember(
        source / "registration/record.json",
        dict(
            protocol_identity=definition["id"],
            singletons=[],
            jobs=[dict(kind="mapping", task_id=f"task{i}") for i in range(645)],
        ),
    )
    remember(
        source / "completion_seal/record.json",
        dict(
            actual_returns=1304,
            mapping_complete_calls=325,
            registration_id=plan["id"],
            terminals=terminals,
        ),
    )
    existing_dir = output / "representation_review/mappings" / old.digest("task0")
    existing = derive_map(dict(index=0), {})
    original_ref = protocol._write(existing_dir, existing)
    original_bytes = (existing_dir / "record.json").read_bytes()
    original_mtime = (existing_dir / "record.json").stat().st_mtime_ns
    result = protocol.review_existing(source, output)
    assert (output / "representation_review/summary/record.json").is_file()
    assert not (output / "representation_review/record.json").exists()
    assert result["m"] == 12 and result["b"] == 2
    assert protocol._write(existing_dir, existing) == original_ref
    assert (existing_dir / "record.json").read_bytes() == original_bytes
    assert (existing_dir / "record.json").stat().st_mtime_ns == original_mtime
    with pytest.raises(ValueError, match="never overwrite"):
        protocol._write(existing_dir, protocol.bound(dict(different="synthetic")))
