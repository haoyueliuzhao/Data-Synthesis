"""User-authorized four-GPU queue recovery; adopt live workers without resampling."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from trusted_synthesis.finance_research.calibration import gpu_inventory, identity, now, publish
from trusted_synthesis.finance_research.v6_collection import bound, persist, require, sha
from trusted_synthesis.finance_research.v10_workflow import (
    WORKTREE,
    available_gpus,
    child_command,
    marker_complete,
)
from trusted_synthesis.finance_research.v13_material_registration import checked, entry, read_ref
from trusted_synthesis.finance_research.v18_registration import OUTPUT
from trusted_synthesis.finance_research.v18_workflow import Supervisor as OriginalSupervisor

GPUS = [1, 2, 3, 6]
DIRECTORY = "queue_recovery_01"
LIVE_KEYS = {"arm-11-c_only", "arm-29-c_only", "arm-47-c_only", "arm-11-full"}
FAILED_KEYS = {"arm-29-full", "arm-47-full", "arm-11-static", "arm-29-static"}
HEADROOM_ERROR = "ValueError: insufficient GPU margin; no allocation/placeholder/wait"


def own_source():
    return sha(Path(__file__))


def arm_root(job):
    return Path(job["result"]).parents[1]


def wire_job(job):
    return {**job, "args": list(map(str, job["args"])), "result": str(job["result"])}


def headroom_only(job, attempt, exit_code):
    """Only an entirely unstarted arm may return to the resource queue."""
    log = Path(attempt) / "controller.log"
    return (
        exit_code == 1
        and job["module"] == "v16_arm_training"
        and job["args"][0] == "run-arm"
        and not arm_root(job).exists()
        and log.is_file()
        and log.read_text().rstrip().splitlines()[-1:] == [HEADROOM_ERROR]
    )


def validate_policy(plan):
    require(
        plan["schema"] == "v18_four_gpu_queue_recovery.v1"
        and plan["allowed_gpu_indices"] == GPUS
        and plan["max_gpu_workers"] == 4
        and plan["minimum_free_mib"] == 24576
        and plan["API_calls"] == 0
        and plan["api_model_policy"] == "deepseek-flash"
        and plan["restart_live_workers"] is False
        and plan["partial_feedback_resampling"] is False
        and plan["automatic_numerical_failure_retry"] is False,
        "fixed four GPUs, unchanged headroom and no live-worker/numerical retry required",
    )


def register(output=OUTPUT):
    output = Path(output).resolve()
    root = output / DIRECTORY
    require(not (root / "registration/record.json").exists(), "preserve recovery registration")
    original = OriginalSupervisor(output)
    handoff = checked(output / "training_handoff/record.json")
    old_launch = checked(output / "workflow_launch_01/record.json")
    old_status = json.loads((output / "workflow/status.json").read_bytes())
    require(
        identity(old_launch["pid"]) == old_launch["process_start_time_ticks"]
        and old_status["protocol_id"] == original.plan["id"]
        and old_status["phase"] == "GPU_WORK_RUNNING"
        and {c["job_key"] for c in old_status["active_children"]} == LIVE_KEYS
        and {f["key"] for f in old_status["failures"]} == FAILED_KEYS,
        "recovery applies only to the observed four live workers and four admission failures",
    )
    jobs = {j["key"]: j for j in original.arm_jobs(Path(handoff["launcher"]))}
    frozen = Path(old_launch["worktree"])
    require(
        WORKTREE.resolve() == frozen.resolve(),
        "run the recovery script with PYTHONPATH pointing to the original frozen runtime",
    )
    for name, expected in (
        original.plan["source_bindings"] | original.workflow["source_bindings"]
    ).items():
        require(
            sha(frozen / "trusted_data_synthesis/src/trusted_synthesis/finance_research" / name)
            == expected,
            "original frozen Student implementation must remain unchanged",
        )
    adopted = []
    for child in old_status["active_children"]:
        source = entry(Path(child["attempt"]) / "launch/record.json")
        launch = read_ref(source)
        job = jobs[child["job_key"]]
        require(
            identity(child["pid"]) == child["birth"] == launch["process_start_time_ticks"]
            and child["pid"] == launch["pid"]
            and child["gpu"] == launch["gpu_index"]
            and launch["key"] == child["job_key"]
            and launch["result"] == str(job["result"])
            and not list(
                arm_root(job).glob("training/outer_attempts/step*/attempt*/failure/record.json")
            ),
            "adopt only the exact still-live, not-failed original worker",
        )
        adopted.append(dict(child, original_launch=source))
    require(sorted(c["gpu"] for c in adopted) == GPUS, "use the four actually occupied GPUs")
    failures = []
    for failure in old_status["failures"]:
        attempt = output / "workflow/jobs" / failure["key"] / "attempt001"
        exit_record = checked(attempt / "exit/record.json")
        require(
            exit_record == failure
            and headroom_only(jobs[failure["key"]], attempt, exit_record["exit_code"]),
            "only the exact before-allocation failures are authorized for requeue",
        )
        failures.append(
            dict(
                key=failure["key"],
                launch=entry(attempt / "launch/record.json"),
                exit=entry(attempt / "exit/record.json"),
                error=HEADROOM_ERROR,
                original_log_sha256=sha(attempt / "controller.log"),
            )
        )
    queued = [j for key, j in jobs.items() if key not in LIVE_KEYS]
    require(
        len(queued) == 11 and all(not arm_root(j).exists() for j in queued),
        "never enqueue an existing partial arm or feedback cohort as fresh work",
    )
    record = bound(
        dict(
            schema="v18_four_gpu_queue_recovery.v1",
            at=now(),
            user_request="恢复实验，自动在当前实验使用的四张GPU上排队",
            original_registration=entry(output / "registration/record.json"),
            original_workflow=entry(output / "workflow/registration/record.json"),
            original_controller=entry(output / "workflow_launch_01/record.json"),
            original_worktree=str(frozen),
            source_sha256=own_source(),
            training_handoff=entry(output / "training_handoff/record.json"),
            material_binding=entry(output / "material/binding/record.json"),
            adopted_workers=adopted,
            original_headroom_failures=failures,
            original_status_at_authorization=old_status,
            queued_jobs=[wire_job(j) for j in queued],
            original_arm_count=15,
            allowed_gpu_indices=GPUS,
            max_gpu_workers=4,
            minimum_free_mib=24576,
            reuse_original_mainline_and_evaluation=True,
            restart_live_workers=False,
            prefix_retrained=False,
            partial_feedback_resampling=False,
            automatic_numerical_failure_retry=False,
            defer_only_unallocated_headroom_failure=True,
            old_controller_continues_reaping_its_workers=True,
            old_failed_attempts_preserved=True,
            old_workflow_registration_unchanged=True,
            API_calls=0,
            api_model_policy="deepseek-flash",
        )
    )
    validate_policy(record)
    persist(root / "registration", record)
    return record


class AdoptedProcess:
    """Observe a non-child; the original parent remains responsible for wait/exit."""

    def __init__(self, child, parent):
        self.child, self.parent = child, parent

    def poll(self):
        child = self.child
        if identity(child["pid"]) == child["birth"]:
            return None
        receipt = Path(child["attempt"]) / "exit/record.json"
        if receipt.is_file():
            result = checked(receipt)
            require(
                result["pid"] == child["pid"] and result["key"] == child["job_key"],
                "adopted exit receipt must identify the exact original process",
            )
            return result["exit_code"]
        require(
            identity(self.parent["pid"]) == self.parent["process_start_time_ticks"],
            "adopted worker exited without its parent's durable receipt; never infer success",
        )
        return None  # The old parent's ten-second reaper has not written its receipt yet.


class Supervisor(OriginalSupervisor):
    mainline_schema = "v18_four_gpu_recovered_mainline_result.v1"

    def __init__(self, output):
        super().__init__(output)
        self.root = self.output / DIRECTORY
        self.recovery = checked(self.root / "registration/record.json")
        validate_policy(self.recovery)
        require(
            self.recovery["source_sha256"] == own_source()
            and self.recovery["original_registration"]
            == entry(self.output / "registration/record.json")
            and self.recovery["original_workflow"]
            == entry(self.output / "workflow/registration/record.json"),
            "frozen recovery code and original scientific registrations required",
        )
        self.parent = read_ref(self.recovery["original_controller"])
        self.handoff = read_ref(self.recovery["training_handoff"])
        require(
            self.recovery["material_binding"]
            == entry(self.output / "material/binding/record.json"),
            "queue recovery cannot replace scientific material",
        )
        self.frozen = Path(self.recovery["original_worktree"])
        require(
            WORKTREE.resolve() == self.frozen.resolve(),
            "the controller and its children must share the original frozen runtime",
        )
        self.workflow = {**self.workflow, "allowed_gpu_indices": GPUS, "max_gpu_workers": 4}
        self.max_gpu_workers = 4

    def guard_old_dispatch(self):
        if identity(self.parent["pid"]) != self.parent["process_start_time_ticks"]:
            return
        state = json.loads((self.output / "workflow/status.json").read_bytes())
        require(
            {c["job_key"] for c in state["active_children"]} <= LIVE_KEYS
            and FAILED_KEYS <= {f["key"] for f in state.get("failures", [])},
            "the old failed queue must not dispatch new work alongside recovery",
        )

    def adopt(self):
        jobs = {j["key"]: j for j in self.arm_jobs(Path(self.handoff["launcher"]))}
        require(
            [wire_job(j) for key, j in jobs.items() if key not in LIVE_KEYS]
            == self.recovery["queued_jobs"],
            "pending arms must still be the eleven unstarted jobs authorized at registration",
        )
        for child in self.recovery["adopted_workers"]:
            read_ref(child["original_launch"])
            key = child["job_key"]
            attempt = self.root / "jobs" / key / "adopt001"
            require(
                not attempt.exists(), "live-worker adoption is one-shot, not a silent cold restart"
            )
            publish(
                attempt / "adoption",
                bound(
                    dict(
                        schema="v18_existing_worker_adoption.v1",
                        at=now(),
                        recovery_id=self.recovery["id"],
                        original_launch=child["original_launch"],
                        pid=child["pid"],
                        birth=child["birth"],
                        gpu=child["gpu"],
                        no_signal_sent=True,
                        no_model_or_feedback_restarted=True,
                    )
                ),
            )
            self.children[key] = dict(
                process=AdoptedProcess(child, self.parent),
                pid=child["pid"],
                birth=child["birth"],
                gpu=child["gpu"],
                attempt=str(attempt),
                job=jobs[key],
                adopted=True,
            )

    def launch(self, job, *, gpu=None):
        require(gpu in GPUS and len(self.children) < 4, "four-GPU concurrency is a hard limit")
        self.guard_old_dispatch()
        directory = self.root / "jobs" / job["key"]
        attempt = directory / f"attempt{len(list(directory.glob('attempt*'))) + 1:03d}"
        attempt.mkdir(parents=True, exist_ok=False)
        command = child_command(job["module"], job["args"] + [job.get("gpu_flag", "--gpu"), gpu])
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
                    schema="v18_recovered_child_launch.v1",
                    at=now(),
                    recovery_id=self.recovery["id"],
                    key=job["key"],
                    pid=process.pid,
                    process_start_time_ticks=birth,
                    command=command,
                    gpu_index=gpu,
                    worktree=str(self.frozen),
                    protocol_id=self.plan["id"],
                    result=str(job["result"]),
                    original_headroom_failure_recovery=job["key"] in FAILED_KEYS,
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
            adopted=False,
        )

    def reap_recovery(self):
        failures, deferred = [], []
        for key, item in list(self.children.items()):
            code = item["process"].poll()
            if code is None:
                continue
            complete = code == 0 and marker_complete(item["job"]["result"])
            resource_wait = not item["adopted"] and headroom_only(
                item["job"], item["attempt"], code
            )
            record = bound(
                dict(
                    schema="v18_recovery_worker_exit.v1",
                    at=now(),
                    key=key,
                    pid=item["pid"],
                    exit_code=code,
                    completed=complete,
                    adopted_original_worker=item["adopted"],
                    result=str(item["job"]["result"]),
                    failed_attempt_retained=True,
                    unallocated_headroom_deferral=resource_wait,
                    partial_feedback_resampled=False,
                )
            )
            publish(Path(item["attempt"]) / "exit", record)
            del self.children[key]
            if resource_wait:
                deferred.append(item["job"])
            elif not complete:
                failures.append(record)
        return failures, deferred

    def gpu_queue(self, jobs, allowed):
        require(
            list(allowed) == GPUS, "every training, dev and mechanism queue uses the same four GPUs"
        )
        pending = [
            j for j in jobs if j["key"] not in self.children and not marker_complete(j["result"])
        ]
        failures, deferrals = [], 0
        while pending or self.children:
            new_failures, deferred = self.reap_recovery()
            failures.extend(new_failures)
            pending.extend(deferred)
            deferrals += len(deferred)
            if failures and not self.children:
                self.update(
                    "BLOCKED_GPU_JOB_SAVED",
                    failures=failures,
                    unstarted=[j["key"] for j in pending],
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
                while pending and free and len(self.children) < 4:
                    self.launch(pending.pop(0), gpu=free.pop(0))
            self.update(
                "FOUR_GPU_QUEUE_RUNNING" if self.children else "WAITING_FOR_FOUR_GPU_HEADROOM",
                allowed_gpu_indices=GPUS,
                recovery_id=self.recovery["id"],
                queued=[j["key"] for j in pending],
                failures=failures,
                headroom_deferrals=deferrals,
                adopted_live_workers=[k for k, c in self.children.items() if c["adopted"]],
                historical_headroom_failures_preserved=True,
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
        self.adopt()
        return self.run_remaining_mainline(self.handoff)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.action == "register":
        print(json.dumps(dict(id=register(args.output)["id"])))
        return
    root = args.output / DIRECTORY
    root.mkdir(parents=True, exist_ok=True)
    with (root / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        supervisor = Supervisor(args.output)

        def stop_requested(signum, frame):
            supervisor.stop = True  # Drain actual workers; never interrupt partial700.

        signal.signal(signal.SIGTERM, stop_requested)
        signal.signal(signal.SIGINT, stop_requested)
        try:
            result = supervisor.run()
        except Exception as exc:
            issue = bound(
                dict(
                    at=now(),
                    error_type=type(exc).__name__,
                    error=str(exc),
                    original_workers_not_signaled=True,
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
