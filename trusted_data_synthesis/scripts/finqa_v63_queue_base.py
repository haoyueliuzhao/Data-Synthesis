"""V63 resource admission and PID-bound process helpers, without old DAG jobs."""
from __future__ import annotations

import fcntl
import importlib
import math
import os
import signal
import subprocess
from pathlib import Path

import finqa_v63_binding as binding

binding.install_scientific_paths()

import finqa_v54_controller as original
import finqa_v63_evaluation as evaluation
import finqa_v63_runtime as resource_api
import finqa_v63_statistics as stats

REPO, V18, DEFAULT_ROOT, PYTHON = binding.REPO, binding.V18, binding.ROOT, binding.PYTHON
GPU_LEASE_ROOT = original.GPU_LEASE_ROOT
GIB, HOST_RESERVE_BYTES = original.GIB, original.HOST_RESERVE_BYTES
GPU_FREE_GIB, HOST_STARTUP_GIB = resource_api.MINIMUM_FREE_GIB, resource_api.HOST_STARTUP_GIB
MAX_WORKERS = binding.MAX_WORKERS
STOP_GRACE_SECONDS, POLL_SECONDS = original.STOP_GRACE_SECONDS, original.POLL_SECONDS
Child, process_state = original.Child, original.process_state
require = binding.require


def _status(path, value):
    require(Path(path).resolve().is_relative_to(binding.ROOT.resolve()),
            "V63 queue status cannot change historical records")
    return original._status(path, value)


def host_requirement(kind, active):
    require(kind in ("feedback", "replay", "distribution", "train", "generate"),
            "V63 has no class or Hold queue stage")
    return original.host_requirement(kind, active)


def gpu_eligible(row, protocol, job):
    require(row["index"] in range(8)
            and row["uuid"] == protocol["gpu_uuids"][str(row["index"])],
            "registered physical GPU index/UUID changed")
    require(job["kind"] in GPU_FREE_GIB, "unregistered GPU resource phase")
    free = row.get("free_mib", row.get("memory_free_mib"))
    isolation = row.get("gpu_isolation", {})
    return (isolation.get("allowed") is True and isolation.get("gpu_uuid") == row["uuid"]
            and type(free) in (int, float) and math.isfinite(free)
            and free >= GPU_FREE_GIB[job["kind"]] * 1024)


def core_jobs(parents):
    require(set(parents) == {str(seed) for seed in stats.SEEDS}, "all three fixed parents required")
    jobs = {}
    for seed in stats.SEEDS:
        require(parents[str(seed)]["seed"] == seed, "wrong fixed scientific parent")
        for arm in stats.ARMS:
            previous = None
            for phase, priority in (("feedback", 0), ("replay", 1), ("distribution", 2), ("train", 3)):
                stage, key = f"{phase}_{arm}", f"seed{seed}.{phase}_{arm}"
                jobs[key] = dict(
                    job_id=key, id=key, seed=seed, arm=arm, feedback_batch=binding.BATCH,
                    temperature=binding.TEMPERATURES[arm], stage=stage, kind=phase, memory_phase=phase,
                    dependencies=[] if previous is None else [previous], priority=priority)
                previous = key
    require(len(jobs) == 24 and sum(job["kind"] == "train" for job in jobs.values()) == 6,
            "V63 requires exactly six four-stage new-batch chains")
    return jobs


def can_dispatch(active):
    require(len(active) <= MAX_WORKERS, "registered six-worker total cap exceeded")
    devices = [child.gpu for child in active.values()]
    require(len(devices) == len(set(devices)), "one experiment worker per physical GPU required")
    return len(active) < MAX_WORKERS


