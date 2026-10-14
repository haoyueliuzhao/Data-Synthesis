"""Version/lifetime-bound frozen views, measured CPU saves, no activation dedup.

Storage IDs are lifetime-scoped (weak references), not naked reused addresses.
The only reference-retention optimization applies to registered immutable model
parameters; requires_grad=False alone never authorizes retention or deduplication.
"""

import contextlib
import os
import threading
import time
import weakref
from collections import Counter
from pathlib import Path

import torch
import torch.nn.functional as F

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p


def process_memory():
    result = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in {"VmRSS", "VmHWM", "VmLck", "VmPin"}:
            result[key + "_bytes"] = int(value.split()[0]) * 1024
    return result


def host_memory():
    rows = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in {"MemAvailable", "MemTotal", "Mlocked", "Unevictable"}:
            rows[key + "_bytes"] = int(value.split()[0]) * 1024
    return rows


def signature(tensor):
    storage = tensor.untyped_storage()
    return (
        str(tensor.device),
        storage._cdata,
        storage.data_ptr(),
        storage.nbytes(),
        str(tensor.dtype),
        tuple(tensor.shape),
        tuple(tensor.stride()),
        tensor.storage_offset(),
        tensor._version,
    )


class Packed:
    def __init__(self, value, *, frozen=False, source=None, owner=None):
        self.value, self.frozen, self.source, self.owner = value, frozen, source, owner


