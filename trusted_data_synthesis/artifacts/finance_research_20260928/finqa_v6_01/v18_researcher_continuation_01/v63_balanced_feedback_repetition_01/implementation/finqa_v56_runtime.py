"""Bounded capacity deferral around unchanged V54 lifetime resource limits.

Insufficient idle capacity is a preflight observation, never a passed scientific
boundary. Only this process's reclaimable allocator cache is released. A fresh
passing observation is required before work; the historical allocated/RSS peaks
are never reset. Exhausted waiting yields the worker to the external scheduler.
"""

from __future__ import annotations

import gc
import time
from contextlib import contextmanager

import finqa_v54_runtime as original

GIB = original.GIB
resource_policy = original.resource_policy
worker_environment = original.worker_environment
inventory, host_memory, process_memory, birth = (
    original.inventory, original.host_memory, original.process_memory, original.birth,
)
GPU_UUIDS, CPU_AFFINITY = original.GPU_UUIDS, original.CPU_AFFINITY
MINIMUM_FREE_GIB, HOST_STARTUP_GIB = original.MINIMUM_FREE_GIB, original.HOST_STARTUP_GIB
ExplicitStop = original.ExplicitStop
require = original.require
now, checked, publish, entry, file_ref, read_ref, digest = (
    original.now, original.checked, original.publish, original.entry,
    original.file_ref, original.read_ref, original.digest,
)
REPO, V18, ROOT = original.REPO, original.V18, original.ROOT / "automatic_recovery_01"


def resource_recovery_policy():
    return dict(
        schema="v56_actual_durable_resource_recovery.v1",
        maximum_single_capacity_wait_seconds=60.0,
        capacity_poll_seconds=2.0,
        release_only_own_reclaimable_cache_before_boundary_recheck=True,
        failed_preflight_is_not_a_passed_scientific_boundary=True,
        scientific_call_requires_fresh_passing_boundary=True,
        historical_allocated_and_RSS_peak_reset_allowed=False,
        resource_wait_yields_device_and_worker_slot=True,
        lifetime_hard_peak_failure_requires_process_exit=True,
        automatic_restart_only_after_actual_exit_and_complete_durable_audit=True,
        new_UNKNOWN_provider_call_blocks_automatic_restart=True,
        stop_signal_blocks_automatic_restart=True,
        repeat_complete_task_response_optimizer_or_feedback_allowed=False,
        allowed_actual_io_errnos=[5, 11, 28, 116],
        uncommitted_failed_work_recalculation_is_explicit_overhead=True,
        mathematical_and_resource_hard_limits_unchanged=True,
    )


class ResourceDeferred(original.ResourceGateError):
    """Known capacity shortage before further work; resume needs durable audit."""

    def __init__(self, message, observation):
        super().__init__(message)
        self.resource_observation = observation
        self.resource_category = observation.get("resource_category", "capacity")


class LifetimeResourceFailure(original.ResourceGateError):
    """A real lifetime hard gate failed; this process may not continue."""

    def __init__(self, message, observation):
        super().__init__(message)
        self.resource_observation = observation
        self.resource_category = observation.get("resource_category", "lifetime_hard_gate")


class R3CapacityError(ResourceDeferred):
    """Actual original R3 physical-free/KV capacity predicates did not admit work."""


