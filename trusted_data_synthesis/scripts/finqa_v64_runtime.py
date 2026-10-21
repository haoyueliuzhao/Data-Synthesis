"""Worker-local native CUDA cache protection for the unchanged V63 science.

No CUDA is initialized on import. Only a cold, registered V64 worker may warm
its own allocator, after the real replay model and virtual parameters exist.
The cache is reusable storage, not device exclusivity or an OOM guarantee.
"""
from __future__ import annotations

from contextlib import contextmanager
import gc
from pathlib import Path
import sys
from types import ModuleType

import finqa_v64_binding as binding

reference = binding.source_module("finqa_v63_runtime")
reference_worker = binding.source_module("finqa_v63_worker")
ROOT, SCIENTIFIC_ROOT = binding.ROOT, binding.SCIENTIFIC_ROOT
GIB = 1024 ** 3
WARM_LIMIT_BYTES = 16 * GIB
WARM_RAW_FREE_BYTES = 14 * GIB
WARM_PEAK_MARGIN_BYTES = 64 * 1024 ** 2
WARM_ALIGNMENT_BYTES = 2 * 1024 ** 2
require = binding.require


def memory_protection_policy():
    return dict(
        schema="v64_worker_local_native_cache_protection.v1",
        scientific_root=str(SCIENTIFIC_ROOT),
        protected_phase="replay",
        allocator_backend="native",
        expandable_segments=False,
        warm_once_per_cold_worker=True,
        warm_position="first_prepare_replay_response_after_model_and_theta_residency",
        maximum_incremental_warm_allocation_bytes=WARM_LIMIT_BYTES,
        prewarm_planning_physical_free_bytes=WARM_RAW_FREE_BYTES,
        planning_full_KV_plus_saved_KV_plus_boundary_bytes=12 * GIB,
        additional_planning_free_margin_bytes=2 * GIB,
        planning_allocated_peak_margin_bytes=WARM_PEAK_MARGIN_BYTES,
        warm_alignment_bytes=WARM_ALIGNMENT_BYTES,
        partial_or_zero_warm_is_explicit=True,
        allocation="torch.empty_uint8_cuda0_without_random_values_or_model_calls",
        live_warm_tensor_released_before_scientific_call=True,
        warm_counts_in_unchanged_76GiB_lifetime_peak=True,
        peak_resets_after_loading=0,
        routine_cleanup="gc_and_original_resource_gates_without_empty_cache",
        capacity_cleanup="own_cache_release_only_if_original_physical_free_predicate_fails",
        inherited_R3_raw_free_and_own_available_checks_unchanged=True,
        final_process_cleanup_releases_own_cache=True,
        cached_bytes_are_estimates_not_contiguous_capacity_guarantees=True,
        native_allocator_may_release_cache_on_allocation_failure=True,
        other_process_control=False,
        external_holder=False,
        device_exclusivity_guaranteed=False,
        scientific_math_dose_state_and_existing_hard_gates_unchanged=True,
    )


resource_protection_policy = memory_protection_policy


def planned_warm_bytes(*, free_bytes, allocated_bytes):
    """Conservative reservation plan; fresh observed gates still decide admission."""
    require(type(free_bytes) is int and free_bytes >= 0
            and type(allocated_bytes) is int and allocated_bytes >= 0,
            "actual nonnegative integer capacity observations required")
    amount = min(WARM_LIMIT_BYTES,
                 max(0, free_bytes - WARM_RAW_FREE_BYTES),
                 max(0, 76 * GIB - allocated_bytes - WARM_PEAK_MARGIN_BYTES))
    return amount // WARM_ALIGNMENT_BYTES * WARM_ALIGNMENT_BYTES


