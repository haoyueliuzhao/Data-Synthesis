"""Cold production phases at an actual B checkpoint, never a reference replay.

All differentiation, Adam proxy, full logP replay, C/N/pi and SFT mathematics
remain the frozen functions. This shell binds actual points and persists real
CPU tensors between processes. It does not run the old monolithic outer loop.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import gc
import hashlib
import importlib
import io
import json
import math
import os
import resource
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace

import finqa_v37_controller as control

GIB = 1024**3
STAGES = (
    "shard00",
    "shard01",
    "shard02",
    "shard03",
    "virtual_point",
    "replay_R3",
    "distribution",
    "train",
)


@contextmanager
def training_point_locks(context, stage):
    """Cooperate with the original seed/arm writer locks, not just this shell."""
    seed = context["seed"]
    arm = {"Static": "static", "C-only": "c_only", "Full": "full"}.get(context["arm"])
    training_root = Path(context["training_root"]).resolve()
    control.require(
        seed in (137, 251, 389)
        and arm is not None
        and Path(context["arm_root"]).resolve() == training_root / f"seed{seed}/arms/{arm}",
        "original training lock target differs from actual seed/arm",
    )
    directory = training_root / "locks"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / f"seed{seed}.lock").open("a") as seed_lock:
        fcntl.flock(seed_lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        with (directory / f"seed{seed}-{arm}.lock").open("a") as arm_lock:
            mode = fcntl.LOCK_EX if stage == "train" else fcntl.LOCK_SH
            fcntl.flock(arm_lock, mode | fcntl.LOCK_NB)
            yield


def dependencies(root):
    training = control.frozen_training_module()
    rt = training.load_runtime()
    # Imports that may initialize Python modules precede restoring the actual
    # training RNG. Never restore RNG after the computation to mask a mutation.
    for name in (
        "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.trajectory_consumer",
        "trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.optimizer_pullback",
        "trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.distribution",
        "trusted_synthesis.finance_research.v6_task",
    ):
        importlib.import_module(name)
    modules = dict(
        context=importlib.import_module("finqa_v37_task_cache"),
        original_cache=importlib.import_module("finqa_v35_task_cache"),
        inherited=importlib.import_module("finqa_v32_performance_worker"),
        memory=importlib.import_module("finqa_v34_tail_memory"),
        guard=importlib.import_module("finqa_v32_same_point_guard"),
        replay=importlib.import_module("finqa_v33_activation_residency"),
        trainer=importlib.import_module("finqa_v37_training"),
        immutable=importlib.import_module("trusted_synthesis.core.immutable_artifacts"),
    )
    for name in ("context", "original_cache", "inherited", "memory", "guard", "replay", "trainer"):
        path = Path(modules[name].__file__).resolve()
        control.require(
            path == Path(root).resolve() / "implementation" / path.name,
            "production dependency is not in the committed execution seal",
        )
    return SimpleNamespace(training=training, rt=rt, **modules)


def cpu_tensors(values):
    return {name: value.detach().cpu().clone() for name, value in values.items()}


def save_payload(directory, rt, immutable, *, context, phase, value):
    """Atomically publish actual tensors and their context/hash/semantic identity."""
    target = Path(directory) / "payload"
    stream = io.BytesIO()
    rt.torch.save(value, stream)
    raw = stream.getvalue()
    body = dict(
        schema="v37_actual_stage_payload.v1",
        at=control.now(),
        context_id=context["id"],
        phase=phase,
        state_sha256=hashlib.sha256(raw).hexdigest(),
        state_digest=rt.v8._tree_digest(value),
        state_bytes=len(raw),
        actual_tensors_saved=True,
    )
    record = dict(body, id=control.digest(body))
    immutable.write_immutable_artifact_directory(
        target,
        {
            "state.pt": raw,
            "record.json": (
                json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
                + "\n"
            ).encode(),
        },
    )
    return control.entry(target / "record.json")


def read_payload(payload_directory, rt, *, context, phase=None):
    directory = Path(payload_directory)
    record = control.checked(directory / "record.json")
    control.require(
        record["schema"] == "v37_actual_stage_payload.v1"
        and record["context_id"] == context["id"]
        and record["actual_tensors_saved"] is True
        and (phase is None or record["phase"] == phase),
        "stage payload belongs to another actual point or phase",
    )
    raw = (directory / "state.pt").read_bytes()
    control.require(
        len(raw) == record["state_bytes"]
        and hashlib.sha256(raw).hexdigest() == record["state_sha256"],
        "actual stage tensor bytes changed",
    )
    value = rt.torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
    control.require(
        rt.v8._tree_digest(value) == record["state_digest"],
        "actual stage tensor semantic digest changed",
    )
    return value


def state_identity(bundle, model, optimizer):
    rt = bundle.rt
    identity = bundle.inherited.state_identity(rt, model, optimizer)
    identity["existing_parameter_gradients"] = rt.v8._tree_digest(
        {name: value.grad for name, value in model.named_parameters()}
    )
    identity["frozen_parameter_storage_versions"] = rt.v8._tree_digest(
        [
            (
                name,
                value._version,
                value.untyped_storage()._cdata,
                tuple(value.shape),
                tuple(value.stride()),
                value.storage_offset(),
            )
            for name, value in model.named_parameters()
            if not value.requires_grad
        ]
    )
    return identity


def validate_branch(context, rt):
    branch = context["branch"]
    control.require(
        context["arm"] in ("C-only", "Full")
        and branch["contribution_only"] is (context["arm"] == "C-only")
        and branch["b_N"] == (0 if context["arm"] == "C-only" else 0.2)
        and branch["parameters"] == rt.v8.PARAMETERS,
        "C-only/Full branch or original distribution parameters changed",
    )
    return branch


def checked_vector(values, context, rt):
    specs = context["parameter_spec"]
    control.require(
        list(values) == [item["name"] for item in specs], "actual vector parameter order differs"
    )
    for item in specs:
        value = values[item["name"]]
        control.require(
            list(value.shape) == item["shape"]
            and str(value.dtype) == item["dtype"]
            and bool(rt.torch.isfinite(value).all()),
            "invalid actual vector coordinate",
        )
    return values


def require_upstream(context_directory, context, plan, stage):
    """A tensor payload from a failed/unexited stage cannot authorize the next."""
    required = {
        "virtual_point": ("shard00", "shard01", "shard02", "shard03"),
        "replay_R3": ("virtual_point",),
        "distribution": ("virtual_point", "replay_R3"),
        "train": ("distribution",) if context["due_outer"] else (),
    }.get(stage, ())
    for previous in required:
        directory = Path(context_directory) / previous
        result = control.checked(directory / "result/record.json")
        exited = control.checked(directory / "exit/record.json")
        control.require(
            result["protocol_id"] == exited["protocol_id"] == plan["id"]
            and result["context_id"] == exited["context_id"] == context["id"]
            and result["stage"] == exited["stage"] == previous
            and result["status"] == "COMPLETE"
            and result["model_released"] is True
            and result["resources"]["all_gates_passed"] is True
            and exited["returncode"] == 0,
            "upstream production stage is failed, unexited or from another actual point",
        )
        if previous in ("virtual_point", "replay_R3", "distribution"):
            control.require(
                result["payload"] == control.entry(directory / "payload/record.json"),
                "upstream accepted payload reference differs",
            )


def load_feedback(point, context, bundle):
    """Load only the persisted actual point's immutable cohort; never collect."""
    rt, guard = bundle.rt, bundle.guard
    root = Path(point["feedback_root"])
    control.require(
        root == Path(context["feedback"]["base_root"]) / rt.v8.digest(point["point_id"]),
        "cross-arm or cross-point feedback forbidden",
    )
    for reference in point["feedback_files"].values():
        control.require(
            control.sha(reference["path"]) == reference["sha256"],
            "point-bound sealed feedback bytes changed",
        )
    intent = json.loads((root / "intent/record.json").read_bytes())
    control.require(
        intent["point_id"] == point["point_id"], "feedback intent belongs to another point"
    )
    cohort, rewards, _ = guard._load_sealed(root, intent, rt)
    control.require(
        cohort.identity.point_id == point["point_id"]
        and cohort.identity.parameter_digest == rt.v8.parameter_digest(point["theta_bar"])
        and cohort.denominator == 700
        and len(rewards) == 700
        and rewards == point["rewards"]
        and cohort.model_dump(mode="json", exclude={"episodes"}) == point["feedback_seal"],
        "complete original feedback/reward/virtual parameter binding differs",
    )
    return cohort, rewards


