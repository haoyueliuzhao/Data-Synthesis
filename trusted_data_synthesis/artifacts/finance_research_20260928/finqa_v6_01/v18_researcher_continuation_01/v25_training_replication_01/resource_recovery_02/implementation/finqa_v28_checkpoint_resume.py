"""Read-only, CPU-only OOM checkpoint proof for the fixed V25 arm jobs.

Static may restore a complete durable checkpoint. C-only/Full additionally
require an uncommitted class-gradient OOM before any feedback for that outer.
Completed earlier feedback stays in place. Generation/replay failures, partial
feedback, unknown exceptions and partial checkpoints are never retried here.
The controller separately enforces retry counts, cooldown and GPU headroom.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


h = load_module(Path(__file__).with_name("finqa_v28_resume_proof.py"), "v28_resume_helpers")
require, checked, reference, digest = h.require, h.checked, h.reference, h.digest
SCIENCE_ID = "bf2f8bfd34469400444d7597a8d9893678adbd6af296c89b0a69c5e9b5ba6d45"
OUTER_STEPS = (298, 596, 894, 1192)
ARM_NAMES = {"static": "Static", "c_only": "C-only", "full": "Full"}
STATE_FIELDS = (
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


def metadata_without_payload(path, omitted):
    """Skip indented frozen JSON payload arrays without deserializing answers."""
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "regular sealed metadata required")
    kept, skipping, sha = [], False, hashlib.sha256()
    with path.open("rb") as stream:
        for raw in stream:
            sha.update(raw)
            line = raw.decode()
            if skipping:
                if line.rstrip() in ("  ],", "  ]"):
                    kept.append(line)
                    skipping = False
                continue
            if any(line.rstrip() == f'  "{key}": [' for key in omitted):
                kept.append(line)
                skipping = True
            else:
                kept.append(line)
    require(not skipping, "unterminated sealed payload")
    value = json.loads("".join(kept))
    for key in omitted:
        value.pop(key, None)
    return value, dict(path=str(path.resolve()), sha256=sha.hexdigest(), bytes=path.stat().st_size)


def source_context(root, job_key):
    plan = checked(root / "protocol/record.json")
    require(plan["id"] == SCIENCE_ID and len(plan["jobs"]) == 24, "fixed science changed")
    match = re.fullmatch(r"replication-train-seed(137|251|389)-(static|c_only|full)", job_key)
    require(match is not None, "only registered arm jobs may checkpoint-resume")
    seed, arm_dir = int(match[1]), match[2]
    job = next((row for row in plan["jobs"] if row["key"] == job_key), None)
    require(
        job is not None
        and job["kind"] == "arm"
        and job["branch"] == "training_replication"
        and job["script"] == h.WORKER
        and job["args"] == ["train", "--seed", str(seed), "--arm", arm_dir],
        "job differs from original scientific registration",
    )
    implementation = checked(root / "implementation/record.json")
    require(implementation["id"] == plan["implementation_id"], "implementation changed")
    worker = root / "implementation" / h.WORKER
    require(
        reference(worker)["sha256"] == implementation["sha256"][h.WORKER] == h.WORKER_SHA,
        "frozen worker changed",
    )
    training = h.checked_ref(
        plan["training_registration"], root / "training_replication/registration/record.json"
    )
    runtime = Path(implementation["scientific_runtime"])
    require(str(runtime) == training["source_binding"]["source_runtime"], "runtime root changed")
    sources = {h.WORKER: reference(worker)}
    for name, sha in h.SOURCE_SHA.items():
        path = runtime / "trusted_data_synthesis/src/trusted_synthesis/finance_research" / name
        sources[name] = reference(path)
        require(sources[name]["sha256"] == sha, "frozen restore/outer runtime changed")
    module = load_module(worker, "v28_original_checkpoint_worker")
    require(
        module.checked_plan(root / "training_replication") == training,
        "complete training source binding changed",
    )
    rt = module.load_runtime()
    require(not rt.torch.cuda.is_initialized(), "proof must remain CPU-only")
    return dict(
        plan=plan,
        training=training,
        job=job,
        seed=seed,
        arm=ARM_NAMES[arm_dir],
        arm_root=root / f"training_replication/seed{seed}/arms/{arm_dir}",
        worker=worker,
        runtime=rt,
        sources=sources,
    )


def checkpoint_evidence(directory, seed, arm, rt):
    import torch

    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), "regular checkpoint required")
    metadata_ref = reference(directory / "record.json")
    metadata = json.loads((directory / "record.json").read_bytes())
    state_ref = reference(directory / "state.pt")
    require(state_ref["sha256"] == metadata["state_sha256"], "checkpoint state hash changed")
    require(
        metadata.get("checkpoint_contains_actual_model_Adam_RNG_pi") is True
        and metadata["seed"] == seed
        and metadata["arm"] == arm
        and 298 <= metadata["step"] < 1490,
        "checkpoint identity or completion changed",
    )
    require(not torch.cuda.is_initialized(), "CPU checkpoint validation required")
    state = torch.load(directory / "state.pt", map_location="cpu", weights_only=False)
    require(h.tree_digest(state) == metadata["actual_state_digest"], "state digest changed")
    require(all(key in state for key in STATE_FIELDS), "incomplete restore state")
    require(
        state["seed"] == seed
        and state["arm"] == arm
        and state["step"] == metadata["step"]
        and state["pool_id"] == metadata["pool_id"]
        and state["schedule"]["schedule_sha256"] == metadata["schedule_sha256"],
        "saved checkpoint coordinate changed",
    )
    require(
        state["rng"].keys() == {"python", "torch", "cuda"}
        and isinstance(state["rng"]["cuda"], (list, tuple))
        and len(state["rng"]["cuda"]) == 1,
        "complete one-device RNG required",
    )
    require(
        isinstance(state["rng"]["python"], tuple)
        and all(
            isinstance(value, torch.Tensor)
            and value.dtype == torch.uint8
            and value.device.type == "cpu"
            and value.ndim == 1
            and value.numel() > 0
            for value in (state["rng"]["torch"], *state["rng"]["cuda"])
        ),
        "RNG state tensors are incomplete",
    )
    require(
        len(state["parameters"]) == len(state["optimizer"]["state"]) == 112,
        "registered LoRA/Adam coordinates incomplete",
    )
    require(
        {float(row["step"]) for row in state["optimizer"]["state"].values()}
        == {float(state["step"])},
        "Adam step does not match checkpoint",
    )
    require(
        all(
            {"step", "exp_avg", "exp_avg_sq"} <= row.keys()
            for row in state["optimizer"]["state"].values()
        ),
        "Adam moments incomplete",
    )
    require(
        metadata["phase"] in {"branch", "step", "outer"}
        and directory.name == f"step{state['step']:04d}_{metadata['phase']}",
        "checkpoint directory coordinate changed",
    )
    if arm == "Static":
        require(
            state["outer_done"] == [] and metadata["phase"] != "outer",
            "Static has unexpected outer history",
        )
    else:
        require(
            state["step"] in OUTER_STEPS
            and metadata["phase"] in {"branch", "step"}
            and state["outer_done"] == [step for step in OUTER_STEPS if step < state["step"]],
            "gradient resume requires the next uncommitted scheduled outer",
        )
    require(not torch.cuda.is_initialized(), "proof unexpectedly initialized CUDA")
    return dict(
        metadata=metadata_ref,
        state=state_ref,
        actual_state_digest=metadata["actual_state_digest"],
        step=state["step"],
        phase=metadata["phase"],
        outer_done=state["outer_done"],
        component_digests={key: h.tree_digest(state[key]) for key in STATE_FIELDS},
        trainable_tensors=112,
        Adam_state_entries=112,
        cuda_initialized=False,
    )


def shared_binding(context, checkpoint):
    import torch

    shared = context["arm_root"].parents[1] / "shared/step0298_step"
    metadata = json.loads((shared / "record.json").read_bytes())
    state_ref = reference(shared / "state.pt")
    require(
        metadata["state_sha256"] == state_ref["sha256"]
        and metadata["seed"] == context["seed"]
        and metadata["arm"] == "shared"
        and metadata["step"] == 298,
        "original shared checkpoint identity changed",
    )
    state = torch.load(shared / "state.pt", map_location="cpu", weights_only=False)
    require(h.tree_digest(state) == metadata["actual_state_digest"], "shared state digest changed")
    for field in ("schedule", "execution_plan", "adapter_binding", "frozen_base_digest", "prior"):
        require(
            h.tree_digest(state[field]) == checkpoint["component_digests"][field],
            "checkpoint/shared binding differs: " + field,
        )
    current = json.loads(Path(checkpoint["metadata"]["path"]).read_bytes())
    require(current["pool_id"] == metadata["pool_id"], "checkpoint shared pool differs")
    return dict(
        metadata=reference(shared / "record.json"),
        state=state_ref,
        original_model_material_schedule_binding=True,
    )


def history_evidence(arm_root, checkpoint, rt):
    """Only sealed earlier cohorts are allowed; no new outer intent is tolerated."""
    rt.arms.no_partial_arm_feedback(arm_root)
    feedback = arm_root / "feedback"
    points = sorted(feedback.iterdir()) if feedback.exists() else []
    require(not feedback.is_symlink(), "symlinked feedback root")
    require(len(points) == len(checkpoint["outer_done"]), "new or uncommitted feedback exists")
    outer_points = {}
    refs = {}
    for step in checkpoint["outer_done"]:
        path = arm_root / f"training/step{step:04d}_outer/record.json"
        record = json.loads(path.read_bytes())
        report = record["evidence"]["feedback_report"]
        require(
            record["step"] == step
            and record["phase"] == "outer"
            and report["denominator"] == 700
            and report["all_receipts_validated"] is True,
            "earlier outer lacks completed feedback proof",
        )
        require(report["point_id"] not in outer_points, "duplicate historical feedback point")
        outer_points[report["point_id"]] = report
        refs[str(path)] = reference(path)
    seen = set()
    for point in points:
        require(point.is_dir() and not point.is_symlink(), "unexpected feedback entry")
        intent_path = point / "intent/record.json"
        intent = json.loads(intent_path.read_bytes())
        point_id = intent["point_id"]
        require(
            point_id in outer_points and point_id not in seen and intent["denominator"] == 700,
            "feedback is not a unique previously committed outer",
        )
        seen.add(point_id)
        refs[str(intent_path)] = reference(intent_path)
        for draw in (0, 1):
            path = point / f"draw{draw}/generation_seal/seal.json"
            seal = checked(path)
            require(
                seal["complete"] is True
                and seal["all_provider_calls_settled"] is True
                and seal["registered_denominator"] == 350
                and len(seal["episodes"]) == 350,
                "partial historical feedback cannot resume",
            )
            refs[str(path)] = reference(path)
            for episode in seal["episodes"]:
                episode_path = (point / f"draw{draw}" / episode["path"]).resolve()
                require(
                    episode_path.is_relative_to(point.resolve())
                    and reference(episode_path)["sha256"] == episode["sha256"],
                    "sealed historical episode missing or changed",
                )
        cohort, cohort_ref = metadata_without_payload(
            point / "cohort_seal/record.json", {"episodes"}
        )
        seal_sha = cohort.pop("seal_sha256")
        report = outer_points[point_id]
        require(
            digest(cohort) == seal_sha == report["cohort_seal_sha256"]
            and cohort["identity"]["point_id"] == point_id
            and cohort["generation_complete"] is True
            and cohort["denominator"] == 700,
            "historical cohort seal differs from committed outer",
        )
        rewards, reward_ref = metadata_without_payload(
            point / "native_rewards/record.json", {"scores"}
        )
        require(
            rewards["cohort_seal_sha256"] == seal_sha
            and len(rewards["rewards"]) == 700
            and digest(rewards["rewards"]) == report["reward_sha256"],
            "historical reward seal differs from committed outer",
        )
        refs[str(point / "cohort_seal/record.json")] = cohort_ref
        refs[str(point / "native_rewards/record.json")] = reward_ref
    require(seen == set(outer_points), "historical feedback identity set changed")
    return dict(
        completed_outer_count=len(seen),
        sealed_feedback_points=sorted(seen),
        references=refs,
        no_current_outer_feedback=True,
    )


def failure_evidence(root, queue_root, job_key, attempt, context):
    require(
        attempt.parent == queue_root / "queue/jobs" / job_key
        and re.fullmatch(r"attempt[0-9]{3,}", attempt.name),
        "foreign failed attempt path",
    )
    execution = checked(queue_root / "protocol/record.json")
    require(
        execution["scientific_protocol"]["id"] == context["plan"]["id"]
        and execution["jobs"] == context["plan"]["jobs"],
        "foreign execution protocol",
    )
    launch, ended, intent = [
        checked(attempt / f"{kind}/record.json") for kind in ("launch", "exit", "intent")
    ]
    require(
        all(
            row["protocol_id"] == execution["id"]
            and row["scientific_protocol_id"] == context["plan"]["id"]
            for row in (launch, ended, intent)
        ),
        "failed evidence protocol differs",
    )
    adopted = launch.get("adopted_existing_process") is True and "origin_launch" in launch
    require(
        launch["job"] == intent["job"] == context["job"]
        and ended["key"] == job_key
        and (ended["exit_code"] == 1 or (adopted and ended["exit_code"] is None))
        and ended["completed"] is False
        and ended["result"] is None,
        "not an observed unsuccessful scientific worker",
    )
    command = launch["command"]
    worker = str(context["worker"])
    require(command == intent["command"] and command.count(worker) == 1, "worker command changed")
    wrapper_evidence = None
    if "--worker" in command:
        require(
            command.count("--worker") == command.count("--") == 1,
            "ambiguous wrapped original command",
        )
        index = command.index("--worker")
        wrapper = Path(command[index - 1]).resolve()
        require(
            wrapper.name == "finqa_v28_memory_worker.py"
            and wrapper.parent.name == "implementation"
            and wrapper.is_relative_to(root),
            "foreign memory wrapper",
        )
        mode = launch.get("memory_mode")
        require(mode in {"high_cache", "shared_checkpointed"}, "unknown wrapper memory mode")
        separator = command.index("--")
        require(
            command[index:separator]
            == ["--worker", worker, "--receipt-dir", command[index + 3], "--memory-mode", mode],
            "wrapped CLI differs",
        )
        receipt_dir = Path(command[index + 3]).resolve()
        manifest = checked(wrapper.parent / "record.json")
        wrapper_protocol = checked(wrapper.parent.parent / "protocol/record.json")
        require(
            wrapper_protocol["implementation_id"] == manifest["id"]
            and wrapper_protocol["scientific_protocol"]["id"] == context["plan"]["id"]
            and reference(wrapper)["sha256"] == manifest["sha256"][wrapper.name],
            "frozen memory wrapper binding changed",
        )
        suffix = command[separator + 1 :]
        receipt = checked(receipt_dir / "wrapper_intent.json")
        require(
            receipt["pid"] == launch["pid"]
            and receipt["memory_mode"] == mode
            and receipt["original_command"] == [worker, *suffix]
            and receipt["scientific_arguments_changed"] is False
            and receipt["source_binding"]["scientific_protocol_id"] == context["plan"]["id"]
            and receipt["source_binding"]["sources"][h.WORKER]["sha256"] == h.WORKER_SHA,
            "wrapper intent differs from original scientific CLI",
        )
        wrapper_evidence = dict(
            source=reference(wrapper), intent=reference(receipt_dir / "wrapper_intent.json")
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
    arm = context["arm_root"]
    scientific_attempts = sorted((arm / "launch_attempts").glob("attempt*"))
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
    original_launch, original_attempt, origins = launch, attempt, []
    seen = {str(attempt / "launch/record.json")}
    while "origin_launch" in original_launch:
        origin = original_launch["origin_launch"]
        path = Path(origin["path"]).resolve()
        require(
            path.is_relative_to(root)
            and str(path) not in seen
            and path.name == "record.json"
            and path.parent.name == "launch",
            "foreign or cyclic adopted launch chain",
        )
        seen.add(str(path))
        original_launch = h.checked_ref(origin, path)
        require(
            all(
                original_launch[field] == launch[field]
                for field in ("job", "pid", "birth", "gpu", "command")
            )
            and original_launch["scientific_protocol_id"] == context["plan"]["id"],
            "adopted worker identity changed",
        )
        origins.append(reference(path))
        original_attempt = path.parents[1]
    log_path = original_attempt / "worker.log"
    if wrapper_evidence is not None:
        require(
            receipt_dir == original_attempt / "memory_reservation",
            "foreign wrapper receipt directory",
        )
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
    refs = {
        kind: reference(attempt / f"{kind}/record.json") for kind in ("launch", "exit", "intent")
    }
    refs.update(
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
        wrapper_evidence=wrapper_evidence,
        outer_failure_audit=stopped.get("outer_failure_audit"),
    )


def prove_checkpoint_oom_resume(source_root, queue_root, job_key, attempt_path):
    """Return deterministic proof, with no files/signals/model/GPU/API actions.

    Re-run immediately before --resume and require the same proof id. Proof
    intentionally changes once another worker has appended a scientific intent.
    """
    root, queue_root, attempt = map(
        lambda value: Path(value).resolve(), (source_root, queue_root, attempt_path)
    )
    require(queue_root.is_relative_to(root) and queue_root != root, "foreign recovery queue")
    context = source_context(root, job_key)
    require(not Path(context["job"]["result"]).exists(), "completed arm cannot resume")
    failure = failure_evidence(root, queue_root, job_key, attempt, context)
    rt, arm = context["runtime"], context["arm_root"]
    latest = rt.launcher.latest_checkpoint(arm / "training")
    require(latest is not None, "no durable same-run checkpoint")
    checkpoint = checkpoint_evidence(latest, context["seed"], context["arm"], rt)
    binding = shared_binding(context, checkpoint)
    if context["arm"] != "Static" and checkpoint["step"] == 298:
        audit_ref = failure["outer_failure_audit"]
        require(isinstance(audit_ref, dict), "first outer requires its frozen failure audit")
        audit_path = Path(audit_ref["path"]).resolve()
        require(
            audit_path.is_relative_to(arm / "training/outer_attempts/step0298"),
            "foreign outer audit",
        )
        audit = h.checked_ref(audit_ref, audit_path)
        require(
            audit["step"] == checkpoint["step"]
            and audit["last_phase"] == "full_class_gradients"
            and audit["error_type"] == "OutOfMemoryError"
            and audit["failure_kind"] == "resource_OOM"
            and audit["feedback_artifacts"] == {}
            and audit["retained_incomplete_feedback"] == []
            and audit["outer_commit_record_exists"] is False,
            "first outer audit is not safe gradient OOM",
        )
    feedback = history_evidence(arm, checkpoint, rt)
    require(
        rt.launcher.latest_checkpoint(arm / "training") == latest,
        "latest checkpoint changed during proof",
    )
    require(
        reference(Path(latest) / "state.pt") == checkpoint["state"],
        "checkpoint changed during proof",
    )
    require(
        failure_evidence(root, queue_root, job_key, attempt, context) == failure,
        "failure evidence changed during proof",
    )
    require(history_evidence(arm, checkpoint, rt) == feedback, "feedback changed during proof")
    value = dict(
        schema="v28_safe_checkpoint_oom_resume_proof.v1",
        eligible=True,
        job_key=job_key,
        scientific_protocol_id=context["plan"]["id"],
        training_protocol_id=context["training"]["id"],
        resume_checkpoint=str(latest),
        resume_flag_required=True,
        **failure,
        checkpoint_evidence=checkpoint,
        historical_feedback=feedback,
        shared_checkpoint_binding=binding,
        source_binding=context["sources"],
        feedback_resampling=False,
        scientific_hyperparameters_changed=False,
        cpu_only_no_model_initialization=True,
        uncommitted_computation_will_be_repeated=True,
        optimizer_updates_lost_since_checkpoint="uncommitted_only",
        retry_budget_enforced_by_controller=True,
        does_not_guarantee_next_attempt_avoids_OOM=True,
    )
    return value | {"id": digest(value)}
