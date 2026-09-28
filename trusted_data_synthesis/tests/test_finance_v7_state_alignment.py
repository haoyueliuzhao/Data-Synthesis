"""Prospective end-to-end CPU controls; model judgments and API envelopes are fixtures."""

import copy
import json

import pytest
from test_finance_public_reasoning import call, mocked_episode
from test_finance_research_datasets import finqa_record
from test_finance_research_r2 import TOKENIZER
from test_finance_v6_state_alignment import alignment_fixture

from trusted_synthesis.finance_research import v6_state_alignment as legacy
from trusted_synthesis.finance_research import v7_state_alignment as current
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.semantic_review import ReviewError
from trusted_synthesis.finance_research.v6_task import (
    public_trajectory_view,
    score_public_reasoning_program,
)
from trusted_synthesis.finance_research.v7_mask_review import slot_review_request


@pytest.fixture(scope="module")
def tokenizer():
    from transformers import AutoTokenizer

    assert (TOKENIZER / "tokenizer_config.json").is_file(), "NO_ADMISSION: real tokenizer absent"
    return AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)


def fixture():
    record = finqa_record()
    record["pre_text"][0] = "Revenue is shown below. " + "Background context. " * 30
    task = adapt_finqa([record], split="train", revision="synthetic-v5-consensus-control")[0]
    episodes = {}
    views, mechanical = [], {}
    for i in range(8):
        sid = f"s{i}"
        episode, _ = mocked_episode(
            task,
            [
                (
                    "R: 8 minus 2 equals 6.\nQ: None.",
                    [call("submit_program", {"program": "subtract(8, 2)"}, f"slot{i}.final")],
                )
            ],
        )
        episodes[sid] = episode
        views.append(dict(slot_id=sid, trajectory=public_trajectory_view(episode, slot_id=sid)))
        native = score_public_reasoning_program(task, episode)["native"]["execution_accuracy"]
        mechanical[sid] = dict(
            sealed=True,
            history_complete=True,
            calls_settled=True,
            actions_observations_bound=True,
            private_reference_isolated=True,
            native_correct=bool(native),
        )
    prepared = dict(
        bundle=dict(
            schema="v6_task_review_bundle.v1",
            task_id=task.public.task_id,
            seal_id="synthetic-eight-mock-episodes-not-paid-data",
            slots=views,
        ),
        mechanical=mechanical,
    )
    sides, requests, arguments = [], [], []
    for reviewer in (0, 1):
        reviews, own_requests, own_arguments = {}, {}, {}
        for sid in episodes:
            request = slot_review_request(prepared, sid, task.reference, reviewer)
            catalog = request["document_catalog"]
            sources = {
                d["text"]: eid for eid, d in catalog.items() if d["kind"] == "source_table_cell"
            }
            src8, src2 = sources["8"], sources["2"]
            claim = next(
                e
                for e, d in catalog.items()
                if d["kind"] == "public_content" and d["text"].startswith("R:")
            )
            empty_q = next(
                e
                for e, d in catalog.items()
                if d["kind"] == "public_content" and d["text"].strip() == "Q: None."
            )
            action = next(e for e, d in catalog.items() if d["kind"] == "action_arguments")
            # A long source anchor also exercises deterministic multiple-fragment
            # projection after sort_keys persistence; all source content is synthetic.
            background = next(
                e
                for e, d in catalog.items()
                if d["kind"] == "source_text" and d["text"].startswith("Revenue is shown")
            )
            anchors = [src8, src2, background]
            terms = [
                dict(
                    term_id=name,
                    subject="synthetic company",
                    attribute=attribute,
                    period=period,
                    value=value,
                    unit="reporting units",
                    public_source_anchor_ids=source,
                )
                for name, attribute, period, value, source in (
                    ("t8", "revenue", "2020", "8", [src8]),
                    ("t2", "revenue", "2019", "2", [src2]),
                    ("t6", "revenue increase", "2019-2020", "6", anchors),
                )
            ]
            value = dict(
                terms=terms,
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
                        support_evidence_ids=[src8, src2],
                        retraction_model_ids=[],
                    )
                ],
                actions={
                    action: dict(label="approved", proposition_ids=["p"], evidence=[action, claim])
                },
                updates=[],
                mask={
                    claim: dict(label="approved", proposition_ids=["p"]),
                    empty_q: dict(label="nonassertive_context", proposition_ids=[]),
                    action: dict(label="approved", proposition_ids=["p"]),
                },
                semantic_graph=dict(
                    nodes=[
                        dict(
                            node_id="n",
                            predicate="answer",
                            operation="subtract",
                            term_ids=["t8", "t2", "t6"],
                            public_source_anchor_ids=anchors,
                            proposition_ids=["p"],
                            accepted=True,
                            evidence=[claim, action],
                        )
                    ],
                    edges=[],
                ),
            )
            reviews[sid] = current.slot_review_record(request, json.dumps(value))
            assert reviews[sid]["semantic_consistent"]
            own_requests[sid], own_arguments[sid] = request, value
        sides.append(reviews)
        requests.append(own_requests)
        arguments.append(own_arguments)
    return prepared, episodes, sides, requests, arguments


