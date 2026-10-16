"""V50 empirical shared-device admission and resource-only native reservation.

The original host/identity/stop/deadline wait state machine is preserved. Only
free-memory admission is stage-specific and external compute PIDs are allowed.
No CUDA is initialized, peaks reset, scientific work repeated, or budget reset.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import finqa_v41_memory_policy as legacy_policy
import finqa_v43_time_policy as time_policy
import finqa_v45_admission as host_policy
import finqa_v50_reservation as reservation

policy = sys.modules[__name__]

GIB = 1024**3
ALLOWED_GPUS = (0,)
DISPATCH_ORDER = (0,)
GPU_UUIDS = {
    "0": "GPU-f813ce38-39d7-ab21-f72b-55f87284eaa5",
}
SHARDS = tuple(f"shard{index:02d}" for index in range(4))
STAGES = (*SHARDS, "virtual_point", "replay_R3", "distribution", "train", "generate")
CPU_AFFINITY = {str(gpu): "0-37,76-113" if gpu < 4 else "38-75,114-151" for gpu in ALLOWED_GPUS}
POLICY_SCHEMA = "v50_empirical_shared_gpu_reserved_admission.v1"
PHASE_MINIMUM_FREE_GIB = dict(reservation.PHASE_MINIMUM_FREE_GIB)
phase_key = legacy_policy.phase_key
host_policy_record = host_policy.host_policy_record
host_memory_requirement = host_policy.host_memory_requirement
startup_budget_bytes = host_policy.startup_budget_bytes
padded_peak_bytes = host_policy.padded_peak_bytes
host_phase = host_policy.host_phase
DISPATCH_ORDER = (0,)
HOST_RESERVE_BYTES = 96 * GIB


class AdmissionError(ValueError):
    """A hard identity/resource boundary failed; waiting cannot repair it."""


class AdmissionStopped(RuntimeError):
    """The existing worker was asked to stop before CUDA admission."""


class AdmissionDeadlineExceeded(TimeoutError):
    """The original absolute stage deadline has expired."""


def _require(condition, message):
    if not condition:
        raise AdmissionError(message)


def minimum_free_mib(stage, context=None):
    return PHASE_MINIMUM_FREE_GIB[phase_key(stage, context)] * 1024


def execution_policy_record():
    return dict(
        schema="v50_single_gpu0_execution_policy.v1",
        allowed_gpu_indices=[0], steady_gpu_indices=[0],
        max_gpu_workers=1, steady_max_gpu_workers=1,
        maximum_project_workers_per_gpu=1,
        all_remaining_training_outer_and_endpoint_work_on_gpu0=True,
        all_other_devices_forbidden=True,
        initializing_waiting_and_draining_count_as_workers=True,
        bootstrap_training_coordinate=dict(seed=251, arm="Full"),
        bootstrap_training_stop_step=1490,
        bootstrap_must_finish_before_other_gpu_work=True,
        completed_bootstrap_not_repeated_after_automatic_recovery=True,
        complete_logical_class_shards=4,
        logical_class_shards_run_sequentially_on_gpu0=True,
        no_sampling_or_optimizer_dose_change=True,
    )


def device_scope_allows(gpu_index, stage, context=None):
    return type(gpu_index) is int and gpu_index == 0 and stage in STAGES


def bootstrap_stage_allows(stage, context, *, full251_complete):
    """Use actual accepted state, never a mutable checkpoint in protocol equality."""
    if full251_complete:
        return stage in STAGES
    if stage != "train" or not isinstance(context, dict):
        return False
    step = context.get("step")
    return (
        context.get("seed") == 251 and context.get("arm") == "Full"
        and context.get("due_outer") is False
        and type(step) is int and 1192 <= step < 1490
        and context.get("training_stop_step", min(1490, step + 298)) == 1490
    )


def eligible_gpu(row, protocol, stage, context=None, *, worker_pid=None):
    if not isinstance(row, dict) or not device_scope_allows(row.get("index"), stage, context):
        return False
    # Clone only this pure policy's globals; no old module is mutated.
    function = legacy_policy.eligible_gpu
    import types

    checked = types.FunctionType(
        function.__code__,
        {**function.__globals__, "minimum_free_mib": minimum_free_mib},
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    checked.__kwdefaults__ = function.__kwdefaults__
    return checked(row, protocol, stage, context, worker_pid=worker_pid)


def reservation_eligible(row, protocol, stage, context=None):
    return eligible_gpu(row, protocol, stage, context)


def check_retry_capacity(condition, inventory):
    scope = dict(allowed_gpu_indices=list(ALLOWED_GPUS), gpu_uuids=dict(GPU_UUIDS))
    if not isinstance(inventory, (list, tuple)):
        return False
    rows = [row for row in inventory if eligible_gpu(row, scope, "replay_R3", None)]
    return reservation.check_retry_capacity(condition, rows)


def reservation_policy_record():
    return reservation.policy_record()


def gpu_policy_record():
    result = legacy_policy.policy_record(
        scope=dict(allowed_gpu_indices=list(ALLOWED_GPUS), gpu_uuids=dict(GPU_UUIDS)),
        evidence_refs=reservation.policy_record()["evidence_refs"],
    )
    result.update(
        schema=POLICY_SCHEMA,
        minimum_free_gib_by_phase=dict(PHASE_MINIMUM_FREE_GIB),
        evidence_interpretation=dict(
            historical_observations_are_not_upper_bounds=True,
            basis="105 successful processes; allocated peaks plus native anchor resource policy",
            non_R3_rule="ceil2GiB(1.125*historical_allocated_peak+4GiB)",
            R3_rule=(
                "historical before-response allocated plus original residency and configured KV"
            ),
            R3_minimum_free_gib=56,
            allocator_probe_is_not_full_scientific_acceptance=True,
            required_boundary_free_gib=2,
            shared_device_competition_remains_a_risk=True,
        ),
    )
    result["admission"].update(
        maximum_total_workers_including_initializing_and_draining=1,
        independent_total_worker_limit=1,
        total_worker_limit_removed=False,
        maximum_project_workers_per_gpu=1,
    )
    result["gpu_execution_policy"] = execution_policy_record()
    result["unchanged_runtime"].update(
        failure_stops_pool_without_automatic_retry=False,
        only_verified_durable_resource_recovery_allowed=True,
    )
    return result


def validate_plan(plan):
    _require(
        plan.get("allowed_gpu_indices") == list(ALLOWED_GPUS)
        and plan.get("gpu_uuids") == GPU_UUIDS,
        "V50 requires only the registered physical GPU0 UUID",
    )
    _require(
        plan.get("gpu_admission_policy") == gpu_policy_record()
        and plan.get("gpu_reservation_policy") == reservation_policy_record(),
        "V50 shared-memory and same-process reservation policy differs",
    )
    _require(
        type(plan.get("max_gpu_workers")) is int and plan["max_gpu_workers"] == 1
        and type(plan.get("independent_total_worker_limit")) is int
        and plan["independent_total_worker_limit"] == 1
        and plan.get("total_worker_limit_removed") is False
        and plan.get("max_workers_per_gpu") == 1
        and plan.get("steady_gpu_indices") == [0]
        and plan.get("steady_max_gpu_workers") == 1
        and plan.get("gpu_execution_policy") == execution_policy_record(),
        "V50 requires GPU0-only single-worker scope",
    )
    _require(
        plan.get("host_admission_policy") == host_policy_record()
        and plan.get("host_ram_runtime_hard_gates_unchanged") is True,
        "V50 keeps registered host admission and runtime hard gates",
    )
    time_policy.validate(plan)
    return plan


def _number(value, message):
    _require(
        isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value),
        message,
    )
    return value


def _iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_record(path, body, *, replace):
    """Publish a complete heartbeat or a new immutable event without partial JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    record = {**body, "id": hashlib.sha256(raw).hexdigest()}
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("xb") as stream:
        stream.write(
            json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False).encode() + b"\n"
        )
        stream.flush()
        os.fsync(stream.fileno())
    try:
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)  # Unlike replace(), never overwrites an event.
            temporary.unlink()
        _sync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()
    return record


