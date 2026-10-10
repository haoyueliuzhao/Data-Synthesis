"""Import only durable V35 task checkpoints for an explicitly authorized recovery.

The stopped run remains read-only and failed. No tensor is deserialized and no
GPU/API is touched here. Each complete task is independently copied to a new
inode, with its original record and mathematical binding unchanged. Source
gradient SHA256 is checked while copying, avoiding a second full tensor scan.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

GIB = 1024**3
GPU_LIMIT = 76 * GIB
FREE_RESERVE = 2 * GIB
HOST_LIMIT = 160 * GIB
HOST_RESERVE = 96 * GIB
STAGES = ("shard00", "shard01", "shard02", "shard03")
ZERO_KEYS = (
    "API_calls",
    "new_sampling_calls",
    "scoring_calls",
    "optimizer_steps",
    "replayed_responses",
)
KNOWN_EXITED_SHARD00_GUARD_ERROR = dict(
    error_type="ValueError",
    error="one or more verified signal guards failed: [{'stage': 'shard00', 'signal': 15, "
    "'error': 'PID/birth matches but worker command does not; no signal sent'}]",
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _counter_gate(record):
    require(
        all(type(record[key]) is int and record[key] == 0 for key in ZERO_KEYS)
        and record["original_B_resume_authorized"] is False,
        "prior stage performed unauthorized scientific work",
    )


def _gone(control, launch):
    require(control.birth(launch["pid"]) != launch["birth"], "prior owned process is still alive")


def _check_observation(row, *, deadline):
    require(
        row["limits"]
        == dict(allocated_memory_limit_bytes=GPU_LIMIT, free_memory_reserve_bytes=FREE_RESERVE),
        "prior GPU resource limits differ",
    )
    keys = (
        "allocated_bytes",
        "reserved_bytes",
        "peak_allocated_bytes",
        "peak_reserved_bytes",
        "free_bytes",
        "total_bytes",
    )
    require(
        all(type(row[key]) is int and row[key] >= 0 for key in keys)
        and type(row["boundary"]) is bool
        and row["allocated_bytes"] <= row["peak_allocated_bytes"] <= GPU_LIMIT
        and row["allocated_bytes"] <= row["reserved_bytes"] <= row["peak_reserved_bytes"]
        and row["peak_allocated_bytes"] <= row["peak_reserved_bytes"]
        and row["free_bytes"] <= row["total_bytes"]
        and (not row["boundary"] or row["free_bytes"] >= FREE_RESERVE)
        and row["allocated_pass"] is True
        and row["free_pass"] is True,
        "prior GPU resource gate failed",
    )
    host = row["host"]
    require(
        host["rss_limit_bytes"] == HOST_LIMIT
        and host["available_reserve_bytes"] == HOST_RESERVE
        and all(
            type(host[key]) is int and host[key] >= 0
            for key in ("rss_bytes", "peak_rss_bytes", "available_bytes")
        )
        and host["rss_bytes"] <= host["peak_rss_bytes"] <= HOST_LIMIT
        and host["available_bytes"] >= HOST_RESERVE
        and host["rss_pass"] is True
        and host["available_pass"] is True
        and host["passed"] is True,
        "prior host resource gate failed",
    )
    require(
        row["deadline_epoch"] == deadline and row["deadline_pass"] is True,
        "prior absolute deadline gate failed",
    )
    require(
        type(row["stop_requested"]) is bool and row["passed"] is (not row["stop_requested"]),
        "prior observation failure is not solely a stop request",
    )


def _stage_evidence(source, stage, protocol, plan, deadline, control):
    directory = source / stage
    launch = control.checked(directory / "launch/record.json")
    exited = control.checked(directory / "exit/record.json")
    require(
        launch["stage"] == exited["stage"] == stage
        and launch["protocol_id"] == exited["protocol_id"] == protocol["id"]
        and launch["global_deadline_epoch"] == exited["global_deadline_epoch"] == deadline,
        "prior stage launch/exit/deadline differs",
    )
    _gone(control, launch)
    result_path, failure_path = directory / "result/record.json", directory / "failure/record.json"
    require(
        result_path.is_file() != failure_path.is_file(),
        "ambiguous or missing prior stage termination",
    )
    successful = result_path.is_file()
    terminal_path = result_path if successful else failure_path
    terminal = control.checked(terminal_path)
    require(
        terminal["protocol_id"] == protocol["id"] and terminal["stage"] == stage,
        "prior stage terminal identity differs",
    )
    _counter_gate(terminal)
    if successful:
        require(
            exited["returncode"] == 0 and terminal["model_released"] is True,
            "completed prior shard has no successful exit/model release",
        )
        control.check_result(protocol, stage, terminal, plan)
    else:
        require(
            exited["returncode"] != 0
            and exited["stop_requested"] is True
            and terminal["error_type"] == "TailStopRequested"
            and terminal["completed_task_caches_preserved"] is True
            and terminal["current_uncommitted_task_not_checkpoint"] is True
            and terminal["automatic_retry"] is False
            and terminal["variant_fallback"] is False,
            "only externally stopped incomplete shards may supply prior durable tasks",
        )

    paths = sorted((directory / "resources").glob("event*/record.json"))
    require(bool(paths), "missing prior resource observations")
    rows, refs = [], []
    for index, path in enumerate(paths):
        require(path.parent.name == f"event{index:06d}", "resource event sequence has gaps")
        event = control.checked(path)
        require(
            event["protocol_id"] == protocol["id"] and event["stage"] == stage,
            "resource event belongs to another stage",
        )
        row = event["observation"]
        require(row["sequence"] == index + 1, "GPU resource sequence differs")
        _check_observation(row, deadline=deadline)
        require(
            not row["stop_requested"] or (not successful and index == len(paths) - 1),
            "stop request precedes later prior resource observations",
        )
        rows.append(row)
        refs.append(control.entry(path))
    labels = {row["label"] for row in rows if row["boundary"]}
    require(
        {"before_model_load", "after_model_load.after_cleanup"} <= labels,
        "prior model loading resource boundaries missing",
    )
    resources = terminal["resources"]
    if successful:
        require(resources["observations"] == rows, "prior successful resource ledger differs")
        host_summary = resources["host"]
    else:
        gpu_only = [
            {
                key: value
                for key, value in row.items()
                if key not in {"host", "deadline_epoch", "deadline_pass"}
            }
            for row in rows
        ]
        require(
            resources["observations"] == gpu_only
            and rows[-1]["stop_requested"] is True
            and resources["limits"]
            == dict(allocated_memory_limit_bytes=GPU_LIMIT, free_memory_reserve_bytes=FREE_RESERVE)
            and resources["peak_reset_calls"] == 0
            and resources["all_passed"] is False
            and resources["max_observed_peak_allocated_bytes"]
            == max(row["peak_allocated_bytes"] for row in rows)
            and resources["min_boundary_free_bytes"]
            == min(row["free_bytes"] for row in rows if row["boundary"]),
            "prior interrupted resource summary contradicts observed gates",
        )
        host_summary = terminal["host_resources"]
        require(
            host_summary["all_passed"] is False,
            "prior interrupted combined status must remain failed",
        )
    require(
        host_summary["rss_limit_bytes"] == HOST_LIMIT
        and host_summary["available_reserve_bytes"] == HOST_RESERVE
        and host_summary["max_observed_peak_rss_bytes"]
        == max(row["host"]["peak_rss_bytes"] for row in rows)
        and host_summary["min_observed_available_bytes"]
        == min(row["host"]["available_bytes"] for row in rows),
        "prior host resource summary contradicts observations",
    )
    return dict(
        stage=stage,
        successful_complete_stage=successful,
        launch=control.entry(directory / "launch/record.json"),
        exit=control.entry(directory / "exit/record.json"),
        terminal=control.entry(terminal_path),
        result=control.entry(result_path) if successful else None,
        resource_event_count=len(rows),
        resource_event_refs_digest=control.digest(refs),
        final_resource_event=refs[-1],
        all_observed_GPU_and_host_numeric_resource_gates_passed=True,
        stop_requested_is_not_a_resource_limit_failure=not successful,
        interrupted_stage_reclassified_as_success=False,
    )


def _fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _rename_no_replace(source, target):
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    require(rename is not None, "atomic no-replace renameat2 is required")
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(target), 1):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(target))


def _copy_checked(source, destination, expected_sha256, expected_bytes, *, deadline):
    """Hash the very source bytes copied, once; never link or mutate the source."""
    sha, count = hashlib.sha256(), 0
    with source.open("rb") as reader, destination.open("xb") as writer:
        before = os.fstat(reader.fileno())
        while chunk := reader.read(4 * 1024 * 1024):
            require(
                time.time() < deadline, "original absolute deadline reached during cache import"
            )
            sha.update(chunk)
            count += len(chunk)
            writer.write(chunk)
        writer.flush()
        os.fsync(writer.fileno())
        after = os.fstat(reader.fileno())
        require(
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
            "source cache changed during copy",
        )
        require(
            (after.st_dev, after.st_ino)
            != (os.fstat(writer.fileno()).st_dev, os.fstat(writer.fileno()).st_ino),
            "recovery cache must use independent destination inodes",
        )
    require(
        count == expected_bytes and sha.hexdigest() == expected_sha256,
        "source gradient checksum/length failed during cache copy",
    )
    return dict(path=str(destination), sha256=sha.hexdigest(), bytes=count)


def prepare_cache(source_root, new_root, control, *, expected_completed=674, expected_missing=70):
    """Seal a no-recompute inheritance manifest, then let a new wrapper launch.

    ``expected_*`` are explicit scope guards; defaults are the observed original
    V35 interruption, and small alternate values are used only by CPU fixtures.
    A failed or partial import is never a completed recovery receipt and is not
    silently retried. Tensor semantic/finite validation remains mandatory in the
    coordinator before CUDA; copying does not claim a new numerical result.
    """
    source, destination = Path(source_root).resolve(), Path(new_root).resolve()
    require(destination == source / "recovery_01", "one independent recovery_01 destination only")
    target_cache = destination / "task_cache"
    require(
        not target_cache.exists()
        and not target_cache.is_symlink()
        and not (destination / "cache_inheritance/record.json").exists(),
        "recovery cache import cannot overwrite or implicitly resume",
    )
    protocol = control.checked_protocol(source)
    plan = control.read_ref(protocol["task_plan"])
    binding = protocol["task_binding"]
    failure_path = source / "failure/record.json"
    failure = control.checked(failure_path)
    status_path = source / "queue/status.json"
    status_raw = status_path.read_bytes()
    status = json.loads(status_raw)
    require(
        failure["schema"] == "v35_bounded_task_failure.v1"
        and failure["protocol_id"] == status["protocol_id"] == protocol["id"]
        and failure["error_type"] == status["error_type"] == "ValueError"
        and failure["error"] == status["error"] == "live worker RSS unavailable"
        and failure["stop_error"] in (None, KNOWN_EXITED_SHARD00_GUARD_ERROR)
        and status["phase"] == "STOPPED_FAILURE_NO_RETRY"
        and status["active_children"] == []
        and failure["no_automatic_retry"] is True
        and failure["no_implicit_fallback"] is True
        and failure["original_B_resume_authorized"] is False
        and status["original_B_resume_authorized"] is False,
        "recovery source is not the stopped RSS-observation-race trial",
    )
    window_path = source / "execution_window/record.json"
    window = control.checked(window_path)
    deadline = window["deadline_epoch"]
    require(
        window["protocol_id"] == protocol["id"]
        and deadline == status["global_deadline_epoch"]
        and deadline - window["first_launch_epoch"] == 4 * 3600
        and time.time() < deadline,
        "original absolute four-hour execution window is inconsistent or exhausted",
    )
    _gone(control, control.checked(source / "queue/run_intent/record.json"))
    require(
        not (source / "coordinator/launch/record.json").exists()
        and not (source / "coordinator/attempt/record.json").exists(),
        "the single global recomputation was already dispatched",
    )
    histories = [
        _stage_evidence(source, stage, protocol, plan, deadline, control) for stage in STAGES
    ]
    inherited = {
        row["stage"]: {key: row[key] for key in ("result", "exit", "launch")}
        for row in histories
        if row["successful_complete_stage"]
    }
    require(set(inherited) == {"shard00"}, "only the known complete shard00 may be inherited")
    # The one permitted secondary guard error sent no signal to an already
    # completed shard00. _stage_evidence above independently requires its real
    # COMPLETE result, exit code 0, model release, all resource gates, and a
    # non-live original PID/birth. No other failed signal guard is admitted.
    require(
        failure["stop_error"] is None or histories[0]["successful_complete_stage"] is True,
        "the known shard00 signal guard requires a verified successful prior exit",
    )

    # Controller-side cgroup/RAM observations are an additional independent
    # history. The RSS race occurred before publishing the offending observation.
    host_refs = []
    for index, path in enumerate(sorted((source / "host_resources").glob("event*/record.json"))):
        event = control.checked(path)
        require(
            path.parent.name == f"event{index:06d}"
            and event["protocol_id"] == protocol["id"]
            and event["passed"] is True
            and event["reserve_bytes"] == HOST_RESERVE
            and event["available_bytes"] >= HOST_RESERVE
            and all(
                row["passed"] is True
                and max(row["rss_bytes"], row["peak_rss_bytes"]) <= HOST_LIMIT
                and row["rss_limit_bytes"] == HOST_LIMIT
                for row in event["processes"]
            ),
            "prior controller host resource history failed",
        )
        host_refs.append(control.entry(path))
    require(bool(host_refs), "missing prior controller host resource history")

    coverage = failure["task_cache_coverage"]
    require(
        coverage["task_plan_id"] == plan["id"]
        and coverage["binding_sha256"] == control.digest(binding)
        and coverage["complete_task_count"] == expected_completed
        and coverage["total_task_count"]
        == expected_completed + expected_missing
        == len(plan["task_ids"])
        and len(coverage["complete_task_ids"]) == expected_completed
        and len(coverage["missing_task_ids"]) == expected_missing,
        "prior sealed cache coverage differs from authorized recovery scope",
    )
    tasks = {task["task_id"]: task for task in plan["tasks"]}
    completed = set(coverage["complete_task_ids"])
    require(
        len(completed) == expected_completed
        and [task for task in plan["task_ids"] if task in completed]
        == coverage["complete_task_ids"]
        and [task for task in plan["task_ids"] if task not in completed]
        == coverage["missing_task_ids"],
        "prior complete/missing task partition or order changed",
    )
    refs = {row["task_id"]: row for row in coverage["task_records"]}
    require(
        list(refs) == coverage["complete_task_ids"],
        "prior task record references incomplete or reordered",
    )
    actual_complete = []
    metadata = []
    for task_id in plan["task_ids"]:
        task = tasks[task_id]
        directory = source / "task_cache" / f"task{task['index']:04d}"
        if task_id not in completed:
            require(
                not directory.exists() and not directory.is_symlink(),
                "unsealed or partial prior task cannot be claimed missing and recomputed",
            )
            continue
        require(
            directory.is_dir()
            and not directory.is_symlink()
            and {p.name for p in directory.iterdir()} == {"record.json", "gradient.pt"}
            and all(
                (directory / name).is_file() and not (directory / name).is_symlink()
                for name in ("record.json", "gradient.pt")
            ),
            "prior complete task is partial or symlinked",
        )
        record_path = directory / "record.json"
        reference = control.entry(record_path)
        require(
            reference == {k: v for k, v in refs[task_id].items() if k != "task_id"},
            "prior complete task record differs from sealed failure coverage",
        )
        record = control.checked(record_path)
        require(
            record["schema"] == "v35_complete_task_gradient.v1"
            and record["complete_task"] is True
            and record["binding"] == binding
            and record["binding_sha256"] == control.digest(binding)
            and record["task_plan_id"] == plan["id"]
            and record["task"] == task
            and record["parameter_spec"] == plan["parameter_spec"],
            "prior task mathematical binding or full coordinate order differs",
        )
        receipt = record["receipt"]
        _counter_gate(receipt)
        require(
            receipt["state_unchanged"] is True
            and receipt["pre_state_identity"] == receipt["post_state_identity"]
            and receipt["original_class_bytecode_unchanged"] is True
            and receipt["stage"] == STAGES[task["shard"]],
            "prior committed task state/source identity changed",
        )
        metadata.append((task_id, directory, reference, record))
        actual_complete.append(task_id)
    require(
        actual_complete == coverage["complete_task_ids"], "prior complete task coverage differs"
    )
    by_shard = []
    for assignment in plan["assignments"]:
        complete_ids = [task for task in assignment["task_ids"] if task in completed]
        missing_ids = [task for task in assignment["task_ids"] if task not in completed]
        stage = STAGES[assignment["shard"]]
        if stage in inherited:
            require(not missing_ids, "inherited completed shard has missing task caches")
        by_shard.append(
            dict(
                stage=stage,
                complete_task_ids=complete_ids,
                missing_task_ids=missing_ids,
                complete_task_count=len(complete_ids),
                missing_task_count=len(missing_ids),
                remaining_rows=sum(tasks[task]["row_count"] for task in missing_ids),
            )
        )

    target_cache.mkdir(parents=True, exist_ok=False)
    copied, byte_count = [], 0
    for task_id, directory, reference, record in metadata:
        require(time.time() < deadline, "original deadline reached before cache import completion")
        task_target = target_cache / directory.name
        staging = Path(tempfile.mkdtemp(prefix=f".{directory.name}.import-", dir=target_cache))
        record_source = directory / "record.json"
        _copy_checked(
            record_source,
            staging / "record.json",
            reference["sha256"],
            record_source.stat().st_size,
            deadline=deadline,
        )
        copied_tensor = _copy_checked(
            directory / "gradient.pt",
            staging / "gradient.pt",
            record["gradient_sha256"],
            record["gradient_bytes"],
            deadline=deadline,
        )
        _fsync_directory(staging)
        _rename_no_replace(staging, task_target)
        _fsync_directory(target_cache)
        byte_count += copied_tensor["bytes"]
        copied.append(
            dict(
                task_id=task_id,
                source_record=reference,
                source_gradient=dict(
                    path=str(directory / "gradient.pt"),
                    sha256=record["gradient_sha256"],
                    bytes=record["gradient_bytes"],
                ),
                destination_record=dict(
                    path=str(task_target / "record.json"),
                    sha256=reference["sha256"],
                    id=reference["id"],
                ),
                destination_gradient=dict(
                    path=str(task_target / "gradient.pt"),
                    sha256=record["gradient_sha256"],
                    bytes=record["gradient_bytes"],
                ),
            )
        )
    require(
        status_path.read_bytes() == status_raw,
        "prior queue status changed during read-only inheritance",
    )
    require(time.time() < deadline, "original deadline reached before recovery inheritance seal")
    return control.publish(
        destination / "cache_inheritance/record.json",
        dict(
            schema="v35_authorized_task_cache_inheritance.v1",
            at=control.now(),
            source_protocol=control.entry(source / "protocol/record.json"),
            source_failure=control.entry(failure_path),
            source_secondary_stop_guard_error=failure["stop_error"],
            known_shard00_guard_failure_requires_successful_prior_exit=True,
            source_queue_snapshot=dict(
                path=str(status_path),
                sha256=hashlib.sha256(status_raw).hexdigest(),
                phase="STOPPED_FAILURE_NO_RETRY",
            ),
            source_execution_window=control.entry(window_path),
            deadline_epoch=deadline,
            first_launch_epoch=window["first_launch_epoch"],
            new_execution_seconds_authorized=0,
            task_plan=protocol["task_plan"],
            task_binding_sha256=control.digest(binding),
            original_math_binding_unchanged=True,
            mathematical_implementation_id=binding["implementation_id"],
            destination_cache_root=str(target_cache),
            complete_task_count=len(copied),
            missing_task_count=expected_missing,
            complete_task_ids=coverage["complete_task_ids"],
            missing_task_ids=coverage["missing_task_ids"],
            remaining_rows=sum(row["remaining_rows"] for row in by_shard),
            by_shard=by_shard,
            inherited_completed_stages=inherited,
            prior_stage_resource_checks=histories,
            prior_controller_host_events_count=len(host_refs),
            prior_controller_host_event_refs_digest=control.digest(host_refs),
            task_records=copied,
            copied_gradient_bytes=byte_count,
            copy_method=(
                "independent inode streaming copy with SHA256 and "
                "fsync/no-replace task-directory publication"
            ),
            hardlinks_or_symlinks_used=False,
            original_record_and_gradient_bytes_unchanged=True,
            tensor_semantic_validation_required_in_coordinator_before_CUDA=True,
            interrupted_task_partial_gradient_reused=False,
            original_failure_reclassified=False,
            original_B_resume_authorized=False,
            automatic_retry=False,
            API_calls=0,
            new_sampling_calls=0,
            scoring_calls=0,
            optimizer_steps=0,
            replayed_responses=0,
        ),
    )
