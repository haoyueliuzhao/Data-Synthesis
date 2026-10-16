"""Read-only, same-point union of complete inherited production task caches.

Actual tensors are still read and validated by the unchanged ProductionTaskCache.
This module only routes each registered original task to its unique source root;
it cannot write, compute, fill missing tasks, or reorder the global aggregation.
"""

from __future__ import annotations

import stat
from pathlib import Path

SCHEMA = "v41_complete_read_only_task_cache_view.v1"


def _identity(path):
    path = Path(path)
    info = path.lstat()
    if path != path.resolve() or not stat.S_ISREG(info.st_mode):
        raise ValueError("read-only task payload must be an unredirected regular file")
    return dict(
        path=str(path),
        device=info.st_dev,
        inode=info.st_ino,
        bytes=info.st_size,
        mtime_ns=info.st_mtime_ns,
        ctime_ns=info.st_ctime_ns,
    )


class ReadOnlyProductionTaskView:
    def __init__(self, parent, context, directory, stage, binding, bundle, *, control):
        self.control, self.index, self.stage = control, binding, stage
        self.root = Path(directory).resolve() / "task_cache"
        control.require(
            stage in ("virtual_point", "replay_R3", "distribution", "train")
            and type(parent) is bundle.context.ProductionTaskCache
            and binding.get("schema") == SCHEMA
            and binding.get("read_only") is True
            and binding.get("writes_allowed") is False
            and binding.get("original_context_id") == context["id"],
            "only complete inherited class caches may have a read-only consumption view",
        )
        self.parent, self.plan, self.binding, self.parameter_spec, self.rt = (
            parent,
            parent.plan,
            parent.binding,
            parent.parameter_spec,
            parent.rt,
        )
        self.binding_sha256 = parent.binding_sha256
        control.require(
            Path(parent.root).resolve() == Path(context["task_cache_root"])
            and self.binding == context["task_binding"]
            and self.parameter_spec == context["parameter_spec"]
            and binding.get("task_plan_id") == self.plan["id"]
            and binding.get("task_plan") == context["task_plan"]
            and control.read_ref(binding["task_plan"]) == self.plan
            and binding.get("binding_sha256") == self.binding_sha256
            and binding.get("task_ids") == self.plan["task_ids"],
            "read-only cache view changed the original point/plan/binding/parameter order",
        )
        task_ids = self.plan["task_ids"]
        records, sources = binding.get("task_records"), binding.get("cache_sources")
        control.require(
            bool(task_ids)
            and len(task_ids) == len(set(task_ids))
            and isinstance(records, list)
            and [row.get("task_id") for row in records] == task_ids
            and isinstance(sources, list)
            and bool(sources),
            "read-only cache view needs every original task exactly once in original order",
        )
        self.records = {row["task_id"]: row for row in records}
        self.readers, self.owners, self.source_ids = {}, {}, {}
        for source in sources:
            root = Path(source["cache_root"])
            selected = source["task_ids"]
            control.require(
                root.is_absolute()
                and root == root.resolve()
                and root.is_dir()
                and not root.is_symlink()
                and root != self.root
                and str(root) not in self.readers
                and isinstance(selected, list)
                and bool(selected)
                and len(selected) == len(set(selected))
                and set(selected) <= set(task_ids)
                and selected == [task for task in task_ids if task in set(selected)]
                and not (set(selected) & set(self.owners)),
                "source roots/tasks must be unique, disjoint, immutable and in original order",
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
            self.readers[str(root)], self.source_ids[str(root)] = reader, list(selected)
            for task in selected:
                control.require(
                    self.records[task].get("cache_root") == str(root),
                    "task record ownership differs from registered source root",
                )
                self.owners[task] = str(root)
        control.require(
            set(self.owners) == set(task_ids),
            "every original task must have one complete source; no subset or zero fill",
        )
        self._check_scope()
        # Registration/file identity checks are cheap; actual tensor/hash/shape
        # verification remains per-process in ProductionTaskCache.read().
        for task in task_ids:
            self._check_record(task)

    def _check_scope(self):
        self.control.require(
            not self.root.exists() and not self.root.is_symlink(),
            "an inherited read-only view cannot shadow tasks in a new local cache",
        )
        for root, reader in self.readers.items():
            path = Path(root)
            self.control.require(
                path.is_dir()
                and not path.is_symlink()
                and path == path.resolve()
                and {item.name for item in path.iterdir()}
                == {reader.directory(task).name for task in self.source_ids[root]},
                "source cache must contain exactly its registered complete task ownership",
            )

    def task(self, task_id):
        return self.parent.task(task_id)

    def directory(self, task_id):
        self.task(task_id)
        return self.readers[self.owners[task_id]].directory(task_id)

    def _check_record(self, task_id):
        directory, reference = self.directory(task_id), self.records[task_id]
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
            "registered read-only task changed, moved or is incomplete",
        )
        record = control.checked(record_path)
        control.require(
            record["binding"] == self.binding
            and record["task_plan_id"] == self.plan["id"]
            and record["task"] == self.task(task_id)
            and record["gradient_sha256"] == reference["gradient"]["sha256"],
            "read-only task metadata differs from its bound actual parameter point",
        )

    def read(self, task_id):
        self._check_record(task_id)
        return self.readers[self.owners[task_id]].read(task_id)

    def has(self, task_id):
        self.read(task_id)
        return True

    def commit(self, *_args, **_kwargs):
        raise ValueError("inherited complete task cache is read-only; no writes or recomputation")

    def get_or_compute(self, *_args, **_kwargs):
        raise ValueError("inherited complete task cache is read-only; no compute fallback")

    def assemble(self, device="cpu"):
        self._check_scope()
        values = {task: self.read(task) for task in self.plan["task_ids"]}
        return {
            task: self.rt.v8._DeviceGradients(states, device) for task, states in values.items()
        }

    def coverage(self):
        self._check_scope()
        complete = [task for task in self.plan["task_ids"] if self.has(task)]
        return dict(
            complete_task_ids=complete,
            missing_task_ids=[],
            complete_task_count=len(complete),
            total_task_count=len(self.plan["task_ids"]),
        )

    def verification_summary(self):
        reports = [reader.verification_summary() for reader in self.readers.values()]
        verified = {task for report in reports for task in report["verified_task_ids"]}
        self.control.require(
            len({report["process_id"] for report in reports}) == 1,
            "strict task verification cannot be borrowed from another process",
        )
        return dict(
            binding_sha256=self.binding_sha256,
            process_id=reports[0]["process_id"],
            strict_payload_file_reads=sum(
                report["strict_payload_file_reads"] for report in reports
            ),
            verified_task_count=len(verified),
            verified_task_ids=[task for task in self.plan["task_ids"] if task in verified],
            source_count=len(self.readers),
            source_verified_task_counts={
                root: len(set(self.source_ids[root]) & verified) for root in self.readers
            },
            inherited_gradient_payload_bytes_copied=0,
            inherited_artifacts_written=False,
            cross_process_verification_waiver=False,
            cross_parameter_point_reuse=False,
            original_task_order_preserved=True,
            read_only=True,
        )


def build_view(parent_cache, context, directory, stage, binding, bundle, *, control):
    return ReadOnlyProductionTaskView(
        parent_cache, context, directory, stage, binding, bundle, control=control
    )
