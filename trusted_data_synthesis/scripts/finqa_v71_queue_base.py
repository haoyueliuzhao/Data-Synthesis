"""Two fixed-distribution train windows and three greedy evaluations."""
from __future__ import annotations

import fcntl
import importlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import tempfile
from types import SimpleNamespace

import finqa_v71_binding as binding
import finqa_v71_resources as resource_api

original = binding.source_module("finqa_v63_queue_base")
REPO, V18, DEFAULT_ROOT, PYTHON = binding.REPO, binding.V18, binding.ROOT, binding.PYTHON
GPU_LEASE_ROOT = original.GPU_LEASE_ROOT
GIB, HOST_RESERVE_BYTES = 1024 ** 3, 96 * 1024 ** 3
GPU_FREE_GIB, HOST_STARTUP_GIB = resource_api.MINIMUM_FREE_GIB, resource_api.HOST_STARTUP_GIB
MAX_WORKERS, STOP_GRACE_SECONDS, POLL_SECONDS = 6, 600, 5
Child, process_state = original.Child, original.process_state
require = binding.require


def checked_file(reference):
    path = Path(reference["path"])
    require(path.is_file() and binding.sha(path) == reference["sha256"], "bound actual file changed")
    return path


def bound(body):
    body = {key: value for key, value in body.items() if key != "id"}
    return dict(body, id=binding.digest(body))


records = SimpleNamespace(require=require, checked=binding.checked, checked_file=checked_file,
    publish=binding.publish, digest=binding.digest, file_binding=binding.entry, bound=bound)


def _status(path, value):
    path = Path(path)
    require(path.resolve().is_relative_to(binding.ROOT.resolve()) and not path.is_symlink(),
            "V71 mutable status escaped its independent root")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".v71-status-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def job_spec(step, stage):
    require(step in (894, 1192) and stage == "train",
            "V71 permits only two train windows and never an outer/probe stage")
    key = f"step{step}.{stage}"
    return dict(job_id=key, id=key, seed=137, step=step, stage=stage,
                kind="train", memory_phase="train", arm="Fixed894", temperature=1.0,
                feedback_batch=1, algorithm="fixed_pi894", probe_only=False,
                condition="fixed_pi894", fixed_distribution=True, outer_updates=0)


def core_jobs(_parents=None):
    jobs = {}
    for point in (894, 1192):
        job = job_spec(point, "train")
        job.update(dependencies=[] if point == 894 else ["step894.train"], priority=0)
        jobs[job["job_id"]] = job
    require(len(jobs) == 2, "fixed-distribution training dose changed")
    return jobs


def generation_jobs():
    planned = importlib.import_module("finqa_v71_evaluation").planned_jobs()
    jobs = {}
    expected = {(1192, 120), (1490, 120), (1490, 883)}
    require(len(planned) == 3 and {(job["step"], job["denominator"]) for job in planned.values()} == expected,
            "V71 has exactly three prespecified greedy evaluation jobs")
    for key, row in planned.items():
        require(key == row["job_id"] and row["seed"] == 137, "evaluation job coordinate changed")
        jobs[key] = dict(row, kind="generate", memory_phase="generate", stage="generate",
            dependencies=[f"step{row['step'] - 298}.train"], priority=5)
    require(sum(job["denominator"] for job in jobs.values()) == 1123, "evaluation dose changed")
    return jobs


def all_jobs():
    core, generation = core_jobs(), generation_jobs()
    require(not set(core) & set(generation), "scientific and evaluation identities collide")
    return dict(core, **generation)


def job_directory(root, job):
    require(Path(root).resolve() == binding.ROOT.resolve(), "foreign V71 job root")
    return (Path(root) / "evaluations/jobs" / job["job_id"] if job["kind"] == "generate"
            else Path(root) / "points" / f"step{job['step']:04d}" / job["stage"])


def host_requirement(kind, active):
    return original.original.host_requirement(kind, active)


def can_dispatch(active):
    require(len(active) <= MAX_WORKERS, "registered total GPU worker cap exceeded")
    devices = [child.gpu for child in active.values()]
    require(len(devices) == len(set(devices)), "one project worker per physical GPU required")
    return len(active) < MAX_WORKERS


def gpu_eligible(row, protocol, job):
    require(row["index"] in range(8) and row["uuid"] == protocol["gpu_uuids"][str(row["index"])],
            "registered physical GPU UUID changed")
    free, ownership = row.get("free_mib", row.get("memory_free_mib")), row.get("gpu_isolation", {})
    return (ownership.get("allowed") is True and ownership.get("gpu_uuid") == row["uuid"]
            and type(free) in (int, float) and math.isfinite(free)
            and free >= GPU_FREE_GIB[resource_api.kind(job)] * 1024)


class Controller(original.Controller):
    """No old scientific constructor/DAG is used by the V71 controller."""

    def job_directory(self, job):
        return job_directory(self.root, job)

    def _host_gate(self, job):
        needed = host_requirement(job["kind"], self._memory())
        if needed is None:
            return None
        try:
            available = self.runtime.host_memory().get("available_bytes")
        except (OSError, ValueError):
            return None
        if type(available) is not int or available < needed:
            return None
        return dict(available_bytes=available, required_bytes=needed,
                    reserve_bytes=HOST_RESERVE_BYTES, live_worker_count=len(self.active))

    def acquire(self, job):
        if not can_dispatch(self.active) or self._host_gate(job) is None:
            return None
        try:
            inventory = {row["index"]: row for row in self.runtime.inventory()}
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        used = {child.gpu for child in self.active.values()}
        for gpu in self.priority:
            row = inventory.get(gpu)
            if gpu in used or row is None or not gpu_eligible(row, self.protocol, job):
                continue
            path = GPU_LEASE_ROOT / ("gpu-" + binding.digest(row["uuid"]) + ".lock")
            path.parent.mkdir(parents=True, exist_ok=True)
            lease = path.open("a")
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                lease.close()
                continue
            try:
                fresh = next((r for r in self.runtime.inventory() if r["index"] == gpu), None)
                host = self._host_gate(job)
                if fresh is None or host is None or not gpu_eligible(fresh, self.protocol, job):
                    lease.close()
                    continue
                return fresh, lease, dict(host=host, gpu=fresh, lease_path=str(path),
                    lease_inode=path.stat().st_ino,
                    minimum_free_mib=GPU_FREE_GIB[resource_api.kind(job)] * 1024,
                    primary_EX_lease=True, initialization_wait_and_draining_count_as_workers=True)
            except BaseException:
                lease.close()
                raise
        return None

    def _validate_result(self, child):
        result = binding.checked(child.directory / "result/record.json")
        resources = result["resources"]
        require(resources["all_gates_passed"] is True
                and resources["single_process_lifetime_includes_loading"] is True,
                "successful full-lifetime resource evidence required")
        closeout = binding.checked(self.root / "resources" / child.job["job_id"] /
            f"pid{child.process.pid}" / "closeout/record.json")
        require(closeout["protocol_id"] == self.protocol["id"]
                and closeout["job_id"] == child.job["job_id"]
                and closeout["pid"] == child.process.pid and closeout["gpu_index"] == child.gpu
                and closeout["status"] == "COMPLETE" and closeout["resources"] == resources,
                "resource closeout belongs to another actual worker")
        require(result["gpu_index"] == child.gpu, "result physical GPU changed")
        self._validate_coordinate(child, result)
        return result
