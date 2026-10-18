"""Durable scientific recovery audit and entry point for V56 job attempts.

The scheduler consumes structured observations and saved-state bindings. It
never classifies an unknown generation or a mathematical mismatch as a retry.
Old complete class gradients are an explicitly bound read-only overlay.
"""

from __future__ import annotations

import argparse
import copy
import errno
import importlib
import json
import os
import re
import sys
import time
from pathlib import Path

import finqa_v54_training as training
import finqa_v54_worker as scientific
import finqa_v56_runtime as runtime

require, checked, publish, digest, file_ref = (training.require, training.checked,
    training.publish, training.digest, training.file_ref)
IO_ERRNOS = {errno.EIO, errno.EAGAIN, errno.ENOSPC, errno.ESTALE}


def build_class_inheritance(old_root):
    """Bind the nine actual whole-task tensors once; no class math or writes."""
    old_root = Path(old_root).resolve()
    seeds = {}
    for seed in training.SEEDS:
        parent_path = old_root / f"parents/seed{seed}/record.json"
        parent = checked(parent_path)
        plan = training.records.read_ref(parent["task_plan"])
        cache_root = old_root / f"parents/seed{seed}/task_cache"
        tasks = []
        for path in sorted(cache_root.glob("task*/record.json")):
            record = checked(path)
            task = record["task"]
            require(record["complete_task"] is True
                    and record["binding"]["parent_id"] == parent["id"]
                    and record["binding"]["parent_state_digest"] == parent["parent_state_digest"]
                    and record["task_plan_id"] == plan["id"]
                    and task == plan["tasks"][task["index"]]
                    and record["parameter_spec"] == parent["parameter_spec"],
                    "old complete-task gradient has a foreign scientific binding")
            gradient = file_ref(path.parent / "gradient.pt")
            require(gradient["sha256"] == record["gradient_sha256"],
                    "old complete-task actual gradient bytes changed")
            tasks.append(dict(task_id=task["task_id"], index=task["index"],
                              rows=task["row_count"], record=training.records.entry(path),
                              gradient=gradient, binding=record["binding"]))
        seeds[str(seed)] = dict(seed=seed, original_parent=training.records.entry(parent_path),
            parent_state_digest=parent["parent_state_digest"],
            component_digests=parent["component_digests"], point_id=parent["point_id"],
            task_plan=parent["task_plan"], parameter_spec=parent["parameter_spec"],
            original_task_cache_root=str(cache_root), tasks=tasks,
            inherited_tasks=len(tasks), inherited_rows=sum(t["rows"] for t in tasks))
    body = dict(schema="v56_complete_task_read_only_overlay.v1", old_root=str(old_root),
                seeds=seeds, total_inherited_tasks=sum(v["inherited_tasks"] for v in seeds.values()),
                total_inherited_rows=sum(v["inherited_rows"] for v in seeds.values()),
                partial_class_rows_reused=False, old_tensor_bytes_validated=True,
                original_task_order_preserved=True, inherited_tasks_recomputed=False)
    return checked_class_inheritance({**body, "id": digest(body)})


def checked_class_inheritance(value):
    require(value.get("id") == digest({k: v for k, v in value.items() if k != "id"})
            and value["schema"] == "v56_complete_task_read_only_overlay.v1"
            and set(value["seeds"]) == {str(s) for s in training.SEEDS}
            and value["total_inherited_tasks"] == 9 and value["total_inherited_rows"] == 45
            and value["partial_class_rows_reused"] is False,
            "only the nine actual complete V55 tasks may be inherited")
    for seed in training.SEEDS:
        row = value["seeds"][str(seed)]
        parent = training.records.read_ref(row["original_parent"])
        plan = training.records.read_ref(row["task_plan"])
        require(row["seed"] == seed and row["parent_state_digest"] == parent["parent_state_digest"]
                and row["component_digests"] == parent["component_digests"]
                and row["point_id"] == parent["point_id"]
                and row["parameter_spec"] == parent["parameter_spec"]
                and row["inherited_tasks"] == len(row["tasks"]) == (9 if seed == 137 else 0)
                and row["inherited_rows"] == sum(t["rows"] for t in row["tasks"]),
                "old task ownership/count differs")
        require(len({t["task_id"] for t in row["tasks"]}) == len(row["tasks"]), "duplicate inherited task")
        for task in row["tasks"]:
            record = training.records.read_ref(task["record"])
            expected = Path(row["original_task_cache_root"]) / f"task{task['index']:04d}"
            require(task["record"]["path"] == str(expected / "record.json")
                    and task["gradient"]["path"] == str(expected / "gradient.pt")
                    and record["complete_task"] is True and record["task"] == plan["tasks"][task["index"]]
                    and record["task"]["task_id"] == task["task_id"]
                    and record["binding"] == task["binding"]
                    and record["binding"]["parent_id"] == parent["id"]
                    and record["gradient_sha256"] == task["gradient"]["sha256"],
                    "inherited class record/source binding changed")
    return value


