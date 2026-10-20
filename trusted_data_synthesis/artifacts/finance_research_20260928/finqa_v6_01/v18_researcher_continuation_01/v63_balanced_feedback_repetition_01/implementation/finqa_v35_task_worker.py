"""Complete-task class gradients and one global, no-replay V35 validation.

Shards execute the sealed class kernel only on whole tasks.  The coordinator
never enters that kernel: it assembles committed CPU tensors in original order
and uses the actual V33 response573 accumulator, not the reference gJ, as input.
"""

from __future__ import annotations

import argparse
import fcntl
import gc
import importlib
import json
import os
import resource
import time
from pathlib import Path

import finqa_v35_task_controller as control

GIB = 1024**3
STAGE_GPUS = {"shard00": 3, "shard01": 4, "shard02": 5, "shard03": 7, "coordinator": 7}
ZERO_COUNTERS = dict(
    API_calls=0,
    new_sampling_calls=0,
    scoring_calls=0,
    optimizer_steps=0,
    replayed_responses=0,
    original_B_resume_authorized=False,
)


def dependencies(root):
    tail = control.frozen_tail_worker(root)
    values = tail.dependencies()
    # Its first import may consume Python RNG before the class kernel's own
    # save/restore scope. Complete this dependency load BEFORE restoring the
    # real pre-state; never hide a mutation after class calculation.
    importlib.import_module(
        "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.trajectory_consumer"
    )
    cache_module = importlib.import_module("finqa_v35_task_cache")
    for module in (tail, values[2], values[3], values[5], cache_module):
        source = Path(module.__file__).resolve()
        control.require(
            source == Path(root).resolve() / "implementation" / source.name,
            "worker dependency is outside the sealed V35 implementation",
        )
    return tail, cache_module, values


def host_memory():
    """Linux RSS high water and machine available RAM; no CUDA or allocations."""
    status = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in {"VmRSS", "VmHWM"}:
            status[key] = int(value.split()[0]) * 1024
    available = None
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            available = int(line.split()[1]) * 1024
            break
    control.require(available is not None, "Linux MemAvailable is required")
    return dict(
        rss_bytes=status["VmRSS"],
        peak_rss_bytes=max(
            status["VmHWM"], int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
        ),
        available_bytes=available,
    )


class ResourceEvents:
    """Enrich unchanged V34 GPU events with host checks, persisting before fail."""

    def __init__(self, sink, *, stage, deadline_epoch, stop, read_host=host_memory):
        self.sink, self.stage, self.stop = sink, stage, stop
        self.deadline_epoch, self.read_host = deadline_epoch, read_host
        self.host_limit = (192 if stage == "coordinator" else 160) * GIB
        self.observations = []

    def stopped(self):
        return self.stop.requested or time.time() >= self.deadline_epoch

    def __call__(self, gpu):
        host = self.read_host()
        host.update(rss_limit_bytes=self.host_limit, available_reserve_bytes=96 * GIB)
        host["rss_pass"] = host["peak_rss_bytes"] <= self.host_limit
        host["available_pass"] = host["available_bytes"] >= 96 * GIB
        host["passed"] = host["rss_pass"] and host["available_pass"]
        event = dict(
            gpu,
            host=host,
            deadline_epoch=self.deadline_epoch,
            deadline_pass=time.time() < self.deadline_epoch,
        )
        event["passed"] = bool(gpu["passed"] and host["passed"] and event["deadline_pass"])
        self.observations.append(event)
        self.sink(event)
        control.require(host["passed"], "V35 host RAM envelope failed")
        control.require(event["deadline_pass"], "V35 shared global deadline reached")

    def report(self):
        return dict(
            rss_limit_bytes=self.host_limit,
            available_reserve_bytes=96 * GIB,
            max_observed_peak_rss_bytes=max(
                (r["host"]["peak_rss_bytes"] for r in self.observations), default=None
            ),
            min_observed_available_bytes=min(
                (r["host"]["available_bytes"] for r in self.observations), default=None
            ),
            all_passed=bool(self.observations) and all(r["passed"] for r in self.observations),
        )


