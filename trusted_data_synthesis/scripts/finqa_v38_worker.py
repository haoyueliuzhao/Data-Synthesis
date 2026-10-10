"""Bounded V37 continuation with explicit parent reads and new stage outputs.

The inherited V37 worker supplies every mathematical phase, training commit,
state comparison and lifetime resource monitor. This entry point only routes
the registered parent stages and waits for admission before initializing CUDA.
"""

from __future__ import annotations

import argparse
import fcntl
import gc
import json
import math
import os
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path

import finqa_v37_worker as base
import finqa_v38_admission as admission
import finqa_v38_controller as control
import finqa_v38_inheritance as inheritance

STAGES = base.STAGES


@contextmanager
def bound_parent_control():
    """Use new protocol routing without editing the frozen parent module."""
    previous = base.control
    base.control = control
    try:
        yield
    finally:
        base.control = previous


def dependencies(root):
    for module in (base, admission, control, inheritance):
        path = Path(module.__file__).resolve()
        control.require(
            path == Path(root) / "implementation" / path.name,
            "recovery dependency is not in the committed execution seal",
        )
    return base.dependencies(root)


def require_inherited_coordinate(context, inherited):
    if inherited:
        control.require(
            context["seed"] == 137
            and context["arm"] == "C-only"
            and context["step"] == 1192
            and context["due_outer"] is True
            and context["training_stop_step"] == 1193,
            "inherited pilot must retain its original outer and one-step SFT boundary",
        )


def read_stage_payload(context_directory, plan, stage, rt, context):
    directory = inheritance.stage_directory(context_directory, plan, stage)
    return base.read_payload(directory / "payload", rt, context=context, phase=stage)


def run(root, context_directory, stage, gpu_index, deadline_epoch):
    with bound_parent_control():
        return _run(root, context_directory, stage, gpu_index, deadline_epoch)


