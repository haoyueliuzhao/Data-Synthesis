"""Add GPU4 to the pending queue without changing frozen replay or live Students."""

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

import finqa_v18_four_gpu_queue_recovery as recovery
import finqa_v19_execution_profile as base_profile
import finqa_v19_profiled_worker as base_worker
import finqa_v19_queued_scheduler as base_queue
import finqa_v19_validate_replay as base_validation
from finqa_v19_optimized_replay import bind_dependencies

from trusted_synthesis.finance_research.calibration import gpu_inventory, identity, now, publish
from trusted_synthesis.finance_research.v6_collection import bound, persist, require, sha
from trusted_synthesis.finance_research.v10_workflow import available_gpus, child_command
from trusted_synthesis.finance_research.v13_material_registration import checked, entry, read_ref

PARENT = base_profile.ROOT
ROOT = PARENT.parent / "five_gpu_queue_01"
GPUS = [1, 2, 3, 4, 6]
CHANGED_FIELDS = {
    "id",
    "schema",
    "at",
    "user_request",
    "allowed_gpu_indices",
    "max_gpu_workers",
    "cpu_affinity",
    "paused_dispatcher",
}


def own_source():
    return sha(Path(__file__))


def check_inheritance(value, parent):
    require(
        all(value.get(k) == v for k, v in parent.items() if k not in CHANGED_FIELDS),
        "GPU extension cannot change scientific, replay, validation or recovery rules",
    )
    require(
        value["schema"] == "v20_five_gpu_execution_extension.v1"
        and value["allowed_gpu_indices"] == GPUS
        and value["max_gpu_workers"] == len(GPUS)
        and value["cpu_affinity"] == {**parent["cpu_affinity"], "4": parent["cpu_affinity"]["6"]}
        and value["resource_extension_source_sha256"] == own_source()
        and value["restart_or_migrate_live_workers"] is False
        and value["GPU4_exclusive_ownership_claimed"] is False,
        "only GPU4 and one additional queue slot are authorized",
    )


def check_parent_handoff(value):
    require(
        value["parent_execution_profile"] == entry(PARENT / "registration/record.json")
        and value["parent_controller"] == entry(PARENT / "launch_01/record.json"),
        "preserve the exact previous profile and controller",
    )
    pause = read_ref(value["paused_dispatcher"])
    previous = read_ref(value["parent_controller"])
    require(
        pause["target_pid"] == previous["pid"]
        and pause["target_birth"] == previous["process_start_time_ticks"]
        and pause["old_dispatcher_owned_Student_children"] == 0
        and pause["no_Student_signal_sent"] is True,
        "resource extension requires the recorded CPU-only dispatcher handoff",
    )


def checked_profile(root=ROOT):
    root = Path(root).resolve()
    value = checked(root / "registration/record.json")
    parent = base_profile.checked_profile(PARENT)
    check_parent_handoff(value)
    check_inheritance(value, parent)
    return value


def register(root=ROOT):
    root = Path(root).resolve()
    require(not (root / "registration/record.json").exists(), "preserve GPU extension registration")
    parent = base_profile.checked_profile(PARENT)
    require(
        not list((PARENT / "queue/jobs").glob("*/attempt*"))
        and not (PARENT / "validation").exists(),
        "this extension is only for the still-unstarted pending execution profile",
    )
    for job in parent["queued_jobs"]:
        require(not Path(job["result"]).parents[1].exists(), "do not restart a partial arm")
    affinity = Path("/sys/devices/system/node/node1/cpulist").read_text().strip()
    require(affinity == parent["cpu_affinity"]["6"], "observed GPU4 and GPU6 NUMA CPU set required")
    value = bound(
        dict(
            **{k: v for k, v in parent.items() if k not in CHANGED_FIELDS},
            schema="v20_five_gpu_execution_extension.v1",
            at=now(),
            user_request="增加GPU4为可用，调整排队任务",
            parent_execution_profile=entry(PARENT / "registration/record.json"),
            parent_controller=entry(PARENT / "launch_01/record.json"),
            resource_extension_source_sha256=own_source(),
            allowed_gpu_indices=GPUS,
            max_gpu_workers=len(GPUS),
            cpu_affinity={**parent["cpu_affinity"], "4": affinity},
            paused_dispatcher=entry(root / "dispatcher_pause_receipt/record.json"),
            restart_or_migrate_live_workers=False,
            GPU4_exclusive_ownership_claimed=False,
            GPU4_NUMA_node=1,
            previous_registration_unchanged=True,
        )
    )
    check_parent_handoff(value)
    check_inheritance(value, parent)
    base_profile.guard_dispatcher(parent)
    base_profile.guard_dispatcher(value)
    persist(root / "registration", value)
    return value