def state_identity(rt, model, optimizer, inherited):
    """Actual state plus already-existing .grad, and frozen parameter versions.

    Trainable values/Adam/RNG/buffers/modes use the original digest helper.
    Frozen parameter storage/version checks avoid re-hashing the entire base
    model after every task; its initial bytes were checked at model loading.
    """
    result = inherited.state_identity(rt, model, optimizer)
    result["existing_parameter_gradients"] = rt.v8._tree_digest(
        {name: p.grad for name, p in model.named_parameters()}
    )
    result["frozen_parameter_storage_versions"] = rt.v8._tree_digest(
        [
            (
                name,
                p._version,
                p.untyped_storage()._cdata,
                tuple(p.shape),
                tuple(p.stride()),
                p.storage_offset(),
            )
            for name, p in model.named_parameters()
            if not p.requires_grad
        ]
    )
    return result


def resources(monitor, events, plan, tail):
    report = tail.accepted_resources(monitor, plan)
    host = events.report()
    return dict(
        report,
        host=host,
        observations=list(events.observations),
        all_gates_passed=report["all_gates_passed"] and host["all_passed"],
        single_process_lifetime_includes_loading=True,
    )


def execute_shard(
    directory,
    plan,
    task_plan,
    stage,
    pool,
    cache,
    model,
    optimizer,
    rt,
    inherited,
    memory,
    monitor,
    stop,
    cache_module,
):
    shard = int(stage[-2:])
    assignment = next(a for a in task_plan["assignments"] if a["shard"] == shard)
    task_ids = assignment["task_ids"]
    completed, reused, row_count = [], [], 0
    original = state_identity(rt, model, optimizer, inherited)
    started = time.monotonic()
    for task_id in task_ids:
        monitor.check_stop("task_start", task_id=task_id)
        if cache.has(task_id):
            # Identity, tensor bytes, coordinates and finite values are checked
            # by has. No class computation occurs for a committed task.
            reused.append(task_id)
        else:
            task_pool = cache_module.TaskPoolView(pool, [task_id])
            monitor.clear_unused("before_task_class_gradients")
            before = state_identity(rt, model, optimizer, inherited)
            values, receipt = memory.class_gradients_with_cpu_saves(
                rt, model, task_pool, device="cuda:0", monitor=monitor
            )
            rt.torch.cuda.synchronize()
            control.require(list(values) == [task_id], "class kernel returned wrong task")
            after = state_identity(rt, model, optimizer, inherited)
            control.require(
                before == after == original,
                "task changed parameters/Adam/RNG/buffers/modes/existing .grad",
            )
            monitor.clear_unused("task_class_gradients_complete")
            monitor.check_stop("before_task_commit", task_id=task_id)
            control.require(not stop.requested, "stop requested before task commit")
            cpu_values = values[task_id].values_cpu
            cache.commit(
                task_id,
                cpu_values,
                receipt=dict(
                    storage=receipt,
                    state_unchanged=True,
                    pre_state_identity=before,
                    post_state_identity=after,
                    stage=stage,
                    original_class_bytecode_unchanged=True,
                    **ZERO_COUNTERS,
                ),
            )
            row_count += receipt["rows_completed"]
            del values, cpu_values
        completed.append(task_id)
        control.status(
            directory,
            dict(
                phase="TASKS_RUNNING",
                stage=stage,
                protocol_id=plan["id"],
                committed_task_ids=completed,
                committed_task_count=len(completed),
                assigned_task_count=len(task_ids),
                reused_task_ids=reused,
                new_completed_rows=row_count,
                row_count_is_not_a_checkpoint=True,
            ),
        )
    control.require(
        original == state_identity(rt, model, optimizer, inherited), "shard changed source state"
    )
    monitor.clear_unused("shard_complete")
    return dict(
        status="COMPLETE",
        task_ids=completed,
        task_count=len(completed),
        complete_task_count=len(completed),
        reused_task_ids=reused,
        class_task_calls=len(completed) - len(reused),
        new_completed_rows=row_count,
        task_gradient_seconds=time.monotonic() - started,
        whole_task_cpu_gradient_checkpoints=True,
        model_optimizer_rng_buffers_existing_grad_unchanged=True,
        class_gradient_passes=0,
        global_class_gradient_pass_contribution=True,
        **ZERO_COUNTERS,
    )


