"""Same-process native-allocator reservation; no mathematical backend changes."""

from __future__ import annotations

import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

GIB = 1024**3
MIB = 1024**2
ANCHOR_BYTES = 2 * MIB
ALLOCATED_LIMIT_BYTES = 76 * GIB
FREE_RESERVE_BYTES = 2 * GIB
SCHEMA = "v52_adaptive_same_process_native_segment_reservation.v1"
FAILURE_SCHEMA = "v52_r3_internal_capacity_failure.v1"
RETRY_SCHEMA = "v52_r3_changed_capacity_required.v1"
WAIT_SCHEMA = "v52_pre_scientific_resource_wait.v1"
PHYSICAL_FAILURE_SCHEMA = "v52_observed_physical_resource_failure.v1"
WAIT_REASONS = frozenset(
    {
        "physical_boundary_free_exhausted",
        "post_cuda_capacity_below_admission_allowance",
        "warm_allocation_cuda_out_of_memory",
        "anchor_allocation_cuda_out_of_memory",
    }
)
PHASE_MINIMUM_FREE_GIB = {
    "class": 24,
    "train": 26,
    "replay_R3": 56,
    "virtual_existing": 22,
    "virtual_first_sampling": 22,
    "distribution": 22,
    "generate": 24,
}
PRODUCTION = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/"
    "v25_training_replication_01/production_resume_01"
)
EVIDENCE_REFS = [
    dict(
        path=str(PRODUCTION / "fixed_gpu_reservation_evidence_01/record.json"),
        sha256="b6acf416294b4ec793d6e3d8b29cf92d9176c4dddca3c870fd4d8bb4ab2e1d64",
        id="a5c0dc5a23df30bf8c7b2922fc3ca02cd4c67c3a347c0261380e521fa25f307d",
    ),
    dict(
        path=str(PRODUCTION / "host_memory_admission_evidence_01/record.json"),
        sha256="7a8fa852f8650d1b26161b83bd9c04413383ea26f7d48ba2a1ab209f2a6b7246",
        id="5e87ca240e266595c3dbf34bd9013cf61db961232209b5d94b34903447970ad0",
    ),
]


class ReservationAdmissionError(RuntimeError):
    """Reservation failed before scientific work; not a generic automatic retry."""


class R3CapacityError(RuntimeError):
    """An actual pre-response resource budget is insufficient; no forward began."""


class ReservationWaitStopped(RuntimeError):
    """An explicit stop interrupts pre-scientific capacity waiting."""


class ReservationPhysicalResourceError(RuntimeError):
    """A measured physical-free boundary failed after model loading began."""


def require(condition, message):
    if not condition:
        raise ReservationAdmissionError(message)