def _run(root, context_directory, stage, gpu_index, deadline_epoch):
    root, context_directory = Path(root).resolve(), Path(context_directory).resolve()
    plan = control.checked_protocol(root)
    control.checked_implementation(root)
    control.require(
        Path(__file__).resolve() == root / "implementation/finqa_v38_worker.py",
        "only the frozen recovery worker may run",
    )
    control.require(
        stage in STAGES
        and gpu_index in (3, 4, 5, 7)
        and math.isfinite(deadline_epoch)
        and time.time() < deadline_epoch,
        "unregistered stage/device or expired recovery dispatch",
    )
    control.require(context_directory.is_relative_to(root), "recovery context escaped new output")
    directory = context_directory / stage
    origin_context = inheritance.resolve_origin_context(context_directory, plan)
    inherited = origin_context != context_directory
    control.require(
        inheritance.stage_directory(context_directory, plan, stage) == directory
        and (not inherited or stage in ("distribution", "train")),
        "completed parent stages cannot be dispatched or written again",
    )
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        control.require(
            not any(
                (directory / name / "record.json").exists()
                for name in ("attempt", "failure", "result")
            ),
            "stage needs another explicit durable recovery, no automatic retry",
        )
        bundle = dependencies(root)
        rt, training = bundle.rt, bundle.training
        control.require(
            not rt.torch.cuda.is_initialized(), "recovery admission must remain CPU-only"
        )
        stop = base.DeadlineStop(bundle.replay.PauseRequest(), deadline_epoch)
        monitor = events = sampler = cache = context = metadata = None
        started = time.monotonic()
        with stop.signals(), ExitStack() as original_ownership:
            try:
                metadata = bundle.context.peek_context(origin_context)
                original_ownership.enter_context(base.training_point_locks(metadata, stage))
                context, pre_state, pool, cache = bundle.context.load_context(
                    origin_context,
                    training=training,
                    rt=rt,
                    original_cache_module=bundle.original_cache,
                )
                control.require(
                    context["id"] == metadata["id"],
                    "context changed while acquiring original arm lock",
                )
                require_inherited_coordinate(context, inherited)
                control.require(
                    stage == "train" or context["due_outer"] is True,
                    "non-outer context cannot run outer phases",
                )
                inheritance.require_upstream(context_directory, context, plan, stage, control)
                control.publish(
                    directory / "attempt/record.json",
                    dict(
                        schema="v38_actual_point_stage_attempt.v1",
                        at=control.now(),
                        protocol_id=plan["id"],
                        context_id=context["id"],
                        stage=stage,
                        gpu_index=gpu_index,
                        pid=os.getpid(),
                        deadline_epoch=deadline_epoch,
                        automatic_retry=False,
                        current_checkpoint=context["checkpoint"],
                        inherited_context=inherited,
                        origin_context_directory=str(origin_context),
                        output_context_directory=str(context_directory),
                        API_calls=0,
                    ),
                )
                gradients = point = replay = cohort = rewards = outer_payload = None
                if stage in ("virtual_point", "distribution"):
                    gradients = cache.assemble(device="cuda:0")  # CPU-backed until use.
                if stage in ("replay_R3", "distribution"):
                    point = read_stage_payload(
                        context_directory, plan, "virtual_point", rt, context
                    )
                    control.require(
                        bundle.guard.recompute_point_id(
                            pre_state, theta_bar=point["theta_bar"], G=point["G"], frozen_runtime=rt
                        )
                        == point["point_id"],
                        "stored virtual point changed",
                    )
                    cohort, rewards = base.load_feedback(point, context, bundle)
                if stage == "distribution":
                    replay = read_stage_payload(context_directory, plan, "replay_R3", rt, context)
                if stage == "train" and context["due_outer"]:
                    outer_payload = read_stage_payload(
                        context_directory, plan, "distribution", rt, context
                    )
                control.require(
                    not rt.torch.cuda.is_initialized(), "CPU source/cache reading initialized CUDA"
                )
                row = admission.wait_for_pre_cuda_admission(
                    plan,
                    stage,
                    gpu_index,
                    directory,
                    deadline_epoch,
                    rt.torch,
                    lambda: stop.requested,
                    context_id=context["id"],
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
                            schema="v38_exact_resource_observation.v1",
                            at=control.now(),
                            protocol_id=plan["id"],
                            context_id=context["id"],
                            stage=stage,
                            observation=value,
                        ),
                    )

                event.count = 0
                events = base.ResourceEvents(event, stage, stop)
                sampler = bundle.inherited.DeviceSamples(row["uuid"])
                with sampler:
                    rt.torch.cuda.reset_peak_memory_stats()  # Once, before model loading.
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
                    original = base.state_identity(bundle, model, optimizer)
                    if stage.startswith("shard"):
                        body = base.execute_shard(
                            directory, context, stage, driver, pool, cache, bundle, monitor, stop
                        )
                    elif stage == "virtual_point":
                        body = base.execute_virtual(
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
                        body = base.execute_replay(
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
                        body = base.execute_distribution(
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
                        if inherited:
                            control.require(
                                body["initial_step"] == 1192
                                and body["committed_step"] == 1193
                                and body["actual_optimizer_steps"] == 1
                                and body["outer_committed"] is True
                                and body["outer_done"] == [298, 596, 894, 1192],
                                "inherited pilot did not commit its single outer and SFT step",
                            )
                    if stage != "train":
                        control.require(
                            original == base.state_identity(bundle, model, optimizer)
                            and rt.v8._tree_digest(driver._payload())
                            == context["pre_state_digest"],
                            "cold outer stage mutated real Student/Adam/RNG/pi/prior/buffers",
                        )
                        body["model_optimizer_rng_buffers_unchanged"] = True
                    if cache is not None:
                        control.publish(
                            directory / "cache_tensor_verification/record.json",
                            dict(
                                schema="v38_actual_point_cache_verification.v1",
                                at=control.now(),
                                protocol_id=plan["id"],
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
                            schema="v38_stage_result.v1",
                            at=control.now(),
                            protocol_id=plan["id"],
                            context_id=context["id"],
                            stage=stage,
                            status="COMPLETE",
                            gpu_index=gpu_index,
                            gpu_uuid=row["uuid"],
                            inherited_context=inherited,
                            origin_context_directory=str(origin_context),
                            output_context_directory=str(context_directory),
                            elapsed_stage_seconds=time.monotonic() - started,
                            resources=resource_report,
                            model_released=True,
                            telemetry=sampler.report(),
                            torch_version=rt.torch.__version__,
                            **(defaults | body),
                        ),
                    )
            except BaseException as error:
                known_context = context if context is not None else metadata
                control.publish(
                    directory / "failure/record.json",
                    dict(
                        schema="v38_stage_failure_no_retry.v1",
                        at=control.now(),
                        protocol_id=plan["id"],
                        context_id=known_context["id"] if known_context else None,
                        stage=stage,
                        inherited_context=inherited,
                        origin_context_directory=str(origin_context),
                        output_context_directory=str(context_directory),
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