def wait_for_pre_cuda_admission(
    plan,
    stage,
    gpu_index,
    directory,
    deadline_epoch,
    torch,
    stop_requested,
    *,
    context_id=None,
    context=None,
    inventory=None,
    host_memory=None,
    process_memory=None,
    birth=None,
    clock=None,
    sleep=None,
    monotonic=None,
    poll_seconds=10.0,
):
    """Wait in the same CPU worker, returning the real registered GPU observation.

    The caller retains its worker slot, GPU lease and original point locks. The
    controller charges the union of fresh WAITING heartbeats to its shared wait
    budget; this function never extends ``deadline_epoch``. Injected readers and
    clocks support CPU-only tests without importing a production controller.
    """
    validate_plan(plan)
    _require(device_scope_allows(gpu_index, stage, context),
             "stage is not authorized on this excluded GPU")
    memory_phase = policy.phase_key(stage, context)
    minimum_free_mib = policy.minimum_free_mib(stage, context)
    if context is not None:
        _require(
            isinstance(context, dict) and context.get("id") == context_id,
            "admission context identity differs",
        )
    if any(reader is None for reader in (inventory, host_memory, process_memory, birth)):
        control = importlib.import_module("finqa_v50_controller")
        inventory = control.inventory if inventory is None else inventory
        host_memory = control.host_memory if host_memory is None else host_memory
        process_memory = control.process_memory if process_memory is None else process_memory
        birth = control.birth if birth is None else birth
    if monotonic is None:
        monotonic = time.monotonic if clock is None else clock
    clock = time.time if clock is None else clock
    sleep = time.sleep if sleep is None else sleep
    _require(stage in STAGES and gpu_index in ALLOWED_GPUS, "unregistered stage or GPU")
    _require(bool(plan.get("id")) and bool(context_id), "protocol and actual context are required")
    _require(callable(stop_requested), "stop_requested must be callable")
    _require(
        0 < _number(poll_seconds, "invalid admission poll period") <= 60, "invalid poll period"
    )
    time_policy.require_no_deadline(deadline_epoch)
    expected_uuid = plan.get("gpu_uuids", {}).get(str(gpu_index))
    _require(isinstance(expected_uuid, str) and bool(expected_uuid), "GPU UUID is not registered")
    pid, registered_birth = os.getpid(), birth(os.getpid())
    _require(registered_birth is not None, "worker birth identity is unavailable")
    wait_directory = Path(directory) / "pre_cuda_wait"
    _require(not (wait_directory / "status.json").exists(), "admission attempt already exists")
    started_epoch = _number(clock(), "invalid admission clock")
    started_monotonic = _number(monotonic(), "invalid admission monotonic clock")
    rss_limit = (160 if stage in SHARDS else 192) * GIB
    waiting_seconds, waiting_since, sequence, wait_polls = 0.0, None, 0, 0
    waiting_started_monotonic = waiting_finished_epoch = waiting_finished_monotonic = None
    last_monotonic = started_monotonic
    last_epoch = started_epoch
    snapshot = {}

    def refresh_clock():
        nonlocal last_epoch, last_monotonic, waiting_seconds
        observed_epoch = _number(clock(), "invalid admission clock")
        observed_monotonic = _number(monotonic(), "invalid admission monotonic clock")
        _require(observed_monotonic >= last_monotonic, "admission monotonic clock reversed")
        if waiting_since is not None:
            waiting_seconds += observed_monotonic - last_monotonic
        last_epoch, last_monotonic = observed_epoch, observed_monotonic

    def check_cpu_stop_deadline():
        snapshot["cuda_initialized"] = bool(torch.cuda.is_initialized())
        _require(
            not snapshot["cuda_initialized"], "CUDA initialized before phase-specific admission"
        )
        if stop_requested():
            raise AdmissionStopped("safe stop requested before CUDA admission")
        time_policy.require_no_deadline(deadline_epoch)

    def emit(phase, *, reason=None):
        nonlocal sequence
        body = dict(
            schema="v50_shared_pre_cuda_admission.v1",
            protocol_id=plan["id"],
            context_id=context_id,
            stage=stage,
            pid=pid,
            birth=registered_birth,
            gpu_index=gpu_index,
            gpu_uuid=expected_uuid,
            started_at=_iso(started_epoch),
            started_epoch=started_epoch,
            at=_iso(last_epoch),
            observed_epoch=last_epoch,
            deadline_epoch=deadline_epoch,
            wallclock_limits_removed=True,
            resource_wait_accounting_retained=True,
            phase=phase,
            reason=reason,
            waiting_seconds=waiting_seconds,
            waiting_started_epoch=waiting_since,
            waiting_finished_epoch=waiting_finished_epoch,
            waiting_started_monotonic=waiting_started_monotonic,
            observed_monotonic=last_monotonic,
            waiting_finished_monotonic=waiting_finished_monotonic,
            elapsed_seconds=max(0.0, last_monotonic - started_monotonic),
            wait_poll_count=wait_polls,
            poll_seconds=poll_seconds,
            sequence=sequence,
            worker_slot_retained=True,
            gpu_lease_retained=True,
            automatic_retry=False,
            minimum_free_mib=minimum_free_mib,
            memory_phase=memory_phase,
            gpu_admission_policy_schema=POLICY_SCHEMA,
            gpu_reservation_policy_schema=reservation.SCHEMA,
            reservation_target_chosen_after_actual_CUDA_admission=True,
            external_compute_process_presence_is_not_a_veto=True,
            rss_limit_bytes=rss_limit,
            host_available_reserve_bytes=HOST_RESERVE_BYTES,
            **snapshot,
        )
        event_path = wait_directory / f"event{sequence:06d}" / "record.json"
        sequence += 1
        _write_record(event_path, body, replace=False)
        _write_record(wait_directory / "status.json", body, replace=True)

    try:
        while True:
            refresh_clock()
            snapshot = {}
            check_cpu_stop_deadline()
            observed_host, observed_process = host_memory(), process_memory(pid)
            snapshot.update(host=observed_host, process_memory=observed_process)
            _require(isinstance(observed_host, dict), "host memory observation unavailable")
            _require(isinstance(observed_process, dict), "worker memory observation unavailable")
            available = _number(observed_host.get("available_bytes"), "host available RAM unknown")
            rss = _number(observed_process.get("rss_bytes"), "worker RSS unknown")
            peak_rss = _number(observed_process.get("peak_rss_bytes"), "worker peak RSS unknown")
            _require(available >= HOST_RESERVE_BYTES, "host available RAM below 96 GiB reserve")
            _require(
                0 <= rss <= rss_limit and 0 <= peak_rss <= rss_limit, "worker RSS limit exceeded"
            )
            observed_inventory = inventory()
            _require(
                isinstance(observed_inventory, (list, tuple))
                and all(isinstance(row, dict) for row in observed_inventory),
                "GPU inventory unavailable or malformed",
            )
            matching = [row for row in observed_inventory if row.get("index") == gpu_index]
            _require(len(matching) == 1, "registered GPU observation missing or duplicated")
            row = matching[0]
            snapshot["gpu"] = row
            _require(row.get("uuid") == expected_uuid, "registered GPU UUID changed")
            processes = row.get("processes")
            _require(isinstance(processes, list), "GPU process observation unavailable")
            _require(
                all(
                    isinstance(item, dict)
                    and type(item.get("pid")) is int
                    and item["pid"] > 0
                    and item.get("gpu_uuid", expected_uuid) == expected_uuid
                    for item in processes
                ),
                "GPU process identity is unavailable",
            )
            _require(
                len({item["pid"] for item in processes}) == len(processes),
                "GPU process observation contains duplicate identities",
            )
            _require(
                all(item["pid"] != pid for item in processes),
                "this CPU-only worker unexpectedly owns a CUDA process",
            )
            free_mib = _number(row.get("free_mib"), "GPU free memory observation unavailable")
            _require(free_mib >= 0, "negative GPU free memory observation")
            # Readers may block, or a signal can arrive while they run. An idle
            # observation cannot admit CUDA past a deadline or a requested stop.
            refresh_clock()
            check_cpu_stop_deadline()
            if policy.eligible_gpu(row, plan, stage, context, worker_pid=pid):
                if waiting_since is not None:
                    waiting_finished_epoch = last_epoch
                    waiting_finished_monotonic = last_monotonic
                emit("READY")
                return row
            if waiting_since is None:
                waiting_since = last_epoch
                waiting_started_monotonic = last_monotonic
            wait_polls += 1
            emit(
                "WAITING",
                reason="insufficient_phase_free_gpu_memory",
            )
            sleep(poll_seconds)
    except BaseException as error:
        if waiting_since is not None:
            waiting_finished_epoch = last_epoch
            waiting_finished_monotonic = last_monotonic
        phase = (
            "STOPPED"
            if isinstance(error, AdmissionStopped)
            else "TIMED_OUT"
            if isinstance(error, AdmissionDeadlineExceeded)
            else "FAILED"
        )
        emit(phase, reason=dict(type=type(error).__name__, message=str(error)))
        raise