def execute_shard(directory, context, stage, driver, pool, cache, bundle, monitor, stop):
    rt, original_cache = bundle.rt, bundle.original_cache
    task_plan = control.read_ref(context["task_plan"])
    tasks = task_plan["assignments"][int(stage[-2:])]["task_ids"]
    original = state_identity(bundle, driver.model, driver.optimizer)
    completed, reused, rows = [], [], 0
    for task_id in tasks:
        monitor.check_stop("task_start", task_id=task_id)
        if cache.has(task_id):
            reused.append(task_id)
        else:
            view = original_cache.TaskPoolView(pool, [task_id])
            monitor.clear_unused("before_task_class_gradients")
            before = state_identity(bundle, driver.model, driver.optimizer)
            values, receipt = bundle.memory.class_gradients_with_cpu_saves(
                rt, driver.model, view, device="cuda:0", monitor=monitor
            )
            rt.torch.cuda.synchronize()
            control.require(list(values) == [task_id], "class kernel changed task coverage")
            after = state_identity(bundle, driver.model, driver.optimizer)
            control.require(before == after == original, "class task mutated real training state")
            monitor.clear_unused("task_class_gradients_complete")
            monitor.check_stop("before_task_commit", task_id=task_id)
            control.require(not stop.requested, "stop before whole-task durable commit")
            cache.commit(
                task_id,
                values[task_id].values_cpu,
                receipt=dict(
                    context_id=context["id"],
                    stage=stage,
                    state_unchanged=True,
                    pre_state_identity=before,
                    post_state_identity=after,
                    storage=receipt,
                    original_class_bytecode_unchanged=True,
                    API_calls=0,
                    new_sampling_calls=0,
                    scoring_calls=0,
                    optimizer_steps=0,
                    replayed_responses=0,
                ),
            )
            rows += receipt["rows_completed"]
            del values
        completed.append(task_id)
        control.status(
            directory,
            dict(
                phase="CLASS_TASKS_RUNNING",
                context_id=context["id"],
                committed_task_ids=completed,
                committed_task_count=len(completed),
                assigned_task_count=len(tasks),
                reused_task_ids=reused,
                new_completed_rows=rows,
                row_count_is_not_a_checkpoint=True,
            ),
        )
    monitor.clear_unused("class_shard_complete")
    control.require(
        original == state_identity(bundle, driver.model, driver.optimizer),
        "class shard changed actual pre-state",
    )
    return dict(
        task_ids=completed,
        task_count=len(completed),
        class_task_calls=len(completed) - len(reused),
        reused_task_ids=reused,
        new_completed_rows=rows,
        class_gradient_passes=0,
        actual_point_task_cache=True,
    )


