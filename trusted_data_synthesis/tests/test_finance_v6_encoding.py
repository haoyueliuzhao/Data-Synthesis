"""Real frozen CPU Student tokenizer controls; all API responses are mock fixtures."""

import copy

import pytest
from test_finance_public_reasoning import call, mocked_episode
from test_finance_research_datasets import finqa_record
from test_finance_research_r2 import TOKENIZER

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.v6_encoding import encode_reviewed_probe_for_student
from trusted_synthesis.finance_research.v6_task import public_trajectory_view


@pytest.fixture
def bundle():
    return adapt_finqa([finqa_record()], split="train", revision="V6-encoding-control")[0]


@pytest.fixture(scope="module")
def tokenizer():
    from transformers import AutoTokenizer

    assert (TOKENIZER / "tokenizer_config.json").is_file(), "NO_ADMISSION: frozen tokenizer absent"
    return AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)


def mask_for(episode, *, failed_first=False, slot_id=None):
    view = public_trajectory_view(episode, slot_id=slot_id)
    spans, actions = [], []
    documents = {row["segment_id"]: row for row in view["segments"]}
    for index, turn in enumerate(view["turns"]):
        if failed_first and index == 0:
            continue
        doc = documents[turn["public_content_segment_id"]]
        if doc["text"]:
            spans.append(
                {
                    "doc_id": "review/" + doc["segment_id"],
                    "original_segment_id": doc["segment_id"],
                    "start": 0,
                    "end": len(doc["text"]),
                    "quote": doc["text"],
                    "layer": "reason",
                }
            )
        actions.extend(action["action_id"] for action in turn["actions"])
    return {
        "episode_sha256": digest(episode),
        "view_id": view["view_id"],
        "slot_id": slot_id,
        "mask_agreement": True,
        "consensus_sha256": "synthetic-fixture-no-semantic-claim",
        "not_a_TokenReceipt": True,
        "positive_content_spans": spans,
        "positive_action_ids": actions,
    }


def chain(bundle):
    return mocked_episode(
        bundle,
        [
            (
                "R: wrong statement subsequently withdrawn.",
                [call("run_program", {"program": "divide(8, 0)"})],
            ),
            (
                "U: The division failed. R: Use 8 minus 2.",
                [call("run_program", {"program": "subtract(8, 2)"})],
            ),
            ("R: The actual result is 6.", [call("submit_program", {"program": "subtract(8, 2)"})]),
        ],
    )[0]


def test_full_history_masks_and_whole_package_normalization(bundle, tokenizer):
    episode = chain(bundle)
    artifact = encode_reviewed_probe_for_student(
        episode, mask_for(episode, failed_first=True), tokenizer
    )
    assert artifact["encoding_admitted"] and artifact["not_a_TokenReceipt"]
    assert not artifact["api_original_sampling_tokens_claimed"]
    assert artifact["L_P"] == sum(len(row["target_ids"]) for row in artifact["rows"])
    assert artifact["L_P"] == sum(artifact["layer_target_counts"].values())
    failed, tool, final = artifact["rows"]
    assert not failed["target_positions"] and not failed["student_eos_supervised"]
    assert "wrong statement subsequently withdrawn" in final["rendered_prompt"]
    assert "divide(8, 0)" in final["rendered_prompt"]
    assert '"status": "error"' in final["rendered_prompt"]
    assert tool["layer_target_counts"]["tool"] > 0 and not tool["layer_target_counts"]["final"]
    assert final["layer_target_counts"]["final"] > 0 and not final["layer_target_counts"]["tool"]
    for row in artifact["rows"]:
        assert row["input_ids"][-1] == tokenizer.eos_token_id
        assert row["target_ids"] == [row["input_ids"][i] for i in row["target_positions"]]
        assert all(i >= row["prompt_token_count"] for i in row["target_positions"])
    assert tool["student_eos_position"] in tool["layer_target_positions"]["tool"]
    assert final["student_eos_position"] in final["layer_target_positions"]["final"]


