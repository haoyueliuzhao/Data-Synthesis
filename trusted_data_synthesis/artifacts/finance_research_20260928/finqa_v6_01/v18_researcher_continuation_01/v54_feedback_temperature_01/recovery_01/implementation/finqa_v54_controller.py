"""Fresh, bounded scientific DAG for V54; actual exits gate every dependency.

Resource shortage is queue waiting. Scientific failures and explicit stop do
not retry: a single shared grace interval drains only identity-bound children.
The original project GPU lease inodes are inherited by every cold worker.
"""

from __future__ import annotations

import argparse
import fcntl
import importlib
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import finqa_v54_evaluation as evaluation
import finqa_v54_runtime as resource_api
import finqa_v54_statistics as stats

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
V18 = REPO / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01"
DEFAULT_ROOT = V18 / "v54_feedback_temperature_01"
GPU_LEASE_ROOT = V18 / "v25_training_replication_01/training_replication/locks"
PYTHON = REPO / "trusted_data_synthesis/.venv/bin/python"
GIB = 1024**3
MAX_WORKERS = 4
GPU_FREE_GIB = resource_api.MINIMUM_FREE_GIB
HOST_STARTUP_GIB = resource_api.HOST_STARTUP_GIB
HOST_RESERVE_BYTES = 96 * GIB
STOP_GRACE_SECONDS = 600
POLL_SECONDS = 5
require = evaluation.require


def _kind_key(kind):
    return "class_" if kind == "class" else kind


def host_requirement(kind, active):
    """Available RAM already excludes RSS: reserve only each budget's remainder."""
    needed = HOST_RESERVE_BYTES + HOST_STARTUP_GIB[_kind_key(kind)] * GIB
    for row in active:
        memory = row.get("memory")
        if not isinstance(memory, dict):
            return None
        rss, peak = memory.get("rss_bytes"), memory.get("peak_rss_bytes")
        if type(rss) is not int or type(peak) is not int or not 0 <= rss <= peak:
            return None
        limit = (160 if row["kind"] == "class" else 192) * GIB
        require(peak <= limit, "active worker exceeded its registered RSS hard gate")
        budget = HOST_STARTUP_GIB[_kind_key(row["kind"])] * GIB
        needed += max(0, budget - rss)
    return needed


def gpu_eligible(row, protocol, job):
    require(row["index"] in range(8), "device outside registered physical GPU0-7")
    require(row["uuid"] == protocol["gpu_uuids"][str(row["index"])], "physical GPU UUID changed")
    free = row.get("free_mib", row.get("memory_free_mib"))
    return (type(free) in (int, float) and math.isfinite(free)
            and free >= GPU_FREE_GIB[_kind_key(job["kind"])] * 1024)


def core_jobs(parents):
    """No dependency can be satisfied by a result file preceding actual exit."""
    require(set(parents) == {str(seed) for seed in stats.SEEDS}, "all three fixed parents required")
    jobs = {}
    for seed in stats.SEEDS:
        parent = parents[str(seed)]
        require(parent["seed"] == seed, "wrong scientific parent seed")
        shards = []
        if parent["old_class_context"] is None:
            require(parent["new_class_task_count"] == 744, "complete new class task roster required")
            for index in range(4):
                stage = f"shard{index:02d}"
                key = f"seed{seed}.{stage}"
                jobs[key] = dict(job_id=key, id=key, seed=seed, stage=stage, kind="class",
                                 memory_phase="class", arm=None, dependencies=[], priority=4)
                shards.append(key)
        else:
            require(parent["new_class_task_count"] == 0, "inherited class must not consume new tasks")
        for stage, kind, dependencies, priority in (
            ("feedback_C05", "feedback", [], 0),
            ("replay_C05", "replay", [f"seed{seed}.feedback_C05"], 1),
            ("distribution_C05", "distribution", [f"seed{seed}.replay_C05", *shards], 2),
            ("train_Hold", "train", [], 5),
            ("train_C05", "train", [f"seed{seed}.distribution_C05"], 3),
        ):
            key = f"seed{seed}.{stage}"
            jobs[key] = dict(job_id=key, id=key, seed=seed, stage=stage, kind=kind,
                memory_phase=kind, arm=stage.removeprefix("train_") if kind == "train" else None,
                dependencies=dependencies, priority=priority)
        if not parent["c1_reuse"]["eligible"]:
            key = f"seed{seed}.train_C1"
            jobs[key] = dict(job_id=key, id=key, seed=seed, stage="train_C1", kind="train",
                memory_phase="train", arm="C1", dependencies=[], priority=5)
    return jobs


