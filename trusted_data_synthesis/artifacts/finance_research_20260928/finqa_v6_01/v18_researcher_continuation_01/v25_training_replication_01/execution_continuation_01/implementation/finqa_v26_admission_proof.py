"""Read-only, fail-closed evidence for a V25 rejection before scientific work.

An empty episode directory is not sufficient.  A replacement execution attempt
is admissible only when the frozen worker failed at its resource gate, its old
process/session is dead, and the complete target tree contains only the public
registration metadata that precedes that gate.  Never imports CUDA or workers.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ERROR = "ValueError: insufficient GPU margin; no allocation/placeholder/wait"
WORKERS = {
    "test": ("finqa_v25_evaluation.py", "generate", {580, 583}),
    "prefix": ("finqa_v25_training_replication.py", "locked_worker", {494, 500}),
    "arm": ("finqa_v25_training_replication.py", "locked_worker", {494, 500}),
}
# The fingerprint is intentionally limited to the exact already-registered
# worker revision, not an arbitrary future script with an equivalent error text.
WORKER_SHA256 = {
    "finqa_v25_evaluation.py": "c4b0ac45534a6e0dd12e344bc3cf299c6e44991af7695700a615ce751f292285",
    "finqa_v25_training_replication.py": (
        "6be6b697e1517cb87ceb5fc8e33bad73d7a" "ffef6e9d9cc8685e88724f019fa05"
    ),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def checked(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "missing or symlinked evidence: " + str(path))
    value = json.loads(path.read_bytes())
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "record identity changed: " + str(path),
    )
    return value


def reference(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "regular evidence file required")
    raw = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def process_snapshot(pid):
    """A reused PID is distinguishable from the launch by Linux start ticks."""
    try:
        fields = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
    except FileNotFoundError:
        return None
    return {
        "pid": pid,
        "state": fields[0],
        "pgrp": int(fields[2]),
        "session": int(fields[3]),
        "birth": fields[19],
    }


def process_group_members(pid):
    """Also reject an orphaned child from the worker's start_new_session group."""
    result = []
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        current = process_snapshot(int(path.name))
        if (
            current is not None
            and current["state"] != "Z"
            and (current["pgrp"] == pid or current["session"] == pid)
        ):
            result.append(current)
    return sorted(result, key=lambda row: row["pid"])


def _target(root, job):
    args = job["args"]
    require("--seed" in args, "registered seed argument required")
    seed = args[args.index("--seed") + 1]
    require(re.fullmatch(r"[0-9]+", seed) is not None, "invalid seed coordinate")
    if job["kind"] == "prefix":
        require(
            job["branch"] == "training_replication" and args == ["prefix", "--seed", seed],
            "unexpected prefix command",
        )
        return root / job["branch"] / f"seed{seed}"
    require("--arm" in args, "registered arm argument required")
    arm = args[args.index("--arm") + 1]
    require(arm in ("static", "c_only", "full"), "invalid arm coordinate")
    command = "generate" if job["kind"] == "test" else "train"
    require(args == [command, "--seed", seed, "--arm", arm], "unexpected worker arguments")
    if job["kind"] == "test":
        require(
            job["branch"] in ("c_only_test_extension", "replication_evaluation"),
            "unexpected evaluation branch",
        )
        return root / job["branch"] / "models" / f"seed{seed}" / arm
    require(
        job["kind"] == "arm" and job["branch"] == "training_replication",
        "unexpected training branch",
    )
    return root / job["branch"] / f"seed{seed}" / "arms" / arm


def _scientific_tree(root, job):
    target = _target(root, job)
    require(not target.is_symlink(), "symlinked scientific target")
    require(not Path(job["result"]).exists(), "completed result must never be replaced")
    evidence = {"target": str(target), "target_exists": target.exists()}
    if job["kind"] != "test":
        require(
            not target.exists(),
            "training target already exists: possible launch/initialization/optimizer work",
        )
        return evidence | {
            "files": [],
            "counts": {
                "scientific_files": 0,
                "worker_launch_intents": 0,
                "fresh_initializations": 0,
                "optimizer_or_step_records": 0,
                "state_files": 0,
                "feedback_records": 0,
            },
        }
    require(target.is_dir(), "expected public evaluation registration is missing")
    allowed = {Path("shards/test1147/generation/run.json")}
    if job["branch"] == "replication_evaluation":
        allowed.add(Path("checkpoint_binding/record.json"))
    allowed_directories = {parent for p in allowed for parent in p.parents if str(parent) != "."}
    found = set()
    for path in target.rglob("*"):
        require(not path.is_symlink(), "symlinked scientific evidence")
        relative = path.relative_to(target)
        if path.is_dir():
            require(
                relative in allowed_directories,
                "non-registration scientific directory: " + str(relative),
            )
        else:
            require(
                path.is_file() and relative in allowed,
                "non-registration scientific file: " + str(relative),
            )
            found.add(relative)
    require(found == allowed, "incomplete public-only model registration")
    files = []
    for relative in sorted(allowed):
        value = checked(target / relative)
        files.append(reference(target / relative) | {"id": value["id"]})
    run = checked(target / "shards/test1147/generation/run.json")
    require(
        run.get("role") == "test"
        and run.get("registered_denominator") == 1147
        and len(run.get("episode_keys", [])) == len(set(run.get("episode_keys", []))) == 1147,
        "public registration does not identify the fixed test1147 tasks",
    )
    return evidence | {
        "files": files,
        "registered_episode_keys": 1147,
        "registration_is_not_generated_output": True,
        "counts": {
            "metadata_files": len(files),
            "scientific_files": 0,
            "model_attempts": 0,
            "provider_intents": 0,
            "provider_receipts": 0,
            "episodes": 0,
            "generation_or_whole_test_seals": 0,
            "score_records": 0,
        },
    }


