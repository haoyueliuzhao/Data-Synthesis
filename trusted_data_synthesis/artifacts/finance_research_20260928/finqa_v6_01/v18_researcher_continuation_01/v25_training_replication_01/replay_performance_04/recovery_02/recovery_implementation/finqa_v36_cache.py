"""Read-only 741-task parent index plus exactly three new V35 task checkpoints.

No mathematical binding, tensor, task plan, or old artifact is rewritten. The
index only binds immutable parent record paths and file identities. Actual
tensor/hash/finite checks are delegated to the byte-identical V35 reader before
values are consumed. A verified value may be reused only inside the same live
process; a JSON receipt never waives verification in another worker.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

ALLOWED_NEW = {
    739: "WELL/2017/page_116.pdf-4",
    741: "WELL/2017/page_48.pdf-2",
    743: "WELL/2017/page_48.pdf-4",
}
STAGES = ("shard00", "shard01", "shard02", "shard03")
INDEX_SCHEMA = "v36_read_only_parent_task_cache_index.v1"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def checked(path):
    value = json.loads(Path(path).read_bytes())
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "sealed overlay/index record changed",
    )
    return value


def file_ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def entry(path):
    return {**file_ref(path), "id": checked(path)["id"]}


def _file_identity(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "cache file missing or symlinked")
    value = path.stat()
    return dict(
        device=value.st_dev,
        inode=value.st_ino,
        size=value.st_size,
        mtime_ns=value.st_mtime_ns,
        ctime_ns=value.st_ctime_ns,
    )


def _paths(directory):
    directory = Path(directory)
    require(
        directory.is_dir() and not directory.is_symlink(), "task directory missing or symlinked"
    )
    require(
        {p.name for p in directory.iterdir()} == {"record.json", "gradient.pt"},
        "partial or unexpected task checkpoint contents",
    )
    return directory / "record.json", directory / "gradient.pt"


def _record_metadata(directory, task, binding, plan):
    record_path, gradient_path = _paths(directory)
    record = checked(record_path)
    require(
        record.get("schema") == "v35_complete_task_gradient.v1"
        and record.get("complete_task") is True
        and record.get("binding") == binding
        and record.get("binding_sha256") == digest(binding)
        and record.get("task_plan_id") == plan["id"]
        and record.get("task") == task
        and record.get("parameter_spec") == plan["parameter_spec"],
        "parent/local cache mathematical binding or task coordinates differ",
    )
    record_stat = _file_identity(record_path)
    gradient_stat = _file_identity(gradient_path)
    require(gradient_stat["size"] == record["gradient_bytes"], "gradient file length differs")
    return record, dict(
        task_id=task["task_id"],
        index=task["index"],
        record=entry(record_path),
        gradient=dict(
            path=str(gradient_path.resolve()),
            sha256=record["gradient_sha256"],
            bytes=record["gradient_bytes"],
        ),
        record_file_identity=record_stat,
        gradient_file_identity=gradient_stat,
    )


def _fixed_scope(plan):
    require(
        len(plan["task_ids"]) == len(plan["tasks"]) == 744
        and [task["index"] for task in plan["tasks"]] == list(range(744))
        and [task["task_id"] for task in plan["tasks"]] == plan["task_ids"]
        and len(set(plan["task_ids"])) == 744,
        "the original 744-task order is required",
    )
    for index, task_id in ALLOWED_NEW.items():
        require(
            plan["tasks"][index]["task_id"] == task_id and plan["tasks"][index]["shard"] == 1,
            "new work differs from the three authorized original tasks",
        )
    require(
        sum(plan["tasks"][index]["row_count"] for index in ALLOWED_NEW) == 26,
        "only the original complete three tasks / 26 rows are authorized",
    )


def prepare_index(oldV35root, recovery1root, newroot, base):
    """Publish only metadata: no .pt copy, load, full SHA scan, GPU or API."""
    old, parent, root = map(lambda p: Path(p).resolve(), (oldV35root, recovery1root, newroot))
    require(
        parent == old / "recovery_01" and root == old / "recovery_02",
        "fixed original/recovery_01/recovery_02 lineage required",
    )
    require(
        not (root / "cache_index/record.json").exists() and not (root / "task_cache").exists(),
        "overlay registration cannot overwrite existing work",
    )
    original = base.checked_protocol(old)
    parent_protocol = base.checked(parent / "protocol/record.json")
    plan = base.read_ref(original["task_plan"])
    binding = original["task_binding"]
    _fixed_scope(plan)
    require(
        parent_protocol["task_binding"] == binding
        and parent_protocol["task_plan"] == original["task_plan"],
        "parent task math was rebound",
    )
    failure = base.checked(parent / "failure/record.json")
    closeout = base.checked(parent / "closeout_01/record.json")
    require(
        failure["protocol_id"] == parent_protocol["id"]
        and failure["original_B_resume_authorized"] is False
        and failure["original_V35_failure_reclassified"] is False
        and closeout["status"] == "STOPPED_FAILURE_NO_RETRY"
        and closeout["durable_complete_tasks"] == 741
        and closeout["global_coordinator_launched"] is False
        and closeout["original_B_resume_authorized"] is False,
        "parent failed closeout/coverage is not the authorized overlay source",
    )
    coverage = failure["task_cache_coverage"]
    allowed = list(ALLOWED_NEW.values())
    expected_parent = [task for task in plan["task_ids"] if task not in set(allowed)]
    require(
        coverage["task_plan_id"] == plan["id"]
        and coverage["binding_sha256"] == digest(binding)
        and coverage["complete_task_count"] == 741
        and coverage["total_task_count"] == 744
        and coverage["complete_task_ids"] == expected_parent
        and coverage["missing_task_ids"] == allowed,
        "sealed parent coverage is not exactly 741 plus the three authorized gaps",
    )
    references = {item["task_id"]: item for item in coverage["task_records"]}
    require(list(references) == expected_parent, "parent record reference order/coverage differs")
    parent_cache = parent / "task_cache"
    require(parent_cache.is_dir() and not parent_cache.is_symlink(), "parent cache root is invalid")
    indexed = []
    tasks = {task["task_id"]: task for task in plan["tasks"]}
    for task in plan["tasks"]:
        directory = parent_cache / f"task{task['index']:04d}"
        if task["index"] in ALLOWED_NEW:
            require(
                not directory.exists() and not directory.is_symlink(),
                "an authorized missing task already has an unregistered parent checkpoint",
            )
            continue
        _record, reference = _record_metadata(directory, task, binding, plan)
        require(
            reference["record"]
            == {k: v for k, v in references[task["task_id"]].items() if k != "task_id"},
            "parent record differs from sealed failed-attempt coverage",
        )
        indexed.append(reference)
    inherited = {}
    for stage, source, protocol in (
        ("shard00", old, original),
        ("shard02", parent, parent_protocol),
        ("shard03", parent, parent_protocol),
    ):
        result_path, exit_path = (
            source / stage / "result/record.json",
            source / stage / "exit/record.json",
        )
        result, exited = base.checked(result_path), base.checked(exit_path)
        require(
            exited["protocol_id"] == result["protocol_id"] == protocol["id"]
            and exited["stage"] == stage
            and exited["returncode"] == 0
            and result["model_released"] is True,
            "inherited stage lacks a real successful result/exit",
        )
        base.check_result(protocol, stage, result, plan)
        inherited[stage] = dict(
            result=base.entry(result_path),
            exit=base.entry(exit_path),
            launch=base.entry(source / stage / "launch/record.json"),
        )
    by_shard = []
    for assignment in plan["assignments"]:
        complete = [task for task in assignment["task_ids"] if task not in set(allowed)]
        missing = [task for task in assignment["task_ids"] if task in set(allowed)]
        by_shard.append(
            dict(
                stage=STAGES[assignment["shard"]],
                complete_task_ids=complete,
                missing_task_ids=missing,
                complete_task_count=len(complete),
                missing_task_count=len(missing),
                remaining_rows=sum(tasks[task]["row_count"] for task in missing),
            )
        )
    return base.publish(
        root / "cache_index/record.json",
        dict(
            schema=INDEX_SCHEMA,
            at=base.now(),
            output_root=str(root),
            source_protocol=base.entry(old / "protocol/record.json"),
            parent_protocol=base.entry(parent / "protocol/record.json"),
            parent_failure=base.entry(parent / "failure/record.json"),
            parent_closeout=base.entry(parent / "closeout_01/record.json"),
            task_plan=original["task_plan"],
            task_plan_id=plan["id"],
            task_binding=copy.deepcopy(binding),
            task_binding_sha256=digest(binding),
            original_math_binding_unchanged=True,
            parent_cache_root=str(parent_cache),
            local_cache_root=str(root / "task_cache"),
            parent_records=indexed,
            complete_task_ids=expected_parent,
            complete_task_count=741,
            missing_task_ids=allowed,
            missing_task_count=3,
            total_task_count=744,
            allowed_new_indices=list(ALLOWED_NEW),
            remaining_rows=26,
            by_shard=by_shard,
            inherited_completed_stages=inherited,
            parent_successful_results_not_inferred_from_controller_completion_list=True,
            parent_file_hash_and_tensor_validation_deferred_until_actual_reader=True,
            full_parent_tensor_validation_stage=(
                "coordinator before CUDA; shard01 separately validates only its 183 reused tasks"
            ),
            metadata_index_is_not_tensor_acceptance=True,
            copied_gradient_bytes=0,
            parent_artifacts_read_only=True,
            hardlinks_or_symlinks_created=False,
            verification_cache_scope=(
                "same process, same binding/index, "
                "unchanged file identities and tensor versions only"
            ),
            cross_process_verification_waiver=False,
            parent_stop_and_PID_admission_owned_by_controller=True,
            original_failures_reclassified=False,
            original_B_resume_authorized=False,
        ),
    )


def _checked_index(root, binding, plan):
    root = Path(root).resolve()
    require(root.name == "recovery_02", "overlay root must be recovery_02")
    index = checked(root / "cache_index/record.json")
    _fixed_scope(plan)
    parent_root = root.parent / "recovery_01/task_cache"
    require(
        index["schema"] == INDEX_SCHEMA
        and index["output_root"] == str(root)
        and index["local_cache_root"] == str(root / "task_cache")
        and index["parent_cache_root"] == str(parent_root)
        and index["task_binding"] == binding
        and index["task_binding_sha256"] == digest(binding)
        and index["task_plan_id"] == plan["id"]
        and index["task_plan"]["id"] == plan["id"]
        and index["allowed_new_indices"] == list(ALLOWED_NEW)
        and index["missing_task_ids"] == list(ALLOWED_NEW.values())
        and index["complete_task_count"] == 741
        and index["missing_task_count"] == 3
        and index["total_task_count"] == 744
        and index["remaining_rows"] == 26
        and index["parent_artifacts_read_only"] is True
        and index["copied_gradient_bytes"] == 0
        and index["cross_process_verification_waiver"] is False,
        "overlay source/index/math binding changed",
    )
    expected = [task for task in plan["task_ids"] if task not in set(ALLOWED_NEW.values())]
    require(
        index["complete_task_ids"] == expected
        and [row["task_id"] for row in index["parent_records"]] == expected,
        "indexed parent task coverage or order differs",
    )
    return index


def _parent_metadata(index, reference, task, binding, plan):
    directory = Path(index["parent_cache_root"]) / f"task{task['index']:04d}"
    require(
        reference["index"] == task["index"]
        and reference["record"]["path"] == str(directory / "record.json")
        and reference["gradient"]["path"] == str(directory / "gradient.pt"),
        "parent task path escaped the pinned read-only cache",
    )
    record, observed = _record_metadata(directory, task, binding, plan)
    require(observed == reference, "parent indexed record/file identity changed")
    return record


def inspect_completed(root, binding, task_plan, task_ids=None):
    """Metadata-only controller coverage. Never implies tensor acceptance."""
    cache_root = Path(root).resolve()
    index = _checked_index(cache_root.parent, binding, task_plan)
    require(cache_root == Path(index["local_cache_root"]), "wrong local overlay cache root")
    requested = list(task_plan["task_ids"] if task_ids is None else task_ids)
    require(
        len(set(requested)) == len(requested) and set(requested) <= set(task_plan["task_ids"]),
        "unknown or duplicate requested tasks",
    )
    parent = {row["task_id"]: row for row in index["parent_records"]}
    result = []
    for task in task_plan["tasks"]:
        task_id = task["task_id"]
        if task_id not in set(requested):
            continue
        local = cache_root / f"task{task['index']:04d}"
        if task_id in parent:
            require(
                not local.exists() and not local.is_symlink(),
                "local cache cannot shadow a parent task",
            )
            record = _parent_metadata(index, parent[task_id], task, binding, task_plan)
            reference = parent[task_id]["record"]
        else:
            if not local.exists() and not local.is_symlink():
                continue
            record, metadata = _record_metadata(local, task, binding, task_plan)
            reference = metadata["record"]
        result.append(
            dict(
                task_id=task_id,
                **reference,
                record=record,
                metadata_only_tensor_acceptance_deferred=True,
            )
        )
    return result


def inspect_overlay(root, *, complete):
    """Controller admission over the bound parent/local metadata union only."""
    root = Path(root).resolve()
    index = checked(root / "cache_index/record.json")
    plan_ref = index["task_plan"]
    require(entry(plan_ref["path"]) == plan_ref, "original task plan reference changed")
    plan = checked(plan_ref["path"])
    rows = inspect_completed(root / "task_cache", index["task_binding"], plan)
    completed = [row["task_id"] for row in rows]
    missing = [task for task in plan["task_ids"] if task not in set(completed)]
    if complete:
        require(not missing, "all 744 complete task checkpoints required before coordinator")
    return dict(
        task_plan_id=plan["id"],
        binding_sha256=index["task_binding_sha256"],
        task_records=[
            {
                key: value
                for key, value in row.items()
                if key not in {"record", "metadata_only_tensor_acceptance_deferred"}
            }
            for row in rows
        ],
        complete_task_ids=completed,
        missing_task_ids=missing,
        complete_task_count=len(completed),
        total_task_count=len(plan["task_ids"]),
        tensor_deserialization_and_finite_checks_required_in_coordinator_before_CUDA=True,
    )


class VerifiedState:
    """Nonserializable-by-contract live-process values, not a durable waiver."""

    def __init__(self, identity):
        self.identity = identity
        self.pid = os.getpid()
        self.values = {}
        self.file_reads = 0

    def __getstate__(self):
        raise TypeError("verified tensor state cannot authorize another process")


def _value_identity(values):
    return tuple(
        (
            state,
            tuple(
                (
                    name,
                    id(tensor),
                    tensor._version,
                    tensor.untyped_storage()._cdata,
                    tuple(tensor.shape),
                    tuple(tensor.stride()),
                    tensor.storage_offset(),
                    str(tensor.dtype),
                )
                for name, tensor in tensors.items()
            ),
        )
        for state, tensors in values.items()
    )


class OverlayTaskCache:
    def __init__(
        self,
        root,
        binding,
        task_plan,
        parameter_spec,
        rt,
        *,
        original_cache_module,
        verified_state=None,
    ):
        self.root = Path(root).resolve()
        self.index = _checked_index(self.root.parent, binding, task_plan)
        require(str(self.root) == self.index["local_cache_root"], "wrong overlay local cache root")
        self.original = original_cache_module
        self.local = self.original.TaskCache(self.root, binding, task_plan, parameter_spec, rt)
        self.parent = self.original.TaskCache(
            self.index["parent_cache_root"], binding, task_plan, parameter_spec, rt
        )
        self.plan, self.binding, self.parameter_spec, self.rt = (
            self.local.plan,
            self.local.binding,
            self.local.parameter_spec,
            rt,
        )
        self.binding_sha256 = self.local.binding_sha256
        self.parents = {row["task_id"]: row for row in self.index["parent_records"]}
        identity = digest(
            dict(
                index_id=self.index["id"],
                root=str(self.root),
                binding=self.binding,
                parameter_spec=self.parameter_spec,
            )
        )
        self.verified_state = (
            verified_state if verified_state is not None else VerifiedState(identity)
        )
        require(
            isinstance(self.verified_state, VerifiedState)
            and self.verified_state.identity == identity
            and self.verified_state.pid == os.getpid(),
            "verified state belongs to another process/index/binding",
        )
        if self.root.exists():
            require(self.root.is_dir() and not self.root.is_symlink(), "invalid local cache root")
            for child in self.root.iterdir():
                if child.name.startswith("task"):
                    require(
                        child.name in {f"task{index:04d}" for index in ALLOWED_NEW},
                        "local cache contains an unauthorized parent/unknown task",
                    )

    def task(self, task_id):
        return self.local.task(task_id)

    def directory(self, task_id):
        self.task(task_id)
        return (self.parent if task_id in self.parents else self.local).directory(task_id)

    def _reader(self, task_id):
        task = self.task(task_id)
        local = self.local.directory(task_id)
        if task_id in self.parents:
            require(
                not local.exists() and not local.is_symlink(), "parent cache cannot be shadowed"
            )
            _parent_metadata(self.index, self.parents[task_id], task, self.binding, self.plan)
            return self.parent
        require(task["index"] in ALLOWED_NEW, "task is outside authorized overlay scope")
        return self.local

    def _read(self, task_id):
        reader = self._reader(task_id)
        directory = reader.directory(task_id)
        record_path, gradient_path = _paths(directory)
        before = (_file_identity(record_path), _file_identity(gradient_path))
        old = self.verified_state.values.get(task_id)
        if old is not None:
            values, record, file_identity, tensor_identity = old
            require(
                file_identity == before and tensor_identity == _value_identity(values),
                "previously verified file or CPU tensor changed",
            )
            return values, record
        values, record = reader._read(task_id)
        after = (_file_identity(record_path), _file_identity(gradient_path))
        require(before == after, "cache files changed during strict tensor verification")
        self.verified_state.values[task_id] = (values, record, after, _value_identity(values))
        self.verified_state.file_reads += 1
        return values, record

    def has(self, task_id):
        reader = self._reader(task_id)
        directory = reader.directory(task_id)
        if not directory.exists() and not directory.is_symlink():
            return False
        self._read(task_id)
        return True

    def read(self, task_id):
        return self._read(task_id)[0]

    def commit(self, task_id, values_cpu, receipt=None):
        task = self.task(task_id)
        require(
            task_id not in self.parents and task["index"] in ALLOWED_NEW,
            "read-only parent/unknown task cannot be committed",
        )
        return self.local.commit(task_id, values_cpu, receipt=receipt)

    def get_or_compute(self, task_id, compute):
        if self.has(task_id):
            return self.read(task_id), True
        values = compute()
        self.commit(task_id, values)
        return values, False

    def completed_records(self, task_ids=None):
        return inspect_completed(self.root, self.binding, self.plan, task_ids)

    def coverage(self):
        complete = [task_id for task_id in self.plan["task_ids"] if self.has(task_id)]
        return dict(
            complete_task_ids=complete,
            missing_task_ids=[task for task in self.plan["task_ids"] if task not in set(complete)],
            complete_task_count=len(complete),
            total_task_count=len(self.plan["task_ids"]),
        )

    def _require_complete(self):
        # Fail on any of the three missing local tasks before loading 741 parent
        # payloads. Parent paths/bytes are still checked when each value is read.
        for task_id in ALLOWED_NEW.values():
            directory = self.local.directory(task_id)
            require(
                directory.is_dir() and not directory.is_symlink(),
                "missing complete authorized local task; no zero fill",
            )

    def assemble(self, device="cpu"):
        self._require_complete()
        values = {task_id: self.read(task_id) for task_id in self.plan["task_ids"]}
        return {
            task_id: self.rt.v8._DeviceGradients(states, device)
            for task_id, states in values.items()
        }

    def validate_complete(self):
        self._require_complete()
        records = []
        for task_id in self.plan["task_ids"]:
            _, record = self._read(task_id)
            records.append(dict(task_id=task_id, **entry(self.directory(task_id) / "record.json")))
            require(records[-1]["id"] == record["id"], "record changed after tensor validation")
        return dict(
            task_plan_id=self.plan["id"],
            binding_sha256=self.binding_sha256,
            task_records=records,
            complete_task_count=len(records),
            total_task_count=len(self.plan["task_ids"]),
            verification=self.verification_summary(),
        )

    def verification_summary(self):
        verified = set(self.verified_state.values)
        return dict(
            index_id=self.index["id"],
            process_id=self.verified_state.pid,
            parent_tasks_strictly_verified=len(verified & set(self.parents)),
            local_tasks_strictly_verified=len(verified - set(self.parents)),
            strict_payload_file_reads=self.verified_state.file_reads,
            verified_task_ids=[task for task in self.plan["task_ids"] if task in verified],
            cross_process_verification_waiver=False,
            parent_gradient_payload_bytes_copied=0,
        )


def overlay_adapter(root, original_cache_module, control=None):
    """Adapt storage only; the original pool/plan/math callables are identical."""
    root = Path(root).resolve()

    def factory(cache_root, binding, task_plan, parameter_spec, rt, *, verified_state=None):
        require(
            Path(cache_root).resolve() == root / "task_cache", "worker requested another cache root"
        )
        return OverlayTaskCache(
            cache_root,
            binding,
            task_plan,
            parameter_spec,
            rt,
            original_cache_module=original_cache_module,
            verified_state=verified_state,
        )

    class Adapter(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(original_cache_module, name)

    return Adapter(
        TaskCache=factory,
        inspect_completed=inspect_completed,
        __file__=original_cache_module.__file__,
        overlay_source=__file__,
        original_cache_module=original_cache_module,
        TaskPoolView=original_cache_module.TaskPoolView,
        make_task_plan=original_cache_module.make_task_plan,
    )
