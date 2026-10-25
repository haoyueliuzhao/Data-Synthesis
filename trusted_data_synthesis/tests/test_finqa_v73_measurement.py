"""CPU-only checks for V73 static actions, true token spans and causal NLL."""
import copy
import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.finance_research.qwen_protocol import parse_qwen_native_response, strict_json_decoder
from trusted_synthesis.finance_research.native_metrics import _program_tokens
from trusted_synthesis.finance_research.metric_vendor.finqa_evaluate import program_tokenization


SPEC = importlib.util.spec_from_file_location("v73_measurement_test", Path(__file__).parents[1] / "scripts/finqa_v73_measurement.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
API = SimpleNamespace(parse=parse_qwen_native_response, decoder=strict_json_decoder,
    program_tokens=lambda value: _program_tokens(value, SimpleNamespace(program_tokenization=program_tokenization)))
TOOLS = [{"type": "function", "function": {"name": name}} for name in m.ACTION_NAMES]


def envelope(name="submit_program", arguments=None):
    return '<tool_call>\n' + json.dumps({"name": name, "arguments": {"program": "add(1, 2)"} if arguments is None else arguments}) + '\n</tool_call>'


@pytest.mark.parametrize(("raw", "category", "A", "S"), [
    (envelope(), "compliant_submit_candidate", 1, 1),
    (envelope("run_program"), "compliant_nonterminal_candidate", 1, 0),
    (envelope("read_source", {"source_id": "table"}), "compliant_nonterminal_candidate", 1, 0),
    (envelope("list_sources", {}), "compliant_nonterminal_candidate", 1, 0),
    (envelope(arguments={"program": "827"}), "attempted_invalid_submit", 0, 0),
    (envelope(arguments={"program": "add(1, 2)", "answer": 3}), "attempted_invalid_submit", 0, 0),
    (envelope("read_source", {"source_id": ""}), "other_contract_failure", 0, 0),
    (envelope("final_answer", {"answer": 3}), "other_contract_failure", 0, 0),
    (envelope() + "\n" + envelope("run_program"), "other_contract_failure", 0, 0),
    ('<tool_call>{"name":"submit_program","arguments":{bad}}</tool_call>', "other_contract_failure", 0, 0),
    ('<tool_call>{"name":"submit_program","arguments":{"program":"add(1, 2)"}}', "other_contract_failure", 0, 0),
    ('I will now submit_program("add(1, 2)").', "plain_no_tool_call", 0, 0),
])
def test_five_static_action_classes_are_mutually_exclusive(raw, category, A, S):
    out = m.classification(raw, TOOLS, api=API)
    assert (out["category"], out["A"], out["S"]) == (category, A, S)
    assert out["tool_execution"] == out["native_scoring"] == 0
    assert out["answer_correctness"] is None


def test_duplicate_json_is_never_repaired_into_a_submit():
    raw = '<tool_call>{"name":"submit_program","arguments":{"program":"add(1, 2)","program":"add(1, 3)"}}</tool_call>'
    assert m.classification(raw, TOOLS, api=API)["category"] == "other_contract_failure"


class ByteTokenizer:
    """Minimal Qwen ByteLevel fake; can intentionally retain noncanonical chunks."""
    eos = 100000

    def __init__(self, chunks):
        alphabet = {value: key for key, value in m._byte_level_inverse().items()}
        self.vocab = {i: "".join(alphabet[b] for b in chunk) for i, chunk in enumerate(chunks)}
        self.vocab[self.eos] = "<|im_end|>"

    def convert_ids_to_tokens(self, token_id):
        return self.vocab[token_id]

    def get_added_vocab(self):
        return {"<|im_end|>": self.eos}

    def decode(self, ids, **kwargs):
        inverse = m._byte_level_inverse()
        return b"".join(bytes(inverse[c] for c in self.vocab[i]) for i in ids).decode()

    def encode(self, *args, **kwargs):
        raise AssertionError("saved generation must not be retokenized")


def grouping(raw=None, *, chunks=None, eos=True):
    raw = raw if raw is not None else "Public reasoning.\n" + envelope()
    chunks = chunks if chunks is not None else [bytes([b]) for b in raw.encode()]
    tokenizer = ByteTokenizer(chunks)
    ids = list(range(len(chunks))) + ([tokenizer.eos] if eos else [])
    out = m.annotate_parent_target(tokenizer, ids, raw, eos_ids=[tokenizer.eos], actual_eos=eos, tools=TOOLS, api=API)
    return out, tokenizer, ids


def test_parent_target_groups_are_partitioned_and_do_not_retokenize():
    out, _, ids = grouping()
    groups = out["position_groups"]
    assert sorted(p for row in groups.values() for p in row) == list(range(len(ids)))
    assert groups["actual_terminal_EOS"] == [len(ids) - 1]
    assert len(groups["program_parameter_content"]) == len("add(1, 2)")
    assert groups["pre_action_text"] and groups["action_structure"]
    assert not groups["boundary_mixed"]


def test_unicode_split_across_actual_tokens_uses_bytes_not_replacement_chars():
    raw = "数值🙂\n" + envelope()
    out, _, _ = grouping(raw)
    assert out["group_token_counts"]["pre_action_text"] == len("数值🙂\n".encode())
    assert not out["position_groups"]["boundary_mixed"]


def test_program_boundary_bpe_token_is_not_misreported_as_pure_structure():
    raw = envelope()
    left = raw.index("add(")
    data = raw.encode()
    # One actual token contains the JSON quote and the first program character.
    chunks = [data[:left - 1], data[left - 1:left + 1], data[left + 1:]]
    out, _, _ = grouping(raw, chunks=chunks)
    assert out["position_groups"]["boundary_mixed"] == [1, 2]
    assert out["token_boundaries"][1]["intersected_groups"] == ["action_structure", "program_parameter_content"]


def test_trailing_whitespace_is_separate_from_action_and_actual_eos():
    out, _, _ = grouping(envelope() + "\n \t")
    assert len(out["position_groups"]["post_action_whitespace"]) == 3
    assert not out["position_groups"]["pre_action_text"]


def test_json_escaped_program_bytes_remain_parameter_content():
    raw = envelope(arguments={"program": "add(1, 2\t)"})
    out, _, _ = grouping(raw)
    assert len(out["position_groups"]["program_parameter_content"]) == len('add(1, 2\\t)')


def test_no_original_eos_is_na_not_synthetic_zero_loss():
    out, _, ids = grouping(envelope(), eos=False)
    summary = m.summarize_token_logps([-0.5] * len(ids), out)
    assert summary["groups"]["actual_terminal_EOS"] == {"token_count": 0, "nll_sum": None, "mean_nll": None, "status": "NA"}
    assert summary["groups"]["pre_action_text"]["mean_nll"] is None


def test_saved_eos_and_raw_decode_mismatch_block_target_annotation():
    out, tokenizer, ids = grouping()
    with pytest.raises(ValueError, match="EOS receipt"):
        m.annotate_parent_target(tokenizer, ids, "Public reasoning.\n" + envelope(), eos_ids=[tokenizer.eos], actual_eos=False, tools=TOOLS, api=API)
    with pytest.raises(ValueError, match="decode mismatch"):
        m.annotate_parent_target(tokenizer, ids, "Different.\n" + envelope(), eos_ids=[tokenizer.eos], actual_eos=True, tools=TOOLS, api=API)


def test_logit_shift_and_full_vocabulary_log_softmax():
    torch = pytest.importorskip("torch")
    logits = torch.tensor([[100., -100., 0.], [0., 1., 2.], [2., 0., -1.], [-3., -2., 4.]], requires_grad=True)
    values = m.causal_target_logps(logits, prompt_length=2, response_ids=[2, 0], position_chunk_size=1)
    expected = [2 - math.log(math.exp(0) + math.exp(1) + math.exp(2)),
                2 - math.log(math.exp(2) + math.exp(0) + math.exp(-1))]
    assert values == pytest.approx(expected, abs=1e-6)
    assert logits.grad is None


def test_logit_chunks_have_identical_values_and_no_temperature():
    torch = pytest.importorskip("torch")
    logits = torch.tensor([[1., 4., 3.], [0., 2., 1.], [8., 7., 3.]])
    one = m.target_logps_from_logits(logits, [0, 1, 2], position_chunk_size=1)
    all_at_once = m.target_logps_from_logits(logits, [0, 1, 2], position_chunk_size=64)
    assert one == all_at_once
    assert all_at_once == pytest.approx(torch.log_softmax(logits, -1)[range(3), [0, 1, 2]].tolist())


def test_nonfinite_logits_and_incorrect_alignment_block_probability():
    torch = pytest.importorskip("torch")
    with pytest.raises(ValueError, match="nonfinite"):
        m.target_logps_from_logits(torch.tensor([[0., float("nan")]]), [0])
    with pytest.raises(ValueError, match="alignment"):
        m.target_logps_from_logits(torch.zeros(2, 3), [0])
    with pytest.raises(ValueError, match="preceding causal"):
        m.causal_target_logps(torch.zeros(2, 3), prompt_length=0, response_ids=[0])


def test_group_nll_sums_and_positions_preserve_full_denominator():
    groups, _, ids = grouping()
    values = [-0.1 * (index + 1) for index in range(len(ids))]
    out = m.summarize_token_logps(values, groups)
    assert sum(v["token_count"] for v in out["groups"].values()) == len(ids)
    assert sum(v["nll_sum"] or 0 for v in out["groups"].values()) == pytest.approx(out["total_nll"])
    bad = copy.deepcopy(groups)
    bad["position_groups"]["action_structure"].append(0)
    with pytest.raises(ValueError, match="overlapping or missing"):
        m.summarize_token_logps(values, bad)
    with pytest.raises(ValueError, match="unknown/nonfinite"):
        m.summarize_token_logps([float("nan")] * len(ids), groups)


def test_completion_budget_label_is_orthogonal_to_action():
    out = m.completion_labels(response_ids=[1, 2], actual_eos=False, finish_reason="length", max_new_tokens=2, eos_ids=[99])
    assert out["reached_token_limit"] and out["truncated_by_token_limit"]
    assert "category" not in out
    out = m.completion_labels(response_ids=[1, 99], actual_eos=True, finish_reason="stop", max_new_tokens=2, eos_ids=[99])
    assert out["reached_token_limit"] and not out["truncated_by_token_limit"]


def test_non_EOS_early_finish_is_not_mislabelled_as_token_limit_truncation():
    out = m.completion_labels(response_ids=[1, 2], actual_eos=False, finish_reason="length", max_new_tokens=2048, eos_ids=[99])
    assert out["non_EOS_finish_before_token_limit"]
    assert not out["reached_token_limit"] and not out["truncated_by_token_limit"]