def execute_virtual(
    directory, context, pre_state, driver, gradients, bundle, monitor, stop, *, collector=None
):
    rt, guard = bundle.rt, bundle.guard
    validate_branch(context, rt)
    prepared = rt.v8.prepare_virtual_point(
        driver.parameters, driver.optimizer, gradients, pre_state["pi"], context["mu"]
    )
    monitor.clear_unused("virtual_point_complete")
    point_id = guard.recompute_point_id(
        pre_state, theta_bar=prepared["theta_bar"], G=prepared["G"], frozen_runtime=rt
    )
    point = dict(
        G=cpu_tensors(prepared["G"]),
        theta_bar=cpu_tensors(prepared["theta_bar"]),
        update=cpu_tensors(prepared["update"]),
        diagnostics=copy.deepcopy(prepared["diagnostics"]),
        adam_binding_snapshot=copy.deepcopy(prepared["binding"].snapshot),
        point_id=point_id,
        pre_state_digest=context["pre_state_digest"],
        branch=copy.deepcopy(context["branch"]),
    )
    # Preserve computed values even if old-point admission fails. This directory
    # is an audit payload, never a feedback/provider directory.
    point_ref = save_payload(
        directory / "computed_point",
        rt,
        bundle.immutable,
        context=context,
        phase="virtual_point_values",
        value=point,
    )
    mode = context["feedback"]["mode"]
    if mode == "sealed_existing":
        control.require(collector is None, "existing feedback cannot enter a collector branch")
        manifest = control.read_ref(context["feedback"]["manifest"])
        guard.check_recomputed_point(manifest, point_id, context["feedback"]["root"])
        control.require(
            manifest["pre_state_digest"] == context["pre_state_digest"],
            "sealed pending feedback pre-state differs",
        )
        control.require(not stop.requested, "stopped before reading admitted sealed feedback")
        cohort, rewards = guard.read_sealed_feedback(manifest, frozen_runtime=rt)
        feedback_root = Path(manifest["feedback_root"])
        new_episodes = sampling_calls = scoring_calls = 0
    else:
        control.require(
            mode == "first_sampling" and context["feedback"]["expected_point_id"] is None,
            "unknown feedback mode or reference-point substitution",
        )
        control.require(
            type(collector) is rt.v8.LocalFeedbackCollector,
            "first feedback requires the exact original local collector",
        )
        feedback_root = Path(context["feedback"]["base_root"]) / rt.v8.digest(point_id)
        control.require(
            not feedback_root.exists(), "existing/partial feedback cannot be sampled or rescored"
        )
        control.require(not stop.requested, "stopped before first actual feedback sampling")
        event_count = 0

        def event(value):
            nonlocal event_count
            control.publish(
                directory / "feedback_events" / f"event{event_count:06d}/record.json",
                dict(
                    schema="v37_original_collector_event.v1",
                    at=control.now(),
                    context_id=context["id"],
                    point_id=point_id,
                    event=value,
                ),
            )
            event_count += 1
            monitor.snapshot("feedback." + value["phase"], boundary=True)

        cohort, rewards = collector.collect(
            driver.model,
            driver.tokenizer,
            prepared["theta_bar"],
            point_id=point_id,
            event_sink=event,
        )
        new_episodes = 700
        sampling_calls = sum(ep.actual_model_calls for ep in cohort.episodes)
        scoring_calls = 700
    control.require(
        cohort.denominator == len(rewards) == 700
        and cohort.identity.point_id == point_id
        and cohort.identity.parameter_digest == rt.v8.parameter_digest(prepared["theta_bar"]),
        "feedback is not the complete actual virtual-point cohort",
    )
    feedback_files = {
        relative: control.file_ref(feedback_root / relative)
        for relative in (
            "intent/record.json",
            "cohort_seal/record.json",
            "native_rewards/record.json",
            "draw0/run.json",
            "draw0/generation_seal/seal.json",
            "draw1/run.json",
            "draw1/generation_seal/seal.json",
        )
    }
    point.update(
        feedback_root=str(feedback_root),
        feedback_files=feedback_files,
        feedback_seal=cohort.model_dump(mode="json", exclude={"episodes"}),
        rewards=list(rewards),
        computed_point_payload=point_ref,
        feedback_mode=mode,
        new_feedback_episodes=new_episodes,
        positive_reward_response_count=sum(
            len(ep.turns)
            for ep, reward in zip(cohort.episodes, rewards, strict=True)
            if reward != 0
        ),
    )
    payload = save_payload(
        directory, rt, bundle.immutable, context=context, phase="virtual_point", value=point
    )
    monitor.clear_unused("virtual_feedback_sealed")
    return dict(
        payload=payload,
        point_id=point_id,
        feedback_mode=mode,
        denominator=700,
        feedback_seal_sha256=cohort.seal_sha256,
        new_feedback_episodes=new_episodes,
        new_sampling_calls=sampling_calls,
        scoring_calls=scoring_calls,
        original_sealed_point_matched=True if mode == "sealed_existing" else None,
        population_gradient_digest=rt.v8.parameter_digest(prepared["G"]),
        actual_virtual_theta_digest=rt.v8.parameter_digest(prepared["theta_bar"]),
        class_gradient_passes=0,
        response_count=point["positive_reward_response_count"],
    )


