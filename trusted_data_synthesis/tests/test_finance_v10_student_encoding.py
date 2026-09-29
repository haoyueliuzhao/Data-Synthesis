"""Real local tokenizer; synthetic API episodes and annotations, no paid calls."""

import copy
import json

import pytest
from test_finance_public_reasoning import call, mocked_episode
from test_finance_research_datasets import finqa_record
from test_finance_research_r2 import TOKENIZER
from test_finance_v10_process_review import fixture

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.v10_process_review import (
    INTEGRITY_CHECKS,
    inspect_process_review,
    prepare_process_request,
    supervision_manifest,
)
from trusted_synthesis.finance_research.v10_student_encoding import (
    encode_process_review_for_student,
)


@pytest.fixture(scope="module")
def tokenizer():
    from transformers import AutoTokenizer

    assert (TOKENIZER / "tokenizer_config.json").is_file()
    return AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)


def manifest(request, annotation):
    return supervision_manifest(inspect_process_review(json.dumps(annotation), request))


def test_single_authority_real_encoding_contains_reason_and_final_without_graph(tokenizer):
    episode, request, body = fixture()
    target = manifest(request, body)
    encoded = encode_process_review_for_student(episode, target, tokenizer)
    assert encoded["encoding_admitted"]
    assert encoded["layer_target_counts"]["reason"] > 0
    assert encoded["layer_target_counts"]["final"] > 0
    assert not encoded["layer_target_counts"]["tool"]
    assert "mask_agreement" not in target
    assert not encoded["training_authorized"] and encoded["not_a_TokenReceipt"]
    assert encoded["feedback_requires_actual_local_tokens_and_EOS"]
    assert not encoded["api_original_sampling_tokens_claimed"]
    row = encoded["rows"][0]
    assert row["rendered_response"].startswith(episode.turns[0].raw_text)
    assert row["input_ids"][-1] == tokenizer.eos_token_id
    assert row["student_eos_position"] in row["layer_target_positions"]["final"]
    assert encoded["L_P"] == sum(encoded["layer_target_counts"].values())
    assert row["target_ids"] == [row["input_ids"][i] for i in row["target_positions"]]
    assert not encoded["public_content_without_positive_reason_targets"]


def recovered_chain():
    task = adapt_finqa([finqa_record()], split="train", revision="v10-recovery-CPU")[0]
    episode, _ = mocked_episode(
        task,
        [
            (
                "An earlier unsupported assertion.",
                [call("run_program", {"program": "divide(8, 0)"})],
            ),
            (
                "The zero divisor failed. Use the visible 8 minus 2 instead.",
                [call("run_program", {"program": "subtract(8, 2)"})],
            ),
            ("The observed result is 6.", [call("submit_program", {"program": "subtract(8, 2)"})]),
        ],
    )
    request = prepare_process_request(
        episode,
        slot_id="recovery-synthetic",
        native_result={"native": {"execution_accuracy": 1, "program_accuracy": 1}},
        integrity={key: True for key in INTEGRITY_CHECKS},
    )
    view = request["trajectory"]
    docs = {doc["segment_id"]: doc for doc in view["segments"]}

    def locator(doc):
        return dict(segment_id=doc["segment_id"], start=0, end=len(doc["text"]), quote=doc["text"])

    last_content = locator(docs[view["turns"][-1]["public_content_segment_id"]])
    source = locator(next(d for d in docs.values() if d["kind"] == "source_table_cell"))
    body = {
        "process": {
            "evidence_and_operations": dict(
                status="supported", summary="Visible subtraction.", evidence=[source, last_content]
            ),
            "observation_interpretation": dict(
                status="supported",
                summary="Observed error and result retained.",
                evidence=[last_content],
            ),
            "unwithdrawn_critical_contradictions": dict(
                status="supported", summary="Earlier mistake was withdrawn.", evidence=[]
            ),
            "actual_revisions": dict(
                status="supported",
                summary="Changed to subtraction after error.",
                evidence=[last_content],
            ),
        },
        "behavior": dict(
            description="Actual error followed by correction and execution.",
            evidence=[last_content],
        ),
        "supervision": [],
    }
    for index, turn in enumerate(view["turns"]):
        ids = [turn["public_content_segment_id"]] + [
            a["arguments_segment_id"] for a in turn["actions"]
        ]
        for sid in ids:
            body["supervision"].append(
                dict(
                    **locator(docs[sid]),
                    decision="positive" if index else "context_only",
                    reason="Synthetic reviewed recovery; original failed history is context.",
                )
            )
    return episode, request, body


