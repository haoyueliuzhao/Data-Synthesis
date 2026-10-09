"""CPU/mock controls; these are not CUDA equivalence or resource results."""

import gc
import importlib
import sys
import weakref
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from trusted_synthesis.finance_research import v8_training_driver as v8

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
memory = importlib.import_module("finqa_v34_tail_memory")


class FakeCuda:
    def __init__(self, *, peak=40 * memory.GIB, free=8 * memory.GIB):
        self.peak, self.free = peak, free
        self.clears, self.resets, self.syncs = 0, 0, 0

    def synchronize(self, device):
        self.syncs += 1

    def mem_get_info(self, device):
        return self.free, 80 * memory.GIB

    def memory_allocated(self, device):
        return 30 * memory.GIB

    def memory_reserved(self, device):
        return 38 * memory.GIB

    def max_memory_allocated(self, device):
        return self.peak

    def max_memory_reserved(self, device):
        return 50 * memory.GIB

    def empty_cache(self):
        self.clears += 1
        self.free = 20 * memory.GIB

    def reset_peak_memory_stats(self):
        self.resets += 1
        raise AssertionError("memory adapter must not reset historical peak")


def monitor_fixture(**kwargs):
    events = []
    cuda = FakeCuda(**kwargs)
    monitor = memory.TailMemoryMonitor(SimpleNamespace(cuda=cuda), event_sink=events.append)
    return monitor, cuda, events


def byte_values(tensor):
    return tensor.contiguous().reshape(-1).view(torch.uint8)


@pytest.mark.parametrize(
    "dtype", [torch.float32, torch.float64, torch.bfloat16, torch.float16, torch.int64, torch.bool]
)
@pytest.mark.parametrize("view", ["contiguous", "transpose", "offset", "strided", "expand"])
def test_saved_value_layout_offset_and_independent_storage(dtype, view):
    model = torch.nn.Linear(2, 2, bias=False)
    store = memory.LayoutPreservingSavedTensors(model, cpu_test=True)
    tensor = torch.arange(30).to(dtype).reshape(5, 6)
    if view == "transpose":
        tensor = tensor.T
    elif view == "offset":
        tensor = tensor[2:4, 1:5]
    elif view == "strided":
        tensor = tensor[::2, 1::2]
    elif view == "expand":
        tensor = tensor[:1, :].expand(5, 6)
    packed = store.pack(tensor)
    restored = store.unpack(packed)
    assert memory._layout(restored) == memory._layout(tensor)
    assert torch.equal(byte_values(restored), byte_values(tensor))
    if view == "expand":
        assert packed.kind == "unsupported_layout_or_device_retained"
        assert restored.untyped_storage()._cdata == tensor.untyped_storage()._cdata
    else:
        assert packed.kind == "layout_preserving_cpu_copy"
        assert restored.untyped_storage()._cdata != tensor.untyped_storage()._cdata
        assert packed.value.untyped_storage()._cdata != tensor.untyped_storage()._cdata
        assert packed.value.is_contiguous()


@pytest.mark.parametrize("shape", [(), (0,), (2, 0, 3)])
def test_scalar_and_empty_saves(shape):
    store = memory.LayoutPreservingSavedTensors(torch.nn.Linear(1, 1), cpu_test=True)
    tensor = torch.empty(shape)
    restored = store.unpack(store.pack(tensor))
    assert memory._layout(restored) == memory._layout(tensor)
    assert torch.equal(byte_values(restored), byte_values(tensor))


def test_cpu_offload_does_not_retain_source_tensor_or_gpu_storage():
    store = memory.LayoutPreservingSavedTensors(torch.nn.Linear(1, 1), cpu_test=True)
    tensor = torch.arange(24.0).reshape(4, 6).T
    source, storage = weakref.ref(tensor), weakref.ref(tensor.untyped_storage())
    expected = tensor.contiguous().clone()
    packed = store.pack(tensor)
    del tensor
    gc.collect()
    assert source() is None and storage() is None
    assert torch.equal(store.unpack(packed), expected)


