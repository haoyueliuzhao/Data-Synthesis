"""C-only251/1192 storage union: 186 immutable parent tasks plus 558 new tasks.

Both readers and the local writer are the unchanged ProductionTaskCache. This
module changes ownership/path routing only, not task planning or class/outer
math. Historical source context, bindings, records and tensors remain untouched.
"""

from __future__ import annotations

import math
import stat
from pathlib import Path

COORDINATE = (251, "C-only", 1192)
NEW_STAGES = ("shard00", "shard01", "shard03")


def _identity(path):
    path = Path(path)
    info = path.lstat()
    if path != path.resolve() or not stat.S_ISREG(info.st_mode):
        raise ValueError("overlay payload must be an unredirected regular file")
    return dict(
        path=str(path),
        device=info.st_dev,
        inode=info.st_ino,
        bytes=info.st_size,
        mtime_ns=info.st_mtime_ns,
        ctime_ns=info.st_ctime_ns,
    )


def allows_new_shard(binding, stage):
    return (
        isinstance(binding, dict)
        and (binding.get("seed"), binding.get("arm"), binding.get("step")) == COORDINATE
        and binding.get("allowed_new_stages") == list(NEW_STAGES)
        and stage in NEW_STAGES
    )


def validate_class_window(directory, context, plan, stage, deadline_epoch, *, control):
    """Require the controller's one atomic shared four-hour supplement window."""
    value = control.checked(Path(directory) / "class_recovery_window/record.json")
    start, end = value.get("started_epoch"), value.get("deadline_epoch")
    control.require(
        all(
            type(item) in (int, float) and math.isfinite(item)
            for item in (start, end, deadline_epoch)
        )
        and end == start + 14400
        and 0 < start < deadline_epoch <= end,
        "class supplement cannot extend or reset its shared four-hour deadline",
    )
    control.require(
        value["schema"] == "v40_single_bounded_class_completion_window.v1"
        and (context["seed"], context["arm"], context["step"]) == COORDINATE
        and (value["seed"], value["arm"], value["step"]) == COORDINATE
        and value["protocol_id"] == plan["id"]
        and value["context_id"] == context["id"]
        and value["window_seconds"] == 14400
        and value["allowed_stages"] == list(NEW_STAGES)
        and value["first_dispatched_shard"] in NEW_STAGES
        and stage in NEW_STAGES
        and value["inherited_task_count"] == 186
        and value["remaining_task_count"] == 558
        and value["authorization"] == plan["partial_class_completion_authorization"],
        "class supplement window does not belong to this authorized point/stage/protocol",
    )
    return value


