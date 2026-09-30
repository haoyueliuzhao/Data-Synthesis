"""Queued-only execution upgrade; existing workers are observed, never signaled."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import finqa_v18_four_gpu_queue_recovery as previous
from finqa_v19_execution_profile import (
    GPUS,
    OPTIMIZED_KEYS,
    ROOT,
    admitted_validation,
    checked_profile,
    guard_dispatcher,
)

from trusted_synthesis.finance_research.calibration import gpu_inventory, identity, now, publish
from trusted_synthesis.finance_research.v6_collection import bound, require
from trusted_synthesis.finance_research.v10_workflow import (
    available_gpus,
    child_command,
    marker_complete,
)
from trusted_synthesis.finance_research.v13_material_registration import checked, entry


class DetachedProcess:
    """Cold controller restore: identify live children, never invent OS exit status."""

    def __init__(self, launch, attempt, result_complete):
        self.launch, self.attempt, self.result_complete = launch, Path(attempt), result_complete
        self.exit_code_source = "live_identity"
        self.actual_exit_code = None

    def poll(self):
        if identity(self.launch["pid"]) == self.launch["process_start_time_ticks"]:
            return None
        path = self.attempt / "exit/record.json"
        if path.exists():
            old = checked(path)
            self.actual_exit_code = old.get("exit_code")
            self.exit_code_source = "previous_durable_exit"
            return 0 if old["completed"] else self.actual_exit_code or 1
        self.exit_code_source = (
            "durable_final_result_without_OS_wait_status"
            if self.result_complete()
            else "unknown_exit_without_final_result"
        )
        return 0 if self.result_complete() else 1


class Supervisor(previous.Supervisor):
    mainline_schema = "v19_queued_execution_complete_mainline.v1"

    def __init__(self, profile_root=ROOT, *, resume=False):
        self.profile_root = Path(profile_root).resolve()
        self.profile = checked_profile(self.profile_root)
        # The original material/launcher/role gates are still the same frozen code.
        super().__init__(self.profile_root.parent)
        self.root = self.profile_root / "queue"
        self.profile_ref = entry(self.profile_root / "registration/record.json")
        self.workflow = {**self.workflow, "allowed_gpu_indices": GPUS, "max_gpu_workers": 4}
        self.max_gpu_workers = 4
        self.resume = resume
        self.history_root = self.root / "jobs"
        require(
            resume or not self.history_root.exists(),
            "existing queue attempts require the explicit resume action",
        )

    def guard_old_dispatch(self):
        super().guard_old_dispatch()
        guard_dispatcher(self.profile)

    def arm_jobs(self, launcher):
        jobs = super().arm_jobs(launcher)
        for job in jobs:
            if job["key"] in OPTIMIZED_KEYS:
                job["script"] = Path(__file__).parent / "finqa_v19_profiled_worker.py"
                job["args"] += ["--profile-root", self.profile_root]
                job["requires_validation"] = True
                job["execution_kind"] = "v19_optimized_replay"
            else:
                job["execution_kind"] = "protected_or_original_numeric_training"
        return jobs

    def validation_job(self):
        return dict(
            key="replay-CUDA-equivalence-gate",
            module="validation_gate",
            script=Path(__file__).parent / "finqa_v19_validate_replay.py",
            args=["--root", self.profile_root],
            gpu_flag="--gpu-index",
            result=self.profile_root / "validation/result/record.json",
            execution_kind="existing_token_no_generation_validation",
        )

    def job_complete(self, job):
        if not marker_complete(job["result"]):
            return False
        if job["module"] == "validation_gate":
            result = checked(job["result"])
            return (
                result["execution_profile_id"] == self.profile["id"] and result["admitted"] is True
            )
        if job["key"] in OPTIMIZED_KEYS:
            result = checked(job["result"])
            require(
                result.get("execution_profile") == self.profile_ref
                and result.get("execution_producer") == "v19_profiled_worker.v1",
                "a pending optimized arm cannot silently finish with a different runtime",
            )
        return True

    def eligible_job(self, job):
        if job["module"] == "validation_gate":
            source = Path(self.profile["validation"]["required_completed_outer"])
            return (source / "record.json").is_file() and (source / "outer_inputs.pt").is_file()
        if not job.get("requires_validation"):
            return True
        path = self.profile_root / "validation/result/record.json"
        if not path.exists():
            return False
        admitted_validation(self.profile_root, self.profile)
        return True

    def recover_active(self, jobs):
        protected = {c["job_key"]: c for c in self.profile["protected_workers"]}
        for job in jobs:
            key = job["key"]
            if key in self.children:
                continue
            if key in protected:
                child = protected[key]
                if self.job_complete(job) and identity(child["pid"]) != child["birth"]:
                    continue
                attempt = self.history_root / key / "adopt001"
                adoption = attempt / "adoption/record.json"
                if adoption.exists():
                    require(self.resume, "existing adoption requires resume")
                    old = checked(adoption)
                    require(
                        old["pid"] == child["pid"]
                        and old["birth"] == child["birth"]
                        and old["execution_profile_id"] == self.profile["id"],
                        "protected worker identity changed",
                    )
                else:
                    publish(
                        attempt / "adoption",
                        bound(
                            dict(
                                schema="v19_protected_worker_observation.v1",
                                at=now(),
                                execution_profile_id=self.profile["id"],
                                original_launch=child["original_launch"],
                                pid=child["pid"],
                                birth=child["birth"],
                                gpu=child["gpu"],
                                new_runtime_not_installed_in_this_worker=True,
                                no_signal_sent=True,
                                no_checkpoint_or_feedback_modified=True,
                            )
                        ),
                    )
                if (attempt / "exit/record.json").exists() and not self.job_complete(job):
                    raise ValueError("protected worker previously failed; do not restart it")
                self.children[key] = dict(
                    process=previous.AdoptedProcess(child, self.parent),
                    pid=child["pid"],
                    birth=child["birth"],
                    gpu=child["gpu"],
                    attempt=str(attempt),
                    job=job,
                    protected=True,
                    detached=False,
                )
                continue
            attempts = sorted((self.history_root / key).glob("attempt*"))
            if not attempts:
                if self.job_complete(job):
                    continue
                if job["module"] == "v16_arm_training":
                    require(
                        not previous.arm_root(job).exists(),
                        "unowned partial arm requires explicit recovery, never fresh sampling",
                    )
                continue
            require(self.resume, "existing worker attempt requires explicit controller resume")
            attempt = attempts[-1]
            launch_path = attempt / "launch/record.json"
            require(
                launch_path.exists(),
                "unsettled launch has no durable PID receipt; inspect before resume",
            )
            launch = checked(launch_path)
            require(
                launch["execution_profile_id"] == self.profile["id"] and launch["key"] == key,
                "cold queue restore changed execution profile",
            )
            live = identity(launch["pid"]) == launch["process_start_time_ticks"]
            if not live and self.job_complete(job):
                continue
            exit_path = attempt / "exit/record.json"
            if not live and exit_path.exists():
                old = checked(exit_path)
                require(
                    old["unallocated_headroom_deferral"] is True,
                    "recorded failure needs explicit inspection; no automatic numerical retry",
                )
                continue
            process = DetachedProcess(launch, attempt, lambda j=job: self.job_complete(j))
            self.children[key] = dict(
                process=process,
                pid=launch["pid"],
                birth=launch["process_start_time_ticks"],
                gpu=launch["gpu_index"],
                attempt=str(attempt),
                job=job,
                protected=False,
                detached=True,
            )

    def launch(self, job, *, gpu=None):
        require(gpu in GPUS and len(self.children) < 4, "four-GPU concurrency limit")
        require(self.eligible_job(job), "optimized worker cannot precede CUDA acceptance")
        self.guard_old_dispatch()
        directory = self.history_root / job["key"]
        attempt = directory / f"attempt{len(list(directory.glob('attempt*'))) + 1:03d}"
        attempt.mkdir(parents=True, exist_ok=False)
        arguments = job["args"] + [job.get("gpu_flag", "--gpu"), gpu]
        command = (
            [sys.executable, "-u", str(job["script"]), *map(str, arguments)]
            if job.get("script")
            else child_command(job["module"], arguments)
        )
        command = [
            self.profile["taskset"]["path"],
            "--cpu-list",
            self.profile["cpu_affinity"][str(gpu)],
            *command,
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.frozen / "trusted_data_synthesis/src")
        with (attempt / "controller.log").open("xb") as log:
            process = subprocess.Popen(
                command,
                cwd=self.frozen,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        birth = identity(process.pid)
        publish(
            attempt / "launch",
            bound(
                dict(
                    schema="v19_queued_worker_launch.v1",
                    at=now(),
                    execution_profile_id=self.profile["id"],
                    key=job["key"],
                    pid=process.pid,
                    process_start_time_ticks=birth,
                    gpu_index=gpu,
                    command=command,
                    result=str(job["result"]),
                    base_runtime_worktree=str(self.frozen),
                    execution_kind=job.get("execution_kind", "original_evaluation_or_mechanism"),
                    requested_cpu_affinity=self.profile["cpu_affinity"][str(gpu)],
                    protected_running_workers_not_changed=True,
                    new_sampling_retry=False,
                )
            ),
        )
        self.children[job["key"]] = dict(
            process=process,
            pid=process.pid,
            birth=birth,
            gpu=gpu,
            attempt=str(attempt),
            job=job,
            protected=False,
            detached=False,
        )

    def headroom_deferral(self, item, code):
        if item["protected"]:
            return False
        if item["job"]["module"] == "validation_gate":
            log = Path(item["attempt"]) / "controller.log"
            return (
                code == 1
                and not (self.profile_root / "validation/attempt/intent/record.json").exists()
                and log.exists()
                and log.read_text().rstrip().splitlines()[-1:] == [previous.HEADROOM_ERROR]
            )
        return previous.headroom_only(item["job"], item["attempt"], code)

    def reap_profiled(self):
        failures, deferred = [], []
        for key, item in list(self.children.items()):
            code = item["process"].poll()
            if code is None:
                continue
            complete = code == 0 and self.job_complete(item["job"])
            wait = self.headroom_deferral(item, code)
            actual_code = item["process"].actual_exit_code if item["detached"] else code
            source = (
                item["process"].exit_code_source
                if item["detached"]
                else "original_parent_receipt"
                if item["protected"]
                else "Popen_wait_status"
            )
            record = bound(
                dict(
                    schema="v19_queued_worker_exit.v1",
                    at=now(),
                    key=key,
                    pid=item["pid"],
                    execution_profile_id=self.profile["id"],
                    exit_code=actual_code,
                    exit_code_source=source,
                    completed=complete,
                    result=str(item["job"]["result"]),
                    unallocated_headroom_deferral=wait,
                    failed_attempt_retained=True,
                    partial_feedback_resampled=False,
                )
            )
            path = Path(item["attempt"]) / "exit/record.json"
            if not path.exists():
                publish(path.parent, record)
            del self.children[key]
            if wait:
                deferred.append(item["job"])
            elif not complete:
                failures.append(record)
        return failures, deferred

    def gpu_queue(self, jobs, allowed):
        require(list(allowed) == GPUS, "all stages remain on the original four GPUs")
        if any(j["key"] in OPTIMIZED_KEYS for j in jobs):
            jobs = [self.validation_job(), *jobs]
        self.recover_active(jobs)
        pending = [j for j in jobs if j["key"] not in self.children and not self.job_complete(j)]
        failures = []
        while pending or self.children:
            new_failures, deferred = self.reap_profiled()
            failures.extend(new_failures)
            pending.extend(deferred)
            if failures and not self.children:
                self.update(
                    "BLOCKED_SAVED", failures=failures, unstarted=[j["key"] for j in pending]
                )
                return False
            if not failures and not self.stop:
                self.guard_old_dispatch()
                free = available_gpus(
                    gpu_inventory(),
                    allowed=GPUS,
                    occupied=[c["gpu"] for c in self.children.values()],
                    minimum_free_mib=24576,
                )
                while free and len(self.children) < 4:
                    candidate = next((j for j in pending if self.eligible_job(j)), None)
                    if candidate is None:
                        break
                    pending.remove(candidate)
                    self.launch(candidate, gpu=free.pop(0))
            self.update(
                "V19_FOUR_GPU_QUEUE_RUNNING"
                if self.children
                else "WAITING_FOR_FREE_GPU_OR_ACCEPTANCE",
                execution_profile_id=self.profile["id"],
                allowed_gpu_indices=GPUS,
                queued=[j["key"] for j in pending],
                failures=failures,
                protected_live_workers=[k for k, c in self.children.items() if c["protected"]],
                optimized_jobs_require_CUDA_validation=True,
                no_running_worker_runtime_change=True,
            )
            if self.stop and not self.children:
                return False
            if pending or self.children:
                time.sleep(10)
        return not failures and not self.stop

    def run(self):
        if self.admission_blocked():
            return None
        self.guard_old_dispatch()
        return self.run_remaining_mainline(self.handoff)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "resume"))
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root / "queue"
    root.mkdir(parents=True, exist_ok=True)
    with (root / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        supervisor = Supervisor(args.root, resume=args.action == "resume")

        def stop_requested(signum, frame):
            supervisor.stop = True  # No signal is forwarded to any Student.

        signal.signal(signal.SIGTERM, stop_requested)
        signal.signal(signal.SIGINT, stop_requested)
        try:
            result = supervisor.run()
        except Exception as error:
            issue = bound(
                dict(
                    at=now(),
                    error_type=type(error).__name__,
                    error=str(error),
                    no_Student_signal_sent=True,
                    no_implicit_retry=True,
                )
            )
            publish(root / "blocked" / issue["id"], issue)
            supervisor.update("BLOCKED_SAVED", issue=issue)
            raise
        if result is not None:
            print(json.dumps(dict(id=result["id"])))


if __name__ == "__main__":
    main()