def execute_coordinator(
    directory,
    plan,
    actual,
    gradient,
    feedback_report,
    cache,
    model,
    optimizer,
    rt,
    inherited,
    guard,
    monitor,
    stop,
    immutable,
    tail,
    assembled_gradients=None,
):
    """Exactly one prepare/update pair on all task tensors; no class kernel."""
    original = state_identity(rt, model, optimizer, inherited)
    # assemble() validates every complete tensor payload before returning, and
    # rejects missing tasks; no separate full-cache coverage read is needed.
    gradients = (
        cache.assemble(device="cuda:0") if assembled_gradients is None else assembled_gradients
    )
    parameters = {n: p for n, p in model.named_parameters() if p.requires_grad}
    gJ = {name: value.to(parameters[name].device) for name, value in gradient.items()}
    control.require(
        rt.v8.parameter_digest(gJ) == plan["saved_gJ_digest"], "saved gJ transfer changed values"
    )
    monitor.clear_unused("coordinator_before_prepare")
    prepared = rt.v8.prepare_virtual_point(
        parameters, optimizer, gradients, actual["pre_state"]["pi"], actual["mu"]
    )
    point = guard.recompute_point_id(
        actual["pre_state"], theta_bar=prepared["theta_bar"], G=prepared["G"], frozen_runtime=rt
    )
    point_comparison = dict(
        gJ_bitwise_equal=rt.v8.parameter_digest(gJ) == rt.v8.parameter_digest(actual["gJ"]),
        aggregate_G_bitwise_equal=rt.v8.parameter_digest(prepared["G"])
        == rt.v8.parameter_digest(actual["G"]),
        theta_bar_bitwise_equal=rt.v8.parameter_digest(prepared["theta_bar"])
        == rt.v8.parameter_digest(actual["theta_bar"]),
        point_id_equal=point == actual["point_id"],
    )
    control.publish(
        directory / "point_comparison/record.json",
        dict(
            schema="v35_task_cache_recomputed_point.v1",
            at=control.now(),
            protocol_id=plan["id"],
            comparison=point_comparison,
            assembled_task_count=len(gradients),
            class_gradient_passes=0,
        ),
    )
    control.require(
        all(point_comparison.values()),
        "class G or actual virtual point differs; no distribution update",
    )
    # Global distribution math is admitted only at the original complete
    # virtual point and after its unchanged resource boundary has passed.
    monitor.clear_unused("virtual_point_complete")
    control.require(not stop.requested, "stopped before coordinator distribution")
    before = actual["pre_state"]
    started = time.monotonic()
    result = rt.v8.update_distribution(
        prepared,
        gradients,
        gJ,
        before["pi"],
        before["prior"],
        actual["mu"],
        feedback_report=feedback_report,
        contribution_only=True,
        control_tasks=[task for task, values in before["prior"].items() if len(values) == 1],
        **rt.v8.PARAMETERS,
    )
    rt.torch.cuda.synchronize()
    comparison = dict(
        **point_comparison,
        pullback_bitwise_equal=rt.v8.parameter_digest(result["a"])
        == rt.v8.parameter_digest(actual["pullback"]),
        C_equal=result["C"] == actual["C"],
        pi_equal=result["distribution"]["pi_next"] == actual["q_next"],
        model_optimizer_rng_buffers_unchanged=original
        == state_identity(rt, model, optimizer, inherited),
    )
    # The inherited writer saves real G/theta/a/C/pi tensors before the final
    # resource gate. Its historical schema is provenance, not a V34 re-run.
    numeric = tail.save_numerical_evidence(
        directory, rt, immutable, plan, result, prepared, comparison, feedback_report
    )
    control.require(all(comparison.values()), "independent global numerical comparison failed")
    monitor.clear_unused("after_distribution")
    control.require(not stop.requested, "stopped after coordinator distribution")
    return dict(
        status="COMPLETE",
        numeric_pass=True,
        comparison=comparison,
        class_gradient_passes=0,
        global_class_gradient_passes=1,
        assembled_task_count=len(gradients),
        task_count=len(gradients),
        state_count=sum(len(states) for states in gradients.values()),
        distribution_seconds=time.monotonic() - started,
        reused_completed_responses=573,
        saved_gJ_digest=plan["saved_gJ_digest"],
        numeric_comparison=control.entry(directory / "numeric_comparison/record.json"),
        numeric_record_id=numeric["id"],
        original_V33_failure_reclassified=False,
        original_V34_failure_reclassified=False,
        task_supplement_only=True,
        **ZERO_COUNTERS,
    )


