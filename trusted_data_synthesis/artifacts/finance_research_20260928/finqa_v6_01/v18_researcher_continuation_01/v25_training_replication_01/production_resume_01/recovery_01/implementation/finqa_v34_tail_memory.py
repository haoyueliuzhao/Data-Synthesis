"""Layout-preserving saved-tensor offload for one frozen class-gradient pass.

This adapter does not replay feedback, change arithmetic, reset CUDA peaks, or
retry an allocation. Frozen parameter views stay on their original storage.
Other provably non-overlapping strided saves receive independent CPU copies;
unpack recreates their original shape, stride and storage offset. Unsupported
layouts are selected for original-device retention *before* any allocation.
"""

from __future__ import annotations

import gc
import hashlib
import json
import time
import weakref
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import torch

BACKEND_VERSION = "v34_layout_preserving_class_saved_tensors.v1"
GIB = 1024**3
LIMITS = dict(allocated_memory_limit_bytes=76 * GIB, free_memory_reserve_bytes=2 * GIB)


def require(condition, message):
    if not condition:
        raise ValueError(message)


class TailMemoryError(RuntimeError):
    """A published resource observation failed the unchanged hard envelope."""


class TailStopRequested(RuntimeError):
    """Stop at a class-row or stage boundary; never retry or resume this pass."""


class TailMemoryMonitor:
    def __init__(
        self,
        torch_module,
        *,
        event_sink,
        stop_requested=lambda: False,
        device="cuda:0",
        limits=None,
    ):
        require(limits is None or limits == LIMITS, "V34 memory limits are fixed at 76 GiB / 2 GiB")
        self.torch, self.device = torch_module, device
        self.event_sink, self.stop_requested = event_sink, stop_requested
        self.observations = []
        self._failed = False

    def snapshot(self, label, *, boundary=False, **context):
        require(not self._failed, "a failed V34 resource gate cannot be resumed")
        cuda = self.torch.cuda
        cuda.synchronize(self.device)
        free, total = cuda.mem_get_info(self.device)
        value = dict(
            event="tail_memory_observation",
            sequence=len(self.observations) + 1,
            label=label,
            boundary=boundary,
            monotonic_seconds=time.monotonic(),
            allocated_bytes=int(cuda.memory_allocated(self.device)),
            reserved_bytes=int(cuda.memory_reserved(self.device)),
            peak_allocated_bytes=int(cuda.max_memory_allocated(self.device)),
            peak_reserved_bytes=int(cuda.max_memory_reserved(self.device)),
            free_bytes=int(free),
            total_bytes=int(total),
            limits=dict(LIMITS),
            context=context,
        )
        value["allocated_pass"] = (
            value["peak_allocated_bytes"] <= LIMITS["allocated_memory_limit_bytes"]
        )
        value["free_pass"] = (
            not boundary or value["free_bytes"] >= LIMITS["free_memory_reserve_bytes"]
        )
        value["stop_requested"] = bool(self.stop_requested())
        value["passed"] = (
            value["allocated_pass"] and value["free_pass"] and not value["stop_requested"]
        )
        self.observations.append(value)
        # Publish the exact numbers before throwing; failed evidence is retained.
        self.event_sink(dict(value))
        if not value["allocated_pass"] or not value["free_pass"]:
            self._failed = True
            raise TailMemoryError(
                "V34 CUDA memory envelope failed: " + json.dumps(value, sort_keys=True)
            )
        if value["stop_requested"]:
            self._failed = True
            raise TailStopRequested("stop requested at " + label)
        return value

    def check_stop(self, label, **context):
        require(not self._failed, "a failed V34 resource gate cannot be resumed")
        if self.stop_requested():
            # Use a full boundary reading so a stop also preserves resource evidence.
            self.snapshot(label, boundary=True, **context)

    def clear_unused(self, label):
        before = self.snapshot(label + ".before_cleanup", boundary=False)
        gc.collect()
        self.torch.cuda.empty_cache()
        after = self.snapshot(label + ".after_cleanup", boundary=True)
        return dict(before=before, after=after)

    def report(self):
        boundaries = [row for row in self.observations if row["boundary"]]
        return dict(
            limits=dict(LIMITS),
            observations=list(self.observations),
            max_observed_peak_allocated_bytes=max(
                (row["peak_allocated_bytes"] for row in self.observations), default=None
            ),
            min_boundary_free_bytes=min((row["free_bytes"] for row in boundaries), default=None),
            all_passed=all(row["passed"] for row in self.observations),
            peak_reset_calls=0,
        )


def _layout(tensor):
    return (
        str(tensor.device),
        tensor.dtype,
        tensor.layout,
        tuple(tensor.shape),
        tuple(tensor.stride()),
        tensor.storage_offset(),
        tensor.is_conj(),
        tensor.is_neg(),
    )


