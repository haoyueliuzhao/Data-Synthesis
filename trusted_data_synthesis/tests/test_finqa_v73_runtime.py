"""CPU tests of saved-state inference construction and causal measurement."""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import torch
from torch import nn

from trusted_synthesis.finance_research.contracts import RunConfig
from trusted_synthesis.experiments.finance_qa_vnext_pq_student import model as original

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from finqa_v73_inputs import _original_tool_specs
import finqa_v73_inputs as inputs
from trusted_synthesis.finance_research.v6_task import public_reasoning_tool_specs


@pytest.fixture(autouse=True)
def pure_test_tool_factory(monkeypatch):
    monkeypatch.setattr(inputs, "_tool_spec_factory", lambda: public_reasoning_tool_specs)


def module(name):
    path = Path(__file__).parents[1] / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name + "_runtime_test", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


runtime = module("finqa_v73_runtime")
measurement = module("finqa_v73_measurement")


def tensor_digest(values):
    h = hashlib.sha256()
    for name, tensor in sorted(values.items()):
        h.update(name.encode())
        h.update(str(tensor.dtype).encode())
        h.update(str(tuple(tensor.shape)).encode())
        h.update(tensor.detach().contiguous().view(torch.uint8).numpy().tobytes())
    return h.hexdigest()


def fixture_model_state():
    model = nn.Module()
    model.config = SimpleNamespace(num_hidden_layers=1, use_cache=True)
    model.model = nn.Module()
    layer = nn.Module()
    layer.self_attn = nn.Module()
    layer.self_attn.q_proj = nn.Linear(4, 4, bias=False, dtype=torch.bfloat16)
    layer.self_attn.v_proj = nn.Linear(4, 4, bias=False, dtype=torch.bfloat16)
    model.model.layers = nn.ModuleList([layer])
    model.register_buffer("saved_buffer", torch.zeros(2))
    model.requires_grad_(False)
    names = [f"model.layers.0.self_attn.{suffix}" for suffix in ("q_proj", "v_proj")]
    parameters = {name + suffix: torch.arange(32, dtype=torch.float32).reshape(shape) / 100
        for name in names for suffix, shape in ((".lora_A", (8, 4)), (".lora_B", (4, 8)))}
    shapes = {name: list(value.shape) for name, value in parameters.items()}
    count = sum(value.numel() for value in parameters.values())
    scope = original.record("trainable_adapter_scope", target_module_names=names,
        trainable_shapes=shapes, trainable_parameter_count=count, base_weights_frozen=True,
        input_output_embeddings_frozen=True,
        implementation="base(x)+(alpha/rank)*B(A(dropout(x))); A/B fp32, residual cast to base dtype")
    architecture = dict(implementation="repository.LowRankLinear", target_module_names=names,
        trainable_shapes=shapes, trainable_parameter_count=count, rank=8, scaling=2.0,
        dropout=0.05, base_dtype="bfloat16", adapter_dtype="float32", loader_scope_id=scope["id"])
    frozen = {name + ".base.weight": model.get_submodule(name).weight for name in names}
    state = dict(parameters=parameters, adapter_binding=architecture,
        frozen_base_digest=tensor_digest(frozen), buffers={"saved_buffer": torch.tensor([4.0, 7.0])})
    final = SimpleNamespace(torch=torch, parameter_digest=tensor_digest, _tree_digest=tensor_digest)
    return model, state, final


def test_exact_saved_adapters_use_original_forward_without_random_init(monkeypatch):
    model, state, final = fixture_model_state()
    before_rng = torch.get_rng_state().clone()
    monkeypatch.setattr(original.LowRankLinear, "__init__", lambda *a, **k: pytest.fail("random adapter init"))
    params, proof = runtime.install_saved_adapters(model, state, original, final)
    assert torch.equal(torch.get_rng_state(), before_rng)
    assert proof["random_LoRA_initialization_calls"] == proof["optimizer_objects_created"] == 0
    assert proof["all_parameters_require_grad_false"] and not model.training
    assert torch.equal(model.saved_buffer, state["buffers"]["saved_buffer"])
    layer = model.model.layers[0].self_attn.q_proj
    assert type(layer) is original.LowRankLinear
    x = torch.arange(4, dtype=torch.bfloat16).reshape(1, 4)
    expected = layer.base(x) + (torch.nn.functional.linear(
        torch.nn.functional.linear(x.float(), state["parameters"]["model.layers.0.self_attn.q_proj.lora_A"]),
        state["parameters"]["model.layers.0.self_attn.q_proj.lora_B"]) * 2).to(torch.bfloat16)
    assert torch.equal(layer(x), expected)
    assert tensor_digest(params) == tensor_digest(state["parameters"])


