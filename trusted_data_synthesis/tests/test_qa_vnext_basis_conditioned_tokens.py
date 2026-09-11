"""Mocked representation controls; no real tokenizer, model, or batch tokenization.

The two historical metadata files are read verbatim. Synthetic token IDs below
exercise prefix/mask/offset/roundtrip controls, not actual Qwen token lengths or
consumability of any collected or held-out package.
"""

import copy
import socket
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support import tokens
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.plan import (
    SYSTEMS,
    encode,
    record,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import (
    SYSTEMS_NEW,
)

ROOT = Path(__file__).resolve().parents[2]


class MockTokenizer:
    """Character mock with duplicate Unicode offsets, never an actual BPE model."""

    all_special_ids = [151643, 151644, 151645]

    def __init__(self, template):
        self.chat_template = template
        self.rendered_messages = []

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        assert tokenize is False
        self.rendered_messages.append(copy.deepcopy(messages))
        text = "".join(
            f"<|im_start|>{message['role']}\n{message['content']}<|im_end|>\n"
            for message in messages
        )
        return text + ("<|im_start|>assistant\n" if add_generation_prompt else "")

    def __call__(
        self,
        text,
        *,
        add_special_tokens,
        truncation,
        padding,
        return_attention_mask=False,
        return_offsets_mapping=False,
    ):
        assert add_special_tokens is truncation is padding is False
        ids, offsets = [], []
        index = 0
        while index < len(text):
            for special, token_id in (("<|im_start|>", 151644), ("<|im_end|>", 151645)):
                if text.startswith(special, index):
                    ids.append(token_id)
                    offsets.append((index, index + len(special)))
                    index += len(special)
                    break
            else:
                char = text[index]
                ids.append(198 if char == "\n" else 1_000_000 + ord(char))
                offsets.append((index, index + 1))
                if ord(char) > 127:
                    # A second token with the same character offset models the
                    # overlapping offsets allowed for Unicode byte fallback.
                    ids.append(3_000_000 + ord(char))
                    offsets.append((index, index + 1))
                index += 1
        result = {"input_ids": ids}
        if return_attention_mask:
            result["attention_mask"] = [1] * len(ids)
        if return_offsets_mapping:
            result["offset_mapping"] = offsets
        return result

    def decode(self, ids, *, skip_special_tokens, clean_up_tokenization_spaces):
        assert skip_special_tokens is clean_up_tokenization_spaces is False
        special = {151644: "<|im_start|>", 151645: "<|im_end|>", 198: "\n"}
        return "".join(
            special[token_id] if token_id in special else chr(token_id - 1_000_000)
            for token_id in ids
            if token_id < 3_000_000
        )


@pytest.fixture(autouse=True)
def no_live_resources(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("mock-only controls cannot load a real tokenizer or access the network")

    monkeypatch.setattr(tokens.assets, "load_tokenizer", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


@pytest.fixture
def bound():
    binding, policy = tokens.read_bound_metadata(ROOT)
    return binding, policy, MockTokenizer(binding["chat_template"])


def candidate(*, basis="endpoint", task="X1", kind="Final", target=None, long_input=False):
    if target is None:
        target = ' \n{ "final": "原样 Unicode🙂 e\u0301", "spelling": 1.00 }\n'
    invalid = '{"tool":"calculate", "arguments":{"expression": 1 + 2}}'
    messages = [
        {"role": "system", "content": SYSTEMS[basis]},
        {"role": "user", "content": " x" * 33_000 if long_input else "synthetic public task"},
        {"role": "assistant", "content": invalid},
        {"role": "user", "content": '{"interface_error":"invalid_json"}'},
        {"role": "assistant", "content": '{"tool":"calculate", "arguments": {}}'},
        {"role": "user", "content": '{"tool_result":{"status":"error","error":"syntax"}}'},
        {"role": "assistant", "content": '{"message":"independent public message"}'},
        {"role": "user", "content": '{"continue":true}'},
    ]
    return record(
        "basis_mock_original_candidate",
        population=basis,
        task_key=task,
        session_label=f"{basis}_{task}_01",
        response_index=3,
        response_kind=kind,
        source_closeout_id="synthetic-source-closeout",
        request_sha256=sha(b"synthetic HTTP binding, not a received real request"),
        response_projection_sha256=sha(b"synthetic public projection binding"),
        raw_response_sha256=sha(target.encode("utf-8")),
        input_messages=messages,
        target_response=target,
    )


def reidentify(row):
    return record(
        row["id"].partition(":")[0],
        **{key: value for key, value in row.items() if key not in {"id", "schema_version"}},
    )


def test_exact_old_metadata_and_new_policy_without_loading_tokenizer(bound):
    binding, policy, _ = bound
    assert binding["id"] == tokens.BINDING_ID
    assert binding["maximum_sequence_length"] == 24_576
    assert binding["model_max_position_embeddings"] == policy["maximum_sequence_length"] == 32_768
    assert policy["inherited_representation_policy_id"] == tokens.PARENT_POLICY_ID
    assert sha((ROOT / tokens.BINDING_PATH).read_bytes()) == tokens.BINDING_SHA256
    assert sha((ROOT / tokens.PARENT_POLICY_PATH).read_bytes()) == tokens.PARENT_POLICY_SHA256
    assert policy["guidance_system_sha256"] == {
        basis: sha(SYSTEMS[basis].encode()) for basis in ("endpoint", "movement")
    }
    assert len(set(policy["guidance_system_sha256"].values())) == 2
    assert policy["generation_conditions"] == ["endpoint", "movement"]
    assert policy["scope"].startswith("new support representation and consumability only")
    assert policy["generation_basis_is_not_actual_method"] is True
    for field in (
        "truncation",
        "historical_token_rows_retokenized",
        "neutral_or_historical_N_E_prefix_substitution",
        "financial_eligibility_inferred",
        "actual_method_inferred",
        "complete_classes_inferred",
        "material_selection_performed",
        "class_weights_assigned",
        "Student_weights",
        "Student_forward",
        "training",
        "NLL",
        "greedy",
        "GPU",
        "Provider",
    ):
        assert policy[field] is False


def test_load_bound_assets_delegates_only_after_exact_metadata_check(bound, monkeypatch):
    binding, policy, mock = bound
    calls = []

    def mocked_loader(original):
        assert original == binding
        calls.append(original)
        return mock

    monkeypatch.setattr(tokens.assets, "load_tokenizer", mocked_loader)
    assert tokens.load_bound_assets(ROOT) == (binding, policy, mock)
    assert calls == [binding]


@pytest.mark.parametrize("basis", ["endpoint", "movement"])
@pytest.mark.parametrize("kind", ["message", "calculate", "read_source", "notebook", "Final"])
def test_exact_guided_history_and_original_target_for_all_positive_kinds(bound, basis, kind):
    binding, policy, tokenizer = bound
    row = candidate(basis=basis, task="X2" if basis == "movement" else "X1", kind=kind)
    before = copy.deepcopy(row)
    result = tokens.encode_candidate(row, binding, policy, tokenizer)
    assert row == before
    assert tokenizer.rendered_messages == [
        row["input_messages"],
        [*row["input_messages"], {"role": "assistant", "content": row["target_response"]}],
    ]
    assert result["population"] == basis
    assert result["guidance_system_sha256"] == sha(SYSTEMS[basis].encode())
    assert result["response_kind"] == kind
    assert result["candidate_id"] == row["id"]
    assert result["source_closeout_id"] == row["source_closeout_id"]
    assert result["tokenrepresentation_status"] == "fit"
    assert result["raw_response_sha256"] == row["raw_response_sha256"]
    assert result["target_raw_byte_count"] == len(row["target_response"].encode())
    ids, labels, mask = result["input_ids"], result["labels"], result["target_mask"]
    start, end = result["target_token_start"], result["target_token_end"]
    assert labels[:start] == [-100] * start
    assert ids[end:] == [151645, 198]
    assert labels[end:] == [-100, -100]
    assert mask == [int(start <= index < end) for index in range(len(ids))]
    assert labels == [token_id if mask[index] else -100 for index, token_id in enumerate(ids)]
    assert result["attention_mask"] == [1] * len(ids)
    assert (
        tokenizer.decode(
            ids[start:end], skip_special_tokens=False, clean_up_tokenization_spaces=False
        ).encode()
        == row["target_response"].encode()
    )
    assert result["causal_target_token_start"] == start - 1
    assert result["causal_target_token_end"] == end - 1
    assert sum(mask[1:]) == result["target_token_count"]
    assert result["target_token_count"] > len(row["target_response"])
    assert all(result["boundary_checks"].values())
    assert not {"method", "actual_method", "complete_class", "class_id", "eligible"} & result.keys()


@pytest.mark.parametrize("replacement", ["movement", "N", "E", "neutral", "whitespace"])
def test_exact_system_rejects_other_guidance_old_conditions_and_surrogates(bound, replacement):
    row = candidate()
    alternatives = {
        "movement": SYSTEMS["movement"],
        "N": SYSTEMS_NEW["N"],
        "E": SYSTEMS_NEW["E"],
        "neutral": "Follow the task.",
        "whitespace": SYSTEMS["endpoint"] + " ",
    }
    row["input_messages"][0]["content"] = alternatives[replacement]
    with pytest.raises(ValueError, match="basis_tokens.original_condition_system"):
        tokens.encode_candidate(reidentify(row), *bound)


def test_relabeling_basis_cannot_remove_the_real_guidance_prefix(bound):
    row = candidate()
    row.update(population="movement", session_label="movement_X1_01")
    with pytest.raises(ValueError, match="basis_tokens.original_condition_system"):
        tokens.encode_candidate(reidentify(row), *bound)


def test_original_input_and_target_swaps_fail_even_after_rehashing_only_the_target(bound):
    row = candidate()
    row["target_response"] = '{"final":"different original response"}'
    with pytest.raises(ValueError, match="basis_tokens.target_bytes"):
        tokens.encode_candidate(row, *bound)
    row["raw_response_sha256"] = sha(row["target_response"].encode())
    with pytest.raises(ValueError, match="basis_tokens.original_candidate_content_identity"):
        tokens.encode_candidate(row, *bound)
    row = candidate()
    row["input_messages"][1]["content"] = "different original source question"
    with pytest.raises(ValueError, match="basis_tokens.original_candidate_content_identity"):
        tokens.encode_candidate(row, *bound)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("population", "N"),
        ("population", "E"),
        ("task_key", "X3C"),
        ("session_label", "endpoint_X1_09"),
        ("session_label", "endpoint_X2_01"),
        ("response_index", True),
        ("response_index", 32),
    ],
)
def test_only_the_fixed_new_generation_conditions_and_sessions_are_accepted(bound, field, value):
    row = candidate()
    row[field] = value
    with pytest.raises(ValueError, match="basis_tokens.population_and_response"):
        tokens.encode_candidate(reidentify(row), *bound)


def test_historical_schema_cannot_be_rehashed_into_a_new_candidate(bound):
    row = candidate()
    row["schema_version"] = "source_class_utility.v1.basis_mock_original_candidate"
    kind = row["id"].partition(":")[0]
    row["id"] = kind + ":" + sha(encode({key: value for key, value in row.items() if key != "id"}))
    with pytest.raises(ValueError, match="basis_tokens.original_candidate_content_identity"):
        tokens.encode_candidate(row, *bound)


@pytest.mark.parametrize("location", ["input", "target"])
def test_overlength_retains_original_and_diagnostics_but_no_cropped_arrays(bound, location):
    row = candidate(
        long_input=location == "input", target="t" * 33_000 if location == "target" else None
    )
    before = copy.deepcopy(row)
    result = tokens.encode_candidate(row, *bound)
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


class MutatedTokenizer:
    def __init__(self, tokenizer, mutation, start, end):
        self.tokenizer, self.mutation, self.start, self.end = tokenizer, mutation, start, end

    def __getattr__(self, name):
        return getattr(self.tokenizer, name)

    def apply_chat_template(self, *args, **kwargs):
        rendered = self.tokenizer.apply_chat_template(*args, **kwargs)
        return rendered + (
            " " if self.mutation == "render" and not kwargs["add_generation_prompt"] else ""
        )

    def __call__(self, text, **kwargs):
        result = self.tokenizer(text, **kwargs)
        if not kwargs.get("return_offsets_mapping"):
            if self.mutation == "prefix":
                result["input_ids"][-1] += 1
            return result
        offsets = result["offset_mapping"]
        start = next(index for index, offset in enumerate(offsets) if offset[0] == self.start)
        end = next(index for index, offset in enumerate(offsets) if offset[0] == self.end)
        if self.mutation == "cross_start":
            offsets[start] = (self.start - 1, self.start + 1)
        elif self.mutation == "cross_end":
            offsets[end - 1] = (self.end - 1, self.end + 1)
        elif self.mutation == "offset_gap":
            offsets[start] = (self.start + 1, self.start + 2)
        elif self.mutation == "offset_shape":
            offsets.pop()
        elif self.mutation == "target_special":
            result["input_ids"][start] = 151644
        elif self.mutation == "suffix":
            result["input_ids"][-1] += 1
        elif self.mutation == "padding":
            result["attention_mask"][-1] = 0
        return result

    def decode(self, *args, **kwargs):
        decoded = self.tokenizer.decode(*args, **kwargs)
        return decoded + (" " if self.mutation == "decode" else "")


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("render", "rendered_content_changed"),
        ("prefix", "prefix_token_mismatch"),
        ("cross_start", "boundary_crossing"),
        ("cross_end", "boundary_crossing"),
        ("offset_gap", "target_offset_coverage"),
        ("offset_shape", "offset_shape"),
        ("target_special", "target_special_token"),
        ("suffix", "suffix_tokens"),
        ("padding", "unexpected_padding"),
        ("decode", "target_decode"),
    ],
)
def test_mocked_boundary_roundtrip_suffix_and_padding_failures_reject(bound, mutation, code):
    binding, policy, tokenizer = bound
    row = candidate(target='{"final":"abc"}')
    prefix = tokenizer.apply_chat_template(
        row["input_messages"], tokenize=False, add_generation_prompt=True
    )
    changed = MutatedTokenizer(
        tokenizer, mutation, len(prefix), len(prefix) + len(row["target_response"])
    )
    with pytest.raises(ValueError, match="basis_tokens." + code):
        tokens.encode_candidate(row, binding, policy, changed)