def execute_replay(
    directory, context, pre_state, point, cohort, rewards, driver, bundle, monitor, stop
):
    rt, backend = bundle.rt, bundle.replay
    theta = {
        name: value.to(driver.parameters[name].device) for name, value in point["theta_bar"].items()
    }
    profile = context["id"]
    checkpoint_root = directory / "checkpoints"
    backend_identity = dict(
        context_id=context["id"],
        variant="R3",
        version=backend.BACKEND_VERSION,
        source_binding=backend.source_binding(),
    )
    feedback = backend.optimized.bind_dependencies(
        backend.v32.feedback_gradient, BACKEND_VERSION=backend.BACKEND_VERSION
    )
    checkpoint_events = []

    def response_observation(value):
        # Let the original accumulator observe stop AFTER its logP validation,
        # ordered add_ and durable pause checkpoint; resource gates still run.
        monitor.snapshot(
            "replay." + value["phase"],
            boundary=True,
            response_backend_observation=value,
            cooperative_stop_pending=stop.requested,
        )

    def factory(model, parameters):
        return backend.R3Session(
            model,
            parameters,
            profile_id=profile,
            resident_kv_budget_bytes=2 * GIB,
            full_kv_budget_bytes=8 * GIB,
            activation_resident_budget_bytes=16 * GIB,
            allocated_memory_limit_bytes=76 * GIB,
            free_memory_reserve_bytes=2 * GIB,
            response_monitor=response_observation,
        )

    def event(value):
        if value.get("event") == "feedback_checkpoint_committed":
            checkpoint_events.append(value)

    rng_source = dict(
        checkpoint=context["checkpoint"]["state"],
        field="rng",
        digest=rt.v8._tree_digest(pre_state["rng"]),
    )
    monitor.clear_unused("before_complete_R3_replay")
    with rt.v8.installed_point(driver.model, theta) as installed:
        gJ, report = feedback(
            cohort,
            rewards,
            driver.model,
            installed,
            root=checkpoint_root,
            profile_id=profile,
            backend_factory=factory,
            backend_identity=backend_identity,
            rng_restore_source=rng_source,
            pause_request=stop,
            pause_after_response=None,
            checkpoint_every=16,
            event_sink=event,
        )
    control.require(
        report["complete_replay"] is True
        and report["denominator"] == 700
        and report["point_id"] == point["point_id"]
        and report["gJ_digest"] == rt.v8.parameter_digest(gJ),
        "incomplete or foreign production response accumulator",
    )
    gradient = cpu_tensors(checked_vector(gJ, context, rt))
    value = dict(
        gJ=gradient,
        feedback_report=copy.deepcopy(report),
        point_id=point["point_id"],
        rng_source=rng_source,
        current_point_only=True,
        V33_reference_gradient_used=False,
    )
    payload = save_payload(
        directory, rt, bundle.immutable, context=context, phase="replay_R3", value=value
    )
    count = report["response_checkpoint_binding"]["response_count"]
    final = control.entry(checkpoint_root / f"response{count:06d}/record.json")
    monitor.clear_unused("complete_R3_replay")
    control.require(not stop.requested, "stop requested after complete replay payload saved")
    return dict(
        payload=payload,
        gJ_digest=report["gJ_digest"],
        denominator=700,
        response_count=count,
        restored_completed_responses=report["restored_completed_responses"],
        replayed_responses=report["accounting"].get("responses_replayed", 0)
        - report["restored_completed_responses"],
        complete_replay=True,
        current_point_only=True,
        final_checkpoint=final,
        checkpoint_events=checkpoint_events,
        replay_backend=backend.BACKEND_VERSION,
    )


