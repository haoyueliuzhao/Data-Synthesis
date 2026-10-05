"""Fresh-seed three-arm replication, using the unchanged frozen V18 numerics.

Only seed admission, schedule construction and new-output orchestration differ.
The V15 state-free prefix, zero-update migration, V8 optimizer/outer methods,
fixed700 feedback collector and full every-step checkpoints are reused verbatim.
No previous model, Adam, RNG, pi, feedback or dev/test score is a training input.
"""

from __future__ import annotations

import argparse
import ast
import copy
import fcntl
import hashlib
import importlib
import inspect
import json
import os
import shutil
import sys
import textwrap
import types
from contextlib import contextmanager
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
FROZEN = REPO / ".codex-worktrees/finqa-v18-researcher-continuation-20260930"
V18 = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01"
)
DEFAULT_ROOT = V18 / "v25_training_replication_01/training_replication"
SEEDS = (137, 251, 389)
OLD_SEEDS = (11, 29, 47)
ARMS = ("Static", "C-only", "Full")
ARM_DIRECTORIES = {"Static": "static", "C-only": "c_only", "Full": "full"}
GIB = 1024**3
DISK_BUDGET = 400 * GIB
DISK_MARGIN = 32 * GIB
_RUNTIME = None
_ADAPTERS = None


def require(condition, message):
    if not condition:
        raise ValueError(message)


def arm_name(arm):
    aliases = {**{a: a for a in ARMS}, **{v: k for k, v in ARM_DIRECTORIES.items()}}
    require(arm in aliases, "only registered Static/C-only/Full arms are admitted")
    return aliases[arm]


def coordinate(seed, arm=None):
    require(type(seed) is int and seed in SEEDS, "fresh registered seeds 137/251/389 only")
    return f"seed{seed}" + ("/arms/" + ARM_DIRECTORIES[arm_name(arm)] if arm else "")


def load_runtime():
    global _RUNTIME
    if _RUNTIME is None:
        source = FROZEN / "trusted_data_synthesis/src"
        for name, module in tuple(sys.modules.items()):
            if name == "trusted_synthesis" or name.startswith("trusted_synthesis."):
                origin = getattr(module, "__file__", None)
                require(
                    origin is None or Path(origin).resolve().is_relative_to(source),
                    "a non-frozen trusted_synthesis runtime is already imported",
                )
        sys.path.insert(0, str(source))
        modules = {
            "prefix": "v15_prefix_training",
            "v8": "v8_training_driver",
            "conditional": "v9_conditional_training",
            "launcher": "v9_training_launcher",
            "material": "v18_material",
            "arms": "v16_arm_training",
            "storage": "storage",
            "calibration": "calibration",
            "continuation": "v18_continuation",
        }
        values = {}
        for key, name in modules.items():
            module = importlib.import_module("trusted_synthesis.finance_research." + name)
            require(
                Path(module.__file__).resolve()
                == source / ("trusted_synthesis/finance_research/" + name + ".py"),
                "only the frozen scientific runtime is admitted",
            )
            values[key] = module
        values["torch"] = importlib.import_module("torch")
        _RUNTIME = types.SimpleNamespace(**values)
    return _RUNTIME


def _clone(function, replacements):
    require(function.__closure__ is None, "unexpected scientific function closure")
    result = types.FunctionType(
        function.__code__,
        function.__globals__ | replacements,
        function.__name__,
        function.__defaults__,
    )
    result.__kwdefaults__ = copy.copy(function.__kwdefaults__)
    return result


