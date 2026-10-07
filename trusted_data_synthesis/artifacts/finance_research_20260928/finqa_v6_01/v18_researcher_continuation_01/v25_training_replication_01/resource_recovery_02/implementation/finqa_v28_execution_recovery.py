"""Bounded same-run V25 recovery; adopt live workers without restarting them.

The only computational restart authorized here is seed251/C-only from its
durable step298 branch checkpoint after a failed uncommitted class gradient.
This is real gradient recomputation, not a zero-compute admission deferral.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import time
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SOURCE_ROOT = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01"
)
ANCESTOR = SOURCE_ROOT / "execution_continuation_01"
PREDECESSOR = SOURCE_ROOT / "same_run_recovery_01"
ROOT = SOURCE_ROOT / "resource_recovery_02"
PREDECESSOR_ID = "cb179148832b7de2496783fc74ec5a4a7de4466251d0b931279502d9796bdba4"
RESUME_KEY = "replication-train-seed251-c_only"
FILES = (
    "finqa_v28_execution_recovery.py",
    "finqa_v28_resume_proof.py",
    "finqa_v28_memory_worker.py",
    "finqa_v28_checkpoint_resume.py",
)
EXECUTION_FLOORS = {"test": 24576, "prefix": 32768, "static": 49152, "automatic": 76800}
MEMORY_POLICY = {
    "idle_mode": "high_cache",
    "idle_minimum_free_mib": 80000,
    "idle_requires_no_compute_processes": True,
    "non_idle_mode": "shared_checkpointed",
    "shared_preserves_original_training_step_checkpoints": True,
    "partial_feedback_never_resampled_for_recovery": True,
    "unproven_computational_failure_stops_dispatch": True,
}
POLL_SECONDS = 10
STABLE_OBSERVATIONS = 2
MAX_AUTOMATIC_CHECKPOINT_RESUMES = 2
CHECKPOINT_RESUME_COOLDOWN_SECONDS = 60


def require(ok, message):
    if not ok:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def checked(path):
    value = json.loads(Path(path).read_text())
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "record identity changed: " + str(path),
    )
    return value


def entry(path):
    path = Path(path).resolve()
    return dict(
        path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), id=checked(path)["id"]
    )


def file_entry(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def publish(path, value):
    require("id" not in value, "cannot overwrite a record identity")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {**value, "id": digest(value)}
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return value


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "missing frozen module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verified_predecessor_module():
    plan = checked(PREDECESSOR / "protocol/record.json")
    manifest = checked(PREDECESSOR / "implementation/record.json")
    require(
        plan["id"] == PREDECESSOR_ID and plan["implementation_id"] == manifest["id"],
        "predecessor execution identity changed",
    )
    for name, sha in manifest["sha256"].items():
        require(
            file_entry(PREDECESSOR / "implementation" / name)["sha256"] == sha,
            "predecessor frozen code changed",
        )
    return load_module(
        PREDECESSOR / "implementation/finqa_v27_same_run_recovery.py",
        "v28_frozen_v27_controller",
    )


# This method is destination/key agnostic. Reuse its exact frozen code without
# mutating the predecessor module or rebinding any of its globals. Its receipt
# schema names remain v27; the enclosing protocol identifies this execution.
_PREDECESSOR_MODULE = verified_predecessor_module()


def predecessor_module():
    return verified_predecessor_module().predecessor_module()


def freeze(root, commit):
    require(
        re.fullmatch(r"[0-9a-f]{40}", commit or "") is not None,
        "full committed source revision required",
    )
    target = Path(root) / "implementation"
    expected = {}
    for name in FILES:
        raw = subprocess.check_output(
            ["git", "show", f"{commit}:trusted_data_synthesis/scripts/{name}"], cwd=REPO
        )
        expected[name] = (raw, hashlib.sha256(raw).hexdigest())
    if (target / "record.json").exists():
        manifest = checked(target / "record.json")
        require(manifest["source_commit"] == commit, "cannot rebind recovery code")
        for name, (_, sha) in expected.items():
            require(
                file_entry(target / name)["sha256"] == sha == manifest["sha256"][name],
                "recovery code changed",
            )
        return manifest
    require(not target.exists(), "partial recovery freeze requires inspection")
    target.mkdir(parents=True)
    for name, (raw, _) in expected.items():
        with (target / name).open("xb") as stream:
            stream.write(raw)
    return publish(
        target / "record.json",
        dict(
            schema="v28_frozen_same_run_recovery.v1",
            at=now(),
            source_commit=commit,
            sha256={name: value[1] for name, value in expected.items()},
        ),
    )


def execution_floor(job):
    if job["kind"] != "arm":
        return EXECUTION_FLOORS[job["kind"]]
    arm = job["args"][job["args"].index("--arm") + 1]
    return EXECUTION_FLOORS["static" if arm == "static" else "automatic"]


def compute_processes():
    """Fail closed if the device-wide compute-process inventory is unavailable."""
    raw = subprocess.check_output(
        ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"],
        text=True,
    )
    occupied = set()
    for line in raw.splitlines():
        if line.strip():
            uuid, pid = [part.strip() for part in line.split(",")]
            require(uuid.startswith("GPU-") and int(pid) > 0, "invalid compute-process inventory")
            occupied.add(uuid)
    return occupied


def memory_mode(row, occupied_uuids):
    return (
        MEMORY_POLICY["idle_mode"]
        if row["free_mib"] >= MEMORY_POLICY["idle_minimum_free_mib"]
        and row["uuid"] not in occupied_uuids
        else MEMORY_POLICY["non_idle_mode"]
    )


def verify_handoff(root, legacy):
    handoff = checked(Path(root) / "handoff/record.json")
    require(
        handoff["predecessor_protocol"] == entry(PREDECESSOR / "protocol/record.json"),
        "handoff belongs to another execution protocol",
    )
    require(
        handoff["stopped_only_controller"] is True
        and handoff["no_worker_signals"] is True
        and handoff["post_handoff_controller_absent"] is True,
        "controller-only handoff required",
    )
    require(
        legacy.process_birth(handoff["controller_pid"]) != str(handoff["birth"]),
        "predecessor controller still exists",
    )
    require(
        entry(handoff["predecessor_controller_launch"]["path"])
        == handoff["predecessor_controller_launch"],
        "controller launch reference changed",
    )
    snapshot = handoff["predecessor_status_snapshot"]
    require(
        file_entry(snapshot["path"])["sha256"] == snapshot["sha256"]
        and json.loads(Path(snapshot["path"]).read_text()) == snapshot["value"],
        "predecessor status changed after handoff",
    )
    require(snapshot["value"]["phase"] == "DRAINING_AFTER_FAILURE", "unrecognized handoff phase")
    for reference in handoff["known_worker_launches"]:
        require(entry(reference["path"]) == reference, "handoff worker launch changed")
    return handoff


def origins_from_predecessor(science, legacy, handoff, resume_proof):
    predecessor = checked(PREDECESSOR / "protocol/record.json")
    known = {ref["path"] for ref in handoff["known_worker_launches"]}
    origins = {}
    for job in science["jobs"]:
        key = job["key"]
        attempts = sorted((PREDECESSOR / "queue/jobs" / key).glob("attempt*"))
        if not attempts:
            original = predecessor["origins"][key]
            if original["state"] == "completed_adopted":
                require(
                    entry(job["result"]) == original["result"], "earlier completed result changed"
                )
                origins[key] = {**original, "state": "completed_adopted"}
            else:
                require(
                    original["state"] == "never_dispatched" and not Path(job["result"]).exists(),
                    "unresolved predecessor job without owned attempt",
                )
                origins[key] = dict(state="never_dispatched", origin_attempt=None)
            continue
        attempt = attempts[-1]
        launch_path, exit_path = attempt / "launch/record.json", attempt / "exit/record.json"
        started = checked(launch_path)
        require(
            started["job"] == job
            and started["protocol_id"] == predecessor["id"]
            and started["scientific_protocol_id"] == science["id"],
            "foreign predecessor launch",
        )
        common = dict(origin_attempt=str(attempt), origin_launch=entry(launch_path))
        if exit_path.exists():
            ended = checked(exit_path)
            require(
                ended["protocol_id"] == predecessor["id"] and ended["key"] == key,
                "foreign predecessor exit",
            )
            common["origin_exit"] = entry(exit_path)
            if ended["completed"]:
                require(
                    ended["result"] == entry(job["result"]), "completed predecessor result changed"
                )
                origins[key] = dict(state="completed_adopted", result=ended["result"], **common)
            else:
                require(
                    key == RESUME_KEY and not Path(job["result"]).exists(),
                    "only the audited C-only gradient OOM is recoverable here",
                )
                origins[key] = dict(
                    state="explicit_same_run_checkpoint_resume", proof=resume_proof, **common
                )
            continue
        require(str(launch_path.resolve()) in known, "unrecorded live worker during handoff")
        if (
            started["birth"] is not None
            and legacy.process_birth(started["pid"]) == started["birth"]
        ):
            origins[key] = dict(
                state="live_predecessor_adopted",
                pid=started["pid"],
                birth=started["birth"],
                gpu=started["gpu"],
                command=started["command"],
                **common,
            )
        elif Path(job["result"]).exists():
            origins[key] = dict(
                state="completed_adopted",
                result=entry(job["result"]),
                detached_completed_during_handoff=True,
                **common,
            )
        else:
            raise ValueError("predecessor worker absent without result: " + key)
    require(
        {k for k, v in origins.items() if v["state"] == "explicit_same_run_checkpoint_resume"}
        == {RESUME_KEY},
        "exactly the one audited same-run checkpoint resume must be registered",
    )
    return origins


def initialize(root, commit):
    root = Path(root).resolve()
    require(
        root == ROOT and not (root / "protocol/record.json").exists(),
        "fixed unused recovery root required",
    )
    base = predecessor_module()
    science, legacy = base.verify_source()
    handoff = verify_handoff(root, legacy)
    manifest = freeze(root, commit)
    proof_module = load_module(root / "implementation" / FILES[1], "v28_resume_proof")
    resume_proof = proof_module.prove_same_run_gradient_oom_resume(SOURCE_ROOT, PREDECESSOR)
    require(
        resume_proof["eligible"] is True and resume_proof["job_key"] == RESUME_KEY,
        "audited checkpoint resume is not eligible",
    )
    origins = origins_from_predecessor(science, legacy, handoff, resume_proof)
    return publish(
        root / "protocol/record.json",
        dict(
            schema="v28_registered_same_run_checkpoint_recovery.v1",
            at=now(),
            user_authority=(
                "尽快使用GPU7；如果得到完全空闲的显卡就设置高显存占用进行独占，"
                "如果并非完全空闲则做好断点保存及恢复续跑"
            ),
            implementation_id=manifest["id"],
            scientific_protocol=entry(SOURCE_ROOT / "protocol/record.json"),
            scientific_implementation=entry(SOURCE_ROOT / "implementation/record.json"),
            predecessor_protocol=entry(PREDECESSOR / "protocol/record.json"),
            predecessor_implementation=entry(PREDECESSOR / "implementation/record.json"),
            predecessor_terminal_status=file_entry(PREDECESSOR / "queue/status.json"),
            handoff=entry(root / "handoff/record.json"),
            origins=origins,
            jobs=science["jobs"],
            budgets=science["budgets"],
            scientific_memory_floors_mib=science["memory_floors_mib"],
            execution_memory_floors_mib=EXECUTION_FLOORS,
            memory_policy=MEMORY_POLICY,
            memory_reservation_wrapper=FILES[2],
            hardware_exclusive_compute_mode=False,
            memory_reservation_is_best_effort_not_hardware_exclusivity=True,
            stable_observations=STABLE_OBSERVATIONS,
            poll_seconds=POLL_SECONDS,
            maximum_explicit_checkpoint_resume_launches={RESUME_KEY: 1},
            maximum_automatic_checkpoint_resumes_per_job=MAX_AUTOMATIC_CHECKPOINT_RESUMES,
            automatic_checkpoint_resume_cooldown_seconds=CHECKPOINT_RESUME_COOLDOWN_SECONDS,
            automatic_checkpoint_resumes_require_idle_high_cache=True,
            explicit_same_run_checkpoint_resume=True,
            uncommitted_gradient_recomputation=True,
            no_feedback_resampling=True,
            no_additional_samples=True,
            no_new_seed_or_hyperparameters=True,
            live_workers_adopted_without_signals_or_restarts=True,
            scientific_budget_not_equal_to_physical_recomputed_gradient_work=True,
            stronger_admission_cannot_prevent_later_external_gpu_allocations=True,
            clean_precompute_deferrals_for_fresh_jobs_only=True,
            API_calls=0,
            api_model="deepseek-flash",
            model_fallback=False,
            failure_policy=(
                "only independently proven checkpoint-safe training OOMs may resume twice "
                "on idle high-cache GPUs; unknown/partial-feedback failure or exhausted "
                "recovery budget stops dispatch and drains owned workers"
            ),
        ),
    )


class RecoveryMixin:
    """V28 lineage, hybrid admission and one-shot resume; reuse adopt/reaping."""

    def __init__(self, root, resume=False):
        self.root = Path(root).resolve()
        require(self.root == ROOT, "fixed same-run recovery root required")
        self.base = type(self)._frozen_base
        self.plan = checked(self.root / "protocol/record.json")
        manifest = checked(self.root / "implementation/record.json")
        require(self.plan["implementation_id"] == manifest["id"], "recovery source binding changed")
        require(
            Path(__file__).resolve() == self.root / "implementation" / FILES[0],
            "run frozen recovery code",
        )
        for name, sha in manifest["sha256"].items():
            require(
                file_entry(self.root / "implementation" / name)["sha256"] == sha,
                "recovery source bytes changed",
            )
        self.science, self.legacy = self.base.verify_source()
        for key in (
            "scientific_protocol",
            "scientific_implementation",
            "predecessor_protocol",
            "predecessor_implementation",
            "handoff",
        ):
            require(entry(self.plan[key]["path"]) == self.plan[key], "recovery reference changed")
        require(
            file_entry(self.plan["predecessor_terminal_status"]["path"])
            == self.plan["predecessor_terminal_status"],
            "predecessor queue was reopened",
        )
        verify_handoff(self.root, self.legacy)
        require(
            self.plan["jobs"] == self.science["jobs"]
            and self.plan["budgets"] == self.science["budgets"]
            and self.plan["scientific_memory_floors_mib"] == self.science["memory_floors_mib"],
            "scientific matrix or budget changed",
        )
        require(
            self.plan["execution_memory_floors_mib"] == EXECUTION_FLOORS
            and self.plan["memory_policy"] == MEMORY_POLICY
            and self.plan["memory_reservation_wrapper"] == FILES[2]
            and self.plan["stable_observations"] == STABLE_OBSERVATIONS
            and self.plan["poll_seconds"] == POLL_SECONDS
            and self.plan["maximum_explicit_checkpoint_resume_launches"] == {RESUME_KEY: 1},
            "registered recovery or resource policy changed",
        )
        require(not (self.root / "result/record.json").exists(), "completed recovery cannot reopen")
        self.proof = load_module(
            ANCESTOR / "implementation/finqa_v26_admission_proof.py",
            "v28_frozen_admission_proof",
        )
        self.resume_proof = load_module(self.root / "implementation" / FILES[1], "v28_resume_proof")
        self.checkpoint_proof = load_module(
            self.root / "implementation" / FILES[3], "v28_checkpoint_resume"
        )
        require(
            self.plan["maximum_automatic_checkpoint_resumes_per_job"]
            == MAX_AUTOMATIC_CHECKPOINT_RESUMES
            and self.plan["automatic_checkpoint_resume_cooldown_seconds"]
            == CHECKPOINT_RESUME_COOLDOWN_SECONDS
            and self.plan["automatic_checkpoint_resumes_require_idle_high_cache"] is True,
            "automatic checkpoint recovery policy changed",
        )
        self.jobs = self.plan["jobs"]
        self.completed, self.children, self.failures = set(), {}, []
        self.stop = False
        self.cooldowns, self.rejections, self.observations = {}, {}, {}
        self.checkpoint_recoveries, self.pending_checkpoint_resumes = {}, {}
        for job in self.jobs:
            self.restore_job(job, resume)
        require(
            len(self.children) <= 8
            and len({c["gpu"] for c in self.children.values()}) == len(self.children),
            "adopted GPU ownership collision",
        )

    def restore_job(self, job, resume):
        origin = self.plan["origins"][job["key"]]
        attempts = sorted((self.root / "queue/jobs" / job["key"]).glob("attempt*"))
        if origin["state"] == "live_predecessor_adopted" and not attempts:
            self.adopt(job, origin)
            return
        if (
            origin["state"] == "live_predecessor_adopted"
            and len(attempts) == 1
            and not (attempts[0] / "launch/record.json").exists()
        ):
            require(resume, "partial adoption requires explicit controller resume")
            self.adopt(job, origin)
            return
        key = job["key"]
        for refkey in ("origin_launch", "origin_exit"):
            if refkey in origin:
                require(entry(origin[refkey]["path"]) == origin[refkey], "original attempt changed")
        if origin["state"] == "completed_adopted":
            require(
                not attempts and entry(job["result"]) == origin["result"],
                "adopted result changed or rerun",
            )
            self.completed.add(key)
            return
        if not attempts:
            require(not Path(job["result"]).exists(), "unowned continuation result")
            return
        require(resume, "existing execution attempts require explicit resume")
        explicit_count = 0
        for number, attempt in enumerate(attempts, 1):
            require(attempt.name == f"attempt{number:03d}", "attempt sequence changed")
            launch, exit_path = attempt / "launch/record.json", attempt / "exit/record.json"
            if not launch.exists():
                self.failures.append(
                    dict(
                        job=key, reason="intent-only or partial launch; cannot infer no computation"
                    )
                )
                return
            started = checked(launch)
            require(
                started["protocol_id"] == self.plan["id"]
                and started["scientific_protocol_id"] == self.science["id"]
                and started["job"] == job,
                "foreign recovery launch",
            )
            explicit_count += int(started.get("explicit_same_run_checkpoint_resume", False))
            require(
                explicit_count <= int(key == RESUME_KEY),
                "explicit checkpoint resume budget exceeded",
            )
            if exit_path.exists():
                ended = checked(exit_path)
                require(
                    ended["protocol_id"] == self.plan["id"]
                    and ended["scientific_protocol_id"] == self.science["id"]
                    and ended["key"] == key,
                    "foreign recovery exit",
                )
                if ended["completed"]:
                    require(
                        attempt == attempts[-1] and ended["result"] == entry(job["result"]),
                        "completed result changed or retried",
                    )
                    self.completed.add(key)
                    continue
                authorization_path = attempt / "checkpoint_resume_authorization/record.json"
                if authorization_path.exists():
                    authorization = self.checked_checkpoint_authorization(job, attempt)
                    self.checkpoint_recoveries[key] = self.checkpoint_recoveries.get(key, 0) + 1
                    require(
                        authorization["resume_number"]
                        == self.checkpoint_recoveries[key]
                        <= MAX_AUTOMATIC_CHECKPOINT_RESUMES,
                        "automatic checkpoint resume sequence changed",
                    )
                    if attempt == attempts[-1]:
                        self.verify_checkpoint_proof(job, attempt, authorization)
                        self.pending_checkpoint_resumes[key] = entry(authorization_path)
                        self.cooldowns[key] = time.monotonic() + CHECKPOINT_RESUME_COOLDOWN_SECONDS
                    elif (attempts[number] / "launch/record.json").exists():
                        following = checked(attempts[number] / "launch/record.json")
                        require(
                            following.get("automatic_checkpoint_resume") is True
                            and following.get("checkpoint_resume_authorization")
                            == entry(authorization_path),
                            "checkpoint recovery launch lost its authorization",
                        )
                    continue
                deferred = attempt / "defer/record.json"
                if not deferred.exists():
                    require(
                        attempt == attempts[-1], "missing historical recovery or deferral receipt"
                    )
                    self.defer(job, attempt)
                else:
                    record = checked(deferred)
                    require(
                        record["exit"] == entry(exit_path)
                        and record["protocol_id"] == self.plan["id"],
                        "deferral identity changed",
                    )
                    self.rejections[key] = self.rejections.get(key, 0) + 1
                    if attempt == attempts[-1]:
                        self.proof.prove_clean_precompute_rejection(SOURCE_ROOT, job, attempt)
                        self.cooldowns[key] = time.monotonic() + record["cooldown_seconds"]
                continue
            require(attempt == attempts[-1], "unfinished attempt was retried")
            child = dict(
                job=job,
                attempt=attempt,
                pid=started["pid"],
                birth=started["birth"],
                gpu=started["gpu"],
                process=None,
            )
            if (
                started["birth"] is not None
                and self.legacy.process_birth(started["pid"]) == started["birth"]
            ):
                self.children[key] = child
            elif Path(job["result"]).exists():
                self.finish(child, None)
            else:
                self.failures.append(
                    dict(
                        job=key,
                        reason=(
                            "detached process absent without result or exit; "
                            "never infer safe restart"
                        ),
                    )
                )

    adopt = _PREDECESSOR_MODULE.RecoveryMixin.adopt

    def checked_checkpoint_authorization(self, job, attempt):
        value = checked(attempt / "checkpoint_resume_authorization/record.json")
        require(
            value["required_memory_mode"] == "high_cache"
            and value["cooldown_seconds"] == CHECKPOINT_RESUME_COOLDOWN_SECONDS,
            "checkpoint recovery resource or cooldown policy changed",
        )
        require(
            value["protocol_id"] == self.plan["id"]
            and value["scientific_protocol_id"] == self.science["id"]
            and value["job_key"] == job["key"]
            and value["failed_exit"] == entry(attempt / "exit/record.json"),
            "checkpoint authorization binding changed",
        )
        require(
            value["proof"]["eligible"] is True and value["proof"]["job_key"] == job["key"],
            "checkpoint proof for another job",
        )
        return value

    def verify_checkpoint_proof(self, job, attempt, authorization):
        current = self.checkpoint_proof.prove_checkpoint_oom_resume(
            SOURCE_ROOT, self.root, job["key"], attempt
        )
        require(
            current == authorization["proof"] and current["eligible"] is True,
            "checkpoint recovery proof changed",
        )

    def authorize_checkpoint_resume(self, job, attempt):
        key = job["key"]
        count = self.checkpoint_recoveries.get(key, 0)
        require(
            count < MAX_AUTOMATIC_CHECKPOINT_RESUMES,
            "automatic checkpoint recovery budget exhausted",
        )
        proof = self.checkpoint_proof.prove_checkpoint_oom_resume(
            SOURCE_ROOT, self.root, key, attempt
        )
        require(
            proof["eligible"] is True and proof["job_key"] == key,
            "training OOM is not checkpoint-safe",
        )
        authorization_path = attempt / "checkpoint_resume_authorization/record.json"
        publish(
            authorization_path,
            dict(
                schema="v28_bounded_checkpoint_resume_authorization.v1",
                at=now(),
                protocol_id=self.plan["id"],
                scientific_protocol_id=self.science["id"],
                job_key=key,
                failed_exit=entry(attempt / "exit/record.json"),
                resume_number=count + 1,
                proof=proof,
                required_memory_mode="high_cache",
                no_feedback_resampling=True,
                cooldown_seconds=CHECKPOINT_RESUME_COOLDOWN_SECONDS,
            ),
        )
        self.checkpoint_recoveries[key] = count + 1
        self.pending_checkpoint_resumes[key] = entry(authorization_path)
        self.cooldowns[key] = time.monotonic() + CHECKPOINT_RESUME_COOLDOWN_SECONDS
        return True

    def defer(self, job, attempt):
        if job["kind"] == "arm":
            try:
                return self.authorize_checkpoint_resume(job, attempt)
            except Exception as exc:
                checkpoint_failure = f"{type(exc).__name__}: {exc}"
            if self.checkpoint_recoveries.get(job["key"], 0) >= MAX_AUTOMATIC_CHECKPOINT_RESUMES:
                self.failures.append(
                    dict(job=job["key"], attempt=str(attempt), reason=checkpoint_failure)
                )
                return False
        if (
            job["key"] == RESUME_KEY
            or self.plan["origins"][job["key"]]["state"] == "live_predecessor_adopted"
        ):
            self.failures.append(
                dict(
                    job=job["key"],
                    attempt=str(attempt),
                    reason=(
                        "adopted or explicitly resumed scientific process failed; "
                        "no further automatic recovery"
                    ),
                )
            )
            return False
        return self.base.Controller.defer(self, job, attempt)

    def launch(self, job, row):
        key = job["key"]
        require(not self.stop and not self.failures, "dispatch halted")
        require(
            job in self.jobs and key not in self.completed | set(self.children),
            "unknown or repeated job",
        )
        require(set(job["dependencies"]) <= self.completed, "unfinished dependency")
        require(self.cooldowns.get(key, 0) <= time.monotonic(), "precompute cooldown not elapsed")
        require(
            row["index"] in range(8)
            and len(self.children) < 8
            and row["index"] not in {c["gpu"] for c in self.children.values()},
            "eight-GPU ownership bound",
        )
        directory = self.root / "queue/jobs" / key
        previous = sorted(directory.glob("attempt*"))
        automatic_reference = self.pending_checkpoint_resumes.get(key)
        automatic_resume = automatic_reference is not None
        explicit_resume = key == RESUME_KEY and not automatic_resume
        is_resume = explicit_resume or automatic_resume
        authorization = None
        if automatic_resume:
            require(
                previous
                and automatic_reference
                == entry(previous[-1] / "checkpoint_resume_authorization/record.json"),
                "automatic recovery does not follow latest failed attempt",
            )
            checkpoint_authorization = self.checked_checkpoint_authorization(job, previous[-1])
            require(
                checkpoint_authorization["resume_number"]
                == self.checkpoint_recoveries[key]
                <= MAX_AUTOMATIC_CHECKPOINT_RESUMES,
                "automatic checkpoint recovery budget changed",
            )
            self.verify_checkpoint_proof(job, previous[-1], checkpoint_authorization)
        elif explicit_resume:
            require(not previous, "the single explicit checkpoint resume has already been launched")
            require(
                self.plan["origins"][key]["state"] == "explicit_same_run_checkpoint_resume",
                "resume not authorized",
            )
            authorization = self.resume_proof.prove_same_run_gradient_oom_resume(
                SOURCE_ROOT, PREDECESSOR
            )
            require(
                authorization == self.plan["origins"][key]["proof"]
                and authorization["eligible"] is True
                and authorization["job_key"] == key,
                "same-run checkpoint proof changed since registration",
            )
        else:
            require(
                self.plan["origins"][key]["state"] == "never_dispatched",
                "only fresh jobs may start new workers",
            )
            if previous:
                prior = checked(previous[-1] / "defer/record.json")
                require(
                    prior["protocol_id"] == self.plan["id"],
                    "previous execution is not a proven deferral",
                )
                self.proof.prove_clean_precompute_rejection(SOURCE_ROOT, job, previous[-1])
        # Observe after CPU checkpoint proof, immediately before the process intent.
        current = next(r for r in self.legacy.inventory() if r["index"] == row["index"])
        require(
            current["uuid"] == self.science["gpu_uuids"][str(row["index"])]
            and current["cpu_affinity"] == self.science["cpu_affinity"][str(row["index"])],
            "GPU mapping changed",
        )
        if (
            current["free_mib"] < execution_floor(job)
            or self.legacy.disk_available(SOURCE_ROOT) < self.science["dispatch_disk_floor_bytes"]
        ):
            self.observations.pop((row["index"], execution_floor(job)), None)
            return False
        occupied_uuids = compute_processes()
        selected_memory_mode = memory_mode(current, occupied_uuids)
        if automatic_resume and selected_memory_mode != "high_cache":
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
            str(self.root / "implementation" / FILES[2]),
            "--worker",
            str(SOURCE_ROOT / "implementation" / job["script"]),
            "--receipt-dir",
            str(attempt / "memory_reservation"),
            "--memory-mode",
            selected_memory_mode,
            "--",
            *job["args"],
            "--root",
            str(SOURCE_ROOT / job["branch"]),
            "--gpu-index",
            str(current["index"]),
        ]
        if is_resume:
            command.append("--resume")
        common = dict(
            protocol_id=self.plan["id"],
            scientific_protocol_id=self.science["id"],
            job=job,
            gpu=current["index"],
            command=command,
            origin_attempt=self.plan["origins"][key]["origin_attempt"],
            previous_execution_attempt=str(previous[-1]) if previous else None,
            explicit_same_run_checkpoint_resume=explicit_resume,
            automatic_checkpoint_resume=automatic_resume,
            checkpoint_resume_authorization=automatic_reference,
            uncommitted_gradient_recomputation=is_resume,
            no_feedback_resampling=True,
            no_additional_samples=True,
            execution_minimum_free_mib=execution_floor(job),
            no_compute_processes_at_admission=current["uuid"] not in occupied_uuids,
            memory_mode=selected_memory_mode,
            memory_reservation_wrapper=FILES[2],
        )
        publish(
            attempt / "intent/record.json",
            dict(
                schema="v28_worker_intent.v1",
                at=now(),
                **common,
                same_run_resume_authorization=authorization,
            ),
        )
        with (attempt / "worker.log").open("xb") as log:
            proc = subprocess.Popen(
                command,
                cwd=self.legacy.FROZEN,
                env=self.legacy.command_environment(),
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        child = dict(
            job=job, attempt=attempt, pid=proc.pid, birth=None, gpu=current["index"], process=proc
        )
        self.children[key] = child
        child["birth"] = self.legacy.process_birth(proc.pid)
        publish(
            attempt / "launch/record.json",
            dict(
                schema="v28_worker_launch.v1",
                at=now(),
                **common,
                gpu_uuid=current["uuid"],
                pid=proc.pid,
                birth=child["birth"],
            ),
        )
        self.pending_checkpoint_resumes.pop(key, None)
        return True

    def finish(self, child, rc):
        job, attempt = child["job"], child["attempt"]
        complete = Path(job["result"]).exists() and (rc == 0 or child["process"] is None)
        result = entry(job["result"]) if complete else None
        launch = checked(attempt / "launch/record.json")
        publish(
            attempt / "exit/record.json",
            dict(
                schema="v28_worker_exit.v1",
                at=now(),
                protocol_id=self.plan["id"],
                scientific_protocol_id=self.science["id"],
                key=job["key"],
                exit_code=rc,
                completed=complete,
                result=result,
                exit_code_source="Popen_wait_status"
                if child["process"] is not None
                else "detached_process_gone",
                explicit_same_run_checkpoint_resume=launch.get(
                    "explicit_same_run_checkpoint_resume", False
                ),
                automatic_checkpoint_resume=launch.get("automatic_checkpoint_resume", False),
                checkpoint_resume_authorization=launch.get("checkpoint_resume_authorization"),
                uncommitted_gradient_recomputation=launch.get(
                    "uncommitted_gradient_recomputation", False
                ),
                no_feedback_resampling=True,
                no_additional_samples=True,
            ),
        )
        if complete:
            self.completed.add(job["key"])
        else:
            self.defer(job, attempt)

    def dispatch(self):
        rows = self.legacy.inventory()
        occupied = {child["gpu"] for child in self.children.values()}
        external = compute_processes()
        idle_floor = MEMORY_POLICY["idle_minimum_free_mib"]
        for row in rows:
            for floor in set(EXECUTION_FLOORS.values()) | {idle_floor}:
                key = (row["index"], floor)
                self.observations[key] = (
                    self.observations.get(key, 0) + 1
                    if row["free_mib"] >= floor
                    and row["index"] not in occupied
                    and (floor != idle_floor or row["uuid"] not in external)
                    else 0
                )
        deferred = {k for k, deadline in self.cooldowns.items() if deadline > time.monotonic()}
        views = [
            {
                **job,
                "minimum_free_mib": idle_floor
                if job["key"] in self.pending_checkpoint_resumes
                else execution_floor(job),
            }
            for job in self.jobs
        ]
        by_key = {job["key"]: job for job in self.jobs}
        pairs = []
        assigned = set(occupied)
        for view in views:
            eligible_rows = [
                row
                for row in rows
                if view["key"] not in self.pending_checkpoint_resumes or row["uuid"] not in external
            ]
            pair = self.base.assignments(
                [view], self.completed, self.children, eligible_rows, assigned, deferred
            )
            if pair:
                pairs.extend(pair)
                assigned.add(pair[0][1]["index"])
        for view, row in pairs:
            if self.stop or self.failures or len(self.children) == 8:
                break
            job = by_key[view["key"]]
            if self.observations[(row["index"], view["minimum_free_mib"])] >= STABLE_OBSERVATIONS:
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
                        k: str(v) if isinstance(v, Path) else v
                        for k, v in child.items()
                        if k != "process"
                    }
                    for child in self.children.values()
                ],
                queued=[
                    j["key"]
                    for j in self.jobs
                    if j["key"] not in self.completed | set(self.children)
                ],
                failures=self.failures,
                clean_precompute_rejections=self.rejections,
                automatic_checkpoint_recovery_counts=self.checkpoint_recoveries,
                pending_checkpoint_resumes=self.pending_checkpoint_resumes,
                cooldown_remaining_seconds={
                    k: max(0, round(v - time.monotonic())) for k, v in self.cooldowns.items()
                },
                allowed_gpu_indices=list(range(8)),
                max_gpu_workers=8,
                API_calls=0,
                explicit_same_run_checkpoint_resume=True,
                uncommitted_gradient_recomputation=True,
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
                phase = (
                    "DRAINING_AFTER_FAILURE"
                    if self.failures
                    else "DRAINING_ON_STOP"
                    if self.stop
                    else "REPLICATION_GPU_RUNNING"
                    if self.children
                    else "WAITING_FOR_RESOURCES"
                )
                self.status(phase)
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
                schema="v28_completed_original_v25_same_run_recovery.v1",
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
                adopted_without_recompute=sorted(
                    k
                    for k, v in self.plan["origins"].items()
                    if v["state"] in ("completed_adopted", "live_predecessor_adopted")
                ),
                explicit_checkpoint_resume_job=RESUME_KEY,
                automatic_checkpoint_recovery_counts=self.checkpoint_recoveries,
                explicit_same_run_checkpoint_resume=True,
                uncommitted_gradient_recomputation=True,
                no_feedback_resampling=True,
                no_additional_samples=True,
                clean_precompute_rejections=self.rejections,
                API_calls=0,
                no_additional_seeds_or_models=True,
                no_algorithm_tuning_from_test=True,
            ),
        )
        self.status("REPLICATION_COMPLETE")


def controller_type(base):
    return type("Controller", (RecoveryMixin, base.Controller), {"_frozen_base": base})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "run", "resume"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    require(args.root.resolve() == ROOT, "fixed recovery destination required")
    (ROOT / "queue").mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        for oldroot in (SOURCE_ROOT, ANCESTOR, PREDECESSOR, ROOT):
            lock = stack.enter_context((oldroot / "queue/controller.lock").open("a"))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == "initialize":
            print(json.dumps(initialize(ROOT, args.source_commit), ensure_ascii=False))
            return
        controller = controller_type(predecessor_module())(ROOT, resume=args.action == "resume")

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