def _signature(tensor):
    if tensor.layout != torch.strided:
        return str(tensor.device), tensor.dtype, tensor.layout, tuple(tensor.shape), tensor._version
    return (*_layout(tensor), tensor.untyped_storage()._cdata, tensor._version)


def _nonoverlapping(tensor):
    """Conservative proof; unusual but valid layouts may remain device-resident."""
    if tensor.numel() == 0:
        return True
    span = 1
    for stride, size in sorted(zip(tensor.stride(), tensor.shape, strict=True)):
        if size <= 1:
            continue
        if stride < span:
            return False
        span += (size - 1) * stride
    return True


def _extent(tensor):
    if tensor.numel() == 0:
        return tensor.storage_offset()
    return (
        tensor.storage_offset()
        + 1
        + sum(
            (size - 1) * stride for size, stride in zip(tensor.shape, tensor.stride(), strict=True)
        )
    )


@dataclass
class _Packed:
    kind: str
    value: object
    original_layout: object
    source: object
    source_signature: object
    saved_signature: object
    extent: int = 0


class LayoutPreservingSavedTensors:
    def __init__(self, model, *, cpu_test=False):
        self.cpu_test = cpu_test
        self.owners = {}
        for name, parameter in model.named_parameters():
            if not parameter.requires_grad and parameter.layout == torch.strided:
                key = str(parameter.device), parameter.untyped_storage()._cdata
                self.owners[key] = (name, parameter, _signature(parameter))
        self.counts, self.logical_bytes = Counter(), Counter()
        self.reconstructed_backing_bytes = 0
        self.packed_total_count = self.packed_live_count = self.packed_peak_count = 0
        self.packed_released_count = 0
        self.cpu_saved_total_bytes = self.cpu_saved_live_bytes = self.cpu_saved_peak_bytes = 0
        self.cpu_saved_released_bytes = 0

    def validate_owners(self):
        for name, owner, signature in self.owners.values():
            require(_signature(owner) == signature, "frozen owner changed: " + name)

    def _release(self, host_bytes):
        self.packed_live_count -= 1
        self.packed_released_count += 1
        self.cpu_saved_live_bytes -= host_bytes
        self.cpu_saved_released_bytes += host_bytes

    def validate_released(self):
        require(
            self.packed_live_count == self.cpu_saved_live_bytes == 0,
            "class pass retains saved objects or owned CPU tensor bytes",
        )
        require(
            self.packed_total_count == self.packed_released_count
            and self.cpu_saved_total_bytes == self.cpu_saved_released_bytes,
            "saved-object/CPU tensor lifetime accounting mismatch",
        )

    def _retained(self, tensor, kind, signature):
        # Detach avoids retaining the graph itself; storage and version stay shared.
        value = tensor.detach()
        return _Packed(kind, value, None, weakref.ref(tensor), signature, _signature(value))

    def pack(self, tensor):
        signature = _signature(tensor)
        key = (
            (str(tensor.device), tensor.untyped_storage()._cdata)
            if tensor.layout == torch.strided
            else None
        )
        if key in self.owners:
            name, owner, expected = self.owners[key]
            require(_signature(owner) == expected, "frozen owner changed: " + name)
            packed = self._retained(tensor, "frozen_owner_retained", signature)
        elif not (
            tensor.layout == torch.strided
            and not tensor.is_quantized
            and not tensor.is_conj()
            and not tensor.is_neg()
            and _nonoverlapping(tensor)
            and (tensor.device.type == "cuda" or self.cpu_test)
        ):
            packed = self._retained(tensor, "unsupported_layout_or_device_retained", signature)
        else:
            # Only storage is changed. Independent native-dtype CPU copies cannot
            # silently make a strided CUDA saved view contiguous on restoration.
            with torch.no_grad():
                host = torch.empty(
                    tensor.shape,
                    dtype=tensor.dtype,
                    device="cpu",
                    pin_memory=tensor.device.type == "cuda",
                )
                host.copy_(tensor)
            require(_signature(tensor) == signature, "source changed during saved-tensor copy")
            packed = _Packed(
                "layout_preserving_cpu_copy",
                host,
                _layout(tensor),
                weakref.ref(tensor),
                signature,
                _signature(host),
                _extent(tensor),
            )
        self.counts[packed.kind] += 1
        self.logical_bytes[packed.kind] += tensor.numel() * tensor.element_size()
        # Each offloaded save owns a distinct CPU tensor. Retained owner views
        # add saved objects, not newly allocated host bytes or duplicate storage.
        host_bytes = (
            packed.value.untyped_storage().nbytes()
            if packed.kind == "layout_preserving_cpu_copy"
            else 0
        )
        self.packed_total_count += 1
        self.packed_live_count += 1
        self.packed_peak_count = max(self.packed_peak_count, self.packed_live_count)
        self.cpu_saved_total_bytes += host_bytes
        self.cpu_saved_live_bytes += host_bytes
        self.cpu_saved_peak_bytes = max(self.cpu_saved_peak_bytes, self.cpu_saved_live_bytes)
        # The callback captures the store and an integer only, never packed or
        # its value. These are logical tensor lifetimes, not pinned allocator
        # reservation/physical occupancy (which may outlive the tensor).
        weakref.finalize(packed, self._release, host_bytes)
        return packed

    def unpack(self, packed):
        source = packed.source()
        if source is not None:
            require(_signature(source) == packed.source_signature, "saved-tensor source mutated")
        require(_signature(packed.value) == packed.saved_signature, "saved-tensor payload mutated")
        if packed.kind != "layout_preserving_cpu_copy":
            return packed.value
        device, dtype, layout, shape, stride, offset, conjugate, negative = packed.original_layout
        require(
            layout == torch.strided and not conjugate and not negative, "unsupported reconstruction"
        )
        with torch.no_grad():
            backing = torch.empty(packed.extent, dtype=dtype, device=device)
            value = backing.as_strided(shape, stride, offset)
            value.copy_(packed.value, non_blocking=device.startswith("cuda"))
        require(_layout(value) == packed.original_layout, "saved-tensor restored layout changed")
        self.counts["layout_preserving_unpacks"] += 1
        self.reconstructed_backing_bytes += backing.numel() * backing.element_size()
        return value

    def report(self):
        return dict(
            counts=dict(self.counts),
            logical_bytes=dict(self.logical_bytes),
            reconstructed_backing_bytes=self.reconstructed_backing_bytes,
            packed_total_count=self.packed_total_count,
            packed_live_count=self.packed_live_count,
            packed_peak_count=self.packed_peak_count,
            packed_released_count=self.packed_released_count,
            cpu_saved_total_bytes=self.cpu_saved_total_bytes,
            cpu_saved_live_bytes=self.cpu_saved_live_bytes,
            cpu_saved_peak_bytes=self.cpu_saved_peak_bytes,
            cpu_saved_released_bytes=self.cpu_saved_released_bytes,
            cpu_saved_bytes_are_tensor_lifetimes_not_pinned_allocator_occupancy=True,
            frozen_owners=len(self.owners),
            cpu_test=self.cpu_test,
            original_shape_stride_storage_offset_preserved=True,
            source_version_policy="pack_before_after_and_unpack_if_source_weakref_alive",
            retained_layout_policy="preselected_unsupported_or_overlapping_no_oom_fallback",
            oom_retry_count=0,
        )


