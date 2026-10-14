"""Same-point immutable task union plus a fresh, uniquely owned remaining set.

Each task tensor is validated by the original ProductionTaskCache reader. Only
complete task records are inherited; interrupted rows are never a checkpoint.
This routes storage, not gradient mathematics, task order or task/pass counts.
"""

from __future__ import annotations

from pathlib import Path

import finqa_v41_task_view as complete_view
import finqa_v43_time_policy as time_policy

SCHEMA = "v43_same_point_partial_task_cache_union.v1"
SHARDS = tuple(f"shard{i:02d}" for i in range(4))


def allows_new_shard(binding, stage):
    return (
        isinstance(binding, dict)
        and binding.get("schema") == SCHEMA
        and isinstance(binding.get("allowed_new_stages"), list)
        and set(binding["allowed_new_stages"]) <= set(SHARDS)
        and stage in binding["allowed_new_stages"]
    )


def validate_class_window(directory, context, plan, stage, deadline_epoch, *, control):
    import finqa_v43_inheritance as inheritance

    time_policy.validate(plan)
    time_policy.require_no_deadline(deadline_epoch)
    binding = inheritance.task_cache_overlay_binding(directory, plan)
    control.require(
        allows_new_shard(binding, stage) and binding["original_context_id"] == context["id"],
        "remaining class tasks must retain exact same-point ownership",
    )
    return binding