def _private_deferral():
    """Bind the verified original deferral to one explicit cleanup substitution."""
    original = binding.source_module("finqa_v56_runtime")
    source = Path(original.__file__).read_text()
    substitutions = (
        ("import finqa_v54_runtime as original",
         "import _v64_original_resource_base as original", 1),
        ('self.job.get("stage") != "replay_C05"',
         'self.job.get("stage") not in ("replay_C1", "replay_C05")', 1),
        ("                    gc.collect()\n                    self.torch.cuda.empty_cache()",
         "                    self._capacity_cleanup(value, free_pass=free_pass)", 1),
    )
    for before, after, count in substitutions:
        require(source.count(before) == count,
                "frozen resource cleanup adapter structure changed")
        source = source.replace(before, after)
    name = "_v64_private_resource_deferral"
    module = ModuleType(name)
    module.__file__ = str(Path(original.__file__).resolve())
    module.__package__ = ""
    sys.modules["_v64_original_resource_base"] = reference._base
    sys.modules[name] = module
    exec(compile(source, module.__file__ + "::V64_cache_cleanup", "exec"), module.__dict__)
    # The unchanged audit recognizes the actual original exception classes.
    module.ExplicitStop = reference.ExplicitStop
    module.LifetimeResourceFailure = reference.LifetimeResourceFailure
    return module


_durable = _private_deferral()
ExplicitStop = reference.ExplicitStop
ResourceGateError = reference.ResourceGateError
ResourceDeferred = reference.ResourceDeferred
LifetimeResourceFailure = reference.LifetimeResourceFailure
R3CapacityError = reference.R3CapacityError


