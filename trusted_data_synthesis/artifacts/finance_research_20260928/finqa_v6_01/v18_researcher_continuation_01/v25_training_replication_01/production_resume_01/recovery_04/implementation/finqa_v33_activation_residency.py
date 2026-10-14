"""R3: one bounded saved-activation storage change on the unchanged V32 R2 math.

Non-frozen, non-SDPA-KV saves get independent contiguous device copies, up to
the registered 16 GiB live budget. Budget spill uses the inherited native CPU
save. This is not view retention, activation deduplication, or an OOM fallback.
The legacy arithmetic functions are only rebound with copied local globals.
"""

from __future__ import annotations

import contextlib
import hashlib
import weakref
from pathlib import Path

import finqa_v19_optimized_replay as optimized
import finqa_v32_replay_variants as v32
import torch

from trusted_synthesis.finance_research.v6_collection import require

GIB = 1024**3
ACTIVATION_RESIDENT_BUDGET_BYTES = 16 * GIB
BACKEND_VERSION = "v33_r2_independent_nonkv_activation_residency.v1"
PauseRequest = v32.PauseRequest
ReplayPaused = v32.ReplayPaused


def source_binding():
    """Bind the adapter and every reused storage/arithmetic source by content."""
    modules = (
        v32,
        optimized,
        optimized.legacy,
        optimized.legacy.gate,
        optimized.canonical,
        optimized.saved,
    )
    paths = {Path(__file__).resolve(), *(Path(module.__file__).resolve() for module in modules)}
    return dict(
        backend_version=BACKEND_VERSION,
        parent_backend_version=v32.BACKEND_VERSION,
        sources={
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)
        },
        block_size=8,
        activation_resident_budget_bytes=ACTIVATION_RESIDENT_BUDGET_BYTES,
        activation_copy_policy="independent_native_contiguous_per_save_no_dedup",
        budget_spill_policy="inherited_native_save_on_cpu_pin_memory_true",
        oom_policy="hard_failure_no_retry_or_variant_fallback",
    )


class ActivationReplayBank(optimized.ReplayBank):
    """The unchanged frozen/KV bank plus exact non-KV allocation lifetimes."""

    def __init__(
        self,
        model,
        *,
        activation_resident_limit=ACTIVATION_RESIDENT_BUDGET_BYTES,
        resident_limit=2 * GIB,
        cpu_resident_test=False,
    ):
        require(
            type(activation_resident_limit) is int
            and 0 <= activation_resident_limit <= ACTIVATION_RESIDENT_BUDGET_BYTES,
            "finite non-KV resident budget within registered 16 GiB required",
        )
        super().__init__(model, resident_limit=resident_limit, cpu_resident_test=cpu_resident_test)
        self.activation_resident_limit = activation_resident_limit
        self.activation_live_bytes = self.activation_peak_bytes = 0
        self.activation_total_bytes = self.activation_released_bytes = 0
        self.activation_live_count = self.activation_peak_count = 0
        self.activation_total_count = self.activation_released_count = 0
        self.activation_spill_total_count = self.activation_spill_host_allocation_bytes = 0

    def acquire_activation(self, amount):
        require(
            self.activation_live_bytes + amount <= self.activation_resident_limit,
            "non-KV residency allocation exceeds registered live budget",
        )
        self.activation_live_bytes += amount
        self.activation_peak_bytes = max(self.activation_peak_bytes, self.activation_live_bytes)
        self.activation_total_bytes += amount
        self.activation_live_count += 1
        self.activation_peak_count = max(self.activation_peak_count, self.activation_live_count)
        self.activation_total_count += 1

    def release_activation(self, amount):
        self.activation_live_bytes -= amount
        self.activation_released_bytes += amount
        self.activation_live_count -= 1
        self.activation_released_count += 1

    def validate(self):
        super().validate()
        require(
            self.activation_live_bytes == self.activation_live_count == 0,
            "previous response retains non-KV saved activations",
        )
        require(
            self.activation_total_bytes == self.activation_released_bytes
            and self.activation_total_count == self.activation_released_count,
            "non-KV activation allocation/release accounting mismatch",
        )

    def activation_report(self):
        return dict(
            resident_non_KV_budget_bytes=self.activation_resident_limit,
            live_resident_non_KV_bytes=self.activation_live_bytes,
            peak_resident_non_KV_bytes=self.activation_peak_bytes,
            cumulative_non_KV_device_copy_bytes=self.activation_total_bytes,
            released_non_KV_device_copy_bytes=self.activation_released_bytes,
            live_resident_non_KV_count=self.activation_live_count,
            peak_resident_non_KV_count=self.activation_peak_count,
            cumulative_non_KV_device_copy_count=self.activation_total_count,
            released_non_KV_device_copy_count=self.activation_released_count,
            cumulative_non_KV_budget_spill_count=self.activation_spill_total_count,
            cumulative_non_KV_budget_spill_host_allocation_bytes=(
                self.activation_spill_host_allocation_bytes
            ),
            non_KV_budget_is_not_total_memory_cap=True,
        )


