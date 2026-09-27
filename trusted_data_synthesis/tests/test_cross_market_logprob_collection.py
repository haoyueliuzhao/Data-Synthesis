"""CPU-only equivalence and allocation controls; no model or API execution."""

import ast
import inspect
import textwrap
import weakref
from contextlib import nullcontext
from types import FunctionType, SimpleNamespace

import cross_market_logprob_collection_20260927 as m
import pytest
import torch


def reference(output, scores):
    return [
        float(torch.log_softmax(score[0].float(), -1)[token])
        for token, score in zip(output, scores, strict=True)
    ]


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16, torch.float16, torch.float64])
def test_exact_python_float_values_and_unchanged_inputs_rng(dtype):
    scores = tuple(
        torch.tensor([[value, -value, 0.0, 17.0, -91.0]], dtype=dtype)
        for value in (0.125, 0.5, 10.0, -99.0)
    )
    output = [4, 0, 3, 1]
    before = tuple(score.clone() for score in scores)
    rng = torch.random.get_rng_state().clone()
    expected = reference(output, scores)
    actual = m.collected_logprobs(output, scores)
    assert actual == expected
    assert all(type(value) is float for value in actual)
    assert all(torch.equal(left, right) for left, right in zip(scores, before, strict=True))
    assert torch.equal(torch.random.get_rng_state(), rng)


@pytest.mark.parametrize("outputs,rows", [([0], 0), ([], 1), ([0, 1], 1), ([0], 2)])
def test_strict_zip_length_rejection(outputs, rows):
    scores = tuple(torch.tensor([[0.0, 1.0]]) for _ in range(rows))
    with pytest.raises(ValueError, match="zip"):
        m.collected_logprobs(outputs, scores)
    with pytest.raises(ValueError, match="zip"):
        reference(outputs, scores)


def test_empty_collection_and_single_pass_iterables():
    assert m.collected_logprobs(iter(()), iter(())) == []
    scores = [torch.tensor([[0.0, 1.0, 2.0]]) for _ in range(3)]
    assert m.collected_logprobs(iter([0, 1, 2]), iter(scores)) == reference([0, 1, 2], scores)


def test_retains_only_cloned_scalars_and_uses_one_host_transfer(monkeypatch):
    scores = tuple(torch.arange(113, dtype=torch.bfloat16).reshape(1, -1) for _ in range(7))
    output = [0, 3, 17, 52, 87, 110, 112]
    expected = reference(output, scores)
    original_softmax, original_stack = torch.log_softmax, torch.stack
    original_cpu, original_tolist = torch.Tensor.cpu, torch.Tensor.tolist
    vocabulary_outputs, softmax_shapes, stacks, host_transfers, conversions = [], [], [], [], []

    def softmax(values, dim):
        # Each previous full-vocabulary temporary is already released.
        assert all(value() is None for value in vocabulary_outputs)
        assert values.dtype == torch.float32
        assert values.shape == (113,)
        assert dim == -1
        softmax_shapes.append(tuple(values.shape))
        result = original_softmax(values, dim)
        vocabulary_outputs.append(weakref.ref(result))
        return result

    def stack(values):
        assert all(value() is None for value in vocabulary_outputs)
        assert len(values) == len(output)
        for value in values:
            assert value.shape == ()
            assert value._base is None
            assert value.untyped_storage().nbytes() == value.element_size()
        stacks.append(len(values))
        return original_stack(values)

    def cpu(value, *args, **kwargs):
        host_transfers.append(tuple(value.shape))
        return original_cpu(value, *args, **kwargs)

    def tolist(value):
        conversions.append(tuple(value.shape))
        return original_tolist(value)

    monkeypatch.setattr(torch, "log_softmax", softmax)
    monkeypatch.setattr(torch, "stack", stack)
    monkeypatch.setattr(torch.Tensor, "cpu", cpu)
    monkeypatch.setattr(torch.Tensor, "tolist", tolist)
    assert m.collected_logprobs(output, scores) == expected
    assert softmax_shapes == [(113,)] * 7
    assert stacks == [7]
    assert host_transfers == [(7,)]
    assert conversions == [(7,)]


@pytest.mark.parametrize("copies", [0, 2])
def test_ast_replacement_rejects_missing_or_multiple_matches(copies):
    tree = ast.parse("\n".join([m._ORIGINAL_ASSIGNMENT] * copies))
    with pytest.raises(ValueError, match="exactly_one_original_assignment"):
        m._replace_collection(tree)


def test_ast_replacement_rejects_existing_helper_name():
    tree = ast.parse(m._ORIGINAL_ASSIGNMENT + "\n" + m._HELPER_NAME + " = None")
    with pytest.raises(ValueError, match="no_existing_helper_name"):
        m._replace_collection(tree)


