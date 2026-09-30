"""Tiny CPU equivalence controls; not a real Qwen7B/CUDA performance claim."""

import contextlib
import functools
import importlib
import sys
from pathlib import Path

import pytest
import torch
from transformers import Qwen2Config, Qwen2ForCausalLM

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
opt = importlib.import_module("finqa_v19_optimized_replay")


def tiny():
    torch.manual_seed(31)
    config = Qwen2Config(
        vocab_size=23,
        hidden_size=8,
        intermediate_size=16,
        num_hidden_layers=2,
        num_attention_heads=2,
        num_key_value_heads=1,
        attention_dropout=0.0,
        max_position_embeddings=32768,
    )
    config._attn_implementation = "sdpa"
    model = Qwen2ForCausalLM(config).float().requires_grad_(False)
    model.model.layers[0].self_attn.q_proj.weight.requires_grad_(True)
    theta = {
        n: (v.detach().clone() + 0.01).requires_grad_(True)
        for n, v in model.named_parameters()
        if v.requires_grad
    }
    return model, theta


def cpu_baseline(*, native_contiguous=False):
    store = functools.partial(opt.canonical.CanonicalSavedTensorStore, pin_memory=native_contiguous)
    prefill = contextlib.contextmanager(
        opt.bind_dependencies(
            opt.legacy.pure_prefill_checkpoints.__wrapped__, CanonicalSavedTensorStore=store
        )
    )

    class Operation(opt.legacy.SegmentedOperation):
        pass

    Operation.forward = opt.bind_dependencies(
        opt.legacy.SegmentedOperation.forward,
        CanonicalSavedTensorStore=store,
        pure_prefill_checkpoints=prefill,
    )
    return opt.bind_dependencies(opt.legacy.segmented_logp, SegmentedOperation=Operation)


@pytest.mark.parametrize("targets", [[1], [1, 4, 6, 8, 10, 12, 13, 14, 15], list(range(1, 18))])
def test_same_fixed8_logp_and_full_gradient_bitwise_on_tiny_cpu(targets):
    model, theta = tiny()
    prompt = [2, 3, 5, 7]
    real = {n: v.detach().clone() for n, v in model.named_parameters()}
    rng = torch.get_rng_state().clone()
    baseline = cpu_baseline()
    values, gradient, _ = baseline(model, theta, prompt, targets, block_size=8, offload=True)
    session = opt.ReplaySession(model, theta, profile_id="synthetic-profile", cpu_test=True)
    actual, derivative, report = session(model, theta, prompt, targets, expected=values.tolist())
    assert torch.equal(actual, values)
    assert all(torch.equal(gradient[n], derivative[n]) for n in gradient)
    assert opt.parameter_digest(gradient) == opt.parameter_digest(derivative)
    # A second response reuses frozen layouts, not any response activations.
    again, again_gradient, again_report = session(
        model, theta, prompt, targets, expected=values.tolist()
    )
    assert torch.equal(again, values)
    assert all(torch.equal(gradient[n], again_gradient[n]) for n in gradient)
    assert again_report["cached_frozen_bank_responses"] == 2
    assert report["single_complete_CPU_KV_bytes"] == 0
    assert report["complete_prefix_adjoint_included"]
    assert report["per_block_process_monitor_threads"] == 0
    assert session.operation.forward.__code__ is opt.legacy.SegmentedOperation.forward.__code__
    assert torch.equal(torch.get_rng_state(), rng)
    assert all(torch.equal(v, real[n]) for n, v in model.named_parameters())
    assert all("forward" not in layer.__dict__ for layer in model.model.layers)
    session.close()


def test_no_monitor_thread_and_no_persistent_module_patch(monkeypatch):
    model, theta = tiny()
    original_forward = opt.legacy.SegmentedOperation.forward
    original_attention = opt.F.scaled_dot_product_attention
    monkeypatch.setattr(
        opt.threading, "Thread", lambda *a, **kw: pytest.fail("no per-block thread")
    )
    session = opt.ReplaySession(model, theta, profile_id="test", cpu_test=True)
    session(model, theta, [2, 3], [4, 5, 6], expected=None)
    assert opt.legacy.SegmentedOperation.forward is original_forward
    assert opt.F.scaled_dot_product_attention is original_attention
    session.close()


def test_session_rejects_parameter_version_and_block_size_changes():
    model, theta = tiny()
    session = opt.ReplaySession(model, theta, profile_id="test", cpu_test=True)
    with pytest.raises(ValueError, match="eight-token"):
        session(model, theta, [1], [2], expected=None, block_size=16)
    with torch.no_grad():
        next(iter(theta.values())).add_(1)
    with pytest.raises(ValueError, match="version"):
        session(model, theta, [1], [2], expected=None)