class SavedTensorStore:
    def __init__(self, model, *, retain_frozen=False, pin_memory=True, event_stream=None):
        self.model, self.retain_frozen = model, retain_frozen
        self.event_stream = event_stream
        self.native = torch.autograd.graph.save_on_cpu(pin_memory=pin_memory)
        self.owners = {}
        for name, value in model.named_parameters():
            if not value.requires_grad:
                storage = value.untyped_storage()
                key = str(value.device), storage._cdata
                self.owners[key] = (name, value, storage, signature(value))
        self.sources, self.KV = {}, {}
        self.sequence = 0
        self.phase = "prefill"
        self.counts = Counter()
        self.logical = Counter()
        self.unique_source = Counter()
        self.host_allocated = Counter()
        self.live_host = Counter()
        self.peak_host = Counter()
        self.live_pinned = self.peak_pinned = self.peak_total_host = 0
        self.peak_process = Counter()
        self.snapshots = []
        self._stop = threading.Event()
        self.started = time.monotonic()

    def _sample(self):
        self.peak_process |= Counter(process_memory())

    def _monitor(self):
        while not self._stop.wait(0.25):
            self._sample()

    def _source(self, tensor, category):
        storage = tensor.untyped_storage()
        key = str(tensor.device), storage._cdata
        old = self.sources.get(key)
        if old is None or old[0]() is not storage:
            self.sequence += 1
            self.sources[key] = (weakref.ref(storage), self.sequence)
            self.unique_source[category] += storage.nbytes()
        return self.sources[key][1]

    def _category(self, tensor):
        storage = tensor.untyped_storage()
        key = str(tensor.device), storage._cdata
        owner = self.owners.get(key)
        if owner is not None:
            _, value, owned_storage, expected = owner
            p.require(
                storage is owned_storage
                and signature(value) == expected
                and tensor.dtype == value.dtype
                and tensor._version == value._version,
                "saved_tensors.bound_frozen_storage_and_version",
            )
            end = tensor.storage_offset()
            if tensor.numel():
                end += (
                    sum(
                        (size - 1) * stride
                        for size, stride in zip(tensor.shape, tensor.stride(), strict=True)
                    )
                    + 1
                )
            p.require(
                all(stride >= 0 for stride in tensor.stride())
                and 0 <= end * tensor.element_size() <= storage.nbytes(),
                "saved_tensors.frozen_view_range",
            )
            return "frozen_weight_or_view", owner
        registered = self.KV.get(key)
        if registered is not None and registered() is storage:
            return "attention_KV_history_or_view", None
        return "prefill_activation" if self.phase == "prefill" else "decode_activation", None

    def _released(self, category, physical, pinned):
        self.live_host[category] -= physical
        if pinned:
            self.live_pinned -= physical

    def pack(self, tensor):
        category, owner = self._category(tensor)
        source = self._source(tensor, category)
        logical = tensor.numel() * tensor.element_size()
        self.counts[category] += 1
        self.logical[category] += logical
        retained = owner is not None and self.retain_frozen
        if retained:
            packed = Packed(tensor.detach(), frozen=True, source=signature(tensor), owner=owner)
            physical, pinned = 0, False
        else:
            value = self.native.pack_hook(tensor)
            device, saved = value
            physical = saved.untyped_storage().nbytes()
            pinned = saved.is_pinned()
            packed = Packed((device, saved))
            self.host_allocated[category] += physical
            self.live_host[category] += physical
            self.peak_host[category] = max(self.peak_host[category], self.live_host[category])
            self.peak_total_host = max(self.peak_total_host, sum(self.live_host.values()))
            if pinned:
                self.live_pinned += physical
                self.peak_pinned = max(self.peak_pinned, self.live_pinned)
            weakref.finalize(packed, self._released, category, physical, pinned)
        if self.event_stream is not None:
            self.event_stream.write(
                p.encode(
                    dict(
                        category=category,
                        phase=self.phase,
                        source_storage_lifetime=source,
                        logical_bytes=logical,
                        source_storage_bytes=tensor.untyped_storage().nbytes(),
                        host_allocation_bytes=physical,
                        pinned=pinned,
                        retained_bound_frozen_view=retained,
                        shape=list(tensor.shape),
                        stride=list(tensor.stride()),
                        offset=tensor.storage_offset(),
                        version=tensor._version,
                        dtype=str(tensor.dtype),
                    )
                )
                + b"\n"
            )
        return packed

    def unpack(self, packed):
        if packed.frozen:
            _, owner, _, expected = packed.owner
            p.require(
                signature(owner) == expected and signature(packed.value) == packed.source,
                "saved_tensors.frozen_view_mutated_before_backward",
            )
            return packed.value
        return self.native.unpack_hook(packed.value)

    @contextlib.contextmanager
    def context(self):
        original = F.scaled_dot_product_attention

        def attention(query, key, value, *args, **kwargs):
            for tensor in (key, value):
                storage = tensor.untyped_storage()
                self.KV[str(tensor.device), storage._cdata] = weakref.ref(storage)
            return original(query, key, value, *args, **kwargs)

        def phase(_module, _args, kwargs):
            self.phase = "prefill" if kwargs["input_ids"].shape[1] > 1 else "decode"

        hook = self.model.register_forward_pre_hook(phase, with_kwargs=True)
        F.scaled_dot_product_attention = attention
        self._sample()
        monitor = threading.Thread(target=self._monitor, daemon=True)
        monitor.start()
        try:
            with torch.autograd.graph.saved_tensors_hooks(self.pack, self.unpack):
                yield self
        finally:
            hook.remove()
            F.scaled_dot_product_attention = original
            self._stop.set()
            monitor.join()
            self._sample()
            for _, value, _, expected in self.owners.values():
                p.require(signature(value) == expected, "saved_tensors.frozen_owner_lifecycle")
            if self.event_stream is not None:
                self.event_stream.flush()
                os.fsync(self.event_stream.fileno())

    def report(self):
        return dict(
            save_events=dict(self.counts),
            logical_saved_bytes=dict(self.logical),
            unique_source_storage_lifetime_bytes=dict(self.unique_source),
            actual_host_allocation_bytes=dict(self.host_allocated),
            live_host_bytes_after_response=dict(self.live_host),
            maximum_live_host_bytes_by_category=dict(self.peak_host),
            maximum_total_live_host_bytes=self.peak_total_host,
            maximum_live_pinned_bytes=self.peak_pinned,
            live_pinned_bytes_after_response=self.live_pinned,
            maximum_observed_process_memory=dict(self.peak_process),
            process_memory_after_response=process_memory(),
            CUDA_allocated_bytes=torch.cuda.memory_allocated()
            if torch.cuda.is_initialized()
            else 0,
            CUDA_reserved_bytes=torch.cuda.memory_reserved() if torch.cuda.is_initialized() else 0,
            CUDA_peak_allocated_bytes=torch.cuda.max_memory_allocated()
            if torch.cuda.is_initialized()
            else 0,
            CUDA_peak_reserved_bytes=torch.cuda.max_memory_reserved()
            if torch.cuda.is_initialized()
            else 0,
            retained_bound_frozen_views=self.retain_frozen,
            classification=(
                "bound frozen storage first; actual SDPA K/V next; "
                "other saves classified by prefill/decode phase"
            ),
            source_unique_method="weakref lifetime IDs; no pointer-only deduplication",
            allocator_cached_memory_is_not_live_saved_tensor_memory=True,
            elapsed_seconds=time.monotonic() - self.started,
        )
