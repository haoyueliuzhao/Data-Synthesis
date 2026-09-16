"""Replay the two saved GPU cases using differentiable autoregressive KV caches.

No new sampling or budget expansion. The virtual point must match its saved
digest exactly. Saved-tensor CPU offload does not detach prefix KV derivatives.
This bounded implementation control does NOT admit 360 full-length sessions.
"""

import argparse
import json
import subprocess
import time
from pathlib import Path

import fixed_kernel_anchored_sources_gpu_gate_20260916 as previous
import numpy as np
import torch
from torch import nn
from torch.nn.attention import SDPBackend, sdpa_kernel

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import optimizer_pullback as adam
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import trajectory_training
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.loss import selected_target_loss

BASE, MIN_FREE_MIB = previous.BASE, previous.MIN_FREE_MIB
GATE_DIRECTORY = "gpu_cached_replay_r2"
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_anchored_sources_cached_replay_20260916.py"


class CachedGradientOperation(nn.Module):
    def __init__(self, model, names):
        super().__init__()
        self.model, self.names = model, tuple(names)

    def forward(self, prompt, targets):
        parameters = dict(self.model.named_parameters())
        device = parameters[self.names[0]].device
        ids = torch.tensor([prompt], dtype=torch.long, device=device)
        cache, logps = None, []
        for index, target in enumerate(targets):
            output = self.model(
                input_ids=ids,
                attention_mask=torch.ones(
                    (1, len(prompt) + index), dtype=torch.long, device=device
                ),
                use_cache=True,
                past_key_values=cache,
                logits_to_keep=1,
            )
            cache = output.past_key_values  # no detach; all prefix derivatives retained
            logps.append(torch.log_softmax(output.logits[0, -1].float(), -1)[target])
            ids = torch.tensor([[target]], dtype=torch.long, device=device)
        values = torch.stack(logps)
        gradients = torch.autograd.grad(
            values.sum(), [parameters[name] for name in self.names], allow_unused=True
        )
        return values.detach(), {
            name: torch.zeros_like(parameters[name]) if value is None else value.detach()
            for name, value in zip(self.names, gradients, strict=True)
        }


def cached_logp(model, theta, prompt, targets, *, offload=True):
    from contextlib import nullcontext

    operation = CachedGradientOperation(model, theta)
    overrides = {"model." + name: value for name, value in theta.items()}
    overrides.update(
        {"model." + name: value.detach().clone() for name, value in model.named_buffers()}
    )
    context = torch.autograd.graph.save_on_cpu(pin_memory=True) if offload else nullcontext()
    # Eval only disables dropout/checkpoint recomputation; autograd remains ON.
    with previous.proxy_mode(model, gradient=False), context:
        return torch.func.functional_call(operation, overrides, (prompt, targets), strict=False)


def prepare(root):
    root = Path(root).resolve()
    old = root / BASE / "gpu_gate_env_r1"
    report = p.checked(p.read_json(old / "report.json"), "anchored_sources_gpu_gate_report")
    p.require(
        report["status"] == "BLOCKED_GPU_NUMERIC_GATE"
        and report["error"]["message"].endswith("replayed_sampling_probabilities_mismatch")
        and report["real_state_unchanged"] is True
        and len(report["cases"]) == 2,
        "cached_replay.only_saved_numerical_counterexample",
    )
    code = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    p.require(
        (root / SCRIPT).read_bytes()
        == subprocess.check_output(["git", "show", code + ":" + SCRIPT], cwd=root),
        "cached_replay.committed_before_execution",
    )
    plan = p.record(
        "anchored_sources_cached_replay_plan",
        code_commit=code,
        code_sha256=p.sha(root / SCRIPT),
        prior_report_id=report["id"],
        old_gate=BASE + "/gpu_gate_env_r1",
        case_ids=[row["id"] for row in report["cases"]],
        original_order_and_actual_tokens_unchanged=True,
        new_model_generate_calls=0,
        new_sampled_tokens=0,
        diagnosis=(
            "cached generation vs full-sequence teacher-forcing numerical path; "
            "hypothesis before replay"
        ),
        replay=(
            "same autoregressive prefill/decode path, differentiable KV cache, "
            "CPU saved-tensor offload"
        ),
        prefix_KV_detached=False,
        probability_atol=previous.ATOL,
        probability_rtol=previous.RTOL,
        original_virtual_digest_must_match=True,
        no_looser_tolerance_or_repaired_probability=True,
        full_response_2048_and_context_24576_not_admitted_by_eight_token_control=True,
        extra_original_package_forward_backward_passes=1,
        real_optimizer_steps=0,
        minimum_free_MiB=MIN_FREE_MIB,
        at=p.now(),
    )
    p.write_once(root / BASE / GATE_DIRECTORY / "plan.json", plan)
    return plan