class TaskCacheOverlay:
    """One canonical task order, original read-only tasks and independent new tasks."""

    def __init__(self, new_cache, inherited, parent, rt):
        self.new, self.plan, self.rt = new_cache, new_cache.plan, rt
        self.binding, self.root = new_cache.binding, new_cache.root
        self.parameter_spec = new_cache.parameter_spec
        require(inherited["parent_state_digest"] == parent["parent_state_digest"]
                and inherited["component_digests"] == parent["component_digests"]
                and inherited["point_id"] == parent["point_id"]
                and inherited["parameter_spec"] == parent["parameter_spec"]
                and inherited["task_plan"]["id"] == self.plan["id"],
                "old task overlay is not the same scientific parent")
        self.entries = {row["task_id"]: row for row in inherited["tasks"]}
        self.old = None
        if self.entries:
            bindings = [row["binding"] for row in self.entries.values()]
            require(all(value == bindings[0] for value in bindings), "mixed old task bindings")
            self.old = training.task_cache.TaskCache(inherited["original_task_cache_root"], bindings[0],
                self.plan, self.parameter_spec, rt)
            require(not any(self.new.directory(task).exists() for task in self.entries),
                    "an inherited complete task must not also have a new gradient")

    def task(self, task):
        return self.new.task(task)

    def directory(self, task):
        return (self.old if task in self.entries else self.new).directory(task)

    def has(self, task):
        return (self.old if task in self.entries else self.new).has(task)

    def read(self, task):
        # Original reader verifies actual bytes, semantic tensors and binding.
        return (self.old if task in self.entries else self.new).read(task)

    def commit(self, task, values_cpu, receipt=None):
        require(task not in self.entries, "inherited complete task cannot be recomputed or rewritten")
        return self.new.commit(task, values_cpu, receipt=receipt)

    def assemble(self, device="cpu"):
        return {task: self.rt.v8._DeviceGradients(self.read(task), device)
                for task in self.plan["task_ids"]}


def overlay_cache(root, parent, rt, new_cache):
    protocol = checked(Path(root) / "protocol/record.json")
    manifest = checked_class_inheritance(protocol["class_cache_inheritance"])
    row = manifest["seeds"][str(parent["seed"])]
    return TaskCacheOverlay(new_cache, row, parent, rt) if row["tasks"] else new_cache


def _job_directory(root, job):
    if job.get("kind") == "generate" or job.get("stage") == "generate":
        return Path(root) / "evaluations/jobs" / job.get("job_id", job.get("id"))
    return scientific.stage_root(root, job["seed"], job["stage"])


def _state_metadata(directory, record, field="state_sha256", filename="state.pt"):
    path = Path(directory) / filename
    require(path.is_file() and path.stat().st_size > 0, "durable actual tensor file is missing")
    # Full bytes/semantic validation belongs to the cold scientific consumer,
    # before any use. Admission binds the exact immutable record and pathname.
    return dict(path=str(path), sha256=record[field], bytes=path.stat().st_size,
                full_tensor_validation_required_in_cold_worker=True)


