"""Read-only V29 OOM proof across bound controller-adoption chains.

Only execution provenance changes here. The byte-pinned V28 checkpoint,
historical-feedback, first-outer and no-resampling checks run unchanged.
No files, signals, model instances, GPU contexts or API calls are created.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
from pathlib import Path
from types import FunctionType

FROZEN_IMPLEMENTATION = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/"
    "v25_training_replication_01/resource_recovery_02/implementation"
)
FROZEN_SHA = {
    "finqa_v28_checkpoint_resume.py": (
        "41eaf97c7aa31a5bcc7150bbb39d4d61e448bb17bdc1868b7741239d7ac050d5"
    ),
    "finqa_v28_resume_proof.py": "c6e04cfdb247ea9edbd8c73c9c5a40379da547c24cb4659b5f040e13b14dcfc5",
    "finqa_v28_memory_worker.py": (
        "91d0665292e5f35e5e11a04e7c2d287a9f3891feb4caab86863358eea3407d19"
    ),
}
for _name, _sha in FROZEN_SHA.items():
    _path = FROZEN_IMPLEMENTATION / _name
    if _path.is_symlink() or hashlib.sha256(_path.read_bytes()).hexdigest() != _sha:
        raise ValueError("frozen V28 checkpoint-proof dependency changed: " + _name)
_spec = importlib.util.spec_from_file_location(
    "v29_byte_pinned_checkpoint_base", FROZEN_IMPLEMENTATION / "finqa_v28_checkpoint_resume.py"
)
v28 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v28)
h = v28.h
require, checked, reference, digest = h.require, h.checked, h.reference, h.digest
source_context, checkpoint_evidence = v28.source_context, v28.checkpoint_evidence
shared_binding, history_evidence = v28.shared_binding, v28.history_evidence


def execution_attempt(root, attempt, job_key, context):
    """Bind one launch and intent to the protocol of their own queue."""
    require(
        attempt.is_relative_to(root)
        and attempt.parent.name == job_key
        and attempt.parent.parent.name == "jobs"
        and attempt.parent.parent.parent.name == "queue"
        and re.fullmatch(r"attempt[0-9]{3,}", attempt.name),
        "foreign execution attempt path",
    )
    queue = attempt.parents[3]
    protocol_path = queue / "protocol/record.json"
    execution = checked(protocol_path)
    require(
        execution["scientific_protocol"]["id"] == context["plan"]["id"]
        and execution["jobs"] == context["plan"]["jobs"],
        "foreign execution protocol",
    )
    launch, intent = [checked(attempt / f"{kind}/record.json") for kind in ("launch", "intent")]
    require(
        all(
            row["protocol_id"] == execution["id"]
            and row["scientific_protocol_id"] == context["plan"]["id"]
            and row["job"] == context["job"]
            for row in (launch, intent)
        )
        and launch["command"] == intent["command"]
        and launch["gpu"] == intent["gpu"]
        and launch.get("memory_mode") == intent.get("memory_mode"),
        "execution launch/intent binding differs",
    )
    require(
        launch.get("origin_launch") == intent.get("origin_launch")
        and launch.get("adopted_existing_process") == intent.get("adopted_existing_process"),
        "execution adoption intent differs",
    )
    return (
        execution,
        launch,
        intent,
        dict(
            protocol=reference(protocol_path),
            launch=reference(attempt / "launch/record.json"),
            intent=reference(attempt / "intent/record.json"),
        ),
    )


def failure_evidence(root, queue_root, job_key, attempt, context):
    require(attempt.parent == queue_root / "queue/jobs" / job_key, "foreign failed attempt path")
    execution, launch, intent, current_refs = execution_attempt(root, attempt, job_key, context)
    require(
        execution.get("schema") == "v29_registered_four_gpu_release_continuation.v1",
        "current failed attempt is not V29",
    )
    ended = checked(attempt / "exit/record.json")
    adopted = launch.get("adopted_existing_process") is True
    require(
        ended["protocol_id"] == execution["id"]
        and ended["scientific_protocol_id"] == context["plan"]["id"]
        and ended["key"] == job_key
        and (ended["exit_code"] == 1 or (adopted and ended["exit_code"] is None))
        and ended["completed"] is False
        and ended["result"] is None,
        "not an observed unsuccessful scientific worker",
    )
    original, original_attempt = launch, attempt
    seen, origins, origin_evidence = {str(attempt / "launch/record.json")}, [], []
    while original.get("origin_launch") is not None:
        require(original.get("adopted_existing_process") is True, "origin link is not adoption")
        origin = original["origin_launch"]
        path = Path(origin["path"]).resolve()
        require(
            path.is_relative_to(root)
            and str(path) not in seen
            and path.name == "record.json"
            and path.parent.name == "launch",
            "foreign or cyclic adopted launch chain",
        )
        seen.add(str(path))
        bound = h.checked_ref(origin, path)
        original_attempt = path.parents[1]
        if original.get("origin_attempt") is not None:
            require(
                Path(original["origin_attempt"]).resolve() == original_attempt,
                "adopted attempt pointer differs",
            )
        _, original, _, refs = execution_attempt(root, original_attempt, job_key, context)
        require(original == bound, "adopted launch changed during proof")
        require(
            all(
                original[field] == launch[field]
                for field in ("job", "pid", "birth", "gpu", "command")
            )
            and original.get("memory_mode") == launch.get("memory_mode"),
            "adopted worker identity changed",
        )
        origins.append(reference(path))
        origin_evidence.append(refs)
    require(original.get("adopted_existing_process") is not True, "adoption lacks execution origin")
    require(bool(origins) == adopted, "adoption provenance differs")

    command, worker = original["command"], str(context["worker"])
    require(command.count(worker) == 1, "worker command changed")
    wrapper_evidence = None
    if "--worker" in command:
        require(
            command.count("--worker") == command.count("--") == 1,
            "ambiguous wrapped original command",
        )
        index, separator = command.index("--worker"), command.index("--")
        require(index > 0 and separator == index + 6, "wrapped CLI differs")
        wrapper = Path(command[index - 1]).resolve()
        require(
            wrapper == FROZEN_IMPLEMENTATION / "finqa_v28_memory_worker.py",
            "foreign memory wrapper",
        )
        mode = original.get("memory_mode")
        require(mode in {"high_cache", "shared_checkpointed"}, "unknown wrapper memory mode")
        require(
            command[index:separator]
            == ["--worker", worker, "--receipt-dir", command[index + 3], "--memory-mode", mode],
            "wrapped CLI differs",
        )
        receipt_dir = Path(command[index + 3]).resolve()
        require(
            receipt_dir == original_attempt / "memory_reservation",
            "foreign wrapper receipt directory",
        )
        manifest = checked(wrapper.parent / "record.json")
        wrapper_protocol = checked(wrapper.parent.parent / "protocol/record.json")
        require(
            wrapper_protocol["implementation_id"] == manifest["id"]
            and wrapper_protocol["scientific_protocol"]["id"] == context["plan"]["id"]
            and wrapper_protocol["jobs"] == context["plan"]["jobs"]
            and reference(wrapper)["sha256"]
            == manifest["sha256"][wrapper.name]
            == FROZEN_SHA[wrapper.name],
            "frozen memory wrapper binding changed",
        )
        suffix = command[separator + 1 :]
        receipt = checked(receipt_dir / "wrapper_intent.json")
        require(
            receipt["pid"] == original["pid"]
            and receipt["memory_mode"] == mode
            and receipt["original_command"] == [worker, *suffix]
            and receipt["scientific_arguments_changed"] is False
            and receipt["source_binding"]["scientific_protocol_id"] == context["plan"]["id"]
            and receipt["source_binding"]["sources"][h.WORKER]["sha256"] == h.WORKER_SHA,
            "wrapper intent differs from original scientific CLI",
        )
        wrapper_evidence = dict(
            source=reference(wrapper),
            intent=reference(receipt_dir / "wrapper_intent.json"),
            manifest=reference(wrapper.parent / "record.json"),
            protocol=reference(wrapper.parent.parent / "protocol/record.json"),
            memory_mode=mode,
        )
    else:
        suffix = command[command.index(worker) + 1 :]
    expected = [
        *context["job"]["args"],
        "--root",
        str(root / "training_replication"),
        "--gpu-index",
        str(launch["gpu"]),
    ]
    require(suffix in (expected, [*expected, "--resume"]), "worker invocation is not original arm")
    pid, birth = launch["pid"], launch["birth"]
    require(
        type(pid) is int and pid > 0 and isinstance(birth, str) and birth.isdigit(),
        "missing failed process identity",
    )
    current = h.process_snapshot(pid)
    require(
        current is None or current["birth"] != birth or current["state"] == "Z",
        "failed worker is still alive",
    )
    require(not h.live_session_members(pid), "failed worker session is still alive")
    scientific_attempts = sorted((context["arm_root"] / "launch_attempts").glob("attempt*"))
    require(scientific_attempts, "missing scientific launch attempt")
    last = scientific_attempts[-1]
    launched, stopped = checked(last / "intent/record.json"), checked(last / "stopped/record.json")
    require(
        launched["pid"] == pid
        and launched["protocol_id"] == context["training"]["id"]
        and launched["seed"] == context["seed"]
        and launched["arm"] == context["arm"]
        and launched["explicit_resume"] == ("--resume" in suffix),
        "scientific attempt differs",
    )
    require(
        stopped["error_type"] == "OutOfMemoryError"
        and "CUDA out of memory" in stopped["error"]
        and stopped["outer_audit_write_error"] is None
        and stopped["retry_performed"] is False
        and stopped["partial_feedback_resampled"] is False,
        "not a settled CUDA OOM",
    )
    log_path = original_attempt / "worker.log"
    log = log_path.read_text()
    require(
        log.count("Traceback (most recent call last):") == 1
        and log.rstrip().endswith("torch.OutOfMemoryError: " + stopped["error"]),
        "traceback is not the unique recorded CUDA OOM",
    )
    if context["arm"] != "Static":
        require(
            "in class_gradients" in log
            and "torch.autograd.grad" in log
            and "in _outer_update" in log,
            "OOM is not before-feedback class gradient computation",
        )
    else:
        require("in step" in log and "in run_until" in log, "Static OOM is not a training step")
    refs = current_refs | dict(
        exit=reference(attempt / "exit/record.json"),
        worker_log=reference(log_path),
        scientific_intent=reference(last / "intent/record.json"),
        scientific_stopped=reference(last / "stopped/record.json"),
    )
    return dict(
        failed_attempt=str(attempt),
        failed_launch=dict(pid=pid, birth=birth, gpu=launch["gpu"]),
        failed_process_dead=True,
        failed_session_dead=True,
        references=refs,
        adopted_launch_chain=origins,
        adopted_protocol_evidence=origin_evidence,
        original_execution_attempt=str(original_attempt),
        wrapper_evidence=wrapper_evidence,
        outer_failure_audit=stopped.get("outer_failure_audit"),
    )


def prove_checkpoint_oom_resume(source_root, queue_root, job_key, attempt_path):
    """Run the unmodified frozen safety composition with V29 provenance checks.

    Invocation-local globals avoid mutating the frozen module or another proof
    call. The only changed failure predicate is the validated adoption chain.
    """
    namespace = dict(v28.prove_checkpoint_oom_resume.__globals__)
    namespace.update(
        {
            name: globals()[name]
            for name in (
                "source_context",
                "checkpoint_evidence",
                "shared_binding",
                "history_evidence",
                "failure_evidence",
            )
        }
    )
    original_composition = FunctionType(v28.prove_checkpoint_oom_resume.__code__, namespace)
    result = original_composition(source_root, queue_root, job_key, attempt_path)
    result.pop("id")
    result.update(
        schema="v29_safe_adopted_checkpoint_oom_resume_proof.v1",
        frozen_v28_safety_source_sha256=FROZEN_SHA["finqa_v28_checkpoint_resume.py"],
    )
    return result | {"id": digest(result)}
