"""Same-point recovery inheritance with uncapped time accounting, never blind retries.

Metadata registration leaves mathematical tensors to the unchanged strict readers.
Old time limits remain historical evidence; this episode's explicit authorization
removes time gates without resetting accumulated work or resource-wait accounting.
"""

from __future__ import annotations

import copy
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import finqa_v42_inheritance as previous

base, old = previous.base, previous.old
require, checked, entry, read_ref = old.require, old.checked, old.entry, old.read_ref
publish, file_ref, digest = old.publish, old.file_ref, old.digest
SHARDS, STAGES = previous.SHARDS, previous.STAGES
checkpoint_metadata = previous.checkpoint_metadata
_actual_context = previous._actual_context
SCHEMA = "v43_verified_same_point_recovery_inheritance.v1"
ALIAS_SCHEMA = "v43_per_stage_original_context_alias.v1"
CACHE_SCHEMA = "v41_complete_read_only_task_cache_view.v1"
PARTIAL_CACHE_SCHEMA = "v43_same_point_partial_task_cache_union.v1"


def _authorization(root, reference=None, body=None):
    require(reference is None or body is None, "cannot mix preview and sealed authority")
    if body is not None:
        value, ref = body, dict(preview_only=True, authorization_body_digest=digest(body))
    else:
        ref = (
            reference
            if isinstance(reference, dict)
            else entry(reference or root / "authorization/record.json")
        )
        value = read_ref(ref)
    require(
        bool(value.get("user_consent"))
        and value.get("time_limits_removed") is True
        and value.get("automatic_recovery_authorized") is True
        and value.get("unknown_feedback_retry_allowed") is False,
        "explicit time-waiver and safe-only automatic-recovery authority required",
    )
    return ref


def _stamp():
    return datetime.now(timezone.utc).isoformat()


def _interrupted_binding(directory, protocol, context_id, stage):
    directory = Path(directory)
    launch, exited = (checked(directory / name / "record.json") for name in ("launch", "exit"))
    require(
        all(
            value["protocol_id"] == protocol["id"]
            and value["context_id"] == context_id
            and value["stage"] == stage
            for value in (launch, exited)
        ),
        "interrupted process point/protocol binding changed",
    )
    old._stopped(launch)
    return dict(
        protocol_scope="parent",
        protocol_ref=entry(Path(protocol["output_root"]) / "protocol/record.json"),
        protocol_id=protocol["id"],
        directory=str(directory),
        stage=stage,
        launch=entry(directory / "launch/record.json"),
        exit=entry(directory / "exit/record.json"),
        failure=entry(directory / "failure/record.json")
        if (directory / "failure/record.json").exists()
        else None,
        immediate_parent_local=True,
        accepted_complete_stage=False,
    )


def _charged_time(prior, directory, interrupted):
    snapshot_path = Path(directory) / "queue/status.json"
    snapshot = read_ref(file_ref(snapshot_path))
    intervals = []
    for binding in interrupted.values():
        launch, exited = read_ref(binding["launch"]), read_ref(binding["exit"])
        start = old._time(launch["at"])
        end = max(old._time(exited["at"]), start + exited["elapsed_worker_wall_seconds"])
        intervals.append((start, end))
    whole = base.union_seconds(intervals)
    tail = base.union_seconds(
        [
            (max(start, old._time(snapshot["at"])), end)
            for start, end in intervals
            if end > max(start, old._time(snapshot["at"]))
        ]
    )
    return dict(
        inherited_compute_seconds=math.ceil(max(prior + whole, snapshot["compute_seconds"] + tail)),
        earlier_inherited_compute_seconds=prior,
        parent_compute_snapshot_seconds=snapshot["compute_seconds"],
        immediate_parent_worker_interval_union_seconds=whole,
        unaccounted_interrupted_seconds_added=tail,
        parent_context_snapshot=file_ref(snapshot_path),
    )


def _cache_union(context, target, prior_overlay):
    plan = read_ref(context["task_plan"])
    rows = copy.deepcopy(prior_overlay["parent_records"])
    for row in rows:
        row["cache_root"] = prior_overlay["parent_cache_root"]
        require(entry(row["record"]["path"]) == row["record"], "parent whole-task metadata changed")
        require(
            old._file_identity(row["gradient"]["path"], size=row["gradient"]["bytes"])
            == row["gradient_file_identity"],
            "parent whole-task tensor identity changed",
        )
    require(
        not Path(prior_overlay["local_cache_root"]).exists(), "V42 unexpectedly sealed new tasks"
    )
    return dict(
        schema=PARTIAL_CACHE_SCHEMA,
        original_context_id=context["id"],
        seed=context["seed"],
        arm=context["arm"],
        step=context["step"],
        task_plan=context["task_plan"],
        task_plan_id=plan["id"],
        binding_sha256=context["math_context_id"],
        task_ids=plan["task_ids"],
        parent_task_ids=prior_overlay["parent_task_ids"],
        local_task_ids=prior_overlay["local_task_ids"],
        task_records=rows,
        cache_sources=[
            dict(
                cache_root=prior_overlay["parent_cache_root"],
                task_ids=prior_overlay["parent_task_ids"],
            )
        ],
        local_cache_root=str(target / "task_cache"),
        allowed_new_stages=prior_overlay["allowed_new_stages"],
        parent_tasks=len(rows),
        new_tasks=len(prior_overlay["local_task_ids"]),
        total_tasks=len(plan["task_ids"]),
        parent_tasks_recomputed=False,
        historical_class_deadline_epoch=prior_overlay["class_deadline_epoch"],
        class_deadline_epoch=None,
        time_limits_removed=True,
    )