def rebind_prepared(point, driver, bundle):
    """Rebind real Adam state, retaining actual persisted G/theta/update values."""
    rt = bundle.rt
    adam = rt.v8.prepare_virtual_point.__globals__["_adam"]()
    clip = point["adam_binding_snapshot"]["clip"]
    binding = adam.bind_adamw(
        driver.parameters,
        driver.optimizer,
        clip_max_norm=clip["max_norm"],
        clip_epsilon=clip["epsilon"],
    )
    control.require(
        binding.snapshot == point["adam_binding_snapshot"],
        "cold real Adam binding differs from persisted virtual point",
    )

    def to_device(values):
        return {name: value.to(driver.parameters[name].device) for name, value in values.items()}

    return dict(
        binding=binding,
        G=to_device(point["G"]),
        theta_bar=to_device(point["theta_bar"]),
        update=to_device(point["update"]),
        diagnostics=copy.deepcopy(point["diagnostics"]),
    )


def execute_distribution(
    directory, context, pre_state, point, replay, driver, gradients, bundle, monitor, stop
):
    rt = bundle.rt
    branch = validate_branch(context, rt)
    control.require(
        replay["current_point_only"] is True
        and replay["V33_reference_gradient_used"] is False
        and replay["point_id"] == point["point_id"],
        "foreign replay gradient input",
    )
    prepared = rebind_prepared(point, driver, bundle)
    gJ = {
        name: value.to(driver.parameters[name].device)
        for name, value in checked_vector(replay["gJ"], context, rt).items()
    }
    report = replay["feedback_report"]
    control.require(
        report["denominator"] == 700 and report["complete_replay"] is True,
        "production update requires actual complete fixed700 replay",
    )
    recomputed = bundle.guard.recompute_point_id(
        pre_state, theta_bar=prepared["theta_bar"], G=prepared["G"], frozen_runtime=rt
    )
    control.require(recomputed == point["point_id"], "cold virtual point changed")
    monitor.clear_unused("before_distribution")
    control.require(not stop.requested, "stopped before production C/N/pi")
    result = rt.v8.update_distribution(
        prepared,
        gradients,
        gJ,
        pre_state["pi"],
        pre_state["prior"],
        context["mu"],
        feedback_report=report,
        contribution_only=branch["contribution_only"],
        control_tasks=[task for task, values in pre_state["prior"].items() if len(values) == 1],
        **branch["parameters"],
    )
    distribution = result["distribution"]
    if "effective_novelty_exponent" in distribution:
        control.require(
            distribution["effective_novelty_exponent"] == branch["b_N"]
            and distribution["contribution_only"] is branch["contribution_only"],
            "Full novelty or C-only branch was changed",
        )
    novelty = (
        copy.deepcopy(distribution["N"])
        if "N" in distribution
        else {
            task: copy.deepcopy(row["N"]) for task, row in distribution["task_diagnostics"].items()
        }
    )
    evidence = {key: copy.deepcopy(value) for key, value in result.items() if key != "a"}
    evidence.update(
        actual_virtual_theta_digest=rt.v8.parameter_digest(prepared["theta_bar"]),
        population_gradient_digest=rt.v8.parameter_digest(prepared["G"]),
        feedback_gradient_digest=rt.v8.parameter_digest(gJ),
        pullback_digest=rt.v8.parameter_digest(result["a"]),
        feedback_seal_sha256=point["feedback_seal"]["seal_sha256"],
        actual_feedback_denominator=700,
        shared_with_other_arm=False,
    )
    outer_inputs = dict(
        schema="v9_real_outer_inputs.v1",
        pre_state=pre_state,
        point_id=point["point_id"],
        mu=copy.deepcopy(context["mu"]),
        G=cpu_tensors(prepared["G"]),
        theta_bar=cpu_tensors(prepared["theta_bar"]),
        gJ=cpu_tensors(gJ),
        pullback=cpu_tensors(result["a"]),
        C=copy.deepcopy(result["C"]),
        q_next=copy.deepcopy(distribution["pi_next"]),
        feedback_seal=copy.deepcopy(point["feedback_seal"]),
        rewards=list(point["rewards"]),
        feedback_report=copy.deepcopy(report),
        actual_tensors_saved=True,
        new_feedback_for_mechanisms=False,
    )
    payload = save_payload(
        directory,
        rt,
        bundle.immutable,
        context=context,
        phase="distribution",
        value=dict(
            outer_inputs=outer_inputs,
            evidence=evidence,
            N=novelty,
            pi_before=copy.deepcopy(pre_state["pi"]),
            pi_after=copy.deepcopy(distribution["pi_next"]),
            pre_state_digest=context["pre_state_digest"],
            training_rng=rt.v8._rng(),
        ),
    )
    monitor.clear_unused("after_distribution")
    control.require(
        not stop.requested, "stop after actual C/N/pi payload saved, before any real commit"
    )
    return dict(
        payload=payload,
        point_id=point["point_id"],
        denominator=700,
        contribution_only=branch["contribution_only"],
        b_N=branch["b_N"],
        C_N_pi_saved=True,
        outer_commits=0,
        reference_comparison_performed=False,
        numerical_contract_checks_passed=True,
        class_gradient_passes=0,
    )


