"""Shared-GPU endpoint reservation with the original generation and scoring maths.

CUDA is initialized once by the resource reservation before model loading. Every
later check observes the actual initialized state and retains its lifetime peak.
"""

from __future__ import annotations

import argparse
import gc
import importlib
import json
import os
import signal
import time
import weakref
from contextlib import contextmanager
from pathlib import Path

import finqa_v40_signals as stop_signals
import finqa_v43_time_policy as time_policy
import finqa_v50_admission as admission
import finqa_v50_admission as policy
import finqa_v50_reservation as reservation


def _controller():
    return importlib.import_module("finqa_v50_controller")


def _parent_module(root, control):
    module = importlib.import_module("finqa_v37_evaluation")
    control.require(
        Path(module.__file__).resolve() == root / "implementation/finqa_v37_evaluation.py",
        "unchanged sealed V37 evaluation shell required",
    )
    return module


def _checked_entry(root, control):
    control.require(
        Path(__file__).resolve() == root / "implementation/finqa_v50_evaluation.py"
        and Path(admission.__file__).resolve() == root / "implementation/finqa_v50_admission.py"
        and Path(control.__file__).resolve() == root / "implementation/finqa_v50_controller.py"
        and Path(reservation.__file__).resolve()
        == root / "implementation/finqa_v50_reservation.py",
        "sealed V50 endpoint shell and admission dependencies required",
    )


class _PreCudaStop:
    def __init__(self):
        self.requested = False

    @contextmanager
    def signals(self):
        def request(_signum, _frame):
            self.requested = True

        previous = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}
        try:
            for number in previous:
                signal.signal(number, request)
            yield self
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)


def install_reserved_observation_hook(final, monitor_factory, stop_requested, owner, control):
    """Keep the exact local provider, observing the existing single lifetime peak."""
    original_loader = final.load_final_provider
    state = dict(load_calls=0, response_calls=0, monitor=None, provider_ref=None)

    def load(*args, **kwargs):
        control.require(not stop_requested(), "safe stop requested before endpoint model load")
        control.require(state["load_calls"] == 0, "one actual endpoint model load only")
        owner.verify_before_model_load()
        state["load_calls"] += 1
        monitor = state["monitor"] = monitor_factory()
        monitor.snapshot("before_model_load", boundary=True)
        owner.mark_model_load_started()
        provider = original_loader(*args, **kwargs)
        state["provider_ref"] = weakref.ref(provider)
        monitor.clear_unused("after_model_load")
        original_chat = provider.chat

        async def observed_chat(*chat_args, **chat_kwargs):
            control.require(
                not stop_requested(), "safe stop requested before next endpoint response"
            )
            monitor.check_stop("before_endpoint_response", response=state["response_calls"] + 1)
            result = await original_chat(*chat_args, **chat_kwargs)
            state["response_calls"] += 1
            monitor.snapshot(
                "after_endpoint_response", boundary=True, response=state["response_calls"]
            )
            return result

        provider.chat = observed_chat
        return provider

    final.load_final_provider = load
    return state, original_loader


@contextmanager
def endpoint_gpu_policy(
    final,
    protocol,
    gpu_index,
    control,
    stop,
    deadline_epoch,
    *,
    directory,
    context_id,
    reservation_owner,
    extra_stop_requested=lambda: False,
):
    """Validate the already-owned CUDA reservation, never impersonate pre-CUDA."""
    admission.validate_plan(protocol)
    control.require(gpu_index == 0, "all endpoint generation must use GPU0")
    time_policy.require_no_deadline(deadline_epoch)
    original, count = final.eligible_gpu, 0

    def eligible(_scientific_plan, index, _inventory):
        nonlocal count
        control.require(index == gpu_index, "endpoint changed its registered GPU")
        count += 1
        control.require(count <= 2, "unregistered third endpoint admission check")
        control.require(
            not stop.requested and not extra_stop_requested(),
            "safe stop requested before reserved endpoint model load",
        )
        control.require(
            final.torch.cuda.is_initialized(),
            "reserved endpoint must honestly retain initialized CUDA",
        )
        reservation_owner.verify_before_model_load()
        rows = control.inventory()
        row = next((item for item in rows if item["index"] == gpu_index), None)
        control.require(
            row is not None and row["uuid"] == protocol["gpu_uuids"][str(gpu_index)],
            "reserved endpoint physical GPU identity changed",
        )
        memory = control.process_memory(os.getpid())
        host = control.host_memory()
        control.require(
            isinstance(memory, dict)
            and type(memory.get("rss_bytes")) is int
            and type(memory.get("peak_rss_bytes")) is int
            and 0 <= memory["rss_bytes"] <= memory["peak_rss_bytes"] <= 192 * 1024**3
            and host["available_bytes"] >= 96 * 1024**3,
            "reserved endpoint host RAM envelope failed",
        )
        control.publish(
            Path(directory) / "post_cuda_rechecks" / f"check{count:04d}" / "record.json",
            dict(
                schema="v50_endpoint_reserved_post_cuda_recheck.v1",
                at=control.now(),
                protocol_id=protocol["id"],
                context_id=context_id,
                stage="generate",
                gpu_index=gpu_index,
                gpu_uuid=row["uuid"],
                pid=os.getpid(),
                birth=control.birth(os.getpid()),
                cuda_initialized=True,
                reservation_admission=control.entry(
                    Path(directory) / "reservation/admission/record.json"
                ),
                host=dict(memory, available_bytes=host["available_bytes"]),
                lifetime_peak_reset_performed=False,
                scientific_model_loaded=False,
                already_owned_reservation_not_retested_as_external_free=True,
            ),
        )
        return row

    final.eligible_gpu = eligible
    try:
        yield
    finally:
        final.eligible_gpu = original