def checked_sources(root, plan, task_plan, training, rt, guard, mechanism, cache_module):
    outer_record, _, actual = mechanism.checked_outer(plan["source_outer"]["path"])
    control.require(
        outer_record["outer_inputs_sha256"] == plan["source_outer"]["outer_inputs"]["sha256"]
        and outer_record["state_sha256"] == plan["source_outer"]["state"]["sha256"],
        "actual source outer differs",
    )
    manifest = control.read_ref(plan["benchmark_manifest"])
    point = guard.recompute_point_id(
        actual["pre_state"], theta_bar=actual["theta_bar"], G=actual["G"], frozen_runtime=rt
    )
    guard.check_recomputed_point(manifest, point)
    cohort, rewards = guard.read_sealed_feedback(manifest, frozen_runtime=rt)
    control.require(
        list(rewards) == actual["rewards"]
        and cohort.seal_sha256 == actual["feedback_seal"]["seal_sha256"],
        "sealed feedback differs",
    )
    binding = plan["task_binding"]
    control.require(
        binding["pre_state_digest"] == rt.v8._tree_digest(actual["pre_state"])
        and binding["point_id"] == actual["point_id"] == point
        and binding["task_plan_id"] == task_plan["id"],
        "task cache source binding differs",
    )
    _, pool, _, _ = training.checked_launch(training.DEFAULT_ROOT)
    parameters = actual["pre_state"]["parameters"]
    spec = [dict(name=n, shape=list(p.shape), dtype=str(p.dtype)) for n, p in parameters.items()]
    control.require(spec == task_plan["parameter_spec"], "actual parameter order/spec differs")
    # Reconstruct the pure-CPU plan once at admission. This validates complete
    # task/package/row identities, full denominators and global registration.
    rebuilt = cache_module.make_task_plan(pool, spec, shards=4)
    control.require(rebuilt == task_plan, "actual source material/task partition differs")
    control.require(
        Path(plan["task_cache_root"]).resolve() == root / "task_cache",
        "task cache must remain in the new V35 directory",
    )
    cache = cache_module.TaskCache(root / "task_cache", binding, task_plan, spec, rt)
    return actual, pool, cache


