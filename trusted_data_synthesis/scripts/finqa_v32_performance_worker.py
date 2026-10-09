"""Bounded, zero-sampling replay measurements against one completed V25 point.

This is an execution/measurement shell, not a third replay implementation. R0
uses frozen V18 and R1/R2 reuse V19 via the V32 storage adapters. It never enters
the V25 training queue, invokes a collector/scorer, or takes an optimizer step.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import fcntl
import hashlib
import importlib
import io
import json
import os
import resource
import subprocess
import threading
import time
from pathlib import Path

import finqa_v32_performance_controller as control


def dependencies():
    training = control.frozen_training_module()
    rt = training.load_runtime()
    guard = importlib.import_module("finqa_v32_same_point_guard")
    variants = importlib.import_module("finqa_v32_replay_variants")
    mechanism = importlib.import_module("trusted_synthesis.finance_research.v9_mechanism_execution")
    immutable = importlib.import_module("trusted_synthesis.core.immutable_artifacts")
    return training, rt, guard, variants, mechanism, immutable


def state_identity(rt, model, optimizer):
    return dict(
        parameters=rt.v8.parameter_digest(
            {name: value for name, value in model.named_parameters() if value.requires_grad}
        ),
        buffers=rt.v8._tree_digest(dict(model.named_buffers())),
        optimizer=rt.v8._tree_digest(optimizer.state_dict()),
        rng=rt.v8._tree_digest(rt.v8._rng()),
        training_modes=[module.training for module in model.modules()],
    )


def restore_pre_state(rt, model, optimizer, before):
    """Restore actual nonempty Adam and RNG, not the old validator's fresh Adam."""
    parameters = {n: p for n, p in model.named_parameters() if p.requires_grad}
    buffers = dict(model.named_buffers())
    control.require(set(parameters) == set(before["parameters"]), "parameter coordinates differ")
    control.require(set(buffers) == set(before["buffers"]), "buffer coordinates differ")
    with rt.torch.no_grad():
        for name, value in before["parameters"].items():
            control.require(
                parameters[name].shape == value.shape and parameters[name].dtype == value.dtype,
                "checkpoint parameter shape/dtype differs",
            )
            parameters[name].copy_(value)
        for name, value in before["buffers"].items():
            buffers[name].copy_(value)
    optimizer.load_state_dict(copy.deepcopy(before["optimizer"]))
    model.train(before["model_training"])
    rt.v8._restore_rng(before["rng"])
    observed = state_identity(rt, model, optimizer)
    control.require(
        observed["parameters"] == rt.v8.parameter_digest(before["parameters"])
        and observed["buffers"] == rt.v8._tree_digest(before["buffers"])
        and observed["optimizer"] == rt.v8._tree_digest(before["optimizer"])
        and observed["rng"] == rt.v8._tree_digest(before["rng"]),
        "actual model/Adam/RNG restore differs from source",
    )
    return parameters, observed


def compare_tensors(rt, values, gradients, reference):
    same_structure = set(gradients) == set(reference["gradient"]) and all(
        value.shape == reference["gradient"][name].shape
        and value.dtype == reference["gradient"][name].dtype
        for name, value in gradients.items()
    )
    result = dict(
        logp_digest=rt.v8._tree_digest(values.detach().cpu()),
        gradient_digest=rt.v8.parameter_digest(gradients),
        baseline_logp_digest=rt.v8._tree_digest(reference["values"]),
        baseline_gradient_digest=rt.v8.parameter_digest(reference["gradient"]),
        shape_dtype_keys_equal=same_structure,
    )
    result["bitwise_logp_equal"] = result["logp_digest"] == result["baseline_logp_digest"]
    result["bitwise_gradient_equal"] = (
        same_structure and result["gradient_digest"] == result["baseline_gradient_digest"]
    )
    return result


