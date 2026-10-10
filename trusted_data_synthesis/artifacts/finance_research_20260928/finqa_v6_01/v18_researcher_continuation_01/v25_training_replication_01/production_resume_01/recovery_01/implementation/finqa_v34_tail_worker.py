"""One independent class-G/C/pi supplement using V33's complete saved gJ.

There is no replay/collector/optimizer-step entry in this worker. The original
numerical functions and actual pre-state are reused; only saved-tensor storage
and resource-boundary accounting change. Old trial artifacts are read-only.
"""

from __future__ import annotations

import argparse
import fcntl
import importlib
import io
import json
import os
import time
from pathlib import Path

import finqa_v34_tail_controller as control


def dependencies():
    training = control.frozen_training_module()
    rt = training.load_runtime()
    inherited = importlib.import_module("finqa_v32_performance_worker")
    guard = importlib.import_module("finqa_v32_same_point_guard")
    variants = importlib.import_module("finqa_v32_replay_variants")
    memory = importlib.import_module("finqa_v34_tail_memory")
    mechanism = importlib.import_module("trusted_synthesis.finance_research.v9_mechanism_execution")
    immutable = importlib.import_module("trusted_synthesis.core.immutable_artifacts")
    return training, rt, inherited, guard, variants.PauseRequest, memory, mechanism, immutable


def load_saved_gradient(plan, rt, actual):
    """Read and validate a completed accumulator, never invoke a replay backend."""
    checkpoint = control.read_ref(plan["source_final_checkpoint"])
    ref = plan["source_final_checkpoint_state"]
    control.require(
        control.sha(ref["path"]) == ref["sha256"] == checkpoint["state_sha256"],
        "source final accumulator bytes changed",
    )
    state = rt.torch.load(ref["path"], map_location="cpu", weights_only=False)
    control.require(
        rt.v8._tree_digest(state) == checkpoint["state_digest"]
        and state["binding"] == checkpoint["binding"]
        and state["cursor"] == checkpoint["cursor"] == 573
        and checkpoint["full_replay_complete"] is True
        and checkpoint["response_prefix_complete"] is True
        and state["accounting"]["responses_replayed"] == 573
        and state["binding"]["denominator"] == 700
        and state["rng_digest"] == rt.v8._tree_digest(actual["pre_state"]["rng"]),
        "saved complete gJ state/cursor/point/RNG differs",
    )
    gradient = state["total"]
    reference = actual["gJ"]
    control.require(set(gradient) == set(reference), "saved gJ parameter coordinates differ")
    control.require(
        all(
            value.shape == reference[name].shape
            and value.dtype == reference[name].dtype
            and value.device.type == "cpu"
            and bool(rt.torch.isfinite(value).all())
            for name, value in gradient.items()
        ),
        "invalid saved gradient tensor",
    )
    digest = rt.v8.parameter_digest(gradient)
    control.require(
        digest == plan["saved_gJ_digest"] == rt.v8.parameter_digest(reference),
        "saved final gJ differs from original reference",
    )
    binding = state["binding"]
    report = dict(
        denominator=binding["denominator"],
        all_receipts_validated=True,
        gJ_digest=digest,
        parameter_digest=binding["parameter_digest"],
        point_id=binding["point_id"],
        cohort_seal_sha256=binding["cohort_seal_sha256"],
        reward_sha256=binding["reward_sha256"],
        accounting=state["accounting"],
        complete_replay=True,
        reused_completed_responses=573,
        replayed_responses_this_supplement=0,
        receipt_validation_provenance=plan["source_final_checkpoint"],
        previously_validated_receipts_not_new_GPU_replay=True,
    )
    return gradient, report


def save_numerical_evidence(directory, rt, immutable, plan, result, prepared, comparison, report):
    """Keep actual computed results even when the subsequent resource gate fails."""
    stream = io.BytesIO()
    rt.torch.save(
        dict(
            aggregate_G={n: v.detach().cpu() for n, v in prepared["G"].items()},
            theta_bar={n: v.detach().cpu() for n, v in prepared["theta_bar"].items()},
            pullback={n: v.detach().cpu() for n, v in result["a"].items()},
            C=result["C"],
            pi=result["distribution"]["pi_next"],
        ),
        stream,
    )
    raw = stream.getvalue()
    import hashlib

    payload = directory / "numeric_payload"
    immutable.write_immutable_artifact_directory(payload, {"state.pt": raw})
    return control.publish(
        directory / "numeric_comparison/record.json",
        dict(
            schema="v34_independent_tail_numeric_comparison.v1",
            at=control.now(),
            protocol_id=plan["id"],
            comparison=comparison,
            numeric_pass=all(comparison.values()),
            resource_acceptance_not_implied=True,
            computed_payload=dict(
                path=str(payload / "state.pt"), sha256=hashlib.sha256(raw).hexdigest()
            ),
            computed_C=result["C"],
            computed_pi=result["distribution"]["pi_next"],
            reused_gJ=report,
        ),
    )