class DeadlineStop:
    def __init__(self, request, deadline_epoch):
        self.request, self.deadline_epoch = request, deadline_epoch

    @property
    def requested(self):
        return self.request.requested or time.time() >= self.deadline_epoch

    @property
    def reason(self):
        return self.request.reason or ("stage_deadline" if self.requested else None)

    def signals(self):
        return self.request.signals()


def host_memory():
    fields = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in {"VmRSS", "VmHWM"}:
            fields[key] = int(value.split()[0]) * 1024
    available = next(
        int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemAvailable:")
    )
    return dict(
        rss_bytes=fields["VmRSS"],
        peak_rss_bytes=max(
            fields["VmHWM"], int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
        ),
        available_bytes=available,
    )


class ResourceEvents:
    def __init__(self, sink, stage, stop):
        self.sink, self.stage, self.stop = sink, stage, stop
        self.limit = (160 if stage.startswith("shard") else 192) * GIB
        self.observations = []

    def __call__(self, gpu):
        host = host_memory()
        host.update(rss_limit_bytes=self.limit, available_reserve_bytes=96 * GIB)
        host["rss_pass"] = host["peak_rss_bytes"] <= self.limit
        host["available_pass"] = host["available_bytes"] >= 96 * GIB
        host["passed"] = host["rss_pass"] and host["available_pass"]
        row = dict(
            gpu,
            host=host,
            deadline_epoch=self.stop.deadline_epoch,
            deadline_pass=time.time() < self.stop.deadline_epoch,
        )
        row["passed"] = bool(gpu["passed"] and host["passed"] and row["deadline_pass"])
        self.observations.append(row)
        self.sink(row)
        control.require(host["passed"], "production host RAM envelope failed")
        # Replay cooperatively checkpoints the accumulated current response
        # before observing a deadline stop; never throw out that accumulator.
        if self.stage != "replay_R3":
            control.require(row["deadline_pass"], "production stage deadline reached")

    def report(self, monitor):
        gpu = monitor.report()
        return dict(
            all_gates_passed=bool(self.observations)
            and all(r["passed"] for r in self.observations),
            observations=self.observations,
            limits_unchanged=True,
            peak_resets_before_model_load=1,
            peak_resets_after_model_loading_begins=0,
            helper_peak_reset_calls=gpu["peak_reset_calls"],
            maximum_allocated_bytes=76 * GIB,
            minimum_device_free_bytes=2 * GIB,
            observed_peak_allocated_bytes=gpu["max_observed_peak_allocated_bytes"],
            observed_minimum_boundary_free_bytes=gpu["min_boundary_free_bytes"],
            host=dict(
                rss_limit_bytes=self.limit,
                available_reserve_bytes=96 * GIB,
                all_passed=bool(self.observations)
                and all(r["host"]["passed"] for r in self.observations),
                max_observed_peak_rss_bytes=max(
                    (r["host"]["peak_rss_bytes"] for r in self.observations), default=None
                ),
                min_observed_available_bytes=min(
                    (r["host"]["available_bytes"] for r in self.observations), default=None
                ),
            ),
        )


