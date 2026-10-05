"""Finite eight-GPU queue for the registered test confirmation and KL shrink control.

New outputs only. Old completed queues, checkpoints and numerical runtime stay frozen.
No retry, resampling, API calls, model selection or signals to other processes.
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
ROOT = V18 / "v23_confirmation_shrink_01"
FROZEN = REPO / ".codex-worktrees/finqa-v18-researcher-continuation-20260930"
PYTHON = REPO / "trusted_data_synthesis/.venv/bin/python"
FILES = (
    "finqa_v23_followup_controller.py",
    "finqa_v23_test_confirmation.py",
    "finqa_v23_shrink_control.py",
)
PARENT_ID = "62ae77b4d4a163ccd5ed754786bec34883ee8f467290dc93ce16d55ff6004787"
SEEDS = (11, 29, 47)
GPUS = tuple(range(8))
MIN_FREE_MIB = 24576


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
            schema="v23_frozen_followup_implementation.v1",
            source_commit=commit,
            sha256={k: v[1] for k, v in expected.items()},
            scientific_runtime=str(FROZEN),
            at=now(),
        ),
    )


def make_jobs(root, shrink_applicable):
    root = Path(root)
    jobs = []
    # Fixed priority: six confirmation models first, then three independent short trains.
    for seed in SEEDS:
        for arm in ("static", "full"):
            jobs.append(
                dict(
                    key=f"test-seed{seed}-{arm}",
                    script=FILES[1],
                    branch="test_confirmation",
                    args=["generate", "--seed", str(seed), "--arm", arm],
                    dependencies=[],
                    result=str(
                        root
                        / f"test_confirmation/models/seed{seed}/{arm}/whole_test_seal/record.json"
                    ),
                )
            )
    if shrink_applicable:
        for seed in SEEDS:
            jobs.append(
                dict(
                    key=f"shrink-train-seed{seed}",
                    script=FILES[2],
                    branch="shrink_control",
                    args=["train", "--seed", str(seed)],
                    dependencies=[],
                    result=str(root / f"shrink_control/seed{seed}/result/record.json"),
                )
            )
        for seed in SEEDS:
            jobs.append(
                dict(
                    key=f"shrink-generate-seed{seed}",
                    script=FILES[2],
                    branch="shrink_control",
                    args=["generate", "--seed", str(seed)],
                    dependencies=[f"shrink-train-seed{seed}"],
                    result=str(
                        root / f"shrink_control/seed{seed}/evaluation/whole_seal/record.json"
                    ),
                )
            )
    return jobs


def ready_jobs(jobs, completed, active):
    return [
        j
        for j in jobs
        if j["key"] not in completed | active and set(j["dependencies"]) <= completed
    ]


def initialize(root, commit, audit_path):
    root = Path(root).resolve()
    require(root == ROOT, "one fixed followup root; no duplicate test cohorts")
    require(
        not (root / "protocol/record.json").exists(),
        "followup already registered; use run or resume",
    )
    parent = checked(V18 / "evaluation_continuation_01/queue/result/record.json")
    require(
        parent["id"] == PARENT_ID
        and not parent["test1147_opened"]
        and not parent["Experiment5_started"],
        "original completed experiment scope changed",
    )
    frozen = freeze(root, commit)
    source = root / "audit_request/record.json"
    if not source.exists():
        raw = Path(audit_path).read_bytes()
        publish(
            source,
            dict(
                schema="v23_user_audit_authority.v1",
                source_path=str(Path(audit_path).resolve()),
                source_sha256=hashlib.sha256(raw).hexdigest(),
                source_text=raw.decode("utf-8"),
                execution_request="参照审计修订并开展后续实验",
                referenced_unattached_audit_appendices_not_read=True,
                external_96_checks_not_claimed_as_local_tests=True,
                at=now(),
            ),
        )
    closeout = root / "parent_closeout/record.json"
    if not closeout.exists():
        publish(
            closeout,
            dict(
                schema="v23_parent_scoped_closeout.v1",
                parent_completion=entry(
                    V18 / "evaluation_continuation_01/queue/result/record.json"
                ),
                verdict="PASS_AS_SCOPED",
                full_VTDO_stable_advantage_confirmed=False,
                no_old_queue_resume=True,
                no_material_rebuild=True,
                audit_request=entry(source),
                at=now(),
            ),
        )
    test = load_module(root, FILES[1])
    shrink = load_module(root, FILES[2])
    test_root, shrink_root = root / "test_confirmation", root / "shrink_control"
    if not (test_root / "registration/record.json").exists():
        test.register(test_root)
    if not (shrink_root / "registration/record.json").exists():
        shrink.prepare(shrink_root, source_root=V18)
    test_reg = checked(test_root / "registration/record.json")
    shrink_reg = checked(shrink_root / "registration/record.json")
    # A publishes its immutable registration before the six prepare_run records.
    # A partial CPU initialization must never become an executable GPU protocol.
    for job in test_reg["jobs"].values():
        run_path = test.generation_root(test_root, job) / "run.json"
        require(run_path.is_file(), "partial confirmation initialization; no GPU dispatch")
        run = checked(run_path)
        require(
            run["tasks"] == test_reg["tasks"]
            and run["config"] == test_reg["config"]
            and run["provider"] == job["model_identity"]
            and run["role"] == "test"
            and run["registered_denominator"] == 1147,
            "confirmation generation registration differs from the frozen protocol",
        )
    # B's public applicability field is checked explicitly before any GPU launch.
    applicable = shrink_reg["applicable"]
    require(type(applicable) is bool, "explicit all-three-seed applicability required")
    rows = inventory()
    return publish(
        root / "protocol/record.json",
        dict(
            schema="v23_registered_confirmation_and_shrink_workflow.v1",
            at=now(),
            audit_request=entry(source),
            parent_closeout=entry(closeout),
            implementation_id=frozen["id"],
            test_registration=entry(test_root / "registration/record.json"),
            shrink_registration=entry(shrink_root / "registration/record.json"),
            test_registration_id=test_reg["id"],
            shrink_all_seeds_applicable=applicable,
            test_sessions=6882,
            test_model_call_cap=220224,
            new_shrink_steps=447 if applicable else 0,
            new_shrink_sessions=1080 if applicable else 0,
            jobs=make_jobs(root, applicable),
            allowed_gpu_indices=list(GPUS),
            max_gpu_workers=8,
            minimum_free_mib=MIN_FREE_MIB,
            cpu_affinity={str(r["index"]): r["cpu_affinity"] for r in rows},
            gpu_uuids={str(r["index"]): r["uuid"] for r in rows},
            gpu_observation_at_registration=rows,
            queue_policy=(
                "fixed test-first list; dependency-ready short-train/evaluation jobs "
                "fill every free GPU; 10-second polling"
            ),
            no_new_Probe_or_feedback=True,
            API_calls_authorized=0,
            api_model="deepseek-flash",
            model_fallback=False,
            no_resampling=True,
            no_auto_retry=True,
            no_seed_or_checkpoint_selection=True,
            failure_policy=(
                "stop new dispatch, drain already-running workers, "
                "preserve partial evidence, no signals to others"
            ),
            headroom_is_not_an_OOM_guarantee=True,
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
        for key in ("test_registration", "shrink_registration"):
            require(
                entry(self.plan[key]["path"]) == self.plan[key], "registered experiment changed"
            )
        require(
            self.plan["api_model"] == "deepseek-flash" and self.plan["API_calls_authorized"] == 0,
            "API policy changed",
        )
        require(
            self.plan["jobs"] == make_jobs(self.root, self.plan["shrink_all_seeds_applicable"]),
            "job matrix changed",
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
                        schema="v23_detached_completed_worker.v1",
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
            ),
        )

    def launch(self, job, row):
        require(
            job in self.jobs and job["key"] not in self.completed | set(self.children),
            "unknown or repeated job",
        )
        require(row["index"] in GPUS and len(self.children) < 8, "eight-GPU bound")
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
        env = dict(
            os.environ,
            PYTHONPATH=str(FROZEN / "trusted_data_synthesis/src"),
            OMP_NUM_THREADS="4",
            MKL_NUM_THREADS="4",
            TOKENIZERS_PARALLELISM="false",
            PYTHONDONTWRITEBYTECODE="1",
        )
        env.pop("CUDA_VISIBLE_DEVICES", None)
        publish(
            attempt / "intent/record.json",
            dict(
                schema="v23_worker_intent.v1",
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
                schema="v23_worker_launch.v1",
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
                        schema="v23_worker_exit.v1",
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

    def run(self):
        while len(self.completed) < len(self.jobs):
            try:
                self.reap()
                if not self.failures and not self.stop:
                    occupied = {c["gpu"] for c in self.children.values()}
                    free = [
                        r
                        for r in inventory()
                        if r["index"] not in occupied and r["free_mib"] >= MIN_FREE_MIB
                    ]
                    for row in sorted(free, key=lambda r: r["index"]):
                        candidates = ready_jobs(self.jobs, self.completed, set(self.children))
                        if not candidates or len(self.children) == 8:
                            break
                        self.launch(candidates[0], row)
                self.status(
                    "DRAINING_AFTER_FAILURE"
                    if self.failures
                    else "FOLLOWUP_GPU_RUNNING"
                    if self.children
                    else "WAITING_FOR_FREE_GPU"
                )
            except Exception as exc:
                self.failures.append({"controller_error": type(exc).__name__, "message": str(exc)})
                # No more dispatch. Keep the current Popen owners alive to reap
                # actual exits; never forward signals to numerical workers.
                self.stop = True
            if (self.failures or self.stop) and not self.children:
                self.status("BLOCKED_SAVED" if self.failures else "STOPPED_SAVED")
                return
            if len(self.completed) < len(self.jobs):
                time.sleep(10)
        self.status("FOLLOWUP_CPU_SCORING")
        test = load_module(self.root, FILES[1])
        shrink = load_module(self.root, FILES[2])
        test_result = self.root / "test_confirmation/summary/record.json"
        if not test_result.exists():
            test.score(self.root / "test_confirmation")
        shrink_result = self.root / "shrink_control/evaluation_result/record.json"
        if self.plan["shrink_all_seeds_applicable"] and not shrink_result.exists():
            shrink.score(self.root / "shrink_control")
        result = self.root / "result/record.json"
        if not result.exists():
            publish(
                result,
                dict(
                    schema="v23_completed_confirmation_and_shrink.v1",
                    at=now(),
                    protocol_id=self.plan["id"],
                    test_summary=entry(test_result),
                    shrink_summary=entry(shrink_result)
                    if self.plan["shrink_all_seeds_applicable"]
                    else None,
                    shrink_status="complete"
                    if self.plan["shrink_all_seeds_applicable"]
                    else "not_applicable_all_seeds_preserved",
                    parent_experiment_reopened=False,
                    API_calls=0,
                    no_additional_seeds_or_models=True,
                    no_algorithm_tuning_from_test=True,
                ),
            )
        self.status("FOLLOWUP_COMPLETE")


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
