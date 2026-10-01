"""GPU0 resource extension; retain live Full29's V20 profile and real parent reaper."""

from __future__ import annotations

import argparse
import fcntl
import json
import signal
from pathlib import Path

import finqa_v18_four_gpu_queue_recovery as recovery
import finqa_v19_execution_profile as replay_profile
import finqa_v19_profiled_worker as replay_worker
import finqa_v19_queued_scheduler as original_queue
import finqa_v20_five_gpu_queue as previous
from finqa_v19_optimized_replay import bind_dependencies

from trusted_synthesis.finance_research.calibration import identity, now, publish
from trusted_synthesis.finance_research.v6_collection import bound, persist, require, sha
from trusted_synthesis.finance_research.v10_workflow import marker_complete
from trusted_synthesis.finance_research.v13_material_registration import checked, entry, read_ref

PARENT = previous.ROOT
ROOT = PARENT.parent / "six_gpu_queue_01"
GPUS = [0, 1, 2, 3, 4, 6]
CONTINUED_KEY = "arm-29-full"
NEW_PROFILE_KEYS = ["arm-47-full"]
CHANGED_FIELDS = {
    "id",
    "schema",
    "at",
    "user_request",
    "allowed_gpu_indices",
    "max_gpu_workers",
    "cpu_affinity",
    "parent_execution_profile",
    "parent_controller",
    "resource_extension_source_sha256",
    "optimized_job_keys",
}


def own_source():
    return sha(Path(__file__))


def parent_launches():
    return [entry(p) for p in sorted((PARENT / "queue/jobs").glob("*/attempt*/launch/record.json"))]


def check_inheritance(value, parent):
    require(
        all(value.get(k) == v for k, v in parent.items() if k not in CHANGED_FIELDS),
        "GPU0 extension cannot change inherited numerical or recovery rules",
    )
    require(
        value["schema"] == "v21_six_gpu_execution_extension.v1"
        and value["allowed_gpu_indices"] == GPUS
        and value["max_gpu_workers"] == len(GPUS)
        and value["cpu_affinity"] == {**parent["cpu_affinity"], "0": parent["cpu_affinity"]["1"]}
        and value["optimized_job_keys"] == NEW_PROFILE_KEYS
        and value["resource_extension_source_sha256"] == own_source()
        and value["new_CUDA_validation_claimed"] is False
        and value["live_Full29_profile_unchanged"] is True
        and value["continued_worker"]["job_key"] == CONTINUED_KEY
        and value["continued_worker"]["gpu"] == 4,
        "only GPU0, a sixth slot and unstarted Full47's resource profile may change",
    )


def checked_profile(root=ROOT):
    value = checked(Path(root) / "registration/record.json")
    parent = previous.checked_profile(PARENT)
    require(
        value["parent_execution_profile"] == entry(PARENT / "registration/record.json")
        and value["parent_controller"] == entry(PARENT / "launch_01/record.json")
        and value["inherited_CUDA_validation"] == entry(PARENT / "validation/result/record.json")
        and value["continued_worker"]["worker_execution_profile"]
        == value["parent_execution_profile"],
        "preserve the live worker's exact profile and the actual prior CUDA acceptance",
    )
    old = read_ref(value["continued_worker"]["original_launch"])
    worker = value["continued_worker"]
    require(
        old["key"] == worker["job_key"]
        and old["pid"] == worker["pid"]
        and old["process_start_time_ticks"] == worker["birth"]
        and old["gpu_index"] == worker["gpu"]
        and old["execution_profile_id"] == parent["id"],
        "the continued Full29 must remain the same originally launched process",
    )
    drain = read_ref(value["parent_drain_receipt"])
    controller = read_ref(value["parent_controller"])
    require(
        drain["target_pid"] == controller["pid"]
        and drain["target_birth"] == controller["process_start_time_ticks"]
        and drain["signal"] == "SIGTERM_controller_only"
        and drain["no_Student_signal_sent"] is True
        and drain["post_signal_heartbeat_observed"] is True
        and drain["parent_launches_unchanged"] is True
        and drain["parent_retained_for_exit_receipts"] is True,
        "preserve the original parent's draining and durable-exit responsibilities",
    )
    check_inheritance(value, parent)
    return value


def inherited_validation(root=ROOT, profile=None):
    profile = profile or checked_profile(root)
    parent = previous.checked_profile(PARENT)
    check_inheritance(profile, parent)
    result = replay_profile.admitted_validation(PARENT, parent)
    require(
        profile["inherited_CUDA_validation"] == entry(PARENT / "validation/result/record.json")
        and result["execution_profile_id"] == parent["id"],
        "do not relabel previous measurements as a new GPU0 validation",
    )
    return result  # Original ID, measured GPU and execution_profile_id are not rewritten.


def guard_parent(profile):
    drain = read_ref(profile["parent_drain_receipt"])
    require(
        parent_launches() == drain["parent_launch_bindings"], "draining parent dispatched new work"
    )
    parent = read_ref(profile["parent_controller"])
    if identity(parent["pid"]) == parent["process_start_time_ticks"]:
        require(
            replay_profile.process_state(parent["pid"]) not in ("T", "t", "Z"),
            "live Full29's original parent must remain runnable to persist its exit status",
        )