def cuda_resources(rt, plan):
    rt.torch.cuda.synchronize()
    free, total = rt.torch.cuda.mem_get_info()
    value = dict(
        peak_allocated_bytes=rt.torch.cuda.max_memory_allocated(),
        peak_reserved_bytes=rt.torch.cuda.max_memory_reserved(),
        device_free_bytes=free,
        device_total_bytes=total,
        thresholds_are_observed_acceptance_not_allocator_limits=True,
    )
    control.require(
        value["peak_allocated_bytes"] <= plan["allocated_memory_limit_bytes"]
        and free >= plan["free_memory_reserve_bytes"],
        "observed CUDA memory envelope exceeded",
    )
    return value


def checked_resume_boundary(root, plan):
    first = control.checked(root / "cohort_first/result/record.json")
    control.require(
        first["protocol_id"] == plan["id"]
        and first["status"] == "PAUSED_AT_REGISTERED_BOUNDARY"
        and first["pause_cursor"] == first["checkpoint"]["cursor"] == 16
        and first["replay_report"]["restored_completed_responses"] == 0,
        "registered cold pause is missing or not the first prefix",
    )
    directory = root / "cohort_replay/checkpoints/response000016"
    record = control.checked(directory / "record.json")
    control.require(
        record == first["checkpoint"]
        and control.sha(directory / "state.pt") == record["state_sha256"],
        "actual response16 H_k checkpoint missing or changed",
    )
    control.require(
        [p.name for p in sorted(directory.parent.glob("response*"))] == ["response000016"],
        "unexpected completed prefix; this trial permits only one cold resume",
    )
    return control.entry(directory / "record.json")


def save_case(directory, body, values, gradients, rt, immutable):
    payload = dict(
        values=values.detach().cpu(),
        gradient={name: value.detach().cpu() for name, value in gradients.items()},
    )
    stream = io.BytesIO()
    rt.torch.save(payload, stream)
    raw = stream.getvalue()
    body = dict(body, result_sha256=hashlib.sha256(raw).hexdigest())
    record = dict(body, id=control.digest(body))
    immutable.write_immutable_artifact_directory(
        directory,
        {
            "record.json": (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode(),
            "result.pt": raw,
        },
    )
    return record


def read_case(root, index, rt):
    directory = root / "micro_R0/cases" / f"case{index:02d}"
    record = control.checked(directory / "record.json")
    raw = (directory / "result.pt").read_bytes()
    control.require(hashlib.sha256(raw).hexdigest() == record["result_sha256"], "R0 case changed")
    return rt.torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)


class DeviceSamples:
    """One-second device telemetry: sampled maxima, never continuous true peaks."""

    def __init__(self, uuid):
        self.uuid = uuid
        self.stop = threading.Event()
        self.samples = 0
        self.max_used_mib = 0
        self.max_utilization = 0
        self.utilization_sum = 0
        self.errors = []
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self.stop.is_set():
            try:
                raw = subprocess.check_output(
                    [
                        "nvidia-smi",
                        f"--id={self.uuid}",
                        "--query-gpu=memory.used,utilization.gpu",
                        "--format=csv,noheader,nounits",
                    ],
                    text=True,
                    timeout=10,
                )
                used, utilization = (int(x.strip()) for x in raw.strip().split(","))
                self.samples += 1
                self.max_used_mib = max(self.max_used_mib, used)
                self.max_utilization = max(self.max_utilization, utilization)
                self.utilization_sum += utilization
            except Exception as exc:
                if len(self.errors) < 5:
                    self.errors.append(f"{type(exc).__name__}: {exc}")
            self.stop.wait(1.0)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.stop.set()
        self.thread.join(timeout=12)

    def report(self):
        return dict(
            sampling_interval_seconds=1,
            sample_count=self.samples,
            sampled_max_device_used_bytes=self.max_used_mib * 1024**2,
            sampled_max_GPU_utilization_percent=self.max_utilization,
            sampled_mean_GPU_utilization_percent=(
                self.utilization_sum / self.samples if self.samples else None
            ),
            process_peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            device_peak_is_sampled_not_continuous=True,
            sampler_errors=self.errors,
        )


