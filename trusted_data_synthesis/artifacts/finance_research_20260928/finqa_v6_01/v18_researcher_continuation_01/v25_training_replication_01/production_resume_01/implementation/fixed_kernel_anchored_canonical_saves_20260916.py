"""Share the ORIGINAL save_on_cpu contiguous layout of each frozen weight view.

R3 plain view retention changed backward layout and failed its gradient control.
This bank keeps at most one immutable contiguous GPU copy per bound view, so it
avoids repeated host copies without changing the baseline backward tensor stride.
"""

import weakref

from fixed_kernel_anchored_saved_tensors_20260916 import SavedTensorStore, signature

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p


class FrozenLayoutBank:
    def __init__(self, model):
        self.model = model
        self.values = {}
        self.extra_storage = {}
        self.live_host = self.peak_host = self.live_pinned = self.peak_pinned = 0

    def release(self, amount, pinned):
        self.live_host -= amount
        if pinned:
            self.live_pinned -= amount

    def take(self, tensor, owner):
        _, value, _, expected = owner
        p.require(signature(value) == expected, "canonical_save.owner_version_lifetime")
        key = signature(tensor)
        if key not in self.values:
            canonical = tensor.detach().contiguous()
            p.require(
                canonical.is_contiguous() and canonical.shape == tensor.shape,
                "canonical_save.exact_native_pack_layout",
            )
            self.values[key] = (canonical, signature(canonical))
            if canonical.untyped_storage()._cdata != tensor.untyped_storage()._cdata:
                self.extra_storage[canonical.untyped_storage()._cdata] = (
                    canonical.untyped_storage().nbytes()
                )
        result, expected_result = self.values[key]
        p.require(signature(result) == expected_result, "canonical_save.shared_layout_not_mutated")
        return result

    @property
    def extra_bytes(self):
        return sum(self.extra_storage.values())


class CanonicalSavedTensorStore(SavedTensorStore):
    def __init__(self, model, *, bank=None, **kwargs):
        super().__init__(model, retain_frozen=True, **kwargs)
        self.bank = bank if bank is not None else FrozenLayoutBank(model)
        p.require(self.bank.model is model, "canonical_save.same_model_owner")

    def pack(self, tensor):
        packed = super().pack(tensor)
        if packed.frozen:
            packed.value = self.bank.take(tensor, packed.owner)
            packed.source = signature(packed.value)
        else:
            saved = packed.value[1]
            amount, pinned = saved.untyped_storage().nbytes(), saved.is_pinned()
            self.bank.live_host += amount
            self.bank.peak_host = max(self.bank.peak_host, self.bank.live_host)
            if pinned:
                self.bank.live_pinned += amount
                self.bank.peak_pinned = max(self.bank.peak_pinned, self.bank.live_pinned)
            weakref.finalize(packed, self.bank.release, amount, pinned)
        return packed

    def report(self):
        return {
            **super().report(),
            "retained_backward_layout": "native save_on_cpu contiguous",
            "unique_canonical_weight_views": len(self.bank.values),
            "extra_resident_canonical_weight_bytes": self.bank.extra_bytes,
            "copied_per_save_event": False,
            "all_nested_stores_maximum_live_host_bytes": self.bank.peak_host,
            "all_nested_stores_live_host_bytes": self.bank.live_host,
            "all_nested_stores_maximum_live_pinned_bytes": self.bank.peak_pinned,
        }