def ready_jobs(jobs, accepted, launched):
    return sorted((job for key, job in jobs.items() if key not in launched
                   and set(job["dependencies"]) <= set(accepted)),
                  key=lambda job: (job["priority"], job["seed"], job["job_id"]))


def can_dispatch(active):
    require(len(active) <= MAX_WORKERS, "registered four-worker cap exceeded")
    gpus = [child.gpu for child in active.values()]
    require(len(gpus) == len(set(gpus)), "more than one experiment worker on a physical GPU")
    return len(active) < MAX_WORKERS


def process_state(process, result_exists):
    """Nonblocking: trustworthy result + live process still occupies its slot."""
    code = process.poll()
    if code is None:
        return ("DRAINING" if result_exists else "RUNNING"), None
    return ("EXITED_SUCCESS" if code == 0 else "EXITED_FAILURE"), code


def registration_module_name(root):
    root = Path(root).resolve()
    if root == DEFAULT_ROOT:
        return "finqa_v54_registration"
    require(root == DEFAULT_ROOT / "recovery_01", "unregistered experiment/recovery controller root")
    return "finqa_v55_registration"


def _status(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".status-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


@dataclass
class Child:
    job: dict
    gpu: int
    uuid: str
    process: object
    lease: object
    birth: str | None
    pidfd: int | None
    directory: Path
    started_epoch: float
    lifecycle: str = "RUNNING"
    signal_sent: bool = False


class Controller:
    def __init__(self, root, *, runtime=None, registration=None):
        self.root = Path(root).resolve()
        self.runtime = runtime or importlib.import_module("finqa_v54_runtime")
        self.registration = registration or importlib.import_module(registration_module_name(self.root))
        self.protocol = self.registration.checked_protocol(self.root)
        self.registration.checked_implementation(self.root)
        prepared = self.registration.checked_prepared(self.root)
        self.prepared = prepared
        self.parents = {}
        for seed in stats.SEEDS:
            reference = prepared["parents"][str(seed)]
            parent = evaluation.checked(evaluation.checked_file(reference))
            require(parent["protocol_id"] == self.protocol["id"] and parent["seed"] == seed,
                    "prepared scientific parent differs from frozen protocol")
            self.parents[str(seed)] = parent
        require(set(self.protocol["gpu_uuids"]) == {str(gpu) for gpu in range(8)},
                "all eight authorized physical UUIDs must be frozen")
        require(Path(self.protocol["gpu_lease_root"]).resolve() == GPU_LEASE_ROOT.resolve(),
                "V54 must share the existing project lease inodes")
        require(self.protocol["max_gpu_workers"] == MAX_WORKERS,
                "registered total worker limit must be four")
        self.priority = self.protocol["gpu_priority"]
        require(len(self.priority) == 8 and set(self.priority) == set(range(8)),
                "complete nonduplicated registered GPU priority required")
        self.core = core_jobs(self.parents)
        self.jobs = dict(self.core)
        self.active, self.accepted, self.launched = {}, {}, set()
        self.stop_reason = None
        self.evaluation_registered = False
        self.wait_started = None
        self.resource_wait_seconds = float(self.protocol.get("inherited_resource_wait_seconds", 0.0))
        require(math.isfinite(self.resource_wait_seconds) and self.resource_wait_seconds >= 0,
                "invalid inherited resource-wait accounting")

    def job_directory(self, job):
        if job["kind"] == "generate":
            return evaluation.job_root(self.root, job)
        return self.root / "stages" / f"seed{job['seed']}" / job["stage"]

    def request_stop(self, reason):
        if self.stop_reason is None:
            self.stop_reason = reason

    def _memory(self):
        rows = []
        for child in self.active.values():
            # A process can disappear between poll and /proc. Defer admission;
            # the next nonblocking reap establishes the real exit code.
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
        if not can_dispatch(self.active):
            return None
        host = self._host_gate(job)
        if host is None:
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
            path = GPU_LEASE_ROOT / ("gpu-" + evaluation.digest(row["uuid"]) + ".lock")
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
                    lease_inode=path.stat().st_ino, minimum_free_mib=GPU_FREE_GIB[_kind_key(job["kind"])] * 1024)
            except BaseException:
                lease.close()
                raise
        return None

    def launch(self, job, acquired):
        row, lease, admission = acquired
        key = job["job_id"]
        directory = self.job_directory(job)
        require(key not in self.launched and not (directory / "launch/record.json").exists(),
                "one actual attempt per registered scientific/evaluation job")
        directory.mkdir(parents=True, exist_ok=True)
        arguments = ([str(self.root / "implementation/finqa_v54_evaluation.py"), "worker",
                      "--root", str(self.root), "--job", key, "--gpu", str(row["index"])]
                     if job["kind"] == "generate" else
                     [str(self.root / "implementation/finqa_v54_worker.py"), "--root", str(self.root),
                      "--seed", str(job["seed"]), "--stage", job["stage"],
                      "--gpu-index", str(row["index"])])
        command = ["/usr/bin/taskset", "--cpu-list", self.protocol["cpu_affinity"][str(row["index"])],
                   str(PYTHON), "-u", *arguments]
        environment = self.runtime.worker_environment(row)
        environment.update(CUDA_VISIBLE_DEVICES=row["uuid"],
            PYTHONPATH=os.pathsep.join((str(self.root / "implementation"),
                                       str(REPO / "trusted_data_synthesis/scripts"),
                                       str(evaluation.FROZEN_SOURCE))),
            V54_GPU_LEASE_FD=str(lease.fileno()), V54_JOB_ID=key)
        started = time.time()
        self.launched.add(key)
        try:
            with (directory / "worker.log").open("xb") as stream:
                process = subprocess.Popen(command, cwd=REPO, env=environment, stdout=stream,
                    stderr=subprocess.STDOUT, start_new_session=True, pass_fds=(lease.fileno(),))
        except BaseException:
            lease.close()
            raise
        child = Child(job=job, gpu=row["index"], uuid=row["uuid"], process=process,
            lease=lease, birth=self.runtime.birth(process.pid), pidfd=None,
            directory=directory, started_epoch=started)
        self.active[key] = child
        if hasattr(os, "pidfd_open"):
            try:
                child.pidfd = os.pidfd_open(process.pid)
            except ProcessLookupError:
                pass
        require(child.birth is not None or process.poll() is not None,
                "live scientific worker identity could not be established")
        evaluation.publish(directory / "launch/record.json", dict(
            schema="v54_device_leased_stage_launch.v1", protocol_id=self.protocol["id"],
            job=job, pid=process.pid, birth=child.birth, gpu_index=child.gpu, gpu_uuid=child.uuid,
            command=command, started_epoch=started, admission=admission,
            inherited_gpu_lease=True, total_worker_count_after_dispatch=len(self.active),
            CPU_initialization_wait_and_draining_count_as_workers=True,
            API_calls_in_controller=0, automatic_retry=False))
        can_dispatch(self.active)

    def _validate_result(self, child):
        result = evaluation.checked(child.directory / "result/record.json")
        job = child.job
        resources = result["resources"]
        require(result["status"] == "COMPLETE" and resources["all_gates_passed"] is True
                and resources["single_process_lifetime_includes_loading"] is True,
                "actual successful result and full-lifetime resource gates required")
        resource_closeout = evaluation.checked(self.root / "resources" / job["job_id"] /
            f"pid{child.process.pid}" / "closeout/record.json")
        require(resource_closeout["protocol_id"] == self.protocol["id"]
                and resource_closeout["job_id"] == job["job_id"]
                and resource_closeout["pid"] == child.process.pid
                and resource_closeout["gpu_index"] == child.gpu
                and resource_closeout["status"] == "COMPLETE"
                and resource_closeout["resources"] == resources,
                "actual final resource boundary is not the accepted worker result")
        if job["kind"] == "generate":
            registration = evaluation.checked(self.root / "evaluations/registration/record.json")
            require(result["schema"] == "v54_evaluation_job_result.v1"
                    and result["registration_id"] == registration["id"]
                    and result["job_id"] == job["job_id"] and result["sessions"] == job["denominator"],
                    "evaluation result coordinate/dose changed")
            evaluation.checked_file(result["whole_queue_seal"])
        else:
            require(result["schema"] == "v54_scientific_stage_result.v1"
                    and result["protocol_id"] == self.protocol["id"]
                    and result["parent_id"] == self.parents[str(job["seed"])]["id"]
                    and (result["seed"], result["stage"], result["gpu_index"])
                        == (job["seed"], job["stage"], child.gpu)
                    and result["model_released"] is True, "scientific stage result binding changed")
            if job["kind"] == "class":
                require(result["task_count"] == len(result["task_ids"]) == 186
                        and result["optimizer_updates"] == 0, "complete class shard required")
            elif job["kind"] == "feedback":
                require((result["denominator"], result["new_feedback_sessions"], result["temperature"])
                        == (700, 700, 0.5) and result["real_parent_unchanged"] is True,
                        "registered low-temperature feedback dose required")
            elif job["kind"] == "replay":
                require(result["denominator"] == 700 and result["temperature"] == 0.5
                        and result["complete_replay"] is True and result["real_parent_unchanged"] is True,
                        "complete matching-temperature feedback replay required")
            elif job["kind"] == "distribution":
                require(result["complete_class_tasks"] == 744 and result["complete_class_rows"] == 4974
                        and result["historical_G_theta_bar_bitwise_equal"] is True
                        and result["real_parent_unchanged"] is True, "same-parent C05 distribution required")
            else:
                require((result["final_step"], result["optimizer_updates"], result["new_optimizer_updates"])
                        == (894, 298, 298), "one complete registered real learning window required")
                evaluation.checked_file(result["branch_result"])
            if "payload" in result:
                evaluation.checked_file(result["payload"])
        return result

    def reap(self):
        for key, child in list(self.active.items()):
            child.lifecycle, code = process_state(child.process,
                (child.directory / "result/record.json").exists())
            if code is None:
                continue
            exit_record = evaluation.publish(child.directory / "actual_exit/record.json", dict(
                schema="v54_actual_worker_exit.v1", protocol_id=self.protocol["id"], job_id=key,
                pid=child.process.pid, birth=child.birth, gpu_index=child.gpu,
                returncode=code, observed_epoch=time.time(), actual_waitpid_observed=True))
            try:
                require(code == 0, f"worker {key} exited with returncode {code}")
                result = self._validate_result(child)
                accepted = evaluation.publish(child.directory / "accepted/record.json", dict(
                    schema="v54_actual_exit_and_result_accepted.v1", protocol_id=self.protocol["id"],
                    job_id=key, result=evaluation.file_binding(child.directory / "result/record.json"),
                    result_id=result["id"], actual_exit=evaluation.file_binding(
                        child.directory / "actual_exit/record.json"), actual_exit_id=exit_record["id"],
                    resources_passed=True, actual_exit_zero=True))
                self.accepted[key] = accepted
            except BaseException as error:
                self.request_stop(dict(kind="SCIENTIFIC_OR_PROCESS_FAILURE", job_id=key,
                                       error_type=type(error).__name__, error=str(error)))
            finally:
                child.lease.close()
                if child.pidfd is not None:
                    os.close(child.pidfd)
                del self.active[key]

    def seal_training(self):
        require(set(self.core) <= set(self.accepted) and not self.active,
                "all scientific DAG nodes must be accepted after real exit")
        training = importlib.import_module("finqa_v54_training")
        branches = {}
        for seed in stats.SEEDS:
            for arm in stats.ARMS:
                training.checked_branch_result(self.root, seed, arm)
                path = self.root / "branches" / f"seed{seed}" / arm / "completed/record.json"
                branches[stats.coordinate(seed, arm)] = evaluation.file_binding(path)
        evaluation.publish(self.root / "training_barrier/record.json", dict(
            schema="v54_controller_training_exit_barrier.v1", protocol_id=self.protocol["id"],
            all_nine_logical_branches_complete=True, all_18_snapshots_sealed=True,
            all_dispatched_training_workers_exited=True, active_children=[], branch_records=branches,
            worker_exits=[evaluation.file_binding(self.job_directory(job) / "actual_exit/record.json")
                          for job in self.core.values()],
            accepted_core_jobs={key: evaluation.file_binding(self.job_directory(job) / "accepted/record.json")
                                for key, job in self.core.items()},
            reused_C1_branches=[stats.coordinate(seed, "C1") for seed in stats.SEEDS
                               if self.parents[str(seed)]["c1_reuse"]["eligible"]]))
        plan = evaluation.prepare_jobs(self.root)
        for key, job in plan["jobs"].items():
            self.jobs[key] = dict(job, kind="generate", dependencies=list(self.core), priority=6)
        self.evaluation_registered = True

    def finish(self):
        require(self.evaluation_registered and set(self.jobs) == set(self.accepted) and not self.active,
                "all fixed generation jobs must have actual successful exits before final scoring")
        panels = {}
        for panel, *_ in evaluation.PANEL_SPECS:
            if self.stop_reason is not None:
                raise RuntimeError("explicit stop before next complete-panel scoring")
            panels[panel] = evaluation.score(self.root, panel)
        complete = all(all(row["status"] == "COMPLETE" for row in summary["comparisons"].values())
                       for summary in panels.values())
        primary = panels[evaluation.PRIMARY_PANEL]
        recovery_accounting = self.feedback_recovery_accounting(require_complete=True)
        promotion = stats.advancement(primary, contracts_complete=complete)
        evaluation.publish(self.root / "promotion/record.json", dict(
            schema="v54_directional_development_decision.v1", protocol_id=self.protocol["id"],
            primary_summary=evaluation.file_binding(self.root / "evaluations/panels" /
                evaluation.PRIMARY_PANEL / "summary/record.json"),
            all_panels_complete=complete, **promotion))
        value = evaluation.publish(self.root / "closeout/record.json", dict(
            schema="v54_fixed_experiment_closeout.v1", protocol_id=self.protocol["id"],
            status="COMPLETE" if complete else "EVALUATION_INCOMPLETE", active_workers=0,
            accepted_jobs=len(self.accepted), logical_branches=9, snapshots=18,
            new_feedback_sessions=2100, new_evaluation_sessions=12267,
            new_API_calls=0, old_test1147_new_generation=0,
            actual_new_optimizer_budget=self.prepared["actual_new_optimizer_budget"],
            resource_wait_seconds=self.resource_wait_seconds,
            feedback_request_recovery=recovery_accounting,
            panel_summaries={panel: evaluation.file_binding(self.root / "evaluations/panels" /
                panel / "summary/record.json") for panel in panels},
            promotion=evaluation.file_binding(self.root / "promotion/record.json"),
            automatic_followup_started=False, finished_epoch=time.time()))
        self.status(value["status"])
        return value

    def feedback_recovery_accounting(self, *, require_complete=False):
        authority = self.protocol.get("feedback_recovery")
        if authority is None:
            return None
        claims, resolutions = {}, {}
        for seed in (137, 389):
            directory = self.root / "feedback_recovery" / f"seed{seed}"
            claim_path, resolution_path = directory / "claim/record.json", directory / "resolution/record.json"
            if claim_path.exists():
                claim = evaluation.checked(claim_path)
                require(claim["protocol_id"] == self.protocol["id"]
                        and claim["authorization_id"] == authority["id"]
                        and claim["seed"] == seed and claim["authorized_reexecution_ordinal"] == 1,
                        "reexecution claim escaped the two registered one-shot requests")
                claims[str(seed)] = evaluation.file_binding(claim_path)
            if resolution_path.exists():
                resolution = evaluation.checked(resolution_path)
                require(str(seed) in claims and resolution["claim_id"] == claim["id"]
                        and resolution["protocol_id"] == self.protocol["id"]
                        and resolution["authorization_id"] == authority["id"]
                        and resolution["seed"] == seed and resolution["new_actual_model_calls"] == 1
                        and resolution["old_unknown_record_preserved"] is True
                        and resolution["old_unknown_reclassified"] is False,
                        "actual returned receipt must resolve the same independent claim")
                resolutions[str(seed)] = evaluation.file_binding(resolution_path)
        if require_complete:
            require(len(claims) == len(resolutions) == 2, "both authorized requests need actual returned receipts")
        return dict(authorization_id=authority["id"], old_unknown_calls=2,
            authorized_single_request_reexecutions=2, actual_claims=claims,
            actual_returned_receipts=resolutions, actual_returned_reexecution_calls=len(resolutions),
            old_unknowns_reclassified=False, logical_complete_feedback_budget=2100,
            old_failed_calls_are_additional_historical_attempts=True)

    def status(self, status):
        _status(self.root / "queue/status.json", dict(schema="v54_controller_queue.v1",
            protocol_id=self.protocol["id"], status=status, updated_epoch=time.time(),
            accepted_jobs=list(self.accepted), pending_jobs=[key for key in self.jobs if key not in self.launched],
            active_workers=[dict(job_id=key, gpu_index=child.gpu, pid=child.process.pid,
                birth=child.birth, lifecycle=child.lifecycle) for key, child in self.active.items()],
            max_gpu_workers=MAX_WORKERS, evaluation_registered=self.evaluation_registered,
            resource_wait_seconds=self.resource_wait_seconds, stop_reason=self.stop_reason))

    def _signal(self, child, number):
        if child.process.poll() is not None:
            return False
        observed_birth = self.runtime.birth(child.process.pid)
        if observed_birth is None:
            # Teardown can remove /proc fields before waitpid observes exit.
            # Keep its lease/slot and let reap establish the actual exit code.
            return False
        require(child.birth is not None and observed_birth == child.birth,
                "refusing to signal an unverified or reused worker PID")
        try:
            if child.pidfd is not None and hasattr(signal, "pidfd_send_signal"):
                signal.pidfd_send_signal(child.pidfd, number)
            else:
                os.kill(child.process.pid, number)
        except ProcessLookupError:
            return False
        return True

    def shutdown(self):
        deadline = time.monotonic() + STOP_GRACE_SECONDS
        for child in self.active.values():
            child.signal_sent = self._signal(child, signal.SIGTERM)
        while self.active and time.monotonic() < deadline:
            self.reap()
            self.status("STOPPING_AT_DURABLE_BOUNDARIES")
            if self.active:
                time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
        for child in self.active.values():
            self._signal(child, signal.SIGKILL)
        while self.active:
            self.reap()
            if self.active:
                time.sleep(0.2)
        status = ("STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME" if self.stop_reason["kind"] == "EXPLICIT_STOP"
                  else "STOPPED_FAILURE_NO_RETRY")
        try:
            recovery_accounting = self.feedback_recovery_accounting()
        except (ValueError, KeyError, OSError) as error:
            recovery_accounting = dict(status="UNVERIFIED", error_type=type(error).__name__, error=str(error))
        value = evaluation.publish(self.root / "closeout/record.json", dict(
            schema="v54_fixed_experiment_closeout.v1", protocol_id=self.protocol["id"], status=status,
            reason=self.stop_reason, active_workers=0, accepted_jobs=list(self.accepted),
            launched_jobs=sorted(self.launched), resource_wait_seconds=self.resource_wait_seconds,
            feedback_request_recovery=recovery_accounting,
            shared_shutdown_grace_seconds=STOP_GRACE_SECONDS, automatic_retry=False,
            historical_evidence_unchanged=True, finished_epoch=time.time()))
        self.status(status)
        return value

    def run(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "owner.lock").open("a") as owner:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require(not (self.root / "launch/record.json").exists(),
                    "V54 controller is fresh once; no implicit resume or duplicate launch")
            evaluation.publish(self.root / "launch/record.json", dict(
                schema="v54_controller_launch.v1", protocol_id=self.protocol["id"],
                pid=os.getpid(), birth=self.runtime.birth(os.getpid()), started_epoch=time.time(),
                source=str(Path(__file__).resolve()), core_jobs=self.core, max_gpu_workers=MAX_WORKERS,
                prepared=evaluation.file_binding(self.root / "prepared/record.json"), automatic_retry=False))
            previous = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}
            for number in previous:
                signal.signal(number, lambda signum, _frame: self.request_stop(
                    dict(kind="EXPLICIT_STOP", signal=signum, received_epoch=time.time())))
            try:
                while self.stop_reason is None:
                    self.reap()
                    if self.stop_reason is not None:
                        break
                    if not self.evaluation_registered and set(self.core) <= set(self.accepted) and not self.active:
                        self.seal_training()
                    if self.evaluation_registered and set(self.jobs) == set(self.accepted) and not self.active:
                        return self.finish()
                    dispatched = False
                    for job in ready_jobs(self.jobs, self.accepted, self.launched):
                        if self.stop_reason is not None or not can_dispatch(self.active):
                            break
                        acquired = self.acquire(job)
                        if acquired is not None:
                            self.launch(job, acquired)
                            dispatched = True
                    now = time.monotonic()
                    if not dispatched and ready_jobs(self.jobs, self.accepted, self.launched) and can_dispatch(self.active):
                        if self.wait_started is not None:
                            self.resource_wait_seconds += now - self.wait_started
                        self.wait_started = now
                    else:
                        self.wait_started = None
                    self.status("RUNNING" if self.active else "WAITING_FOR_REGISTERED_RESOURCES")
                    time.sleep(POLL_SECONDS)
            except BaseException as error:
                self.request_stop(dict(kind="CONTROLLER_FAILURE", error_type=type(error).__name__, error=str(error)))
            finally:
                for number, handler in previous.items():
                    signal.signal(number, handler)
            return self.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run",))
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    result = Controller(args.root).run()
    print(json.dumps(dict(status=result["status"], id=result["id"]), sort_keys=True))
    return 0 if result["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