class ResourceGuard(reference.ResourceGuard):
    ensure_capacity = _durable.ResourceGuard.ensure_capacity

    def __init__(self, root, job, gpu_index, *, torch_module=None):
        import finqa_v64_registration as registration

        require(Path(root).resolve() == SCIENTIFIC_ROOT.resolve(),
                "V64 resource guard requires the original scientific root")
        self.control_protocol = registration.checked_protocol(ROOT)
        require(self.control_protocol["memory_protection_policy"] == memory_protection_policy(),
                "registered allocator protection policy changed")
        self._warm_attempted = False
        self._warm_allocation_bytes = 0
        self._warm_status = "NOT_ATTEMPTED" if job.get("kind") == "replay" else "NOT_APPLICABLE"
        self._warm_receipt = None
        self._cache_release_count = 0
        self._cache_retained_wait_count = 0
        self._protection_events = []
        super().__init__(root, job, gpu_index, torch_module=torch_module)

    def _protection_event(self, kind, **body):
        value = dict(at=reference.now(), event=kind,
                     control_protocol_id=self.control_protocol["id"],
                     job_id=self.job_id, gpu_index=self.gpu, **body)
        self._protection_events.append(value)
        self._record(value)
        return value

    def _capacity_cleanup(self, observation, *, free_pass):
        gc.collect()
        if not free_pass:
            self._cache_release_count += 1
            self._protection_event("v64_protection_released_for_physical_free",
                reason="original_physical_free_preflight_failed",
                original_failed_preflight=observation,
                release_only_own_unused_cache=True,
                next_operation_requires_fresh_original_gates=True)
            self.torch.cuda.empty_cache()
        else:
            self._cache_retained_wait_count += 1
            self._protection_event("v64_cache_retained_during_capacity_wait",
                reason="physical_free_predicate_passed_cache_release_adds_no_own_capacity",
                original_failed_preflight=observation,
                next_operation_requires_fresh_original_gates=True)

    def _warm_replay_cache(self):
        if self._warm_attempted:
            return
        require(self.kind == "replay", "only the registered replay stage is prewarmed")
        if self.stop.requested:
            raise ExplicitStop("explicit stop before worker-local cache prewarm")
        before = self.ensure_capacity("v64_before_replay_cache_warm", boundary=True)
        require(self.torch.cuda.memory.get_allocator_backend() == "native",
                "registered native allocator required for reusable cache")
        amount = planned_warm_bytes(free_bytes=before["free_bytes"],
                                    allocated_bytes=before["allocated_bytes"])
        self._warm_attempted = True
        self._warm_status = "WARMING"
        self._protection_event("v64_cache_warm_started", requested_bytes=amount,
            maximum_bytes=WARM_LIMIT_BYTES, before=before,
            model_or_rng_call=False, extra_scientific_response=False)
        temporary = None
        try:
            try:
                if amount:
                    temporary = self.torch.empty(amount, dtype=self.torch.uint8, device="cuda:0")
                    self._warm_allocation_bytes = amount
                    self.torch.cuda.synchronize()
            finally:
                # Release the tensor, not the allocator cache. No live ballast
                # competes with the model's following allocations.
                del temporary
            after = self.ensure_capacity("v64_after_replay_cache_warm", boundary=True,
                warm_allocation_bytes=self._warm_allocation_bytes)
            self._warm_status = "FULL" if amount == WARM_LIMIT_BYTES else "PARTIAL" if amount else "ZERO"
            if self.stop.requested:
                raise ExplicitStop("explicit stop after worker-local cache prewarm")
            receipt = dict(
                schema="v64_actual_worker_local_cache_warm.v1",
                control_protocol_id=self.control_protocol["id"],
                scientific_protocol_id=self.protocol["id"],
                job_id=self.job_id, gpu_index=self.gpu,
                requested_warm_bytes=amount,
                actual_warm_allocation_bytes=self._warm_allocation_bytes,
                status=self._warm_status, before=before, after=after,
                planning_free_headroom_observed_after=after["free_bytes"] >= WARM_RAW_FREE_BYTES,
                planning_margin_is_not_a_new_scientific_gate=True,
                estimated_reusable_bytes_after=max(0, after["reserved_bytes"] - after["allocated_bytes"]),
                actual_reserved_growth_bytes=after["reserved_bytes"] - before["reserved_bytes"],
                cache_releases_during_warm=self._cache_release_count,
                live_warm_tensor_remaining=False,
                model_or_rng_call=False, extra_scientific_response=False,
                original_peak_stats_not_reset=True,
                contiguous_reuse_or_future_free_guaranteed=False)
            destination = (ROOT / "resources" / self.job_id / self.directory.name
                           / "cache_warm/record.json")
            binding.publish(destination, receipt)
            self._warm_receipt = binding.entry(destination)
            self._protection_event("v64_cache_warm_finished", status=self._warm_status,
                                   actual_warm_allocation_bytes=self._warm_allocation_bytes,
                                   receipt=self._warm_receipt)
        except BaseException as error:
            self._warm_status = "FAILED"
            self._protection_event("v64_cache_warm_failed",
                actual_warm_allocation_bytes=self._warm_allocation_bytes,
                error_type=type(error).__name__, error=str(error),
                no_scientific_call_admitted=True)
            raise

    def prepare_replay_response(self, session, model, prompt_length, response_length):
        # This method is invoked only after model/theta setup and immediately
        # before the original backend call. It never changes a model argument.
        self._warm_replay_cache()
        return super().prepare_replay_response(session, model, prompt_length, response_length)

    def report(self):
        value = super().report()
        original_pre_model_warm = value["warm_allocation_bytes"]
        value.update(
            control_protocol_id=self.control_protocol["id"],
            inherited_pre_model_warm_allocation_bytes=original_pre_model_warm,
            warm_allocation_bytes=self._warm_allocation_bytes,
            resource_protection=dict(
                policy=memory_protection_policy(),
                warm_attempted=self._warm_attempted, status=self._warm_status,
                actual_warm_allocation_bytes=self._warm_allocation_bytes,
                receipt=self._warm_receipt, cache_release_count=self._cache_release_count,
                cache_retained_wait_count=self._cache_retained_wait_count,
                protection_degraded=self._cache_release_count > 0,
                events=list(self._protection_events),
                future_capacity_or_exclusivity_guaranteed=False))
        return value


class ScientificMonitor(reference_worker.ScientificMonitor):
    def clear_unused(self, label):
        before = self.snapshot(label + ".before_cleanup", boundary=False)
        gc.collect()
        after = self.snapshot(label + ".after_cleanup", boundary=True)
        return dict(before=before, after=after, routine_allocator_cache_retained=True)


@contextmanager
def execution_context(root, job, gpu_index):
    with ResourceGuard(root, job, gpu_index) as guard:
        yield guard


def controller_runtime():
    return reference.controller_runtime()


def __getattr__(name):
    return getattr(reference, name)