class ActivationSavedTensorStore(optimized.BoundaryAuditedStore):
    """Extend exactly the non-owner/non-KV branch; preserve both original branches."""

    def __init__(self, model, *, bank, **kwargs):
        require(isinstance(bank, ActivationReplayBank), "R3 activation bank required")
        super().__init__(model, bank=bank, **kwargs)

    def pack(self, tensor):
        storage = tensor.untyped_storage()
        key = str(tensor.device), storage._cdata
        registered = self.KV.get(key)
        if (
            key in self.owners
            or registered is not None and registered() is storage
            or not (tensor.device.type == "cuda" or self.bank.cpu_resident_test)
        ):
            return super().pack(tensor)

        amount = tensor.numel() * tensor.element_size()
        if self.bank.activation_live_bytes + amount > self.bank.activation_resident_limit:
            # Budget spill is decided before allocation. OOM is never caught.
            packed = super().pack(tensor)
            self.bank.activation_spill_total_count += 1
            self.bank.activation_spill_host_allocation_bytes += (
                packed.value[1].untyped_storage().nbytes()
            )
            return packed

        original_source = optimized.saved.signature(tensor)
        with torch.no_grad():
            value = torch.empty(
                tensor.size(), dtype=tensor.dtype, layout=tensor.layout, device=tensor.device
            )
            value.copy_(tensor)
        require(
            optimized.saved.signature(tensor) == original_source,
            "non-KV source changed during independent copy",
        )
        require(
            value.is_contiguous() and value.untyped_storage().nbytes() == amount,
            "non-KV copy must use the native independent contiguous storage layout",
        )
        packed = optimized.saved.Packed(value, source=optimized.saved.signature(value))
        packed.device_resident_non_KV = True
        # Metadata only: retaining neither the source tensor nor its storage/view.
        packed.original_source_signature = original_source
        self.bank.acquire_activation(amount)
        weakref.finalize(packed, self.bank.release_activation, amount)
        self.counts["device_saved_non_KV_copy"] += 1
        self.logical["device_saved_non_KV_copy"] += amount
        return packed

    def unpack(self, packed):
        if getattr(packed, "device_resident_non_KV", False):
            require(
                optimized.saved.signature(packed.value) == packed.source,
                "independent saved non-KV device copy was mutated",
            )
            return packed.value
        return super().unpack(packed)

    def report(self):
        return {**super().report(), **self.bank.activation_report()}