def audit_job_resume(root, job):
    """Pure read-only checkpoint/settlement audit, never a scientific restore."""
    root = Path(root).resolve()
    directory = _job_directory(root, job)
    evidence, progress, unknown, allowed = [training.records.entry(root / "protocol/record.json")], 0, 0, True
    details = {}
    stage = job["stage"]
    if stage in ("feedback_C05", "generate"):
        feedback = importlib.import_module("finqa_v56_feedback")
        protocol = checked(root / "protocol/record.json")
        inheritance = (protocol["feedback_inheritance"]["seeds"][str(job["seed"])]) if stage == "feedback_C05" else None
        audit_directory = (directory / "shards" / job["panel"] / "generation"
                           if stage == "generate" else directory)
        if stage == "generate":
            evidence.append(training.records.entry(root / "evaluations/registration/record.json"))
        result = feedback.audit_resume(audit_directory, inheritance=inheritance)
        evidence.extend(result["evidence"])
        progress, unknown, allowed = result["progress_units"], result["unknown_calls"], result["resume_allowed"]
        details["feedback_audit"] = result
    else:
        parent = training.checked_parent(root, job["seed"])
        evidence.append(training.records.entry(root / f"parents/seed{job['seed']}/record.json"))
        if stage.startswith("shard"):
            plan = training.records.read_ref(parent["task_plan"])
            assigned = set(plan["assignments"][int(stage[-2:])]["task_ids"])
            protocol = checked(root / "protocol/record.json")
            inherited = checked_class_inheritance(protocol["class_cache_inheritance"])["seeds"][str(job["seed"])]
            records = [row["record"] for row in inherited["tasks"] if row["task_id"] in assigned]
            task_ids = {row["task_id"] for row in inherited["tasks"] if row["task_id"] in assigned}
            for path in sorted((root / f"parents/seed{job['seed']}/task_cache").glob("task*/record.json")):
                row = checked(path)
                if row["task"]["task_id"] not in assigned:
                    continue
                require(row["complete_task"] is True and row["binding"]["parent_id"] == parent["id"]
                        and row["task_plan_id"] == plan["id"], "foreign/partial class checkpoint")
                require(row["task"]["task_id"] not in task_ids, "inherited task was duplicated in the new cache")
                task_ids.add(row["task"]["task_id"])
                _state_metadata(path.parent, row, "gradient_sha256", "gradient.pt")
                records.append(training.records.entry(path))
            require(len({ref["path"] for ref in records}) == len(records), "duplicate class checkpoint")
            evidence.extend(records)
            progress = len(records)
            details["complete_task_count"] = progress
        elif stage.startswith("train_"):
            arm = stage.removeprefix("train_")
            base = training.branch_root(root, job["seed"], arm)
            checkpoint = training.latest_branch_checkpoint(base / "training")
            if checkpoint is not None:
                row = json.loads((checkpoint / "record.json").read_bytes())
                require(row["seed"] == job["seed"] and row["arm"] == "C-only"
                        and 596 <= row["step"] <= 894, "training durable cursor changed")
                _state_metadata(checkpoint, row)
                evidence.append(file_ref(checkpoint / "record.json"))
                evidence.append(training.records.entry(base / "binding/record.json"))
                progress = row["step"] - 596
            details["committed_optimizer_updates"] = progress
        elif stage == "replay_C05":
            candidates = sorted(directory.glob("checkpoints/response*/record.json"))
            if candidates:
                path = candidates[-1]
                row = checked(path)
                require(row["schema"] == "v19_response_boundary_checkpoint.v1"
                        and row["response_prefix_complete"] is True
                        and row["binding"]["point_id"] == parent["point_id"]
                        and row["binding"]["denominator"] == 700
                        and row["binding"]["backend_identity"]["temperature"] == 0.5
                        and path.parent.name == f"response{row['cursor']:06d}",
                        "response checkpoint belongs to another actual probability/point")
                _state_metadata(path.parent, row)
                evidence.append(training.records.entry(path))
                progress = row["cursor"]
            details["persisted_response_prefix"] = progress
        elif stage == "distribution_C05":
            if (directory / "payload/record.json").exists():
                row = checked(directory / "payload/record.json")
                require(row["parent_id"] == parent["id"] and row["stage"] == stage,
                        "saved distribution payload belongs to another parent")
                _state_metadata(directory / "payload", row)
                evidence.append(training.records.entry(directory / "payload/record.json"))
                progress = 1
        else:
            raise ValueError("unregistered durable scientific stage")
    complete = (directory / "result/record.json").exists()
    if complete:
        result = checked(directory / "result/record.json")
        require(result["status"] == "COMPLETE", "invalid complete stage record")
        evidence.append(training.records.entry(directory / "result/record.json"))
    body = dict(resume_allowed=bool(allowed and unknown == 0), unknown_calls=unknown,
                progress_units=progress, evidence=evidence, complete_stage=complete,
                full_tensor_validation_before_cold_scientific_use=True, details=details)
    body["durable_progress_digest"] = (details["feedback_audit"]["durable_progress_digest"]
        if "feedback_audit" in details else digest(dict(progress_units=progress,
            evidence=[dict(path=v["path"], sha256=v["sha256"]) for v in evidence])))
    return body