def validate(root=ROOT, *, gpu_index):
    # Reuse the registered four cases, exact equality/timing criterion and code.
    run = bind_dependencies(base_validation.run, checked_profile=checked_profile)
    return run(root, gpu_index=gpu_index)


def run_arm(output, seed, arm, gpu_index, *, profile_root=ROOT, resume=False):
    # No mutable patch of either frozen module; only the resource profile loader differs.
    run = bind_dependencies(base_worker.run, checked_profile=checked_profile)
    return run(output, seed, arm, gpu_index, profile_root=profile_root, resume=resume)


class Supervisor(base_queue.Supervisor):
    mainline_schema = "v20_five_gpu_complete_mainline.v1"

    def __init__(self, profile_root=ROOT, *, resume=False):
        self.profile_root = Path(profile_root).resolve()
        self.profile = checked_profile(self.profile_root)
        # The original V18 material/mainline and V19 process recovery are retained.
        recovery.Supervisor.__init__(self, self.profile_root.parent)
        self.root = self.profile_root / "queue"
        self.profile_ref = entry(self.profile_root / "registration/record.json")
        self.workflow = {**self.workflow, "allowed_gpu_indices": GPUS, "max_gpu_workers": len(GPUS)}
        self.max_gpu_workers = len(GPUS)
        self.resume = resume
        self.history_root = self.root / "jobs"
        require(
            resume or not self.history_root.exists(), "existing attempts require explicit resume"
        )

    def guard_old_dispatch(self):
        recovery.Supervisor.guard_old_dispatch(self)
        base_profile.guard_dispatcher(read_ref(self.profile["parent_execution_profile"]))
        base_profile.guard_dispatcher(self.profile)

    def arm_jobs(self, launcher):
        jobs = super().arm_jobs(launcher)
        for job in jobs:
            if job["key"] in base_profile.OPTIMIZED_KEYS:
                job["script"] = Path(__file__)
                job["execution_kind"] = "unchanged_v19_replay_with_GPU4_resource_extension"
        return jobs

    def validation_job(self):
        job = super().validation_job()
        job.update(script=Path(__file__), args=["validate", "--root", self.profile_root])
        return job

    def launch(self, job, *, gpu=None):
        require(gpu in GPUS and len(self.children) < len(GPUS), "five-GPU concurrency limit")
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
                    schema="v20_five_gpu_worker_launch.v1",
                    at=now(),
                    execution_profile_id=self.profile["id"],
                    parent_execution_profile=self.profile["parent_execution_profile"],
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

    def gpu_queue(self, jobs, allowed):
        require(list(allowed) == GPUS, "all stages use only the authorized five GPUs")
        if any(j["key"] in base_profile.OPTIMIZED_KEYS for j in jobs):
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
                    minimum_free_mib=self.profile["minimum_free_mib"],
                )
                while free and len(self.children) < len(GPUS):
                    candidate = next((j for j in pending if self.eligible_job(j)), None)
                    if candidate is None:
                        break
                    pending.remove(candidate)
                    self.launch(candidate, gpu=free.pop(0))
            self.update(
                "V20_FIVE_GPU_QUEUE_RUNNING"
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("register", "run", "resume", "validate", "run-arm", "resume-arm")
    )
    parser.add_argument("--root", "--profile-root", dest="root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int, choices=(29, 47))
    parser.add_argument("--arm", choices=("Full",))
    parser.add_argument("--gpu-index", type=int, choices=GPUS)
    args = parser.parse_args()
    if args.action == "register":
        result = register(args.root)
    elif args.action == "validate":
        require(args.gpu_index is not None, "validation requires an explicit GPU")
        result = validate(args.root, gpu_index=args.gpu_index)
    elif args.action in ("run-arm", "resume-arm"):
        require(
            all(v is not None for v in (args.output, args.seed, args.arm, args.gpu_index)),
            "worker requires the original output, seed, arm and explicit GPU",
        )
        result = run_arm(
            args.output,
            args.seed,
            args.arm,
            args.gpu_index,
            profile_root=args.root,
            resume=args.action == "resume-arm",
        )
    else:
        root = args.root / "queue"
        root.mkdir(parents=True, exist_ok=True)
        with (root / "controller.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            supervisor = Supervisor(args.root, resume=args.action == "resume")

            def stop_requested(signum, frame):
                supervisor.stop = True  # Never signal any Student.

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