def run(root, stage, gpu_index, deadline_epoch):
    root = Path(root).resolve()
    plan = control.checked_protocol(root)
    control.require(
        Path(__file__).resolve() == root / "implementation" / Path(__file__).name,
        "only the sealed V35 worker may run",
    )
    control.require(
        stage in STAGE_GPUS and gpu_index == STAGE_GPUS[stage], "unregistered stage/GPU"
    )
    window = control.checked(root / "execution_window/record.json")
    control.require(
        deadline_epoch == window["deadline_epoch"]
        and window["protocol_id"] == plan["id"]
        and time.time() < deadline_epoch,
        "shared execution deadline differs or expired",
    )
    directory = root / stage
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        control.require(not (directory / "attempt/record.json").exists(), "one stage attempt only")
        tail, cache_module, values = dependencies(root)
        training, rt, inherited, guard, PauseRequest, memory, mechanism, immutable = values
        control.require(not rt.torch.cuda.is_initialized(), "fresh CPU-only entry required")
        stop, monitor, events, sampler = PauseRequest(), None, None, None
        started = time.monotonic()
        control.publish(
            directory / "attempt/record.json",
            dict(
                schema="v35_task_stage_attempt.v1",
                at=control.now(),
                protocol_id=plan["id"],
                stage=stage,
                pid=os.getpid(),
                gpu_index=gpu_index,
                deadline_epoch=deadline_epoch,
                automatic_retry=False,
                **ZERO_COUNTERS,
            ),
        )

        def publish_event(value):
            number = publish_event.count
            publish_event.count += 1
            control.publish(
                directory / "resources" / f"event{number:06d}" / "record.json",
                dict(
                    schema="v35_exact_resource_observation.v1",
                    at=control.now(),
                    protocol_id=plan["id"],
                    stage=stage,
                    observation=value,
                ),
            )

        publish_event.count = 0
        with stop.signals():
            try:
                task_plan = control.read_ref(plan["task_plan"])
                actual, pool, cache = checked_sources(
                    root, plan, task_plan, training, rt, guard, mechanism, cache_module
                )
                gradient = feedback_report = assembled_gradients = None
                if stage == "coordinator":
                    gradient, feedback_report = tail.load_saved_gradient(plan, rt, actual)
                    # All tensors stay CPU-backed: _DeviceGradients transfers
                    # only when the original global kernel accesses a state.
                    assembled_gradients = cache.assemble(device="cuda:0")
                    control.require(
                        list(assembled_gradients) == task_plan["task_ids"],
                        "all original tasks required before CUDA",
                    )
                control.require(
                    not rt.torch.cuda.is_initialized(), "source reading created CUDA context"
                )
                control.verify_original_B_paused(plan)
                row = next((r for r in control.inventory() if r["index"] == gpu_index), None)
                control.require(
                    row is not None
                    and control.eligible(row, plan)
                    and row["uuid"] == plan["gpu_uuids"][str(gpu_index)],
                    "registered GPU is not fully idle or UUID changed",
                )
                events = ResourceEvents(
                    publish_event, stage=stage, deadline_epoch=deadline_epoch, stop=stop
                )
                control.require(not events.stopped(), "stopped before CUDA admission")
                host = host_memory()
                control.require(
                    host["peak_rss_bytes"] <= events.host_limit
                    and host["available_bytes"] >= 96 * GIB,
                    "host admission failed",
                )
                os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
                os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
                sampler = inherited.DeviceSamples(row["uuid"])
                with sampler:
                    rt.torch.cuda.reset_peak_memory_stats()
                    monitor = memory.TailMemoryMonitor(
                        rt.torch, event_sink=events, stop_requested=events.stopped
                    )
                    monitor.snapshot("before_model_load", boundary=True)
                    science = training.checked_plan(training.DEFAULT_ROOT)
                    assets = rt.launcher.read_bound(science["assets_protocol"]["path"])
                    model, _tokenizer, optimizer, scope, _fresh = rt.launcher._load_components(
                        assets, 137
                    )
                    control.require(
                        rt.v8.validate_student_adapters(model, scope)
                        == actual["pre_state"]["adapter_binding"]
                        and rt.v8.parameter_digest(
                            {n: p for n, p in model.named_parameters() if not p.requires_grad}
                        )
                        == actual["pre_state"]["frozen_base_digest"],
                        "actual model/adapter binding differs",
                    )
                    inherited.restore_pre_state(rt, model, optimizer, actual["pre_state"])
                    monitor.clear_unused("after_model_load")
                    if stage == "coordinator":
                        body = execute_coordinator(
                            directory,
                            plan,
                            actual,
                            gradient,
                            feedback_report,
                            cache,
                            model,
                            optimizer,
                            rt,
                            inherited,
                            guard,
                            monitor,
                            stop,
                            immutable,
                            tail,
                            assembled_gradients=assembled_gradients,
                        )
                    else:
                        body = execute_shard(
                            directory,
                            plan,
                            task_plan,
                            stage,
                            pool,
                            cache,
                            model,
                            optimizer,
                            rt,
                            inherited,
                            memory,
                            monitor,
                            stop,
                            cache_module,
                        )
                    del model, optimizer, _tokenizer, _fresh
                    gc.collect()
                    monitor.clear_unused("model_released")
                    body["resources"] = resources(monitor, events, plan, tail)
                    control.require(
                        body["resources"]["all_gates_passed"], "final combined resource gate failed"
                    )
                    return control.publish(
                        directory / "result/record.json",
                        dict(
                            schema="v35_task_stage_result.v1",
                            at=control.now(),
                            protocol_id=plan["id"],
                            stage=stage,
                            gpu_index=gpu_index,
                            gpu_uuid=row["uuid"],
                            elapsed_stage_seconds=time.monotonic() - started,
                            telemetry=sampler.report(),
                            torch_version=rt.torch.__version__,
                            backend_version=memory.BACKEND_VERSION,
                            model_released=True,
                            **body,
                        ),
                    )
            except BaseException as exc:
                control.publish(
                    directory / "failure/record.json",
                    dict(
                        schema="v35_task_stage_failure_no_retry.v1",
                        at=control.now(),
                        protocol_id=plan["id"],
                        stage=stage,
                        error_type=type(exc).__name__,
                        error=str(exc),
                        resources=monitor.report() if monitor is not None else None,
                        host_resources=events.report() if events is not None else None,
                        telemetry=sampler.report() if sampler is not None else None,
                        numeric_comparison=(
                            control.entry(directory / "numeric_comparison/record.json")
                            if (directory / "numeric_comparison/record.json").exists()
                            else None
                        ),
                        completed_task_caches_preserved=True,
                        current_uncommitted_task_not_checkpoint=True,
                        automatic_retry=False,
                        variant_fallback=False,
                        **ZERO_COUNTERS,
                    ),
                )
                raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--stage", choices=tuple(STAGE_GPUS), required=True)
    parser.add_argument("--gpu-index", type=int, required=True)
    parser.add_argument("--deadline-epoch", type=float, required=True)
    args = parser.parse_args()
    result = run(args.root, args.stage, args.gpu_index, args.deadline_epoch)
    print(json.dumps(dict(status=result["status"], id=result["id"])))
