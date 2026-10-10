"""CPU-only, bounded admission for a worker that already owns a GPU lease.

An unrelated process arriving during CPU preparation is a resource wait, not a
reason to repeat a scientific stage. Device identity, host-memory and time gates
remain hard boundaries. This module never initializes CUDA or resets a peak.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

GIB = 1024**3
ALLOWED_GPUS = (3, 4, 5, 7)
SHARDS = tuple(f"shard{index:02d}" for index in range(4))
STAGES = (*SHARDS, "virtual_point", "replay_R3", "distribution", "train", "generate")
MINIMUM_FREE_MIB = 72 * 1024
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
    inventory=None,
    host_memory=None,
    process_memory=None,
    birth=None,
    clock=None,
    sleep=None,
    monotonic=None,
    poll_seconds=10.0,
):
    """Wait in the same CPU worker, returning its registered idle GPU observation.

    The caller retains its worker slot, GPU lease and original point locks. The
    controller charges the union of fresh WAITING heartbeats to its shared wait
    budget; this function never extends ``deadline_epoch``. Injected readers and
    clocks support CPU-only tests without importing a production controller.
    """
    if any(reader is None for reader in (inventory, host_memory, process_memory, birth)):
        control = importlib.import_module("finqa_v38_controller")
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
    _number(deadline_epoch, "invalid original stage deadline")
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
        _require(not snapshot["cuda_initialized"], "CUDA initialized before idle admission")
        if stop_requested():
            raise AdmissionStopped("safe stop requested before CUDA admission")
        if last_epoch >= deadline_epoch:
            raise AdmissionDeadlineExceeded("original stage deadline reached before CUDA")

    def emit(phase, *, reason=None):
        nonlocal sequence
        body = dict(
            schema="v38_pre_cuda_admission.v1",
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
            minimum_free_mib=MINIMUM_FREE_MIB,
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
            _require(isinstance(observed_inventory, (list, tuple)), "GPU inventory unavailable")
            matching = [row for row in observed_inventory if row.get("index") == gpu_index]
            _require(len(matching) == 1, "registered GPU observation missing or duplicated")
            row = matching[0]
            snapshot["gpu"] = row
            _require(row.get("uuid") == expected_uuid, "registered GPU UUID changed")
            processes = row.get("processes")
            _require(isinstance(processes, list), "GPU process observation unavailable")
            _require(
                all(
                    isinstance(item, dict) and isinstance(item.get("pid"), int)
                    for item in processes
                ),
                "GPU process identity is unavailable",
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
            if not processes and free_mib >= MINIMUM_FREE_MIB:
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
                reason="external_gpu_process" if processes else "insufficient_free_gpu_memory",
            )
            sleep(min(poll_seconds, max(0.0, deadline_epoch - clock())))
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
