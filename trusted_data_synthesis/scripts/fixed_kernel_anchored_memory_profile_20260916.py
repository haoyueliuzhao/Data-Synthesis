"""Once-only saved-token attribution and conditional frozen-view retention.

Fresh worker processes isolate each phase's pinned allocator/RSS high-water mark.
No new sampling, financial session, training step or full-A release.
"""

# ruff: noqa: E501 -- fixed measurement/provenance fields
import argparse
import gc
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

import fixed_kernel_anchored_sources_cached_replay_20260916 as r2
import fixed_kernel_anchored_sources_gpu_gate_20260916 as gate
import torch
from fixed_kernel_anchored_saved_tensors_20260916 import SavedTensorStore, host_memory
from safetensors.torch import load_file, save_file
from torch.nn.attention import SDPBackend, sdpa_kernel

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import trajectory_training

BASE, GATE_DIRECTORY = gate.BASE, "saved_tensors_profile_r3"
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_anchored_memory_profile_20260916.py"
SOURCES = [
    SCRIPT,
    "trusted_data_synthesis/scripts/fixed_kernel_anchored_saved_tensors_20260916.py",
    r2.SCRIPT,
    gate.SCRIPT,
]
MIN_FREE_MIB, MIN_HOST_AVAILABLE_BYTES = 61440, 512 * 2**30
PHASES = ("original_save_on_cpu", "retain_bound_immutable_views")


def prepare(root):
    root = Path(root).resolve()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    refs = {}
    for path in SOURCES:
        raw = (root / path).read_bytes()
        p.require(
            raw == subprocess.check_output(["git", "show", head + ":" + path], cwd=root),
            "profile.committed_sources",
        )
        refs[path] = p.sha(raw)
    previous = p.checked(
        p.read_json(root / BASE / "gpu_cached_replay_r2/report.json"),
        "anchored_sources_cached_replay_report",
    )
    p.require(previous["status"] == "PASS_AS_SCOPED_CACHED_LOGP_CONTROL", "profile.passed_R2")
    plan = p.record(
        "anchored_memory_profile_plan",
        code_commit=head,
        sources=refs,
        audit_sha256="065ead447c38ddd67537c800287957274978694e80a70204ce51a486f89b2920",
        R2_report_id=previous["id"],
        old_gate=BASE + "/gpu_gate_env_r1",
        phases=list(PHASES),
        fresh_process_per_phase=True,
        only_existing_two_contexts_and_2_plus_8_tokens=True,
        new_model_generate_calls=0,
        new_financial_sessions=0,
        optimization_condition="measured frozen logical saves exceed distinct registered frozen storage bytes",
        activation_deduplication=False,
        probability_atol=gate.ATOL,
        probability_rtol=gate.RTOL,
        full_gradient_atol=1e-6,
        full_gradient_rtol=1e-5,
        baseline_gradient_digest_must_match_R2=True,
        minimum_free_MiB=MIN_FREE_MIB,
        minimum_host_available_bytes=MIN_HOST_AVAILABLE_BYTES,
        maximum_concurrent_gradient_workers=1,
        automatic_retry=False,
        full_adaptive_A_admitted=False,
        at=p.now(),
    )
    p.write_once(root / BASE / GATE_DIRECTORY / "plan.json", plan)
    return plan


