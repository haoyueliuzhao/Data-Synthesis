"""Execution-only continuation of the frozen V25 experiment.

This controller does not import scientific workers, select models, alter training
or regenerate completed results. Only demonstrably precompute GPU refusals may
be deferred. All actual scientific work still runs the original frozen CLI.
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
ROOT = SOURCE_ROOT / "execution_continuation_01"
SOURCE_PROTOCOL_ID = "bf2f8bfd34469400444d7597a8d9893678adbd6af296c89b0a69c5e9b5ba6d45"
SOURCE_COMMIT = "5ccf58870e1f14f5f8a13fbab0aee4086251d6e8"
FILES = ("finqa_v26_execution_continuation.py", "finqa_v26_admission_proof.py")
OLD_CONTROLLER = "finqa_v25_replication_controller.py"
MEMORY_FLOORS = {"test": 24576, "prefix": 32768, "arm": 49152}
POLL_SECONDS = 10
STABLE_OBSERVATIONS = 2
BASE_DEFER_SECONDS = 60
MAX_DEFER_SECONDS = 480


def require(ok, message):
    if not ok:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def checked(path):
    value = json.loads(Path(path).read_text())
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "record identity changed: " + str(path),
    )
    return value


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


def entry(path):
    path = Path(path).resolve()
    return dict(
        path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), id=checked(path)["id"]
    )


def file_entry(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "missing frozen module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_source():
    plan = checked(SOURCE_ROOT / "protocol/record.json")
    manifest = checked(SOURCE_ROOT / "implementation/record.json")
    require(plan["id"] == SOURCE_PROTOCOL_ID, "original scientific protocol changed")
    require(
        manifest["id"] == plan["implementation_id"] and manifest["source_commit"] == SOURCE_COMMIT,
        "original frozen source binding changed",
    )
    for name, sha in manifest["sha256"].items():
        require(
            file_entry(SOURCE_ROOT / "implementation" / name)["sha256"] == sha,
            "original frozen source bytes changed",
        )
    for key in (
        "training_registration",
        "extension_registration",
        "replication_evaluation_registration",
    ):
        require(entry(plan[key]["path"]) == plan[key], "original registration changed")
    require(
        plan["memory_floors_mib"] == MEMORY_FLOORS
        and plan["API_calls_authorized"] == 0
        and plan["api_model"] == "deepseek-flash",
        "scientific policy changed",
    )
    legacy = load_module(
        SOURCE_ROOT / "implementation" / OLD_CONTROLLER, "v26_frozen_v25_controller"
    )
    require(
        plan["jobs"] == legacy.make_jobs(SOURCE_ROOT) and plan["budgets"] == legacy.budgets(),
        "fixed 24-job matrix or scientific budgets changed",
    )
    return plan, legacy


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
        require(manifest["source_commit"] == commit, "cannot rebind frozen execution code")
        for name, (_, sha) in expected.items():
            require(
                file_entry(target / name)["sha256"] == sha == manifest["sha256"][name],
                "execution source changed",
            )
        return manifest
    require(not target.exists(), "partial freeze requires inspection")
    target.mkdir(parents=True)
    for name, (raw, _) in expected.items():
        with (target / name).open("xb") as stream:
            stream.write(raw)
    return publish(
        target / "record.json",
        dict(
            schema="v26_frozen_execution_only_implementation.v1",
            source_commit=commit,
            sha256={k: v[1] for k, v in expected.items()},
            at=now(),
        ),
    )


def origin_state(plan, legacy, proof):
    """Bind legacy exits; absence of a result never alone authorizes reentry."""
    states = {}
    for job in plan["jobs"]:
        attempt = SOURCE_ROOT / "queue/jobs" / job["key"] / "attempt001"
        if not attempt.exists():
            require(not Path(job["result"]).exists(), "unowned legacy completion")
            states[job["key"]] = dict(state="never_dispatched", origin_attempt=None)
            continue
        started = checked(attempt / "launch/record.json")
        ended = checked(attempt / "exit/record.json")
        require(
            started["protocol_id"] == plan["id"] and started["job"] == job, "foreign legacy launch"
        )
        require(
            ended["protocol_id"] == plan["id"] and ended["key"] == job["key"], "foreign legacy exit"
        )
        require(
            started["birth"] is None or legacy.process_birth(started["pid"]) != started["birth"],
            "legacy worker still alive",
        )
        refs = dict(
            origin_attempt=str(attempt),
            origin_launch=entry(attempt / "launch/record.json"),
            origin_exit=entry(attempt / "exit/record.json"),
        )
        if ended["completed"]:
            require(ended["result"] == entry(job["result"]), "legacy completed result changed")
            result = checked(job["result"])
            if job["kind"] == "test":
                require(
                    result["denominator"] == 1147
                    and len(result["episode_sha256"]) == 1147
                    and result["all_generation_complete"] is True
                    and result["all_provider_calls_settled"] is True,
                    "legacy test seal not complete",
                )
            if job["kind"] == "prefix":
                require(
                    result["actual_new_updates"] == 298
                    and result["migration_optimizer_steps"] == 0
                    and result["complete_prefix"] is True,
                    "legacy prefix not complete",
                )
                for key in ("prefix_checkpoint", "shared_checkpoint"):
                    state_path = Path(result[key]["path"]) / "state.pt"
                    require(
                        file_entry(state_path)["sha256"] == result[key]["state_sha256"],
                        "prefix checkpoint changed",
                    )
            states[job["key"]] = dict(state="completed_adopted", result=ended["result"], **refs)
        else:
            evidence = proof.prove_clean_precompute_rejection(SOURCE_ROOT, job, attempt)
            require(evidence.get("clean") is True, "unclean legacy failure cannot be redispatched")
            states[job["key"]] = dict(state="clean_precompute_rejection", proof=evidence, **refs)
    return states


def initialize(root, commit):
    root = Path(root).resolve()
    require(root == ROOT, "one fixed execution continuation root")
    require(
        not (root / "protocol/record.json").exists(),
        "already registered; use run or explicit resume",
    )
    plan, legacy = verify_source()
    status_path = SOURCE_ROOT / "queue/status.json"
    status = json.loads(status_path.read_text())
    require(
        status["phase"] == "BLOCKED_SAVED" and not status["active_children"],
        "legacy controller not drained",
    )
    require(
        not (SOURCE_ROOT / "result/record.json").exists(), "completed science cannot be reopened"
    )
    manifest = freeze(root, commit)
    proof = load_module(root / "implementation" / FILES[1], "v26_admission_proof")
    origins = origin_state(plan, legacy, proof)
    require(
        {k for k, v in origins.items() if v["state"] == "completed_adopted"}
        == {
            "extension-test-seed11-c_only",
            "extension-test-seed29-c_only",
            "replication-prefix-seed137",
        },
        "exact three completed jobs must be adopted without computation",
    )
    require(
        {k for k, v in origins.items() if v["state"] == "clean_precompute_rejection"}
        == {"extension-test-seed47-c_only", "replication-prefix-seed251"},
        "only the two observed clean refusals may initially be reentered",
    )
    return publish(
        root / "protocol/record.json",
        dict(
            schema="v26_execution_only_continuation.v1",
            at=now(),
            user_authority="继续完成实验",
            implementation_id=manifest["id"],
            scientific_protocol=entry(SOURCE_ROOT / "protocol/record.json"),
            scientific_implementation=entry(SOURCE_ROOT / "implementation/record.json"),
            legacy_terminal_status=file_entry(status_path),
            origins=origins,
            jobs=plan["jobs"],
            budgets=plan["budgets"],
            memory_floors_mib=MEMORY_FLOORS,
            max_gpu_workers=8,
            allowed_gpu_indices=list(range(8)),
            stable_observations=STABLE_OBSERVATIONS,
            poll_seconds=POLL_SECONDS,
            base_defer_seconds=BASE_DEFER_SECONDS,
            max_defer_seconds=MAX_DEFER_SECONDS,
            scheduling=(
                "original fixed dependency-ready order; each job takes smallest qualifying "
                "free GPU; stable observations and immediate recheck"
            ),
            rejection_policy=(
                "only fully proven precompute admission refusal may defer with bounded "
                "exponential cooldown; no scientific retries"
            ),
            failure_policy=(
                "all other failures stop dispatch and drain owned workers; PID birth verified; "
                "never signal other workloads"
            ),
            no_scientific_configuration_change=True,
            no_result_driven_gate=True,
            no_new_seeds=True,
            API_calls=0,
            api_model="deepseek-flash",
            model_fallback=False,
            original_attempts_and_results_immutable=True,
        ),
    )


def assignments(jobs, completed, active, rows, occupied=(), deferred=()):
    """Keep original ready-job order; use best-fit GPU to preserve scarce memory."""
    excluded = set(completed) | set(active) | set(deferred)
    ready = [
        j for j in jobs if j["key"] not in excluded and set(j["dependencies"]) <= set(completed)
    ]
    available = {r["index"]: r for r in rows if r["index"] not in set(occupied)}
    chosen = []
    for job in ready:
        eligible = [r for r in available.values() if r["free_mib"] >= job["minimum_free_mib"]]
        if eligible:
            row = min(eligible, key=lambda r: (r["free_mib"], r["index"]))
            chosen.append((job, row))
            del available[row["index"]]
    return chosen


class Controller:
    def __init__(self, root, resume=False):
        self.root = Path(root).resolve()
        require(self.root == ROOT, "fixed continuation root required")
        self.plan = checked(self.root / "protocol/record.json")
        manifest = checked(self.root / "implementation/record.json")
        require(
            manifest["id"] == self.plan["implementation_id"],
            "execution implementation binding changed",
        )
        require(
            Path(__file__).resolve() == self.root / "implementation" / FILES[0],
            "run the frozen committed execution controller",
        )
        for name, sha in manifest["sha256"].items():
            require(
                file_entry(self.root / "implementation" / name)["sha256"] == sha,
                "frozen execution code changed",
            )
        self.science, self.legacy = verify_source()
        for key in ("scientific_protocol", "scientific_implementation"):
            require(
                entry(self.plan[key]["path"]) == self.plan[key], "scientific source binding changed"
            )
        require(
            file_entry(self.plan["legacy_terminal_status"]["path"])
            == self.plan["legacy_terminal_status"],
            "legacy queue was reopened or changed",
        )
        require(
            self.plan["jobs"] == self.science["jobs"]
            and self.plan["budgets"] == self.science["budgets"]
            and self.plan["memory_floors_mib"] == MEMORY_FLOORS,
            "execution plan changed scientific budget",
        )
        require(
            self.plan["stable_observations"] == STABLE_OBSERVATIONS
            and self.plan["poll_seconds"] == POLL_SECONDS
            and self.plan["base_defer_seconds"] == BASE_DEFER_SECONDS
            and self.plan["max_defer_seconds"] == MAX_DEFER_SECONDS,
            "registered scheduling policy changed",
        )
        require(
            not (self.root / "result/record.json").exists(),
            "completed continuation must not be reopened",
        )
        self.proof = load_module(self.root / "implementation" / FILES[1], "v26_admission_proof")
        self.jobs = self.plan["jobs"]
        self.completed, self.children, self.failures = set(), {}, []
        self.stop = False
        self.cooldowns, self.rejections, self.observations = {}, {}, {}
        for job in self.jobs:
            self.restore_job(job, resume)

    def restore_job(self, job, resume):
        key = job["key"]
        origin = self.plan["origins"][key]
        for refkey in ("origin_launch", "origin_exit"):
            if refkey in origin:
                require(entry(origin[refkey]["path"]) == origin[refkey], "original attempt changed")
        directory = self.root / "queue/jobs" / key
        attempts = sorted(directory.glob("attempt*"))
        if origin["state"] == "completed_adopted":
            require(
                not attempts and entry(job["result"]) == origin["result"],
                "adopted result changed or rerun",
            )
            self.completed.add(key)
            return
        if not attempts:
            require(not Path(job["result"]).exists(), "unowned continuation result")
            if origin["state"] == "clean_precompute_rejection":
                self.proof.prove_clean_precompute_rejection(
                    SOURCE_ROOT, job, Path(origin["origin_attempt"])
                )
            return
        require(resume, "existing execution attempts require explicit resume")
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
                "foreign continuation launch",
            )
            if exit_path.exists():
                ended = checked(exit_path)
                require(
                    ended["protocol_id"] == self.plan["id"]
                    and ended["key"] == key
                    and ended["scientific_protocol_id"] == self.science["id"],
                    "foreign continuation exit",
                )
                if ended["completed"]:
                    require(
                        attempt == attempts[-1] and ended["result"] == entry(job["result"]),
                        "completed result changed or retried",
                    )
                    self.completed.add(key)
                else:
                    deferred = attempt / "defer/record.json"
                    if not deferred.exists():
                        # A crash between exit and proof can safely reconstruct the proof,
                        # but only for the most recent attempt and with explicit resume.
                        require(attempt == attempts[-1], "missing historical deferral receipt")
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
                        reason="detached process absent without result or exit; never restart",
                    )
                )

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
                        for k, v in c.items()
                        if k != "process"
                    }
                    for c in self.children.values()
                ],
                queued=[
                    j["key"]
                    for j in self.jobs
                    if j["key"] not in self.completed | set(self.children)
                ],
                failures=self.failures,
                clean_precompute_rejections=self.rejections,
                cooldown_remaining_seconds={
                    k: max(0, round(v - time.monotonic())) for k, v in self.cooldowns.items()
                },
                allowed_gpu_indices=list(range(8)),
                max_gpu_workers=8,
                API_calls=0,
                no_scientific_retry=True,
                available_disk_bytes=self.legacy.disk_available(SOURCE_ROOT),
                extension_scored=(
                    SOURCE_ROOT / "c_only_test_extension/summary/record.json"
                ).exists(),
                replication_scored=(
                    SOURCE_ROOT / "replication_evaluation/summary/record.json"
                ).exists(),
            ),
        )

    def defer(self, job, attempt):
        key = job["key"]
        try:
            evidence = self.proof.prove_clean_precompute_rejection(SOURCE_ROOT, job, attempt)
            require(evidence.get("clean") is True, "precompute proof not clean")
            count = self.rejections.get(key, 0) + 1
            cooldown = min(MAX_DEFER_SECONDS, BASE_DEFER_SECONDS * 2 ** min(count - 1, 3))
            publish(
                attempt / "defer/record.json",
                dict(
                    schema="v26_proven_precompute_deferral.v1",
                    at=now(),
                    protocol_id=self.plan["id"],
                    scientific_protocol_id=self.science["id"],
                    key=key,
                    exit=entry(attempt / "exit/record.json"),
                    proof=evidence,
                    cooldown_seconds=cooldown,
                    scientific_retry=False,
                ),
            )
            self.rejections[key] = count
            self.cooldowns[key] = time.monotonic() + cooldown
            return True
        except Exception as exc:
            self.failures.append(
                dict(
                    job=key,
                    reason="not a proven precompute admission refusal",
                    error_type=type(exc).__name__,
                    message=str(exc),
                    attempt=str(attempt),
                )
            )
            return False

    def launch(self, job, row):
        require(not self.stop and not self.failures, "dispatch halted")
        require(
            job in self.jobs and job["key"] not in self.completed | set(self.children),
            "unknown or repeated job",
        )
        require(set(job["dependencies"]) <= self.completed, "unfinished dependency")
        require(
            self.cooldowns.get(job["key"], 0) <= time.monotonic(), "precompute cooldown not elapsed"
        )
        require(
            row["index"] in range(8)
            and len(self.children) < 8
            and row["index"] not in {c["gpu"] for c in self.children.values()},
            "eight-GPU ownership bound",
        )
        if self.legacy.disk_available(SOURCE_ROOT) < self.science["dispatch_disk_floor_bytes"]:
            return False
        # The global pre-dispatch snapshot may be stale after another launch.
        current = next(r for r in self.legacy.inventory() if r["index"] == row["index"])
        require(
            current["uuid"] == self.science["gpu_uuids"][str(row["index"])]
            and current["cpu_affinity"] == self.science["cpu_affinity"][str(row["index"])],
            "GPU mapping changed",
        )
        if current["free_mib"] < job["minimum_free_mib"]:
            self.observations.pop((row["index"], job["kind"]), None)
            return False
        directory = self.root / "queue/jobs" / job["key"]
        previous = sorted(directory.glob("attempt*"))
        if previous:
            prior = checked(previous[-1] / "defer/record.json")
            require(
                prior["protocol_id"] == self.plan["id"],
                "only proven deferred attempt may be reentered",
            )
            self.proof.prove_clean_precompute_rejection(SOURCE_ROOT, job, previous[-1])
        else:
            origin = self.plan["origins"][job["key"]]
            if origin["state"] == "clean_precompute_rejection":
                self.proof.prove_clean_precompute_rejection(
                    SOURCE_ROOT, job, Path(origin["origin_attempt"])
                )
            require(
                origin["state"] != "completed_adopted", "completed scientific work cannot rerun"
            )
        attempt = directory / f"attempt{len(previous) + 1:03d}"
        attempt.mkdir(parents=True)
        command = [
            "/usr/bin/taskset",
            "--cpu-list",
            current["cpu_affinity"],
            str(self.legacy.PYTHON),
            "-u",
            str(SOURCE_ROOT / "implementation" / job["script"]),
            *job["args"],
            "--root",
            str(SOURCE_ROOT / job["branch"]),
            "--gpu-index",
            str(current["index"]),
        ]
        common = dict(
            protocol_id=self.plan["id"],
            scientific_protocol_id=self.science["id"],
            job=job,
            gpu=current["index"],
            command=command,
            origin_attempt=self.plan["origins"][job["key"]]["origin_attempt"],
            previous_execution_attempt=str(previous[-1]) if previous else None,
        )
        publish(
            attempt / "intent/record.json", dict(schema="v26_worker_intent.v1", at=now(), **common)
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
        # Retain ownership even if the process or receipt fails immediately.
        child = dict(
            job=job, attempt=attempt, pid=proc.pid, birth=None, gpu=current["index"], process=proc
        )
        self.children[job["key"]] = child
        child["birth"] = self.legacy.process_birth(proc.pid)
        publish(
            attempt / "launch/record.json",
            dict(
                schema="v26_worker_launch.v1",
                at=now(),
                **common,
                gpu_uuid=current["uuid"],
                pid=proc.pid,
                birth=child["birth"],
                no_scientific_retry=True,
            ),
        )
        return True

    def finish(self, child, rc):
        job, attempt = child["job"], child["attempt"]
        complete = Path(job["result"]).exists() and (rc == 0 or child["process"] is None)
        result = entry(job["result"]) if complete else None
        publish(
            attempt / "exit/record.json",
            dict(
                schema="v26_worker_exit.v1",
                at=now(),
                protocol_id=self.plan["id"],
                scientific_protocol_id=self.science["id"],
                key=job["key"],
                exit_code=rc,
                exit_code_source="Popen_wait_status"
                if child["process"] is not None
                else "detached_process_gone",
                completed=complete,
                result=result,
                no_scientific_retry=True,
            ),
        )
        if complete:
            self.completed.add(job["key"])
        else:
            self.defer(job, attempt)

    def reap(self):
        for key, child in list(self.children.items()):
            proc = child["process"]
            rc = proc.poll() if proc is not None else None
            if (proc is not None and rc is None) or (
                proc is None
                and child["birth"] is not None
                and self.legacy.process_birth(child["pid"]) == child["birth"]
            ):
                continue
            try:
                self.finish(child, rc)
            except Exception as exc:
                self.failures.append(dict(job=key, error_type=type(exc).__name__, message=str(exc)))
            del self.children[key]

    def score_ready_blocks(self):
        for branch in ("c_only_test_extension", "replication_evaluation"):
            keys = {j["key"] for j in self.jobs if j["branch"] == branch}
            if (
                keys <= self.completed
                and not (SOURCE_ROOT / branch / "summary/record.json").exists()
            ):
                self.legacy.cpu_command(
                    SOURCE_ROOT,
                    "finqa_v25_evaluation.py",
                    ["score", "--root", str(SOURCE_ROOT / branch)],
                )

    def dispatch(self):
        rows = self.legacy.inventory()
        occupied = {c["gpu"] for c in self.children.values()}
        for row in rows:
            for kind, floor in MEMORY_FLOORS.items():
                key = (row["index"], kind)
                self.observations[key] = (
                    self.observations.get(key, 0) + 1
                    if row["free_mib"] >= floor and row["index"] not in occupied
                    else 0
                )
        deferred = {k for k, deadline in self.cooldowns.items() if deadline > time.monotonic()}
        pairs = assignments(self.jobs, self.completed, self.children, rows, occupied, deferred)
        for job, row in pairs:
            if self.stop or self.failures or len(self.children) == 8:
                break
            if self.observations[(row["index"], job["kind"])] >= STABLE_OBSERVATIONS:
                self.launch(job, row)

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
                schema="v26_completed_original_v25_science.v1",
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
                    k for k, v in self.plan["origins"].items() if v["state"] == "completed_adopted"
                ),
                clean_precompute_rejections=self.rejections,
                API_calls=0,
                no_scientific_retry=True,
                no_additional_seeds_or_models=True,
                no_algorithm_tuning_from_test=True,
            ),
        )
        self.status("REPLICATION_COMPLETE")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "run", "resume"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    require(args.root.resolve() == ROOT, "fixed execution destination required")
    (ROOT / "queue").mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        # Exclude both another continuation and the old controller, without
        # rewriting the old queue, status, attempts or scientific protocol.
        for path in (SOURCE_ROOT / "queue/controller.lock", ROOT / "queue/controller.lock"):
            lock = stack.enter_context(path.open("a"))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == "initialize":
            print(json.dumps(initialize(ROOT, args.source_commit), ensure_ascii=False))
            return
        controller = Controller(ROOT, resume=args.action == "resume")

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
