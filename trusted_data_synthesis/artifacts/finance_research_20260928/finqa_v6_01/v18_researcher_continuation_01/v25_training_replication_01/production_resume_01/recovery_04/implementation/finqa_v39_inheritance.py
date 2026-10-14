"""Metadata-only, read-only inheritance after an explicitly authorized handoff.

This is not a retry mechanism. Every dispatched parent stage must have a real
successful exit; unfinished attempts, failed stages and live processes reject
migration. Tensor bytes and large feedback cohorts remain under the original
worker's same-point validation, and are never copied or relabelled here.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import finqa_v38_inheritance as old

require, checked, entry, read_ref = old.require, old.checked, old.entry, old.read_ref
publish, file_ref, digest = old.publish, old.file_ref, old.digest
SHARDS = old.SHARDS
STAGES = (*SHARDS, "virtual_point", "replay_R3", "distribution", "train")
SCHEMA = "v39_read_only_parent_migration.v1"
ALIAS_SCHEMA = "v39_parent_context_alias.v1"
ARM_KEYS = {"Static": "static", "C-only": "c_only", "Full": "full"}
SEEDS = (137, 251, 389)


def union_seconds(intervals):
    merged = []
    for start, end in sorted(intervals):
        require(
            old._finite_nonnegative(start) and old._finite_nonnegative(end) and start <= end,
            "invalid parent elapsed interval",
        )
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return sum(end - start for start, end in merged)


def phase_name(context, stage):
    if stage in SHARDS:
        return "class_gradients"
    if stage == "virtual_point":
        return (
            "virtual_existing"
            if context["feedback"]["mode"] == "sealed_existing"
            else "virtual_first_sampling"
        )
    return stage


def timing_from_stages(context, protocol, stage_bindings, snapshot):
    """Carry actual worker-time union and original phase absolute deadlines."""
    intervals, phases = [], {}
    for stage, binding in stage_bindings.items():
        if binding["protocol_scope"] != "parent":
            continue
        launch, exited = read_ref(binding["launch"]), read_ref(binding["exit"])
        start, end = old._time(launch["at"]), old._time(exited["at"])
        require(start <= end, "parent exit predates launch")
        elapsed = exited["elapsed_worker_wall_seconds"]
        require(old._finite_nonnegative(elapsed), "invalid parent worker elapsed duration")
        # Include the measured monotonic duration even if the UTC clock moved.
        intervals.append((start, max(end, start + elapsed)))
        phase = phase_name(context, stage)
        limit = protocol["stage_limits_seconds"][phase]
        recorded = launch["deadline_epoch"]
        require(old._finite_nonnegative(recorded), "parent stage deadline missing")
        row = phases.setdefault(phase, dict(first_launch_epoch=start, deadlines=[]))
        row["first_launch_epoch"] = min(row["first_launch_epoch"], start)
        row["deadlines"].append(recorded)
        row["limit_seconds"] = limit
    compute = snapshot.get("compute_seconds", 0)
    require(old._finite_nonnegative(compute), "invalid parent compute snapshot")
    deadlines = {
        phase: min(row["first_launch_epoch"] + row["limit_seconds"], *row["deadlines"])
        for phase, row in phases.items()
    }
    return dict(
        inherited_compute_seconds=math.ceil(max(compute, union_seconds(intervals))),
        phase_deadlines_epoch=deadlines,
        phase_first_launch_epoch={key: row["first_launch_epoch"] for key, row in phases.items()},
        worker_interval_union_seconds=union_seconds(intervals),
        parent_compute_snapshot_seconds=compute,
        phase_budgets_reset=False,
    )


def checkpoint_metadata(reference):
    """Verify the bounded state record and stat the Tensor; do not hash Tensor."""
    directory = Path(reference["path"]).resolve()
    require(directory == Path(reference["path"]), "redirected training checkpoint")
    record = read_ref(reference["record"])
    require(
        Path(reference["record"]["path"]) == directory / "record.json"
        and Path(reference["state"]["path"]) == directory / "state.pt"
        and record["state_sha256"] == reference["state"]["sha256"]
        and all(record[key] == reference[key] for key in ("seed", "arm", "step", "phase"))
        and record["actual_state_digest"] == reference["actual_state_digest"],
        "actual checkpoint record binding changed",
    )
    return dict(reference=reference, tensor_identity=old._file_identity(directory / "state.pt"))


def inspect_stage(directory, protocol, context, stage, task_plan=None):
    """A nonempty attempted stage must be COMPLETE and physically exited."""
    directory = Path(directory)
    markers = ("launch", "attempt", "result", "exit", "failure", "payload")
    if not any((directory / name).exists() for name in markers):
        return None
    require(not (directory / "failure").exists(), "failed stage cannot be migrated or retried")
    require(
        all((directory / name / "record.json").is_file() for name in ("launch", "result", "exit")),
        "partial or unexited stage cannot be migrated",
    )
    launch, result, exited = (
        checked(directory / name / "record.json") for name in ("launch", "result", "exit")
    )
    require(
        all(row["protocol_id"] == protocol["id"] for row in (launch, result, exited))
        and all(row["context_id"] == context["id"] for row in (launch, result, exited))
        and all(row["stage"] == stage for row in (launch, result, exited))
        and result["status"] == "COMPLETE"
        and result["model_released"] is True
        and exited["returncode"] == 0
        and exited["stop_requested"] is False,
        "parent stage is incomplete, failed or bound to another protocol/context",
    )
    old._stopped(launch)
    require(
        result["gpu_index"] in (3, 4, 5, 7)
        and result["gpu_index"] == launch["gpu_index"]
        and result["gpu_uuid"]
        == launch["gpu_uuid"]
        == protocol["gpu_uuids"][str(result["gpu_index"])],
        "parent GPU identity changed",
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
        result["API_calls"] == 0 and (stage == "virtual_point" or result["scoring_calls"] == 0),
        "unauthorized API or scoring outside frozen virtual-point reward",
    )
    require(stage == "train" or result["optimizer_steps"] == 0, "optimizer outside train")
    require(stage == "replay_R3" or result["replayed_responses"] == 0, "replay outside R3")
    require(
        stage in ("virtual_point", "generate") or result["new_sampling_calls"] == 0,
        "sampling outside its phase",
    )
    if stage not in ("train", "generate"):
        require(
            result["model_optimizer_rng_buffers_unchanged"] is True,
            "real state changed outside train",
        )
    if stage in SHARDS:
        tasks = task_plan["assignments"][SHARDS.index(stage)]["task_ids"]
        require(
            result["task_ids"] == tasks
            and result["task_count"] == len(tasks)
            and result["class_task_calls"] + len(result["reused_task_ids"]) == len(tasks)
            and len(set(result["reused_task_ids"])) == len(result["reused_task_ids"])
            and set(result["reused_task_ids"]) <= set(tasks),
            "parent whole-task coverage changed",
        )
    if stage in ("virtual_point", "replay_R3", "distribution"):
        require(result["denominator"] == 700, "feedback denominator changed")
    if stage == "virtual_point":
        expected = 0 if context["feedback"]["mode"] == "sealed_existing" else 700
        require(
            result["feedback_mode"] == context["feedback"]["mode"]
            and result["new_feedback_episodes"] == expected,
            "original feedback reuse/new-sampling dose changed",
        )
    if stage == "replay_R3":
        require(
            result["complete_replay"] is True
            and result["current_point_only"] is True
            and result["replayed_responses"] == result["response_count"],
            "parent actual response replay incomplete or cross-point",
        )
    if stage == "generate":
        require(
            result["session_count"] == result["new_generation_episodes"] == 1147
            and result["new_sampling_calls"] == result["actual_response_calls"]
            and result["private_test_scoring"] is False,
            "parent endpoint generation dose or score barrier changed",
        )
    binding = dict(
        protocol_scope="parent",
        protocol_id=protocol["id"],
        directory=str(directory.resolve()),
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
            commits["next_checkpoint"]["reference"]["step"] == result["committed_step"]
            and all(
                (row["reference"]["seed"], row["reference"]["arm"])
                == (context["seed"], context["arm"])
                for row in commits.values()
            ),
            "actual training commit coordinate changed",
        )
        binding["actual_training_commits"] = commits
    return binding


def _read_context(directory):
    value = checked(directory / "context/record.json")
    if value["schema"] == old.ALIAS_SCHEMA:
        # The V38 first-point alias is already complete. Do not interpret it as
        # a new V38 scientific context or re-label its six V37 source stages.
        original = read_ref(value["original_context"])
        require(original["id"] == value["original_context_id"], "V38 pilot alias changed")
        require(
            (directory / "completion/record.json").exists(),
            "incomplete old pilot is outside handoff scope",
        )
        return original, True
    require(
        value["schema"] == "v37_actual_production_context.v1"
        and value["run_root"] == value["outer_root"] == str(directory),
        "parent context coordinate changed",
    )
    return value, False


def _validate_handoff(parent, protocol, handoff_record):
    reference = handoff_record if isinstance(handoff_record, dict) else entry(handoff_record)
    handoff = read_ref(reference)
    require(
        handoff["status"] == "COMPLETE"
        and handoff["parent_root"] == str(parent)
        and handoff["parent_protocol_id"] == protocol["id"]
        and handoff["controller_exited"] is True
        and handoff["children_exited"] is True,
        "successful authorized parent handoff is required",
    )
    queue_path = parent / "queue/status.json"
    queue = json.loads(queue_path.read_bytes())
    pause_path = parent / "failure/record.json"
    pause = read_ref(handoff["parent_pause"])
    expected_stop = dict(
        phase="PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME",
        error_type="DurablePause",
        error="explicit safe stop requested",
        stop_error=None,
        actual_progress_audit_error=None,
        automatic_retry=False,
        completed_task_response_and_step_artifacts_preserved=True,
    )
    require(
        handoff["parent_pause"] == file_ref(pause_path)
        or handoff["parent_pause"] == entry(pause_path),
        "handoff pause reference must bind the untouched parent stop record",
    )
    require(
        all(
            queue.get(key) == expected and pause.get(key) == expected
            for key, expected in expected_stop.items()
        )
        and queue["active_children"] == []
        and queue["protocol_id"] == pause["protocol_id"] == protocol["id"]
        and queue["pilot_accepted"] is True,
        "parent must have only the authorized clean DurablePause, "
        "no scientific failure or active children",
    )
    require(handoff["parent_final_queue"] == queue, "parent queue changed after successful handoff")
    old._stopped(checked(parent / "launch_01/record.json"))
    wait = handoff["global_resource_wait_seconds"]
    require(
        old._finite_nonnegative(wait) and wait >= queue["global_external_resource_wait_seconds"],
        "handoff omitted already consumed external-resource wait",
    )
    return reference, handoff, queue, math.ceil(wait)


def inspect_parent_migration(newroot, parentroot, handoff_record):
    """Build registration metadata only after the old controller really exits."""
    root, parent = Path(newroot).resolve(), Path(parentroot).resolve()
    require(
        root == parent.parent / "gpu6_resume_01", "independent authorized migration root required"
    )
    require(not (root / "inheritance/record.json").exists(), "migration already registered")
    protocol = checked(parent / "protocol/record.json")
    require(
        protocol["schema"] == "v38_same_point_admission_recovery_protocol.v1", "expected V38 parent"
    )
    handoff_ref, handoff, queue, wait = _validate_handoff(parent, protocol, handoff_record)
    require(
        wait < protocol["resource_wait_budget_seconds"], "original resource wait budget exhausted"
    )
    progress_path = parent / "actual_final_progress/record.json"
    progress = checked(progress_path)
    require(
        handoff["actual_progress"] in (entry(progress_path), file_ref(progress_path)),
        "handoff actual committed-state audit changed",
    )
    require(
        progress["schema"] == "v37_actual_B_CPU_state_snapshot.v1"
        and progress["endpoint_scores_or_answers_read"] is False
        and progress["original_state_or_feedback_modified"] is False,
        "actual CPU state audit missing or changed",
    )
    remaining_updates, remaining_outers = (
        progress["remaining_physical_updates"],
        progress["remaining_outers"],
    )
    require(
        type(remaining_updates) is int
        and 0 <= remaining_updates <= 5810
        and type(remaining_outers) is int
        and 0 <= remaining_outers <= 15
        and progress["completed_physical_updates"] + remaining_updates == 11622
        and progress["completed_outers"] + remaining_outers == 24,
        "original nine-model optimizer/outer dose changed",
    )
    actual_updates, actual_outers = 5810 - remaining_updates, 15 - remaining_outers
    require(
        queue["accepted_new_optimizer_updates"] == actual_updates
        and queue["accepted_new_outer_updates"] == actual_outers,
        "accepted counters differ from actual committed checkpoint audit",
    )
    coordinates = {(s, a) for s in SEEDS for a in ARM_KEYS}
    require(
        {(row["seed"], row["arm"]) for row in progress["arms"]} == coordinates
        and len(progress["arms"]) == 9,
        "actual nine-model coordinate coverage changed",
    )
    latest = {(row["seed"], row["arm"]): row for row in progress["arms"]}
    require(
        {(row["seed"], row["arm"]) for row in queue["completed_training_coordinates"]}
        == {coordinate for coordinate, row in latest.items() if row["step"] == 1490},
        "completed training coordinates differ from actual endpoints",
    )
    checkpoints = [
        dict(seed=row["seed"], arm=row["arm"], **checkpoint_metadata(row["checkpoint"]))
        for row in progress["arms"]
    ]
    inherited, completed, unused, all_stage_refs = [], [], [], []
    deferred_feedback = []
    for record in sorted((parent / "contexts").glob("seed*/*/step*/context/record.json")):
        directory = record.parent.parent.resolve()
        context, pilot_alias = _read_context(directory)
        coordinate = context["seed"], context["arm"]
        require(coordinate in coordinates, "unregistered parent coordinate")
        task_plan = read_ref(context["task_plan"]) if context["due_outer"] else None
        bindings = {}
        for stage in STAGES:
            binding = inspect_stage(directory / stage, protocol, context, stage, task_plan)
            if binding is not None:
                bindings[stage] = binding
                all_stage_refs.append(binding)
        if "train" in bindings:
            completion = checked(directory / "completion/record.json")
            require(
                completion["context_id"] == context["id"]
                and completion["protocol_id"] == protocol["id"]
                and completion["result"] == bindings["train"]["result"],
                "completed context has no controller acceptance",
            )
            completed.append(
                dict(
                    context=entry(record),
                    context_id=context["id"],
                    completion=entry(directory / "completion/record.json"),
                    stage_bindings=bindings,
                    pilot_alias=pilot_alias,
                )
            )
            continue
        require(not pilot_alias, "unfinished V38 pilot cannot be migrated")
        require(
            context["checkpoint"] == latest[coordinate]["checkpoint"],
            "unfinished context is not the latest actual parameter point",
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
            context["due_outer"] is True,
            "partially attempted train is not a safe migration boundary",
        )
        require(set(bindings).issubset(STAGES[:-1]), "invalid unfinished stage set")
        require(
            set(SHARDS) <= bindings.keys(),
            "partial class phase cannot migrate: all four parent shards must complete",
        )
        if any(s in bindings for s in ("virtual_point", "replay_R3", "distribution")):
            require(
                set(SHARDS) <= bindings.keys(),
                "downstream phase without four complete class shards",
            )
        if "replay_R3" in bindings:
            require("virtual_point" in bindings, "replay without sealed virtual point")
        if "distribution" in bindings:
            require("replay_R3" in bindings, "distribution without complete response replay")
        target = root / directory.relative_to(parent)
        require(not (target / "context/record.json").exists(), "migration alias already exists")
        for stage in STAGES:
            bindings.setdefault(
                stage, dict(protocol_scope="current", directory=str(target / stage))
            )
        queue_path = directory / "queue/status.json"
        snapshot = json.loads(queue_path.read_bytes())
        require(
            snapshot["context_id"] == context["id"] and snapshot["protocol_id"] == protocol["id"],
            "parent context timing snapshot is foreign",
        )
        # Context snapshots may lag a real exit; immutable checked exits and
        # the final empty global queue are authoritative, not stale labels.
        for child in snapshot.get("active_children", []):
            require(
                child.get("stage") in bindings
                and bindings[child["stage"]]["protocol_scope"] == "parent",
                "snapshot contains an unaccepted stage",
            )
            launch = read_ref(bindings[child["stage"]]["launch"])
            require(
                all(child[key] == launch[key] for key in ("pid", "birth", "gpu_index", "gpu_uuid")),
                "stale snapshot child differs from the checked exited worker",
            )
            old._stopped(launch)
        timing = timing_from_stages(context, protocol, bindings, snapshot)
        require(
            timing["inherited_compute_seconds"] < protocol["outer_compute_budget_seconds"],
            "original outer time exhausted",
        )
        old._verify_refs(context["sources"])
        old._verify_refs(context["execution_binding"])
        old._verify_refs(context["feedback"], deferred=deferred_feedback)
        checkpoint_metadata(context["checkpoint"])
        cache = Path(context["task_cache_root"])
        require(cache == directory / "task_cache", "parent cache directory binding changed")
        inventory = [
            old._file_identity(cache / f"task{index:04d}" / name)
            for index in range(len(task_plan["task_ids"]))
            for name in ("record.json", "gradient.pt")
        ]
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
                **timing,
                task_cache_inventory=dict(
                    tasks=len(task_plan["task_ids"]),
                    metadata_digest=digest(inventory),
                    tensor_contents_read=False,
                ),
            )
        )
    require(
        len({(x["seed"], x["arm"]) for x in inherited}) == len(inherited),
        "multiple unfinished contexts per actual coordinate",
    )
    accepted_train_results = [
        read_ref(row["stage_bindings"]["train"]["result"]) for row in completed
    ]
    require(
        sum(row["actual_optimizer_steps"] for row in accepted_train_results) == actual_updates
        and sum(int(row["outer_committed"]) for row in accepted_train_results) == actual_outers,
        "accepted parent training commits do not cover actual cumulative updates",
    )
    evaluations = []
    for coordinate in sorted(coordinates):
        seed, arm = coordinate
        directory = parent / f"evaluations/seed{seed}_{ARM_KEYS[arm]}"
        context = dict(id=f"evaluation:{seed}:{ARM_KEYS[arm]}", seed=seed, arm=arm)
        binding = inspect_stage(directory / "generate", protocol, context, "generate")
        seal = (
            Path(protocol["evaluation_root"])
            / f"models/seed{seed}/{ARM_KEYS[arm]}/whole_test_seal/record.json"
        )
        registered = dict(seed=seed, arm=arm) in queue["completed_evaluation_coordinates"]
        if registered:
            value = checked(seal)
            require(
                value["seed"] == seed
                and value["arm"] == arm
                and value["denominator"] == 1147
                and value["all_generation_complete"] is True
                and value["all_provider_calls_settled"] is True,
                "endpoint seal incomplete or from another coordinate",
            )
            require(
                latest[coordinate]["step"] == 1490, "endpoint seal before final real training state"
            )
            require(
                binding is not None or (seed, arm) in ((137, "Static"), (251, "Static")),
                "new endpoint seal lacks exited generation worker",
            )
            if binding:
                require(
                    read_ref(binding["result"])["whole_test_seal"] == entry(seal),
                    "generation result seal differs",
                )
                all_stage_refs.append(binding)
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
                binding is None and not seal.exists(),
                "unaccepted endpoint generation cannot be repeated",
            )
    first_sampling = sum(
        read_ref(row["result"]).get("new_feedback_episodes", 0)
        for row in all_stage_refs
        if Path(row["directory"]).name == "virtual_point"
    )
    pending_sampled = sum(
        read_ref(row["stage_bindings"]["virtual_point"]["result"]).get("new_feedback_episodes", 0)
        for row in inherited
        if row["stage_bindings"]["virtual_point"]["protocol_scope"] == "parent"
    )
    require(
        0 <= first_sampling <= 8400
        and first_sampling % 700 == 0
        and 8400 - first_sampling
        == progress["future_first_sampling_feedback_episodes"] - pending_sampled,
        "remaining first-sampling budget disagrees with actual saved cohorts",
    )
    return dict(
        schema=SCHEMA,
        at=datetime.now(timezone.utc).isoformat(),
        new_root=str(root),
        parent_root=str(parent),
        parent_protocol=entry(parent / "protocol/record.json"),
        parent_implementation=entry(parent / "implementation/record.json"),
        parent_pause=entry(parent / "failure/record.json"),
        handoff=handoff_ref,
        parent_queue=file_ref(parent / "queue/status.json"),
        actual_final_progress=entry(progress_path),
        context_inheritances=inherited,
        completed_contexts=completed,
        unused_contexts=unused,
        completed_evaluations=evaluations,
        latest_checkpoints=checkpoints,
        all_parent_stage_bindings=all_stage_refs,
        accepted_new_optimizer_updates=actual_updates,
        accepted_new_outer_updates=actual_outers,
        inherited_resource_wait_seconds=wait,
        remaining_optimizer_updates=remaining_updates,
        remaining_outer_updates=remaining_outers,
        remaining_scientific_budget=dict(
            **{
                key: progress[key]
                for key in (
                    "pending_sealed_feedback_episodes",
                    "future_first_sampling_outers",
                    "future_first_sampling_feedback_episodes",
                )
            },
            original_reused_feedback_episodes=2100,
            original_first_sampling_feedback_episodes=8400,
            already_generated_first_sampling_feedback_episodes=first_sampling,
            already_generated_uncommitted_feedback_episodes=pending_sampled,
            remaining_new_feedback_episodes=8400 - first_sampling,
            remaining_endpoint_answers=(9 - len(evaluations)) * 1147,
            total_endpoint_answers=10323,
        ),
        deferred_feedback_content_verification=deferred_feedback,
        parent_contexts_rewritten=False,
        parent_tensors_copied=False,
        tensor_contents_read=False,
        failed_attempts_retried=False,
        new_sampling_calls=0,
        replayed_responses=0,
        optimizer_updates=0,
        budgets_reset_or_enlarged=False,
        endpoint_scores_or_answers_read=False,
    )


def initialize_parent_migration(newroot, parentroot, handoff_record):
    root = Path(newroot).resolve()
    value = publish(
        root / "inheritance/record.json", inspect_parent_migration(root, parentroot, handoff_record)
    )
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
        "migration belongs to another episode",
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
        "context outside migration root",
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
        "migration alias binding changed",
    )
    require(
        read_ref(item["original_context"])["id"] == item["original_context_id"],
        "parent context changed",
    )
    return Path(item["origin_context_directory"])


def stage_directory(newctx, plan, stage):
    require(stage in STAGES, "unknown scientific stage")
    directory = Path(newctx).resolve()
    origin = resolve_origin_context(directory, plan)
    item = inherited_context(directory, plan)
    if item is None:
        return directory / stage
    binding = item["stage_bindings"][stage]
    require(binding["protocol_scope"] in ("parent", "current"), "unknown stage protocol owner")
    expected = (origin if binding["protocol_scope"] == "parent" else directory) / stage
    require(binding["directory"] == str(expected), "inherited stage directory changed")
    return expected


def require_upstream(newctx, context, plan, stage, control):
    directory = Path(newctx).resolve()
    origin, item = resolve_origin_context(directory, plan), inherited_context(directory, plan)
    require(
        context == checked(origin / "context/record.json"),
        "actual scientific context was relabelled",
    )
    require(
        stage_directory(directory, plan, stage) == directory / stage,
        "completed parent stage must not be rerun",
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