def worker(root, phase):
    root = Path(root).resolve()
    out = root / BASE / GATE_DIRECTORY / phase
    plan = p.checked(p.read_json(out.parent / "plan.json"), "anchored_memory_profile_plan")
    p.require(phase in PHASES, "profile.registered_phase")
    p.write_once(
        out / "started.json",
        p.record("profile_phase_started", pid=os.getpid(), phase=phase, at=p.now()),
    )
    started, cases, error, stage, unchanged = time.monotonic(), [], None, "load", None
    try:
        frozen = p.read_json(root / gate.PARENT / "preparation/execution_freeze.json")
        model, _ = trajectory_training.load_registered_student(
            frozen["base_binding"], 11, trainable=True
        )
        names = {name: value for name, value in model.named_parameters() if value.requires_grad}
        optimizer = trajectory_training.optimizer_factory(
            list(names.values()), frozen["training_configuration"]
        )
        before = gate.storage_versions(model), gate.tensor_digest(names), gate.rng_digest()
        modes = [module.training for module in model.modules()]
        stage = "reconstruct_existing_virtual_point"
        names, bound, theta = r2.reconstruct(model, optimizer, root, plan)
        old_results = p.read_json(root / BASE / "gpu_cached_replay_r2/report.json")["cases"]
        for index in range(2):
            stage = "existing_case_" + str(index)
            original = p.read_json(root / plan["old_gate"] / "cases" / (str(index) + ".json"))
            torch.cuda.reset_peak_memory_stats()
            with (out / (str(index) + "_save_events.jsonl")).open("xb") as stream:
                store = SavedTensorStore(
                    model, retain_frozen=phase == PHASES[1], event_stream=stream
                )
                with store.context(), sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                    logps, gradients = r2.cached_logp(
                        model,
                        theta,
                        original["prompt_input_ids"],
                        original["generated_token_ids"],
                        offload=False,
                    )
            expected = torch.tensor(original["sampled_token_logprobs"], device=logps.device)
            digest = gate.tensor_digest(gradients)
            gradient_equal, maximum_difference = True, 0.0
            if phase == PHASES[0]:
                gradient_equal = digest == old_results[index]["gradient_digest"]
            else:
                reference = load_file(
                    str(out.parent / PHASES[0] / (str(index) + "_gradient.safetensors"))
                )
                for name, value in gradients.items():
                    current = value.detach().cpu()
                    maximum_difference = max(
                        maximum_difference, float((current - reference[name]).abs().max())
                    )
                    gradient_equal &= bool(
                        torch.allclose(
                            current,
                            reference[name],
                            atol=plan["full_gradient_atol"],
                            rtol=plan["full_gradient_rtol"],
                        )
                    )
            save_file(
                {name: value.detach().cpu().contiguous() for name, value in gradients.items()},
                str(out / (str(index) + "_gradient.safetensors")),
            )
            gc.collect()
            torch.cuda.synchronize()
            measured = store.report()
            case = p.record(
                "anchored_memory_profile_case",
                phase=phase,
                original_case_id=original["id"],
                prompt_tokens=len(original["prompt_input_ids"]),
                output_tokens=len(original["generated_token_ids"]),
                logP_max_difference=float((logps - expected).abs().max()),
                logP_passed=bool(torch.allclose(logps, expected, atol=gate.ATOL, rtol=gate.RTOL)),
                full_gradient_equal=gradient_equal,
                full_gradient_max_difference=maximum_difference,
                gradient_digest=digest,
                expected_R2_gradient_digest=old_results[index]["gradient_digest"],
                measurement=measured,
            )
            p.write_once(out / (str(index) + "_case.json"), case)
            cases.append(case)
            p.require(
                case["logP_passed"] and gradient_equal, "profile.numeric_or_full_gradient_mismatch"
            )
            p.require(
                sum(measured["live_host_bytes_after_response"].values()) == 0,
                "profile.response_saved_tensor_release",
            )
            del logps, gradients
        stage = "isolation"
        r2.adam._verify(bound)
        unchanged = (
            before == (gate.storage_versions(model), gate.tensor_digest(names), gate.rng_digest())
            and not optimizer.state
            and all(value.grad is None for value in names.values())
            and modes == [module.training for module in model.modules()]
        )
        p.require(unchanged, "profile.real_state_changed")
    except BaseException as failure:
        traceback.print_exc()
        error = dict(stage=stage, type=type(failure).__name__, message=str(failure))
    report = p.record(
        "anchored_memory_profile_phase",
        phase=phase,
        plan_id=plan["id"],
        cases=cases,
        status="PASS_AS_SCOPED" if error is None else "BLOCKED",
        error=error,
        real_state_unchanged=unchanged,
        elapsed_seconds=time.monotonic() - started,
        new_model_generate_calls=0,
        finished_at=p.now(),
    )
    p.write_once(out / "report.json", report)
    return report


def run(root):
    root = Path(root).resolve()
    out = root / BASE / GATE_DIRECTORY
    plan = p.checked(p.read_json(out / "plan.json"), "anchored_memory_profile_plan")
    for path, expected in plan["sources"].items():
        p.require(p.sha(root / path) == expected, "profile.frozen_code")
    p.write_once(out / "started.json", p.record("profile_started", pid=os.getpid(), at=p.now()))
    reports = []
    for phase in PHASES:
        if phase == PHASES[1]:
            measurements = [case["measurement"] for case in reports[0]["cases"]]
            p.require(
                any(
                    row["logical_saved_bytes"].get("frozen_weight_or_view", 0)
                    > row["unique_source_storage_lifetime_bytes"].get("frozen_weight_or_view", 0)
                    for row in measurements
                ),
                "profile.require_observed_repeated_frozen_saves",
            )
        while True:
            free = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--id=" + os.environ["CUDA_VISIBLE_DEVICES"],
                    "--query-gpu=memory.free",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
            )
            memory = host_memory()
            if (
                int(free.strip()) >= MIN_FREE_MIB
                and memory["MemAvailable_bytes"] >= MIN_HOST_AVAILABLE_BYTES
            ):
                break
            print(
                json.dumps(
                    dict(
                        waiting_for_phase=phase,
                        GPU_free_MiB=int(free.strip()),
                        host=memory,
                        at=p.now(),
                    )
                ),
                flush=True,
            )
            time.sleep(30)
        with (out / (phase + ".log")).open("x") as stream:
            subprocess.run(
                [
                    sys.executable,
                    str(root / SCRIPT),
                    "--root",
                    str(root),
                    "--mode",
                    "worker",
                    "--phase",
                    phase,
                ],
                cwd=root,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=True,
            )
        result = p.read_json(out / phase / "report.json")
        reports.append(result)
        if result["status"] != "PASS_AS_SCOPED":
            break
    report = p.record(
        "anchored_memory_profile_report",
        plan_id=plan["id"],
        phases=[dict(phase=r["phase"], id=r["id"], status=r["status"]) for r in reports],
        status="PASS_AS_SCOPED_MEMORY_ATTRIBUTION_AND_FROZEN_RETENTION"
        if len(reports) == 2 and all(r["status"] == "PASS_AS_SCOPED" for r in reports)
        else "BLOCKED_MEMORY_IMPLEMENTATION",
        full_A_admitted=False,
        new_financial_sessions=0,
        new_model_generate_calls=0,
        finished_at=p.now(),
    )
    p.write_once(out / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("prepare", "run", "worker"), required=True)
    parser.add_argument("--phase", choices=PHASES)
    args = parser.parse_args()
    value = (
        prepare(args.root)
        if args.mode == "prepare"
        else worker(args.root, args.phase)
        if args.mode == "worker"
        else run(args.root)
    )
    print(json.dumps({key: value[key] for key in ("id", "status") if key in value}))