def reconstruct(model, optimizer, root, plan):
    old = root / plan["old_gate"]
    package = p.read_json(old / "plan.json")["original_train_package"]
    saved = p.read_json(old / "virtual_point.json")
    frozen = p.read_json(root / previous.PARENT / "preparation/execution_freeze.json")
    cache = root / frozen["trajectory_cache"]["cache_root"]
    inputs = np.load(cache / "A/input_ids.npy", mmap_mode="r", allow_pickle=False)
    positions = np.load(cache / "A/target_positions.npy", mmap_mode="r", allow_pickle=False)
    names = {name: value for name, value in model.named_parameters() if value.requires_grad}
    bound = adam.bind_adamw(names, optimizer, clip_max_norm=1.0)
    diagnostic = {name: torch.zeros_like(value) for name, value in names.items()}
    with previous.proxy_mode(model, gradient=True), sdpa_kernel(SDPBackend.FLASH_ATTENTION):
        for segment in package["segments"]:
            ids = np.asarray(
                inputs[segment["input_offset"] : segment["input_offset"] + segment["input_length"]]
            )
            targets = np.asarray(
                positions[
                    segment["target_offset"] : segment["target_offset"] + segment["target_count"]
                ]
            )
            logits = model(
                input_ids=torch.tensor(ids.copy()[None, :], dtype=torch.long, device="cuda:0"),
                attention_mask=torch.ones((1, len(ids)), dtype=torch.long, device="cuda:0"),
                use_cache=False,
                logits_to_keep=torch.tensor(targets.copy() - 1, dtype=torch.long, device="cuda:0"),
            ).logits
            loss = selected_target_loss(
                logits,
                torch.tensor(ids[targets].copy(), dtype=torch.long, device="cuda:0"),
                1 / package["whole_package_target_tokens"],
            )
            derivatives = torch.autograd.grad(loss, tuple(names.values()), allow_unused=True)
            for (name, _), value in zip(names.items(), derivatives, strict=True):
                if value is not None:
                    diagnostic[name] += value.detach()
            del logits, loss, derivatives
    virtual = adam.virtual_step(bound, diagnostic)
    p.require(
        previous.tensor_digest(diagnostic) == saved["diagnostic_gradient_digest"]
        and previous.tensor_digest(virtual["theta_bar"]) == saved["virtual_parameter_digest"],
        "cached_replay.exact_same_original_gradient_and_virtual_point",
    )
    return names, bound, virtual["theta_bar"]