def register(root=ROOT):
    root = Path(root).resolve()
    require(not (root / "registration/record.json").exists(), "preserve six-GPU registration")
    parent = previous.checked_profile(PARENT)
    accepted = replay_profile.admitted_validation(PARENT, parent)
    state = json.loads((PARENT / "queue/status.json").read_bytes())
    require(
        not state["failures"]
        and {c["job_key"] for c in state["active_children"]}
        == {c["job_key"] for c in parent["protected_workers"]} | {CONTINUED_KEY},
        "retain precisely the five observed live workers",
    )
    child = next(c for c in state["active_children"] if c["job_key"] == CONTINUED_KEY)
    require(identity(child["pid"]) == child["birth"], "original Full29 must still be alive")
    remaining = [j for j in parent["queued_jobs"] if j["key"] != CONTINUED_KEY]
    require(
        state["queued"] == [j["key"] for j in remaining]
        and all(not Path(j["result"]).parents[1].exists() for j in remaining),
        "only the ten still-unstarted arms may be scheduled anew",
    )
    affinity = Path("/sys/devices/system/node/node0/cpulist").read_text().strip()
    require(affinity == parent["cpu_affinity"]["1"], "observed GPU0 and GPU1 NUMA CPU set required")
    value = bound(
        dict(
            **{k: v for k, v in parent.items() if k not in CHANGED_FIELDS},
            schema="v21_six_gpu_execution_extension.v1",
            at=now(),
            user_request="将GPU0也纳入",
            parent_execution_profile=entry(PARENT / "registration/record.json"),
            parent_controller=entry(PARENT / "launch_01/record.json"),
            resource_extension_source_sha256=own_source(),
            allowed_gpu_indices=GPUS,
            max_gpu_workers=len(GPUS),
            cpu_affinity={**parent["cpu_affinity"], "0": affinity},
            optimized_job_keys=NEW_PROFILE_KEYS,
            parent_drain_receipt=entry(root / "parent_drain_receipt/record.json"),
            inherited_CUDA_validation=entry(PARENT / "validation/result/record.json"),
            inherited_CUDA_validation_id=accepted["id"],
            new_CUDA_validation_claimed=False,
            live_Full29_profile_unchanged=True,
            continued_worker=dict(
                child,
                original_launch=entry(Path(child["attempt"]) / "launch/record.json"),
                worker_execution_profile=entry(PARENT / "registration/record.json"),
            ),
            pending_job_keys=[j["key"] for j in remaining],
            GPU0_NUMA_node=0,
            same_A100_hardware_family_observed=True,
        )
    )
    check_inheritance(value, parent)
    guard_parent(value)
    persist(root / "registration", value)
    return checked_profile(root)


def run_arm(output, seed, arm, gpu_index, *, profile_root=ROOT, resume=False):
    execute = bind_dependencies(
        replay_worker.run, checked_profile=checked_profile, admitted_validation=inherited_validation
    )
    return execute(output, seed, arm, gpu_index, profile_root=profile_root, resume=resume)


def six_gpu_require(condition, message):
    require(condition, message.replace("five-GPU", "six-GPU").replace("five GPUs", "six GPUs"))


