"""Synthetic review judgments, mocked public episodes, real CPU tokenizer only."""

import copy
import json

import pytest
from test_finance_public_reasoning import call, mocked_episode
from test_finance_research_datasets import finqa_record
from test_finance_research_r2 import TOKENIZER
from test_finance_v6_state_alignment import alignment_fixture

from trusted_synthesis.finance_research import v8_single_target_review as review
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.v6_task import public_trajectory_view


def authored(request):
    catalog = request["document_catalog"]
    sources = {d["text"]: e for e, d in catalog.items() if d["kind"] == "source_table_cell"}
    a, b = sources["8"], sources["2"]
    claim = next(
        e
        for e, d in catalog.items()
        if d["kind"] == "public_content" and d["text"].startswith("R:")
    )
    action = next(e for e, d in catalog.items() if d["kind"] == "action_arguments")
    terms = [
        dict(
            term_id=name,
            subject="synthetic revenue",
            attribute=attribute,
            period=period,
            value=value,
            unit="reporting units",
            public_source_anchor_ids=anchors,
        )
        for name, attribute, period, value, anchors in (
            ("t8", "revenue", "2020", "8", [a]),
            ("t2", "revenue", "2019", "2", [b]),
            ("t6", "increase", "2019-2020", "6", [a, b]),
        )
    ]
    targets = {}
    for eid, doc in catalog.items():
        if doc["kind"] not in {"public_content", "action_arguments"}:
            continue
        targets[eid] = (
            dict(label="approved", proposition_ids=["p"], evidence=[a, b, eid])
            if eid in (claim, action)
            else dict(label="nonassertive_context", proposition_ids=[], evidence=[])
        )
    return dict(
        terms=terms,
        nodes=[
            dict(
                node_id="n",
                predicate="answer",
                operation="subtract",
                term_ids=["t8", "t2", "t6"],
                public_source_anchor_ids=[a, b],
                proposition_ids=["p"],
                accepted=True,
                evidence=[claim, action],
            )
        ],
        edges=[],
        v_trace="valid",
        reason_codes=[],
        coverage_complete=True,
        propositions=[
            dict(
                proposition_id="p",
                status="assertion",
                critical=True,
                judgment="supported",
                accepted=True,
                model_claim_ids=[claim],
                support_evidence_ids=[a, b],
                retraction_model_ids=[],
            )
        ],
        updates=[],
        targets=targets,
    )


def fixture():
    task = adapt_finqa([finqa_record()], split="train", revision="v8-synthetic-control")[0]
    body = "R: 8 minus 2 equals 6.\nQ: None; submitting the predicted program."
    episodes, slots, mechanical = {}, [], {}
    for i in range(8):
        sid = f"s{i}"
        episode, _ = mocked_episode(
            task, [(body, [call("submit_program", {"program": "subtract(8, 2)"}, f"slot{i}")])]
        )
        episodes[sid] = episode
        slots.append(dict(slot_id=sid, trajectory=public_trajectory_view(episode, slot_id=sid)))
        mechanical[sid] = dict(
            sealed=True,
            history_complete=True,
            calls_settled=True,
            actions_observations_bound=True,
            private_reference_isolated=True,
            native_correct=True,
        )
    prepared = dict(
        bundle=dict(
            schema="v6_task_review_bundle.v1",
            task_id=task.public.task_id,
            seal_id="synthetic-complete-eight",
            slots=slots,
        ),
        mechanical=mechanical,
    )
    requests, raw, sides = [], [], []
    for reviewer in (0, 1):
        rr, vv, ss = {}, {}, {}
        for sid in episodes:
            request = review.slot_review_request(prepared, sid, task.reference, reviewer)
            value = authored(request)
            artifact = dict(
                wire_protocol=review.REVIEW_WIRE,
                semantic_review_request_sha256=digest(request),
                finish_reason="tool_calls",
                review_format_error=None,
                review_text=json.dumps(value),
            )
            ss[sid] = review.slot_review_record(request, artifact)
            rr[sid], vv[sid] = request, value
        requests.append(rr)
        raw.append(vv)
        sides.append(ss)
    return prepared, episodes, requests, raw, sides


def align(prepared, sides):
    requests = [review.alignment_request(prepared, sides[r], r) for r in (0, 1)]
    values = [alignment_fixture(req) for req in requests]
    checked = [review.validate_alignment(json.dumps(values[r]), requests[r]) for r in (0, 1)]
    return requests, values, checked