class _ObservedPool:
    def __init__(self, pool, monitor):
        self.pool, self.monitor, self.rows_completed = pool, monitor, 0

    def __getattr__(self, name):
        return getattr(self.pool, name)

    def row_arrays(self, package_id):
        for index, row in enumerate(self.pool.row_arrays(package_id)):
            context = dict(
                package_id=package_id, package_row=index, completed_rows=self.rows_completed
            )
            self.monitor.check_stop("class_row_start", **context)
            yield row
            # The original class_gradients loop has finished its backward AND
            # ordered CPU add_ accumulation before advancing this iterator.
            self.rows_completed += 1
            self.monitor.snapshot(
                "class_row_end",
                boundary=True,
                package_id=package_id,
                package_row=index,
                completed_rows=self.rows_completed,
            )


def class_gradients_with_cpu_saves(rt, model, pool, *, device, monitor, cpu_test=False):
    require(cpu_test or str(device).startswith("cuda"), "CPU execution must be explicit test mode")
    original = rt.v8.class_gradients
    code, globals_identity = original.__code__, original.__globals__
    store = LayoutPreservingSavedTensors(model, cpu_test=cpu_test)
    observed = _ObservedPool(pool, monitor)
    monitor.check_stop("class_pass_start")
    with rt.torch.autograd.graph.saved_tensors_hooks(store.pack, store.unpack):
        gradients = original(model, observed, device=device)
    store.validate_owners()
    store.validate_released()
    require(
        rt.v8.class_gradients is original
        and original.__code__ is code
        and original.__globals__ is globals_identity,
        "frozen class-gradient function binding changed",
    )
    source = Path(code.co_filename)
    receipt = dict(
        backend_version=BACKEND_VERSION,
        frozen_class_source=dict(
            path=str(source), sha256=hashlib.sha256(source.read_bytes()).hexdigest()
        ),
        frozen_class_bytecode_and_global_binding_unchanged=True,
        rows_completed=observed.rows_completed,
        saved_tensors=store.report(),
        new_feedback_samples=0,
        replayed_feedback_responses=0,
    )
    return gradients, receipt