def test_failed_history_kept_without_positive_targets_and_real_observations_are_inputs(tokenizer):
    episode, request, body = recovered_chain()
    encoded = encode_process_review_for_student(episode, manifest(request, body), tokenizer)
    assert encoded["encoding_admitted"] and len(encoded["rows"]) == 3
    failed, tool, final = encoded["rows"]
    assert not failed["target_positions"] and not failed["student_eos_supervised"]
    assert "earlier unsupported assertion" in final["rendered_prompt"]
    assert "divide(8, 0)" in final["rendered_prompt"]
    assert '"status": "error"' in final["rendered_prompt"]
    assert tool["layer_target_counts"]["reason"] and tool["layer_target_counts"]["tool"]
    assert final["layer_target_counts"]["reason"] and final["layer_target_counts"]["final"]
    for row in encoded["rows"]:
        assert all(i >= row["prompt_token_count"] for i in row["target_positions"])
    assert encoded["L_P"] == sum(len(row["target_ids"]) for row in encoded["rows"])


def test_all_reason_masked_is_reported_not_hidden_by_tool_only_rendering(tokenizer):
    episode, request, body = fixture()
    body["supervision"] = [body["supervision"][-1]]
    encoded = encode_process_review_for_student(episode, manifest(request, body), tokenizer)
    assert encoded["public_content_without_positive_reason_targets"]
    assert encoded["layer_target_counts"]["reason"] == 0
    assert encoded["rows"][0]["rendered_response"].startswith(episode.turns[0].raw_text)
    assert encoded["encoding_admitted"] and not encoded["training_authorized"]


def test_unknown_process_has_no_positive_targets_but_history_is_not_deleted(tokenizer):
    episode, request, body = fixture()
    body["process"]["evidence_and_operations"]["status"] = "unknown"
    encoded = encode_process_review_for_student(episode, manifest(request, body), tokenizer)
    assert not encoded["encoding_admitted"] and not encoded["total_supervised_tokens"]
    assert encoded["rows"][0]["rendered_response"].startswith(episode.turns[0].raw_text)
    assert not encoded["rows"][0]["student_eos_supervised"]


def test_rehashed_target_tampering_cannot_bypass_original_authority(tokenizer):
    episode, request, body = fixture()
    target = copy.deepcopy(manifest(request, body))
    target["positive_content_spans"][0]["quote"] = "host invented reasoning"
    target["id"] = digest({k: v for k, v in target.items() if k != "id"})
    with pytest.raises(ValueError, match="derive exactly"):
        encode_process_review_for_student(episode, target, tokenizer)


def test_failed_action_marked_positive_is_annotation_unknown_not_financial_verdict(tokenizer):
    episode, request, body = recovered_chain()
    body["supervision"][1]["decision"] = "positive"
    review = inspect_process_review(json.dumps(body), request)
    assert review["review_status"] == "annotation_failed"
    assert review["process_validity"] == "unknown"
    encoded = encode_process_review_for_student(episode, supervision_manifest(review), tokenizer)
    assert not encoded["encoding_admitted"] and encoded["total_supervised_tokens"] == 0


def test_context_limit_is_not_silently_changed_or_truncated(tokenizer):
    episode, request, body = fixture()
    with pytest.raises(ValueError, match="24576"):
        encode_process_review_for_student(
            episode, manifest(request, body), tokenizer, context_limit=16384
        )


def test_cross_span_tokens_not_expanded(tokenizer):
    episode, request, body = fixture("R: Unsupported. U: 收入🧮 changed correctly.")
    decision = body["supervision"][0]
    content = episode.turns[0].raw_text
    decision.update(start=content.index("收入"), end=content.index(" changed"), quote="收入🧮")
    body["supervision"] = [decision, body["supervision"][-1]]
    encoded = encode_process_review_for_student(episode, manifest(request, body), tokenizer)
    row = encoded["rows"][0]
    tokenized = tokenizer(
        row["rendered_prompt"] + row["rendered_response"],
        add_special_tokens=False,
        return_offsets_mapping=True,
    )
    left, right = (
        len(row["rendered_prompt"]) + decision["start"],
        len(row["rendered_prompt"]) + decision["end"],
    )
    assert row["layer_target_positions"]["reason"]
    assert all(
        left <= tokenized["offset_mapping"][i][0] < tokenized["offset_mapping"][i][1] <= right
        for i in row["layer_target_positions"]["reason"]
    )