def _seed_adapter(function, *, replace_validator=False):
    """Narrow checked AST substitution; never edit the frozen module or its globals."""
    source = textwrap.dedent(inspect.getsource(function))
    tree = ast.parse(source)
    before = ast.dump(tree, include_attributes=False)

    class Admission(ast.NodeTransformer):
        seeds = 0
        imports = 0

        def visit_Compare(self, node):
            if (
                isinstance(node.left, ast.Name)
                and node.left.id == "seed"
                and len(node.ops) == 1
                and isinstance(node.ops[0], ast.In)
                and len(node.comparators) == 1
                and isinstance(node.comparators[0], ast.Tuple)
                and all(isinstance(x, ast.Constant) for x in node.comparators[0].elts)
                and tuple(x.value for x in node.comparators[0].elts) == OLD_SEEDS
            ):
                node.comparators[0].elts = [ast.Constant(value=s) for s in SEEDS]
                self.seeds += 1
            return self.generic_visit(node)

        def visit_ImportFrom(self, node):
            if (
                replace_validator
                and node.level == 1
                and node.module == "v9_conditional_training"
                and [(x.name, x.asname) for x in node.names]
                == [("validate_execution_schedule", None)]
            ):
                self.imports += 1
                return ast.copy_location(ast.Pass(), node)
            return node

    adapter = Admission()
    tree = ast.fix_missing_locations(adapter.visit(tree))
    require(
        adapter.seeds == 1 and adapter.imports == int(replace_validator),
        "frozen constructor/schedule changed; refuse broader adaptation",
    )
    namespace = function.__globals__.copy()
    if replace_validator:
        namespace["validate_execution_schedule"] = validate_execution_schedule
    exec(compile(tree, str(Path(__file__)) + ":seed-admission", "exec"), namespace)
    patched = namespace[function.__name__]
    metadata = dict(
        original_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        original_ast_sha256=hashlib.sha256(before.encode()).hexdigest(),
        adapted_ast_sha256=hashlib.sha256(
            ast.dump(tree, include_attributes=False).encode()
        ).hexdigest(),
        changed_seed_guard_count=adapter.seeds,
        replaced_schedule_validator_import_count=adapter.imports,
        numerical_expressions_changed=False,
    )
    return patched, metadata


def adapters():
    global _ADAPTERS
    if _ADAPTERS is None:
        rt = load_runtime()
        schedule, schedule_receipt = _seed_adapter(rt.conditional.build_task_schedule)
        initializer, initializer_receipt = _seed_adapter(
            rt.v8.TrainingDriver.__init__, replace_validator=True
        )

        class ReplicationPrefix(rt.prefix.PrefixDriver):
            __init__ = _clone(
                rt.prefix.PrefixDriver.__init__,
                {
                    "SEEDS": SEEDS,
                    "build_task_schedule": build_task_schedule,
                },
            )

        class ReplicationDriver(rt.v8.TrainingDriver):
            def __init__(self, model, optimizer, pool, **kwargs):
                coordinate(kwargs["seed"])
                require(kwargs.get("arm") in ARMS, "no shared tail, Manual arm or new variant")
                plan = rt.conditional.execution_plan(len(pool.task_ids))
                schedule = build_task_schedule(pool.task_ids, kwargs["seed"])
                require(
                    "execution_plan" not in kwargs and "task_schedule" not in kwargs,
                    "registered execution coordinates cannot be overridden",
                )
                if pool.production_verified:
                    require(
                        getattr(pool, "conditional_scope_verified", False),
                        "verified original material required",
                    )
                else:
                    require(str(kwargs.get("device", "cpu")) == "cpu", "CPU controls only")
                    kwargs["cpu_control_schedule"] = schedule
                initializer(
                    self,
                    model,
                    optimizer,
                    pool,
                    execution_plan=plan,
                    task_schedule=schedule,
                    **kwargs,
                )

        _ADAPTERS = types.SimpleNamespace(
            schedule=schedule,
            PrefixDriver=ReplicationPrefix,
            TrainingDriver=ReplicationDriver,
            migrate=_clone(
                rt.prefix.migrate_prefix_checkpoint, {"build_task_schedule": build_task_schedule}
            ),
            receipt=dict(
                schedule=schedule_receipt,
                constructor=initializer_receipt,
                prefix_constructor_bytecode_unchanged=True,
                migration_bytecode_unchanged=True,
                all_training_step_outer_restore_commit_methods_inherited=True,
                frozen_module_globals_mutated=False,
            ),
        )
    return _ADAPTERS


def build_task_schedule(task_ids, seed):
    coordinate(seed)
    return adapters().schedule(task_ids, seed)


def validate_execution_schedule(plan, schedule, task_ids, seed):
    require(
        plan == load_runtime().conditional.execution_plan(len(task_ids)),
        "original scientific coordinates changed",
    )
    require(schedule == build_task_schedule(task_ids, seed), "new registered seed schedule changed")