@pytest.mark.parametrize("kind", ["missing_parameter", "wrong_rank", "wrong_architecture", "wrong_base", "missing_buffer"])
def test_saved_state_mismatch_blocks_inference(kind):
    model, state, final = fixture_model_state()
    if kind == "missing_parameter":
        state["parameters"].pop(next(iter(state["parameters"])))
    elif kind == "wrong_rank":
        state["parameters"][next(iter(state["parameters"]))] = torch.zeros(7, 4)
    elif kind == "wrong_architecture":
        state["adapter_binding"]["scaling"] = 1.0
    elif kind == "wrong_base":
        state["frozen_base_digest"] = "wrong"
    else:
        state["buffers"] = {}
    with pytest.raises(ValueError):
        runtime.install_saved_adapters(model, state, original, final)


class CausalToy(nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = nn.Parameter(torch.arange(49, dtype=torch.float32).reshape(7, 7), requires_grad=False)
        self.calls = []
        self.eval()

    def forward(self, **kwargs):
        self.calls.append(kwargs)
        assert not torch.is_grad_enabled()
        ids = kwargs["input_ids"]
        return SimpleNamespace(logits=self.weight[ids[:, -kwargs["logits_to_keep"]:]])


def test_teacher_forcing_predicts_each_target_from_its_predecessor_including_EOS():
    model = CausalToy()
    prompt, target = [1, 2, 3], [4, 5, 6]
    observed = runtime.teacher_forced_logps(model, prompt, target, torch, measurement)
    expected = torch.log_softmax(model.weight[[3, 4, 5]], -1)[torch.arange(3), torch.tensor(target)].tolist()
    assert observed == expected
    assert len(model.calls) == 1
    assert model.calls[0]["input_ids"].tolist() == [[1, 2, 3, 4, 5]]
    assert model.calls[0]["logits_to_keep"] == 3
    assert model.calls[0]["use_cache"] is False
    assert all(not p.requires_grad for p in model.parameters())


@pytest.mark.parametrize("kind", ["train_mode", "grad_enabled", "empty_prompt", "empty_target", "too_many_targets", "context_overflow"])
def test_teacher_forcing_refuses_training_or_unregistered_sequence(kind):
    model = CausalToy()
    prompt, target = [1, 2], [3, 4]
    if kind == "train_mode": model.train()
    elif kind == "grad_enabled": model.weight.requires_grad_(True)
    elif kind == "empty_prompt": prompt = []
    elif kind == "empty_target": target = []
    elif kind == "too_many_targets": target = [1] * 2049
    else: prompt = [1] * 24576
    with pytest.raises(ValueError):
        runtime.teacher_forced_logps(model, prompt, target, torch, measurement)
    assert model.calls == []


class Tokenizer:
    def apply_chat_template(self, messages, *, tools, tokenize, add_generation_prompt):
        assert tokenize is False and add_generation_prompt is True
        return json.dumps([messages, tools], sort_keys=True)

    def __call__(self, rendered, **kwargs):
        assert kwargs == dict(add_special_tokens=False, truncation=False, padding=False)
        return dict(input_ids=[ord(c) for c in rendered])


def context_fixture():
    request = dict(messages=[dict(role="user", content="original public request")], tools=_original_tool_specs(),
        config=RunConfig(role="development", tier="EVAL_NATIVE", temperature=0.0,
            top_p=1.0, top_k=0, local_tool_protocol="qwen2.5-native-tool-call-v1").model_dump(mode="json"))
    ids = [ord(c) for c in json.dumps([request["messages"], request["tools"]], sort_keys=True)]
    return dict(context_id="frozen_context", request=request, prompt_input_ids=ids)


def test_generation_context_keeps_original_messages_and_actual_tokens():
    value = context_fixture()
    before = copy.deepcopy(value)
    result = runtime.validate_generation_context(value, Tokenizer(), RunConfig)
    assert result.max_new_tokens == 2048 and value == before


@pytest.mark.parametrize("kind", ["prompt_changed", "temperature_changed", "token_limit_changed"])
def test_generation_rejects_rewritten_input_or_decoding(kind):
    value = context_fixture()
    if kind == "prompt_changed": value["request"]["messages"][0]["content"] += " please submit"
    elif kind == "temperature_changed": value["request"]["config"]["temperature"] = 1.0
    else: value["request"]["config"]["max_new_tokens"] = 1024
    with pytest.raises(ValueError):
        runtime.validate_generation_context(value, Tokenizer(), RunConfig)


class Guard:
    def __init__(self):
        self.labels = []
    def check(self, label, **kwargs):
        self.labels.append(label)


class Provider:
    actual_model_calls = 0
    def __init__(self, context, error=None):
        self.context, self.calls, self.error = context, [], error
    async def chat(self, messages, tools, config):
        self.calls.append((messages, tools, config))
        self.actual_model_calls += 1
        if self.error: raise self.error
        payload = dict(receipt=dict(prompt_input_ids=self.context["prompt_input_ids"], raw_generated_token_ids=[4, 5]))
        return SimpleNamespace(model_dump=lambda **kwargs: payload)


def predictor_fixture(context, error=None):
    value = runtime.Predictor.__new__(runtime.Predictor)
    value.closed, value.model_label, value._counts = False, "P", Counter()
    value.tokenizer, value.guard = Tokenizer(), Guard()
    value.final = SimpleNamespace(RunConfig=RunConfig)
    value.provider = Provider(context, error)
    return value


def test_generate_one_turn_never_executes_tool_or_follows_up():
    context = context_fixture()
    predictor = predictor_fixture(context)
    result = predictor.generate(context)
    assert len(predictor.provider.calls) == result["actual_model_generate_calls"] == 1
    assert result["tools_executed"] == result["next_assistant_turns"] == result["native_scoring_calls"] == 0
    # Return the receipt to the caller before any potentially failing after-call gate.
    assert predictor.guard.labels == ["before_single_probe_response"]


def test_unknown_generation_failure_is_not_retried_by_runtime():
    context = context_fixture()
    predictor = predictor_fixture(context, RuntimeError("unknown actual return"))
    with pytest.raises(RuntimeError, match="unknown actual return"):
        predictor.generate(context)
    assert len(predictor.provider.calls) == 1


def test_actual_provider_call_receives_original_tool_order_after_JSON_reload():
    class OrderSensitiveTokenizer(Tokenizer):
        def apply_chat_template(self, messages, *, tools, tokenize, add_generation_prompt):
            return json.dumps(messages, sort_keys=True) + json.dumps(tools, sort_keys=False)
    tokenizer = OrderSensitiveTokenizer()
    original_context = context_fixture()
    request = original_context["request"]
    text = tokenizer.apply_chat_template(request["messages"], tools=request["tools"],
        tokenize=False, add_generation_prompt=True)
    original_context["prompt_input_ids"] = [ord(char) for char in text]
    context = json.loads(json.dumps(original_context, sort_keys=True))
    assert list(context["request"]["tools"][0]) == ["function", "type"]
    predictor = predictor_fixture(context)
    predictor.tokenizer = tokenizer
    result = predictor.generate(context)
    tools_received = predictor.provider.calls[0][1]
    assert list(tools_received[0]) == ["type", "function"]
    assert tools_received == context["request"]["tools"]
    assert list(context["request"]["tools"][0]) == ["function", "type"]
    assert result["actual_model_generate_calls"] == 1


def test_probability_channel_has_no_generate_and_exposes_flat_group_summaries():
    model = CausalToy()
    value = runtime.Predictor.__new__(runtime.Predictor)
    value.closed, value.model_label, value._counts = False, "L", Counter()
    value.guard, value.model = Guard(), model
    value.provider = SimpleNamespace(_storage_versions=lambda: {"weight": model.weight._version})
    value.final, value.measurement = SimpleNamespace(torch=torch), measurement
    groups = {name: [] for name in measurement.TOKEN_GROUPS}
    groups["action_structure"], groups["actual_terminal_EOS"] = [0], [1]
    grouping = dict(id="frozen_groups", policy_id="policy", response_token_count=2, position_groups=groups)
    result = value.measure(dict(target_id="saved_target", prompt_input_ids=[1, 2],
        raw_generated_token_ids=[3, 4], grouping=grouping))
    assert len(model.calls) == result["probability_sequences"] == 1
    assert result["newly_generated_responses"] == result["backward_calls"] == result["optimizer_updates"] == 0
    assert result["groups"]["action_structure"]["token_count"] == 1
    assert result["groups"]["pre_action_text"]["mean_nll"] is None
    assert result["groups"]["actual_terminal_EOS"]["token_count"] == 1
