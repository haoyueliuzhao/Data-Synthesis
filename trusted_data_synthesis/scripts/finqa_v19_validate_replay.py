"""Deferred CUDA equivalence/timing gate on existing sealed tokens, never a new rollout."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from pathlib import Path

from finqa_v19_execution_profile import ROOT, checked_profile, file_ref, read_file
from finqa_v19_optimized_replay import ReplaySession, legacy

from trusted_synthesis.finance_research.calibration import gpu_inventory, now
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.providers import parameter_digest
from trusted_synthesis.finance_research.v6_collection import bound, persist, require
from trusted_synthesis.finance_research.v8_training_driver import (
    _rng,
    _tree_digest,
    installed_point,
)
from trusted_synthesis.finance_research.v9_training_launcher import _load_components, eligible_gpu
from trusted_synthesis.finance_research.v13_material_registration import read_ref


def run(root=ROOT, *, gpu_index):
    import torch
    from torch.nn.attention import SDPBackend, sdpa_kernel

    from trusted_synthesis.finance_research.v9_mechanism_execution import checked_outer

    root = Path(root).resolve()
    profile = checked_profile(root)
    require(
        gpu_index in profile["allowed_gpu_indices"],
        "validation is restricted to the same four GPUs",
    )
    output = root / "validation"
    require(
        not (output / "result/record.json").exists(), "never silently repeat the CUDA acceptance"
    )
    require(
        not (output / "attempt/intent/record.json").exists(),
        "failed validation needs explicit inspection",
    )
    plan = read_ref(profile["original_launcher"])
    assets = read_file(plan["assets_protocol"])
    require(assets["id"] == plan["assets_protocol_id"], "original model assets changed")
    source = Path(profile["validation"]["required_completed_outer"])
    require(
        (source / "outer_inputs.pt").is_file(),
        "original completed first outer must exist before validation",
    )
    outer_record, _state, actual = checked_outer(source)
    require(
        actual["point_id"] == profile["validation"]["expected_point_id"]
        and parameter_digest(actual["theta_bar"])
        == profile["validation"]["expected_parameter_digest"],
        "validation cannot choose another actual virtual point",
    )
    row = eligible_gpu(plan, gpu_index, gpu_inventory())
    locks = Path(profile["original_launcher"]["path"]).parents[1] / "locks"
    with (locks / ("gpu-" + digest(row["uuid"]) + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = eligible_gpu(plan, gpu_index, gpu_inventory())
        require(
            current["uuid"] == row["uuid"] and not torch.cuda.is_initialized(),
            "fresh validation process and unchanged free GPU required",
        )
        os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        persist(
            output / "attempt/intent",
            bound(
                dict(
                    schema="v19_existing_token_CUDA_validation_intent.v1",
                    at=now(),
                    execution_profile_id=profile["id"],
                    pid=os.getpid(),
                    gpu_observed=current,
                    source_outer=file_ref(source / "record.json"),
                    source_outer_state_sha=outer_record["state_sha256"],
                    no_new_rollouts=True,
                    no_optimizer_steps=True,
                    baseline_then_optimized_order=True,
                )
            ),
        )
        components = None
        session = None
        try:
            components = _load_components(assets, 11)
            model, _tokenizer, optimizer, _scope, _fresh = components
            with torch.no_grad():
                buffers = dict(model.named_buffers())
                for name, value in actual["pre_state"]["buffers"].items():
                    buffers[name].copy_(value)
            theta = {name: value.to("cuda:0") for name, value in actual["theta_bar"].items()}
            cases = []
            for selected in profile["validation"]["cases"]:
                episode = read_file(selected["episode"])
                receipt = episode["turns"][selected["turn_index"]]["receipt"]
                require(
                    digest(receipt) == selected["receipt_sha256"]
                    and receipt["identity"]["parameter_digest"] == parameter_digest(theta),
                    "same original tokens and parameter point required",
                )
                cases.append((selected, receipt))
            reports = []
            with installed_point(model, theta) as installed:
                before_rng = _tree_digest(_rng())
                before_parameters = parameter_digest(installed)
                before_buffers = _tree_digest(dict(model.named_buffers()))
                modes = [m.training for m in model.modules()]
                baseline = []
                for selected, receipt in cases:
                    torch.cuda.reset_peak_memory_stats()
                    torch.cuda.synchronize()
                    started = time.monotonic()
                    with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                        values, gradient, accounting = legacy.segmented_logp(
                            model,
                            installed,
                            receipt["prompt_input_ids"],
                            receipt["raw_generated_token_ids"],
                            expected=receipt["sampled_token_logprobs"],
                            block_size=8,
                            prefill_checkpoint=True,
                            offload=True,
                        )
                    torch.cuda.synchronize()
                    elapsed = time.monotonic() - started
                    baseline.append(
                        (values.detach().cpu(), {k: v.detach().cpu() for k, v in gradient.items()})
                    )
                    reports.append(
                        dict(
                            case=selected,
                            baseline_seconds=elapsed,
                            baseline_peak_allocated=torch.cuda.max_memory_allocated(),
                            baseline_gradient_digest=parameter_digest(gradient),
                            output_tokens=accounting["output_tokens"],
                            baseline_storage_accounting=accounting,
                        )
                    )
                    del values, gradient
                session = ReplaySession(model, installed, profile_id=profile["id"])
                for index, (_selected, receipt) in enumerate(cases):
                    torch.cuda.reset_peak_memory_stats()
                    torch.cuda.synchronize()
                    started = time.monotonic()
                    with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                        values, gradient, accounting = session(
                            model,
                            installed,
                            receipt["prompt_input_ids"],
                            receipt["raw_generated_token_ids"],
                            expected=receipt["sampled_token_logprobs"],
                            block_size=8,
                        )
                    torch.cuda.synchronize()
                    elapsed = time.monotonic() - started
                    old_values, old_gradient = baseline[index]
                    equal_values = _tree_digest(values.cpu()) == _tree_digest(old_values)
                    optimized_digest = parameter_digest(gradient)
                    equal_gradient = optimized_digest == reports[index]["baseline_gradient_digest"]
                    reports[index].update(
                        optimized_seconds=elapsed,
                        optimized_peak_allocated=torch.cuda.max_memory_allocated(),
                        optimized_gradient_digest=optimized_digest,
                        logp_bitwise_equal=equal_values,
                        gradient_bitwise_equal=equal_gradient,
                        same_shape_dtype_keys=(
                            set(gradient) == set(old_gradient)
                            and all(
                                value.shape == old_gradient[name].shape
                                and value.dtype == old_gradient[name].dtype
                                for name, value in gradient.items()
                            )
                        ),
                        storage_accounting=accounting,
                    )
                    persist(
                        output / "cases" / f"case{index:02d}",
                        bound(
                            dict(
                                schema="v19_paired_replay_case.v1",
                                execution_profile_id=profile["id"],
                                **reports[index],
                            )
                        ),
                    )
                    del values, gradient
                session.close()
                session = None
                unchanged = (
                    parameter_digest(installed) == before_parameters
                    and _tree_digest(_rng()) == before_rng
                    and _tree_digest(dict(model.named_buffers())) == before_buffers
                    and [m.training for m in model.modules()] == modes
                    and not optimizer.state
                )
            baseline_time = sum(r["baseline_seconds"] for r in reports)
            optimized_time = sum(r["optimized_seconds"] for r in reports)
            ratio = optimized_time / baseline_time
            equal = all(
                r["logp_bitwise_equal"]
                and r["gradient_bitwise_equal"]
                and r["same_shape_dtype_keys"]
                for r in reports
            )
            residency_exercised = any(
                r["storage_accounting"]["peak_resident_saved_KV_bytes"] > 0 for r in reports
            )
            admitted = (
                equal
                and unchanged
                and residency_exercised
                and ratio <= profile["validation"]["maximum_optimized_time_ratio"]
            )
            result = bound(
                dict(
                    schema="v19_actual_replay_CUDA_validation.v1",
                    at=now(),
                    execution_profile_id=profile["id"],
                    admitted=admitted,
                    all_cases_bitwise_equal=equal,
                    actual_point_model_RNG_buffers_unchanged=unchanged,
                    production_CUDA_measured=True,
                    saved_KV_residency_exercised=residency_exercised,
                    gpu_index=gpu_index,
                    baseline_total_seconds=baseline_time,
                    optimized_total_seconds=optimized_time,
                    optimized_over_baseline=ratio,
                    case_count=len(cases),
                    report_scope=(
                        "four existing responses; not a full700 benchmark "
                        "or universal memory guarantee"
                    ),
                    new_generation_calls=0,
                    optimizer_steps=0,
                    API_calls=0,
                )
            )
            persist(output / "result", result)
            require(
                admitted,
                "optimized CUDA equivalence/performance gate failed; no fallback or resampling",
            )
            return result
        except BaseException as error:
            if session is not None:
                try:
                    session.close(aborted=True)
                except Exception as cleanup:
                    error.add_note(f"validation cleanup: {cleanup}")
            try:
                persist(
                    output / "attempt/failure",
                    bound(
                        dict(
                            schema="v19_validation_failure.v1",
                            at=now(),
                            execution_profile_id=profile["id"],
                            error_type=type(error).__name__,
                            error=str(error),
                            no_automatic_retry=True,
                            new_feedback_generated=False,
                        )
                    ),
                )
            except Exception as recording:
                error.add_note(f"validation failure recording: {recording}")
            raise
        finally:
            if components is not None:
                del components
            if torch.cuda.is_initialized():
                torch.cuda.empty_cache()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--gpu-index", type=int, choices=(1, 2, 3, 6), required=True)
    args = parser.parse_args()
    print(json.dumps(dict(id=run(args.root, gpu_index=args.gpu_index)["id"])))