class StateFreePool:
    """Expose only original package order/positive rows, with genuine states removed."""

    def __init__(self, full_pool, binding_ref):
        self.task_ids = tuple(full_pool.task_ids)
        self.packages = tuple(
            {k: v for k, v in p.items() if k != "state_id"} for p in full_pool.packages
        )
        self.row_arrays = full_pool.row_arrays
        self.cache_id = binding_ref["id"]
        self.prefix_binding_ref = dict(binding_ref)
        self.production_verified = full_pool.production_verified
        self.prefix_only, self.full_training_admitted = True, False
        self.tokenizer_binding = full_pool.tokenizer_binding
        self.material_order_id = full_pool.material_order_id
        self.execution_plan = full_pool.execution_plan
        require(
            load_runtime().prefix.package_inventory(self)
            == load_runtime().prefix.package_inventory(full_pool),
            "state-free view changed package/row order or denominator",
        )


def source_binding():
    rt = load_runtime()
    return dict(
        script_sha256=rt.launcher.sha(__file__),
        source_runtime=str(FROZEN),
        runtime_binding=rt.storage.runtime_binding(),
        prefix_sources=rt.prefix.source_bindings(),
        numerical_runtime=rt.prefix.numerical_runtime(),
        seed_admission=adapters().receipt,
    )


def read_reference(reference, *, bound=True):
    rt = load_runtime()
    require(
        rt.launcher.sha(reference["path"]) == reference["sha256"],
        "registered source bytes changed: " + reference["path"],
    )
    return (
        rt.launcher.read_bound(reference["path"])
        if bound
        else json.loads(Path(reference["path"]).read_bytes())
    )


def disk_required(consumed, budget=DISK_BUDGET):
    require(consumed >= 0 and budget > 0, "nonnegative disk accounting required")
    return max(DISK_MARGIN, budget - consumed)


def disk_gate(root, *, budget=DISK_BUDGET):
    """Global remaining reservation includes all concurrent B workers, not each anew."""
    root = Path(root)
    existing = root
    while not existing.exists():
        existing = existing.parent
    consumed = (
        sum(p.stat().st_blocks * 512 for p in root.rglob("*") if p.is_file())
        if root.exists()
        else 0
    )
    free = shutil.disk_usage(existing).free
    needed = disk_required(consumed, budget)
    require(free >= needed, "insufficient remaining registered full-checkpoint disk budget")
    return dict(
        free_bytes=free,
        replication_allocated_bytes=consumed,
        remaining_required_bytes=needed,
        total_registered_budget_bytes=budget,
        physical_reservation=False,
        each_worker_not_charged_full_budget_again=True,
    )


