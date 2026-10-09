"""CPU layout/lifetime/bitwise controls only; never a CUDA speedup claim."""

import gc
import hashlib
import importlib
import sys
import weakref
from pathlib import Path

import pytest
import torch
from test_finance_v19_optimized_replay import cpu_baseline, tiny

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
v33 = importlib.import_module("finqa_v33_activation_residency")


@pytest.fixture(autouse=True)
def cpu_native_contiguous(monkeypatch):
    # Emulate save_on_cpu(pin_memory=True)'s independent contiguous CPU buffer
    # without querying devices or allocating page-locked memory in these tests.
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)


def store_fixture(*, activation_limit=1024, kv_limit=128):
    model = torch.nn.Linear(6, 4, bias=False).requires_grad_(False)
    bank = v33.ActivationReplayBank(
        model,
        activation_resident_limit=activation_limit,
        resident_limit=kv_limit,
        cpu_resident_test=True,
    )
    return model, bank, v33.ActivationSavedTensorStore(model, bank=bank)


def byte_values(tensor):
    return tensor.contiguous().reshape(-1).view(torch.uint8)


@pytest.mark.parametrize(
    "dtype", [torch.float32, torch.float64, torch.bfloat16, torch.float16, torch.int64, torch.bool]
)
@pytest.mark.parametrize("view", ["contiguous", "transpose", "offset", "strided", "expand"])
def test_nonkv_layout_dtype_and_independent_per_save_match_native(dtype, view):
    _, bank, store = store_fixture(activation_limit=4096)
    tensor = torch.arange(24).to(dtype).reshape(4, 6)
    if view == "transpose":
        tensor = tensor.T
    elif view == "offset":
        tensor = tensor[1:3, 1:5]
    elif view == "strided":
        tensor = tensor[::2, ::2]
    elif view == "expand":
        tensor = tensor[:1, :].expand(4, 6)
    native = torch.autograd.graph.save_on_cpu(pin_memory=True)
    expected = native.unpack_hook(native.pack_hook(tensor))
    first, second = store.pack(tensor), store.pack(tensor)
    for packed in (first, second):
        actual = store.unpack(packed)
        assert packed.device_resident_non_KV
        assert actual.dtype == expected.dtype and actual.shape == expected.shape
        assert actual.stride() == expected.stride() and actual.is_contiguous()
        assert torch.equal(byte_values(actual), byte_values(expected))
        assert actual.untyped_storage()._cdata != tensor.untyped_storage()._cdata
    assert first.value.untyped_storage()._cdata != second.value.untyped_storage()._cdata
    amount = tensor.numel() * tensor.element_size()
    assert bank.activation_live_bytes == bank.activation_peak_bytes == 2 * amount
    assert bank.activation_live_count == bank.activation_total_count == 2
    del first, second, packed
    assert bank.activation_live_count == bank.activation_live_bytes == 0
    assert bank.activation_released_count == 2
    assert bank.activation_released_bytes == 2 * amount
    bank.validate()


@pytest.mark.parametrize("shape", [(), (0,), (2, 0, 3)])
def test_scalar_and_empty_saves_count_lifetimes_even_when_zero_bytes(shape):
    _, bank, store = store_fixture()
    tensor = torch.empty(shape)
    packed = store.pack(tensor)
    assert store.unpack(packed).shape == shape
    assert bank.activation_live_count == 1
    with pytest.raises(ValueError, match="retains non-KV"):
        bank.validate()
    del packed
    bank.validate()


def test_source_mutation_does_not_pollute_copy_or_retain_source_view():
    _, bank, store = store_fixture()
    owner = torch.arange(24, dtype=torch.float32)
    tensor = owner.reshape(4, 6).T
    source_ref, storage_ref = weakref.ref(tensor), weakref.ref(tensor.untyped_storage())
    expected = tensor.contiguous().clone()
    packed = store.pack(tensor)
    assert packed.original_source_signature[-1] == tensor._version
    owner.add_(100)
    assert torch.equal(store.unpack(packed), expected)
    del tensor, owner
    gc.collect()
    assert source_ref() is None and storage_ref() is None
    del packed
    bank.validate()


def test_saved_copy_mutation_is_rejected_at_unpack():
    _, bank, store = store_fixture()
    packed = store.pack(torch.arange(6.0).reshape(2, 3).T)
    packed.value.add_(1)
    with pytest.raises(ValueError, match="non-KV device copy was mutated"):
        store.unpack(packed)
    del packed
    bank.validate()


def test_source_version_change_during_pack_is_rejected(monkeypatch):
    _, bank, store = store_fixture()
    tensor = torch.arange(6.0)
    original = torch.Tensor.copy_

    def mutate_source(destination, source, *args, **kwargs):
        result = original(destination, source, *args, **kwargs)
        source.add_(1)
        return result

    monkeypatch.setattr(torch.Tensor, "copy_", mutate_source)
    with pytest.raises(ValueError, match="source changed during"):
        store.pack(tensor)
    assert bank.activation_total_count == bank.activation_live_count == 0
    bank.validate()