class R3Session(v32.ReplaySession):
    """R2 full/saved-KV storage plus one separately bounded activation budget.

    The private inherited variant remains R2 so all V32 admission and actual-KV
    checks execute unchanged. Public monitoring and reports identify R3. CPU
    residency emulation is explicit and is not CUDA performance validation.
    """

    def __init__(
        self,
        model,
        theta,
        *,
        profile_id,
        cpu_test=False,
        resident_kv_budget_bytes=2 * GIB,
        full_kv_budget_bytes=8 * GIB,
        activation_resident_budget_bytes=ACTIVATION_RESIDENT_BUDGET_BYTES,
        allocated_memory_limit_bytes=76 * GIB,
        free_memory_reserve_bytes=2 * GIB,
        response_monitor=None,
        cpu_resident_test=False,
    ):
        require(not cpu_resident_test or cpu_test, "CPU residency emulation is only a test")
        require(
            cpu_test or activation_resident_budget_bytes == ACTIVATION_RESIDENT_BUDGET_BYTES,
            "production R3 requires the single registered 16 GiB non-KV budget",
        )
        require(
            theta and all(value.dtype == torch.float32 for value in theta.values()),
            "R3 trainable parameter and gradient path requires original FP32 dtype",
        )

        def monitor(row):
            response_monitor({**row, "variant": "R3"})

        super().__init__(
            model,
            theta,
            variant="R2",
            profile_id=profile_id,
            cpu_test=cpu_test,
            resident_kv_budget_bytes=resident_kv_budget_bytes,
            full_kv_budget_bytes=full_kv_budget_bytes,
            allocated_memory_limit_bytes=allocated_memory_limit_bytes,
            free_memory_reserve_bytes=free_memory_reserve_bytes,
            response_monitor=monitor if response_monitor else None,
        )
        self.bank = ActivationReplayBank(
            model,
            activation_resident_limit=activation_resident_budget_bytes,
            resident_limit=resident_kv_budget_bytes,
            cpu_resident_test=cpu_resident_test,
        )
        prefill = contextlib.contextmanager(
            optimized.bind_dependencies(
                optimized.legacy.pure_prefill_checkpoints.__wrapped__,
                CanonicalSavedTensorStore=ActivationSavedTensorStore,
            )
        )
        self.operation.forward = optimized.bind_dependencies(
            self.operation.forward,
            CanonicalSavedTensorStore=ActivationSavedTensorStore,
            pure_prefill_checkpoints=prefill,
        )

    def __call__(self, model, theta, prompt, targets, *, expected, block_size=8):
        admission = {"cpu_test_only": True}
        if not self.cpu_test:
            before = self.memory_snapshot()
            incremental = (
                v32.estimate_complete_kv_bytes(model, len(prompt), len(targets))
                + self.bank.resident_limit
                + self.bank.activation_resident_limit
            )
            free = before["device_free_bytes_at_response_boundary"]
            reusable = max(
                before["torch_reserved_bytes"] - before["torch_allocated_bytes"], 0
            )
            require(free >= self.free_memory_reserve_bytes, "R3 physical free reserve exhausted")
            require(
                free + reusable >= self.free_memory_reserve_bytes + incremental,
                "insufficient free memory for R3 KV/non-KV residency plus reserve",
            )
            admission = dict(
                physical_free_bytes=free,
                estimated_reusable_own_allocator_bytes=reusable,
                estimated_available_bytes=free + reusable,
                incremental_budget_bytes=incremental,
                reserve_bytes=self.free_memory_reserve_bytes,
                inherited_raw_free_KV_admission_unchanged=True,
                estimate_does_not_guarantee_fragmentation_or_OOM_safety=True,
                placeholder_allocation=False,
            )
        values, gradient, report = super().__call__(
            model, theta, prompt, targets, expected=expected, block_size=block_size
        )
        report.update(
            replay_variant="R3",
            replay_backend_version=BACKEND_VERSION,
            parent_replay_backend_version=v32.BACKEND_VERSION,
            independent_non_KV_contiguous_per_save=True,
            original_frozen_owner_and_KV_paths_reused=True,
            cross_response_activation_cache=False,
            budget_spill_policy="inherited_native_save_on_cpu_pin_memory_true",
            oom_policy="hard_failure_no_retry_or_variant_fallback",
            non_KV_memory_admission=admission,
            **self.bank.activation_report(),
        )
        return values, gradient, report
