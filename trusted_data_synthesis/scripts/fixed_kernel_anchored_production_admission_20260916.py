"""Frozen-layout repair, full-gradient adjoints, exact length and cloned Adam gate.

No new model.generate, financial response, training update or effect selection.
Original R3 attribution is reused rather than repeated. Each phase is fresh.
"""

# ruff: noqa: E501 -- frozen controls and explicit provenance
import argparse
import copy
import gc
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from collections import Counter
from pathlib import Path

import fixed_kernel_anchored_segmented_replay_20260916 as segmented
import fixed_kernel_anchored_sources_cached_replay_20260916 as r2
import fixed_kernel_anchored_sources_gpu_gate_20260916 as gate
import torch
from fixed_kernel_anchored_canonical_saves_20260916 import CanonicalSavedTensorStore
from fixed_kernel_anchored_saved_tensors_20260916 import host_memory, process_memory
from safetensors.torch import load_file, save_file
from torch.nn.attention import SDPBackend, sdpa_kernel

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import trajectory_training

BASE, GATE_DIRECTORY = gate.BASE, "production_admission_r4"
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_anchored_production_admission_20260916.py"
SOURCES = [
    SCRIPT,
    "trusted_data_synthesis/scripts/fixed_kernel_anchored_segmented_replay_20260916.py",
    "trusted_data_synthesis/scripts/fixed_kernel_anchored_canonical_saves_20260916.py",
    "trusted_data_synthesis/scripts/fixed_kernel_anchored_saved_tensors_20260916.py",
    r2.SCRIPT,
    gate.SCRIPT,
]
PHASES = (
    "canonical_full_saved_tokens",
    "segmented_saved_tokens",
    "full_length_release_and_nonempty_Adam",
)
MIN_FREE_MIB, MIN_HOST_AVAILABLE_BYTES = 61440, 512 * 2**30


class Monitor:
    def __init__(self):
        self.peak = Counter(process_memory())
        self.stop = threading.Event()
        self.started = time.monotonic()

    def __enter__(self):
        torch.cuda.reset_peak_memory_stats()

        def sample():
            while not self.stop.wait(0.1):
                self.peak |= Counter(process_memory())

        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        torch.cuda.synchronize()
        self.stop.set()
        self.thread.join()
        self.peak |= Counter(process_memory())

    def report(self):
        return dict(
            observed_process_peak=dict(self.peak),
            after=process_memory(),
            CUDA_peak_allocated=torch.cuda.max_memory_allocated(),
            CUDA_peak_reserved=torch.cuda.max_memory_reserved(),
            CUDA_allocated_after=torch.cuda.memory_allocated(),
            CUDA_reserved_after=torch.cuda.memory_reserved(),
            elapsed_seconds=time.monotonic() - self.started,
        )