def profiled_reference(variants, torch):
    """Add diagnostic ranges via copied globals; frozen arithmetic stays intact."""
    old = variants.optimized.legacy
    bind = variants.optimized.bind_dependencies

    def annotated(name, function):
        def call(*args, **kwargs):
            with torch.profiler.record_function(name):
                return function(*args, **kwargs)

        return call

    def model_call(model, ids, length, cache):
        label = "R0.prefill_model" if ids.shape[1] > 1 else "R0.decode_model"
        with torch.profiler.record_function(label):
            return old._call(model, ids, length, cache)

    def vjp(outputs, inputs, covectors):
        label = "R0.prefill_adjoint" if len(inputs) == 112 else "R0.block_adjoint"
        with torch.profiler.record_function(label):
            return old._vjp(outputs, inputs, covectors)

    class ProfileStore(old.CanonicalSavedTensorStore):
        def __init__(self, *args, **kwargs):
            with torch.profiler.record_function("R0.saved_tensor_store_init"):
                super().__init__(*args, **kwargs)

        def report(self):
            with torch.profiler.record_function("R0.saved_tensor_store_report"):
                return super().report()

    prefill = contextlib.contextmanager(
        bind(old.pure_prefill_checkpoints.__wrapped__, CanonicalSavedTensorStore=ProfileStore)
    )

    class ProfileOperation(old.SegmentedOperation):
        pass

    ProfileOperation.forward = bind(
        old.SegmentedOperation.forward,
        forward_saved_tokens=annotated(
            "R0.cached_forward_and_complete_KV_D2H",
            bind(old.forward_saved_tokens, _call=model_call),
        ),
        cache_from_prefix=annotated("R0.prefix_KV_H2D", old.cache_from_prefix),
        _call=model_call,
        _vjp=vjp,
        CanonicalSavedTensorStore=ProfileStore,
        FrozenLayoutBank=annotated("R0.frozen_layout_bank_init", old.FrozenLayoutBank),
        pure_prefill_checkpoints=prefill,
    )
    return bind(old.segmented_logp, SegmentedOperation=ProfileOperation)


def run_profile(root, plan, model, theta, case, receipt, index, rt, variants):
    torch = rt.torch
    from torch.nn.attention import SDPBackend, sdpa_kernel

    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    started = time.monotonic()
    with torch.profiler.profile(
        activities=[torch.profiler.ProfilerActivity.CPU, torch.profiler.ProfilerActivity.CUDA],
        record_shapes=False,
        with_stack=False,
        profile_memory=True,
    ) as profiler:
        with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
            values, gradients, _ = profiled_reference(variants, torch)(
                model,
                theta,
                list(receipt.prompt_input_ids),
                list(receipt.raw_generated_token_ids),
                expected=list(receipt.sampled_token_logprobs),
                block_size=8,
                prefill_checkpoint=True,
                offload=True,
            )
        torch.cuda.synchronize()
    elapsed = time.monotonic() - started
    memory = cuda_resources(rt, plan)
    comparison = compare_tensors(rt, values, gradients, read_case(root, index, rt))
    control.require(
        comparison["bitwise_logp_equal"] and comparison["bitwise_gradient_equal"],
        "diagnostic instrumentation changed the reference result",
    )
    trace = root / "micro_R0/profile/trace.json"
    trace.parent.mkdir(parents=True, exist_ok=True)
    control.require(not trace.exists(), "profile cannot be repeated or overwritten")
    profiler.export_chrome_trace(str(trace))
    events = []
    for event in profiler.key_averages():
        events.append(
            dict(
                name=event.key,
                count=event.count,
                self_cpu_time_us=event.self_cpu_time_total,
                total_cpu_time_us=event.cpu_time_total,
                self_device_time_us=getattr(event, "self_device_time_total", None),
                total_device_time_us=getattr(event, "device_time_total", None),
            )
        )
    return control.publish(
        root / "micro_R0/profile/record.json",
        dict(
            schema="v32_diagnostic_single_response_profile.v1",
            at=control.now(),
            protocol_id=plan["id"],
            case=case,
            profile_seconds=elapsed,
            profiler_timing_excluded_from_speedup=True,
            trace=control.file_ref(trace),
            nested_ranges_are_not_additive_exclusive_costs=True,
            record_shapes=False,
            with_stack=False,
            profile_memory=True,
            comparison=comparison,
            events=events,
            resources=memory,
        ),
    )