def align(prepared, sides, *, unknown_pair=False):
    requests = [current.alignment_request(prepared, sides[r], r) for r in (0, 1)]
    raw = [alignment_fixture(request) for request in requests]
    if unknown_pair:
        raw[1]["pairs"]["s0_s1"].update(relation="unknown", basis="unresolved")
    checked = [current.validate_alignment(json.dumps(raw[r]), requests[r]) for r in (0, 1)]
    return requests, raw, checked


def test_two_v5_reviews_align_and_real_student_tokenizer_gives_empty_q_zero_loss(tokenizer):
    prepared, episodes, sides, _, _ = fixture()
    _, _, checked = align(prepared, sides)
    result = current.resolve_decomposed_pair(prepared, *sides, *checked)
    assert result["task_mapping"] == "complete" and result["common_kernel_material_ready"]
    assert result["valid_slots_retained"] == [f"s{i}" for i in range(8)]
    assert {s["state_id"] for s in result["slots"].values()} == {"z0"}
    assert not result["actual_training_performed"] and not result["old_reviews_reclassified"]
    manifest = result["slots"]["s0"]["encoding_manifest"]
    assert len(manifest["nonassertive_context_spans"]) == 1
    assert all("Q: None." not in span["quote"] for span in manifest["positive_content_spans"])
    artifact = current.encode_reviewed_probe_for_student(episodes["s0"], manifest, tokenizer)
    assert artifact["schema"] == "v7_student_encoding.v1" and artifact["encoding_admitted"]
    assert artifact["not_a_TokenReceipt"] and artifact["actual_model_or_training_calls"] == 0
    assert artifact["L_P"] == sum(len(r["target_ids"]) for r in artifact["rows"])
    row = artifact["rows"][0]
    assert "Q: None." in row["rendered_response"]  # History text is not deleted.
    text = row["rendered_prompt"] + row["rendered_response"]
    left = len(row["rendered_prompt"]) + row["rendered_response"].index("Q: None.")
    right = left + len("Q: None.")
    offsets = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)[
        "offset_mapping"
    ]
    touched = [i for i, (a, b) in enumerate(offsets) if a < right and left < b]
    assert touched and not set(touched) & set(row["target_positions"])
    assert row["layer_target_counts"]["reason"] > 0 and row["layer_target_counts"]["final"] > 0
    assert row["student_eos_supervised"]


def test_old_alignment_defaults_reject_new_mask_and_new_wrapper_requires_v5_binding():
    prepared, _, sides, _, _ = fixture()
    with pytest.raises(ReviewError, match="outside this alignment version"):
        legacy.alignment_request(prepared, sides[0], 0)
    bad = copy.deepcopy(sides[0])
    bad["s0"]["wire_protocol"] = "v6_slot_review.v4"
    with pytest.raises(ReviewError, match="v5 slot judgments"):
        current.alignment_request(prepared, bad, 0)


def test_sort_keys_alignment_roundtrip_and_no_other_reviewers_context():
    prepared, _, sides, _, _ = fixture()
    requests, values, checked = align(prepared, sides)
    loaded = json.loads(json.dumps(requests[0], sort_keys=True, ensure_ascii=False))
    assert list(loaded["document_catalog"])[:3] == ["e0", "e1", "e10"]
    assert current.validate_alignment(json.dumps(values[0]), loaded) == checked[0]
    assert not requests[0]["other_reviewer_output_visible"]
    assert set(requests[0]["own_slot_reviews"]) == {f"s{i}" for i in range(8)}
    assert all(r["reviewer"] == 0 for r in requests[0]["own_slot_reviews"].values())