def test_only_tokens_wholly_inside_original_approved_character_spans(bundle, tokenizer):
    prose = "R: Unsupported. U: 收入🧮 changed correctly."
    episode, _ = mocked_episode(
        bundle, [(prose, [call("submit_program", {"program": "subtract(8, 2)"})])]
    )
    mask = mask_for(episode, slot_id="s0")
    span = mask["positive_content_spans"][0]
    span.update(start=prose.index("收入"), end=prose.index(" changed"), quote="收入🧮")
    artifact = encode_reviewed_probe_for_student(episode, mask, tokenizer)
    row = artifact["rows"][0]
    encoded = tokenizer(
        row["rendered_prompt"] + row["rendered_response"],
        add_special_tokens=False,
        return_offsets_mapping=True,
    )
    positive = row["layer_target_positions"]["reason"]
    assert positive
    left, right = (
        len(row["rendered_prompt"]) + span["start"],
        len(row["rendered_prompt"]) + span["end"],
    )
    assert all(
        left <= encoded["offset_mapping"][i][0] < encoded["offset_mapping"][i][1] <= right
        for i in positive
    )


def test_failed_action_cannot_become_supervised_even_with_positive_manifest(bundle, tokenizer):
    episode = chain(bundle)
    with pytest.raises(ValueError, match="successful execution"):
        encode_reviewed_probe_for_student(episode, mask_for(episode), tokenizer)


@pytest.mark.parametrize("corruption", ["quote", "view", "agreement"])
def test_mask_binding_rejects_forged_spans_or_context(bundle, tokenizer, corruption):
    episode = chain(bundle)
    mask = mask_for(episode, failed_first=True)
    if corruption == "quote":
        mask["positive_content_spans"][0]["quote"] = "fabricated"
    elif corruption == "view":
        mask["view_id"] = "other"
    else:
        mask["mask_agreement"] = False
    with pytest.raises(ValueError):
        encode_reviewed_probe_for_student(episode, mask, tokenizer)


def test_overlength_is_blocked_without_deleting_or_truncating_material(bundle, tokenizer):
    long_source = bundle.public.sources[0].model_copy(update={"content": "extra " * 25000})
    public = bundle.public.model_copy(
        update={"sources": (long_source,) + bundle.public.sources[1:]}
    )
    large = bundle.model_copy(update={"public": public})
    episode, _ = mocked_episode(
        large, [("R: Submit.", [call("submit_program", {"program": "subtract(8, 2)"})])]
    )
    artifact = encode_reviewed_probe_for_student(episode, mask_for(episode), tokenizer)
    assert not artifact["encoding_admitted"] and artifact["max_sequence_tokens"] > 24576
    assert not artifact["context_truncated"] and artifact["rows"]
    assert long_source.content in artifact["rows"][0]["rendered_prompt"]


def test_api_history_or_hidden_thinking_cannot_enter_normal_encoding(bundle, tokenizer):
    episode = chain(bundle)
    original = episode.turns[1]
    metadata = copy.deepcopy(original.provider_metadata)
    metadata["public_request"]["messages"][2]["content"] = "host deleted failed text"
    metadata["request_sha256"] = digest(metadata["public_request"])
    changed = episode.model_copy(
        update={
            "turns": (
                episode.turns[0],
                original.model_copy(update={"provider_metadata": metadata}),
                episode.turns[2],
            )
        }
    )
    with pytest.raises(ValueError, match="API request"):
        encode_reviewed_probe_for_student(changed, mask_for(changed, failed_first=True), tokenizer)
    private, _ = mocked_episode(
        bundle,
        [("R: public", [call("submit_program", {"program": "subtract(8, 2)"})])],
        private_content="hidden",
    )
    with pytest.raises(ValueError, match="private thinking"):
        encode_reviewed_probe_for_student(private, mask_for(private), tokenizer)