def session_factory(plan, variants, variant, *, monitor=None):
    if variant == "R0":

        def reference(_model, _theta):
            def call(model, theta, prompt, targets, **kwargs):
                return variants.optimized.legacy.segmented_logp(
                    model,
                    theta,
                    prompt,
                    targets,
                    prefill_checkpoint=True,
                    offload=True,
                    **kwargs,
                )

            return call

        return reference
    return lambda model, theta: variants.ReplaySession(
        model,
        theta,
        variant=variant,
        profile_id=plan["id"],
        resident_kv_budget_bytes=plan["resident_saved_KV_budget_bytes"],
        full_kv_budget_bytes=plan["full_kv_budget_bytes"],
        allocated_memory_limit_bytes=plan["allocated_memory_limit_bytes"],
        free_memory_reserve_bytes=plan["free_memory_reserve_bytes"],
        response_monitor=monitor,
    )


def execute_micro(root, stage, plan, actual, cohort, model, optimizer, rt, variants, immutable):
    from torch.nn.attention import SDPBackend, sdpa_kernel

    torch = rt.torch
    variant = stage.removeprefix("micro_")
    pause = variants.PauseRequest()
    before_original = state_identity(rt, model, optimizer)
    theta = {name: value.to("cuda:0") for name, value in actual["theta_bar"].items()}
    reports, profile_ref = [], None
    with pause.signals(), rt.v8.installed_point(model, theta) as installed:
        before = state_identity(rt, model, optimizer)
        backend = session_factory(plan, variants, variant)(model, installed)
        try:
            warm = next(case for case in plan["cases"] if case["case_id"] == plan["warmup_case_id"])
            receipt = cohort.episodes[warm["episode_index"]].turns[warm["turn_index"]].receipt
            torch.cuda.reset_peak_memory_stats()
            warm_started = time.monotonic()
            with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                values, gradient, _ = backend(
                    model,
                    installed,
                    list(receipt.prompt_input_ids),
                    list(receipt.raw_generated_token_ids),
                    expected=list(receipt.sampled_token_logprobs),
                    block_size=8,
                )
            del values, gradient
            torch.cuda.synchronize()
            warm_resources = cuda_resources(rt, plan)
            warm_seconds = time.monotonic() - warm_started
            control.require(before == state_identity(rt, model, optimizer), "warmup mutated state")
            for index, case in enumerate(plan["cases"]):
                control.require(not pause.requested, "micro stage paused; no automatic retry")
                receipt = cohort.episodes[case["episode_index"]].turns[case["turn_index"]].receipt
                control.require(
                    control.digest(receipt.model_dump(mode="json")) == case["receipt_sha256"],
                    "registered response identity changed",
                )
                torch.cuda.reset_peak_memory_stats()
                torch.cuda.synchronize()
                started = time.monotonic()
                with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                    values, gradient, accounting = backend(
                        model,
                        installed,
                        list(receipt.prompt_input_ids),
                        list(receipt.raw_generated_token_ids),
                        expected=list(receipt.sampled_token_logprobs),
                        block_size=8,
                    )
                torch.cuda.synchronize()
                elapsed = time.monotonic() - started
                memory = cuda_resources(rt, plan)
                allocated = memory["peak_allocated_bytes"]
                reserved = memory["peak_reserved_bytes"]
                reference = (
                    dict(
                        values=values.detach().cpu(),
                        gradient={name: value.detach().cpu() for name, value in gradient.items()},
                    )
                    if variant == "R0"
                    else read_case(root, index, rt)
                )
                compared = compare_tensors(rt, values, gradient, reference)
                unchanged = before == state_identity(rt, model, optimizer)
                result = save_case(
                    root / stage / "cases" / f"case{index:02d}",
                    dict(
                        schema="v32_paired_existing_response.v1",
                        at=control.now(),
                        protocol_id=plan["id"],
                        variant=variant,
                        case_id=case["case_id"],
                        response_index=case["response_index"],
                        seconds=elapsed,
                        peak_allocated_bytes=allocated,
                        peak_reserved_bytes=reserved,
                        state_unchanged=unchanged,
                        storage_accounting=accounting,
                        resource_envelope=memory,
                        **compared,
                    ),
                    values,
                    gradient,
                    rt,
                    immutable,
                )
                reports.append(result)
                del values, gradient, reference
                control.require(
                    compared["bitwise_logp_equal"]
                    and compared["bitwise_gradient_equal"]
                    and compared["shape_dtype_keys_equal"]
                    and unchanged
                    and allocated <= plan["allocated_memory_limit_bytes"]
                    and accounting["complete_prefix_adjoint_included"] is True
                    and accounting["sampling_calls"] == 0,
                    "per-response numeric/state/resource gate failed; no fallback",
                )
            if variant == "R0":
                control.require(not pause.requested, "pause before diagnostic profiling")
                index = next(
                    i
                    for i, row in enumerate(plan["cases"])
                    if row["case_id"] == plan["profile_case_id"]
                )
                case = plan["cases"][index]
                receipt = cohort.episodes[case["episode_index"]].turns[case["turn_index"]].receipt
                profile = run_profile(
                    root, plan, model, installed, case, receipt, index, rt, variants
                )
                profile_ref = dict(path=str(root / stage / "profile/record.json"), id=profile["id"])
            control.require(before == state_identity(rt, model, optimizer), "micro state changed")
        finally:
            if hasattr(backend, "close"):
                backend.close(aborted=not len(reports) == len(plan["cases"]))
    control.require(
        before_original == state_identity(rt, model, optimizer), "point restore changed state"
    )
    return dict(
        status="COMPLETE",
        numeric_pass=True,
        variant=variant,
        unprofiled_seconds=sum(row["seconds"] for row in reports),
        case_count=len(reports),
        case_results=reports,
        warmup_responses=1,
        warmup_seconds=warm_seconds,
        warmup_resources=warm_resources,
        profile_responses=int(variant == "R0"),
        diagnostic_profile=profile_ref,
        model_optimizer_rng_buffers_unchanged=True,
        sampling_atol=1e-6,
        sampling_rtol=1e-5,
        inherited_bitwise_logp_and_all_gradient_contract=True,
    )