def test_template_and_policy_drift_reject_before_representation(bound):
    binding, policy, tokenizer = bound
    tokenizer.chat_template += " "
    with pytest.raises(ValueError, match="basis_tokens.runtime_template"):
        tokens.encode_candidate(candidate(), binding, policy, tokenizer)
    tokenizer.chat_template = binding["chat_template"]
    changed = copy.deepcopy(policy)
    changed["guidance_system_sha256"]["movement"] = changed["guidance_system_sha256"]["endpoint"]
    with pytest.raises(ValueError, match="basis_tokens.frozen_policy"):
        tokens.encode_candidate(candidate(), binding, changed, tokenizer)


@pytest.mark.parametrize("field", ["chat_template", "model_max_length_declared", "members"])
def test_modified_binding_content_cannot_retain_the_historical_identity(bound, field):
    binding, policy, tokenizer = bound
    changed = copy.deepcopy(binding)
    changed[field] = "changed"
    with pytest.raises(ValueError, match="basis_tokens.existing_binding_identity"):
        tokens.encode_candidate(candidate(), changed, policy, tokenizer)


def test_embedded_template_special_token_in_original_target_is_not_rewritten(bound):
    row = candidate(target='{"final":"<|im_start|>"}')
    before = copy.deepcopy(row)
    with pytest.raises(ValueError, match="basis_tokens.target_special_token"):
        tokens.encode_candidate(row, *bound)
    assert row == before