def run(root, seed, arm, gpu_index, deadline_epoch=None):
    directory = Path(root).resolve() / "evaluations" / f"seed{seed}_{arm}" / "generate"

    def record_signals(evidence):
        control = _controller()
        control.publish(
            directory / "signal_audit/record.json",
            dict(
                schema="v50_endpoint_stop_signal_audit.v1",
                at=control.now(),
                protocol_id=control.checked(Path(root) / "protocol/record.json")["id"],
                context_id=f"evaluation:{seed}:{arm}",
                stage="generate",
                **evidence,
                original_stop_handlers_preserved=True,
                automatic_retry=False,
            ),
        )

    with stop_signals.audit_signal_installations(sink=record_signals):
        return _run(root, seed, arm, gpu_index, deadline_epoch)


def _run(root, seed, arm, gpu_index, deadline_epoch):
    root = Path(root).resolve()
    control = _controller()
    protocol = control.checked_protocol(root)
    control.checked_implementation(root)
    admission.validate_plan(protocol)
    _checked_entry(root, control)
    time_policy.validate(protocol)
    control.require(
        gpu_index in admission.ALLOWED_GPUS and deadline_epoch is None,
        "unregistered endpoint device or unexpected wall-clock deadline",
    )
    parent = _parent_module(root, control)
    directory = root / "evaluations" / f"seed{seed}_{arm}" / "generate"
    stop = _PreCudaStop()
    original_control = parent.control
    parent.control = control
    try:
        with stop.signals():
            return _generate(
                root, seed, arm, gpu_index, deadline_epoch, control, protocol, parent, stop
            )
    except BaseException as error:
        if not (directory / "failure/record.json").exists():
            control.publish(
                directory / "failure/record.json",
                dict(
                    schema="v50_endpoint_pre_generation_failure.v1",
                    at=control.now(),
                    protocol_id=protocol["id"],
                    context_id=f"evaluation:{seed}:{arm}",
                    stage="generate",
                    status="STOPPED_FAILURE_NO_RETRY",
                    error_type=type(error).__name__,
                    error=str(error),
                    retry=False,
                    pid=os.getpid(),
                    birth=control.birth(os.getpid()),
                    gpu_index=gpu_index,
                    deadline_epoch=deadline_epoch,
                    API_calls=0,
                    scoring_calls=0,
                    actual_response_calls=0,
                    original_evaluation_source_unchanged=True,
                ),
            )
        raise
    finally:
        parent.control = original_control


