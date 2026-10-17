"""One explicitly authorized continuation of the saved Full389 response prefix.

V38 and the unsuccessful V39 handoff remain failed historical episodes. Only
the original response000261 checkpoint may resume; its stage remains a failed
parent stage and a new current-protocol attempt, never a fabricated completion.
All other inherited stages require accepted results and actual zero exits.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import finqa_v39_inheritance as base

old = base.old
require, checked, entry, read_ref = old.require, old.checked, old.entry, old.read_ref
publish, file_ref, digest = old.publish, old.file_ref, old.digest
SHARDS, STAGES, ARM_KEYS, SEEDS = base.SHARDS, base.STAGES, base.ARM_KEYS, base.SEEDS
SCHEMA = "v40_explicit_saved_response_prefix_recovery.v1"
ALIAS_SCHEMA = "v40_parent_context_alias.v1"
PARENT_PROTOCOL_ID = "28a3d931f15acc5240a07da7c126c42418c4ed50ab665811d072d1d290706462"
REPLAY_COORDINATE = (389, "Full", 298)
REPLAY_RELATIVE = Path("contexts/seed389/full/step0298_outer")
REPLAY_CURSOR, REPLAY_TOTAL = 261, 447
PARTIAL_CLASS_COORDINATE = (251, "C-only", 1192)
PARTIAL_CLASS_AUTHORIZATION = dict(
    schema="v40_explicit_C251_1192_class_completion_authorization.v1",
    seed=251,
    arm="C-only",
    step=1192,
    inherited_shards=["shard02"],
    remaining_shards=["shard00", "shard01", "shard03"],
    inherited_task_count=186,
    remaining_task_count=558,
    window_seconds=14400,
    deadline_rule="first_remaining_shard_dispatch_plus_14400_seconds",
    original_phase_deadline_extended=True,
    outer_compute_budget_reset=False,
    global_resource_wait_budget_reset=False,
    completed_tasks_recomputed=False,
    parent_cache_modified=False,
    automatic_retry=False,
)


def _partial_class_authority(root, authorization_record=None):
    reference = (
        entry(Path(root) / "authorization/record.json")
        if authorization_record is None
        else authorization_record
    )
    if not isinstance(reference, dict):
        reference = entry(reference)
    authority = read_ref(reference)
    require(
        authority.get("partial_class_recovery") == PARTIAL_CLASS_AUTHORIZATION,
        "explicit 186 inherited/558 new task and four-hour class exception authority required",
    )
    return reference


def inspect_task_cache_overlay(directory, target, context, task_plan, bindings, authority):
    """Seal exactly the parent 186 tasks and the disjoint 558 new tasks."""
    directory, target = Path(directory), Path(target)
    require(
        (context["seed"], context["arm"], context["step"]) == PARTIAL_CLASS_COORDINATE
        and context["due_outer"] is True
        and context["branch"]["contribution_only"] is True
        and context["branch"]["b_N"] == 0
        and set(bindings) == {"shard02"}
        and bindings["shard02"]["protocol_scope"] == "parent",
        "only the authorized C251/1192 completed shard02 may use a partial-class overlay",
    )
    task_ids = task_plan["task_ids"]
    tasks = {row["task_id"]: row for row in task_plan["tasks"]}
    require(
        len(task_ids) == len(tasks) == 744
        and list(tasks) == task_ids
        and [row["index"] for row in tasks.values()] == list(range(744))
        and len(task_plan["assignments"]) == 4
        and task_plan["parameter_spec"] == context["parameter_spec"],
        "complete task plan/order/parameter binding changed",
    )
    assignments = task_plan["assignments"]
    flattened = [task for row in assignments for task in row["task_ids"]]
    require(
        len(flattened) == len(set(flattened)) == 744
        and set(flattened) == set(task_ids)
        and all(len(row["task_ids"]) == 186 for row in assignments)
        and all(
            tasks[task]["shard"] == index
            for index, row in enumerate(assignments)
            for task in row["task_ids"]
        ),
        "original four task partitions are not disjoint and complete",
    )
    parent_ids = list(assignments[2]["task_ids"])
    parent_set = set(parent_ids)
    local_ids = [task for task in task_ids if task not in parent_set]
    require(
        len(parent_ids) == 186
        and len(local_ids) == 558
        and parent_set.isdisjoint(local_ids)
        and parent_set | set(local_ids) == set(task_ids)
        and read_ref(bindings["shard02"]["result"])["task_ids"] == parent_ids,
        "186 inherited/558 new task partition changed",
    )
    cache = Path(context["task_cache_root"])
    require(
        cache == directory / "task_cache" and cache == cache.resolve(),
        "original partial cache root changed",
    )
    expected_dirs = {f"task{tasks[task]['index']:04d}" for task in parent_ids}
    require(
        {path.name for path in cache.iterdir()} == expected_dirs,
        "parent partial cache contains tasks outside the accepted shard02",
    )
    binding_sha = digest(context["task_binding"])
    require(binding_sha == context["math_context_id"], "original task-gradient binding changed")
    records = []
    for task in parent_ids:
        path = cache / f"task{tasks[task]['index']:04d}"
        require(
            path == path.resolve()
            and {child.name for child in path.iterdir()} == {"record.json", "gradient.pt"},
            "inherited complete task directory is redirected or incomplete",
        )
        reference = entry(path / "record.json")
        record = read_ref(reference)
        require(
            record["schema"] == "v35_complete_task_gradient.v1"
            and record["complete_task"] is True
            and record["binding"] == context["task_binding"]
            and record["binding_sha256"] == binding_sha
            and record["task_plan_id"] == task_plan["id"]
            and record["task"] == tasks[task]
            and record["parameter_spec"] == context["parameter_spec"],
            "parent task record changed actual point/task/parameter binding",
        )
        records.append(
            dict(
                task_id=task,
                record=reference,
                gradient=dict(
                    path=str(path / "gradient.pt"),
                    sha256=record["gradient_sha256"],
                    bytes=record["gradient_bytes"],
                ),
                record_file_identity=old._file_identity(path / "record.json"),
                gradient_file_identity=old._file_identity(
                    path / "gradient.pt", size=record["gradient_bytes"]
                ),
            )
        )
    return dict(
        schema="v40_read_only_parent_shard_and_new_task_overlay.v1",
        seed=251,
        arm="C-only",
        step=1192,
        original_context_id=context["id"],
        authorization=authority,
        parent_cache_root=str(cache),
        local_cache_root=str(target / "task_cache"),
        task_plan_id=task_plan["id"],
        task_plan=context["task_plan"],
        binding_sha256=binding_sha,
        parent_task_ids=parent_ids,
        local_task_ids=local_ids,
        parent_task_indices=[tasks[task]["index"] for task in parent_ids],
        local_task_indices=[tasks[task]["index"] for task in local_ids],
        allowed_new_stages=["shard00", "shard01", "shard03"],
        parent_records=records,
        parent_tasks=186,
        new_tasks=558,
        total_tasks=744,
        parent_tensor_contents_read=False,
        gradient_content_validation="unchanged_task_cache_read_before_use",
        parent_records_rewritten=False,
        task_gradient_binding_changed=False,
        parent_tasks_recomputed=False,
        new_task_outputs_only_in_current_root=True,
    )


def checkpoint_metadata(reference, *, coordinate=None):
    """The actual legacy reference carries coordinates only in its small record."""
    directory = Path(reference["path"])
    require(directory.is_absolute() and directory == directory.resolve(), "redirected checkpoint")
    record = read_ref(reference["record"])
    require(
        Path(reference["record"]["path"]) == directory / "record.json"
        and Path(reference["state"]["path"]) == directory / "state.pt"
        and record["state_sha256"] == reference["state"]["sha256"]
        and record["actual_state_digest"] == reference["actual_state_digest"]
        and record["phase"] == reference["phase"],
        "actual checkpoint record binding changed",
    )
    actual = record["seed"], record["arm"], record["step"]
    require(
        coordinate is None or tuple(coordinate) == actual, "checkpoint is from another coordinate"
    )
    for key in ("seed", "arm", "step"):
        require(
            key not in reference or reference[key] == record[key],
            "optional checkpoint coordinate changed",
        )
    return dict(
        reference=reference,
        seed=actual[0],
        arm=actual[1],
        step=actual[2],
        tensor_identity=old._file_identity(directory / "state.pt"),
    )


def _state_sha(path):
    """Only the small explicitly authorized replay checkpoint is hashed here."""
    path = Path(path)
    require(
        path.name == "state.pt"
        and path.parent.name == "response000261"
        and 0 < path.stat().st_size <= 64 * 1024**2,
        "bounded saved replay checkpoint required",
    )
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            value.update(block)
    return value.hexdigest()


def check_interrupted_resources(resources):
    """Check observed lifetime gates, without inventing a model-release boundary."""
    cap, reserve, rss, host_reserve = 76 * old.GIB, 2 * old.GIB, 192 * old.GIB, 96 * old.GIB
    require(
        resources["all_gates_passed"] is True
        and resources["limits_unchanged"] is True
        and resources["maximum_allocated_bytes"] == cap
        and resources["minimum_device_free_bytes"] == reserve
        and resources["peak_resets_before_model_load"] == 1
        and resources["peak_resets_after_model_loading_begins"] == 0
        and resources["helper_peak_reset_calls"] == 0,
        "interrupted process resource contract failed",
    )
    rows = resources["observations"]
    require(
        rows
        and rows[0]["label"] == "before_model_load"
        and rows[-1]["label"] == "replay.after_response"
        and any(row["label"] == "after_model_load.after_cleanup" for row in rows),
        "interrupted replay has no verified model-load/response boundary",
    )
    for row in rows:
        require(
            all(
                row[key] is True
                for key in ("passed", "allocated_pass", "free_pass", "deadline_pass")
            )
            and row["stop_requested"] is False
            and row["limits"]
            == dict(allocated_memory_limit_bytes=cap, free_memory_reserve_bytes=reserve)
            and 0 <= row["allocated_bytes"] <= row["peak_allocated_bytes"] <= cap
            and row["allocated_bytes"] <= row["reserved_bytes"] <= row["peak_reserved_bytes"]
            and row["peak_allocated_bytes"] <= row["peak_reserved_bytes"]
            and 0 <= row["free_bytes"] <= row["total_bytes"]
            and (not row["boundary"] or row["free_bytes"] >= reserve),
            "interrupted process GPU/deadline gate failed",
        )
        host = row["host"]
        require(
            all(host[key] is True for key in ("passed", "rss_pass", "available_pass"))
            and host["rss_limit_bytes"] == rss
            and host["available_reserve_bytes"] == host_reserve
            and 0 <= host["rss_bytes"] <= host["peak_rss_bytes"] <= rss
            and host["available_bytes"] >= host_reserve,
            "interrupted process host gate failed",
        )
    boundaries = [row for row in rows if row["boundary"]]
    require(
        boundaries
        and resources["observed_peak_allocated_bytes"]
        == max(row["peak_allocated_bytes"] for row in rows)
        and resources["observed_minimum_boundary_free_bytes"]
        == min(row["free_bytes"] for row in boundaries)
        and resources["host"]["all_passed"] is True
        and resources["host"]["rss_limit_bytes"] == rss
        and resources["host"]["available_reserve_bytes"] == host_reserve
        and resources["host"]["max_observed_peak_rss_bytes"]
        == max(row["host"]["peak_rss_bytes"] for row in rows)
        and resources["host"]["min_observed_available_bytes"]
        == min(row["host"]["available_bytes"] for row in rows),
        "interrupted resource summary contradicts actual observations",
    )


def inspect_replay_restore(directory, protocol, context):
    require(
        (context["seed"], context["arm"], context["step"]) == REPLAY_COORDINATE
        and context["due_outer"] is True
        and context["branch"]["b_N"] == 0.2
        and context["branch"]["contribution_only"] is False,
        "only authorized Full389/298 replay may resume",
    )
    directory = Path(directory)
    require(
        directory.name == "replay_R3" and directory.parent == Path(context["run_root"]),
        "replay source must be the unchanged scientific context",
    )
    failure, launch, exited = (
        checked(directory / name / "record.json") for name in ("failure", "launch", "exit")
    )
    require(
        all(
            row["protocol_id"] == protocol["id"]
            and row["context_id"] == context["id"]
            and row["stage"] == "replay_R3"
            for row in (failure, launch, exited)
        )
        and failure["error_type"] == "ReplayPaused"
        and failure["error"] == "replay paused at complete response 261"
        and failure["automatic_retry"] is False
        and failure["API_calls"] == 0
        and exited["returncode"] == -15
        and exited["stop_requested"] is True
        and not (directory / "result").exists()
        and not (directory / "payload").exists(),
        "not the explicitly authorized SIGTERM response-boundary interruption",
    )
    old._stopped(launch)
    require(
        launch["gpu_index"] in (3, 4, 5, 7)
        and launch["gpu_uuid"] == protocol["gpu_uuids"][str(launch["gpu_index"])],
        "failed replay GPU binding changed",
    )
    check_interrupted_resources(failure["resources"])
    checkpoint_dir = directory / "checkpoints/response000261"
    checkpoint = checked(checkpoint_dir / "record.json")
    binding = checkpoint["binding"]
    virtual = checked(directory.parent / "virtual_point/result/record.json")
    require(
        checkpoint == failure["durable_replay_checkpoint"]
        and checkpoint["schema"] == "v19_response_boundary_checkpoint.v1"
        and checkpoint["cursor"] == REPLAY_CURSOR
        and checkpoint["full_replay_complete"] is False
        and checkpoint["response_prefix_complete"] is True
        and checkpoint["no_feedback_generation"] is True
        and checkpoint["optimizer_steps_performed"] == 0
        and binding["schema"] == "v32_fixed_replay_point_binding.v1"
        and binding["execution_profile_id"] == context["id"]
        and binding["point_id"] == virtual["point_id"]
        and binding["response_count"] == virtual["response_count"] == REPLAY_TOTAL
        and binding["denominator"] == virtual["denominator"] == 700
        and binding["gradient_length_normalized"] is False,
        "saved cumulative response prefix is incomplete or from another parameter point",
    )
    require(
        all(
            int(path.name.removeprefix("response")) <= REPLAY_CURSOR
            for path in (directory / "checkpoints").glob("response[0-9]*")
            if path.is_dir()
        ),
        "a later response checkpoint exists; scope must not silently rewind",
    )
    tensor = old._file_identity(checkpoint_dir / "state.pt")
    require(
        _state_sha(checkpoint_dir / "state.pt") == checkpoint["state_sha256"],
        "saved cumulative replay Tensor bytes changed",
    )
    require(
        old._finite_nonnegative(launch["deadline_epoch"])
        and old._finite_nonnegative(exited["elapsed_worker_wall_seconds"]),
        "replay budget binding missing",
    )
    return dict(
        checkpoint=entry(checkpoint_dir / "record.json"),
        state=dict(path=str(checkpoint_dir / "state.pt"), sha256=checkpoint["state_sha256"]),
        checkpoint_directory=str(checkpoint_dir),
        tensor_identity=tensor,
        binding=binding,
        inherited_response_count=REPLAY_CURSOR,
        total_response_count=REPLAY_TOTAL,
        remaining_response_count=REPLAY_TOTAL - REPLAY_CURSOR,
        parent_stage_failure=entry(directory / "failure/record.json"),
        parent_stage_launch=entry(directory / "launch/record.json"),
        parent_stage_exit=entry(directory / "exit/record.json"),
        original_phase_deadline_epoch=launch["deadline_epoch"],
        full_replay_complete=False,
        failed_parent_stage_reclassified=False,
        parent_saved_prefix_replayed_again=False,
        state_bytes_verified=True,
        tensor_structure_gradient_and_RNG_verification="unchanged_v19_storage_read_before_resume",
    )


def context_timing(context, protocol, bindings, snapshot, restore=None):
    timing = base.timing_from_stages(context, protocol, bindings, snapshot)
    if restore is None:
        return timing
    launch = read_ref(restore["parent_stage_launch"])
    exited = read_ref(restore["parent_stage_exit"])
    intervals = []
    for binding in bindings.values():
        if binding["protocol_scope"] == "parent":
            started, ended = read_ref(binding["launch"]), read_ref(binding["exit"])
            epoch = old._time(started["at"])
            intervals.append(
                (epoch, max(old._time(ended["at"]), epoch + ended["elapsed_worker_wall_seconds"]))
            )
    start = old._time(launch["at"])
    elapsed = exited["elapsed_worker_wall_seconds"]
    intervals.append((start, max(old._time(exited["at"]), start + elapsed)))
    # The frozen context queue was written at launch, before the interrupted
    # worker's runtime. Keep that runtime even when the last snapshot is stale.
    snapshot_at = old._time(snapshot["at"])
    unaccounted = max(0, max(old._time(exited["at"]), start + elapsed) - max(snapshot_at, start))
    timing["inherited_compute_seconds"] = math.ceil(
        max(
            timing["inherited_compute_seconds"],
            base.union_seconds(intervals),
            snapshot["compute_seconds"] + unaccounted,
        )
    )
    timing["worker_interval_union_seconds"] = base.union_seconds(intervals)
    timing["interrupted_worker_seconds"] = elapsed
    timing["unaccounted_interrupted_seconds_added"] = unaccounted
    timing["phase_deadlines_epoch"]["replay_R3"] = launch["deadline_epoch"]
    timing["phase_first_launch_epoch"]["replay_R3"] = start
    timing["interrupted_stage_included_in_time_not_completed_stages"] = True
    return timing


def _parent_stopped(parent, protocol):
    failure = checked(parent / "failure/record.json")
    queue = json.loads((parent / "queue/status.json").read_bytes())
    expected = dict(
        phase="STOPPED_FAILURE_NO_RETRY",
        error_type="ValueError",
        error="worker reported failure: replay_R3",
        stop_error=None,
        actual_progress_audit_error=None,
        automatic_retry=False,
    )
    require(
        all(
            failure.get(key) == value and queue.get(key) == value for key, value in expected.items()
        )
        and failure["protocol_id"] == queue["protocol_id"] == protocol["id"]
        and queue["active_children"] == []
        and queue["pilot_accepted"] is True,
        "parent is not the stopped, audited replay-prefix failure",
    )
    old._stopped(checked(parent / "launch_01/record.json"))
    handoff = parent / "controlled_handoff_gpu6_01"
    plan, stopped = checked(handoff / "plan/record.json"), checked(handoff / "failure/record.json")
    require(
        stopped["plan_id"] == plan["id"]
        and stopped["status"] == "STOPPED_NO_MIGRATION"
        and stopped["error"] == "observed stage recorded failure"
        and all(
            stopped[key] is False
            for key in (
                "controller_signalled",
                "workers_signalled",
                "new_experiment_started_by_handoff",
                "continuation_callback_invoked",
                "automatic_retry",
            )
        )
        and read_ref(plan["parent_protocol"])["id"] == protocol["id"]
        and not (handoff / "closeout").exists(),
        "failed handoff was altered or already continued",
    )
    migration_root = parent.parent / "gpu6_resume_01"
    old._stopped(checked(migration_root / "migration_launch/record.json"))
    require(
        not (migration_root / "protocol/record.json").exists()
        and not (migration_root / "launch_01/record.json").exists(),
        "V39 already initialized a scientific continuation",
    )
    duration = old._time(stopped["at"]) - old._time(plan["at"])
    require(
        duration >= 0
        and old._finite_nonnegative(queue["global_external_resource_wait_seconds"])
        and old._finite_nonnegative(plan["initial_queue"]["global_external_resource_wait_seconds"]),
        "handoff/global resource accounting changed",
    )
    used = math.ceil(
        max(
            queue["global_external_resource_wait_seconds"],
            plan["initial_queue"]["global_external_resource_wait_seconds"] + duration,
        )
    )
    return queue, dict(
        inherited_resource_wait_seconds=used,
        failed_handoff=entry(handoff / "failure/record.json"),
        failed_handoff_plan=entry(handoff / "plan/record.json"),
        failed_migration_launch=entry(migration_root / "migration_launch/record.json"),
        resource_wait_accounting=dict(
            parent_final_wait_seconds=queue["global_external_resource_wait_seconds"],
            failed_handoff_initial_wait_seconds=plan["initial_queue"][
                "global_external_resource_wait_seconds"
            ],
            failed_handoff_elapsed_wall_seconds=duration,
            rule=(
                "ceil(max(parent_final_wait, "
                "handoff_initial_wait + failed_handoff_actual_elapsed_wall))"
            ),
            failed_handoff_unspent_plan_deadline_not_a_recovery_deadline=True,
            budgets_reset_or_enlarged=False,
        ),
    )


def inspect_parent_recovery(newroot, parentroot, *, authorization_record=None):
    root, parent = Path(newroot).resolve(), Path(parentroot).resolve()
    require(root == parent.parent / "recovery_02", "fixed independent V40 root required")
    require(not (root / "inheritance/record.json").exists(), "recovery already registered")
    protocol = checked(parent / "protocol/record.json")
    require(
        protocol["id"] == PARENT_PROTOCOL_ID
        and protocol["schema"] == "v38_same_point_admission_recovery_protocol.v1",
        "original V38 protocol changed",
    )
    queue, waiting = _parent_stopped(parent, protocol)
    require(
        waiting["inherited_resource_wait_seconds"] < protocol["resource_wait_budget_seconds"],
        "original wait budget exhausted",
    )
    progress_path = parent / "actual_final_progress/record.json"
    progress = checked(progress_path)
    require(
        progress["schema"] == "v37_actual_B_CPU_state_snapshot.v1"
        and progress["endpoint_scores_or_answers_read"] is False
        and progress["original_state_or_feedback_modified"] is False
        and (progress["remaining_physical_updates"], progress["remaining_outers"]) == (4143, 11)
        and (progress["completed_physical_updates"], progress["completed_outers"]) == (7479, 13)
        and progress["pending_sealed_feedback_episodes"] == 0
        and progress["future_first_sampling_feedback_episodes"] == 7700,
        "actual fixed nine-model state or original remaining dose changed",
    )
    require(
        (queue["accepted_new_optimizer_updates"], queue["accepted_new_outer_updates"]) == (1667, 4),
        "accepted counters contradict actual committed-state audit",
    )
    coordinates = {(seed, arm) for seed in SEEDS for arm in ARM_KEYS}
    latest = {(row["seed"], row["arm"]): row for row in progress["arms"]}
    require(
        set(latest) == coordinates and len(progress["arms"]) == 9,
        "nine-model coordinate coverage changed",
    )
    require(
        {(row["seed"], row["arm"]) for row in queue["completed_training_coordinates"]}
        == {key for key, row in latest.items() if row["step"] == 1490},
        "actual complete training set changed",
    )
    checkpoints = [
        checkpoint_metadata(row["checkpoint"], coordinate=(row["seed"], row["arm"], row["step"]))
        for row in progress["arms"]
    ]
    inherited, completed, unused, all_stages, deferred = [], [], [], [], []
    restore_count = partial_class_count = 0
    class_authority = None
    for record in sorted((parent / "contexts").glob("seed*/*/step*/context/record.json")):
        directory = record.parent.parent.resolve()
        context, alias = base._read_context(directory)
        coordinate = context["seed"], context["arm"]
        require(coordinate in coordinates, "foreign scientific coordinate")
        task_plan = read_ref(context["task_plan"]) if context["due_outer"] else None
        bindings, restore = {}, None
        for stage in STAGES:
            if directory == parent / REPLAY_RELATIVE and stage == "replay_R3":
                restore = inspect_replay_restore(directory / stage, protocol, context)
                restore_count += 1
                continue
            binding = base.inspect_stage(directory / stage, protocol, context, stage, task_plan)
            if binding is not None:
                bindings[stage] = binding
                all_stages.append(binding)
        if "train" in bindings:
            require(
                restore is None, "failed prefix cannot coexist with a committed downstream train"
            )
            completion = checked(directory / "completion/record.json")
            require(
                completion["context_id"] == context["id"]
                and completion["protocol_id"] == protocol["id"]
                and completion["result"] == bindings["train"]["result"],
                "completed training lacks accepted controller record",
            )
            completed.append(
                dict(
                    context=entry(record),
                    context_id=context["id"],
                    completion=entry(directory / "completion/record.json"),
                    stage_bindings=bindings,
                    pilot_alias=alias,
                )
            )
            continue
        require(
            not alias and context["checkpoint"] == latest[coordinate]["checkpoint"],
            "unfinished context is not the latest actual coordinate",
        )
        if not bindings:
            require(restore is None, "failed replay has no accepted upstream stages")
            unused.append(
                dict(
                    context=entry(record),
                    seed=coordinate[0],
                    arm=coordinate[1],
                    reason="no_stage_dispatched_recreate_from_same_actual_checkpoint",
                )
            )
            continue
        target = root / directory.relative_to(parent)
        overlay = None
        require(context["due_outer"] is True, "incomplete training attempt cannot be retried")
        if not set(SHARDS) <= bindings.keys():
            class_authority = _partial_class_authority(root, authorization_record)
            overlay = inspect_task_cache_overlay(
                directory, target, context, task_plan, bindings, class_authority
            )
            partial_class_count += 1
        if "replay_R3" in bindings:
            require("virtual_point" in bindings, "accepted replay lacks same-point virtual result")
        if "distribution" in bindings:
            require("replay_R3" in bindings, "distribution lacks accepted complete replay")
        if restore is not None:
            require(
                set(bindings) == {*SHARDS, "virtual_point"},
                "authorized replay must retain exactly five completed parent stages",
            )
        require(not (target / "context/record.json").exists(), "recovery alias already exists")
        for stage in STAGES:
            bindings.setdefault(
                stage, dict(protocol_scope="current", directory=str(target / stage))
            )
        if restore:
            bindings["replay_R3"]["durable_replay_restore"] = restore
        queue_path = directory / "queue/status.json"
        snapshot = json.loads(queue_path.read_bytes())
        require(
            snapshot["context_id"] == context["id"] and snapshot["protocol_id"] == protocol["id"],
            "foreign timing snapshot",
        )
        for child in snapshot.get("active_children", []):
            stage = child["stage"]
            source = (
                restore["parent_stage_launch"]
                if restore and stage == "replay_R3"
                else bindings[stage]["launch"]
            )
            launch = read_ref(source)
            require(
                all(child[key] == launch[key] for key in ("pid", "birth", "gpu_index", "gpu_uuid")),
                "stale child identity differs from exited worker",
            )
            old._stopped(launch)
        timing = context_timing(context, protocol, bindings, snapshot, restore)
        require(
            timing["inherited_compute_seconds"] < protocol["outer_compute_budget_seconds"],
            "original outer budget exhausted",
        )
        old._verify_refs(context["sources"])
        old._verify_refs(context["execution_binding"])
        old._verify_refs(context["feedback"], deferred=deferred)
        checkpoint_metadata(
            context["checkpoint"], coordinate=(context["seed"], context["arm"], context["step"])
        )
        cache = Path(context["task_cache_root"])
        require(cache == directory / "task_cache", "parent cache directory changed")
        if overlay is None:
            inventory = [
                old._file_identity(cache / f"task{index:04d}" / name)
                for index in range(len(task_plan["task_ids"]))
                for name in ("record.json", "gradient.pt")
            ]
        else:
            inventory = [
                row[key]
                for row in overlay["parent_records"]
                for key in ("record_file_identity", "gradient_file_identity")
            ]
        partial = override = None
        if overlay is not None:
            original_deadline = timing["phase_deadlines_epoch"]["class_gradients"]
            partial = dict(
                **PARTIAL_CLASS_AUTHORIZATION,
                authorization=class_authority,
                original_class_deadline_epoch=original_deadline,
                inherited_compute_seconds=timing["inherited_compute_seconds"],
                parent_compute_snapshot_seconds=timing["parent_compute_snapshot_seconds"],
                actual_new_passes_per_remaining_task=1,
                original_class_deadline_retained_as_historical_evidence=True,
            )
            override = dict(
                schema="v40_explicit_single_class_phase_deadline_override.v1",
                authorization=class_authority,
                phase="class_gradients",
                seed=251,
                arm="C-only",
                step=1192,
                allowed_new_stages=list(PARTIAL_CLASS_AUTHORIZATION["remaining_shards"]),
                window_seconds=14400,
                deadline_rule=PARTIAL_CLASS_AUTHORIZATION["deadline_rule"],
                original_deadline_epoch=original_deadline,
                original_phase_deadline_extended=True,
                inherited_compute_seconds=timing["inherited_compute_seconds"],
                outer_compute_budget_reset=False,
                global_resource_wait_budget_reset=False,
                window_record=str(target / "class_recovery_window/record.json"),
                shared_across_all_three_remaining_shards=True,
                automatic_retry=False,
            )
            timing.pop("phase_budgets_reset", None)
            timing["only_authorized_class_window_rebased"] = True
        inherited.append(
            dict(
                seed=context["seed"],
                arm=context["arm"],
                step=context["step"],
                original_context=entry(record),
                original_context_id=context["id"],
                origin_context_directory=str(directory),
                new_context_directory=str(target),
                parent_context_snapshot=file_ref(queue_path),
                stage_bindings=bindings,
                parent_protocol=entry(parent / "protocol/record.json"),
                task_plan=context["task_plan"],
                task_cache_root=context["task_cache_root"],
                task_cache_inventory=dict(
                    tasks=len(overlay["parent_task_ids"])
                    if overlay
                    else len(task_plan["task_ids"]),
                    total_planned_tasks=len(task_plan["task_ids"]),
                    metadata_digest=digest(inventory),
                    tensor_contents_read=False,
                ),
                durable_replay_restore=restore,
                task_cache_overlay=overlay,
                partial_class_recovery=partial,
                class_deadline_override=override,
                **timing,
            )
        )
    require(
        restore_count == partial_class_count == 1
        and len({(row["seed"], row["arm"]) for row in inherited}) == len(inherited),
        "exactly one authorized replay restore and one C251 class completion required",
    )
    accepted = [read_ref(row["stage_bindings"]["train"]["result"]) for row in completed]
    require(
        sum(row["actual_optimizer_steps"] for row in accepted) == 1667
        and sum(int(row["outer_committed"]) for row in accepted) == 4,
        "accepted actual training commits do not cover cumulative progress",
    )
    evaluations = []
    for seed, arm in sorted(coordinates):
        directory = parent / f"evaluations/seed{seed}_{ARM_KEYS[arm]}"
        context = dict(id=f"evaluation:{seed}:{ARM_KEYS[arm]}", seed=seed, arm=arm)
        binding = base.inspect_stage(directory / "generate", protocol, context, "generate")
        seal = (
            Path(protocol["evaluation_root"])
            / f"models/seed{seed}/{ARM_KEYS[arm]}/whole_test_seal/record.json"
        )
        if dict(seed=seed, arm=arm) in queue["completed_evaluation_coordinates"]:
            value = checked(seal)
            require(
                (value["seed"], value["arm"], value["denominator"]) == (seed, arm, 1147)
                and value["all_generation_complete"] is True
                and value["all_provider_calls_settled"] is True
                and latest[(seed, arm)]["step"] == 1490,
                "parent endpoint seal incomplete",
            )
            require(
                binding is not None or (seed, arm) in ((137, "Static"), (251, "Static")),
                "new endpoint lacks real completed worker",
            )
            if binding:
                require(
                    read_ref(binding["result"])["whole_test_seal"] == entry(seal),
                    "endpoint result seal changed",
                )
                all_stages.append(binding)
            evaluations.append(
                dict(
                    seed=seed,
                    arm=arm,
                    whole_test_seal=entry(seal),
                    stage_binding=binding,
                    answers_or_scores_read=False,
                )
            )
        else:
            require(
                binding is None and not seal.exists(), "unaccepted endpoint cannot be regenerated"
            )
    require(len(evaluations) == 4, "authorized four sealed endpoints changed")
    sampled = sum(
        read_ref(row["result"]).get("new_feedback_episodes", 0)
        for row in all_stages
        if Path(row["directory"]).name == "virtual_point"
    )
    pending = sum(
        read_ref(row["stage_bindings"]["virtual_point"]["result"]).get("new_feedback_episodes", 0)
        for row in inherited
        if row["stage_bindings"]["virtual_point"]["protocol_scope"] == "parent"
    )
    require(
        sampled == 1400 and pending == 700 and 8400 - sampled == 7700 - pending == 7000,
        "already sealed feedback must be deducted from future new-sampling dose",
    )
    return dict(
        schema=SCHEMA,
        at=datetime.now(timezone.utc).isoformat(),
        new_root=str(root),
        parent_root=str(parent),
        parent_protocol=entry(parent / "protocol/record.json"),
        parent_implementation=entry(parent / "implementation/record.json"),
        parent_failure=entry(parent / "failure/record.json"),
        parent_queue=file_ref(parent / "queue/status.json"),
        actual_final_progress=entry(progress_path),
        context_inheritances=inherited,
        completed_contexts=completed,
        unused_contexts=unused,
        completed_evaluations=evaluations,
        latest_checkpoints=checkpoints,
        all_parent_stage_bindings=all_stages,
        accepted_new_optimizer_updates=1667,
        accepted_new_outer_updates=4,
        remaining_optimizer_updates=4143,
        remaining_outer_updates=11,
        remaining_scientific_budget=dict(
            original_reused_feedback_episodes=2100,
            original_first_sampling_feedback_episodes=8400,
            pending_sealed_feedback_episodes=0,
            future_first_sampling_outers=11,
            future_first_sampling_feedback_episodes=7700,
            already_generated_first_sampling_feedback_episodes=sampled,
            already_generated_uncommitted_feedback_episodes=pending,
            remaining_new_feedback_episodes=7000,
            remaining_endpoint_answers=5735,
            total_endpoint_answers=10323,
        ),
        deferred_feedback_content_verification=deferred,
        partial_class_authorization=class_authority,
        parent_contexts_rewritten=False,
        parent_tensors_copied=False,
        failed_parent_stage_reclassified=False,
        completed_stages_redispatched=False,
        authorized_saved_prefix_resume_only=True,
        inherited_response_count=261,
        remaining_response_count=186,
        new_sampling_calls=0,
        replayed_responses=0,
        optimizer_updates=0,
        outer_and_global_budgets_reset=False,
        only_explicitly_authorized_class_deadline_extended=True,
        endpoint_scores_or_answers_read=False,
        **waiting,
    )


def initialize_parent_recovery(newroot, parentroot):
    root = Path(newroot).resolve()
    value = publish(root / "inheritance/record.json", inspect_parent_recovery(root, parentroot))
    for item in value["context_inheritances"]:
        publish(
            Path(item["new_context_directory"]) / "context/record.json",
            dict(
                schema=ALIAS_SCHEMA,
                new_context_directory=item["new_context_directory"],
                original_context=item["original_context"],
                original_context_id=item["original_context_id"],
                origin_context_directory=item["origin_context_directory"],
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
        "wrong recovery inheritance",
    )
    return value


def inherited_context(newctx, plan):
    directory = str(Path(newctx).resolve())
    rows = [
        row
        for row in _inheritance(plan)["context_inheritances"]
        if row["new_context_directory"] == directory
    ]
    require(len(rows) <= 1, "duplicate context inheritance")
    return rows[0] if rows else None


def resolve_origin_context(newctx, plan):
    directory = Path(newctx).resolve()
    require(
        directory.is_relative_to(Path(plan["output_root"]).resolve() / "contexts"),
        "context outside recovery root",
    )
    value, item = checked(directory / "context/record.json"), inherited_context(directory, plan)
    if item is None:
        require(
            value["schema"] == "v37_actual_production_context.v1"
            and value["run_root"] == value["outer_root"] == str(directory),
            "new context must own its actual coordinate",
        )
        return directory
    require(
        value["schema"] == ALIAS_SCHEMA
        and value["inheritance"] == plan["inheritance"]
        and all(
            value[key] == item[key]
            for key in (
                "new_context_directory",
                "original_context",
                "original_context_id",
                "origin_context_directory",
            )
        ),
        "parent alias changed",
    )
    require(
        read_ref(item["original_context"])["id"] == item["original_context_id"],
        "original context changed",
    )
    return Path(item["origin_context_directory"])


def stage_directory(newctx, plan, stage):
    require(stage in STAGES, "unknown production stage")
    directory = Path(newctx).resolve()
    origin, item = resolve_origin_context(directory, plan), inherited_context(directory, plan)
    if item is None:
        return directory / stage
    binding = item["stage_bindings"][stage]
    require(binding["protocol_scope"] in ("parent", "current"), "unknown stage protocol owner")
    expected = (origin if binding["protocol_scope"] == "parent" else directory) / stage
    require(binding["directory"] == str(expected), "stage directory changed")
    return expected


def replay_resume_binding(newctx, plan):
    directory = Path(newctx).resolve()
    resolve_origin_context(directory, plan)
    item = inherited_context(directory, plan)
    if item is None or item.get("durable_replay_restore") is None:
        return None
    require(
        (item["seed"], item["arm"], item["step"]) == REPLAY_COORDINATE
        and item["stage_bindings"]["replay_R3"]["protocol_scope"] == "current"
        and item["stage_bindings"]["replay_R3"]["durable_replay_restore"]
        == item["durable_replay_restore"],
        "saved prefix restore escaped its explicit current-stage scope",
    )
    value = item["durable_replay_restore"]
    require(
        read_ref(value["checkpoint"])["binding"] == value["binding"], "saved replay binding changed"
    )
    return value


def task_cache_overlay_binding(newctx, plan):
    directory = Path(newctx).resolve()
    origin = resolve_origin_context(directory, plan)
    item = inherited_context(directory, plan)
    if item is None or item.get("task_cache_overlay") is None:
        return None
    value = item["task_cache_overlay"]
    require(
        value["schema"] == "v40_read_only_parent_shard_and_new_task_overlay.v1"
        and (item["seed"], item["arm"], item["step"]) == PARTIAL_CLASS_COORDINATE
        and (value["seed"], value["arm"], value["step"]) == PARTIAL_CLASS_COORDINATE
        and value["original_context_id"] == item["original_context_id"]
        and value["parent_cache_root"] == str(origin / "task_cache")
        and value["local_cache_root"] == str(directory / "task_cache")
        and value["allowed_new_stages"] == PARTIAL_CLASS_AUTHORIZATION["remaining_shards"]
        and {
            stage
            for stage, binding in item["stage_bindings"].items()
            if binding["protocol_scope"] == "parent"
        }
        == {"shard02"}
        and value["authorization"] == plan["audit"]
        and read_ref(value["authorization"])["partial_class_recovery"]
        == PARTIAL_CLASS_AUTHORIZATION,
        "task-cache overlay escaped its explicit same-point authority",
    )
    return value


def require_upstream(newctx, context, plan, stage, control):
    directory = Path(newctx).resolve()
    origin, item = resolve_origin_context(directory, plan), inherited_context(directory, plan)
    require(context == checked(origin / "context/record.json"), "scientific context was relabelled")
    require(
        stage_directory(directory, plan, stage) == directory / stage,
        "completed parent stage must not rerun",
    )
    required = {
        "virtual_point": SHARDS,
        "replay_R3": ("virtual_point",),
        "distribution": (*SHARDS, "virtual_point", "replay_R3"),
        "train": ("distribution",) if context["due_outer"] else (),
    }.get(stage, ())
    task_plan = read_ref(context["task_plan"]) if context["due_outer"] else None
    for previous in required:
        source = stage_directory(directory, plan, previous)
        binding = item["stage_bindings"][previous] if item else None
        is_parent = binding is not None and binding["protocol_scope"] == "parent"
        owner = read_ref(item["parent_protocol"]) if is_parent else plan
        result, exited = (
            checked(source / "result/record.json"),
            checked(source / "exit/record.json"),
        )
        if is_parent:
            require(
                binding["protocol_id"] == owner["id"]
                and binding["result"] == entry(source / "result/record.json")
                and binding["exit"] == entry(source / "exit/record.json"),
                "source stage reference changed",
            )
        require(
            result["context_id"] == exited["context_id"] == context["id"]
            and result["protocol_id"] == exited["protocol_id"] == owner["id"]
            and result["stage"] == exited["stage"] == previous
            and exited["returncode"] == 0
            and exited["stop_requested"] is False,
            "upstream actual protocol/point/exit changed",
        )
        control.check_result(owner, previous, result, task_plan)
        if previous in ("virtual_point", "replay_R3", "distribution"):
            reference, _identity = old._payload(source, context, previous)
            require(
                result["payload"] == reference
                and (not is_parent or binding["payload"] == reference),
                "upstream saved value changed",
            )