def test_single_target_authority_preserves_whole_semicolon_text_and_no_duplicate_obligation():
    _, _, requests, raw, sides = fixture()
    request = requests[0]["s0"]
    disk = json.loads(json.dumps(request, sort_keys=True))
    assert review.validate_slot_review(json.dumps(raw[0]["s0"]), disk)["semantic_consistent"]
    schema = request["strict_tool"]["function"]["parameters"]["properties"]
    assert "targets" in schema and not {"actions", "mask", "semantic_graph"} & set(schema)
    spans = request["compact_catalog"]["spans"]
    for doc_id, doc in request["document_index"].items():
        original = sorted(
            (s for s in spans.values() if s["doc_id"] == doc_id), key=lambda s: s["start"]
        )
        assert "".join(s["quote"] for s in original) == doc["text"]
    slot = sides[0]["s0"]
    assert slot["semantic_consistent"] and slot["v_trace"] == "valid"
    mask = slot["parsed"]["slot"]["mask"]
    assert len([s for s in mask if s["label"] == "nonassertive_context"]) == 2
    assert slot["action_and_mask_from_single_model_target"]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_action_target",
        "extra_mask_table",
        "wrong_source",
        "financial_nonassertive",
        "critical_unknown",
        "extra_reason_field",
    ],
)
def test_negative_controls_never_repair_or_false_approve(mutation):
    prepared, _, requests, values, _ = fixture()
    request, value = copy.deepcopy(requests[0]["s0"]), copy.deepcopy(values[0]["s0"])
    action = next(
        e for e, d in request["document_catalog"].items() if d["kind"] == "action_arguments"
    )
    claim = value["propositions"][0]["model_claim_ids"][0]
    if mutation == "missing_action_target":
        value["targets"].pop(action)
    elif mutation == "extra_mask_table":
        value["mask"] = {}
    elif mutation == "wrong_source":
        value["terms"][0]["public_source_anchor_ids"] = [action]
    elif mutation == "financial_nonassertive":
        value["targets"][claim] = dict(
            label="nonassertive_context", proposition_ids=[], evidence=[]
        )
    elif mutation == "critical_unknown":
        value["propositions"][0]["judgment"] = "unknown"
    else:
        changed = copy.deepcopy(prepared)
        for s in changed["bundle"]["slots"]:
            if s["slot_id"] == "s0":
                for segment in s["trajectory"]["segments"]:
                    if segment["kind"] == "action_arguments":
                        segment["text"] = '{"program":"subtract(8, 2)","reason":"result correct"}'
                        segment["end"] = len(segment["text"])
        request = review.slot_review_request(changed, "s0", {}, 0)
        value = authored(request)
    result = review.inspect_slot_review(json.dumps(value), request)
    assert not result["interface_admitted"] or not result["semantic_consistent"]
    if result["validation"]:
        assert (
            result["validation"]["v_trace"] == "unknown" and result["validation"]["derived"] is None
        )


def test_action_approval_never_approves_unknown_reasoning_or_uses_tool_ok_as_approval():
    _, _, requests, values, _ = fixture()
    request, value = requests[0]["s0"], copy.deepcopy(values[0]["s0"])
    claim = value["propositions"][0]["model_claim_ids"][0]
    value["targets"][claim]["label"] = "unknown"
    result = review.validate_slot_review(json.dumps(value), request)
    assert not result["derived"]["mask_complete"]
    assert (
        next(s for s in result["parsed"]["slot"]["mask"] if s["quote"].startswith("R:"))["label"]
        == "unknown"
    )
    action = next(
        e for e, d in request["document_catalog"].items() if d["kind"] == "action_arguments"
    )
    value["targets"][action]["label"] = "unknown"
    result = review.validate_slot_review(json.dumps(value), request)
    assert result["parsed"]["slot"]["actions"][0]["label"] == "unknown"


def test_both_reviewers_complete_path_to_real_cpu_tokenizer_without_positive_procedural_text():
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)
    prepared, episodes, _, _, sides = fixture()
    requests, values, checked = align(prepared, sides)
    disk = json.loads(json.dumps(requests[0], sort_keys=True))
    assert review.validate_alignment(json.dumps(values[0]), disk) == checked[0]
    resolution = review.resolve_pair(prepared, *sides, *checked)
    assert resolution["task_mapping"] == "complete" and len(resolution["valid_slots_retained"]) == 8
    manifest = resolution["slots"]["s0"]["encoding_manifest"]
    artifact = review.encode_reviewed_probe_for_student(episodes["s0"], manifest, tokenizer)
    assert artifact["encoding_admitted"] and artifact["schema"] == "v8_student_encoding.v1"
    row = artifact["rows"][0]
    assert "Q: None; submitting the predicted program." in row["rendered_response"]
    positions = tokenizer(
        row["rendered_prompt"] + row["rendered_response"],
        add_special_tokens=False,
        return_offsets_mapping=True,
    )["offset_mapping"]
    for zero in manifest["nonassertive_context_spans"]:
        left, right = (
            len(row["rendered_prompt"]) + zero["start"],
            len(row["rendered_prompt"]) + zero["end"],
        )
        overlap = {i for i, (a, b) in enumerate(positions) if a < right and left < b}
        assert not overlap & set(row["target_positions"])
    assert artifact["L_P"] > 0 and artifact["actual_model_calls"] == 0


def test_no_mask_intersection_or_deletion_of_hard_jointly_qualified_package():
    prepared, _, requests, values, sides = fixture()
    changed = copy.deepcopy(values[1]["s0"])
    claim = changed["propositions"][0]["model_claim_ids"][0]
    changed["targets"][claim]["label"] = "unknown"
    sides[1]["s0"] = review.validate_slot_review(json.dumps(changed), requests[1]["s0"])
    _, _, checked = align(prepared, sides)
    result = review.resolve_pair(prepared, *sides, *checked)
    assert len(result["valid_slots_retained"]) == 8
    assert result["slots"]["s0"]["encoding_manifest"] is None
    assert result["unencodable_jointly_qualified_slots"] == ["s0"]
    assert not result["common_kernel_material_ready"]