class Controller:
    """Only admission, actual-result validation and owned-process signalling."""

    def __init__(self, root, *, runtime=None, registration=None):
        self.root = Path(root).resolve()
        require(self.root == binding.ROOT.resolve(), "foreign V63 queue root")
        self.runtime = runtime or resource_api.controller_runtime()
        self.registration = registration or importlib.import_module("finqa_v63_registration")
        self.protocol = self.registration.checked_protocol(self.root)
        self.registration.checked_implementation(self.root)
        self.prepared = self.registration.checked_prepared(self.root)
        self.parents = {}
        for seed in stats.SEEDS:
            parent = binding.read_ref(self.prepared["parents"][str(seed)])
            require(parent["protocol_id"] == self.protocol["id"] and parent["seed"] == seed,
                    "prepared parent binding changed")
            self.parents[str(seed)] = parent
        require(set(self.protocol["gpu_uuids"]) == {str(gpu) for gpu in range(8)}
                and Path(self.protocol["gpu_lease_root"]).resolve() == GPU_LEASE_ROOT.resolve(),
                "V63 must retain all eight registered identities and existing project GPU leases")
        require(self.protocol["max_gpu_workers"] == MAX_WORKERS
                and self.protocol["max_workers_per_gpu"] == 1,
                "registered total/per-device worker limits changed")
        self.priority = self.protocol["gpu_priority"]
        require(len(self.priority) == 8 and set(self.priority) == set(range(8)),
                "complete nonduplicated GPU priority required")
        self.core = core_jobs(self.parents)
        self.jobs = dict(self.core)
        self.active, self.accepted, self.launched = {}, {}, set()
        self.evaluation_registered = False
        self.wait_started = None
        self.resource_wait_seconds = float(self.protocol.get("inherited_resource_wait_seconds", 0.0))
        require(math.isfinite(self.resource_wait_seconds) and self.resource_wait_seconds >= 0,
                "invalid resource waiting statistics")

    def job_directory(self, job):
        return (evaluation.job_root(self.root, job) if job["kind"] == "generate"
                else self.root / "stages" / f"seed{job['seed']}" / job["stage"])

    def _memory(self):
        rows = []
        for child in self.active.values():
            try:
                memory = self.runtime.process_memory(child.process.pid)
            except (FileNotFoundError, ProcessLookupError):
                memory = None
            rows.append(dict(kind=child.job["kind"], memory=memory))
        return rows

    def _host_gate(self, job):
        needed = host_requirement(job["kind"], self._memory())
        if needed is None:
            return None
        try:
            observed = self.runtime.host_memory()
        except (OSError, ValueError):
            return None
        available = observed.get("available_bytes")
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
                return fresh, lease, dict(
                    host=host, gpu=fresh, lease_path=str(path), lease_inode=path.stat().st_ino,
                    minimum_free_mib=GPU_FREE_GIB[job["kind"]] * 1024,
                    initialization_wait_and_draining_count_as_workers=True)
            except BaseException:
                lease.close()
                raise
        return None

    def _validate_coordinate(self, child, result):
        job = child.job
        require(result["status"] == "COMPLETE" and result["feedback_batch"] == binding.BATCH,
                "complete matching new-batch result required")
        if job["kind"] == "generate":
            plan = evaluation.checked(self.root / "evaluations/registration/record.json")
            require(result["schema"] == "v63_b1_evaluation_job_result.v1"
                    and result["registration_id"] == plan["id"]
                    and result["job_id"] == job["job_id"] and result["sessions"] == job["denominator"],
                    "new evaluation coordinate or dose changed")
            evaluation.checked_file(result["whole_queue_seal"])
            return
        require(result["schema"] == "v63_scientific_stage_result.v1"
                and result["protocol_id"] == self.protocol["id"]
                and result["parent_id"] == self.parents[str(job["seed"])]["id"]
                and (result["seed"], result["stage"], result["arm"], result["temperature"])
                    == (job["seed"], job["stage"], job["arm"], job["temperature"])
                and result["model_released"] is True,
                "scientific new condition or parent binding changed")
        if job["kind"] == "feedback":
            require(result["denominator"] == result["new_feedback_sessions"] == 700
                    and result["real_parent_unchanged"] is True,
                    "each new condition needs its own complete 700 feedback episodes")
        elif job["kind"] == "replay":
            require(result["denominator"] == 700 and result["complete_replay"] is True
                    and result["real_parent_unchanged"] is True
                    and result["draw_diagnostics_passed"] is True,
                    "complete same-temperature formal replay and draw diagnostic agreement required")
        elif job["kind"] == "distribution":
            require(result["complete_class_tasks"] == 744 and result["complete_class_rows"] == 4974
                    and result["historical_G_theta_bar_bitwise_equal"] is True
                    and result["draw_C_diagnostics_passed"] is True
                    and result["real_parent_unchanged"] is True,
                    "same-parent full-cache distribution and draw-C linearity agreement required")
        elif job["kind"] == "train":
            require((result["final_step"], result["optimizer_updates"], result["new_optimizer_updates"])
                    == (894, 298, 298), "new C1 and C05 each need 298 real committed updates")
            evaluation.checked_file(result["branch_result"])
        else:
            raise ValueError("unregistered new scientific stage")
        if "payload" in result:
            evaluation.checked_file(result["payload"])

    def _validate_result(self, child):
        result = evaluation.checked(child.directory / "result/record.json")
        resources = result["resources"]
        require(resources["all_gates_passed"] is True
                and resources["single_process_lifetime_includes_loading"] is True,
                "successful full-process lifetime resource gates required")
        closeout = evaluation.checked(self.root / "resources" / child.job["job_id"] /
            f"pid{child.process.pid}" / "closeout/record.json")
        require(closeout["protocol_id"] == self.protocol["id"]
                and closeout["job_id"] == child.job["job_id"]
                and closeout["pid"] == child.process.pid and closeout["gpu_index"] == child.gpu
                and closeout["status"] == "COMPLETE" and closeout["resources"] == resources,
                "accepted resource report must match the actual worker's final boundary")
        if child.job["kind"] != "generate":
            require(result["gpu_index"] == child.gpu, "scientific result GPU differs from actual worker")
        self._validate_coordinate(child, result)
        return result

    def _signal(self, child, number):
        if child.process.poll() is not None:
            return False
        observed_birth = self.runtime.birth(child.process.pid)
        if observed_birth is None:
            return False
        require(isinstance(child.birth, str) and child.birth.isdigit()
                and observed_birth == child.birth, "refusing to signal an unverified or reused worker PID")
        try:
            if child.pidfd is not None and hasattr(signal, "pidfd_send_signal"):
                signal.pidfd_send_signal(child.pidfd, number)
            else:
                os.kill(child.process.pid, number)
        except ProcessLookupError:
            return False
        return True