def prepare(root=DEFAULT_ROOT, source_root=V18):
    root, source_root, rt = Path(root).resolve(), Path(source_root).resolve(), load_runtime()
    if (root / "registration/record.json").exists():
        plan = checked_plan(root)
        require(plan["source_root"] == str(source_root), "source root cannot be rebound")
        return plan
    require(source_root == V18.resolve(), "only the specified existing V18 material is admitted")
    require(not root.exists(), "new immutable training root required; inspect partial registration")
    source_path = source_root / "training/five_arm_training/registration/record.json"
    original = rt.launcher.read_bound(source_path)
    require(tuple(original["seeds"]) == OLD_SEEDS, "source old-seed registration changed")
    require(original["runtime_binding"] == rt.storage.runtime_binding(), "source runtime changed")
    for key in ("material_binding", "assets_protocol", "scale_decision"):
        read_reference(original[key])
    pool = rt.material.load_training_pool(original["material_binding"]["path"])
    identity = rt.launcher.material_identity(pool)
    require(identity == original["material_identity"], "original material identity changed")
    rt.continuation.validate_condition_realization(
        rt.launcher.read_bound(original["scale_decision"]["path"]),
        original["material_binding"]["path"],
        identity,
    )
    execution = pool.execution_plan
    require(
        len(pool.task_ids) == 744
        and len(pool.packages) == 2468
        and sum(len(z) for z in pool._manifest.registration.pi0.values()) == 1360
        and execution["shared_step"] == 298
        and execution["final_step"] == 1490
        and execution["outer_steps"] == [298, 596, 894, 1192],
        "fixed full V18 material required",
    )
    assets = rt.launcher.read_bound(original["assets_protocol"]["path"])
    require(assets["id"] == original["assets_protocol_id"], "base/role assets changed")
    require(original["feedback_config"]["api_model"] == "deepseek-flash", "API policy changed")
    disk = disk_gate(root)
    prefix_binding = rt.launcher.bound(
        dict(
            schema="v25_fresh_state_free_prefix_material.v1",
            source_material=original["material_binding"],
            full_pool_id=pool.cache_id,
            material_order_id=pool.material_order_id,
            package_inventory_sha256=rt.prefix.digest(rt.prefix.package_inventory(pool)),
            original_material_prefix_reference=pool.prefix_binding_ref,
            old_prefix_tensors_loaded=False,
            state_labels_exposed_to_prefix=False,
        )
    )
    rt.v8._publish(root / "prefix_binding", prefix_binding)
    prefix_ref = rt.launcher.file_binding(root / "prefix_binding/record.json") | {
        "id": prefix_binding["id"]
    }
    plan = rt.launcher.bound(
        dict(
            schema="v25_fresh_seed_three_arm_training.v1",
            at=rt.calibration.now(),
            source_root=str(source_root),
            training_root=str(root),
            original_registration=rt.launcher.file_binding(source_path),
            material_binding=original["material_binding"],
            material_identity=identity,
            assets_protocol=original["assets_protocol"],
            assets_protocol_id=assets["id"],
            prefix_binding=prefix_ref,
            training_task_ids=list(pool.task_ids),
            tokenizer_binding=list(pool.tokenizer_binding),
            seeds=list(SEEDS),
            arms=list(ARMS),
            arm_directories=ARM_DIRECTORIES,
            fresh_seed_nonoverlap=sorted(set(SEEDS) & set(OLD_SEEDS)),
            schedules={
                str(s): build_task_schedule(pool.task_ids, s)["schedule_sha256"] for s in SEEDS
            },
            source_binding=source_binding(),
            runtime_binding=rt.storage.runtime_binding(),
            feedback_config=original["feedback_config"],
            feedback_seeds=original["feedback_seeds"],
            feedback_sampling_seeds_are_not_training_seeds=True,
            API_calls=0,
            api_model="deepseek-flash",
            model_fallback=False,
            budgets=dict(
                prefix_updates=894,
                tail_updates=10728,
                physical_updates=11622,
                outer_updates=24,
                new_feedback_episodes=16800,
                new_material_packages=0,
                final_models=9,
                full_checkpoint_disk_bytes=DISK_BUDGET,
            ),
            legacy_execution_plan_budget_fields_are_not_replication_budgets=True,
            device_policy=dict(
                allowed_gpu_indices=list(range(8)),
                minimum_free_mib=24576,
                prefix_minimum_free_mib=32768,
                arm_minimum_free_mib=49152,
                no_placeholders=True,
            ),
            checkpoint_policy=(
                "complete original state at every actual step; no sparse save or eviction"
            ),
            disk_admission=disk,
            old_checkpoint_inputs=[],
            old_feedback_inputs=[],
            cross_arm_feedback_shared=False,
            cross_arm_outer_shared=False,
            shared_prefix_updates_per_seed=298,
            tail_updates_per_arm=1192,
            no_dev_selection=True,
            no_optional_stopping=True,
            known_benchmark_training_randomness_replication=True,
            new_unseen_benchmark_confirmation=False,
        )
    )
    rt.v8._publish(root / "registration", plan)
    return plan


def checked_plan(root):
    rt, root = load_runtime(), Path(root).resolve()
    plan = rt.launcher.read_bound(root / "registration/record.json")
    require(
        plan["schema"] == "v25_fresh_seed_three_arm_training.v1"
        and plan["training_root"] == str(root)
        and plan["source_binding"] == source_binding()
        and plan["seeds"] == list(SEEDS)
        and plan["arms"] == list(ARMS),
        "registered training source, runtime or coordinates changed",
    )
    for key in ("original_registration", "material_binding", "assets_protocol", "prefix_binding"):
        read_reference(plan[key])
    require(
        plan["budgets"]["physical_updates"] == 11622
        and plan["budgets"]["new_feedback_episodes"] == 16800,
        "fixed replication budget changed",
    )
    return plan