def policy_record():
    return dict(
        schema=SCHEMA,
        evidence_refs=[dict(row) for row in EVIDENCE_REFS],
        allocator_backend="native",
        allocator_configuration="backend:native,expandable_segments:False",
        torch_version="2.7.1+cu128",
        anchor_bytes=ANCHOR_BYTES,
        target_cap_bytes=72 * GIB,
        reservation_target="floor_GiB(min(72GiB,actual_post_CUDA_free-stage_headroom))",
        headroom_bytes_by_stage=dict(replay_R3=8 * GIB, other=4 * GIB),
        minimum_free_gib_by_phase=dict(PHASE_MINIMUM_FREE_GIB),
        post_CUDA_admission_allowance_bytes=3 * GIB,
        native_empty_cache_preserved=True,
        live_anchor_same_segment_proof_required=True,
        lifetime_allocated_limit_bytes=ALLOCATED_LIMIT_BYTES,
        actual_boundary_free_reserve_bytes=FREE_RESERVE_BYTES,
        warm_allocation_in_lifetime_peak=True,
        peak_reset_calls_before_first_allocation=1,
        subsequent_peak_resets_allowed=False,
        reserve_before_CPU_state_and_model_loading=True,
        R3_original_backend_source_and_hash_unchanged=True,
        R3_original_admission_predicates_unchanged=True,
        R3_before_each_response_empty_cache=True,
        R3_expected_full_KV_bytes=2 * GIB,
        R3_original_full_KV_limit_bytes=8 * GIB,
        R3_historical_before_response_allocated_upper_bytes=30665053696,
        R3_config_bound_KV_bytes=1526726656,
        R3_minimum_basis="historical before-response allocated + 20GiB + config KV + allowance",
        phase_peak_allocated_bytes=dict(
            class_=17356511232,
            train=20384589312,
            replay_R3=36125065728,
            virtual_point=17140014080,
            distribution=15384683520,
            generate=17723328512,
        ),
        historical_observations_are_not_guaranteed_upper_bounds=True,
        shared_external_growth_can_still_violate_physical_free=True,
        retained_only_within_one_cold_worker_lifetime=True,
        cross_stage_or_recovery_permanent_exclusivity_claimed=False,
        standalone_placeholder_process=False,
        total_worker_limit_removed=False,
        independent_total_worker_limit=2,
        pre_scientific_resource_wait=dict(
            schema=WAIT_SCHEMA,
            reasons=sorted(WAIT_REASONS),
            poll_seconds=2,
            same_process_reservation_lease_and_worker_slot_retained=True,
            no_new_deadline=True,
            other_device_dispatch_continues=True,
            sole_peak_reset_before_first_allocation=True,
            model_load_must_not_have_started=True,
            host_UUID_allocator_and_lifetime_peak_failures_are_not_waitable=True,
            actual_torch_cuda_OOM_only=True,
            OOM_required_capacity_growth_bytes=GIB,
            immutable_wait_events_and_interval_accounting=True,
        ),
        post_model_physical_resource_failure_schema=PHYSICAL_FAILURE_SCHEMA,
    )