def test_packed_lifetimes_and_owned_cpu_bytes_release_without_retaining_packed():
    store = memory.LayoutPreservingSavedTensors(torch.nn.Linear(1, 1), cpu_test=True)
    tensor = torch.arange(12.0).reshape(3, 4).T
    first, second = store.pack(tensor), store.pack(tensor)
    first_ref, first_host_ref = weakref.ref(first), weakref.ref(first.value)
    amount = tensor.numel() * tensor.element_size()
    assert store.packed_live_count == store.packed_peak_count == store.packed_total_count == 2
    assert store.cpu_saved_live_bytes == store.cpu_saved_peak_bytes == 2 * amount
    with pytest.raises(ValueError, match="retains saved"):
        store.validate_released()
    del first
    assert first_ref() is None and first_host_ref() is None
    assert store.packed_live_count == store.packed_released_count == 1
    assert store.cpu_saved_live_bytes == store.cpu_saved_released_bytes == amount
    del second
    store.validate_released()
    assert store.packed_released_count == 2
    assert store.cpu_saved_released_bytes == store.cpu_saved_total_bytes == 2 * amount
    assert store.packed_peak_count == 2 and store.cpu_saved_peak_bytes == 2 * amount


def test_owner_view_saves_and_empty_copies_do_not_duplicate_host_storage_accounting():
    model = torch.nn.Linear(4, 3, bias=False).requires_grad_(False)
    store = memory.LayoutPreservingSavedTensors(model, cpu_test=True)
    first, second = store.pack(model.weight), store.pack(model.weight.T)
    empty = store.pack(torch.empty(0, 3))
    assert store.packed_live_count == store.packed_peak_count == 3
    assert store.cpu_saved_live_bytes == store.cpu_saved_total_bytes == 0
    del first, second, empty
    store.validate_released()
    assert store.packed_released_count == 3
    assert store.report()["cpu_saved_bytes_are_tensor_lifetimes_not_pinned_allocator_occupancy"]


def test_frozen_parameter_view_keeps_original_owner_and_version_checks():
    model = torch.nn.Linear(4, 3, bias=False).requires_grad_(False)
    store = memory.LayoutPreservingSavedTensors(model, cpu_test=True)
    view = model.weight.T[1:]
    packed = store.pack(view)
    assert packed.kind == "frozen_owner_retained"
    restored = store.unpack(packed)
    assert restored.untyped_storage()._cdata == model.weight.untyped_storage()._cdata
    assert memory._layout(restored) == memory._layout(view)
    model.weight.add_(1)
    with pytest.raises(ValueError, match="frozen owner changed"):
        store.validate_owners()
    with pytest.raises(ValueError, match="mutated"):
        store.unpack(packed)


def test_source_and_cpu_payload_mutation_are_hard_failures():
    store = memory.LayoutPreservingSavedTensors(torch.nn.Linear(1, 1), cpu_test=True)
    tensor = torch.arange(8.0)[1::2]
    first = store.pack(tensor)
    tensor.add_(1)
    with pytest.raises(ValueError, match="source mutated"):
        store.unpack(first)
    second = store.pack(tensor)
    second.value.add_(1)
    with pytest.raises(ValueError, match="payload mutated"):
        store.unpack(second)


def test_source_mutation_during_pack_is_rejected(monkeypatch):
    store = memory.LayoutPreservingSavedTensors(torch.nn.Linear(1, 1), cpu_test=True)
    tensor = torch.arange(8.0)
    original = torch.Tensor.copy_

    def mutate(destination, source, *args, **kwargs):
        result = original(destination, source, *args, **kwargs)
        source.add_(1)
        return result

    monkeypatch.setattr(torch.Tensor, "copy_", mutate)
    with pytest.raises(ValueError, match="source changed during"):
        store.pack(tensor)


def test_overlapping_and_sparse_saves_are_retained_before_allocation():
    store = memory.LayoutPreservingSavedTensors(torch.nn.Linear(1, 1), cpu_test=True)
    overlap = torch.arange(8.0).as_strided((3, 3), (1, 1))
    sparse = torch.eye(3).to_sparse()
    for tensor in (overlap, sparse):
        packed = store.pack(tensor)
        assert packed.kind == "unsupported_layout_or_device_retained"
        assert memory._signature(store.unpack(packed)) == memory._signature(tensor)


def test_oom_is_never_caught_or_retried(monkeypatch):
    store = memory.LayoutPreservingSavedTensors(torch.nn.Linear(1, 1), cpu_test=True)
    tensor = torch.arange(4.0)
    count = 0

    def oom(*args, **kwargs):
        nonlocal count
        count += 1
        raise torch.OutOfMemoryError("intentional CPU/mock allocation failure")

    monkeypatch.setattr(torch, "empty", oom)
    with pytest.raises(torch.OutOfMemoryError):
        store.pack(tensor)
    assert count == 1 and store.report()["oom_retry_count"] == 0


