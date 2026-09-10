"""New local-interface controls using CPU synthetic modules and fake decoders only.

The tiny random Qwen architecture below is not the bound Qwen2.5-7B checkpoint.
No pretrained model, tokenizer, Student weights, teacher call or GPU is used.
"""

import builtins
import copy
import io
import json
import os
import socket
from fractions import Fraction
from pathlib import Path

import pytest
import torch
from torch import nn
from transformers import AutoModelForCausalLM, AutoTokenizer, Qwen2Config, Qwen2ForCausalLM

from trusted_synthesis.experiments.finance_qa_vnext_pq_student import (
    guards,
    inference,
    loss,
    model,
    panel,
    runtime,
    train,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import (
    SYSTEM,
    encode,
    evaluation_config,
    training_config,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def synthetic_only(monkeypatch):
    counts = {"pretrained": 0, "Student": 0, "tokenizer": 0, "GPU": 0, "network": 0}
    cpu_state = torch.get_rng_state()
    old_threads = torch.get_num_threads()
    old_deterministic = torch.are_deterministic_algorithms_enabled()

    def fail(name):
        def blocked(*args, **kwargs):
            counts[name] += 1
            raise AssertionError("synthetic-only control reached " + name)

        return blocked

    monkeypatch.setattr(AutoModelForCausalLM, "from_pretrained", fail("pretrained"))
    monkeypatch.setattr(Qwen2ForCausalLM, "from_pretrained", fail("pretrained"))
    monkeypatch.setattr(AutoTokenizer, "from_pretrained", fail("tokenizer"))
    monkeypatch.setattr(model, "load_student", fail("Student"))
    monkeypatch.setattr(model, "bind_checkpoint", fail("Student"))
    monkeypatch.setattr(torch.cuda, "_lazy_init", fail("GPU"))
    monkeypatch.setattr(socket.socket, "connect", fail("network"))
    monkeypatch.setattr(socket.socket, "connect_ex", fail("network"))
    monkeypatch.setattr(socket, "create_connection", fail("network"))
    torch.set_num_threads(2)
    yield
    torch.set_rng_state(cpu_state)
    torch.set_num_threads(old_threads)
    torch.use_deterministic_algorithms(old_deterministic)
    assert not any(counts.values())
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_low_rank_zero_B_preserves_base_and_only_A_B_can_receive_gradients(dtype):
    torch.random.default_generator.manual_seed(101)
    base = nn.Linear(8, 5, bias=True, device="cpu", dtype=dtype)
    inputs = torch.randn(3, 8, dtype=dtype, device="cpu")
    expected = base(inputs).detach().clone()
    adapted = model.LowRankLinear(copy.deepcopy(base), rank=4, alpha=8, dropout=0.25)
    adapted.train()
    actual = adapted(inputs)
    torch.testing.assert_close(actual, expected, atol=0, rtol=0)
    assert actual.dtype == dtype
    assert {name for name, parameter in adapted.named_parameters() if parameter.requires_grad} == {
        "lora_A",
        "lora_B",
    }
    assert adapted.lora_A.dtype == adapted.lora_B.dtype == torch.float32
    assert torch.count_nonzero(adapted.lora_B) == 0
    actual.float().square().sum().backward()
    assert adapted.base.weight.grad is adapted.base.bias.grad is None
    assert adapted.lora_A.grad is not None and torch.count_nonzero(adapted.lora_A.grad) == 0
    assert adapted.lora_B.grad is not None and torch.count_nonzero(adapted.lora_B.grad) > 0


class SyntheticAttention(nn.Module):
    def __init__(self):
        super().__init__()
        self.attention = nn.Module()
        self.attention.q_proj = nn.Linear(16, 16)
        self.attention.k_proj = nn.Linear(16, 16)
        self.attention.v_proj = nn.Linear(16, 8)
        self.embedding = nn.Embedding(32, 16)


def paired_adapter(seed):
    torch.random.default_generator.manual_seed(9001)
    synthetic = SyntheticAttention()
    torch.random.default_generator.manual_seed(seed)
    scope = model.install_adapters(synthetic, training_config())
    return synthetic, scope


def test_paired_seed_adapter_identity_and_trainable_scope_are_reproducible():
    first, scope = paired_adapter(11)
    paired, second_scope = paired_adapter(11)
    other_seed, _ = paired_adapter(29)
    assert model.adapter_digest(first) == model.adapter_digest(paired)
    assert model.adapter_digest(first) != model.adapter_digest(other_seed)
    assert scope == second_scope
    assert scope["target_module_names"] == ["attention.q_proj", "attention.v_proj"]
    assert scope["trainable_parameter_count"] == 8 * (16 + 16 + 16 + 8)
    assert not first.embedding.weight.requires_grad
    assert not first.attention.k_proj.weight.requires_grad
    assert all(
        name.endswith((".lora_A", ".lora_B"))
        for name, p in first.named_parameters()
        if p.requires_grad
    )


def test_tiny_random_Qwen_nonreentrant_checkpoint_and_selected_causal_loss_backward():
    torch.random.default_generator.manual_seed(31)
    configuration = Qwen2Config(
        vocab_size=97,
        hidden_size=32,
        intermediate_size=64,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=2,
        max_position_embeddings=64,
        attention_dropout=0.0,
        use_cache=False,
        tie_word_embeddings=False,
    )
    configuration._attn_implementation = "eager"
    with torch.device("cpu"):
        full = Qwen2ForCausalLM(configuration)
    assert sum(p.numel() for p in full.parameters()) < 100_000
    model.install_adapters(full, training_config())
    full.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    full.train()
    selected = copy.deepcopy(full)
    assert full.is_gradient_checkpointing and selected.is_gradient_checkpointing
    inputs = torch.arange(1, 13, dtype=torch.long).unsqueeze(0)
    attention = torch.ones_like(inputs)
    labels = torch.full_like(inputs, -100)
    labels[:, 6:10] = inputs[:, 6:10]
    target_positions = torch.where(labels[0] != -100)[0]
    paired_rng = torch.get_rng_state()
    full_logits = full(
        input_ids=inputs, attention_mask=attention, use_cache=False, logits_to_keep=0
    ).logits
    full_loss = loss.full_causal_loss(full_logits, labels, Fraction(1, 259 * 18))
    full_loss.backward()
    torch.set_rng_state(paired_rng)
    selected_logits = selected(
        input_ids=inputs,
        attention_mask=attention,
        use_cache=False,
        logits_to_keep=target_positions - 1,
    ).logits
    selected_loss = loss.selected_target_loss(
        selected_logits, labels[0, target_positions], Fraction(1, 259 * 18)
    )
    selected_loss.backward()
    assert selected_logits.shape == (1, 4, 97)
    assert full_logits.shape == (1, 12, 97)
    torch.testing.assert_close(selected_loss, full_loss, atol=1e-7, rtol=1e-6)
    full_parameters = dict(full.named_parameters())
    has_nonzero_gradient = False
    for name, parameter in selected.named_parameters():
        if parameter.requires_grad:
            assert parameter.grad is not None and torch.isfinite(parameter.grad).all()
            torch.testing.assert_close(
                parameter.grad, full_parameters[name].grad, atol=1e-7, rtol=1e-5
            )
            has_nonzero_gradient |= bool(torch.count_nonzero(parameter.grad))
        else:
            assert parameter.grad is full_parameters[name].grad is None
    assert has_nonzero_gradient


def test_paired_training_order_is_a_complete_same_budget_permutation():
    first = train.row_orders(11)
    assert first == train.row_orders(11)
    assert first != train.row_orders(29)
    assert len(first) == 10
    assert all(len(order) == 36 and sorted(order) == list(range(36)) for order in first)


def synthetic_public():
    return {
        "id": "synthetic:public",
        "task_id": "synthetic:arithmetic",
        "question": "Synthetic interface control, with no online reference answer.",
        "numeric_catalog": [],
        "segments": {},
    }


class FakeDecoder:
    def __init__(self, outputs):
        self.outputs = outputs
        self.histories = []

    def __call__(self, messages):
        self.histories.append(copy.deepcopy(messages))
        require_index = len(self.histories) - 1
        assert require_index < len(self.outputs), "first Final must stop generation"
        output = self.outputs[require_index]
        if isinstance(output, str):
            return {
                "content": output,
                "finish_reason": "stop",
                "generation_invoked": True,
                "synthetic_only": True,
            }
        return {**output, "synthetic_only": True}


def test_open_runtime_keeps_JSON_error_and_history_then_executes_original_tool_and_Final(tmp_path):
    bad = '{"tool":"calculate","arguments":{"expression":2+3}}'
    good = (
        '{"message":"I choose addition for this synthetic control.",'
        '"tool":"calculate","arguments":{"expression":"2+3"}}'
    )
    final = '{"final":{"value":5,"answer":"five"}}'
    decoder = FakeDecoder([bad, good, final])
    directory = tmp_path / "error_recovery"
    result = runtime.run_session(
        synthetic_public(), directory, decoder, {"synthetic_decoder": True}
    )
    assert result["terminal"] == "model_final"
    assert result["model_requests"] == result["decoder_requests"] == 3
    assert result["tool_calls"] == 1
    assert result["events"][0]["protocol_error"] is not None
    assert result["events"][0]["tool_call"] is None
    call = result["events"][1]["tool_call"]
    assert call["id"] == "tool:1"
    assert call["output"]["result"]["exact_value"] == "5"
    assert call["output"]["result"]["source_declarations_validated"] is False
    assert result["final"] == {"value": 5, "answer": "five"}
    assert (directory / "turns/000_assistant.raw").read_bytes() == bad.encode()
    assert (directory / "turns/001_assistant.raw").read_bytes() == good.encode()
    assert decoder.histories[0][0] == {"role": "system", "content": SYSTEM}
    assert decoder.histories[1][2] == {"role": "assistant", "content": bad}
    assert "interface_error" in json.loads(decoder.histories[1][3]["content"])
    assert decoder.histories[2][:4] == decoder.histories[1]
    assert decoder.histories[2][4] == {"role": "assistant", "content": good}
    assert json.loads(decoder.histories[2][5]["content"]) == {"tool_result": call["output"]}
    for index, history in enumerate(decoder.histories):
        saved = json.loads((directory / f"turns/{index:03d}_request.json").read_bytes())
        assert saved["messages"] == history
    assert all(event["oracle_feedback"] is False for event in result["events"])


def test_first_Final_has_no_numeric_correctness_or_calculation_gate(tmp_path):
    raw = '{"final":"unsupported answer", "tool":"calculate", "arguments":{"expression":"1+1"}}'
    decoder = FakeDecoder([raw])
    result = runtime.run_session(
        synthetic_public(), tmp_path / "first_final", decoder, {"synthetic_decoder": True}
    )
    assert result["terminal"] == "model_final"
    assert result["final"] == "unsupported answer"
    assert result["tool_calls"] == 0
    assert result["events"][0]["final"] is True
    assert len(decoder.histories) == 1


@pytest.mark.parametrize(
    "raw",
    [
        r'{"final":"\ud800"}',
        r'{"final":{"answer":["\udfff"]}}',
        r'{"\ud800":"message"}',
        r'{"tool":"calculate","arguments":{"expression":"\ud800"}}',
        r'{"message":{"nested":[{"\udfff":"value"}]}}',
    ],
)
def test_local_transport_rejects_lone_surrogates_without_rewriting_original_output(tmp_path, raw):
    assert raw.isascii()
    final = '{"final":"done"}'
    decoder = FakeDecoder([raw, final])
    directory = tmp_path / "invalid_unicode"
    result = runtime.run_session(
        synthetic_public(), directory, decoder, {"synthetic_decoder": True}
    )
    assert result["terminal"] == "model_final" and result["final"] == "done"
    assert result["model_requests"] == result["decoder_requests"] == 2
    assert result["tool_calls"] == 0
    assert result["events"][0]["final"] is False
    assert result["events"][0]["tool_call"] is None
    error = "response_strings_must_be_unicode_scalars"
    assert result["events"][0]["protocol_error"] == error
    assert (directory / "turns/000_assistant.raw").read_bytes() == raw.encode()
    assert decoder.histories[1][2] == {"role": "assistant", "content": raw}
    assert json.loads(decoder.histories[1][3]["content"]) == {"interface_error": error}
    saved_messages = json.loads((directory / "messages.json").read_bytes())
    assert saved_messages[2] == {"role": "assistant", "content": raw}
    assert json.loads((directory / "result.json").read_bytes()) == result


def test_local_transport_accepts_escaped_surrogate_pairs_in_values_and_keys(tmp_path):
    raw = r'{"final":{"answer":"\ud83d\ude00","\ud83d\ude00":["\ud83d\ude00"]}}'
    decoder = FakeDecoder([raw])
    directory = tmp_path / "valid_unicode"
    result = runtime.run_session(
        synthetic_public(), directory, decoder, {"synthetic_decoder": True}
    )
    scalar = "\U0001f600"
    assert result["terminal"] == "model_final"
    assert result["final"] == {"answer": scalar, scalar: [scalar]}
    assert result["events"][0]["final"] is True
    assert result["events"][0]["protocol_error"] is None
    assert result["model_requests"] == 1 and result["tool_calls"] == 0
    assert (directory / "turns/000_assistant.raw").read_bytes() == raw.encode()
    assert json.loads((directory / "result.json").read_bytes()) == result


@pytest.mark.parametrize(
    "invoked,finish,terminal",
    [
        (True, "stop", "unknown_empty_public_output"),
        (False, "context_token_limit", "context_token_limit"),
    ],
)
def test_empty_generated_output_differs_from_context_rejection_without_fabricated_raw(
    tmp_path, invoked, finish, terminal
):
    decoder = FakeDecoder([{"content": "", "finish_reason": finish, "generation_invoked": invoked}])
    directory = tmp_path / "empty_or_not_called"
    result = runtime.run_session(
        synthetic_public(), directory, decoder, {"synthetic_decoder": True}
    )
    assert result["terminal"] == terminal
    assert result["model_requests"] == int(invoked)
    assert result["decoder_requests"] == 1
    assert result["events"] == [] and result["final"] is None
    raw_path = directory / "turns/000_assistant.raw"
    assert raw_path.exists() is invoked
    if invoked:
        assert raw_path.read_bytes() == b""
    else:
        assert result["attempts"][0]["raw_response_sha256"] is None


class ContextTokenizer:
    def __init__(self, count):
        self.count = count

    def apply_chat_template(self, messages, **kwargs):
        assert kwargs == {"tokenize": False, "add_generation_prompt": True}
        return "synthetic rendered prompt"

    def __call__(self, rendered, **kwargs):
        assert kwargs["truncation"] is False and kwargs["add_special_tokens"] is False
        return {"input_ids": torch.zeros((1, self.count), dtype=torch.long)}


def test_local_decoder_reserves_output_before_any_model_or_device_invocation():
    class NeverGenerate:
        def generate(self, **kwargs):
            raise AssertionError("context rejection must precede generate")

    config = evaluation_config()
    count = config["maximum_sequence_length"] - config["max_new_tokens_per_response"] + 1
    decoder = inference.LocalDecoder(NeverGenerate(), ContextTokenizer(count))
    result = decoder(runtime.initial_messages(synthetic_public()))
    assert result["finish_reason"] == "context_token_limit"
    assert result["generation_invoked"] is False
    assert result["generated_token_ids"] == [] and result["content"] == ""
    assert result["prompt_truncated"] is False


def test_offline_guard_covers_pathlib_io_os_env_and_socket_entry_points(tmp_path):
    private = tmp_path / "evaluation_targets.json"
    private.write_text("synthetic private target, not a real evaluation target")
    env = tmp_path / ".env"
    env.write_text("synthetic marker; no credential")
    with guards.offline_guard([private]) as counts:
        for reader in (
            lambda: builtins.open(private, "rb"),
            lambda: io.open(private, "rb"),  # noqa: UP020 - exercise the separate guarded entry
            lambda: private.read_bytes(),
            lambda: os.open(private, os.O_RDONLY),
            lambda: env.read_text(),
        ):
            with pytest.raises(PermissionError, match="pq_offline.private_file"):
                reader()
        with socket.socket() as connection:
            with pytest.raises(RuntimeError, match="socket_connect"):
                connection.connect(("127.0.0.1", 9))
            with pytest.raises(RuntimeError, match="socket_connect_ex"):
                connection.connect_ex(("127.0.0.1", 9))
        with pytest.raises(RuntimeError, match="socket_create_connection"):
            socket.create_connection(("127.0.0.1", 9))
        assert counts == {
            "private_or_credential_file_read": 5,
            "socket_connect": 1,
            "socket_connect_ex": 1,
            "socket_create_connection": 1,
        }
        with pytest.raises(ValueError, match="pq_offline.no_forbidden_calls"):
            guards.report(counts, "isolated_negative_controls")


def test_offline_guard_allows_public_file_without_claiming_arbitrary_code_isolation(tmp_path):
    public = tmp_path / "public.json"
    public.write_bytes(encode({"synthetic_public": True}))
    with guards.offline_guard([]) as counts:
        assert json.loads(public.read_bytes()) == {"synthetic_public": True}
        report = guards.report(counts, "positive_public_read_control")
        assert report["all_zero"] is True
        assert "instrumented" in report["scope"]


def test_twelve_eval_pages_are_disjoint_and_source_precision_is_not_coarse_answer_text():
    chosen = panel.build(ROOT)
    assert len(chosen.tasks) == 12
    pages = {task["entry"]["filename"] for task in chosen.tasks.values()}
    assert len(pages) == 12 and pages.isdisjoint(panel.TRAINING_PAGES)
    assert sum(task["group"] == "transfer" for task in chosen.tasks.values()) == 6
    assert sum(task["group"] == "regression" for task in chosen.tasks.values()) == 6
    assert chosen.tasks["R3"]["relations"] == {}
    assert chosen.tasks["R5"]["exact_target"] == "3644/3"
    assert chosen.tasks["R5"]["entry"]["qa"]["answer"] == "1215"
    assert chosen.tasks["R6"]["exact_target"] == "77"
    assert chosen.tasks["T5"]["entry"]["filename"] == "AON/2007/page_188.pdf"
    for key, task in chosen.tasks.items():
        assert task["entry"]["qa"]["question"] == panel.SPECS[key]["question"]
        assert all(field in task["entry"] for field in ("pre_text", "post_text", "table"))
