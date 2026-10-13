"""Actual-production-state contexts and complete-task class-gradient checkpoints.

This module does not sample, score, train, construct a model, or initialize CUDA.
Unlike V36, it has no reference G/C/pi and no fixed C-only/step298 cache scope.
Every pending outer binds its own complete committed state, arm, pi/prior, full
schedule, material and source bytes before any class gradient can be reused.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

SEEDS = (137, 251, 389)
ARMS = {"Static": "static", "C-only": "c_only", "Full": "full"}
PENDING_SEALED = {
    (137, "C-only", 1192): "c07e70cc25add945f46a87646a237679d093ad26f15cd94a9efc4d0a2a2c402a",
    (137, "Full", 1192): "48ae977e67bf65a82f9823c01e86ea1481f3303d61ba5f5d9ed75bf92b2ae57f",
    (251, "C-only", 894): "1c1030c652c297cc960ed4c9d0f674596e06381281e88257092bdb42531afc09",
}
COMPONENTS = (
    "parameters",
    "buffers",
    "optimizer",
    "rng",
    "pi",
    "prior",
    "schedule",
    "execution_plan",
    "adapter_binding",
    "frozen_base_digest",
    "model_training",
    "outer_done",
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def file_ref(path):
    path = Path(path).resolve()
    require(path.is_file(), "required source file missing: " + str(path))
    return dict(path=str(path), sha256=sha(path))


def checked(path):
    value = json.loads(Path(path).read_bytes())
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "immutable production context/record identity changed",
    )
    return value


def entry(path):
    return {**file_ref(path), "id": checked(path)["id"]}


def read_ref(reference):
    require(sha(reference["path"]) == reference["sha256"], "bound source bytes changed")
    value = json.loads(Path(reference["path"]).read_bytes())
    if "id" in reference:
        require(
            checked(reference["path"])["id"] == reference["id"], "bound record identity changed"
        )
    return value


def publish(path, body):
    """Immutable one-record publication; no old state or evidence is rewritten."""
    path = Path(path)
    require("id" not in body and not path.exists(), "refuse context/record overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {**body, "id": digest(body)}
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return value


def _latest_path(directory):
    """The original durable phase order, without reading each state twice."""
    candidates = []
    phase_order = {"initial": 0, "step": 1, "branch": 2, "outer": 3}
    for path in Path(directory).glob("step*_*"):
        match = re.fullmatch(r"step([0-9]+)_(initial|step|branch|outer)", path.name)
        require(match is not None and path.is_dir(), "unknown training checkpoint entry")
        candidates.append((int(match[1]), phase_order[match[2]], path.resolve()))
    return max(candidates, key=lambda value: value[:2])[2] if candidates else None


def read_checkpoint(checkpoint, rt):
    """Read one actual complete CPU state, preserving the native checkpoint contract."""
    checkpoint = Path(checkpoint).resolve()
    record_path, state_path = checkpoint / "record.json", checkpoint / "state.pt"
    record_raw, raw = record_path.read_bytes(), state_path.read_bytes()
    record = json.loads(record_raw)
    require(
        hashlib.sha256(raw).hexdigest() == record["state_sha256"], "checkpoint state bytes changed"
    )
    state = rt.torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
    require(
        rt.v8._tree_digest(state) == record["actual_state_digest"],
        "checkpoint full state digest changed",
    )
    require(
        state["schema"] == "v8_committed_training_state.v1"
        and state["seed"] in SEEDS
        and state["arm"] in ARMS
        and all(state[key] == record[key] for key in ("seed", "arm", "step", "pool_id"))
        and state["schedule"]["schedule_sha256"] == record["schedule_sha256"]
        and checkpoint.name == f"step{state['step']:04d}_{record['phase']}"
        and record["checkpoint_contains_actual_model_Adam_RNG_pi"] is True,
        "checkpoint is not the original complete production coordinate",
    )
    require(all(key in state for key in COMPONENTS), "incomplete production pre-state")
    require(
        bool(state["parameters"])
        and all(
            tensor.device.type == "cpu"
            and tensor.dtype == rt.torch.float32
            and not tensor.requires_grad
            and bool(rt.torch.isfinite(tensor).all())
            for tensor in state["parameters"].values()
        ),
        "actual finite FP32 trainable parameters required",
    )
    reference = dict(
        path=str(checkpoint),
        record=dict(path=str(record_path), sha256=hashlib.sha256(record_raw).hexdigest()),
        state=dict(path=str(state_path), sha256=hashlib.sha256(raw).hexdigest()),
        actual_state_digest=record["actual_state_digest"],
        phase=record["phase"],
    )
    return state, reference


def _check_actual_state(state, checkpoint, training_root, training, rt, pool, *, latest):
    arm_root = Path(training_root) / f"seed{state['seed']}/arms/{ARMS[state['arm']]}"
    require(
        Path(checkpoint["path"]).parent == arm_root / "training",
        "cross-arm/run checkpoint forbidden",
    )
    if latest:
        require(
            _latest_path(arm_root / "training") == Path(checkpoint["path"]),
            "production registration requires the latest actual durable checkpoint",
        )
    require(
        state["pool_id"] == pool.cache_id
        and state["schedule"] == training.build_task_schedule(pool.task_ids, state["seed"])
        and state["execution_plan"] == rt.conditional.execution_plan(len(pool.task_ids)),
        "actual material/schedule/execution plan changed",
    )
    require(
        state["prior"] == pool._manifest.registration.pi0
        and set(state["pi"]) == set(state["prior"]) == set(pool.task_ids)
        and all(set(state["pi"][task]) == set(state["prior"][task]) for task in pool.task_ids),
        "actual prior or current pi support differs; reset/renormalization forbidden",
    )
    outer_steps = state["execution_plan"]["outer_steps"]
    require(
        state["outer_done"] == sorted(set(state["outer_done"]))
        and set(state["outer_done"]) <= {step for step in outer_steps if step <= state["step"]},
        "completed outer history is inconsistent",
    )
    due = (
        state["arm"] in ("C-only", "Full")
        and state["step"] in outer_steps
        and state["step"] not in state["outer_done"]
    )
    return arm_root, due


def _verify_source_tree(value):
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and "sha256" in value:
            require(sha(value["path"]) == value["sha256"], "bound production source bytes changed")
        for item in value.values():
            _verify_source_tree(item)
    elif isinstance(value, list):
        for item in value:
            _verify_source_tree(item)


def _sources(training, rt, original_cache_module, supplied):
    require(isinstance(supplied, dict), "explicit execution source bindings required")
    value = copy.deepcopy(supplied)
    required = dict(frozen_training=file_ref(training.__file__), frozen_v8=file_ref(rt.v8.__file__))
    if original_cache_module is not None:
        required["original_task_cache"] = file_ref(original_cache_module.__file__)
        storage = Path(original_cache_module.__file__).with_name("finqa_v34_tail_memory.py")
        required["original_class_saved_tensor_storage"] = file_ref(storage)
    for key, reference in required.items():
        require(
            key not in value or value[key] == reference,
            "supplied source differs from actual imported frozen module",
        )
        value[key] = reference
    _verify_source_tree(value)
    return value


def _feedback(training_root, checkpoint, state, *, explicit=None):
    """Bind existing pending feedback without reading private scores or sampling."""
    arm_root = Path(checkpoint["path"]).parent.parent
    coordinate = (state["seed"], state["arm"], state["step"])
    expected = PENDING_SEALED.get(coordinate)
    base = arm_root / "feedback"
    if expected is None:
        require(
            explicit is None, "future-point feedback cannot be replaced with a reference cohort"
        )
        return dict(
            mode="first_sampling",
            base_root=str(base),
            root=None,
            expected_point_id=None,
            manifest=None,
            seal_ref=None,
            reward_ref=None,
            intent_ref=None,
            denominator=700,
            prior_point_match_required_before_provider=True,
            old_reference_gradient_or_feedback_reused=False,
        )
    path = (
        Path(training_root).parent
        / "replay_performance_01/manifests"
        / f"seed{state['seed']}_{ARMS[state['arm']]}_outer{state['step']}"
        / "record.json"
    )
    reference = entry(path)
    manifest = read_ref(reference)
    require(
        manifest["schema"] == "v32_read_only_same_point_manifest.v1"
        and (manifest["seed"], manifest["arm"], manifest["step"]) == coordinate
        and manifest["point_id"] == expected
        and manifest["checkpoint"] == checkpoint["path"]
        and manifest["checkpoint_record"] == checkpoint["record"]
        and manifest["checkpoint_state"] == checkpoint["state"]
        and manifest["actual_state_digest"] == checkpoint["actual_state_digest"]
        and manifest["pre_state_digest"] == checkpoint["actual_state_digest"]
        and manifest["denominator"] == 700
        and manifest["pending_point_recomputation_required"] is True
        and manifest["new_sampling_allowed"] is False
        and manifest["native_rescoring_allowed"] is False,
        "pending feedback is not bound to this actual uncommitted production state",
    )
    root = Path(manifest["feedback_root"]).resolve()
    require(root == base / digest(expected), "pending feedback root escaped its actual arm/point")
    files = manifest["feedback_files"]
    _verify_source_tree(files)
    require(
        file_ref(root / "intent/record.json") == manifest["intent_file"]
        and files["cohort"]["path"] == str(root / "cohort_seal/record.json")
        and files["rewards"]["path"] == str(root / "native_rewards/record.json"),
        "sealed intent/cohort/reward file binding differs",
    )
    value = dict(
        mode="sealed_existing",
        base_root=str(base),
        root=str(root),
        expected_point_id=expected,
        manifest=reference,
        seal_ref=files["cohort"],
        reward_ref=files["rewards"],
        intent_ref=manifest["intent_file"],
        feedback_files=copy.deepcopy(files),
        denominator=700,
        cohort_seal_sha256=manifest["cohort_seal_sha256"],
        rewards_sha256=manifest["rewards_sha256"],
        prior_point_match_required_before_provider=True,
        new_sampling_allowed=False,
        native_rescoring_allowed=False,
        source_episode_bytes_verified_in_manifest=700,
        actual_episode_validation_before_use_owned_by_same_point_guard=True,
    )
    require(
        explicit is None or explicit == value or explicit == reference,
        "explicit feedback binding differs from fixed original pending cohort",
    )
    return value


def _context_base(
    run_root,
    checkpoint,
    *,
    training,
    rt,
    sources,
    execution_binding,
    training_root=None,
    original_cache_module=None,
):
    require(
        isinstance(execution_binding, dict) and bool(execution_binding),
        "explicit production authorization/implementation binding required",
    )
    _verify_source_tree(execution_binding)
    training_root = Path(training_root or training.DEFAULT_ROOT).resolve()
    plan, pool, _prefix, _assets = training.checked_launch(training_root)
    state, checkpoint = read_checkpoint(checkpoint, rt)
    arm_root, due = _check_actual_state(
        state, checkpoint, training_root, training, rt, pool, latest=True
    )
    root = Path(run_root).resolve()
    require(
        root != arm_root and not root.is_relative_to(arm_root),
        "context/cache output must not overwrite the original training or feedback tree",
    )
    require(
        not (root / "context/record.json").exists(),
        "context already registered; no implicit new attempt",
    )
    branch = dict(
        contribution_only=state["arm"] == "C-only",
        b_N=0.0 if state["arm"] == "C-only" else (0.2 if state["arm"] == "Full" else None),
        parameters=copy.deepcopy(rt.v8.PARAMETERS),
    )
    require(
        branch["parameters"]["novelty_exponent"] == 0.2
        and branch["parameters"]["contribution_exponent"] == 0.8,
        "registered Full/C-only branch parameters changed",
    )
    components = {key: rt.v8._tree_digest(state[key]) for key in COMPONENTS}
    body = dict(
        schema="v37_actual_production_context.v1",
        at=datetime.now(timezone.utc).isoformat(),
        run_root=str(root),
        outer_root=str(root),
        training_root=str(training_root),
        arm_root=str(arm_root),
        checkpoint=checkpoint,
        seed=state["seed"],
        arm=state["arm"],
        step=state["step"],
        due_outer=due,
        outer_done=list(state["outer_done"]),
        execution_plan=copy.deepcopy(state["execution_plan"]),
        schedule_sha256=state["schedule"]["schedule_sha256"],
        pre_state_digest=checkpoint["actual_state_digest"],
        component_digest=components,
        pi=copy.deepcopy(state["pi"]),
        prior=copy.deepcopy(state["prior"]),
        mu=copy.deepcopy(pool._manifest.registration.mu),
        pool_id=pool.cache_id,
        training_protocol_id=plan["id"],
        training_protocol=file_ref(training_root / "registration/record.json"),
        branch=branch,
        sources=_sources(training, rt, original_cache_module, sources),
        execution_binding=copy.deepcopy(execution_binding),
        no_reference_G_C_pi_required=True,
        cross_parameter_point_cache_reuse_allowed=False,
        original_checkpoint_or_feedback_rewritten=False,
    )
    if "training_stop_step" in execution_binding:
        stop_step = execution_binding["training_stop_step"]
        require(
            type(stop_step) is int
            and state["step"] < stop_step <= state["execution_plan"]["final_step"],
            "explicit training stop must remain inside the original remaining schedule",
        )
        body["training_stop_step"] = stop_step
    return body, state, pool


def prepare_outer(
    outer_root,
    checkpoint,
    *,
    training,
    rt,
    original_cache_module,
    sources,
    execution_binding,
    feedback_binding=None,
    training_root=None,
):
    body, state, pool = _context_base(
        outer_root,
        checkpoint,
        training=training,
        rt=rt,
        original_cache_module=original_cache_module,
        sources=sources,
        execution_binding=execution_binding,
        training_root=training_root,
    )
    require(
        body["due_outer"] and state["arm"] in ("C-only", "Full"),
        "class-gradient context requires a due uncommitted actual outer",
    )
    root = Path(body["outer_root"])
    require(
        not (root / "task_cache").exists(), "cannot borrow an existing or reference-point cache"
    )
    spec = [
        dict(name=name, shape=list(value.shape), dtype=str(value.dtype))
        for name, value in state["parameters"].items()
    ]
    task_plan = original_cache_module.make_task_plan(pool, spec, shards=4)
    feedback = _feedback(
        body["training_root"], body["checkpoint"], state, explicit=feedback_binding
    )
    publish(root / "task_plan/record.json", {k: v for k, v in task_plan.items() if k != "id"})
    binding = dict(
        schema="v37_actual_outer_task_gradient_binding.v1",
        seed=state["seed"],
        arm=state["arm"],
        step=state["step"],
        checkpoint=copy.deepcopy(body["checkpoint"]),
        pre_state_digest=body["pre_state_digest"],
        component_digest=copy.deepcopy(body["component_digest"]),
        pool_id=body["pool_id"],
        mu_digest=rt.v8._tree_digest(body["mu"]),
        schedule_sha256=body["schedule_sha256"],
        task_plan_id=task_plan["id"],
        parameter_spec=spec,
        branch=copy.deepcopy(body["branch"]),
        numerical_sources=copy.deepcopy(body["sources"]),
        expected_existing_sampling_point_id=feedback["expected_point_id"],
        cross_parameter_point_reuse=False,
    )
    body.update(
        kind="outer",
        parameter_spec=spec,
        task_plan=entry(root / "task_plan/record.json"),
        task_binding=binding,
        math_context_id=digest(binding),
        task_cache_root=str(root / "task_cache"),
        feedback=feedback,
    )
    return publish(root / "context/record.json", body)


def prepare_training_context(
    run_root, checkpoint, *, training, rt, sources, execution_binding, training_root=None
):
    body, state, _pool = _context_base(
        run_root,
        checkpoint,
        training=training,
        rt=rt,
        sources=sources,
        execution_binding=execution_binding,
        training_root=training_root,
    )
    require(
        not body["due_outer"], "an uncommitted due outer cannot be bypassed by training context"
    )
    body.update(
        kind="training", task_plan=None, task_binding=None, task_cache_root=None, feedback=None
    )
    return publish(Path(run_root) / "context/record.json", body)


def peek_context(run_root):
    """Read immutable scheduling metadata only; never deserialize checkpoint tensors."""
    root = Path(run_root).resolve()
    context = checked(root / "context/record.json")
    require(
        context["schema"] == "v37_actual_production_context.v1"
        and context["run_root"] == context["outer_root"] == str(root),
        "production context metadata path differs",
    )
    return context


def load_context(run_root, *, training, rt, original_cache_module=None):
    root = Path(run_root).resolve()
    context = peek_context(root)
    require(
        context["schema"] == "v37_actual_production_context.v1"
        and context["run_root"] == context["outer_root"] == str(root),
        "production context output scope changed",
    )
    _verify_source_tree(context["sources"])
    _verify_source_tree(context["execution_binding"])
    plan, pool, _prefix, _assets = training.checked_launch(context["training_root"])
    state, source = read_checkpoint(context["checkpoint"]["path"], rt)
    arm_root, due = _check_actual_state(
        state, source, context["training_root"], training, rt, pool, latest=False
    )
    require(
        source == context["checkpoint"]
        and plan["id"] == context["training_protocol_id"]
        and file_ref(Path(context["training_root"]) / "registration/record.json")
        == context["training_protocol"]
        and str(arm_root) == context["arm_root"]
        and due == context["due_outer"]
        and all(
            context[key] == state[key]
            for key in ("seed", "arm", "step", "pi", "prior", "outer_done", "execution_plan")
        )
        and context["pre_state_digest"] == rt.v8._tree_digest(state)
        and context["component_digest"]
        == {key: rt.v8._tree_digest(state[key]) for key in COMPONENTS}
        and context["mu"] == pool._manifest.registration.mu,
        "context is not the complete actual checkpoint/schedule/pi/arm state",
    )
    expected_branch = dict(
        contribution_only=state["arm"] == "C-only",
        b_N=0.0 if state["arm"] == "C-only" else (0.2 if state["arm"] == "Full" else None),
        parameters=copy.deepcopy(rt.v8.PARAMETERS),
    )
    require(context["branch"] == expected_branch, "Full/C-only branch binding changed")
    if context["kind"] == "training":
        require(not due and context["task_binding"] is None, "invalid non-outer training context")
        return context, state, pool, None
    require(
        context["kind"] == "outer" and due and original_cache_module is not None,
        "actual pending outer/cache runtime required",
    )
    task_plan = read_ref(context["task_plan"])
    spec = [
        dict(name=name, shape=list(value.shape), dtype=str(value.dtype))
        for name, value in state["parameters"].items()
    ]
    require(
        spec == context["parameter_spec"]
        and original_cache_module.make_task_plan(pool, spec, shards=4) == task_plan,
        "actual task/state/row/parameter order differs from registered complete-task plan",
    )
    binding = context["task_binding"]
    require(
        binding["schema"] == "v37_actual_outer_task_gradient_binding.v1"
        and all(
            binding[key] == context[key]
            for key in (
                "seed",
                "arm",
                "step",
                "checkpoint",
                "pre_state_digest",
                "component_digest",
                "pool_id",
                "schedule_sha256",
                "branch",
            )
        )
        and binding["parameter_spec"] == spec
        and binding["task_plan_id"] == task_plan["id"]
        and binding["mu_digest"] == rt.v8._tree_digest(context["mu"])
        and binding["numerical_sources"] == context["sources"]
        and digest(binding) == context["math_context_id"]
        and binding["cross_parameter_point_reuse"] is False
        and context["task_cache_root"] == str(root / "task_cache"),
        "task cache binding attempted cross-point or cross-arm reuse",
    )
    feedback = _feedback(context["training_root"], source, state)
    require(
        feedback == context["feedback"]
        and binding["expected_existing_sampling_point_id"] == feedback["expected_point_id"],
        "same-point sealed feedback binding changed",
    )
    cache = ProductionTaskCache(
        root / "task_cache",
        binding,
        task_plan,
        spec,
        rt,
        original_cache_module=original_cache_module,
    )
    return context, state, pool, cache


def _file_identity(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "missing/symlinked task payload")
    value = path.stat()
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


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


class VerifiedState:
    def __init__(self, identity):
        self.identity, self.pid, self.values, self.file_reads = identity, os.getpid(), {}, 0

    def __getstate__(self):
        raise TypeError("actual-point verified tensors cannot authorize another process")


class ProductionTaskCache:
    """Same-point durable cache, with V36's strict reader and live-process reuse."""

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
        require(
            binding.get("schema") == "v37_actual_outer_task_gradient_binding.v1"
            and binding.get("cross_parameter_point_reuse") is False
            and binding["task_plan_id"] == task_plan["id"]
            and binding["parameter_spec"] == parameter_spec,
            "production cache cannot borrow a V35/V36 reference-point binding",
        )
        self.original = original_cache_module.TaskCache(
            root, binding, task_plan, parameter_spec, rt
        )
        self.root, self.plan, self.binding, self.rt = (
            self.original.root,
            self.original.plan,
            self.original.binding,
            rt,
        )
        self.parameter_spec, self.binding_sha256 = (
            self.original.parameter_spec,
            self.original.binding_sha256,
        )
        identity = digest(
            dict(root=str(self.root.resolve()), binding=self.binding, task_plan_id=task_plan["id"])
        )
        self.verified_state = (
            verified_state if verified_state is not None else VerifiedState(identity)
        )
        require(
            isinstance(self.verified_state, VerifiedState)
            and self.verified_state.identity == identity
            and self.verified_state.pid == os.getpid(),
            "verified values belong to another actual point or process",
        )

    def task(self, task_id):
        return self.original.task(task_id)

    def directory(self, task_id):
        return self.original.directory(task_id)

    def _read(self, task_id):
        target = self.directory(task_id)
        before = (_file_identity(target / "record.json"), _file_identity(target / "gradient.pt"))
        cached = self.verified_state.values.get(task_id)
        if cached is not None:
            values, record, file_identity, tensor_identity = cached
            require(
                before == file_identity and _value_identity(values) == tensor_identity,
                "previously verified production files/CPU tensors changed",
            )
            return values, record
        values, record = self.original._read(task_id)
        after = (_file_identity(target / "record.json"), _file_identity(target / "gradient.pt"))
        require(before == after, "production cache changed during strict verification")
        self.verified_state.values[task_id] = (values, record, after, _value_identity(values))
        self.verified_state.file_reads += 1
        return values, record

    def has(self, task_id):
        path = self.directory(task_id)
        if not path.exists() and not path.is_symlink():
            return False
        self._read(task_id)
        return True

    def read(self, task_id):
        return self._read(task_id)[0]

    def commit(self, task_id, values_cpu, receipt=None):
        return self.original.commit(task_id, values_cpu, receipt=receipt)

    def get_or_compute(self, task_id, compute):
        if self.has(task_id):
            return self.read(task_id), True
        values = compute()
        self.commit(task_id, values)
        return values, False

    def assemble(self, device="cpu"):
        require(
            all(self.directory(task).is_dir() for task in self.plan["task_ids"]),
            "every original task must be complete; zero fill or subset aggregation forbidden",
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
        return dict(
            binding_sha256=self.binding_sha256,
            process_id=self.verified_state.pid,
            strict_payload_file_reads=self.verified_state.file_reads,
            verified_task_count=len(self.verified_state.values),
            verified_task_ids=[
                task for task in self.plan["task_ids"] if task in self.verified_state.values
            ],
            cross_process_verification_waiver=False,
            cross_parameter_point_reuse=False,
        )


def inspect_cache(run_root, *, complete=False):
    """Controller metadata coverage; mathematical use still requires real tensor validation."""
    root = Path(run_root).resolve()
    context = checked(root / "context/record.json")
    require(
        context["kind"] == "outer" and context["task_cache_root"] == str(root / "task_cache"),
        "only an actual outer has class-gradient cache coverage",
    )
    plan = read_ref(context["task_plan"])
    rows = []
    for task in plan["tasks"]:
        directory = root / "task_cache" / f"task{task['index']:04d}"
        if not directory.exists() and not directory.is_symlink():
            continue
        require(
            directory.is_dir()
            and not directory.is_symlink()
            and {path.name for path in directory.iterdir()} == {"record.json", "gradient.pt"},
            "incomplete production task checkpoint",
        )
        record = checked(directory / "record.json")
        require(
            record["schema"] == "v35_complete_task_gradient.v1"
            and record["complete_task"] is True
            and record["binding"] == context["task_binding"]
            and record["binding_sha256"] == digest(context["task_binding"])
            and record["task_plan_id"] == plan["id"]
            and record["task"] == task
            and record["parameter_spec"] == context["parameter_spec"]
            and not (directory / "record.json").is_symlink()
            and not (directory / "gradient.pt").is_symlink()
            and (directory / "gradient.pt").stat().st_size == record["gradient_bytes"],
            "production task metadata is not bound to this complete actual point",
        )
        rows.append(dict(task_id=task["task_id"], **entry(directory / "record.json")))
    completed = [row["task_id"] for row in rows]
    missing = [task for task in plan["task_ids"] if task not in set(completed)]
    require(
        not complete or not missing,
        "complete original task population required before global calculation",
    )
    return dict(
        context_id=context["id"],
        task_plan_id=plan["id"],
        binding_sha256=digest(context["task_binding"]),
        task_records=rows,
        complete_task_ids=completed,
        missing_task_ids=missing,
        complete_task_count=len(completed),
        total_task_count=len(plan["task_ids"]),
        tensor_deserialization_and_finite_checks_required_before_use=True,
    )


def production_snapshot(*, training, rt, training_root=None):
    """CPU-only complete-state progress; never reads endpoint predictions/scores."""
    root = Path(training_root or training.DEFAULT_ROOT).resolve()
    plan, pool, _prefix, _assets = training.checked_launch(root)
    shared_step = rt.conditional.execution_plan(len(pool.task_ids))["shared_step"]
    rows, pending = [], []
    for seed in SEEDS:
        for arm, name in ARMS.items():
            checkpoint = _latest_path(root / f"seed{seed}/arms/{name}/training")
            require(checkpoint is not None, "registered original arm checkpoint missing")
            state, reference = read_checkpoint(checkpoint, rt)
            _arm_root, due = _check_actual_state(
                state, reference, root, training, rt, pool, latest=False
            )
            require((state["seed"], state["arm"]) == (seed, arm), "arm checkpoint identity differs")
            rows.append(
                dict(
                    seed=seed,
                    arm=arm,
                    checkpoint=reference,
                    step=state["step"],
                    outer_done=state["outer_done"],
                    due_outer=due,
                    remaining_updates=state["execution_plan"]["final_step"] - state["step"],
                    remaining_outers=len(state["execution_plan"]["outer_steps"])
                    - len(state["outer_done"])
                    if arm != "Static"
                    else 0,
                )
            )
            if due and (seed, arm, state["step"]) in PENDING_SEALED:
                feedback = _feedback(root, reference, state)
                pending.append(
                    dict(
                        seed=seed,
                        arm=arm,
                        step=state["step"],
                        feedback=feedback,
                        checkpoint=reference,
                    )
                )
    completed_updates = len(SEEDS) * shared_step + sum(row["step"] - shared_step for row in rows)
    remaining_outers = sum(row["remaining_outers"] for row in rows)
    return dict(
        schema="v37_actual_B_CPU_state_snapshot.v1",
        at=datetime.now(timezone.utc).isoformat(),
        training_root=str(root),
        training_protocol_id=plan["id"],
        arms=rows,
        completed_physical_updates=completed_updates,
        remaining_physical_updates=plan["budgets"]["physical_updates"] - completed_updates,
        completed_outers=sum(len(row["outer_done"]) for row in rows),
        remaining_outers=remaining_outers,
        pending_sealed_outers=pending,
        pending_sealed_feedback_episodes=700 * len(pending),
        future_first_sampling_outers=remaining_outers - len(pending),
        future_first_sampling_feedback_episodes=700 * (remaining_outers - len(pending)),
        endpoint_scores_or_answers_read=False,
        original_state_or_feedback_modified=False,
        episode_data_deep_validation_deferred_to_actual_same_point_worker=True,
    )