@pytest.mark.parametrize(
    "limit",
    [
        {
            "allocated_memory_limit_bytes": 77 * memory.GIB,
            "free_memory_reserve_bytes": 2 * memory.GIB,
        },
        {},
    ],
)
def test_limits_cannot_be_relaxed(limit):
    with pytest.raises(ValueError, match="fixed"):
        memory.TailMemoryMonitor(
            SimpleNamespace(cuda=FakeCuda()), event_sink=lambda event: None, limits=limit
        )


@pytest.mark.parametrize(
    "peak,free", [(76 * memory.GIB + 1, 8 * memory.GIB), (40 * memory.GIB, 2 * memory.GIB - 1)]
)
def test_failure_publishes_exact_resources_before_raise(peak, free):
    monitor, cuda, events = monitor_fixture(peak=peak, free=free)
    with pytest.raises(memory.TailMemoryError) as failure:
        monitor.snapshot("class_row_end", boundary=True, completed_rows=4)
    assert events[-1]["peak_allocated_bytes"] == peak
    assert events[-1]["free_bytes"] == free
    assert events[-1]["context"]["completed_rows"] == 4
    assert events[-1]["passed"] is False
    assert str(peak) in str(failure.value) and str(free) in str(failure.value)
    assert monitor.report()["all_passed"] is False
    assert cuda.resets == 0
    with pytest.raises(ValueError, match="cannot be resumed"):
        monitor.snapshot("illegal_retry", boundary=True)


def test_cleanup_records_both_readings_and_does_not_erase_peak():
    monitor, cuda, events = monitor_fixture(free=memory.GIB)
    result = monitor.clear_unused("class_boundary")
    assert result["before"]["free_bytes"] == memory.GIB
    assert result["before"]["boundary"] is False
    assert result["after"]["free_bytes"] == 20 * memory.GIB
    assert result["after"]["boundary"] is True
    assert result["before"]["peak_allocated_bytes"] == result["after"]["peak_allocated_bytes"]
    assert cuda.clears == 1 and cuda.resets == 0 and len(events) == 2
    assert monitor.report()["min_boundary_free_bytes"] == 20 * memory.GIB


def test_cleanup_never_hides_a_failed_historical_peak():
    monitor, cuda, events = monitor_fixture(peak=77 * memory.GIB, free=memory.GIB)
    with pytest.raises(memory.TailMemoryError):
        monitor.clear_unused("illegal_peak_cleanup")
    assert cuda.clears == cuda.resets == 0 and len(events) == 1


def test_exact_registered_limits_are_inclusive_and_free_gate_is_boundary_only():
    monitor, _, _ = monitor_fixture(peak=76 * memory.GIB, free=2 * memory.GIB)
    assert monitor.snapshot("exact_limits", boundary=True)["passed"]
    interior, _, _ = monitor_fixture(peak=76 * memory.GIB, free=1)
    assert interior.snapshot("pre_cleanup_observation", boundary=False)["passed"]


class TinyModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.embedding = torch.nn.Embedding(9, 5).requires_grad_(False)
        self.output = torch.nn.Linear(5, 9, bias=False)
        self.calls = 0

    def forward(self, *, input_ids, attention_mask, use_cache, logits_to_keep):
        self.calls += 1
        hidden = self.embedding(input_ids)[:, logits_to_keep, :]
        # Noncontiguous transpose saves participate in actual autograd.
        logits = hidden.transpose(1, 2).transpose(1, 2) @ self.output.weight.T
        return SimpleNamespace(logits=logits)


def tiny_pool():
    packages = [
        dict(task_id="task", state_id="a", package_id="p1", whole_package_target_tokens=4),
        dict(task_id="task", state_id="a", package_id="p2", whole_package_target_tokens=2),
        dict(task_id="task", state_id="b", package_id="p3", whole_package_target_tokens=2),
    ]
    row = dict(input_ids=[1, 2, 3, 4], target_positions=[2, 3], target_ids=[3, 4])
    return v8.VerifiedPool(
        ["task"],
        packages,
        {"p1": [row, row], "p2": [row], "p3": [row]},
        binding_id="cpu_mock_only",
        chi={},
        production=False,
    )


