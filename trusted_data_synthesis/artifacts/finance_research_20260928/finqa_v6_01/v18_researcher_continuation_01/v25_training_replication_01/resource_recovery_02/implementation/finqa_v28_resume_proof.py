"""Narrow read-only proof for the one inspected seed251/C-only gradient OOM.

This is not generic OOM retry permission.  It admits one explicit same-run
restore of the original step0298_branch after an uncommitted gradient failure,
only while all original evidence and the complete arm tree remain unchanged.
No model is instantiated; checkpoint tensors are deserialized on CPU only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

JOB_KEY = "replication-train-seed251-c_only"
ORIGINAL_PID = 651779
ORIGINAL_BIRTH = "373851616"
WORKER = "finqa_v25_training_replication.py"
WORKER_SHA = "6be6b697e1517cb87ceb5fc8e33bad73d7affef6e9d9cc8685e88724f019fa05"
BRANCH_SHA = "818c955c172ddea3839520d7d5f65e408467ac3baab00e838f9ab341d19c98fa"
BRANCH_DIGEST = "b7a9a7c1637dd5b95e62c92a436f22c919943dd52524d814030e923464de0f7a"
SHARED_SHA = "5ad7be1185e3a2eb97673bb5d41d48ac0d44665abc473ac8a2b0e59b4893269e"
SHARED_DIGEST = "7c4cbc41d73e26bc97c8c212a26342c984cbeac4055e69ef2b7a2aec33dd6182"
SOURCE_SHA = {
    "v8_training_driver.py": "cc5d18faa9af8121926e684d5d8f6a0e6eecacb3b4e725441487f73230c87b4d",
    "v9_training_launcher.py": "06f2a5d11b9d422103a89398af0de9ff8a38e4978e8281f93a89b9763f217dea",
    "v16_arm_training.py": "4fc19b1f6a241a45e9e3377a41a69631f37e31c28fb452542e5a435a5a6e3086",
}
OUTER = Path("training/outer_attempts/step0298/attempt001")
EXPECTED_FILES = {
    Path("launch_attempts/attempt001/intent/record.json"),
    Path("launch_attempts/attempt001/stopped/record.json"),
    Path("training/step0298_branch/record.json"),
    Path("training/step0298_branch/state.pt"),
    OUTER / "intent/record.json",
    OUTER / "phases/000/record.json",
    OUTER / "phases/001/record.json",
    OUTER / "failure/record.json",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def reference(path):
    path = Path(path)
    require(
        path.is_file() and not path.is_symlink(), "regular evidence file required: " + str(path)
    )
    raw = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def checked(path):
    reference(path)
    value = json.loads(Path(path).read_bytes())
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "bound evidence changed: " + str(path),
    )
    return value


def checked_ref(ref, path):
    value = checked(path)
    require(
        ref
        == {
            "path": str(Path(path).resolve()),
            "sha256": reference(path)["sha256"],
            "id": value["id"],
        },
        "evidence reference changed: " + str(path),
    )
    return value


def process_snapshot(pid):
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


def live_session_members(pid):
    result = []
    for path in Path("/proc").iterdir():
        if path.name.isdigit():
            row = process_snapshot(int(path.name))
            if (
                row is not None
                and row["state"] != "Z"
                and (row["pgrp"] == pid or row["session"] == pid)
            ):
                result.append(row)
    return sorted(result, key=lambda row: row["pid"])


def arm_inventory(arm_root):
    """Reject even empty additional directories, including a feedback intent root."""
    arm_root = Path(arm_root)
    allowed_dirs = {parent for p in EXPECTED_FILES for parent in p.parents if str(parent) != "."}
    require(arm_root.is_dir() and not arm_root.is_symlink(), "original arm directory required")
    found = {}
    for path in arm_root.rglob("*"):
        require(not path.is_symlink(), "symlinked arm evidence")
        relative = path.relative_to(arm_root)
        if path.is_dir():
            require(relative in allowed_dirs, "unexpected arm directory: " + str(relative))
        else:
            require(
                path.is_file() and relative in EXPECTED_FILES,
                "unexpected scientific artifact: " + str(relative),
            )
            found[str(relative)] = reference(path)
    require(set(map(Path, found)) == EXPECTED_FILES, "original eight-file arm tree incomplete")
    return found


def tree_digest(value):
    """Exact CPU implementation of the bound V8 tensor-tree identity algorithm."""
    import torch

    if isinstance(value, torch.Tensor):
        raw = value.detach().cpu().contiguous()
        return digest(
            {
                "shape": list(raw.shape),
                "dtype": str(raw.dtype),
                "sha256": hashlib.sha256(
                    raw.reshape(-1).view(torch.uint8).numpy().tobytes()
                ).hexdigest(),
            }
        )
    if isinstance(value, dict):
        return digest({str(k): tree_digest(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return digest([tree_digest(v) for v in value])
    return digest(value)


def checkpoint_evidence(branch, shared):
    import torch

    require(not torch.cuda.is_initialized(), "resume proof must run in a CPU-only process")
    checkpoints = {}
    states = {}
    for label, directory, sha, actual, arm, phase in (
        ("branch", Path(branch), BRANCH_SHA, BRANCH_DIGEST, "C-only", "branch"),
        ("shared", Path(shared), SHARED_SHA, SHARED_DIGEST, "shared", "step"),
    ):
        state_ref = reference(directory / "state.pt")
        metadata = json.loads((directory / "record.json").read_bytes())
        require(
            state_ref["sha256"] == metadata["state_sha256"] == sha
            and metadata["actual_state_digest"] == actual,
            "not the explicitly audited checkpoint bytes",
        )
        require(
            metadata["seed"] == 251
            and metadata["arm"] == arm
            and metadata["step"] == 298
            and metadata["phase"] == phase
            and metadata["checkpoint_contains_actual_model_Adam_RNG_pi"] is True,
            "checkpoint coordinates or completeness changed",
        )
        # Local trusted checkpoints are identified by an exact prior SHA before
        # deserialization. map_location forbids restoring device storage to CUDA.
        state = torch.load(directory / "state.pt", map_location="cpu", weights_only=False)
        require(tree_digest(state) == actual, "tensor state identity changed")
        require(
            state["seed"] == 251
            and state["arm"] == arm
            and state["step"] == 298
            and state["outer_done"] == []
            and state["pool_id"] == metadata["pool_id"]
            and state["schedule"]["schedule_sha256"] == metadata["schedule_sha256"],
            "saved training state coordinates changed",
        )
        checkpoints[label] = {
            "metadata": reference(directory / "record.json"),
            "state": state_ref,
            "actual_state_digest": actual,
        }
        states[label] = state
    saved, parent = states["branch"], states["shared"]
    require(
        saved.keys() == parent.keys()
        and [k for k in saved if tree_digest(saved[k]) != tree_digest(parent[k])] == ["arm"],
        "branch differs from its original shared point beyond the arm label",
    )
    fields = (
        "parameters",
        "buffers",
        "optimizer",
        "rng",
        "pi",
        "prior",
        "schedule",
        "execution_plan",
        "adapter_binding",
        "frozen_base_digest",
        "model_training",
    )
    require(all(k in saved for k in fields), "incomplete saved restore state")
    require(
        saved["rng"].keys() == {"python", "torch", "cuda"}
        and saved["rng"]["cuda"] is not None
        and len(saved["rng"]["cuda"]) == 1,
        "Python/Torch/one-device CUDA RNG not fully retained",
    )
    require(
        len(saved["parameters"]) == len(saved["optimizer"]["state"]) == 112,
        "registered LoRA/Adam coordinates incomplete",
    )
    require(
        {float(row["step"]) for row in saved["optimizer"]["state"].values()} == {298.0},
        "saved Adam step is not the actual shared step298",
    )
    require(tree_digest(saved["pi"]) == tree_digest(saved["prior"]), "outer pi already changed")
    require(not torch.cuda.is_initialized(), "CPU proof unexpectedly initialized CUDA")
    return {
        "checkpoints": checkpoints,
        "component_digests": {k: tree_digest(saved[k]) for k in fields},
        "shared_comparison_differences": ["arm"],
        "trainable_tensors": 112,
        "Adam_state_entries": 112,
        "Adam_step_values": [298],
        "outer_done": [],
        "cuda_initialized": False,
        "step": 298,
        "pool_id": saved["pool_id"],
        "schedule_sha256": saved["schedule"]["schedule_sha256"],
    }


def prove_same_run_gradient_oom_resume(source_root, predecessor_root):
    """Return deterministic bound evidence, or fail before any state mutation.

    Call again immediately before the authorized new --resume launch. Evidence
    identity is stable while the source tree is unchanged; no timestamp is added.
    Once a new worker intent exists this narrow one-time proof intentionally fails.
    """
    root, predecessor = Path(source_root).resolve(), Path(predecessor_root).resolve()
    require(predecessor == root / "same_run_recovery_01", "wrong predecessor root")
    plan = checked(root / "protocol/record.json")
    training = checked(root / "training_replication/registration/record.json")
    implementation = checked(root / "implementation/record.json")
    require(implementation["id"] == plan["implementation_id"], "frozen implementation changed")
    job = next((j for j in plan["jobs"] if j["key"] == JOB_KEY), None)
    require(
        job is not None
        and job["kind"] == "arm"
        and job["branch"] == "training_replication"
        and job["script"] == WORKER
        and job["args"] == ["train", "--seed", "251", "--arm", "c_only"],
        "only the registered seed251/C-only arm may resume",
    )
    worker = root / "implementation" / WORKER
    require(
        reference(worker)["sha256"]
        == implementation["sha256"][WORKER]
        == training["source_binding"]["script_sha256"]
        == WORKER_SHA,
        "frozen scientific worker changed",
    )
    runtime = Path(implementation["scientific_runtime"])
    require(str(runtime) == training["source_binding"]["source_runtime"], "runtime root changed")
    sources = {WORKER: reference(worker)}
    for name, sha in SOURCE_SHA.items():
        path = runtime / "trusted_data_synthesis/src/trusted_synthesis/finance_research" / name
        sources[name] = reference(path)
        require(sources[name]["sha256"] == sha, "frozen restore/outer runtime changed: " + name)
    attempt = predecessor / "queue/jobs" / JOB_KEY / "attempt001"
    launch = checked(attempt / "launch/record.json")
    ended = checked(attempt / "exit/record.json")
    intent = checked(attempt / "intent/record.json")
    execution_plan = checked(predecessor / "protocol/record.json")
    require(
        all(
            r["protocol_id"] == execution_plan["id"] and r["scientific_protocol_id"] == plan["id"]
            for r in (launch, ended, intent)
        ),
        "failed execution belongs to a different protocol",
    )
    require(
        launch["job"] == intent["job"] == job
        and ended["key"] == JOB_KEY
        and ended["exit_code"] == 1
        and ended["completed"] is False
        and ended["result"] is None,
        "not the original observed failed worker",
    )
    command = launch["command"]
    require(
        command == intent["command"]
        and str(worker) in command
        and "--resume" not in command
        and command[command.index(str(worker)) + 1 :]
        == [
            *job["args"],
            "--root",
            str(root / "training_replication"),
            "--gpu-index",
            str(launch["gpu"]),
        ],
        "original worker command changed",
    )
    pid, birth = launch["pid"], launch["birth"]
    require(
        type(pid) is int and pid > 0 and isinstance(birth, str) and birth.isdigit(),
        "original process identity missing",
    )
    require(
        pid == ORIGINAL_PID and birth == ORIGINAL_BIRTH,
        "not the explicitly audited original process identity",
    )
    observed = process_snapshot(pid)
    require(
        observed is None or observed["state"] == "Z" or observed["birth"] != birth,
        "original failed worker still alive",
    )
    require(not live_session_members(pid), "original failed worker session still alive")
    arm = root / "training_replication/seed251/arms/c_only"
    inventory = arm_inventory(arm)
    launched = checked(arm / "launch_attempts/attempt001/intent/record.json")
    stopped = checked(arm / "launch_attempts/attempt001/stopped/record.json")
    failure = checked_ref(stopped["outer_failure_audit"], arm / OUTER / "failure/record.json")
    outer_intent = checked_ref(failure["intent"], arm / OUTER / "intent/record.json")
    last = checked_ref(failure["last_phase_record"], arm / OUTER / "phases/001/record.json")
    first = checked(arm / OUTER / "phases/000/record.json")
    require(
        launched["pid"] == pid
        and launched["protocol_id"] == training["id"]
        and launched["seed"] == 251
        and launched["arm"] == "C-only"
        and launched["explicit_resume"] is False,
        "scientific launch identity changed",
    )
    require(
        stopped["error_type"] == "OutOfMemoryError"
        and stopped["outer_audit_write_error"] is None
        and stopped["retry_performed"] is False
        and stopped["partial_feedback_resampled"] is False
        and stopped["error"] == failure["error"],
        "scientific stop receipt changed",
    )
    require(
        failure["failure_kind"] == "resource_OOM"
        and failure["error_type"] == "OutOfMemoryError"
        and failure["last_phase"] == "full_class_gradients"
        and failure["feedback_artifacts"] == {}
        and failure["retained_incomplete_feedback"] == []
        and failure["last_completed_replay_response"] is None
        and failure["outer_commit_record_exists"] is False
        and failure["last_committed_training_step"] == 298
        and failure["stopped_before_next_training_step"] is True
        and failure["failure_counted_as_Q_zero"] is False
        and failure["feedback_resampled"] is False
        and failure["automatic_retry"] is False,
        "failure is not the audited pre-feedback uncommitted gradient OOM",
    )
    require(
        first["phase"] == "capture_pre_outer_state"
        and last["phase"] == "full_class_gradients"
        and outer_intent["optimizer_steps_in_outer"] == 0
        and outer_intent["automatic_resampling"] is False,
        "outer progress advanced beyond the safe restore boundary",
    )
    require(
        all(
            r["seed"] == 251
            and r["arm"] == "C-only"
            and r["step"] == 298
            and r["CPU_control_only"] is False
            for r in (failure, outer_intent, first, last)
        ),
        "outer identity changed",
    )
    log = (attempt / "worker.log").read_text()
    require(
        log.count("Traceback (most recent call last):") == 1
        and "in class_gradients" in log
        and "torch.autograd.grad" in log
        and log.rstrip().endswith("torch.OutOfMemoryError: " + failure["error"]),
        "original traceback is not the audited gradient OOM",
    )
    branch = arm / "training/step0298_branch"
    shared = root / "training_replication/seed251/shared/step0298_step"
    metadata = json.loads((branch / "record.json").read_bytes())
    require(
        metadata["evidence"]
        == {"shared_actual_state_digest": SHARED_DIGEST, "shared_checkpoint": str(shared)},
        "branch points to a different shared source",
    )
    tensors = checkpoint_evidence(branch, shared)
    require(
        all(
            r["pool_id"] == tensors["pool_id"]
            and r["schedule_sha256"] == tensors["schedule_sha256"]
            for r in (failure, outer_intent, first, last)
        ),
        "outer/checkpoint binding changed",
    )
    # An explicit second snapshot rejects concurrent additions or byte changes
    # during CPU verification, before the controller may append a resume intent.
    require(arm_inventory(arm) == inventory, "arm evidence changed during preflight")
    value = {
        "schema": "v28_same_run_gradient_oom_restore_proof.v1",
        "eligible": True,
        "job_key": JOB_KEY,
        "scientific_protocol_id": plan["id"],
        "training_protocol_id": training["id"],
        "predecessor_protocol_id": execution_plan["id"],
        "resume_checkpoint": str(branch),
        "resume_flag_required": True,
        "original_process": {
            "pid": pid,
            "birth": birth,
            "observed": observed,
            "original_identity_alive": False,
            "live_session_members": [],
        },
        "source_binding": sources,
        "arm_files": inventory,
        "arm_file_count": 8,
        "references": {
            "failed_intent": reference(attempt / "intent/record.json"),
            "failed_launch": reference(attempt / "launch/record.json"),
            "failed_exit": reference(attempt / "exit/record.json"),
            "worker_log": reference(attempt / "worker.log"),
            "protocol": reference(root / "protocol/record.json"),
            "training_registration": reference(
                root / "training_replication/registration/record.json"
            ),
        },
        "checkpoint_evidence": tensors,
        "feedback_root_exists": False,
        "provider_intents": 0,
        "feedback_episodes": 0,
        "outer_commits": 0,
        "uncommitted_gradient_computation_will_be_repeated": True,
        "optimizer_updates_repeated": 0,
        "feedback_resampling": False,
        "scientific_hyperparameters_changed": False,
        "source_checkpoint_must_not_change": True,
        "cpu_only_no_model_initialization": True,
        "does_not_guarantee_next_attempt_avoids_OOM": True,
    }
    return value | {"id": digest(value)}