def _generate(root, seed, arm, gpu_index, deadline_epoch, control, protocol, parent, pre_stop):
    root = Path(root).resolve()
    control.require(
        Path(__file__).resolve() == root / "implementation" / Path(__file__).name,
        "sealed evaluation shell required",
    )
    control.require(
        seed in (137, 251, 389) and arm in ("static", "c_only", "full"), "unregistered endpoint"
    )
    control.require(gpu_index in admission.ALLOWED_GPUS, "GPU outside newly authorized host scope")
    directory = root / "evaluations" / f"seed{seed}_{arm}" / "generate"
    directory.mkdir(parents=True, exist_ok=True)
    control.require(not (directory / "attempt/record.json").exists(), "one generation attempt only")
    evaluator = parent.frozen_evaluator(protocol)
    canonical_arm = evaluator.arm_name(arm)
    final = evaluator.load_runtime()
    # The following imports have no CUDA entry; do them before loading a model.
    memory = importlib.import_module("finqa_v34_tail_memory")
    variants = importlib.import_module("finqa_v32_replay_variants")
    host = importlib.import_module("finqa_v35_task_worker")
    tail = importlib.import_module("finqa_v34_tail_worker")
    inherited = importlib.import_module("finqa_v32_performance_worker")
    evaluation_root = Path(protocol["evaluation_root"])
    evaluation = evaluator.checked_plan(evaluation_root, final)
    control.require(evaluation["block"] == "B", "B-only evaluator")
    key = evaluator.coordinate(seed, arm)
    original_seal = (
        evaluator.model_root(evaluation_root, evaluation["jobs"][key])
        / "whole_test_seal/record.json"
    )
    control.require(not original_seal.exists(), "completed model must not be generated again")
    row = admission.wait_for_pre_cuda_admission(
        protocol,
        "generate",
        gpu_index,
        directory,
        deadline_epoch,
        final.torch,
        lambda: pre_stop.requested,
        context_id=f"evaluation:{seed}:{arm}",
        inventory=control.inventory,
        host_memory=control.host_memory,
        process_memory=control.process_memory,
        birth=control.birth,
    )
    control.require(not final.torch.cuda.is_initialized(), "fresh evaluation worker required")
    os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    with reservation.Reservation(
        final.torch,
        directory,
        protocol,
        f"evaluation:{seed}:{arm}",
        "generate",
        gpu_index,
        control=control,
        stop_requested=lambda: pre_stop.requested,
    ) as reservation_owner:
        reservation_owner.start(policy.minimum_free_mib("generate", None) * 1024**2)
        context_id = f"evaluation:{seed}:{arm}"
        control.publish(
            directory / "attempt/record.json",
            dict(
                schema="v50_endpoint_attempt.v1",
                at=control.now(),
                protocol_id=protocol["id"],
                context_id=context_id,
                stage="generate",
                seed=seed,
                arm=canonical_arm,
                gpu_index=gpu_index,
                gpu_uuid=row["uuid"],
                pid=os.getpid(),
                deadline_epoch=deadline_epoch,
                automatic_retry=False,
                scoring_allowed=False,
                device_admission_and_same_process_reservation_override=True,
                original_evaluation_registration_unchanged=True,
            ),
        )
        stop = variants.PauseRequest()
        reservation_owner.stop_requested = lambda: stop.requested or pre_stop.requested
        started = time.monotonic()
        observations = []

        def event_sink(value):
            observed_host = host.host_memory()
            observed_host.update(
                rss_limit_bytes=192 * 1024**3, available_reserve_bytes=96 * 1024**3
            )
            observed_host["rss_pass"] = (
                observed_host["peak_rss_bytes"] <= observed_host["rss_limit_bytes"]
            )
            observed_host["available_pass"] = (
                observed_host["available_bytes"] >= observed_host["available_reserve_bytes"]
            )
            observed_host["passed"] = observed_host["rss_pass"] and observed_host["available_pass"]
            event = dict(
                value,
                host=observed_host,
                deadline_pass=True,
                wallclock_limits_removed=True,
                elapsed_accounting_retained=True,
            )
            event["passed"] = event["passed"] and observed_host["passed"] and event["deadline_pass"]
            observations.append(event)
            control.publish(
                directory / "resources" / f"event{len(observations):06d}/record.json",
                dict(
                    schema="v50_endpoint_resources.v1",
                    at=control.now(),
                    protocol_id=protocol["id"],
                    observation=event,
                ),
            )
            control.require(event["passed"], "endpoint resource/deadline envelope failed")

        state, original_loader = install_reserved_observation_hook(
            final,
            lambda: memory.TailMemoryMonitor(
                final.torch,
                event_sink=event_sink,
                stop_requested=lambda: stop.requested or pre_stop.requested,
            ),
            lambda: stop.requested or pre_stop.requested,
            reservation_owner,
            control,
        )
        with (
            stop.signals(),
            inherited.DeviceSamples(row["uuid"]),
            endpoint_gpu_policy(
                final,
                protocol,
                gpu_index,
                control,
                pre_stop,
                deadline_epoch,
                directory=directory,
                context_id=context_id,
                extra_stop_requested=lambda: stop.requested,
                reservation_owner=reservation_owner,
            ),
        ):
            try:
                seal = evaluator.generate(evaluation_root, seed, arm, gpu_index, resume=False)
                final.load_final_provider = original_loader
                gc.collect()
                control.require(
                    state["load_calls"] == 1 and state["provider_ref"]() is None,
                    "endpoint provider not released",
                )
                monitor = state["monitor"]
                monitor.clear_unused("model_released")
                resources = tail.accepted_resources(monitor, protocol)
                resources.update(
                    observations=observations,
                    all_gates_passed=resources["all_gates_passed"]
                    and all(item["passed"] for item in observations),
                    host=dict(
                        rss_limit_bytes=192 * 1024**3,
                        available_reserve_bytes=96 * 1024**3,
                        max_observed_peak_rss_bytes=max(
                            item["host"]["peak_rss_bytes"] for item in observations
                        ),
                        min_observed_available_bytes=min(
                            item["host"]["available_bytes"] for item in observations
                        ),
                        all_passed=all(item["host"]["passed"] for item in observations),
                    ),
                    single_process_lifetime_includes_loading=True,
                )
                control.require(
                    resources["all_gates_passed"], "endpoint final resource gate failed"
                )
                reservation_owner.report()
                return control.publish(
                    directory / "result/record.json",
                    dict(
                        schema="v50_endpoint_generation_result.v1",
                        at=control.now(),
                        protocol_id=protocol["id"],
                        context_id=context_id,
                        stage="generate",
                        status="COMPLETE",
                        seed=seed,
                        arm=canonical_arm,
                        gpu_index=gpu_index,
                        gpu_uuid=row["uuid"],
                        model_released=True,
                        resources=resources,
                        gpu_reservation=control.entry(directory / "reservation/result/record.json"),
                        whole_test_seal=control.entry(original_seal),
                        original_seal_id=seal["id"],
                        session_count=1147,
                        new_generation_episodes=1147,
                        API_calls=0,
                        new_sampling_calls=state["response_calls"],
                        scoring_calls=0,
                        optimizer_steps=0,
                        replayed_responses=0,
                        actual_response_calls=state["response_calls"],
                        elapsed_seconds=time.monotonic() - started,
                        memory_phase=policy.phase_key("generate", None),
                        minimum_free_mib=policy.minimum_free_mib("generate", None),
                        gpu_admission_policy_schema=admission.POLICY_SCHEMA,
                        time_policy_schema=time_policy.SCHEMA,
                        generation_only=True,
                        private_test_scoring=False,
                    ),
                )
            except BaseException as error:
                control.publish(
                    directory / "failure/record.json",
                    dict(
                        schema="v50_endpoint_generation_failure.v1",
                        at=control.now(),
                        protocol_id=protocol["id"],
                        context_id=context_id,
                        stage="generate",
                        status="STOPPED_FAILURE_NO_RETRY",
                        error_type=type(error).__name__,
                        error=str(error),
                        retry=False,
                        scoring_calls=0,
                        resource_observations=observations,
                        actual_response_calls=state["response_calls"],
                    ),
                )
                raise
            finally:
                final.load_final_provider = original_loader


def score(root):
    """Keep the original nine-seal barrier; no device override or early scoring."""
    root = Path(root).resolve()
    control = _controller()
    protocol = control.checked_protocol(root)
    control.checked_implementation(root)
    admission.validate_plan(protocol)
    _checked_entry(root, control)
    parent = _parent_module(root, control)
    original_control = parent.control
    parent.control = control
    try:
        return parent.score(root)
    finally:
        parent.control = original_control


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--stage", choices=("generate",), required=True)
    generate.add_argument("--root", type=Path, required=True)
    generate.add_argument("--seed", type=int, required=True)
    generate.add_argument("--arm", choices=("static", "c_only", "full"), required=True)
    generate.add_argument("--gpu-index", type=int, required=True)
    generate.add_argument("--deadline-epoch", type=float, default=None)
    sub.add_parser("score").add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = (
        score(args.root)
        if args.command == "score"
        else run(args.root, args.seed, args.arm, args.gpu_index, args.deadline_epoch)
    )
    print(json.dumps(dict(status=result["status"], id=result["id"])))
    return result


if __name__ == "__main__":
    main()