def test_budget_spill_is_original_native_copy_and_released_budget_is_reusable():
    _, bank, store = store_fixture(activation_limit=24)
    tensor = torch.arange(6.0).reshape(2, 3).T
    first, spilled = store.pack(tensor), store.pack(tensor)
    assert first.device_resident_non_KV and not getattr(spilled, "device_resident_non_KV", False)
    assert bank.activation_live_bytes == 24 and bank.live_host == 24
    assert store.unpack(spilled).is_contiguous()
    expected = tensor.clone()
    tensor.add_(1)
    assert torch.equal(store.unpack(spilled), expected)
    del first
    third = store.pack(tensor)
    assert third.device_resident_non_KV
    assert bank.activation_total_bytes == 48 and bank.activation_peak_bytes == 24
    assert bank.activation_spill_total_count == 1
    assert bank.activation_spill_host_allocation_bytes == 24
    del spilled, third
    assert bank.live_host == bank.live_pinned == 0
    bank.validate()


def test_frozen_owner_and_identified_kv_paths_remain_original_and_separate():
    model, bank, store = store_fixture(activation_limit=0, kv_limit=24)
    owner = model.weight.T
    frozen = store.pack(owner)
    again = store.pack(owner)
    assert frozen.frozen and frozen.value is again.value
    assert not getattr(frozen, "device_resident_non_KV", False)
    tensor = torch.arange(6.0).reshape(2, 3).T
    storage = tensor.untyped_storage()
    store.KV["cpu", storage._cdata] = weakref.ref(storage)
    kv, spilled_kv = store.pack(tensor), store.pack(tensor)
    assert kv.device_resident_KV and not getattr(kv, "device_resident_non_KV", False)
    assert not getattr(spilled_kv, "device_resident_KV", False)
    assert bank.resident_live == 24
    assert bank.activation_total_count == bank.activation_spill_total_count == 0
    del frozen, again, kv, spilled_kv
    bank.validate()
    model.weight.add_(1)
    with pytest.raises(ValueError, match="bound_frozen_storage_and_version"):
        store.pack(owner)


def test_stale_kv_storage_registration_cannot_capture_unrelated_activation():
    _, bank, store = store_fixture()
    tensor = torch.arange(6.0)
    other_storage = torch.arange(1.0).untyped_storage()
    store.KV["cpu", tensor.untyped_storage()._cdata] = weakref.ref(other_storage)
    packed = store.pack(tensor)
    assert packed.device_resident_non_KV and bank.resident_total == 0
    del packed
    bank.validate()


@pytest.mark.parametrize("targets", [[1], [1, 4, 6, 8, 10, 12, 13, 14, 15], list(range(1, 18))])
@pytest.mark.parametrize("activation_limit", [64, 1024 * 1024])
def test_complete_tiny_gradients_bitwise_and_response_lifecycle(targets, activation_limit):
    model, theta = tiny()
    prompt = [2, 3, 5, 7]
    baseline = cpu_baseline(native_contiguous=True)
    expected, expected_gradient, _ = baseline(
        model, theta, prompt, targets, block_size=8, offload=True
    )
    rng = torch.get_rng_state().clone()
    snapshots = {name: value.detach().clone() for name, value in model.named_parameters()}
    frozen_forward = v33.optimized.legacy.SegmentedOperation.forward
    frozen_prefill = v33.optimized.legacy.pure_prefill_checkpoints
    monitor = []
    session = v33.R3Session(
        model,
        theta,
        profile_id="v33-cpu-only",
        cpu_test=True,
        cpu_resident_test=True,
        activation_resident_budget_bytes=activation_limit,
        response_monitor=monitor.append,
    )
    bank = session.bank
    for response in range(2):
        actual, gradient, report = session(
            model, theta, prompt, targets, expected=expected.tolist()
        )
        assert torch.equal(byte_values(actual), byte_values(expected))
        assert v33.optimized.parameter_digest(gradient) == v33.optimized.parameter_digest(
            expected_gradient
        )
        assert all(gradient[name].dtype == torch.float32 for name in gradient)
        assert session.bank is bank and report["cached_frozen_bank_responses"] == response + 1
        assert report["replay_variant"] == "R3"
        assert report["replay_backend_version"] == v33.BACKEND_VERSION
        assert report["complete_prefix_adjoint_included"]
        assert report["live_resident_non_KV_count"] == report["live_resident_non_KV_bytes"] == 0
        assert 0 < report["peak_resident_non_KV_bytes"] <= activation_limit
        assert report["cumulative_non_KV_device_copy_count"] > 0
        assert (
            report["released_non_KV_device_copy_count"]
            == report["cumulative_non_KV_device_copy_count"]
        )
        if activation_limit == 64:
            assert report["cumulative_non_KV_budget_spill_count"] > 0
        bank.validate()
    assert session.operation.forward.__code__ is frozen_forward.__code__
    assert v33.optimized.legacy.SegmentedOperation.forward is frozen_forward
    assert v33.optimized.legacy.pure_prefill_checkpoints is frozen_prefill
    assert all(row["variant"] == "R3" for row in monitor)
    assert torch.equal(torch.get_rng_state(), rng)
    assert all(torch.equal(value, snapshots[name]) for name, value in model.named_parameters())
    session.close()