def test_critical_unknown_is_not_admitted_but_other_jointly_valid_candidates_are_retained():
    prepared, _, sides, requests, arguments = fixture()
    value = copy.deepcopy(arguments[1]["s0"])
    value["propositions"][0]["judgment"] = "unknown"
    sides[1]["s0"] = current.slot_review_record(requests[1]["s0"], json.dumps(value))
    assert sides[1]["s0"]["v_trace"] == "unknown"
    _, _, checked = align(prepared, sides)
    result = current.resolve_decomposed_pair(prepared, *sides, *checked)
    assert len(result["slots"]) == 8 and result["valid_slots_retained"] == [
        f"s{i}" for i in range(1, 8)
    ]
    assert result["slots"]["s0"]["encoding_manifest"] is None
    assert not result["slots"]["s0"]["common_material_valid"]


def test_mechanically_failed_v5_slot_keeps_bound_coordinate_without_blocking_eligible_subset():
    prepared, _, sides, requests, _ = fixture()
    failed = current.slot_review_record(requests[1]["s0"], "{")
    assert not failed["interface_admitted"] and failed["v_trace"] == "unknown"
    assert failed["original_coordinate_retained"] and failed["review_request_sha256"]
    sides[1]["s0"] = failed
    _, _, checked = align(prepared, sides)
    result = current.resolve_decomposed_pair(prepared, *sides, *checked)
    assert len(result["slots"]) == 8
    assert result["task_mapping"] == "complete" and len(result["valid_slots_retained"]) == 7
    assert result["slots"]["s0"]["mapper"] == "not_applicable"
    with pytest.raises(ReviewError, match="actual v5 request"):
        current.slot_review_record(requests[1]["s0"]["typed_baseline_request"], "{")
    corrupted = copy.deepcopy(sides[1])
    corrupted["s0"]["review_request_sha256"] = "unbound-old-failure"
    with pytest.raises(ReviewError, match="bound v5 unknown record"):
        current.alignment_request(prepared, corrupted, 1)


def test_uncertain_alignment_cannot_drop_a_jointly_qualified_package_to_form_kernel():
    prepared, _, sides, _, _ = fixture()
    _, _, checked = align(prepared, sides, unknown_pair=True)
    result = current.resolve_decomposed_pair(prepared, *sides, *checked)
    assert len(result["valid_slots_retained"]) == 8 and result["task_mapping"] == "incomplete"
    assert not result["common_kernel_material_ready"]
    assert all(s["mapper"] == "unknown" for s in result["slots"].values())


def test_mask_disagreement_keeps_all_jointly_qualified_packages_and_blocks_kernel_encoding():
    prepared, _, sides, requests, arguments = fixture()
    changed = copy.deepcopy(arguments[1]["s0"])
    for value in changed["mask"].values():
        if value["label"] == "nonassertive_context":
            value["label"] = "unknown"
    sides[1]["s0"] = current.slot_review_record(requests[1]["s0"], json.dumps(changed))
    assert sides[1]["s0"]["v_trace"] == "valid"
    _, _, checked = align(prepared, sides)
    result = current.resolve_decomposed_pair(prepared, *sides, *checked)
    assert len(result["valid_slots_retained"]) == 8
    assert result["unencodable_jointly_qualified_slots"] == ["s0"]
    assert result["slots"]["s0"]["encoding_manifest"] is None
    assert not result["common_kernel_material_ready"]


def test_zero_context_metadata_cannot_overlap_positive_student_targets(tokenizer):
    prepared, episodes, sides, _, _ = fixture()
    _, _, checked = align(prepared, sides)
    result = current.resolve_decomposed_pair(prepared, *sides, *checked)
    manifest = copy.deepcopy(result["slots"]["s0"]["encoding_manifest"])
    zero = manifest["nonassertive_context_spans"][0]
    manifest["positive_content_spans"].append(
        {k: zero[k] for k in ("doc_id", "start", "end", "quote", "original_segment_id")}
        | dict(layer="reason")
    )
    with pytest.raises(ReviewError, match="overlaps"):
        current.encode_reviewed_probe_for_student(episodes["s0"], manifest, tokenizer)