def accepted_resources(monitor, plan):
    report = monitor.report()
    return dict(
        all_gates_passed=report["all_passed"],
        limits_unchanged=True,
        peak_resets_before_model_load=1,
        peak_resets_after_model_loading_begins=0,
        helper_peak_reset_calls=report["peak_reset_calls"],
        maximum_allocated_bytes=plan["allocated_memory_limit_bytes"],
        minimum_device_free_bytes=plan["free_memory_reserve_bytes"],
        observed_peak_allocated_bytes=report["max_observed_peak_allocated_bytes"],
        observed_minimum_boundary_free_bytes=report["min_boundary_free_bytes"],
        observations=report["observations"],
    )


def execute_tail(
    directory,
    plan,
    actual,
    gradient,
    feedback_report,
    model,
    optimizer,
    training,
    rt,
    inherited,
    guard,
    memory,
    monitor,
    stop,
    immutable,
):
    original = inherited.state_identity(rt, model, optimizer)
    parameters = {n: p for n, p in model.named_parameters() if p.requires_grad}
    gJ = {name: value.to(parameters[name].device) for name, value in gradient.items()}
    control.require(
        rt.v8.parameter_digest(gJ) == plan["saved_gJ_digest"], "gJ transfer changed values"
    )
    _, pool, _, _ = training.checked_launch(training.DEFAULT_ROOT)
    monitor.clear_unused("before_class_gradients")
    started = time.monotonic()
    gradients, storage_receipt = memory.class_gradients_with_cpu_saves(
        rt,
        model,
        pool,
        device="cuda:0",
        monitor=monitor,
    )
    rt.torch.cuda.synchronize()
    class_seconds = time.monotonic() - started
    # The function has returned: temporary saved tensors are no longer needed.
    monitor.clear_unused("class_gradients_complete")
    control.publish(
        directory / "storage_receipt/record.json",
        dict(
            schema="v34_class_storage_receipt.v1",
            at=control.now(),
            protocol_id=plan["id"],
            class_gradient_passes=1,
            class_gradient_seconds=class_seconds,
            **storage_receipt,
        ),
    )
    control.require(not stop.requested, "stop requested after class gradients; no retry")
    prepared = rt.v8.prepare_virtual_point(
        parameters,
        optimizer,
        gradients,
        actual["pre_state"]["pi"],
        actual["mu"],
    )
    monitor.clear_unused("virtual_point_complete")
    point = guard.recompute_point_id(
        actual["pre_state"],
        theta_bar=prepared["theta_bar"],
        G=prepared["G"],
        frozen_runtime=rt,
    )
    guard.check_recomputed_point(control.read_ref(plan["benchmark_manifest"]), point)
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
            schema="v34_recomputed_class_G_point.v1",
            at=control.now(),
            protocol_id=plan["id"],
            comparison=point_comparison,
            class_gradient_passes=1,
            class_gradient_seconds=class_seconds,
        ),
    )
    control.require(
        all(point_comparison.values()), "class G or actual virtual point differs; no fallback"
    )
    control.require(not stop.requested, "stop requested before independent C/pi; no retry")
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
    distribution_seconds = time.monotonic() - started
    comparison = dict(
        **point_comparison,
        pullback_bitwise_equal=rt.v8.parameter_digest(result["a"])
        == rt.v8.parameter_digest(actual["pullback"]),
        C_equal=result["C"] == actual["C"],
        pi_equal=result["distribution"]["pi_next"] == actual["q_next"],
        model_optimizer_rng_buffers_unchanged=original
        == inherited.state_identity(rt, model, optimizer),
    )
    numeric = save_numerical_evidence(
        directory, rt, immutable, plan, result, prepared, comparison, feedback_report
    )
    control.require(all(comparison.values()), "independent tail numerical comparison failed")
    monitor.clear_unused("after_distribution")
    control.require(not stop.requested, "stop requested after tail; no successful result published")
    return dict(
        status="COMPLETE",
        numeric_pass=True,
        comparison=comparison,
        class_gradient_passes=1,
        class_gradient_seconds=class_seconds,
        distribution_seconds=distribution_seconds,
        reused_completed_responses=573,
        replayed_responses=0,
        saved_gJ_digest=plan["saved_gJ_digest"],
        numeric_comparison=control.entry(directory / "numeric_comparison/record.json"),
        storage_receipt=control.entry(directory / "storage_receipt/record.json"),
        backend_version=memory.BACKEND_VERSION,
        resources=accepted_resources(monitor, plan),
        numeric_record_id=numeric["id"],
        original_V33_failure_reclassified=False,
        tail_supplement_only=True,
    )


