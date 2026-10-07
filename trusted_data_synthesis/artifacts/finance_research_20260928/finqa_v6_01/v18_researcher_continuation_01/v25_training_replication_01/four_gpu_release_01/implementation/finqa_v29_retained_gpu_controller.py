"""Continue unchanged V25 science with a hard maximum of six owned GPUs.

The four administrative pauses are checkpoint resumes, not failed experiments
or fresh scientific attempts. The frozen V28 worker and bounded OOM proof are
reused without modifying their code or the running retained workers.
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
PREDECESSOR = SOURCE_ROOT / "resource_recovery_02"
ROOT = SOURCE_ROOT / "four_gpu_release_01"
PREDECESSOR_ID = "e9b3dbd1673780ba0d53474ea1271c47ae2b27cfa91c66ef1b9c5de0380baa46"
FILES = ("finqa_v29_retained_gpu_controller.py", "finqa_v29_checkpoint_resume.py")
ALLOWED_GPUS = tuple(range(8))
RETAINED_AT_RELEASE = (3, 4, 5, 7)
RELEASED_GPUS = (0, 1, 2, 6)
MAX_GPU_WORKERS = 6
PAUSED_KEYS = {
    "replication-train-seed251-full": 0,
    "replication-train-seed389-static": 1,
    "replication-train-seed389-c_only": 2,
    "replication-train-seed389-full": 6,
}


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verified_predecessor_module():
    plan = json.loads((PREDECESSOR / "protocol/record.json").read_text())
    manifest = json.loads((PREDECESSOR / "implementation/record.json").read_text())
    if plan["id"] != PREDECESSOR_ID or plan["implementation_id"] != manifest["id"]:
        raise ValueError("fixed V28 lineage changed")
    for name, sha in manifest["sha256"].items():
        if hashlib.sha256((PREDECESSOR / "implementation" / name).read_bytes()).hexdigest() != sha:
            raise ValueError("V28 frozen implementation changed")
    module = load_module(
        PREDECESSOR / "implementation/finqa_v28_execution_recovery.py", "v29_frozen_v28"
    )
    module.checked(PREDECESSOR / "protocol/record.json")
    module.checked(PREDECESSOR / "implementation/record.json")
    return module


v28 = verified_predecessor_module()
require, checked, entry = v28.require, v28.checked, v28.entry
file_entry, publish, now, digest = v28.file_entry, v28.publish, v28.now, v28.digest
EXECUTION_FLOORS, MEMORY_POLICY = v28.EXECUTION_FLOORS, v28.MEMORY_POLICY
POLL_SECONDS, STABLE_OBSERVATIONS = v28.POLL_SECONDS, v28.STABLE_OBSERVATIONS
WRAPPER = PREDECESSOR / "implementation/finqa_v28_memory_worker.py"


def freeze(root, commit):
    require(re.fullmatch(r"[0-9a-f]{40}", commit or "") is not None, "full source commit required")
    target = Path(root) / "implementation"
    sources = {
        name: subprocess.check_output(
            ["git", "show", f"{commit}:trusted_data_synthesis/scripts/{name}"], cwd=REPO
        )
        for name in FILES
    }
    hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()}
    if (target / "record.json").exists():
        manifest = checked(target / "record.json")
        require(
            manifest["source_commit"] == commit
            and manifest["sha256"] == hashes
            and all(file_entry(target / name)["sha256"] == sha for name, sha in hashes.items()),
            "V29 implementation rebind forbidden",
        )
        return manifest
    require(not target.exists(), "partial V29 freeze requires inspection")
    target.mkdir(parents=True)
    for name, raw in sources.items():
        with (target / name).open("xb") as stream:
            stream.write(raw)
    return publish(
        target / "record.json",
        dict(
            schema="v29_frozen_retained_gpu_controller.v1",
            at=now(),
            source_commit=commit,
            sha256=hashes,
            predecessor_implementation=entry(PREDECESSOR / "implementation/record.json"),
        ),
    )


def verify_release(root, legacy):
    value = checked(Path(root) / "resource_release/record.json")
    require(
        value["predecessor_protocol"] == entry(PREDECESSOR / "protocol/record.json"),
        "release belongs to another predecessor",
    )
    require(
        value["retained_gpu_indices"] == list(RETAINED_AT_RELEASE)
        and value["released_gpu_indices"] == list(RELEASED_GPUS),
        "four-GPU release changed",
    )
    require(
        value["post_handoff_controller_absent"] is True
        and legacy.process_birth(value["controller_pid"]) != str(value["birth"]),
        "predecessor controller remains live",
    )
    require(
        entry(value["predecessor_controller_launch"]["path"])
        == value["predecessor_controller_launch"],
        "old controller launch changed",
    )
    snapshot = value["predecessor_status_snapshot"]
    require(
        file_entry(snapshot["path"])["sha256"] == snapshot["sha256"]
        and json.loads(Path(snapshot["path"]).read_text()) == snapshot["value"],
        "predecessor snapshot changed",
    )
    require(
        not snapshot["value"].get("failures")
        and not snapshot["value"].get("pending_checkpoint_resumes"),
        "unresolved predecessor failures or recovery authorizations",
    )
    require(
        {row["job_key"]: row["gpu"] for row in value["paused_jobs"]} == PAUSED_KEYS,
        "administrative pause population changed",
    )
    for row in value["paused_jobs"]:
        require(
            row["process_absent"] is True and legacy.process_birth(row["pid"]) != str(row["birth"]),
            "released worker remains live",
        )
        launch = checked(row["origin_launch"]["path"])
        require(
            entry(row["origin_launch"]["path"]) == row["origin_launch"]
            and launch["job"]["key"] == row["job_key"]
            and all(launch[key] == row[key] for key in ("gpu", "pid", "birth")),
            "paused process launch identity changed",
        )
    for ref in value["retained_worker_launches"]:
        require(entry(ref["path"]) == ref, "retained worker launch changed")
    return value


def verify_resource_policy(root):
    policy = checked(Path(root) / "resource_policy/record.json")
    require(
        policy["release_ref"] == entry(Path(root) / "resource_release/record.json")
        and policy["allowed_gpu_indices"] == list(ALLOWED_GPUS)
        and policy["max_gpu_workers"] == MAX_GPU_WORKERS
        and policy["released_gpus_reusable_only_when_idle"] is True,
        "six-card idle-reuse authority changed",
    )
    require(bool(policy["explicit_followup_authority"]), "missing followup resource authority")
    return policy


def verify_administrative_checkpoint(job, origin):
    """Recheck the CPU-validated receipt bytes and absence of new feedback."""
    proof = origin["proof"]
    require(
        proof["eligible"] is True
        and proof["job_key"] == job["key"]
        and proof["no_feedback_resampling"] is True,
        "administrative resume not proven",
    )
    checkpoint = proof["checkpoint"]
    for key in ("metadata", "state"):
        ref = checkpoint[key]
        require(file_entry(ref["path"])["sha256"] == ref["sha256"], "paused checkpoint changed")
    arm = SOURCE_ROOT / job["branch"] / f"seed{job['args'][2]}/arms/{job['args'][4]}"
    require(
        Path(checkpoint["metadata"]["path"]).resolve().parent.parent == arm / "training",
        "checkpoint belongs to another arm",
    )
    require(not Path(job["result"]).exists(), "paused job already completed")
    checkpoints = sorted((arm / "training").glob("step*/record.json"))
    require(
        checkpoints and checkpoints[-1].resolve() == Path(checkpoint["metadata"]["path"]).resolve(),
        "a newer checkpoint appeared after resource release",
    )
    feedback = arm / "feedback"
    require(
        not feedback.is_symlink() and not feedback.exists(),
        "partial feedback forbids administrative replay",
    )
    inventory = proof["arm_file_inventory"]
    files = {str(path.relative_to(arm)): path for path in arm.rglob("*") if path.is_file()}
    require(set(files) == set(inventory), "paused arm file inventory changed")
    for relative, path in files.items():
        ref = inventory[relative]
        require(
            not path.is_symlink()
            and str(path.resolve()) == ref["path"]
            and path.stat().st_size == ref["bytes"],
            "paused arm file identity changed",
        )
        if path.suffix == ".json":
            require(file_entry(path)["sha256"] == ref["sha256"], "paused arm metadata changed")
    return proof


def origins_from_predecessor(science, legacy, release):
    predecessor = checked(PREDECESSOR / "protocol/record.json")
    paused = {row["job_key"]: row for row in release["paused_jobs"]}
    retained = {ref["path"] for ref in release["retained_worker_launches"]}
    origins = {}
    for job in science["jobs"]:
        key = job["key"]
        attempts = sorted((PREDECESSOR / "queue/jobs" / key).glob("attempt*"))
        old = predecessor["origins"][key]
        if not attempts:
            require(
                old["state"] in {"completed_adopted", "never_dispatched"},
                "unresolved predecessor job without owned attempt",
            )
            if old["state"] == "completed_adopted":
                require(entry(job["result"]) == old["result"], "completed result changed")
                origins[key] = old
            else:
                require(not Path(job["result"]).exists(), "unowned predecessor result")
                origins[key] = dict(state="never_dispatched", origin_attempt=None)
            continue
        attempt = attempts[-1]
        ref = entry(attempt / "launch/record.json")
        launch = checked(ref["path"])
        require(
            launch["job"] == job
            and launch["protocol_id"] == predecessor["id"]
            and launch["scientific_protocol_id"] == science["id"],
            "foreign predecessor launch",
        )
        common = dict(origin_attempt=str(attempt), origin_launch=ref)
        live = legacy.process_birth(launch["pid"]) == launch["birth"]
        if Path(job["result"]).exists() and not live:
            require(key not in paused, "paused job completed unexpectedly")
            origins[key] = dict(state="completed_adopted", result=entry(job["result"]), **common)
        elif key in paused:
            require(paused[key]["origin_launch"] == ref, "paused job latest launch changed")
            origin = dict(
                state="administrative_checkpoint_resume", proof=paused[key]["proof"], **common
            )
            verify_administrative_checkpoint(job, origin)
            origins[key] = origin
        else:
            require(
                ref["path"] in retained and launch["gpu"] in RETAINED_AT_RELEASE and live,
                "predecessor worker absent without owned result",
            )
            origins[key] = dict(
                state="live_predecessor_adopted",
                **common,
                **{k: launch[k] for k in ("pid", "birth", "gpu", "command")},
            )
    require(
        {k for k, row in origins.items() if row["state"] == "administrative_checkpoint_resume"}
        == set(PAUSED_KEYS),
        "fixed administrative resume set changed",
    )
    return origins


def initialize(root, commit):
    root = Path(root).resolve()
    require(
        root == ROOT and not (root / "protocol/record.json").exists(),
        "unused fixed V29 root required",
    )
    science, legacy = v28.predecessor_module().verify_source()
    release = verify_release(root, legacy)
    verify_resource_policy(root)
    origins = origins_from_predecessor(science, legacy, release)
    manifest = freeze(root, commit)
    return publish(
        root / "protocol/record.json",
        dict(
            schema="v29_registered_four_gpu_release_continuation.v1",
            at=now(),
            user_authority="查看当前进度，尽快让渡四张显卡；后续调整策略，最多同时占用六张卡；只要仍空闲即可重新使用，但总占卡不超过6张",
            implementation_id=manifest["id"],
            scientific_protocol=entry(SOURCE_ROOT / "protocol/record.json"),
            scientific_implementation=entry(SOURCE_ROOT / "implementation/record.json"),
            predecessor_protocol=entry(PREDECESSOR / "protocol/record.json"),
            predecessor_implementation=entry(PREDECESSOR / "implementation/record.json"),
            predecessor_terminal_status=file_entry(PREDECESSOR / "queue/status.json"),
            resource_release=entry(root / "resource_release/record.json"),
            resource_policy=entry(root / "resource_policy/record.json"),
            origins=origins,
            jobs=science["jobs"],
            budgets=science["budgets"],
            scientific_memory_floors_mib=science["memory_floors_mib"],
            execution_memory_floors_mib=EXECUTION_FLOORS,
            memory_policy=MEMORY_POLICY,
            memory_reservation_wrapper=file_entry(WRAPPER),
            allowed_gpu_indices=list(ALLOWED_GPUS),
            released_gpu_indices=list(RELEASED_GPUS),
            max_gpu_workers=MAX_GPU_WORKERS,
            retained_gpu_indices_at_release=list(RETAINED_AT_RELEASE),
            released_gpu_reuse_requires_idle_high_cache=True,
            maximum_administrative_checkpoint_resume_launches={key: 1 for key in PAUSED_KEYS},
            inherited_checkpoint_recovery_counts=release["predecessor_status_snapshot"][
                "value"
            ].get("automatic_checkpoint_recovery_counts", {}),
            maximum_automatic_checkpoint_resumes_per_job=v28.MAX_AUTOMATIC_CHECKPOINT_RESUMES,
            automatic_checkpoint_resume_cooldown_seconds=v28.CHECKPOINT_RESUME_COOLDOWN_SECONDS,
            automatic_checkpoint_resumes_require_idle_high_cache=True,
            no_feedback_resampling=True,
            no_additional_samples=True,
            no_new_seed_or_hyperparameters=True,
            retained_workers_adopted_without_signals_or_restarts=True,
            administrative_pauses_do_not_consume_OOM_retry_budget=True,
            stable_observations=STABLE_OBSERVATIONS,
            poll_seconds=POLL_SECONDS,
            API_calls=0,
            api_model="deepseek-flash",
            model_fallback=False,
        ),
    )


class RetainedMixin(v28.RecoveryMixin):
    def __init__(self, root, resume=False):
        self.root = Path(root).resolve()
        require(self.root == ROOT, "fixed retained-GPU root required")
        require(
            Path(__file__).resolve() == self.root / "implementation" / FILES[0],
            "run frozen V29 code",
        )
        self.base = type(self)._frozen_base
        self.science, self.legacy = self.base.verify_source()
        self.plan = checked(self.root / "protocol/record.json")
        manifest = checked(self.root / "implementation/record.json")
        require(
            self.plan["implementation_id"] == manifest["id"]
            and manifest["sha256"]
            == {name: file_entry(self.root / "implementation" / name)["sha256"] for name in FILES},
            "V29 source binding changed",
        )
        for key in (
            "scientific_protocol",
            "scientific_implementation",
            "predecessor_protocol",
            "predecessor_implementation",
            "resource_release",
            "resource_policy",
        ):
            require(
                entry(self.plan[key]["path"]) == self.plan[key], "V29 lineage reference changed"
            )
        require(
            file_entry(self.plan["predecessor_terminal_status"]["path"])
            == self.plan["predecessor_terminal_status"],
            "predecessor queue reopened",
        )
        release = verify_release(self.root, self.legacy)
        verify_resource_policy(self.root)
        require(
            self.plan["jobs"] == self.science["jobs"]
            and self.plan["budgets"] == self.science["budgets"]
            and self.plan["scientific_memory_floors_mib"] == self.science["memory_floors_mib"],
            "scientific matrix changed",
        )
        require(
            self.plan["allowed_gpu_indices"] == list(ALLOWED_GPUS)
            and self.plan["released_gpu_indices"] == list(RELEASED_GPUS)
            and self.plan["max_gpu_workers"] == MAX_GPU_WORKERS
            and self.plan["retained_gpu_indices_at_release"] == list(RETAINED_AT_RELEASE)
            and self.plan["released_gpu_reuse_requires_idle_high_cache"] is True,
            "six-GPU cap or idle-only reuse restriction changed",
        )
        require(
            self.plan["execution_memory_floors_mib"] == EXECUTION_FLOORS
            and self.plan["memory_policy"] == MEMORY_POLICY
            and self.plan["memory_reservation_wrapper"] == file_entry(WRAPPER)
            and self.plan["maximum_administrative_checkpoint_resume_launches"]
            == {key: 1 for key in PAUSED_KEYS}
            and self.plan["maximum_automatic_checkpoint_resumes_per_job"]
            == v28.MAX_AUTOMATIC_CHECKPOINT_RESUMES
            and self.plan["automatic_checkpoint_resume_cooldown_seconds"]
            == v28.CHECKPOINT_RESUME_COOLDOWN_SECONDS
            and self.plan["automatic_checkpoint_resumes_require_idle_high_cache"] is True,
            "resource or retry policy changed",
        )
        require(not (self.root / "result/record.json").exists(), "completed run cannot reopen")
        self.proof = load_module(
            SOURCE_ROOT / "execution_continuation_01/implementation/finqa_v26_admission_proof.py",
            "v29_admission_proof",
        )
        self.checkpoint_proof = load_module(
            self.root / "implementation" / FILES[1], "v29_checkpoint_proof"
        )
        self.jobs = self.plan["jobs"]
        self.completed, self.children, self.failures = set(), {}, []
        self.stop = False
        self.cooldowns, self.rejections, self.observations = {}, {}, {}
        self.checkpoint_recoveries = dict(self.plan["inherited_checkpoint_recovery_counts"])
        require(
            self.checkpoint_recoveries
            == release["predecessor_status_snapshot"]["value"].get(
                "automatic_checkpoint_recovery_counts", {}
            )
            and all(
                type(count) is int and 0 <= count <= v28.MAX_AUTOMATIC_CHECKPOINT_RESUMES
                for count in self.checkpoint_recoveries.values()
            ),
            "inherited checkpoint retry budget changed",
        )
        self.pending_checkpoint_resumes = {}
        for job in self.jobs:
            self.restore_job(job, resume)
        require(
            len(self.children) <= MAX_GPU_WORKERS
            and {c["gpu"] for c in self.children.values()} <= set(ALLOWED_GPUS)
            and len({c["gpu"] for c in self.children.values()}) == len(self.children),
            "six-GPU ownership bound or GPU collision",
        )

    def restore_job(self, job, resume):
        origin = self.plan["origins"][job["key"]]
        launches = sorted(
            (self.root / "queue/jobs" / job["key"]).glob("attempt*/launch/record.json")
        )
        administrative = 0
        for index, path in enumerate(launches):
            record = checked(path)
            require(record["gpu"] in ALLOWED_GPUS, "historical launch used an unknown GPU")
            if record["gpu"] in RELEASED_GPUS:
                require(
                    record.get("memory_mode") == "high_cache"
                    and record.get("no_compute_processes_at_admission") is True,
                    "released GPU was reused without idle admission",
                )
            if record.get("administrative_checkpoint_resume"):
                administrative += 1
                require(
                    index == 0
                    and administrative == 1
                    and origin["state"] == "administrative_checkpoint_resume"
                    and record["administrative_resume_authorization"] == origin["proof"]
                    and "--resume" in record["command"],
                    "administrative resume authorization changed",
                )
        result = super().restore_job(job, resume)
        require(len(self.children) <= MAX_GPU_WORKERS, "six-GPU restore worker bound")
        return result

    def adopt(self, job, origin):
        # Keep wrapper mode in the adoption receipt so V28 OOM proof can follow
        # the original launch chain without guessing its memory policy.
        source = checked(origin["origin_launch"]["path"])
        require(
            entry(origin["origin_launch"]["path"]) == origin["origin_launch"]
            and source["job"] == job
            and source["pid"] == origin["pid"]
            and source["birth"] == origin["birth"]
            and source["gpu"] in ALLOWED_GPUS,
            "foreign retained worker",
        )
        attempt = self.root / "queue/jobs" / job["key"] / "attempt001"
        common = dict(
            protocol_id=self.plan["id"],
            scientific_protocol_id=self.science["id"],
            job=job,
            gpu=origin["gpu"],
            command=origin["command"],
            origin_attempt=origin["origin_attempt"],
            origin_launch=origin["origin_launch"],
            adopted_existing_process=True,
            new_process_started=False,
            explicit_same_run_checkpoint_resume=False,
            no_feedback_resampling=True,
            memory_mode=source.get("memory_mode"),
        )
        child = dict(
            job=job,
            attempt=attempt,
            pid=origin["pid"],
            birth=origin["birth"],
            gpu=origin["gpu"],
            process=None,
        )
        self.children[job["key"]] = child
        if (attempt / "intent/record.json").exists():
            intent = checked(attempt / "intent/record.json")
            require(
                all(intent.get(k) == value for k, value in common.items()),
                "partial adoption changed",
            )
        else:
            publish(
                attempt / "intent/record.json",
                dict(schema="v29_worker_adoption_intent.v1", at=now(), **common),
            )
        publish(
            attempt / "launch/record.json",
            dict(
                schema="v29_retained_worker_adoption.v1",
                at=now(),
                **common,
                pid=child["pid"],
                birth=child["birth"],
                gpu_uuid=self.science["gpu_uuids"][str(child["gpu"])],
            ),
        )
        if self.legacy.process_birth(child["pid"]) != child["birth"]:
            self.finish(child, None)
            del self.children[job["key"]]

    def launch(self, job, row):
        key = job["key"]
        require(not self.stop and not self.failures, "dispatch halted")
        require(
            row["index"] in ALLOWED_GPUS
            and len(self.children) < MAX_GPU_WORKERS
            and row["index"] not in {c["gpu"] for c in self.children.values()},
            "six-GPU worker bound or GPU ownership collision",
        )
        require(
            job in self.jobs and key not in self.completed | set(self.children),
            "unknown or repeated job",
        )
        require(set(job["dependencies"]) <= self.completed, "unfinished dependency")
        require(self.cooldowns.get(key, 0) <= time.monotonic(), "cooldown not elapsed")
        origin = self.plan["origins"][key]
        directory = self.root / "queue/jobs" / key
        previous = sorted(directory.glob("attempt*"))
        automatic_reference = self.pending_checkpoint_resumes.get(key)
        automatic_resume = automatic_reference is not None
        admin_resume = (
            origin["state"] == "administrative_checkpoint_resume" and not automatic_resume
        )
        authorization = None
        if automatic_resume:
            require(
                previous
                and automatic_reference
                == entry(previous[-1] / "checkpoint_resume_authorization/record.json"),
                "automatic resume lacks latest authorization",
            )
            authorization = self.checked_checkpoint_authorization(job, previous[-1])
            require(
                authorization["resume_number"]
                == self.checkpoint_recoveries[key]
                <= v28.MAX_AUTOMATIC_CHECKPOINT_RESUMES,
                "checkpoint retry budget changed",
            )
            self.verify_checkpoint_proof(job, previous[-1], authorization)
        elif admin_resume:
            require(not previous, "administrative checkpoint resume already launched")
            authorization = verify_administrative_checkpoint(job, origin)
        else:
            require(
                origin["state"] == "never_dispatched", "only fresh jobs may start fresh workers"
            )
            if previous:
                require(
                    checked(previous[-1] / "defer/record.json")["protocol_id"] == self.plan["id"],
                    "previous attempt lacks proven deferral",
                )
                self.proof.prove_clean_precompute_rejection(SOURCE_ROOT, job, previous[-1])
        current = next(r for r in self.legacy.inventory() if r["index"] == row["index"])
        require(
            current["uuid"] == self.science["gpu_uuids"][str(row["index"])]
            and current["cpu_affinity"] == self.science["cpu_affinity"][str(row["index"])],
            "GPU mapping changed",
        )
        if (
            current["free_mib"] < v28.execution_floor(job)
            or self.legacy.disk_available(SOURCE_ROOT) < self.science["dispatch_disk_floor_bytes"]
        ):
            self.observations.pop((row["index"], v28.execution_floor(job)), None)
            return False
        occupied = v28.compute_processes()
        mode = v28.memory_mode(current, occupied)
        if (automatic_resume or current["index"] in RELEASED_GPUS) and mode != "high_cache":
            self.observations.pop((row["index"], MEMORY_POLICY["idle_minimum_free_mib"]), None)
            return False
        attempt = directory / f"attempt{len(previous) + 1:03d}"
        attempt.mkdir(parents=True)
        command = [
            "/usr/bin/taskset",
            "--cpu-list",
            current["cpu_affinity"],
            str(self.legacy.PYTHON),
            "-u",
            str(WRAPPER),
            "--worker",
            str(SOURCE_ROOT / "implementation" / job["script"]),
            "--receipt-dir",
            str(attempt / "memory_reservation"),
            "--memory-mode",
            mode,
            "--",
            *job["args"],
            "--root",
            str(SOURCE_ROOT / job["branch"]),
            "--gpu-index",
            str(current["index"]),
        ]
        if admin_resume or automatic_resume:
            command.append("--resume")
        common = dict(
            protocol_id=self.plan["id"],
            scientific_protocol_id=self.science["id"],
            job=job,
            gpu=current["index"],
            command=command,
            origin_attempt=origin["origin_attempt"],
            previous_execution_attempt=str(previous[-1]) if previous else None,
            explicit_same_run_checkpoint_resume=False,
            administrative_checkpoint_resume=admin_resume,
            administrative_resume_authorization=authorization if admin_resume else None,
            automatic_checkpoint_resume=automatic_resume,
            checkpoint_resume_authorization=automatic_reference,
            uncommitted_gradient_recomputation=admin_resume or automatic_resume,
            no_feedback_resampling=True,
            no_additional_samples=True,
            execution_minimum_free_mib=v28.execution_floor(job),
            no_compute_processes_at_admission=current["uuid"] not in occupied,
            memory_mode=mode,
            memory_reservation_wrapper=str(WRAPPER),
        )
        publish(
            attempt / "intent/record.json", dict(schema="v29_worker_intent.v1", at=now(), **common)
        )
        with (attempt / "worker.log").open("xb") as log:
            process = subprocess.Popen(
                command,
                cwd=self.legacy.FROZEN,
                env=self.legacy.command_environment(),
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        child = dict(
            job=job,
            attempt=attempt,
            pid=process.pid,
            birth=None,
            gpu=current["index"],
            process=process,
        )
        self.children[key] = child
        child["birth"] = self.legacy.process_birth(process.pid)
        publish(
            attempt / "launch/record.json",
            dict(
                schema="v29_worker_launch.v1",
                at=now(),
                **common,
                gpu_uuid=current["uuid"],
                pid=process.pid,
                birth=child["birth"],
            ),
        )
        self.pending_checkpoint_resumes.pop(key, None)
        return True

    def dispatch(self):
        rows = [row for row in self.legacy.inventory() if row["index"] in ALLOWED_GPUS]
        occupied = {child["gpu"] for child in self.children.values()}
        external = v28.compute_processes()
        idle_floor = MEMORY_POLICY["idle_minimum_free_mib"]
        for row in rows:
            for floor in set(EXECUTION_FLOORS.values()) | {idle_floor}:
                key = (row["index"], floor)
                self.observations[key] = (
                    self.observations.get(key, 0) + 1
                    if (
                        row["free_mib"] >= floor
                        and row["index"] not in occupied
                        and (floor != idle_floor or row["uuid"] not in external)
                        and (
                            row["index"] not in RELEASED_GPUS
                            or v28.memory_mode(row, external) == "high_cache"
                        )
                    )
                    else 0
                )
        deferred = {key for key, deadline in self.cooldowns.items() if deadline > time.monotonic()}
        assigned, pairs = set(occupied), []
        for job in self.jobs:
            view = {
                **job,
                "minimum_free_mib": idle_floor
                if job["key"] in self.pending_checkpoint_resumes
                else v28.execution_floor(job),
            }
            candidates = [
                row
                for row in rows
                if (
                    job["key"] not in self.pending_checkpoint_resumes or row["uuid"] not in external
                )
                and (
                    row["index"] not in RELEASED_GPUS
                    or v28.memory_mode(row, external) == "high_cache"
                )
            ]
            pair = self.base.assignments(
                [view], self.completed, self.children, candidates, assigned, deferred
            )
            if pair:
                pairs.append((job, pair[0][1], view["minimum_free_mib"]))
                assigned.add(pair[0][1]["index"])
        for job, row, floor in pairs:
            if self.stop or self.failures or len(self.children) >= MAX_GPU_WORKERS:
                break
            if self.observations[(row["index"], floor)] >= STABLE_OBSERVATIONS:
                self.launch(job, row)

    def status(self, phase):
        self.legacy.atomic_status(
            self.root,
            dict(
                at=now(),
                phase=phase,
                protocol_id=self.plan["id"],
                scientific_protocol_id=self.science["id"],
                completed=sorted(self.completed),
                total_jobs=len(self.jobs),
                active_children=[
                    {
                        key: str(value) if isinstance(value, Path) else value
                        for key, value in child.items()
                        if key != "process"
                    }
                    for child in self.children.values()
                ],
                queued=[
                    job["key"]
                    for job in self.jobs
                    if job["key"] not in self.completed | set(self.children)
                ],
                failures=self.failures,
                clean_precompute_rejections=self.rejections,
                automatic_checkpoint_recovery_counts=self.checkpoint_recoveries,
                pending_checkpoint_resumes=self.pending_checkpoint_resumes,
                cooldown_remaining_seconds={
                    key: max(0, round(value - time.monotonic()))
                    for key, value in self.cooldowns.items()
                },
                allowed_gpu_indices=list(ALLOWED_GPUS),
                released_gpu_indices=list(RELEASED_GPUS),
                max_gpu_workers=MAX_GPU_WORKERS,
                released_gpu_reuse_requires_idle_high_cache=True,
                administrative_checkpoint_resume_jobs=sorted(PAUSED_KEYS),
                API_calls=0,
                no_feedback_resampling=True,
                no_additional_samples=True,
                execution_memory_floors_mib=EXECUTION_FLOORS,
                memory_policy=MEMORY_POLICY,
                hardware_exclusive_compute_mode=False,
                available_disk_bytes=self.legacy.disk_available(SOURCE_ROOT),
                extension_scored=(
                    SOURCE_ROOT / "c_only_test_extension/summary/record.json"
                ).exists(),
                replication_scored=(
                    SOURCE_ROOT / "replication_evaluation/summary/record.json"
                ).exists(),
            ),
        )

    def run(self):
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
                time.sleep(POLL_SECONDS)
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
                schema="v29_completed_original_v25_four_gpu_continuation.v1",
                at=now(),
                protocol_id=self.plan["id"],
                scientific_protocol_id=self.science["id"],
                original_protocol=entry(SOURCE_ROOT / "protocol/record.json"),
                extension_summary=entry(SOURCE_ROOT / "c_only_test_extension/summary/record.json"),
                replication_summary=entry(
                    SOURCE_ROOT / "replication_evaluation/summary/record.json"
                ),
                combined_descriptive_summary=entry(combined / "record.json"),
                jobs_completed=sorted(self.completed),
                registered_budgets=self.science["budgets"],
                allowed_gpu_indices=list(ALLOWED_GPUS),
                released_gpu_indices=list(RELEASED_GPUS),
                administrative_checkpoint_resume_jobs=sorted(PAUSED_KEYS),
                max_gpu_workers=MAX_GPU_WORKERS,
                released_gpu_reuse_requires_idle_high_cache=True,
                automatic_checkpoint_recovery_counts=self.checkpoint_recoveries,
                no_feedback_resampling=True,
                no_additional_samples=True,
                API_calls=0,
                no_additional_seeds_or_models=True,
                no_algorithm_tuning_from_test=True,
            ),
        )
        self.status("REPLICATION_COMPLETE")


def controller_type(base):
    return type("Controller", (RetainedMixin, base.Controller), {"_frozen_base": base})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "run", "resume"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    require(args.root.resolve() == ROOT, "fixed V29 destination required")
    (ROOT / "queue").mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        for root in (
            SOURCE_ROOT,
            SOURCE_ROOT / "execution_continuation_01",
            SOURCE_ROOT / "same_run_recovery_01",
            PREDECESSOR,
            ROOT,
        ):
            lock = stack.enter_context((root / "queue/controller.lock").open("a"))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == "initialize":
            print(json.dumps(initialize(ROOT, args.source_commit), ensure_ascii=False))
            return
        controller = controller_type(v28.predecessor_module())(ROOT, resume=args.action == "resume")

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