def inspect_parent_recovery(
    newroot, parentroot, *, authorization_record=None, authorization_body=None
):
    root, parent = Path(newroot).resolve(), Path(parentroot).resolve()
    if parent.name != "recovery_03":
        return inspect_automatic_recovery(
            root,
            parent,
            authorization_record=authorization_record,
            authorization_body=authorization_body,
        )
    require(root == parent.parent / "recovery_04", "fixed independent initial V43 root required")
    require(not (root / "inheritance/record.json").exists(), "initial recovery already registered")
    authority = _authorization(root, authorization_record, authorization_body)
    protocol = checked(parent / "protocol/record.json")
    require(
        protocol["schema"] == "v42_explicit_bounded_same_point_recovery_protocol.v1",
        "initial V43 must inherit the actual stopped V42",
    )
    prior = read_ref(protocol["inheritance"])
    require(
        prior["schema"] == previous.SCHEMA and prior["new_root"] == str(parent),
        "V42 inheritance changed",
    )
    closeout = checked(parent / "closeout_01/record.json")
    queue = read_ref(file_ref(parent / "queue/status.json"))
    failure = checked(parent / "failure/record.json")
    require(
        queue["phase"] == failure["phase"] == closeout["status"] == "STOPPED_FAILURE_NO_RETRY"
        and queue["active_children"] == []
        and failure["stop_error"] is None
        and failure["actual_progress_audit_error"] is None,
        "V42 must be physically stopped with an actual final state snapshot",
    )
    old._stopped(checked(parent / "launch_01/record.json"))
    require(
        closeout["feedback"]["new_provider_calls"]
        == closeout["feedback"]["new_complete_episodes"]
        == 0
        and closeout["feedback"]["new_model_call_intents"] == 0
        and closeout["feedback"]["retained_complete_episodes"] == 450
        and closeout["class_tasks"]["new_complete_tasks"] == 0
        and closeout["class_tasks"]["parent_complete_tasks"] == 277,
        "initial repair cannot discard new provider calls or complete tasks",
    )
    for reference in closeout["feedback"]["new_unknown_episode_events"]:
        require(
            read_ref(reference)["kind"] == "episode_started",
            "unknown provider call cannot be reissued",
        )
    progress = checked(parent / "actual_final_progress/record.json")
    initial = read_ref(protocol["initial_state_snapshot"])
    require(
        progress["arms"] == initial["arms"]
        and progress["remaining_physical_updates"] == 2355
        and progress["remaining_outers"] == 7,
        "V42 must have no new optimizer/outer commits to use this initial repair",
    )
    newitems = []
    expected = {(251, "Full", 894): 45931, (389, "C-only", 894): 29728, (389, "Full", 596): 10688}
    for source in prior["context_inheritances"]:
        item = copy.deepcopy(source)
        context = read_ref(item["original_context"])
        directory = Path(item["new_context_directory"])
        target = root / directory.relative_to(parent)
        coordinate = context["seed"], context["arm"], context["step"]
        require(coordinate in expected, "initial recovery scope changed")
        interrupted = {}
        for stage, binding in item["stage_bindings"].items():
            if binding["protocol_scope"] == "parent":
                require(
                    entry(Path(binding["directory"]) / "result/record.json") == binding["result"]
                    and entry(Path(binding["directory"]) / "exit/record.json") == binding["exit"],
                    "inherited successful stage changed",
                )
                old._stopped(read_ref(binding["launch"]))
            else:
                if (directory / stage / "launch/record.json").exists():
                    require(
                        not (directory / stage / "result/record.json").exists(),
                        "unexpected V42 completion",
                    )
                    interrupted[stage] = _interrupted_binding(
                        directory / stage, protocol, context["id"], stage
                    )
                item["stage_bindings"][stage] = dict(
                    protocol_scope="current", directory=str(target / stage)
                )
        timing = _charged_time(item["inherited_compute_seconds"], directory, interrupted)
        require(
            timing["inherited_compute_seconds"] == expected[coordinate],
            "V42 interrupted time changed",
        )
        item.update(timing)
        item["historical_interrupted_stage_bindings"] = [
            source.get("interrupted_stage_bindings", {}),
            interrupted,
        ]
        item["interrupted_stage_bindings"] = interrupted
        item["historical_phase_deadlines_epoch"] = copy.deepcopy(source["phase_deadlines_epoch"])
        item["historical_phase_deadline_overrides"] = copy.deepcopy(
            source["phase_deadline_overrides"]
        )
        item["phase_deadlines_epoch"] = {}
        item["phase_first_launch_epoch"] = {}
        item["phase_deadline_overrides"] = {}
        item["distribution_recovery_window"] = False
        item["time_limits_removed"] = True
        if coordinate == (251, "Full", 894):
            item["historical_distribution_window"] = entry(
                directory / "distribution_recovery_window/record.json"
            )
        item["immediate_parent_context"] = entry(directory / "context/record.json")
        item["immediate_parent_context_directory"] = str(directory)
        item["new_context_directory"] = str(target)
        item["parent_protocol"] = entry(parent / "protocol/record.json")
        if source.get("task_cache_overlay") is not None:
            item["task_cache_overlay"] = _cache_union(context, target, source["task_cache_overlay"])
        if item.get("feedback_resume") is not None:
            item["feedback_resume"]["new_feedback_base_root"] = str(target / "feedback_resume_view")
        item["replay_resume"] = None
        newitems.append(item)
    wait = math.ceil(queue["global_external_resource_wait_seconds"])
    require(
        wait == closeout["next_inherited_resource_wait_seconds"] == 93720, "V42 final wait changed"
    )
    value = copy.deepcopy(prior)
    value.pop("id", None)
    value.update(
        schema=SCHEMA,
        at=_stamp(),
        new_root=str(root),
        parent_root=str(parent),
        parent_protocol=entry(parent / "protocol/record.json"),
        parent_implementation=entry(parent / "implementation/record.json"),
        historical_inheritance=protocol["inheritance"],
        parent_pause=entry(parent / "failure/record.json"),
        parent_failure=entry(parent / "failure/record.json"),
        parent_closeout=entry(parent / "closeout_01/record.json"),
        parent_queue=file_ref(parent / "queue/status.json"),
        actual_final_progress=entry(parent / "actual_final_progress/record.json"),
        recovery_authorization=authority,
        context_inheritances=newitems,
        inherited_resource_wait_seconds=wait,
        resource_wait_budget_seconds=None,
        outer_compute_budget_seconds=None,
        time_limits_removed=True,
        original_budgets_reset=False,
        original_accounting_reset=False,
        original_deadlines_retained_as_historical_evidence=True,
        automatic_recovery_authorized=True,
        initial_repair_of_known_zero_call_guard_failure=True,
    )
    return value