def prove_clean_precompute_rejection(root, job, attempt_path):
    """Return serializable evidence or raise ValueError; never grants a retry itself.

    ``root`` is the original scientific V25 root. ``attempt_path`` may be in
    its old queue or in the explicitly authorized execution-only continuation.
    Caller must hold the dispatch lock and publish this evidence before creating
    a new numbered attempt. Preserve old attempt, exit and public run records.
    """
    root, attempt = Path(root).resolve(), Path(attempt_path).resolve()
    require(attempt.is_relative_to(root), "attempt outside registered experiment")
    plan = checked(root / "protocol/record.json")
    require(job in plan["jobs"], "job outside immutable scientific protocol")
    require(job["kind"] in WORKERS, "unsupported worker kind")
    manifest = checked(root / "implementation/record.json")
    require(manifest["id"] == plan["implementation_id"], "implementation binding changed")
    script, function, lines = WORKERS[job["kind"]]
    require(job["script"] == script, "wrong registered worker script")
    worker = root / "implementation" / script
    worker_ref = reference(worker)
    require(
        worker_ref["sha256"] == manifest["sha256"][script] == WORKER_SHA256[script],
        "worker differs from the narrowly audited precompute fingerprint",
    )
    records = {
        name: checked(attempt / name / "record.json") for name in ("intent", "launch", "exit")
    }
    intent, launch, ended = (records[name] for name in ("intent", "launch", "exit"))
    require(
        len({record["protocol_id"] for record in records.values()}) == 1,
        "attempt execution protocol changed",
    )
    require(
        all(
            record.get("scientific_protocol_id", record["protocol_id"]) == plan["id"]
            for record in records.values()
        ),
        "attempt belongs to another scientific protocol",
    )
    require(
        intent["job"] == launch["job"] == job and ended["key"] == job["key"], "foreign attempt job"
    )
    require(
        ended["exit_code"] == 1 and ended["completed"] is False and ended["result"] is None,
        "not an observed uncompleted admission rejection",
    )
    require(
        intent["gpu"] == launch["gpu"] and intent["command"] == launch["command"],
        "launch differs from original intent",
    )
    command = launch["command"]
    require(
        str(worker) in command and "--resume" not in command,
        "only a fresh unchanged worker launch may be requeued",
    )
    script_index = command.index(str(worker))
    require(
        command[script_index + 1 :]
        == [*job["args"], "--root", str(root / job["branch"]), "--gpu-index", str(launch["gpu"])],
        "worker command differs from frozen scientific coordinates",
    )
    pid, birth = launch["pid"], launch["birth"]
    require(
        type(pid) is int and pid > 0 and isinstance(birth, str) and birth.isdigit(),
        "missing original process identity",
    )
    current = process_snapshot(pid)
    require(
        current is None or current["state"] == "Z" or current["birth"] != birth,
        "original worker is still alive",
    )
    descendants = process_group_members(pid)
    require(not descendants, "original worker session has live processes")
    log_path = attempt / "worker.log"
    log = log_path.read_text()
    require(
        log.count("Traceback (most recent call last):") == 1 and log.rstrip().endswith(ERROR),
        "failure is not the unique known admission rejection",
    )
    frames = re.findall(r'^  File "([^"]+)", line ([0-9]+), in ([^\n]+)$', log, re.MULTILINE)
    worker_frames = [(int(line), name) for path, line, name in frames if path == str(worker)]
    require(
        worker_frames and worker_frames[-1][0] in lines and worker_frames[-1][1] == function,
        "failure was not at the audited precompute resource gate",
    )
    require(
        len(frames) >= 3
        and frames[-2][2] == "eligible_gpu"
        and frames[-1][2] == "require"
        and Path(frames[-2][0]).name == Path(frames[-1][0]).name == "v9_training_launcher.py",
        "resource rejection did not originate in the frozen eligible_gpu guard",
    )
    require(
        ".eligible_gpu(" in worker.read_text().splitlines()[worker_frames[-1][0] - 1],
        "traceback source line no longer names the audited resource guard",
    )
    science = _scientific_tree(root, job)
    return {
        "schema": "v26_clean_precompute_admission_rejection.v1",
        "at": datetime.now(timezone.utc).isoformat(),
        "clean": True,
        "scientific_protocol_id": plan["id"],
        "job_key": job["key"],
        "job_digest": digest(job),
        "attempt": str(attempt),
        "failure_fingerprint": {
            "error": ERROR,
            "worker_function": function,
            "worker_line": worker_frames[-1][0],
            "worker": worker_ref,
        },
        "references": {
            "protocol": reference(root / "protocol/record.json"),
            "implementation": reference(root / "implementation/record.json"),
            "worker_log": reference(log_path),
            **{
                name: reference(attempt / name / "record.json") | {"id": records[name]["id"]}
                for name in records
            },
        },
        "old_process": {
            "pid": pid,
            "birth": birth,
            "observed": current,
            "original_identity_alive": False,
            "live_session_members": descendants,
        },
        "scientific_target": science,
        "scientific_budget_consumed_by_attempt": {
            "provider_calls": 0,
            "episodes": 0,
            "optimizer_steps": 0,
            "outer_updates": 0,
        },
        "current_gpu_capacity_consulted": False,
        "old_attempt_must_remain_immutable": True,
        "replacement_requires_new_execution_attempt": True,
        "same_coordinate_resampling_authorized": False,
    }


prove_clean_admission_failure = prove_clean_precompute_rejection
