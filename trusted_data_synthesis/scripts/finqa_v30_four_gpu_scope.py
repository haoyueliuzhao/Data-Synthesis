"""Narrow the existing V29 queue to physical GPUs 3, 4, 5 and 7.

The scientific protocol, existing attempts and live workers are unchanged.
Only the resource scope is supplemented; the frozen V29 modules are not patched.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import re
import signal
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SOURCE_ROOT = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01"
)
QUEUE_ROOT = SOURCE_ROOT / "four_gpu_release_01"
ROOT = QUEUE_ROOT / "gpu_scope_01"
PREDECESSOR_ID = "ca31f1b0117777f3c7c697daa5e101da1cffa6a03893a11f87fc11fa6fd449b5"
FILE = "finqa_v30_four_gpu_scope.py"
ALLOWED_GPUS = (3, 4, 5, 7)
EXCLUDED_GPUS = (0, 1, 2, 6)
MAX_GPU_WORKERS = 4


def predecessor_module():
    plan = json.loads((QUEUE_ROOT / "protocol/record.json").read_text())
    manifest = json.loads((QUEUE_ROOT / "implementation/record.json").read_text())
    if plan["id"] != PREDECESSOR_ID or plan["implementation_id"] != manifest["id"]:
        raise ValueError("fixed V29 predecessor changed")
    for name, sha in manifest["sha256"].items():
        if hashlib.sha256((QUEUE_ROOT / "implementation" / name).read_bytes()).hexdigest() != sha:
            raise ValueError("frozen V29 implementation changed")
    spec = importlib.util.spec_from_file_location(
        "v30_frozen_v29", QUEUE_ROOT / "implementation/finqa_v29_retained_gpu_controller.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.checked(QUEUE_ROOT / "protocol/record.json")
    module.checked(QUEUE_ROOT / "implementation/record.json")
    return module


v29 = predecessor_module()
require, checked, entry = v29.require, v29.checked, v29.entry
publish, file_entry, now = v29.publish, v29.file_entry, v29.now


def initialize(root, commit):
    """Register only an immutable supplement; never touch the active queue."""
    root = Path(root).resolve()
    require(root == ROOT, "fixed GPU scope root required")
    require(re.fullmatch(r"[0-9a-f]{40}", commit or "") is not None, "full source commit required")
    require(not (root / "implementation").exists(), "GPU scope already initialized")
    science = checked(SOURCE_ROOT / "protocol/record.json")
    raw = subprocess.check_output(
        ["git", "show", f"{commit}:trusted_data_synthesis/scripts/{FILE}"], cwd=REPO
    )
    target = root / "implementation"
    target.mkdir(parents=True)
    with (target / FILE).open("xb") as stream:
        stream.write(raw)
    manifest = publish(
        target / "record.json",
        dict(
            schema="v30_frozen_gpu_scope.v1",
            at=now(),
            source_commit=commit,
            sha256={FILE: hashlib.sha256(raw).hexdigest()},
            predecessor_implementation=entry(QUEUE_ROOT / "implementation/record.json"),
        ),
    )
    return publish(
        root / "protocol/record.json",
        dict(
            schema="v30_four_gpu_scope_supplement.v1",
            at=now(),
            user_authority="2026-10-08：约束任务只在这四张卡上运行；当前四卡为 GPU3、4、5、7",
            implementation_id=manifest["id"],
            predecessor_protocol=entry(QUEUE_ROOT / "protocol/record.json"),
            predecessor_resource_policy=entry(QUEUE_ROOT / "resource_policy/record.json"),
            scientific_protocol=entry(SOURCE_ROOT / "protocol/record.json"),
            queue_root=str(QUEUE_ROOT),
            allowed_gpu_indices=list(ALLOWED_GPUS),
            allowed_gpu_uuids={str(gpu): science["gpu_uuids"][str(gpu)] for gpu in ALLOWED_GPUS},
            excluded_gpu_indices=list(EXCLUDED_GPUS),
            max_gpu_workers=MAX_GPU_WORKERS,
            excluded_gpus_reusable_when_idle=False,
            scope_applies_to_current_and_future_workers_and_all_resume_paths=True,
            cpu_initializing_workers_count_toward_limit=True,
            predecessor_scientific_protocol_and_attempts_unchanged=True,
            workers_adopted_without_signals_or_restarts=True,
            memory_and_checkpoint_recovery_policy_unchanged=True,
            no_feedback_resampling=True,
            no_additional_samples=True,
            API_calls=0,
            api_model="deepseek-flash",
            model_fallback=False,
        ),
    )


def verify_policy(root):
    root = Path(root).resolve()
    require(root == ROOT, "fixed GPU scope root required")
    require(Path(__file__).resolve() == root / "implementation" / FILE, "run frozen V30 code")
    policy = checked(root / "protocol/record.json")
    manifest = checked(root / "implementation/record.json")
    require(
        policy["implementation_id"] == manifest["id"]
        and manifest["sha256"] == {FILE: file_entry(root / "implementation" / FILE)["sha256"]},
        "GPU scope source binding changed",
    )
    for key in ("predecessor_protocol", "predecessor_resource_policy", "scientific_protocol"):
        require(entry(policy[key]["path"]) == policy[key], "GPU scope lineage changed")
    science = checked(policy["scientific_protocol"]["path"])
    require(
        policy["queue_root"] == str(QUEUE_ROOT)
        and policy["allowed_gpu_indices"] == list(ALLOWED_GPUS)
        and policy["allowed_gpu_uuids"]
        == {str(gpu): science["gpu_uuids"][str(gpu)] for gpu in ALLOWED_GPUS}
        and policy["excluded_gpu_indices"] == list(EXCLUDED_GPUS)
        and policy["max_gpu_workers"] == MAX_GPU_WORKERS
        and policy["excluded_gpus_reusable_when_idle"] is False,
        "four-GPU scope changed",
    )
    return policy


def check_ownership(children):
    gpus = [child["gpu"] for child in children.values()]
    require(
        len(gpus) <= MAX_GPU_WORKERS
        and set(gpus) <= set(ALLOWED_GPUS)
        and len(set(gpus)) == len(gpus),
        "four-GPU scope ownership bound or GPU collision",
    )


def verify_handoff(root, legacy):
    value = checked(Path(root) / "handoff/record.json")
    ref = value["predecessor_controller_launch"]
    require(
        ref == entry(QUEUE_ROOT / "launch_01/record.json"),
        "predecessor controller launch changed",
    )
    launch = checked(ref["path"])
    require(
        launch["protocol_id"] == PREDECESSOR_ID
        and launch["pid"] == value["controller_pid"]
        and str(launch["birth"]) == str(value["birth"])
        and value["post_handoff_controller_absent"] is True
        and legacy.process_birth(value["controller_pid"]) != str(value["birth"])
        and value["no_worker_signals"] is True,
        "controller-only handoff not proven",
    )
    snapshot = value["predecessor_status_snapshot"]
    require(
        file_entry(snapshot["path"])["sha256"] == snapshot["sha256"]
        and json.loads(Path(snapshot["path"]).read_text()) == snapshot["value"],
        "handoff snapshot changed",
    )
    status = snapshot["value"]
    require(
        status["protocol_id"] == PREDECESSOR_ID
        and not status["failures"]
        and status["phase"] == "DRAINING_ON_STOP",
        "foreign or failed predecessor status",
    )
    children = {row["job"]["key"]: row for row in status["active_children"]}
    check_ownership(children)
    expected = {str(Path(child["attempt"]) / "launch/record.json") for child in children.values()}
    require(
        {ref["path"] for ref in value["retained_worker_launches"]} == expected,
        "handoff live-worker population changed",
    )
    for ref in value["retained_worker_launches"]:
        require(entry(ref["path"]) == ref, "retained worker launch changed")
        launch = checked(ref["path"])
        child = children[launch["job"]["key"]]
        require(
            all(launch[key] == child[key] for key in ("pid", "birth", "gpu", "job")),
            "handoff worker identity changed",
        )
    return value


class ScopedLegacy:
    """Filter resource visibility and annotate status without mutating frozen modules."""

    def __init__(self, legacy, policy_ref):
        self._legacy, self._policy_ref = legacy, policy_ref

    def __getattr__(self, name):
        return getattr(self._legacy, name)

    def inventory(self):
        return [row for row in self._legacy.inventory() if row["index"] in ALLOWED_GPUS]

    def atomic_status(self, root, value):
        value = dict(value)
        value.update(
            supplemental_resource_policy=self._policy_ref,
            predecessor_registered_allowed_gpu_indices=list(v29.ALLOWED_GPUS),
            predecessor_registered_max_gpu_workers=v29.MAX_GPU_WORKERS,
            allowed_gpu_indices=list(ALLOWED_GPUS),
            max_gpu_workers=MAX_GPU_WORKERS,
            excluded_gpu_indices=list(EXCLUDED_GPUS),
            excluded_gpus_reusable_when_idle=False,
            released_gpu_reuse_requires_idle_high_cache=False,
        )
        return self._legacy.atomic_status(root, value)


class ScopedMixin:
    def __init__(self, root, resume=True):
        self.scope_root = Path(root).resolve()
        self.scope = verify_policy(self.scope_root)
        self.scope_ref = entry(self.scope_root / "protocol/record.json")
        base = type(self)._frozen_base
        _, legacy = base.verify_source()
        verify_handoff(self.scope_root, legacy)
        super().__init__(QUEUE_ROOT, resume=True)
        check_ownership(self.children)
        self.legacy = ScopedLegacy(self.legacy, self.scope_ref)

    def adopt(self, job, origin):
        require(origin["gpu"] in ALLOWED_GPUS, "adoption outside four-GPU scope")
        check_ownership(self.children)
        require(len(self.children) < MAX_GPU_WORKERS, "four-GPU adoption capacity reached")
        return super().adopt(job, origin)

    def launch(self, job, row):
        check_ownership(self.children)
        require(
            row["index"] in ALLOWED_GPUS and len(self.children) < MAX_GPU_WORKERS,
            "launch outside four-GPU scope or capacity reached",
        )
        return super().launch(job, row)

    def dispatch(self):
        check_ownership(self.children)
        if len(self.children) < MAX_GPU_WORKERS:
            return super().dispatch()

    def status(self, phase):
        check_ownership(self.children)
        return super().status(phase)

    def run(self):
        # Same V29 lifecycle and scorers. Only final publication adds the scope;
        # no original module global, protocol or historical receipt is rewritten.
        while len(self.completed) < len(self.jobs):
            try:
                self.reap()
                if not self.failures and not self.stop:
                    self.score_ready_blocks()
                    if (
                        self.legacy.disk_available(SOURCE_ROOT)
                        >= self.science["dispatch_disk_floor_bytes"]
                    ):
                        self.dispatch()
                self.status(
                    "DRAINING_AFTER_FAILURE"
                    if self.failures
                    else "DRAINING_ON_STOP"
                    if self.stop
                    else "REPLICATION_GPU_RUNNING"
                    if self.children
                    else "WAITING_FOR_RESOURCES"
                )
            except Exception as exc:
                self.failures.append(dict(controller_error=type(exc).__name__, message=str(exc)))
                self.stop = True
            if (self.failures or self.stop) and not self.children:
                self.status("BLOCKED_SAVED" if self.failures else "STOPPED_SAVED")
                return
            if len(self.completed) < len(self.jobs):
                time.sleep(v29.POLL_SECONDS)
        if self.failures or self.stop:
            self.status("BLOCKED_SAVED" if self.failures else "STOPPED_SAVED")
            return
        self.status("REPLICATION_CPU_SCORING")
        self.score_ready_blocks()
        combined = SOURCE_ROOT / "descriptive_six_seed_summary"
        if not (combined / "record.json").exists():
            self.legacy.cpu_command(
                SOURCE_ROOT,
                "finqa_v25_evaluation.py",
                [
                    "combine",
                    "--a-root",
                    str(SOURCE_ROOT / "c_only_test_extension"),
                    "--b-root",
                    str(SOURCE_ROOT / "replication_evaluation"),
                    "--output",
                    str(combined),
                ],
            )
        publish(
            self.root / "result/record.json",
            dict(
                schema="v30_completed_original_v25_scoped_v29_queue.v1",
                at=now(),
                protocol_id=self.plan["id"],
                scientific_protocol_id=self.science["id"],
                supplemental_resource_policy=self.scope_ref,
                original_protocol=entry(SOURCE_ROOT / "protocol/record.json"),
                extension_summary=entry(SOURCE_ROOT / "c_only_test_extension/summary/record.json"),
                replication_summary=entry(
                    SOURCE_ROOT / "replication_evaluation/summary/record.json"
                ),
                combined_descriptive_summary=entry(combined / "record.json"),
                jobs_completed=sorted(self.completed),
                registered_budgets=self.science["budgets"],
                predecessor_registered_allowed_gpu_indices=list(v29.ALLOWED_GPUS),
                predecessor_registered_max_gpu_workers=v29.MAX_GPU_WORKERS,
                allowed_gpu_indices=list(ALLOWED_GPUS),
                max_gpu_workers=MAX_GPU_WORKERS,
                excluded_gpu_indices=list(EXCLUDED_GPUS),
                excluded_gpus_reusable_when_idle=False,
                administrative_checkpoint_resume_jobs=sorted(v29.PAUSED_KEYS),
                automatic_checkpoint_recovery_counts=self.checkpoint_recoveries,
                no_feedback_resampling=True,
                no_additional_samples=True,
                API_calls=0,
                no_additional_seeds_or_models=True,
                no_algorithm_tuning_from_test=True,
            ),
        )
        publish(
            self.scope_root / "result/record.json",
            dict(
                schema="v30_completed_resource_scope.v1",
                at=now(),
                protocol_id=self.scope["id"],
                queue_result=entry(self.root / "result/record.json"),
            ),
        )
        self.status("REPLICATION_COMPLETE")


def controller_type(base):
    return type("Controller", (ScopedMixin, v29.controller_type(base)), {"_frozen_base": base})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "resume"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    require(args.root.resolve() == ROOT, "fixed V30 destination required")
    (ROOT / "queue").mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        # Registering the supplement is safe while the old controller is active;
        # actual restoration acquires all inherited queue locks as well.
        roots = (
            (ROOT,)
            if args.action == "initialize"
            else (
                SOURCE_ROOT,
                SOURCE_ROOT / "execution_continuation_01",
                SOURCE_ROOT / "same_run_recovery_01",
                v29.PREDECESSOR,
                QUEUE_ROOT,
                ROOT,
            )
        )
        for root in roots:
            lock = stack.enter_context((root / "queue/controller.lock").open("a"))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == "initialize":
            print(json.dumps(initialize(ROOT, args.source_commit), ensure_ascii=False))
            return
        controller = controller_type(v29.v28.predecessor_module())(ROOT)

        def stop_requested(signum, frame):
            controller.stop = True

        signal.signal(signal.SIGTERM, stop_requested)
        signal.signal(signal.SIGINT, stop_requested)
        try:
            controller.run()
        except Exception as exc:
            controller.failures.append(dict(controller_error=type(exc).__name__, message=str(exc)))
            controller.status(
                "BLOCKED_SAVED_WITH_LIVE_CHILDREN" if controller.children else "BLOCKED_SAVED"
            )
            raise


if __name__ == "__main__":
    main()
