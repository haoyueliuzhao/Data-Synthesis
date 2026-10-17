"""Explicit V42 restart: immutable completed values and narrowly authorized unfinished work.

Only the stopped V40 pool and the newly authorized bounded recovery may initialize.
V40's already accepted recovery pilot and its historical failed prefix are not
run again. Metadata is inspected here; original cache readers validate tensor
contents when used. No checkpoint, cohort, cache or historical record is edited.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import finqa_v40_inheritance as previous

base, old = previous.base, previous.old
require, checked, entry, read_ref = old.require, old.checked, old.entry, old.read_ref
publish, file_ref, digest = old.publish, old.file_ref, old.digest
SHARDS, STAGES, ARM_KEYS, SEEDS = base.SHARDS, base.STAGES, base.ARM_KEYS, base.SEEDS
SCHEMA = "v42_explicit_stopped_V40_recovery.v1"
ALIAS_SCHEMA = "v42_per_stage_parent_context_alias.v1"
CACHE_SCHEMA = "v41_complete_read_only_task_cache_view.v1"
PARENT_PROTOCOL_ID = "8732c9297d5a08cda1cb3990622cc8ee1d0868714c4aaf4de2c252e4a0b97160"
checkpoint_metadata = previous.checkpoint_metadata


def _actual_context(reference):
    """Follow explicit historical aliases without changing their scientific ID."""
    seen = set()
    while True:
        path = reference["path"]
        require(path not in seen, "cyclic scientific context alias")
        seen.add(path)
        context = read_ref(reference)
        if context["schema"] == "v37_actual_production_context.v1":
            directory = Path(path).parent.parent
            require(
                directory == directory.resolve()
                and context["run_root"] == context["outer_root"] == str(directory),
                "original scientific context location changed",
            )
            return reference, context, directory
        require(
            context["schema"] in (old.ALIAS_SCHEMA, base.ALIAS_SCHEMA, previous.ALIAS_SCHEMA),
            "unknown historical scientific alias",
        )
        reference = context["original_context"]
        require(read_ref(reference)["id"] == context["original_context_id"], "alias ID changed")


def inspect_stage(directory, protocol, context, stage, task_plan=None, *, protocol_ref):
    """Validate each accepted worker under its real protocol, including all 8 GPUs."""
    directory = Path(directory)
    markers = ("launch", "attempt", "result", "exit", "failure", "payload")
    if not any((directory / name).exists() for name in markers):
        return None
    require(directory == directory.resolve(), "redirected stage directory")
    require(not (directory / "failure").exists(), "failed stage cannot migrate or retry")
    require(
        all((directory / name / "record.json").is_file() for name in ("launch", "result", "exit")),
        "partial or unexited stage cannot migrate",
    )
    launch, result, exited = (
        checked(directory / name / "record.json") for name in ("launch", "result", "exit")
    )
    require(read_ref(protocol_ref) == protocol, "stage protocol reference changed")
    require(
        all(row["protocol_id"] == protocol["id"] for row in (launch, result, exited))
        and all(row["context_id"] == context["id"] for row in (launch, result, exited))
        and all(row["stage"] == stage for row in (launch, result, exited))
        and result["status"] == "COMPLETE"
        and result["model_released"] is True
        and exited["returncode"] == 0
        and exited["stop_requested"] is False,
        "stage is not accepted, physically successful and bound to its actual point",
    )
    old._stopped(launch)
    gpu = result["gpu_index"]
    require(
        type(gpu) is int
        and gpu in protocol["allowed_gpu_indices"]
        and gpu == launch["gpu_index"]
        and result["gpu_uuid"] == launch["gpu_uuid"] == protocol["gpu_uuids"][str(gpu)],
        "stage GPU differs from its own registered protocol",
    )
    old._check_resources(result["resources"], stage)
    for key in (
        "API_calls",
        "new_sampling_calls",
        "scoring_calls",
        "optimizer_steps",
        "replayed_responses",
    ):
        require(type(result[key]) is int and result[key] >= 0, "invalid scientific counter")
    require(
        result["API_calls"] == 0
        and (stage == "virtual_point" or result["scoring_calls"] == 0)
        and (stage == "train" or result["optimizer_steps"] == 0)
        and (stage == "replay_R3" or result["replayed_responses"] == 0)
        and (stage in ("virtual_point", "generate") or result["new_sampling_calls"] == 0),
        "scientific activity outside its registered stage",
    )
    if stage not in ("train", "generate"):
        require(result["model_optimizer_rng_buffers_unchanged"] is True, "real state changed")
    if stage in SHARDS:
        tasks = task_plan["assignments"][SHARDS.index(stage)]["task_ids"]
        reused = result["reused_task_ids"]
        require(
            result["task_ids"] == tasks
            and result["task_count"] == len(tasks)
            and result["class_task_calls"] + len(reused) == len(tasks)
            and len(set(reused)) == len(reused)
            and set(reused) <= set(tasks),
            "whole-task coverage changed",
        )
    if stage in ("virtual_point", "replay_R3", "distribution"):
        require(result["denominator"] == 700, "feedback denominator changed")
    if stage == "virtual_point":
        expected = 0 if context["feedback"]["mode"] == "sealed_existing" else 700
        require(
            result["feedback_mode"] == context["feedback"]["mode"]
            and result["new_feedback_episodes"] == expected,
            "same-point feedback ownership or dose changed",
        )
    if stage == "replay_R3":
        require(
            result["complete_replay"] is True and result["current_point_only"] is True,
            "actual cumulative response replay is incomplete",
        )
        if result.get("restored_completed_responses", 0):
            require(
                (context["seed"], context["arm"], context["step"]) == previous.REPLAY_COORDINATE
                and result["restored_completed_responses"]
                == result["inherited_response_count"]
                == 261
                and result["actual_new_response_calls"] == 186
                and result["replayed_responses"] == 186
                and result["response_count"] == 447,
                "V40 prefix recovery dose changed",
            )
        else:
            require(
                result["replayed_responses"] == result["response_count"],
                "non-resumed replay must cover its complete response cohort",
            )
    if stage == "generate":
        require(
            result["session_count"] == result["new_generation_episodes"] == 1147
            and result["new_sampling_calls"] == result["actual_response_calls"]
            and result["private_test_scoring"] is False,
            "endpoint dose or all-model scoring barrier changed",
        )
    binding = dict(
        protocol_scope="parent",
        protocol_id=protocol["id"],
        protocol_ref=protocol_ref,
        directory=str(directory),
        launch=entry(directory / "launch/record.json"),
        result=entry(directory / "result/record.json"),
        exit=entry(directory / "exit/record.json"),
    )
    if (directory / "attempt/record.json").exists():
        binding["attempt"] = entry(directory / "attempt/record.json")
    if stage in ("virtual_point", "replay_R3", "distribution"):
        binding["payload"], binding["tensor_identity"] = old._payload(directory, context, stage)
        require(result["payload"] == binding["payload"], "actual saved phase value changed")
    if stage == "train":
        commits = {}
        for key in ("next_checkpoint", "outer_checkpoint", "first_sft_after_outer"):
            if result.get(key):
                path = Path(result[key]).resolve()
                # Legacy scientific checkpoints use their state digest and a
                # file reference, not the scheduler's self-ID JSON wrapper.
                meta = read_ref(file_ref(path / "record.json"))
                reference = dict(
                    path=str(path),
                    record=file_ref(path / "record.json"),
                    state=dict(path=str(path / "state.pt"), sha256=meta["state_sha256"]),
                    **{
                        name: meta[name]
                        for name in ("seed", "arm", "step", "phase", "actual_state_digest")
                    },
                )
                commits[key] = checkpoint_metadata(reference)
        require(
            commits["next_checkpoint"]["step"] == result["committed_step"]
            and all(
                (row["seed"], row["arm"]) == (context["seed"], context["arm"])
                for row in commits.values()
            ),
            "actual training commit coordinate changed",
        )
        binding["actual_training_commits"] = commits
    return binding


DISTRIBUTION_COORDINATE = (251, "Full", 894)
PARTIAL_CLASS_COORDINATE = (389, "Full", 596)
PARTIAL_FEEDBACK_COORDINATE = (389, "C-only", 894)
AUTHORIZED_INTERRUPTED = {
    DISTRIBUTION_COORDINATE: "distribution",
    PARTIAL_CLASS_COORDINATE: "shard01",
    PARTIAL_FEEDBACK_COORDINATE: "virtual_point",
}


def _validate_parent_restart(root, parent, protocol, authorization_record, authorization_body=None):
    require(
        authorization_record is None or authorization_body is None,
        "preview body and sealed authorization cannot be mixed",
    )
    if authorization_body is not None:
        authorization = authorization_body
        authorization_ref = dict(preview_only=True, authorization_body_digest=digest(authorization))
    else:
        authorization_ref = (
            authorization_record
            if isinstance(authorization_record, dict)
            else entry(authorization_record or root / "authorization/record.json")
        )
        authorization = read_ref(authorization_ref)
    require(
        bool(authorization.get("user_consent"))
        and authorization.get("global_resource_wait_budget_seconds") == 129600
        and authorization.get("distribution_window_seconds") == 7200
        and authorization.get("unknown_request_reexecution_authorized") is True,
        "explicit bounded wait, distribution and unique unknown-request authority required",
    )
    queue = json.loads((parent / "queue/status.json").read_bytes())
    failure = checked(parent / "failure/record.json")
    require(
        protocol["schema"] == "v40_explicit_durable_replay_recovery_protocol.v1"
        and protocol["id"] == PARENT_PROTOCOL_ID
        and queue["protocol_id"] == failure["protocol_id"] == protocol["id"]
        and queue["phase"] == failure["phase"] == "PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME"
        and queue["pilot_accepted"] is True
        and queue["active_children"] == []
        and failure["automatic_retry"] is False
        and failure["stop_error"] is None
        and failure["actual_progress_audit_error"] is None,
        "only the fully exited registered V40 durable pause may recover",
    )
    old._stopped(checked(parent / "launch_01/record.json"))
    pilot_ref = entry(parent / "pilot_acceptance/record.json")
    pilot = read_ref(pilot_ref)
    require(
        pilot["protocol_id"] == protocol["id"]
        and pilot["remaining_matrix_dispatch_authorized"] is True
        and pilot["restored_completed_responses"] == 261
        and pilot["actual_new_response_calls"] == 186
        and pilot["cumulative_complete_response_count"] == 447
        and pilot["outer_commits"] == pilot["actual_optimizer_steps"] == 1
        and pilot["committed_step"] == 299,
        "the actual accepted V40 pilot must be inherited, never repeated",
    )
    train, exited = read_ref(pilot["train_result"]), read_ref(pilot["train_actual_exit"])
    require(
        train["status"] == "COMPLETE" and exited["returncode"] == 0,
        "accepted pilot physical success changed",
    )
    handoff = parent / "controlled_admission_handoff_01"
    plan_ref, failure_ref = (
        entry(handoff / "plan/record.json"),
        entry(handoff / "failure/record.json"),
    )
    plan, failed = read_ref(plan_ref), read_ref(failure_ref)
    require(
        plan["mode"] == "passive_all_or_none"
        and failed["status"] == "STOPPED_NO_MIGRATION"
        and all(
            failed[key] is False
            for key in (
                "controller_signalled",
                "workers_signalled",
                "parent_resume_attempted",
                "new_experiment_started_by_handoff",
                "continuation_callback_invoked",
                "automatic_retry",
            )
        )
        and read_ref(plan["parent_protocol"])["id"] == protocol["id"],
        "the expired observer must remain a failed no-migration episode",
    )
    heartbeat_path = (
        parent / "contexts/seed251/full/step0894_outer/distribution/pre_cuda_wait/status.json"
    )
    heartbeat = json.loads(heartbeat_path.read_bytes())
    end = old._time(failed["at"])
    require(heartbeat["waiting_started_epoch"] > end, "post-observer wait must be disjoint")
    wall = end - old._time(plan["at"])
    initial = plan["initial_queue"]["global_external_resource_wait_seconds"]
    post = heartbeat["waiting_seconds"]
    require(
        wall >= 0
        and post >= 0
        and abs(queue["global_external_resource_wait_seconds"] - initial - post) < 0.01,
        "registered global wait decomposition changed",
    )
    used = math.ceil(max(queue["global_external_resource_wait_seconds"], initial + wall + post))
    require(used == 93466, "fixed stopped-episode wait audit changed")
    accounting = dict(
        failed_handoff_plan=plan_ref,
        failed_handoff=failure_ref,
        parent_final_wait_seconds=queue["global_external_resource_wait_seconds"],
        failed_handoff_initial_wait_seconds=initial,
        failed_handoff_elapsed_wall_seconds=wall,
        disjoint_post_handoff_wait_seconds=post,
        disjoint_post_handoff_wait=file_ref(heartbeat_path),
        inherited_resource_wait_seconds=used,
        resource_wait_budget_seconds=129600,
        original_wait_accounting_not_rewritten=True,
        original_wait_reset=False,
    )
    return authorization_ref, accounting, queue, used, pilot_ref


def inspect_interrupted_stage(directory, protocol, context, stage, *, protocol_ref):
    coordinate = context["seed"], context["arm"], context["step"]
    require(AUTHORIZED_INTERRUPTED.get(coordinate) == stage, "unregistered failed-stage recovery")
    directory = Path(directory)
    require(not (directory / "result").exists(), "a complete result cannot be retried")
    launch, exited = (checked(directory / name / "record.json") for name in ("launch", "exit"))
    require(
        all(
            row["protocol_id"] == protocol["id"]
            and row["context_id"] == context["id"]
            and row["stage"] == stage
            for row in (launch, exited)
        )
        and exited["returncode"] == (-9 if coordinate == PARTIAL_FEEDBACK_COORDINATE else 1),
        "interrupted stage identity or actual exit changed",
    )
    old._stopped(launch)
    if coordinate == DISTRIBUTION_COORDINATE:
        heartbeat = json.loads((directory / "pre_cuda_wait/status.json").read_bytes())
        require(
            heartbeat["cuda_initialized"] is False
            and heartbeat["phase"] == "STOPPED"
            and heartbeat["deadline_epoch"] == launch["deadline_epoch"],
            "only the original pre-CUDA timed-out distribution may restart",
        )
    return dict(
        protocol_scope="parent",
        protocol_ref=protocol_ref,
        protocol_id=protocol["id"],
        directory=str(directory),
        launch=entry(directory / "launch/record.json"),
        exit=entry(directory / "exit/record.json"),
        failure=entry(directory / "failure/record.json")
        if (directory / "failure/record.json").exists()
        else None,
        immediate_parent_local=True,
        accepted_complete_stage=False,
        stage=stage,
        actual_old_attempt_preserved=True,
    )


def inspect_partial_task_overlay(context, target, class_deadline_epoch):
    require(
        (context["seed"], context["arm"], context["step"]) == PARTIAL_CLASS_COORDINATE,
        "only fixed Full389/596 may supplement incomplete class",
    )
    plan = read_ref(context["task_plan"])
    tasks = {row["task_id"]: row for row in plan["tasks"]}
    expected = set(plan["assignments"][0]["task_ids"]) | set(
        plan["assignments"][1]["task_ids"][:91]
    )
    parent_ids = [task for task in plan["task_ids"] if task in expected]
    local_ids = [task for task in plan["task_ids"] if task not in expected]
    root = Path(context["task_cache_root"])
    require(
        len(parent_ids) == 277
        and len(local_ids) == 467
        and root == root.resolve()
        and root.is_dir()
        and {path.name for path in root.iterdir()}
        == {f"task{tasks[t]['index']:04d}" for t in parent_ids},
        "parent cache must preserve exactly 186 shard00 plus 91 shard01 whole tasks",
    )
    records = []
    for task in parent_ids:
        directory = root / f"task{tasks[task]['index']:04d}"
        require(
            directory == directory.resolve()
            and {path.name for path in directory.iterdir()} == {"record.json", "gradient.pt"},
            "only actual complete task tensors are resumable",
        )
        record = checked(directory / "record.json")
        require(
            record["schema"] == "v35_complete_task_gradient.v1"
            and record["complete_task"] is True
            and record["binding"] == context["task_binding"]
            and record["binding_sha256"]
            == context["math_context_id"]
            == digest(context["task_binding"])
            and record["task_plan_id"] == plan["id"]
            and record["task"] == tasks[task]
            and record["parameter_spec"] == context["parameter_spec"],
            "parent whole-task point/order/parameter binding changed",
        )
        records.append(
            dict(
                task_id=task,
                record=entry(directory / "record.json"),
                gradient=dict(
                    path=str(directory / "gradient.pt"),
                    sha256=record["gradient_sha256"],
                    bytes=record["gradient_bytes"],
                ),
                record_file_identity=old._file_identity(directory / "record.json"),
                gradient_file_identity=old._file_identity(
                    directory / "gradient.pt", size=record["gradient_bytes"]
                ),
            )
        )
    return dict(
        schema="v42_exact_277_parent_plus_467_new_tasks.v1",
        seed=389,
        arm="Full",
        step=596,
        original_context_id=context["id"],
        parent_cache_root=str(root),
        local_cache_root=str(Path(target) / "task_cache"),
        task_plan_id=plan["id"],
        binding_sha256=context["math_context_id"],
        parent_task_ids=parent_ids,
        local_task_ids=local_ids,
        allowed_new_stages=["shard01", "shard02", "shard03"],
        parent_records=records,
        parent_tasks=277,
        new_tasks=467,
        total_tasks=744,
        class_deadline_epoch=class_deadline_epoch,
        parent_tasks_recomputed=False,
        parent_records_rewritten=False,
        partial_task_rows_restorable=False,
        unfinished_task_whole_recomputation_allowed=True,
    )


def _phase_timing(context, bindings, snapshot, parent_item=None, *, class_window=None):
    """Old consumed time plus new real interval union; no phase clock reset."""
    parent_item = parent_item or {}
    inherited = parent_item.get("inherited_compute_seconds", 0)
    snapshot_used = snapshot.get("compute_seconds", 0)
    require(
        old._finite_nonnegative(inherited) and old._finite_nonnegative(snapshot_used),
        "invalid inherited/snapshot compute time",
    )
    all_intervals, local_intervals = [], []
    deadlines = dict(parent_item.get("phase_deadlines_epoch", {}))
    first = dict(parent_item.get("phase_first_launch_epoch", {}))
    for stage, binding in bindings.items():
        if binding["protocol_scope"] != "parent":
            continue
        launch, exited = read_ref(binding["launch"]), read_ref(binding["exit"])
        start, end = old._time(launch["at"]), old._time(exited["at"])
        elapsed = exited["elapsed_worker_wall_seconds"]
        require(start <= end and old._finite_nonnegative(elapsed), "invalid worker interval")
        interval = (start, max(end, start + elapsed))
        all_intervals.append(interval)
        if binding.get("immediate_parent_local", False):
            local_intervals.append(interval)
        phase = base.phase_name(context, stage)
        deadline = launch["deadline_epoch"]
        require(old._finite_nonnegative(deadline), "missing original absolute phase deadline")
        deadlines[phase] = min(deadlines.get(phase, deadline), deadline)
        first[phase] = min(first.get(phase, start), start)
    if class_window is not None:
        window = read_ref(class_window)
        require(
            (context["seed"], context["arm"], context["step"]) == previous.PARTIAL_CLASS_COORDINATE
            and window["context_id"] == context["id"]
            and window["window_seconds"] == 14400
            and window["deadline_epoch"] == window["started_epoch"] + 14400
            and window["allowed_stages"] == ["shard00", "shard01", "shard03"],
            "original bounded class supplement window changed",
        )
        # This already-authorized exception superseded only the old class
        # deadline, not any outer/wait budget. Its actual timestamp is preserved.
        deadlines["class_gradients"] = window["deadline_epoch"]
        first["class_gradients"] = window["started_epoch"]
    total = base.union_seconds(all_intervals)
    new = base.union_seconds(local_intervals)
    return dict(
        inherited_compute_seconds=math.ceil(max(snapshot_used, total, inherited + new)),
        phase_deadlines_epoch=deadlines,
        phase_first_launch_epoch=first,
        worker_interval_union_seconds=total,
        immediate_parent_worker_interval_union_seconds=new,
        earlier_inherited_compute_seconds=inherited,
        parent_compute_snapshot_seconds=snapshot_used,
        inherited_class_completion_window=class_window,
        phase_budgets_reset=False,
    )


def recovery_timing(
    context, bindings, interrupted, snapshot, parent_item=None, *, class_window=None
):
    """Keep snapshot-accounted polling time and all later interrupted work."""
    timing = _phase_timing(
        context, {**bindings, **interrupted}, snapshot, parent_item, class_window=class_window
    )
    intervals = []
    for value in interrupted.values():
        launch, exited = read_ref(value["launch"]), read_ref(value["exit"])
        start = old._time(launch["at"])
        end = max(old._time(exited["at"]), start + exited["elapsed_worker_wall_seconds"])
        intervals.append((max(start, old._time(snapshot["at"])), end))
    added = base.union_seconds([(start, end) for start, end in intervals if end > start])
    timing["inherited_compute_seconds"] = math.ceil(
        max(timing["inherited_compute_seconds"], snapshot["compute_seconds"] + added)
    )
    timing["unaccounted_interrupted_seconds_added"] = added
    return timing


def inspect_cache_view(context, bindings, parent_item=None):
    """Seal complete original-order cache ownership, including the V40 186+558 union."""
    require(set(SHARDS) <= bindings.keys(), "all four exited class shards are required")
    plan = read_ref(context["task_plan"])
    task_ids, tasks = plan["task_ids"], {row["task_id"]: row for row in plan["tasks"]}
    require(
        len(task_ids) == len(tasks) == 744
        and list(tasks) == task_ids
        and [row["index"] for row in tasks.values()] == list(range(744))
        and plan["parameter_spec"] == context["parameter_spec"],
        "complete original task order/specification required",
    )
    overlay = (parent_item or {}).get("task_cache_overlay")
    if overlay:
        require(
            (context["seed"], context["arm"], context["step"]) == previous.PARTIAL_CLASS_COORDINATE
            and overlay["original_context_id"] == context["id"]
            and overlay["parent_cache_root"] == context["task_cache_root"]
            and overlay["parent_task_ids"] == plan["assignments"][2]["task_ids"]
            and len(overlay["parent_task_ids"]) == 186
            and len(overlay["local_task_ids"]) == 558,
            "V40 complete overlay ownership changed",
        )
        sources = [
            dict(cache_root=overlay["parent_cache_root"], task_ids=overlay["parent_task_ids"]),
            dict(cache_root=overlay["local_cache_root"], task_ids=overlay["local_task_ids"]),
        ]
    else:
        sources = [dict(cache_root=context["task_cache_root"], task_ids=task_ids)]
    flattened = [task for source in sources for task in source["task_ids"]]
    require(
        len(flattened) == len(set(flattened)) == 744 and set(flattened) == set(task_ids),
        "cache sources must partition every original task exactly once",
    )
    owner, inventory = {}, []
    for source in sources:
        cache = Path(source["cache_root"])
        require(cache == cache.resolve() and cache.is_dir(), "redirected/missing cache root")
        expected = {f"task{tasks[task]['index']:04d}" for task in source["task_ids"]}
        require(
            {path.name for path in cache.iterdir()} == expected,
            "complete cache source contains missing or shadow tasks",
        )
        source["stages"] = [
            stage
            for stage in SHARDS
            if set(read_ref(bindings[stage]["result"])["task_ids"]) <= set(source["task_ids"])
        ]
        source["stage_sources"] = [
            dict(
                stage=stage,
                directory=bindings[stage]["directory"],
                protocol_ref=bindings[stage]["protocol_ref"],
                result=bindings[stage]["result"],
                exit=bindings[stage]["exit"],
            )
            for stage in source["stages"]
        ]
        for task in source["task_ids"]:
            owner[task] = str(cache)
    binding_sha = digest(context["task_binding"])
    require(binding_sha == context["math_context_id"], "actual task binding changed")
    for task in task_ids:
        directory = Path(owner[task]) / f"task{tasks[task]['index']:04d}"
        require(
            directory == directory.resolve()
            and {path.name for path in directory.iterdir()} == {"record.json", "gradient.pt"},
            "complete task must retain its exact record and actual tensor",
        )
        reference = entry(directory / "record.json")
        record = read_ref(reference)
        require(
            record["schema"] == "v35_complete_task_gradient.v1"
            and record["complete_task"] is True
            and record["binding"] == context["task_binding"]
            and record["binding_sha256"] == binding_sha
            and record["task_plan_id"] == plan["id"]
            and record["task"] == tasks[task]
            and record["parameter_spec"] == context["parameter_spec"],
            "task cache metadata changed actual point/order/parameter binding",
        )
        inventory.append(
            dict(
                task_id=task,
                cache_root=owner[task],
                record=reference,
                gradient=dict(
                    path=str(directory / "gradient.pt"),
                    sha256=record["gradient_sha256"],
                    bytes=record["gradient_bytes"],
                ),
                record_file_identity=old._file_identity(directory / "record.json"),
                gradient_file_identity=old._file_identity(
                    directory / "gradient.pt", size=record["gradient_bytes"]
                ),
            )
        )
    return dict(
        schema=CACHE_SCHEMA,
        original_context_id=context["id"],
        task_plan=context["task_plan"],
        task_plan_id=plan["id"],
        binding_sha256=binding_sha,
        task_ids=task_ids,
        cache_sources=sources,
        task_records=inventory,
        tasks=744,
        source_layout="completed_V40_overlay" if overlay else "single_complete_source",
        inherited_overlay=overlay,
        read_only=True,
        writes_allowed=False,
        tensor_contents_read=False,
        gradient_content_validation="unchanged_ProductionTaskCache_read_before_use",
    )


def _deduplicate(bindings):
    unique, semantic = {}, {}
    for binding in bindings:
        result = read_ref(binding["result"])
        key = result["context_id"], result["stage"]
        prior = semantic.setdefault(key, binding["result"])
        require(prior == binding["result"], "two accepted results for one scientific stage")
        unique[binding["result"]["path"]] = binding
    return list(unique.values())


def scientific_budget(progress, bindings, unfinished, evaluations):
    """Deduct actual unique sealed cohorts, including sampled but uncommitted outers."""
    sampled = sum(
        read_ref(row["result"]).get("new_feedback_episodes", 0)
        for row in _deduplicate(bindings)
        if Path(row["directory"]).name == "virtual_point"
    )
    pending = sum(
        read_ref(item["stage_bindings"]["virtual_point"]["result"]).get("new_feedback_episodes", 0)
        for item in unfinished
        if item["stage_bindings"]["virtual_point"]["protocol_scope"] == "parent"
    )
    require(
        0 <= pending <= sampled <= 8400
        and sampled % 700 == pending % 700 == 0
        and 8400 - sampled == progress["future_first_sampling_feedback_episodes"] - pending,
        "remaining first-sampling budget disagrees with actual unique saved cohorts",
    )
    require(sampled == 4200 and pending == 700, "fixed V42 sealed cohort accounting changed")
    unstarted = 8400 - sampled - 700
    return dict(
        legacy_snapshot_not_sampling_authority=dict(
            **{
                key: progress[key]
                for key in (
                    "pending_sealed_feedback_episodes",
                    "future_first_sampling_outers",
                    "future_first_sampling_feedback_episodes",
                )
            },
            sampling_authority=False,
            reason="original checkpoint snapshot does not enumerate production feedback payloads",
        ),
        future_first_sampling_outers=unstarted // 700,
        future_first_sampling_feedback_episodes=unstarted,
        pending_sealed_feedback_episodes=pending,
        pending_sealed_feedback_definition=(
            "complete sealed cohorts whose original outer is not yet committed; "
            "excludes the unsealed partial C-only389 step894 cohort"
        ),
        known_sealed_uncommitted_feedback_episodes=pending,
        known_sealed_uncommitted_coordinates=[dict(seed=251, arm="Full", step=894, episodes=700)],
        original_reused_feedback_episodes=2100,
        original_first_sampling_feedback_episodes=8400,
        already_generated_first_sampling_feedback_episodes=sampled,
        already_generated_uncommitted_feedback_episodes=pending,
        reserved_partial_feedback_episodes=700,
        completed_partial_feedback_episodes=450,
        remaining_partial_feedback_episodes=250,
        first_sampling_unstarted_feedback_episodes=unstarted,
        one_unknown_provider_request_reexecution_authorized=True,
        remaining_new_feedback_episodes=8400 - sampled - 450,
        remaining_endpoint_answers=(9 - len(evaluations)) * 1147,
        total_endpoint_answers=10323,
    )


def inspect_parent_recovery(
    newroot, parentroot, *, authorization_record=None, authorization_body=None
):
    root, parent = Path(newroot).resolve(), Path(parentroot).resolve()
    require(root == parent.parent / "recovery_03", "independent V42 root required")
    require(not (root / "inheritance/record.json").exists(), "migration already registered")
    protocol_ref = entry(parent / "protocol/record.json")
    protocol = read_ref(protocol_ref)
    authorization_ref, wait_accounting, queue, wait, pilot_ref = _validate_parent_restart(
        root, parent, protocol, authorization_record, authorization_body
    )
    require(wait < 129600, "authorized cumulative resource wait exhausted")
    baseline = read_ref(protocol["inheritance"])
    require(
        baseline["schema"] == previous.SCHEMA and baseline["new_root"] == str(parent),
        "V40 original inheritance changed",
    )
    progress_path = parent / "actual_final_progress/record.json"
    progress = checked(progress_path)
    require(
        progress["schema"] == "v37_actual_B_CPU_state_snapshot.v1"
        and progress["endpoint_scores_or_answers_read"] is False
        and progress["original_state_or_feedback_modified"] is False,
        "successful handoff lacks unchanged actual-state CPU snapshot",
    )
    remaining, outers = progress["remaining_physical_updates"], progress["remaining_outers"]
    require(
        type(remaining) is int
        and 0 <= remaining <= 5810
        and type(outers) is int
        and 0 <= outers <= 15
        and progress["completed_physical_updates"] + remaining == 11622
        and progress["completed_outers"] + outers == 24,
        "original nine-model scientific dose changed",
    )
    accepted, accepted_outer = 5810 - remaining, 15 - outers
    require(
        queue["accepted_new_optimizer_updates"] == accepted
        and queue["accepted_new_outer_updates"] == accepted_outer,
        "cumulative controller counters disagree with actual committed states",
    )
    coordinates = {(seed, arm) for seed in SEEDS for arm in ARM_KEYS}
    latest = {(row["seed"], row["arm"]): row for row in progress["arms"]}
    require(
        set(latest) == coordinates and len(progress["arms"]) == 9, "nine-model coverage changed"
    )
    require(
        {(row["seed"], row["arm"]) for row in queue["completed_training_coordinates"]}
        == {key for key, row in latest.items() if row["step"] == 1490},
        "completed training set differs from actual endpoint checkpoints",
    )
    checkpoints = [
        checkpoint_metadata(row["checkpoint"], coordinate=(row["seed"], row["arm"], row["step"]))
        for row in progress["arms"]
    ]
    inherited, completed, unused, stages, deferred = [], [], [], [], []
    context_by_id = {}
    for item in baseline["completed_contexts"]:
        _, context, _ = _actual_context(item["context"])
        context_by_id[context["id"]] = context
    for item in baseline["context_inheritances"]:
        _, context, _ = _actual_context(item["original_context"])
        context_by_id[context["id"]] = context
    # Historical completed work remains independently bound to its V38 owner.
    earlier_protocol_ref = baseline["parent_protocol"]
    earlier_protocol = read_ref(earlier_protocol_ref)
    for binding in baseline["all_parent_stage_bindings"]:
        result = read_ref(binding["result"])
        if result["stage"] == "generate":
            coordinate = next(
                (seed, arm)
                for seed, arm in coordinates
                if result["context_id"] == f"evaluation:{seed}:{ARM_KEYS[arm]}"
            )
            context = dict(id=result["context_id"], seed=coordinate[0], arm=coordinate[1])
        else:
            context = context_by_id[result["context_id"]]
        plan = read_ref(context["task_plan"]) if context.get("due_outer") else None
        inspected = inspect_stage(
            binding["directory"],
            earlier_protocol,
            context,
            result["stage"],
            plan,
            protocol_ref=earlier_protocol_ref,
        )
        require(
            inspected is not None and inspected["result"] == binding["result"],
            "historical accepted result binding changed",
        )
        stages.append(inspected)
    historical_train = [
        read_ref(row["result"])
        for row in _deduplicate(stages)
        if Path(row["directory"]).name == "train"
    ]
    require(
        sum(row["actual_optimizer_steps"] for row in historical_train) == 1667
        and sum(int(row["outer_committed"]) for row in historical_train) == 4,
        "historical 1667 optimizer and four outer commits require their actual accepted results",
    )
    for record in sorted((parent / "contexts").glob("seed*/*/step*/context/record.json")):
        directory = record.parent.parent.resolve()
        origin_ref, context, origin = _actual_context(entry(record))
        coordinate = context["seed"], context["arm"]
        require(coordinate in coordinates, "foreign coordinate")
        parent_item = previous.inherited_context(directory, protocol)
        require(
            previous.resolve_origin_context(directory, protocol) == origin,
            "V40 scientific alias differs from registered source",
        )
        plan = read_ref(context["task_plan"]) if context["due_outer"] else None
        bindings, interrupted = {}, {}
        for stage in STAGES:
            source = previous.stage_directory(directory, protocol, stage)
            old_binding = parent_item["stage_bindings"][stage] if parent_item else None
            from_earlier = old_binding is not None and old_binding["protocol_scope"] == "parent"
            owner_ref = parent_item["parent_protocol"] if from_earlier else protocol_ref
            if from_earlier:
                require(
                    not (directory / stage).exists(),
                    "inherited stage has a duplicate local attempt",
                )
            if (
                context["seed"],
                context["arm"],
                context["step"],
            ) in AUTHORIZED_INTERRUPTED and stage == AUTHORIZED_INTERRUPTED[
                (context["seed"], context["arm"], context["step"])
            ]:
                require(not from_earlier, "explicit interrupted stage must belong to V40")
                interrupted[stage] = inspect_interrupted_stage(
                    source, protocol, context, stage, protocol_ref=protocol_ref
                )
                continue
            binding = inspect_stage(
                source, read_ref(owner_ref), context, stage, plan, protocol_ref=owner_ref
            )
            if binding is not None:
                if from_earlier:
                    require(
                        binding["result"] == old_binding["result"]
                        and binding["exit"] == old_binding["exit"],
                        "V40 inherited stage source changed",
                    )
                binding["immediate_parent_local"] = not from_earlier
                bindings[stage] = binding
                stages.append(binding)
        if "train" in bindings:
            completion = checked(directory / "completion/record.json")
            require(
                completion["context_id"] == context["id"]
                and completion["protocol_id"] == protocol["id"]
                and completion["result"] == bindings["train"]["result"],
                "completed context lacks actual controller acceptance",
            )
            completed.append(
                dict(
                    context=entry(record),
                    original_context=origin_ref,
                    context_id=context["id"],
                    completion=entry(directory / "completion/record.json"),
                    stage_bindings=bindings,
                )
            )
            continue
        require(
            context["checkpoint"] == latest[coordinate]["checkpoint"],
            "unfinished point is not latest actual state",
        )
        if not bindings:
            unused.append(
                dict(
                    context=entry(record),
                    seed=coordinate[0],
                    arm=coordinate[1],
                    reason="no_stage_dispatched_recreate_from_same_actual_checkpoint",
                )
            )
            continue
        require(
            context["due_outer"] is True
            and (
                set(SHARDS) <= bindings.keys()
                or (
                    (context["seed"], context["arm"], context["step"]) == PARTIAL_CLASS_COORDINATE
                    and set(bindings) == {"shard00"}
                    and set(interrupted) == {"shard01"}
                )
            ),
            "only registered complete class or exact interrupted Full389 class may recover",
        )
        require(
            "replay_R3" not in bindings or "virtual_point" in bindings,
            "replay lacks sealed virtual point",
        )
        require(
            "distribution" not in bindings or "replay_R3" in bindings,
            "distribution lacks complete replay",
        )
        target = root / directory.relative_to(parent)
        require(not (target / "context/record.json").exists(), "new alias already exists")
        cache_view = (
            inspect_cache_view(context, bindings, parent_item)
            if set(SHARDS) <= bindings.keys()
            else None
        )
        snapshot_path = directory / "queue/status.json"
        snapshot = json.loads(snapshot_path.read_bytes())
        require(
            snapshot["context_id"] == context["id"] and snapshot["protocol_id"] == protocol["id"],
            "foreign per-context timing snapshot",
        )
        for child in snapshot.get("active_children", []):
            historical = {**bindings, **interrupted}
            require(child["stage"] in historical, "stale child missing actual exited attempt")
            launch = read_ref(historical[child["stage"]]["launch"])
            require(
                all(child[key] == launch[key] for key in ("pid", "birth", "gpu_index", "gpu_uuid")),
                "stale child differs from actual exited worker",
            )
            old._stopped(launch)
        window_path = directory / "class_recovery_window/record.json"
        window = entry(window_path) if window_path.exists() else None
        if (parent_item or {}).get("task_cache_overlay"):
            require(window is not None, "completed V40 supplement lacks its original class window")
        timing = recovery_timing(
            context, bindings, interrupted, snapshot, parent_item, class_window=window
        )
        task_overlay = (
            inspect_partial_task_overlay(
                context, target, timing["phase_deadlines_epoch"]["class_gradients"]
            )
            if (context["seed"], context["arm"], context["step"]) == PARTIAL_CLASS_COORDINATE
            else None
        )
        feedback_resume = None
        if (context["seed"], context["arm"], context["step"]) == PARTIAL_FEEDBACK_COORDINATE:
            import finqa_v42_feedback_resume

            feedback_resume = finqa_v42_feedback_resume.inspect_partial_feedback(directory)
            feedback_resume["new_feedback_base_root"] = str(target / "feedback_resume_view")
        phase_overrides = {}
        if (context["seed"], context["arm"], context["step"]) == DISTRIBUTION_COORDINATE:
            phase_overrides["distribution"] = dict(
                window_seconds=7200,
                starts_at_first_dispatch=True,
                only_authorized_coordinate=[251, "Full", 894],
                original_deadline_epoch=timing["phase_deadlines_epoch"]["distribution"],
                authorization=authorization_ref,
                original_outer_budget_reset=False,
            )
        expected_compute = {
            DISTRIBUTION_COORDINATE: 45784,
            PARTIAL_FEEDBACK_COORDINATE: 29611,
            PARTIAL_CLASS_COORDINATE: 10541,
        }
        require(
            timing["inherited_compute_seconds"]
            == expected_compute[(context["seed"], context["arm"], context["step"])],
            "fixed interrupted outer timing changed",
        )
        require(
            timing["inherited_compute_seconds"] < protocol["outer_compute_budget_seconds"],
            "inherited outer compute budget exhausted",
        )
        old._verify_refs(context["sources"])
        old._verify_refs(context["execution_binding"])
        old._verify_refs(context["feedback"], deferred=deferred)
        checkpoint_metadata(context["checkpoint"], coordinate=(*coordinate, context["step"]))
        for stage in STAGES:
            bindings.setdefault(
                stage, dict(protocol_scope="current", directory=str(target / stage))
            )
        inherited.append(
            dict(
                seed=context["seed"],
                arm=context["arm"],
                step=context["step"],
                original_context=origin_ref,
                original_context_id=context["id"],
                origin_context_directory=str(origin),
                immediate_parent_context=entry(record),
                immediate_parent_context_directory=str(directory),
                new_context_directory=str(target),
                parent_context_snapshot=file_ref(snapshot_path),
                parent_protocol=protocol_ref,
                stage_bindings=bindings,
                task_plan=context["task_plan"],
                task_cache_root=context["task_cache_root"],
                task_cache_view=cache_view,
                task_cache_overlay=task_overlay,
                feedback_resume=feedback_resume,
                interrupted_stage_bindings=interrupted,
                phase_deadline_overrides=phase_overrides,
                distribution_recovery_window=bool(phase_overrides),
                task_cache_inventory=dict(
                    tasks=744 if cache_view else 277,
                    metadata_digest=digest(
                        cache_view["task_records"] if cache_view else task_overlay["parent_records"]
                    ),
                    tensor_contents_read=False,
                ),
                **timing,
            )
        )
    require(
        len({(row["seed"], row["arm"]) for row in inherited}) == len(inherited),
        "multiple unfinished scientific contexts for one coordinate",
    )
    current_train = [read_ref(row["stage_bindings"]["train"]["result"]) for row in completed]
    require(
        baseline["accepted_new_optimizer_updates"] == 1667
        and baseline["accepted_new_outer_updates"] == 4
        and 1667 + sum(row["actual_optimizer_steps"] for row in current_train) == accepted
        and 4 + sum(int(row["outer_committed"]) for row in current_train) == accepted_outer,
        "historical plus actual V40 commits do not cover cumulative state progress",
    )
    earlier_eval = {(row["seed"], row["arm"]): row for row in baseline["completed_evaluations"]}
    evaluations = []
    for seed, arm in sorted(coordinates):
        directory = parent / f"evaluations/seed{seed}_{ARM_KEYS[arm]}"
        context = dict(id=f"evaluation:{seed}:{ARM_KEYS[arm]}", seed=seed, arm=arm)
        binding = inspect_stage(
            directory / "generate", protocol, context, "generate", protocol_ref=protocol_ref
        )
        seal = (
            Path(protocol["evaluation_root"])
            / f"models/seed{seed}/{ARM_KEYS[arm]}/whole_test_seal/record.json"
        )
        registered = dict(seed=seed, arm=arm) in queue["completed_evaluation_coordinates"]
        if registered:
            value = checked(seal)
            require(
                (value["seed"], value["arm"], value["denominator"]) == (seed, arm, 1147)
                and value["all_generation_complete"] is True
                and value["all_provider_calls_settled"] is True
                and latest[(seed, arm)]["step"] == 1490,
                "endpoint seal is not a complete final-model seal",
            )
            if (seed, arm) in earlier_eval:
                require(
                    binding is None and earlier_eval[(seed, arm)]["whole_test_seal"] == entry(seal),
                    "previously sealed endpoint was regenerated or changed",
                )
                saved = earlier_eval[(seed, arm)]["stage_binding"]
                binding = next(
                    (row for row in stages if saved and row["result"] == saved["result"]), None
                )
                require(
                    saved is None or binding is not None,
                    "historical endpoint worker binding missing",
                )
            else:
                require(
                    binding is not None
                    and read_ref(binding["result"])["whole_test_seal"] == entry(seal),
                    "new sealed endpoint lacks actual exited generation worker",
                )
                stages.append(binding)
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
                binding is None and not seal.exists() and (seed, arm) not in earlier_eval,
                "unaccepted endpoint cannot be regenerated",
            )
    stages = _deduplicate(stages)
    return dict(
        schema=SCHEMA,
        at=datetime.now(timezone.utc).isoformat(),
        new_root=str(root),
        parent_root=str(parent),
        parent_protocol=protocol_ref,
        parent_implementation=entry(parent / "implementation/record.json"),
        historical_inheritance=protocol["inheritance"],
        parent_pause=entry(parent / "failure/record.json"),
        parent_pilot_acceptance=pilot_ref,
        parent_pilot_repeated=False,
        recovery_authorization=authorization_ref,
        failed_handoff=wait_accounting["failed_handoff"],
        resource_wait_accounting=wait_accounting,
        resource_wait_budget_seconds=129600,
        parent_queue=file_ref(parent / "queue/status.json"),
        actual_final_progress=entry(progress_path),
        context_inheritances=inherited,
        completed_contexts=completed,
        historical_completed_contexts=baseline["completed_contexts"],
        unused_contexts=unused,
        completed_evaluations=evaluations,
        latest_checkpoints=checkpoints,
        all_parent_stage_bindings=stages,
        accepted_new_optimizer_updates=accepted,
        accepted_new_outer_updates=accepted_outer,
        inherited_resource_wait_seconds=wait,
        remaining_optimizer_updates=remaining,
        remaining_outer_updates=outers,
        remaining_scientific_budget=scientific_budget(progress, stages, inherited, evaluations),
        deferred_feedback_content_verification=deferred,
        parent_contexts_rewritten=False,
        parent_tensors_copied=False,
        tensor_contents_read=False,
        completed_stages_redispatched=False,
        authorized_interrupted_stages_registered=True,
        automatic_retry=False,
        new_sampling_calls=0,
        replayed_responses=0,
        optimizer_updates=0,
        original_budgets_reset=False,
        explicitly_authorized_resource_wait_extension_seconds=43200,
        explicitly_authorized_distribution_window_seconds=7200,
        endpoint_scores_or_answers_read=False,
    )


def initialize_parent_recovery(newroot, parentroot, *, authorization_record=None):
    root = Path(newroot).resolve()
    value = publish(
        root / "inheritance/record.json",
        inspect_parent_recovery(root, parentroot, authorization_record=authorization_record),
    )
    for item in value["context_inheritances"]:
        publish(
            Path(item["new_context_directory"]) / "context/record.json",
            dict(
                schema=ALIAS_SCHEMA,
                **{
                    key: item[key]
                    for key in (
                        "new_context_directory",
                        "original_context",
                        "original_context_id",
                        "origin_context_directory",
                    )
                },
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
        "wrong V42 inheritance episode",
    )
    return value


def inherited_context(newctx, plan):
    directory = str(Path(newctx).resolve())
    rows = [
        row
        for row in _inheritance(plan)["context_inheritances"]
        if row["new_context_directory"] == directory
    ]
    require(len(rows) <= 1, "duplicate inherited context")
    return rows[0] if rows else None


def resolve_origin_context(newctx, plan):
    directory = Path(newctx).resolve()
    require(
        directory.is_relative_to(Path(plan["output_root"]).resolve() / "contexts"),
        "foreign context directory",
    )
    value, item = checked(directory / "context/record.json"), inherited_context(directory, plan)
    if item is None:
        require(
            value["schema"] == "v37_actual_production_context.v1"
            and value["run_root"] == value["outer_root"] == str(directory),
            "new context must own actual point",
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
        "per-stage parent context alias changed",
    )
    reference, context, origin = _actual_context(item["original_context"])
    require(
        reference == item["original_context"]
        and context["id"] == item["original_context_id"]
        and str(origin) == item["origin_context_directory"],
        "original scientific context changed",
    )
    return origin


def stage_directory(newctx, plan, stage):
    require(stage in STAGES, "unknown scientific stage")
    directory = Path(newctx).resolve()
    resolve_origin_context(directory, plan)
    item = inherited_context(directory, plan)
    if item is None:
        return directory / stage
    binding = item["stage_bindings"][stage]
    source = Path(binding["directory"])
    require(source == source.resolve() and source.name == stage, "redirected stage source")
    if binding["protocol_scope"] == "current":
        require(source == directory / stage, "new stage outside current output root")
    else:
        require(
            binding["protocol_scope"] == "parent"
            and read_ref(binding["protocol_ref"])["id"] == binding["protocol_id"]
            and binding["result"] == entry(source / "result/record.json")
            and binding["exit"] == entry(source / "exit/record.json"),
            "independent stage owner/source changed",
        )
    return source


def task_cache_view_binding(newctx, plan):
    directory = Path(newctx).resolve()
    resolve_origin_context(directory, plan)
    item = inherited_context(directory, plan)
    if item is None:
        return None
    value = item["task_cache_view"]
    if value is None:
        require(item.get("task_cache_overlay") is not None, "missing registered cache ownership")
        return None
    require(
        value["schema"] == CACHE_SCHEMA
        and value["original_context_id"] == item["original_context_id"]
        and value["read_only"] is True
        and value["writes_allowed"] is False
        and value["tasks"] == 744
        and all(item["stage_bindings"][stage]["protocol_scope"] == "parent" for stage in SHARDS),
        "only complete immutable class caches may be inherited",
    )
    return value


def require_upstream(newctx, context, plan, stage, control):
    directory = Path(newctx).resolve()
    origin, item = resolve_origin_context(directory, plan), inherited_context(directory, plan)
    require(context == checked(origin / "context/record.json"), "scientific context relabelled")
    require(
        stage_directory(directory, plan, stage) == directory / stage, "completed stage cannot rerun"
    )
    required = {
        "virtual_point": SHARDS,
        "replay_R3": ("virtual_point",),
        "distribution": (*SHARDS, "virtual_point", "replay_R3"),
        "train": ("distribution",) if context["due_outer"] else (),
    }.get(stage, ())
    task_plan = read_ref(context["task_plan"]) if context["due_outer"] else None
    for previous_stage in required:
        source = stage_directory(directory, plan, previous_stage)
        binding = item["stage_bindings"][previous_stage] if item else None
        inherited = binding is not None and binding["protocol_scope"] == "parent"
        owner = read_ref(binding["protocol_ref"]) if inherited else plan
        result, exited = (
            checked(source / "result/record.json"),
            checked(source / "exit/record.json"),
        )
        require(
            result["context_id"] == exited["context_id"] == context["id"]
            and result["protocol_id"] == exited["protocol_id"] == owner["id"]
            and result["stage"] == exited["stage"] == previous_stage
            and exited["returncode"] == 0
            and exited["stop_requested"] is False,
            "upstream actual point/protocol/exit changed",
        )
        control.check_result(owner, previous_stage, result, task_plan)
        if previous_stage in ("virtual_point", "replay_R3", "distribution"):
            reference, _ = old._payload(source, context, previous_stage)
            require(
                result["payload"] == reference
                and (not inherited or binding["payload"] == reference),
                "upstream actual saved value changed",
            )


def task_cache_overlay_binding(newctx, plan):
    resolve_origin_context(newctx, plan)
    item = inherited_context(newctx, plan)
    value = item.get("task_cache_overlay") if item else None
    if value is None:
        return task_cache_view_binding(newctx, plan)
    if value is not None:
        require(
            (value["seed"], value["arm"], value["step"]) == PARTIAL_CLASS_COORDINATE
            and value["original_context_id"] == item["original_context_id"]
            and len(value["parent_task_ids"]) == 277
            and len(value["local_task_ids"]) == 467,
            "fixed task supplement ownership changed",
        )
    return value


def feedback_resume_binding(newctx, plan):
    resolve_origin_context(newctx, plan)
    item = inherited_context(newctx, plan)
    value = item.get("feedback_resume") if item else None
    if value is not None:
        require(
            (item["seed"], item["arm"], item["step"]) == PARTIAL_FEEDBACK_COORDINATE,
            "partial feedback recovery escaped its registered coordinate",
        )
    return value
