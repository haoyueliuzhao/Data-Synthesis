"""Read-only inheritance of the six accepted V37 first-point stages.

This module never imports Torch, opens a Tensor, samples, or changes a parent
record.  A new episode writes an explicit alias and new attempt directories;
the original scientific context and payload IDs remain unchanged.  Actual
Tensor content validation remains the original worker's responsibility.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

GIB = 1024**3
SHARDS = tuple(f"shard{i:02d}" for i in range(4))
INHERITED_STAGES = (*SHARDS, "virtual_point", "replay_R3")
CURRENT_STAGES = ("distribution", "train")
FIRST_CONTEXT = Path("contexts/seed137/c_only/step1192_outer")
SCHEMA = "v38_first_point_stage_inheritance.v1"
ALIAS_SCHEMA = "v38_parent_context_alias.v1"
PARENT_FILES = (
    "finqa_v37_controller.py",
    "finqa_v37_worker.py",
    "finqa_v37_task_cache.py",
    "finqa_v37_training.py",
    "finqa_v37_evaluation.py",
)
EXPECTED_PROGRESS = dict(
    completed_optimizer_updates=5812,
    remaining_optimizer_updates=5810,
    completed_outer_updates=9,
    remaining_outer_updates=15,
    reused_sealed_feedback_episodes=2100,
    first_sampling_feedback_episodes=8400,
    remaining_endpoint_answers=8029,
    total_endpoint_answers=10323,
)


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def sha(path):
    """Hash bounded metadata/source files only, never scientific Tensor payloads."""
    path = Path(path)
    require(path.suffix in {".json", ".py", ".txt", ".md"}, "metadata/source hash only")
    require(path.stat().st_size <= 64 * 1024**2, "metadata exceeds bounded read size")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(path):
    path = Path(path)
    sha(path)  # Also enforce the bounded metadata-only read contract.
    value = json.loads(path.read_bytes())
    require(
        isinstance(value, dict)
        and value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "immutable record identity changed: " + str(path),
    )
    return value


def file_ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha(path))


def entry(path):
    return {**file_ref(path), "id": checked(path)["id"]}


def read_ref(reference):
    require(isinstance(reference, dict), "explicit metadata reference required")
    path = Path(reference["path"])
    require(path.is_absolute() and sha(path) == reference["sha256"], "source bytes changed")
    value = json.loads(path.read_bytes())
    if "id" in reference:
        require(checked(path)["id"] == reference["id"], "source record identity changed")
    return value


def _verify_refs(value, *, deferred=None):
    if isinstance(value, dict):
        if {"path", "sha256"} <= value.keys():
            path = Path(value["path"])
            if deferred is not None and path.stat().st_size > 64 * 1024**2:
                require(
                    path.suffix == ".json", "only large feedback JSON validation may be deferred"
                )
                item = dict(
                    reference=dict(value),
                    file_identity=_file_identity(path),
                    content_hash_verified_here=False,
                    required_verification="original_same_point_worker_before_use",
                )
                if item not in deferred:
                    deferred.append(item)
                return
            if Path(value["path"]).suffix == ".json":
                read_ref(value)
            else:
                require(
                    "id" not in value and sha(value["path"]) == value["sha256"],
                    "bound source bytes changed",
                )
        else:
            for item in value.values():
                _verify_refs(item, deferred=deferred)
    elif isinstance(value, list):
        for item in value:
            _verify_refs(item, deferred=deferred)


def publish(path, body):
    path = Path(path)
    require("id" not in body and not path.exists(), "refuse inheritance record overwrite")
    value = {**body, "id": digest(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return value


def _file_identity(path, *, size=None):
    """Record existence/identity, without opening a potentially large Tensor."""
    path = Path(path)
    require(path.is_absolute() and path == path.resolve(), "redirected inherited file")
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), "inherited payload must be a regular file")
    require(size is None or info.st_size == size, "persisted payload length changed")
    return dict(
        path=str(path),
        device=info.st_dev,
        inode=info.st_ino,
        bytes=info.st_size,
        mtime_ns=info.st_mtime_ns,
        ctime_ns=info.st_ctime_ns,
    )


def _birth(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return None
    return None if fields[0] == "Z" else fields[19]


def _stopped(launch):
    require(type(launch["pid"]) is int and launch["birth"] is not None, "process identity missing")
    require(_birth(launch["pid"]) != str(launch["birth"]), "parent process is still live")


def _time(value):
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, "inherited time must include a timezone")
    return parsed.timestamp()


def _finite_nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _check_resources(resources, stage):
    """The original V37 observation and summary gates, using metadata only."""
    cap, reserve, rss = 76 * GIB, 2 * GIB, (160 if stage in SHARDS else 192) * GIB
    require(
        resources["all_gates_passed"] is True
        and resources["limits_unchanged"] is True
        and resources["maximum_allocated_bytes"] == cap
        and resources["minimum_device_free_bytes"] == reserve
        and resources["peak_resets_before_model_load"] == 1
        and resources["peak_resets_after_model_loading_begins"] == 0
        and resources["helper_peak_reset_calls"] == 0,
        "parent lifetime resource contract failed",
    )
    observations = resources["observations"]
    require(
        observations
        and observations[-1]["label"] == "model_released.after_cleanup"
        and any(row["label"] == "after_model_load.after_cleanup" for row in observations),
        "parent model load/release boundaries missing",
    )
    for row in observations:
        require(
            all(
                row[key] is True
                for key in ("passed", "allocated_pass", "free_pass", "deadline_pass")
            )
            and row["stop_requested"] is False
            and row["limits"]
            == dict(allocated_memory_limit_bytes=cap, free_memory_reserve_bytes=reserve),
            "parent resource observation failed",
        )
        require(
            all(
                type(row[key]) is int and row[key] >= 0
                for key in (
                    "allocated_bytes",
                    "reserved_bytes",
                    "peak_allocated_bytes",
                    "peak_reserved_bytes",
                    "free_bytes",
                    "total_bytes",
                )
            )
            and row["allocated_bytes"] <= row["peak_allocated_bytes"] <= cap
            and row["allocated_bytes"] <= row["reserved_bytes"] <= row["peak_reserved_bytes"]
            and row["peak_allocated_bytes"] <= row["peak_reserved_bytes"]
            and row["free_bytes"] <= row["total_bytes"]
            and (not row["boundary"] or row["free_bytes"] >= reserve),
            "parent GPU resource values violate original limits",
        )
        host = row["host"]
        require(
            all(host[key] is True for key in ("passed", "rss_pass", "available_pass"))
            and host["rss_limit_bytes"] == rss
            and host["available_reserve_bytes"] == 96 * GIB
            and 0 <= host["rss_bytes"] <= host["peak_rss_bytes"] <= rss
            and host["available_bytes"] >= 96 * GIB,
            "parent host resource values violate original limits",
        )
    boundaries = [row for row in observations if row["boundary"]]
    host = resources["host"]
    require(
        boundaries
        and resources["observed_peak_allocated_bytes"]
        == max(row["peak_allocated_bytes"] for row in observations)
        and resources["observed_minimum_boundary_free_bytes"]
        == min(row["free_bytes"] for row in boundaries)
        and host["all_passed"] is True
        and host["rss_limit_bytes"] == rss
        and host["available_reserve_bytes"] == 96 * GIB
        and host["max_observed_peak_rss_bytes"]
        == max(row["host"]["peak_rss_bytes"] for row in observations)
        and host["min_observed_available_bytes"]
        == min(row["host"]["available_bytes"] for row in observations),
        "parent resource summary contradicts its observations",
    )


def _check_stage(directory, protocol, context, stage, task_plan):
    result = checked(directory / "result/record.json")
    exited = checked(directory / "exit/record.json")
    launch = checked(directory / "launch/record.json")
    require(
        all(row["protocol_id"] == protocol["id"] for row in (result, exited, launch))
        and all(row["context_id"] == context["id"] for row in (result, exited, launch))
        and all(row["stage"] == stage for row in (result, exited, launch))
        and result["status"] == "COMPLETE"
        and result["model_released"] is True
        and result["model_optimizer_rng_buffers_unchanged"] is True
        and exited["returncode"] == 0
        and exited["stop_requested"] is False,
        "parent stage is incomplete, failed, unexited or from another point",
    )
    require(
        result["gpu_index"] in (3, 4, 5, 7)
        and result["gpu_index"] == launch["gpu_index"]
        and result["gpu_uuid"]
        == launch["gpu_uuid"]
        == protocol["gpu_uuids"][str(result["gpu_index"])],
        "parent stage GPU binding changed",
    )
    require(
        all(
            type(result[key]) is int and result[key] == 0
            for key in ("API_calls", "new_sampling_calls", "scoring_calls", "optimizer_steps")
        )
        and _finite_nonnegative(exited["elapsed_worker_wall_seconds"]),
        "parent stage scientific dose or elapsed time changed",
    )
    _stopped(launch)
    _check_resources(result["resources"], stage)
    if stage in SHARDS:
        tasks = task_plan["assignments"][SHARDS.index(stage)]["task_ids"]
        require(
            result["task_ids"] == tasks
            and len(tasks) == result["task_count"] == 186
            and result["class_task_calls"] == 186
            and result["reused_task_ids"] == []
            and result["replayed_responses"] == 0,
            "parent first-point task coverage changed",
        )
    else:
        require(
            result["denominator"] == 700 and result["response_count"] == 527,
            "parent response count or fixed denominator changed",
        )
    if stage == "virtual_point":
        require(
            result["feedback_mode"] == "sealed_existing"
            and result["point_id"] == context["feedback"]["expected_point_id"]
            and result["original_sealed_point_matched"] is True
            and result["new_feedback_episodes"] == result["replayed_responses"] == 0,
            "parent virtual point is not the original sealed-feedback point",
        )
    if stage == "replay_R3":
        require(
            result["complete_replay"] is True
            and result["current_point_only"] is True
            and result["replayed_responses"] == 527
            and result["restored_completed_responses"] == 0,
            "parent final replay is incomplete or from a different point",
        )
    return result, exited, launch


def _payload(directory, context, phase):
    reference = entry(directory / "payload/record.json")
    value = read_ref(reference)
    require(
        value["context_id"] == context["id"]
        and value["phase"] == phase
        and value["actual_tensors_saved"] is True
        and type(value["state_bytes"]) is int
        and value["state_bytes"] > 0,
        "parent payload is not the actual bound phase value",
    )
    return reference, _file_identity(directory / "payload/state.pt", size=value["state_bytes"])


def inspect_parent_recovery(newroot, parentroot):
    """Return validated inheritance metadata without writing or opening Tensors."""
    root, parent = Path(newroot).resolve(), Path(parentroot).resolve()
    require(root == parent / "recovery_01", "only the separately authorized first recovery root")
    target, origin = root / FIRST_CONTEXT, parent / FIRST_CONTEXT
    require(not (root / "inheritance/record.json").exists(), "inheritance already sealed")
    require(not (target / "context/record.json").exists(), "recovery context already exists")
    protocol = checked(parent / "protocol/record.json")
    implementation = checked(parent / "implementation/record.json")
    require(
        protocol["schema"] == "v37_original_B_controlled_production_protocol.v1"
        and protocol["initial_progress"] == EXPECTED_PROGRESS
        and protocol["first_gate"]
        == dict(seed=137, arm="C-only", step=1192, next_actual_sft_step=1193)
        and protocol["implementation_id"] == implementation["id"]
        and implementation["schema"] == "v37_committed_production_implementation.v1"
        and implementation["committed_files"] == list(PARENT_FILES),
        "parent scientific protocol or implementation binding changed",
    )
    for name, expected in implementation["sha256"].items():
        require(Path(name).name == name and name.endswith(".py"), "unsafe source member")
        require(sha(parent / "implementation" / name) == expected, "parent source bytes changed")
    require(set(PARENT_FILES) <= implementation["sha256"].keys(), "parent source members missing")
    for key in ("original_mathematical_implementation", "lifecycle_implementation"):
        if key in implementation:
            read_ref(implementation[key])
    queue_path = parent / "queue/status.json"
    queue = json.loads(queue_path.read_bytes())
    require(
        queue["phase"] == "STOPPED_FAILURE_NO_RETRY"
        and not queue["active_children"]
        and queue["protocol_id"] == protocol["id"]
        and queue["pilot_accepted"] is False
        and queue["accepted_new_optimizer_updates"] == queue["accepted_new_outer_updates"] == 0,
        "parent queue is live, accepted or no longer the failed first point",
    )
    _stopped(checked(parent / "launch_01/record.json"))
    failure = checked(parent / "failure/record.json")
    require(failure["protocol_id"] == protocol["id"], "parent failure protocol changed")
    context = checked(origin / "context/record.json")
    require(
        context["schema"] == "v37_actual_production_context.v1"
        and context["run_root"] == context["outer_root"] == str(origin)
        and (context["seed"], context["arm"], context["step"]) == (137, "C-only", 1192)
        and context["due_outer"] is True
        and context["training_stop_step"] == 1193
        and context["branch"]["contribution_only"] is True
        and context["branch"]["b_N"] == 0
        and context["feedback"]["mode"] == "sealed_existing"
        and context["feedback"]["denominator"] == 700
        and context["execution_binding"]["protocol"] == entry(parent / "protocol/record.json")
        and context["execution_binding"]["implementation_id"] == implementation["id"],
        "parent actual scientific context changed",
    )
    _verify_refs(context["sources"])
    _verify_refs(context["execution_binding"])
    deferred_feedback = []
    _verify_refs(context["feedback"], deferred=deferred_feedback)
    state_record = read_ref(context["checkpoint"]["record"])
    require(
        (state_record["seed"], state_record["arm"], state_record["step"], state_record["phase"])
        == (137, "C-only", 1192, "step")
        and state_record["state_sha256"] == context["checkpoint"]["state"]["sha256"],
        "parent checkpoint reference changed",
    )
    checkpoint = Path(context["checkpoint"]["path"])
    require(
        checkpoint.name == "step1192_step"
        and not (checkpoint.parent / "step1192_outer").exists()
        and not (checkpoint.parent / "step1193_step").exists()
        and not (origin / "train").exists()
        and not (parent / "pilot_acceptance").exists(),
        "first outer/SFT has already started or committed",
    )
    checkpoint_identity = _file_identity(Path(context["checkpoint"]["state"]["path"]))
    task_plan = read_ref(context["task_plan"])
    require(
        len(task_plan["tasks"]) == len(task_plan["task_ids"]) == 744,
        "parent task plan does not cover exactly 744 tasks",
    )
    cache = Path(context["task_cache_root"])
    require(cache == origin / "task_cache", "parent task cache path changed")
    inventory = []
    for index in range(744):
        for name in ("record.json", "gradient.pt"):
            inventory.append(_file_identity(cache / f"task{index:04d}" / name))
    stages, results, launches, exits = {}, {}, [], []
    for stage in INHERITED_STAGES:
        directory = origin / stage
        result, exited, launch = _check_stage(directory, protocol, context, stage, task_plan)
        results[stage] = result
        launches.append(launch)
        exits.append(exited)
        binding = dict(
            protocol_scope="parent",
            protocol_id=protocol["id"],
            directory=str(directory),
            result=entry(directory / "result/record.json"),
            exit=entry(directory / "exit/record.json"),
            launch=entry(directory / "launch/record.json"),
        )
        if stage in ("virtual_point", "replay_R3"):
            binding["payload"], binding["tensor_identity"] = _payload(directory, context, stage)
            require(result["payload"] == binding["payload"], "accepted parent payload ref changed")
        stages[stage] = binding
    require(
        sum(results[s]["new_completed_rows"] for s in SHARDS) == 4974,
        "parent class-gradient row coverage changed",
    )
    final_path = origin / "replay_R3/checkpoints/response000527/record.json"
    final = checked(final_path)
    require(
        results["replay_R3"]["final_checkpoint"] == entry(final_path)
        and final["cursor"] == 527
        and final["full_replay_complete"] is True
        and final["response_prefix_complete"] is True
        and final["no_feedback_generation"] is True
        and final["optimizer_steps_performed"] == 0
        and final["binding"]["denominator"] == 700
        and final["binding"]["response_count"] == 527
        and final["binding"]["point_id"] == context["feedback"]["expected_point_id"],
        "parent final response checkpoint binding changed",
    )
    final_tensor = _file_identity(final_path.with_name("state.pt"))
    failed_dir = origin / "distribution"
    failed = checked(failed_dir / "failure/record.json")
    failed_exit = checked(failed_dir / "exit/record.json")
    failed_launch = checked(failed_dir / "launch/record.json")
    require(
        all(
            x["protocol_id"] == protocol["id"]
            and x["context_id"] == context["id"]
            and x["stage"] == "distribution"
            for x in (failed, failed_exit, failed_launch)
        )
        and failed["error"] == "GPU is not fully idle or UUID changed"
        and failed["resources"] is None
        and failed["telemetry"] is None
        and failed_exit["returncode"] != 0
        and not (failed_dir / "payload").exists()
        and not (failed_dir / "result").exists(),
        "parent distribution did not stop at the audited pre-CUDA boundary",
    )
    _stopped(failed_launch)
    progress = checked(parent / "actual_final_progress/record.json")
    require(
        progress["remaining_physical_updates"] == 5810
        and progress["remaining_outers"] == 15
        and progress["pending_sealed_feedback_episodes"] == 2100
        and progress["future_first_sampling_feedback_episodes"] == 8400
        and progress["future_first_sampling_outers"] == 12
        and progress["completed_physical_updates"] == 5812
        and progress["completed_outers"] == 9
        and progress["endpoint_scores_or_answers_read"] is False,
        "remaining original matrix budget changed",
    )
    require(
        {(p["seed"], p["arm"], p["step"]) for p in progress["pending_sealed_outers"]}
        == {(137, "C-only", 1192), (137, "Full", 1192), (251, "C-only", 894)},
        "the three same-point sealed feedback cohorts changed",
    )
    snapshot_path = origin / "queue/status.json"
    snapshot = json.loads(snapshot_path.read_bytes())
    failed_elapsed = failed_exit["elapsed_worker_wall_seconds"]
    require(
        snapshot["context_id"] == context["id"]
        and snapshot["protocol_id"] == protocol["id"]
        and set(snapshot["completed_stages"]) == set(INHERITED_STAGES)
        and all(
            _finite_nonnegative(v)
            for v in (
                snapshot["compute_seconds"],
                failed_elapsed,
                queue["global_external_resource_wait_seconds"],
            )
        ),
        "parent final timing snapshot is not the audited failed context",
    )
    first_at = min(_time(row["at"]) for row in launches)
    last_at = max(_time(failure["at"]), _time(failed_exit["at"]))
    inherited_compute = math.ceil(
        max(last_at - first_at, snapshot["compute_seconds"] + failed_elapsed)
    )
    inherited_distribution = math.ceil(failed_elapsed)
    inherited_wait = math.ceil(queue["global_external_resource_wait_seconds"] + failed_elapsed)
    require(
        inherited_compute < protocol["outer_compute_budget_seconds"]
        and inherited_distribution < protocol["stage_limits_seconds"]["distribution"]
        and inherited_wait < protocol["resource_wait_budget_seconds"],
        "original remaining resource/time budget is exhausted",
    )
    for stage in CURRENT_STAGES:
        stages[stage] = dict(protocol_scope="current", directory=str(target / stage))
    original_context = entry(origin / "context/record.json")
    return dict(
        schema=SCHEMA,
        at=datetime.now(timezone.utc).isoformat(),
        new_root=str(root),
        parent_root=str(parent),
        original_context=original_context,
        original_context_id=context["id"],
        origin_context_directory=str(origin),
        new_context_directory=str(target),
        parent_protocol=entry(parent / "protocol/record.json"),
        parent_implementation=entry(parent / "implementation/record.json"),
        parent_failure=entry(parent / "failure/record.json"),
        parent_queue=file_ref(queue_path),
        parent_context_snapshot=file_ref(snapshot_path),
        parent_final_progress=entry(parent / "actual_final_progress/record.json"),
        failed_distribution=dict(
            launch=entry(failed_dir / "launch/record.json"),
            failure=entry(failed_dir / "failure/record.json"),
            exit=entry(failed_dir / "exit/record.json"),
        ),
        stage_bindings=stages,
        checkpoint_tensor_identity=checkpoint_identity,
        task_plan=context["task_plan"],
        task_cache_root=str(cache),
        task_cache_inventory=dict(
            tasks=744,
            records=744,
            tensors=744,
            rows=4974,
            metadata_digest=digest(inventory),
            tensor_contents_read=False,
        ),
        final_response_checkpoint=entry(final_path),
        final_response_tensor_identity=final_tensor,
        inherited_compute_seconds=inherited_compute,
        inherited_distribution_seconds=inherited_distribution,
        inherited_resource_wait_seconds=inherited_wait,
        timing_accounting=dict(
            first_parent_launch_epoch=first_at,
            parent_failure_envelope_end_epoch=last_at,
            last_context_compute_snapshot_seconds=snapshot["compute_seconds"],
            failed_distribution_worker_seconds=failed_elapsed,
            compute_rule="ceil(max(wall_envelope, snapshot_plus_failed_worker))",
            resource_wait_rule="ceil(parent_wait_plus_failed_admission_worker)",
            conservative_overcount_allowed=True,
            budgets_reset_or_enlarged=False,
        ),
        remaining_scientific_budget=dict(EXPECTED_PROGRESS),
        deferred_feedback_content_verification=deferred_feedback,
        original_context_rewritten=False,
        parent_failure_reclassified=False,
        inherited_stage_results_fabricated=False,
        tensor_content_verification_deferred_to_worker=True,
        new_sampling_calls=0,
        replayed_responses=0,
        optimizer_updates=0,
    )


def initialize_parent_recovery(newroot, parentroot):
    """Seal metadata-only inheritance once; never rewrite or execute the parent."""
    root = Path(newroot).resolve()
    body = inspect_parent_recovery(root, parentroot)
    value = publish(root / "inheritance/record.json", body)
    target = Path(value["new_context_directory"])
    publish(
        target / "context/record.json",
        dict(
            schema=ALIAS_SCHEMA,
            new_context_directory=str(target),
            original_context=value["original_context"],
            original_context_id=value["original_context_id"],
            origin_context_directory=value["origin_context_directory"],
            inheritance=entry(root / "inheritance/record.json"),
            original_context_rewritten=False,
            actual_scientific_context_copied=False,
        ),
    )
    return value


def _inheritance(plan):
    value = read_ref(plan["inheritance"])
    require(
        value["schema"] == SCHEMA and value["new_root"] == str(Path(plan["output_root"]).resolve()),
        "recovery inheritance belongs to another episode",
    )
    require(
        set(value["stage_bindings"]) == set((*INHERITED_STAGES, *CURRENT_STAGES)),
        "recovery stage binding set changed",
    )
    return value


def resolve_origin_context(new_context_dir, newplan):
    """Return the unchanged parent coordinate for the alias, otherwise the new one."""
    directory = Path(new_context_dir).resolve()
    inherited = _inheritance(newplan)
    require(
        directory.is_relative_to(Path(newplan["output_root"]).resolve() / "contexts"),
        "context is outside the registered recovery episode",
    )
    value = checked(directory / "context/record.json")
    if directory == Path(inherited["new_context_directory"]):
        require(
            value["schema"] == ALIAS_SCHEMA
            and value["new_context_directory"] == str(directory)
            and value["inheritance"] == newplan["inheritance"]
            and value["original_context"] == inherited["original_context"]
            and value["original_context_id"] == inherited["original_context_id"]
            and value["origin_context_directory"] == inherited["origin_context_directory"],
            "first-point alias binding changed",
        )
        source = read_ref(inherited["original_context"])
        require(source["id"] == value["original_context_id"], "original context identity changed")
        return Path(inherited["origin_context_directory"])
    require(
        value["schema"] == "v37_actual_production_context.v1"
        and value["run_root"] == value["outer_root"] == str(directory),
        "future context must own its actual new coordinate",
    )
    return directory


def stage_directory(newctx, plan, stage):
    """Resolve only the declared stage storage; payload IDs are never relabeled."""
    require(stage in (*INHERITED_STAGES, *CURRENT_STAGES), "unknown production stage")
    directory = Path(newctx).resolve()
    origin = resolve_origin_context(directory, plan)
    if origin == directory:
        return directory / stage
    inherited = _inheritance(plan)
    binding = inherited["stage_bindings"][stage]
    expected = (origin if stage in INHERITED_STAGES else directory) / stage
    expected_scope = "parent" if stage in INHERITED_STAGES else "current"
    require(
        binding["directory"] == str(expected) and binding["protocol_scope"] == expected_scope,
        "stage storage or ownership differs from explicit inheritance",
    )
    return expected


def require_upstream(newctx, context, plan, stage, control):
    """Admit original results/exit records under their actual protocol owner."""
    directory = Path(newctx).resolve()
    origin = resolve_origin_context(directory, plan)
    inherited = _inheritance(plan)
    require(context == checked(origin / "context/record.json"), "actual context was relabeled")
    if origin != directory:
        require(stage in CURRENT_STAGES, "completed inherited stage must not be rerun")
    required = {
        "virtual_point": SHARDS,
        "replay_R3": ("virtual_point",),
        "distribution": INHERITED_STAGES,
        "train": ("distribution",) if context["due_outer"] else (),
    }.get(stage, ())
    task_plan = read_ref(context["task_plan"]) if context.get("due_outer") else None
    for previous in required:
        source = stage_directory(directory, plan, previous)
        if origin != directory and previous in INHERITED_STAGES:
            binding = inherited["stage_bindings"][previous]
            owner = read_ref(inherited["parent_protocol"])
            require(binding["protocol_id"] == owner["id"], "parent stage protocol changed")
            result, exited = read_ref(binding["result"]), read_ref(binding["exit"])
            require(
                binding["result"] == entry(source / "result/record.json")
                and binding["exit"] == entry(source / "exit/record.json"),
                "parent stage reference points outside its bound directory",
            )
        else:
            owner = plan
            result, exited = (
                checked(source / "result/record.json"),
                checked(source / "exit/record.json"),
            )
        require(
            result["protocol_id"] == exited["protocol_id"] == owner["id"]
            and result["context_id"] == exited["context_id"] == context["id"]
            and result["stage"] == exited["stage"] == previous
            and result["status"] == "COMPLETE"
            and result["model_released"] is True
            and result["resources"]["all_gates_passed"] is True
            and exited["returncode"] == 0,
            "upstream stage is failed, unexited or from another actual protocol/point",
        )
        control.check_result(owner, previous, result, task_plan)
        if previous in ("virtual_point", "replay_R3", "distribution"):
            reference, _identity = _payload(source, context, previous)
            require(result["payload"] == reference, "upstream actual payload reference changed")
            if origin != directory and previous in INHERITED_STAGES:
                require(
                    inherited["stage_bindings"][previous]["payload"] == reference,
                    "inherited payload binding changed",
                )