def execute_cohort(
    root, stage, plan, actual, cohort, rewards, model, optimizer, training, rt, variants, guard
):
    selected = control.checked(root / "selection/record.json")
    control.require(selected["protocol_id"] == plan["id"], "selection belongs to another trial")
    variant = selected["selected_variant"]
    control.require(variant in ("R1", "R2"), "only an admitted candidate can replay full cohort")
    pause = variants.PauseRequest()
    original = state_identity(rt, model, optimizer)
    theta = {name: value.to("cuda:0") for name, value in actual["theta_bar"].items()}
    checkpoint_root = root / "cohort_replay/checkpoints"
    resume_boundary = checked_resume_boundary(root, plan) if stage == "cohort_resume" else None
    if stage == "cohort_first":
        control.require(
            not list(checkpoint_root.glob("response*")), "first cohort prefix already exists"
        )
    backend_identity = dict(
        protocol_id=plan["id"],
        variant=variant,
        version=variants.BACKEND_VERSION,
        adapter_source=control.file_ref(Path(variants.__file__)),
        inherited_V19_source=control.file_ref(Path(variants.optimized.__file__)),
    )
    rng_source = dict(
        outer_inputs=plan["source_outer"]["outer_inputs"],
        field="pre_state.rng",
        digest=rt.v8._tree_digest(actual["pre_state"]["rng"]),
    )
    events = []

    def event(value):
        if value.get("event") == "feedback_checkpoint_committed":
            events.append(value)

    with pause.signals():
        rt.torch.cuda.reset_peak_memory_stats()
        rt.torch.cuda.synchronize()
        replay_started = time.monotonic()
        try:
            with rt.v8.installed_point(model, theta) as installed:
                gJ, report = variants.feedback_gradient(
                    cohort,
                    rewards,
                    model,
                    installed,
                    root=checkpoint_root,
                    profile_id=plan["id"],
                    backend_factory=session_factory(plan, variants, variant),
                    backend_identity=backend_identity,
                    rng_restore_source=rng_source,
                    pause_request=pause,
                    pause_after_response=(
                        plan["pause_after_response"] if stage == "cohort_first" else None
                    ),
                    checkpoint_every=16,
                    event_sink=event,
                )
        except variants.ReplayPaused as stopped:
            rt.torch.cuda.synchronize()
            replay_elapsed = time.monotonic() - replay_started
            control.require(original == state_identity(rt, model, optimizer), "pause changed state")
            fixed = (
                stage == "cohort_first"
                and stopped.checkpoint_record["cursor"] == 16
                and stopped.report["restored_completed_responses"] == 0
                and not pause.requested
            )
            return dict(
                status="PAUSED_AT_REGISTERED_BOUNDARY" if fixed else "PAUSED_ON_REQUEST",
                numeric_pass=fixed,
                pause_cursor=stopped.checkpoint_record["cursor"],
                checkpoint=stopped.checkpoint_record,
                replay_report=stopped.report,
                checkpoint_events=events,
                full_cohort_validation_complete=False,
                replay_wall_seconds_this_process=replay_elapsed,
                replay_clock_includes_point_context_and_checkpoint_writes=True,
                resources_replay=cuda_resources(rt, plan),
                model_optimizer_rng_buffers_unchanged=True,
                selected_variant=variant,
            )
        control.require(stage == "cohort_resume", "registered pause was not executed")
        rt.torch.cuda.synchronize()
        replay_elapsed = time.monotonic() - replay_started
        control.require(
            report["restored_completed_responses"] == 16,
            "cohort must restore the actual sixteen-response prefix, never replay from zero",
        )
        replay_resources = cuda_resources(rt, plan)
        control.require(original == state_identity(rt, model, optimizer), "cohort mutated state")
        control.require(
            rt.v8.parameter_digest(gJ) == rt.v8.parameter_digest(actual["gJ"]),
            "full accumulated gJ differs from saved reference; no numerical retry",
        )
        control.require(not pause.requested, "paused before independent C validation")
        # The saved outer contains aggregate G, not the 1360 class gradients.
        # Exactly one original class pass is explicitly charged to this trial.
        _, pool, _, _ = training.checked_launch(training.DEFAULT_ROOT)
        parameters = {n: p for n, p in model.named_parameters() if p.requires_grad}
        started = time.monotonic()
        gradients = rt.v8.class_gradients(model, pool, device="cuda:0")
        prepared = rt.v8.prepare_virtual_point(
            parameters, optimizer, gradients, actual["pre_state"]["pi"], actual["mu"]
        )
        rt.torch.cuda.synchronize()
        class_seconds = time.monotonic() - started
        control.require(not pause.requested, "pause requested during independent C validation")
        point = guard.recompute_point_id(
            actual["pre_state"], theta_bar=prepared["theta_bar"], G=prepared["G"], frozen_runtime=rt
        )
        manifest = control.read_ref(plan["benchmark_manifest"])
        guard.check_recomputed_point(manifest, point)
        control.require(
            rt.v8.parameter_digest(prepared["G"]) == rt.v8.parameter_digest(actual["G"])
            and rt.v8.parameter_digest(prepared["theta_bar"])
            == rt.v8.parameter_digest(actual["theta_bar"]),
            "original class-G or virtual point changed; no new sampling allowed",
        )
        before = actual["pre_state"]
        result = rt.v8.update_distribution(
            prepared,
            gradients,
            gJ,
            before["pi"],
            before["prior"],
            actual["mu"],
            feedback_report=report,
            contribution_only=True,
            control_tasks=[task for task, values in before["prior"].items() if len(values) == 1],
            **rt.v8.PARAMETERS,
        )
        comparison = dict(
            gJ_bitwise_equal=True,
            aggregate_G_bitwise_equal=True,
            theta_bar_bitwise_equal=True,
            point_id_equal=point == actual["point_id"],
            pullback_bitwise_equal=(
                rt.v8.parameter_digest(result["a"]) == rt.v8.parameter_digest(actual["pullback"])
            ),
            C_equal=result["C"] == actual["C"],
            pi_equal=result["distribution"]["pi_next"] == actual["q_next"],
            model_optimizer_rng_buffers_unchanged=original == state_identity(rt, model, optimizer),
        )
        control.require(all(comparison.values()), "full cohort numerical comparison failed")
        final_resources = cuda_resources(rt, plan)
        prefix_result = control.checked(root / "cohort_first/result/record.json")
        return dict(
            status="COMPLETE",
            numeric_pass=True,
            selected_variant=variant,
            full_cohort_validation_complete=True,
            comparison=comparison,
            replay_report=report,
            replay_wall_seconds_this_process=replay_elapsed,
            replay_wall_seconds_both_processes=(
                replay_elapsed + prefix_result["replay_wall_seconds_this_process"]
            ),
            replay_clock_includes_point_context_and_checkpoint_writes=True,
            checkpoint_events=events,
            class_gradient_passes=1,
            class_gradient_and_virtual_point_seconds=class_seconds,
            restored_boundary=resume_boundary,
            restored_completed_responses=16,
            resources_replay=replay_resources,
            resources_including_class_pass=final_resources,
            original_reference_full700_reruns=0,
            pause_resume_verified=True,
            performance_validation_not_B_scientific_budget=True,
        )


