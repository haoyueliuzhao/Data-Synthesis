"""Synthetic open-history tokenizer-only controls, not new model materialization."""

import copy
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_open_materialization import tokens
from trusted_synthesis.experiments.finance_qa_vnext_open_materialization.plan import record, sha
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import execution_guard
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import SYSTEMS

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def local_assets():
    with execution_guard(online=False) as counts:
        bound = tokens.load_bound_assets(ROOT)
        yield bound
        assert not any(counts.values())


def candidate(*, population="T", target='{"final":"原样 Unicode🙂"}', long_input=False):
    invalid = '{"tool":"calculate", "arguments":{"expression": 1 + 2}}'
    messages = [
        {"role": "system", "content": SYSTEMS[population]},
        {"role": "user", "content": " x" * 33_000 if long_input else "synthetic task only"},
        {"role": "assistant", "content": invalid},
        {"role": "user", "content": '{"interface_error":"invalid_json"}'},
    ]
    return record(
        "synthetic_open_candidate",
        population=population,
        task_key="synthetic",
        session_label=population + "_synthetic_01",
        response_index=1,
        source_closeout_id="synthetic-closeout",
        request_sha256=sha(b"synthetic request binding, not a model call"),
        response_projection_sha256=sha(b"synthetic public projection binding"),
        raw_response_sha256=sha(target.encode("utf-8")),
        input_messages=messages,
        target_response=target,
    )


def test_existing_binding_is_unchanged_and_32768_policy_is_inherited(local_assets):
    binding, policy, tokenizer = local_assets
    assert binding["id"] == tokens.BINDING_ID
    assert binding["maximum_sequence_length"] == 24_576
    assert policy["maximum_sequence_length"] == 32_768
    assert policy["inherited_representation_policy_id"] == tokens.PARENT_POLICY_ID
    assert policy["truncation"] is False
    assert policy["Student_weights"] is policy["Student_forward"] is policy["GPU"] is False
    assert tokenizer.chat_template == binding["chat_template"]


def test_multimessage_errors_preserved_as_masked_prefix_and_exact_unicode_target(local_assets):
    binding, policy, tokenizer = local_assets
    row = candidate()
    before = copy.deepcopy(row)
    result = tokens.encode_candidate(row, binding, policy, tokenizer)
    assert row == before
    prefix = tokenizer.apply_chat_template(
        row["input_messages"], tokenize=False, add_generation_prompt=True
    )
    assert row["input_messages"][2]["content"] in prefix
    assert row["input_messages"][3]["content"] in prefix
    assert SYSTEMS["T"] in prefix
    ids, labels, mask = result["input_ids"], result["labels"], result["target_mask"]
    start, end = result["target_token_start"], result["target_token_end"]
    prefix_ids = tokenizer(prefix, add_special_tokens=False, truncation=False)["input_ids"]
    assert ids[:start] == prefix_ids
    assert labels[:start] == [-100] * start
    assert mask == [int(start <= i < end) for i in range(len(ids))]
    assert labels == [token if mask[i] else -100 for i, token in enumerate(ids)]
    assert ids[end:] == [151645, 198]
    assert labels[end:] == [-100, -100]
    assert (
        tokenizer.decode(
            ids[start:end], skip_special_tokens=False, clean_up_tokenization_spaces=False
        ).encode()
        == row["target_response"].encode()
    )
    assert result["causal_target_token_start"] == start - 1
    assert result["causal_target_token_end"] == end - 1
    assert not {"qualification_id", "public_runtime_state_id"} & result.keys()


def test_bound_target_cross_swap_and_condition_system_cross_swap_are_rejected(local_assets):
    binding, policy, tokenizer = local_assets
    row = candidate()
    row["target_response"] = '{"final":"a different interaction"}'
    with pytest.raises(ValueError, match="open_tokens.target_bytes"):
        tokens.encode_candidate(row, binding, policy, tokenizer)
    row["raw_response_sha256"] = sha(row["target_response"].encode())
    with pytest.raises(ValueError, match="open_tokens.candidate_identity"):
        tokens.encode_candidate(row, binding, policy, tokenizer)
    row = candidate()
    row["input_messages"][1]["content"] = "an unrelated synthetic source question"
    with pytest.raises(ValueError, match="open_tokens.candidate_identity"):
        tokens.encode_candidate(row, binding, policy, tokenizer)
    row = candidate()
    row["input_messages"][0]["content"] = SYSTEMS["A"]
    with pytest.raises(ValueError, match="open_tokens.original_condition_system"):
        tokens.encode_candidate(row, binding, policy, tokenizer)


def test_content_boundary_and_special_tokens_fail_closed(local_assets):
    binding, policy, tokenizer = local_assets
    row = candidate()
    prefix = tokenizer.apply_chat_template(
        row["input_messages"], tokenize=False, add_generation_prompt=True
    )

    class CrossingOffset:
        def __getattr__(self, name):
            return getattr(tokenizer, name)

        def __call__(self, text, **kwargs):
            encoded = tokenizer(text, **kwargs)
            if kwargs.get("return_offsets_mapping"):
                for index, (left, right) in enumerate(encoded["offset_mapping"]):
                    if left == len(prefix) and right > left:
                        encoded["offset_mapping"][index] = (left - 1, right)
                        break
            return encoded

    with pytest.raises(ValueError, match="open_tokens.boundary_crossing"):
        tokens.encode_candidate(row, binding, policy, CrossingOffset())
    with pytest.raises(ValueError, match="open_tokens.target_special_token"):
        tokens.encode_candidate(
            candidate(target='{"final":"<|im_start|>"}'), binding, policy, tokenizer
        )


def test_overlength_keeps_raw_candidate_and_diagnostics_without_truncation(local_assets):
    binding, policy, tokenizer = local_assets
    row = candidate(long_input=True)
    before = copy.deepcopy(row)
    result = tokens.encode_candidate(row, binding, policy, tokenizer)
    assert row == before
    assert result["tokenrepresentation_status"] == "not_fit"
    assert result["reason"] == "maximum_sequence_length_exceeded"
    assert result["sequence_length"] > 32_768
    assert result["target_token_count"] > 0
    assert result["consumable_token_representation"] is False
    assert result["truncated"] is False
    assert result["original_candidate_retained"] is True
    assert all(
        result[key] is None for key in ("input_ids", "labels", "attention_mask", "target_mask")
    )