def test_original_complete_class_gradient_cpu_bitwise_and_binding_unchanged():
    torch.manual_seed(3491)
    model, pool = TinyModel(), tiny_pool()
    original = v8.class_gradients
    bytecode, globals_id = original.__code__, id(original.__globals__)
    parameter_values = {n: p.detach().clone() for n, p in model.named_parameters()}
    expected = original(model, pool, device="cpu")
    rng = torch.get_rng_state().clone()
    monitor, cuda, events = monitor_fixture()
    actual, receipt = memory.class_gradients_with_cpu_saves(
        SimpleNamespace(torch=torch, v8=v8),
        model,
        pool,
        device="cpu",
        monitor=monitor,
        cpu_test=True,
    )
    for task in expected:
        for state in expected[task]:
            for name in expected[task][state]:
                assert torch.equal(
                    byte_values(expected[task][state][name]), byte_values(actual[task][state][name])
                )
    assert original is v8.class_gradients and original.__code__ is bytecode
    assert id(original.__globals__) == globals_id
    assert model.training and torch.equal(torch.get_rng_state(), rng)
    assert all(torch.equal(parameter_values[n], p) for n, p in model.named_parameters())
    assert receipt["rows_completed"] == 4
    assert receipt["saved_tensors"]["counts"]["layout_preserving_unpacks"] > 0
    assert receipt["saved_tensors"]["packed_live_count"] == 0
    assert receipt["saved_tensors"]["cpu_saved_live_bytes"] == 0
    assert (
        receipt["saved_tensors"]["packed_total_count"]
        == receipt["saved_tensors"]["packed_released_count"]
    )
    assert (
        receipt["saved_tensors"]["cpu_saved_total_bytes"]
        == receipt["saved_tensors"]["cpu_saved_released_bytes"]
    )
    assert all(row["label"] == "class_row_end" and row["boundary"] for row in events)
    assert len(events) == 4 and cuda.clears == cuda.resets == 0


def test_row_boundary_stop_preserves_mode_rng_and_does_not_start_next_row():
    model, pool = TinyModel(), tiny_pool()
    rng = torch.get_rng_state().clone()
    monitor, cuda, events = monitor_fixture()
    monitor.stop_requested = lambda: model.calls == 1
    with pytest.raises(memory.TailStopRequested):
        memory.class_gradients_with_cpu_saves(
            SimpleNamespace(torch=torch, v8=v8),
            model,
            pool,
            device="cpu",
            monitor=monitor,
            cpu_test=True,
        )
    assert model.calls == 1 and model.training
    assert torch.equal(torch.get_rng_state(), rng)
    assert events[-1]["context"]["completed_rows"] == 1
    assert events[-1]["stop_requested"] is True
    assert cuda.resets == 0


def test_stop_unwinds_saved_tensor_hooks_without_persistent_torch_patch(monkeypatch):
    model, pool = TinyModel(), tiny_pool()
    monitor, _, _ = monitor_fixture()
    monitor.stop_requested = lambda: model.calls == 1
    pack_calls = []
    original = memory.LayoutPreservingSavedTensors.pack

    def count(store, tensor):
        pack_calls.append(tensor.shape)
        return original(store, tensor)

    monkeypatch.setattr(memory.LayoutPreservingSavedTensors, "pack", count)
    with pytest.raises(memory.TailStopRequested):
        memory.class_gradients_with_cpu_saves(
            SimpleNamespace(torch=torch, v8=v8),
            model,
            pool,
            device="cpu",
            monitor=monitor,
            cpu_test=True,
        )
    before = len(pack_calls)
    tensor = torch.arange(3.0, requires_grad=True)
    (tensor.square().sum()).backward()
    assert before > 0 and len(pack_calls) == before
    assert torch.equal(tensor.grad, torch.tensor([0.0, 2.0, 4.0]))


def test_cpu_mode_needs_explicit_test_flag():
    monitor, _, _ = monitor_fixture()
    with pytest.raises(ValueError, match="explicit test"):
        memory.class_gradients_with_cpu_saves(
            SimpleNamespace(torch=torch, v8=v8),
            TinyModel(),
            tiny_pool(),
            device="cpu",
            monitor=monitor,
        )