def test_fixed_budget_dtype_parameter_versions_and_fixed8_controls():
    model, theta = tiny()
    with pytest.raises(ValueError, match="single registered 16 GiB"):
        v33.R3Session(model, theta, profile_id="invalid", activation_resident_budget_bytes=1)
    with pytest.raises(ValueError, match="only a test"):
        v33.R3Session(model, theta, profile_id="invalid", cpu_resident_test=True)
    with pytest.raises(ValueError, match="FP32"):
        v33.R3Session(
            model,
            {name: value.double() for name, value in theta.items()},
            profile_id="invalid",
            cpu_test=True,
        )
    session = v33.R3Session(model, theta, profile_id="cpu", cpu_test=True, cpu_resident_test=True)
    with pytest.raises(ValueError, match="eight-token"):
        session(model, theta, [1], [2], expected=None, block_size=16)
    with torch.no_grad():
        next(iter(theta.values())).add_(1)
    with pytest.raises(ValueError, match="version"):
        session(model, theta, [1], [2], expected=None)
    session.close()


def test_device_allocation_error_propagates_without_native_retry(monkeypatch):
    _, bank, store = store_fixture()
    tensor = torch.arange(4.0)

    def allocation_error(*_args, **_kwargs):
        raise torch.OutOfMemoryError("synthetic test only")

    monkeypatch.setattr(torch, "empty", allocation_error)
    monkeypatch.setattr(
        store.native, "pack_hook", lambda _: pytest.fail("OOM may not retry on CPU")
    )
    with pytest.raises(torch.OutOfMemoryError, match="synthetic"):
        store.pack(tensor)
    assert bank.activation_total_count == bank.activation_spill_total_count == 0
    bank.validate()


@pytest.mark.parametrize("failure", [None, "physical", "estimate", "peak"])
def test_mock_cuda_admission_reuses_allocator_estimate_and_preserves_hard_caps(failure):
    model, theta = tiny()
    session = v33.R3Session(
        model, theta, profile_id="cpu-admission-mock", cpu_test=True, cpu_resident_test=True
    )
    # Only the admission branch is switched: all tensors and operations stay CPU;
    # memory_snapshot is a synthetic fixture, never a device query.
    session.cpu_test = False
    snapshot = dict(
        torch_allocated_bytes=4 * v33.GIB,
        torch_reserved_bytes=(5 if failure == "estimate" else 20) * v33.GIB,
        torch_peak_allocated_bytes=(77 if failure == "peak" else 4) * v33.GIB,
        torch_peak_reserved_bytes=20 * v33.GIB,
        device_free_bytes_at_response_boundary=(1 if failure == "physical" else 6) * v33.GIB,
        device_total_bytes=80 * v33.GIB,
        device_used_bytes_at_response_boundary=74 * v33.GIB,
    )
    session.memory_snapshot = lambda: dict(snapshot)
    if failure:
        messages = {
            "physical": "physical free reserve exhausted",
            "estimate": "insufficient free memory for R3",
            "peak": "observed allocated peak",
        }
        with pytest.raises(ValueError, match=messages[failure]):
            session(model, theta, [2, 3], [4], expected=None)
        assert session.calls == (1 if failure == "peak" else 0)
    else:
        _, _, report = session(model, theta, [2, 3], [4], expected=None)
        admission = report["non_KV_memory_admission"]
        assert admission["physical_free_bytes"] == 6 * v33.GIB
        assert admission["estimated_reusable_own_allocator_bytes"] == 16 * v33.GIB
        assert admission["estimated_available_bytes"] == 22 * v33.GIB
        assert admission["inherited_raw_free_KV_admission_unchanged"]
        assert not admission["placeholder_allocation"]
    session.close()


def test_source_binding_contains_exact_adapter_and_legacy_hashes():
    binding = v33.source_binding()
    assert binding["backend_version"] == v33.BACKEND_VERSION
    for module in (v33, v33.optimized, v33.optimized.legacy):
        path = Path(module.__file__)
        assert binding["sources"][path.name] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert binding["block_size"] == 8
    assert binding["activation_resident_budget_bytes"] == 16 * v33.GIB
