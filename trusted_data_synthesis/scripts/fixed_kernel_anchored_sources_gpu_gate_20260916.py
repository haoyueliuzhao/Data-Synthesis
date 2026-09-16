"""Bounded real-Qwen virtual-point/RNG/logP gate; never an effect-search pilot.

One original fused package supplies a diagnostic gradient (NOT full-population
G). Two fixed input contexts each sample at most8 tokens, then replay all sampled
IDs including actual EOS. No reward, Contribution, pi or real optimizer update.
The legacy strict replay tolerance is not relaxed if CUDA precision fails it.
"""

# ruff: noqa: E501 -- exact artifact paths and frozen diagnostic scope
import argparse
import contextlib
import hashlib
import json
import os
import pickle
import random
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn.attention import SDPBackend, sdpa_kernel

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import optimizer_pullback as adam
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import trajectory_training

BASE = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/anchored_sources_20260916"
GATE_DIRECTORY = "gpu_gate_env_r1"
PARENT = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/parallel_tail_execution_20260914"
)
GIVEN = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/given_sources_value_20260915"
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_anchored_sources_gpu_gate_20260916.py"
MIN_FREE_MIB = 61440
ATOL, RTOL = 1e-6, 1e-5


def tensor_digest(tensors):
    digest = hashlib.sha256()
    for name, value in sorted(tensors.items()):
        digest.update(p.encode([name, str(value.dtype), list(value.shape)]))
        digest.update(value.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def rng_digest():
    return dict(
        cpu=p.sha(torch.get_rng_state().numpy().tobytes()),
        cuda=p.sha(torch.cuda.get_rng_state(0).cpu().numpy().tobytes()),
        python=p.sha(pickle.dumps(random.getstate())),
        numpy=p.sha(pickle.dumps(np.random.get_state())),
    )


def storage_versions(model):
    return {
        name: (value.data_ptr(), value._version, str(value.dtype), tuple(value.shape))
        for name, value in [*model.named_parameters(), *model.named_buffers()]
    }


@contextlib.contextmanager
def proxy_mode(model, *, gradient):
    modes = [(module, module.training) for module in model.modules()]
    model.train(gradient)
    # Keep real .05 dropout unchanged outside this proxy. Train-mode enables
    # nonreentrant checkpointing; only dropout is disabled within the proxy.
    for module in model.modules():
        if isinstance(module, nn.Dropout):
            module.train(False)
    try:
        yield
    finally:
        for module, training in modes:
            module.training = training


class LogProbGradientOperation(nn.Module):
    """Backward lives inside functional_call so checkpoint recomputation sees theta_bar."""

    def __init__(self, model, names):
        super().__init__()
        self.model = model
        self.names = tuple(names)

    def forward(self, ids, positions, targets):
        logits = self.model(
            input_ids=ids,
            attention_mask=torch.ones_like(ids),
            use_cache=False,
            logits_to_keep=positions,
        ).logits[0]
        logps = torch.log_softmax(logits.float(), dim=-1).gather(-1, targets[:, None]).squeeze(-1)
        parameters = dict(self.model.named_parameters())
        derivatives = torch.autograd.grad(
            logps.sum(), [parameters[name] for name in self.names], allow_unused=True
        )
        return logps.detach(), {
            name: torch.zeros_like(parameters[name]) if value is None else value.detach()
            for name, value in zip(self.names, derivatives, strict=True)
        }


def replay_logp(model, theta_bar, prompt, target):
    device = next(iter(theta_bar.values())).device
    operation = LogProbGradientOperation(model, theta_bar)
    overrides = {"model." + name: value for name, value in theta_bar.items()}
    overrides.update(
        {"model." + name: value.detach().clone() for name, value in model.named_buffers()}
    )
    ids = torch.tensor([prompt + target], dtype=torch.long, device=device)
    positions = torch.arange(len(prompt) - 1, len(prompt) + len(target) - 1, device=device)
    targets = torch.tensor(target, dtype=torch.long, device=device)
    with proxy_mode(model, gradient=True):
        return torch.func.functional_call(
            operation, overrides, (ids, positions, targets), strict=False
        )


class GenerateOperation(nn.Module):
    def __init__(self, model, configuration):
        super().__init__()
        self.model = model
        self.configuration = configuration

    def forward(self, ids):
        return self.model.generate(
            input_ids=ids,
            attention_mask=torch.ones_like(ids),
            generation_config=self.configuration,
            logits_to_keep=1,
            return_dict_in_generate=True,
            output_scores=True,
        )


def sample_prefix(model, theta_bar, prompt, configuration, seed):
    operation = GenerateOperation(model, configuration)
    overrides = {"model." + name: value for name, value in theta_bar.items()}
    overrides.update(
        {"model." + name: value.detach().clone() for name, value in model.named_buffers()}
    )
    ids = torch.tensor([prompt], dtype=torch.long, device="cuda:0")
    before = rng_digest()
    with torch.random.fork_rng(devices=[0]), proxy_mode(model, gradient=False), torch.no_grad():
        torch.manual_seed(seed)
        generated = torch.func.functional_call(operation, overrides, (ids,), strict=False)
        target = generated.sequences[0, len(prompt) :].tolist()
        p.require(len(target) == len(generated.scores), "anchored_gpu.exact_sampled_score_count")
        logps = [
            float(torch.log_softmax(score[0].float(), dim=-1)[token])
            for token, score in zip(target, generated.scores, strict=True)
        ]
        del generated
    p.require(rng_digest() == before, "anchored_gpu.probe_RNG_isolation")
    return target, logps


def prepare(root):
    root = Path(root).resolve()
    output = root / BASE / GATE_DIRECTORY
    p.require(not (output / "plan.json").exists(), "anchored_gpu.one_registration")
    failed = p.checked(
        p.read_json(root / BASE / "gpu_gate/report.json"), "anchored_sources_gpu_gate_report"
    )
    p.require(
        failed["status"] == "BLOCKED_GPU_NUMERIC_GATE"
        and failed["error"]["stage"] == "original_package_gradient"
        and "CUBLAS_WORKSPACE_CONFIG" in failed["error"]["message"]
        and not failed["cases"]
        and failed["real_state_unchanged"] is True,
        "anchored_gpu.explicit_environment_only_revision_of_preserved_failure",
    )
    material = p.checked(
        p.read_json(root / BASE / "material_binding/report.json"),
        "anchored_sources_material_admission",
    )
    source_manifest = p.read_json(root / GIVEN / "inputs_v2/manifest.json")
    admission = p.read_json(root / GIVEN / "inputs_v2/admission.json")
    longest = max(
        admission["checks"], key=lambda row: (row["initial_prompt_tokens"], row["task_id"])
    )
    row = next(row for row in source_manifest["tasks"] if row["task_id"] == longest["task_id"])
    frozen = p.read_json(root / PARENT / "preparation/execution_freeze.json")
    cache = root / frozen["trajectory_cache"]["cache_root"]
    package = p.read_json(cache / "A/packages.json")["packages"][0]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    p.require(
        (root / SCRIPT).read_bytes()
        == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
        "anchored_gpu.committed_before_control",
    )
    plan = p.record(
        "anchored_sources_gpu_gate_plan",
        code_commit=head,
        revises_failed_gate_report_id=failed["id"],
        revision_reason="missing deterministic CuBLAS launch environment; no sampling occurred in first attempt",
        required_launch_environment={"CUBLAS_WORKSPACE_CONFIG": ":4096:8"},
        source_sha256=p.sha(root / SCRIPT),
        material_admission_id=material["id"],
        utility_environment="J_sources_v2",
        source_view_manifest_id=source_manifest["id"],
        longest_public_view=row,
        original_train_package_id=package["package_id"],
        original_train_package=package,
        diagnostic_gradient_is_full_population_G=False,
        real_training_or_optimizer_steps=0,
        selected_contexts=["synthetic_reply_only_OK", longest["task_id"]],
        sampled_token_cap_per_context=8,
        maximum_model_generate_calls=2,
        maximum_total_sampled_tokens=16,
        synthetic_reward_or_C_used=False,
        feedback_360_not_replaced_by_this_control=True,
        stochastic_policy=dict(
            temperature=1.0,
            top_p=1.0,
            top_k=0,
            do_sample=True,
            repetition_penalty=1.0,
            forced_eos=False,
        ),
        probability_replay_atol=ATOL,
        probability_replay_rtol=RTOL,
        tolerances_source="unchanged old CPU feedback replay criterion; not relaxed after CUDA results",
        stop_on_first_numeric_or_isolation_failure=True,
        no_automatic_retry=True,
        minimum_free_MiB=MIN_FREE_MIB,
        only_registered_own_processes=True,
        scope="bounded real CUDA implementation gate; no financial effect, no distribution update, no fullA release",
        at=p.now(),
    )
    p.write_once(output / "plan.json", plan)
    return plan


def run(root):
    import fixed_kernel_source_view_compact_20260915 as public_runtime
    from transformers import GenerationConfig

    from trusted_synthesis.experiments.finance_qa_vnext_pq_student.loss import selected_target_loss
    from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (
        load_tokenizer,
    )

    root = Path(root).resolve()
    out = root / BASE / GATE_DIRECTORY
    plan = p.checked(p.read_json(out / "plan.json"), "anchored_sources_gpu_gate_plan")
    p.require(plan["source_sha256"] == p.sha(root / SCRIPT), "anchored_gpu.frozen_source")
    p.require(
        os.environ.get("CUBLAS_WORKSPACE_CONFIG") == ":4096:8",
        "anchored_gpu.frozen_deterministic_launch_environment",
    )
    p.require(
        bool(os.environ.get("CUDA_VISIBLE_DEVICES")), "anchored_gpu.explicit_one_device_scope"
    )
    p.write_once(
        out / "started.json",
        p.record(
            "anchored_sources_gpu_gate_started",
            plan_id=plan["id"],
            pid=os.getpid(),
            CUDA_VISIBLE_DEVICES=os.environ["CUDA_VISIBLE_DEVICES"],
            at=p.now(),
        ),
    )
    started = time.monotonic()
    cases = []
    stage = "load"
    error = None
    model = None
    unchanged = None
    virtual_id = None
    try:
        frozen = p.read_json(root / PARENT / "preparation/execution_freeze.json")
        model, scope = trajectory_training.load_registered_student(
            frozen["base_binding"], 11, trainable=True
        )
        names = {name: value for name, value in model.named_parameters() if value.requires_grad}
        optimizer = trajectory_training.optimizer_factory(
            list(names.values()), frozen["training_configuration"]
        )
        tokenizer = load_tokenizer(frozen["tokenizer_binding"])
        initial_storage = storage_versions(model)
        initial_digest = tensor_digest(names)
        initial_modes = [module.training for module in model.modules()]
        initial_rng = rng_digest()
        bound = adam.bind_adamw(names, optimizer, clip_max_norm=1.0)
        stage = "original_package_gradient"
        cache = root / frozen["trajectory_cache"]["cache_root"]
        inputs = np.load(cache / "A/input_ids.npy", mmap_mode="r", allow_pickle=False)
        positions = np.load(cache / "A/target_positions.npy", mmap_mode="r", allow_pickle=False)
        package = plan["original_train_package"]
        diagnostic = {name: torch.zeros_like(value) for name, value in names.items()}
        for segment in package["segments"]:
            ids = np.asarray(
                inputs[segment["input_offset"] : segment["input_offset"] + segment["input_length"]]
            )
            target = np.asarray(
                positions[
                    segment["target_offset"] : segment["target_offset"] + segment["target_count"]
                ]
            )
            ids_tensor = torch.tensor(ids.copy()[None, :], dtype=torch.long, device="cuda:0")
            selected = torch.tensor(target.copy() - 1, dtype=torch.long, device="cuda:0")
            labels = torch.tensor(ids[target].copy(), dtype=torch.long, device="cuda:0")
            with proxy_mode(model, gradient=True), sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                logits = model(
                    input_ids=ids_tensor,
                    attention_mask=torch.ones_like(ids_tensor),
                    use_cache=False,
                    logits_to_keep=selected,
                ).logits
                loss = selected_target_loss(
                    logits, labels, 1 / package["whole_package_target_tokens"]
                )
                derivatives = torch.autograd.grad(loss, tuple(names.values()), allow_unused=True)
            for (name, _), value in zip(names.items(), derivatives, strict=True):
                if value is not None:
                    diagnostic[name] += value.detach()
            del logits, loss, derivatives, ids_tensor, selected, labels
        virtual = adam.virtual_step(bound, diagnostic)
        theta = virtual["theta_bar"]
        virtual_id = virtual["diagnostics"]["id"]
        p.write_once(
            out / "virtual_point.json",
            p.record(
                "anchored_sources_control_virtual_point",
                plan_id=plan["id"],
                optimizer_snapshot=bound.snapshot,
                virtual_step=virtual["diagnostics"],
                virtual_parameter_digest=tensor_digest(theta),
                diagnostic_gradient_digest=tensor_digest(diagnostic),
                original_package_id=package["package_id"],
                full_population_G=False,
                real_optimizer_steps=0,
                actual_original_target_tokens=package["whole_package_target_tokens"],
            ),
        )
        generation = frozen["base_binding"]["generation_config"]
        eos = generation.get("eos_token_id", tokenizer.eos_token_id)
        eos = [eos] if isinstance(eos, int) else eos
        config = GenerationConfig(
            do_sample=True,
            temperature=1.0,
            top_p=1.0,
            top_k=0,
            num_beams=1,
            num_return_sequences=1,
            repetition_penalty=1.0,
            max_new_tokens=8,
            use_cache=True,
            eos_token_id=eos,
            pad_token_id=generation.get("pad_token_id", tokenizer.pad_token_id),
            bos_token_id=generation.get("bos_token_id", tokenizer.bos_token_id),
        )
        view = p.read_json(root / plan["longest_public_view"]["path"])
        contexts = [
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Reply only with the word OK."},
            ],
            [
                {
                    "role": "system",
                    "content": public_runtime.SYSTEM + "\nRequested guidance: neutral",
                },
                *view["public_messages"],
            ],
        ]
        for index, messages in enumerate(contexts):
            stage = "sample_and_replay_context_" + str(index)
            rendered = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            prompt = tokenizer(rendered, add_special_tokens=False, truncation=False)["input_ids"]
            seed = int(
                p.sha(p.encode(["A", 11, 0, plan["selected_contexts"][index], 1]))[:16], 16
            ) % (2**63)
            with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                target, sampled = sample_prefix(model, theta, prompt, config, seed)
                p.require(bool(target), "anchored_gpu.nonempty_actual_samples")
                replayed, gradient = replay_logp(model, theta, prompt, target)
            expected = torch.tensor(sampled, dtype=replayed.dtype, device=replayed.device)
            discrepancy = (replayed - expected).abs()
            passed = bool(torch.allclose(replayed, expected, atol=ATOL, rtol=RTOL))
            case = p.record(
                "anchored_sources_probability_replay_control",
                context=plan["selected_contexts"][index],
                prompt_input_ids=prompt,
                generated_token_ids=target,
                sampled_token_logprobs=sampled,
                replayed_token_logprobs=replayed.cpu().tolist(),
                actual_eos_included=target[-1] in eos,
                max_absolute_logprob_difference=float(discrepancy.max()),
                passed=passed,
                gradient_finite=all(bool(torch.isfinite(v).all()) for v in gradient.values()),
                gradient_digest=tensor_digest(gradient),
                gradient_is_not_reward_feedback=True,
                actual_model_generate_calls=1,
                SFT_mask_used=False,
                length_normalized=False,
                same_virtual_parameter_digest=tensor_digest(theta),
                EOS_forced=False,
            )
            p.write_once(out / "cases" / (str(index) + ".json"), case)
            cases.append(
                {
                    key: case[key]
                    for key in (
                        "id",
                        "context",
                        "max_absolute_logprob_difference",
                        "passed",
                        "gradient_finite",
                        "actual_eos_included",
                    )
                }
            )
            p.require(passed, "anchored_gpu.replayed_sampling_probabilities_mismatch")
            p.require(case["gradient_finite"], "anchored_gpu.finite_replayed_logprob_gradient")
        stage = "isolation"
        adam._verify(bound)
        unchanged = (
            storage_versions(model) == initial_storage
            and tensor_digest(names) == initial_digest
            and all(value.grad is None for value in names.values())
            and not optimizer.state
            and [module.training for module in model.modules()] == initial_modes
            and rng_digest() == initial_rng
        )
        p.require(unchanged, "anchored_gpu.real_model_optimizer_grad_mode_or_RNG_changed")
    except BaseException as failure:
        import traceback

        traceback.print_exc()
        error = dict(stage=stage, type=type(failure).__name__, message=str(failure))
        if model is not None and "initial_storage" in locals():
            unchanged = (
                storage_versions(model) == initial_storage
                and tensor_digest(names) == initial_digest
                and all(value.grad is None for value in names.values())
                and not optimizer.state
                and [module.training for module in model.modules()] == initial_modes
                and rng_digest() == initial_rng
            )
    report = p.record(
        "anchored_sources_gpu_gate_report",
        plan_id=plan["id"],
        status="PASS_AS_SCOPED_GPU_NUMERIC_GATE" if error is None else "BLOCKED_GPU_NUMERIC_GATE",
        passed=error is None,
        completed_contexts=len(cases),
        cases=cases,
        error=error,
        actual_Qwen_loaded=model is not None,
        actual_original_package_gradient_computed=virtual_id is not None,
        real_state_unchanged=unchanged,
        virtual_step_id=virtual_id,
        actual_full_feedback_rounds=0,
        actual_anchored_training_runs=0,
        full_A_launcher_admitted=False,
        no_parameter_probability_reward_or_tolerance_repair=True,
        peak_reserved_bytes=torch.cuda.max_memory_reserved() if model is not None else None,
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
    result = prepare(args.root) if args.mode == "prepare" else run(args.root)
    print(json.dumps({key: result[key] for key in ("id", "status") if key in result}))
