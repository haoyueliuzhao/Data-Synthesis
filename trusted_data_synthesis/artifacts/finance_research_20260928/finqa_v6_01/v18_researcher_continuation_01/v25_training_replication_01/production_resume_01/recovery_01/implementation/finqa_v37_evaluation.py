"""Original B endpoint generation with lifetime accounting and one score barrier.

The frozen V25 evaluator still owns task selection, endpoint binding, generation,
sealing and scoring. This shell observes resources and never changes an answer,
model argument, provider result, sampling setting or registered score rule.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib
import json
import os
import sys
import time
import weakref
from pathlib import Path

import finqa_v37_controller as control


def frozen_evaluator(protocol):
    reference = protocol["source_evaluation_module"]
    path = Path(reference["path"]).resolve()
    control.require(
        hashlib.sha256(path.read_bytes()).hexdigest() == reference["sha256"],
        "frozen evaluator changed",
    )
    source_manifest = control.checked(path.parent / "record.json")
    for name in (
        "finqa_v25_evaluation.py",
        "finqa_v25_training_replication.py",
        "finqa_v23_test_confirmation.py",
    ):
        source = path.with_name(name)
        control.require(
            hashlib.sha256(source.read_bytes()).hexdigest() == source_manifest["sha256"][name],
            "original evaluation dependency changed: " + name,
        )
        module_name = source.stem
        if module_name in sys.modules:
            control.require(
                Path(sys.modules[module_name].__file__).resolve() == source,
                "foreign evaluation import",
            )
    sys.path.insert(0, str(path.parent))
    evaluator = importlib.import_module(path.stem)
    control.require(Path(evaluator.__file__).resolve() == path, "wrong evaluation implementation")
    return evaluator


def install_observation_hook(final, monitor_factory, stop_requested):
    """Observe the exact same local provider before/after each model response."""
    original_loader = final.load_final_provider
    state = dict(load_calls=0, response_calls=0, monitor=None, provider_ref=None)

    def load(*args, **kwargs):
        control.require(state["load_calls"] == 0, "one actual endpoint model load only")
        state["load_calls"] += 1
        control.require(
            not final.torch.cuda.is_initialized(),
            "fresh process before endpoint model load required",
        )
        final.torch.cuda.reset_peak_memory_stats()
        monitor = state["monitor"] = monitor_factory()
        monitor.snapshot("before_model_load", boundary=True)
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


def run(root, seed, arm, gpu_index, deadline_epoch):
    root = Path(root).resolve()
    protocol = control.checked_protocol(root)
    control.require(
        Path(__file__).resolve() == root / "implementation" / Path(__file__).name,
        "sealed evaluation shell required",
    )
    control.require(
        seed in (137, 251, 389) and arm in ("static", "c_only", "full"), "unregistered endpoint"
    )
    control.require(gpu_index in (3, 4, 5, 7), "GPU outside four-card whitelist")
    directory = root / "evaluations" / f"seed{seed}_{arm}" / "generate"
    directory.mkdir(parents=True, exist_ok=True)
    control.require(not (directory / "attempt/record.json").exists(), "one generation attempt only")
    evaluator = frozen_evaluator(protocol)
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
    row = next((r for r in control.inventory() if r["index"] == gpu_index), None)
    control.require(
        row is not None
        and control.eligible(row, protocol)
        and row["uuid"] == protocol["gpu_uuids"][str(gpu_index)],
        "registered GPU is not idle or UUID changed",
    )
    control.require(not final.torch.cuda.is_initialized(), "fresh evaluation worker required")
    os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    context_id = f"evaluation:{seed}:{arm}"
    control.publish(
        directory / "attempt/record.json",
        dict(
            schema="v37_endpoint_attempt.v1",
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
        ),
    )
    stop = variants.PauseRequest()
    started = time.monotonic()
    observations = []

    def event_sink(value):
        observed_host = host.host_memory()
        observed_host.update(rss_limit_bytes=192 * 1024**3, available_reserve_bytes=96 * 1024**3)
        observed_host["rss_pass"] = (
            observed_host["peak_rss_bytes"] <= observed_host["rss_limit_bytes"]
        )
        observed_host["available_pass"] = (
            observed_host["available_bytes"] >= observed_host["available_reserve_bytes"]
        )
        observed_host["passed"] = observed_host["rss_pass"] and observed_host["available_pass"]
        event = dict(value, host=observed_host, deadline_pass=time.time() < deadline_epoch)
        event["passed"] = event["passed"] and observed_host["passed"] and event["deadline_pass"]
        observations.append(event)
        control.publish(
            directory / "resources" / f"event{len(observations):06d}/record.json",
            dict(
                schema="v37_endpoint_resources.v1",
                at=control.now(),
                protocol_id=protocol["id"],
                observation=event,
            ),
        )
        control.require(event["passed"], "endpoint resource/deadline envelope failed")

    state, original_loader = install_observation_hook(
        final,
        lambda: memory.TailMemoryMonitor(
            final.torch,
            event_sink=event_sink,
            stop_requested=lambda: stop.requested or time.time() >= deadline_epoch,
        ),
        lambda: stop.requested or time.time() >= deadline_epoch,
    )
    with stop.signals(), inherited.DeviceSamples(row["uuid"]):
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
            control.require(resources["all_gates_passed"], "endpoint final resource gate failed")
            return control.publish(
                directory / "result/record.json",
                dict(
                    schema="v37_endpoint_generation_result.v1",
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
                    generation_only=True,
                    private_test_scoring=False,
                ),
            )
        except BaseException as error:
            control.publish(
                directory / "failure/record.json",
                dict(
                    schema="v37_endpoint_generation_failure.v1",
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
    root = Path(root).resolve()
    protocol = control.checked_protocol(root)
    evaluator = frozen_evaluator(protocol)
    final = evaluator.load_runtime()
    control.require(not final.torch.cuda.is_initialized(), "block scoring is CPU-only")
    evaluation_root = Path(protocol["evaluation_root"])
    plan = evaluator.checked_plan(evaluation_root, final)
    control.require(
        plan["block"] == "B" and len(plan["jobs"]) == 9, "all original nine models required"
    )
    control.require(
        not (root / "scoring/attempt/record.json").exists(), "one unified scoring attempt only"
    )
    # The original score() performs the one actual all-answer validation before
    # reading private references; this admission only binds the nine metadata seals.
    seals = {
        key: control.entry(
            evaluator.model_root(evaluation_root, job) / "whole_test_seal/record.json"
        )
        for key, job in plan["jobs"].items()
    }
    control.publish(
        root / "scoring/attempt/record.json",
        dict(
            schema="v37_unified_B_scoring_attempt.v1",
            at=control.now(),
            protocol_id=protocol["id"],
            all_nine_model_seal_metadata_present=True,
            model_seals=seals,
            API_calls=0,
        ),
    )
    summary = evaluator.score(evaluation_root)
    source_root = Path(protocol["source_evaluation_module"]["path"]).parents[1]
    combined_root = source_root / "descriptive_six_seed_summary"
    evaluator.combine(source_root / "c_only_test_extension", evaluation_root, combined_root)
    return control.publish(
        root / "scoring/result/record.json",
        dict(
            schema="v37_unified_B_scoring_result.v1",
            at=control.now(),
            protocol_id=protocol["id"],
            status="COMPLETE",
            summary=control.entry(evaluation_root / "summary/record.json"),
            scientific_summary_id=summary["id"],
            combined_descriptive_summary=control.entry(combined_root / "record.json"),
            reported_models=9,
            task_denominator=1147,
            separate_new_seed_block=True,
            API_calls=0,
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("generate")
    run_parser.add_argument("--stage", choices=("generate",), required=True)
    run_parser.add_argument("--root", type=Path, required=True)
    run_parser.add_argument("--seed", type=int, required=True)
    run_parser.add_argument("--arm", choices=("static", "c_only", "full"), required=True)
    run_parser.add_argument("--gpu-index", type=int, required=True)
    run_parser.add_argument("--deadline-epoch", type=float, required=True)
    sub.add_parser("score").add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    result = (
        score(args.root)
        if args.command == "score"
        else run(args.root, args.seed, args.arm, args.gpu_index, args.deadline_epoch)
    )
    print(json.dumps(dict(status=result["status"], id=result["id"])))