def prepare(root):
    root = Path(root).resolve()
    out = root / BASE / GATE_DIRECTORY
    old = p.read_json(root / BASE / "saved_tensors_profile_r3/report.json")
    baseline = p.read_json(
        root / BASE / "saved_tensors_profile_r3/original_save_on_cpu/report.json"
    )
    failed = p.read_json(
        root / BASE / "saved_tensors_profile_r3/retain_bound_immutable_views/report.json"
    )
    p.require(
        baseline["status"] == "PASS_AS_SCOPED"
        and failed["status"] == "BLOCKED"
        and failed["error"]["message"].endswith("numeric_or_full_gradient_mismatch"),
        "admission.actual_preserved_R3_counterexample",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    refs = {}
    for path in SOURCES:
        raw = (root / path).read_bytes()
        p.require(
            raw == subprocess.check_output(["git", "show", head + ":" + path], cwd=root),
            "admission.commit_before_control",
        )
        refs[path] = p.sha(raw)
    old_case = p.read_json(root / BASE / "gpu_gate_env_r1/cases/1.json")
    prompt = (old_case["prompt_input_ids"] * 2)[:22528]
    tokens = (old_case["generated_token_ids"] * 256)[:2048]
    pressure = p.record(
        "anchored_synthetic_boundary_tokens",
        prompt=prompt,
        targets=tokens,
        rule="repeat existing long input to22528 and existing eight outputIDs to2048; no new sampling",
        synthetic_only=True,
        financial_response=False,
        sampled_model_output=False,
    )
    p.require(len(prompt) == 22528 and len(tokens) == 2048, "admission.actual_length_boundary")
    p.write_once(out / "synthetic_boundary_tokens.json", pressure)
    plan = p.record(
        "anchored_production_admission_plan",
        code_commit=head,
        sources=refs,
        phases=list(PHASES),
        R3_report_id=old["id"],
        baseline_report_id=baseline["id"],
        failed_direct_retention_id=failed["id"],
        old_gate=BASE + "/gpu_gate_env_r1",
        pressure_input_id=pressure["id"],
        raw_gradient_reference=BASE + "/saved_tensors_profile_r3/original_save_on_cpu",
        reference_gradient_digests=[case["gradient_digest"] for case in baseline["cases"]],
        probability_atol=gate.ATOL,
        probability_rtol=gate.RTOL,
        gradient_atol=1e-6,
        gradient_rtol=1e-5,
        no_tolerance_relaxation=True,
        decode_block_size=8,
        prefill="pure per-layer recomputation with explicit VJP under same virtual scope and original contiguous saved layout",
        cache_boundaries="views of one immutable complete append-only cache; full boundary adjoints returned",
        zero_new_financial_sessions=True,
        new_model_generate_calls=0,
        new_random_sampled_tokens=0,
        prefill_mode="eval; dropout off; never train-mode checkpoint switch",
        cloned_Adam_control_steps=200,
        cloned_Adam_reference_next_step=201,
        cloned_Adam_is_not_real_epoch5_training=True,
        actual_Student_optimizer_steps=0,
        actual_epoch5_step200_must_be_asserted_in_registered_run=True,
        minimum_free_MiB=MIN_FREE_MIB,
        minimum_host_available_bytes=MIN_HOST_AVAILABLE_BYTES,
        maximum_concurrent_gradient_workers=1,
        no_automatic_retry=True,
        at=p.now(),
    )
    p.write_once(out / "plan.json", plan)
    return plan


def compare_gradient(actual, reference, plan):
    rows, difference2, reference2, dot = [], 0.0, 0.0, 0.0
    passed = True
    for name, value in actual.items():
        a, b = value.detach().cpu(), reference[name]
        maximum = float((a - b).abs().max())
        finite = bool(torch.isfinite(a).all())
        same = finite and bool(
            torch.allclose(a, b, atol=plan["gradient_atol"], rtol=plan["gradient_rtol"])
        )
        passed &= same
        difference2 += float((a.double() - b.double()).square().sum())
        reference2 += float(b.double().square().sum())
        dot += float((a.double() * b.double()).sum())
        rows.append(dict(parameter=name, maximum_absolute_difference=maximum, passed=same))
    return dict(
        passed=passed,
        maximum_absolute_difference=max(row["maximum_absolute_difference"] for row in rows),
        relative_L2=(difference2 / reference2) ** 0.5 if reference2 else 0.0,
        reference_norm=reference2**0.5,
        inner_product=dot,
        mismatched_parameters=[row for row in rows if not row["passed"]],
    )


def nonempty_adam(names, config, root, out):
    from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import (
        optimizer_pullback as adam,
    )

    vector = load_file(
        str(root / BASE / "saved_tensors_profile_r3/original_save_on_cpu/1_gradient.safetensors"),
        device="cuda:0",
    )
    scratch = {name: torch.nn.Parameter(value.detach().clone()) for name, value in names.items()}
    optimizer = trajectory_training.optimizer_factory(list(scratch.values()), config)
    for _ in range(200):
        for name, value in scratch.items():
            value.grad = vector[name].clone()
        torch.nn.utils.clip_grad_norm_(list(scratch.values()), 1.0, error_if_nonfinite=True)
        optimizer.step()
    optimizer.zero_grad(set_to_none=True)
    p.require(
        all(int(optimizer.state[value]["step"].item()) == 200 for value in scratch.values()),
        "admission.actual_clone_step200",
    )
    bound = adam.bind_adamw(scratch, optimizer, clip_max_norm=1.0)
    proposed = adam.virtual_step(bound, vector)
    pulled = adam.pullback(bound, vector, {name: -value for name, value in vector.items()})
    reference = {
        name: torch.nn.Parameter(value.detach().clone()) for name, value in scratch.items()
    }
    real_step = trajectory_training.optimizer_factory(list(reference.values()), config)
    real_step.load_state_dict(copy.deepcopy(optimizer.state_dict()))
    for name, value in reference.items():
        value.grad = vector[name].clone()
    torch.nn.utils.clip_grad_norm_(list(reference.values()), 1.0, error_if_nonfinite=True)
    real_step.step()
    maximum = max(
        float((proposed["theta_bar"][name] - value).abs().max())
        for name, value in reference.items()
    )
    passed = all(
        torch.allclose(proposed["theta_bar"][name], value, atol=1e-7, rtol=1e-6)
        for name, value in reference.items()
    )
    adam._verify(bound)
    report = p.record(
        "anchored_nonempty_GPU_Adam_control",
        cloned_actual_step=200,
        real_clone_next_step=201,
        virtual_matches_actual_clone_step=passed,
        maximum_absolute_parameter_difference=maximum,
        captured_optimizer_id=bound.snapshot["id"],
        pullback_id=pulled["diagnostics"]["id"],
        finite_pullback=all(bool(torch.isfinite(value).all()) for value in pulled["a"].values()),
        actual_training_updates=0,
        synthetic_moment_history_not_actual_epoch5=True,
    )
    p.write_once(out / "nonempty_Adam.json", report)
    p.require(passed and report["finite_pullback"], "admission.actual_nonempty_Adam_wiring")
    return report


def worker(root, phase):
    root = Path(root).resolve()
    out = root / BASE / GATE_DIRECTORY / phase
    plan = p.checked(p.read_json(out.parent / "plan.json"), "anchored_production_admission_plan")
    p.write_once(
        out / "started.json",
        p.record("production_control_started", pid=os.getpid(), phase=phase, at=p.now()),
    )
    for path, expected in plan["sources"].items():
        p.require(p.sha(root / path) == expected, "admission.frozen_phase_code")
    started, results, error, stage, unchanged = time.monotonic(), [], None, "load", None
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
        names, bound, theta = r2.reconstruct(model, optimizer, root, plan)
        indices = [0, 1] if phase != PHASES[2] else ["synthetic_boundary", 0]
        for index in indices:
            stage = "case_" + str(index)
            expected, reference = None, None
            if index == "synthetic_boundary":
                inputs = p.checked(
                    p.read_json(out.parent / "synthetic_boundary_tokens.json"),
                    "anchored_synthetic_boundary_tokens",
                )
                prompt, tokens = inputs["prompt"], inputs["targets"]
                p.require(
                    inputs["id"] == plan["pressure_input_id"], "admission.fixed_pressure_input"
                )
            else:
                inputs = p.read_json(root / plan["old_gate"] / "cases" / (str(index) + ".json"))
                prompt, tokens, expected = (
                    inputs["prompt_input_ids"],
                    inputs["generated_token_ids"],
                    inputs["sampled_token_logprobs"],
                )
                reference = load_file(
                    str(
                        root
                        / plan["raw_gradient_reference"]
                        / (str(index) + "_gradient.safetensors")
                    )
                )
                p.require(
                    gate.tensor_digest(reference) == plan["reference_gradient_digests"][index],
                    "admission.original_complete_gradient_reference",
                )
            with Monitor() as resource, sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                if phase == PHASES[0]:
                    store = CanonicalSavedTensorStore(model)
                    with store.context():
                        values, gradient = r2.cached_logp(
                            model, theta, prompt, tokens, offload=False
                        )
                    accounting = store.report()
                    p.require(
                        store.bank.live_host == store.bank.live_pinned == 0,
                        "admission.full_graph_saved_release",
                    )
                    del store
                else:
                    with (out / (str(index) + "_events.jsonl")).open("xb") as stream:

                        def emit(event):
                            stream.write(p.encode(dict(at=p.now(), **event)) + b"\n")
                            stream.flush()

                        values, gradient, accounting = segmented.segmented_logp(
                            model,
                            theta,
                            prompt,
                            tokens,
                            expected=expected,
                            block_size=8,
                            event_sink=emit,
                        )
                comparison = (
                    compare_gradient(gradient, reference, plan) if reference is not None else None
                )
                actual_probabilities = values.detach().cpu().tolist()
                probability_difference = (
                    float((values - torch.tensor(expected, device=values.device)).abs().max())
                    if expected is not None
                    else None
                )
                probability_passed = (
                    bool(
                        torch.allclose(
                            values,
                            torch.tensor(expected, device=values.device),
                            atol=gate.ATOL,
                            rtol=gate.RTOL,
                        )
                    )
                    if expected is not None
                    else True
                )
                save_file(
                    {name: value.detach().cpu().contiguous() for name, value in gradient.items()},
                    str(out / (str(index) + "_gradient.safetensors")),
                )
                digest = gate.tensor_digest(gradient)
                del values, gradient
                gc.collect()
            result = p.record(
                "anchored_production_control_case",
                phase=phase,
                input_id=inputs["id"],
                prompt_tokens=len(prompt),
                output_tokens=len(tokens),
                synthetic_only=index == "synthetic_boundary",
                logP_max_difference=probability_difference,
                logP_passed=probability_passed,
                sampled_probabilities_used=expected is not None,
                replayed_logprobs=actual_probabilities,
                full_gradient_comparison=comparison,
                gradient_digest=digest,
                replay_accounting=accounting,
                resources=resource.report(),
            )
            p.write_once(out / (str(index) + "_case.json"), result)
            results.append(result)
            p.require(
                probability_passed and (comparison is None or comparison["passed"]),
                "admission.probability_or_full_gradient_mismatch",
            )
            torch.cuda.empty_cache()
        if phase == PHASES[2]:
            stage = "cloned_nonempty_Adam"
            nonempty_adam(names, frozen["training_configuration"], root, out)
        stage = "isolation"
        r2.adam._verify(bound)
        unchanged = (
            before == (gate.storage_versions(model), gate.tensor_digest(names), gate.rng_digest())
            and modes == [module.training for module in model.modules()]
            and not optimizer.state
            and all(value.grad is None for value in names.values())
        )
        p.require(unchanged, "admission.real_state_isolation")
    except BaseException as failure:
        traceback.print_exc()
        error = dict(stage=stage, type=type(failure).__name__, message=str(failure))
    report = p.record(
        "anchored_production_control_phase",
        plan_id=plan["id"],
        phase=phase,
        status="PASS_AS_SCOPED" if error is None else "BLOCKED",
        cases=results,
        error=error,
        real_state_unchanged=unchanged,
        elapsed_seconds=time.monotonic() - started,
        actual_training_updates=0,
        new_model_generate_calls=0,
        finished_at=p.now(),
    )
    p.write_once(out / "report.json", report)
    return report


def run(root):
    root = Path(root).resolve()
    out = root / BASE / GATE_DIRECTORY
    plan = p.checked(p.read_json(out / "plan.json"), "anchored_production_admission_plan")
    p.write_once(
        out / "started.json", p.record("production_controls_started", pid=os.getpid(), at=p.now())
    )
    phases = []
    for phase in PHASES:
        while True:
            free = int(
                subprocess.check_output(
                    [
                        "nvidia-smi",
                        "--id=" + os.environ["CUDA_VISIBLE_DEVICES"],
                        "--query-gpu=memory.free",
                        "--format=csv,noheader,nounits",
                    ],
                    text=True,
                ).strip()
            )
            memory = host_memory()
            if free >= MIN_FREE_MIB and memory["MemAvailable_bytes"] >= MIN_HOST_AVAILABLE_BYTES:
                break
            print(
                json.dumps(dict(waiting_for=phase, GPU_free_MiB=free, host=memory, at=p.now())),
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
        phases.append({key: result[key] for key in ("id", "phase", "status", "error")})
        if result["status"] != "PASS_AS_SCOPED":
            break
    passed = len(phases) == len(PHASES) and all(row["status"] == "PASS_AS_SCOPED" for row in phases)
    report = p.record(
        "anchored_production_resource_admission",
        plan_id=plan["id"],
        phases=phases,
        status="PASS_RESOURCE_AND_NUMERICAL_SCOPE"
        if passed
        else "BLOCKED_PRODUCTION_IMPLEMENTATION",
        passed=passed,
        full_response_contract_admitted=passed,
        full_financial_feedback_already_executed=False,
        first_formal_run="A/full_anchored_vtdo/11 only after complete production script registration",
        no_extra_effect_pilot=True,
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