class PartialTaskUnion:
    def __init__(self, parent, context, directory, stage, binding, bundle, *, control):
        self.control, self.index, self.stage = control, binding, stage
        self.root = Path(directory).resolve() / "task_cache"
        self.parent, self.plan, self.binding, self.parameter_spec, self.rt = (
            parent,
            parent.plan,
            parent.binding,
            parent.parameter_spec,
            parent.rt,
        )
        self.binding_sha256 = parent.binding_sha256
        task_ids = self.plan["task_ids"]
        control.require(
            type(parent) is bundle.context.ProductionTaskCache
            and binding.get("schema") == SCHEMA
            and binding["original_context_id"] == context["id"]
            and (binding["seed"], binding["arm"], binding["step"])
            == (context["seed"], context["arm"], context["step"])
            and Path(parent.root).resolve() == Path(context["task_cache_root"])
            and self.root == Path(binding["local_cache_root"])
            and self.binding == context["task_binding"]
            and self.parameter_spec == context["parameter_spec"]
            and binding["binding_sha256"] == self.binding_sha256
            and binding["task_plan_id"] == self.plan["id"]
            and binding["task_plan"] == context["task_plan"]
            and control.read_ref(binding["task_plan"]) == self.plan
            and binding["task_ids"] == task_ids
            and len(task_ids) == len(set(task_ids)),
            "partial task union changed point/plan/binding/parameter order",
        )
        parent_ids, local_ids = binding["parent_task_ids"], binding["local_task_ids"]
        parents, locals_ = set(parent_ids), set(local_ids)
        control.require(
            parent_ids == [task for task in task_ids if task in parents]
            and local_ids == [task for task in task_ids if task in locals_]
            and not parents & locals_
            and parents | locals_ == set(task_ids)
            and len(parent_ids) == len(parents)
            and len(local_ids) == len(locals_)
            and [row["task_id"] for row in binding["task_records"]] == parent_ids,
            "partial task union must cover every original task once without shadowing",
        )
        expected_stages = [
            stage_
            for i, stage_ in enumerate(SHARDS)
            if set(self.plan["assignments"][i]["task_ids"]) & locals_
        ]
        receipt_stages = binding.get("cache_only_receipt_stages", [])
        control.require(
            isinstance(receipt_stages, list)
            and receipt_stages == [s for s in SHARDS if s in set(receipt_stages)]
            and not set(receipt_stages) & set(expected_stages)
            and all(
                set(self.plan["assignments"][SHARDS.index(s)]["task_ids"]) <= parents
                for s in receipt_stages
            ),
            "cache-only stage receipts require every assigned complete parent task",
        )
        expected_stages = [s for s in SHARDS if s in expected_stages or s in receipt_stages]
        control.require(
            binding["allowed_new_stages"] == expected_stages
            and stage in (*expected_stages, "virtual_point", "replay_R3", "distribution", "train"),
            "partial union may dispatch only shards containing missing complete tasks",
        )
        self.records = {row["task_id"]: row for row in binding["task_records"]}
        self.readers, self.owners, self.source_ids = {}, {}, {}
        for source in binding["cache_sources"]:
            root = Path(source["cache_root"])
            selected = source["task_ids"]
            control.require(
                root.is_absolute()
                and root == root.resolve()
                and root.is_dir()
                and not root.is_symlink()
                and root != self.root
                and str(root) not in self.readers
                and bool(selected)
                and selected == [task for task in parent_ids if task in set(selected)]
                and len(selected) == len(set(selected))
                and not (set(selected) & set(self.owners)),
                "task union source ownership is ambiguous or redirected",
            )
            reader = (
                parent
                if root == Path(parent.root).resolve()
                else bundle.context.ProductionTaskCache(
                    root,
                    self.binding,
                    self.plan,
                    self.parameter_spec,
                    bundle.rt,
                    original_cache_module=bundle.original_cache,
                )
            )
            self.readers[str(root)], self.source_ids[str(root)] = reader, selected
            for task in selected:
                control.require(
                    self.records[task]["cache_root"] == str(root),
                    "task source differs from registered owner",
                )
                self.owners[task] = str(root)
        control.require(
            set(self.owners) == parents, "every inherited task requires one immutable owner"
        )
        self.locals = locals_
        self.local = bundle.context.ProductionTaskCache(
            self.root,
            self.binding,
            self.plan,
            self.parameter_spec,
            bundle.rt,
            original_cache_module=bundle.original_cache,
        )
        self.commit_allowed = (
            set(self.plan["assignments"][int(stage[-2:])]["task_ids"]) & self.locals
            if stage in SHARDS
            else set()
        )
        self._check_scope()
        for task in parent_ids:
            self._check_parent(task)

    def _check_scope(self):
        self.control.require(not self.root.is_symlink(), "new task cache cannot be redirected")
        for root, reader in self.readers.items():
            path = Path(root)
            self.control.require(
                path.is_dir()
                and not path.is_symlink()
                and {p.name for p in path.iterdir() if p.name.startswith("task")}
                == {reader.directory(task).name for task in self.source_ids[root]},
                "parent task cache complete ownership changed",
            )
        if self.root.exists():
            allowed = {self.local.directory(task).name for task in self.locals}
            self.control.require(
                self.root.is_dir()
                and all(
                    not p.is_symlink() and p.name in allowed
                    for p in self.root.iterdir()
                    if p.name.startswith("task")
                ),
                "local cache may not shadow inherited tasks",
            )

    def task(self, task_id):
        return self.parent.task(task_id)

    def directory(self, task_id):
        self.task(task_id)
        return (
            self.readers[self.owners[task_id]] if task_id in self.owners else self.local
        ).directory(task_id)

    def _check_parent(self, task_id):
        directory, reference = self.directory(task_id), self.records[task_id]
        record_path, tensor_path = directory / "record.json", directory / "gradient.pt"
        self.control.require(
            directory.is_dir()
            and not directory.is_symlink()
            and {p.name for p in directory.iterdir()} == {"record.json", "gradient.pt"}
            and self.control.entry(record_path) == reference["record"]
            and complete_view._identity(record_path) == reference["record_file_identity"]
            and complete_view._identity(tensor_path) == reference["gradient_file_identity"]
            and reference["gradient"]["path"] == str(tensor_path)
            and reference["gradient"]["bytes"] == tensor_path.stat().st_size,
            "inherited complete task files changed",
        )
        record = self.control.checked(record_path)
        self.control.require(
            record["binding"] == self.binding
            and record["task_plan_id"] == self.plan["id"]
            and record["task"] == self.task(task_id)
            and record["gradient_sha256"] == reference["gradient"]["sha256"]
            and not self.local.directory(task_id).exists(),
            "inherited same-point task metadata changed or shadowed",
        )

    def _reader(self, task_id):
        self.task(task_id)
        if task_id in self.owners:
            self._check_parent(task_id)
            return self.readers[self.owners[task_id]]
        self.control.require(task_id in self.locals, "task is outside registered union")
        return self.local

    def has(self, task_id):
        return self._reader(task_id).has(task_id)

    def read(self, task_id):
        return self._reader(task_id).read(task_id)

    def commit(self, task_id, values_cpu, receipt=None):
        self.control.require(
            task_id in self.commit_allowed and task_id not in self.owners,
            "only dispatched missing complete tasks may be committed",
        )
        return self.local.commit(task_id, values_cpu, receipt=receipt)

    def assemble(self, device="cpu"):
        self._check_scope()
        self.control.require(
            all(self.local.directory(task).is_dir() for task in self.locals),
            "full original task population required; no zero fill or partial class",
        )
        values = {task: self.read(task) for task in self.plan["task_ids"]}
        return {
            task: self.rt.v8._DeviceGradients(states, device) for task, states in values.items()
        }

    def coverage(self):
        complete = [task for task in self.plan["task_ids"] if self.has(task)]
        return dict(
            complete_task_ids=complete,
            missing_task_ids=[task for task in self.plan["task_ids"] if task not in set(complete)],
            complete_task_count=len(complete),
            total_task_count=len(self.plan["task_ids"]),
        )

    def verification_summary(self):
        reports = [reader.verification_summary() for reader in (*self.readers.values(), self.local)]
        verified = {task for report in reports for task in report["verified_task_ids"]}
        self.control.require(
            len({r["process_id"] for r in reports}) == 1, "cross-process verification forbidden"
        )
        return dict(
            binding_sha256=self.binding_sha256,
            process_id=reports[0]["process_id"],
            strict_payload_file_reads=sum(r["strict_payload_file_reads"] for r in reports),
            verified_task_count=len(verified),
            verified_task_ids=[t for t in self.plan["task_ids"] if t in verified],
            parent_tasks_strictly_verified=len(verified & set(self.owners)),
            local_tasks_strictly_verified=len(verified & self.locals),
            registered_parent_task_count=len(self.owners),
            registered_new_task_count=len(self.locals),
            inherited_gradient_payload_bytes_copied=0,
            parent_artifacts_written=False,
            cross_process_verification_waiver=False,
            cross_parameter_point_reuse=False,
            original_task_order_preserved=True,
        )


def build_overlay(parent_cache, context, directory, stage, binding, bundle, *, control):
    if binding.get("schema") == complete_view.SCHEMA:
        return complete_view.build_view(
            parent_cache, context, directory, stage, binding, bundle, control=control
        )
    return PartialTaskUnion(
        parent_cache, context, directory, stage, binding, bundle, control=control
    )
