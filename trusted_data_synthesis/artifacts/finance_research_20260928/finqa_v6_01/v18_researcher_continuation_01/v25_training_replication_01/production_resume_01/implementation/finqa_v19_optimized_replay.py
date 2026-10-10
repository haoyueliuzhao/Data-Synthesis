"""Versioned replay storage optimization; the frozen numeric bytecode is reused.

No persistent patch of the frozen numeric modules, new sampling, block-size
change or detached boundary derivative. Temporary hooks follow the original
saved-tensor contexts. A session owns one fixed virtual parameter point.
"""

from __future__ import annotations

import contextlib
import threading
import time
import types
import weakref
from collections import Counter

import fixed_kernel_anchored_canonical_saves_20260916 as canonical
import fixed_kernel_anchored_saved_tensors_20260916 as saved
import fixed_kernel_anchored_segmented_replay_20260916 as legacy
import torch
import torch.nn.functional as F

from trusted_synthesis.finance_research.providers import parameter_digest
from trusted_synthesis.finance_research.v6_collection import require


def bind_dependencies(function, **bindings):
    """Copy a function's globals, never modify its module or arithmetic bytecode."""

    def names(code):
        result = set(code.co_names)
        for value in code.co_consts:
            if isinstance(value, types.CodeType):
                result.update(names(value))
        return result

    require(
        set(bindings) <= names(function.__code__) and set(bindings) <= set(function.__globals__),
        "unknown frozen dependency",
    )
    result = types.FunctionType(
        function.__code__,
        {**function.__globals__, **bindings},
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    result.__kwdefaults__ = function.__kwdefaults__
    result.__doc__ = function.__doc__
    return result


class ReplayBank(canonical.FrozenLayoutBank):
    """Reuse frozen weights; bounded saved-KV copies are never activation-deduplicated."""

    def __init__(self, model, *, resident_limit=2 * 1024**3, cpu_resident_test=False):
        super().__init__(model)
        require(
            type(resident_limit) is int and 0 <= resident_limit <= 2 * 1024**3,
            "finite registered saved-KV device budget required",
        )
        self.resident_limit, self.cpu_resident_test = resident_limit, cpu_resident_test
        self.resident_live = self.resident_peak = self.resident_total = 0
        self.owners = {}
        for name, value in model.named_parameters():
            if not value.requires_grad:
                storage = value.untyped_storage()
                self.owners[str(value.device), storage._cdata] = (
                    name,
                    value,
                    storage,
                    saved.signature(value),
                )

    def validate(self):
        for _, value, _, expected in self.owners.values():
            require(saved.signature(value) == expected, "fixed base owner changed during replay")
        require(
            self.live_host == self.live_pinned == self.resident_live == 0,
            "previous response retains saved tensors",
        )

    def release_resident(self, amount):
        self.resident_live -= amount


class BoundaryAuditedStore(canonical.CanonicalSavedTensorStore):
    """Same native save/unpack, range/version checks and exact byte accounting.

    Reuse the fixed owner registry. No thread or /proc sampling is created per
    eight-token block. Process/GPU telemetry belongs at response boundaries.
    """

    def __init__(self, model, *, bank, **kwargs):
        require(bank.model is model and isinstance(bank, ReplayBank), "bound replay bank required")
        self.model, self.retain_frozen, self.bank = model, True, bank
        self.event_stream = None
        self.native = torch.autograd.graph.save_on_cpu(
            pin_memory=next(model.parameters()).device.type == "cuda" or bank.cpu_resident_test
        )
        self.owners = bank.owners
        self.sources, self.KV = {}, {}
        self.sequence, self.phase = 0, "prefill"
        self.counts, self.logical, self.unique_source = Counter(), Counter(), Counter()
        self.host_allocated, self.live_host, self.peak_host = Counter(), Counter(), Counter()
        self.live_pinned = self.peak_pinned = self.peak_total_host = 0
        self.peak_process, self.snapshots = Counter(), []
        self._stop, self.started = threading.Event(), time.monotonic()

    def pack(self, tensor):
        storage = tensor.untyped_storage()
        key = str(tensor.device), storage._cdata
        registered = self.KV.get(key)
        amount = tensor.numel() * tensor.element_size()
        if (
            key not in self.owners
            and registered is not None
            and registered() is storage
            and (tensor.device.type == "cuda" or self.bank.cpu_resident_test)
            and self.bank.resident_live + amount <= self.bank.resident_limit
        ):
            # Emulate native pin_memory=True packing's independent contiguous
            # buffer exactly, but on this device. No view retention or dedup.
            with torch.no_grad():
                value = torch.empty(
                    tensor.size(), dtype=tensor.dtype, layout=tensor.layout, device=tensor.device
                )
                value.copy_(tensor)
            packed = saved.Packed(value, source=saved.signature(value))
            packed.device_resident_KV = True
            self.bank.resident_live += amount
            self.bank.resident_peak = max(self.bank.resident_peak, self.bank.resident_live)
            self.bank.resident_total += amount
            weakref.finalize(packed, self.bank.release_resident, amount)
            self.counts["device_saved_KV_copy"] += 1
            self.logical["device_saved_KV_copy"] += amount
            return packed
        return super().pack(tensor)

    def unpack(self, packed):
        if getattr(packed, "device_resident_KV", False):
            require(
                saved.signature(packed.value) == packed.source,
                "independent saved-KV device copy was mutated",
            )
            return packed.value
        return super().unpack(packed)

    @contextlib.contextmanager
    def context(self):
        original = F.scaled_dot_product_attention

        def attention(query, key, value, *args, **kwargs):
            # Keep both Python storage wrappers alive throughout the pack hooks;
            # a weak reference alone may expire even while its tensor is alive.
            storages = [(tensor.device, tensor.untyped_storage()) for tensor in (key, value)]
            for device, storage in storages:
                self.KV[str(device), storage._cdata] = weakref.ref(storage)
            return original(query, key, value, *args, **kwargs)

        def phase(_module, _args, kwargs):
            self.phase = "prefill" if kwargs["input_ids"].shape[1] > 1 else "decode"

        hook = self.model.register_forward_pre_hook(phase, with_kwargs=True)
        F.scaled_dot_product_attention = attention
        try:
            with torch.autograd.graph.saved_tensors_hooks(self.pack, self.unpack):
                yield self
        finally:
            hook.remove()
            F.scaled_dot_product_attention = original
            # pack/unpack still validate every saved frozen operand. The full
            # owner sweep is performed before/after each complete response,
            # instead of repeating it at every nested eight-token context.

    def report(self):
        return dict(
            maximum_total_live_host_bytes=self.peak_total_host,
            live_host_bytes_after_response=dict(self.live_host),
            actual_host_allocation_bytes=dict(self.host_allocated),
            maximum_live_pinned_bytes=self.peak_pinned,
            extra_resident_canonical_weight_bytes=self.bank.extra_bytes,
            diagnostic_sampling="response_boundaries_not_per_block",
            process_memory_sampled_in_this_block=False,
            live_device_saved_KV_bytes=self.bank.resident_live,
            maximum_device_saved_KV_bytes=self.bank.resident_peak,
        )


def forward_saved_tokens_on_device(model, prompt, targets):
    """The original token-at-a-time forward; retain its final KV on this device."""
    device = next(model.parameters()).device
    cache, values = None, []
    ids = torch.tensor([prompt], dtype=torch.long, device=device)
    with torch.no_grad():
        for index, target in enumerate(targets):
            output = legacy._call(model, ids, len(prompt) + index, cache)
            cache = output.past_key_values
            values.append(torch.log_softmax(output.logits[0, -1].float(), -1)[target].detach())
            ids = torch.tensor([[target]], dtype=torch.long, device=device)
        state = legacy.cache_tensors(cache)
        require(
            all(value.shape[-2] == len(prompt) + len(targets) - 1 for value in state),
            "exact complete KV cache length required",
        )
        # No dtype/layout change. cache_from_prefix still creates differentiable
        # boundary leaves; only the CPU round trip is absent.
        complete = tuple(value.detach().contiguous() for value in state)
    return torch.stack(values), complete


class ReplaySession:
    """Fixed8, same token order and same VJPs, with an outer-local storage bank."""

    def __init__(
        self,
        model,
        theta,
        *,
        profile_id,
        cpu_test=False,
        resident_kv_budget_bytes=2 * 1024**3,
        cpu_resident_test=False,
    ):
        require(
            theta and all(v.device.type == ("cpu" if cpu_test else "cuda") for v in theta.values()),
            "production replay requires CUDA; CPU is only an explicit test",
        )
        self.model, self.profile_id = model, profile_id
        self.parameter_digest = parameter_digest(theta)
        self.parameter_versions = {name: saved.signature(value) for name, value in theta.items()}
        require(not cpu_resident_test or cpu_test, "CPU residency emulation is only a test")
        self.bank = ReplayBank(
            model, resident_limit=resident_kv_budget_bytes, cpu_resident_test=cpu_resident_test
        )
        self.calls = 0

        def fixed_bank(actual_model):
            require(actual_model is model, "replay bank belongs to another model")
            require(
                self.bank.live_host == self.bank.live_pinned == self.bank.resident_live == 0,
                "the previous response's saved tensors are still live",
            )
            return self.bank

        prefill = contextlib.contextmanager(
            bind_dependencies(
                legacy.pure_prefill_checkpoints.__wrapped__,
                CanonicalSavedTensorStore=BoundaryAuditedStore,
            )
        )

        class ResidentOperation(legacy.SegmentedOperation):
            pass

        ResidentOperation.forward = bind_dependencies(
            legacy.SegmentedOperation.forward,
            forward_saved_tokens=forward_saved_tokens_on_device,
            FrozenLayoutBank=fixed_bank,
            CanonicalSavedTensorStore=BoundaryAuditedStore,
            pure_prefill_checkpoints=prefill,
        )
        self.operation = ResidentOperation
        self.kernel = bind_dependencies(legacy.segmented_logp, SegmentedOperation=ResidentOperation)

    def __call__(self, model, theta, prompt, targets, *, expected, block_size=8):
        require(
            model is self.model and block_size == 8, "fixed model and original eight-token blocks"
        )
        require(
            {name: saved.signature(value) for name, value in theta.items()}
            == self.parameter_versions,
            "virtual parameter lifetime/version changed",
        )
        self.bank.validate()
        values, gradient, accounting = self.kernel(
            model,
            theta,
            prompt,
            targets,
            expected=expected,
            block_size=8,
            prefill_checkpoint=True,
            offload=True,
        )
        self.bank.validate()
        self.calls += 1
        accounting["single_complete_GPU_KV_bytes"] = accounting["single_complete_CPU_KV_bytes"]
        accounting["single_complete_CPU_KV_bytes"] = 0
        accounting.update(
            execution_profile_id=self.profile_id,
            cached_frozen_bank_responses=self.calls,
            per_block_process_monitor_threads=0,
            original_numeric_bytecode_reused=True,
            resident_saved_KV_budget_bytes=self.bank.resident_limit,
            peak_resident_saved_KV_bytes=self.bank.resident_peak,
            cumulative_saved_KV_device_copy_bytes=self.bank.resident_total,
            activation_deduplication=False,
        )
        return values, gradient, accounting

    def close(self, *, aborted=False):
        if not aborted:
            self.bank.validate()
        self.bank.values.clear()
        self.bank.extra_storage.clear()