def run(root, stage, gpu_index):
    root = Path(root).resolve()
    plan = control.checked_protocol(root)
    control.require(
        Path(__file__).resolve() == root / "implementation" / Path(__file__).name,
        "only the committed frozen tail worker may run",
    )
    control.require(stage == "tail_validation" and gpu_index == 7, "unregistered tail stage/GPU")
    directory = root / stage
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        control.require(not (directory / "attempt/record.json").exists(), "one tail attempt only")
        training, rt, inherited, guard, PauseRequest, memory, mechanism, immutable = dependencies()
        control.require(not rt.torch.cuda.is_initialized(), "fresh CPU-only entry required")
        stop, monitor, sampler = PauseRequest(), None, None
        started = time.monotonic()
        control.publish(
            directory / "attempt/record.json",
            dict(
                schema="v34_tail_attempt.v1",
                at=control.now(),
                protocol_id=plan["id"],
                stage=stage,
                pid=os.getpid(),
                gpu_index=gpu_index,
                original_B_resume_authorized=False,
                API_calls=0,
                new_sampling_calls=0,
                scoring_calls=0,
                optimizer_steps=0,
                replayed_responses=0,
                automatic_retry=False,
            ),
        )

        def event(value):
            number = event.count
            event.count += 1
            control.publish(
                directory / "resources" / f"event{number:06d}" / "record.json",
                dict(
                    schema="v34_exact_resource_observation.v1",
                    at=control.now(),
                    protocol_id=plan["id"],
                    observation=value,
                ),
            )

        event.count = 0
        with stop.signals():
            try:
                outer_record, _, actual = mechanism.checked_outer(plan["source_outer"]["path"])
                control.require(
                    outer_record["outer_inputs_sha256"]
                    == plan["source_outer"]["outer_inputs"]["sha256"]
                    and outer_record["state_sha256"] == plan["source_outer"]["state"]["sha256"],
                    "actual source outer differs",
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
                    "sealed feedback differs",
                )
                gradient, feedback_report = load_saved_gradient(plan, rt, actual)
                control.require(
                    not rt.torch.cuda.is_initialized(), "source reading created CUDA context"
                )
                control.verify_original_B_paused(plan)
                row = next(
                    (value for value in control.inventory() if value["index"] == gpu_index), None
                )
                control.require(
                    row is not None
                    and control.eligible(row, plan)
                    and row["uuid"] == plan["gpu_uuids"][str(gpu_index)],
                    "GPU7 no longer idle or UUID changed",
                )
                control.require(not stop.requested, "stopped before CUDA admission")
                os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
                os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
                sampler = inherited.DeviceSamples(row["uuid"])
                with sampler:
                    # Exactly one reset, before model loading. No later reset is
                    # permitted to hide a previous phase's allocated high water.
                    rt.torch.cuda.reset_peak_memory_stats()
                    monitor = memory.TailMemoryMonitor(
                        rt.torch, event_sink=event, stop_requested=lambda: stop.requested
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
                    body = execute_tail(
                        directory,
                        plan,
                        actual,
                        gradient,
                        feedback_report,
                        model,
                        optimizer,
                        training,
                        rt,
                        inherited,
                        guard,
                        memory,
                        monitor,
                        stop,
                        immutable,
                    )
                    return control.publish(
                        directory / "result/record.json",
                        dict(
                            schema="v34_tail_supplement_result.v1",
                            at=control.now(),
                            protocol_id=plan["id"],
                            stage=stage,
                            gpu_index=gpu_index,
                            gpu_uuid=row["uuid"],
                            elapsed_stage_seconds=time.monotonic() - started,
                            telemetry=sampler.report(),
                            torch_version=rt.torch.__version__,
                            API_calls=0,
                            new_sampling_calls=0,
                            scoring_calls=0,
                            optimizer_steps=0,
                            original_B_resume_authorized=False,
                            **body,
                        ),
                    )
            except BaseException as exc:
                control.publish(
                    directory / "failure/record.json",
                    dict(
                        schema="v34_tail_failure_no_retry.v1",
                        at=control.now(),
                        protocol_id=plan["id"],
                        stage=stage,
                        error_type=type(exc).__name__,
                        error=str(exc),
                        resources=monitor.report() if monitor is not None else None,
                        telemetry=sampler.report() if sampler is not None else None,
                        exact_resource_observations_persisted_before_gate=True,
                        numeric_comparison=(
                            control.entry(directory / "numeric_comparison/record.json")
                            if (directory / "numeric_comparison/record.json").exists()
                            else None
                        ),
                        automatic_retry=False,
                        variant_fallback=False,
                        API_calls=0,
                        new_sampling_calls=0,
                        scoring_calls=0,
                        optimizer_steps=0,
                        replayed_responses=0,
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
    print(json.dumps(dict(status=result["status"], id=result["id"])))