class ResourceGuard(original.ResourceGuard):
    def __init__(self, root, job, gpu_index, *, torch_module=None):
        from pathlib import Path
        protocol = checked(Path(root) / "protocol/record.json")
        require(protocol.get("resource_recovery_policy") == resource_recovery_policy(),
                "V56 bounded deferral requires its independently registered policy")
        super().__init__(root, job, gpu_index, torch_module=torch_module)
        self.preflight_observations = []
        self.deferred_observation = None
        self._capacity_wait_active = False
        self._startup_wait_deadline = self._began + 60.0

    def _observe_host_capacity(self):
        host = self._host()
        if host["peak_rss_bytes"] > host["rss_limit_bytes"]:
            self.violation = dict(resource_category="host_RSS_lifetime_peak", at=original.now(), host=host)
            self._record(self.violation)
            return False
        if not host["passed"]:
            if self._capacity_wait_active:
                self._publish_preflight(dict(resource_category="host_available_preflight",
                    at=original.now(), host=host), status="WAITING")
                return True
            # A reserve failure observed while actual work is in flight is
            # retained as a failure and requires exiting this process.
            self.violation = dict(resource_category="host_available_during_work", at=original.now(), host=host)
            self._record(self.violation)
            return False
        return True

    def _host_sampler(self):
        while not self._thread_stop.wait(1.0):
            try:
                if not self._observe_host_capacity():
                    return
            except BaseException as error:
                self.violation = dict(kind="host_observation_failed", at=original.now(),
                                      error_type=type(error).__name__, error=str(error))
                self._record(self.violation)
                return

    def _publish_preflight(self, observation, *, status):
        value = dict(observation, event="v56_capacity_preflight", status=status,
                     accepted_scientific_boundary=False,
                     historical_peaks_preserved=True)
        self.preflight_observations.append(value)
        self._record(value)
        return value

    def _defer(self, observation):
        self.deferred_observation = self._publish_preflight(observation, status="DEFERRED")
        error = R3CapacityError if observation.get("resource_category") == "R3_capacity" else ResourceDeferred
        raise error("bounded capacity wait exhausted before further scientific work", self.deferred_observation)

    def _wait_until_capacity(self, *, cuda_initialized):
        start = time.monotonic()
        minimum = MINIMUM_FREE_GIB[self.kind] * GIB
        while True:
            if self.stop.requested:
                raise ExplicitStop("explicit stop during V56 pre-scientific resource wait")
            rows = {int(row["index"]): row for row in inventory()}
            require(self.gpu in rows and rows[self.gpu]["uuid"] == GPU_UUIDS[str(self.gpu)],
                    "physical GPU identity changed while awaiting capacity")
            host = self._host()
            if host["peak_rss_bytes"] > host["rss_limit_bytes"]:
                self.violation = dict(resource_category="host_RSS_lifetime_peak", at=original.now(), host=host)
                self._record(self.violation)
                raise LifetimeResourceFailure("historical RSS limit exceeded before model loading", self.violation)
            if cuda_initialized:
                require(self.torch.cuda.memory_allocated() == 0,
                        "pre-model resource wait cannot contain scientific CUDA tensors")
                free = int(self.torch.cuda.mem_get_info()[0])
                required = max(2 * GIB, minimum - 3 * GIB)
            else:
                free, required = int(rows[self.gpu]["free_mib"] * 1024 ** 2), minimum
            value = dict(at=original.now(), label="pre_model_capacity" if cuda_initialized else "pre_CUDA_capacity",
                         resource_category="startup_capacity", gpu_index=self.gpu,
                         free_bytes=free, required_free_bytes=required, host=host,
                         cuda_initialized=cuda_initialized, elapsed_seconds=time.monotonic() - start)
            if host["passed"] and free >= required:
                self._record(dict(value, event="resource_admitted"))
                return
            self._publish_preflight(value, status="WAITING")
            if time.monotonic() >= self._startup_wait_deadline:
                self._defer(value)
            time.sleep(min(2.0, max(0, self._startup_wait_deadline - time.monotonic())))

    def _sample(self, label, boundary, context):
        cuda = self.torch.cuda
        cuda.synchronize()
        free, total = cuda.mem_get_info()
        host = self._host()
        return dict(at=original.now(), label=str(label), boundary=bool(boundary),
                    allocated_bytes=int(cuda.memory_allocated()), reserved_bytes=int(cuda.memory_reserved()),
                    peak_allocated_bytes=int(cuda.max_memory_allocated()),
                    peak_reserved_bytes=int(cuda.max_memory_reserved()),
                    free_bytes=int(free), total_bytes=int(total), host=host,
                    stop_requested=self.stop.requested,
                    context={key: value for key, value in context.items()
                             if isinstance(value, (str, int, float, bool, type(None)))})

    def _hard_gates(self, value):
        value["allocated_pass"] = value["peak_allocated_bytes"] <= 76 * GIB
        if not value["allocated_pass"] or value["host"]["peak_rss_bytes"] > value["host"]["rss_limit_bytes"]:
            value.update(passed=False, free_pass=value["free_bytes"] >= 2 * GIB,
                         resource_category="allocated_lifetime_peak" if not value["allocated_pass"] else "host_RSS_lifetime_peak")
            self.violation = value
            self.observations.append(value)
            self._record(value)
            raise LifetimeResourceFailure("V56 lifetime allocated/RSS hard peak exceeded", value)

    def ensure_capacity(self, label, *, boundary=True, required_free_bytes=2 * GIB,
                        required_own_available_bytes=None, **context):
        if self.violation is not None:
            raise LifetimeResourceFailure("an existing V56 resource violation cannot be cleared", self.violation)
        if self.stop.requested and self.job.get("stage") != "replay_C05":
            raise ExplicitStop("explicit stop before next scientific operation")
        first = time.monotonic()
        deadline = first + 60.0
        waiting = False
        try:
            while True:
                if self.violation is not None:
                    raise LifetimeResourceFailure("an observed resource failure cannot turn into a passing boundary", self.violation)
                value = self._sample(label, boundary, context)
                self._hard_gates(value)
                available = value["free_bytes"] + max(0, value["reserved_bytes"] - value["allocated_bytes"])
                free_pass = not boundary or value["free_bytes"] >= required_free_bytes
                capacity_pass = required_own_available_bytes is None or available >= required_own_available_bytes
                value.update(free_pass=free_pass, passed=free_pass and capacity_pass and value["host"]["passed"])
                if value["passed"]:
                    # Only this fresh observation admits the next operation.
                    self.observations.append(value)
                    self._record(value)
                    return value
                value.update(resource_category="R3_capacity" if required_own_available_bytes is not None else "boundary_capacity",
                             required_free_bytes=required_free_bytes,
                             required_own_available_bytes=required_own_available_bytes,
                             own_available_bytes=available)
                self._publish_preflight(value, status="WAITING")
                if self.stop.requested:
                    raise ExplicitStop("explicit stop during V56 scientific-boundary resource wait")
                if not waiting:
                    # This affects allocator storage only. It does not clear
                    # live tensors, touch another process, or reset any peak.
                    waiting = True
                    self._capacity_wait_active = True
                    gc.collect()
                    self.torch.cuda.empty_cache()
                    continue
                if time.monotonic() >= deadline:
                    self._defer(value)
                time.sleep(min(2.0, max(0, deadline - time.monotonic())))
        finally:
            self._capacity_wait_active = False
            if waiting:
                self.wait_seconds += time.monotonic() - first

    def check(self, label, boundary=True, **context):
        original_response = context.get("response_backend_observation")
        if isinstance(original_response, dict) and original_response.get("phase") == "after_response":
            # The original R3 method checks this already measured snapshot
            # after calling its monitor. Later cache cleanup cannot turn that
            # historical failed boundary into a passed one.
            peak = original_response["torch_peak_allocated_bytes"]
            free = original_response["device_free_bytes_at_response_boundary"]
            if peak > 76 * GIB:
                self.violation = dict(at=original.now(), resource_category="allocated_lifetime_peak",
                    peak_allocated_bytes=peak, free_bytes=free, boundary=True,
                    original_R3_response_observation=original_response)
                self._record(self.violation)
                raise LifetimeResourceFailure("original R3 response lifetime peak failed", self.violation)
            if free < 2 * GIB:
                observation = dict(at=original.now(), resource_category="R3_capacity",
                    label="original_R3_after_response", boundary=True, passed=False,
                    peak_allocated_bytes=peak, free_bytes=free, required_free_bytes=2 * GIB,
                    original_R3_response_observation=original_response,
                    completed_response_not_yet_accumulated=True)
                self.deferred_observation = self._publish_preflight(observation, status="FAILED_ORIGINAL_BOUNDARY")
                raise R3CapacityError("original R3 response free boundary requires cold durable restore",
                                      self.deferred_observation)
        return self.ensure_capacity(label, boundary=boundary, **context)

    def prepare_replay_response(self, session, model, prompt_length, response_length):
        import finqa_v32_replay_variants as variants

        kv = variants.estimate_complete_kv_bytes(model, prompt_length, response_length)
        require(kv <= session.full_kv_budget_bytes == 8 * GIB
                and session.bank.resident_limit == 2 * GIB
                and session.bank.activation_resident_limit == 16 * GIB,
                "registered original R3 full/saved-KV and activation budgets changed")
        incremental = kv + session.bank.resident_limit + session.bank.activation_resident_limit
        return self.ensure_capacity("before_actual_R3_response", boundary=True,
                                    required_free_bytes=2 * GIB + kv + session.bank.resident_limit,
                                    required_own_available_bytes=2 * GIB + incremental,
                                    estimated_incremental_bytes=incremental)

    def report(self):
        report = super().report()
        report.update(
            all_gates_passed=report["all_gates_passed"] and self.deferred_observation is None,
            preflight_shortages=len(self.preflight_observations),
            preflight_shortages_not_reclassified_as_pass=True,
            deferred_observation=self.deferred_observation,
            maximum_single_capacity_wait_seconds=60.0,
            own_cache_release_does_not_reset_historical_peak=True,
        )
        return report


@contextmanager
def execution_context(root, job, gpu_index):
    with ResourceGuard(root, job, gpu_index) as guard:
        yield guard