def run(root, stage, gpu_index):
    root = Path(root).resolve()
    plan = control.checked_protocol(root)
    control.require(
        Path(__file__).resolve() == root / "implementation" / Path(__file__).name,
        "only committed frozen worker may run",
    )
    control.require(
        stage in {"micro_R0", "micro_R1", "micro_R2", "cohort_first", "cohort_resume"},
        "unregistered stage",
    )
    directory = root / stage
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        control.require(
            not (directory / "attempt/record.json").exists(), "stage cannot automatically repeat"
        )
        training, rt, guard, variants, mechanism, immutable = dependencies()
        control.require(not rt.torch.cuda.is_initialized(), "fresh CPU-only admission required")
        row = next((row for row in control.inventory() if row["index"] == gpu_index), None)
        control.require(
            row is not None and control.eligible(row, plan), "GPU not idle or not admitted"
        )
        control.require(
            row["uuid"] == plan["gpu_uuids"][str(gpu_index)], "physical GPU UUID changed"
        )
        os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        started = time.monotonic()
        control.publish(
            directory / "attempt/record.json",
            dict(
                schema="v32_performance_worker_attempt.v1",
                at=control.now(),
                protocol_id=plan["id"],
                stage=stage,
                pid=os.getpid(),
                gpu_index=gpu_index,
                gpu_uuid=row["uuid"],
                original_B_resume_authorized=False,
                API_calls=0,
                new_sampling_calls=0,
                scoring_calls=0,
                optimizer_steps=0,
            ),
        )
        sampler = DeviceSamples(row["uuid"])
        with sampler:
            try:
                outer_record, _, actual = mechanism.checked_outer(plan["source_outer"]["path"])
                control.require(
                    outer_record["outer_inputs_sha256"]
                    == plan["source_outer"]["outer_inputs"]["sha256"]
                    and outer_record["state_sha256"] == plan["source_outer"]["state"]["sha256"],
                    "source outer differs from registered tensors",
                )
                manifest = control.read_ref(plan["benchmark_manifest"])
                point = guard.recompute_point_id(
                    actual["pre_state"],
                    theta_bar=actual["theta_bar"],
                    G=actual["G"],
                    frozen_runtime=rt,
                )
                guard.check_recomputed_point(manifest, point)
                cohort, rewards = guard.read_sealed_feedback(manifest, frozen_runtime=rt)
                control.require(
                    list(rewards) == actual["rewards"]
                    and cohort.seal_sha256 == actual["feedback_seal"]["seal_sha256"],
                    "saved rewards/cohort changed",
                )
                science = training.checked_plan(training.DEFAULT_ROOT)
                assets = rt.launcher.read_bound(science["assets_protocol"]["path"])
                model, _tokenizer, optimizer, _scope, _fresh = rt.launcher._load_components(
                    assets, 137
                )
                control.require(
                    rt.v8.validate_student_adapters(model, _scope)
                    == actual["pre_state"]["adapter_binding"]
                    and rt.v8.parameter_digest(
                        {n: p for n, p in model.named_parameters() if not p.requires_grad}
                    )
                    == actual["pre_state"]["frozen_base_digest"],
                    "actual frozen base or adapter binding differs from saved point",
                )
                restore_pre_state(rt, model, optimizer, actual["pre_state"])
                if stage.startswith("micro_"):
                    result = execute_micro(
                        root, stage, plan, actual, cohort, model, optimizer, rt, variants, immutable
                    )
                else:
                    result = execute_cohort(
                        root,
                        stage,
                        plan,
                        actual,
                        cohort,
                        rewards,
                        model,
                        optimizer,
                        training,
                        rt,
                        variants,
                        guard,
                    )
                return control.publish(
                    directory / "result/record.json",
                    dict(
                        schema="v32_performance_stage_result.v1",
                        at=control.now(),
                        protocol_id=plan["id"],
                        stage=stage,
                        gpu_index=gpu_index,
                        gpu_uuid=row["uuid"],
                        elapsed_stage_seconds=time.monotonic() - started,
                        resources=sampler.report(),
                        torch_version=rt.torch.__version__,
                        API_calls=0,
                        new_sampling_calls=0,
                        scoring_calls=0,
                        optimizer_steps=0,
                        original_B_resume_authorized=False,
                        **result,
                    ),
                )
            except BaseException as exc:
                control.publish(
                    directory / "failure/record.json",
                    dict(
                        schema="v32_bounded_performance_failure.v1",
                        at=control.now(),
                        protocol_id=plan["id"],
                        stage=stage,
                        error_type=type(exc).__name__,
                        error=str(exc),
                        resources=sampler.report(),
                        automatic_retry=False,
                        new_sampling_calls=0,
                        scoring_calls=0,
                        optimizer_steps=0,
                        API_calls=0,
                        original_B_still_paused=True,
                    ),
                )
                raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--gpu-index", type=int, required=True)
    args = parser.parse_args()
    result = run(args.root, args.stage, args.gpu_index)
    print(json.dumps(dict(status=result["status"], id=result["id"]), ensure_ascii=False))