def reuse_complete_result(root, job, attempt_dir):
    """CPU finalization after post-science reporting IO failed; no model calls."""
    root, attempt_dir = Path(root), Path(attempt_dir)
    directory = _job_directory(root, job)
    result_path = directory / "result/record.json"
    result = checked(result_path)
    protocol = checked(root / "protocol/record.json")
    require(result["status"] == "COMPLETE" and result["resources"]["all_gates_passed"] is True,
            "only an already complete scientifically admitted result may be finalized")
    if job["stage"] != "generate":
        require(result["protocol_id"] == protocol["id"]
                and result["stage"] == job["stage"] and result["seed"] == job["seed"],
                "saved successful result belongs to a different scientific job")
        if result.get("payload"):
            payload = training.records.read_ref(result["payload"])
            require(training.sha(Path(result["payload"]["path"]).parent / "state.pt") == payload["state_sha256"],
                    "saved complete scientific tensor changed before finalization")
        if result.get("branch_result"):
            branch = training.records.read_ref(result["branch_result"])
            for checkpoint in branch["snapshots"].values():
                require(training.sha(Path(checkpoint["path"]) / "state.pt") == checkpoint["state_sha256"],
                        "saved complete branch tensor changed before finalization")
    observations = Path(result["resources"]["observations_path"]).resolve()
    require(observations.is_relative_to(root.resolve() / "resources" / job.get("job_id", job.get("id"))),
            "successful resource evidence belongs to another job root")
    closeout_path = observations.parent / "closeout/record.json"
    closeout = checked(closeout_path)
    require(closeout["status"] == "COMPLETE" and closeout["resources"] == result["resources"]
            and closeout["protocol_id"] == protocol["id"]
            and closeout["job_id"] == job.get("job_id", job.get("id")),
            "complete original resource closeout is required before CPU finalization")
    publish(attempt_dir / "reused_result/record.json", dict(protocol_id=protocol["id"],
        job_id=job.get("job_id", job.get("id")), source_result=training.records.entry(result_path),
        source_resource_closeout=training.records.entry(closeout_path), scientific_calls=0,
        verified_durable_result=True, original_scientific_result_rewritten=False))
    return result


def _exception_chain(error):
    result, seen = [], set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        native_errno = error.errno if isinstance(error, OSError) else None
        if (type(error).__name__ == "GenerationPreCallPause"
                and type(error).__module__ == "finqa_v56_feedback"
                and getattr(error, "actual_model_calls", None) == 0):
            native_errno = getattr(error, "errno", None)
        result.append(dict(type=type(error).__name__, module=type(error).__module__,
                           actual_errno=native_errno,
                           message=str(error)))
        error = error.__cause__ or error.__context__
    return result


def record_attempt_failure(root, job, attempt_dir, error, *, guard=None):
    """Persist actual exception and resource observations; no retry decision here."""
    attempt_dir, root = Path(attempt_dir), Path(root)
    protocol = checked(root / "protocol/record.json")
    resources = guard.report() if guard is not None else None
    resource_closeout = None
    if guard is not None and (guard.directory / "closeout/record.json").exists():
        resource_closeout = training.records.entry(guard.directory / "closeout/record.json")
    if guard is None:
        path = root / "resources" / job.get("job_id", job.get("id")) / f"pid{os.getpid()}/closeout/record.json"
        if path.exists():
            closed = checked(path)
            resources, resource_closeout = closed["resources"], training.records.entry(path)
    body = dict(schema="v56_actual_attempt_failure.v1", protocol_id=protocol["id"],
                job=job, pid=os.getpid(), attempt_root=str(attempt_dir.resolve()),
                exception_chain=_exception_chain(error), exception_type=type(error).__name__,
                error=str(error), finished_epoch=time.time(), resource_closeout=resource_closeout,
                resources=resources, automatic_retry_in_worker=False,
                CUDA_initialized=bool(sys.modules.get("torch") and sys.modules["torch"].cuda.is_initialized()))
    return publish(attempt_dir / "failure/record.json", body)


