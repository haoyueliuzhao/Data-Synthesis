"""Whole-task scheduling and immutable CPU class-gradient checkpoints.

This module has no GPU, sampling, optimizer or distribution-update entry point.
It only selects complete original tasks and persists their already-computed
class gradients. The original registration, package/row order, and parameter
coordinates are never renormalized or rewritten.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
from collections.abc import Mapping
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def json_bytes(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def _seal(value):
    return {**value, "id": digest(value)}


def _checked_record(value):
    require(isinstance(value, dict), "record must be an object")
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "record identity/checksum changed",
    )
    return value


def _parameter_spec(spec):
    spec = copy.deepcopy(list(spec))
    require(bool(spec), "empty parameter specification")
    names = [item["name"] for item in spec]
    require(len(set(names)) == len(names), "duplicate parameter coordinates")
    for item in spec:
        require(
            set(item) == {"name", "shape", "dtype"}
            and isinstance(item["name"], str)
            and bool(item["name"])
            and isinstance(item["shape"], list)
            and all(
                isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in item["shape"]
            )
            and item["dtype"] in ("torch.float32", "torch.float64"),
            "invalid parameter specification (FP64 is CPU-fixture only)",
        )
    return spec


class TaskPoolView:
    """A complete-task subset retaining the exact original global registration."""

    def __init__(self, pool, task_ids):
        requested = tuple(task_ids)
        require(bool(requested) and len(set(requested)) == len(requested), "empty/duplicate tasks")
        require(set(requested) <= set(pool.task_ids), "unknown task in pool view")
        self._pool = pool
        self.task_ids = tuple(task for task in pool.task_ids if task in set(requested))
        self._packages = tuple(p for p in pool.packages if p["task_id"] in self.task_ids)
        self._allowed_packages = {p["package_id"] for p in self._packages}
        require(len(self._allowed_packages) == len(self._packages), "duplicate package IDs")
        require(
            {p["task_id"] for p in self._packages} == set(self.task_ids), "incomplete task view"
        )
        # In particular, never instantiate VerifiedPool with a subset: that would
        # silently construct a local uniform mu and a new registration.
        self._manifest = pool._manifest

    def __getattr__(self, name):
        return getattr(self._pool, name)

    @property
    def packages(self):
        return self._packages

    def row_arrays(self, package_id):
        require(package_id in self._allowed_packages, "package is outside complete-task view")
        return self._pool.row_arrays(package_id)


def make_task_plan(pool, parameter_spec, shards=4):
    """Pure-CPU LPT scheduling by effective input-token cost, never by state."""
    require(
        isinstance(shards, int) and not isinstance(shards, bool) and shards > 0, "invalid shards"
    )
    spec = _parameter_spec(parameter_spec)
    task_ids = list(pool.task_ids)
    require(bool(task_ids) and len(set(task_ids)) == len(task_ids), "empty/duplicate source tasks")
    registration = pool._manifest.registration
    require(set(registration.pi0) == set(task_ids), "task view cannot be a planning source")
    packages = list(pool.packages)
    require(len({p["package_id"] for p in packages}) == len(packages), "duplicate source packages")
    require({p["task_id"] for p in packages} == set(task_ids), "source tasks/packages disagree")
    tasks = []
    for index, task_id in enumerate(task_ids):
        state_ids = list(registration.pi0[task_id])
        selected = [p for p in packages if p["task_id"] == task_id]
        require(
            bool(state_ids) and {p["state_id"] for p in selected} == set(state_ids),
            "task state support incomplete",
        )
        items = []
        for package in selected:
            rows = tuple(pool.row_arrays(package["package_id"]))
            denominator = package["whole_package_target_tokens"]
            require(denominator > 0, "nonpositive package target denominator")
            require(
                sum(len(row["target_ids"]) for row in rows) == denominator,
                "complete-package target-token denominator disagrees with rows",
            )
            items.append(
                dict(
                    package_id=package["package_id"],
                    state_id=package["state_id"],
                    whole_package_target_tokens=denominator,
                    row_count=len(rows),
                    input_tokens=sum(len(row["input_ids"]) for row in rows),
                    row_arrays_sha256=digest(rows),
                    original_package_sha256=digest(package),
                )
            )
        tasks.append(
            dict(
                index=index,
                task_id=task_id,
                state_ids=state_ids,
                packages=items,
                row_count=sum(item["row_count"] for item in items),
                input_tokens=sum(item["input_tokens"] for item in items),
            )
        )
    loads = [0] * shards
    for task in sorted(tasks, key=lambda task: (-task["input_tokens"], task["index"])):
        shard = min(range(shards), key=lambda index: (loads[index], index))
        task["shard"] = shard
        loads[shard] += task["input_tokens"]
    assignments = []
    for shard in range(shards):
        selected = [task for task in tasks if task["shard"] == shard]
        assignments.append(
            dict(
                shard=shard,
                task_ids=[task["task_id"] for task in selected],
                task_indices=[task["index"] for task in selected],
                row_count=sum(task["row_count"] for task in selected),
                input_tokens=sum(task["input_tokens"] for task in selected),
            )
        )
    # Convert tuples to JSON arrays up front so round-tripping the plan cannot
    # change equality; dict insertion order remains the original registration.
    global_registration = json.loads(
        json_bytes(
            dict(
                task_ids=task_ids,
                state_support=registration.state_support,
                mu=registration.mu,
                pi0=registration.pi0,
                qualification_registration_id=registration.qualification_registration_id,
                validator_binding_id=registration.validator_binding_id,
                pool_cache_id=pool.cache_id,
            )
        )
    )
    return _seal(
        dict(
            schema="v35_complete_task_plan.v1",
            task_ids=task_ids,
            tasks=tasks,
            assignments=assignments,
            shards=shards,
            scheduling="LPT effective-row input tokens; ties original task index then shard index",
            parameter_spec=spec,
            global_registration=global_registration,
            package_count=len(packages),
            state_count=sum(len(task["state_ids"]) for task in tasks),
            row_count=sum(task["row_count"] for task in tasks),
            input_tokens=sum(task["input_tokens"] for task in tasks),
            all_singleton_control_tasks_included=True,
            local_mu_or_pi_recomputed=False,
        )
    )


def validate_plan(task_plan, pool=None):
    """Check a sealed plan; an actual pool also verifies every original row."""
    _checked_record(task_plan)
    require(task_plan.get("schema") == "v35_complete_task_plan.v1", "unknown task plan schema")
    if pool is not None:
        require(
            make_task_plan(pool, task_plan["parameter_spec"], task_plan["shards"]) == task_plan,
            "task plan differs from frozen actual pool",
        )
    return task_plan


def inspect_completed(root, binding, task_plan, task_ids=None):
    """Stdlib-only durable metadata/file-SHA inspection, not tensor acceptance.

    Missing tasks are not returned. An existing incomplete, tampered, or bound
    to another point/source task is an error. Temporary publisher siblings are
    never treated as completed tasks. The GPU coordinator must additionally
    perform TaskCache's full tensor/semantic validation before global math.
    """
    root = Path(root)
    require(not root.is_symlink(), "cache root cannot be a symlink")
    plan = validate_plan(task_plan)
    tasks = {task["task_id"]: task for task in plan["tasks"]}
    selected = list(plan["task_ids"] if task_ids is None else task_ids)
    require(
        len(set(selected)) == len(selected) and set(selected) <= set(tasks),
        "unknown/duplicate task selection",
    )
    result = []
    for task_id in plan["task_ids"]:
        if task_id not in selected:
            continue
        task = tasks[task_id]
        target = root / f"task{task['index']:04d}"
        if not target.exists() and not target.is_symlink():
            continue
        require(target.is_dir() and not target.is_symlink(), "invalid complete task checkpoint")
        require(
            {entry.name for entry in target.iterdir()} == {"record.json", "gradient.pt"}
            and all(not (target / name).is_symlink() for name in ("record.json", "gradient.pt")),
            "partial/temporary task checkpoint rejected",
        )
        record_path = target / "record.json"
        raw = record_path.read_bytes()
        record = _checked_record(json.loads(raw))
        require(
            record.get("schema") == "v35_complete_task_gradient.v1"
            and record.get("complete_task") is True
            and record.get("binding") == binding
            and record.get("binding_sha256") == digest(binding)
            and record.get("task_plan_id") == plan["id"]
            and record.get("task") == task
            and record.get("parameter_spec") == plan["parameter_spec"],
            "task checkpoint binding/point/source/order differs",
        )
        tensor_path = target / "gradient.pt"
        sha = hashlib.sha256()
        with tensor_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha.update(chunk)
        require(
            tensor_path.stat().st_size == record["gradient_bytes"]
            and sha.hexdigest() == record["gradient_sha256"],
            "gradient file checksum differs",
        )
        result.append(
            dict(
                task_id=task_id,
                path=str(record_path),
                sha256=hashlib.sha256(raw).hexdigest(),
                id=record["id"],
                record=record,
            )
        )
    return result


class TaskCache:
    """One independently atomic no-replace directory per complete original task.

    Binding is supplied by the registered controller and compared in full. It
    must identify the actual point/prestate/material/frozen numerical source and
    storage source. This cache never widens cross-protocol reuse on its own.
    """

    def __init__(self, root, binding, task_plan, parameter_spec, rt):
        self.root = Path(root)
        require(not self.root.is_symlink(), "cache root cannot be a symlink")
        self.plan = copy.deepcopy(_checked_record(task_plan))
        require(self.plan["schema"] == "v35_complete_task_plan.v1", "unknown task plan schema")
        self.parameter_spec = _parameter_spec(parameter_spec)
        require(
            self.parameter_spec == self.plan["parameter_spec"], "parameter specification differs"
        )
        require(isinstance(binding, dict) and bool(binding), "nonempty source binding required")
        self.binding = json.loads(json_bytes(binding))
        self.binding_sha256 = digest(self.binding)
        self.rt = rt
        self.tasks = {task["task_id"]: task for task in self.plan["tasks"]}
        require(list(self.tasks) == self.plan["task_ids"], "task plan order changed")
        require(
            [task["index"] for task in self.tasks.values()] == list(range(len(self.tasks))),
            "noncanonical task indices",
        )

    def task(self, task_id):
        require(task_id in self.tasks, "task is outside frozen plan")
        return self.tasks[task_id]

    def directory(self, task_id):
        return self.root / f"task{self.task(task_id)['index']:04d}"

    def _validate_values(self, task_id, values):
        task = self.task(task_id)
        require(isinstance(values, Mapping), "task values must be a mapping")
        require(list(values) == task["state_ids"], "task states incomplete or out of order")
        names = [item["name"] for item in self.parameter_spec]
        for state, tensors in values.items():
            require(
                isinstance(tensors, Mapping) and list(tensors) == names, "parameter order differs"
            )
            for item in self.parameter_spec:
                tensor = tensors[item["name"]]
                require(
                    isinstance(tensor, self.rt.torch.Tensor)
                    and tensor.device.type == "cpu"
                    and list(tensor.shape) == item["shape"]
                    and str(tensor.dtype) == item["dtype"]
                    and tensor.layout == self.rt.torch.strided
                    and not tensor.requires_grad
                    and bool(self.rt.torch.isfinite(tensor).all()),
                    f"invalid/nonfinite CPU class gradient {task_id}/{state}/{item['name']}",
                )
        return values

    def _tensor_manifest(self, values):
        return [
            dict(
                state_id=state,
                parameters=[
                    dict(
                        name=name,
                        shape=list(tensor.shape),
                        dtype=str(tensor.dtype),
                        sha256=hashlib.sha256(
                            tensor.detach()
                            .contiguous()
                            .reshape(-1)
                            .view(self.rt.torch.uint8)
                            .numpy()
                            .tobytes()
                        ).hexdigest(),
                    )
                    for name, tensor in tensors.items()
                ],
            )
            for state, tensors in values.items()
        ]

    def commit(self, task_id, values_cpu, receipt=None):
        # The controller imports this module before choosing its frozen runtime;
        # never preload mutable trusted_synthesis modules at module import time.
        from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

        target = self.directory(task_id)
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"complete-task cache is immutable: {target}")
        values = self._validate_values(task_id, values_cpu)
        payload = dict(
            schema="v35_complete_task_gradient_payload.v1",
            binding=self.binding,
            task_plan_id=self.plan["id"],
            task=self.task(task_id),
            parameter_spec=self.parameter_spec,
            values_cpu=values,
        )
        stream = io.BytesIO()
        self.rt.torch.save(payload, stream)
        raw = stream.getvalue()
        record = _seal(
            dict(
                schema="v35_complete_task_gradient.v1",
                binding=self.binding,
                binding_sha256=self.binding_sha256,
                task_plan_id=self.plan["id"],
                task=self.task(task_id),
                parameter_spec=self.parameter_spec,
                complete_task=True,
                gradient_sha256=hashlib.sha256(raw).hexdigest(),
                gradient_bytes=len(raw),
                gradient_semantic_digest=self.rt.v8._tree_digest(values),
                payload_semantic_digest=self.rt.v8._tree_digest(payload),
                tensor_manifest=self._tensor_manifest(values),
                receipt=receipt,
            )
        )
        write_immutable_artifact_directory(
            target,
            {
                "record.json": json_bytes(record) + b"\n",
                "gradient.pt": raw,
            },
        )
        return record

    def _read(self, task_id):
        target = self.directory(task_id)
        require(target.is_dir() and not target.is_symlink(), "missing complete task checkpoint")
        require(
            {entry.name for entry in target.iterdir()} == {"record.json", "gradient.pt"}
            and all(not (target / name).is_symlink() for name in ("record.json", "gradient.pt")),
            "partial/temporary task checkpoint rejected",
        )
        record = _checked_record(json.loads((target / "record.json").read_bytes()))
        require(
            record.get("schema") == "v35_complete_task_gradient.v1"
            and record.get("complete_task") is True
            and record.get("binding") == self.binding
            and record.get("binding_sha256") == self.binding_sha256
            and record.get("task_plan_id") == self.plan["id"]
            and record.get("task") == self.task(task_id)
            and record.get("parameter_spec") == self.parameter_spec,
            "task checkpoint binding/point/source/order differs",
        )
        raw = (target / "gradient.pt").read_bytes()
        require(
            len(raw) == record["gradient_bytes"]
            and hashlib.sha256(raw).hexdigest() == record["gradient_sha256"],
            "gradient file checksum differs",
        )
        payload = self.rt.torch.load(io.BytesIO(raw), map_location="cpu", weights_only=True)
        require(
            payload.get("schema") == "v35_complete_task_gradient_payload.v1"
            and payload.get("binding") == self.binding
            and payload.get("task_plan_id") == self.plan["id"]
            and payload.get("task") == self.task(task_id)
            and payload.get("parameter_spec") == self.parameter_spec,
            "gradient payload binding differs",
        )
        values = self._validate_values(task_id, payload["values_cpu"])
        require(
            self.rt.v8._tree_digest(values) == record["gradient_semantic_digest"]
            and self.rt.v8._tree_digest(payload) == record["payload_semantic_digest"]
            and self._tensor_manifest(values) == record["tensor_manifest"],
            "gradient semantic/tensor digest differs",
        )
        return values, record

    def has(self, task_id):
        target = self.directory(task_id)
        if not target.exists() and not target.is_symlink():
            return False
        self._read(task_id)
        return True

    def read(self, task_id):
        return self._read(task_id)[0]

    def get_or_compute(self, task_id, compute):
        target = self.directory(task_id)
        if target.exists() or target.is_symlink():
            return self.read(task_id), True
        values = compute()
        self.commit(task_id, values)
        return values, False

    def coverage(self):
        complete, missing = [], []
        for task_id in self.plan["task_ids"]:
            (complete if self.has(task_id) else missing).append(task_id)
        return dict(
            complete_task_ids=complete,
            missing_task_ids=missing,
            complete_task_count=len(complete),
            total_task_count=len(self.tasks),
        )

    def completed_records(self, task_ids=None):
        return inspect_completed(self.root, self.binding, self.plan, task_ids)

    def validate_complete(self):
        records = []
        for task_id in self.plan["task_ids"]:
            _, record = self._read(task_id)
            path = self.directory(task_id) / "record.json"
            records.append(
                dict(
                    task_id=task_id,
                    path=str(path),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    id=record["id"],
                )
            )
        return dict(
            task_plan_id=self.plan["id"],
            binding_sha256=self.binding_sha256,
            task_records=records,
            complete_task_count=len(records),
            total_task_count=len(self.tasks),
        )

    def assemble(self, device="cpu"):
        # Read every complete task first. No zero-fill, local aggregation or
        # normalization is permitted. DeviceGradients moves only one state when
        # the frozen global mathematical kernel subsequently requests that state.
        values = {task_id: self.read(task_id) for task_id in self.plan["task_ids"]}
        return {
            task_id: self.rt.v8._DeviceGradients(states, device)
            for task_id, states in values.items()
        }