def test_factory_preserves_original_class_globals_and_all_other_ast():
    import fixed_kernel_anchored_feedback_20260916 as frozen

    original = frozen.Decoder.__call__
    original_globals = dict(original.__globals__)
    original_tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    optimized = m.optimized_decoder_class()
    assert issubclass(optimized, frozen.Decoder)
    assert optimized.__init__ is frozen.Decoder.__init__
    assert frozen.Decoder.__call__ is original
    assert original.__globals__ == original_globals
    assert optimized.__call__.__globals__ is not original.__globals__
    assert optimized.__call__.__globals__[m._HELPER_NAME] is m.collected_logprobs
    assert set(optimized.__call__.__globals__) - set(original_globals) == {
        m._HELPER_NAME,
        "__call__",
    }
    for key, value in original_globals.items():
        assert optimized.__call__.__globals__[key] is value

    changed = m._replace_collection(original_tree)
    expected_assignment = ast.parse(m._REPLACEMENT_ASSIGNMENT).body[0]
    assignments = [node for node in ast.walk(changed) if isinstance(node, ast.Assign)]
    matches = [
        node for node in assignments if m._ast_text(node) == m._ast_text(expected_assignment)
    ]
    assert len(matches) == 1
    matches[0].value = ast.parse(textwrap.dedent(m._ORIGINAL_ASSIGNMENT)).body[0].value
    assert m._ast_text(changed) == m._ast_text(original_tree)

    binding = optimized.logprob_collection_binding
    assert binding["source_sha256"] == m.SOURCE_SHA256
    assert binding["changed_assignment_count"] == 1
    assert binding["all_other_AST_unchanged"] is True
    assert binding["original_call_ast_sha256"] != binding["optimized_call_ast_sha256"]


def test_factory_rejects_unregistered_source_digest(monkeypatch):
    monkeypatch.setattr(m, "SOURCE_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="exact_frozen_source_bytes"):
        m.optimized_decoder_class()


def test_mock_callback_preserves_model_call_receipt_and_rng():
    import fixed_kernel_anchored_feedback_20260916 as frozen

    optimized_class = m.optimized_decoder_class()
    scores = tuple(torch.tensor([[0.1, -0.3, 0.9, 1.7]]) for _ in range(3))
    generation_calls, collection_calls = [], []
    torch_proxy = SimpleNamespace(
        tensor=lambda value, **kwargs: torch.tensor(value, dtype=kwargs["dtype"]),
        long=torch.long,
        ones_like=torch.ones_like,
        no_grad=torch.no_grad,
        log_softmax=torch.log_softmax,
    )

    def collect(output, actual_scores):
        collection_calls.append((output, actual_scores))
        return m.collected_logprobs(output, actual_scores)

    namespace = {
        **frozen.Decoder.__call__.__globals__,
        "torch": torch_proxy,
        "sdpa_kernel": lambda *_: nullcontext(),
        m._HELPER_NAME: collect,
    }
    functions = [
        FunctionType(callback.__code__, dict(namespace))
        for callback in (frozen.Decoder.__call__, optimized_class.__call__)
    ]

    class Tokenizer:
        def apply_chat_template(self, *args, **kwargs):
            return "synthetic public context"

        def __call__(self, *args, **kwargs):
            return {"input_ids": [0, 1]}

        def decode(self, *args, **kwargs):
            return "synthetic response"

    def generate(**kwargs):
        generation_calls.append(kwargs)
        return SimpleNamespace(sequences=torch.tensor([[0, 1, 2, 1, 3]]), scores=scores)

    config = object()
    messages = [
        {"role": "system", "content": frozen.views.SYSTEM + "\nRequested guidance: neutral"}
    ]
    context = dict(
        max_responses=32,
        max_tools=32,
        history_must_not_be_truncated=True,
        identity={"task_id": "synthetic"},
        response_index=0,
    )
    rng = torch.random.get_rng_state().clone()
    results = []
    for callback in functions:
        decoder = SimpleNamespace(
            fatal=None,
            stochastic=True,
            calls=0,
            generated_tokens=0,
            model=SimpleNamespace(generate=generate),
            tokenizer=Tokenizer(),
            point={"id": "synthetic-point", "parameter_digest": "synthetic-digest"},
            config=config,
            eos=[3],
        )
        results.append(callback(decoder, messages, context))
        assert decoder.calls == 1 and decoder.generated_tokens == 3
    assert results[0] == results[1]
    assert len(generation_calls) == 2
    for key in generation_calls[0]:
        left, right = generation_calls[0][key], generation_calls[1][key]
        assert torch.equal(left, right) if isinstance(left, torch.Tensor) else left is right
    assert collection_calls == [([2, 1, 3], scores)]
    assert torch.equal(torch.random.get_rng_state(), rng)
