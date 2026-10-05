"""Finite independent queue for C-only test extension and fresh-seed replication.

Only registered new roots are writable. No old queue resume, implicit retry,
resampling, candidate selection, or signals to another workload.
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
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
V18 = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01"
)
PARENT = V18 / "v23_confirmation_shrink_01"
ROOT = V18 / "v25_training_replication_01"
FROZEN = REPO / ".codex-worktrees/finqa-v18-researcher-continuation-20260930"
PYTHON = REPO / "trusted_data_synthesis/.venv/bin/python"
FILES = (
    "finqa_v25_replication_controller.py",
    "finqa_v25_training_replication.py",
    "finqa_v25_evaluation.py",
    "finqa_v23_test_confirmation.py",
)
PARENT_ID = "5e78a50033afb2d25144a1fdac74c0f6b4cb9676566f79a448c969df26ee0fea"
OLD_SEEDS = (11, 29, 47)
NEW_SEEDS = (137, 251, 389)
ARMS = ("static", "c_only", "full")
GPUS = tuple(range(8))
MEMORY_FLOORS = {"test": 24576, "prefix": 32768, "arm": 49152}
MIN_INITIAL_DISK_BYTES = 400 * 1024**3
MIN_LAUNCH_DISK_BYTES = 32 * 1024**3
CLEANUP = REPO / (
    "trusted_data_synthesis/artifacts/storage_cleanup_20261005_non_epoch_01/result.json"
)


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


def bound(value):
    require("id" not in value, "cannot overwrite a record identity")
    return {**value, "id": digest(value)}


def checked(path):
    value = json.loads(Path(path).read_text())
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "record identity changed: " + str(path),
    )
    return value


def publish(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = bound(value)
    with path.open("x") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return payload


def entry(path):
    path = Path(path).resolve()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "id": checked(path)["id"],
    }


def atomic_status(root, value):
    path = Path(root) / "queue/status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".status-", suffix=".tmp", dir=path.parent)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def inventory():
    raw = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,memory.free,pci.bus_id",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    )
    rows = []
    for line in raw.splitlines():
        index, uuid, memory, pci = [v.strip() for v in line.split(",")]
        domain, bus, slot = pci.lower().split(":")
        device = Path("/sys/bus/pci/devices") / f"{domain[-4:]}:{bus}:{slot}"
        node = int((device / "numa_node").read_text().strip())
        require(node >= 0, "observed NUMA affinity required")
        cpus = Path(f"/sys/devices/system/node/node{node}/cpulist").read_text().strip()
        rows.append(dict(index=int(index), uuid=uuid, free_mib=int(memory), cpu_affinity=cpus))
    require({r["index"] for r in rows} == set(GPUS), "all eight authorized devices must be visible")
    return rows


def load_module(root, name):
    path = Path(root) / "implementation" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    require(spec is not None and spec.loader is not None, "missing frozen module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def freeze(root, commit):
    require(
        re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "full committed source revision required"
    )
    target = Path(root) / "implementation"
    expected = {}
    for name in FILES:
        rel = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", f"{commit}:{rel}"], cwd=REPO)
        expected[name] = (raw, hashlib.sha256(raw).hexdigest())
    if (target / "record.json").exists():
        manifest = checked(target / "record.json")
        require(manifest["source_commit"] == commit, "cannot rebind a frozen continuation")
        for name, (_, sha) in expected.items():
            require(
                hashlib.sha256((target / name).read_bytes()).hexdigest()
                == sha
                == manifest["sha256"][name],
                "frozen implementation changed",
            )
        return manifest
    require(not target.exists(), "partial implementation freeze requires inspection")
    target.mkdir(parents=True)
    for name, (raw, _) in expected.items():
        with (target / name).open("xb") as stream:
            stream.write(raw)
    return publish(
        target / "record.json",
        dict(
            schema="v25_frozen_followup_implementation.v1",
            source_commit=commit,
            sha256={k: v[1] for k, v in expected.items()},
            scientific_runtime=str(FROZEN),
            at=now(),
        ),
    )


def budgets():
    """Physical updates count each fresh prefix once, never reuse an old prefix."""
    return dict(
        old_c_only_test_sessions=3 * 1147,
        fresh_prefix_steps=3 * 298,
        branch_training_steps=3 * 3 * (1490 - 298),
        replication_physical_training_steps=3 * (298 + 3 * (1490 - 298)),
        replication_final_models=9,
        replication_outer_updates=3 * 2 * 4,
        replication_feedback_sessions=3 * 2 * 4 * 700,
        replication_test_sessions=3 * 3 * 1147,
        new_local_sessions=3 * 1147 + 3 * 2 * 4 * 700 + 3 * 3 * 1147,
        maximum_generate_calls=(3 * 1147 + 3 * 2 * 4 * 700 + 3 * 3 * 1147) * 32,
        new_Probe_or_QA_sessions=0,
        external_API_calls=0,
    )


def make_jobs(root):
    root = Path(root)
    jobs = []
    # Interleave the cheap extension and independent prefixes. Scientific A
    # outcomes never gate B. Available memory can admit later eligible jobs.
    for old_seed, new_seed in zip(OLD_SEEDS, NEW_SEEDS, strict=True):
        jobs.extend(
            [
                dict(
                    key=f"extension-test-seed{old_seed}-c_only",
                    script=FILES[2],
                    branch="c_only_test_extension",
                    args=["generate", "--seed", str(old_seed), "--arm", "c_only"],
                    dependencies=[],
                    kind="test",
                    result=str(
                        root
                        / (
                            f"c_only_test_extension/models/seed{old_seed}/c_only/"
                            "whole_test_seal/record.json"
                        )
                    ),
                ),
                dict(
                    key=f"replication-prefix-seed{new_seed}",
                    script=FILES[1],
                    branch="training_replication",
                    args=["prefix", "--seed", str(new_seed)],
                    dependencies=[],
                    kind="prefix",
                    result=str(
                        root / (f"training_replication/seed{new_seed}/prefix_result/record.json")
                    ),
                ),
            ]
        )
    for seed in NEW_SEEDS:
        for arm in ARMS:
            jobs.append(
                dict(
                    key=f"replication-train-seed{seed}-{arm}",
                    script=FILES[1],
                    branch="training_replication",
                    args=["train", "--seed", str(seed), "--arm", arm],
                    dependencies=[f"replication-prefix-seed{seed}"],
                    kind="arm",
                    result=str(
                        root / (f"training_replication/seed{seed}/arms/{arm}/result/record.json")
                    ),
                )
            )
    for seed in NEW_SEEDS:
        for arm in ARMS:
            jobs.append(
                dict(
                    key=f"replication-test-seed{seed}-{arm}",
                    script=FILES[2],
                    branch="replication_evaluation",
                    args=["generate", "--seed", str(seed), "--arm", arm],
                    dependencies=[f"replication-train-seed{seed}-{arm}"],
                    kind="test",
                    result=str(
                        root
                        / (
                            f"replication_evaluation/models/seed{seed}/{arm}/"
                            "whole_test_seal/record.json"
                        )
                    ),
                )
            )
    for job in jobs:
        job["minimum_free_mib"] = MEMORY_FLOORS[job["kind"]]
    require(len(jobs) == len({j["key"] for j in jobs}) == 24, "fixed 24-job budget")
    return jobs


def ready_jobs(jobs, completed, active):
    return [
        j
        for j in jobs
        if j["key"] not in completed | active and set(j["dependencies"]) <= completed
    ]


def admitted_jobs(jobs, completed, active, row):
    return [
        job
        for job in ready_jobs(jobs, completed, active)
        if row["free_mib"] >= job["minimum_free_mib"]
    ]


def disk_available(root):
    info = os.statvfs(root)
    return info.f_bavail * info.f_frsize


def command_environment():
    env = dict(
        os.environ,
        PYTHONPATH=str(FROZEN / "trusted_data_synthesis/src"),
        OMP_NUM_THREADS="4",
        MKL_NUM_THREADS="4",
        TOKENIZERS_PARALLELISM="false",
        PYTHONDONTWRITEBYTECODE="1",
    )
    env.pop("CUDA_VISIBLE_DEVICES", None)
    return env


def cpu_command(root, script, arguments):
    """Registered metadata/scoring operations; never a GPU worker or retry."""
    subprocess.run(
        [str(PYTHON), "-u", str(Path(root) / "implementation" / script), *arguments],
        cwd=FROZEN,
        env=command_environment(),
        check=True,
    )


def cleanup_receipt():
    raw = CLEANUP.read_bytes()
    value = json.loads(raw)
    require(
        value.get("status") == "COMPLETE"
        and value.get("deleted_count") == 17760
        and value.get("protected_after", {}).get("unchanged") is True,
        "user-approved cleanup must complete before the new experiment",
    )
    return dict(path=str(CLEANUP), sha256=hashlib.sha256(raw).hexdigest())


def initialize(root, commit, audit_path):
    root = Path(root).resolve()
    require(root == ROOT, "one fixed successor root; no duplicate experiment blocks")
    require(
        not (root / "protocol/record.json").exists(),
        "already registered; inspect and use run or explicit resume",
    )
    parent = checked(PARENT / "result/record.json")
    require(
        parent["id"] == PARENT_ID and parent["shrink_status"] == "complete",
        "the original confirmation and shrink experiment must remain complete",
    )
    cleanup = cleanup_receipt()
    require(
        disk_available(V18) >= MIN_INITIAL_DISK_BYTES,
        "at least 400 GiB available before the registered full-checkpoint run",
    )
    frozen = freeze(root, commit)
    authority = root / "audit_request/record.json"
    if not authority.exists():
        raw = Path(audit_path).read_bytes()
        publish(
            authority,
            dict(
                schema="v25_user_audit_and_execution_authority.v1",
                at=now(),
                source_path=str(Path(audit_path).resolve()),
                source_sha256=hashlib.sha256(raw).hexdigest(),
                source_text=raw.decode("utf-8"),
                execution_request="参照审计修订并开展后续实验",
                cleanup_and_continuation_request="同意，清理完成后继续本轮实验",
                referenced_unattached_audit_appendices_not_read=True,
                no_new_models_or_parameters_selected_using_extension_results=True,
            ),
        )
    closeout = root / "parent_closeout/record.json"
    if not closeout.exists():
        publish(
            closeout,
            dict(
                schema="v25_parent_scoped_closeout.v1",
                at=now(),
                parent_completion=entry(PARENT / "result/record.json"),
                verdict="PASS_AS_SCOPED",
                fixed_model_Full_minus_Static_positive_confirmation=True,
                retraining_stability_established=False,
                Full_over_C_only_advantage_established=False,
                independent_N_value_established=False,
                old_records_unchanged=True,
                audit_request=entry(authority),
            ),
        )
    train_root = root / "training_replication"
    a_root = root / "c_only_test_extension"
    b_root = root / "replication_evaluation"
    cpu_command(
        root,
        FILES[1],
        [
            "prepare",
            "--root",
            str(train_root),
            "--source-root",
            str(V18),
        ],
    )
    cpu_command(root, FILES[2], ["register-a", "--root", str(a_root)])
    cpu_command(
        root,
        FILES[2],
        [
            "register-b",
            "--root",
            str(b_root),
            "--training-root",
            str(train_root),
        ],
    )
    refs = {
        "training_registration": entry(train_root / "registration/record.json"),
        "extension_registration": entry(a_root / "registration/record.json"),
        "replication_evaluation_registration": entry(b_root / "registration/record.json"),
    }
    rows = inventory()
    return publish(
        root / "protocol/record.json",
        dict(
            schema="v25_registered_extension_and_replication_workflow.v1",
            at=now(),
            audit_request=entry(authority),
            parent_closeout=entry(closeout),
            implementation_id=frozen["id"],
            cleanup_receipt=cleanup,
            **refs,
            budgets=budgets(),
            old_seeds=list(OLD_SEEDS),
            new_seeds=list(NEW_SEEDS),
            replication_arms=list(ARMS),
            jobs=make_jobs(root),
            allowed_gpu_indices=list(GPUS),
            max_gpu_workers=8,
            memory_floors_mib=MEMORY_FLOORS,
            initial_disk_floor_bytes=MIN_INITIAL_DISK_BYTES,
            dispatch_disk_floor_bytes=MIN_LAUNCH_DISK_BYTES,
            checkpoint_policy="complete original per-step state; no sparse-save change or GC",
            cpu_affinity={str(r["index"]): r["cpu_affinity"] for r in rows},
            gpu_uuids={str(r["index"]): r["uuid"] for r in rows},
            gpu_observation_at_registration=rows,
            queue_policy=(
                "fixed interleaved extension/prefix list, then dependency-ready arms and "
                "single-endpoint evaluation; eligible jobs use idle capacity; 10-second polling"
            ),
            extension_results_not_a_gate_for_replication=True,
            score_barriers=(
                "A all three new models sealed; B all nine new models sealed; "
                "score A when ready without reading its effects for dispatch"
            ),
            test_is_known_benchmark=True,
            no_dev_selection=True,
            no_old_prefix_reuse=True,
            API_calls_authorized=0,
            api_model="deepseek-flash",
            model_fallback=False,
            no_resampling=True,
            no_auto_retry=True,
            no_seed_or_checkpoint_selection=True,
            failure_policy=(
                "on infrastructure/contract failure stop new dispatch and drain owned workers; "
                "negative scientific effects do not stop or change the replication"
            ),
            headroom_is_not_an_OOM_or_disk_capacity_guarantee=True,
        ),
    )


def process_birth(pid):
    path = Path("/proc") / str(pid) / "stat"
    if not path.exists():
        return None
    rest = path.read_text().rsplit(")", 1)[1].split()
    return None if rest[0] == "Z" else rest[19]


class Controller:
    def __init__(self, root, resume=False):
        self.root = Path(root).resolve()
        require(self.root == ROOT, "only the registered followup root may execute")
        self.plan = checked(self.root / "protocol/record.json")
        manifest = checked(self.root / "implementation/record.json")
        require(manifest["id"] == self.plan["implementation_id"], "implementation binding changed")
        require(
            Path(__file__).resolve() == self.root / "implementation" / FILES[0],
            "run the committed frozen controller, not mutable workspace code",
        )
        for name, sha in manifest["sha256"].items():
            require(
                hashlib.sha256((self.root / "implementation" / name).read_bytes()).hexdigest()
                == sha,
                "frozen script changed",
            )
        for key in (
            "training_registration",
            "extension_registration",
            "replication_evaluation_registration",
        ):
            require(
                entry(self.plan[key]["path"]) == self.plan[key], "registered experiment changed"
            )
        require(
            self.plan["api_model"] == "deepseek-flash" and self.plan["API_calls_authorized"] == 0,
            "API policy changed",
        )
        require(
            self.plan["jobs"] == make_jobs(self.root)
            and self.plan["budgets"] == budgets()
            and self.plan["memory_floors_mib"] == MEMORY_FLOORS
            and self.plan["dispatch_disk_floor_bytes"] == MIN_LAUNCH_DISK_BYTES,
            "job matrix changed",
        )
        require(
            not (self.root / "result/record.json").exists(),
            "completed queue must not be reopened",
        )
        self.jobs = self.plan["jobs"]
        self.children = {}
        self.completed = set()
        self.failures = []
        self.stop = False
        for job in self.jobs:
            attempt = self.root / "queue/jobs" / job["key"] / "attempt001"
            launch, exit_path = attempt / "launch/record.json", attempt / "exit/record.json"
            if not launch.exists():
                require(not Path(job["result"]).exists(), "unowned result requires inspection")
                if attempt.exists():
                    require(resume, "partial prior attempt requires explicit inspection/resume")
                    self.failures.append(
                        {
                            "job": job["key"],
                            "reason": (
                                "intent-only or partial launch; "
                                "never start a replacement automatically"
                            ),
                        }
                    )
                continue
            require(resume, "existing attempts require explicit resume")
            started = checked(launch)
            require(
                started["protocol_id"] == self.plan["id"] and started["job"] == job,
                "foreign launched job",
            )
            if exit_path.exists():
                ended = checked(exit_path)
                require(
                    ended["protocol_id"] == self.plan["id"] and ended["key"] == job["key"],
                    "foreign worker exit",
                )
                if ended["completed"] and Path(job["result"]).exists():
                    require(
                        ended["result"] == entry(job["result"]),
                        "completed worker result was changed or replaced",
                    )
                    self.completed.add(job["key"])
                else:
                    self.failures.append({"job": job["key"], "exit": str(exit_path)})
            elif started["birth"] is not None and process_birth(started["pid"]) == started["birth"]:
                self.children[job["key"]] = dict(
                    job=job,
                    attempt=attempt,
                    pid=started["pid"],
                    birth=started["birth"],
                    gpu=started["gpu"],
                    process=None,
                )
            elif Path(job["result"]).exists():
                checked(job["result"])
                publish(
                    exit_path,
                    dict(
                        schema="v25_detached_completed_worker.v1",
                        at=now(),
                        key=job["key"],
                        completed=True,
                        exit_code=None,
                        exit_code_source="detached_process_gone_with_bound_completion_record",
                        result=entry(job["result"]),
                        protocol_id=self.plan["id"],
                    ),
                )
                self.completed.add(job["key"])
            else:
                self.failures.append(
                    {
                        "job": job["key"],
                        "reason": "previous worker absent without completion; never auto-restart",
                    }
                )

    def status(self, phase):
        atomic_status(
            self.root,
            dict(
                at=now(),
                phase=phase,
                protocol_id=self.plan["id"],
                completed=sorted(self.completed),
                total_jobs=len(self.jobs),
                active_children=[
                    {
                        k: (str(v) if isinstance(v, Path) else v)
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
                allowed_gpu_indices=list(GPUS),
                max_gpu_workers=8,
                API_calls=0,
                no_resampling=True,
                parent_experiment_remains_complete=True,
                available_disk_bytes=disk_available(self.root),
                extension_scored=(self.root / "c_only_test_extension/summary/record.json").exists(),
                replication_scored=(
                    self.root / "replication_evaluation/summary/record.json"
                ).exists(),
            ),
        )

    def launch(self, job, row):
        require(
            job in self.jobs and job["key"] not in self.completed | set(self.children),
            "unknown or repeated job",
        )
        require(row["index"] in GPUS and len(self.children) < 8, "eight-GPU bound")
        require(row["free_mib"] >= job["minimum_free_mib"], "job memory admission floor")
        require(
            row["index"] not in {c["gpu"] for c in self.children.values()},
            "one owned worker per GPU",
        )
        require(disk_available(self.root) >= MIN_LAUNCH_DISK_BYTES, "disk admission floor")
        require(
            row["uuid"] == self.plan["gpu_uuids"][str(row["index"])]
            and row["cpu_affinity"] == self.plan["cpu_affinity"][str(row["index"])],
            "GPU mapping changed",
        )
        attempt = self.root / "queue/jobs" / job["key"] / "attempt001"
        require(not attempt.exists(), "one attempt only; no implicit retry")
        attempt.mkdir(parents=True)
        command = [
            "/usr/bin/taskset",
            "--cpu-list",
            row["cpu_affinity"],
            str(PYTHON),
            "-u",
            str(self.root / "implementation" / job["script"]),
            *job["args"],
            "--root",
            str(self.root / job["branch"]),
            "--gpu-index",
            str(row["index"]),
        ]
        env = command_environment()
        publish(
            attempt / "intent/record.json",
            dict(
                schema="v25_worker_intent.v1",
                at=now(),
                protocol_id=self.plan["id"],
                job=job,
                gpu=row["index"],
                command=command,
            ),
        )
        with (attempt / "worker.log").open("xb") as log:
            proc = subprocess.Popen(
                command,
                cwd=FROZEN,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        # Own the process before any fallible identity/receipt I/O. Even an early
        # exit or failed receipt must be drained; it must not become an unowned retry.
        self.children[job["key"]] = dict(
            job=job, attempt=attempt, pid=proc.pid, birth=None, gpu=row["index"], process=proc
        )
        birth = process_birth(proc.pid)
        self.children[job["key"]]["birth"] = birth
        publish(
            attempt / "launch/record.json",
            dict(
                schema="v25_worker_launch.v1",
                at=now(),
                protocol_id=self.plan["id"],
                job=job,
                gpu=row["index"],
                gpu_uuid=row["uuid"],
                pid=proc.pid,
                birth=birth,
                command=command,
                no_resampling=True,
            ),
        )

    def reap(self):
        for key, child in list(self.children.items()):
            proc = child["process"]
            rc = proc.poll() if proc is not None else None
            if (proc is not None and rc is None) or (
                proc is None
                and child["birth"] is not None
                and process_birth(child["pid"]) == child["birth"]
            ):
                continue
            job = child["job"]
            complete = Path(job["result"]).exists() and (rc == 0 or proc is None)
            try:
                result = entry(job["result"]) if complete else None
                publish(
                    child["attempt"] / "exit/record.json",
                    dict(
                        schema="v25_worker_exit.v1",
                        at=now(),
                        protocol_id=self.plan["id"],
                        key=key,
                        exit_code=rc,
                        exit_code_source="Popen_wait_status"
                        if proc is not None
                        else "detached_process_gone",
                        completed=complete,
                        result=result,
                        no_automatic_retry=True,
                    ),
                )
            except Exception as exc:
                complete = False
                self.failures.append(
                    {"job": key, "receipt_error": type(exc).__name__, "message": str(exc)}
                )
            del self.children[key]
            if complete:
                self.completed.add(key)
            else:
                self.failures.append(
                    {"job": key, "exit_code": rc, "log": str(child["attempt"] / "worker.log")}
                )

    def score_ready_blocks(self):
        # No metric value is inspected by the scheduler.
        extension = {j["key"] for j in self.jobs if j["branch"] == "c_only_test_extension"}
        replication = {j["key"] for j in self.jobs if j["branch"] == "replication_evaluation"}
        for keys, branch in (
            (extension, "c_only_test_extension"),
            (replication, "replication_evaluation"),
        ):
            if keys <= self.completed and not (self.root / branch / "summary/record.json").exists():
                cpu_command(self.root, FILES[2], ["score", "--root", str(self.root / branch)])

    def run(self):
        while len(self.completed) < len(self.jobs):
            try:
                self.reap()
                if not self.failures and not self.stop:
                    self.score_ready_blocks()
                    occupied = {c["gpu"] for c in self.children.values()}
                    if disk_available(self.root) >= MIN_LAUNCH_DISK_BYTES:
                        for row in sorted(inventory(), key=lambda r: r["index"]):
                            if row["index"] in occupied:
                                continue
                            candidates = admitted_jobs(
                                self.jobs,
                                self.completed,
                                set(self.children),
                                row,
                            )
                            if len(self.children) == 8:
                                break
                            if candidates:
                                self.launch(candidates[0], row)
                                occupied.add(row["index"])
                phase = (
                    "DRAINING_AFTER_FAILURE"
                    if self.failures
                    else "REPLICATION_GPU_RUNNING"
                    if self.children
                    else "WAITING_FOR_DISK_HEADROOM"
                    if disk_available(self.root) < MIN_LAUNCH_DISK_BYTES
                    else "WAITING_FOR_FREE_GPU"
                )
                self.status(phase)
            except Exception as exc:
                self.failures.append({"controller_error": type(exc).__name__, "message": str(exc)})
                self.stop = True
            if (self.failures or self.stop) and not self.children:
                self.status("BLOCKED_SAVED" if self.failures else "STOPPED_SAVED")
                return
            if len(self.completed) < len(self.jobs):
                time.sleep(10)
        if self.failures or self.stop:
            self.status("BLOCKED_SAVED" if self.failures else "STOPPED_SAVED")
            return
        self.status("REPLICATION_CPU_SCORING")
        self.score_ready_blocks()
        a_root = self.root / "c_only_test_extension"
        b_root = self.root / "replication_evaluation"
        combined = self.root / "descriptive_six_seed_summary"
        cpu_command(
            self.root,
            FILES[2],
            [
                "combine",
                "--a-root",
                str(a_root),
                "--b-root",
                str(b_root),
                "--output",
                str(combined),
            ],
        )
        publish(
            self.root / "result/record.json",
            dict(
                schema="v25_completed_extension_and_training_replication.v1",
                at=now(),
                protocol_id=self.plan["id"],
                extension_summary=entry(a_root / "summary/record.json"),
                replication_summary=entry(b_root / "summary/record.json"),
                combined_descriptive_summary=entry(combined / "record.json"),
                physical_training_steps=budgets()["replication_physical_training_steps"],
                registered_budgets=budgets(),
                parent_experiment_reopened=False,
                API_calls=0,
                no_additional_seeds_or_models=True,
                no_algorithm_tuning_from_extension_or_replication_test=True,
            ),
        )
        self.status("REPLICATION_COMPLETE")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "run", "resume"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    parser.add_argument("--audit-path", type=Path)
    args = parser.parse_args()
    require(args.root.resolve() == ROOT, "fixed followup destination required")
    (args.root / "queue").mkdir(parents=True, exist_ok=True)
    with (args.root / "queue/controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == "initialize":
            require(
                args.source_commit is not None and args.audit_path is not None,
                "source commit and supplied user audit required",
            )
            print(
                json.dumps(
                    initialize(args.root, args.source_commit, args.audit_path), ensure_ascii=False
                )
            )
            return
        controller = Controller(args.root, resume=args.action == "resume")

        def stop_requested(signum, frame):
            controller.stop = True

        signal.signal(signal.SIGTERM, stop_requested)
        signal.signal(signal.SIGINT, stop_requested)
        try:
            controller.run()
        except Exception as exc:
            controller.failures.append(
                {"controller_error": type(exc).__name__, "message": str(exc)}
            )
            controller.status(
                "BLOCKED_SAVED_WITH_LIVE_CHILDREN" if controller.children else "BLOCKED_SAVED"
            )
            raise


if __name__ == "__main__":
    main()