def run(root, context_directory, stage, gpu_index, deadline_epoch):
    root, context_directory = Path(root).resolve(), Path(context_directory).resolve()
    plan = control.checked_protocol(root)
    control.checked_implementation(root)
    control.require(
        Path(__file__).resolve() == root / "implementation" / Path(__file__).name,
        "only the frozen production worker may run",
    )
    control.require(
        stage in STAGES
        and gpu_index in (3, 4, 5, 7)
        and math.isfinite(deadline_epoch)
        and time.time() < deadline_epoch,
        "unregistered stage/device or expired production dispatch",
    )
    control.require(
        context_directory.is_relative_to(root), "production context escaped registered output"
    )
    directory = context_directory / stage
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        control.require(
            not (directory / "attempt/record.json").exists(),
            "stage needs explicit durable recovery, no automatic retry",
        )
        bundle = dependencies(root)
        rt, training = bundle.rt, bundle.training
        control.require(
            not rt.torch.cuda.is_initialized(), "production admission must remain CPU-only"
        )
        stop = DeadlineStop(bundle.replay.PauseRequest(), deadline_epoch)
        monitor = events = sampler = cache = context = None
        started = time.monotonic()
        with stop.signals(), ExitStack() as original_ownership:
            try:
                metadata = bundle.context.peek_context(context_directory)
                original_ownership.enter_context(training_point_locks(metadata, stage))
                context, pre_state, pool, cache = bundle.context.load_context(
                    context_directory,
                    training=training,
                    rt=rt,
                    original_cache_module=bundle.original_cache,
                )
                control.require(
                    context["id"] == metadata["id"],
                    "context changed while acquiring original arm lock",
                )
                control.require(
                    stage == "train" or context["due_outer"] is True,
                    "non-outer context cannot run outer phases",
                )
                require_upstream(context_directory, context, plan, stage)
                control.publish(
                    directory / "attempt/record.json",
                    dict(
                        schema="v37_actual_point_stage_attempt.v1",
                        at=control.now(),
                        protocol_id=plan["id"],
                        context_id=context["id"],
                        stage=stage,
                        gpu_index=gpu_index,
                        pid=os.getpid(),
                        deadline_epoch=deadline_epoch,
                        automatic_retry=False,
                        current_checkpoint=context["checkpoint"],
                        API_calls=0,
                    ),
                )
                gradients = point = replay = cohort = rewards = outer_payload = None
                if stage in ("virtual_point", "distribution"):
                    gradients = cache.assemble(device="cuda:0")  # Still CPU-backed before use.
                if stage in ("replay_R3", "distribution"):
                    point = read_payload(
                        context_directory / "virtual_point/payload",
                        rt,
                        context=context,
                        phase="virtual_point",
                    )
                    control.require(
                        bundle.guard.recompute_point_id(
                            pre_state, theta_bar=point["theta_bar"], G=point["G"], frozen_runtime=rt
                        )
                        == point["point_id"],
                        "stored virtual point changed",
                    )
                    cohort, rewards = load_feedback(point, context, bundle)
                if stage == "distribution":
                    replay = read_payload(
                        context_directory / "replay_R3/payload",
                        rt,
                        context=context,
                        phase="replay_R3",
                    )
                if stage == "train" and context["due_outer"]:
                    outer_payload = read_payload(
                        context_directory / "distribution/payload",
                        rt,
                        context=context,
                        phase="distribution",
                    )
                control.require(
                    not rt.torch.cuda.is_initialized(), "CPU source/cache reading initialized CUDA"
                )
                row = next((r for r in control.inventory() if r["index"] == gpu_index), None)
                control.require(
                    row is not None
                    and control.eligible(row, plan)
                    and row["uuid"] == plan["gpu_uuids"][str(gpu_index)],
                    "GPU is not fully idle or UUID changed",
                )
                control.require(not stop.requested, "stopped before CUDA admission")
                os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
                os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

                def event(value):
                    number = event.count
                    event.count += 1
                    control.publish(
                        directory / "resources" / f"event{number:06d}/record.json",
                        dict(
                            schema="v37_exact_resource_observation.v1",
                            at=control.now(),
                            protocol_id=plan["id"],
                            context_id=context["id"],
                            stage=stage,
                            observation=value,
                        ),
                    )

                event.count = 0
                events = ResourceEvents(event, stage, stop)
                sampler = bundle.inherited.DeviceSamples(row["uuid"])
                with sampler:
                    rt.torch.cuda.reset_peak_memory_stats()  # Exactly once, before loading.
                    monitor = bundle.memory.TailMemoryMonitor(
                        rt.torch,
                        event_sink=events,
                        stop_requested=(lambda: False)
                        if stage == "replay_R3"
                        else (lambda: stop.requested),
                    )
                    monitor.snapshot("before_model_load", boundary=True)
                    science = training.checked_plan(context["training_root"])
                    assets = rt.launcher.read_bound(science["assets_protocol"]["path"])
                    model, tokenizer, optimizer, scope, fresh = rt.launcher._load_components(
                        assets, context["seed"]
                    )
                    collector = None
                    if stage == "virtual_point" and context["feedback"]["mode"] == "first_sampling":
                        collector = rt.v8.LocalFeedbackCollector(
                            snapshot=assets["snapshot"],
                            role_plan=assets["role_plan"],
                            root=context["feedback"]["base_root"],
                            config=science["feedback_config"],
                            model_id=assets["assets"]["base_binding"]["id"],
                            seeds=tuple(science["feedback_seeds"]),
                        )
                    driver = training.adapters().TrainingDriver(
                        model,
                        optimizer,
                        pool,
                        root=Path(context["arm_root"]) / "training",
                        seed=context["seed"],
                        arm=context["arm"],
                        device="cuda:0",
                        tokenizer=tokenizer,
                        adapter_scope=scope,
                        feedback_collector=None,
                    )
                    driver.restore(context["checkpoint"]["path"])
                    control.require(
                        rt.v8._tree_digest(driver._payload()) == context["pre_state_digest"],
                        "actual model/Adam/RNG/pi/prior restore differs",
                    )
                    monitor.clear_unused("after_model_load")
                    original = state_identity(bundle, model, optimizer)
                    if stage.startswith("shard"):
                        body = execute_shard(
                            directory, context, stage, driver, pool, cache, bundle, monitor, stop
                        )
                    elif stage == "virtual_point":
                        body = execute_virtual(
                            directory,
                            context,
                            pre_state,
                            driver,
                            gradients,
                            bundle,
                            monitor,
                            stop,
                            collector=collector,
                        )
                    elif stage == "replay_R3":
                        body = execute_replay(
                            directory,
                            context,
                            pre_state,
                            point,
                            cohort,
                            rewards,
                            driver,
                            bundle,
                            monitor,
                            stop,
                        )
                    elif stage == "distribution":
                        body = execute_distribution(
                            directory,
                            context,
                            pre_state,
                            point,
                            replay,
                            driver,
                            gradients,
                            bundle,
                            monitor,
                            stop,
                        )
                    else:
                        body = bundle.trainer.execute_training(
                            context,
                            directory,
                            driver,
                            rt,
                            monitor,
                            lambda: stop.requested,
                            training=training,
                            outer_inputs=outer_payload["outer_inputs"] if outer_payload else None,
                            evidence=outer_payload["evidence"] if outer_payload else None,
                        )
                    if stage != "train":
                        control.require(
                            original == state_identity(bundle, model, optimizer)
                            and rt.v8._tree_digest(driver._payload())
                            == context["pre_state_digest"],
                            "cold outer stage mutated real Student/Adam/RNG/pi/prior/buffers",
                        )
                        body["model_optimizer_rng_buffers_unchanged"] = True
                    if cache is not None:
                        control.publish(
                            directory / "cache_tensor_verification/record.json",
                            dict(
                                schema="v37_actual_point_cache_verification.v1",
                                at=control.now(),
                                context_id=context["id"],
                                stage=stage,
                                **cache.verification_summary(),
                            ),
                        )
                        body["cache_tensor_verification"] = control.entry(
                            directory / "cache_tensor_verification/record.json"
                        )
                    del driver, model, optimizer, tokenizer, fresh, collector
                    gc.collect()
                    monitor.clear_unused("model_released")
                    resource_report = events.report(monitor)
                    control.require(
                        resource_report["all_gates_passed"] and not stop.requested,
                        "production final resource/deadline/stop gate failed",
                    )
                    defaults = dict(
                        API_calls=0,
                        new_sampling_calls=0,
                        scoring_calls=0,
                        optimizer_steps=body.get("actual_optimizer_steps", 0),
                        replayed_responses=0,
                    )
                    if "context_id" in body:
                        control.require(
                            body.pop("context_id") == context["id"],
                            "training result belongs to another context",
                        )
                    return control.publish(
                        directory / "result/record.json",
                        dict(
                            schema="v37_stage_result.v1",
                            at=control.now(),
                            protocol_id=plan["id"],
                            context_id=context["id"],
                            stage=stage,
                            status="COMPLETE",
                            gpu_index=gpu_index,
                            gpu_uuid=row["uuid"],
                            elapsed_stage_seconds=time.monotonic() - started,
                            resources=resource_report,
                            model_released=True,
                            telemetry=sampler.report(),
                            torch_version=rt.torch.__version__,
                            **(defaults | body),
                        ),
                    )
            except BaseException as error:
                control.publish(
                    directory / "failure/record.json",
                    dict(
                        schema="v37_stage_failure_no_retry.v1",
                        at=control.now(),
                        protocol_id=plan["id"],
                        context_id=context["id"] if context else None,
                        stage=stage,
                        error_type=type(error).__name__,
                        error=str(error),
                        automatic_retry=False,
                        durable_replay_checkpoint=getattr(error, "checkpoint_record", None),
                        resources=events.report(monitor) if monitor is not None else None,
                        telemetry=sampler.report() if sampler is not None else None,
                        complete_task_caches_preserved=True,
                        API_calls=0,
                    ),
                )
                raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--gpu-index", type=int, required=True)
    parser.add_argument("--deadline-epoch", type=float, required=True)
    args = parser.parse_args()
    result = run(args.root, args.context, args.stage, args.gpu_index, args.deadline_epoch)
    print(json.dumps(dict(status=result["status"], id=result["id"])))