def _publish_aliases(root, value):
    sealed = publish(root / "inheritance/record.json", value)
    for item in sealed["context_inheritances"]:
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
    return sealed


def initialize_parent_recovery(newroot, parentroot, *, authorization_record=None):
    root = Path(newroot).resolve()
    return _publish_aliases(
        root, inspect_parent_recovery(root, parentroot, authorization_record=authorization_record)
    )


def _inheritance(plan):
    value = read_ref(plan["inheritance"])
    require(
        value["schema"] == SCHEMA and value["new_root"] == str(Path(plan["output_root"]).resolve()),
        "wrong V43 inheritance episode",
    )
    return value


def inherited_context(newctx, plan):
    rows = [
        row
        for row in _inheritance(plan)["context_inheritances"]
        if row["new_context_directory"] == str(Path(newctx).resolve())
    ]
    require(len(rows) <= 1, "duplicate inherited scientific context")
    return rows[0] if rows else None


def resolve_origin_context(newctx, plan):
    directory = Path(newctx).resolve()
    require(
        directory.is_relative_to(Path(plan["output_root"]).resolve() / "contexts"),
        "foreign context path",
    )
    alias = checked(directory / "context/record.json")
    item = inherited_context(directory, plan)
    if item is None:
        require(
            alias["schema"] == "v37_actual_production_context.v1"
            and alias["run_root"] == alias["outer_root"] == str(directory),
            "fresh context must own actual point",
        )
        return directory
    require(
        alias["schema"] == ALIAS_SCHEMA
        and alias["inheritance"] == plan["inheritance"]
        and all(
            alias[key] == item[key]
            for key in (
                "new_context_directory",
                "original_context",
                "original_context_id",
                "origin_context_directory",
            )
        ),
        "original scientific alias binding changed",
    )
    reference, context, origin = _actual_context(item["original_context"])
    require(
        reference == item["original_context"]
        and context["id"] == item["original_context_id"]
        and str(origin) == item["origin_context_directory"],
        "original scientific point changed",
    )
    return origin


def stage_directory(newctx, plan, stage):
    require(stage in STAGES, "unknown stage")
    directory = Path(newctx).resolve()
    resolve_origin_context(directory, plan)
    item = inherited_context(directory, plan)
    if item is None:
        return directory / stage
    binding = item["stage_bindings"][stage]
    source = Path(binding["directory"])
    require(source == source.resolve() and source.name == stage, "redirected stage")
    if binding["protocol_scope"] == "current":
        require(source == directory / stage, "current stage escaped attempt")
    else:
        require(
            read_ref(binding["protocol_ref"])["id"] == binding["protocol_id"]
            and entry(source / "result/record.json") == binding["result"]
            and entry(source / "exit/record.json") == binding["exit"],
            "inherited stage owner changed",
        )
    return source


def task_cache_overlay_binding(newctx, plan):
    resolve_origin_context(newctx, plan)
    item = inherited_context(newctx, plan)
    if item is None:
        return None
    return item.get("task_cache_overlay") or item.get("task_cache_view")


def task_cache_view_binding(newctx, plan):
    value = task_cache_overlay_binding(newctx, plan)
    return value if value is not None and value["schema"] == CACHE_SCHEMA else None


def feedback_resume_binding(newctx, plan):
    resolve_origin_context(newctx, plan)
    item = inherited_context(newctx, plan)
    return item.get("feedback_resume") if item else None


def replay_resume_binding(newctx, plan):
    resolve_origin_context(newctx, plan)
    item = inherited_context(newctx, plan)
    return item.get("replay_resume") if item else None