class ProductionTaskOverlay:
    def __init__(self, parent, context, directory, stage, binding, bundle, *, control):
        self.control, self.stage = control, stage
        self.root = Path(directory).resolve() / "task_cache"
        self.index = binding
        control.require(
            (context["seed"], context["arm"], context["step"]) == COORDINATE
            and (binding["seed"], binding["arm"], binding["step"]) == COORDINATE
            and binding["original_context_id"] == context["id"]
            and binding["allowed_new_stages"] == list(NEW_STAGES)
            and stage in (*NEW_STAGES, "virtual_point", "replay_R3", "distribution", "train")
            and type(parent) is bundle.context.ProductionTaskCache,
            "only the registered partial C-only251 class cache may use this overlay",
        )
        control.require(
            Path(parent.root).resolve()
            == Path(context["task_cache_root"])
            == Path(binding["parent_cache_root"])
            and self.root == Path(binding["local_cache_root"])
            and parent.binding == context["task_binding"]
            and parent.binding_sha256 == binding["binding_sha256"]
            and parent.plan["id"] == binding["task_plan_id"]
            and parent.parameter_spec == context["parameter_spec"]
            and self.root != Path(parent.root).resolve(),
            "overlay changed the original point/binding/specification or cache roots",
        )
        self.parent, self.plan, self.binding, self.parameter_spec, self.rt = (
            parent,
            parent.plan,
            parent.binding,
            parent.parameter_spec,
            parent.rt,
        )
        self.binding_sha256 = parent.binding_sha256
        task_ids = self.plan["task_ids"]
        parent_ids = self.plan["assignments"][2]["task_ids"]
        parent_set = set(parent_ids)
        local_ids = [task for task in task_ids if task not in parent_set]
        records = binding["parent_records"]
        control.require(
            len(task_ids) == len(set(task_ids)) == 744
            and len(parent_ids) == 186
            and len(local_ids) == 558
            and binding["parent_task_ids"] == parent_ids
            and binding["local_task_ids"] == local_ids
            and [row["task_id"] for row in records] == parent_ids
            and set(local_ids)
            == {
                task for index in (0, 1, 3) for task in self.plan["assignments"][index]["task_ids"]
            },
            "overlay ownership must be original shard02 plus the other three shards",
        )
        self.parents = {row["task_id"]: row for row in records}
        self.locals = set(local_ids)
        self.commit_allowed = (
            set(self.plan["assignments"][int(stage[-2:])]["task_ids"])
            if stage in NEW_STAGES
            else set()
        )
        self.local = bundle.context.ProductionTaskCache(
            self.root,
            self.binding,
            self.plan,
            self.parameter_spec,
            bundle.rt,
            original_cache_module=bundle.original_cache,
        )
        self._check_scope()
        for task in parent_ids:
            self._check_parent(task)

    def _check_scope(self):
        control = self.control
        parent_root = Path(self.parent.root)
        control.require(
            parent_root.is_dir()
            and not parent_root.is_symlink()
            and {path.name for path in parent_root.iterdir()}
            == {self.parent.directory(task).name for task in self.parents},
            "parent cache must contain exactly its registered 186 complete tasks",
        )
        control.require(not self.root.is_symlink(), "local cache cannot be redirected")
        if self.root.exists():
            control.require(self.root.is_dir(), "local cache root must be a directory")
            allowed = {self.local.directory(task).name for task in self.locals}
            control.require(
                all(
                    not path.is_symlink() and path.name in allowed
                    for path in self.root.iterdir()
                    if path.name.startswith("task")
                ),
                "local cache may not shadow parent tasks or add unknown tasks",
            )

    def _check_parent(self, task):
        directory, reference = self.parent.directory(task), self.parents[task]
        record_path, gradient_path = directory / "record.json", directory / "gradient.pt"
        control = self.control
        control.require(
            directory.is_dir()
            and not directory.is_symlink()
            and {path.name for path in directory.iterdir()} == {"record.json", "gradient.pt"}
            and control.entry(record_path) == reference["record"]
            and _identity(record_path) == reference["record_file_identity"]
            and _identity(gradient_path) == reference["gradient_file_identity"]
            and reference["gradient"]["path"] == str(gradient_path)
            and reference["gradient"]["bytes"] == gradient_path.stat().st_size,
            "registered read-only parent task changed or is incomplete",
        )
        record = control.checked(record_path)
        control.require(
            record["binding"] == self.binding
            and record["task_plan_id"] == self.plan["id"]
            and record["task"] == self.task(task)
            and record["gradient_sha256"] == reference["gradient"]["sha256"],
            "parent task metadata differs from the exact current-point overlay",
        )
        local = self.local.directory(task)
        control.require(
            not local.exists() and not local.is_symlink(),
            "local task cannot shadow parent",
        )

    def task(self, task_id):
        return self.parent.task(task_id)

    def directory(self, task_id):
        self.task(task_id)
        return (self.parent if task_id in self.parents else self.local).directory(task_id)

    def _reader(self, task_id):
        self.task(task_id)
        if task_id in self.parents:
            self._check_parent(task_id)
            return self.parent
        self.control.require(task_id in self.locals, "unknown overlay task")
        parent = self.parent.directory(task_id)
        self.control.require(
            not parent.exists() and not parent.is_symlink(),
            "unregistered parent task cannot substitute for new work",
        )
        return self.local

    def has(self, task_id):
        return self._reader(task_id).has(task_id)

    def read(self, task_id):
        return self._reader(task_id).read(task_id)

    def commit(self, task_id, values_cpu, receipt=None):
        self.control.require(
            task_id in self.commit_allowed
            and task_id in self.locals
            and task_id not in self.parents,
            "only the dispatched new shard may write its own previously uncomputed tasks",
        )
        self._reader(task_id)
        return self.local.commit(task_id, values_cpu, receipt=receipt)

    def assemble(self, device="cpu"):
        self._check_scope()
        self.control.require(
            all(self.local.directory(task).is_dir() for task in self.locals),
            "all 558 complete local tasks are required; no subset or zero fill",
        )
        values = {task: self.read(task) for task in self.plan["task_ids"]}
        return {
            task: self.rt.v8._DeviceGradients(states, device) for task, states in values.items()
        }

    def coverage(self):
        complete = [task for task in self.plan["task_ids"] if self.has(task)]
        present = set(complete)
        return dict(
            complete_task_ids=complete,
            missing_task_ids=[task for task in self.plan["task_ids"] if task not in present],
            complete_task_count=len(complete),
            total_task_count=len(self.plan["task_ids"]),
        )

    def verification_summary(self):
        parent = self.parent.verification_summary()
        local = self.local.verification_summary()
        verified = set(parent["verified_task_ids"]) | set(local["verified_task_ids"])
        return dict(
            binding_sha256=self.binding_sha256,
            process_id=parent["process_id"],
            strict_payload_file_reads=(
                parent["strict_payload_file_reads"] + local["strict_payload_file_reads"]
            ),
            verified_task_count=len(verified),
            verified_task_ids=[task for task in self.plan["task_ids"] if task in verified],
            parent_tasks_strictly_verified=parent["verified_task_count"],
            local_tasks_strictly_verified=local["verified_task_count"],
            registered_parent_task_count=186,
            registered_new_task_count=558,
            parent_gradient_payload_bytes_copied=0,
            parent_artifacts_written=False,
            cross_process_verification_waiver=False,
            cross_parameter_point_reuse=False,
            original_task_order_preserved=True,
        )


def build_overlay(parent_cache, context, directory, stage, binding, bundle, *, control):
    return ProductionTaskOverlay(
        parent_cache, context, directory, stage, binding, bundle, control=control
    )