def classify_attempt(root, job, attempt_dir, returncode):
    """Known resource/IO evidence AND settled actual durable state are required."""
    root, attempt_dir = Path(root), Path(attempt_dir)
    path = attempt_dir / "failure/record.json"
    verdict = dict(classification="HARD_BLOCK", reason="missing structured failure evidence",
                   resume_allowed=False, unknown_calls=0, evidence=[], actual_errno=None)
    if not path.exists():
        return verdict
    failure = checked(path)
    require(failure["schema"] == "v56_actual_attempt_failure.v1"
            and failure["protocol_id"] == checked(root / "protocol/record.json")["id"]
            and failure["attempt_root"] == str(attempt_dir.resolve())
            and failure["job"].get("stage") == job["stage"]
            and failure["job"].get("job_id", failure["job"].get("id")) == job.get("job_id", job.get("id")),
            "attempt failure ownership differs")
    verdict["evidence"] = [training.records.entry(path)]
    try:
        audit = audit_job_resume(root, job)
    except OSError as error:
        if error.errno in IO_ERRNOS:
            verdict.update(classification="AUDIT_IO_WAIT", actual_errno=error.errno,
                reason="actual transient IO prevents reading durable evidence; no science may dispatch")
            return verdict
        verdict["reason"] = "durable state audit IO failed: " + str(error)
        return verdict
    except (ValueError, KeyError) as error:
        verdict["reason"] = "durable state audit failed: " + type(error).__name__ + ": " + str(error)
        return verdict
    verdict.update({key: audit[key] for key in ("unknown_calls", "durable_progress_digest", "progress_units")})
    verdict["evidence"].extend(audit["evidence"])
    if audit["unknown_calls"] or not audit["resume_allowed"]:
        verdict["reason"] = "unsettled feedback or invalid saved-state binding"
        return verdict
    resources = failure.get("resources") or {}
    chain = failure.get("exception_chain", [])
    types = {row["type"] for row in chain}
    if returncode < 0 or resources.get("received_signals") or types & {"ExplicitStop", "KeyboardInterrupt", "ReplayPaused"}:
        verdict.update(classification="EXPLICIT_STOP", reason="stop signal is not a resource retry authorization")
        return verdict
    violation = resources.get("observed_violation") or {}
    peak = violation.get("peak_allocated_bytes", 0)
    host = violation.get("host") or {}
    if peak > 76 * runtime.GIB or host.get("peak_rss_bytes", 0) > host.get("rss_limit_bytes", float("inf")):
        verdict["reason"] = "historical allocated/self-RSS hard peak requires diagnosis, not an automatic retry"
        return verdict
    if failure.get("resource_closeout"):
        closeout = training.records.read_ref(failure["resource_closeout"])
        require(closeout["resources"] == resources and closeout["pid"] == failure["pid"],
                "failure resource evidence differs from actual closed process")
        verdict["evidence"].append(failure["resource_closeout"])
    deferred = resources.get("deferred_observation")
    external_ram = host and host.get("available_bytes", float("inf")) < host.get("available_reserve_bytes", 96 * runtime.GIB)
    external_free = violation.get("boundary") is True and violation.get("free_bytes", float("inf")) < 2 * runtime.GIB
    actual_oom = any(row["type"] == "OutOfMemoryError" and row["module"].startswith("torch") for row in chain)
    if deferred or external_ram or external_free or actual_oom:
        verdict.update(classification="RETRY_SAFE_RESOURCE", reason="actual resource shortage with settled durable boundaries",
                       resume_allowed=True)
        return verdict
    for row in chain:
        if row.get("actual_errno") in IO_ERRNOS:
            verdict.update(classification="RETRY_SAFE_IO", reason="actual transient IO errno with settled durable boundaries",
                           actual_errno=row["actual_errno"], resume_allowed=True)
            return verdict
    verdict["reason"] = "failure is not a proved transient resource or allowed IO error"
    return verdict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--seed", type=int, choices=training.SEEDS, required=True)
    parser.add_argument("--stage", choices=scientific.STAGES, required=True)
    parser.add_argument("--gpu-index", type=int, required=True)
    parser.add_argument("--attempt-root", type=Path)
    args = parser.parse_args()
    result = scientific.run(args.root, args.seed, args.stage, args.gpu_index, attempt_root=args.attempt_root)
    print(json.dumps(dict(status=result["status"], id=result["id"])))


if __name__ == "__main__":
    main()