def test_frozen_owner_version_is_not_silently_rebased():
    model, theta = tiny()
    session = opt.ReplaySession(model, theta, profile_id="test", cpu_test=True)
    frozen = next(v for v in model.parameters() if not v.requires_grad)
    with torch.no_grad():
        frozen.add_(1)
    with pytest.raises(ValueError, match="owner changed"):
        session(model, theta, [1], [2], expected=None)


def test_production_cannot_claim_cpu_as_cuda_acceptance():
    model, theta = tiny()
    with pytest.raises(ValueError, match="production replay requires CUDA"):
        opt.ReplaySession(model, theta, profile_id="production")


def test_function_binding_rejects_unknown_override():
    with pytest.raises(ValueError, match="unknown frozen dependency"):
        opt.bind_dependencies(opt.legacy.segmented_logp, arbitrary_new_math=lambda: None)


def test_cpu_math_attention_matches_native_contiguous_backward(monkeypatch):
    # Force native pin_memory=True's contiguous packing without any CUDA or
    # pinned allocation. This is a CPU layout control, not CUDA acceptance.
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    model, theta = tiny()
    prompt, targets = [2, 3, 5, 7], list(range(1, 18))
    values, gradient, _ = cpu_baseline(native_contiguous=True)(
        model, theta, prompt, targets, block_size=8, offload=True
    )
    session = opt.ReplaySession(
        model,
        theta,
        profile_id="layout-test",
        cpu_test=True,
        resident_kv_budget_bytes=1024,
        cpu_resident_test=True,
    )
    actual, derivative, report = session(model, theta, prompt, targets, expected=values.tolist())
    assert torch.equal(actual.view(torch.uint8), values.view(torch.uint8))
    assert opt.parameter_digest(gradient) == opt.parameter_digest(derivative)
    # CPU math SDPA saves transformed intermediates, not the CUDA flash kernel's
    # original K/V storages. This test does NOT claim to exercise GPU KV residency.
    assert report["peak_resident_saved_KV_bytes"] <= 1024
    assert session.bank.resident_live == 0
    session.close()


def test_registered_saved_tensor_residency_preserves_backward_bytes(monkeypatch):
    import weakref

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    torch.manual_seed(17)
    x = torch.randn(2, 3, requires_grad=True)
    key = torch.randn(3, 2, requires_grad=True)
    with torch.autograd.graph.save_on_cpu(pin_memory=True):
        expected_loss = (x @ key).square().sum()
    expected = torch.autograd.grad(expected_loss, (x, key))
    a, b = x.detach().clone().requires_grad_(True), key.detach().clone().requires_grad_(True)
    model = torch.nn.Linear(2, 2, bias=False).requires_grad_(False)
    bank = opt.ReplayBank(model, resident_limit=128, cpu_resident_test=True)
    store = opt.BoundaryAuditedStore(model, bank=bank)
    storages = [value.untyped_storage() for value in (a, b)]
    for storage in storages:
        store.KV["cpu", storage._cdata] = weakref.ref(storage)
    with store.context():
        actual_loss = (a @ b).square().sum()
        actual = torch.autograd.grad(actual_loss, (a, b))
    assert opt.parameter_digest(dict(zip(("a", "b"), actual, strict=True))) == opt.parameter_digest(
        dict(zip(("a", "b"), expected, strict=True))
    )
    assert 0 < bank.resident_peak <= 128 and bank.resident_live == 0
    bank.validate()


def test_saved_kv_budget_and_private_copy_no_alias_or_dedup(monkeypatch):
    import weakref

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    model, _ = tiny()
    bank = opt.ReplayBank(model, resident_limit=32, cpu_resident_test=True)
    store = opt.BoundaryAuditedStore(model, bank=bank)
    tensor = torch.arange(6, dtype=torch.float32).reshape(2, 3)
    storage = tensor.untyped_storage()
    store.KV[str(tensor.device), storage._cdata] = weakref.ref(storage)
    first = store.pack(tensor)
    second = store.pack(tensor)
    assert first.device_resident_KV
    assert not getattr(second, "device_resident_KV", False)  # Bounded CPU spill.
    assert first.value.is_contiguous() and first.value.data_ptr() != tensor.data_ptr()
    assert torch.equal(store.unpack(first), tensor)
    assert bank.resident_live == 24
    first.value.add_(1)
    with pytest.raises(ValueError, match="mutated"):
        store.unpack(first)
    del first, second
    assert bank.resident_live == bank.live_host == bank.live_pinned == 0