def target_bytes(free_bytes, minimum_free_bytes, stage):
    require(type(free_bytes) is int and free_bytes >= 0, "invalid actual post-CUDA free bytes")
    require(
        free_bytes >= minimum_free_bytes - 3 * GIB,
        "post-CUDA capacity fell below the registered admission allowance",
    )
    headroom = (8 if stage == "replay_R3" else 4) * GIB
    target = min(72 * GIB, (free_bytes - headroom) // GIB * GIB)
    require(target >= GIB, "no usable same-process reservation fits the physical reserve")
    return target


def assess_r3_capacity(allocated, reserved, free, total, kv):
    for value in (allocated, reserved, free, total, kv):
        require(type(value) is int and value >= 0, "invalid R3 byte observation")
    require(reserved >= allocated and total >= free, "inconsistent R3 byte observation")
    reusable = reserved - allocated
    raw_required = 4 * GIB + kv
    required_available = 20 * GIB + kv
    required_capacity = allocated + required_available
    allocated_budget = allocated + 18 * GIB + kv
    required_dispatch = max(56 * GIB, math.ceil((required_capacity + 4 * GIB) / GIB) * GIB)
    recoverable = (
        kv <= 8 * GIB
        and raw_required <= 8 * GIB
        and allocated_budget <= ALLOCATED_LIMIT_BYTES
        and required_dispatch <= total
        and free + reserved + 4 * GIB <= total
    )
    condition = dict(
        schema=RETRY_SCHEMA,
        stage="replay_R3",
        required_dispatch_free_bytes=required_dispatch,
        failed_available_capacity_bytes=free + reserved,
        self_context_reclaim_allowance_bytes=3 * GIB,
        minimum_capacity_increase_bytes=4 * GIB,
        required_allocated_budget_bytes=allocated_budget,
        device_total_bytes=total,
        recoverable_when_capacity_changes=recoverable,
    )
    return dict(
        allocated_bytes=allocated,
        reserved_bytes=reserved,
        physical_free_bytes=free,
        device_total_bytes=total,
        estimated_complete_kv_bytes=kv,
        resident_kv_budget_bytes=2 * GIB,
        activation_resident_budget_bytes=16 * GIB,
        free_reserve_bytes=FREE_RESERVE_BYTES,
        allocated_limit_bytes=ALLOCATED_LIMIT_BYTES,
        reusable_bytes=reusable,
        available_bytes=free + reusable,
        raw_required_free_bytes=raw_required,
        required_available_bytes=required_available,
        required_device_capacity_bytes=required_capacity,
        required_allocated_budget_bytes=allocated_budget,
        physical_free_pass=free >= FREE_RESERVE_BYTES,
        raw_free_pass=free >= raw_required,
        available_pass=free + reusable >= required_available,
        allocated_pass=allocated < ALLOCATED_LIMIT_BYTES,
        original_full_KV_cap_pass=kv <= 8 * GIB,
        expected_KV_bound_pass=kv <= 2 * GIB,
        recoverable_when_capacity_changes=recoverable,
        retry_capacity_condition=condition,
    )


def check_retry_capacity(condition, inventory):
    """No unchanged-capacity cold retries; invalid or impossible conditions wait."""
    if not isinstance(condition, dict) or condition.get("schema") != RETRY_SCHEMA:
        return False
    expected = {
        "schema",
        "stage",
        "required_dispatch_free_bytes",
        "failed_available_capacity_bytes",
        "minimum_capacity_increase_bytes",
        "required_allocated_budget_bytes",
        "device_total_bytes",
        "recoverable_when_capacity_changes",
        "self_context_reclaim_allowance_bytes",
    }
    if (
        set(condition) != expected
        or condition["stage"] != "replay_R3"
        or condition["recoverable_when_capacity_changes"] is not True
    ):
        return False
    names = expected - {"schema", "stage", "recoverable_when_capacity_changes"}
    if any(type(condition[name]) is not int or condition[name] < 0 for name in names):
        return False
    if (
        condition["minimum_capacity_increase_bytes"] != 4 * GIB
        or condition["self_context_reclaim_allowance_bytes"] != 3 * GIB
        or condition["required_allocated_budget_bytes"] > ALLOCATED_LIMIT_BYTES
        or condition["required_dispatch_free_bytes"] > condition["device_total_bytes"]
    ):
        return False
    minimum = max(
        condition["required_dispatch_free_bytes"],
        condition["failed_available_capacity_bytes"] + 4 * GIB,
    )
    if not isinstance(inventory, (tuple, list)):
        return False
    for row in inventory:
        free = row.get("free_mib") if isinstance(row, dict) else None
        if type(free) in (int, float) and math.isfinite(free) and free * MIB >= minimum:
            return True
    return False


class Reservation:
    def __init__(
        self,
        torch,
        directory,
        plan,
        context_id,
        stage,
        gpu_index,
        *,
        control,
        stop_requested=lambda: False,
        memory_phase=None,
        clock=None,
        monotonic=None,
        sleep=None,
    ):
        self.torch, self.directory, self.plan = torch, Path(directory), plan
        self.context_id, self.stage, self.gpu_index = context_id, stage, gpu_index
        self.control = control
        self.anchor = None
        self.address = self.target = None
        self.started = self.closed = False
        self.reset_calls = self.response_calls = 0
        self.maximum_observed_KV_bytes = self.expected_KV_bound_exceedances = 0
        self.observations = []
        self._original_reset = None
        self.model_load_started = False
        self.wait_episodes = 0
        self.minimum_dispatch_free_bytes = None
        self.memory_phase = memory_phase or (
            "class"
            if stage.startswith("shard")
            else "virtual_existing"
            if stage == "virtual_point"
            else stage
        )
        self.stop_requested = stop_requested
        self.clock = time.time if clock is None else clock
        self.monotonic = time.monotonic if monotonic is None else monotonic
        self.sleep = time.sleep if sleep is None else sleep

    def common(self):
        return dict(
            protocol_id=self.plan["id"],
            context_id=self.context_id,
            stage=self.stage,
            gpu_index=self.gpu_index,
            gpu_uuid=self.plan["gpu_uuids"][str(self.gpu_index)],
            pid=os.getpid(),
            birth=self.control.birth(os.getpid()),
            at=self.control.now(),
        )

    def _observe(self, label):
        cuda = self.torch.cuda
        cuda.synchronize()
        free, total = cuda.mem_get_info()
        row = dict(
            label=label,
            allocated_bytes=int(cuda.memory_allocated()),
            reserved_bytes=int(cuda.memory_reserved()),
            peak_allocated_bytes=int(cuda.max_memory_allocated()),
            peak_reserved_bytes=int(cuda.max_memory_reserved()),
            physical_free_bytes=int(free),
            device_total_bytes=int(total),
        )
        require(
            all(type(value) is int and value >= 0 for key, value in row.items() if key != "label")
            and row["allocated_bytes"] <= row["reserved_bytes"] <= row["device_total_bytes"]
            and row["allocated_bytes"] <= row["peak_allocated_bytes"]
            and row["reserved_bytes"] <= row["peak_reserved_bytes"]
            and row["physical_free_bytes"] <= row["device_total_bytes"],
            "inconsistent actual CUDA byte observation",
        )
        self.observations.append(row)
        return row

    def _invariants(self, row, *, expected_allocated=None):
        require(
            row["peak_allocated_bytes"] <= ALLOCATED_LIMIT_BYTES,
            "lifetime allocated limit exceeded",
        )
        if expected_allocated is not None:
            require(
                row["allocated_bytes"] == expected_allocated,
                "CPU state loading allocated scientific CUDA tensors",
            )
        if self.started:
            require(row["reserved_bytes"] >= self.target, "anchored reservation was released")
            self.segment_proof()

    def snapshot(self, label, *, enforce=True, expected_allocated=None):
        row = self._observe(label)
        if enforce:
            self._invariants(row, expected_allocated=expected_allocated)
            if row["physical_free_bytes"] < FREE_RESERVE_BYTES:
                if not self.model_load_started:
                    row = self._wait_capacity(
                        "physical_boundary_free_exhausted",
                        row,
                        required_physical_free_bytes=FREE_RESERVE_BYTES,
                        expected_allocated=expected_allocated,
                    )
                else:
                    self.control.publish(
                        self.directory / "reservation/physical_resource_failure/record.json",
                        dict(
                            schema=PHYSICAL_FAILURE_SCHEMA,
                            **self.common(),
                            error_type="ReservationPhysicalResourceError",
                            reason="physical_boundary_free_exhausted",
                            observation=row,
                            required_physical_free_bytes=FREE_RESERVE_BYTES,
                            lifetime_allocated_limit_bytes=ALLOCATED_LIMIT_BYTES,
                            model_load_started=True,
                            proof_no_scientific_work=False,
                            allocator_anchor_and_lifetime_peak_invariants_passed=True,
                            reservation_admission=self.control.entry(
                                self.directory / "reservation/admission/record.json"
                            ),
                        ),
                    )
                    raise ReservationPhysicalResourceError("physical boundary reserve exhausted")
        elif self.started:
            require(row["reserved_bytes"] >= self.target, "anchored reservation was released")
        return row

    def _wait_capacity(
        self,
        reason,
        failed,
        *,
        required_physical_free_bytes,
        expected_allocated=None,
        required_available_capacity_bytes=0,
        requested_bytes=None,
        current_observation=None,
    ):
        # No generic ReservationAdmissionError is caught here: only exact measured
        # capacity predicates or a native CUDA OOM at our own allocation site enter.
        from finqa_v52_admission import POLICY_SCHEMA, _write_record

        require(
            reason in WAIT_REASONS and not self.model_load_started,
            "only proven pre-scientific capacity can wait",
        )
        self._invariants(
            failed, expected_allocated=(expected_allocated if current_observation is None else None)
        )
        if reason == "physical_boundary_free_exhausted":
            require(
                failed["physical_free_bytes"] < FREE_RESERVE_BYTES,
                "physical shortage evidence absent",
            )
        elif reason == "post_cuda_capacity_below_admission_allowance":
            require(
                failed["physical_free_bytes"] < required_physical_free_bytes,
                "post-CUDA shortage evidence absent",
            )
        else:
            require(
                type(requested_bytes) is int and requested_bytes > 0,
                "actual failed allocation size missing",
            )
        require(
            0 <= required_available_capacity_bytes <= failed["device_total_bytes"],
            "resource wait cannot satisfy the fixed device capacity",
        )
        self.wait_episodes += 1
        directory = self.directory / "reservation_wait" / f"episode{self.wait_episodes:04d}"
        require(not (directory / "status.json").exists(), "resource wait episode already exists")
        began_epoch, began = self.clock(), self.monotonic()
        last, sequence, row = (
            began,
            0,
            failed if current_observation is None else current_observation,
        )
        registered = self.common()
        registered.pop("at")
        require(registered["birth"] is not None, "resource wait process birth is unknown")
        host = process = gpu = None

        def emit(phase, *, error=None):
            nonlocal sequence, last
            observed_epoch, observed = self.clock(), self.monotonic()
            require(
                all(
                    type(value) in (int, float) and math.isfinite(value)
                    for value in (observed_epoch, observed, began_epoch, began)
                )
                and observed >= last,
                "resource wait clock reversed or invalid",
            )
            last = observed
            body = dict(
                schema=WAIT_SCHEMA,
                **registered,
                at=datetime.fromtimestamp(observed_epoch, timezone.utc).isoformat(),
                phase=phase,
                reason=reason,
                error=error,
                sequence=sequence,
                observed_epoch=observed_epoch,
                observed_monotonic=observed,
                started_epoch=began_epoch,
                waiting_started_epoch=began_epoch,
                waiting_started_monotonic=began,
                waiting_finished_monotonic=None if phase == "WAITING" else observed,
                waiting_finished_epoch=None if phase == "WAITING" else observed_epoch,
                waiting_seconds=observed - began,
                poll_seconds=2,
                deadline_epoch=None,
                cuda_initialized=True,
                wallclock_limits_removed=True,
                resource_wait_accounting_retained=True,
                worker_slot_retained=True,
                gpu_lease_retained=True,
                automatic_retry=False,
                model_load_started=False,
                proof_no_scientific_work=True,
                scientific_model_calls=0,
                API_calls=0,
                optimizer_commits=0,
                new_feedback_calls=0,
                actual_response_calls=0,
                target_bytes=self.target,
                anchor_held=self.started,
                lifetime_peak_reset_calls=self.reset_calls,
                minimum_dispatch_free_bytes=self.minimum_dispatch_free_bytes,
                memory_phase=self.memory_phase,
                gpu_admission_policy_schema=POLICY_SCHEMA,
                gpu_reservation_policy_schema=SCHEMA,
                failed_observation=failed,
                observation=row,
                required_physical_free_bytes=required_physical_free_bytes,
                required_available_capacity_bytes=required_available_capacity_bytes,
                requested_allocation_bytes=requested_bytes,
                host=host,
                process_memory=process,
                gpu=gpu,
                original_scientific_source_unchanged=True,
            )
            _write_record(directory / f"event{sequence:06d}/record.json", body, replace=False)
            _write_record(directory / "status.json", body, replace=True)
            sequence += 1

        def checks():
            nonlocal host, process, gpu
            require(
                not self.model_load_started and self.reset_calls == 1,
                "science or extra peak reset began during resource wait",
            )
            require(
                self.control.birth(os.getpid()) == registered["birth"],
                "resource wait process identity changed",
            )
            if self.stop_requested():
                raise ReservationWaitStopped("safe stop requested during CUDA resource wait")
            inventory = self.control.inventory()
            matching = [item for item in inventory if item.get("index") == self.gpu_index]
            require(
                len(matching) == 1 and matching[0].get("uuid") == registered["gpu_uuid"],
                "resource wait GPU UUID changed",
            )
            gpu = matching[0]
            host, process = self.control.host_memory(), self.control.process_memory(os.getpid())
            limit = (160 if self.stage.startswith("shard") else 192) * GIB
            require(
                isinstance(host, dict)
                and type(host.get("available_bytes")) is int
                and host["available_bytes"] >= 96 * GIB,
                "resource wait host RAM reserve failed",
            )
            require(
                isinstance(process, dict)
                and all(type(process.get(key)) is int for key in ("rss_bytes", "peak_rss_bytes"))
                and 0 <= process["rss_bytes"] <= process["peak_rss_bytes"] <= limit,
                "resource wait worker RSS limit failed",
            )
            self._invariants(row, expected_allocated=expected_allocated)
            if self.stop_requested():
                raise ReservationWaitStopped("safe stop requested during CUDA resource wait")

        try:
            checks()
            emit("WAITING")  # Preserve the measured failed boundary, never mark it passed.
            while True:
                self.sleep(2)
                row = self._observe(f"resource_wait:{reason}")
                checks()
                if (
                    row["physical_free_bytes"] >= required_physical_free_bytes
                    and row["physical_free_bytes"] + row["reserved_bytes"]
                    >= required_available_capacity_bytes
                ):
                    emit("READY")
                    return row
                emit("WAITING")
        except BaseException as error:
            emit(
                "STOPPED" if isinstance(error, ReservationWaitStopped) else "FAILED",
                error=dict(type=type(error).__name__, message=str(error)),
            )
            raise

    def mark_model_load_started(self):
        require(not self.model_load_started, "model loading may begin only once")
        self.verify_before_model_load()
        self.model_load_started = True
        self.control.publish(
            self.directory / "reservation/model_load_started/record.json",
            dict(
                schema="v52_reserved_model_load_started.v1",
                **self.common(),
                model_load_started=True,
                lifetime_peak_reset_calls=self.reset_calls,
            ),
        )

    def segment_proof(self):
        segments = [s for s in self.torch.cuda.memory_snapshot() if s["address"] == self.address]
        require(len(segments) == 1, "anchored native segment missing")
        segment = segments[0]
        require(
            segment["total_size"] == self.target
            and segment["active_size"] >= ANCHOR_BYTES
            and self.anchor.data_ptr() == self.address
            and not segment.get("is_expandable", False),
            "anchor does not retain the exact warmed native segment",
        )
        return {
            key: segment[key]
            for key in (
                "address",
                "total_size",
                "allocated_size",
                "active_size",
                "stream",
                "segment_type",
            )
            if key in segment
        }

    def start(self, minimum_free_bytes):
        require(
            not self.started and not self.torch.cuda.is_initialized(),
            "fresh CUDA reservation required",
        )
        require(self.torch.__version__ == "2.7.1+cu128", "unregistered allocator runtime")
        allowed = (None, "", "backend:native,expandable_segments:False")
        require(
            os.environ.get("PYTORCH_CUDA_ALLOC_CONF") in allowed
            and os.environ.get("PYTORCH_ALLOC_CONF") in (None, "")
            and os.environ.get("PYTORCH_NO_CUDA_MEMORY_CACHING") in (None, "", "0"),
            "unregistered native allocator environment",
        )
        require(
            self.torch.cuda.memory.get_allocator_backend() == "native", "native allocator required"
        )
        self._original_reset = self.torch.cuda.reset_peak_memory_stats
        self._original_reset()
        self.reset_calls = 1

        def no_more_reset(*_args, **_kwargs):
            raise ReservationAdmissionError("later lifetime peak reset is forbidden")

        # Protect the lifetime peak immediately, including every warming attempt.
        self.torch.cuda.reset_peak_memory_stats = no_more_reset
        self.minimum_dispatch_free_bytes = minimum_free_bytes
        require(
            self.torch.cuda.memory_allocated() == self.torch.cuda.memory_reserved() == 0,
            "reservation must precede all scientific CUDA allocations",
        )
        before = self.snapshot("before_reservation", expected_allocated=0)
        needed = max(FREE_RESERVE_BYTES, minimum_free_bytes - 3 * GIB)
        if before["physical_free_bytes"] < needed:
            before = self._wait_capacity(
                "post_cuda_capacity_below_admission_allowance",
                before,
                required_physical_free_bytes=needed,
                expected_allocated=0,
            )
        self.target = target_bytes(before["physical_free_bytes"], minimum_free_bytes, self.stage)
        cpu_rng, gpu_rng = self.torch.get_rng_state(), self.torch.cuda.get_rng_state()
        while True:
            warm = None
            allocation_site = "warm"
            requested_bytes = self.target
            try:
                warm = self.torch.empty(self.target, dtype=self.torch.uint8, device="cuda:0")
                warm.zero_()
                self.torch.cuda.synchronize()
                self.address = warm.data_ptr()
                self.snapshot("warm_allocation_in_lifetime_peak", expected_allocated=self.target)
                del warm
                warm = None
                allocation_site, requested_bytes = "anchor", ANCHOR_BYTES
                self.anchor = self.torch.empty(
                    ANCHOR_BYTES, dtype=self.torch.uint8, device="cuda:0"
                )
                break
            except self.torch.cuda.OutOfMemoryError:
                # Typed native allocator OOM only, in our pre-model allocation.
                # Release only this incomplete warm/anchor, not scientific tensors.
                failed = self._observe(f"{allocation_site}_allocation_cuda_out_of_memory")
                self._invariants(failed)
                require(
                    not self.started
                    and not self.model_load_started
                    and failed["allocated_bytes"] in (0, self.target, ANCHOR_BYTES),
                    "allocation OOM contains unregistered CUDA tensors",
                )
                warm = self.anchor = None
                self.torch.cuda.empty_cache()
                cleaned = self._observe("after_incomplete_reservation_cleanup")
                self._invariants(cleaned, expected_allocated=0)
                required_growth = failed["physical_free_bytes"] + failed["reserved_bytes"] + GIB
                ready = self._wait_capacity(
                    f"{allocation_site}_allocation_cuda_out_of_memory",
                    failed,
                    required_physical_free_bytes=needed,
                    required_available_capacity_bytes=required_growth,
                    requested_bytes=requested_bytes,
                    current_observation=cleaned,
                    expected_allocated=0,
                )
                require(
                    ready["allocated_bytes"] == 0, "incomplete warm allocation survived cleanup"
                )
                self.target = target_bytes(
                    ready["physical_free_bytes"], minimum_free_bytes, self.stage
                )
        require(self.anchor.data_ptr() == self.address, "anchor failed to reuse the warmed segment")
        self.started = True
        self.torch.cuda.empty_cache()
        proof = self.segment_proof()
        after = self.snapshot(
            "reservation_held_after_original_empty_cache", expected_allocated=ANCHOR_BYTES
        )
        require(
            self.torch.equal(cpu_rng, self.torch.get_rng_state())
            and self.torch.equal(gpu_rng, self.torch.cuda.get_rng_state()),
            "reservation consumed scientific RNG",
        )

        return self.control.publish(
            self.directory / "reservation/admission/record.json",
            dict(
                schema=SCHEMA,
                **self.common(),
                target_bytes=self.target,
                minimum_dispatch_free_bytes=minimum_free_bytes,
                anchor_bytes=ANCHOR_BYTES,
                before=before,
                after=after,
                segment=proof,
                cuda_initialized=True,
                before_CPU_state_and_model_load=True,
                scientific_model_calls=0,
                cpu_and_cuda_rng_unchanged=True,
                original_empty_cache_called=True,
                lifetime_peak_reset_calls=1,
                policy=self.plan["gpu_reservation_policy"],
            ),
        )

    def verify_before_model_load(self):
        require(not self.model_load_started, "pre-model guard called after model loading began")
        return self.snapshot(
            "after_CPU_state_loading_before_model", expected_allocated=ANCHOR_BYTES
        )

    def _checkpoint(self):
        candidates = sorted((self.directory / "checkpoints").glob("response*/record.json"))
        if candidates:
            reference = self.control.entry(candidates[-1])
            value = self.control.checked(candidates[-1])
            return reference, value["cursor"]
        inherited = self.directory / "inherited_prefix/record.json"
        if inherited.exists():
            value = self.control.checked(inherited)
            return value["parent_checkpoint"], value["inherited_response_count"]
        return None, None

    def before_r3(self, session, model, prompt, targets, backend):
        # Only unanchored cached segments can be returned; both original R3
        # capacity predicates still execute unchanged immediately afterwards.
        self.torch.cuda.empty_cache()
        observed = self.snapshot("before_original_R3_resource_checks", enforce=False)
        kv = backend.v32.estimate_complete_kv_bytes(model, len(prompt), len(targets))
        self.maximum_observed_KV_bytes = max(self.maximum_observed_KV_bytes, kv)
        self.expected_KV_bound_exceedances += int(kv > 2 * GIB)
        assessment = assess_r3_capacity(
            observed["allocated_bytes"],
            observed["reserved_bytes"],
            observed["physical_free_bytes"],
            observed["device_total_bytes"],
            kv,
        )
        assessment["peak_allocated_bytes"] = observed["peak_allocated_bytes"]
        assessment["lifetime_allocated_pass"] = (
            observed["peak_allocated_bytes"] <= ALLOCATED_LIMIT_BYTES
        )
        if not assessment["lifetime_allocated_pass"]:
            assessment["recoverable_when_capacity_changes"] = False
            assessment["retry_capacity_condition"]["recoverable_when_capacity_changes"] = False
        require(
            session.bank.resident_limit == 2 * GIB
            and session.bank.activation_resident_limit == 16 * GIB
            and session.full_kv_budget_bytes == 8 * GIB,
            "registered R3 storage budgets differ",
        )
        passed = all(
            assessment[key]
            for key in (
                "physical_free_pass",
                "raw_free_pass",
                "available_pass",
                "allocated_pass",
                "original_full_KV_cap_pass",
                "lifetime_allocated_pass",
            )
        )
        if passed:
            return
        checkpoint, cursor = self._checkpoint()
        source = backend.source_binding()
        body = dict(
            schema=FAILURE_SCHEMA,
            **self.common(),
            error_type="R3CapacityError",
            before_scientific_response=True,
            failed_response_forward_calls=0,
            successful_response_calls_this_worker=self.response_calls,
            latest_actual_checkpoint_ref=checkpoint,
            latest_actual_checkpoint_cursor=cursor,
            backend_source_binding=source,
            backend_source_binding_digest=self.control.digest(source),
            reservation_admission=self.control.entry(
                self.directory / "reservation/admission/record.json"
            ),
            assessment=assessment,
            recoverable_when_capacity_changes=assessment["recoverable_when_capacity_changes"],
            retry_capacity_condition=assessment["retry_capacity_condition"],
            reason="original_R3_resource_budget_insufficient_before_forward",
            original_R3_predicates_not_bypassed=True,
        )
        self.control.publish(self.directory / "reservation/r3_capacity_failure/record.json", body)
        raise R3CapacityError("R3 resource capacity is insufficient before the next response")

    def report(self):
        self.snapshot("reservation_final_boundary")
        return self.control.publish(
            self.directory / "reservation/result/record.json",
            dict(
                schema=SCHEMA,
                **self.common(),
                status="COMPLETE",
                target_bytes=self.target,
                anchor_bytes=ANCHOR_BYTES,
                segment=self.segment_proof(),
                observations=list(self.observations),
                lifetime_peak_reset_calls=self.reset_calls,
                reservation_held_through_final_scientific_boundary=True,
                original_empty_cache_unchanged=True,
                original_R3_source_and_backend_hash_unchanged=True,
                maximum_observed_KV_bytes=self.maximum_observed_KV_bytes,
                expected_KV_bound_exceedances=self.expected_KV_bound_exceedances,
                original_8GiB_KV_cap_not_replaced_by_expected_2GiB=True,
                all_passed=True,
            ),
        )

    def close(self):
        if self.closed:
            return
        self.anchor = None
        if self._original_reset is not None:
            self.torch.cuda.reset_peak_memory_stats = self._original_reset
        if self.torch.cuda.is_initialized():
            self.torch.cuda.empty_cache()
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def r3_session_class(backend, reservation):
    class SameMathematicsReservedR3(backend.R3Session):
        def __call__(self, model, theta, prompt, targets, **kwargs):
            reservation.before_r3(self, model, prompt, targets, backend)
            result = super().__call__(model, theta, prompt, targets, **kwargs)
            reservation.response_calls += 1
            return result

    return SameMathematicsReservedR3