def require_upstream(newctx, context, plan, stage, control):
    directory = Path(newctx).resolve()
    origin, item = resolve_origin_context(directory, plan), inherited_context(directory, plan)
    require(context == checked(origin / "context/record.json"), "scientific point relabelled")
    require(
        stage_directory(directory, plan, stage) == directory / stage, "complete stage cannot rerun"
    )
    required = {
        "virtual_point": SHARDS,
        "replay_R3": ("virtual_point",),
        "distribution": (*SHARDS, "virtual_point", "replay_R3"),
        "train": ("distribution",) if context["due_outer"] else (),
    }.get(stage, ())
    task_plan = read_ref(context["task_plan"]) if context["due_outer"] else None
    for prior in required:
        source = stage_directory(directory, plan, prior)
        binding = item["stage_bindings"][prior] if item else None
        inherited = binding is not None and binding["protocol_scope"] == "parent"
        owner = read_ref(binding["protocol_ref"]) if inherited else plan
        result, exited = (
            checked(source / "result/record.json"),
            checked(source / "exit/record.json"),
        )
        require(
            result["context_id"] == exited["context_id"] == context["id"]
            and result["protocol_id"] == exited["protocol_id"] == owner["id"]
            and exited["returncode"] == 0
            and exited["stop_requested"] is False,
            "upstream actual point/owner/exit changed",
        )
        control.check_result(owner, prior, result, task_plan)
        if prior in ("virtual_point", "replay_R3", "distribution"):
            reference, _ = old._payload(source, context, prior)
            require(
                result["payload"] == reference
                and (not inherited or binding["payload"] == reference),
                "saved upstream mathematical value changed",
            )


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
            and result["new_feedback_episodes"] + result.get("inherited_feedback_episodes", 0)
            == expected,
            "same-point feedback ownership or dose changed",
        )
    if stage == "replay_R3":
        require(
            result["complete_replay"] is True and result["current_point_only"] is True,
            "actual cumulative response replay is incomplete",
        )
        if result.get("restored_completed_responses", 0):
            require(
                result["restored_completed_responses"] == result["inherited_response_count"]
                and result["actual_new_response_calls"] == result["replayed_responses"]
                and result["inherited_response_count"] + result["replayed_responses"]
                == result["response_count"],
                "resumed replay cumulative and new response counts differ",
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


def _observed_physical_resource_failure(value):
    resources = value.get("resources") or {}
    if resources.get("limits_unchanged") is not True:
        return False
    return any(
        row.get("allocated_pass") is False
        or row.get("free_pass") is False
        or (row.get("host") or {}).get("rss_pass") is False
        or (row.get("host") or {}).get("available_pass") is False
        for row in resources.get("observations", [])
    )


def validate_safe_recovery(parentroot):
    """Only documented resource/stop failures with actual exit may be continued.

    Native feedback or endpoint generation interrupted after CUDA is deliberately
    unsupported: no generic consumer may silently retry an unknown response.
    """
    parent = Path(parentroot).resolve()
    evidence = []
    try:
        protocol = checked(parent / "protocol/record.json")
        require(
            protocol["schema"] == "v43_explicit_no_deadline_supervised_protocol.v1"
            and protocol["output_root"] == str(parent),
            "foreign automatic-recovery parent",
        )
        queue = read_ref(file_ref(parent / "queue/status.json"))
        failure = checked(parent / "failure/record.json")
        require(
            queue["active_children"] == []
            and queue["phase"] == failure["phase"]
            and failure["phase"]
            in ("STOPPED_FAILURE_NO_RETRY", "PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME")
            and failure["stop_error"] is None
            and failure["actual_progress_audit_error"] is None,
            "parent pool is not fully stopped with valid actual-state audit",
        )
        old._stopped(checked(parent / "launch_01/record.json"))
        progress = checked(parent / "actual_final_progress/record.json")
        require(
            progress["endpoint_scores_or_answers_read"] is False
            and progress["original_state_or_feedback_modified"] is False,
            "actual checkpoint audit is not read-only",
        )
        evidence.extend(
            entry(parent / name / "record.json")
            for name in ("protocol", "failure", "launch_01", "actual_final_progress")
        )
        trigger = failure.get("error", "").lower()
        if (
            "explicit safe stop requested" in trigger
            or "user stop" in trigger
            or "manual stop" in trigger
        ):
            return dict(allowed=False, reason="manual_stop_is_terminal", evidence_refs=evidence)
        classes = []
        failures = 0
        for path in sorted(parent.glob("contexts/seed*/*/step*/*/launch/record.json")) + sorted(
            parent.glob("evaluations/*/generate/launch/record.json")
        ):
            directory = path.parent.parent
            launch, exited = checked(path), checked(directory / "exit/record.json")
            require(
                launch["protocol_id"] == exited["protocol_id"] == protocol["id"]
                and launch["context_id"] == exited["context_id"]
                and launch["stage"] == exited["stage"],
                "worker ownership mismatch",
            )
            old._stopped(launch)
            evidence.extend((entry(path), entry(directory / "exit/record.json")))
            if (
                (directory / "result/record.json").exists()
                and exited["returncode"] == 0
                and exited["stop_requested"] is False
            ):
                continue
            failures += 1
            failure_path = directory / "failure/record.json"
            require(failure_path.exists(), "unsupported_unexplained_worker_exit")
            stopped = checked(failure_path)
            evidence.append(entry(failure_path))
            require(
                stopped["protocol_id"] == protocol["id"]
                and stopped["context_id"] == launch["context_id"]
                and stopped["stage"] == launch["stage"],
                "failed-worker identity mismatch",
            )
            cause = stopped.get("error", "").lower()
            if any(
                word in cause
                for word in (
                    "checksum",
                    "binding",
                    "mismatch",
                    "numerical",
                    "nonfinite",
                    "nan",
                    "explicit reexecution",
                    "wrong point",
                    "changed",
                )
            ):
                return dict(
                    allowed=False,
                    reason="numerical_or_binding_failure_requires_user",
                    evidence_refs=evidence,
                )
            resource = stopped.get("error_type") in (
                "OutOfMemoryError",
                "AdmissionStopped",
                "TailStopRequested",
                "ReplayPaused",
            ) or any(
                word in cause
                for word in (
                    "out of memory",
                    "memory limit",
                    "memory reserve",
                    "rss limit",
                    "host memory",
                    "safe stop",
                    "resource wait",
                    "disk space",
                )
            )
            if (
                stopped.get("error_type") == "TailMemoryError"
                or cause == "production host ram envelope failed"
            ):
                resource = _observed_physical_resource_failure(stopped)
            if stopped.get("error_type") == "AdmissionError" and cause in (
                "host available ram below 96 gib reserve",
                "worker rss limit exceeded",
                "worker lifetime rss above stage limit",
            ):
                resource = True
            require(resource, "unsupported_nonresource_failure_requires_user")
            heartbeat = directory / "pre_cuda_wait/status.json"
            pre_cuda = False
            if heartbeat.exists():
                value = checked(heartbeat)
                pre_cuda = (
                    value.get("cuda_initialized") is False
                    and value.get("phase") in ("STOPPED", "FAILED", "TIMED_OUT")
                    and stopped.get("resources") is None
                )
            stage = launch["stage"]
            if stage in ("virtual_point", "generate") and not pre_cuda:
                return dict(
                    allowed=False,
                    reason="unsupported_partial_generation_or_unknown_feedback_requires_user",
                    evidence_refs=evidence,
                )
            classes.append(
                dict(
                    directory=str(directory),
                    stage=stage,
                    pre_cuda=pre_cuda,
                    recovery_kind="pre_cuda_no_scientific_call"
                    if pre_cuda
                    else "whole_task_cache"
                    if stage in SHARDS
                    else "ordered_response_checkpoint"
                    if stage == "replay_R3"
                    else "actual_committed_training_state"
                    if stage == "train"
                    else "saved_distribution_inputs",
                )
            )
        require(
            failures or any(word in trigger for word in ("resource", "memory", "disk")),
            "unsupported_controller_failure_without_safe_worker_boundary",
        )
        return dict(
            allowed=True,
            reason="resource_failure_with_verified_exits_and_durable_boundary_consumers",
            evidence_refs=evidence,
            interrupted_stages=classes,
            unknown_feedback_retry=False,
            numerical_failures_retried=False,
        )
    except (OSError, KeyError, TypeError, ValueError) as error:
        return dict(
            allowed=False,
            reason="unsafe_or_unsupported_recovery: " + str(error),
            evidence_refs=evidence,
        )


def _automatic_cache(context, source_directory, target, prior_item, bindings):
    """Partition exact whole-task tensor ownership across any number of attempts."""
    plan = read_ref(context["task_plan"])
    tasks = {row["task_id"]: row for row in plan["tasks"]}
    index = {f"task{row['index']:04d}": task for task, row in tasks.items()}
    older = (prior_item or {}).get("task_cache_overlay") or (prior_item or {}).get(
        "task_cache_view"
    )
    roots = (
        [Path(row["cache_root"]) for row in older["cache_sources"]]
        if older
        else [Path(context["task_cache_root"])]
    )
    if older and older.get("local_cache_root"):
        roots.append(Path(older["local_cache_root"]))
    roots.append(Path(source_directory) / "task_cache")
    inventory, owners, sources = {}, {}, []
    for cache in dict.fromkeys(roots):
        if not cache.exists():
            continue
        require(
            cache == cache.resolve() and cache.is_dir() and not cache.is_symlink(),
            "redirected task source",
        )
        selected = []
        for directory in sorted(cache.iterdir()):
            require(
                directory.name in index and directory.is_dir() and directory == directory.resolve(),
                "unrecognized/incomplete task-cache entry",
            )
            task = index[directory.name]
            require(
                task not in owners
                and {path.name for path in directory.iterdir()} == {"record.json", "gradient.pt"},
                "task cache shadow or incomplete whole task",
            )
            record = checked(directory / "record.json")
            require(
                record["complete_task"] is True
                and record["binding"] == context["task_binding"]
                and record["binding_sha256"]
                == context["math_context_id"]
                == digest(context["task_binding"])
                and record["task_plan_id"] == plan["id"]
                and record["task"] == tasks[task]
                and record["parameter_spec"] == context["parameter_spec"],
                "task point/order/parameter mismatch",
            )
            owners[task] = str(cache)
            inventory[task] = dict(
                task_id=task,
                cache_root=str(cache),
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
            selected.append(task)
        if selected:
            sources.append(
                dict(
                    cache_root=str(cache),
                    task_ids=[task for task in plan["task_ids"] if task in set(selected)],
                )
            )
    parent_ids = [task for task in plan["task_ids"] if task in owners]
    local_ids = [task for task in plan["task_ids"] if task not in owners]
    complete_shards = [stage for stage in SHARDS if stage in bindings]
    for stage in complete_shards:
        require(
            set(plan["assignments"][SHARDS.index(stage)]["task_ids"]) <= set(parent_ids),
            "successful shard lost its actual task tensors",
        )
    record = dict(
        original_context_id=context["id"],
        seed=context["seed"],
        arm=context["arm"],
        step=context["step"],
        task_plan=context["task_plan"],
        task_plan_id=plan["id"],
        binding_sha256=context["math_context_id"],
        task_ids=plan["task_ids"],
        task_records=[inventory[task] for task in parent_ids],
        cache_sources=sources,
    )
    if set(complete_shards) == set(SHARDS):
        require(
            len(parent_ids) == 744 and not local_ids, "complete class requires all actual tensors"
        )
        return dict(
            record, schema=CACHE_SCHEMA, tasks=744, read_only=True, writes_allowed=False
        ), None
    pending = [stage for stage in SHARDS if stage not in complete_shards]
    receipts = [
        stage
        for stage in pending
        if set(plan["assignments"][SHARDS.index(stage)]["task_ids"]) <= set(parent_ids)
    ]
    return None, dict(
        record,
        schema=PARTIAL_CACHE_SCHEMA,
        parent_task_ids=parent_ids,
        local_task_ids=local_ids,
        local_cache_root=str(Path(target) / "task_cache"),
        allowed_new_stages=pending,
        cache_only_receipt_stages=receipts,
        parent_tasks=len(parent_ids),
        new_tasks=len(local_ids),
        total_tasks=744,
        time_limits_removed=True,
        class_deadline_epoch=None,
    )


def _replay_prefix(directory, context, virtual_binding, old_resume=None):
    directory = Path(directory)
    candidates = sorted(
        path for path in (directory / "checkpoints").glob("response[0-9]*") if path.is_dir()
    )
    if not candidates:
        return old_resume
    require(
        all(
            re.fullmatch(r"response\d{6}", path.name) and (path / "record.json").exists()
            for path in candidates
        ),
        "incomplete response checkpoint directory",
    )
    source = candidates[-1]
    record = checked(source / "record.json")
    binding, cursor = record["binding"], record["cursor"]
    virtual = read_ref(virtual_binding["result"])
    require(
        record["schema"] == "v19_response_boundary_checkpoint.v1"
        and record["response_prefix_complete"] is True
        and record["no_feedback_generation"] is True
        and record["optimizer_steps_performed"] == 0
        and source.name == f"response{cursor:06d}"
        and 0 <= cursor <= binding["response_count"]
        and (not record["full_replay_complete"] or cursor == binding["response_count"])
        and binding["execution_profile_id"] == context["id"]
        and binding["point_id"] == virtual["point_id"]
        and binding["response_count"] == virtual["response_count"]
        and binding["denominator"] == 700
        and binding["gradient_length_normalized"] is False,
        "response checkpoint point/cohort/cursor mismatch",
    )
    if old_resume is not None:
        require(
            cursor >= old_resume["inherited_response_count"] and binding == old_resume["binding"],
            "response checkpoint rewound or changed binding",
        )
    return dict(
        checkpoint=entry(source / "record.json"),
        state=dict(path=str(source / "state.pt"), sha256=record["state_sha256"]),
        checkpoint_directory=str(source),
        tensor_identity=old._file_identity(source / "state.pt"),
        binding=binding,
        inherited_response_count=cursor,
        total_response_count=binding["response_count"],
        remaining_response_count=binding["response_count"] - cursor,
        parent_stage_launch=entry(directory / "launch/record.json"),
        parent_stage_exit=entry(directory / "exit/record.json"),
        parent_stage_failure=entry(directory / "failure/record.json")
        if (directory / "failure/record.json").exists()
        else None,
        full_replay_complete=record["full_replay_complete"],
        parent_saved_prefix_replayed_again=False,
        state_bytes_verified=False,
        tensor_structure_gradient_and_RNG_verification="unchanged_v19_storage_read_before_resume",
    )


def inspect_automatic_recovery(
    newroot,
    parentroot,
    *,
    authorization_record=None,
    authorization_body=None,
    authorization_root=None,
):
    audit = validate_safe_recovery(parentroot)
    require(audit["allowed"], audit["reason"])
    root, parent = Path(newroot).resolve(), Path(parentroot).resolve()
    protocol = checked(parent / "protocol/record.json")
    supervision = Path(protocol["supervision_root"]).resolve()
    require(
        supervision.name == "recovery_04"
        and (parent == supervision or parent.parent == supervision / "attempts")
        and root.parent == supervision / "attempts"
        and re.fullmatch(r"attempt\d{4,}", root.name),
        "automatic attempt escaped the explicitly authorized recovery tree",
    )
    number = 1 if parent == supervision else int(parent.name.removeprefix("attempt"))
    require(
        root.name == f"attempt{number + 1:04d}" and not (root / "inheritance/record.json").exists(),
        "automatic attempt must be fresh and strictly sequential",
    )
    authority = _authorization(root, authorization_record, authorization_body)
    prior = read_ref(protocol["inheritance"])
    require(
        prior["schema"] == SCHEMA and prior["new_root"] == str(parent), "parent inheritance changed"
    )
    progress = checked(parent / "actual_final_progress/record.json")
    latest = {(row["seed"], row["arm"]): row for row in progress["arms"]}
    require(
        len(latest) == 9
        and progress["completed_physical_updates"] + progress["remaining_physical_updates"] == 11622
        and progress["completed_outers"] + progress["remaining_outers"] == 24,
        "original nine-model scientific dose changed",
    )
    checkpoints = [
        checkpoint_metadata(row["checkpoint"], coordinate=(row["seed"], row["arm"], row["step"]))
        for row in progress["arms"]
    ]
    prior_items = {row["new_context_directory"]: row for row in prior["context_inheritances"]}
    stages = list(prior["all_parent_stage_bindings"])
    inherited, completed, superseded, unused = [], [], [], []
    parent_ref = entry(parent / "protocol/record.json")
    for record_path in sorted(parent.glob("contexts/seed*/*/step*/context/record.json")):
        directory = record_path.parent.parent
        source_item = prior_items.get(str(directory))
        original_ref = source_item["original_context"] if source_item else entry(record_path)
        _, context, origin = _actual_context(original_ref)
        plan = read_ref(context["task_plan"]) if context["due_outer"] else None
        bindings, interrupted = {}, {}
        for stage in STAGES:
            older = source_item["stage_bindings"][stage] if source_item else None
            if older and older["protocol_scope"] == "parent":
                source, owner_ref = Path(older["directory"]), older["protocol_ref"]
                binding = inspect_stage(
                    source, read_ref(owner_ref), context, stage, plan, protocol_ref=owner_ref
                )
            else:
                source = directory / stage
                if (source / "launch/record.json").exists() and not (
                    (source / "result/record.json").exists()
                    and checked(source / "exit/record.json")["returncode"] == 0
                    and checked(source / "exit/record.json")["stop_requested"] is False
                ):
                    interrupted[stage] = _interrupted_binding(
                        source, protocol, context["id"], stage
                    )
                    continue
                binding = inspect_stage(
                    source, protocol, context, stage, plan, protocol_ref=parent_ref
                )
            if binding is not None:
                bindings[stage] = binding
                stages.append(binding)
        coordinate = context["seed"], context["arm"]
        actual = latest[coordinate]
        if "train" in bindings:
            completed.append(
                dict(
                    context=entry(record_path),
                    original_context=original_ref,
                    context_id=context["id"],
                    stage_bindings=bindings,
                )
            )
            continue
        if actual["checkpoint"] != context["checkpoint"]:
            limits = [context["execution_plan"]["final_step"]]
            if context["arm"] != "Static":
                limits.extend(
                    step
                    for step in context["execution_plan"]["outer_steps"]
                    if step > context["step"]
                )
            training_limit = context.get(
                "training_stop_step", min(min(limits), context["step"] + 298)
            )
            require(
                "train" in interrupted
                and actual["step"] >= context["step"]
                and actual["step"] <= training_limit,
                "actual state changed outside the interrupted training segment",
            )
            if actual["step"] == 1490:
                endpoint = Path(context["arm_root"]) / "result/record.json"
                require(
                    endpoint.exists(),
                    "unsupported_final_step_without_model_endpoint_seal_requires_user",
                )
                value = checked(endpoint)
                require(
                    value["final_checkpoint"]["path"] == actual["checkpoint"]["path"]
                    and value["result"]["committed_step"] == 1490,
                    "final-model endpoint differs from actual committed state",
                )
            superseded.append(
                dict(
                    context=entry(record_path),
                    actual_checkpoint=actual["checkpoint"],
                    reason="recreate_from_actual_committed_optimizer_and_outer_state_without_repeating_commits",
                )
            )
            continue
        if not bindings and not interrupted:
            unused.append(
                dict(
                    context=entry(record_path),
                    seed=context["seed"],
                    arm=context["arm"],
                    reason="not_dispatched_recreate_from_identical_actual_checkpoint",
                )
            )
            continue
        if not context["due_outer"]:
            require(
                set(interrupted) <= {"train"}, "non-outer attempt has unexpected scientific stage"
            )
            unused.append(
                dict(
                    context=entry(record_path),
                    seed=context["seed"],
                    arm=context["arm"],
                    reason="train_recreate_from_actual_unchanged_checkpoint",
                )
            )
            continue
        target = root / directory.relative_to(parent)
        item = copy.deepcopy(source_item or {})
        current_attempt_bindings = {
            stage: value
            for stage, value in bindings.items()
            if Path(value["directory"]).is_relative_to(parent)
        }
        local_timing = {**current_attempt_bindings, **interrupted}
        timing = _charged_time(
            (source_item or {}).get("inherited_compute_seconds", 0), directory, local_timing
        )
        cache_view, overlay = _automatic_cache(context, directory, target, source_item, bindings)
        resume = (source_item or {}).get("replay_resume")
        if "replay_R3" in interrupted:
            require(
                "virtual_point" in bindings, "interrupted replay lacks sealed same-point feedback"
            )
            resume = _replay_prefix(
                directory / "replay_R3", context, bindings["virtual_point"], resume
            )
        if "replay_R3" in bindings:
            resume = None
        for stage in STAGES:
            bindings.setdefault(
                stage, dict(protocol_scope="current", directory=str(target / stage))
            )
        item.update(
            seed=context["seed"],
            arm=context["arm"],
            step=context["step"],
            original_context=original_ref,
            original_context_id=context["id"],
            origin_context_directory=str(origin),
            immediate_parent_context=entry(record_path),
            immediate_parent_context_directory=str(directory),
            new_context_directory=str(target),
            parent_protocol=parent_ref,
            stage_bindings=bindings,
            task_plan=context["task_plan"],
            task_cache_root=context["task_cache_root"],
            task_cache_view=cache_view,
            task_cache_overlay=overlay,
            replay_resume=resume,
            interrupted_stage_bindings=interrupted,
            phase_deadlines_epoch={},
            phase_first_launch_epoch={},
            phase_deadline_overrides={},
            distribution_recovery_window=False,
            time_limits_removed=True,
            **timing,
        )
        if item.get("feedback_resume") is not None:
            if bindings["virtual_point"]["protocol_scope"] == "parent":
                # Later replay/distribution must read the already completed cohort,
                # not instantiate another partial-feedback view.
                item["feedback_resume"]["new_feedback_base_root"] = source_item["feedback_resume"][
                    "new_feedback_base_root"
                ]
            else:
                item["feedback_resume"]["new_feedback_base_root"] = str(
                    target / "feedback_resume_view"
                )
        inherited.append(item)
    evaluations = copy.deepcopy(prior["completed_evaluations"])
    known = {(row["seed"], row["arm"]) for row in evaluations}
    for seed, arm in latest:
        key = previous.ARM_KEYS[arm]
        directory = parent / f"evaluations/seed{seed}_{key}/generate"
        if not (directory / "result/record.json").exists():
            continue
        binding = inspect_stage(
            directory,
            protocol,
            dict(id=f"evaluation:{seed}:{key}", seed=seed, arm=arm),
            "generate",
            protocol_ref=parent_ref,
        )
        require((seed, arm) not in known, "completed endpoint was generated twice")
        result = read_ref(binding["result"])
        seal = read_ref(result["whole_test_seal"])
        require(
            latest[(seed, arm)]["step"] == 1490
            and seal["denominator"] == 1147
            and seal["all_generation_complete"] is True
            and seal["all_provider_calls_settled"] is True,
            "endpoint is not a complete actual final-model generation seal",
        )
        evaluations.append(
            dict(
                seed=seed,
                arm=arm,
                whole_test_seal=result["whole_test_seal"],
                stage_binding=binding,
                answers_or_scores_read=False,
            )
        )
        stages.append(binding)
    stages = previous._deduplicate(stages)
    sampled = sum(
        700
        for binding in stages
        if Path(binding["directory"]).name == "virtual_point"
        and read_ref(binding["result"]).get("feedback_mode") == "first_sampling"
    )
    pending = sum(
        700
        for item in inherited
        if item["stage_bindings"]["virtual_point"]["protocol_scope"] == "parent"
    )
    partial = [
        item
        for item in inherited
        if item.get("feedback_resume") is not None
        and item["stage_bindings"]["virtual_point"]["protocol_scope"] == "current"
    ]
    require(len(partial) <= 1 and sampled <= 8400, "scientific feedback ownership changed")
    reserved, partial_done = 700 * len(partial), 450 * len(partial)
    virgin = 8400 - sampled - reserved
    require(virgin >= 0 and virgin % 700 == 0, "remaining first-sampling cohort budget invalid")
    budget = dict(
        original_reused_feedback_episodes=2100,
        original_first_sampling_feedback_episodes=8400,
        already_generated_first_sampling_feedback_episodes=sampled,
        already_generated_uncommitted_feedback_episodes=pending,
        pending_sealed_feedback_episodes=pending,
        future_first_sampling_outers=virgin // 700,
        future_first_sampling_feedback_episodes=virgin,
        reserved_partial_feedback_episodes=reserved,
        completed_partial_feedback_episodes=partial_done,
        remaining_partial_feedback_episodes=reserved - partial_done,
        remaining_new_feedback_episodes=8400 - sampled - partial_done,
        remaining_endpoint_answers=(9 - len(evaluations)) * 1147,
        total_endpoint_answers=10323,
    )
    queue = read_ref(file_ref(parent / "queue/status.json"))
    value = copy.deepcopy(prior)
    value.pop("id", None)
    value.update(
        schema=SCHEMA,
        at=_stamp(),
        new_root=str(root),
        parent_root=str(parent),
        parent_protocol=parent_ref,
        parent_implementation=entry(parent / "implementation/record.json"),
        historical_inheritance=protocol["inheritance"],
        parent_pause=entry(parent / "failure/record.json"),
        parent_failure=entry(parent / "failure/record.json"),
        parent_queue=file_ref(parent / "queue/status.json"),
        actual_final_progress=entry(parent / "actual_final_progress/record.json"),
        recovery_authorization=authority,
        safe_recovery_audit=audit,
        context_inheritances=inherited,
        completed_contexts=completed,
        superseded_interrupted_training_contexts=superseded,
        unused_contexts=unused,
        latest_checkpoints=checkpoints,
        completed_evaluations=evaluations,
        all_parent_stage_bindings=stages,
        accepted_new_optimizer_updates=5810 - progress["remaining_physical_updates"],
        accepted_new_outer_updates=15 - progress["remaining_outers"],
        remaining_optimizer_updates=progress["remaining_physical_updates"],
        remaining_outer_updates=progress["remaining_outers"],
        remaining_scientific_budget=budget,
        inherited_resource_wait_seconds=math.ceil(queue["global_external_resource_wait_seconds"]),
        resource_wait_budget_seconds=None,
        outer_compute_budget_seconds=None,
        time_limits_removed=True,
        original_accounting_reset=False,
    )
    return value


def initialize_automatic_recovery(
    newroot, parentroot, *, authorization_record=None, authorization_root=None
):
    root = Path(newroot).resolve()
    return _publish_aliases(
        root,
        inspect_automatic_recovery(
            root,
            parentroot,
            authorization_record=authorization_record,
            authorization_root=authorization_root,
        ),
    )