def checked_launch(root):
    rt, plan = load_runtime(), checked_plan(root)
    pool = rt.material.load_training_pool(plan["material_binding"]["path"])
    require(
        rt.launcher.material_identity(pool) == plan["material_identity"]
        and list(pool.task_ids) == plan["training_task_ids"],
        "actual material changed",
    )
    pool = copy.copy(pool)
    pool.prefix_binding_ref = dict(plan["prefix_binding"])
    prefix = StateFreePool(pool, plan["prefix_binding"])
    assets = read_reference(plan["assets_protocol"])
    return plan, pool, prefix, assets


@contextmanager
def locked_worker(root, plan, seed, arm, gpu_index):
    rt = load_runtime()
    locks = Path(root) / "locks"
    locks.mkdir(exist_ok=True)
    minimum = plan["device_policy"]["arm_minimum_free_mib" if arm else "prefix_minimum_free_mib"]
    gpu_plan = dict(device_policy=plan["device_policy"] | {"minimum_free_mib": minimum})
    with (locks / f"seed{seed}.lock").open("a") as seed_lock:
        fcntl.flock(seed_lock, (fcntl.LOCK_SH if arm else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        with (locks / f"seed{seed}-{ARM_DIRECTORIES[arm] if arm else 'prefix'}.lock").open(
            "a"
        ) as task_lock:
            fcntl.flock(task_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            row = rt.launcher.eligible_gpu(gpu_plan, gpu_index, rt.calibration.gpu_inventory())
            with (locks / ("gpu-" + rt.prefix.digest(row["uuid"]) + ".lock")).open("a") as gpu_lock:
                fcntl.flock(gpu_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with (locks / "disk-admission.lock").open("a") as disk_lock:
                    fcntl.flock(disk_lock, fcntl.LOCK_EX)
                    disk = disk_gate(root, budget=plan["budgets"]["full_checkpoint_disk_bytes"])
                current = rt.launcher.eligible_gpu(
                    gpu_plan, gpu_index, rt.calibration.gpu_inventory()
                )
                require(current["uuid"] == row["uuid"], "GPU identity changed before load")
                require(
                    not rt.torch.cuda.is_initialized()
                    or os.environ.get("CUDA_VISIBLE_DEVICES") == row["uuid"],
                    "initialized CUDA process cannot remap GPU",
                )
                os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
                os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
                yield dict(gpu=current, disk=disk)


def _attempt(root, plan, seed, arm, resume, admission):
    rt = load_runtime()
    attempts = Path(root) / "launch_attempts"
    attempt = attempts / f"attempt{len(list(attempts.glob('attempt*'))) + 1:03d}"
    rt.v8._publish(
        attempt / "intent",
        rt.launcher.bound(
            dict(
                schema="v25_fresh_replication_attempt.v1",
                at=rt.calibration.now(),
                protocol_id=plan["id"],
                seed=seed,
                arm=arm or "fresh_shared_prefix",
                explicit_resume=resume,
                pid=os.getpid(),
                admission=admission,
                no_GPU_placeholder=True,
                automatic_retry=False,
            )
        ),
    )
    return attempt


def _failed(attempt, failure):
    rt = load_runtime()
    rt.v8._publish(
        attempt / "stopped",
        rt.launcher.bound(
            dict(
                at=rt.calibration.now(),
                error_type=type(failure).__name__,
                error=str(failure),
                outer_failure_audit=getattr(failure, "outer_failure_audit", None),
                outer_audit_write_error=getattr(failure, "outer_audit_write_error", None),
                retry_performed=False,
                partial_feedback_resampled=False,
                recovery="explicit resume from durable same-run model/Adam/RNG/pi only",
            )
        ),
    )


def _shared_checkpoint(root, plan, seed):
    rt = load_runtime()
    result = rt.launcher.read_bound(Path(root) / coordinate(seed) / "prefix_result/record.json")
    path = Path(root) / coordinate(seed) / "shared/step0298_step"
    summary = json.loads((path / "record.json").read_bytes())
    proof = summary["evidence"]
    require(
        result["protocol_id"] == plan["id"]
        and result["seed"] == seed
        and result["shared_checkpoint"] == rt.launcher._checkpoint_ref(path)
        and summary["seed"] == seed
        and summary["step"] == 298
        and summary["arm"] == "shared"
        and summary["phase"] == "step"
        and summary["pool_id"] == plan["material_identity"]["pool_id"]
        and proof["schema"] == "v15_completed_prefix_migration.v1"
        and proof["id"] == rt.prefix.digest({k: v for k, v in proof.items() if k != "id"})
        and proof["prefix_binding"] == plan["prefix_binding"]
        and Path(proof["source_prefix"]["path"]).resolve()
        == Path(root).resolve() / coordinate(seed) / "prefix/step0298_step"
        and proof["optimizer_steps_performed"] == 0
        and proof["first_outer_not_executed"] is True,
        "only this new seed's genuinely trained zero-update migration can branch",
    )
    require(
        rt.launcher.sha(path / "state.pt") == summary["state_sha256"],
        "new shared state bytes changed",
    )
    return path


def run_prefix(root, seed, gpu_index, *, resume=False):
    coordinate(seed)
    root, rt = Path(root).resolve(), load_runtime()
    plan, full, prefix, assets = checked_launch(root)
    seed_root = root / coordinate(seed)
    require(resume or not seed_root.exists(), "existing prefix requires explicit resume")
    require(not (seed_root / "prefix_result/record.json").exists(), "completed prefix cannot rerun")
    with locked_worker(root, plan, seed, None, gpu_index) as admission:
        require(not (seed_root / "prefix_result/record.json").exists(), "prefix already complete")
        attempt = _attempt(seed_root, plan, seed, None, resume, admission)
        components = None
        try:
            components = rt.launcher._load_components(assets, seed)
            model, tokenizer, optimizer, scope, fresh = components
            driver = adapters().PrefixDriver(
                model,
                optimizer,
                prefix,
                root=seed_root / "prefix",
                seed=seed,
                device="cuda:0",
                tokenizer=tokenizer,
                adapter_scope=scope,
            )
            checkpoint = rt.prefix.latest_checkpoint(driver.root)
            if checkpoint is None:
                fresh_record = rt.launcher.bound(
                    dict(
                        **fresh,
                        protocol_id=plan["id"],
                        old_model_or_optimizer_loaded=False,
                    )
                )
                fresh_path = seed_root / "fresh_initialization/record.json"
                if fresh_path.exists():
                    require(
                        resume and rt.launcher.read_bound(fresh_path) == fresh_record,
                        "pre-checkpoint resume must reproduce identical fresh initialization",
                    )
                else:
                    rt.v8._publish(fresh_path.parent, fresh_record)
            else:
                require(resume, "existing prefix commit requires explicit resume")
                driver.restore(checkpoint)
            actual = driver.run_until()
            require(
                actual["committed_step"] == 298 and actual["consumption"]["updates"] == 298,
                "genuine new 298-update prefix required",
            )
            checkpoint = driver.root / "step0298_step"
            shared = seed_root / "shared/step0298_step"
            if shared.exists():
                require(resume, "existing migration requires explicit resume")
                state, summary = rt.prefix._state(shared)
                before, _ = rt.prefix._state(checkpoint)
                require(
                    summary["evidence"]["source_prefix"] == rt.prefix.checkpoint_ref(checkpoint)
                    and state["pi"] == state["prior"] == full._manifest.registration.pi0
                    and state["outer_done"] == []
                    and rt.v8._tree_digest(
                        {k: before[k] for k in rt.prefix.COMMON_COMPUTATION_FIELDS}
                    )
                    == rt.v8._tree_digest(
                        {k: state[k] for k in rt.prefix.COMMON_COMPUTATION_FIELDS}
                    ),
                    "existing migration is not an exact zero-update continuation",
                )
            else:
                adapters().migrate(checkpoint, prefix, full, seed_root / "shared")
            result = rt.launcher.bound(
                dict(
                    schema="v25_new_prefix_result.v1",
                    protocol_id=plan["id"],
                    seed=seed,
                    prefix_checkpoint=rt.prefix.checkpoint_ref(checkpoint),
                    shared_checkpoint=rt.launcher._checkpoint_ref(shared),
                    actual=actual,
                    first_step_acceptance=rt.launcher.file_binding(
                        driver.root / "first_step_acceptance/record.json"
                    ),
                    fresh_initialization=rt.launcher.file_binding(
                        seed_root / "fresh_initialization/record.json"
                    ),
                    actual_new_updates=298,
                    old_prefix_reused=False,
                    feedback_calls=0,
                    complete_prefix=True,
                    migration_optimizer_steps=0,
                )
            )
            rt.v8._publish(seed_root / "prefix_result", result)
            return result
        except Exception as failure:
            _failed(attempt, failure)
            raise
        finally:
            if components is not None:
                del components
            if rt.torch.cuda.is_initialized():
                rt.torch.cuda.empty_cache()


def run_arm(root, seed, arm, gpu_index, *, resume=False):
    arm = arm_name(arm)
    coordinate(seed, arm)
    root, rt = Path(root).resolve(), load_runtime()
    plan, pool, _prefix, assets = checked_launch(root)
    shared = _shared_checkpoint(root, plan, seed)
    arm_root = root / coordinate(seed, arm)
    require(resume or not arm_root.exists(), "existing arm requires explicit resume")
    require(not (arm_root / "result/record.json").exists(), "completed arm cannot rerun")
    rt.arms.no_partial_arm_feedback(arm_root)
    with locked_worker(root, plan, seed, arm, gpu_index) as admission:
        require(not (arm_root / "result/record.json").exists(), "arm already complete")
        rt.arms.no_partial_arm_feedback(arm_root)
        attempt = _attempt(arm_root, plan, seed, arm, resume, admission)
        components = None
        try:
            components = rt.launcher._load_components(assets, seed)
            model, tokenizer, optimizer, scope, _fresh = components
            collector = None
            if arm in ("C-only", "Full"):
                collector = rt.v8.LocalFeedbackCollector(
                    snapshot=assets["snapshot"],
                    role_plan=assets["role_plan"],
                    root=arm_root / "feedback",
                    config=plan["feedback_config"],
                    model_id=assets["assets"]["base_binding"]["id"],
                    seeds=tuple(plan["feedback_seeds"]),
                )
            driver = adapters().TrainingDriver(
                model,
                optimizer,
                pool,
                root=arm_root / "training",
                seed=seed,
                arm=arm,
                device="cuda:0",
                tokenizer=tokenizer,
                adapter_scope=scope,
                feedback_collector=collector,
            )
            committed = rt.launcher.latest_checkpoint(driver.root)
            if committed is None:
                driver.restore(shared, branch=True)
            else:
                require(resume, "existing arm commit requires explicit resume")
                driver.restore(committed)
            actual = driver.run_until(driver.final_step)
            expected = list(driver.outer_steps) if collector else []
            require(
                driver.step_index == 1490 and driver.outer_done == expected,
                "all actual scheduled outer updates required",
            )
            result = rt.launcher.bound(
                dict(
                    schema="v25_new_arm_result.v1",
                    protocol_id=plan["id"],
                    seed=seed,
                    arm=arm,
                    pool_id=pool.cache_id,
                    shared_checkpoint=rt.launcher._checkpoint_ref(shared),
                    final_checkpoint=rt.launcher._checkpoint_ref(driver.root / "step1490_step"),
                    result=actual,
                    actual_student_training=True,
                    actual_tail_updates=1192,
                    actual_feedback_denominator=700 if collector else 0,
                    actual_outer_updates=4 if collector else 0,
                    new_feedback_episodes=2800 if collector else 0,
                    old_checkpoint_or_feedback_reused=False,
                    cross_arm_feedback_shared=False,
                    cross_arm_outer_shared=False,
                    dev_evaluated=False,
                    test_opened=False,
                )
            )
            rt.v8._publish(arm_root / "result", result)
            return result
        except Exception as failure:
            _failed(attempt, failure)
            raise
        finally:
            if components is not None:
                del components
            if rt.torch.cuda.is_initialized():
                rt.torch.cuda.empty_cache()


def evaluation_contract(root):
    rt, plan = load_runtime(), checked_plan(root)
    assets = read_reference(plan["assets_protocol"])
    reference = rt.launcher.file_binding(Path(root) / "registration/record.json")
    return dict(
        registration=reference,
        registration_id=plan["id"],
        training_protocol=reference,
        training_protocol_id=plan["id"],
        training_root=str(Path(root).resolve()),
        seeds=list(SEEDS),
        arms=list(ARMS),
        arm_directories=ARM_DIRECTORIES,
        final_step=1490,
        runtime_binding=plan["runtime_binding"],
        assets=assets["assets"],
        assets_source=assets,
        assets_protocol=plan["assets_protocol"],
        training_task_ids=plan["training_task_ids"],
        material_identity=plan["material_identity"],
        device_policy=plan["device_policy"],
        tokenizer_binding=plan["tokenizer_binding"],
    )


def checked_evaluation_checkpoint(root, seed, arm):
    arm = arm_name(arm)
    coordinate(seed, arm)
    root, rt = Path(root).resolve(), load_runtime()
    plan = checked_plan(root)
    result_path = root / coordinate(seed, arm) / "result/record.json"
    result = rt.launcher.read_bound(result_path)
    require(
        result["schema"] == "v25_new_arm_result.v1"
        and result["protocol_id"] == plan["id"]
        and result["seed"] == seed
        and result["arm"] == arm
        and result["actual_student_training"] is True
        and result["actual_tail_updates"] == 1192
        and result["pool_id"] == plan["material_identity"]["pool_id"],
        "actual new completed arm result required, not old endpoint or readiness flag",
    )
    path = root / coordinate(seed, arm) / "training/step1490_step"
    require(
        result["final_checkpoint"] == rt.launcher._checkpoint_ref(path)
        and Path(result["final_checkpoint"]["path"]).resolve() == path,
        "wrong actual registered endpoint",
    )
    state, summary = rt.prefix._state(path)
    execution = plan["material_identity"]["execution_plan"]
    require(
        state["schema"] == "v8_committed_training_state.v1"
        and state["seed"] == summary["seed"] == seed
        and state["arm"] == summary["arm"] == arm
        and state["step"] == summary["step"] == 1490
        and summary["phase"] == "step"
        and state["pool_id"] == summary["pool_id"] == plan["material_identity"]["pool_id"]
        and state["execution_plan"] == execution
        and state["schedule"] == build_task_schedule(plan["training_task_ids"], seed)
        and summary["schedule_sha256"] == state["schedule"]["schedule_sha256"]
        and state["outer_done"] == (execution["outer_steps"] if arm in ("C-only", "Full") else []),
        "wrong new final state coordinate, schedule or completed outer history",
    )
    require(
        state["parameters"]
        and all(
            name.endswith((".lora_A", ".lora_B"))
            and value.dtype == rt.torch.float32
            and rt.torch.isfinite(value).all().item()
            for name, value in state["parameters"].items()
        ),
        "actual finite FP32 LoRA checkpoint required",
    )
    require(arm != "Static" or state["pi"] == state["prior"], "Static prior changed")
    evidence = dict(
        seed=seed,
        arm=arm,
        step=1490,
        phase="step",
        registration_id=plan["id"],
        checkpoint=rt.launcher.file_binding(path / "state.pt"),
        checkpoint_summary=rt.launcher.file_binding(path / "record.json"),
        arm_result=rt.launcher.file_binding(result_path),
        seed_result=rt.launcher.file_binding(result_path),
        state_sha256=summary["state_sha256"],
        actual_state_digest=summary["actual_state_digest"],
        parameter_digest=rt.v8.parameter_digest(state["parameters"]),
        buffers_digest=rt.v8._tree_digest(state["buffers"]),
        frozen_base_digest=state["frozen_base_digest"],
        adapter_binding=state["adapter_binding"],
        pool_id=state["pool_id"],
        schedule_sha256=state["schedule"]["schedule_sha256"],
    )
    return evidence, state


checked_final_checkpoint = checked_evaluation_checkpoint


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    prepare_parser.add_argument("--source-root", type=Path, default=V18)
    for name in ("prefix", "train"):
        sub = commands.add_parser(name)
        sub.add_argument("--root", type=Path, default=DEFAULT_ROOT)
        sub.add_argument("--seed", type=int, choices=SEEDS, required=True)
        sub.add_argument("--gpu-index", type=int, choices=range(8), required=True)
        sub.add_argument("--resume", action="store_true")
        if name == "train":
            sub.add_argument("--arm", choices=list(ARM_DIRECTORIES.values()), required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare(args.root, args.source_root)
    elif args.command == "prefix":
        result = run_prefix(args.root, args.seed, args.gpu_index, resume=args.resume)
    else:
        result = run_arm(args.root, args.seed, args.arm, args.gpu_index, resume=args.resume)
    print(json.dumps(dict(id=result["id"], command=args.command), ensure_ascii=False))


if __name__ == "__main__":
    main()