def run(root):
    import os
    import traceback

    root = Path(root).resolve()
    out = root / BASE / GATE_DIRECTORY
    plan = p.checked(p.read_json(out / "plan.json"), "anchored_sources_cached_replay_plan")
    p.require(p.sha(root / SCRIPT) == plan["code_sha256"], "cached_replay.frozen_code")
    p.require(
        os.environ.get("CUBLAS_WORKSPACE_CONFIG") == ":4096:8", "cached_replay.deterministic_launch"
    )
    p.write_once(
        out / "started.json", p.record("cached_replay_started", pid=os.getpid(), at=p.now())
    )
    started, cases, error, unchanged = time.monotonic(), [], None, None
    stage = "load"
    try:
        frozen = p.read_json(root / previous.PARENT / "preparation/execution_freeze.json")
        model, _ = trajectory_training.load_registered_student(
            frozen["base_binding"], 11, trainable=True
        )
        names = {name: value for name, value in model.named_parameters() if value.requires_grad}
        optimizer = trajectory_training.optimizer_factory(
            list(names.values()), frozen["training_configuration"]
        )
        before = (
            previous.storage_versions(model),
            previous.tensor_digest(names),
            previous.rng_digest(),
        )
        modes = [module.training for module in model.modules()]
        stage = "reconstruct_same_virtual_point"
        names, bound, theta = reconstruct(model, optimizer, root, plan)
        for index, expected_id in enumerate(plan["case_ids"]):
            stage = "replay_saved_case_" + str(index)
            saved = p.checked(
                p.read_json(root / plan["old_gate"] / "cases" / (str(index) + ".json")),
                "anchored_sources_probability_replay_control",
            )
            p.require(saved["id"] == expected_id, "cached_replay.exact_saved_case")
            with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                values, derivatives = cached_logp(
                    model, theta, saved["prompt_input_ids"], saved["generated_token_ids"]
                )
            expected = torch.tensor(saved["sampled_token_logprobs"], device=values.device)
            case = p.record(
                "anchored_sources_cached_replay_case",
                original_case_id=expected_id,
                context=saved["context"],
                prompt_tokens=len(saved["prompt_input_ids"]),
                generated_token_ids=saved["generated_token_ids"],
                actual_eos_included=saved["actual_eos_included"],
                sampled_logprobs=saved["sampled_token_logprobs"],
                cached_replayed_logprobs=values.cpu().tolist(),
                maximum_absolute_difference=float((values - expected).abs().max()),
                passed=bool(
                    torch.allclose(values, expected, atol=previous.ATOL, rtol=previous.RTOL)
                ),
                finite_gradient=all(
                    bool(torch.isfinite(value).all()) for value in derivatives.values()
                ),
                gradient_digest=previous.tensor_digest(derivatives),
                virtual_point_digest=previous.tensor_digest(theta),
                new_sampled_tokens=0,
                prefix_KV_detached=False,
                actual_financial_feedback=False,
            )
            p.write_once(out / "cases" / (str(index) + ".json"), case)
            cases.append(case)
            p.require(
                case["passed"] and case["finite_gradient"],
                "cached_replay.numeric_or_gradient_failure",
            )
            del derivatives, values
        stage = "isolation"
        adam._verify(bound)
        unchanged = (
            before
            == (
                previous.storage_versions(model),
                previous.tensor_digest(names),
                previous.rng_digest(),
            )
            and not optimizer.state
            and all(v.grad is None for v in names.values())
            and modes == [module.training for module in model.modules()]
        )
        p.require(unchanged, "cached_replay.real_state_changed")
    except BaseException as failure:
        traceback.print_exc()
        error = dict(stage=stage, type=type(failure).__name__, message=str(failure))
        if "before" in locals():
            unchanged = (
                before
                == (
                    previous.storage_versions(model),
                    previous.tensor_digest(names),
                    previous.rng_digest(),
                )
                and not optimizer.state
                and all(v.grad is None for v in names.values())
                and modes == [module.training for module in model.modules()]
            )
    report = p.record(
        "anchored_sources_cached_replay_report",
        plan_id=plan["id"],
        status="PASS_AS_SCOPED_CACHED_LOGP_CONTROL"
        if error is None
        else "BLOCKED_CACHED_LOGP_CONTROL",
        cases=cases,
        error=error,
        real_state_unchanged=unchanged,
        new_model_generate_calls=0,
        new_sampled_tokens=0,
        real_optimizer_steps=0,
        full_A_launcher_admitted=False,
        full360_feedback_not_executed=True,
        peak_reserved_bytes=torch.cuda.max_memory_reserved(),
        elapsed_seconds=time.monotonic() - started,
        finished_at=p.now(),
    )
    p.write_once(out / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("prepare", "run"), required=True)
    args = parser.parse_args()
    value = prepare(args.root) if args.mode == "prepare" else run(args.root)
    print(json.dumps({key: value[key] for key in ("id", "status") if key in value}))