class Supervisor(original_queue.Supervisor):
    mainline_schema = "v21_six_gpu_complete_mainline.v1"

    def __init__(self, profile_root=ROOT, *, resume=False):
        self.profile_root = Path(profile_root).resolve()
        self.profile = checked_profile(self.profile_root)
        inherited_validation(self.profile_root, self.profile)
        recovery.Supervisor.__init__(self, self.profile_root.parent)
        self.root = self.profile_root / "queue"
        self.profile_ref = entry(self.profile_root / "registration/record.json")
        self.workflow = {**self.workflow, "allowed_gpu_indices": GPUS, "max_gpu_workers": len(GPUS)}
        self.max_gpu_workers = len(GPUS)
        self.resume = resume
        self.history_root = self.root / "jobs"
        self.continued_parent = read_ref(self.profile["parent_controller"])
        require(
            resume or not self.history_root.exists(), "existing attempts require explicit resume"
        )

    def update(self, phase, **details):
        if phase == "V20_FIVE_GPU_QUEUE_RUNNING":
            phase = "V21_SIX_GPU_QUEUE_RUNNING"
        return super().update(phase, **details)

    def guard_old_dispatch(self):
        recovery.Supervisor.guard_old_dispatch(self)
        parent = read_ref(self.profile["parent_execution_profile"])
        replay_profile.guard_dispatcher(parent)
        replay_profile.guard_dispatcher(read_ref(parent["parent_execution_profile"]))
        guard_parent(self.profile)

    def arm_jobs(self, launcher):
        jobs = recovery.Supervisor.arm_jobs(self, launcher)
        for job in jobs:
            if job["key"] == CONTINUED_KEY:
                job["script"] = (
                    Path(self.continued_parent["script_worktree"])
                    / "trusted_data_synthesis/scripts/finqa_v20_five_gpu_queue.py"
                )
                job["args"] += ["--profile-root", PARENT]
                job["execution_kind"] = "continued_live_V20_Full29_not_restarted"
            elif job["key"] in NEW_PROFILE_KEYS:
                job["script"] = Path(__file__)
                job["args"] += ["--profile-root", self.profile_root]
                job["requires_validation"] = True
                job["execution_kind"] = "unchanged_replay_with_GPU0_resource_extension"
        return jobs

    def validation_job(self):
        # A completed evidence reference, never a new GPU job or copied result.
        return dict(
            key="inherited-V20-CUDA-acceptance",
            module="validation_gate",
            args=[],
            result=PARENT / "validation/result/record.json",
        )

    def worker_profile(self, key):
        return (
            self.profile["parent_execution_profile"] if key == CONTINUED_KEY else self.profile_ref
        )

    def job_complete(self, job):
        if job["module"] == "validation_gate":
            inherited_validation(self.profile_root, self.profile)
            return True
        if not marker_complete(job["result"]):
            return False
        if job["key"] in replay_profile.OPTIMIZED_KEYS:
            result = checked(job["result"])
            require(
                result.get("execution_profile") == self.worker_profile(job["key"])
                and result.get("execution_producer") == "v19_profiled_worker.v1"
                and result.get("validation_id") == self.profile["inherited_CUDA_validation_id"],
                "each optimized arm must keep its own exact execution profile and acceptance",
            )
        return True

    def eligible_job(self, job):
        if job["key"] == CONTINUED_KEY or job["module"] == "validation_gate":
            return False
        if job.get("requires_validation"):
            inherited_validation(self.profile_root, self.profile)
        return True

    def recover_active(self, jobs):
        job = next((j for j in jobs if j["key"] == CONTINUED_KEY), None)
        if job is not None and CONTINUED_KEY not in self.children:
            child = self.profile["continued_worker"]
            if not (self.job_complete(job) and identity(child["pid"]) != child["birth"]):
                attempt = self.history_root / CONTINUED_KEY / "adopt001"
                path = attempt / "adoption/record.json"
                if path.exists():
                    old = checked(path)
                    require(
                        self.resume
                        and old["original_launch"] == child["original_launch"]
                        and old["worker_execution_profile"] == child["worker_execution_profile"],
                        "continued worker cold restore must retain the original runtime",
                    )
                else:
                    publish(
                        attempt / "adoption",
                        bound(
                            dict(
                                schema="v21_existing_profiled_worker_observation.v1",
                                at=now(),
                                queue_policy_id=self.profile["id"],
                                pid=child["pid"],
                                birth=child["birth"],
                                gpu=child["gpu"],
                                original_launch=child["original_launch"],
                                worker_execution_profile=child["worker_execution_profile"],
                                original_parent=self.profile["parent_controller"],
                                no_signal_sent=True,
                                no_checkpoint_or_feedback_modified=True,
                            )
                        ),
                    )
                require(
                    not (attempt / "exit/record.json").exists() or self.job_complete(job),
                    "a previously failed live worker requires inspection, not restart",
                )
                self.children[CONTINUED_KEY] = dict(
                    process=recovery.AdoptedProcess(child, self.continued_parent),
                    pid=child["pid"],
                    birth=child["birth"],
                    gpu=child["gpu"],
                    attempt=str(attempt),
                    job=job,
                    protected=True,
                    detached=False,
                )
        super().recover_active([j for j in jobs if j["key"] != CONTINUED_KEY])

    def launch(self, job, *, gpu=None):
        require(job["key"] != CONTINUED_KEY, "never relaunch the live V20 Full29")

        def launch_bound(value):
            return bound(
                dict(
                    value,
                    schema="v21_six_gpu_worker_launch.v1",
                    queue_policy_id=self.profile["id"],
                    worker_execution_profile=self.worker_profile(job["key"])
                    if job["key"] in replay_profile.OPTIMIZED_KEYS
                    else None,
                )
            )

        execute = bind_dependencies(
            previous.Supervisor.launch, GPUS=GPUS, require=six_gpu_require, bound=launch_bound
        )
        return execute(self, job, gpu=gpu)

    def gpu_queue(self, jobs, allowed):
        execute = bind_dependencies(
            previous.Supervisor.gpu_queue, GPUS=GPUS, require=six_gpu_require
        )
        return execute(self, jobs, allowed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run", "resume", "run-arm", "resume-arm"))
    parser.add_argument("--root", "--profile-root", dest="root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int, choices=(47,))
    parser.add_argument("--arm", choices=("Full",))
    parser.add_argument("--gpu-index", type=int, choices=GPUS)
    args = parser.parse_args()
    if args.action == "register":
        result = register(args.root)
    elif args.action in ("run-arm", "resume-arm"):
        require(
            all(v is not None for v in (args.output, args.seed, args.arm, args.gpu_index)),
            "Full47 requires its original output, seed, arm and explicit GPU",
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
                supervisor.stop = True

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
